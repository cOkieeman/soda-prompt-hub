# Windows 商业安装包（暂不签名）

本目录把已经通过 manifest 校验的 Windows Desktop 与 Worker 便携目录转换为两个标准的
per-user 安装器。当前按产品决策暂不执行 Soda 自有 Authenticode 签名，但仍校验微软提供的
WebView2 bootstrapper 签名。

## 构建要求

普通用户无需执行本节。当前下载按[Mac+Worker](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.1.1-mac-windows-20260914)
与[Windows单机](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.1.1-windows-standalone-20260914)分组，
每套附独立SHA256SUMS和手动验收说明。2026-09-14构建为1.1.1 Pre-release，不代表生命周期手验全通过。

- Windows 10/11 x64 构建机
- PowerShell 5.1 或更高版本
- `.NET 8 SDK`、Python 3.12、`uv`
- Inno Setup 6
- 已发布并解压的 Desktop 与 Worker `win-x64` 目录

```powershell
.\deploy\windows-installer\build.ps1 `
  -DesktopPackageRoot C:\release\Soda-Prompt-Hub-Desktop-<版本>-win-x64 `
  -WorkerPackageRoot C:\release\Soda-Compute-Worker-<版本>-win-x64 `
  -OutputRoot C:\release\commercial
```

如果 `uv.exe` 或 `ISCC.exe` 是 per-user 安装且尚未进入当前 PowerShell 的 PATH，可分别通过
`-UvExecutable` 与 `-InnoCompiler` 传入绝对路径。

也可在Mac的.NET 8 SDK容器交叉编译两个win-x64 self-contained宿主，再传到Windows执行Inno安装器构建；
这是2026-09-13所用流程，不要求在最终用户电脑安装SDK。它不能替代Windows实机安装/运行验收。
跨设备源码暂存使用 `scripts/stage_windows_desktop_source.py`：在生成manifest之前将`.ps1`规范化为UTF-8 BOM，
避免PowerShell 5.1按ANSI解码中文。传输与解压后核对manifest，不在记录哈希之后手改编码。

构建脚本会执行以下操作：

1. 拒绝包含 `.venv`、`worker-config.json`、`__pycache__` 或 `.pyc` 的 payload。
2. 校验并解压官方 Python 3.12.10 embeddable runtime。
3. Desktop 依赖严格从仓库 `uv.lock` 导出并在构建机预装；`python312._pth` 同时固定指向包内
   `core/src`，用户首次启动不联网 pip，也不依赖环境变量里的 `PYTHONPATH`。
4. Worker 仅携带标准库 Python runtime。
   Desktop 另完整携带官方 MinGit 2.55.0.windows.5 x64，固定下载 URL 与 SHA-256，保留其全部
   DLL、HTTPS helper、CA 证书和许可证。`GIT_RUNTIME.json` 记录上游与哈希。构建机可用
   `-GitArchive` 指定离线 ZIP；最终用户不需要装 Git，不会修改系统 PATH 或关闭 TLS 验证。
   Desktop 便携构建同样准备 Git；当前 Desktop 发布仅支持 win-x64，不能混装 x64 Git 到 ARM64 包。
5. 下载 WebView2 bootstrapper，并要求其 Authenticode 签名有效且属于 Microsoft。
6. 生成两个 unsigned Setup `.exe` 及 `COMMERCIAL_RELEASE.json` SHA-256 清单。

## 安装与数据边界

- Desktop：`%LOCALAPPDATA%\Programs\Soda Prompt Hub`
- Worker：`%LOCALAPPDATA%\Programs\Soda Compute Worker`
- Worker 配置与日志：`%LOCALAPPDATA%\Soda Prompt Hub\Compute Worker`
- Prompt Hub 资料：`%USERPROFILE%\Documents\Soda Prompt Hub`

覆盖安装和卸载不会删除资料库、数据库、Worker 配置、任务目录或日志。已有便携版目录中的
`worker-config.json` 仍按旧路径读取，不强制迁移。

构建完成后应在 Windows 实机执行生命周期验收：

```powershell
.\deploy\windows-installer\test-lifecycle.ps1 `
  -InstallerRoot C:\release\commercial\installers `
  -StatusPath C:\release\windows-lifecycle-status.json
```

该脚本会验证覆盖安装、包内 Python、Core health、卸载删除程序目录、个人数据与 Worker 配置保留，
然后重新安装两个产品。它只清理自己创建的测试标记。

## 当前刻意保留的限制

- Soda 自有 Windows Authenticode 签名尚未执行，因此 SmartScreen 可能显示未知发布者。
- Inno Setup 只在构建机使用，不会安装到最终用户电脑。
- ComfyUI 和模型权重不属于安装包。
- MinGit 是独立子进程依赖，不是自有代码；其 GPLv2 及组件许可证仍有效。包中保留原文与上游
  来源，但这不等于完成面向外部商业分发的全部合规审核。正式对外分发前需落实相应源码提供义务，
  包括 Git for Windows 与随包组件的对应源码，不能只附一个上游链接就宣称已经合规。
