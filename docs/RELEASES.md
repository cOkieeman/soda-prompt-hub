# 正式版本体系

## 版本号

Soda Prompt Hub 使用 `主版本.次版本.修订版本`：

- 主版本：出现需要迁移使用习惯或接口的重大不兼容变化；
- 次版本：增加向后兼容的功能；
- 修订版本：修复问题，不增加新的使用流程。

需要区分 Python 包阶段时可使用 PEP 440 后缀：

- `1.1.0.dev1`：开发版；
- `1.1.0rc1`：候选版；
- `1.1.0`：正式版。

开发版和候选版不得以正式版名义发布。首页、健康接口和 `/api/system/version` 都从 Python 包元数据
读取同一程序版本。

## 四类独立版本

| 版本 | 来源 | 作用 |
|---|---|---|
| 程序版本 | `pyproject.toml` 包元数据 | Core / WebUI 的软件版本 |
| 运行时通道 | 由程序版本推导 | 软件内显示的正式、候选或开发，不是安装包验收状态 |
| 数据结构版本 | SQLite `schema_migrations` | 个人数据库迁移状态 |
| Worker 版本与协议 | Worker `RELEASE.json` | Windows 执行器及通信兼容性 |

提示词资料库 revision、WD14/CLIP 模型版本和 Windows 模型版本不绑定程序版本，分别由各自系统管理。

## 发布元数据

根目录 `RELEASE.json` 描述程序版本、Python 版本和配套 Worker。`deploy/windows-worker/RELEASE.json`
描述 Worker 版本、发布通道和协议。自动测试要求它们与 `pyproject.toml` 保持一致。

## 桌面发行包

普通用户使用三个标准产物：

- Mac Apple Silicon：自包含 DMG；
- Windows Desktop：per-user Setup；
- Windows Compute Worker：独立 per-user Setup。

三个组件组成两套下载：Mac + 独立 Worker，以及 Windows 单机 Desktop（已管理本机 Worker）。
均把程序与个人数据分离。当前 1.1.0 桌面验收构建暂未做正式平台签名，首次运行的系统提示、系统要求、
文件大小和 SHA-256 必须随 Release 一起公布。详细边界见[商业分发与安装说明](COMMERCIAL_RELEASE.md)。

便携 ZIP 继续作为维护和排错选项，不作为普通用户的首选安装路径。

### Windows Worker 便携发行包

构建命令：

```bash
uv run python scripts/build_windows_worker_release.py
```

产物位于 `dist/Soda-Prompt-Hub-Windows-Worker-<版本>.zip`。构建器使用固定白名单，只包含 Worker
程序、脚本、示例配置、说明、许可证和 `MANIFEST.sha256`；不包含真实配置、任务、模型、图片或凭据。
ZIP 内文件时间和权限使用固定值；同一提交、同一工具链重复构建应得到相同 SHA-256，便于核对发布包。

发布前必须解压并重新计算清单中每个文件的 SHA-256，还要扫描绝对个人路径、token 和真实配置。

## Mac 更新策略

商业 DMG 通过覆盖 `/Applications/Soda Prompt Hub.app` 升级，个人资料目录保持不变。源码 ZIP 的安全
更新器继续作为维护路径：它先备份个人资料和旧程序，再准备依赖和初始化；失败时恢复旧程序。提示词来源
和模型不随代码更新。

## 发布检查清单

1. 同步 `pyproject.toml`、根 `RELEASE.json` 和 Worker `RELEASE.json` 的正式版本与通道。
2. 更新 `CHANGELOG.md`，写清新增、修复、升级步骤和兼容性。
3. 运行格式、lint、类型、锁文件、全量测试和覆盖率检查。
4. 检查全部页面脚本语法、Mac `.command` 语法和两个 Windows C# 工程 build。
5. 构建 Mac DMG 与两个 Windows Setup，逐个核对内部 manifest 和外层 SHA-256。
6. 在隔离环境验证 Mac App 只使用包内 Python；运行 `hdiutil verify`。
7. 在 Windows 实机验证覆盖安装、包内 Python、Core health、卸载保留数据和重装。
8. 扫描发行文件中的凭据、真实配置、个人绝对路径、`.venv`、`__pycache__`、`.pyc` 和大文件。
9. 生成统一发布清单和 SBOM；公布未签名状态、系统要求、文件大小与 SHA-256。
10. 在桌面和手机视口检查首页版本、数据结构版本与设备兼容状态。
11. 平台签名启用后，重新验证签名、notarization、安装、升级和卸载，不复用签名前的 hash。
12. 经维护者明确确认后才 commit、push、合并、打 tag 和创建 GitHub Release。

