# Linux Compatibility Audit

Soda Prompt Hub Linux 适配审计报告（第一阶段交付物）。

> **文档位置说明**：上游 `tests/test_public_docs.py` 要求 `docs/*.md`（顶层）**恰好**是 12 个既有文件，
> 为不修改上游文档契约，Linux 相关文档统一放在 `docs/linux/` 子目录。与主任务书中的路径对应关系：
> `docs/LINUX_COMPATIBILITY_AUDIT.md` → `docs/linux/COMPATIBILITY_AUDIT.md`；
> `docs/LINUX_DEV_ENVIRONMENT.md` → `docs/linux/DEV_ENVIRONMENT.md`；
> `docs/LINUX_INSTALL.md` → `docs/linux/INSTALL.md`；
> `docs/LINUX_UPDATE.md` → `docs/linux/UPDATE.md`。

| 项目 | 值 |
| --- | --- |
| 上游仓库 | `https://github.com/cOkieeman/soda-prompt-hub` |
| 基线 commit | `e96249bc29b71cdf8efba52d232c368f5c466549`（`main`，2026-09-14 10:34 UTC） |
| 软件版本 | `1.1.1`（`pyproject.toml`） |
| 审计分支 | `linux/main`（基于 `upstream/main`） |
| 审计日期 | 2026-09-14 |
| 审计方式 | 只读静态分析（`git grep` 遍历 `upstream/main` 树），未修改任何上游文件 |
| 覆盖范围 | `src/`、`tests/`、`deploy/`、`scripts/`、`docs/`、`.github/` |

---

## 0. 结论摘要

1. **上游 Python 核心已在 Linux 上事实可用。** 官方 CI（`.github/workflows/ci.yml`）的 `quality` job 全程运行于 `ubuntu-latest`：`uv sync --locked` → `ruff format --check` → `ruff check` → `ty check src/` → `pytest` → `uv build`。`tests/` 共 498 个测试函数，其中只有 4 个 macOS 专属文件带 `skipif(darwin)`；Windows 相关测试断言的是打包脚本的文本与逻辑，在 Linux 上照常运行。
2. **Linux 适配的真实工作量集中在“部署层 + 流水线 + 文档”，而不是“改业务代码”。**
3. **核心代码只有 2 个真实缺口**，且都不阻塞“Linux Core 可启动”：
   - **G1｜使用模式没有 Linux 语义**：Linux 会被推断为 `mac_remote`（“Mac 管理 Windows”的远端模式）。
   - **G2｜SMB 双机配对仅 macOS**：Linux 上该能力不存在，应标注“暂不支持”，而不是伪造一条走不通的路径。
4. 其余工作全部是新增文件（`deploy/linux/`、`.github/workflows/linux.yml`、`docs/linux/*.md`、`CHANGELOG.md` 条目），**不触碰上游核心**，满足主任务书 §1/§16 对“diff 纯新增、可自动 rebase”的要求。

分类统计：

| 分类 | 条目数 | 说明 |
| --- | --- | --- |
| A 无需修改 | 12 | CLI、环境变量、路径、文件管理器、git 调用、模型下载、无 GPU 硬依赖等 |
| B 需要路径适配 | 1 | 默认资料库目录 `~/Documents/...` 不符合 Linux XDG 习惯 |
| C 需要替代命令 | 1 | SMB 挂载诊断固定调用 `/usr/bin/open`（macOS 专属） |
| D Linux 暂不支持 | 5 | Compute Worker、桌面宿主、SMB 双机、LoRA 训练、平台安装包 |
| E 建议抽象 | 0 | 不建议新增平台抽象层（见 §3） |

> 2026-09-14 **严格复核补充**：逐条重跑主任务书 §1.1 的全部关键词后，新增发现 **2 项 Linux 受限点**
> （分类属 C 类，见 §11）。上表为第一轮结论；复核结果不改变“核心无需修改即可运行”的判断。

> 2026-09-14 **CI 首轮实测补充**：在 Ubuntu 22.04 与 24.04 上跑完整套件后，发现并修复了
> **1 个真实缺陷**（WebP 媒体类型依赖系统 MIME 数据库，见 §12.1）与 **1 个测试缺陷**
> （心跳新鲜度用例时间敏感，见 §12.2）。§2 的“Linux 无需修改即可运行”结论仍然成立，
> 但这两项说明：**“能跑起来”与“行为正确”必须靠实机 CI 才能分开验证。**

---

## 1. 已兼容（A）

