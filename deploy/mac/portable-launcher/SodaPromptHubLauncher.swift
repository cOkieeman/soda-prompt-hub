import AppKit
import Foundation
import WebKit
import Darwin

// Shared by adoption and stop: never infer ownership from a listening port alone.
enum CoreProcessGuard {
    static func matches(_ value: String, uid: uid_t, port: Int) -> Bool {
        let tokens = value.split(whereSeparator: { $0.isWhitespace }).map(String.init)
        guard tokens.first == String(uid), tokens.count > 7 else { return false }
        let args = Array(tokens.dropFirst(6)) // uid + five lstart fields
        let module = args.indices.contains { index in
            args[index] == "-m" && index + 2 < args.count
                && args[index + 1] == "prompt_hub" && args[index + 2] == "serve"
        }
        let correctPort = args.indices.contains { index in
            args[index] == "--port" && index + 1 < args.count && args[index + 1] == String(port)
        }
        return module && correctPort
    }

    static func identity(pid: Int32, port: Int) -> String? {
        guard pid > 1, pid != getpid() else { return nil }
        let process = Process(), pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/bin/ps")
        process.arguments = ["-ww", "-p", String(pid), "-o", "uid=,lstart=,command="]
        process.standardOutput = pipe
        process.standardError = FileHandle.nullDevice
        do { try process.run() } catch { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0,
              let value = String(data: data, encoding: .utf8),
              matches(value, uid: getuid(), port: port) else { return nil }
        return value
    }

    static func terminate(pid: Int32, port: Int, expected: String) -> Bool {
        guard identity(pid: pid, port: port) == expected else { return false }
        return kill(pid, SIGTERM) == 0
    }
}

private let launcherName = "Soda Prompt Hub"
private let serviceIdentity = "soda-prompt-hub"
private let hostBridgeName = "sodaHost"

private struct HealthSnapshot {
    let version: String
    let releaseChannel: String
    let database: String
    let processID: Int32?
}

final class LauncherDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate,
    WKNavigationDelegate, WKScriptMessageHandler
{
    private let environment = ProcessInfo.processInfo.environment
    private let fileManager = FileManager.default
    private let clockFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter
    }()
    private var serviceProcess: Process?
    private var adoptedCore: (pid: Int32, identity: String)?
    private var stopInProgress = false
    private var serviceLogHandle: FileHandle?
    private var startupTimer: Timer?
    private var connectionTimer: Timer?
    private var connectionRequestInFlight = false
    private var connectionState = "checking"
    private var connectionLabel = "正在检查设备连接"
    private var connectionDetail = "工作台启动后会自动检查共享目录与 Worker 心跳。"
    private var connectionDevice = "计算设备"
    private var connectionCheckedAt = "--:--:--"
    private var lastConnectionState: String?
    private var connectionNotice = ""
    private var savedReconnectURL: URL?
    private var reconnectAttempted = false
    private var startupStartedAt = Date()
    private var healthCheckInFlight = false
    private var pageOpened = false
    private var intentionalShutdown = false
    private var preserveServiceOnQuit = false
    private var pendingRestart = false
    private var suppressTerminationFailure = false
    private var shellWindow: NSWindow?
    private var webView: WKWebView?
    private var webViewIsReady = false
    private var statusItem: NSStatusItem?
    private var statusMenuItem: NSMenuItem?
    private var stopAndQuitMenuItem: NSMenuItem?
    private var phase = "checking"
    private var step = 1
    private var stepTitle = "正在定位安装目录"
    private var stepDetail = "启动器正在确认本机环境，请稍候。"
    private var coreState = "CHECKING"
    private var coreDetail = "正在确认服务身份"
    private var libraryState = "LOCAL"
    private var libraryDetail = "Documents / Soda Prompt Hub"
    private var computeState = "OPTIONAL"
    private var computeDetail = "可以稍后连接 Windows"
    private var reportedVersion = ""
    private var reportedReleaseChannel = "stable"
    private var errorTitle = ""
    private var errorDetail = ""

