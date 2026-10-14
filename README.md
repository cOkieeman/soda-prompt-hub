# Soda Prompt Hub

Soda Prompt Hub 是一套本机优先的 AI 绘图创作与数据集整理工具。Mac 或 Windows Desktop 都可以独立
保存提示词、视觉参照、OC、创作项目、结果图、Caption、审核记录和冻结版本；Windows Worker 可以把
经过确认的任务交给本机 ComfyUI，也可以与另一台设备配合。LoRA 正式训练仍在 Windows 的训练工具中完成。

当前版本为 `1.2.0`，三端安装包见 [1.2.0 Release](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0)。
安装包标为 **Pre-release**：已完成双端运行与维护者界面验收，完整安装生命周期及平台签名仍待完成。
版本与构建标识的区别见[正式版本体系](docs/RELEASES.md)。

1.2.0 加入场景提案、画幅建议、真实 LoRA 辅助、个人画廊与生成记录；详见[创作指南](docs/CREATIVE_AI_GUIDE.md)。

## 下载：先选使用方式

| 使用方式 | 下载 | 要运行的应用 |
| --- | --- | --- |
| Mac 管理 Windows | [Mac 启动器 + Windows Worker](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0) | Mac 安装 DMG；Windows 安装并打开 Soda Compute Worker |
| Windows 单机 | [Windows Desktop](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0) | 只安装并打开 Soda Prompt Hub，自动管理本机 Core / Worker |

Mac 包面向 Apple Silicon（arm64），Windows 包面向 x64。下载 Release 的 Assets 中的 DMG / Setup，
不是 GitHub 自动生成的 Source code ZIP。每套附有 `SHA256SUMS` 和手动验收说明。
Windows 单机**不需要另开独立 Worker，也不需要 SMB 配对**。两套请分开测试，避免同时运行时混淆任务。

### Linux（实验性，非官方构建）

Linux 支持由社区适配分支提供，状态为 **Experimental**，不随官方 DMG / Setup 发布：

| 能力 | Linux 状态 |
| --- | --- |
| Core：资料库、创作、审核、数据集整理 | 支持 |
| systemd 用户服务、安装 / 更新 / 卸载脚本 | 支持 |
| 应用菜单启动器 | 支持：点击后启动或复用 Core，并在默认浏览器打开工作台 |
| Compute Worker（ComfyUI 出图执行端） | **实验性支持**（`install.sh --with-worker`，见 [Linux Worker](docs/linux/WORKER.md)） |
| SMB 双机配对 | 暂不支持（Linux 用本地桥接目录代替） |
| LoRA 正式训练 | 暂不支持（仅 Windows） |

分支做了什么、怎么用、怎么验证见[Linux 适配说明](docs/linux/README.md)；
具体步骤见[安装](docs/linux/INSTALL.md)与[更新](docs/linux/UPDATE.md)。

## 五分钟开始

1. 按上表下载，核对校验和，备份已有资料并正常退出旧服务，再安装对应应用。
2. Windows 单机：启动 ComfyUI，再打开 Soda Prompt Hub，在启动器设置填写本机 ComfyUI 地址。
3. Mac 管理 Windows：Windows 打开 ComfyUI 和独立 Soda Compute Worker；Mac 打开应用，按“设备连接”的配对引导完成共享授权。
4. 启动台显示 Core 已就绪后打开工作台，确认实时 Worker / ComfyUI 状态。最终用户无需预装 Python、`uv`、Git 或 `.NET SDK`。
5. 按需安装资料库和可选模型；外部 AI 服务的 URL、Key 与模型在“设备连接 → 模型服务”配置。

完整安装步骤见[快速开始](docs/QUICK_START.md)，测试范围见[1.2.0 发行验证](docs/acceptance/release-1.2.0-20261005.md)。

程序默认只监听本机 `127.0.0.1`。新用户的个人资料默认保存在：

| 管理端 | 个人资料目录 |
| --- | --- |
| Mac | `~/Documents/Soda Prompt Hub/prompt-library` |
| Windows 单机 | `%USERPROFILE%\Documents\Soda Prompt Hub\prompt-library` |
| Linux | `~/.local/share/soda-prompt-hub/library`（由 `PROMPT_HUB_LIBRARY_ROOT` 决定） |

程序和个人资料彼此独立。重新安装或更新程序不会主动移动、删除提示词、图片、数据库或模型。

启动器不显示 Terminal。关闭窗口或“收起窗口”不会停止服务；Mac 用“退出并停止服务”，
Windows 单机用“退出并停止本机服务”。只退出启动器可以保留服务。
日志、数据目录和故障处理入口见[安装说明](docs/COMMERCIAL_RELEASE.md)与[排错](docs/TROUBLESHOOTING.md)。

## 它能做什么