| # | 文件 / 位置 | 证据 | 说明 |
| --- | --- | --- | --- |
| A1 | `.github/workflows/ci.yml:16-49` | `runs-on: ubuntu-latest` + `uv sync --locked` + `ruff`/`ty`/`pytest`/`uv build` | **Linux 基线已存在**：核心、测试、构建全部在 Ubuntu 上通过 |
| A2 | `src/prompt_hub/cli.py:47-50, 110-111` | `serve --host` 默认 `127.0.0.1`、`--port` 默认 `8765`；`uvicorn.run("prompt_hub.api:app", ...)` | 满足主任务书 §8、§25（仅监听本机） |
| A3 | `src/prompt_hub/config.py:55-66` | `PROMPT_HUB_LIBRARY_ROOT` / `PROMPT_HUB_DATABASE` | 资料库位置可由环境变量覆盖，部署脚本可完全接管 |
| A4 | `src/prompt_hub/config.py:161-167` | `PROMPT_HUB_MODELS_ROOT` / `PROMPT_HUB_TAGGER_MODEL` | 模型目录可覆盖，无硬编码 |
| A5 | `src/prompt_hub/config.py:42-52` | `Path.home() / "Documents" / ...` 且带旧目录回退 | 使用 `pathlib`，无 `C:\`、无 `AppData`（见 B1 仅为默认值语义问题） |
| A6 | `src/prompt_hub/workspace_routes.py:744-757` | `darwin → /usr/bin/open -R`、`win32 → explorer.exe /select,`、`linux → xdg-open` | “打开所在文件夹”**已有 Linux 分支** |
| A7 | `src/prompt_hub/importers.py:615`、`maintenance.py:392`、`source_sync.py:196` | 均使用 `shutil.which("git")` | 无 `/usr/bin/git` 硬编码；历史 Windows 修复已被上游吸收，**不要重复实现** |
| A8 | `src/prompt_hub/model_connections.py:365-367` | `chmod(0o600)` 写入后设置权限 | 满足主任务书 §25（不明文保存 API Key、不用 `777`） |
| A9 | `src/prompt_hub/windows_worker_core.py:69-95` | `msvcrt` / `fcntl` 双实现文件锁 | Worker 的文件锁逻辑本身是跨平台写法 |
| A10 | `src/prompt_hub/wd14.py:132-140` | `auto` → 无 CoreML 时退回 `CPUExecutionProvider` | WD14 打标在 Linux 上可用（仅显式指定 `coreml` 才报错） |
| A11 | `src/prompt_hub/optional_models.py:181-241` | HuggingFace HTTPS 下载 + `sha256` 校验 + `revision` 收据 | 可选模型安装在 Linux 上平台无关 |
| A12 | 全 `src/` 扫描 | 无 `windll` / `kernel32` / `nvidia-smi` / `torch` / `cuda` 引用；无盘符硬编码 | 满足主任务书 §11：**没有 NVIDIA GPU 也不影响 Prompt Hub 启动** |

---

## 2. 必须修改 / 需要决策（B、C）

### G1｜使用模式（usage mode）没有 Linux 语义 — 严重度 Medium

| 项目 | 内容 |
| --- | --- |
| 文件 | `src/prompt_hub/web.py`、`src/prompt_hub/desktop_connection.py`、`src/prompt_hub/api.py` |
| 代码位置 | `web.py:53-57`、`web.py:72-85`、`desktop_connection.py:24-45`、`api.py:372-374` |
| 问题 | `render_index_html()` 在未显式传入时执行 `mode = "windows_local" if sys.platform == "win32" else "mac_remote"`；`connection_summary()` 中 `local = sys.platform == "win32"`。`api.py:374` 调用时**没有传 `usage_mode`**，因此 Linux 一律落入 `mac_remote`。 |
| 原因 | 使用模式是二元的（本机 / Mac 远程双机），用 `sys.platform` 推断，没有第三个取值；`web.py:55-57` 对未知取值直接 `raise ValueError`。 |
| 影响 | 不崩溃，但语义错误：Linux 用户看到的是“Mac 连接 …”文案、引导进入 SMB 配对（而 SMB 诊断是 macOS 专属，见 G2），示例路径也被替换成 `/Users/your-name/...`。 |
| 解决方案 | 方案 A（第一阶段，零核心改动）：接受 `mac_remote` 事实语义，在文档中如实说明 Linux Core 作为“资料库/创作/审核端”。方案 B（推荐长期）：向上游提 PR，把取值集合扩为 `{windows_local, mac_remote, linux_local}`，`sys.platform` 推断改为三分支，并把示例路径与文案补上 Linux 版本。方案 C：新增 `PROMPT_HUB_USAGE_MODE` 环境变量由部署层覆盖（仍需核心改动）。 |
| 是否影响 upstream merge | **影响**。`web.py` / `desktop_connection.py` 属于核心文件，本地长期携带 patch 会持续产生 rebase 冲突，建议走方案 B 反哺上游，合并后再 rebase。 |

### G2｜SMB 双机模式仅 macOS — 严重度 Low（归类为“暂不支持”）

| 项目 | 内容 |
| --- | --- |
| 文件 | `src/prompt_hub/remote_routes.py`、`src/prompt_hub/desktop_connection.py` |
| 代码位置 | `remote_routes.py:85`（`if sys.platform != "darwin": …`）、`remote_routes.py:99-100`（`["/usr/bin/open", destination]`）、`desktop_connection.py:149-160`（`smb://` 目标构造） |
| 问题 | 挂载诊断与“连接 Windows”的打开动作硬编码 macOS：非 darwin 直接返回不支持，且调用 `/usr/bin/open`。 |
| 原因 | 这是 Mac↔Windows 双机工作流的实现，未设计 Linux 侧对等能力（Linux 上对应的是 `gio mount` / `mount.cifs` + GVFS，需要桌面会话）。 |
| 影响 | Linux 无法进入“双机模式”；不影响 Linux Core 独立运行。 |
| 解决方案 | 第一阶段**明确标注 Linux 不支持 SMB 双机**，UI/文档不要暗示可配对；后续若需要，另立设计（HTTP Worker 协议或 `gio mount` 集成）。 |
| 是否影响 upstream merge | 不改代码则**无影响**。 |

