using System.Diagnostics;
using System.Globalization;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using SodaPromptHub.ComputeWorker;

namespace SodaPromptHub.Desktop;

internal sealed class DesktopHost : IDisposable
{
    private static readonly string[] BridgeDirectories = ["outbox", "inbox", "processing", "completed", "failed"];
    private readonly HttpClient httpClient = new() { Timeout = TimeSpan.FromSeconds(2) };
    private readonly object processGate = new();
    private readonly WorkerHost worker = new(localDesktop: true);
    private readonly SemaphoreSlim localStartGate = new(1, 1);
    private string? localComputeError;
    private Process? ownedCore;
    private bool starting;
    private bool checkedOnce;
    private string? lastError;

    internal DesktopHost()
    {
        AppRoot = AppContext.BaseDirectory;
        CoreRoot = Path.Combine(AppRoot, "core");
        UiRoot = Path.Combine(AppRoot, "desktop-ui");
        DataRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
            "Soda Prompt Hub");
        LibraryRoot = Path.Combine(DataRoot, "prompt-library");
        LocalBridgeMount = Path.Combine(DataRoot, "Bridge");
        LocalBridgeRoot = Path.Combine(LocalBridgeMount, "prompt-hub");
        LogsRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Soda Prompt Hub",
            "Logs");
        worker.StatusChanged += (_, _) => StatusChanged?.Invoke(this, EventArgs.Empty);
    }

    internal string AppRoot { get; }
    internal string CoreRoot { get; }
    internal string UiRoot { get; }
    internal string DataRoot { get; }
    internal string LibraryRoot { get; }
    internal string LocalBridgeMount { get; }
    internal string LocalBridgeRoot { get; }
    internal string LogsRoot { get; }
    internal event EventHandler? StatusChanged;

    internal async Task<Dictionary<string, object?>> GetStatusAsync()
    {
        var health = await ReadHealthAsync();
        var ownedRunning = IsOwnedCoreRunning();
        var externalCore = health.IsPromptHub && !ownedRunning;
        var localComputeConfigured = IsLocalComputeConfigured();
        Dictionary<string, object?>? workerStatus = null;
        if (localComputeConfigured)
        {
            workerStatus = await worker.GetStatusAsync();
        }

        var phase = health.IsPromptHub ? "ready" : starting || !checkedOnce ? "checking" : "attention";
        var errorTitle = string.Empty;
        var errorDetail = string.Empty;
        if (!health.IsPromptHub && checkedOnce && !starting)
        {
            if (health.Reachable)
            {
                errorTitle = "端口被其他服务占用";
                errorDetail = "127.0.0.1:8765 已响应，但不是 Soda Prompt Hub。启动器没有覆盖或停止它。";
            }
            else
            {
                errorTitle = "本机 Core 没有响应";
                errorDetail = lastError ?? "请重试启动；若仍未完成，请打开 Core 日志查看原因。";
            }
        }

        var workerState = Value(workerStatus, "coreState", "STOPPED");
        var workerDetail = Value(workerStatus, "coreDetail", "完成设置后可在本机运行 Worker");
        var workerCommand = Value(workerStatus, "primaryCommand", "startWorker");
        var computeState = localComputeConfigured
            ? workerState switch
            {
                "RUNNING" => "LOCAL",
                "EXTERNAL" => "EXTERNAL",
                _ => Value(workerStatus, "comfyState", "READY") == "REACHABLE" ? "READY" : "CONFIGURED",
            }
            : "OPTIONAL";
        var computeDetail = localComputeError ?? (localComputeConfigured
            ? workerState is "RUNNING" or "EXTERNAL" && Value(workerStatus, "comfyState", "OFFLINE") == "OFFLINE"
                ? "Worker 已准备 · 等待本机 ComfyUI"
                : workerDetail
            : "正在自动准备本机计算");
        var computeActionLabel = workerCommand == "stopWorker" ? "停止本机计算" : "启动本机计算";
        var canComputeAction = localComputeConfigured && Bool(workerStatus, "canPrimary");

        var coreState = health.IsPromptHub ? externalCore ? "EXTERNAL" : "READY" : starting ? "STARTING" : "STOPPED";
        var coreDetail = health.IsPromptHub
            ? externalCore ? "已有本机 Core · 不接管" : $"PID {OwnedCoreId()} · 127.0.0.1:8765"
            : "127.0.0.1:8765";
        var stepTitle = health.IsPromptHub
            ? "本机工作台已经准备好"
            : starting
                ? "正在启动 Prompt Hub Core"
                : errorTitle.Length > 0 ? errorTitle : "正在检查本机服务";
        var stepDetail = health.IsPromptHub
            ? "Core 与资料库都在这台 Windows 设备上。"
            : starting
                ? "首次运行可能需要准备 Python 环境；进度会写入 setup.log。"
                : errorDetail.Length > 0 ? errorDetail : "正在确认端口、资料目录和 Python 环境。";

        return new Dictionary<string, object?>
        {
            ["phase"] = phase,
            ["step"] = health.IsPromptHub ? 5 : starting ? 3 : 2,
            ["stepTitle"] = stepTitle,
            ["stepDetail"] = stepDetail,
            ["coreState"] = coreState,
            ["coreDetail"] = coreDetail,
            ["libraryState"] = Directory.Exists(LibraryRoot) ? "LOCAL" : "READY",
            ["libraryDetail"] = LibraryRoot,
            ["computeState"] = computeState,
            ["computeDetail"] = computeDetail,
            ["localWorkerState"] = workerState,
            ["localComfyState"] = Value(workerStatus, "comfyState", "UNKNOWN"),
            ["version"] = health.Version ?? ReadReleaseVersion(),
            ["releaseChannel"] = health.ReleaseChannel is null
                ? "Stable · Windows local first"
                : $"{health.ReleaseChannel} · Windows local first",
            ["checkedAt"] = DateTime.Now.ToString("HH:mm:ss", CultureInfo.InvariantCulture),
            ["canPrimary"] = health.IsPromptHub || (!starting && !health.Reachable),
            ["canRestart"] = health.IsPromptHub && ownedRunning,
            ["primaryCommand"] = health.IsPromptHub ? "openWorkspace" : "retryCore",
            ["primaryLabel"] = health.IsPromptHub ? "打开工作台" : starting ? "正在启动" : "重试启动",
            ["errorTitle"] = errorTitle,
            ["errorDetail"] = errorDetail,
            ["buildLabel"] = health.IsPromptHub ? "WINDOWS / LOCAL" : "LOCAL FIRST",
            ["canComputeAction"] = canComputeAction,
            ["computeActionLabel"] = computeActionLabel,
        };
    }

    internal async Task<Dictionary<string, object?>> StartCoreAsync()
    {
        var health = await ReadHealthAsync();
        if (health.IsPromptHub)
        {
            checkedOnce = true;
            return await GetStatusAsync();
        }
        if (health.Reachable)
        {
            checkedOnce = true;
            lastError = "端口 8765 已由其他服务使用。";
            return await GetStatusAsync();
        }

        bool alreadyRunning;
        lock (processGate)
        {
            alreadyRunning = ownedCore is { HasExited: false };
            starting = true;
            checkedOnce = true;
            lastError = null;
        }
        if (alreadyRunning)
        {
            starting = false;
            return await GetStatusAsync();
        }
        StatusChanged?.Invoke(this, EventArgs.Empty);

        try
        {
            EnsureDataDirectories();
            await EnsureGitRuntimeAsync();
            var python = await EnsurePythonRuntimeAsync();
            var logPath = Path.Combine(LogsRoot, "core.log");
            var process = new Process
            {
                StartInfo = CreateCoreStartInfo(python),
                EnableRaisingEvents = true,
            };
            AttachLog(process, logPath);
            process.Exited += (_, _) =>
            {
                if (process.ExitCode != 0)
                {
                    lastError = $"Core 已退出，exit code {process.ExitCode}。请查看 core.log。";
                }
                StatusChanged?.Invoke(this, EventArgs.Empty);
            };
            if (!process.Start())
            {
                throw new InvalidOperationException("Windows 没有创建 Core 进程。");
            }
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            lock (processGate)
            {
                ownedCore = process;
            }

            var deadline = DateTime.UtcNow.AddSeconds(45);
            while (DateTime.UtcNow < deadline)
            {
                if (process.HasExited)
                {
                    throw new InvalidOperationException($"Core 启动后退出，exit code {process.ExitCode}。请查看 core.log。");
                }
                if ((await ReadHealthAsync()).IsPromptHub)
                {
                    if (IsLocalComputeConfigured())
                    {
                        await ConfigureLocalNodeAsync();
                    }
                    return await GetStatusAsync();
                }
                await Task.Delay(500);
            }
            throw new TimeoutException("Core 在 45 秒内没有响应。请查看 core.log。");
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or TimeoutException or System.ComponentModel.Win32Exception)
        {
            lastError = error.Message;
        }
        finally
        {
            starting = false;
            StatusChanged?.Invoke(this, EventArgs.Empty);
        }
        return await GetStatusAsync();
    }

    internal async Task<Dictionary<string, object?>> RestartCoreAsync()
    {
        var health = await ReadHealthAsync();
        if (health.IsPromptHub && !IsOwnedCoreRunning())
        {
            lastError = "当前 Core 不是由这个启动器启动的，因此不会被重新启动。";
            checkedOnce = true;
            return await GetStatusAsync();
        }
        await StopCoreAsync();
        return await StartCoreAsync();
    }

    internal async Task StopCoreAsync()
    {
        Process? process;
        lock (processGate)
        {
            process = ownedCore;
        }
        if (process is null || process.HasExited)
        {
            return;
        }
        try
        {
            process.Kill(entireProcessTree: true);
            await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(8));
            lastError = null;
        }
        catch (Exception error) when (error is InvalidOperationException or System.ComponentModel.Win32Exception or TimeoutException)
        {
            lastError = $"停止 Core 失败：{error.Message}";
        }
        StatusChanged?.Invoke(this, EventArgs.Empty);
    }

    internal async Task<Dictionary<string, object?>> ToggleLocalWorkerAsync()
    {
        if (!IsLocalComputeConfigured())
        {
            throw new InvalidOperationException("请先打开“设置”，保存本机 ComfyUI 与模型目录。 ");
        }
        var status = await worker.GetStatusAsync();
        var command = Value(status, "primaryCommand", "startWorker");
        if (command == "stopWorker")
        {
            await worker.StopAsync();
        }
        else
        {
            await ConfigureLocalNodeAsync();
            await worker.StartAsync();
        }
        return await GetStatusAsync();
    }

    internal Dictionary<string, object?> GetEditableWorkerConfig()
    {
        var config = worker.GetEditableConfig();
        config["bridgeRoot"] = LocalBridgeRoot;
        return config;
    }

    internal async Task<Dictionary<string, object?>> SaveLocalWorkerConfigAsync(JsonElement config)
    {
        if (worker.HasActiveTask()) throw new InvalidOperationException("任务执行中，请完成后再修改 ComfyUI 设置。");
        var running = await worker.GetStatusAsync();
        if (Value(running, "coreState", "STOPPED") == "RUNNING") await worker.StopAsync();
        EnsureBridgeDirectories();
        var root = JsonNode.Parse(config.GetRawText()) as JsonObject
            ?? throw new InvalidOperationException("本机计算配置无效。");
        root["bridgeRoot"] = LocalBridgeRoot;
        using var document = JsonDocument.Parse(root.ToJsonString());
        worker.SaveConfig(document.RootElement);
        if ((await ReadHealthAsync()).IsPromptHub)
        {
            await ConfigureLocalNodeAsync();
        }
        await StartLocalWorkspaceAsync();
        return await GetStatusAsync();
    }

    internal async Task<bool> StopOwnedServicesAsync()
    {
        if (worker.HasActiveTask())
        {
            return false;
        }
        await worker.StopAsync();
        await StopCoreAsync();
        return true;
    }

    internal async Task OpenWorkspaceAsync()
    {
        // Called from WinForms: never block its synchronization context on HTTP.
        var health = await ReadHealthAsync();
        if (!health.IsPromptHub)
        {
            throw new InvalidOperationException("Core 尚未就绪，不能打开工作台。 ");
        }
        OpenPath("http://127.0.0.1:8765/");
    }

    internal void OpenLogs()
    {
        Directory.CreateDirectory(LogsRoot);
        OpenPath(LogsRoot);
    }

    internal void OpenDataFolder()
    {
        Directory.CreateDirectory(DataRoot);
        OpenPath(DataRoot);
    }

    internal async Task<string> ExportDiagnosticsAsync()
    {
        var status = await GetStatusAsync();
        var archive = DiagnosticBundle.Create(
            "Soda-Prompt-Hub",
            "Soda Prompt Hub",
            Convert.ToString(status["version"], CultureInfo.InvariantCulture) ?? ReadReleaseVersion(),
            File.Exists(Path.Combine(AppRoot, "INSTALL_MODE.json")),
            status,
            LogsRoot,
            [
                Path.Combine(CoreRoot, "RELEASE.json"),
                Path.Combine(AppRoot, "INSTALL_MODE.json"),
                Path.Combine(AppRoot, "PYTHON_RUNTIME.json"),
            ]);
        DiagnosticBundle.Reveal(archive);
        return archive;
    }

    internal void OpenWorkerConfig() => worker.OpenConfig();

    internal bool IsOwnedCoreRunning()
    {
        lock (processGate)
        {
            return ownedCore is { HasExited: false };
        }
    }

    public void Dispose()
    {
        httpClient.Dispose();
        worker.Dispose();
        lock (processGate)
        {
            ownedCore?.Dispose();
            ownedCore = null;
        }
    }

    private void EnsureDataDirectories()
    {
        Directory.CreateDirectory(LibraryRoot);
        Directory.CreateDirectory(LogsRoot);
    }

    private void EnsureBridgeDirectories()
    {
        Directory.CreateDirectory(LocalBridgeRoot);
        foreach (var name in BridgeDirectories)
        {
            Directory.CreateDirectory(Path.Combine(LocalBridgeRoot, name));
        }
    }

    private bool IsLocalComputeConfigured()
    {
        var configPath = worker.ConfigPath;
        if (!File.Exists(configPath))
        {
            return false;
        }
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(configPath));
            var root = document.RootElement;
            var bridge = root.GetProperty("bridge_root").GetString() ?? string.Empty;
            return string.Equals(
                Path.GetFullPath(bridge).TrimEnd(Path.DirectorySeparatorChar),
                Path.GetFullPath(LocalBridgeRoot).TrimEnd(Path.DirectorySeparatorChar),
                StringComparison.OrdinalIgnoreCase);
        }
        catch (Exception error) when (error is IOException or JsonException or ArgumentException)
        {
            return false;
        }
    }

    private async Task ConfigureLocalNodeAsync()
    {
        EnsureBridgeDirectories();
        var contract = await httpClient.GetFromJsonAsync<JsonObject>("http://127.0.0.1:8765/api/compute/contract");
        var capabilities = contract?["roles"]?["compute_5060ti"]?["capabilities"]?.DeepClone()
            ?? new JsonArray("comfyui_generate", "lora_catalog_snapshot", "model_catalog_snapshot");
        var node = new JsonObject
        {
            ["label"] = "本机 Windows 计算",
            ["role"] = "compute_5060ti",
            ["host"] = "127.0.0.1",
            ["smb_mount"] = LocalBridgeMount,
            ["enabled"] = true,
            ["capabilities"] = capabilities,
            ["notes"] = "由 Soda Prompt Hub Desktop 配置的本机 bridge。",
        };
        using var put = await httpClient.PutAsJsonAsync(
            "http://127.0.0.1:8765/api/remote-nodes/compute-5060ti",
            node);
        put.EnsureSuccessStatusCode();
        using var prepare = await httpClient.PostAsync(
            "http://127.0.0.1:8765/api/remote-nodes/compute-5060ti/prepare",
            content: null);
        prepare.EnsureSuccessStatusCode();
    }

    internal async Task StartLocalWorkspaceAsync()
    {
        await localStartGate.WaitAsync();
        try
        {
            if (!(await ReadHealthAsync()).IsPromptHub) return;
            using var healthResponse = await httpClient.GetAsync("http://127.0.0.1:8765/api/health");
            using var healthDocument = JsonDocument.Parse(await healthResponse.Content.ReadAsStringAsync());
            var database = healthDocument.RootElement.GetProperty("database").GetString() ?? "";
            if (!Path.GetFullPath(database).StartsWith(Path.GetFullPath(LibraryRoot) + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("当前 WebUI 使用另一份资料库，不会自动改写它的设备配置。");
            EnsureBridgeDirectories();
            EnsureLocalWorkerConfig();
            await ConfigureLocalNodeAsync();
            var status = await worker.GetStatusAsync();
            if (Value(status, "coreState", "STOPPED") is not ("RUNNING" or "EXTERNAL"))
            {
                await worker.StartAsync();
            }
            var current = await worker.GetStatusAsync();
            localComputeError = Value(current, "coreState", "STOPPED") is "RUNNING" or "EXTERNAL"
                ? null : Value(current, "errorDetail", "本机 Worker 没有启动，请检查日志。");
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or HttpRequestException or TaskCanceledException)
        {
            localComputeError = $"本机计算未就绪：{error.Message}";
        }
        finally
        {
            localStartGate.Release();
            StatusChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    private void EnsureLocalWorkerConfig()
    {
        if (File.Exists(worker.ConfigPath))
        {
            if (!IsLocalComputeConfigured())
                throw new InvalidOperationException("现有配置属于远程 Worker，未覆盖。请在设置中确认本机计算目录。");
            return;
        }
        // Import only a previous Desktop configuration; never copy a remote bridge profile.
        var legacyPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Soda Prompt Hub", "Compute Worker", "worker-config.json");
        JsonObject? config = null;
        if (File.Exists(legacyPath))
        {
            var candidate = JsonNode.Parse(File.ReadAllText(legacyPath)) as JsonObject;
            if (string.Equals(candidate?["bridge_root"]?.GetValue<string>(), LocalBridgeRoot,
                StringComparison.OrdinalIgnoreCase)) config = candidate;
        }
        config ??= new JsonObject
        {
            ["bridge_root"] = LocalBridgeRoot,
            ["comfyui_url"] = "http://127.0.0.1:8188",
            ["role"] = "compute_5060ti",
            ["lora_roots"] = new JsonArray(),
            ["model_roots"] = new JsonArray(),
        };
        config["worker_id"] = "desktop-local-worker";
        Directory.CreateDirectory(worker.StateRoot);
        var temporary = worker.ConfigPath + ".initial.tmp";
        File.WriteAllText(temporary, config.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temporary, worker.ConfigPath, overwrite: false);
    }

    private async Task EnsureGitRuntimeAsync()
    {
        var executable = GitRuntime.Resolve(AppRoot);
        if (executable is not null && await RunProbeAsync(new PythonCommand(executable, []), "--version") != 0)
            throw new InvalidOperationException("内置 Git 无法运行，资料库拉取不可用。请重新安装完整的 Windows Desktop 安装包。");
    }

    private async Task<PythonCommand> EnsurePythonRuntimeAsync()
    {
        var localPython = Path.Combine(AppRoot, ".venv", "Scripts", "python.exe");
        if (File.Exists(localPython) && await CanRunCoreAsync(new PythonCommand(localPython, [])))
        {
            return new PythonCommand(localPython, []);
        }

        var configured = Environment.GetEnvironmentVariable("SODA_PROMPT_HUB_PYTHON");
        var candidates = new List<PythonCommand>();
        if (!string.IsNullOrWhiteSpace(configured) && Path.IsPathFullyQualified(configured) && File.Exists(configured))
        {
            candidates.Add(new PythonCommand(configured, []));
        }
        var bundledPython = Path.Combine(AppRoot, "runtime", "python", "python.exe");
        if (File.Exists(bundledPython))
        {
            candidates.Add(new PythonCommand(bundledPython, []));
        }
        candidates.Add(new PythonCommand("py.exe", ["-3.12"]));
        candidates.Add(new PythonCommand("python.exe", []));

        foreach (var candidate in candidates)
        {
            if (await CanRunCoreAsync(candidate))
            {
                return candidate;
            }
        }

        PythonCommand? bootstrap = null;
        foreach (var candidate in candidates)
        {
            if (await IsPython312Async(candidate))
            {
                bootstrap = candidate;
                break;
            }
        }
        if (bootstrap is null)
        {
            throw new InvalidOperationException("找不到 Python 3.12。请安装 Python 3.12，或设置 SODA_PROMPT_HUB_PYTHON。");
        }
        await RunSetupAsync(bootstrap, "-m", "venv", Path.Combine(AppRoot, ".venv"));
        var installed = new PythonCommand(localPython, []);
        await RunSetupAsync(
            installed,
            "-m", "pip", "install", "--disable-pip-version-check", "--editable", CoreRoot);
        if (!await CanRunCoreAsync(installed))
        {
            throw new InvalidOperationException("Python 运行环境已创建，但 Core 依赖校验没有通过。请查看 setup.log。");
        }
        return installed;
    }

    private async Task<bool> CanRunCoreAsync(PythonCommand command)
    {
        return await RunProbeAsync(command, "-c", "import fastapi, uvicorn, prompt_hub") == 0;
    }

    private async Task<bool> IsPython312Async(PythonCommand command)
    {
        return await RunProbeAsync(
            command,
            "-c", "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)") == 0;
    }

    private async Task<int> RunProbeAsync(PythonCommand command, params string[] arguments)
    {
        try
        {
            using var process = new Process { StartInfo = CreatePythonStartInfo(command, redirect: true) };
            foreach (var argument in arguments)
            {
                process.StartInfo.ArgumentList.Add(argument);
            }
            ApplyCoreEnvironment(process.StartInfo);
            process.Start();
            await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(8));
            return process.ExitCode;
        }
        catch (Exception error) when (error is System.ComponentModel.Win32Exception or InvalidOperationException or TimeoutException)
        {
            return -1;
        }
    }

    private async Task RunSetupAsync(PythonCommand command, params string[] arguments)
    {
        Directory.CreateDirectory(LogsRoot);
        var info = CreatePythonStartInfo(command, redirect: true);
        foreach (var argument in arguments)
        {
            info.ArgumentList.Add(argument);
        }
        ApplyCoreEnvironment(info);
        using var process = new Process { StartInfo = info };
        process.Start();
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync().WaitAsync(TimeSpan.FromMinutes(15));
        var output = (await stdout) + (await stderr);
        await File.AppendAllTextAsync(
            Path.Combine(LogsRoot, "setup.log"),
            $"[{DateTimeOffset.Now:O}] {command.FileName} {string.Join(' ', arguments)}{Environment.NewLine}{output}{Environment.NewLine}",
            Encoding.UTF8);
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException($"准备 Python 运行环境失败，exit code {process.ExitCode}。请查看 setup.log。");
        }
    }

    private ProcessStartInfo CreateCoreStartInfo(PythonCommand python)
    {
        var info = CreatePythonStartInfo(python, redirect: true);
        info.ArgumentList.Add("-m");
        info.ArgumentList.Add("prompt_hub");
        info.ArgumentList.Add("serve");
        info.ArgumentList.Add("--host");
        info.ArgumentList.Add("127.0.0.1");
        info.ArgumentList.Add("--port");
        info.ArgumentList.Add("8765");
        ApplyCoreEnvironment(info);
        return info;
    }

    private ProcessStartInfo CreatePythonStartInfo(PythonCommand python, bool redirect)
    {
        var info = new ProcessStartInfo
        {
            FileName = python.FileName,
            WorkingDirectory = CoreRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
            RedirectStandardOutput = redirect,
            RedirectStandardError = redirect,
        };
        foreach (var argument in python.PrefixArguments)
        {
            info.ArgumentList.Add(argument);
        }
        return info;
    }

    private void ApplyCoreEnvironment(ProcessStartInfo info)
    {
        GitRuntime.Configure(info, AppRoot);
        info.Environment["PYTHONPATH"] = Path.Combine(CoreRoot, "src");
        info.Environment["PYTHONUTF8"] = "1";
        info.Environment["PYTHONUNBUFFERED"] = "1";
        info.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        info.Environment["ORT_DISABLE_TELEMETRY"] = "1";
        info.Environment["PROMPT_HUB_LIBRARY_ROOT"] = LibraryRoot;
    }

    private static void AttachLog(Process process, string path)
    {
        var gate = new object();
        void WriteLine(object sender, DataReceivedEventArgs eventArgs)
        {
            if (eventArgs.Data is null)
            {
                return;
            }
            lock (gate)
            {
                File.AppendAllText(path, eventArgs.Data + Environment.NewLine, Encoding.UTF8);
            }
        }
        process.OutputDataReceived += WriteLine;
        process.ErrorDataReceived += WriteLine;
    }

    private async Task<HealthResult> ReadHealthAsync()
    {
        try
        {
            using var response = await httpClient.GetAsync("http://127.0.0.1:8765/api/health");
            if (!response.IsSuccessStatusCode)
            {
                return new HealthResult(true, false, null, null);
            }
            using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            var root = document.RootElement;
            var service = root.TryGetProperty("service", out var serviceValue) ? serviceValue.GetString() : null;
            var version = root.TryGetProperty("version", out var versionValue) ? versionValue.GetString() : null;
            var channel = root.TryGetProperty("release_channel", out var channelValue) ? channelValue.GetString() : null;
            return new HealthResult(
                true,
                string.Equals(service, "soda-prompt-hub", StringComparison.Ordinal),
                version,
                channel);
        }
        catch (Exception error) when (error is HttpRequestException or TaskCanceledException or JsonException)
        {
            return new HealthResult(false, false, null, null);
        }
    }

    private static string BundledVersion => typeof(DesktopHost).Assembly.GetName().Version?.ToString(3) ?? "unknown";

    private string ReadReleaseVersion()
    {
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(Path.Combine(CoreRoot, "RELEASE.json")));
            return document.RootElement.GetProperty("product_version").GetString() ?? BundledVersion;
        }
        catch (Exception error) when (error is IOException or JsonException or KeyNotFoundException)
        {
            return BundledVersion;
        }
    }

    private int? OwnedCoreId()
    {
        lock (processGate)
        {
            return ownedCore is { HasExited: false } ? ownedCore.Id : null;
        }
    }

    private static string Value(Dictionary<string, object?>? values, string key, string fallback)
    {
        return values is not null && values.TryGetValue(key, out var value) && value is not null
            ? Convert.ToString(value, CultureInfo.InvariantCulture) ?? fallback
            : fallback;
    }

    private static bool Bool(Dictionary<string, object?>? values, string key)
    {
        return values is not null && values.TryGetValue(key, out var value) && value is true;
    }

    private static void OpenPath(string value)
    {
        Process.Start(new ProcessStartInfo(value) { UseShellExecute = true });
    }

    private sealed record PythonCommand(string FileName, IReadOnlyList<string> PrefixArguments);
    private sealed record HealthResult(bool Reachable, bool IsPromptHub, string? Version, string? ReleaseChannel);
}
