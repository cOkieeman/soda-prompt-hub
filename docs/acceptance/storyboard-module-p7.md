# P7 分镜模块接入报告

本次接入只修改 Hub。没有提交、切分支、推送、创建 PR，也没有修改核心库或节点包；所有出图验收使用假 Worker，未向真实 ComfyUI 投递。

## 结果与边界

Hub 主导航新增“分镜”，提供项目、页面、草稿缩略图、OC 角色卡、AI 拆格、翻译确认、校验、编译、编辑器、Worker 投递、结果回收选图、导入和按页导出。原有界面继续沿用现有布局和 token。

`soda_storyboard` 固定为 0.4.1 的 Release wheel URL。项目模型、导入解释、版式几何、校验、服装词汇检查、翻译清单及应用、MOSS 编译、工作流图、分镜包、布局预览和编辑器均调用核心库。Hub 负责资料目录、索引、路径和资源边界、模型连接、OC 映射、确认事务、Worker 与复盘接线。

离线测试环境从只读的 `v0.4.1` tag（`55862c1`，包含 F8）提取临时副本并构建 wheel，安装到 Hub `.venv`。没有使用本地 main 的 0.4.2，也没有使用 F7 目录中较早的同版本待发布产物。`uv.lock` 中的 SHA256 来自该 tag 的离线构建；由于无外网，本轮未独立核对 GitHub 附件的字节哈希。联网环境应核对 Release 附件，并在必要时刷新这一直接依赖的锁记录。