### B1｜默认资料库目录不符合 Linux XDG 习惯 — 严重度 Low

| 项目 | 内容 |
| --- | --- |
| 文件 | `src/prompt_hub/config.py` |
| 代码位置 | `config.py:42-52` |
| 问题 | 默认值是 `~/Documents/Soda Prompt Hub/prompt-library`；Linux 上 `~/Documents` 可能不存在（由 xdg-user-dirs 创建，中文桌面下还可能显示为本地化名称），且 XDG 惯例是 `$XDG_DATA_HOME`。 |
| 原因 | 默认值面向 macOS / Windows 用户目录习惯设计。 |
| 影响 | 程序会自动 `mkdir(parents=True)`，因此**不会启动失败**；只是目录位置不符合 Linux 惯例，且在未装 xdg-user-dirs 的精简系统上会凭空创建 `~/Documents`。 |
| 解决方案 | 第一阶段**不改核心**：由 `deploy/linux/install.sh` 与 systemd unit 显式设置 `PROMPT_HUB_LIBRARY_ROOT` / `PROMPT_HUB_MODELS_ROOT`（默认建议 `~/.local/share/soda-prompt-hub`）。若要改核心默认值，需同时保住既有用户数据语义（`config.py` 中已有旧目录回退先例，可照此模式扩展），并写入 CHANGELOG。 |
| 是否影响 upstream merge | 不改核心则无影响；改核心则 Medium。 |

### B2｜模型目录内部的符号链接会被拒绝 — 严重度 Low-Medium

| 项目 | 内容 |
| --- | --- |
| 文件 | `src/prompt_hub/optional_models.py` |
| 代码位置 | `optional_models.py:131-140` |
| 问题 | `root()` 在 `models_root` 及其子目录路径上发现符号链接即抛 `VisualModelError("安装目录不能经过符号链接")`。Linux 上把大模型放到另一块盘再用符号链接接回来是常见做法。 |
| 原因 | 符号链接检查是安全设计（防止越出模型根目录）。 |
| 影响 | `models_root` 自身是符号链接时是安全的（先 `resolve()`，见 `:131`），但**`models_root` 内部子目录是符号链接**时会直接报错，属于 Linux 使用习惯上的真实摩擦点。 |
| 解决方案 | 第一阶段不改，文档中给出规避方式（把 `PROMPT_HUB_MODELS_ROOT` 直接指向真实目录，而不是在内部做软链）；若要放开，需向上游论证。 |
| 是否影响 upstream merge | 不改代码则无影响。 |

### C1｜平台显示标签 — 严重度 Trivial（仅外观）

| 项目 | 内容 |
| --- | --- |
| 文件 | `src/prompt_hub/optional_models.py` |
| 代码位置 | `optional_models.py:142-148` |
| 问题 | `host` 字段是 `Windows` / `Mac` / `platform.system()` 三选一，Linux 上会显示英文 `Linux`。 |
| 原因 | 二元标签设计。 |
| 影响 | 仅影响展示文案，不影响功能。 |
| 解决方案 | 可选：向上游 PR 补一个 `Linux` 分支；或第一阶段忽略。 |
| 是否影响 upstream merge | Low。 |

---

## 3. 建议抽象（E）

**结论：不建议为 Linux 适配新增 `src/prompt_hub/platform/` 抽象层。**

理由：

1. 上游已经把平台差异收敛到**极少的数据点**（`sys.platform` 判断 3 处 + `platform.system()` 1 处），没有散落的 `if Windows: …` 分支需要治理。
2. 上游迭代极快（`1.1.0` 于 2026-09-13、`1.1.1` 预发布于 2026-09-14，另有 `fix/windows-standalone-frontend`、`ui/unify-art-direction` 活跃分支与 18 个 PR）。**任何新增的中间层都会提高 rebase 成本**，与主任务书 §1/§4/§31 的“低维护成本”目标相冲突。
3. Linux 特有逻辑天然适合放在 `deploy/linux/` 与 `scripts/linux/`——它们是新增目录，不会与上游产生冲突。

因此：**先不抽象，等 Linux 侧真的出现第二处需要平台分支的核心逻辑时再评估**（符合主任务书“不要为了形式主义增加抽象层”）。

---

## 4. Windows-only（D，保持不动）

