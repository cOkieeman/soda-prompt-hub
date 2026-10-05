# Soda Prompt Hub — Linux 适配

> **非官方构建。** 本目录属于社区维护的 Linux 适配分支（`linux/main`），不是
> [cOkieeman/soda-prompt-hub](https://github.com/cOkieeman/soda-prompt-hub) 的官方发行。
> 上游项目与许可证见仓库根目录 `README.md` 与 `LICENSE`。

**一句话**：在不破坏上游 macOS / Windows 功能的前提下，让 Soda Prompt Hub 在 Linux 上原生运行，
并建立一套跟随上游更新、自动测试、自动构建的长效维护机制。

**当前状态**：Ubuntu 24.04 实测通过；GitHub Actions 四个作业全绿；向上游提交了 2 个修复 PR。
Linux 侧改动几乎全是新增文件，核心代码只动了两处真实缺陷。上游基线 `1.1.1`（`upstream/main` = `e96249b`）。

## 目录

- [快速开始](#快速开始)
- [支持状态](#支持状态)
- [这个分支做了什么](#这个分支做了什么)
- [修复并已提交上游的缺陷](#修复并已提交上游的缺陷)
- [上游同步机制](#上游同步机制)
- [已知限制](#已知限制)
- [怎么验证](#怎么验证)
- [文档索引](#文档索引)

## 快速开始

```bash
git clone https://github.com/TPSROG/soda-prompt-hub.git
cd soda-prompt-hub
git switch linux/main
./deploy/linux/install.sh
```

然后打开 <http://127.0.0.1:8765>。

安装完成后也可以直接从应用菜单点击 **Soda Prompt Hub**。启动器会复用正在运行的 Core，或先启动
Core 并等待健康检查通过，再用默认浏览器打开工作台。无桌面会话的服务器与 WSL 继续使用 CLI。

安装脚本会检查环境、创建用户数据目录、执行 `uv sync --locked`、安装 systemd **用户**服务并做健康检查；
不需要 `sudo`，也不会删除任何用户数据。参数、目录布局与排错见 [安装指南](INSTALL.md)，
更新与回滚见 [更新指南](UPDATE.md)。

日常命令：

| 操作 | 命令 |
| --- | --- |
| 查看状态 | `soda-prompt-hub status` |
| 启停 / 重启 | `soda-prompt-hub start` / `stop` / `restart` |
| 查看日志 | `soda-prompt-hub logs` |
| 安全更新 | `soda-prompt-hub update` |

程序与用户数据完全分离：程序在仓库目录，数据默认在 `~/.local/share/soda-prompt-hub/`。

## 支持状态

| 能力 | Linux 状态 |
| --- | --- |
| Core：资料库、检索、创作、审核、数据集整理 | **支持**（Ubuntu 24.04 实测；22.04 需本分支的媒体类型修复） |
| systemd 用户服务、安装 / 更新 / 卸载脚本 | **支持** |
| CLI（`prompt-hub` / `soda-prompt-hub`） | **支持** |
| 应用菜单启动器 | **支持**：Desktop Entry + 用户级图标；浏览器 UI |
| Compute Worker（ComfyUI 出图执行端） | **实验性支持**：`install.sh --with-worker`，已用真实 ComfyUI 出图验证 → [WORKER.md](WORKER.md) |
| 远端 / 带认证的 ComfyUI | **支持**：`comfyui_url` 可用 `http(s)://用户名:密码@主机` |
| SMB 双机配对 | 暂不支持；Linux 侧用本地桥接目录代替（无需 SMB） |
| LoRA 正式训练 | 暂不支持（Windows-only） |
| 嵌入式桌面宿主 / 托盘 | 暂不支持；轻量启动器使用 systemd + 默认浏览器 |
| `.deb` / `.rpm` / AppImage / Snap / Flatpak | 暂不提供；第一阶段只出 `tar.gz` + `SHA256SUMS` |

整体按 **Experimental** 对待：核心与部署链路已实测，但不承诺与官方安装包相同的验收强度。

## 这个分支做了什么

| 阶段 | 内容 | 证据 |
| --- | --- | --- |
| Phase 1 | 仓库审计：找出全部平台耦合点并分级（A–E） | [兼容性审计](COMPATIBILITY_AUDIT.md) |
| Phase 2 | 设计决策（D1–D11）与实施计划，含"明确不做"清单 | [实施计划](IMPLEMENTATION_PLAN.md) |
| Phase 3 | Linux 原生运行验证 | WSL2 Ubuntu 24.04 实测 |
| Phase 4 | `deploy/linux/`：安装 / 卸载 / 更新 / 启停 / 状态 + systemd 用户服务 | 14 项实机验收（见实施计划 §7） |
| Phase 5 | `tests/linux/`：部署层静态契约测试 + Linux 行为测试 | 25 个用例；完整套件 577 passed |
| Phase 6 | `.github/workflows/linux.yml`：格式 / Lint / 类型检查、22.04 + 24.04 测试、部署冒烟、systemd 用户服务 | 4 个作业全绿 |
| Phase 7 | 固定维护分支 `linux/main`；按需手动合并 `upstream/main` 并通过 PR 审查 | 见 [上游同步机制](#上游同步机制) |
| Phase 8 | Release 暂不自动化；需要时从已通过 Linux CI 的 `linux/main` 手动打包 | 避免非默认分支的失效触发器与写权限风险 |
| Phase 9 | 文档：本目录、根 README 的 Linux 章节、CHANGELOG | 本页与 [INSTALL](INSTALL.md) / [UPDATE](UPDATE.md) |

**刻意的约束**：Linux 侧改动几乎全部是新增文件（`deploy/linux/`、`scripts/linux/`、`tests/linux/`、
`docs/linux/`、Linux CI 工作流）。核心代码只改了下面两个真实缺陷——目的是让这个分支随时能干净地跟随上游 rebase。

## 修复并已提交上游的缺陷

两个修复都已单独开 PR 给上游（分支从 `upstream/main` 拉出，各自只有一个提交，不含任何 Linux 部署内容）：

| PR | 内容 | 状态 |
| --- | --- | --- |
| [#20](https://github.com/cOkieeman/soda-prompt-hub/pull/20) | `fix: 显式指定图片媒体类型，不再依赖系统 MIME 数据库` | MERGED |
| [#21](https://github.com/cOkieeman/soda-prompt-hub/pull/21) | `test: 心跳新鲜度用例改为在执行时生成时间戳` | MERGED |

### #20 WebP 缩略图被当成二进制流下发（真实缺陷）

| 项目 | 内容 |
| --- | --- |
| 现象 | Ubuntu 22.04 上，资料库来源缩略图与创作项目结果图返回 `Content-Type: application/octet-stream`，浏览器不再内联显示图片 |
| 根因 | 4 处 `FileResponse(path)` 未显式指定 `media_type`，Starlette 于是调用 `mimetypes.guess_type()`；**CPython 内置 MIME 表不含 `.webp`**，该映射只能来自系统 `/etc/mime.types`（Ubuntu 24.04 有、22.04 没有） |
| 影响面 | 任何 `/etc/mime.types` 不完整的 Linux（22.04 LTS、最小化容器、服务器镜像）；属跨平台隐患 |
| 修法 | 新增 `prompt_hub.media.media_type_for(path)`，对项目自己产出的图片格式给出确定类型，其余后缀仍交给 `mimetypes` |
| 覆盖端点 | 资料库来源媒体、创作项目结果图、网页收藏媒体、数据集工作区原图 |
| 回归测试 | `tests/test_media_types.py`（把 `mimetypes.guess_type` 打桩成永远返回 `None`） |
| 复现证据 | 隐藏 `/etc/mime.types` 后：修复前 3 个测试失败，修复后 64 个相关测试全部通过 |

### #21 心跳新鲜度用例时间敏感（测试缺陷）

| 项目 | 内容 |
| --- | --- |
| 现象 | 偶发失败 `assert 'connected' == 'stale'`；同一提交在较快的 ubuntu-24.04 通过、在 ubuntu-22.04（整轮 223 秒）失败 |
| 根因 | 参数表在**收集阶段**计算 `now + 2 分钟`，而判定条件是 `age < -15s` 或 `age > 25s`；用例若在收集后 **105–145 秒**之间执行，`age` 落进 `-15–+25 秒` 窗口 |
| 实证 | 实测判定窗口：未来 10 秒 → `connected`，未来 30 秒 → `stale`，过去 30 秒 → `stale` |
| 修法 | 时间戳改到用例内部生成，与判定使用同一时刻的时钟 |
| 性质 | 与平台无关的测试稳定性问题，慢机器上同样会命中 |

## 上游同步机制

`linux/main` 是独立维护分支。需要同步时，从它创建临时分支，合并 `upstream/main`，解决冲突并让
`.github/workflows/linux.yml` 全绿后，再通过 PR 合回 `linux/main`。不要直接 push 合并结果到维护分支。

`schedule`、`workflow_run` 与 `workflow_dispatch` 要求工作流存在于默认分支。本仓库默认分支继续保持
`main`，所以 Linux-only 分支不携带自动同步或自动 Release 工作流。以后若确实需要定时任务，应在
`main` 上单独审查一个最小调度工作流，并把 checkout ref 固定为 `linux/main`；不得 checkout 任意
PR 的 `head_sha` 后使用写权限。

## 已知限制

| 项目 | 说明 | 出处 |
| --- | --- | --- |
| 数据集目录浏览不含外接卷 | `browse_roots()` 只认 `$HOME` 与 macOS `/Volumes`；Linux 的 `/media`、`/mnt` 不在范围内 | 审计 §11 F1 |
| 主目录快捷入口仅英文名 | `Desktop / Pictures / Downloads`，中文等 locale 下不显示（有 `is_dir()` 保护，不报错） | 审计 §11 F2 |
| 使用模式语义 | ✅ 已修复：Linux 现在是 `linux_local` 本机模式（审计 G1/G2） | 审计 §13 |
| Compute Worker | 本机 ComfyUI 执行端仍仅限 Windows | 审计 §6 |

## 怎么验证

```bash
scripts/linux/check-env.sh              # 环境自检（只检查、不安装）
./deploy/linux/status.sh                # 服务、监听、健康、数据占用
uv run pytest tests/linux -q            # 25 个 Linux 用例
uv run pytest -q                        # 完整套件（577 passed / 9 skipped）
```

CI：仓库 **Actions → Linux**，四个作业 —— `格式 / Lint / 类型检查`、`Tests on ubuntu-22.04`、
`Tests on ubuntu-24.04`、`systemd 用户服务`（在真实 runner 上执行安装、状态检查、健康检查与卸载）。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [INSTALL.md](INSTALL.md) | 安装步骤、参数、目录布局、排错 |
| [UPDATE.md](UPDATE.md) | 安全更新、回滚、从发行包更新 |
| [COMPATIBILITY_AUDIT.md](COMPATIBILITY_AUDIT.md) | 平台耦合审计（§10 实测、§11 复核、§12 CI 发现） |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | 设计决策、阶段计划、验收证据与待办 |
| [DEV_ENVIRONMENT.md](DEV_ENVIRONMENT.md) | WSL2 开发/测试环境的实际状态 |
| [WORKER.md](WORKER.md) | Linux Compute Worker：安装、配置、桥接协议、验证结果与限制 |

## 许可与署名

代码沿用上游的 [MIT License](../../LICENSE)。本 Linux 分支由社区维护，非官方发行；
第三方提示词、图片、模型、工作流与数据集继续遵循各自来源的许可证或使用条款。
