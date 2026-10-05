# 快速开始

先选一种使用方式；1.2.0 安装包标为 Pre-release，运行与界面已验收，完整安装生命周期与平台签名仍待完成。

- [Windows 单机版](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0)：只装 Desktop Setup，不另开独立 Worker。
- [Mac + Windows Worker](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0)：Mac 装 DMG，Windows 装 Worker Setup。

下载 Assets 中的安装器并核对 `SHA256SUMS`。遇到安全阻止或“已损坏”提示，先查看
[安装说明](COMMERCIAL_RELEASE.md)与[排错](TROUBLESHOOTING.md)，不要关闭系统安全保护。

## 安装前准备

- Windows 10/11 x64；双机模式另需 macOS Apple Silicon 设备；
- 可访问 GitHub 和公开提示词仓库的网络；
- 至少预留数 GB 空间。带图片的视觉资料库会占用更多空间；
- ComfyUI 需自行安装并启动；模型和 API Key 不包含在应用中；
- 升级前备份个人数据并正常退出旧服务。普通用户不使用 Source code ZIP 安装。

## Windows 单机：第一次安装

1. 运行 `Soda-Prompt-Hub-Desktop-1.2.0-Setup.exe`，安装到所选用户程序目录。
2. 启动自己的 ComfyUI，确认其本机网页可打开。
3. 从开始菜单打开 `Soda Prompt Hub`。启动器自动准备本地任务目录并管理 Core / Worker；无需共享授权。
4. 在启动器设置填写 ComfyUI 地址（默认 `http://127.0.0.1:8188`），就绪后打开工作台。
5. 在“设置 → 设备连接”确认本机 Worker 和 ComfyUI 状态；模型 URL / Key 在“模型服务”中配置。

自包含安装包内置 Python、依赖与私有 Git，不需要用户安装 Python、Git、`uv` 或 SDK。
安装包放在 D 盘不会自动迁移已安装应用和个人资料。具体位置见[程序与个人数据](COMMERCIAL_RELEASE.md#程序与个人数据)。

## Mac 管理 Windows：第一次安装

1. 打开 `Soda-Prompt-Hub-1.2.0-macOS-arm64.dmg`。
2. 把 `Soda Prompt Hub.app` 拖入 Applications。
3. 按上面的校验与系统安全提示说明确认来源；当前包没有 Developer ID 签名或 Apple 公证。
4. App 会使用包内 Python 3.12 和固定依赖启动 Core，不需要安装 Homebrew、Python 或 `uv`。
5. 启动台显示就绪后打开工作台；本机地址仍是 <http://127.0.0.1:8765/>。
6. Windows 安装并打开同套 Release 的 `Soda Compute Worker`，保持 ComfyUI 开启，按[Worker 指南](WINDOWS_WORKER.md)设置共享任务目录。
7. Mac WebUI“设置 → 设备连接”按引导填写主机和共享名，在系统窗口完成首次共享登录，再检查实时 Worker 心跳与 ComfyUI 状态。

安装后的程序位置：

```text
/Applications/Soda Prompt Hub.app
```

新用户的个人资料位置：

```text
$HOME/Documents/Soda Prompt Hub/prompt-library
```

如果电脑已经有旧版 `$HOME/Documents/Codex/soda-person/prompt-library`，程序会继续沿用旧目录，
不会复制出第二套资料。

## 第一次打开

首页出现“把推荐提示词资料装到本机”时：

1. 先查看来源名和许可证提示；
2. 点“安装推荐资料库”；
3. 等待下载和本地索引完成；
4. 某个来源失败时可稍后在“设置 → 资料管理”中单独重试。

Kisegaeningyou 包含较多视觉图片，第一次下载可能比纯文字仓库慢。AnimaDex 首次安装只使用仓库
自带的角色、画师和作品缩略图样例；完整公共目录需要在 `animadex.net` 的 Account 页面生成
“Offline dataset export” token，并按 AnimaDex 自己的导入说明下载到独立 `animadex-data` 目录。
Prompt Hub 不保存 token，也不会把下载数据放进 GitHub 仓库。点“暂时跳过”只隐藏当前提醒，
不会关闭资料管理功能。

## 每天使用

- 启动：Mac 从 Applications 打开应用；Windows 单机从开始菜单打开 Soda Prompt Hub。
- 关闭启动台：关闭窗口；Core 会继续在后台运行。
- 完全退出：Mac 启动台或菜单栏应用图标中选择“退出并停止服务”；Windows 单机托盘选择“退出并停止本机服务”。只选“退出启动器”会保留服务。
- 页面打不开：从启动台或菜单栏打开日志；维护人员仍可使用源码包中的诊断脚本。

只用 Mac 时，现在就可以查资料、写 Prompt、导入 OC、整理和打标数据集。需要 Windows 出图时，
继续阅读[Windows Worker 指南](WINDOWS_WORKER.md)。

## 怎样确认安装正确

- 首页右侧能看到当前程序版本和数据结构版本；
- “提示词库”能打开，不出现空白错误页；
- “数据集”可以选择一个本地图片目录并进行只读扫描；
- 单机“设备连接”不要求配对另一台设备；双机未配对时显示配置引导，配对后要检查实时状态，不能只看上次自检。

本次验证范围见[1.2.0 发行验证](acceptance/release-1.2.0-20261005.md)。完整安装生命周期可按[两模式手动验收清单](acceptance/manual-1.1.1-pre1-20260914.md)继续验证。

若不符合，按[常见问题与排错](TROUBLESHOOTING.md)处理。