| 组件 | 位置 | 说明 |
| --- | --- | --- |
| Compute Worker（Python） | `src/prompt_hub/windows_worker.py`、`windows_worker_core.py`、`windows_worker_support.py`、`deploy/windows-worker/` | 核心代码**从不 import**（仅 worker 内部互相 import），因此不影响 Linux Core 启动 |
| Windows 桌面宿主 | `deploy/windows-desktop/`（C#：`DesktopHost.cs`、`GitRuntime.cs`、`ShellForm.cs`、`build.ps1`） | .NET/WinForms + WebView2，Linux 无等价物 |
| Compute Worker 外壳 | `deploy/windows-shell/`（C#：`SodaComputeWorker`、托盘、诊断包） | 同上 |
| 安装器 | `deploy/windows-installer/`（Inno Setup `desktop.iss` / `worker.iss`、`prepare-runtime.ps1`） | Windows 安装体系 |
| 桌面 UI 桥 | `deploy/desktop-ui/desktop.js`（15 处盘符引用）、`BRIDGE_CONTRACT.md` | 宿主注入的桥接 UI |
| 打包脚本 | `scripts/package_windows_desktop_release.py`、`package_windows_shell_release.py`、`stage_windows_*`、`build_windows_worker_release.py` | Windows 发行流水线 |
| 测试 | `tests/test_windows_*.py`、`tests/desktop-host-regression/`（C# 项目） | 在 Linux 上为文本/逻辑断言，可继续运行 |
| 功能 | LoRA 正式训练、CUDA/GPU 侧工作 | 依赖 Windows 训练工具链 |

**原则：不动、不删、不重构。** Linux 第一步不提供对等实现。

---

## 5. macOS-only

| 组件 | 位置 | 说明 |
| --- | --- | --- |
| 启动器脚本 | `deploy/mac/*.command`（首次安装 / 启动 / 停止 / 更新 / 诊断） | 5 个 `.command` |
| 便携启动器 | `deploy/mac/portable-launcher/`（Swift + zsh） | 含 `run-server.zsh` |
| SMB 配对诊断 | `src/prompt_hub/remote_routes.py:85-105`、`desktop_connection.py:149-160` | 见 G2 |
| 打包脚本 | `scripts/build_mac_commercial_release.py`、`build_mac_portable_launcher.py` | 含 `.dmg` 与 `/usr/bin/...` 调用 |
| 测试 | `tests/test_mac_*.py`、`test_desktop_icon_signing.py` | 已带 `skipif(sys.platform != "darwin")`，Linux 上自动跳过 |

---

## 6. Linux 暂不支持（明确标注）

| 能力 | 状态 | 原因 | 处理方式 |
| --- | --- | --- | --- |
| 数据集工作区目录浏览的“外接卷” | **受限** | `browse_roots()` 只认 `$HOME` 与 macOS 的 `/Volumes`，Linux 上的 `/media`、`/mnt` 不在浏览范围内（见 §11 F1） | 需要时把资料放进主目录或用符号链接接入；修法建议走上游 PR |
| 主目录快捷入口（桌面 / 图片 / 下载） | **受限** | 固定英文目录名，中文等其他 locale 的 Linux 上不显示；有 `is_dir()` 保护，不会报错（见 §11 F2） | 低优先，可与 locale 适配一起反哺上游 |
| Compute Worker（ComfyUI 执行端） | **暂不支持** | Worker 是 Windows 实体（GUI/托盘/`.bat`/`.ps1`/本机服务管理） | 标注 `Linux unsupported / future work`；未来需另立设计（HTTP/WebSocket 协议 + CLI daemon） |
| SMB 双机配对 | **暂不支持** | 见 G2，实现硬编码 macOS + GVFS 桌面会话 | 标注不支持，不提供入口 |
| LoRA 正式训练 | **暂不支持** | 上游本身也在 Windows 训练工具中完成 | 标注不支持 |
| 桌面宿主（托盘/启动器 GUI） | **暂不支持** | 上游宿主为 C#/WinForms 与 Swift | 第一版用 `systemd --user` + 浏览器访问 `127.0.0.1:8765` |
| 平台安装包（`.deb` / `.rpm` / AppImage / Snap / Flatpak） | **暂缓** | 主任务书 §18 明确排除 | 第一阶段只出 `tar.gz` + `SHA256SUMS` |
| Docker | **暂缓** | 主任务书 §19 明确排除 | 第二阶段再评估 |

---

## 7. 潜在风险