完整操作说明见 [USER_GUIDE 的分镜模块](../../USER_GUIDE.md#分镜模块)；格式及编辑器文档链接到核心库，不在 Hub 复制实现。

## 架构、存储与进程

所有服务在 `api.create_app()` 创建一次并注入 `create_storyboard_router()`；lifespan 初始化 Store，正常退出时关闭托管编辑器。

```text
<library_root>/storyboards/
  index.json                   # soda-storyboard-hub-index-v1
  projects/<project-id>/        # 原样核心项目目录
    project.json
    characters/*.json
    pages/*.json
    pages/<page-id>/renders/    # Worker 图像登记后的生产文件
    exports/
  generation-runs/*.json        # soda-storyboard-generation-v1
  locks/<project-id>.lock       # 跨进程事务锁，不放进核心项目
  trash/                       # 已删除项目
  previews/                    # 临时布局缩略图，返回后移除
```

删除页面会进入所属核心项目的 `.trash/`，删除项目会整体移入 Hub 的 `storyboards/trash/`，不会删除原始导入文件。核心分镜包按页定义，因此多页项目逐页导出，未发明新的整项目包格式。

AI 方案只在有界内存预览缓存中保留，最多 64 项、有效期一小时；重启后需重新生成。确认请求只能引用服务端预览 ID。确认前核对项目、角色资料及页面版本，AI 拆格仅写空白页；已有页面另建一页保留。翻译只应用核心待办清单中的项，不覆盖新鲜译文或手动覆盖内容。

每个项目最多启动一个 Hub 托管编辑器。使用核心 `edit` 的端口和健康检查能力、wheel 内的 `Server/Store` 及静态资源；Hub 子进程适配器增加路径、画布、同源请求和事务边界，将编辑器直接生成请求引导回 Hub Worker。仅绑定 `127.0.0.1`，自动分配空闲端口，核对项目与实例身份后复用或停止。Windows 后台进程不弹终端窗口。健康检查暂不可达时保留自己持有的进程句柄，不覆盖成第二个实例；退出仅回收自己持有的进程。

Hub 与托管编辑器共享可重入的项目文件锁：Windows 使用 `msvcrt`，POSIX 使用 `flock`。预览版本检查到最终写入在同一临界区，避免编辑器刚保存的人工内容被 Hub 覆盖。锁竞争超时为 15 秒。外部 CLI、插件或独立核心编辑器不会遵守此 Hub 侧锁，仍需避免同时写同一项目。

固定 0.4.1 没有 F9 production 路径公开接口，Hub 先检查项目内相对路径、链接、导入文档和画布资源上限；若未来核心提供路径检查模块，则复用它。没有改写核心编译或布局算法。

## Worker、复盘和选图

默认调用核心 `minimal_graph`。可选 Soda-MOSS-v2 使用新规则 `moss-soda-v2`，调用核心 `v2_graph` 适配用户导入的 API 图；界面提供工作流文件登记及明确的替换选项。登记工作流不会投递任务。

映射保持为 JSON 620、尺寸 150、种子 84、存图 81、负面 75、模型子图 135、采样子图 148；要求导出 API 前切到“JSON 直通”。整页 LoRA 由核心 `select_lora` 遵循项目策略和页面选择，Hub 不重新实现选择算法。

任务复用 `RemoteNodeStore` 的 `comfyui_generate`，没有修改 Worker 协议或发行单文件。回传先校验任务归属、相对路径、大小及哈希，再导入 `ComfyResultStore`。最近任务可在刷新浏览器后恢复。

核心没有 `register_render`，因此 Hub 使用一处兼容接线，按核心 `production.renders` 格式登记已验证的外部结果。人工选图再调用核心 `pick_render`，同时更新 Hub 复盘状态。不会因 AI 建议自动选图。原始结果保留在 Hub 复盘库，核心生产目录中的图按核心画布处理能力规范化。

## 新路由与页面

页面为现有单页应用中的“分镜”导航，不复制核心编辑器。以下路径均以前缀 `/api/storyboard` 开始；`P=/projects/{project_id}`，`S=P/pages/{page_id}`。

| 方法与路径 | 用途 |
| --- | --- |
| `GET/POST /projects`、`GET/DELETE P` | 项目列表、新建、读取和回收站删除 |
| `GET/POST P/pages`、`GET/PUT/DELETE S` | 页面列表、新建、读取、版本化保存和删除 |
| `GET S/preview.png` | 核心布局缩略图 |
| `POST /import`、`POST P/import` | 新项目或当前项目导入包、分镜单、Markdown、frame 数组和 MOSS JSON |
| `GET P/export?page_id=...` | 核心分镜包下载 |
| `POST S/validate`、`POST S/compile` | 核心校验和 MOSS 编译 |
| `GET/POST S/translations/todo` | 核心翻译清单 |
| `POST S/ai/preview`、`POST S/ai/apply` | 拆格和版式预览、确认 |
| `POST S/translations/preview`、`POST S/translations/apply` | AI 译文预览、确认或人工清单应用 |
| `POST P/characters/preview`、`POST P/characters/apply` | OC 中英文角色卡预览和确认 |
| `POST S/editor/start`、`POST S/editor/stop` | 托管核心编辑器 |
| `POST S/generate` | Worker 投递 |
| `GET S/results`、`POST S/results/refresh`、`POST S/results/pick` | 候选、回收和选图 |

复用原有 `POST /api/workflow-profiles/moss-soda-v2/import` 登记 API 工作流。原有通用创作投递入口对这个新模型族给出明确提示，避免误走旧的提示词编译路径；旧规则行为保留。

## 改动清单与建议提交分组

1. **依赖、项目与编辑器**：`pyproject.toml`、`uv.lock`、`storyboard.py`、`storyboard_safety.py`、`storyboard_lock.py`、`storyboard_editor.py`、`storyboard_editor_server.py`；随组加入 Store、编辑器、锁测试及 pudding fixture 的 LICENSE/NOTICE。
2. **AI、OC、HTTP 装配**：`storyboard_ai.py`、`storyboard_routes.py`、`api.py` 和 HTTP 测试。装配点引用第三组的生成服务，若要求每次提交独立可运行，应将第二、三组合并提交。
3. **Worker 与 MOSS 规则**：`storyboard_generation.py`、`workflow_profiles.py`、`workflow_routes.py` 及生成集成测试。
4. **页面与文档**：`storyboard_web.py`、`web_assets/storyboard.js/css`、导航装配的 `web.py/base.js/index.html`、Web 测试、`USER_GUIDE.md`、`CHANGELOG.md` 和本报告。

这些是验收方的建议提交范围；本轮没有执行任何 git 写操作。

## 验证命令与结果

离线运行使用已安装的 `.venv`，避免 `uv run` 重新同步网络依赖。PowerShell 下先设置 `$env:PYTHONUTF8='1'`；测试临时目录放 `.venv`，避免默认系统 TEMP 权限限制和原有文档扫描误扫测试生成的 Markdown。

```powershell
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/ruff.exe check .
.venv/Scripts/ty.exe check src/
uv lock --check --offline --cache-dir .venv/.p7-state/uv-cache
node --check src/prompt_hub/web_assets/base.js
node --check src/prompt_hub/web_assets/storyboard.js
.venv/Scripts/python.exe -m pytest tests/test_storyboard_store.py tests/test_storyboard_editor.py tests/test_storyboard_lock.py tests/test_storyboard_generation.py tests/test_storyboard_routes.py tests/test_storyboard_web.py --no-cov --basetemp .venv/.p7-storyboard-check -o cache_dir=.venv/.p7-pytest-cache
.venv/Scripts/python.exe -m pytest --basetemp .venv/.p7-full-check -o cache_dir=.venv/.p7-pytest-cache
```

| 检查 | 结果 |
| --- | --- |
| Ruff format / check、ty、`git diff --check` | 通过；251 个 Python 文件格式检查通过 |
| `uv lock --check --offline` | 通过，52 个包；URL 固定为 0.4.1 |
| 两个 JS 文件的 `node --check` | 通过 |
| 新增分镜测试 | **94 passed**，9.00 秒 |
| 原有工作流测试 | 18 passed；与生成测试共 48 passed |
| pudding HTTP 导入→校验→编译→导出→核心读回 | 通过，页/角色/项目设置一致 |
| Hub wheel 构建及内容检查 | 通过，新模块、JS/CSS 与固定核心 URL 均在 wheel 中 |
| 真正启动核心编辑器子进程 | 启动、wheel UI、实例复用、停止和端口关闭均通过 |
| 完整 pytest，1065 项 | **1005 passed、32 skipped、28 failed**，259.30 秒 |
| 完整测试覆盖率 | **85.45%**，高于 80% 门槛 |

完整回归的 28 项失败中，27 项已在未修改的 HEAD 临时副本中逐项复现。另 1 项是本报告最初放在 `docs/` 根目录触发既有文档白名单；已移至 `docs/acceptance/`，相关文档测试复测 **3 passed**。完整回归保留原始计数，没有把补测结果伪装成一次全绿运行。当前仍不能满足“原有测试全部通过”的完成标准。

本机原始日志保存在忽略目录 `.planning/pytest-final-rerun.log`、`.planning/pytest-baseline-failures.log`；临时库、浏览器数据、截图、wheel 和原始 HEAD 副本均在 `.venv/.p7-*`，不进入建议提交范围。

`examples/pudding` 的项目、页和角色 JSON 以保留 LICENSE/NOTICE 的测试 fixture 提供；测试先复制到临时目录，再经核心导出、Hub HTTP 导入、校验、编译、Hub 导出、核心 `load_bundle` 读回，逐项比较页、角色与项目设置。原示例目录没有被写入。

本机 Chrome 的隔离浏览器冒烟已通过并独立复验：项目/页面管理、OC 资源、API 工作流登记及明确替换、登记不投递、OC 确认、AI 多版式及译文确认、编译、假 Worker 投递/刷新恢复/回收/选图、假编辑器新窗口、下载和导入、页面回收站；桌面及 390px 手机宽度无横向溢出，零 JS 异常。截图已检查，隔离假服务已停止。浏览器任务中的模型、Worker、编辑器入口均为假实现；真实核心编辑器另有 loopback HTTP 测试和实际子进程启停冒烟。

## 待用户确认的决定

- 使用当前资料库下独立的 `storyboards/`，不迁移已有项目或数据；可后续调整导航位置或目录组织。
- 将固定 wheel 作为必需依赖，编辑器仅在本机 loopback 上按项目运行。
- AI 拆格确认仅填空白页；需要另一方案时新建页面。分镜包沿用核心按页格式。
- `uv.lock` 的离线 tag 构建哈希是否与线上 Release 附件一致，需要联网环境最终核对。

## 手动验收与实机出图

1. 安装 0.4.1 Release wheel，按现有方式启动 Hub。打开“分镜”，导入核心库 pudding 示例导出的分镜包，检查草稿、角色和导入报告。
2. 校验、查看翻译清单、编译；导出当前页，用核心 `load_bundle` 或节点/插件读取，核对页、角色、设置。
3. 新建空白页，选择 Hub 已启用模型并生成两格以上方案。确认前刷新页面，确认尚未写入；重新预览并选择版式后确认，检查页面缩略图。翻译重复相同的预览/确认流程。
4. 选择 OC，核对中英文外观、服装款式及颜色，可明确选择模型补全；预览后确认角色卡。测试不带 LoRA、项目 `none` 和单 LoRA 的页面选择。
5. 打开编辑器，新窗口编辑并保存，回 Hub 重读。保留旧预览，再在编辑器保存一处变更，确认旧预览应提示冲突。正常退出 Hub 后确认托管编辑器端口关闭。
6. **实机出图由用户执行**：先确认现有 Worker 和目标 ComfyUI 连接正常；选择 `minimal`，按设备实际文件名填写 MOSS 模型、文本编码器、VAE，选择 draft 和固定种子，手动投递一张。
7. 回收结果，进入现有复盘查看原图，再在分镜模块“选为本页成图”。检查页面 `production.renders`、`selected_render`，由插件/节点继续读取；再次刷新页面后核对任务和选图状态。
8. 在 ComfyUI 将 Soda-MOSS-v2 切为“JSON 直通”后导出 API，回 Hub 的分镜页登记，再手动选择 `moss-soda-v2` 投递一张，对照节点映射、尺寸、种子、模型和负面提示词。缺模型/节点时以真实错误排查，不自动安装或替换。
9. 删除测试页/项目，核对回收站保留文件及原始导入文件不受影响。

## 未完成项、风险与核心接口需求

没有执行真实 ComfyUI 生成，也没有验证外部模型质量；这是本次执行的明确边界。桌面发行包安装与跨设备使用仍需原有手验流程。

完整原有测试在此 Windows 沙箱不能全部通过。27 项原有失败已在未修改的 HEAD 临时副本逐项复现，涉及无符号链接权限、POSIX 权限和可执行位、Git Bash 路径、系统 MIME、Windows 配对路径、PowerShell 发行脚本换行/校验。没有放宽测试门槛或修改这些原有功能来规避失败，不能据此宣称“原有测试全部通过”。

核心需要补充的接口：

1. `register_render`：校验并登记外部 Worker 结果，返回可供 `pick_render` 选择的候选。Hub 的生产记录兼容接线可以随之移除。
2. 稳定公开的 production 路径验证 API，并发布 F9 修复；0.4.1 当前由 Hub 包装器保护。
3. 可注入锁/事务和路径检查的编辑器启动 API，以及并发安全的外部生产记录保存 API，减少对子进程模块接线的依赖。
4. 如果需要整个项目一个包，核心应定义多页项目包 API；Hub 当前严格使用现有按页 bundle。

升级核心库前应重新跑生产记录、编辑器和导入导出契约测试；当前严格固定 0.4.1。
