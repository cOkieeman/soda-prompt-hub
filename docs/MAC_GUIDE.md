# Mac 使用与维护

本指南适用于 Mac 管理 Windows：项目、审核、Caption 和版本记录保存在 Mac。
Windows 单机的数据则保存在 Windows，见[快速开始](QUICK_START.md)。

## 启动、停止与诊断

从[Mac + Windows Worker Release](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0)
下载 DMG，核对 SHA-256，将应用拖入 Applications。默认应用位置是：

```text
/Applications/Soda Prompt Hub.app
```

这是自包含应用，内置 Python 和依赖，不需要预装 Python，不要求首次运行安装脚本或准备外部 `.venv`。
个人资料默认在 `~/Documents/Soda Prompt Hub/prompt-library`；已有安装可能沿用旧资料目录，
以启动器“打开数据目录”显示的位置为准。日志入口指向 `~/Library/Logs/Soda Prompt Hub`。

- 双击应用：检查 Core、显示启动状态并提供工作台入口。
- 关闭窗口或“收起窗口”：隐藏启动台，Core 继续运行。
- “退出启动器”：退出应用界面，保留 Core。
- “退出并停止服务”：启动台窗口和屏幕顶部菜单栏应用图标中均有入口；不是 Dock 右键菜单。
- 启动失败：窗口显示错误，先看日志，再重试；不要连续开多个实例。

停服前先在 WebUI 等待或取消扫描、打标、草稿等任务。停服按钮仅在已确认目标进程身份时可用：
校验同一用户、Core 命令、端口和启动时间后，才请求正常退出；可以识别并接管已有的匹配 Core。
身份变化或退出超时会报错，不按端口强杀无关程序。“重启 Core”仍限于当前启动器启动的进程。
停止 Mac Core 不会停止 Windows 独立 Worker。

## 连接 Windows

Windows 开启 ComfyUI 和独立 Soda Compute Worker。Mac WebUI“设置 → 设备连接”按配对引导保存主机与共享名称，
在系统窗口完成 SMB 授权；密码由 macOS 钥匙串保存，不填写进 Prompt Hub。

启动器每5秒检查连接。“共享已连接”只证明任务目录可访问；“已连接 · 可以计算”还要求 Worker
持续心跳和 ComfyUI 可用。心跳超过25秒会显示中断，历史自检不能证明当前在线。
连接恢复/断开有状态反馈；未配对或 Windows 离线不影响 Mac 已保存资料的整理。
具体 Worker 配置见[Windows Worker 指南](WINDOWS_WORKER.md)。

## 安全更新顺序

1. 备份个人资料，确认没有正在写入的任务；外部原图单独备份。
2. 下载目标构建的 DMG，核对日期、tag 和 SHA-256。界面同为1.1.0不代表是同一构建。
3. 从当前启动器选择“退出并停止服务”；失败时先处理日志中的原因。
4. 用 DMG 中的新 App 覆盖 Applications 中的旧 App，不拖动个人资料目录。
5. 从 Applications 打开新版，核对项目、配置与结果，再核对[1.2.0 发行验证范围](acceptance/release-1.2.0-20261005.md)。

DMG 覆盖安装不会自动执行旧源码更新器的备份/失败回滚流程，应事先主动备份。
完成备份与停服后，覆盖旧 `.app` 即可升级；删除 `.app` 只卸载程序，不主动删除个人资料。
当前包尚未 Developer ID 签名，也没有Apple公证。
2026-09-13包是未正式平台签名、待手动验收的Pre-release；不要因软件显示stable就跳过验收。
安全提示或“已损坏”见[排错](TROUBLESHOOTING.md)，不要关闭 Gatekeeper。

## 备份与恢复

普通用户优先使用 WebUI 的个人数据备份入口。维护人员也可在配置相同资料目录的源码环境运行：

```bash
uv run --no-sync prompt-hub backup
uv run --no-sync prompt-hub verify-backup /绝对路径/备份目录
uv run --no-sync prompt-hub restore /绝对路径/备份目录 \
  --destination "$HOME/Documents/Soda Prompt Hub/restore-tests/prompt-hub-YYYYMMDD"
```

恢复目标必须不存在或为空；核对后再决定是否切换正式资料位置。不要覆盖正在使用的资料库。
外部数据集原图、公共资料来源和大模型不等于已经包含在个人数据备份中，应按需要另行保存。

## 维护附录：旧源码安装与轻量启动器

以下仅适用于维护人员和已有源码安装，不是 DMG 用户的必做步骤。

- 旧源码默认安装目录为 `$HOME/Applications/Soda Prompt Hub`，不要与 `/Applications/Soda Prompt Hub.app` 混淆。
- `deploy/mac` 的启动、停止、诊断和更新 `.command` 用于该源码安装。
- 更新源码安装时，完整解压新源码包，在新包的 `deploy/mac` 运行 `更新-Soda-Prompt-Hub.command`。
  更新器先停服、备份资料与旧程序，再准备依赖和初始化；失败时尝试恢复旧程序。
- 该更新器的旧程序快照默认在 `~/Library/Application Support/Soda Prompt Hub/program-backups`；
  不要把这项保障推及普通 DMG 覆盖安装。

轻量启动器构建：

```bash
uv run --no-sync python scripts/build_mac_portable_launcher.py \
  --runtime-root-hint "$HOME/Applications/Soda Prompt Hub"
```

它依赖外部源码运行环境。面向普通用户的自包含构建改用：

```bash
.venv/bin/python scripts/build_mac_commercial_release.py
```

构建后验证 App 的 manifest、ad-hoc 签名和 DMG 哈希；ad-hoc 不等于 Developer ID 签名或公证。
签名后必须重新验收，不复用原哈希。

## 自定义位置与监听

- `PROMPT_HUB_LIBRARY_ROOT`：个人资料目录。
- `PROMPT_HUB_MODELS_ROOT`：本地模型目录。
- `PROMPT_HUB_INSTALL_ROOT`：旧源码安装/更新目录，不是 DMG App 的移动开关。
- `PROMPT_HUB_PORT`：页面端口，默认8765。

普通用户无需设置这些变量。维护启动、备份、恢复时必须确认使用同一资料位置。
默认 `127.0.0.1` 仅供本机访问；局域网监听属于高级配置，不是 Mac→Windows 配对的必要步骤。