| # | 风险 | 等级 | 缓解 |
| --- | --- | --- | --- |
| R1 | 上游更新频率极高（每日多次提交、频繁 PR / Pre-release） | High | Linux 侧改动**只新增文件、不改核心**；唯一核心改动（G1）走上游 PR 而非长期携带 |
| R2 | 验证环境与真实 Ubuntu 存在差异（WSL2 的 systemd user、无桌面会话导致 `xdg-open` 不可用、`/mnt/*` 性能与权限） | Medium | `check-env.sh` 显式报告差异；CI 用真实 `ubuntu-latest` 交叉验证；文档标注 WSL2 的局限 |
| R3 | 上游 CI 只保证“测试与构建通过”，不保证“用户级部署行为”（systemd、`install.sh`、linger） | Medium | Linux 专属 CI 增加部署冒烟作业（上游没有的部分） |
| R4 | 数据目录语义被无意改变（主任务书 §24 明令禁止） | High | Linux 端只通过环境变量注入路径，绝不改数据库 schema / 资料库格式 / hash 规则 |
| R5 | 用户把 Linux 版误当成“官方全功能版” | Medium | README 标注 `Linux support: Experimental`，明确列出支持/不支持矩阵（主任务书 §20） |
| R6 | 本机 C 盘仅剩约 9.6 GB，WSL 发行版默认落在 C 盘 | Medium | 发行版安装后迁移到 D 盘；`install.sh` 不往 C 盘写大文件 |
| R7 | fork `main` 与上游历史分叉（落后 91 个 commit，另有 1 个游离 commit） | Low | Linux 工作基于 `upstream/main` 独立分支；fork 主线清理另行决定 |
| R8 | 许可证与署名（上游为 MIT，另有商业化打包脚本） | Low | 保留 `LICENSE` 与来源说明；Linux 构建标注“非官方构建” |

---

## 8. 推荐实施顺序

映射主任务书 Phase 2–10：

| 阶段 | 内容 | 是否触碰核心 |
| --- | --- | --- |
| Phase 2 | Linux compatibility design（本文档 + Implementation Plan） | 否 |
| Phase 3 | Linux native runtime：在 WSL2 Ubuntu 实跑 `uv sync` / `pytest` / `serve` | 否 |
| Phase 4 | Linux 部署：`deploy/linux/{install,uninstall,update,start,stop,status}.sh` + `soda-prompt-hub.service` | 否 |
| Phase 5 | Linux 测试：`tests/linux/`（启动、数据目录、路径、UTF-8/空格/中文、API） | 否 |
| Phase 6 | Linux CI：`.github/workflows/linux.yml`（补充上游没有的部署冒烟与 22.04/24.04 矩阵） | 否 |
| Phase 7 | 上游同步：固定 `linux/main`，临时同步分支经 PR 回合 | 否 |
| Phase 8 | Release：暂不自动化，按需从通过 CI 的 `linux/main` 手动打包 | 否 |
| Phase 9 | 文档：`docs/linux/INSTALL.md`、`docs/linux/UPDATE.md`、`docs/linux/DEV_ENVIRONMENT.md`、README / CHANGELOG | 否 |
| Phase 10 | 最终验收（主任务书 §27/§29） | 否 |
| 独立轨道 | G1 反哺上游 PR（`linux_local` 使用模式） | **是** |

---

## 9. 与验收标准对照（主任务书 §27 / §29）

| 验收问题 | 当前答案（基于本次审计） | 验证方式 |
| --- | --- | --- |
| 1. Linux 核心是否可以独立运行？ | 预期可以（上游 CI 已在 Ubuntu 跑通测试与构建） | Phase 3 实机 `uv run --no-sync prompt-hub serve` |
| 2. 是否需要修改核心 Python 代码？ | **不需要即可运行**；建议仅修 G1（使用模式）以修正语义 | Phase 3 实机验证 |
| 3. Windows / macOS 是否受影响？ | 不受影响（Linux 侧全部为新增文件） | 全量 `pytest` + 上游 CI 对照 |
| 4. Linux Worker 是否已实现？ | **否**（Windows-only） | 文档标注 |
| 5. 哪些功能仍 Windows-only？ | Compute Worker、桌面宿主、LoRA 训练、SMB 双机的 Windows 侧 | 见 §4 |
| 6. 是否可以通过 systemd 运行？ | 待实现（`deploy/linux/`），WSL2 可验证 `systemctl --user` | Phase 4/5 |
| 7. 是否可以安全更新？ | 待实现（`update.sh` 不动用户数据） | Phase 4 |
| 8–10. 上游更新后多久发现 / 能否自动 CI / 自动 Release？ | 按需人工发现与同步；分支 push/PR 自动 CI；Release 暂不自动化 | Phase 7/8 |
| 11. 用户数据是否与程序更新完全分离？ | 是（程序在仓库/安装目录，数据由 `PROMPT_HUB_LIBRARY_ROOT` 指向） | Phase 4 验收 |
| 12. 是否存在需要人工处理的 merge conflict？ | 预期不存在（纯新增 diff） | Phase 7 模拟上游提交 |
| 13. 是否存在无法自动 rebase 的 Linux patch？ | 只有 G1 属于核心改动，若上游未接受则需人工处理 | Phase 7 |

---

## 10. Linux 实测结果（WSL2 首轮，2026-09-14）

环境：WSL2 + Ubuntu 24.04.5 LTS，x86_64，Python 3.12.3，uv 0.12.13。
详细环境记录见 `docs/linux/DEV_ENVIRONMENT.md`。

### 10.1 上游基线：测试与构建

| 项目 | 结果 |
| --- | --- |
| `uv sync --locked` | 成功，约 10.6 秒（约 50 个包），`uv.lock` 无改动 |
| `pytest` | **543 passed, 9 skipped, 0 failed**，覆盖率 **83.41%**（门槛 80%），约 126 秒 |
| 跳过项 | 9 个，全部为 macOS 专属 |
| 结论 | 上游核心在 Linux 上**开箱可用**，无需任何核心代码修改 |