    private lazy var host = environment["PROMPT_HUB_HOST"] ?? "127.0.0.1"
    private lazy var port: Int = {
        guard
            let rawPort = environment["PROMPT_HUB_PORT"],
            let parsedPort = Int(rawPort),
            (1 ... 65_535).contains(parsedPort)
        else {
            return 8765
        }
        return parsedPort
    }()
    private lazy var startupTimeout: TimeInterval = {
        guard
            let rawTimeout = environment["PROMPT_HUB_LAUNCHER_TIMEOUT"],
            let parsedTimeout = TimeInterval(rawTimeout),
            parsedTimeout > 0
        else {
            return 120
        }
        return parsedTimeout
    }()
    private lazy var pageURL = URL(string: "http://\(host):\(port)/")!
    private lazy var healthURL = pageURL.appendingPathComponent("api/health")
    private lazy var stateRoot = configuredDirectory(
        key: "PROMPT_HUB_LAUNCHER_STATE_ROOT",
        fallback: fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Soda Prompt Hub")
    )
    private lazy var logRoot = configuredDirectory(
        key: "PROMPT_HUB_LAUNCHER_LOG_ROOT",
        fallback: fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/Soda Prompt Hub")
    )
    private lazy var dataRoot = configuredDirectory(
        key: "PROMPT_HUB_LIBRARY_ROOT",
        fallback: fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent("Documents/Soda Prompt Hub/prompt-library")
    )
    private lazy var launcherLog = logRoot.appendingPathComponent("launcher.log")
    private lazy var serverLog = logRoot.appendingPathComponent("server.log")
    private lazy var pidFile = stateRoot.appendingPathComponent("prompt-hub.pid")

    func applicationDidFinishLaunching(_: Notification) {
        NSApp.setActivationPolicy(.regular)
        configureStatusItem()
        guard configureShellWindow() else { return }
        showShellWindow()

        do {
            try fileManager.createDirectory(at: stateRoot, withIntermediateDirectories: true)
            try fileManager.createDirectory(at: logRoot, withIntermediateDirectories: true)
        } catch {
            presentFailure("无法建立启动器目录", detail: error.localizedDescription)
            return
        }

        log("收到启动请求")
        requestDocumentsAccess()
    }

    func applicationShouldHandleReopen(_: NSApplication, hasVisibleWindows _: Bool) -> Bool {
        showShellWindow()
        if phase == "ready" {
            openPage()
        }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_: NSApplication) -> Bool {
        false
    }

    func applicationWillTerminate(_: Notification) {
        intentionalShutdown = true
        startupTimer?.invalidate()
        connectionTimer?.invalidate()
        if !preserveServiceOnQuit, let process = serviceProcess, process.isRunning {
            process.terminate()
        }
        try? serviceLogHandle?.close()
        webView?.configuration.userContentController.removeScriptMessageHandler(
            forName: hostBridgeName
        )
    }

    func windowShouldClose(_: NSWindow) -> Bool {
        shellWindow?.orderOut(nil)
        return false
    }

    func webView(_ webView: WKWebView, didFinish _: WKNavigation!) {
        webViewIsReady = true
        log("Desktop UI 已加载：\(webView.url?.absoluteString ?? "unknown")")
        webView.evaluateJavaScript(
            "JSON.stringify({readyState: document.readyState, title: document.title, bodyLength: document.body?.innerText.length || 0})"
        ) { [weak self] result, error in
            if let error {
                self?.log("ERROR: Desktop UI 自检失败 — \(error.localizedDescription)")
            } else {
                self?.log("Desktop UI 自检：\(String(describing: result))")
            }
        }
        pushStatus()
    }

    func webView(_: WKWebView, didFail _: WKNavigation!, withError error: Error) {
        log("ERROR: Desktop UI 导航失败 — \(error.localizedDescription)")
    }

    func webView(_: WKWebView, didFailProvisionalNavigation _: WKNavigation!, withError error: Error) {
        log("ERROR: Desktop UI 加载失败 — \(error.localizedDescription)")
    }

    func webView(
        _: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        if url.isFileURL {
            decisionHandler(.allow)
            return
        }
        if navigationAction.navigationType == .linkActivated {
            NSWorkspace.shared.open(url)
        }
        decisionHandler(.cancel)
    }

    func userContentController(_: WKUserContentController, didReceive message: WKScriptMessage) {
        guard
            message.name == hostBridgeName,
            let payload = message.body as? [String: Any],
            let identifier = payload["id"] as? String,
            let method = payload["method"] as? String
        else {
            return
        }

        switch method {
        case "getStatus":
            resolveBridge(identifier)
        case "openWorkspace":
            guard phase == "ready" else {
                rejectBridge(identifier, message: "Core 尚未准备好")
                return
            }
            openPage()
            resolveBridge(identifier)
        case "restartCore":
            guard restartOwnedCore() else {
                rejectBridge(identifier, message: "当前 Core 不由这个启动器托管，无法安全重启")
                return
            }
            resolveBridge(identifier)
        case "retryCore":
            beginStartup()
            resolveBridge(identifier)
        case "openLogs":
            NSWorkspace.shared.open(logRoot)
            resolveBridge(identifier)
        case "openDataFolder":
            openDataFolder()
            resolveBridge(identifier)
        case "checkConnection":
            refreshConnection()
            resolveBridge(identifier)
        case "reconnectDevice":
            reconnectDevice()
            resolveBridge(identifier)
        case "openDeviceSettings":
            if phase == "ready", let url = URL(string: "?view=remote", relativeTo: pageURL) {
                NSWorkspace.shared.open(url.absoluteURL)
            }
            resolveBridge(identifier)
        case "hideWindow":
            shellWindow?.orderOut(nil)
            resolveBridge(identifier)
        case "stopServiceAndQuit":
            resolveBridge(identifier)
            stopServiceAndQuit()
        default:
            rejectBridge(identifier, message: "不支持的启动器操作")
        }
    }

