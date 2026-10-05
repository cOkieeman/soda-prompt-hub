# Linux Implementation Plan

本文件是主任务书 §30 要求的 **Implementation Plan**，与 `docs/linux/COMPATIBILITY_AUDIT.md`（审计）配套。
两者合起来构成第一阶段的分析交付物。

基线：`upstream/main` = `e96249b`（1.1.1）。实测环境见 `docs/linux/DEV_ENVIRONMENT.md`。

---

## 1. 范围

### 第一阶段做

| 项目 | 交付物 |
| --- | --- |
| Linux 原生运行 | 已验证：`uv sync --locked` + `uv run --no-sync prompt-hub serve` |
| Linux 部署层 | `deploy/linux/`：安装 / 卸载 / 更新 / 启停 / 状态 + systemd **user** unit |
| Linux 便利命令 | `soda-prompt-hub`（start/stop/restart/status/logs/serve/update） |
| Linux 轻量启动器 | 用户级 Desktop Entry + 图标；启动/复用 Core 后打开默认浏览器 |
| Linux 测试 | `tests/linux/`：启动、数据目录、路径、HTTP 契约 |
| Linux CI | `.github/workflows/linux.yml`：只补上游没有的部分（Ubuntu 22.04/24.04 矩阵 + 部署冒烟） |
| 上游同步 | 固定维护分支 `linux/main`；按需从临时分支合并 `upstream/main`，通过 PR 回合 |
| Release | 暂不自动化；从通过 Linux CI 的 `linux/main` 手动打包 |
| 文档 | `docs/linux/INSTALL.md`、`docs/linux/UPDATE.md`、README Linux 章节、CHANGELOG Linux 条目 |

### 第一阶段明确不做

| 项目 | 原因 |
| --- | --- |
| Linux Compute Worker（ComfyUI 执行端） | Windows 实体（GUI/托盘/本机服务管理），需先抽协议，属后续独立设计 |
| SMB 双机配对 | 上游实现硬编码 macOS（`remote_routes.py:85`、`/usr/bin/open`） |
| LoRA 正式训练 | 上游本身也在 Windows 训练工具中完成 |
| 嵌入式桌面宿主 / 托盘 | 上游宿主为 C#/WinForms 与 Swift；Linux 轻量版用 Desktop Entry + systemd + 浏览器 |
| `.deb` / `.rpm` / AppImage / Snap / Flatpak | 主任务书 §18 |
| Docker | 主任务书 §19 |

---

## 2. 已锁定的设计决策

| # | 决策 | 依据 |
| --- | --- | --- |
| D1 | **不新增 `src/prompt_hub/platform/` 抽象层** | 平台差异已收敛在 3 处；上游迭代极快，中间层只会放大 rebase 成本（审计 §3） |
| D2 | **Linux 侧改动全部为新增文件** | 唯一例外是 `.gitattributes` 追加 LF 规则；核心代码零改动（审计 §3、§7 R1） |
| D3 | **不修改核心默认路径语义** | 资料库/模型路径一律由部署层通过环境变量注入（审计 B1） |
| D4 | **默认资料库落在 XDG 目录** | `$XDG_DATA_HOME/soda-prompt-hub/library`，而不是 `~/Documents/...`；不改核心默认值 |
| D5 | **systemd 用 user 级，不用 root** | 主任务书 §6/§7/§25 |
| D6 | **默认只监听 `127.0.0.1`** | 主任务书 §25；非本机地址需显式传参并打印警告 |
| D7 | **`loginctl enable-linger` 只作为可选参数** | 主任务书 §7；实测 WSL 下 `Linger=no` |
| D8 | **不重复实现上游已有能力** | 审计 A6/A7（`xdg-open` 分支、`shutil.which("git")` 均已存在） |
| D9 | **Linux CI 不引入新工具，但按 §13 执行项目既有的格式 / lint / 类型检查命令** | 主任务书 §13；命令与上游 `ci.yml` 完全一致，新增价值在 22.04/24.04 矩阵与部署冒烟 |
| D10 | **上游同步不直接 merge 到生产分支** | 主任务书 §16：同步分支 → CI → 成功开 PR / 失败开 Issue |
| D11 | **G1（usage mode）走上游 PR，不在本地长期携带** | 涉及 `web.py`/`desktop_connection.py` 等核心文件（审计 G1） |

