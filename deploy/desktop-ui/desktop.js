(() => {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const requestedProduct = params.get("product");
  const product = ["desktop", "worker"].includes(requestedProduct) ? requestedProduct : "mac";
  const elements = {
    body: document.body,
    brandName: document.querySelector("#brandName"),
    buildLabel: document.querySelector("#buildLabel"),
    checkedAt: document.querySelector("#checkedAt"),
    comfyDetail: document.querySelector("#comfyDetail"),
    comfyState: document.querySelector("#comfyState"),
    computeDetail: document.querySelector("#computeDetail"),
    computeState: document.querySelector("#computeState"),
    connectionCard: document.querySelector("#connectionCard"),
    connectionDevice: document.querySelector("#connectionDevice"),
    connectionLabel: document.querySelector("#connectionLabel"),
    connectionDetail: document.querySelector("#connectionDetail"),
    connectionCheckedAt: document.querySelector("#connectionCheckedAt"),
    connectionNotice: document.querySelector("#connectionNotice"),
    computeAction: document.querySelector("#computeAction"),
    configAction: document.querySelector("#configAction"),
    coreDetail: document.querySelector("#coreDetail"),
    coreState: document.querySelector("#coreState"),
    errorCard: document.querySelector("#errorCard"),
    errorDetail: document.querySelector("#errorDetail"),
    errorRetry: document.querySelector("#errorCard [data-command]"),
    errorTitle: document.querySelector("#errorTitle"),
    folderAction: document.querySelector("#folderAction"),
    heroDescription: document.querySelector("#heroDescription"),
    heroTitle: document.querySelector("#heroTitle"),
    hideAction: document.querySelector("#hideAction"),
    libraryDetail: document.querySelector("#libraryDetail"),
    libraryState: document.querySelector("#libraryState"),
    logsAction: document.querySelector("#logsAction"),
    panelTitle: document.querySelector("#panelTitle"),
    phaseEyebrow: document.querySelector("#phaseEyebrow"),
    platformCopy: document.querySelector("#platformCopy"),
    primaryAction: document.querySelector("#primaryAction"),
    primaryLabel: document.querySelector("#primaryLabel"),
    programDetail: document.querySelector("#programDetail"),
    programVersion: document.querySelector("#programVersion"),
    railCopy: document.querySelector("#railCopy"),
    restartAction: document.querySelector("#restartAction"),
    settingsForm: document.querySelector("#workerSettingsForm"),
    settingsNotice: document.querySelector("#settingsNotice"),
    settingsOverlay: document.querySelector("#settingsOverlay"),
    settingsTitle: document.querySelector("#settingsTitle"),
    stepCard: document.querySelector("#stepCard"),
    stepDetail: document.querySelector("#stepDetail"),
    stepIndex: document.querySelector("#stepIndex"),
    stepTitle: document.querySelector("#stepTitle"),
    taskDetail: document.querySelector("#taskDetail"),
    taskLane: document.querySelector("#taskLane"),
    taskState: document.querySelector("#taskState"),
    taskTitle: document.querySelector("#taskTitle"),
    titleCopy: document.querySelector("#titleCopy"),
    toast: document.querySelector("#toast"),
  };

  const productCopy = {
    mac: {
      appName: "Soda Prompt Hub",
      brand: "SODA /\nPROMPT HUB",
      platform: "MAC DESKTOP / 01",
      hero: "Your local\ncreative archive.",
      description: "本地创作资料中枢。资料、角色、Prompt 与结果都在这台设备上，由你掌控。",
      panel: "System check",
      signalTitles: ["Core service", "Local library", "Compute device"],
      restart: "重新启动",
      folder: "数据目录",
    },
    worker: {
      appName: "Soda Compute Worker",
      brand: "SODA /\nCOMPUTE WORKER",
      platform: "WINDOWS COMPUTE / 02",
      hero: "Compute,\nunder control.",
      description: "供 Mac 连接的 Windows 计算端。打开后自动启动接收服务，保持此程序与 ComfyUI 运行即可。首次需要配置共享目录。",
      panel: "Device signal",
      signalTitles: ["Worker process", "Bridge transport", "GPU device"],
      restart: "运行自检",
      folder: "Bridge 目录",
    },
    desktop: {
      appName: "Soda Prompt Hub",
      brand: "SODA /\nPROMPT HUB",
      platform: "WINDOWS DESKTOP / 03",
      hero: "Create here.\nCompute here.",
      description: "一台 Windows，直接进入创作。工作台与计算服务一起启动，只需连接本机 ComfyUI，无需配对其他设备。",
      panel: "Local system",
      signalTitles: ["Core service", "Local library", "Local compute"],
      restart: "重新启动",
      folder: "数据目录",
    },
  }[product];

  const commonFallback = {
    phase: "checking",
    step: 1,
    checkedAt: "--:--:--",
    canPrimary: false,
    canRestart: false,
    errorTitle: "",
    errorDetail: "",
    taskState: "WAITING",
    taskTitle: "等待下一个已校验任务",
    taskDetail: "Worker 只会领取 bridge 中通过协议校验的任务。",
  };
  const fallbackStatus = product === "worker" ? {
    ...commonFallback,
    stepTitle: "正在读取 Worker 配置",
    stepDetail: "正在确认 bridge、ComfyUI 和 Python 环境。",
    coreState: "CHECKING",
    coreDetail: "prompt_hub_worker.py",
    libraryState: "CHECKING",
    libraryDetail: "worker-config.json",
    computeState: "CHECKING",
    computeDetail: "CUDA device",
    comfyState: "CHECKING",
    comfyDetail: "127.0.0.1:8188",
    version: "1.2.0",
    releaseChannel: "Stable · protocol v2",
    primaryCommand: "startWorker",
  } : {
    ...commonFallback,
    stepTitle: "正在连接原生启动器",
    stepDetail: "正在读取本机服务状态。",
    coreState: "CHECKING",
    coreDetail: "127.0.0.1:8765",
    libraryState: "LOCAL",
    libraryDetail: "Documents / Soda Prompt Hub",
    computeState: "OPTIONAL",
    computeDetail: product === "desktop" ? "可以稍后启用本机 Worker" : "可以稍后连接 Windows",
    comfyState: "",
    comfyDetail: "",
    version: "1.2.0",
    releaseChannel: "Stable · Local first",
    canOpenWorkspace: false,
    primaryCommand: "openWorkspace",
  };

  let latestStatus = { ...fallbackStatus };
  let sequence = 0;
  let toastTimer = null;
  const pending = new Map();

  function hasNativeHost() {
    return Boolean(window.webkit?.messageHandlers?.sodaHost || window.chrome?.webview);
  }

  function postNativeMessage(message) {
    const webkit = window.webkit?.messageHandlers?.sodaHost;
    if (webkit) {
      webkit.postMessage(message);
      return;
    }
    window.chrome?.webview?.postMessage(message);
  }

  function callHost(method, commandParams = {}) {
    if (!hasNativeHost()) {
      if (method === "getStatus") return Promise.resolve(latestStatus);
      if (method === "getWorkerConfig") {
        return Promise.resolve({
          config: {
            bridgeRoot: "D:\\PromptHub-Bridge\\prompt-hub",
            comfyUiUrl: "http://127.0.0.1:8188",
            loraRoots: ["F:\\ComfyUI\\models\\loras"],
            modelRoots: {
              checkpoint: ["F:\\ComfyUI\\models\\checkpoints"],
              diffusion_model: ["F:\\ComfyUI\\models\\diffusion_models"],
              vae: ["F:\\ComfyUI\\models\\vae"],
              text_encoder: ["F:\\ComfyUI\\models\\text_encoders"],
              upscaler: ["F:\\ComfyUI\\models\\upscale_models"],
              controlnet: ["F:\\ComfyUI\\models\\controlnet"],
            },
          },
        });
      }
      if (method === "chooseFolder") {
        return Promise.resolve({ path: commandParams.initial || "D:\\PromptHub-Bridge\\prompt-hub" });
      }
      showToast("当前为界面预览，原生操作将在 App 中生效。");
      return Promise.resolve({ preview: true });
    }

    const id = `desktop-${Date.now()}-${sequence += 1}`;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      postNativeMessage({ id, method, params: commandParams });
      const timeout = ["selfTestWorker", "saveWorkerConfig"].includes(method) ? 130000 : 30000;
      window.setTimeout(() => {
        if (!pending.has(id)) return;
        pending.delete(id);
        reject(new Error("原生启动器响应超时"));
      }, timeout);
    });
  }

  function text(element, value) {
    if (element && typeof value === "string") element.textContent = value;
  }

  function configureProduct() {
    elements.body.dataset.product = product;
    document.title = productCopy.appName;
    text(elements.titleCopy, productCopy.appName);
    text(elements.brandName, productCopy.brand);
    text(elements.platformCopy, productCopy.platform);
    text(elements.heroTitle, productCopy.hero);
    text(elements.heroDescription, productCopy.description);
    text(elements.panelTitle, productCopy.panel);
    text(document.querySelector('[data-signal="core"] h3'), productCopy.signalTitles[0]);
    text(document.querySelector('[data-signal="library"] h3'), productCopy.signalTitles[1]);
    text(document.querySelector('[data-signal="compute"] h3'), productCopy.signalTitles[2]);
    text(elements.restartAction, productCopy.restart);
    text(elements.folderAction, productCopy.folder);
    text(elements.settingsTitle, product === "desktop" ? "配置本机计算" : "配置计算设备");
    document.querySelectorAll(".worker-only").forEach((element) => {
      element.hidden = product !== "worker";
    });
    document.querySelectorAll(".mac-only").forEach((element) => {
      element.hidden = product !== "mac";
    });
    document.querySelectorAll(".desktop-only").forEach((element) => {
      element.hidden = product !== "desktop";
    });
    document.querySelectorAll(".windows-only").forEach((element) => {
      element.hidden = !["desktop", "worker"].includes(product);
    });
    document.querySelectorAll(".compute-settings").forEach((element) => {
      element.hidden = !["desktop", "worker"].includes(product);
    });
    document.querySelectorAll(".bridge-config").forEach((element) => {
      element.hidden = product === "desktop";
    });
    elements.settingsOverlay.hidden = true;
    if (product === "worker") {
      elements.restartAction.dataset.command = "selfTestWorker";
      elements.errorRetry.dataset.command = "startWorker";
    }
  }

  function normalizeStatus(status) {
    return { ...fallbackStatus, ...status };
  }

  function previewStatus(phase) {
    const macSamples = {
      starting: {
        phase: "starting", step: 3, stepTitle: "正在启动 Core",
        stepDetail: "后台启动，不会显示 Terminal。", coreState: "STARTING",
        coreDetail: "127.0.0.1:8765",
      },
      ready: {
        phase: "ready", step: 5, stepTitle: "工作台已经准备好",
        stepDetail: "http://127.0.0.1:8765/", coreState: "READY",
        coreDetail: "127.0.0.1:8765", checkedAt: "12:33:13",
        canOpenWorkspace: true, canPrimary: true,
      },
      attention: {
        phase: "attention", step: 4, coreState: "ERROR",
        coreDetail: "服务身份检查没有通过", canPrimary: true,
        primaryCommand: "retryCore", errorTitle: "Soda Prompt Hub 启动超时",
        errorDetail: "Core 没有在等待时间内响应。你的资料没有受到影响。",
      },
    };
    const workerSamples = {
      idle: {
        phase: "idle", step: 4, checkedAt: "12:33:13", coreState: "STOPPED",
        coreDetail: "随时可以启动", libraryState: "READY",
        libraryDetail: "D:\\PromptHub-Bridge\\prompt-hub", computeState: "CUDA",
        computeDetail: "RTX 5060 Ti · 15.8 GB FREE", comfyState: "REACHABLE",
        comfyDetail: "ComfyUI 0.34.0 · 127.0.0.1:8188", canPrimary: true,
        canRestart: true, primaryCommand: "startWorker", primaryLabel: "启动 Worker",
      },
      starting: {
        phase: "starting", step: 3, coreState: "STARTING",
        coreDetail: "正在创建后台进程", libraryState: "READY",
        libraryDetail: "D:\\PromptHub-Bridge\\prompt-hub", computeState: "CUDA",
        computeDetail: "RTX 5060 Ti", comfyState: "REACHABLE",
        comfyDetail: "127.0.0.1:8188", primaryLabel: "正在启动",
      },
      ready: {
        phase: "ready", step: 5, checkedAt: "12:33:13", coreState: "RUNNING",
        coreDetail: "PID 18420 · background", libraryState: "READY",
        libraryDetail: "D:\\PromptHub-Bridge\\prompt-hub", computeState: "CUDA",
        computeDetail: "RTX 5060 Ti · 15.8 GB FREE", comfyState: "REACHABLE",
        comfyDetail: "ComfyUI 0.34.0 · 127.0.0.1:8188", canPrimary: true,
        primaryCommand: "stopWorker", primaryLabel: "停止 Worker",
      },
      busy: {
        phase: "busy", step: 5, checkedAt: "12:33:13", coreState: "RUNNING",
        coreDetail: "PID 18420 · background", libraryState: "ACTIVE",
        libraryDetail: "D:\\PromptHub-Bridge\\prompt-hub", computeState: "CUDA",
        computeDetail: "RTX 5060 Ti · 15.8 GB FREE", comfyState: "GENERATING",
        comfyDetail: "ComfyUI 0.34.0 · 127.0.0.1:8188", canPrimary: false,
        primaryCommand: "stopWorker", primaryLabel: "任务执行中", taskState: "GENERATING",
        taskTitle: "正在执行 comfyui_generate", taskDetail: "task-20260911-0421 · 已通过 manifest 校验",
      },
      attention: {
        phase: "attention", step: 2, coreState: "STOPPED",
        coreDetail: "Worker 未启动", libraryState: "READY",
        libraryDetail: "D:\\PromptHub-Bridge\\prompt-hub", computeState: "UNKNOWN",
        computeDetail: "等待自检", comfyState: "OFFLINE", comfyDetail: "127.0.0.1:8188",
        canPrimary: true, primaryCommand: "startWorker", primaryLabel: "启动 Worker",
        errorTitle: "ComfyUI 尚未就绪", errorDetail: "请先启动 ComfyUI，再运行自检或启动 Worker。",
      },
    };
    const desktopSamples = {
      starting: {
        phase: "starting", step: 3, stepTitle: "正在启动本机 Core",
        stepDetail: "Core 将在后台运行，不会显示命令窗口。", coreState: "STARTING",
        coreDetail: "127.0.0.1:8765", computeState: "OPTIONAL",
        computeDetail: "本机 Worker 尚未启动", computeActionLabel: "启动本机计算",
      },
      ready: {
        phase: "ready", step: 5, stepTitle: "本机工作台已经准备好",
        stepDetail: "http://127.0.0.1:8765/", coreState: "READY",
        coreDetail: "PID 14208 · owned", libraryState: "LOCAL",
        libraryDetail: "Documents\\Soda Prompt Hub\\prompt-library",
        computeState: "LOCAL", computeDetail: "RTX 5060 Ti · Worker running",
        checkedAt: "12:33:13", canPrimary: true, canRestart: true,
        canComputeAction: true, computeActionLabel: "停止本机计算",
      },
      attention: {
        phase: "attention", step: 3, coreState: "ERROR",
        coreDetail: "Core 启动没有完成", libraryState: "SAFE",
        libraryDetail: "用户资料未修改", computeState: "OPTIONAL",
        computeDetail: "本机 Worker 未启动", canPrimary: true, canRestart: true,
        primaryCommand: "retryCore", computeActionLabel: "启动本机计算",
        errorTitle: "本机 Core 没有响应",
        errorDetail: "请检查 Python 3.12 与 Core 日志。你的资料没有受到影响。",
      },
    };
    const samples = product === "worker" ? workerSamples : product === "desktop" ? desktopSamples : macSamples;
    const sample = samples[phase];
    return sample ? normalizeStatus(sample) : null;
  }

  function phaseCopy(phase) {
    if (product === "worker") {
      return {
        checking: ["DEVICE CHECK", "CHECKING · WORKER ENVIRONMENT", "正在检查"],
        starting: ["STARTUP SEQUENCE", "STARTING · COMPUTE WORKER", "正在启动"],
        idle: ["DEVICE READY", "READY TO START · COMFYUI AVAILABLE", "启动 Worker"],
        ready: ["COMPUTE ONLINE", "RUNNING IN SYSTEM TRAY", "停止 Worker"],
        busy: ["VERIFIED TASK", "WORKING · VERIFIED TASK IN PROGRESS", "任务执行中"],
        attention: ["NEEDS ATTENTION", "ATTENTION · DEVICE NEEDS REVIEW", "重新尝试"],
      }[phase] || ["DEVICE CHECK", "CHECKING · WORKER ENVIRONMENT", "正在检查"];
    }
    return {
      checking: ["SYSTEM CHECK", "CHECKING · LOCAL SERVICES", "正在检查"],
      starting: ["STARTUP SEQUENCE", "STARTING · PROMPT HUB CORE", "正在启动"],
      ready: ["LOCAL FIRST", "READY · LOCAL WORKSPACE AVAILABLE", "打开工作台"],
      attention: ["NEEDS ATTENTION", "ATTENTION · STARTUP NEEDS REVIEW", "重试启动"],
    }[phase] || ["SYSTEM CHECK", "CHECKING · LOCAL SERVICES", "正在检查"];
  }

  function render(status) {
    const previousSignal = `${latestStatus.phase}/${latestStatus.connectionState}/${latestStatus.coreState}`;
    latestStatus = normalizeStatus(status);
    const nextSignal = `${latestStatus.phase}/${latestStatus.connectionState}/${latestStatus.coreState}`;
    if (previousSignal !== nextSignal && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      document.querySelector('.system-panel')?.animate([
        {opacity: 0.65, transform: 'translateY(4px)'}, {opacity: 1, transform: 'translateY(0)'}
      ], {duration: 280, easing: 'ease-out'});
    }
    const validPhases = ["checking", "starting", "idle", "ready", "busy", "attention"];
    const phase = validPhases.includes(latestStatus.phase) ? latestStatus.phase : "checking";
    elements.body.dataset.phase = phase;

    text(elements.checkedAt, latestStatus.checkedAt);
    text(elements.coreState, latestStatus.coreState);
    text(elements.coreDetail, latestStatus.coreDetail);
    text(elements.libraryState, latestStatus.libraryState);
    text(elements.libraryDetail, latestStatus.libraryDetail);
    text(elements.computeState, latestStatus.computeState);
    text(elements.computeDetail, latestStatus.computeDetail);
    text(elements.computeAction, latestStatus.computeActionLabel || "启动本机计算");
    if (elements.computeAction) elements.computeAction.disabled = !latestStatus.canComputeAction;
    text(elements.comfyState, latestStatus.comfyState);
    text(elements.comfyDetail, latestStatus.comfyDetail);
    text(elements.taskState, latestStatus.taskState);
    text(elements.taskTitle, latestStatus.taskTitle);
    text(elements.taskDetail, latestStatus.taskDetail);
    text(elements.programVersion, `${productCopy.appName} ${latestStatus.version}`);
    text(elements.programDetail, latestStatus.releaseChannel);
    text(elements.stepIndex, String(latestStatus.step).padStart(2, "0"));
    text(elements.stepTitle, latestStatus.stepTitle);
    text(elements.stepDetail, latestStatus.stepDetail);

    const copy = phaseCopy(phase);
    text(elements.phaseEyebrow, copy[0]);
    text(elements.railCopy, latestStatus.railCopy || copy[1]);
    text(elements.primaryLabel, latestStatus.primaryLabel || copy[2]);
    elements.primaryAction.dataset.command = latestStatus.primaryCommand
      || (phase === "attention" ? "retryCore" : "openWorkspace");
    const canPrimary = latestStatus.canPrimary ?? latestStatus.canOpenWorkspace;
    elements.primaryAction.disabled = !canPrimary;
    elements.restartAction.disabled = !latestStatus.canRestart;
    const stopQuit = document.querySelector('#stopQuitAction');
    if (stopQuit) stopQuit.disabled = !latestStatus.canStop;
    elements.errorRetry.disabled = !canPrimary;
    elements.errorCard.hidden = phase !== "attention";
    const showConnection = product === "mac" && phase === "ready";
    elements.connectionCard.hidden = !showConnection;
    if (showConnection) {
      const reconnect = document.querySelector('#reconnectAction');
      if (reconnect) reconnect.hidden = !['mount_missing','not_configured'].includes(latestStatus.connectionState);
      elements.connectionCard.dataset.state = latestStatus.connectionState || "checking";
      text(elements.connectionDevice, latestStatus.connectionDevice || "计算设备");
      text(elements.connectionLabel, latestStatus.connectionLabel || "正在检查设备连接");
      text(elements.connectionDetail, latestStatus.connectionDetail || "等待最新连接检查结果。");
      text(elements.connectionCheckedAt, latestStatus.connectionCheckedAt || "--:--:--");
      text(elements.connectionNotice, latestStatus.connectionNotice || "");
      elements.connectionNotice.hidden = !latestStatus.connectionNotice;
    }
    elements.stepCard.hidden = showConnection || phase === "attention" || (product === "worker" && ["ready", "busy", "idle"].includes(phase));
    if (product === "worker") {
      elements.taskLane.hidden = !["idle", "ready", "busy"].includes(phase);
    }
    text(elements.errorTitle, latestStatus.errorTitle || "启动未完成");
    text(elements.errorDetail, latestStatus.errorDetail || "请查看日志后重试。");
    elements.buildLabel.textContent = latestStatus.buildLabel
      || (phase === "ready" || phase === "busy" ? "READY / LOCAL" : product === "worker" ? "COMPUTE NODE" : "LOCAL FIRST");
  }

  function showToast(message) {
    window.clearTimeout(toastTimer);
    text(elements.toast, message);
    elements.toast.hidden = false;
    toastTimer = window.setTimeout(() => {
      elements.toast.hidden = true;
    }, 3200);
  }

  async function runCommand(button) {
    const method = button.dataset.command;
    if (!method || button.disabled) return;
    button.disabled = true;
    try {
      const result = await callHost(method);
      if (result?.status) render(result.status);
      if (result?.message) showToast(result.message);
    } catch (error) {
      showToast(error instanceof Error ? error.message : "操作没有完成");
    } finally {
      if (button !== elements.primaryAction) button.disabled = false;
    }
  }

  function lines(value) {
    return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  }

  function setField(id, value) {
    const field = document.querySelector(`#${id}`);
    if (field) field.value = Array.isArray(value) ? value.join("\n") : value || "";
  }

  function populateWorkerConfig(config) {
    setField("bridgeRoot", config.bridgeRoot);
    setField("comfyUiUrl", config.comfyUiUrl || "http://127.0.0.1:8188");
    setField("loraRoots", config.loraRoots);
    setField("modelCheckpoint", config.modelRoots?.checkpoint);
    setField("modelDiffusion", config.modelRoots?.diffusion_model);
    setField("modelVae", config.modelRoots?.vae);
    setField("modelTextEncoder", config.modelRoots?.text_encoder);
    setField("modelUpscaler", config.modelRoots?.upscaler);
    setField("modelControlnet", config.modelRoots?.controlnet);
  }

  async function openSettings() {
    elements.configAction.disabled = true;
    text(elements.settingsNotice, "正在读取现有配置…");
    try {
      const result = await callHost("getWorkerConfig");
      populateWorkerConfig(result?.config || {});
      text(elements.settingsNotice, "保存前不会修改现有配置。");
      elements.settingsOverlay.hidden = false;
      document.querySelector(product === 'desktop' ? '#comfyUiUrl' : '#bridgeRoot')?.focus();
    } catch (error) {
      showToast(error instanceof Error ? error.message : "配置读取失败");
    } finally {
      elements.configAction.disabled = false;
    }
  }

  function closeSettings() {
    elements.settingsOverlay.hidden = true;
    if (resumeGuide) { resumeGuide = false; openGuide(); }
  }

  async function chooseFolder(button) {
    const field = document.querySelector(`#${button.dataset.folderFor}`);
    if (!field) return;
    const current = lines(field.value);
    button.disabled = true;
    try {
      const result = await callHost("chooseFolder", { initial: current.at(-1) || "" });
      if (!result?.path) return;
      const values = field.tagName === "TEXTAREA" ? [...current, result.path] : [result.path];
      field.value = [...new Set(values)].join("\n");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "目录选择没有完成");
    } finally {
      button.disabled = false;
    }
  }

  async function saveSettings(event) {
    event.preventDefault();
    const saveButton = elements.settingsForm.querySelector(".settings-save");
    saveButton.disabled = true;
    text(elements.settingsNotice, "正在校验并保存…");
    const value = (id) => document.querySelector(`#${id}`)?.value.trim() || "";
    try {
      const result = await callHost("saveWorkerConfig", {
        config: {
          bridgeRoot: value("bridgeRoot"),
          comfyUiUrl: value("comfyUiUrl"),
          loraRoots: lines(value("loraRoots")),
          modelRoots: {
            checkpoint: lines(value("modelCheckpoint")),
            diffusion_model: lines(value("modelDiffusion")),
            vae: lines(value("modelVae")),
            text_encoder: lines(value("modelTextEncoder")),
            upscaler: lines(value("modelUpscaler")),
            controlnet: lines(value("modelControlnet")),
          },
        },
      });
      if (result?.preview) {
        text(elements.settingsNotice, "预览模式不会写入配置。");
        return;
      }
      if (result?.status) render(result.status);
      closeSettings();
      showToast("配置已保存，旧配置已备份。");
    } catch (error) {
      text(elements.settingsNotice, error instanceof Error ? error.message : "配置保存失败");
    } finally {
      saveButton.disabled = false;
    }
  }

  const guide = document.querySelector('#setupGuide');
  let guideStep = 0, guideBusy = false, resumeGuide = false, guideShared = false;
  function guideStepTo(step) {
    guideStep = step;
    guide.querySelectorAll('[data-setup-step]').forEach(el => el.hidden = Number(el.dataset.setupStep) !== step);
    guide.querySelectorAll('.setup-track li').forEach((el,index) => {
      if (index === step) el.setAttribute('aria-current','step'); else el.removeAttribute('aria-current');
    });
    document.querySelector('#setupBack').hidden = step === 0;
    guide.querySelector(`[data-setup-step="${step}"] h3`)?.focus();
  }
  async function guideRun(action) {
    if (guideBusy) return;
    guideBusy = true;
    guide.querySelectorAll('button').forEach(el => el.disabled = true);
    text(document.querySelector('#setupNotice'), '正在检查，请稍候…');
    try { await action(); }
    catch (error) { text(document.querySelector('#setupNotice'), error.message || '操作未完成，请重试。'); }
    finally {
      guideBusy = false;
      guide.querySelectorAll('button').forEach(el => el.disabled = false);
      document.querySelector('#setupCopy').disabled = !guideShared;
    }
  }
  function openGuide() {
    if (product === 'mac') {
      callHost('openDeviceSettings').catch(error => showToast(error.message));
      return;
    }
    text(document.querySelector('#setupGuideTitle'), product === 'desktop' ? '在这台 Windows 上开始' : '让 Mac 连接这台 Windows');
    document.querySelector('#setupBridgeHelp').hidden = product === 'desktop';
    document.querySelector('#setupShareTab').hidden = product === 'desktop';
    const finalTab = guide.querySelector('.setup-track li:last-child');
    text(finalTab, product === 'desktop' ? '02 检查状态' : '03 检查状态');
    guide.showModal();guideStepTo(guideStep);
  }
  async function readShare() {
    guideShared = false;document.querySelector('#setupAddress').value = '';
    if (!hasNativeHost()) {
      text(document.querySelector('#setupShareFolder'), '预览示例：D:\\PromptHub-Bridge');
      text(document.querySelector('#setupShareDetail'), '预览不检查系统共享。实际 App 会读取共享名称，不改变权限。');
      text(document.querySelector('#setupNotice'), '界面预览 · 没有连接实际 Windows。');return;
    }
    const info = await callHost('getPairingInfo');
    text(document.querySelector('#setupShareFolder'), `待共享文件夹：${info.shareFolder || '请先完成本机设置'}`);
    text(document.querySelector('#setupShareDetail'), info.detail);
    document.querySelector('#setupAddress').value = info.addresses?.[0] || '';
    guideShared = Boolean(info.addresses?.length);
    text(document.querySelector('#setupNotice'), guideShared ? '共享名称已读取；Mac 登录与读写权限尚待验收。' : '未确认共享。请按提示设置后重新检测；也可在 Mac 手动填写地址与共享名称。');
  }
  async function checkGuide() {
    guideStepTo(2);
    const result = await callHost('getStatus'), status = result?.status || result;
    if (hasNativeHost()) render(status);
    const current = hasNativeHost() ? status : latestStatus;
    const checks = product === 'desktop'
      ? [['工作台服务', ['READY','EXTERNAL'].includes(current.coreState)], ['本机 Worker', ['RUNNING','EXTERNAL'].includes(current.localWorkerState)], ['ComfyUI', current.localComfyState === 'REACHABLE']]
      : [['Windows Worker', ['RUNNING','EXTERNAL'].includes(current.coreState)], ['ComfyUI', current.comfyState === 'REACHABLE']];
    document.querySelector('#setupChecks').replaceChildren(...checks.map(([label,ok]) => {
      const row=document.createElement('li'),name=document.createElement('span'),value=document.createElement('strong');
      name.textContent=label;value.textContent=ok?'已就绪':'尚未就绪';row.append(name,value);return row;
    }));
    text(document.querySelector('#setupCheckHelp'), product === 'desktop'
      ? '无需连接其他设备。ComfyUI 未就绪时，请启动它并在本机设置中核对地址；Worker 未启动时返回主界面检查服务。'
      : '这只是 Windows 本机检查。请到 Mac 的配对引导完成系统登录与共享读写验收。');
    text(document.querySelector('#setupNotice'), !hasNativeHost() ? '界面预览 · 状态为示例，不代表实机。' : checks.every(([,ok])=>ok) ? '本机检查通过。' : '检查完成，仍有项目需要处理。');
  }
  document.querySelector('#setupGuideAction').addEventListener('click',openGuide);
  document.querySelector('#setupGuideClose').addEventListener('click',()=>guide.close());
  guide.addEventListener('cancel',event=>{if(guideBusy)event.preventDefault();});
  guide.addEventListener('close',()=>document.querySelector('#setupGuideAction').focus());
  document.querySelector('#setupEdit').addEventListener('click',()=>{resumeGuide=true;guide.close();openSettings();});
  document.querySelector('#setupNext').addEventListener('click',()=>guideRun(async()=>{if(product==='desktop')await checkGuide();else{guideStepTo(1);await readShare();}}));
  document.querySelector('#setupReadShare').addEventListener('click',()=>guideRun(readShare));
  document.querySelector('#setupOpenFolder').addEventListener('click',()=>guideRun(async()=>{const result=await callHost('openShareFolder');text(document.querySelector('#setupNotice'),result.message || '预览不会打开系统文件夹。');}));
  document.querySelector('#setupCopy').addEventListener('click',()=>guideRun(async()=>{const result=await callHost('copyPairingAddress');text(document.querySelector('#setupNotice'),result.message);}));
  document.querySelector('#setupToCheck').addEventListener('click',()=>guideRun(checkGuide));
  document.querySelector('#setupCheck').addEventListener('click',()=>guideRun(checkGuide));
  document.querySelector('#setupBack').addEventListener('click',()=>guideStepTo(product==='desktop'?0:guideStep-1));
  document.querySelector('#setupFinish').addEventListener('click',()=>guide.close());

  configureProduct();
  document.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("click", () => runCommand(button));
  });
  elements.configAction?.addEventListener("click", openSettings);
  document.querySelectorAll("[data-settings-close]").forEach((button) => {
    button.addEventListener("click", closeSettings);
  });
  document.querySelectorAll("[data-folder-for]").forEach((button) => {
    button.addEventListener("click", () => chooseFolder(button));
  });
  elements.settingsForm?.addEventListener("submit", saveSettings);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !elements.settingsOverlay.hidden) closeSettings();
  });

  window.SodaDesktop = Object.freeze({
    receiveStatus(status) {
      render(status);
    },
    resolve(id, payload) {
      const request = pending.get(id);
      if (!request) return;
      pending.delete(id);
      request.resolve(payload);
    },
    reject(id, message) {
      const request = pending.get(id);
      if (!request) return;
      pending.delete(id);
      request.reject(new Error(message || "原生操作失败"));
    },
  });

  const preview = !hasNativeHost() ? previewStatus(params.get("preview")) : null;
  if (preview) {
    render(preview);
  } else {
    render(fallbackStatus);
    callHost("getStatus")
      .then((result) => render(result?.status || result))
      .catch((error) => showToast(error.message));
  }
})();
