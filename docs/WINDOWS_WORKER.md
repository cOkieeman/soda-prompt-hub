# Windows Worker 完整指南

Windows Worker 是 Mac Prompt Hub 与 Windows 本机 ComfyUI 之间的任务执行器。它不需要 Windows
登录密码或 API Key，也不要求把 ComfyUI 的 `8188` 端口开放到局域网。

本指南的独立Worker适用于**Mac管理Windows**。Windows单机请使用[Desktop快速开始](QUICK_START.md#windows-单机第一次安装)，
由一个启动器自动管理本机Worker，不再安装/打开这份独立控制台。

## 下载与首次配置

1. 从[Mac + Windows Worker Release](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0)下载并运行 `Soda-Compute-Worker-1.2.0-Setup.exe`。
2. 当前安装器未签名；若 SmartScreen 拦截，先核对 Release 页面公布的 SHA-256，再选择继续运行。
3. 从开始菜单打开 `Soda Compute Worker`。
4. 启动 ComfyUI，确认 <http://127.0.0.1:8188> 能打开。
5. 在“设置”中确认 bridge、ComfyUI、LoRA 和模型目录。
6. 有效配置下会自动启动接收服务；若未运行，按界面提示保存配置并启动。需要独立自检时先停Worker，不能把上次自检通过当实时在线。

这套是 1.2.0 Pre-release，未正式签名；已完成运行与界面验收，完整 Setup 生命周期仍待验证。
Mac配对共享的首次授权由系统窗口处理；Worker窗口可收起到系统托盘，不显示命令窗口。

安装器已经包含 Python 3.12 runtime，普通用户不需要安装 Python。只有维护包或图形界面无法启动时，
才使用便携 ZIP 中的 `1-先自检.bat` 和 `2-启动Worker.bat`。图形包可先运行
`校验桌面包.ps1`，完整检查 `.exe`、Desktop UI 和 Worker 文件。

## 四类路径

| 路径 | 作用 | 是否可在不同硬盘 |
|---|---|---|
| `bridge_root` | 与 Mac 交换任务和结果 | 是 |
| ComfyUI 目录 | Windows 本机执行出图 | 是 |
| `lora_roots` | 允许扫描的 LoRA 文件夹 | 是，可配置多个 |
| `model_roots` | Checkpoint、UNet、VAE 等目录 | 是，可分类配置 |

Windows 可共享 `D:\PromptHub-Bridge`；Mac Finder 挂载后可能是
`/Volumes/PromptHub-Bridge`。Mac 页面填写 Finder 看到的共享根，不填写 ComfyUI 或模型目录。

## 每天启动

```text
先开 ComfyUI → 再打开 Soda Compute Worker 并启动 → 最后从 Mac 投递
```

图形版从主界面或托盘正常停止；任务位于 `processing` 时会拒绝停止，防止丢失正在生成或回传的结果。
维护脚本仍使用 `Ctrl+C`。意外关机后，先恢复 ComfyUI，再启动 Worker；它会检查 `processing` 中
尚未结束的任务。单机锁会阻止同时启动两只 Worker。

图形设置只在用户点击“保存并检查”时写入配置。已有 `worker-config.json` 会先备份为
`worker-config.backup.json`，再通过同目录临时文件原子替换；未知的超时和身份字段会保留。高级用户仍可
从设置面板打开 JSON。

## 版本与兼容性

自检生成的 `worker-status.json` 会记录：

- `worker_version`：当前 Worker 版本；
- `release_channel`：正式版、候选版或开发版；
- `protocol_version`：Mac/Windows 通信协议；
- `worker_build_sha256`：实际运行脚本的 SHA-256。

Mac 设备页会分别显示“连接是否成功”和“Worker 版本是否合适”。只要协议兼容，版本较旧通常只会
提示建议更新，不会误报为断线；协议不兼容时必须先更新 Worker。

自检文件是历史诊断；实时在线以Worker心跳和ComfyUI状态为准。Mac启动器每5秒检查，心跳超过25秒提示中断。
不同安装包可能同为1.1.0，核对Release日期、tag和安装包SHA-256；脚本build hash可辅助区分实际执行器。

## 安全升级 Worker

1. 确认当前没有任务位于 `processing`，再从图形界面或托盘停止 Worker。
2. 运行新版 `Soda-Compute-Worker-<版本>-Setup.exe` 覆盖安装。
3. 启动新版 Worker 并运行自检；安装器会继续使用原来的用户配置和日志目录。
4. 在 Prompt Hub“设备连接”重新检查，确认 Worker 版本和协议兼容。

高级用户继续使用便携 ZIP 时，应解压到新目录、验证 manifest，再复制旧目录的真实
`worker-config.json`；不要反向覆盖新版示例文件。

发行 ZIP 不包含真实 `worker-config.json`、任务、模型、图片或登录信息。

## LoRA 和底模清单

Worker 只读取配置白名单内的路径。它可以回传名称、类型、相对路径、大小、修改时间、metadata、
Civitai 来源和同名预览图；不会读取权重内容，也不会把大权重复制到 Mac。

模型清单支持 Checkpoint、Diffusion Model/UNet、VAE、Text Encoder、放大模型和 ControlNet。
LoRA Manager 检查可运行 `3-检查LoRAManager.ps1`，结果写入共享目录的 `diagnostics`。

## ComfyUI workflow

Worker 接收 ComfyUI 的 **API Format** workflow，不是普通 UI workflow JSON。仓库附带
`examples/comfyui-smoke-empty-image-v1.json`，只生成 128×128 空白测试图，不加载底模，可用于验证
任务领取、图片返回和 SHA-256 校验。

## 共享目录

| 目录 | 含义 |
|---|---|
| `outbox` | Mac 新投递的任务 |
| `processing` | Worker 已领取或正在执行 |
| `inbox` | Windows 已返回、等待 Mac 验收 |
| `completed` | 已完成任务记录 |
| `failed` | 失败或取消记录 |
| `packages` | ComfyUI API workflow 包 |
| `datasets` | Mac 交付给 Windows 的冻结数据集 |
| `diagnostics` | 自检和插件检查结果 |

## 安全边界

- ComfyUI URL 只允许 `127.0.0.1`、`localhost` 或 `::1`。
- 任务路径不能越过共享目录。
- manifest 和输出文件都做 SHA-256 校验。
- Worker 不保存 SMB 密码、API Key 或 token。
- 当前正式执行 ComfyUI 出图以及 LoRA/模型只读清单；训练仍在 Windows 现有工具中操作。
