const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const assets = path.join(__dirname, "../src/prompt_hub/web_assets");
function storage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key),
  };
}

function navigation(initialUrl, local = storage(), session = storage()) {
  const listeners = {};
  const frames = [];
  const history = [];
  const window = {
    location: new URL(initialUrl), scrollY: 0,
    addEventListener: (event, callback) => { listeners[event] = callback; },
    history: {
      scrollRestoration: "auto",
      pushState: (state, _, url) => { history.push(state); window.location = new URL(url); },
      replaceState: (state, _, url) => { history[history.length - 1] = state; window.location = new URL(url); },
    },
    scrollTo: ({top}) => { window.scrollY = top; },
  };
  const context = {window, localStorage: local, sessionStorage: session, URL, URLSearchParams,
    requestAnimationFrame: callback => frames.push(callback), setTimeout, clearTimeout};
  vm.runInNewContext(fs.readFileSync(path.join(assets, "navigation.js"), "utf8"), context);
  return {
    window, listeners, history, nav: window.PromptHubNavigation,
    frame: () => { while (frames.length) frames.shift()(); },
  };
}

test("query route wins over a previously saved homepage", () => {
  const app = navigation("http://localhost/?view=studio&project=p1&step=caption",
    storage({"soda-prompt-hub-route-v1":'{"view":"home"}'}));
  assert.equal(app.nav.read().project, "p1");
  assert.equal(app.nav.read().step, "caption");
});

test("standalone tagger route keeps its project across refresh", () => {
  const app = navigation("http://localhost/?view=tagger&project=p1");
  assert.equal(app.nav.read().view, "tagger");
  assert.equal(app.nav.read().project, "p1");
  app.nav.commit({view:"tagger",project:"p2"});
  const refreshed = navigation(app.window.location.href);
  assert.equal(refreshed.nav.read().view, "tagger");
  assert.equal(refreshed.nav.read().project, "p2");
});

test("tagger exit waits for saving before returning to the Hub", async () => {
  const source = fs.readFileSync(path.join(assets, "workbench.js"), "utf8");
  const handler = source.slice(source.indexOf("  async function returnToHubHome()"), source.indexOf("  function hideScreens()"));
  const calls = [];
  let finishSave;
  const context = {
    window: {
      SodaStudio: {save: () => new Promise(resolve => { finishSave = resolve; })},
      setPromptHubView: async view => calls.push(view),
    },
    message: () => assert.fail("Successful exit must not show an error"),
  };
  vm.runInNewContext(handler, context);
  const exiting = context.returnToHubHome();
  assert.deepEqual(calls, []);
  finishSave();
  await exiting;
  assert.deepEqual(calls, ["home"]);
});

test("a failed save keeps the tagger open and reports the error", async () => {
  const source = fs.readFileSync(path.join(assets, "workbench.js"), "utf8");
  const handler = source.slice(source.indexOf("  async function returnToHubHome()"), source.indexOf("  function hideScreens()"));
  const messages = [];
  const context = {
    window: {
      SodaStudio: {save: async () => { throw new Error("Save failed"); }},
      setPromptHubView: () => assert.fail("Failed save must not navigate"),
    },
    message: (text, error) => messages.push({text, error}),
  };
  vm.runInNewContext(handler, context);
  await context.returnToHubHome();
  assert.deepEqual(messages, [{text: "Save failed", error: true}]);
});

test("chat model manager retains its subpage on refresh and history navigation", () => {
  const first = navigation("http://localhost/?view=settings");
  first.nav.commit({view: "remote", tab: "endpoints"});
  const refreshed = navigation(first.window.location.href);
  assert.equal(refreshed.nav.read().view, "remote");
  assert.equal(refreshed.nav.read().tab, "endpoints");
  refreshed.nav.commit({view: "remote", tab: "tasks"});
  assert.equal(refreshed.nav.current().tab, "tasks");
});

test("opening chat connections carries an explicit endpoint route", () => {
  const source = fs.readFileSync(path.join(assets, "../remote_web.py"), "utf8");
  let observed;
  const context = {window: {setPromptHubView: (view, options) => {observed = {view, options};}}};
  vm.runInNewContext(source.split('\n').find(line => line.includes('window.openModelEndpoints=')), context);
  context.window.openModelEndpoints();
  assert.equal(observed.view, 'remote');
  assert.equal(observed.options.route.tab, 'endpoints');
});

test("dataset project list is a separate refreshable route from original home", () => {
  const app = navigation("http://localhost/?view=projects");
  assert.equal(app.nav.read().view, "projects");
  app.nav.commit({view:"home"}); app.nav.restore({view:"home"}); app.frame();
  assert.equal(app.nav.current().view,"home");
});

test("refresh restores project, subpage and scroll position", () => {
  const local = storage(), session = storage();
  const first = navigation("http://localhost/?view=studio&project=p1&step=generate", local, session);
  first.nav.commit(first.nav.read(), "replace");
  first.nav.restore(first.nav.current()); first.frame();
  first.window.scrollY = 1193; first.listeners.pagehide();
  const second = navigation(first.window.location.href, local, session);
  second.nav.commit(second.nav.read(), "replace");
  second.nav.restore(second.nav.current()); second.frame();
  assert.equal(second.window.scrollY, 1193);
  assert.equal(second.nav.current().step, "generate");
});

test("same navigation button preserves scroll and does not push duplicate history", () => {
  const app = navigation("http://localhost/?view=studio&project=p1&step=generate");
  app.nav.commit(app.nav.read(), "replace"); app.nav.restore(app.nav.current()); app.frame();
  app.window.scrollY = 980;
  app.nav.commit(app.nav.current()); app.nav.restore(app.nav.current()); app.frame();
  assert.equal(app.window.scrollY, 980);
  assert.equal(app.history.length, 0);
});

test("slow loading cannot overwrite the destination scroll position", () => {
  const app = navigation("http://localhost/?view=studio&project=p1&step=generate");
  const generate = app.nav.read(), caption = {...generate, step:"caption"};
  app.nav.commit(caption); app.nav.restore(caption); app.frame();
  app.window.scrollY = 435;
  app.nav.commit(generate); app.nav.restore(generate); app.frame();
  app.nav.commit(caption);
  app.window.scrollY = 0; app.nav.capture();
  app.nav.restore(caption); app.frame();
  assert.equal(app.window.scrollY, 435);
});

test("stale async restoration cannot scroll a newer route", () => {
  const app = navigation("http://localhost/?view=home");
  app.nav.commit({view:"home"}); app.nav.restore({view:"home"});
  app.nav.commit({view:"settings"}); app.window.scrollY = 720;
  app.frame();
  assert.equal(app.window.scrollY, 720);
});

test("back and forward use URL route and do not create another history entry", () => {
  const app = navigation("http://localhost/?view=home");
  let observed;
  app.window.setPromptHubView = (view, options) => { observed = {view, options}; };
  app.window.location = new URL("http://localhost/?view=studio&project=p2&step=review");
  app.listeners.popstate();
  assert.equal(observed.options.route.project, "p2");
  assert.equal(observed.options.route.step, "review");
  assert.equal(observed.options.historyMode, "none");
});

function studio(fetch) {
  const nodes = new Map();
  const document = {
    querySelector: selector => {
      if (!nodes.has(selector)) nodes.set(selector, {textContent:"",innerHTML:"",dataset:{}});
      return nodes.get(selector);
    },
    querySelectorAll: () => [],
    addEventListener: () => {},
  };
  const window = {};
  const localStorage = storage();
  const context = {window, document, localStorage, sessionStorage: storage(), structuredClone,
    fetch, File:class File {}, setTimeout, clearTimeout, setInterval:() => {}, URLSearchParams};
  let source = fs.readFileSync(path.join(assets, "studio.js"), "utf8");
  source = source.replace('  document.addEventListener("DOMContentLoaded", () => {',
    '  window.testStudio = {state, markChanged, saveCurrent, persistCaptionDraft, renderCaptionEditor, previewBatch, generationProgress};\n  document.addEventListener("DOMContentLoaded", () => {');
  vm.runInNewContext(source, context);
  window.testStudio.state.project = {
    project_id:"project-1", revision:3,
    studio:{body:"original",backend:"comfyui",locks:{},locked_values:{}},
  };
  return {...window.testStudio, nodes, document, localStorage};
}

