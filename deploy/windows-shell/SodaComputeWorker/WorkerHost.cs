using System.Diagnostics;
using System.Globalization;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace SodaPromptHub.ComputeWorker;

internal sealed class WorkerHost : IDisposable
{
    private const string ExpectedProtocol = "soda-compute-bridge-v2";
    private static readonly (string Field, string AssetType, string DefaultRootId)[] ModelTypes =
    [
        ("checkpoint", "checkpoint", "comfyui-checkpoints"),
        ("diffusion_model", "diffusion_model", "comfyui-diffusion-models"),
        ("vae", "vae", "comfyui-vae"),
        ("text_encoder", "text_encoder", "comfyui-text-encoders"),
        ("upscaler", "upscaler", "comfyui-upscalers"),
        ("controlnet", "controlnet", "comfyui-controlnet"),
    ];
    private readonly HttpClient httpClient = new() { Timeout = TimeSpan.FromSeconds(2) };
    private readonly object processGate = new();
    private Process? ownedProcess;
    private string? lastError;
    private bool starting;

    internal WorkerHost(bool localDesktop = false)
    {
        AppRoot = AppContext.BaseDirectory;
        WorkerRoot = File.Exists(Path.Combine(AppRoot, "prompt_hub_worker.py"))
            ? AppRoot
            : Path.Combine(AppRoot, "worker");
        UiRoot = Path.Combine(AppRoot, "desktop-ui");
        var installedMode = File.Exists(Path.Combine(AppRoot, "INSTALL_MODE.json"));
        StateRoot = installedMode
            ? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Soda Prompt Hub",
                localDesktop ? "Desktop Worker" : "Compute Worker")
            : WorkerRoot;
        ConfigPath = Path.Combine(StateRoot, "worker-config.json");
        LogsRoot = Path.Combine(StateRoot, installedMode ? "Logs" : "logs");
    }

    internal string AppRoot { get; }
    internal string WorkerRoot { get; }
    internal string UiRoot { get; }
    internal string StateRoot { get; }
    internal string ConfigPath { get; }
    internal string LogsRoot { get; }

    internal event EventHandler? StatusChanged;

    internal async Task<Dictionary<string, object?>> GetStatusAsync()
    {
        var release = ReadObject(Path.Combine(WorkerRoot, "RELEASE.json"));
        var version = GetString(release, "worker_version", BundledVersion);
        var channel = GetString(release, "release_channel", "stable");
        var protocol = GetString(release, "protocol_version", ExpectedProtocol);
        var configResult = ReadConfig();
        var workerRunning = IsOwnedProcessRunning();
        var externalWorker = !workerRunning && configResult.Config is not null && IsExternalWorkerRunning(configResult.Config.WorkerId);
        var anyWorkerRunning = workerRunning || externalWorker;
        var status = configResult.Config is null
            ? null
            : ReadObject(Path.Combine(configResult.Config.BridgeRoot, "worker-status.json"));
        var comfyReachable = configResult.Config is not null
            && await IsComfyUiReachableAsync(configResult.Config.ComfyUiUrl);
        var task = configResult.Config is null ? null : FindCurrentTask(configResult.Config.BridgeRoot);
        var gpu = ReadGpu(status);
        var checkedAt = DateTime.Now.ToString("HH:mm:ss", CultureInfo.InvariantCulture);

        if (configResult.Config is null)
        {
            return Status(
                phase: "attention",
                step: 1,
                stepTitle: "需要完成 Worker 配置",
                stepDetail: configResult.Error ?? "worker-config.json 不存在",
                coreState: "STOPPED",
                coreDetail: "Worker 尚未启动",
                bridgeState: "CONFIG",
                bridgeDetail: "请检查 worker-config.json",
                gpuState: "UNKNOWN",
                gpuDetail: "完成自检后显示设备",
                comfyState: "UNKNOWN",
                comfyDetail: "等待读取本机地址",
                version: version,
                releaseDetail: ReleaseDetail(channel, protocol),
                checkedAt: checkedAt,
                canPrimary: false,
                canSelfTest: false,
                primaryCommand: "startWorker",
                primaryLabel: "需要配置",
                errorTitle: "Worker 配置不可用",
                errorDetail: configResult.Error ?? "请打开配置，填写这台电脑的 bridge 与 ComfyUI 路径。",
                task: task);
        }

        var config = configResult.Config;
        var bridgeReady = Directory.Exists(config.BridgeRoot);
        var statusReady = string.Equals(GetString(status, "status"), "ready", StringComparison.OrdinalIgnoreCase);
        var protocolReady = string.Equals(protocol, ExpectedProtocol, StringComparison.Ordinal);
        var phase = "idle";
        var errorTitle = string.Empty;
        var errorDetail = string.Empty;

        if (starting)
        {
            phase = "starting";
        }
        else if (!protocolReady)
        {
            phase = "attention";
            errorTitle = "Worker 协议不兼容";
            errorDetail = $"当前协议为 {protocol}，需要 {ExpectedProtocol}。";
        }
        else if (!bridgeReady)
        {
            phase = "attention";
            errorTitle = "Bridge 目录不可用";
            errorDetail = $"找不到 {config.BridgeRoot}。配置文件没有被修改。";
        }
        else if (!comfyReachable)
        {
            phase = "attention";
            errorTitle = "ComfyUI 尚未就绪";
            errorDetail = $"无法连接 {config.ComfyUiUrl}。请先启动 ComfyUI。";
        }
        else if (anyWorkerRunning && task is not null)
        {
            phase = "busy";
        }
        else if (anyWorkerRunning)
        {
            phase = "ready";
        }

        if (!string.IsNullOrWhiteSpace(lastError))
        {
            phase = "attention";
            errorTitle = "Worker 操作没有完成";
            errorDetail = lastError;
        }

        var canStop = workerRunning && task is null;
        var canStart = !anyWorkerRunning && bridgeReady && protocolReady;
        var primaryCommand = anyWorkerRunning ? "stopWorker" : "startWorker";
        var primaryLabel = task is not null
            ? "任务执行中"
            : externalWorker
                ? "外部 Worker 运行中"
                : anyWorkerRunning
                    ? "停止 Worker"
                    : "启动 Worker";
        var stepTitle = phase switch
        {
            "starting" => "正在启动后台 Worker",
            "attention" => errorTitle,
            "idle" => "设备已经通过检查",
            "busy" => "正在执行已校验任务",
            _ => "Worker 正在等待任务",
        };
        var stepDetail = phase switch
        {
            "starting" => "不会显示命令窗口，运行日志将写入 logs。",
            "idle" => "启动后可收起到系统托盘。",
            "busy" => task?.Detail ?? "任务执行中",
            _ => config.BridgeRoot,
        };
        var workerDetail = externalWorker
            ? "由命令行或另一控制台启动"
            : workerRunning
                ? $"PID {OwnedProcessId()} · background"
                : "随时可以启动";

        return Status(
            phase: phase,
            step: phase == "starting" ? 3 : 5,
            stepTitle: stepTitle,
            stepDetail: stepDetail,
            coreState: externalWorker ? "EXTERNAL" : anyWorkerRunning ? "RUNNING" : "STOPPED",
            coreDetail: workerDetail,
            bridgeState: bridgeReady ? task is null ? "READY" : "ACTIVE" : "OFFLINE",
            bridgeDetail: config.BridgeRoot,
            gpuState: string.IsNullOrWhiteSpace(gpu.Name) ? "UNKNOWN" : "CUDA",
            gpuDetail: gpu.Detail,
            comfyState: comfyReachable ? task is null ? "REACHABLE" : "GENERATING" : "OFFLINE",
            comfyDetail: $"{gpu.ComfyVersion} · {config.ComfyUiUrl}".Trim(' ', '·'),
            version: version,
            releaseDetail: ReleaseDetail(channel, protocol),
            checkedAt: checkedAt,
            canPrimary: canStart || canStop,
            canSelfTest: !anyWorkerRunning,
            primaryCommand: primaryCommand,
            primaryLabel: primaryLabel,
            errorTitle: errorTitle,
            errorDetail: errorDetail,
            task: task,
            statusReady: statusReady);
    }

    internal async Task<Dictionary<string, object?>> StartAsync()
    {
        bool alreadyRunning;
        lock (processGate)
        {
            alreadyRunning = ownedProcess is { HasExited: false };
            starting = true;
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
            var config = ReadConfig();
            if (config.Config is null)
            {
                throw new InvalidOperationException(config.Error ?? "worker-config.json 不可用");
            }
            if (IsExternalWorkerRunning(config.Config.WorkerId))
            {
                throw new InvalidOperationException("已有另一个 Worker 正在运行；当前控制台不会接管或停止它。");
            }
            // The receiver stays available while ComfyUI is starting or temporarily offline.

            Directory.CreateDirectory(LogsRoot);
            var python = await FindPythonAsync();
            var process = new Process
            {
                StartInfo = CreateWorkerStartInfo(python, "--log-file", Path.Combine(LogsRoot, "worker.log")),
                EnableRaisingEvents = true,
            };
            process.Exited += (_, _) =>
            {
                lock (processGate)
                {
                    if (!process.HasExited || process.ExitCode == 0)
                    {
                        lastError = null;
                    }
                    else
                    {
                        lastError = $"Worker 已退出，exit code {process.ExitCode}。请查看日志。";
                    }
                }
                StatusChanged?.Invoke(this, EventArgs.Empty);
            };
            if (!process.Start())
            {
                throw new InvalidOperationException("Windows 没有创建 Worker 进程。");
            }
            lock (processGate)
            {
                ownedProcess = process;
            }
            await Task.Delay(700);
            if (process.HasExited)
            {
                throw new InvalidOperationException($"Worker 启动后立即退出，exit code {process.ExitCode}。请查看日志。");
            }
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or System.ComponentModel.Win32Exception)
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

    internal async Task<Dictionary<string, object?>> StopAsync()
    {
        var config = ReadConfig().Config;
        if (config is not null && FindCurrentTask(config.BridgeRoot) is not null)
        {
            lastError = "任务执行中，未停止 Worker。请等待回传完成后再停止。";
            return await GetStatusAsync();
        }

        Process? process;
        lock (processGate)
        {
            process = ownedProcess;
        }
        if (process is null || process.HasExited)
        {
            lastError = IsExternalWorkerRunning(config?.WorkerId ?? string.Empty)
                ? "这个 Worker 不是由当前控制台启动的，因此不会被强制停止。"
                : null;
            return await GetStatusAsync();
        }

        try
        {
            process.Kill(entireProcessTree: true);
            await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(5));
            lastError = null;
        }
        catch (Exception error) when (error is InvalidOperationException or System.ComponentModel.Win32Exception or TimeoutException)
        {
            lastError = $"停止 Worker 失败：{error.Message}";
        }
        StatusChanged?.Invoke(this, EventArgs.Empty);
        return await GetStatusAsync();
    }

    internal async Task<Dictionary<string, object?>> SelfTestAsync()
    {
        if (IsOwnedProcessRunning())
        {
            lastError = "Worker 运行中无需重复自检；先停止 Worker 后再运行独立自检。";
            return await GetStatusAsync();
        }
        var config = ReadConfig();
        if (config.Config is null)
        {
            lastError = config.Error;
            return await GetStatusAsync();
        }
        if (IsExternalWorkerRunning(config.Config.WorkerId))
        {
            lastError = "检测到外部 Worker，独立自检会与它争用运行锁。";
            return await GetStatusAsync();
        }

        starting = true;
        lastError = null;
        StatusChanged?.Invoke(this, EventArgs.Empty);
        try
        {
            Directory.CreateDirectory(LogsRoot);
            var python = await FindPythonAsync();
            using var process = new Process
            {
                StartInfo = CreateWorkerStartInfo(python, "--self-test"),
            };
            process.StartInfo.RedirectStandardOutput = true;
            process.StartInfo.RedirectStandardError = true;
            process.Start();
            var stdoutTask = process.StandardOutput.ReadToEndAsync();
            var stderrTask = process.StandardError.ReadToEndAsync();
            await process.WaitForExitAsync().WaitAsync(TimeSpan.FromMinutes(2));
            var output = (await stdoutTask) + (await stderrTask);
            await File.AppendAllTextAsync(
                Path.Combine(LogsRoot, "self-test.log"),
                $"[{DateTimeOffset.Now:O}]\n{output}\n",
                System.Text.Encoding.UTF8);
            if (process.ExitCode != 0)
            {
                throw new InvalidOperationException($"自检失败，exit code {process.ExitCode}。请查看 self-test.log。");
            }
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or System.ComponentModel.Win32Exception or TimeoutException)
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

    internal void OpenLogs()
    {
        Directory.CreateDirectory(LogsRoot);
        OpenPath(LogsRoot);
    }

    internal void OpenBridge()
    {
        var config = ReadConfig();
        if (config.Config is null || !Directory.Exists(config.Config.BridgeRoot))
        {
            throw new InvalidOperationException(config.Error ?? "Bridge 目录不存在。");
        }
        OpenPath(config.Config.BridgeRoot);
    }

    internal Dictionary<string, object?> GetPairingInfo()
    {
        var config = ReadConfig().Config;
        var bridge = config?.BridgeRoot ?? string.Empty;
        var parent = string.IsNullOrEmpty(bridge) ? null : Directory.GetParent(bridge)?.FullName;
        var compatible = string.Equals(Path.GetFileName(bridge.TrimEnd(Path.DirectorySeparatorChar)), "prompt-hub", StringComparison.OrdinalIgnoreCase);
        var addresses = new List<string>();
        var error = string.Empty;
        if (parent is not null && compatible)
        {
            var resume = 0;
            int code;
            do
            {
                code = NetShareEnum(null, 2, out var buffer, -1, out var count, out _, ref resume);
                try
                {
                    if (code is not (0 or 234))
                    {
                        error = $"系统未允许读取共享列表（{code}）。请在文件夹属性中核对共享名称，再在 Mac 手动填写。";
                        break;
                    }
                    for (var index = 0; index < count; index++)
                    {
                        var share = Marshal.PtrToStructure<ShareInfo>(IntPtr.Add(buffer, index * Marshal.SizeOf<ShareInfo>()));
                        if (share.Type == 0 && !share.Name.EndsWith('$') && !string.IsNullOrEmpty(share.Path)
                            && string.Equals(Path.GetFullPath(share.Path).TrimEnd('\\'), parent.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase))
                        {
                            addresses.Add($"smb://{Environment.MachineName}/{Uri.EscapeDataString(share.Name)}");
                        }
                    }
                }
                finally { if (buffer != IntPtr.Zero) NetApiBufferFree(buffer); }
            } while (code == 234);
        }
        return new Dictionary<string, object?>
        {
            ["host"] = Environment.MachineName,
            ["bridgeRoot"] = bridge,
            ["shareFolder"] = parent ?? string.Empty,
            ["compatible"] = compatible,
            ["addresses"] = addresses,
            ["detail"] = !compatible ? "请先在设置中选择以 prompt-hub 命名的任务目录；向导不会移动原有资料。"
                : error.Length > 0 ? error
                : addresses.Count == 0 ? "尚未找到直接共享的上级文件夹。请按下方步骤在系统里开启指定文件夹共享。"
                : "已找到共享；账号读写权限与网络连通性需要在 Mac 登录后验收。",
        };
    }

    internal void OpenShareFolder()
    {
        var config = ReadConfig().Config ?? throw new InvalidOperationException("请先保存 Worker 配置。");
        var parent = Directory.GetParent(config.BridgeRoot)?.FullName;
        if (parent is null || !Directory.Exists(parent)) throw new InvalidOperationException("共享文件夹不存在，请先在设置中选择任务目录。");
        OpenPath(parent);
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct ShareInfo
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string Name;
        public uint Type;
        [MarshalAs(UnmanagedType.LPWStr)] public string Remark;
        public uint Permissions;
        public uint MaxUses;
        public uint CurrentUses;
        [MarshalAs(UnmanagedType.LPWStr)] public string Path;
        [MarshalAs(UnmanagedType.LPWStr)] public string Password;
    }

    [DllImport("Netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern int NetShareEnum(string? server, int level, out IntPtr buffer, int preferredLength, out int entriesRead, out int totalEntries, ref int resume);

    [DllImport("Netapi32.dll")]
    private static extern int NetApiBufferFree(IntPtr buffer);

    internal async Task<string> ExportDiagnosticsAsync()
    {
        var status = await GetStatusAsync();
        var archive = DiagnosticBundle.Create(
            "Soda-Compute-Worker",
            "Soda Compute Worker",
            Convert.ToString(status["version"], CultureInfo.InvariantCulture) ?? BundledVersion,
            File.Exists(Path.Combine(AppRoot, "INSTALL_MODE.json")),
            status,
            LogsRoot,
            [
                Path.Combine(WorkerRoot, "RELEASE.json"),
                Path.Combine(AppRoot, "INSTALL_MODE.json"),
                Path.Combine(AppRoot, "PYTHON_RUNTIME.json"),
            ]);
        DiagnosticBundle.Reveal(archive);
        return archive;
    }

    internal void OpenConfig()
    {
        if (!File.Exists(ConfigPath))
        {
            var example = Path.Combine(WorkerRoot, "worker-config.example.json");
            if (!File.Exists(example))
            {
                throw new FileNotFoundException("找不到 worker-config.example.json。", example);
            }
            Directory.CreateDirectory(StateRoot);
            File.Copy(example, ConfigPath, overwrite: false);
        }
        Process.Start(new ProcessStartInfo("notepad.exe", $"\"{ConfigPath}\"") { UseShellExecute = true });
    }

    private static string BundledVersion => typeof(WorkerHost).Assembly.GetName().Version?.ToString(3) ?? "unknown";

    internal Dictionary<string, object?> GetEditableConfig()
    {
        var root = ReadConfigNode();
        var modelRoots = ModelTypes.ToDictionary(
            item => item.Field,
            item => (object?)ReadRootPaths(root["model_roots"] as JsonArray, "asset_type", item.AssetType),
            StringComparer.Ordinal);
        return new Dictionary<string, object?>
        {
            ["bridgeRoot"] = root["bridge_root"]?.GetValue<string>() ?? string.Empty,
            ["comfyUiUrl"] = root["comfyui_url"]?.GetValue<string>() ?? "http://127.0.0.1:8188",
            ["loraRoots"] = ReadRootPaths(root["lora_roots"] as JsonArray),
            ["modelRoots"] = modelRoots,
        };
    }

    internal void SaveConfig(JsonElement config)
    {
        var currentConfig = ReadConfig().Config;
        if (IsOwnedProcessRunning()
            || (currentConfig is not null && IsExternalWorkerRunning(currentConfig.WorkerId)))
        {
            throw new InvalidOperationException("Worker 运行时不能修改配置。请先停止 Worker。");
        }

        var bridgeRoot = RequiredString(config, "bridgeRoot");
        var comfyUiUrl = RequiredString(config, "comfyUiUrl").TrimEnd('/');
        ValidateAbsolutePath(bridgeRoot, "Bridge");
        if (!Uri.TryCreate(comfyUiUrl, UriKind.Absolute, out var comfyUri)
            || comfyUri.Scheme != Uri.UriSchemeHttp
            || comfyUri.Host is not ("127.0.0.1" or "localhost" or "::1"))
        {
            throw new InvalidOperationException("ComfyUI 地址必须是本机 HTTP 地址。");
        }

        var loraRoots = ReadStringArray(config, "loraRoots");
        loraRoots.ForEach(path => ValidateAbsolutePath(path, "LoRA"));
        if (!config.TryGetProperty("modelRoots", out var modelValue)
            || modelValue.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidOperationException("模型目录配置无效。");
        }
        var modelPaths = ModelTypes.ToDictionary(
            item => item.AssetType,
            item => ReadStringArray(modelValue, item.Field),
            StringComparer.Ordinal);
        foreach (var paths in modelPaths.Values)
        {
            paths.ForEach(path => ValidateAbsolutePath(path, "模型"));
        }

        var root = ReadConfigNode();
        root["bridge_root"] = bridgeRoot;
        root["comfyui_url"] = comfyUiUrl;
        root["lora_roots"] = BuildLoraRoots(root["lora_roots"] as JsonArray, loraRoots);
        root["model_roots"] = BuildModelRoots(root["model_roots"] as JsonArray, modelPaths);

        Directory.CreateDirectory(StateRoot);
        var configPath = ConfigPath;
        var backupPath = Path.Combine(StateRoot, "worker-config.backup.json");
        var temporaryPath = Path.Combine(StateRoot, $".worker-config.{Guid.NewGuid():N}.tmp");
        var payload = root.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine;
        try
        {
            File.WriteAllText(temporaryPath, payload, System.Text.Encoding.UTF8);
            if (File.Exists(configPath))
            {
                File.Copy(configPath, backupPath, overwrite: true);
            }
            File.Move(temporaryPath, configPath, overwrite: true);
            lastError = null;
        }
        finally
        {
            File.Delete(temporaryPath);
        }
        StatusChanged?.Invoke(this, EventArgs.Empty);
    }

    internal bool HasActiveTask()
    {
        var config = ReadConfig().Config;
        return config is not null && FindCurrentTask(config.BridgeRoot) is not null;
    }

    internal bool IsOwnedProcessRunning()
    {
        lock (processGate)
        {
            return ownedProcess is { HasExited: false };
        }
    }

    public void Dispose()
    {
        httpClient.Dispose();
        lock (processGate)
        {
            ownedProcess?.Dispose();
            ownedProcess = null;
        }
    }

    private ProcessStartInfo CreateWorkerStartInfo(PythonCommand python, params string[] extraArguments)
    {
        var info = new ProcessStartInfo
        {
            FileName = python.FileName,
            WorkingDirectory = WorkerRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
        };
        foreach (var argument in python.PrefixArguments)
        {
            info.ArgumentList.Add(argument);
        }
        info.ArgumentList.Add(Path.Combine(WorkerRoot, "prompt_hub_worker.py"));
        info.ArgumentList.Add("--config");
        info.ArgumentList.Add(ConfigPath);
        foreach (var argument in extraArguments)
        {
            info.ArgumentList.Add(argument);
        }
        info.Environment["PYTHONUTF8"] = "1";
        info.Environment["PYTHONUNBUFFERED"] = "1";
        info.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        return info;
    }

    private async Task<PythonCommand> FindPythonAsync()
    {
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
            try
            {
                using var process = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = candidate.FileName,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                    },
                };
                foreach (var argument in candidate.PrefixArguments)
                {
                    process.StartInfo.ArgumentList.Add(argument);
                }
                process.StartInfo.ArgumentList.Add("--version");
                process.Start();
                await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(5));
                if (process.ExitCode == 0)
                {
                    return candidate;
                }
            }
            catch (Exception error) when (error is System.ComponentModel.Win32Exception or TimeoutException or InvalidOperationException)
            {
                continue;
            }
        }
        throw new InvalidOperationException("找不到 Python 3.12。请安装 Python，或设置 SODA_PROMPT_HUB_PYTHON。 ");
    }

    private async Task<bool> IsComfyUiReachableAsync(string url)
    {
        try
        {
            using var response = await httpClient.GetAsync($"{url.TrimEnd('/')}/system_stats");
            return response.IsSuccessStatusCode;
        }
        catch (Exception error) when (error is HttpRequestException or TaskCanceledException or UriFormatException)
        {
            return false;
        }
    }

    private bool IsExternalWorkerRunning(string workerId)
    {
        if (string.IsNullOrWhiteSpace(workerId))
        {
            return false;
        }
        var safeWorkerId = string.Concat(workerId.Where(character => char.IsAsciiLetterOrDigit(character) || "._-".Contains(character)));
        var lockPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "PromptHub",
            $"{safeWorkerId}.lock");
        if (!File.Exists(lockPath))
        {
            return false;
        }
        try
        {
            using var stream = new FileStream(lockPath, FileMode.Open, FileAccess.ReadWrite, FileShare.ReadWrite);
            stream.Lock(0, 1);
            stream.Unlock(0, 1);
            return false;
        }
        catch (IOException)
        {
            return true;
        }
    }

    private static TaskInfo? FindCurrentTask(string bridgeRoot)
    {
        var processing = Path.Combine(bridgeRoot, "processing");
        if (!Directory.Exists(processing))
        {
            return null;
        }
        var taskPath = Directory.EnumerateFiles(processing, "*.json")
            .FirstOrDefault(path => !path.EndsWith(".state.json", StringComparison.OrdinalIgnoreCase));
        if (taskPath is null)
        {
            return null;
        }
        var task = ReadObject(taskPath);
        var type = GetString(task, "task_type", "verified task");
        var id = GetString(task, "task_id", Path.GetFileNameWithoutExtension(taskPath));
        return new TaskInfo("WORKING", $"正在执行 {type}", $"{id} · 已进入 processing");
    }

    private ConfigResult ReadConfig()
    {
        if (!File.Exists(ConfigPath))
        {
            return new ConfigResult(null, "worker-config.json 不存在；打开配置会从示例创建，不会覆盖旧文件。");
        }
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(ConfigPath));
            var root = document.RootElement;
            var bridgeRoot = root.GetProperty("bridge_root").GetString()?.Trim() ?? string.Empty;
            var comfyUiUrl = root.GetProperty("comfyui_url").GetString()?.Trim().TrimEnd('/') ?? string.Empty;
            var workerId = root.GetProperty("worker_id").GetString()?.Trim() ?? string.Empty;
            if (!Path.IsPathFullyQualified(bridgeRoot) || string.IsNullOrWhiteSpace(workerId))
            {
                return new ConfigResult(null, "bridge_root 必须是绝对路径，worker_id 不能为空。");
            }
            if (!Uri.TryCreate(comfyUiUrl, UriKind.Absolute, out var comfyUri)
                || comfyUri.Scheme != Uri.UriSchemeHttp
                || comfyUri.Host is not ("127.0.0.1" or "localhost" or "::1"))
            {
                return new ConfigResult(null, "comfyui_url 必须是本机 HTTP 地址。");
            }
            return new ConfigResult(new WorkerConfig(bridgeRoot, comfyUiUrl, workerId), null);
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException)
        {
            return new ConfigResult(null, $"无法读取 worker-config.json：{error.Message}");
        }
    }

    private JsonObject ReadConfigNode()
    {
        var examplePath = Path.Combine(WorkerRoot, "worker-config.example.json");
        var sourcePath = File.Exists(ConfigPath) ? ConfigPath : examplePath;
        try
        {
            var node = JsonNode.Parse(File.ReadAllText(sourcePath));
            return node as JsonObject
                ?? throw new InvalidOperationException("Worker 配置必须是 JSON 对象。");
        }
        catch (Exception error) when (error is IOException or JsonException)
        {
            throw new InvalidOperationException($"无法读取 Worker 配置：{error.Message}", error);
        }
    }

    private static List<string> ReadRootPaths(
        JsonArray? roots,
        string? discriminator = null,
        string? expected = null)
    {
        if (roots is null)
        {
            return [];
        }
        return roots
            .OfType<JsonObject>()
            .Where(root => discriminator is null
                || string.Equals(root[discriminator]?.GetValue<string>(), expected, StringComparison.Ordinal))
            .Select(root => root["path"]?.GetValue<string>()?.Trim() ?? string.Empty)
            .Where(path => !string.IsNullOrWhiteSpace(path))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static JsonArray BuildLoraRoots(JsonArray? existing, IReadOnlyList<string> paths)
    {
        var current = existing?.OfType<JsonObject>().ToList() ?? [];
        var result = new JsonArray();
        for (var index = 0; index < paths.Count; index += 1)
        {
            var item = index < current.Count
                ? (JsonObject)current[index].DeepClone()
                : new JsonObject();
            item["root_id"] ??= index == 0 ? "comfyui-main" : $"comfyui-{index + 1}";
            item["path"] = paths[index];
            result.Add(item);
        }
        return result;
    }

    private static JsonArray BuildModelRoots(
        JsonArray? existing,
        IReadOnlyDictionary<string, List<string>> pathsByType)
    {
        var current = existing?.OfType<JsonObject>().ToList() ?? [];
        var result = new JsonArray();
        foreach (var type in ModelTypes)
        {
            var matching = current
                .Where(item => string.Equals(
                    item["asset_type"]?.GetValue<string>(),
                    type.AssetType,
                    StringComparison.Ordinal))
                .ToList();
            var paths = pathsByType[type.AssetType];
            for (var index = 0; index < paths.Count; index += 1)
            {
                var item = index < matching.Count
                    ? (JsonObject)matching[index].DeepClone()
                    : new JsonObject();
                item["root_id"] ??= index == 0 ? type.DefaultRootId : $"{type.DefaultRootId}-{index + 1}";
                item["asset_type"] = type.AssetType;
                item["path"] = paths[index];
                result.Add(item);
            }
        }
        return result;
    }

    private static string RequiredString(JsonElement root, string name)
    {
        if (!root.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.String)
        {
            throw new InvalidOperationException($"配置字段 {name} 无效。");
        }
        var result = value.GetString()?.Trim() ?? string.Empty;
        return !string.IsNullOrWhiteSpace(result)
            ? result
            : throw new InvalidOperationException($"配置字段 {name} 不能为空。");
    }

    private static List<string> ReadStringArray(JsonElement root, string name)
    {
        if (!root.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Array)
        {
            throw new InvalidOperationException($"配置字段 {name} 必须是目录列表。");
        }
        return value.EnumerateArray()
            .Where(item => item.ValueKind == JsonValueKind.String)
            .Select(item => item.GetString()?.Trim() ?? string.Empty)
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static void ValidateAbsolutePath(string path, string label)
    {
        if (!Path.IsPathFullyQualified(path))
        {
            throw new InvalidOperationException($"{label} 目录必须是绝对路径：{path}");
        }
    }

    private static GpuInfo ReadGpu(Dictionary<string, JsonElement>? status)
    {
        if (status is null || !status.TryGetValue("system_stats", out var stats) || stats.ValueKind != JsonValueKind.Object)
        {
            return new GpuInfo(string.Empty, "完成自检后显示设备", "ComfyUI");
        }
        var comfyVersion = "ComfyUI";
        if (stats.TryGetProperty("system", out var system)
            && system.TryGetProperty("comfyui_version", out var comfyValue))
        {
            comfyVersion = $"ComfyUI {comfyValue.GetString()}";
        }
        if (!stats.TryGetProperty("devices", out var devices)
            || devices.ValueKind != JsonValueKind.Array
            || devices.GetArrayLength() == 0)
        {
            return new GpuInfo(string.Empty, "CUDA device", comfyVersion);
        }
        var device = devices[0];
        var name = device.TryGetProperty("name", out var nameValue) ? nameValue.GetString() ?? "CUDA device" : "CUDA device";
        var detail = name.Replace("cuda:0 ", string.Empty, StringComparison.OrdinalIgnoreCase);
        if (device.TryGetProperty("vram_free", out var freeValue) && freeValue.TryGetInt64(out var free))
        {
            detail = $"{detail} · {free / 1024d / 1024d / 1024d:F1} GB FREE";
        }
        return new GpuInfo(name, detail, comfyVersion);
    }

    private static Dictionary<string, object?> Status(
        string phase,
        int step,
        string stepTitle,
        string stepDetail,
        string coreState,
        string coreDetail,
        string bridgeState,
        string bridgeDetail,
        string gpuState,
        string gpuDetail,
        string comfyState,
        string comfyDetail,
        string version,
        string releaseDetail,
        string checkedAt,
        bool canPrimary,
        bool canSelfTest,
        string primaryCommand,
        string primaryLabel,
        string errorTitle,
        string errorDetail,
        TaskInfo? task,
        bool statusReady = false)
    {
        return new Dictionary<string, object?>
        {
            ["phase"] = phase,
            ["step"] = step,
            ["stepTitle"] = stepTitle,
            ["stepDetail"] = stepDetail,
            ["coreState"] = coreState,
            ["coreDetail"] = coreDetail,
            ["libraryState"] = bridgeState,
            ["libraryDetail"] = bridgeDetail,
            ["computeState"] = gpuState,
            ["computeDetail"] = gpuDetail,
            ["comfyState"] = comfyState,
            ["comfyDetail"] = comfyDetail,
            ["version"] = version,
            ["releaseChannel"] = releaseDetail,
            ["checkedAt"] = checkedAt,
            ["canPrimary"] = canPrimary,
            ["canRestart"] = canSelfTest,
            ["primaryCommand"] = primaryCommand,
            ["primaryLabel"] = primaryLabel,
            ["errorTitle"] = errorTitle,
            ["errorDetail"] = errorDetail,
            ["taskState"] = task?.State ?? "WAITING",
            ["taskTitle"] = task?.Title ?? "等待下一个已校验任务",
            ["taskDetail"] = task?.Detail ?? (statusReady ? "Worker 已通过最近一次自检。" : "运行自检后写入设备状态。"),
            ["buildLabel"] = "COMPUTE NODE",
        };
    }

    private static Dictionary<string, JsonElement>? ReadObject(string path)
    {
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path));
            if (document.RootElement.ValueKind != JsonValueKind.Object)
            {
                return null;
            }
            return document.RootElement.EnumerateObject()
                .ToDictionary(property => property.Name, property => property.Value.Clone(), StringComparer.Ordinal);
        }
        catch (Exception error) when (error is IOException or JsonException)
        {
            return null;
        }
    }

    private static string GetString(Dictionary<string, JsonElement>? value, string key, string fallback = "")
    {
        if (value is not null && value.TryGetValue(key, out var element) && element.ValueKind == JsonValueKind.String)
        {
            return element.GetString() ?? fallback;
        }
        return fallback;
    }

    private static string ReleaseDetail(string channel, string protocol)
    {
        var shortProtocol = protocol == ExpectedProtocol ? "protocol v2" : protocol;
        return $"{CultureInfo.InvariantCulture.TextInfo.ToTitleCase(channel)} · {shortProtocol}";
    }

    private static void OpenPath(string path)
    {
        Process.Start(new ProcessStartInfo("explorer.exe", $"\"{path}\"") { UseShellExecute = true });
    }

    private int OwnedProcessId()
    {
        lock (processGate)
        {
            return ownedProcess is { HasExited: false } ? ownedProcess.Id : 0;
        }
    }

    private sealed record WorkerConfig(string BridgeRoot, string ComfyUiUrl, string WorkerId);
    private sealed record ConfigResult(WorkerConfig? Config, string? Error);
    private sealed record GpuInfo(string Name, string Detail, string ComfyVersion);
    private sealed record PythonCommand(string FileName, string[] PrefixArguments);
    private sealed record TaskInfo(string State, string Title, string Detail);
}