> 上表是**未做任何修复**时的首轮基线，用于回答“上游核心能否开箱运行”。
> 加入 `tests/linux` 与两处修复后的最终状态为 **577 passed / 9 skipped**，
> 且 GitHub Actions 四个作业全绿；两处修复的来龙去脉见 §12。

### 10.2 新发现：测试套件隐性依赖 Node.js（E 类，建议反哺上游）

| 项目 | 内容 |
| --- | --- |
| 位置 | `tests/test_pairing_guide.py:26` |
| 问题 | 该测试直接 `assert shutil.which("node")`，**缺少 Node 时是失败而不是跳过**；另有 12 个 Node 相关测试用 `skipif` 跳过 |
| 原因 | GitHub `ubuntu-latest` runner 预装 Node，上游 CI 因此看不到这个问题 |
| 影响 | 任何没有 Node 的 Linux 环境（含最小化服务器、CI 镜像、自托管 runner）会看到 1 个红色失败 + 12 个跳过；13 个 UI 行为测试失去覆盖 |
| 解决方案 | 第一阶段：本地与 Linux CI 显式安装 Node.js（已验证：安装后 543 通过 / 9 跳过）；长期：建议向上游提 PR，把该断言改为 `pytest.mark.skipif` 或 `pytest.importorskip("node")` |
| 是否影响 upstream merge | 不影响（仅建议上游修改；本地 CI 自行安装 Node 即可） |

### 10.3 服务与路径实测

| 场景 | 结果 |
| --- | --- |
| 默认配置（不设环境变量） | `GET /` = 200；`/api/health` = `status: ok`；`/api/stats` 正常；监听 `127.0.0.1:8765`（未暴露 `0.0.0.0`） |
| 中文 + 空格 + UTF-8 路径（`~/资料库 测试/Soda Prompt Hub`） | `prompt-hub init` 成功建库；服务启动正常；`/api/health` 返回该路径；SQLite 文件正常生成 |
| 资料库根目录为符号链接（`~/linked-library` → `~/real-library-target`） | 服务启动正常，`/api/health` 正常 |
| 默认目录行为 | 确认会在 Linux 上创建 `~/Documents/Soda Prompt Hub/prompt-library`，印证 B1（非 XDG） |

### 10.4 systemd（WSL2）

| 项目 | 结果 |
| --- | --- |
| PID 1 | systemd 255 |
| `systemctl is-system-running` | `running` |
| `systemctl --user` | 可用（`XDG_RUNTIME_DIR=/run/user/1000`） |
| `journalctl --user` | 可用 |
| `loginctl show-user voldm -p Linger` | **`Linger=no`** |
| 影响 | 后续 `deploy/linux` 的 systemd **user** service 在会话结束后会停止；若要常驻需 `loginctl enable-linger`（按主任务书 §7，只作为可选步骤，不默认开启） |

### 10.5 WSL2 环境侧注意（不属于项目代码问题）

| 项目 | 说明 |
| --- | --- |
| 代理 | `wsl.exe` 提示 Windows 侧 localhost 代理未镜像到 WSL（NAT 模式限制）；实测 WSL 内直连可用 |
| 下载源 | `releases.astral.sh` 约 3 KB/s 不可用（uv 改用 pipx + PyPI 镜像安装）；Ubuntu 源与 PyPI 均正常 |
| Node.js | 见 10.2，必须安装 |
| `xdg-open` | 未安装，无桌面会话；“打开所在文件夹”会走失败分支（可用于验证可读错误，但无法验证图形打开） |

---

## 11. 复核补充发现（2026-09-14 严格复核）

复核方式：逐条重跑主任务书 §1.1 的全部关键词，并对照 §12 的测试清单逐项核对用例覆盖。

### 11.1 关键词覆盖闭环

| 关键词 | 命中情况 | 结论 |
| --- | --- | --- |
| `platform.machine()` | 0 | 无依赖机器架构的分支 |
| UNC 路径 `\\host\share` | 0 | `src/` 中无 UNC 硬编码 |
| `cmd.exe` | 0 | 无 `cmd` 调用 |
| `.exe` | 仅 `explorer.exe`（`workspace_routes.py:748`，Windows 分支） | 已归类，无需处理 |
| `.bat` | 仅 `tests/` 中 Windows 打包测试的断言 | 不影响 Linux |
| `Desktop` | 1 处实质命中（`dataset_workspace.py:38`） | → F2 |
| `Finder` / `/Volumes` / `osascript` | `remote_web.py`、`pairing_web.py`、`dataset_workspace.py` | 归入 G2 与 F1 |

### 11.2 F1｜数据集目录浏览不覆盖 Linux 外接卷（Medium）