test("generation progress distinguishes queued, active, complete, and failed jobs", () => {
  const app = studio();
  const queued = app.generationProgress([{status:"queued"}]);
  assert.equal(queued.label, "排隊中，尚未出圖");
  assert.equal(queued.value, 0);

  const running = app.generationProgress([{status:"running",progress_current:0,progress_total:1}]);
  assert.equal(running.label, "正在出圖");
  assert.equal(running.value, null);

  const batch = app.generationProgress([{status:"completed"},{status:"running",progress_current:0,progress_total:1}]);
  assert.equal(batch.value, 50);

  const completed = app.generationProgress([{status:"completed"}]);
  assert.equal(completed.label, "已出圖，圖片已加入畫廊");
  assert.equal(completed.value, 100);

  const failed = app.generationProgress([{status:"failed",error:"provider unavailable"}]);
  assert.equal(failed.label, "出圖失敗");
  assert.equal(failed.value, 0);
});

test("typing creates a synchronous draft before the debounce can run", async () => {
  const app = studio(async () => ({ok:true,json:async () => ({revision:4})}));
  app.state.project.studio.body = "edited immediately before refresh";
  app.markChanged();
  const saved = JSON.parse(app.localStorage.getItem("soda-studio-draft-project-1"));
  assert.equal(saved.studio.body, "edited immediately before refresh");
  assert.equal(saved.revision, 3);
  await app.saveCurrent();
});

test("overlapping saves are serialized and preserve edits made during a request", async () => {
  const pending = [], bodies = [];
  const app = studio((url, options) => new Promise(resolve => {
    bodies.push(JSON.parse(options.body));
    pending.push(() => resolve({ok:true,json:async () => ({revision:3 + bodies.length})}));
  }));
  app.markChanged();
  const first = app.saveCurrent();
  app.state.project.studio.body = "newer text";
  app.markChanged();
  pending.shift()(); await new Promise(resolve => setImmediate(resolve));
  assert.equal(bodies.length, 2);
  assert.equal(bodies[1].expected_revision, 4);
  assert.equal(bodies[1].studio.body, "newer text");
  pending.shift()(); await first;
  assert.equal(app.localStorage.getItem("soda-studio-draft-project-1"), null);
});

test("failed save retains the local draft for recovery", async () => {
  const app = studio(async () => ({ok:false,status:409,json:async () => ({detail:"revision conflict"})}));
  app.markChanged();
  await assert.rejects(app.saveCurrent(), /revision conflict/);
  assert.ok(app.localStorage.getItem("soda-studio-draft-project-1"));
  assert.equal(app.state.dirty, true);
});

test("caption typing preserves every field and confirmation per image", () => {
  const app = studio();
  const form = {elements:{
    long:{value:"long draft"},medium:{value:"medium draft"},short:{value:"short draft"},
    json:{value:'{"regions":[]}'},confirmed:{checked:true},
  }};
  app.nodes.set("#studioCaptionForm", form);
  app.state.selectedImage = "image-1";
  app.state.images = [{item_id:"image-1",updated_at:"version-1"}];
  app.persistCaptionDraft();
  const saved = JSON.parse(app.localStorage.getItem("soda-studio-caption-project-1-image-1"));
  assert.equal(saved.long, "long draft");
  assert.equal(saved.json, '{"regions":[]}');
  assert.equal(saved.confirmed, true);
});

function theme(saved, darkSystem = false) {
  const localStorage = storage(saved ? {"soda-prompt-hub-theme-v1":saved} : {});
  const listeners = {}, systemListeners = {};
  const selects = [{value:""},{value:""}];
  const document = {
    documentElement:{dataset:{}},
    querySelectorAll: () => selects,
    addEventListener: (name, callback) => { listeners[name] = callback; },
  };
  const system = {matches:darkSystem,addEventListener:(name,callback) => { systemListeners[name] = callback; }};
  const window = {
    matchMedia: () => system,
    addEventListener: (name, callback) => { listeners[name] = callback; },
    location:{reload:() => assert.fail("Theme change must not reload the document")},
  };
  vm.runInNewContext(fs.readFileSync(path.join(assets,"theme.js"),"utf8"),{window,document,localStorage});
  return {document,selects,system,systemListeners,listeners,localStorage};
}

test("dark theme is applied in the head before the first page render", () => {
  const app = theme();
  assert.equal(app.document.documentElement.dataset.theme,"dark");
  assert.equal(app.selects[0].value,"dark");
});

test("manual light selection persists through refresh without changing route", () => {
  const app = theme();
  app.listeners.change({target:{matches:() => true,value:"light"}});
  assert.equal(app.localStorage.getItem("soda-prompt-hub-theme-v1"),"light");
  assert.equal(app.selects[1].value,"light");
  assert.equal(theme("light").document.documentElement.dataset.theme,"light");
});

test("system preference responds to OS changes and preserves manual dark", () => {
  const app = theme("system",false);
  assert.equal(app.document.documentElement.dataset.theme,"light");
  app.system.matches = true; app.systemListeners.change();
  assert.equal(app.document.documentElement.dataset.theme,"dark");
  app.listeners.change({target:{matches:() => true,value:"dark"}});
  app.system.matches = false; app.systemListeners.change();
  assert.equal(app.document.documentElement.dataset.theme,"dark");
});

test("appearance stays synchronized between open pages", () => {
  const app = theme();
  app.listeners.storage({key:"soda-prompt-hub-theme-v1",newValue:"light"});
  assert.equal(app.document.documentElement.dataset.theme,"light");
  assert.equal(app.selects[0].value,"light");
});

function palette(dark) {
  const tokens = {};
  for (const name of ["base.css", "studio.css", "theme.css"]) {
    const css = fs.readFileSync(path.join(assets, name), "utf8");
    const blocks = [...css.matchAll(/:root\s*\{([^}]+)\}/g)].map(match => match[1]);
    if (dark) blocks.push(...[...css.matchAll(/html\[data-theme="dark"\]\s*\{([^}]+)\}/g)].map(match => match[1]));
    for (const block of blocks) {
      for (const match of block.matchAll(/(--[\w-]+):\s*(#[\da-f]{6})\s*;/gi)) tokens[match[1]] = match[2];
    }
  }
  return tokens;
}

function contrast(foreground, background) {
  function luminance(hex) {
    const channels = hex.slice(1).match(/../g).map(channel => {
      const value = Number.parseInt(channel, 16) / 255;
      return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
    });
    return channels.reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
  }
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (values[0] + .05) / (values[1] + .05);
}

for (const dark of [false, true]) {
  test(`${dark ? "dark" : "light"} palette keeps text, fields and selected actions above 4.5:1`, () => {
    const tokens = palette(dark);
    for (const [foreground, background] of [
      ["--ink", "--paper"], ["--muted", "--paper-deep"], ["--muted", "--field-bg"],
      ["--on-acid", "--acid"], ["--on-signal", "--signal-fill"],
      ["--inverse-text", "--inverse-bg"], ["--inverse-muted", "--inverse-bg"],
      ["--studio-muted", "--studio-paper"],
    ]) {
      const ratio = contrast(tokens[foreground], tokens[background]);
      assert.ok(ratio >= 4.5, `${foreground} on ${background} has contrast ${ratio.toFixed(2)}`);
    }
  });
}

test("legacy panel backgrounds keep their own inverse and action tokens", () => {
  const files = [
    ...["base.css", "creative.css", "gallery.css", "optional_models.css"].map(name => path.join(assets, name)),
    ...["search", "workspace", "lora", "comfy", "remote", "source_center"].map(name => path.join(assets, `../${name}_web.py`)),
  ];
  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    assert.doesNotMatch(source, /background(?:-color)?:\s*var\(--(?:ink|signal)\)/, file);
    assert.doesNotMatch(source, /font(?:-size)?:[^;{}\n]*\b(?:[6-9]|1[0-2])px\b/, file);
  }
});

test("dataset preview growth keeps browser scroll anchoring disabled inside its page", () => {
  const css = fs.readFileSync(path.join(assets, "studio.css"), "utf8");
  assert.match(css, /\.studio-page\s*\{\s*overflow-anchor:\s*none;\s*\}/);
});