---

## 3. 阶段与验收

### Phase 4｜Linux 部署层（本阶段）

新增：

```text
deploy/linux/
├── lib.sh                     # 共用函数（路径解析、systemd 探测、健康检查）
├── install.sh                 # 安装：检查环境 → 建目录 → uv sync → 装 unit → 启服务 → 健康检查
├── uninstall.sh               # 卸载：停服务、移除 unit 与便利命令；默认保留用户数据
├── update.sh                  # 更新：git pull --ff-only → uv sync → 重启 → 健康检查 → 数据不变证明
├── start.sh / stop.sh / status.sh
└── soda-prompt-hub.service    # systemd user unit 模板
```

安装布局：

| 内容 | 位置 |
| --- | --- |
| 程序（仓库本体） | 用户 clone 的位置，脚本自动解析绝对路径 |
| Python 环境 | `<repo>/.venv`（由 `uv sync` 创建） |
| 用户数据 | `${XDG_DATA_HOME:-~/.local/share}/soda-prompt-hub/{library,models}` |
| 安装记录 | 同上目录下 `install.env`（供 update/uninstall/启停脚本读取） |
| systemd unit | `${XDG_CONFIG_HOME:-~/.config}/systemd/user/soda-prompt-hub.service` |
| 便利命令 | `~/.local/bin/soda-prompt-hub` |

验收：

```bash
./deploy/linux/install.sh
systemctl --user status soda-prompt-hub
curl http://127.0.0.1:8765/api/health
./deploy/linux/update.sh          # 用户数据不变
./deploy/linux/status.sh
./deploy/linux/uninstall.sh       # 数据默认保留
```

### Phase 5｜Linux 测试（`tests/linux/`）

| 用例组 | 内容 |
| --- | --- |
| 部署静态检查 | 7 个脚本 `bash -n` 通过；严格模式；无 `sudo` 硬编码；无 `chmod 777`；默认 `127.0.0.1` |
| 启动 | 冷启动 → `/api/health` 返回 ok |
| 数据目录 | 建库、写入、重启后仍可读 |
| 路径 | 含空格、中文、UTF-8、符号链接的资料库根目录 |
| 便利命令 | `soda-prompt-hub status` 能读取 `install.env` 并给出正确状态 |

验收：`uv run pytest tests/linux -q` 通过，且不影响上游既有测试。

### Phase 6｜Linux CI

`.github/workflows/linux.yml`：`ubuntu-22.04` + `ubuntu-24.04` 矩阵；`uv sync --locked` → 既有 lint/type/test →
新增 `tests/linux` → 部署冒烟（`install.sh --no-service` 场景 + systemd 可用时跑 user service）。
安装 Node.js（审计 §10.2：缺 Node 会导致 1 个测试硬失败）。

### Phase 7｜上游同步

按需从 `linux/main` 建临时同步分支，合并 `upstream/main`，跑 Linux CI 后通过 PR 回合；冲突必须人工处理，
不得直接向维护分支 push。

### Phase 8｜Release

第一阶段不在 Linux-only 分支启用自动 Release。需要发行时，从已通过 Linux CI 的 `linux/main` 使用
`scripts/build_linux_release.py` 手动产出带版本、架构和日期的 `tar.gz`、`LINUX_RELEASE.json` 与
`SHA256SUMS`。

### Phase 9｜文档

`docs/linux/INSTALL.md`、`docs/linux/UPDATE.md`、README Linux 章节（标注 `Experimental`，写明 Core 支持 / Worker 不支持）、
`CHANGELOG.md` 的 Linux 条目。

### Phase 10｜最终验收

按主任务书 §27（干净 Ubuntu 上 clone → install → systemd → 8765 → update 后数据不丢）
与 §29（13 个问题逐条给答案）执行。