| 项目 | 内容 |
| --- | --- |
| 位置 | `src/prompt_hub/dataset_workspace.py:615-630`（`browse_roots()`） |
| 问题 | 浏览根 = `$HOME` 加上“若 `/Volumes` 存在则枚举其子目录”（macOS 惯例）。Linux 的 `/media/$USER`、`/run/media/$USER`、`/mnt/*` 都不在范围内。 |
| 影响 | 数据集导入/浏览只能看到主目录；素材放在挂载盘的用户会“看不到盘”。**不会崩溃**：越界时返回可读错误“目录浏览范围仅限于个人主目录和已挂载的外接卷”。 |
| 方案 | 第一阶段零改动，文档说明可把资料放进主目录或用符号链接接入；长期建议向上游 PR 增加 XDG 挂载点扫描。 |
| 是否影响 upstream merge | 不改代码则无影响。 |

### 11.3 F2｜主目录快捷入口仅识别英文目录名（Low）

| 项目 | 内容 |
| --- | --- |
| 位置 | `src/prompt_hub/dataset_workspace.py:38`（`BROWSE_HOME_SHORTCUTS = Desktop / Pictures / Downloads`） |
| 问题 | 快捷入口固定英文目录名；中文等 locale 的 Linux（`~/桌面`、`~/图片`、`~/下载` 或 xdg-user-dirs 自定义）不会出现这些入口。 |
| 影响 | 仅体验问题：逐项 `is_dir()` 判断，目录不存在就直接跳过，不会报错。 |
| 方案 | 低优先；若要修，建议读取 XDG `user-dirs.dirs` 并反哺上游。 |

### 11.4 结论

两项都属于“Linux 使用受限”，不影响第一阶段“可运行 / 可部署 / 可更新”的结论，
也不改变 §0 中“核心无需修改即可运行”的判断。

---

## 12. CI 首轮实测发现并已修复的缺陷（2026-09-14）