    private func configureShellWindow() -> Bool {
        guard
            let indexURL = Bundle.main.url(
                forResource: "index",
                withExtension: "html",
                subdirectory: "desktop-ui"
            )
        else {
            showFallbackAlert(
                "启动器资源缺失",
                detail: "请重新运行安装器，恢复 Desktop UI 文件。"
            )
            return false
        }

        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(self, name: hostBridgeName)
        let contentView = WKWebView(
            frame: NSRect(x: 0, y: 0, width: 820, height: 620),
            configuration: configuration
        )
        contentView.navigationDelegate = self
        contentView.autoresizingMask = [.width, .height]

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 820, height: 620),
            styleMask: [.titled, .closable, .miniaturizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = launcherName
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.backgroundColor = NSColor(
            calibratedRed: 236 / 255,
            green: 232 / 255,
            blue: 220 / 255,
            alpha: 1
        )
        window.isReleasedWhenClosed = false
        window.isMovableByWindowBackground = true
        window.minSize = NSSize(width: 820, height: 620)
        window.maxSize = NSSize(width: 1024, height: 800)
        window.collectionBehavior = [.fullScreenNone]
        window.delegate = self
        window.contentView = contentView
        window.standardWindowButton(.zoomButton)?.isHidden = true
        window.center()

        shellWindow = window
        webView = contentView
        log("加载 Desktop UI 资源：\(indexURL.path)")
        contentView.loadFileURL(
            indexURL,
            allowingReadAccessTo: indexURL.deletingLastPathComponent()
        )
        return true
    }