for (const [locale, title, count, preview] of [
  ["zh-CN", "数据集生成", "MOSS · 3 张图片 · 2 张已采用", "已准备 6 组提示词。"],
  ["zh-TW", "資料集生成", "MOSS · 3 張圖片 · 2 張已採用", "已準備 6 組提示詞。"],
  ["en", "Dataset generation", "MOSS · 3 images · 2 selected", "6 prompts prepared."],
]) {
  test(`dataset studio uses the shared ${locale} locale for static and dynamic messages`, () => {
    const context = {
      window: {}, navigator: {language: locale},
      document: {documentElement: {}, addEventListener: () => {}},
      localStorage: storage({"soda-prompt-hub-ui-language": locale}),
    };
    vm.createContext(context);
    for (const name of ["workbench_i18n.js", "studio_i18n.js", "i18n.js"]) {
      vm.runInContext(fs.readFileSync(path.join(assets, name), "utf8"), context);
    }
    const t = context.window.promptHubI18n.t;
    assert.equal(context.window.promptHubI18n.getLocale(), locale);
    assert.equal(t("資料集生成"), title);
    assert.equal(t("MOSS · 3 張圖片 · 2 張已採用"), count);
    assert.equal(t("已準備 6 組提示詞。"), preview);
    assert.equal(t("返回主界面"), {"zh-CN":"返回主界面", "zh-TW":"返回主介面", en:"Back to Hub"}[locale]);
    assert.equal(t(t("資料集生成")), title);
    assert.equal(t("1girl, solo, __pose/standing__"), "1girl, solo, __pose/standing__");
    assert.equal(t("https://example.test/v1"), "https://example.test/v1");
  });
}


test("creation engine survives refresh independently of dataset routes", () => {
  const app=navigation("http://localhost/?view=creative&engine=novelai&project=draft-nai");
  assert.equal(app.nav.read().engine,"novelai");
  app.nav.commit(app.nav.read(),"replace");app.nav.restore(app.nav.current());app.frame();
  const restored=navigation(app.window.location.href);
  assert.equal(restored.nav.read().project,"draft-nai");
  assert.equal(restored.nav.read().engine,"novelai");
});

test("gallery detail route updates preserve scroll capture", () => {
  const app=navigation("http://localhost/?view=gallery&tab=local");
  app.nav.commit(app.nav.read(),"replace");app.nav.restore(app.nav.current());app.frame();
  app.window.scrollY=800;
  app.nav.commit({...app.nav.current(),asset:"asset-one"},"replace",{preserveScroll:true});
  app.window.scrollY=850;app.nav.capture();
  app.nav.restore(app.nav.current());app.frame();
  assert.equal(app.window.scrollY,850);
  assert.equal(app.nav.current().asset,"asset-one");
});

test("online gallery tab is restored from its explicit URL", () => {
  const app=navigation("http://localhost/?view=gallery&tab=online");
  assert.equal(app.nav.read().tab,"online");
  assert.equal(app.nav.read().view,"gallery");
});

test("launcher quality and UC presets follow the selected model and preserve user text", () => {
  const context = {window: {}};
  vm.runInNewContext(fs.readFileSync(path.join(assets, "novelai_presets.js"), "utf8"), context);
  const presets = context.window.SodaNaiPresets;
  assert.equal(presets.quality("nai-diffusion-5-full", "light"), "very aesthetic, amazing quality, no text");
  assert.equal(presets.quality("nai-diffusion-4-5-full", "standard"), "location, very aesthetic, masterpiece, no text");
  assert.match(presets.negative("nai-diffusion-5-full", "light"), /0::ai-generated::/);
  assert.doesNotMatch(presets.negative("nai-diffusion-4-5-full", "light"), /0::ai-generated::/);
  const heavy = presets.negative("nai-diffusion-5-full", "heavy");
  const light = presets.negative("nai-diffusion-5-full", "light");
  const manual = "-3::artist collaboration::, watermark";
  assert.equal(presets.replace(heavy + ", " + manual, heavy, light, true), light + ", " + manual);
  assert.equal(presets.replace(manual, heavy, "", true), manual);
  assert.equal(presets.replace(light + ", " + manual, light, "", true), manual);
  assert.equal(presets.replace("signature, no text", "", "no text", false), "signature, no text");
});

test("typing into the canvas seed updates the inputs saved in the recipe immediately", () => {
  const source = fs.readFileSync(path.join(assets, "creation_canvas.js"), "utf8");
  const start = source.indexOf("  function updateSeed(event) {");
  const end = source.indexOf('  $("#creationSeed").addEventListener', start);
  const saved = {seed: 1, seed_mode: "increment"};
  const errors = [];
  const fields = {};
  for (const name of ["seed", "seed_mode"]) {
    fields[`[data-recipe="${name}"]`] = {
      value: saved[name],
      dispatchEvent(event) { assert.equal(event.type, "input"); saved[name] = this.value; },
    };
  }
  fields["#creationSeedLock"] = {setAttribute() {}, innerHTML: ""};
  const context = {
    $: selector => fields[selector], state: {engine: "novelai"}, recipe: () => saved,
    icon: value => value, translate: value => value, showError: error => errors.push(error),
    Event: class {constructor(type) {this.type = type;}},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(start, end), context);
  const input = {value: "123456"};
  context.updateSeed({type: "input", target: input});
  assert.equal(Number(saved.seed), 123456);
  assert.equal(saved.seed_mode, "fixed");
  input.value = "";
  context.updateSeed({type: "input", target: input});
  assert.equal(saved.seed_mode, "random");
  assert.equal(Number(saved.seed), 123456);
  input.value = String(2 ** 32);
  context.updateSeed({type: "change", target: input});
  assert.equal(errors.length, 1);
  assert.equal(Number(saved.seed), 123456);
});