---

## 4. 独立轨道：G1 反哺上游

`usage_mode` 目前只有 `windows_local` / `mac_remote`，Linux 会落入 `mac_remote`（审计 G1）。
计划向上游提交一个**纯增量** PR：新增 `linux_local` 取值 + 文案与示例路径的 Linux 分支。
在合并前，Linux 部署层**不改核心**，接受 `mac_remote` 的事实语义，并在 README / CHANGELOG 中如实说明。

---

## 5. 风险与缓解（承审计 §7）

| 风险 | 缓解 |
| --- | --- |
| 上游高速迭代导致 rebase 冲突 | 改动纯新增（D2）；唯一核心改动走上游 PR（D11） |
| WSL 与真实 Ubuntu 差异 | CI 用真实 `ubuntu-latest` 交叉验证；WSL 限制写入 `DEV_ENVIRONMENT.md` |
| `Linger=no` 导致 user service 在会话结束后停止 | `install.sh --enable-linger` 作为可选参数（D7），并在安装输出中明确提示 |
| 误改用户数据 | `update.sh` 打印更新前后数据库大小/mtime 作为证据；`uninstall.sh` 默认保留数据 |
| 上游 CI 的 Node 隐性依赖 | Linux CI 显式安装 Node（审计 §10.2） |

---

## 6. 提交序列（对应主任务书 §22）

```text
audit: add Linux compatibility audit                     ✅ 已完成
chore(linux): pin shell scripts to LF line endings       ✅ 已完成
audit: record measured Linux baseline and Node dependency ✅ 已完成
docs(linux): add Linux implementation plan               ← 本文件
feat(linux): add native Linux deployment scripts
feat(linux): add systemd user service
test(linux): add Linux compatibility tests
ci: add Linux CI workflow
ci: add upstream compatibility workflow
ci: add Linux release workflow
docs(linux): add Linux installation guide
```

---

## 7. 实施进度与实测证据

### Phase 4｜Linux 部署层 — ✅ 已完成并在 WSL2 实机验证（2026-09-14）

环境：WSL2 + Ubuntu 24.04.5，systemd 255，`systemctl --user` 可用。

| # | 验收项 | 结果 |
| --- | --- | --- |
| 1 | `./deploy/linux/install.sh` | ✅ 一次通过：环境检查 → 建目录 → `uv sync --locked` → 写 unit → 启用并启动 → 健康检查 |
| 2 | 渲染后的 unit | ✅ 占位符全部替换为绝对路径；`Environment=` 注入资料库/模型目录；`ExecStart` 指向 `.venv/bin/prompt-hub` |
| 3 | `systemctl --user status soda-prompt-hub` | ✅ `active (running)`，`enabled`，Main PID 正常，日志进入 journald |
| 4 | 监听范围 | ✅ 仅 `127.0.0.1:8765`（`ss -ltn` 实测），未暴露 `0.0.0.0` |
| 5 | `GET /`、`/api/health`、`/api/stats` | ✅ 200 / `status: ok` / 正常 |
| 6 | `soda-prompt-hub version` / `status` | ✅ 输出 1.1.1 与完整状态报告（含 unit、PID、监听、健康、数据占用、日志） |
| 7 | `install.sh` 幂等（重复执行） | ✅ 检测到既有安装并沿用既有数据目录，只重启服务，不重复建目录 |
| 8 | `update.sh` | ✅ 拉取（已是最新）→ 依赖同步 → 重启 → 健康检查；**更新前后数据库大小与 mtime 完全一致** |
| 9 | 用户数据实证 | ✅ 更新前后标记文件 `private/personal-prompts/wsl-marker.txt` 与数据库均保留 |
| 10 | `update.sh` 脏工作区保护 | ✅ 工作区有未提交改动时拒绝执行并给出提示（需 `--force`） |
| 11 | 崩溃自动重启 | ✅ `kill -9` 主进程后第 5 秒自动重启，健康检查恢复（`Restart=on-failure` + `RestartSec=5`） |
| 12 | 无 systemd 场景（direct 模式） | ✅ `--no-service` + `start.sh`/`stop.sh` 以进程方式启停成功（用 `/tmp` 覆盖 XDG 路径、端口 8799 验证，未影响正式安装） |
| 13 | `uninstall.sh`（默认） | ✅ 停止并禁用服务、移除 unit 与便利命令；**资料库、标记文件、数据库全部保留** |
| 14 | 重新安装 | ✅ 卸载后重装恢复正常，健康检查通过 |