    private func configureStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let resources = Bundle.main.resourceURL,
            let icon = NSImage(contentsOf: resources.appendingPathComponent("desktop-ui/app-icon.png"))
        {
            icon.size = NSSize(width: 18, height: 18)
            item.button?.image = icon
        } else {
            item.button?.title = "S"
        }
        item.button?.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .bold)
        item.button?.toolTip = launcherName

        let menu = NSMenu()
        let stateItem = NSMenuItem(title: "状态：正在检查", action: nil, keyEquivalent: "")
        stateItem.isEnabled = false
        menu.addItem(stateItem)
        menu.addItem(.separator())
        menu.addItem(menuItem("打开启动台", action: #selector(showShellFromMenu)))
        menu.addItem(menuItem("打开工作台", action: #selector(openWorkspaceFromMenu)))
        menu.addItem(menuItem("查看日志", action: #selector(openLogsFromMenu)))
        menu.addItem(menuItem("数据目录", action: #selector(openDataFromMenu)))
        menu.addItem(menuItem("检查设备连接", action: #selector(checkConnectionFromMenu)))
        menu.addItem(.separator())
        let stopItem = menuItem("退出并停止服务", action: #selector(stopServiceAndQuit))
        stopItem.isEnabled = false
        menu.addItem(stopItem)
        menu.addItem(menuItem("退出启动器", action: #selector(quitLauncher)))

        item.menu = menu
        statusItem = item
        statusMenuItem = stateItem
        stopAndQuitMenuItem = stopItem
    }

    private func menuItem(_ title: String, action: Selector) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
        item.target = self
        return item
    }

    @objc private func showShellFromMenu() {
        showShellWindow()
    }

    @objc private func openWorkspaceFromMenu() {
        if phase == "ready" {
            openPage()
        } else {
            showShellWindow()
        }
    }

    @objc private func openLogsFromMenu() {
        NSWorkspace.shared.open(logRoot)
    }

    @objc private func openDataFromMenu() {
        openDataFolder()
    }

    @objc private func checkConnectionFromMenu() {
        showShellWindow()
        refreshConnection()
    }

    @objc private func stopServiceAndQuit() {
        guard !stopInProgress else { return }
        guard let core = adoptedCore else {
            showShellWindow()
            presentFailure("无法安全停止服务", detail: "尚未确认 Core 的进程身份。请重新检查或重开启动器；不会按端口强制终止程序。")
            return
        }
        stopInProgress = true
        intentionalShutdown = true
        updateStatus(phase: "stopping", step: 3, title: "正在停止 Core",
                     detail: "等待服务正常退出，数据与 Windows Worker 保持不变。", core: "STOPPING")
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }
            let signaled = CoreProcessGuard.terminate(pid: core.pid, port: self.port, expected: core.identity)
            let deadline = Date().addingTimeInterval(10)
            var stopped = false
            while signaled && Date() < deadline {
                if kill(core.pid, 0) != 0 && errno == ESRCH {
                    stopped = true
                    break
                }
                Thread.sleep(forTimeInterval: 0.1)
            }
            DispatchQueue.main.async {
                self.stopInProgress = false
                if stopped {
                    self.preserveServiceOnQuit = true
                    self.adoptedCore = nil
                    NSApp.terminate(nil)
                } else {
                    self.intentionalShutdown = false
                    self.presentFailure("服务尚未停止", detail: "进程身份变化或正常退出超时。没有强制终止任何进程，请检查服务日志后重试。")
                }
            }
        }
    }

    @objc private func quitLauncher() {
        preserveServiceOnQuit = true
        NSApp.terminate(nil)
    }

    private func showShellWindow() {
        guard let window = shellWindow else { return }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func configuredDirectory(key: String, fallback: URL) -> URL {
        guard let configured = environment[key], !configured.isEmpty else { return fallback }
        return URL(fileURLWithPath: configured, isDirectory: true)
    }

    private func requestDocumentsAccess() {
        let documents = fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent("Documents", isDirectory: true)
        updateStatus(
            phase: "checking",
            step: 2,
            title: "正在检查资料库",
            detail: documents.path,
            core: "CHECKING"
        )
        // Filesystem/TCC access can block. Keep the main run loop available for the permission UI.
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let accessError: Error?
            do {
                _ = try FileManager.default.contentsOfDirectory(
                    at: documents, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles]
                )
                accessError = nil
            } catch {
                accessError = error
            }
            DispatchQueue.main.async {
                guard let self else { return }
                if let accessError {
                    self.presentFailure("需要访问 Documents",
                        detail: "请允许访问本地资料后重试。\n\(accessError.localizedDescription)")
                } else {
                    NSApp.setActivationPolicy(.accessory)
                    self.beginStartup()
                }
            }
        }
    }

    private func beginStartup() {
        startupTimer?.invalidate()
        errorTitle = ""
        errorDetail = ""
        intentionalShutdown = false
        pageOpened = false
        updateStatus(
            phase: "checking",
            step: 3,
            title: "正在确认服务身份",
            detail: healthURL.absoluteString,
            core: "CHECKING"
        )
        checkHealth { [weak self] health in
            guard let self else { return }
            if let health {
                self.log("服务已经运行")
                self.becomeReady(health)
                return
            }
            self.startService()
        }
    }

    private func checkHealth(completion: @escaping (HealthSnapshot?) -> Void) {
        guard !healthCheckInFlight else {
            completion(nil)
            return
        }
        healthCheckInFlight = true
        var request = URLRequest(url: healthURL)
        request.timeoutInterval = 2
        URLSession.shared.dataTask(with: request) { [weak self] data, _, _ in
            var health: HealthSnapshot?
            if
                let data,
                let payload = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                payload["service"] as? String == serviceIdentity
            {
                health = HealthSnapshot(
                    version: payload["version"] as? String ?? "",
                    releaseChannel: payload["release_channel"] as? String ?? "stable",
                    database: payload["database"] as? String ?? "",
                    processID: (payload["process_id"] as? NSNumber)?.int32Value
                )
            }
            DispatchQueue.main.async {
                self?.healthCheckInFlight = false
                completion(health)
            }
        }.resume()
    }

    private func startService() {
        updateStatus(
            phase: "starting",
            step: 1,
            title: "正在定位安装目录",
            detail: "检查正式程序与便携目录。",
            core: "STARTING"
        )
        guard let repository = findRepository() else {
            presentFailure(
                "找不到 Soda Prompt Hub",
                detail: "请先运行首次安装器，或把启动器放回完整源码包附近。"
            )
            return
        }
        updateStatus(
            phase: "starting",
            step: 2,
            title: "正在检查运行组件",
            detail: repository.path,
            core: "STARTING"
        )
        guard let launchCommand = command(for: repository) else {
            presentFailure(
                "缺少运行组件",
                detail: "没有找到项目运行环境或 uv。请先运行首次安装器。"
            )
            return
        }

        rotateServerLogIfNeeded()
        do {
            if !fileManager.fileExists(atPath: serverLog.path) {
                fileManager.createFile(atPath: serverLog.path, contents: nil)
            }
            let logHandle = try FileHandle(forWritingTo: serverLog)
            try logHandle.seekToEnd()
            serviceLogHandle = logHandle

            let process = Process()
            process.executableURL = launchCommand.executable
            process.arguments = launchCommand.arguments
            process.currentDirectoryURL = repository
            process.standardOutput = logHandle
            process.standardError = logHandle
            var childEnvironment = environment
            childEnvironment["PATH"] = [
                fileManager.homeDirectoryForCurrentUser.appendingPathComponent(".local/bin").path,
                fileManager.homeDirectoryForCurrentUser.appendingPathComponent(".cargo/bin").path,
                "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin",
            ].joined(separator: ":")
            childEnvironment["PYTHONUNBUFFERED"] = "1"
            if childEnvironment["ORT_DISABLE_TELEMETRY"] == nil {
                childEnvironment["ORT_DISABLE_TELEMETRY"] = "1"
            }
            childEnvironment["PYTHONNOUSERSITE"] = "1"
            childEnvironment["PYTHONDONTWRITEBYTECODE"] = "1"
            let sourcePath = repository.appendingPathComponent("src").path
            childEnvironment["PYTHONPATH"] = [sourcePath, childEnvironment["PYTHONPATH"]]
                .compactMap { $0 }
                .joined(separator: ":")
            process.environment = childEnvironment
            process.qualityOfService = .userInitiated
            process.terminationHandler = { [weak self] finishedProcess in
                DispatchQueue.main.async {
                    self?.serviceDidTerminate(finishedProcess)
                }
            }

            updateStatus(
                phase: "starting",
                step: 3,
                title: "正在启动 Core",
                detail: "后台启动，不会显示 Terminal。",
                core: "STARTING"
            )
            try process.run()
            serviceProcess = process
            try "\(process.processIdentifier)\n".write(
                to: pidFile,
                atomically: true,
                encoding: .utf8
            )
            log("启动程序：\(repository.path)")
            log("后台进程：\(process.processIdentifier)")
            startupStartedAt = Date()
            startupTimer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) {
                [weak self] _ in self?.pollUntilReady()
            }
            updateStatus(
                phase: "starting",
                step: 4,
                title: "正在确认服务身份",
                detail: healthURL.absoluteString,
                core: "STARTING"
            )
            pollUntilReady()
        } catch {
            presentFailure("Soda Prompt Hub 启动失败", detail: error.localizedDescription)
        }
    }

    private func pollUntilReady() {
        if Date().timeIntervalSince(startupStartedAt) > startupTimeout {
            suppressTerminationFailure = true
            serviceProcess?.terminate()
            presentFailure("Soda Prompt Hub 启动超时", detail: "请查看日志：\(serverLog.path)")
            return
        }
        checkHealth { [weak self] health in
            guard let self, let health else { return }
            self.becomeReady(health)
        }
    }

    private func becomeReady(_ health: HealthSnapshot) {
        let savedPID = (try? String(contentsOf: pidFile, encoding: .utf8))
            .flatMap { Int32($0.trimmingCharacters(in: .whitespacesAndNewlines)) }
        let candidate = health.processID ?? serviceProcess?.processIdentifier ?? savedPID
        if let pid = candidate {
            DispatchQueue.global(qos: .utility).async { [weak self] in
                guard let self else { return }
                let identity = CoreProcessGuard.identity(pid: pid, port: self.port)
                DispatchQueue.main.async {
                    if self.phase == "ready", let identity {
                        self.adoptedCore = (pid, identity)
                        self.updateMenuState()
                    }
                }
            }
        }
        startupTimer?.invalidate()
        reportedVersion = health.version
        reportedReleaseChannel = health.releaseChannel
        if !health.database.isEmpty {
            libraryDetail = health.database
        }
        updateStatus(
            phase: "ready",
            step: 5,
            title: "工作台已经准备好",
            detail: pageURL.absoluteString,
            core: "READY"
        )
        log("服务已就绪")
        refreshConnection()
        if connectionTimer == nil {
            connectionTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) {
                [weak self] _ in self?.refreshConnection()
            }
        }
        if !pageOpened {
            pageOpened = true
            openPage()
            // Keep the connection result visible until the user explicitly hides the launcher.
        }
    }

    private func restartOwnedCore() -> Bool {
        guard let process = serviceProcess, process.isRunning else { return false }
        pendingRestart = true
        startupTimer?.invalidate()
        updateStatus(
            phase: "starting",
            step: 3,
            title: "正在重新启动 Core",
            detail: "等待当前进程安全退出。",
            core: "STARTING"
        )
        process.terminate()
        return true
    }

    private func refreshConnection() {
        guard phase == "ready", !connectionRequestInFlight else { return }
        connectionRequestInFlight = true
        var request = URLRequest(url: pageURL.appendingPathComponent("api/desktop/connection"))
        request.timeoutInterval = 4
        request.cachePolicy = .reloadIgnoringLocalCacheData
        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            let httpStatus = (response as? HTTPURLResponse)?.statusCode
            let payload = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async {
                guard let self else { return }
                self.connectionRequestInFlight = false
                guard self.phase == "ready" else { return }
                let previous = self.lastConnectionState
                if httpStatus == 200, let payload,
                    let state = payload["state"] as? String,
                    let label = payload["label"] as? String
                {
                    self.connectionState = state
                    self.connectionLabel = label
                    self.connectionDetail = payload["detail"] as? String ?? ""
                    self.connectionDevice = payload["device"] as? String ?? "计算设备"
                    self.computeState = payload["share_connected"] as? Bool == true ? "已挂载" : "未连接"
                    self.computeDetail = self.connectionDevice
                    if let raw = payload["reconnect_url"] as? String,
                       let url = URL(string: raw), url.scheme == "smb", url.host != nil,
                       url.user == nil, url.password == nil {
                        self.savedReconnectURL = url
                    } else {
                        self.savedReconnectURL = nil
                    }
                    if payload["share_connected"] as? Bool == true {
                        self.reconnectAttempted = false
                    }
                } else {
                    self.connectionState = "unavailable"
                    self.connectionLabel = "连接状态无法确认"
                    self.connectionDetail = httpStatus == 404
                        ? "当前后台服务不支持连接检查，请退出旧服务后重新打开新版启动器。"
                        : "本机连接检查没有响应，正在自动重试；请勿将此前状态视为在线。"
                    self.computeState = "待确认"
                    self.computeDetail = "无法读取最新状态"
                }
                self.connectionCheckedAt = self.clockFormatter.string(from: Date())
                if previous != self.connectionState {
                    self.connectionNotice = ""
                    if previous == "connected" {
                        self.connectionNotice = "设备连接发生变化：\(self.connectionLabel)"
                        self.showShellWindow()
                    } else if previous != nil, self.connectionState == "connected" {
                        self.connectionNotice = "设备已连接，可以发送计算任务。"
                        self.showShellWindow()
                    }
                    self.log("设备连接：\(self.connectionLabel)")
                }
                self.lastConnectionState = self.connectionState
                if self.connectionState == "mount_missing", !self.reconnectAttempted,
                   self.savedReconnectURL != nil {
                    self.reconnectDevice()
                }
                let shortLabels = ["connected": "在线", "not_configured": "本机",
                    "disabled": "未启用", "stale": "断开", "stopped": "已停止",
                    "compute_unavailable": "计算未就绪", "mount_missing": "未连接"]
                self.statusItem?.button?.title = " \(shortLabels[self.connectionState] ?? "待确认")"
                self.statusItem?.button?.toolTip = "\(launcherName) · \(self.connectionLabel)"
                self.updateMenuState()
                self.pushStatus()
            }
        }.resume()
    }

    private func reconnectDevice() {
        guard let url = savedReconnectURL else {
            if let settings = URL(string: "?view=remote", relativeTo: pageURL) {
                NSWorkspace.shared.open(settings)
            }
            return
        }
        reconnectAttempted = true
        connectionNotice = "正在连接已保存的 Windows 主机；如系统要求登录，请完成确认。"
        showShellWindow()
        if !NSWorkspace.shared.open(url) {
            connectionNotice = "系统未能打开连接。请检查主机地址，或在设备设置中重新配对。"
        }
        pushStatus()
    }

    private func serviceDidTerminate(_ process: Process) {
        startupTimer?.invalidate()
        try? serviceLogHandle?.close()
        serviceLogHandle = nil
        serviceProcess = nil
        try? fileManager.removeItem(at: pidFile)

        if pendingRestart {
            pendingRestart = false
            startService()
            return
        }
        if suppressTerminationFailure {
            suppressTerminationFailure = false
            return
        }
        if intentionalShutdown {
            return
        }
        presentFailure(
            "Soda Prompt Hub 已停止",
            detail: "退出码：\(process.terminationStatus)\n日志：\(serverLog.path)"
        )
    }

    private func findRepository() -> URL? {
        var candidates: [URL] = []
        if let explicit = environment["PROMPT_HUB_REPO"], !explicit.isEmpty {
            candidates.append(URL(fileURLWithPath: explicit, isDirectory: true))
        }
        if
            let hintURL = Bundle.main.url(forResource: "repository-path", withExtension: nil),
            let hint = try? String(contentsOf: hintURL, encoding: .utf8)
                .trimmingCharacters(in: .whitespacesAndNewlines),
            !hint.isEmpty
        {
            candidates.append(URL(fileURLWithPath: hint, isDirectory: true))
        }
        if let bundledProduct = Bundle.main.resourceURL?.appendingPathComponent(
            "product",
            isDirectory: true
        ) {
            candidates.append(bundledProduct)
        }
        let appParent = Bundle.main.bundleURL.deletingLastPathComponent()
        candidates.append(appParent)
        candidates.append(appParent.deletingLastPathComponent())
        candidates.append(
            fileManager.homeDirectoryForCurrentUser
                .appendingPathComponent("Applications/Soda Prompt Hub", isDirectory: true)
        )
        return candidates.first { candidate in
            fileManager.fileExists(atPath: candidate.appendingPathComponent("pyproject.toml").path)
                && fileManager.fileExists(
                    atPath: candidate.appendingPathComponent("src/prompt_hub", isDirectory: true).path
                )
        }
    }

    private func command(for repository: URL) -> (executable: URL, arguments: [String])? {
        if
            let bundledPython = Bundle.main.resourceURL?.appendingPathComponent(
                "runtime/python/bin/python3.12"
            ),
            fileManager.isExecutableFile(atPath: bundledPython.path)
        {
            return (
                bundledPython,
                ["-m", "prompt_hub", "serve", "--host", host, "--port", String(port)]
            )
        }
        let python = repository.appendingPathComponent(".venv/bin/python")
        if fileManager.isExecutableFile(atPath: python.path) {
            return (
                python,
                ["-m", "prompt_hub", "serve", "--host", host, "--port", String(port)]
            )
        }
        for path in uvCandidates() where fileManager.isExecutableFile(atPath: path.path) {
            return (
                path,
                [
                    "run", "--project", repository.path, "--no-sync", "prompt-hub", "serve",
                    "--host", host, "--port", String(port),
                ]
            )
        }
        return nil
    }

    private func uvCandidates() -> [URL] {
        if let explicit = environment["PROMPT_HUB_UV_BIN"], !explicit.isEmpty {
            return [URL(fileURLWithPath: explicit)]
        }
        return [
            fileManager.homeDirectoryForCurrentUser.appendingPathComponent(".local/bin/uv"),
            fileManager.homeDirectoryForCurrentUser.appendingPathComponent(".cargo/bin/uv"),
            URL(fileURLWithPath: "/opt/homebrew/bin/uv"),
            URL(fileURLWithPath: "/usr/local/bin/uv"),
        ]
    }

    private func openPage() {
        log("打开页面：\(pageURL.absoluteString)")
        if environment["PROMPT_HUB_LAUNCHER_SKIP_OPEN"] != "1" {
            NSWorkspace.shared.open(pageURL)
        }
    }

    private func openDataFolder() {
        let destination: URL
        if fileManager.fileExists(atPath: dataRoot.path) {
            destination = dataRoot
        } else {
            destination = dataRoot.deletingLastPathComponent()
        }
        NSWorkspace.shared.open(destination)
    }

    private func scheduleAutomaticHide() {
        guard environment["PROMPT_HUB_LAUNCHER_KEEP_VISIBLE"] != "1" else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.4) { [weak self] in
            guard self?.phase == "ready" else { return }
            self?.shellWindow?.orderOut(nil)
        }
    }

    private func updateStatus(
        phase: String,
        step: Int,
        title: String,
        detail: String,
        core: String
    ) {
        self.phase = phase
        self.step = step
        stepTitle = title
        stepDetail = detail
        coreState = core
        coreDetail = core == "READY" ? "\(host):\(port)" : detail
        updateMenuState()
        pushStatus()
    }

    private func presentFailure(_ title: String, detail: String) {
        log("ERROR: \(title) — \(detail)")
        errorTitle = title
        errorDetail = detail
        updateStatus(
            phase: "attention",
            step: max(step, 1),
            title: title,
            detail: detail,
            core: "ERROR"
        )
        showShellWindow()
        if let dialogLog = environment["PROMPT_HUB_LAUNCHER_DIALOG_LOG"] {
            let line = "\(title): \(detail)\n"
            try? line.write(toFile: dialogLog, atomically: true, encoding: .utf8)
        }
    }

    private func shellStatus() -> [String: Any] {
        let bundleVersion = Bundle.main.object(
            forInfoDictionaryKey: "CFBundleShortVersionString"
        ) as? String ?? "unknown"
        let version = reportedVersion.isEmpty ? bundleVersion : reportedVersion
        let channel = reportedReleaseChannel.lowercased() == "stable" ? "Stable" : reportedReleaseChannel
        let ownsRunningService = serviceProcess?.isRunning == true
        return [
            "phase": phase,
            "step": step,
            "stepTitle": stepTitle,
            "stepDetail": stepDetail,
            "coreState": coreState,
            "coreDetail": coreDetail,
            "libraryState": libraryState,
            "libraryDetail": libraryDetail,
            "computeState": computeState,
            "computeDetail": computeDetail,
            "connectionState": connectionState,
            "connectionLabel": connectionLabel,
            "connectionDetail": connectionDetail,
            "connectionDevice": connectionDevice,
            "connectionCheckedAt": connectionCheckedAt,
            "connectionNotice": connectionNotice,
            "version": version,
            "releaseChannel": "\(channel) · Local first",
            "checkedAt": clockFormatter.string(from: Date()),
            "canOpenWorkspace": phase == "ready",
            "canPrimary": phase == "ready" || phase == "attention",
            "canRestart": phase == "ready" && ownsRunningService,
            "canStop": adoptedCore != nil && !stopInProgress,
            "errorTitle": errorTitle,
            "errorDetail": errorDetail,
        ]
    }

    private func pushStatus() {
        guard webViewIsReady, let statusJSON = serializedJSON(shellStatus()) else { return }
        webView?.evaluateJavaScript(
            "window.SodaDesktop && window.SodaDesktop.receiveStatus(\(statusJSON));"
        )
    }

    private func resolveBridge(_ identifier: String) {
        guard
            let identifierJSON = serializedJSON(identifier),
            let resultJSON = serializedJSON(["status": shellStatus()])
        else {
            return
        }
        webView?.evaluateJavaScript(
            "window.SodaDesktop && window.SodaDesktop.resolve(\(identifierJSON), \(resultJSON));"
        )
    }

    private func rejectBridge(_ identifier: String, message: String) {
        guard
            let identifierJSON = serializedJSON(identifier),
            let messageJSON = serializedJSON(message)
        else {
            return
        }
        webView?.evaluateJavaScript(
            "window.SodaDesktop && window.SodaDesktop.reject(\(identifierJSON), \(messageJSON));"
        )
    }

    private func serializedJSON(_ value: Any) -> String? {
        guard
            let data = try? JSONSerialization.data(withJSONObject: value, options: [.fragmentsAllowed])
        else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    private func updateMenuState() {
        let labels = [
            "checking": "状态：正在检查",
            "starting": "状态：正在启动",
            "ready": "状态：可以使用",
            "attention": "状态：需要处理",
        ]
        statusMenuItem?.title = labels[phase] ?? "状态：未知"
        if phase == "ready" {
            statusMenuItem?.title = "设备：\(connectionLabel)"
        }
        stopAndQuitMenuItem?.isEnabled = adoptedCore != nil && !stopInProgress
    }

    private func rotateServerLogIfNeeded() {
        guard
            let attributes = try? fileManager.attributesOfItem(atPath: serverLog.path),
            let size = attributes[.size] as? NSNumber,
            size.intValue > 10 * 1024 * 1024
        else {
            return
        }
        let previous = serverLog.deletingLastPathComponent()
            .appendingPathComponent("server.log.previous")
        try? fileManager.removeItem(at: previous)
        try? fileManager.moveItem(at: serverLog, to: previous)
    }

    private func log(_ message: String) {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        let line = "[\(formatter.string(from: Date()))] \(message)\n"
        if !fileManager.fileExists(atPath: launcherLog.path) {
            fileManager.createFile(atPath: launcherLog.path, contents: nil)
        }
        guard let handle = try? FileHandle(forWritingTo: launcherLog) else { return }
        defer { try? handle.close() }
        _ = try? handle.seekToEnd()
        _ = try? handle.write(contentsOf: Data(line.utf8))
    }

    private func showFallbackAlert(_ title: String, detail: String) {
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.alertStyle = .critical
        alert.messageText = title
        alert.informativeText = detail
        alert.addButton(withTitle: "好")
        alert.runModal()
        NSApp.terminate(nil)
    }
}

@main
enum LauncherMain {
    static func main() {
        let application = NSApplication.shared
        let delegate = LauncherDelegate()
        application.delegate = delegate
        application.run()
    }
}