test("gallery detail loading hides the previous image and its actions", () => {
  const source = fs.readFileSync(path.join(assets, "online_gallery_viewer.js"), "utf8");
  const fields = {};
  const layout = {hidden: false};
  const state = {item: {id: "previous"}, media: [{url: "previous.png"}]};
  const nodes = {
    onlineFavorite: {disabled: false},
    onlineSourceLink: {removeAttribute(name) {this.removed = name;}},
  };
  const context = {
    state, nodes, translate: value => value,
    $: selector => fields[selector] ||= {},
    dialog: {setAttribute() {}, querySelector: () => layout},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  function loading("), source.indexOf("  function show(")), context);
  context.loading();
  assert.equal(layout.hidden, true);
  assert.equal(state.item, null);
  assert.equal(state.media.length, 0);
  assert.equal(nodes.onlineFavorite.disabled, true);
  assert.equal(nodes.onlineSourceLink.removed, "href");
  assert.equal(fields["#onlineByline"].textContent, "");
  assert.equal(fields["#onlineViewerLoading"].hidden, false);
});

test("a slow gallery detail cannot overwrite a newer inspected work", async () => {
  const source = fs.readFileSync(path.join(assets, "online_gallery.js"), "utf8");
  const fields = {};
  const pending = [];
  const displayed = [];
  let loadingCount = 0;
  const context = {
    state: {detailRun: 0}, mediaUrl: value => value,
    refreshRemoteFavorite: async () => {},
    $: selector => fields[selector] ||= {removeAttribute() {}},
    dialog: {open: false, showModal() {this.open = true;}},
    api: () => new Promise(resolve => pending.push(resolve)),
    window: {SodaOnlineViewer: {loading() {loadingCount++;}, show: item => displayed.push(item.id)}},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  async function inspect("), source.indexOf("  async function loadAccount(")), context);
  const first = context.inspect({id: "first", source: "aitag", title: "First"});
  const second = context.inspect({id: "second", source: "aitag", title: "Second"});
  assert.equal(loadingCount, 2);
  pending[1]({id: "second", title: "Second", prompt: "second prompt", media: []});
  await second;
  pending[0]({id: "first", title: "First", prompt: "first prompt", media: []});
  await first;
  assert.deepEqual(displayed, ["second"]);
  assert.equal(context.state.active.id, "second");
  assert.equal(fields["#onlinePrompt"].textContent, "second prompt");
});

test("adding a character preserves the global prompt and enforces the six-character limit", () => {
  const source = fs.readFileSync(path.join(assets, "novelai_characters.js"), "utf8");
  const saved = {body: "garden, watercolor", characters: []};
  const context = {
    recipe: () => saved, state: {}, section: {}, t: value => value,
    crypto: {randomUUID: () => String(saved.characters.length)},
    $: () => ({}), persistCharacters: values => {saved.characters = values;},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  function addCharacter("), source.indexOf("  function editor(")), context);
  for (let index = 0; index < 6; index++) assert.equal(context.addCharacter({gender: "female", prompt: "girl,"}), true);
  assert.equal(context.addCharacter({prompt: "boy,"}), false);
  assert.equal(saved.body, "garden, watercolor");
  assert.equal(saved.characters.length, 6);
});

test("editing a replaced character card does not trigger outside-click collapse", () => {
  const source = fs.readFileSync(path.join(assets, "novelai_characters.js"), "utf8");
  const section = {};
  const state = {selected: "character-one"};
  let handler;
  let renders = 0;
  const context = {
    state, section, render: () => {renders++;}, window: {},
    document: {addEventListener: (_name, callback) => {handler = callback;}, querySelectorAll: () => []},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('  document.addEventListener("click"'), source.indexOf('  $("#naiClosePositions")')), context);
  handler({target: {closest: () => null}, composedPath: () => [section]});
  assert.equal(state.selected, "character-one");
  assert.equal(renders, 0);
  handler({target: {closest: () => null}, composedPath: () => []});
  assert.equal(state.selected, "");
  assert.equal(renders, 1);
});

test("position markers number only enabled characters while retaining their saved indices", () => {
  const source = fs.readFileSync(path.join(assets, "novelai_characters.js"), "utf8");
  const fields = {};
  const context = {
    recipe: () => ({width: 1216, height: 832, characters: [
      {name: "Disabled", enabled: false}, {name: "First", enabled: true}, {name: "Second"},
    ]}),
    state: {}, t: value => value, escape: value => value, gender: () => "other", key: (_character, index) => index,
    $: selector => fields[selector] ||= {style: {setProperty() {}}},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  function renderPositions("), source.indexOf("  async function saveToLibrary(")), context);
  context.renderPositions();
  const markers = fields["#naiPositionBoard"].innerHTML;
  assert.doesNotMatch(markers, /data-position-character="0"/);
  assert.match(markers, /data-position-character="1"[^>]*><span>1<\/span><\/button>/);
  assert.match(markers, /data-position-character="2"[^>]*><span>2<\/span><\/button>/);
});

test("NovelAI login modes submit only their active credentials and reset secret visibility", () => {
  const source = fs.readFileSync(path.join(assets, "novelai_account.js"), "utf8");
  const fields = {};
  const form = {elements: {token: {value: "test-only"}, email: {}, password: {value: "test-only"}}};
  const context = {
    state: {}, form, status() {},
    $: selector => fields[selector] ||= {},
    dialog: {querySelectorAll: () => []},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  function setMode("), source.indexOf('  $("#naiAccountButton").addEventListener')), context);
  context.setMode("credentials");
  assert.equal(form.elements.token.disabled, true);
  assert.equal(form.elements.token.required, false);
  assert.equal(form.elements.email.disabled, false);
  assert.equal(form.elements.password.required, true);
  assert.equal(form.elements.token.value, "");
  assert.equal(form.elements.password.value, "");
  assert.equal(form.elements.password.type, "password");
  context.setMode("token");
  assert.equal(form.elements.token.disabled, false);
  assert.equal(form.elements.token.required, true);
  assert.equal(form.elements.email.disabled, true);
  assert.equal(form.elements.password.disabled, true);
});

for (const switchProject of [false, true]) {
  test(`a closed NovelAI login cannot bind a late result after project switch=${switchProject}`, async () => {
    const source = fs.readFileSync(path.join(assets, "novelai_account.js"), "utf8");
    const state = {run: 0, mode: "token"};
    let activeProject = {project_id: "original"};
    let handler;
    let resolveLogin;
    let pending;
    const bindings = [];
    const context = {
      state, current: () => ({project: activeProject}), select: {value: ""},
      form: {addEventListener: (_name, callback) => {handler = callback;}},
      FormData: class {[Symbol.iterator]() {return [][Symbol.iterator]();}},
      action: callback => {pending = callback();}, status() {}, renderAccounts() {}, renderSession() {},
      api: () => new Promise(resolve => {resolveLogin = resolve;}),
      window: {SodaStudio: {reloadConnections: async () => {}, setFields: fields => bindings.push(fields), save: async () => {}}},
    };
    vm.createContext(context);
    vm.runInContext(source.slice(source.indexOf('  form.addEventListener("submit"'), source.indexOf('  $("#naiAccountRefresh").addEventListener')), context);
    handler({preventDefault() {}});
    state.run++;
    if (switchProject) activeProject = {project_id: "different"};
    resolveLogin({provider: {id: "test-account"}});
    await pending;
    assert.deepEqual(bindings, []);
  });
}

test("switching NovelAI accounts loads the new account cache before a failed refresh", async () => {
  const source = fs.readFileSync(path.join(assets, "novelai_account.js"), "utf8");
  const state = {session: {provider: {id: "old"}}};
  const provider = {id: "new", has_api_key: true};
  let handler;
  let pending;
  const calls = [];
  const context = {
    state, select: {value: "new", addEventListener: (_name, callback) => {handler = callback;}},
    current: () => ({bootstrap: {connections: {providers: [provider]}}}),
    status() {}, renderSession: value => {state.session = value;},
    action: callback => {pending = callback().catch(() => {});},
    session: async refresh => {
      calls.push(Boolean(refresh));
      if (refresh) throw Error("offline");
      state.session = {provider, subscription: {fixed_anlas: 50}};
    },
    window: {SodaStudio: {setFields() {}, reloadConnections: async () => {}}},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('  select.addEventListener("change"'), source.indexOf('  form.addEventListener("submit"')), context);
  handler();
  assert.equal(state.session.provider.id, "new");
  await pending;
  assert.deepEqual(calls, [false, true]);
  assert.equal(state.session.provider.id, "new");
  assert.equal(state.session.subscription.fixed_anlas, 50);
});

test("a slow Agent conversation cannot replace a more recently selected conversation", async () => {
  const source = fs.readFileSync(path.join(assets, "agent.js"), "utf8");
  const requests = [];
  const state = {busy: false, run: 0, polls: new Map()};
  const fields = {};
  const context = {
    state, api: () => new Promise(resolve => requests.push(resolve)),
    $: selector => fields[selector] ||= {value: "", querySelectorAll: () => []},
    localStorage: storage(), draftKey: () => "test-draft",
    renderAttachments() {}, render() {}, status() {},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  async function openChat("), source.indexOf("  async function pollChat(")), context);
  const older = context.openChat("older");
  const newer = context.openChat("newer");
  requests[1]({id: "newer", messages: []});
  await newer;
  requests[0]({id: "older", messages: []});
  await older;
  assert.equal(state.chat.id, "newer");
});

for (const remembered of [false, true]) {
  test(`Agent refresh keeps the chosen image provider with remembered=${remembered}`, async () => {
    const source = fs.readFileSync(path.join(assets, "agent.js"), "utf8");
    const fields = {};
    for (const selector of ["#agentModel", "#agentImageProvider", "#agentPackages", "#agentCatalog"]) {
      const field = {value: "", querySelectorAll: () => []};
      Object.defineProperty(field, "innerHTML", {set(markup) {this.value = /value="([^"]*)"/.exec(markup)?.[1] || "";}});
      fields[selector] = field;
    }
    fields["#agentImageProvider"].value = remembered ? "" : "image-second";
    const context = {
      state: {}, $: selector => fields[selector], esc: value => value, render() {},
      localStorage: storage({"soda-agent-image-provider": "image-second"}),
      api: async () => ({models: [{id: "chat", name: "Chat"}], providers: [
        {id: "image-first", label: "First", model: "test"}, {id: "image-second", label: "Second", model: "test"},
      ], packages: []}),
    };
    vm.createContext(context);
    vm.runInContext(source.slice(source.indexOf("  async function bootstrap("), source.indexOf("  async function send(")), context);
    await context.bootstrap();
    assert.equal(fields["#agentImageProvider"].value, "image-second");
  });
}

test("an earlier conversation's image poll cannot update the current conversation", async () => {
  const source = fs.readFileSync(path.join(assets, "agent.js"), "utf8");
  let resolveJob;
  const field = {textContent: "current job"};
  const state = {chat: {id: "older"}, polls: new Map()};
  const context = {
    state, host: {querySelector: () => field},
    api: () => new Promise(resolve => {resolveJob = resolve;}),
    clearTimeout() {}, setTimeout: () => assert.fail("Stale poll must stop"),
    status: () => assert.fail("Stale poll must not change status"),
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  async function pollJob("), source.indexOf('  host.addEventListener("click"')), context);
  const pending = context.pollJob("old-job", "1:0");
  state.chat = {id: "newer"};
  resolveJob({status: "running", progress_message: "old job"});
  await pending;
  assert.equal(field.textContent, "current job");
});

test("an image submission finishing after a chat switch cannot attach to the new chat", async () => {
  const source = fs.readFileSync(path.join(assets, "agent.js"), "utf8");
  const start = source.indexOf("      if(button.dataset.agentGenerate!==undefined)");
  const end = source.indexOf("    }catch(error)", start);
  let resolveRequest;
  const state = {chat: {id: "older", messages: [{proposals: [{}]}]}};
  const context = {
    state, button: {dataset: {agentGenerate: "0:0"}},
    $: () => ({value: "test-provider"}),
    api: () => new Promise(resolve => {resolveRequest = resolve;}),
    status: () => assert.fail("Previous chat must not update current status"),
    pollJob: () => assert.fail("Previous chat must not poll in current chat"),
  };
  vm.createContext(context);
  vm.runInContext("async function generate() {" + source.slice(start, end) + "}", context);
  const pending = context.generate();
  state.chat = {id: "newer", messages: [{proposals: [{}]}]};
  resolveRequest({job_ids: ["older-job"]});
  await pending;
  assert.equal(state.chat.messages[0].proposals[0].job_ids, undefined);
});

test("gallery generation versions use their recorded submitted prompt, including empty negative", () => {
  const source = fs.readFileSync(path.join(assets, "gallery.js"), "utf8");
  const context = {};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  function records("), source.indexOf("  function compactEvidence(")), context);
  const older = {backend: "novelai", request: {input: "old submitted", parameters: {uc: ""}}, prompt: {positive: "assembled old"}};
  const newer = {backend: "novelai", request: {input: "new submitted", parameters: {uc: "negative"}}};
  assert.equal(context.generationEvidence({hub_generation: older}).prompts.positive.text, "old submitted");
  assert.equal(context.generationEvidence({hub_generation: older}).prompts.negative.text, "");
  assert.equal(context.generationEvidence({hub_generation: newer}).prompts.positive.text, "new submitted");
  assert.equal(context.generationEvidence({hub_generation: {backend: "comfyui", prompt: {positive: "composed"}}}).prompts.positive.text, "composed");
});

test("prompt completion replaces the active tag while preserving weights and neighboring tags", () => {
  const source = fs.readFileSync(path.join(assets, "prompt_editor.js"), "utf8");
  const context = {};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  function tokenAt("), source.indexOf("  function closeSuggestions(")), context);
  const text = "1girl, 1.5::artist:blue_hair::, sunset";
  const cursor = text.indexOf("hair") + 2;
  const token = context.tokenAt({value: text, selectionStart: cursor});
  assert.equal(text.slice(token.start, token.end), "blue_hair");
  assert.equal(text.slice(0, token.start), "1girl, 1.5::artist:");
  assert.equal(text.slice(token.end), "::, sunset");
});

test("prompt history keeps character and positive-negative edits in separate sessions", () => {
  const source = fs.readFileSync(path.join(assets, "prompt_editor.js"), "utf8");
  const context = {localStorage: storage()};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  function history("), source.indexOf("  function markup(")), context);
  context.remember("first-positive", "first");
  context.remember("first-negative", "negative");
  context.remember("second-positive", "second");
  context.remember("first-positive", "revised");
  assert.equal(context.history("first-positive")[0].text, "revised");
  assert.equal(context.history("first-positive")[1].text, "first");
  assert.equal(context.history("first-negative")[0].text, "negative");
  assert.equal(context.history("second-positive")[0].text, "second");
});

for (const replace of [false, true]) {
  test(`gallery slot restore preserves explicit empty fields with replace=${replace}`, async () => {
    const source = fs.readFileSync(path.join(assets, "workbench.js"), "utf8");
    const recipe = {prefix: "existing prefix", body: "existing body", negative: "existing negative", suffix: "existing suffix"};
    const routes = [];
    let saved = 0;
    const context = {
      state: {engine: "agent"},
      open: async (view, options) => routes.push({view, options}),
      window: {SodaStudio: {
        current: () => ({project: {studio: recipe}}),
        setFields: fields => Object.assign(recipe, fields),
        save: async () => { saved++; },
      }},
    };
    vm.createContext(context);
    vm.runInContext(source.slice(source.indexOf("  async function applySlots("), source.indexOf("  async function repair(")), context);
    await context.applySlots({prefix: "restored prefix", body: "restored body", negative: "", suffix: ""}, {replace, engine: "novelai"});
    assert.equal(routes[0].options.route.engine, "novelai");
    assert.equal(recipe.body, replace ? "restored body" : "existing body\nrestored body");
    assert.equal(recipe.negative, replace ? "" : "existing negative");
    assert.equal(recipe.suffix, replace ? "" : "existing suffix");
    assert.equal(saved, 1);
  });
}

for (const [kind, expected, scripts, tools] of [
  ['preset', '提示詞預設', [], []],
  ['skill', 'SKILL 指南', [], []],
  ['dsh', 'DSH 插件', ['index.js'], []],
]) {
  test(`package ${kind} is labelled by its content without claiming executable tools`, () => {
    const source = fs.readFileSync(path.join(assets, "agent.js"), "utf8");
    const field = {innerHTML: ""};
    const context = {
      state: {bootstrap: {packages: [{id: 'package-test', title: 'Example', status: 'ready', kind, tool_files: scripts, tools}]}},
      $: () => field, window: {}, esc: value => value,
    };
    vm.createContext(context);
    vm.runInContext(source.slice(source.indexOf('    $("#agentPackages").innerHTML ='), source.indexOf('    $("#agentCatalog").innerHTML =')), context);
    assert.ok(field.innerHTML.includes(expected));
    assert.ok(!field.innerHTML.includes('已註冊工具'));
    assert.ok(!field.innerHTML.includes('附帶腳本'));
  });
}

test("NovelAI gallery reuse replaces prompt fields and resets preset selectors", async () => {
  const source = fs.readFileSync(path.join(assets, "gallery_workbench.js"), "utf8");
  let handler;
  let restored;
  const notice = {textContent:""};
  const context = {
    active: {hub_generation: {backend: "novelai", prompt: {prefix:"", body:"gallery prompt", negative:"", suffix:""}, recipe: {}}},
    $: () => ({addEventListener: (_name, callback) => {handler = callback;}}),
    document: {querySelector: () => notice},
    structuredClone,
    window: {SodaGallery: {close() {}}, SodaWorkbench: {applySlots: async (fields, options) => {restored = {fields, options};}}},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('  $("#galleryReusePrompt").addEventListener'), source.indexOf('  const filterIds=')), context);
  await handler();
  assert.equal(restored.fields.body, "gallery prompt");
  assert.equal(restored.fields.prefix, "");
  assert.equal(restored.fields.negative, "");
  assert.equal(restored.fields.nai_quality, "");
  assert.equal(restored.fields.nai_uc, "none");
  assert.equal(restored.fields.nai_uc_text, "");
  assert.equal(restored.options.engine, "novelai");
  assert.equal(restored.options.replace, true);
  assert.equal(notice.textContent, "已用畫廊提示詞替換目前內容。");
});

function wildcardV2StudioSource() {
  return fs.readFileSync(path.join(assets, "studio.js"), "utf8");
}

test("enabling Wildcard V2 and changing model family updates sampling and negative defaults", () => {
  const source = wildcardV2StudioSource();
  const presets = {
    anima: {width:1024, height:1536, steps:12, cfg:1.0, negative:"lowres, blurry, bad anatomy, extra fingers, extra limbs, deformed, watermark, signature, text, logo, loli, child, kid"},
    moss: {width:832, height:1216, steps:25, cfg:2.5, negative:"worst quality, low quality, blurry, jpeg artifacts, overexposed, blown-out highlights, blinding glare, harsh white specular patches, washed out, bad anatomy, bad hands, deformed hands, fused fingers, extra fingers, missing fingers, extra limbs, deformed, text, watermark, signature"},
    krea2: {width:832, height:1216, steps:10, cfg:1.0, negative:""},
  };
  const recipe = {backend:"comfyui", text_mode:"wildcard", width:512, height:768, steps:25, cfg:4.0,
    negative:"old negative", locked_values:{negative:"old locked negative"}, wildcard_v2:{enabled:false, family:"anima"}};
  const renderedSampling = [];
  const context = {
    state:{bootstrap:{wildcard_v2_sampling_presets:presets}, project:{studio:recipe}},
    populateRecipe:() => renderedSampling.push([recipe.width, recipe.height, recipe.steps, recipe.cfg, recipe.negative]),
    renderWildcardV2:() => {}, markChanged:() => {}, structuredClone,
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  const wildcardV2Active"), source.indexOf("  const v2RandomModes")), context);
  vm.runInContext(source.slice(source.indexOf("  function applyWildcardV2SamplingPreset"), source.indexOf("  async function loadWildcardV2Pools")), context);
  vm.runInContext(source.slice(source.indexOf("  function bindStudioWorkflow"), source.indexOf("  function translated")), context);

  context.setWildcardV2Value("enabled", true);
  assert.equal(recipe.wildcard_v2_sampling_family, "anima");
  assert.equal(Object.hasOwn(recipe.locked_values, "negative"), false);
  context.setWildcardV2Value("family", "moss");
  assert.equal(recipe.wildcard_v2_sampling_family, "moss");
  context.setWildcardV2Value("family", "krea2");
  assert.equal(recipe.wildcard_v2_sampling_family, "krea2");
  for (const [index, preset] of Object.values(presets).entries()) {
    assert.deepEqual(renderedSampling[index], Object.values(preset));
  }
  recipe.steps = 14;
  context.bindStudioWorkflow(recipe, {profile_id:"legacy", bindings:{},
    source_values:{width:512, height:768, steps:25, cfg:4.0, negative:"legacy negative"}});
  assert.deepEqual([recipe.width, recipe.height, recipe.steps, recipe.cfg, recipe.negative], [832, 1216, 14, 1.0, ""]);
});

test("Wildcard V2 switches to a fixed character only after the user enters a specific trigger", () => {
  const source = wildcardV2StudioSource();
  const recipe = {wildcard_v2:{character_mode:"random", character:""}};
  const context = {
    state:{bootstrap:{wildcard_v2_generic_character_tags:["1girl", "adult woman", "solo"]}, project:{studio:recipe}},
    renderWildcardV2:() => {}, markChanged:() => {},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  function hasSpecificWildcardV2Character"), source.indexOf("  async function loadWildcardV2Pools")), context);
  context.setWildcardV2Value("character_mode", "fixed");
  assert.equal(context.state.v2CharacterEditing, true);
  assert.equal(recipe.wildcard_v2.character_mode, "random");
  context.setWildcardV2Value("character", "1girl，adult_woman\n solo.");
  assert.equal(recipe.wildcard_v2.character_mode, "random");
  context.setWildcardV2Value("character", "anima_oc_trigger, 1girl");
  assert.equal(recipe.wildcard_v2.character_mode, "fixed");
  context.setWildcardV2Value("character", "solo");
  assert.equal(recipe.wildcard_v2.character_mode, "random");
});

test("general Wildcard V2 slot suggestions exclude whole-prompt pools", async () => {
  const source = wildcardV2StudioSource();
  const scenePools = ["__moss_lora_v2/girl/scene__", "__moss_lora_v2/anima/slots/lighting__"];
  const wholePools = ["world/scenery", "world/creature", "world/still_life", "all"]
    .map(pool => `__moss_lora_v2/${pool}__`);
  const status = {};
  const datalist = {options:[], replaceChildren(...options) {this.options = options;}};
  const slots = {};
  const context = {
    state:{v2PoolsRequest:null},
    v2Slots:[["outfit", "Outfit", [["random", "Random"]]]],
    v2PairedPoolLists:{},
    $:selector => selector === "#studioWildcardV2Pools" ? datalist : status,
    document:{createElement:() => ({})},
    api:async () => ({pools:[...scenePools, ...wholePools], scene_pools:scenePools}),
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  function mountWildcardV2Slots"), source.indexOf("  function renderWildcardV2Slot")), context);
  vm.runInContext(source.slice(source.indexOf("  function replaceWildcardV2PoolOptions"), source.indexOf("  function populateRecipe")), context);
  context.mountWildcardV2Slots(slots);
  await context.loadWildcardV2Pools();
  assert.match(slots.innerHTML, /data-v2-setting="outfit_pool"[^>]+list="studioWildcardV2Pools"/);
  assert.deepEqual(datalist.options.map(option => option.value), scenePools);
  assert.equal(status.hidden, true);
});

test("editorial Wildcard V2 presents ordered independent slots and applies either pool pair", () => {
  const source = wildcardV2StudioSource();
  const html = fs.readFileSync(path.join(assets, "studio.html"), "utf8");
  const recipe = {wildcard_v2:{layout:"bundled", layout_mode:"fixed", layout_text:"saved layout",
    outfit_mode:"fixed", layout_pool:"custom layout", scene_light_mode:"none", scene_light_pool:"custom scene"}};
  const context = {
    state:{project:{studio:recipe}},
    renderWildcardV2() {}, markChanged() {},
    setWildcardV2Value(key, value) {recipe.wildcard_v2[key] = value;},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  const v2NoneMode"), source.indexOf("  const state =")), context);
  vm.runInContext(source.slice(source.indexOf("  function mountWildcardV2Slots"), source.indexOf("  function renderWildcardV2Slot")), context);
  vm.runInContext(source.slice(source.indexOf("  function setWildcardV2Preset"), source.indexOf("  function wildcardV2TagChoices")), context);
  const slots = {};
  context.mountWildcardV2Slots(slots);
  const categories = [...slots.innerHTML.matchAll(/data-v2-category="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(categories.slice(0, 6), ["layout", "style", "character", "outfit", "action", "scene_light"]);
  assert.match(slots.innerHTML, /data-v2-setting="layout_text"[^>]*data-v2-long/);
  assert.match(slots.innerHTML, /type="text" data-v2-setting="layout_pool"[^>]+list="studioWildcardV2LayoutPools"/);
  assert.match(slots.innerHTML, /type="text" data-v2-setting="scene_light_pool"[^>]+list="studioWildcardV2SceneLightPools"/);
  const styleModes = slots.innerHTML.slice(slots.innerHTML.indexOf('data-v2-category="style"'),
    slots.innerHTML.indexOf('data-v2-category="character"'));
  assert.deepEqual([...styleModes.matchAll(/data-v2-mode="([^"]+)"/g)].map(match => match[1]), ["preset", "fixed", "wildcard", "none"]);
  assert.deepEqual([...html.matchAll(/data-v2-preset="([^"]+)"/g)].map(match => match[1]), ["design", "world", "bundled"]);
  assert.match(html, /<details id="studioWildcardV2TestLight" hidden>/);

  for (const preset of ["design", "world"]) {
    context.setWildcardV2Preset(preset);
    assert.equal(recipe.wildcard_v2.scene_preset, preset);
    assert.equal(recipe.wildcard_v2.layout, "independent");
    assert.equal(recipe.wildcard_v2.layout_mode, "random");
    assert.equal(recipe.wildcard_v2.scene_light_mode, "random");
    assert.equal(recipe.wildcard_v2.layout_pool, "");
    assert.equal(recipe.wildcard_v2.scene_light_pool, "");
    assert.equal(recipe.wildcard_v2.outfit_mode, "fixed");
    assert.equal(recipe.wildcard_v2.layout_text, "saved layout");
  }
  context.setWildcardV2Preset("bundled");
  assert.equal(recipe.wildcard_v2.layout, "bundled");
});

test("layout and scene-light offer the two official references for the current family", () => {
  const source = wildcardV2StudioSource();
  const layoutList = {options:[], replaceChildren(...options) {this.options = options;}};
  const sceneLightList = {options:[], replaceChildren(...options) {this.options = options;}};
  const context = {
    $:selector => selector === "#studioWildcardV2LayoutPools" ? layoutList : sceneLightList,
    document:{createElement:() => ({})},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  const v2PairedPoolLists"), source.indexOf("  const v2TestLightActive")), context);
  vm.runInContext(source.slice(source.indexOf("  function renderWildcardV2PairOptions"), source.indexOf("  function renderWildcardV2(recipe")), context);
  vm.runInContext(source.slice(source.indexOf("  function replaceWildcardV2PoolOptions"), source.indexOf("  async function loadWildcardV2Pools")), context);
  for (const branch of ["anima", "nl"]) {
    const ref = name => `__moss_lora_v2/${branch}/slots/${name}__`;
    const designLayout = ref("layout_design");
    const worldLayout = ref("layout_camera");
    const designSceneLight = ref("scene_light_design");
    const worldSceneLight = ref("scene_light_world");
    context.renderWildcardV2PairOptions({design:{layout:[designLayout], scene_light:[designSceneLight]},
      world:{layout:[worldLayout], scene_light:[worldSceneLight]}});
    assert.deepEqual(layoutList.options.map(option => option.value), [designLayout, worldLayout]);
    assert.deepEqual(sceneLightList.options.map(option => option.value), [designSceneLight, worldSceneLight]);
  }
});

test("Wildcard V2 tag chips use active pool metadata and retain removable saved choices", () => {
  const source = wildcardV2StudioSource();
  const context = {};
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf("  const v2NoneMode"), source.indexOf("  const state =")), context);
  vm.runInContext(source.slice(source.indexOf("  function wildcardV2TagChoices"), source.indexOf("  function renderWildcardV2TagFilters")), context);
  const settings = {layout:"independent", style_mode:"wildcard", style_pool:"__style/pool__", action_mode:"fixed",
    tag_filters:{style:["saved style"]}};
  const tagsByPool = {
    "__style/pool__":{style:["ink"], line:["linework"]},
    "__layout/pool__":{style:["ink"]},
    "__outfit/pool__":{clothing:["coat"]},
    "__action/unused__":{style:["unused action"]},
    "__light/unused__":{style:["unused light"]},
    "__scene/pool__":{line:["scene"]},
  };
  const defaults = {layout:["__layout/pool__"], outfit:["__outfit/pool__"],
    action:["__action/unused__"], scene_light:["__scene/pool__"], test_lighting:["__light/unused__"]};
  const choices = context.wildcardV2TagChoices(settings, "design", tagsByPool, defaults);
  assert.equal(JSON.stringify(choices), JSON.stringify({style:["ink", "saved style"], line:["linework", "scene"], clothing:["coat"]}));
  const overrideChoices = context.wildcardV2TagChoices({...settings, test_lighting_mode:"random"}, "design", tagsByPool, defaults);
  assert.equal(JSON.stringify(overrideChoices), JSON.stringify({style:["ink", "saved style", "unused light"], line:["linework"], clothing:["coat"]}));
  const noHeaders = context.wildcardV2TagChoices({}, "world", {}, defaults);
  assert.equal(JSON.stringify(noHeaders), JSON.stringify({style:[], line:[], clothing:[]}));
});

test("workflow controls are compact, named, and exclude unused serialized state", () => {
  const source = fs.readFileSync(path.join(assets, "studio.js"), "utf8");
  const start = source.indexOf("  function selectedWorkflow()");
  const end = source.indexOf("  function renderPrefixRows()", start);
  assert.ok(start >= 0 && end > start);

  const fields = [
    {key:"prompt::text", title:"Prompt", input:"text", type:"text", value:""},
    {key:"controls::SlidersState#/sliders/0/value", title:"Pixaroma", input:"value_1", type:"boolean", value:true,
      control:{kind:"toggle",connected:true,targets:[{class_type:"ComfySwitchNode",input:"switch",title:"Turbo 模型切换"}]}},
    {key:"controls::SlidersState#/sliders/1/value", title:"Pixaroma", input:"value_2", type:"number", value:12,
      control:{kind:"int",connected:true,min:1,max:50,step:1,targets:[{class_type:"ComfySwitchNode",input:"on_true",title:"实际主采样步数",mode:"turbo"}]}},
    {key:"controls::SlidersState#/sliders/2/value", title:"Pixaroma", input:"value_3", type:"number", value:5,
      control:{kind:"float",connected:true,targets:[{class_type:"ComfySwitchNode",input:"on_false",title:"实际主采样 CFG",mode:"turbo"}]}},
    {key:"controls::SlidersState#/sliders/3/value", title:"Pixaroma", input:"value_4", type:"text", value:"er_sde",
      control:{kind:"combo",connected:true,targets:[{class_type:"Sampler Selector (Image Saver)",input:"sampler_name",title:"主采样器"}]}},
    {key:"controls::SlidersState#/sliders/4/value", title:"Pixaroma", input:"value_5", type:"text", value:"sgm_uniform",
      control:{kind:"combo",connected:true,targets:[{class_type:"Scheduler Selector (Image Saver)",input:"scheduler",title:"主调度器"}]}},
    {key:"controls::SlidersState#/sliders/5/value", title:"Pixaroma", input:"value_6", type:"number", value:0.4,
      control:{kind:"float",connected:false}},
    {key:"controls::SlidersState", title:"Pixaroma", input:"SlidersState", type:"text", value:'{"sliders":[]}'},
    {key:"sampler::steps#", title:"Sampler", input:"steps", type:"number", value:12,
      source_key:"controls::SlidersState#/sliders/1/value"},
  ];
  const workflow = {profile_id:"test-workflow",fields,bindings:{steps:["sampler::steps#"]},postprocess:[]};
  const recipe = {workflow_id:"test-workflow",bindings:{prefix:["prompt::text"]},overrides:{},branches:{},reference_bindings:{}};
  const selectors = ["#studioWorkflowControls","#studioWorkflowSummary","#studioWorkflowParametersToggle",
    "#studioWorkflowParameters","#studioWorkflowBindings","#studioWorkflowOverrides",
    "#studioWorkflowStateOverrides","#studioWorkflowUnconnected","#studioPostprocess","#studioReferenceBindings"];
  const elements = new Map(selectors.map(selector => {
    const attributes = {};
    return [selector,{innerHTML:"",hidden:false,textContent:"",value:"",
      setAttribute:(name,value) => {attributes[name] = String(value);},
      getAttribute:name => attributes[name] ?? (name === "aria-expanded" ? "false" : null)}];
  }));
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);
  const context = {
    state:{bootstrap:{workflows:[workflow]},project:{studio:recipe},images:[]},
    $:selector => elements.get(selector),
    document:{querySelectorAll:() => []},
    window:{t:value => ({
      "工作流常用參數":"工作流常用参数",
      "步數":"步数",
      "標準":"标准",
      "採樣器":"采样器",
      "調度器":"调度器",
      "其他工作流參數":"其他工作流参数",
    })[value] || value},
    escape,
    roles:{},
    wildcardV2Active:recipe => Boolean(recipe.wildcard_v2?.enabled),
    v2SamplingFields:new Set(["width", "height", "steps", "cfg", "negative"]),
  };
  vm.createContext(context);
  vm.runInContext(source.slice(start,end) + "\nrenderWorkflow();",context);

  const parameters = elements.get("#studioWorkflowParameters").innerHTML;
  const bindings = elements.get("#studioWorkflowBindings").innerHTML;
  assert.equal(elements.get("#studioWorkflowControls").hidden,false);
  assert.equal(elements.get("#studioWorkflowParametersToggle").textContent,"工作流常用参数 · 5");
  assert.match(parameters,/Turbo 模式/);
  assert.match(parameters,/Turbo · 步数/);
  assert.match(parameters,/标准 · CFG/);
  assert.match(parameters,/采样器/);
  assert.match(parameters,/调度器/);
  assert.match(parameters,/其他工作流参数 · 4/);
  assert.doesNotMatch(parameters,/value_6/);
  assert.match(parameters,/<details class="studio-workflow-branches"/);
  assert.match(bindings,/data-binding-choice="prefix"/);
  assert.doesNotMatch(bindings,/multiple size="2"/);
  assert.match(elements.get("#studioWorkflowStateOverrides").innerHTML,/SlidersState/);

  recipe.wildcard_v2 = {enabled:true};
  vm.runInContext("renderWorkflow();", context);
  const v2Parameters = elements.get("#studioWorkflowParameters").innerHTML;
  assert.doesNotMatch(v2Parameters, /Turbo · 步数/);
  assert.match(v2Parameters, /标准 · CFG/);
});

test("workflow mode buttons update the saved override and expansion state", () => {
  const source = fs.readFileSync(path.join(assets, "studio.js"), "utf8");
  const start = source.indexOf('    $("#studioWorkflowParametersToggle").addEventListener("click"');
  const end = source.indexOf('    $("#studioPage").addEventListener("input"',start);
  assert.ok(start >= 0 && end > start);
  const handlers = {};
  const attributes = {"aria-expanded":"false"};
  const parameterButton = {
    getAttribute:name => attributes[name] ?? null,
    setAttribute:(name,value) => {attributes[name] = String(value);},
    addEventListener:(name,handler) => {handlers.parameters = handler;},
  };
  const parameterPanel = {hidden:true};
  const choices = [
    {dataset:{value:"false"},setAttribute(name,value){this[name]=value;}},
    {dataset:{value:"true"},setAttribute(name,value){this[name]=value;}},
  ];
  const group = {querySelectorAll:() => choices};
  const modeButton = {
    dataset:{value:"true",overrideChoice:"controls::SlidersState#/sliders/0/value"},
    closest:selector => selector === '[role="group"]' ? group : null,
  };
  const controls = {addEventListener:(name,handler) => {handlers.controls = handler;}};
  const state = {project:{studio:{overrides:{}}}};
  let changes = 0;
  const context = {
    $:selector => selector === "#studioWorkflowParametersToggle" ? parameterButton :
      selector === "#studioWorkflowParameters" ? parameterPanel : controls,
    state,
    markChanged:() => {changes++;},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(start,end),context);
  handlers.parameters({currentTarget:parameterButton});
  assert.equal(parameterPanel.hidden,false);
  assert.equal(attributes["aria-expanded"],"true");
  handlers.controls({target:{closest:selector => selector === "[data-override-choice]" ? modeButton : null}});
  assert.equal(state.project.studio.overrides[modeButton.dataset.overrideChoice],true);
  assert.equal(choices[0]["aria-pressed"],"false");
  assert.equal(choices[1]["aria-pressed"],"true");
  assert.equal(changes,1);
});

test("ComfyUI creation keeps the simple workflow controls in its visible workflow strip", () => {
  const source = fs.readFileSync(path.join(assets, "creation_canvas.js"), "utf8");
  const layout = fs.readFileSync(path.join(assets, "approved_layout.css"), "utf8");
  assert.match(source,/workflowTop\.append\(\$\("#studioWorkflowControls"\)\)/);
  assert.match(source,/\$\("#creationComfyContent"\)\.append\(\$\("#studioWorkflowControls"\)\)/);
  assert.doesNotMatch(source,/"#studioWorkflowBindings"\s*,\s*"#studioPostprocess"/);
  assert.match(layout,/#creationWorkflowTop\s*\{[^}]*display:\s*grid/s);
  assert.match(layout,/#creationWorkflowTop\s*>\s*#studioWorkflowControls\s*\{[^}]*grid-column:\s*1\s*\/\s*-1/s);
});

test("Agent Enter submits, Shift+Enter inserts a newline, and IME confirmation is preserved", () => {
  const source = fs.readFileSync(path.join(assets, "agent.js"), "utf8");
  const handlers = {};
  let submitted = 0;
  const input = {addEventListener: (name, handler) => {handlers[name] = handler;}};
  const form = {requestSubmit: () => {submitted++;}};
  const context = {$: selector => selector === "#agentInput" ? input : form};
  const start = source.indexOf('  $("#agentInput").addEventListener("keydown"');
  const end = source.indexOf('  $("#agentInput").addEventListener("input"', start);
  assert.ok(start >= 0 && end > start);
  vm.createContext(context);
  vm.runInContext(source.slice(start, end), context);

  let prevented = false;
  handlers.keydown({key:"Enter",shiftKey:false,isComposing:false,keyCode:13,preventDefault:() => {prevented = true;}});
  assert.equal(submitted, 1);
  assert.equal(prevented, true);

  prevented = false;
  handlers.keydown({key:"Enter",shiftKey:true,isComposing:false,keyCode:13,preventDefault:() => {prevented = true;}});
  assert.equal(submitted, 1);
  assert.equal(prevented, false);

  handlers.keydown({key:"Enter",shiftKey:false,isComposing:true,keyCode:13,preventDefault:() => {prevented = true;}});
  handlers.keydown({key:"Enter",shiftKey:false,isComposing:false,keyCode:229,preventDefault:() => {prevented = true;}});
  assert.equal(submitted, 1);
  assert.equal(prevented, false);
});

function imageProviderForm(api) {
  const source = fs.readFileSync(path.join(assets, "studio.js"), "utf8");
  const handlers = {};
  const fields = {};
  for (const name of ['id', 'kind', 'label', 'base_url', 'model', 'api_key']) fields[name] = {value: ''};
  Object.assign(fields.kind, {value: 'openai'});
  fields.references = {checked: true};
  const form = {elements: fields, addEventListener: (name, callback) => {handlers[name] = callback;}};
  let pending;
  const state = {providerFormRun: 0};
  const context = {
    state, api, $: () => form, bootstrap: async () => {}, renderSettings() {}, notice() {},
    FormData: class {[Symbol.iterator]() {return Object.entries(fields).filter(([name]) => name !== 'references').map(([name, field]) => [name, field.value])[Symbol.iterator]();}},
    action: (_button, callback) => {pending = callback();},
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('    $("#studioProviderForm").addEventListener("submit"'), source.indexOf('    $("#studioNewProvider").addEventListener')), context);
  return {fields, state, submit: () => {handlers.submit({target: form, preventDefault() {}, submitter: {}});return pending;}};
}

test("saving an image provider twice edits the id returned by its first save", async () => {
  const requests = [];
  const form = imageProviderForm(async (_url, options) => {requests.push(options.body.provider);return {saved_provider_id: 'image-saved'};});
  form.fields.api_key.value = 'test-only-key';
  await form.submit();
  assert.equal(form.fields.id.value, 'image-saved');
  assert.equal(form.fields.api_key.value, '');
  await form.submit();
  assert.equal(requests[0].id, '');
  assert.equal(requests[1].id, 'image-saved');
});

for (const switched of [false, true]) {
  test(`a slow provider save preserves new credential input with editor switched=${switched}`, async () => {
    let resolveSave;
    const form = imageProviderForm(() => new Promise(resolve => {resolveSave = resolve;}));
    form.fields.api_key.value = 'submitted-test-only-key';
    const pending = form.submit();
    form.fields.api_key.value = 'new-test-only-key';
    if (switched) {form.state.providerFormRun++;form.fields.id.value = 'other-editor';}
    resolveSave({saved_provider_id: 'image-saved'});
    await pending;
    assert.equal(form.fields.api_key.value, 'new-test-only-key');
    assert.equal(form.fields.id.value, switched ? 'other-editor' : 'image-saved');
  });
}

test("an earlier provider model fetch cannot populate another connection's editor", async () => {
  const source = fs.readFileSync(path.join(assets, "studio.js"), "utf8");
  const fields = {};
  const state = {providerDiscoveryRun: 0};
  let handler;
  let pending;
  let resolveModels;
  const form = {elements: {base_url: {reportValidity: () => true}, model: {value: ''}}};
  const context = {
    state, window: {}, AbortController,
    $: selector => selector === '#studioProviderForm' ? form : fields[selector] ||= {innerHTML: '', addEventListener: (_name, callback) => {handler = callback;}},
    FormData: class {[Symbol.iterator]() {return [][Symbol.iterator]();}},
    clearProviderModels: () => {state.providerDiscoveryRun++;}, notice() {},
    action: (_button, callback) => {pending = callback();},
    api: () => new Promise(resolve => {resolveModels = resolve;}),
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('    $("#studioDiscoverProviderModels").addEventListener'), source.indexOf('    $("#studioProviderModelSelect").addEventListener')), context);
  handler({currentTarget: {}});
  state.providerDiscoveryRun++;
  resolveModels({models: [{id: 'stale-model', name: 'Stale model'}]});
  await pending;
  assert.equal(fields['#studioProviderModelSelect'], undefined);
});

test("Agent connection management opens the chat model endpoint manager", () => {
  const source = fs.readFileSync(path.join(assets, "agent.js"), "utf8");
  let handler;
  let opened = 0;
  vm.runInNewContext(source.split('\n').find(line => line.includes('$("#agentConnections").addEventListener')), {
    $: () => ({addEventListener: (_name, callback) => {handler = callback;}}),
    window: {openModelEndpoints: () => {opened++;}},
  });
  handler();
  assert.equal(opened, 1);
});