- 从灵感、OC 或参考图建立绘图项目，并输出 Anima tags 与 Krea 2 自然语言 Prompt。
- AI 提供场景、镜头与画幅方案，以及真实本地 LoRA 搭配；支持个人作品与参考画廊、按用途分析和方案复盘，见[创作辅助指南](docs/CREATIVE_AI_GUIDE.md)。
- 检索本地提示词库、视觉参照、网页收藏和 OC Manager JSON；可按来源快速切换，并只查看带图资料。
- 使用 AnimaDex 的角色、画师和作品缩略图作视觉参照；完整目录仍由用户使用自己的导出 token 下载到本机。
- 导入 Krea2、Anima、Illustrious Style Explorer 与 Neons 资料；支持只读本地图库映射；见[画风资料来源](docs/STYLE_SOURCES.md)。
- 使用 LM Studio 或可选的 OpenAI-compatible 模型辅助整理；模型结果先作为建议或草稿。
- 使用 WD14 生成 Anima 标签草稿，人工审核后冻结为带哈希的版本化数据集。
- 通过 Windows 本机 Worker 运行 ComfyUI、回收图片，并同步 LoRA/底模只读清单；Mac 双机模式使用 SMB 交换任务。
- 使用 `Soda Compute Worker.exe` 在 Windows 图形界面查看 GPU、bridge、ComfyUI 和当前任务，并从系统托盘启停 Worker。
- 在工作台管理 Workflow Profile、底模、LoRA、尺寸、Steps、CFG、Sampler 和 Scheduler 的选择。

## 两种方式，数据分别保存在管理端

Windows 单机的项目、审核和结果保存在 Windows；Core 和 Worker 使用本地任务目录交换记录，不需要共享。
Mac 管理 Windows 时，项目、审核和结果保存在 Mac，通信过程如下：

```text
Mac Prompt Hub（事实、审核、版本）
        ↓ 写任务与冻结数据集
SMB 共享文件夹（运输通道）
        ↓ Worker 领取
Windows ComfyUI（出图）
        ↓ 返回图片与运行记录
Mac 校验 SHA-256 后导入
```

Windows 模型权重不会被复制到 Mac；Mac 上选择的是 Worker 回传的只读清单。SMB 密码由 Finder 与
macOS 钥匙串保存，Prompt Hub 不读取密码。更完整的文件关系见[设备与文件关系](docs/ARCHITECTURE.md)。

## 文档导航

| 我现在要做什么 | 应该看哪里 |
|---|---|
| 第一次安装，先把页面打开 | [快速开始](docs/QUICK_START.md) |
| 下载、安装、升级或卸载商业包 | [商业分发与安装说明](docs/COMMERCIAL_RELEASE.md) |
| 从灵感到出图、复盘和数据集 | [核心工作流](docs/WORKFLOWS.md) |
| 设计有故事感的画面、挑选 LoRA 并整理个人画廊 | [创作辅助与画廊](docs/CREATIVE_AI_GUIDE.md) |
| 按页面顺序完成日常操作 | [用户使用说明书草稿](docs/USER_MANUAL_DRAFT.md) |
| 启动、停止、备份、恢复和安全更新 | [Mac 使用与维护](docs/MAC_GUIDE.md) |
| 在 Windows 安装、自检和启动 Worker | [Windows Worker 完整指南](docs/WINDOWS_WORKER.md) |
| 按需安装 WD14、真人打标和 CLIP | [可选本地模型](docs/OPTIONAL_MODELS.md) |
| 构建 Windows Worker 图形启动器 | [Windows Shell 构建说明](deploy/windows-shell/README.md) |
| 了解 Mac、Windows Worker 与 Windows 单机版的产品形态 | [Desktop 产品计划](docs/DESKTOP_PRODUCT_PLAN.md) |
| 查看三端启动器的视觉与交互规格 | [Desktop UI 规格](docs/DESKTOP_UI_SPEC.md) |
| 弄清两台设备和文件怎样关联 | [设备与文件关系](docs/ARCHITECTURE.md) |
| 页面打不开、共享盘断开或任务不动 | [常见问题与排错](docs/TROUBLESHOOTING.md) |
| 版本号、更新通道和发布检查 | [正式版本体系](docs/RELEASES.md) |
| 查看长期开发边界和历史路线 | [开发计划](DEVELOPMENT_PLAN.md) |
| 安装新包后手动验收两种模式 | [1.2.0 发行验证](docs/acceptance/release-1.2.0-20261005.md) |

## 当前边界

- Prompt Hub 交付打好标、经过人工审核的冻结数据集，但不自动开始正式训练。
- 标签终筛、正则、CUDA/Torch 环境、训练参数和长时间训练由 Windows 工具负责。
- OC Manager 通过 JSON 导入，Prompt Hub 不回写它的数据库。
- 外部数据集按只读方式扫描；缩略图、草稿和审核状态保存在 Prompt Hub 自己的资料目录。
- 公共仓库不包含模型权重、个人图片、数据库、API Key、SMB 密码或真实 `worker-config.json`。

## 开发者启动

```bash
git clone https://github.com/cOkieeman/soda-prompt-hub.git
cd soda-prompt-hub
uv sync
uv run --no-sync prompt-hub serve --host 127.0.0.1 --port 8765
```

自定义个人资料位置时使用 `PROMPT_HUB_LIBRARY_ROOT`；模型目录使用 `PROMPT_HUB_MODELS_ROOT`。
开发检查与贡献约定见[开发计划](DEVELOPMENT_PLAN.md)和[正式版本体系](docs/RELEASES.md)。

## 许可证

代码采用 [MIT License](LICENSE)。第三方提示词、图片、模型、工作流和数据集继续遵循各自来源的
许可证或使用条款，不因本项目采用 MIT 而被重新授权。