静态审计只能回答“能不能跑”，下面的问题只有在真实 Ubuntu 上跑完整套件才会暴露。
两项都已在本分支修复并各自补了回归测试，另外各自作为一个独立提交提给上游
（[#20](https://github.com/cOkieeman/soda-prompt-hub/pull/20)、
[#21](https://github.com/cOkieeman/soda-prompt-hub/pull/21)，均不含任何 Linux 部署内容）。

### 12.1 WebP 媒体类型依赖系统 MIME 数据库（真实缺陷，已修复）

| 项目 | 内容 |
| --- | --- |
| 位置 | `src/prompt_hub/api.py:822`、`api.py:901`、`source_routes.py:124`、`workspace_routes.py:674` |
| 现象 | Ubuntu 22.04 上，资料库来源缩略图与创作项目结果图返回 `Content-Type: application/octet-stream`，浏览器不内联显示（测试断言 `'application/octet-stream' == 'image/webp'` 失败） |
| 原因 | 这些 `FileResponse(path)` 没有显式 `media_type`，Starlette 于是调用 `mimetypes.guess_type()`。**CPython 内置 MIME 表不含 `.webp`**（实测：纯内置表返回 `(None, None)`，`.jpg` 正常），该映射只能来自系统 `/etc/mime.types`：Ubuntu 24.04 有，22.04 没有 |
| 影响面 | 任何 `/etc/mime.types` 不完整的 Linux（22.04 LTS、最小化容器、服务器镜像）；与平台无关，Windows 上属同类隐患 |
| 修复 | 新增 `prompt_hub.media.media_type_for(path)`：对项目自己产出的图片格式（webp/png/jpg/jpeg/gif/avif/bmp/tif/tiff）给出确定类型，其余后缀仍交给 `mimetypes`，未识别回退 `application/octet-stream`；应用到上述 4 个端点 |
| 回归测试 | `tests/test_media_types.py`：把 `mimetypes.guess_type` 打桩成永远返回 `None`，断言各格式仍返回正确类型 |
| 复现证据 | 在 WSL 中隐藏 `/etc/mime.types`：修复前 3 个测试失败，修复后同一条件下 64 个相关测试全部通过（系统文件已还原） |
| 分类 | 属 §2「必须修改」类；本分支已修，另可作为上游 PR |

### 12.2 心跳新鲜度用例时间敏感（测试缺陷，已修复）

| 项目 | 内容 |
| --- | --- |
| 位置 | `tests/test_desktop_connection.py::test_connection_only_reports_fresh_live_worker` |
| 现象 | 偶发失败：`assert 'connected' == 'stale'`。同一提交在 ubuntu-24.04 通过、在较慢的 ubuntu-22.04（整轮 223 秒）失败 |
| 原因 | 参数表在**收集阶段**计算 `datetime.now(UTC) + 2 分钟`，而 `connection_summary()` 判定 stale 的条件是 `age < -15s` 或 `age > 25s`。用例若在收集后 **105～145 秒**之间执行，`age` 落进 `-15～+25 秒` 窗口，于是期望 stale 得到 connected |
| 实证 | 直接构造心跳测判定窗口：未来 10 秒→`connected`、未来 30 秒→`stale`、过去 30 秒→`stale` |
| 修复 | “未来 2 分钟”的时间戳改到用例内部生成（参数表用哨兵值占位），与判定使用同一时刻的时钟 |
| 分类 | 与平台无关的测试稳定性问题；本分支已修，可另行反哺上游 |

### 12.3 修复后的最终状态

| 项目 | 值 |
| --- | --- |
| 完整套件（WSL2 Ubuntu 24.04） | **577 passed / 9 skipped / 0 failed** |
| GitHub Actions（`linux/main`） | 4 个作业全绿：格式/Lint/类型检查、Tests on ubuntu-22.04、Tests on ubuntu-24.04、systemd 用户服务 |
| 结论 | 第一阶段“可运行 / 可部署 / 可更新”的验收不受影响；上述两项属额外发现，均已闭环 |

---

## 13. 后续修复情况（2026-09-15）

| 编号 | 问题 | 状态 |
| --- | --- | --- |
| G1 | 使用模式只有 `windows_local` / `mac_remote`，Linux 落入 macOS 远端语义 | ✅ 已修复：新增 `linux_local`（`src/prompt_hub/usage_modes.py`，commit `4c28d3f`） |
| G2 | Linux 侧需要 SMB 语义才能与计算端协作 | ✅ 已解决：Core 与 Worker 走本地桥接目录，`install.sh --with-worker` 自动登记本机节点；配对入口在本机模式下隐藏 |
| — | `comfyui_url` 被限制为本机 http，且 HTTP 客户端不带认证 | ✅ 已修复：支持任意 `http(s)` 主机与 URL 内嵌 Basic 认证（commit `0af44d5`） |
| F1 | 数据集目录浏览不含 Linux 外接卷（`/media`、`/mnt`） | ⬜ 未修复（可用符号链接规避） |
| F2 | 主目录快捷入口仅识别英文目录名 | ⬜ 未修复 |

Linux Compute Worker 已用真实 ComfyUI 端到端出图验证，详见 `docs/linux/WORKER.md`。

---

## 附录 A：复现本次审计的命令

```bash
git fetch upstream
git switch -c linux/main upstream/main

# 平台判断 / Windows 目录 / 盘符 / 外壳
git grep -nIE "sys\.platform|platform\.system|os\.name|winreg|WindowsError|pywin32" upstream/main -- src tests
git grep -nIE "USERPROFILE|LOCALAPPDATA|APPDATA|PROGRAMDATA|AppData" upstream/main -- src tests
git grep -nIE "[A-Za-z]:\\\\" upstream/main -- src tests
git grep -nIE "powershell|pwsh|cmd\.exe" upstream/main -- src tests

# macOS / SMB / 文件管理器 / 可执行文件
git grep -nIE "osascript|/Volumes|\.dmg|darwin" upstream/main -- src tests
git grep -nIE "smb://|SMB|cifs|mount" upstream/main -- src tests
git grep -nIE "xdg-open|explorer\.exe|startfile" upstream/main -- src
git grep -nIE "shutil\.which|/usr/bin/" upstream/main -- src

# 子进程 / 权限 / GPU
git grep -nIE "subprocess\.(run|Popen|check_output|call)" upstream/main -- src
git grep -nIE "chmod|is_symlink" upstream/main -- src
git grep -nIE "nvidia-smi|torch|cuda|rocm" upstream/main -- src

# 测试规模与平台跳过
git grep -h -E "^\s*def test_" upstream/main -- tests | wc -l
git grep -nE "pytest\.mark\.skipif" upstream/main -- tests
```

## 附录 B：验证状态清单

### 已在 WSL2 Ubuntu 24.04 实测（2026-09-14）

| # | 项目 | 状态 |
| --- | --- | --- |
| 1 | `uv sync --locked` 依赖安装与 `uv.lock` 无改动 | ✅ 已验证，见 §10.1 |
| 2 | `pytest` 通过/跳过/失败明细 | ✅ 已验证：543 / 9 / 0，见 §10.1 |
| 3 | `prompt-hub serve` 与 `GET /`、`/api/health`、`/api/stats` | ✅ 已验证，见 §10.3 |
| 4 | 中文 / 空格 / UTF-8 路径与符号链接路径 | ✅ 已验证，见 §10.3 |
| 5 | 默认资料库目录的实际落点 | ✅ 已验证，见 §10.3（印证 B1） |
| 6 | `systemctl --user`、`journalctl --user`、`Linger` 状态 | ✅ 已验证，见 §10.4 |

### 仍需验证（属于后续阶段）

| # | 项目 | 计划阶段 |
| --- | --- | --- |
| 7 | `xdg-open` 在无桌面会话时的失败路径是否返回可读错误而不是崩溃 | Phase 4/5（需要安装 `xdg-utils` 或模拟缺失） |
| 8 | `deploy/linux/*.sh` 与 systemd unit 的幂等性、重启策略、日志进入 journald | Phase 4/5 |
| 9 | `install.sh` / `update.sh` 的幂等性与“更新不动用户数据”的实证 | Phase 4/10 |
| 10 | 缩略图生成、导入流程在真实资料库数据量下的表现 | Phase 5（需要真实资料库） |
| 11 | GPU / ComfyUI Worker 路径 | 不在第一阶段范围（Linux Worker 暂不支持） |