安装布局实测结果：

| 内容 | 实测位置 |
| --- | --- |
| 程序 | `/home/voldm/projects/soda-prompt-hub`（仓库本体） |
| Python 环境 | `<repo>/.venv` |
| 用户数据 | `~/.local/share/soda-prompt-hub/{library,models}` |
| 安装记录 | `~/.local/share/soda-prompt-hub/install.env` |
| systemd unit | `~/.config/systemd/user/soda-prompt-hub.service` |
| 便利命令 | `~/.local/bin/soda-prompt-hub` |

### 与主任务书 §27 第一阶段验收标准的对照

| 验收步骤 | 状态 |
| --- | --- |
| 干净环境中 clone 后执行 `./deploy/linux/install.sh` | ✅ 已完成（WSL2 Ubuntu 24.04） |
| `systemctl --user status soda-prompt-hub` 显示运行中 | ✅ |
| 访问 `http://127.0.0.1:8765` | ✅ 200 |
| `./deploy/linux/update.sh` 安全更新且不丢用户资料 | ✅ 见上表 8–10 |

### Phase 5｜Linux 测试 — ✅ 已完成

| 项目 | 结果 |
| --- | --- |
| 静态契约测试 | `tests/linux/test_linux_packaging.py`（脚本清单、严格模式、不依赖 CWD、无 sudo、无 777、不把远程内容管道给 shell、默认只用 127.0.0.1、unit 必须是用户服务且有重启策略、模板占位符必须全部被替换、XDG 路径、update 仅快进、uninstall 默认保留数据、LF/UTF-8/无本机路径、`bash -n`） |
| 行为测试 | `tests/linux/test_linux_deployment.py`（隔离 `HOME`/XDG 下跑 help、未安装时的错误提示、`install --no-service` → start → 健康检查 → status → stop 全流程，并验证程序与用户数据分离） |
| 结果 | 新增用例 **25 passed**；完整套件 **577 passed / 9 skipped / 0 failed**（WSL2 Ubuntu 24.04） |
| 抓到的真实缺陷 | `install.sh --no-service` 打印的直接运行命令漏了 `PROMPT_HUB_MODELS_ROOT`（已修复） |
| 上游契约约束 | `tests/test_public_docs.py` 要求 `docs/*.md` 顶层**恰好**是 12 个既有文件，因此 Linux 文档统一放在 `docs/linux/` 子目录（不改上游契约） |
| §12 清单覆盖闭环 | 严格复核发现首轮缺 4 项，已补齐：中文 + UTF-8 + 空格路径、`PROMPT_HUB_MODELS_ROOT` 行为、资料库**写入 / 读取 / 重启后保留**、`localhost` 访问 |
| 复核新增发现 | §1.1 关键词重跑后新增 2 项 Linux 受限点（F1 数据集浏览不含外接卷、F2 快捷入口仅英文目录名），已写入审计 §11 |

### Phase 6｜Linux CI — ✅ 工作流就绪

`.github/workflows/linux.yml`：

- `lint` 作业：按主任务书 §13 执行项目**既有**的检查命令 —— `uv run ruff format --check .`、`uv run ruff check .`、`uv run ty check src/`（不引入任何新工具）。
- `tests` 作业：`ubuntu-22.04` 与 `ubuntu-24.04` 矩阵，装 Node（测试套件的隐性依赖），`uv sync --locked` → 完整 `pytest` → **部署冒烟**（`install.sh --no-service` → `start.sh` → `/api/health` → `status.sh` → `stop.sh`）。
- `systemd-user-service` 作业：在 runner 具备用户级 systemd 时执行真实安装、`systemctl --user status`、健康检查、`uninstall.sh`，并断言卸载后用户数据仍在。
- 这些命令与上游 `ci.yml` 相同，使 Linux 工作流可独立作为发布前的质量闸门；新增价值在 22.04/24.04 矩阵与部署冒烟。