## Git 标签与 Release

正式版本使用 `v<版本>` 标签，例如 `v1.1.0`。已发布标签和附件不移动、不覆盖；通常后续修复使用新的修订版本。

### 2026-10-05：1.2.0 验收构建

[1.2.0 Release](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.2.0) 包含 Mac arm64 DMG、Windows x64 Desktop / Compute Worker Setup，以及统一校验清单和依赖库存。产品和 Worker 版本均为 `1.2.0`。

本次安装包保留 **Pre-release**，不改变原有 Latest：双端运行与维护者界面验收已完成，但 Windows Setup 的完整安装生命周期和正式平台签名尚未完成。测试范围见[发行验证](acceptance/release-1.2.0-20261005.md)。

附件来自已验收的冻结源码；发布提交只补充文档与验证范围，不改运行代码。`BUILD_PROVENANCE.json` 记录冻结源码与附件哈希，已有附件不覆盖。此次不新增 Linux 安装包。

### 2026-09-14：1.1.1 第一版预发布候选

源码、Core、Mac 启动器、Windows Desktop 和 Windows Worker 的产品版本统一为 `1.1.1`。第一批安装包
仍应在 GitHub 标为 **Pre-release**，用独立构建标识和 SHA-256 区分；“Pre-release”是安装包验收状态，
不是把程序版本退回 `1.1.1rc1`。在 Windows 新安装、备份、文件管理器和两种运行模式完成手工验收前，
不得设为 Latest。

| 下载 | Git tag | 发布状态 |
| --- | --- | --- |
| [Mac + Windows Worker](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.1.1-mac-windows-20260914) | `v1.1.1-mac-windows-20260914` | Pre-release |
| [Windows 单机](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.1.1-windows-standalone-20260914) | `v1.1.1-windows-standalone-20260914` | Pre-release |

### 2026-09-13：同版本桌面验收构建

本轮经维护者明确决定保持软件 `1.1.0`，用独立构建标签区分两套附件：

| 下载 | Git tag | 对应源码 |
| --- | --- | --- |
| [Mac + Windows Worker](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.1.0-mac-windows-20260913) | `v1.1.0-mac-windows-20260913` | `5f5e885` |
| [Windows 单机](https://github.com/cOkieeman/soda-prompt-hub/releases/tag/v1.1.0-windows-standalone-20260913) | `v1.1.0-windows-standalone-20260913` | `5f5e885` |

两条 GitHub Release 标为 **Pre-release**，没有取代9月9日 `v1.1.0` 的 Latest 标记。
软件内仍显示 `1.1.0 / stable`，这是运行时元数据，不代表新桌面包已完成原生人工验收。
用户应同时核对 Release 日期、使用模式、commit 和 `SHA256SUMS`，不能只比较界面版本号。
这些带模式/日期的 Git tag 不是 Python 包版本，不写入 `pyproject.toml`。

以后同版本构建也必须先确认独立的构建标识，绑定准确源码，公开测试范围、签名状态与每个附件的哈希；
不得移动本次标签或用新文件覆盖旧包。原生验收未完成时保留 Pre-release，并明确待测项。

### 2026-10-05：画风来源与本地映射构建

本次仅提交 PR，未合并、未创建发布标签，也未上传新的 GitHub Release。
产品与 Worker 版本仍为 `1.1.1`，本机构建标识为 `style-refresh-20261005`，不修改已有 `v1.1.1` 标签或附件。
Mac 仅 ad-hoc 签名、未 notarize；Windows Setup 未作 Authenticode 产品签名。
未来若授权发布，须使用独立构建标签并公开验收范围，不直接替换已有正式附件。
Linux 适配源码保留为实验性，本次不新增 Linux 发行附件。

本次已在 Mac Apple Silicon 和 Windows x64 上验证安装、包内 Python、Core health、来源筛选、
桌面快捷方式、双机桥接与 Windows 本机 Worker。只读扫描并完成两端模型 / LoRA 清单导入，
未执行新一轮真实图像生成、训练或全面原生升级 / 回滚组合验收。测试范围与附件哈希已在维护者本机记录；附件尚未公开。
九套来源的目录映射、公共图库、ComfyUI 模型和 LoRA 权重均不随安装包分发；须在使用者设备上另行配置。
安装器不默认清空个人资料。本次维护者的全新初始化是另行授权的部署操作。
