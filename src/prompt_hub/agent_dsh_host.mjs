import {readFileSync} from "node:fs";
import {pathToFileURL} from "node:url";
import path from "node:path";

const request = JSON.parse(readFileSync(0, "utf8"));
console.log = (...values) => process.stderr.write(values.map(String).join(" ") + "\n");
const sections = [];
const tools = new Map();
const projections = new Map();
const service = {
  register(definition) { projections.set(definition.key, definition); return () => projections.delete(definition.key); },
};
const ctx = {
  effect(callback) { return callback(); },
  systemPrompt: {section(section) { sections.push(section); return () => {}; }},
  tools: {register(tool) { tools.set(tool.name, tool); return () => tools.delete(tool.name); }},
  get(name) { if (name === "sessionProjections") return service; return ctx[name]; },
  inject(names, callback) {
    if (names.every(name => ctx.get(name) !== undefined)) return callback(ctx);
  },
};

try {
  const imported = await import(pathToFileURL(path.resolve(request.root, request.entry)).href);
  const plugin = typeof imported.apply === "function" ? imported : imported.default;
  const apply = typeof plugin === "function" ? plugin : plugin?.apply;
  if (typeof apply !== "function") throw Error("Plugin must export apply(ctx, config)");
  await apply(ctx, request.config || {});
  let result = null;
  if (request.operation === "execute") {
    const tool = tools.get(request.tool);
    if (!tool) throw Error("Plugin tool was not registered");
    result = await tool.execute(request.arguments || {}, {ctx});
  }
  const views = {};
  for (const [key, definition] of projections) {
    let state = definition.init();
    for (const event of request.events || []) state = definition.apply(state, event);
    views[key] = definition.wire?.view ? definition.wire.view(state) : state;
  }
  process.stdout.write(JSON.stringify({
    name: plugin?.name || imported.name || "plugin",
    sections: sections.sort((a, b) => (a.order || 0) - (b.order || 0)).map(section => section.text || ""),
    tools: [...tools.values()].map(tool => ({name: tool.name, description: tool.description || "", parameters: tool.parameters || {type: "object", properties: {}}})),
    projections: views, result,
  }));
} catch (error) {
  process.stderr.write(error.message);
  process.exitCode = 1;
}
