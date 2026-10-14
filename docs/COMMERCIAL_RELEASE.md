# 商业分发与安装说明

Soda Prompt Hub 1.2.0 提供 Mac Desktop、Windows Desktop 和独立 Compute Worker 三种组件。
从 [1.2.0 Release](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0) 下载所需的 DMG 或 Setup，核对同页的 `SHA256SUMS.txt`。

安装包标为 **Pre-release**：Mac 与 Windows 的运行、升级资料保留和维护者界面验收已完成；
Windows Setup 的完整覆盖安装 / 卸载 / 重装流程和平台签名仍待验证。实际范围见[1.2.0 发行验证](acceptance/release-1.2.0-20261005.md)。

| 产品 | 适用场景 | 分发文件 |
|---|---|---|
| Mac Desktop | 在 Mac 本机管理资料和创作 | `Soda-Prompt-Hub-1.2.0-macOS-arm64.dmg` |
| Windows Desktop | 在一台 Windows 设备上独立管理和创作 | `Soda-Prompt-Hub-Desktop-1.2.0-Setup.exe` |
| Windows Compute Worker | 双机模式下接收 Mac 任务并调用 Windows 本机 ComfyUI | `Soda-Compute-Worker-1.2.0-Setup.exe` |

Windows 单机版自动准备本地任务目录并管理 Core / Worker，不要求 SMB、不另开独立 Worker。
Mac 管理 Windows 时才安装独立 Worker 并配置共享。Mac 在 Windows 离线时仍可整理本地资料。

## 普通用户安装

### macOS Apple Silicon

1. 打开 DMG，把 `Soda Prompt Hub.app` 拖入 `Applications`。
2. 先核对官方 Release 的 SHA-256，再按系统提供的应用授权流程处理未知开发者提示；被阻止时见[排错](TROUBLESHOOTING.md)，不关闭系统安全保护。
3. App 会使用包内 Python 和依赖启动 Core，不需要预装 Python、`uv` 或 Homebrew。
4. 升级前备份并“退出并停止服务”，再覆盖 `/Applications/Soda Prompt Hub.app`；删除 App 即可卸载程序。

当前 DMG 尚未 Developer ID 签名或 notarize，因此第一次打开会有系统提示。不要从非官方来源下载，
并在安装前核对 Release 页面公布的 SHA-256。

App 使用免费的 ad-hoc 签名保证包内代码与资源结构完整；这不代表 Apple 开发者认证，也不需要定期续费。
每次更新代码、图标或运行时后，构建器会重新签名并执行严格校验。内部 hash 清单记录运行时与资源，
启动器可执行文件和签名封装由 `codesign --verify --deep --strict` 校验，整个 DMG 另有 SHA-256。

### Windows 10/11 x64

1. 双击对应的 Setup `.exe`。
2. 当前安装器未做 Soda Authenticode 签名；若系统阻止，核对来源和 SHA-256 后按系统允许的授权流程处理。不要关闭杀毒软件；没有允许入口时记录提示并停止安装。
3. 安装器使用当前 Windows 用户的目录，不要求管理员权限，并自动确认 WebView2 Runtime。
4. Desktop 和 Worker 已包含 Python 3.12 runtime；最终用户不需要安装 Python、`uv`、`.NET SDK` 或
   Inno Setup。
5. 可从开始菜单或 Windows“已安装的应用”卸载；同版本覆盖安装也支持修复安装。

ComfyUI、模型权重和训练工具不随安装器分发。单机版只需确认本机 ComfyUI 地址；独立 Worker 还需确认
与 Mac 共享一致的 bridge。LoRA 和模型扫描目录属于按需设置，不是打开 WebUI 的前置条件。
升级前停止对应服务，安装后从新快捷方式打开；不要同时运行旧便携 EXE 和新安装版。

## 程序与个人数据

| 内容 | 默认位置 | 卸载时处理 |
|---|---|---|
| Mac App | `/Applications/Soda Prompt Hub.app` | 删除 App |
| Mac 个人资料 | `~/Documents/Soda Prompt Hub` | 保留 |
| Windows Desktop 程序 | `%LOCALAPPDATA%\Programs\Soda Prompt Hub` | 删除 |
| Windows Worker 程序 | `%LOCALAPPDATA%\Programs\Soda Compute Worker` | 删除 |
| Windows 个人资料 | `%USERPROFILE%\Documents\Soda Prompt Hub` | 保留 |
| Windows Worker 配置与日志 | `%LOCALAPPDATA%\Soda Prompt Hub\Compute Worker` | 保留 |
| Windows 单机 Worker 配置 | `%LOCALAPPDATA%\Soda Prompt Hub\Desktop Worker` | 保留 |

单机与独立 Worker 配置分开保存。把下载文件放 D 盘不等于迁移应用、AppData 或个人资料；不要手动拖走已安装程序目录。

程序更新只替换程序目录。数据库、提示词资料、图片、模型、Worker 配置、bridge 任务和日志不会因为覆盖安装或
卸载而删除。若用户确实要清除个人数据，应先备份，再手工删除对应数据目录。

## 诊断与隐私

Windows Desktop 和 Worker 的主界面、托盘菜单都可以导出诊断 ZIP。诊断包只包含版本、有限状态和最多
8 个日志文件的末尾 512 KiB，并脱敏用户主目录、token、password、API key 与 Bearer 值。它不包含：

- `worker-config.json`、数据库或完整 Prompt 库；
- bridge 中的任务与返回图片；
- 模型、LoRA、数据集原图或权重；
- SMB 密码或外部模型 API Key。

提交诊断包前仍应由用户自行检查内容。

## 维护者发布检查

1. 确认 `pyproject.toml`、根 `RELEASE.json` 和 Worker `RELEASE.json` 都是目标版本；当前源码为 `1.2.0 stable`。
2. 在 Windows 构建两个 Setup，并核对 Microsoft WebView2 bootstrapper 的有效签名。
3. 在 Mac 构建自包含 DMG，运行 `hdiutil verify`，并验证 App 内 `MANIFEST.sha256`。
4. 在 Windows 实机执行 `deploy/windows-installer/test-lifecycle.ps1`，验证覆盖安装、包内 Python、卸载保留
   数据和重装。
5. 运行全量测试、Ruff、JavaScript 语法、两个 C# 工程 build 和 `git diff --check`。
6. 生成统一 SHA-256 清单；Release 页面必须同时公布文件大小、hash、未签名状态和系统要求。
7. 发布前扫描绝对个人路径、凭据、真实 `worker-config.json`、`.venv`、`__pycache__` 与 `.pyc`。

Windows Authenticode、Mac Developer ID 与 notarization 延后处理，但不能据此断言“只差签名”。
1.1.1 新安装包原生验收按[pre1 手动清单](acceptance/manual-1.1.1-pre1-20260914.md)执行；源码测试与构建成功不能替代它。
对外商业再分发还需核对第三方组件许可及源码提供义务，尤其随包 Git，见[安装器分发边界](../deploy/windows-installer/README.md#当前刻意保留的限制)。
完成签名后仍需重新执行安装、升级、卸载和 hash 验收。