### Phase 7｜上游同步 — ✅ 固定分支人工维护

从 `linux/main` 建 `linux/sync-<sha>` 临时分支，合并 `upstream/main`，推送后运行 Linux CI，再通过 PR
回合；冲突人工处理。**绝不**直接合并或 push 到维护分支。

### Phase 8｜Release — ⏸ 暂不自动化

非默认分支上的 `schedule` / `workflow_run` 不会按预期触发，因此本分支不携带自动发布工作流。
需要发行时，从已通过 Linux CI 的 `linux/main` 手动打包并校验 `SHA256SUMS`。

### Phase 9｜文档 — ✅ 完成

`docs/linux/INSTALL.md`、`docs/linux/UPDATE.md`、README 的 Linux 章节（含 `Experimental` 支持矩阵与 Linux 数据目录）、`CHANGELOG.md` 的 Linux 条目。

### Phase 8.1｜轻量桌面启动器与可复现发行包 — ✅ 已实现，待 Linux CI 验证

- 安装用户级 Desktop Entry 与标准 256×256 hicolor 图标，不需要 root。
- `soda-prompt-hub open` 会启动或复用 Core、核对健康状态，并通过 `xdg-open` / `gio open` 打开工作台。
- headless CI 使用 `PROMPT_HUB_LAUNCHER_SKIP_OPEN=1` 验证完整启动链，不伪造图形桌面。
- `scripts/build_linux_release.py` 生成确定时间戳、固定 uid/gid 与规范权限的可复现源码 tar.gz。

### Phase 6 的真实验证（push 之后的 2026-09-14 晚）

`linux/main` 已推送到 `TPSROG/soda-prompt-hub`，GitHub Actions 首轮即暴露出两个问题，
修复后四个作业全绿。完整记录见审计 §12。

| 轮次 | ubuntu-22.04 | ubuntu-24.04 | lint | systemd | 处理 |
| --- | --- | --- | --- | --- | --- |
| ① `3989340` | ❌ 3 个 WebP 媒体类型失败 | ✅ | ✅ | ✅ | 新增 `media_type_for()`，4 个图片端点显式指定类型 |
| ② `89ab5df` | ❌ 1 个时间敏感用例 | ✅ | ❌（我漏跑 ruff） | ✅ | 时间戳改到执行时生成；修正全角标点并重排 |
| ③ `351d514` | ✅ | ✅ | ✅ | ✅ | **全绿** |

这两轮说明：**Phase 6 的价值不在于“多跑一遍测试”，而在于把静态审计看不见的行为差异暴露出来。**

### 待办

| 项目 | 说明 |
| --- | --- |
| 自动化调度 | 默认分支继续保持 `main`；如未来需要定时同步，应在 `main` 单独审查最小调度 workflow，并固定操作 `linux/main` |
| §28 上游更新验收 | 按固定分支的人工同步流程模拟一次上游提交并验收 |
| 上游 PR | ✅ 已提交：[#20](https://github.com/cOkieeman/soda-prompt-hub/pull/20)（WebP 媒体类型）与 [#21](https://github.com/cOkieeman/soda-prompt-hub/pull/21)（心跳用例时间戳），均从 `upstream/main` 拉出、各自只有一个提交、不含 Linux 部署内容；等待上游审核 |
| G1 / G2 / F1 / F2 | `usage_mode` 的 `linux_local` 语义、SMB 配对限制、数据集浏览的外接卷与快捷入口；可沿用“先修 + 反哺上游”的既有轨道 |
| Phase 10 | 干净 Ubuntu 上的完整验收已在 WSL2 与 GitHub runner 完成；如需真实 VPS，可在启用默认分支后重跑 |
