# 进度日志

## 2026-09-05：阶段 41 外部模型 API 补充层（开始）

- 用户确认由我们接手修改 PR #2 的方向；不直接合并对方分支。
- 已完成根因审查和主分支对照：当前 `main` 干净，146/146 测试、coverage 80.74%、Ruff format/lint、ty 全部通过。
- 已确定实施边界：保留 LM Studio 与现有所有交互；外部 API 为可选补充；密钥不返回前端、不写仓库；首版只支持 OpenAI-compatible。
- 当前进入现有配置、API、模型调用和前端模式审计；未修改产品代码，未 commit、未 push、未创建 PR。
- 首次一次性更新三个规划文件时因误判 `progress.md` 标题为英文而未应用；已核对实际标题后改用正确锚点，没有产生部分写入。
- 已完成现有配置、API、模型调用、Krea 2 后台任务和绘图页事件流审计；确认采用独立 store/router + 显式依赖注入，不改动现有项目、数据集或 Windows 任务协议。
- 已先增加 11 项后端回归；首次运行按预期因 `model_connections` 尚不存在而在收集阶段失败，证明测试能捕获缺失实现。
- 新增私有模型连接 store、独立 API router 和 OpenAI-compatible 请求适配；配置固定写入个人库 `private/model-connections.json` 并设为 `0600`，公开响应不含密钥。
- 模型发现改由后端执行；外部文本与视觉请求已使用真实 `model_name` 和服务密钥，现有 LM Studio 调用保持原协议。11 项定向测试已通过。
- 恢复工作后定向 Ruff 复现 `_NoRedirect.redirect_request()` 的 6 个参数缺少类型；按标准库覆写签名补齐后，又触发 `HTTPMessage` 仅用于类型检查的单项规则，移入 `TYPE_CHECKING` 后解决。
- 当前定向门为 Ruff、ty 与 12/12 测试通过；继续审计外部请求重定向、失效连接、前端编辑能力和完整回归，不提前标记阶段完成。
- 安全审计补出两项失败回归：外部推理默认跟随重定向、已删除连接会退化为 LM Studio 模型名。实现后外部请求禁止重定向并限制响应为 4 MiB，失效连接会直接提示重新选择；本地 LM Studio 行为保持不变。
- 页面补齐已有连接的“编辑 / 取消编辑”，编辑时 API Key 留空会保留原密钥；新增、修改、删除都复用同一连接列表和模型选择器。相关 Ruff、ty 与 13/13 定向测试通过。
- 首次完整 pytest 为 158 passed / 1 failed；失败根因是 `create_app()` 给所有 Krea 2 模型强制注入新包装器，绕过了既有本地 captioner 扩展点。现已收窄为只有保留的外部连接 ID 走新适配，本地模型继续使用原入口；原失败用例与外部模型 13 项组合回归通过。
- 修正后完整工程门通过：159/159 pytest、80.13% coverage、104 文件 Ruff format、Ruff lint、ty、`uv lock --check` 与 `git diff --check` 全部正常。
- 首次页面 JavaScript 提取检查因 raw string 在 `<script>` 前带换行而把 HTML 标签交给 Node，属于验收命令提取错误；同时确认 8765 当前未运行，后续用正则剥离标签后重试并启动本轮代码。
- 正则剥离后 8 段整页 JavaScript 全部通过 Node 语法检查；本轮服务已在 `127.0.0.1:8765` 启动。
- 真实 Edge 页面首次发现密码管理器把外部模型表单误判成登录框并自动填充，未提交、未保存。已将 Base URL 标记为 URL、API Key 标记为 `new-password` 并增加常见密码管理器忽略标记；重启后复核三个输入均为空。
- 浏览器桌面 1462px 和窄屏 684px 均无横向溢出；折叠区可展开，API Key 为 password 字段，窄屏完整显示读取、模型名、视觉标记和保存入口，console 0 warning/error。测试后已恢复桌面视口并折叠设置区。
- 正式服务健康检查与 doctor 7/7 通过；当前未保存外部连接，公开 `/api/model-connections`、`/api/models` 均不含 `api_key` 字段，正式个人库未因验收创建假配置。
- README 与 Mac 操作手册已补充外部模型的使用顺序、图片外发提示、协议范围和密钥位置。
- 最终修改后工程门再次通过：159/159 pytest、80.13% coverage、104 文件 Ruff format、Ruff lint、ty、锁文件、8 段整页 JavaScript、doctor 7/7 与 `git diff --check` 全部正常。阶段 41 标记 complete；服务保留运行，未 commit、未 push、未创建 PR。

## 2026-09-03：ComfyUI LoRA Manager 真实适配

- 用户已打开 5060 Ti；只读网络探测确认 `192.168.1.10:445` 与 `:8188` TCP 可达。
- Mac 重启后 `/Volumes/PromptHub-5060Ti` 尚未恢复，设备诊断为 `mount_missing`；Finder 已打开 SMB 重新连接窗口，等待用户本人输入 Windows 密码并选择是否存入 macOS Keychain。
- 直接 HTTP 读取 ComfyUI `/system_stats`、`/object_info/LoraLoader` 和 `/extensions` 均超时；不要求为此扩大局域网暴露，后续仍优先走 SMB + Windows 本机 Worker。
- UU 远程显示 `CHINAMI-5E1E3GQ` 在线，并可打开远程 PowerShell；待 SMB 恢复后继续只读确认插件 API、metadata、预览和 LoRA 目录来源。
- 会话恢复脚本首次误用不存在的 `/opt/homebrew/bin/python3`；已改用系统 Python，恢复检查正常完成。
- 首次看到 Finder 自动填入 Mac 用户名 `soda` 后误称其为 Windows SMB 用户，随后又错误采用了配置前旧表中的 `Administrator`。回查原任务的真实挂载记录，最终专用账户是 `PromptHubWorker`，历史挂载源为 `//PromptHubWorker@192.168.1.10/PromptHub-5060Ti`；后续以该真实证据为准。
- 用户重新挂载后设备诊断恢复为 `ready`：SMB 可写、Worker ready、ComfyUI reachable、RTX 5060 Ti 16GB 状态正常。
- 新增只读诊断脚本 `deploy/windows-worker/3-检查LoRAManager.ps1`，已按相同 SHA-256 同步到 Windows 共享 worker 目录；脚本只生成插件/LoRA 目录与本机 ComfyUI 接口报告。
- 远程终端执行前 Mac 被系统锁定，且因检测到用户物理输入暂停自动解锁；等待用户手动解锁后继续，不重复运行未知状态的命令。

## 2026-09-02：纠正 ComfyUI LoRA Manager 边界

- 用户确认 `comfyui-lora-manager` 是安装在 Windows ComfyUI 内的 LoRA 管理插件，不是独立训练器或直接面向 Mac 的同步服务。
- 设备页、智能检索空状态、README、Mac/Windows 操作说明、连接清单、完成度审计与开发计划已统一为：Windows Worker 适配器读取 LoRA Manager metadata、预览和 ComfyUI LoRA 目录，再向 Mac 提交只读标准化清单。
- AnimaLoraStudio 继续独立负责训练；训练产物进入 ComfyUI LoRA 目录后由 LoRA Manager 扫描管理。Mac 不复制权重，也不直接连接插件。
- 当前只完成 Mac 侧清单接收和检索接口；Windows 读取适配与远程下载仍保持未实现状态。
- 新鲜验证通过：94/94 pytest、81.15% coverage、89 文件 Ruff format、Ruff lint、ty、整页 JavaScript、98 条 OpenAPI 路径与 `git diff --check`。
- 正式服务已重启；浏览器实测设备页显示“ComfyUI LoRA 远程清单”和 Windows Worker 适配器边界，控制台 0 warning/error。

## 2026-09-02：单一 5060 Ti 制图 / 炼丹节点

- 用户取消 4070S，确认所有 Windows 侧制图、训练、VLM、Embedding 与 LoRA 管理都由 5060 Ti 承担。
- 只读审计确认当前没有持久化 `nodes.json`、历史远程任务或 SMB 挂载，因此改为单节点不需要迁移用户数据。
- 将 compute contract 升级为 `soda-compute-bridge-v2`，统一角色 `compute_5060ti`；`comfyui_generate`、`lora_train`、`embedding_batch`、`vlm_caption_batch` 和 `lora_catalog_snapshot` 均指向同一节点。
- 设备页由两张卡收敛为一张“5060 Ti · 制图与炼丹节点”，保留完整 capability，并明确只保存位置、不保存密码。
- 首轮代码静态检查、类型检查与 6 项 API/远程节点定向测试通过；测试证明同一节点可以接收 ComfyUI 与训练类任务。
- 当前文档整块补丁因 README 实际换行与预期不同被整体拒绝，确认没有部分应用后改为逐文件精确更新。
- README、Mac 操作手册、完成度审计和任务计划已改为单节点方案；单 GPU 默认采用串行调度，训练与制图互斥，Embedding/VLM 在空闲时执行。
- 完整工程门通过：81 个文件 format check、Ruff lint、ty、77/77 pytest、81.98% coverage、整页 JavaScript、OpenAPI 87 条路径与 `git diff --check` 均通过。
- 正式服务会话 `36737`（PID `77523`）已运行新版本；浏览器强制刷新后确认设备页仅有 1 张“5060 Ti · 制图与炼丹节点”卡片，不再出现 4070S。
- 正式 `/api/compute/contract` 返回 `soda-compute-bridge-v2`，并确认 `compute_5060ti` 同时具备 ComfyUI、LoRA、WD14、Embedding、VLM 与 LoRA 清单能力。
- 已取得 5060 Ti 的设备名、局域网地址、ComfyUI、AnimaLoraStudio、底模、LoRA 与 LoRA Manager 路径；凭据未写入连接资料。
- 已通过 Finder 以专用标准用户挂载 `smb://192.168.1.10/PromptHub-5060Ti`，Mac 实际路径为 `/Volumes/PromptHub-5060Ti`；临时探针的创建、读写与清理通过。
- 已登记唯一 `compute-5060ti` 节点并建立 `prompt-hub/outbox`、`inbox`、`processing`、`completed`、`failed`；五目录均可写，正式诊断状态为 `ready`，`credentials_stored=false`。
- 用户确认 Windows 系统 Python 为 3.12.10，ComfyUI 本机地址为 `http://127.0.0.1:8188`；阶段 23 Windows worker 与 ComfyUI 最小闭环开始。
- **状态：** Mac 单节点改造与真实 SMB 交付桥完成；等待 Windows worker 部署与 ComfyUI/LoRA 真实任务验收。

## 2026-09-01：Mac 发布前标签语言与 Windows 接口收口

- 已恢复阶段 21 规划、既有测试证据和 dirty worktree 边界。
- 已确认本轮目标：逐页面核对所有 tag/标签交互，中文仅用于显示和选择，英文 canonical 继续用于保存与 Anima/Krea 2/LoRA 导出。
- 已建立五步执行计划；下一步完整检查 LoRA、数据集、创作、检索和远程设备页面及其测试。
- 首次跨 8 个文件的整块补丁因 `dataset_curation.py` import 形状与预期不同而整体未应用；已确认无部分修改，改为按领域拆分小补丁。
- 已实现常用标签 catalog、中文批量标签解析、数据集统计标签点击添加、创作台 character tag 本地化、检索与 Windows LoRA tag 切换，以及 LoRA coverage 中英对照与偏置提示修复。
- 首轮定向格式检查发现 `tests/test_tag_locale.py` 一处仅格式差异；按项目 formatter 修正后，Ruff、ty 与 18 项相关测试通过。
- 已补齐 Mac 侧 Windows 共享任务桥：原子写入 outbox、本地任务事实副本、五目录状态扫描、returned 待审核状态、失败任务新 ID 重试和任务详情 API。
- 任务投递会校验节点角色/capability、必需 payload、manifest 相对路径与 SHA-256，并递归拒绝密码、token、API key、credential 和 private key 字段。
- 设备页新增“跨设备任务状态”，显示等待领取、执行中、结果待审核、完成、失败与取消；失败任务可显式重新投递，旧记录保留。
- 首轮远程桥静态检查发现 2 处 formatter 差异、1 个参数数量 lint、1 个性能 lint 和 1 个 ty 联合类型问题；已通过改为 values 对象、字典更新和显式类型收窄解决。
- 修正后 Ruff、ty、整页 JavaScript 与 22 项相关测试通过；真实 SMB/worker 仍留到明天，不宣称远程计算已发生。
- 正式服务已安全停止旧进程并以新代码重启，当前服务会话为 `97689`。
- 首轮正式组合检查因未给带 `?` 的 URL 加引号触发 zsh glob，同时 Python 单行 f-string 中错误使用转义；请求未执行到后续检查，改用引号 URL 与 `%` 格式后从头重跑。
- 浏览器设备页桌面验收显示两节点、任务 ledger 和 LoRA snapshot 诚实空状态，1280px 无横向溢出、控制台无 warning/error。
- 标签检索首轮定位使用了不存在的中文 placeholder，读取实时 DOM 后改用 `searchbox`；`silver_hair` 与 `silver hair` 在当前 FTS 无命中，未重复猜测更多变体，改用页面已有的 `yellow jacket` 资料验证切换分支。
- 中文模式对未收录长尾 tag 会诚实保留英文，因此按钮从“标签：中文”改为“标签：中英”，并补充常见服装词根；英文模式仍为 `TAGS: EN`，canonical 数据不变。
- 正式标签切换复验通过：`黄色夹克 (yellow jacket)` → `yellow jacket`，中英模式显示标准英文输出前缀，英文模式不显示。
- 数据集页已加载 86 项中文候选，其中“银发”对应 `silver_hair`；正式数据集为空，因此未污染正式工作区。
- 390×844 设备页节点与任务列表均为单列，`innerWidth=390`、`scrollWidth=390`、任务列表宽 370px；控制台 0 warning/error。
- 浏览器视口已恢复默认，正式标签页保留在“设备连接”，服务会话更新为 `13226`。
- 首次核对测试报告旧数字时，shell 检索命令的双引号未闭合，zsh 在执行任何文档检查前返回 `unmatched \"`；已改为不含嵌套引号的安全检索并重新核对，确认没有旧测试数字残留。
- 最终新鲜门首次整页 JavaScript 提取误用系统 Python，因找不到项目包而失败；管道未启用 `pipefail` 又让外层返回 0，该次 JavaScript 结果作废。改用 `uv run python` 与严格管道重新执行，其他已显示通过的 Ruff、ty、77 项 pytest 和 diff 检查证据保留。
- 正式诊断断言首次将每项真实的 `ok` 布尔字段误读为 `status`，因此脚本在健康、86 项标签目录与 87 条 OpenAPI 已通过后中止；返回内容显示 7 项均为 `ok: true`，但该次 doctor 判定仍作废，按真实结构重新执行。
- 修正后的 doctor 7 项通过；后续独立 SQLite 脚本误猜 `Settings.embedding_database_path` 属性名而中止，未执行敏感扫描。正式诊断中的两库完整性结果有效，独立 SQLite 与敏感扫描改按 `config.py` 的真实字段重跑。
- 文档更新后的最终新鲜工程门通过：81 个文件 format check、Ruff lint、ty、77/77 pytest、82.01% coverage、整页 JavaScript 严格管道检查和 `git diff --check` 均通过。
- 正式运行态复核通过：`/api/health=ok`、Tag catalog 86 项、OpenAPI 87 条路径、doctor 7/7、主库与 embedding 库 `integrity_check=ok`；私钥、GitHub/OpenAI/Google key 形状与非示例 `.env` 扫描均为 0。
- **状态：** Mac 本机开发收口完成；真实 SMB、Windows worker、LoRA Manager snapshot、训练/回传和断线恢复留到明天跨设备验收。

## 会话：2026-09-01（Mac 收口与 5060 Ti 接口预留）

- **状态：** in progress
- 用户要求继续完成 Mac 本机能力，并把明天连接 5060 Ti 所需接口留好；今天不配置 Windows SSH/SMB。
- 已恢复规划、发现、进度与 dirty worktree；确认现有改动均需保护，不 commit、push 或创建 PR。
- 本轮顺序：混合检索 API → 检索/相似图 UI → worker/LoRA Manager 契约 → Mac 备份恢复与诊断 → 全量验收。
- 安全边界：当前无真实 CLIP/SigLIP runtime 与 embedding，空状态必须明确，不得用随机或非语义特征冒充视觉检索。
- 新增混合检索后端第一版：关键词始终返回；只有收到真实 query vector 且存在兼容索引时才合入 cosine 结果；支持按源 SHA-256 以图查图。
- 首轮 5 项定向测试通过。Ruff 发现动态 SQL 形式、import 顺序和全角标点规范问题；已改为两条固定参数化 SQL 并整理类型导入，等待复测。
- 混合检索与 source-status API 已接入正式应用；9 项相关/API 测试通过，ty 通过。Ruff 第二轮只发现 FastAPI `Annotated` 和多余 `noqa`，已修正。
- 新增“智能检索”主页面和数据集详情“以此图查相似”入口。浏览器桌面实测：四分组可见、空索引明确显示等待真实视觉索引，`gothic` 返回 24 条提示词和 5 条视觉参考，控制台 0 warning/error，1280px 无横向溢出。
- 390×844 实测单列、`innerWidth=390`、`scrollWidth=390`、四分组均保留，控制台 0 warning/error。浏览器首轮误用文档示例中的 `tab.playwright.screenshot`，已按实际 API 改为 `tab.screenshot`，未影响页面。
- 正式库当前没有已注册数据集工作区，因此数据集详情按钮的真实页面点击需使用隔离夹具或后续用户数据集；后端 source-status 与 by-source 行为已有自动测试覆盖。
- 新增统一维护模块与 CLI：`backup`、`verify-backup`、`restore --destination`、`doctor`；恢复只允许不存在或为空的新目录，不提供覆盖正式库的快捷操作。
- 新增 Mac 双击启动/停止/备份/诊断入口；正式诊断实跑 7 项全部通过，数据库与 embedding SQLite 均为 `ok`，磁盘剩余 711.8 GiB。
- 首次正式备份和恢复到废纸篓测试通过（7 文件、两库完整性 `ok`），但校验 SQLite 时生成了空 WAL/SHM 辅助文件；已改用 immutable 只读校验，准备重新生成更干净的正式基线包。
- 数据集工作台新增每页 200 张分页；完整筛选集合继续负责全选和批量操作，卡片 DOM 与详情切换只处理当前页，保存 caption/草稿后保持当前页。
- 首次整块 patch 因同一文件出现多个更新段被工具拒绝，文件未产生部分修改；改为小块定向 patch 后完成。
- 定向 pytest 首轮被项目全局 80% coverage 门拦截（单测覆盖率仅代表本次采样）；改用 `--no-cov` 完成局部回归，最终发布仍保留全量 coverage 门。
- 隔离规模夹具完成 1,000 与 10,000 张扫描：均为 100% 有效，SHA/pHash 与完全重复组正确；报告约 494 KiB / 4.8 MiB，相同 SHA 只产生一份缩略图。
- 应用内浏览器 1280px 实测 10,000 张只渲染 200 张，显示 50 页；下一页从 `image-00001.webp` 切到 `image-00201.webp`，全选仍显示 10,000 张，清空后恢复 0 张；控制台 0 warning/error、无横向溢出。
- 390×844 实测单列宽 322px、页面宽 390px、滚动宽 390px；第 4 页首图为 `image-00601.webp`，仍只渲染 200 张，控制台 0 warning/error。
- 新增 `MAC_OPERATIONS_GUIDE.md`，覆盖一次创作、数据集审核、LoRA 训练、Windows 回传、日常启动/停止/备份/诊断/恢复和明天 SMB 配置顺序。
- 最终正式备份生成于 `backups/prompt-hub/mac-pre-windows-final-20260901`；manifest 包含 `remote-nodes`，verify 与恢复到新目录均通过，两库 integrity 为 `ok`。
- 全量 pytest 76/76 通过，coverage 81.97%；Ruff format/check、ty、整页 JavaScript、`git diff --check`、OpenAPI 83 路径、两库完整性与 credential-shaped 敏感信息扫描通过。
- 首轮全量 Ruff 暴露 `search_web.py` 尚未加入内嵌页面模块的 E501/RUF001 精确例外；只新增该文件 per-file ignore 后全量复验通过，未放宽全项目 lint。
- 正式 8765 已重启到最终代码；doctor 7 项全部 `ok`，磁盘剩余约 711.6 GiB。
- 正式浏览器 `gothic` 返回 4 分组、29 张结果卡；设备页显示 4070S/5060 Ti 两张卡与 LoRA snapshot 空状态。1280px 与 390px 均无横向溢出，控制台 0 warning/error。

## 会话：2026-09-01（完整目标继续：M7 Mac 本地能力）

- **状态：** in progress
- 上一轮阶段报告不是完整目标完成证明；根据 `completion_audit.md` 继续开发 M7A/M7D/M7B/M7C。
- 新增资料源安全增量同步领域与 API：只处理干净且有 upstream 的 Git 仓库，执行 fetch + fast-forward-only；本地改动和无 upstream 仓库明确跳过。
- 首轮静态检查发现 `api.py` import 排序和 `Path` 仅用于类型标注；已按 Ruff 建议调整，不改变同步行为。
- 资料同步真实 Git 测试首轮 Ruff 报告测试进程路径与安全标注；测试改为解析本机 Git 绝对路径，并只对受控临时仓库命令添加精确 `S603` 说明。
- 定向测试通过但 ty 拒绝测试进度替身，因为同步服务最初绑定了具体 `JobContext`；已改为只要求 `update()` 的结构化 Protocol，便于本机 runner、测试和未来 Windows 编排共同复用。
- M7A 加入全量回归后 63 项 pytest 通过，覆盖率 82.68%；资料源仍只执行 `fetch --prune` 与 `merge --ff-only`，脏工作树不覆盖。
- 审计本项目运行环境：当前只有 ONNX Runtime、Pillow 与 NumPy，没有 torch/transformers/MLX/open_clip，也未发现本机 CLIP/SigLIP 模型；M7B/M7C 不使用随机向量或颜色直方图冒充语义 embedding。
- 新增 Krea 2 VLM 本地原生 Chat 调用：图片缩到 1024px、`reasoning=off`、只接受英文 ASCII 自然语言草稿与结构化观察；合法成年 SFW/NSFW 可客观描述，疑似未成年人成人内容降级为非露骨描述并返回警告。
- 新增 `dataset_krea2_vlm` 可恢复后台队列、源 SHA-256 校验、selected/missing/failed/all 范围、逐图失败记录与重试；模型结果只写 `krea2_vlm.draft`，不修改正式 Krea 2 或 Anima caption。
- 新增草稿保存/确认 API；只有确认动作才创建 Krea 2 caption snapshot，并以 `source=vlm-confirmed` 写入正式 caption。
- 数据集工作台已加入视觉模型选择、草稿队列按钮、卡片状态、正式 caption/模型草稿对照、警告、保存草稿与确认写入入口。
- 11 项相关定向测试实际通过；该定向命令因全项目 80% coverage 门只覆盖 45.66% 而返回失败，属于测试选择造成的覆盖率门问题，需以随后全量 pytest 为准。Ruff、ty 与数据集页面 JavaScript 语法检查当前通过。
- M7D 加入全量回归后 66 项 pytest 通过，覆盖率 82.41%。隔离浏览器验证草稿保存不覆盖正式 Krea 2；确认后生成 KREA2 快照、`source=vlm-confirmed`，Anima 不变。
- 浏览器发现手工草稿状态会显示空模型时间分隔符，已修正为“人工保存草稿”；桌面无横向溢出，390×844 下 `scrollWidth=375`、Caption desk 单列、详情草稿可见，控制台 0 warning/error。
- 隔离 QA 数据目录已停止并移入 `/Users/soda/.Trash/prompt-hub-m7-qa-6Kaeqo`，可恢复；正式 8765 没有导入 QA 工作区。
- 新增独立版本化 embedding SQLite 索引：按 model ID + revision + dimension 并存版本，float32 单位向量、asset 类型/路径/源 SHA-256/生成设备/worker/metadata 均保留。
- 新增 5060 Ti embedding 批量结果导入与向量查询 API；导入必须通过 Mac 预期 SHA-256 回验，查询返回 cosine score、真实来源和匹配原因。当前只完成索引与远程接口，不宣称 Mac 已有 CLIP 生成 runtime。
- 新增远程 `vlm_caption_batch` 结果导入 API；Mac 按扫描报告回验每张源图 SHA-256，结果仍只进入 Krea 2 草稿，必须人工确认。
- embedding + 远程 VLM 的 7 项定向测试、Ruff 与 ty 通过。
- 首轮最终检查发现 Ruff format 会改写 3 个文件；已执行项目格式化后重新运行完整验证。
- 最终新鲜验证通过：68 项 pytest、82.31% coverage、70 文件 Ruff format、Ruff lint、ty、整页 JavaScript、`git diff --check`、73 条 OpenAPI 路径、正式 SQLite 与 embedding SQLite `integrity_check=ok`。
- 正式 8765 已重启到 M7 Mac 接口版本；健康检查、空 embedding 索引与资料同步状态接口返回正常。本轮未 commit、未 push、未创建 PR。

## 会话：2026-09-01（M5 ComfyUI 回流与 Windows worker 接口收口）

- **状态：** feature complete / final full regression pending
- 新增独立 ComfyUI 回流库：PNG/JPEG/WebP 校验、SHA-256 去重、原图/缩略图、只读目录导入、disposition 与项目关联索引。
- 解析 ComfyUI `prompt` / `workflow`、KSampler 参数、checkpoint、LoRA、尺寸及 CLIP 正负 Prompt 节点引用；A1111 `parameters` 和无 metadata 图片安全降级。
- 新增回流 API 与“结果回流”页面，固定为导入→核对→选择项目→关联/候选/失败/分支四步；只有候选进入 `dataset_selected`。
- 3 项 M5 专项测试通过；隔离服务桌面 1280px、手机 390×844 无横向溢出，真实候选点击成功，控制台 0 warning/error。
- 全局 tag 边界审计补齐 LoRA 风险标记：页面显示中文 + canonical 英文，项目 JSON 继续只保存英文 ID。
- `/api/compute/contract` 增加 `comfyui_generate`、`lora_train`、`embedding_batch`、`vlm_caption_batch` 的 payload/result、worker 注册和源 SHA-256 回验规则；未保存 Windows 地址、共享路径或凭据。
- M7 向量索引和批量 VLM 不标记完成；等待明天连接 5060 Ti 后，用真实模型与 SMB 任务流实现和验收。
- 完成前全量验证通过：62/62 pytest、82.76% coverage、Ruff format/check、ty、整页 JavaScript、`git diff --check`、65 条 OpenAPI 路径与正式 SQLite `integrity_check=ok`。
- 隔离 QA 目录已停止服务并移入可恢复的废纸篓：`/Users/soda/.Trash/prompt-hub-m5-qa-7xQejS`；正式回流库保持空列表，未写入测试图。
- 正式 8765 已重启到 M5 版本；资料仍为 33,631 条、4 个来源，正式回流页空状态无横向溢出，浏览器控制台 0 warning/error。
- 本轮未 commit、未 push、未创建 PR。

## 会话：2026-09-01（完整目标审计与 M5 启动）

- **状态：** in progress
- 按持久目标重新审计 Mac 本机完成度，确认上一轮 M3/M4 属于有效进展，但 M5 ComfyUI 元数据回流、M7 部分本地能力、全局 tag 本地化审计和统一最终测试报告仍未完成。
- 新增 `completion_audit.md`，逐项记录明确要求、当前证据、完成判定和下一步，防止用局部通过替代完整目标。
- 当前优先实现不依赖 Windows 的 M5；Windows SMB、驱动和训练 smoke test 留到设备连接后执行。

## 会话：2026-09-01（V1.8 LoRA 项目台与 5060 Ti 交付接口）

- **状态：** M3 + M4 feature complete / real dataset and Windows smoke test pending
- 新增四类 LoRA 项目、Trigger、fixed/controllable/variable/forbidden drift、OC Manager 只读来源、数据集工作区图片引用和八维覆盖矩阵。
- 每个项目在 `prompt-library/lora-projects` 下建立标准项目根目录、管理文件、训练/正则/导出/测试/丹炉导入目录；网页索引不是唯一事实源。
- 图片仅保存 workspace ID、相对路径、SHA-256、pHash、状态、覆盖和风险标记；自动测试确认源图片、源 caption 与 OC 记录不变。
- 新增不可变冻结包：Anima/Krea2 独立 train/reg caption 树、manifest、文件与 caption 哈希、测试 prompt、run 占位 ID 和 5060 Ti 16GB 配置草案。
- Krea 2 草案固定 Raw FP8、Qwen3-VL FP8、28 层 block swap、batch 1、grad checkpoint、`krea2_shift`、关闭 shuffle/dropout；正式训练前仍需 Windows smoke test。
- 浏览器隔离验收发现保存后左侧 revision 摘要滞后一轮；修正为活动项目更新时同步列表摘要，复验显示 R2/R3 与磁盘一致。
- 桌面 1280px 与手机 390×844 无横向溢出，正式页面控制台 0 warning/error；隔离 QA 项目已移入废纸篓 `prompt-hub-m3-qa-bF2adZ`。
- 最终发布门通过：59/59 测试、coverage 83.41%、Ruff format/check、ty、整页 JavaScript、`git diff --check`、正式 SQLite `integrity_check=ok`；OpenAPI 58 条路径含 6 条 LoRA 路径。
- 正式 8765 已重启到最新 M3/M4；桌面 1280px、手机 390×844、冻结入口与浏览器 0 warning/error 复核通过。
- 本轮未 commit、未配置 remote、未 push、未创建 PR。

## 会话：2026-09-01（M2 WD14 长队列、双 Caption 与版本化导出）

- **状态：** feature complete / user dataset scale gate pending
- 恢复阶段 17 / M2 上下文，确认本轮继续 Mac 本地能力，不保存 Windows 地址、共享路径或凭据。
- 双语标签、WD14、Anima/Krea 2 英文编译和非英文 caption 导出保护的 19 项定向测试通过；`ty` 通过。
- 首轮 Ruff 检查发现 `creative.py` 一处长行和 `dataset_export.py` 一处全角分号；均为静态格式问题，已按原语义修正，等待复验。
- 新增 M2 工作区策展模块后的首次静态检查发现领域模块尚未配置既有异常/复杂度豁免、一个频率字典类型过宽，以及全角逗号提示；已改为显式常量和类型，并按 `dataset_workspace.py` 同级规则配置，等待复验。
- 新增 `dataset_curation.py`：WD14 单次加载模型后连续处理任意长度队列，逐图保存 rating/general/character、置信度、阈值、模型、provider、耗时、失败信息和任务 ID。
- 同一任务中断后按 `job_id` 跳过已完成图片；30 张文件级回归在第 10 张中断，恢复时只处理剩余 20 张。人工确认 Anima 与 Krea 2 均保持不变。
- 每张图维护独立 Anima canonical tags 与 Krea 2 英文自然语言记录；中文仅用于 chips 显示。手工与批量修改生成带 `profile_id` 的快照，可预览、查看和按原分支回退。
- 增加频率、低频、疑似拼写、可配置冲突规则、批量增加/删除/替换/排序/标准化，以及不静默删除的冲突提示。
- 增加只读来源的版本化导出：只允许已标记保留、英文 caption、无完全重复哈希的图片；输出独立 Anima/Krea 2 目录与 ZIP、`manifest.json`、`audit.json` 和图片/caption 哈希。
- 网页流程收敛为“选图 → WD14 → 大图双 Caption 审核 → 冻结导出”；真实 WD14 对 3 张图片完成，桌面和 390×844 手机无横向溢出，控制台 0 warning/error。
- 浏览器验收发现旧 Krea 2 快照缺少显式分支；已增加 `profile_id`，并按旧 `edit-krea2` 操作名兼容识别。首屏超过 500 标签的中文预载改为分批请求，避免 422。
- 55 项全量功能测试、Ruff、ty 与 JavaScript 语法检查已通过；完成文档更新后还需执行最终 coverage、正式数据库与服务复核。
- 最终 coverage 运行升级为 56 项并全部通过，总覆盖率 84.60%。首个整页 JavaScript 提取命令误把 `</body>` 送入 Node，产生工具命令语法错误；模块脚本此前均通过，已改用正则只提取 `<script>` 内容复验。
- 临时验收工作区已由 API 移除，返回 `source_untouched=true`；两条对应后台任务已按精确 workspace ID 清理。直接永久删除测试目录的命令被安全策略拒绝，改用移动到 macOS 废纸篓的可恢复清理方式。
- 移动后复核命令误用 zsh 特殊变量名 `path`，覆盖了命令搜索路径并使末尾 `curl` 未找到；两个目录移动本身均已成功，后续改用绝对命令路径查询。
- 工作区空列表与健康检查已返回正常；后台任务复核 URL 首次未加引号，`?` 被 zsh 当成 glob，随后改用带引号 URL。
- 服务日志显示 500 条分批后首屏仍有一次标签映射 422；根因是资料卡的中文标题也被送入 canonical tag 解析。前端改为只批量映射 ASCII tags，原中文标题直接显示。
- 进一步复现确认实际拒绝项是加权 Prompt 语法 `{black bodystocking:1.2}`；它虽为 ASCII，但不是 canonical tag。前端最终改为使用与后端一致的 canonical 字符规则，权重片段原样保留、不进入本地化接口。
- **最终验证：** 56/56 测试通过，coverage 84.60%；Ruff format/check、ty、整页 JavaScript 语法和 `git diff --check` 通过。正式 SQLite `integrity_check=ok`，资料 33,631 条、来源 4 个；OpenAPI 52 条路径包含 M2 与 compute contract。
- 正式 8765 已使用最新代码重启。最终首屏标签本地化为 200，数据集工作区恢复为空；桌面页面身份、空状态、无横向溢出和浏览器 0 warning/error 复核通过。
- 临时 QA 图片与测试导出已移动到 macOS 废纸篓，名称为 `prompt-hub-m2-qa-20260901-Uaerst` 和 `prompt-hub-m2-export-20260901-b101b24e`，可恢复；未触碰用户真实数据集。
- 本轮工作树未 commit、未配置 remote、未 push、未创建 PR。

## 会话：2026-09-01（V1.7A 数据集工作台前端与 5060 Ti 接口预留）

- **状态：** complete / M1 feature complete, release-scale gate pending
- 在主导航增加“数据集”，实现目录读取、最近工作区、重新扫描、移除派生记录和只读边界说明。
- 新增独立 `workspace_web.py`，提供统计、坏图/caption/审核/重复/格式/尺寸筛选、缩略图网格、
  多选与全选当前结果、批量保留/待复查/排除、大图审核弹窗和键盘上一张/下一张。
- 审核状态保存在工作区 `review.json`，按相对路径与 SHA-256 追踪；扫描报告不会被改写，源目录
  不会被移动、改名、覆盖。原图路由只允许访问当前报告中登记且有效的图片。
- 增加移除工作区 API，只清理 Prompt Hub 自己的 manifest、报告与缩略图；自动测试逐字节确认源图片
  与 caption 保持不变。
- 浏览器首次验收发现小数据集同秒完成时前端因 `updated_at` 秒级相同未加载报告；改为只要工作区
  有报告且页面尚未加载就强制读取，复测统计与 4 张卡片正确。
- 桌面端真实交互完成：完全重复筛选得到 2 张、全选、批量标记保留、大图打开与键盘切换均通过；
  控制台 0 warning/error。390×844 下 `innerWidth=390`、`scrollWidth=390`，无横向溢出。
- 浏览器截图方法与技能说明不一致：实际截图位于标签页对象而非页面控制对象；未重复审核写入，改用
  正确接口后完成证据截图。
- 临时 `/tmp` 验收目录及正式库中的临时工作区记录已删除；源目录删除前由 API 确认
  `source_untouched=true`，正式工作区列表恢复为空。
- 新增 `/api/compute/contract`：固定 `soda-compute-bridge-v1` 任务信封、SMB 目录状态流、4070S/
  5060 Ti 能力角色与安全边界；尚未保存 Windows 地址、共享路径或凭据，也未发起连接。
- 完整测试 49 项通过、覆盖率 86.10%；ruff、ty 与 diff 静态检查通过。正式 SQLite
  `integrity_check=ok`。正式 8765 已重启，OpenAPI 42 条路径、新计算协议、空工作区、33,631 条资料
  与 4 个来源均复核通过；正式浏览器页面保持打开，控制台 0 warning/error。
- V1.7 新改动仍保留为未提交工作树；未创建第三个 commit，未配置 remote、未 push、未创建 PR。

## 会话：2026-09-01（设备归属与 M7 细化）

- **状态：** complete
- 用户确认 M1、M2、M5、M7 应以 Mac 功能为主，并要求解释 M7；本轮只更新设备与架构计划，不修改业务代码或设备配置。
- 明确 M1/M2/M3/M5 的产品状态与审核均在 Mac；M4 的准备与冻结在 Mac，smoke test/训练/checkpoint 测试在 5060 Ti。
- 明确 M7 是 Mac 产品功能而不是 Windows 子系统：资料缓存、向量索引、混合检索、UI、caption 审核和版本状态均在 Mac。
- M7 拆为资料同步、混合检索、相似图/聚类、Krea 2 VLM caption 四部分；单图与小批量可在 Mac，大批量 embedding/VLM 默认下放空闲的 5060 Ti，4070S 只作可选 worker。
- Windows 只返回可重建计算结果与模型版本；Mac 校验文件哈希后写入版本化索引，Windows 离线不影响已有搜索和审核。

## 会话：2026-09-01（完整交付计划）

- **状态：** complete
- 用户要求给出从当前状态到系统完全完成的计划；本轮只更新规划，不继续修改业务代码、数据库、正式服务或 Git 历史。
- 将绘图主线完成定义为 V2.1：数据集工作台、WD14 长队列、LoRA 项目管理、ComfyUI 回流、两台 Windows 交付桥、视觉检索与 Krea 2 VLM caption 全部闭环。
- 将执行顺序拆为 M1–M8，并为每个里程碑补充实施清单、真实验收门和最晚需要的用户输入。
- MiniMax H3 作为 M9 独立视频阶段，复用资料、任务和版本基础，但不阻塞绘图主线发布，也不混入静态绘图槽位。
- 全局完成标准固定为：原始数据不静默覆盖、模型结果先审核、Anima/Krea 2 分树、长任务可恢复、导出可追踪、Mac/Windows 分工明确、正式恢复测试通过。

## 会话：2026-09-01（阶段 16 收口 / V1.7 第一段）

- **状态：** complete / V1.7 first backend slice
- 用户以“继续”明确确认创建第二个本地重构 commit，并继续 V1.7；授权不包含 remote、push、PR 或 Windows 操作。
- 提交前重新执行 Ruff format/check、ty、43 项 pytest、OpenAPI 路径/方法集合和最终 HTML bundle 对照；网页 SHA-256 为 `4044ade48a9b8ef3daf139e6c2b0478d577d2aa4d61608300bfb8a3890c8b114`，31 条 API 路径与基线一致。
- ty 新版本暴露一处测试对可空配方结果直接下标的问题；测试改为先断言配方存在，不改变业务行为。
- 已创建第二个本地 commit `2235e57 refactor: split dataset routes and creative layout`；仓库仍无 remote、未 push、未创建 PR，提交后工作树干净。
- 新增 SQLite 持久化后台任务：支持 queued/running/completed/failed/canceled、进度、合作式取消、服务重启恢复、自动重试和显式重试；首版单 worker 控制 Mac 内存与磁盘竞争。
- 新增只读数据集工作区：来源目录只扫描不写入；Prompt Hub 自己的 `datasets/workspaces` 保存 manifest、版本化扫描报告和派生缩略图。
- 扫描覆盖 PNG/JPEG/WebP 解码、尺寸、同目录同名 `.txt` 配对、缺失 caption、孤立 `.txt`、SHA-256 完全重复和 64-bit pHash 近似重复。
- pHash 首版使用 32×32 灰度低频 DCT 与 Hamming distance 5；最初实现的 dHash 在规划复核时被主动纠正，不以泛称“感知哈希”代替计划中的 pHash。
- 新增数据集工作区与任务 API：导入、列表、详情、当前报告、重新扫描、任务列表/详情/取消/重试，以及受限 WebP 缩略图读取。
- 新增 4 项定向测试，覆盖中断恢复、自动重试、运行中取消、只读源字节不变、坏图、caption 配对、完全/近似重复、报告版本保留和真实 TestClient 后台扫描。
- 完整验证通过：47 项 pytest、覆盖率 86.20%、Ruff format/check、ty 与 diff check 全部成功。
- 正式 8765 已正常重启加载新版本；OpenAPI 从原 31 条兼容路径增加到 40 条，V1.7 导入、报告与任务端点均可达。
- 正式首页 SHA-256 仍为 `4044ade48a9b8ef3daf139e6c2b0478d577d2aa4d61608300bfb8a3890c8b114`，确认这轮没有改变现有页面成品。
- 正式 SQLite `integrity_check=ok`，仍为 33,631 条资料和 4 个来源；只新增空的 `background_jobs` 表与数据集工作区目录，没有导入或改写任何用户数据集。
- V1.7 新改动按授权边界留在本机工作树，尚未创建第三个 commit；remote 仍为空，未 push、未创建 PR。

## 会话：2026-08-31（阶段 16 工程安全门）

- **状态：** in_progress
- 用户已明确授权建立本地 Git 基线和工程备份；授权不包含 remote、push 或 PR。
- 已确认项目目录已有 `.git`、当前分支为 `main`，但没有任何 commit、没有 remote，项目文件均未跟踪。
- 已按敏感配置保护规则检查：项目内没有 `.env`、私钥、数据库或超过 10 MiB 的待提交文件；安全关键词扫描未返回命中文件。
- 已确认正式数据位于项目外的 `prompt-library`，Git 基线不会直接包含数据库、结果图、个人资料、导出包或模型。
- 已确认正式备份范围：SQLite 在线备份，以及 `private`、`test-results`、`exports`、OC 导入快照、LM Studio MCP 配置和模型/资料源版本清单。
- 当前 `.gitignore` 仅覆盖 Python 产物和虚拟环境，仍需补充测试缓存、浏览器 QA、环境文件、数据库、密钥、日志和本地数据目录规则。
- 已创建 `/Users/soda/Documents/Codex/soda-person/backups/prompt-hub-v1.6-baseline-20260831`：包含 SQLite 在线一致性备份、个人目录布局、OC 导入目录、结果与导出目录、LM Studio MCP 配置副本和恢复说明。
- 备份数据库 `integrity_check=ok`，包含 33,631 条资料和 1 个创作项目；SHA-256 为 `1852de4d3bd037817a8ab3bd5c1ede2b35fbcb438be6af0fb7025e1c33a5c75f`。
- WD14 模型不重复复制 467 MB 权重，恢复说明记录文件大小与三个 SHA-256；四个公共 Git 资料源记录精确 commit，均为干净工作树。
- 已完善 `.gitignore`，新增测试/浏览器缓存、环境文件、凭据、私钥、数据库、压缩包和本地数据/模型目录规则。
- Git 实际候选清单为 43 个文本文件，均为代码、测试、文档和依赖锁；缓存、虚拟环境和浏览器 QA 已正确显示为 ignored。
- 首次敏感内容复合正则因 shell 引号解析失败，未读取或输出任何候选文件内容；改为独立规则后继续审计。
- 独立规则复检完成：候选文件未命中私钥头、GitHub/OpenAI/Google/Slack token 形态、Bearer 凭据、长值密钥赋值或带凭据 URL。
- `.env`、任意 `*.env`、数据库、私钥、浏览器 QA、测试缓存、lint 缓存与虚拟环境均已由 `git check-ignore` 验证；示例环境文件仍允许纳入版本控制。
- 首次提交前完整验证在 Ruff format gate 停止：`creative.py`、`sourcing.py` 和 3 个测试文件共 5 个文件需要机械格式化；后续检查尚未执行，不误报为通过。
- 已用锁定环境执行 Ruff 自动格式化，5 个文件仅发生机械换行调整；随后从头验证通过：39 个文件格式正确、Ruff check 和 ty 均通过、43 项 pytest 全通过、覆盖率 85.88%。
- 正式 8765 健康接口返回 `ok`；正式 SQLite `integrity_check=ok`，仍为 33,631 条资料和 1 个创作项目。
- 已暂存 43 个工程文本文件；staged 敏感扫描无命中。首次 `git diff --cached --check` 只发现 `BASELINE.md` 末尾多余空行，修正后重新暂存复检。
- 提交前完整验证再次通过后，已创建 `chore: establish Prompt Hub V1.6 baseline` 本地 root commit；未配置 remote、未 push、未创建 PR。
- 基线最终 commit 为 `230185d`，提交后工作树干净；备份恢复说明已在 Git 仓库外记录该 commit。
- 代码拆分阶段已启动。`gitnexus-refactoring` 技能要求的图索引工具在当前环境没有暴露，因此改用本地静态调用搜索、精确路由清单和全量测试作为替代，不执行猜测式批量改名。
- 首轮拆分范围收束为：先把数据集 API 与请求模型从 `api.py` 提取为独立路由模块；前端静态资源和数据库继续分小步处理，避免一次跨越后端、页面、SQLite 三层。
- 已新增 `dataset_routes.py` 与 `result_assets.py`，并从 `api.py` 移出数据集请求模型、ZIP/精选/WD14/审核端点及通用结果资产路径函数。
- 首轮定向 Ruff 在测试前停止：1 条 import 顺序、4 条类型 import、2 条 FastAPI 注册函数复杂度。采用 TYPE_CHECKING 和文件级精确例外修正，不放宽全局规则。
- 规范修正后 Ruff 与 ty 通过；定向测试 14 项中 12 项通过，2 项因 monkeypatch 仍指向旧模块失败。已改为 patch 新所有者 `dataset_routes.tag_image`，等待全量回归。
- 修正测试 patch 后全量验证通过：43 项 pytest、覆盖率 85.96%、Ruff format/check、ty、diff check、正式健康接口和 SQLite 完整性均成功。
- 首次额外路由对照脚本的 Python 引号错误导致基线与当前输出都为空，被 shell 误判为相同；该结果作废，改为对子命令退出码做显式检查后重跑。
- 第二次对照已能正确传播错误，但 FastAPI 内部 `_IncludedRouter` 不具备 `methods`；调整为仅比较真实 HTTP 路由后再执行。
- 继续调查确认 `include_router()` 在当前 FastAPI 中以 `_IncludedRouter` 嵌套保存，不会展平到顶层 `app.routes`；简单路由列表因此误报少 6 条。
- 无 lifespan 的 TestClient 探针已进入 `dataset_routes.export_creative_dataset` 后才因临时库未初始化失败，证明数据集路由实际可达；最终改用 OpenAPI 集合和上下文 TestClient 验证。
- OpenAPI 最终对照通过：基线与当前均为 31 条路径，HTTP 方法集合完全一致。
- 已新增 `creative_web_layout.py` 作为创作台 HTML 布局的独立所有者；首次删除旧内嵌 HTML 的长补丁校验失败且未产生部分删除，改用当前文件生成精确 apply patch。
- 精确补丁已移除旧内嵌 HTML，`creative_web.py` 改为导入独立布局；基线与当前的 `CREATIVE_HTML`、最终 `INDEX_HTML` SHA-256 分别完全一致。
- `api.py` 从 816 行降为 577 行；数据集路由为 222 行、结果资产工具为 55 行。`creative_web.py` 从 764 行降为 651 行，布局模块为 116 行。
- 本轮代码拆分仅改变模块所有权，没有更改 URL、请求/响应、SQLite schema、HTML、CSS 或 JavaScript；后台任务框架仍留在阶段 16 后续，不在本次基线重构中混入新功能。
- 最终检查发现新布局文件需要继承旧静态 HTML 的 `E501`/`RUF001` 精确例外，且 import 需显式声明 re-export；已按原边界修正，不改变中文页面文本。
- Ruff 不接受同名 alias 形式，已改为标准 `__all__` 声明三个公开静态常量，等待重新执行完整验证。
- 完整验证通过后，OpenAPI 31 条路径和最终网页 bundle 再次与基线完全一致。
- 最后的变更文件敏感扫描首次使用 GNU `xargs -a`，macOS BSD xargs 不支持该参数，扫描未执行；改用逐文件循环重跑。
- macOS 兼容扫描重跑通过：本轮变更文件未命中私钥、常见 token 或 Bearer 凭据形态；仓库仍无 remote。
- 阶段 16 本轮交付完成：V1.6 私有备份、本地 Git 基线、数据集 API 拆分、结果资产工具拆分和创作台 HTML 布局拆分均已验证；后台任务框架继续作为阶段 16 的后续前置，不与本次纯重构混合。

## 会话：2026-08-31（V1.6 后续路线规划）

- **状态：** complete
- 审计确认 V1.6 已完成单图/小批量 WD14 打标、人工审核、Anima/Krea 2 caption 隔离和数据集 ZIP 导出。
- 确认下一主线不做 MiniMax H3，也暂不做 Windows SSH；优先建设完整数据集工作台。
- 记录后续顺序：工程安全门 → V1.7 数据集工作台 → V1.8 LoRA 项目管理 → V1.9 ComfyUI 元数据回流 → V2.0 Windows 交付桥 → V2.1 视觉检索与 Krea 2 批量 caption。
- 确认 4070S Windows 主机负责 ComfyUI 生成/测试，5060 Ti 16GB Windows 主机负责 LoRA 训练/批量测试，Mac 负责规划、检索、审核、版本与交付。
- 本轮只更新规划文档，没有修改业务代码、数据库、模型、正式服务或 Git 历史。

## 会话：2026-08-31（阶段 15）

### V1.6 数据集自动打标与人工审核
- **状态：** complete
- 用户确认继续开发 WD14 网页接入。
- 本轮目标：结果图单图打标、精选图片批量打标、标签人工删改、确认写入 Anima caption，并保持 Krea 2 自然语言 caption 独立。
- 写入边界：WD14 结果先作为模型建议保存；不自动覆盖已有人工 caption，rating 只作分级信息，character 与 general 分区展示。
- 验收范围：API 与路径安全、旧项目兼容、批量部分失败、真实模型推理、桌面/手机交互、数据集 ZIP 回归。
- 主要风险：正式项目误写、同步批量推理阻塞、NSFW rating 混入训练 caption，以及前端重绘丢失尚未确认的编辑。
- 已完成现有数据结构与 API 审计：无需迁移 SQLite，将在结果资产 JSON 中增加非覆盖式 `wd14_tagging`；继续复用现有私有图片路径校验和项目保存机制。
- 已确定审核流程：模型原始结果保留，用户编辑保存为草稿；只有“确认用作 Anima caption”动作才写入 Anima 覆盖值，Krea 2 caption 不受影响。
- 已定位实现入口：`api.py` 结果图路由、`dataset_export.py` 资产更新、`creative_web.py` 结果画廊，以及 `tests/test_dataset_export.py` 数据集回归测试。
- 首次后端补丁因同一补丁中重复指定 `api.py` 被工具整体拒绝，未产生部分写入；改为按新模块、API 主体和辅助函数分开应用。
- 已新增 `dataset_tagging.py`：保存原始 WD14 结果、去重规范化审核草稿、确认写入 Anima caption，并保持其他 Profile caption 不变。
- 已增加单图打标、精选批量打标和审核确认 API；批量同步上限为 24 张，逐图返回 tagged/failed，不因单项失败丢失成功结果。
- 已增加领域与 API 回归测试，覆盖非覆盖式保存、草稿去重、确认写入、Krea 2 保留和批量部分失败。
- 首轮定向测试 4 项通过；ruff 仅发现测试模拟函数的未使用参数和异常消息字面量，共 3 项规范问题，已改为下划线参数和局部消息变量。
- 修正后定向验证通过：4 项 WD14 数据集测试、相关 ruff 和完整 `src` ty 检查均通过。
- 前端已加入 WD14 阈值工具栏、精选批量入口、单图打标按钮、rating/character 分区提示、可编辑草稿，以及保存草稿/确认 Anima 两步操作。
- 前端草稿输入会先同步到页面内项目状态，切换 Profile 或精选状态时不丢失；错误路径会恢复按钮并同时显示在结果图与数据集状态区。
- 前后端定向验证通过：数据集打标/导出/API 共 9 项测试通过，ruff、ty 与抽取后的完整前端 JavaScript 语法检查均通过。
- 已在 `/tmp/prompt-hub-v16-qa.eIRjBm` 的隔离库和 8766 端口完成真实模型验收：上传成人向女巫图、精选、WD14、确认 Anima、导出 ZIP 全部成功。
- 真实结果为 sensitive 98.3%、40 个 general、0 个 character；确认前 Krea 2 caption 保持独立，确认后 ZIP `.txt` 与 Anima 审核草稿一致。
- 实测发现 `grey_hair`/`white_hair` 同时出现，已作为人工审核必要性的真实样例记录，不增加自动静默删标规则。
- 已更新 README 与绘图工作流说明，移除“当前无自动打标”的旧描述，并写明单图/批量、阈值、草稿/确认和双 Profile 隔离顺序。
- 浏览器桌面首轮检查：页面标题、创作台和真实验收项目均正常；结果卡显示 sensitive 98%、阈值、CPU provider、原创 OC 无角色候选、审核草稿与“已确认到 Anima caption”。
- WD14 工具栏、单图重新打标、保存草稿、确认 Anima、精选批量和导出入口均在真实 DOM 中可见且语义清楚。
- 浏览器实际点击“重新运行 WD14”约 1 秒返回 43 个 general 标签，状态从旧确认值正确变为“尚未确认”，没有自动覆盖既有 caption。
- 人工从草稿删除 `white_hair` 后，“保存审核草稿”仍保持未确认；再点“确认用作 Anima caption”后状态变为已确认，Anima caption 不再包含该标签。
- 浏览器按可见 label 精确定位 `Caption Profile` 未匹配到内嵌 select；页面无运行错误，改用已有稳定元素 ID `#datasetProfile` 继续验证，不重复该定位方式。
- Krea 2 Profile 切换后仍显示原自然语言 caption；随后点击“打标全部精选”成功处理 1/1 张，只刷新 WD14 草稿为尚未确认，没有改写 Krea 2。
- 桌面截图确认 WD14 审核区、双确认按钮、阈值工具栏、Profile 与导出区层次清楚；浏览器控制台 0 warning/error。
- 浏览器支持临时 viewport override；将按项目既有验收规格使用 390×844，并在完成后恢复默认视口。
- 390×844 实测 `innerWidth=390`、`scrollWidth=375`，结果图库与 WD14 工具栏都降为单列，没有横向溢出；控制台仍为 0 warning/error。
- 手机端滚动截图确认草稿双按钮、general/character 阈值、批量按钮、Profile 与导出区均完整可读；临时 viewport override 已执行 reset。
- 已停止隔离 8766 服务，并将正式 8765 从旧进程平滑重启到新版进程 PID 72551。
- 正式服务健康正常，页面包含 WD14 工具栏/批量/确认入口；正式 SQLite `integrity_check=ok`，保留 33,631 条资料与 1 个现有创作项目。
- 完成前最终验证：43 项 pytest 全部通过，覆盖率 85.88%；ruff、ty、JavaScript 语法、Git diff、正式服务页面标记与模型文件检查均通过。
- 最终真实 CLI 推理为 CPU 约 0.695 秒，正确返回女巫帽、泳装、扫帚等标签；正式 8765 由 PID 72551 持续监听。

## 会话：2026-08-31（阶段 14）

### WD14 本地打标器安装
- **状态：** complete
- 用户确认安装 `SmilingWolf/wd-swinv2-tagger-v3`。
- 安装目标：模型独立保存在 `soda-person/models/wd14`，Prompt Hub 使用 ONNX Runtime；本轮只验证推理，不自动覆盖现有 caption。
- 预计下载约 467 MB ONNX 模型和约 308 KB 标签表；主要风险是 arm64 运行时兼容、预处理格式与标签类别映射。
- 环境检查：本机为 arm64，数据卷可用约 712 GiB；现有项目未安装 `onnxruntime`，也尚无 `soda-person/models` 目录。
- 已核对官方 Space 推理实现：透明图先铺白底、白色补方、448×448 bicubic、RGB 转 BGR、float32 NHWC，再送入 ONNX。
- 模型文件下载完成：`model.onnx` 446 MiB、`selected_tags.csv` 301 KiB；SHA-256 已记录。
- ONNX Runtime 1.29.0 成功加载模型；输入为动态 batch × 448 × 448 × 3 float，输出为 10,861 标签，CoreML 与 CPU provider 均可用。
- 项目 CLI 暂无图片打标入口；决定补一个最小 `prompt-hub tag-image`，用于安装验收和后续 V1.6 复用，不在本轮增加网页批处理界面。
- 首轮静态检查：WD14 单元测试 2 项通过，但 ruff 报参数数量，ty 报 ONNX 稀疏输出联合类型和标签字典类型过宽；已增加输出类型检查、TypedDict，并按同类领域函数豁免参数数量。
- 第二轮 ty 仍不能为 `sorted(TypedDict, key=float)` 匹配重载；改用 NumPy 概率索引降序后构造标签结果，避免重复同一类型写法。
- 第三轮 ty 要求空列表显式绑定 `list[ScoredTag]`；已补充局部类型注解，逻辑不变。
- 首次真实图片推理时 CoreML provider 只支持 2580 个节点中的 1221 个，并在执行分区时失败；模型可正常加载，问题属于该 ONNX 图的 CoreML 兼容性。
- 将 `auto` 明确改为 CPU provider，避免用户看到运行时崩溃；显式 `--provider coreml` 仍保留用于未来运行时版本复测。
- CPU provider 真实推理成功：1024×1536 图片首次加载加推理约 0.684 秒，正确输出女单人、女巫帽、白色比基尼、扫帚、蓝眼、全身等标签，character 为空且未误报。
- 已补充 CLI 回归测试、README 使用命令和模型目录内 `MODEL_INFO.md`；命令默认只输出 JSON，不写 sidecar。
- 完成前全量验证：39 项 pytest 全部通过，覆盖率 86.08%；ruff 与 ty 均通过。
- 再次使用真实图片和 `auto` provider 验证成功，实际采用 CPUExecutionProvider，耗时约 0.928 秒；输出的泳装、女巫帽、扫帚等标签与画面一致。
- 正式网页服务 `/api/health` 返回正常；本轮安装未改写正式数据库、原图或已有 caption。
- 下一阶段边界明确为 V1.6 网页单图/批量打标与人工审核；当前安装阶段不自动覆盖数据集文本。

## 会话：2026-08-31（阶段 13）

### V1.5 结果精选与数据集导出
- **状态：** complete
- 已确认下一步聚焦本地绘图闭环：从生成结果中精选图片，形成可转交 Windows 训练机的数据集包。
- 已审计结果图保存在私有 `test-results/prompt-hub` 目录，项目 JSON 已记录 `result_assets`；现有导出只覆盖项目 JSON，尚无图片与 caption 数据集包。
- 本轮范围：精选状态、单图 caption 覆盖、Anima/Krea 2 Profile、ZIP + manifest、前端入口、测试与本机部署。
- 明确延后：Windows SSH、自动远程传输、视频提示词流程。
- 两次规划补丁因阶段标题和错误日志文字与预期不一致而整体未写入；读取现状后改为分文件更新，未影响业务代码。
- 审计命令误读了不存在的 `creative_profiles.py`；Profile 实际位于其他模块，后续按定义检索，不再凭文件名猜测。
- 已定位 Profile 编译器：Anima `positive` 是逗号标签，Krea 2 `positive` 是连贯描述，可直接作为各自默认 caption。
- 确定 caption 覆盖按 Profile 分开保存为 `dataset_captions`，避免 Anima tags 与 Krea 2 自然语言互相污染。
- 首次后端静态检查发现新导出函数复杂度、异常消息与一处未使用变量不符合项目规则；已拆成选择、准备、manifest、写包四个小函数，并按现有中文领域模块配置异常规则。
- 新增数据集测试首次 lint 只有一行 103 字符超限；已按项目 100 字符规则拆行，不放宽测试规则。
- 后端、前端、使用说明与页面标记已完成；全量验证为 36 项 pytest 通过、覆盖率 87.80%，ruff 与 ty 均通过。
- 浏览器 QA 将使用 `/tmp/prompt-hub-v15-qa.bu8K51` 隔离资料库与 8766 端口；测试上传只读取现有 Kisega 图片，不改正式项目和资料库。
- 浏览器首次上传误用了普通 Playwright 的 `locator.setInputFiles`，插件明确要求 file chooser 流程；调用未发生上传，已读取专用说明后改用 `waitForEvent("filechooser")` + `chooser.setFiles`。
- 隔离浏览器已完成两图导入、单图精选、Anima 单图 caption 保存、Krea 2 Profile 切换与 ZIP 导出；界面显示只导出 1 张，控制台 0 warning/error。
- ZIP 实体复核通过：只包含 1 张精选原图、同名 `.txt` 和 `manifest.json`；Krea 2 caption 为项目自然语言，manifest 标记 `caption_source=profile`。
- 390×844 响应式检查为 `innerWidth=390`、`scrollWidth=375`，两张结果卡与导出面板均为单列，控制台 0 warning/error。
- 浏览器插件不支持普通 Playwright 的 `isDisabled`、`scrollIntoViewIfNeeded` 和 `playwright.screenshot`；均未影响业务动作，改用 DOM 状态、页面滚动和 tab screenshot 取证。
- 正式 8765 已重启加载 V1.5；页面入口、导出目录、Qwen3 14B 加载状态、正式数据库 `integrity_check=ok` 与 404 路径保护均通过。
- 完成前重新执行全量验证：36 项 pytest 全部通过、覆盖率 87.80%，ruff、ty、前端 JavaScript 语法、正式健康接口、数据库完整性与 Git diff 检查均为成功状态。

## 会话：2026-08-30

### 阶段 0：规划与基线冻结
- **状态：** complete
- 执行的操作：
  - 对比 Prompt Hub 与绘梦台的产品定位和首次使用路径；
  - 明确绘图优先、MiniMax H3 视频延后；
  - 确定统一创作项目、七槽位和模型 Profile 架构；
  - 拆分八个绘图开发阶段及验收条件。
  - 审计项目结构、FastAPI 路由、SQLite 数据表、MCP 工具与现有测试；
  - 运行完整 pytest、ruff 和 ty 基线检查。
  - 读取正在运行的真实服务健康、统计、来源、检索样例和 OC 世界接口；
  - 写入 API、数据库、MCP、页面行为和回归检查清单。
- 创建/修改的文件：
  - `DEVELOPMENT_PLAN.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
  - `BASELINE.md`
- 未修改：
  - 业务代码；
  - 数据库；
  - 本地提示词和视觉资料；
  - OC Manager 数据；
  - Git 历史与远程仓库。

## 测试结果

| 测试 | 输入 | 预期结果 | 实际结果 | 状态 |
|------|------|---------|---------|------|
| 规划范围检查 | 用户需求与现有功能 | 绘图主线完整、视频延后 | 已写入开发计划 | 通过 |
| 文件边界检查 | 本轮修改 | 只新增规划文档 | 未修改代码和数据 | 通过 |
| pytest 基线 | 现有完整测试集 | 所有测试通过且覆盖率不低于 80% | 13 passed，覆盖率 86.44% | 通过 |
| ruff 基线 | 全项目 | 无 lint 错误 | All checks passed | 通过 |
| ty 基线 | `src/` | 无类型错误 | All checks passed | 通过 |
| 真实服务只读检查 | health/stats/sources/search/OC worlds | 服务和现有资料可读取 | 33,631 条、4 来源、OC 为空 | 通过 |
| 阶段 1 pytest | 修改后完整测试集 | 无回归 | 13 passed，覆盖率 86.44% | 通过 |
| 阶段 1 ruff/ty | 全项目与 `src/` | 无 lint/类型错误 | 两项均通过 | 通过 |
| 示例任务 | 维多利亚军装 × 黄昏图书馆 | 打开真实检索结果 | 返回 2 条结果 | 通过 |
| 桌面导航 | 四个顶级入口 | 页面状态正确切换 | 全部通过 | 通过 |
| 手机布局 | 390×844 | 四个入口可见且无横向溢出 | 2×2 导航、无溢出 | 通过 |
| 浏览器控制台 | 首页与各入口 | 无 warning/error | 空 | 通过 |
| 8765 主服务 | 新版首页与真实资料库 | 首页可见、统计正确 | 33,631 条、4 个导航入口 | 通过 |
| 绘图 V1 pytest | 完整测试集 | 无回归、覆盖率不低于 80% | 19 passed，覆盖率 88.32% | 通过 |
| 绘图 V1 ruff/ty | 全项目与 `src/` | 无 lint/类型错误 | 两项均通过 | 通过 |
| SQLite 完整性 | 真实主库 | `integrity_check=ok` | ok；33,631 条资料、1 项目、1 配方 | 通过 |
| 七槽位锁定 | 连续输入后立即锁定角色 | 输入不丢失、自动保存 | 角色保留，保存到 R2 | 通过 |
| 成人分级 | Adult 项目 | negative 不含固定 `nsfw/nude` | 只保留质量规避词 | 通过 |
| 双 Profile | 同一项目切换 Anima/Krea 2 | 输出形态不同 | 标签版与自然语言版均生成 | 通过 |
| 资料进入创作 | 视觉卡选择服装槽位 | 文字与图片参考进入项目 | 1 个本地视觉参考，保存到 R5 | 通过 |
| 本地模型确认流 | Qwen3 14B + 锁定角色 | 只预览，确认后改未锁定项 | 约 60 秒成功，角色未变，保存到 R6 | 通过 |
| 手机创作台 | 390×844 | 七槽位可用且无横向溢出 | 390/390，0 error / 0 warning | 通过 |
| 8765 主服务 | 正式端口加载绘图 V1 | 项目、参考、模型正常 | R6 项目、7 槽位、1 参考、9 文本模型、0 控制台错误 | 通过 |

### 阶段 1：导航与第一次使用
- **状态：** complete
- 执行的操作：
  - 确定采用“渐进拆分现有前端资源，再增加开始创作入口”的实现顺序。
  - 通过本机浏览器记录改造前 DOM 与窄屏视觉基线。
  - 新增全局中文导航、默认“开始创作”首页、三步绘图说明和独立资料管理页；
  - 将 Prompt 与 OC 的既有检索入口放入清晰的顶级导航；
  - 在首页展示 Anima/Krea 2 首批目标和本地资料状态；
  - 增加首页关键内容的 API 页面回归断言；
  - 运行修改后的完整 pytest、ruff 和 ty 检查。
  - 在 8766 独立测试实例验证桌面首页与四个顶级导航入口。
  - 将手机导航调整为两行四格，并验证 390px 无横向溢出；
  - 把 Type、Safety、Source 收入默认折叠的高级筛选；
  - 增加可打开真实检索结果的维多利亚军装示例任务；
  - 增加页面描述与内联 favicon；
  - 验证示例返回 2 条真实结果，高级筛选可展开，控制台无 warning/error。
  - 完成最终 pytest、ruff、ty 与独立服务健康检查；
  - 停止 8766 测试实例，将已验证版本切换到 8765 主服务；
  - 刷新用户当前页面，确认首页、真实统计和导航正常，控制台无错误。
- 创建/修改的文件：
  - `src/prompt_hub/web.py`
  - `tests/test_api.py`
  - `progress.md`
- 下一阶段：
  - 在进入七槽位编辑器前抽取静态资源，避免继续扩大 `web.py`；
  - 设计 CreativeProject 数据表与七槽位编辑器。

### 阶段 2–7：绘图 V1 创作闭环
- **状态：** complete
- 执行中的操作：
  - 用户确认阶段 1 体验明显改善，授权继续完成绘图 V1；
  - 采用新增领域模块和增量建表方式，保护既有 33,631 条资料；
  - 先备份真实 SQLite，再在测试数据库验证项目、配方和双 Profile。
  - 已创建 23MB 迁移前备份并通过 SQLite 完整性检查；
  - 已确认 LM Studio 本机接口和 10 个模型可发现，主站 8765 正常。
  - 新增 CreativeProject 与 Recipe 增量表、项目 API、双 Profile 编译与标准 JSON 导出；
  - 完成七槽位、逐项锁定、项目级成人分级、自动保存与恢复；
  - 完成提示词/视觉卡片加入指定槽位及资料篮；
  - 完成 OC 角色进入创作、角色 Prompt 与 gallery 参考映射；
  - 完成配方、生成参数、结果图路径/链接和实测备注；
  - 接入 LM Studio 模型发现、锁定保护、建议预览与确认应用；
  - 实测 Qwen3 14B 约 60 秒返回并写入未锁定槽位，Gemma 4 12B 首次调用超时后调整默认策略；
  - 桌面端验证成人项目不会错误加入 `nsfw/nude` negative，Krea 2、配方和资料引用闭环正常；
  - 390×844 手机端无横向溢出，控制台 0 error / 0 warning；
  - 清理一个由本轮创建且内容为空的测试项目，保留完整“黄昏图书馆调查员”示例项目与配方；
  - 新增 `DRAWING_V1_GUIDE.md`，说明日常顺序、OC、LM Studio 与 Windows 手动交付。
- 创建/修改的文件：
  - `src/prompt_hub/creative.py`
  - `src/prompt_hub/local_model.py`
  - `src/prompt_hub/creative_web.py`
  - `src/prompt_hub/api.py`
  - `src/prompt_hub/web.py`
  - `tests/test_creative.py`
  - `tests/test_api.py`
  - `README.md`
  - `DRAWING_V1_GUIDE.md`
  - `pyproject.toml`
- 未完成的外部连接：
  - 两台 Windows 的局域网自动发送、ComfyUI workflow 启动与结果回传；需要设备固定地址及共享目录/SSH/代理方式。

### 阶段 9：V1.1 本地智能取材
- **状态：** complete
- 已执行：
  - 用户确认开始实现“本地资料库智能取材”；
  - 首轮前端与相关性测试发现一处测试断言超过项目行宽，已拆行后继续验证；未涉及运行逻辑。
  - 相关性单测首次运行时，最小测试资料树缺少 `reading` 卡片，导致候选为空；已给测试夹具补充动作与发型样本，用来验证“精确动作优先、发型词不误命中瞳色”。
  - 审计现有 FTS 查询、资料类型、分类、成人分级与真实搜索样例；
  - 确认采用“即时词典检索 + 可选本地模型扩展 + 用户逐项确认”的实现顺序；
  - 确认多词 FTS 的 AND 行为需要短语搜索和单词回退。
  - 新增七槽位检索编排、成人分级过滤、分类亲和排序、精确动作优先和视觉/收藏加权；
  - 新增 `/api/creative/source` 与 `/api/creative/source/expand`，模型只扩展检索词；
  - 创作台新增“从本地库智能取材”、分槽候选卡、图片、命中词、来源依据与确认加入按钮；
  - 8766 真实库实测：现有成人项目即时返回 23 条候选、9 张图片，锁定角色槽位未检索；
  - Qwen3 14B 后台扩展成功，页面保持本地候选先可用，浏览器无 warning/error；
  - 实际加入 1 张 Kisega 服装视觉参照，文字进入服装槽位、图片进入参考区，项目保存为 R8；
  - 390×844 验证布局改为单列，`innerWidth=390`、内容宽 375，无横向溢出。
  - 全量验证通过：26 项 pytest、88.74% 覆盖率、ruff、ty、SQLite `integrity_check=ok`；
  - 停止 8766 测试服务，将验证版本切换到 8765；正式端口健康检查、取材接口、项目 R8、9 个本地模型与浏览器 0 warning/error 均复查通过。

### 阶段 10：V1.2 结果图复盘与配方迭代
- **状态：** complete
- 已执行：
  - 用户实测 V1.1 可用并授权继续下一步开发；
  - 确定继续绘图主线，不提前开发 Windows SSH 或 MiniMax H3；
  - 将下一步定义为结果图本地导入、视觉复盘、七槽位改进建议和确认写回。
  - 审计确认 LM Studio 已安装 6 个 VLM，其中 Gemma 4 12B Heretic 当前已加载，Qwen3.5 9B 视觉模型已安装但未加载；
  - 审计确认现有项目仅记录结果图路径，尚无私有图片存储、缩略图或视觉分析 API；
  - 确定使用原始图片字节上传，避免引入 `python-multipart`，并将用户结果图与公共资料媒体分离。
  - 首次结果媒体补丁因附带不存在的 pyproject 匹配行而整体未应用；确认无部分改动后拆分并重新执行。
  - 结果媒体首轮 lint 报告类型导入、领域异常消息和测试全角标点；已按项目既有规则调整，不放宽全局检查。
  - 首次前端大补丁因截断输出中的重复行假象而匹配失败；确认无部分应用后按精确文件内容重新执行。
  - 新增项目私有结果图存储、原图/缩略图路由、视觉分析 API 与确认写回 API；
  - 新增创作台结果图库、视觉模型选择、七槽位观察、优缺点、改进建议和双 Profile 反推 Prompt 预览；
  - 确认写回只补充空且未锁定槽位，已有槽位与锁定槽位保持不变；
  - 定向验证通过：JavaScript 语法检查、ruff、ty，以及结果媒体/创作/API 共 13 项测试。
  - 使用真实 SFW Kisega 服装图调用已加载 Gemma 4 12B Vision，180 秒未返回并触发预期超时；
  - 根据既定模型分工，将复盘默认项改为 Qwen3.5 9B Uncensored，Gemma 4 12B 保留为手动选项。
  - Qwen3.5 9B 首次视觉请求立即返回 HTTP 400；发现旧本地请求封装未读取错误正文，已增强诊断信息后再继续定位。
  - 改进后的诊断确认失败原因是 24GB 机器上已有 Qwen 14B + Gemma 12B 驻留，LM Studio 保护机制拒绝再加载约 11.51GB 的 Qwen3.5 9B；模型文件与视觉协议本身未报错。
  - 临时卸载 Qwen 14B 后，Qwen3.5 9B 以 4096 context、parallel 1 成功加载，占用约 9.73 GiB；
  - 首版 1400-token 完整视觉复盘仍在 180 秒超时；已将图片缩至 1024、输出限制为 700 tokens，并约束每项长度后继续验证；
  - 压缩版请求返回空正文；查阅 LM Studio 官方说明后确认 `/no_think` 应放在用户 Prompt 末尾，已修正视觉消息模板；
  - 等待过程中一次轮询工具参数引号误写，未影响正在运行的模型请求，已更正后取得真实超时结果。
  - 移动 `/no_think` 时发现字符串拼接逗号位置错误，未进入服务运行；已修正并先执行语法检查。
  - 单独加载 Qwen3.5 9B 后完成第二次真实图片调用：约 72 秒结束，但正文为空、无法解析 JSON；确认下一步采用 LM Studio 官方 JSON Schema 结构化输出，而非继续盲目增加 token。
  - 更新进度文档时首次补丁因标题层级与预期不一致而未应用；定位实际 `###` 标题后重新写入。
  - 首次合并前端提示补丁因 `lmStatus` 实际文案与上下文不一致而未应用；重新读取精确片段后分段更新。
  - JSON Schema 版本真实图片调用约 124 秒后仍为空正文；复查多模态顺序发现图片块位于 `/no_think` 之后，已改为图片在前、末尾文字指令在后。
  - 专项测试 4 项通过，但单文件运行被全项目 80% coverage 门槛标红；这是测试选择造成的覆盖率不足，需以最终全量测试结果为准。
  - 将视觉复盘改为 LM Studio 原生 `/api/v1/chat`，显式设置 `reasoning: off`、`store: false`；避免社区微调忽略控制词并把输出预算全部用于隐藏推理。
  - 等待视觉调用时一次轮询参数引号写错，工具调用本身未执行；已用正确参数继续读取原会话，没有影响模型任务或文件。
  - 原生 Chat 首次请求返回 `Expected 'text' | 'image'`；本机 0.4.20 实际输入判别值为 `text`，已将文档描述中的 `message` 改为服务端接受的字段。
  - 原生 Chat + `reasoning: off` 真实图复盘成功：Qwen3.5 9B Q8 约 63 秒返回完整七槽位、优缺点、改进建议与 Anima/Krea 2 双格式反推。
  - 首次批量补 README/使用指南/测试记录时补丁上下文未匹配，确认未部分应用后拆为精确片段完成。
  - 首次从 Python 常量管道检查 JavaScript 时，开头空行使 `removeprefix` 未移除 `<script>`；改为先 `strip()` 后再检查。
  - 新增 4 条页面标记断言后触发单测试函数 52 statements 限制；合并为一条 `all(...)` 断言，不放宽 lint 规则。
  - 全量验证通过：30 项 pytest、87.15% 覆盖率、ruff、ty、JavaScript 语法与 SQLite `integrity_check=ok`。
  - 8766 临时资料库完成浏览器端到端验收：真实复盘约 60 秒返回，双 Profile Prompt 可展开，“只写入实测备注”成功且锁定角色保持不变。
  - 390×844 手机验收无横向溢出，结果图/槽位/诊断均为单列，桌面与手机控制台均为 0 warning/error。
  - 浏览器截图首次误用 `tab.playwright.screenshot`，发现当前 API 实际为 `tab.screenshot`；改用正确接口后取得桌面和手机视觉证据。
  - 停止并关闭 8766 临时 QA 服务；永久删除临时目录的命令被安全策略拒绝，未绕过，交由系统清理。
  - 卸载临时 Qwen3.5 9B Vision，恢复日常 `qwen3-14b-abliterated`（4096 context、parallel 1，约 9.79 GiB）。
  - 正式 8765 已启动 V1.2；健康接口、页面新功能标记、本地模型状态、正式数据库完整性与浏览器控制台均复查通过。

### 阶段 11：V1.3 创作版本链与下一轮分支
- **状态：** complete
- 已执行：
  - 用户确认继续下一步开发；
  - 继续绘图主线，Windows SSH 与 MiniMax H3 保持延后；
  - 确定 V1.3 解决“复盘后继续修改会覆盖同一项目”的问题，建立独立于保存 revision 的创作 iteration；
  - 确定新版本保留槽位、锁定、参考和生成参数，清空旧结果图，并记录父项目、源结果图和复盘摘要。
  - 审计确认现有项目表无 lineage 列，项目列表的 `R` 仅表示保存 revision；配方则保存完整项目导出快照。
  - 确定采用可重复 `lineage_json` 增量迁移，旧项目默认视为 V1，新分支独立创建项目且不修改父项目。
  - 新增 `lineage_json` 可重复迁移、项目 lineage 读写、下一版构造逻辑与结果图 branch API；
  - 新增旧数据库迁移和结果图分支测试，确认参数/锁定/参考保留、旧结果图不复制、父项目原图仍可访问；
  - 定向 ruff、ty 与 11 项创作/复盘测试通过。
  - 创作台项目列表新增 V/R 双标识，派生项目新增版本来源提示与来源图入口；
  - 视觉复盘面板新增“由此创建下一版”，成功后自动切换到独立 V2/V3；
  - 使用文档补充版本分支顺序与 V/R 区别，并增加 V2→V3 链路及导出 lineage 测试；
  - 首次批量补测试与文档时，同一文件中的补丁片段顺序逆向导致上下文匹配失败；确认未部分应用后按行号顺序重排并完成。
  - V1.3 完整静态与回归检查通过：JavaScript 语法、ruff、ty、32 项 pytest，覆盖率 87.41%。
  - 浏览器验收采用独立资料库与固定复盘响应，只验证 V1→V2 页面闭环，避免重复加载视觉模型或污染正式数据。
  - 8766 隔离库已建立 V1 测试项目并导入真实 WebP 视觉参照；初始状态为 V1/R1，含锁定角色、参考、Steps/CFG/Seed 与旧结果路径。
  - 浏览器已通过首页入口进入创作台；项目卡和保存状态正确显示 V1/R2，锁定、参考、参数与结果图均按隔离数据渲染，页面无空白或错误覆盖层。
  - 首次点击“由此创建下一版”后，自动化等待预期成功文案超时；未重复点击，先检查当前页面与服务状态，防止误建多个分支。
  - 现态确认分支实际成功，页面真实提示为“已创建 V2”；V2/R1、来源图、锁定角色、1 条参考、Steps 28、CFG 5.5、Seed 123 均保留，旧结果图路径与图库均已清空，控制台无 warning/error。
  - 390×844 手机验收通过：页面宽 390、内容滚动宽 375，无横向溢出；V2 来源提示、单列槽位和空结果区均正常，控制台无 warning/error。
  - 隔离库 API 复核确认 V2 lineage、V1/V2 数据边界与来源原图 HTTP 200；SQLite `integrity_check=ok`，随后正常停止 8766 测试服务。
  - 正式数据库迁移前完整性为 `ok`；已用 SQLite 在线备份生成 `prompt-library-pre-v13-lineage-20260831.sqlite`（约 23MB），备份完整性同样为 `ok`。
  - 旧 8765 服务已正常停止，新版本服务完成启动并执行正式库增量迁移，进程保持运行。
  - 正式健康接口、V1.3 页面标记、旧项目读取、`lineage_json` 字段与 SQLite 完整性均通过；读取本地模型状态时首次 jq 假定了错误 JSON 形状，需按真实响应调整。
  - 按真实响应复核：日常 `qwen3-14b-abliterated` 仍保持加载；正式资料库 4 个来源、33,631 条条目均可读取，迁移未改变既有统计。
  - 正式 8765 浏览器复核通过：旧项目显示 V1/R12，页面标题和主流程正确，控制台 0 warning/error。
  - 完成前整体验证首次运行时，测试与服务断言已通过，但 SQLite 字段检查误用仅 trigger 可用的 `RAISE()`，整条验证未完成；修正检查脚本后从头重跑。
  - 修正后完整完成前验证通过：JavaScript 语法、ruff、ty、32 项 pytest（87.41%）、正式健康与页面标记、旧项目 lineage 兼容、Qwen3 14B 加载状态、正式库与备份完整性全部通过。

### 阶段 12：V1.4 版本对照与建议应用
- **状态：** complete
- 已执行：
  - 用户确认继续开发；
  - 继续绘图主线，Windows SSH 与 MiniMax H3 保持延后；
  - 确定补齐 V1.3 之后的使用缺口：父版本对照、槽位变化和显式应用复盘建议；
  - 确定不新增数据库列，仍使用 lineage JSON，并严格保护锁定槽位和已有内容。
  - 审计确认单项目 GET API 已存在且有 404 测试，不需要新增端点；V1.4 只需复用它读取父项目。
  - 审计确认 `next_iteration_values` 目前只保存摘要、问题、改进和双 Profile Prompt，尚未保存 `observed_slots`；这是建议应用缺少结构化来源的直接原因。
  - 前端当前只有一行 lineage notice，没有父项目状态、差异数据或建议应用状态；最近项目只加载 30 条，不能单纯依赖列表查父项目。
  - 确定后端提供 iteration context 与显式 apply 端点：context 负责父版本缺失降级和槽位差异，apply 复用领域保护规则并返回实际应用槽位。
  - 首次后端整块补丁因 `reconstructed_prompts` 邻近上下文与真实缩进不一致而校验失败；确认未部分应用，改为读取精确行号后拆分更新。
  - V1.4 后端领域逻辑、iteration context/apply API 与首轮测试已加入；13 项定向业务断言全部通过。
  - 定向检查发现复盘端到端测试达到 57 statements，超过项目 50 上限；同时两个文件的定向 pytest 因全局覆盖率门槛标红，需拆分测试并以最终全量覆盖率为准。
  - 拆分测试后完整后端验证通过：34 项 pytest、87.85% 覆盖率、ruff 与 ty 均通过。
  - 派生项目新增“本轮迭代对照”：只显示有变化或有复盘观察的槽位，并展示上一版、当前版、建议值和保护状态。
  - 新增显式“确认填入空槽位”操作；服务端再次校验空值与锁定，重复点击不会继续改写。
  - README、绘图使用指南、开发计划和页面标记测试已补充 V1.4 工作流。
  - 8766 隔离库已建立 V1/V2 验收数据：角色锁定、服装已有且视觉建议故意冲突，动作已修改，灯光为空且有可应用建议，用于验证保护边界。
  - 首轮桌面浏览器验收确认版本、摘要、建议、冲突值和按钮均正确，控制台无 warning/error；但因视觉模型通常返回七槽位，原筛选仍展示 7 行，需进一步隐藏“建议值等于当前值”的未变化项。
  - 更新隔离服务后直接 reload 会回到默认首页，自动化等待“本轮迭代对照”超时；页面当前视图不写入 URL，改为按真实路径重新进入创作台。
  - 收紧筛选后桌面对照由 7 行降为 4 行：角色冲突、服装冲突、动作变化和灯光建议，符合预期。
  - 点击“确认填入 1 个空槽位”后等待稳定成功提示超时；未重复点击，先核对实际字段与异步刷新，排查提示被 context 重绘覆盖的问题。
  - 现态确认首次应用实际成功：只写入 lighting=`warm rim light`，锁定角色、已有服装和动作均保持不变，按钮转为禁用，控制台无 warning/error。
  - 将应用结果消息写入项目级前端 state 后复验通过；“已填入：灯光。”在异步 context 刷新后仍稳定显示。
  - 390×844 手机验收通过：`innerWidth=390`、`scrollWidth=375`，对照行降为单列 269px，无横向溢出；4 条对照和成功提示可读，控制台无 warning/error。
  - 隔离 API 复核确认父 V1 仍为 R1 且角色/服装/灯光完全未变；V2 只新增 lighting 和应用记录，再次可应用槽位为空，SQLite `integrity_check=ok`。
  - 已恢复浏览器默认视口并关闭隔离测试标签页。
  - 正式 8765 已重启加载 V1.4；健康接口、页面标记、旧 V1/R12 项目兼容、Qwen3 14B 加载状态与数据库完整性均通过。
  - 正式浏览器复核确认旧 V1 不显示迭代面板，页面标题与保存状态正确，控制台 0 warning/error。

## 错误日志

| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| 2026-09-01 | M5 新增 `comfy_results.py` 首轮 Ruff 报告领域异常消息、动态 JSON 类型与正则别名 | 1 | 沿用现有领域模块的有限 per-file ignore，并将 `re.I` 改为 `re.IGNORECASE`；随后重新执行完整静态检查 |
| 2026-09-01 | Pillow 的 `Image.info` 类型允许 tuple key，ty 不接受直接传给字符串键元数据解析器 | 1 | 在读取图片信息时显式将 key 规范化为字符串，不改变元数据值 |
| 2026-09-01 | M5 路由首轮 Ruff 报告 import 排序与关联 helper 6 参数复杂度 | 1 | 修正 import 顺序，并仅对该领域路由沿用现有 API helper 的参数数目例外 |
| 2026-09-01 | ComfyUI 多节点提取器在加入正负 Prompt 连线识别后超过默认复杂度阈值 | 1 | 保持集中式节点解析以便核对 workflow，只对该领域模块增加复杂度例外，测试覆盖各参数分支 |
| 2026-09-01 | ty 无法从 HTTP 异常转换 helper 的 `None` 返回类型推断路由必定中止 | 1 | 将 helper 明确标注为 `NoReturn`，与现有 LoRA 路由保持一致 |
| 2026-09-01 | M5 前端首个整块补丁因预期存在重复变量、实际仅一行而整体未应用 | 1 | 确认无半成品文件后，改为先新增独立页面文件，再按精确锚点接入导航和页面组合 |
| 2026-08-30 | 更新进度日志时批量补丁目标行位置不匹配 | 2 | 停止批量补丁，读取当前文件并按段落分别更新 |
| 2026-08-30 | 浏览器中“KREA 2”同时匹配 Profile 与导出按钮 | 1 | 改用 Profile 数据属性精确定位 |
| 2026-08-30 | Gemma 4 12B Heretic 在双模型已加载状态下 120 秒未返回 JSON | 1 | 默认优先当前已加载文本模型，缩短输出并限制等待时间 |
| 2026-08-30 | V1.1 首次批量更新规划文件时补丁段落归属错误 | 1 | 读取精确位置后按文件分别更新 |
| 2026-08-30 | V1.1 首轮取材测试过滤掉测试库 `dress` 分类并出现 lint 细节 | 1 | 补充精确分类亲和词，修正长行和标点 |
| 2026-08-30 | 文档检索命令引用不存在的 `docs/*.md`，zsh 未执行后续读取 | 1 | 改用 `rg --files` 确认真实路径后读取 |
| 2026-08-30 | 精确动作排序测试的最小资料树缺少 `reading` 条目 | 1 | 补充专用测试样本，保留严格断言 |
| 2026-08-30 | 共享测试资料夹新增样本导致 importer 旧数量断言失败 | 1 | 撤回共享夹具变更，在单项测试内建立独立来源 |
| 2026-08-30 | 运行时检查请求 `/health` 得到 404 | 1 | 确认项目真实端点为 `/api/health` 后重新检查 |
| 2026-08-30 | 专用测试数据构造有两行超过 100 字符 | 1 | 按项目格式拆为多行构造，不改变测试语义 |
| 2026-08-31 | V1.3 浏览器分支后等待“已从 V1 创建 V2”超时 | 1 | 不重复点击，先读取现态与请求日志，区分文案偏差和真实失败 |
| 2026-08-31 | 正式服务模型状态 jq 将对象误当数组 | 1 | 先查看 API 顶层结构，再按 `models` 字段读取，不影响服务或模型 |
| 2026-08-31 | 首次正式 stats 摘要使用了不存在的顶层字段 | 1 | 查看真实键后按 `entries`、`sources` 与嵌套 `oc_manager` 读取 |
| 2026-08-31 | 完成前 SQLite 字段断言误用 trigger 专用 `RAISE()` | 1 | 改用字段计数加 shell `test`，从头重新执行完整验收 |
| 2026-08-31 | V1.4 首次后端整块补丁上下文不匹配 | 1 | 确认未部分应用，按精确行号拆分 lineage review 与新领域函数补丁 |
| 2026-08-31 | V1.4 复盘端到端测试超过 50 statements | 1 | 将 iteration context/apply 场景拆成独立 API 测试，不放宽 lint 规则 |
| 2026-08-31 | 两文件定向 pytest 未达到全项目 80% coverage | 1 | 定向断言已通过，最终运行全部测试确认真实覆盖率 |
| 2026-08-31 | V1.4 隔离页 reload 后等待迭代标题超时 | 1 | reload 会回首页，改为重新点击“新建或继续绘图项目”后验收 |
| 2026-09-01 | M4 首次整块补丁因路由参数上下文不匹配被拒绝 | 1 | 确认无部分应用，读取实际文件后拆分为领域、路由与 API 小补丁 |
| 2026-09-01 | 隔离 LoRA 页按 label 读取 textarea 超时 | 1 | 先检查可见 DOM，确认保存已完成，再用唯一 ID 的只读页面状态核对 |
| 2026-08-31 | V1.4 应用建议后成功提示未稳定出现 | 1 | 不重复应用，先检查字段与按钮状态，再修正异步重绘提示生命周期 |

## 五问重启检查

| 问题 | 答案 |
|------|------|
| 我在哪里？ | 阶段 12 / 绘图 V1.4 版本对照与建议应用已完成并部署 |
| 我要去哪里？ | 先体验复盘→分支→对照→确认填入；Windows 自动传输和 MiniMax H3 继续延后 |
| 目标是什么？ | 建成本地优先、引导式、多模型兼容的绘图创作中枢 |
| 我学到了什么？ | 见 `findings.md` |
| 我做了什么？ | 完成父版本对照、冲突展示、安全建议应用、桌面/手机验收并部署到 8765 |

---

*每个阶段完成后或遇到错误时更新。*

### 阶段 23：V2.3 Windows worker 与 ComfyUI 最小闭环
- **状态：** in_progress / 等待 Windows 真实自检与首张回传图
- 已执行：
  - 用户确认 Windows Python 3.12.10 与本机 ComfyUI `http://127.0.0.1:8188` 已就绪。
  - 新增 stdlib-only `windows_worker.py`，实现单实例锁、outbox 原子领取、单 GPU 串行执行、processing 重启恢复与结果幂等清理。
  - 定义 `soda-comfyui-package-v1`：生成包必须包含 workflow ID 与 ComfyUI API Format `api_prompt`。
  - 实现 `/prompt` 提交、`/history/{prompt_id}` 轮询、`/view` 图片下载、超时中断和取消标记。
  - 成功时回传图片、API workflow、run log、源哈希与输出 SHA-256；失败时回传错误信封与 traceback 文件。
  - Mac 新增 returned task integrity API，校验 result/protocol/task type、源 manifest、输出归属、大小与 SHA-256。
  - Mac 新增 queued/running 任务取消 API；设备页增加“取消任务”和“校验回传”操作。
  - 新增 worker mock ComfyUI 自动测试，覆盖成功闭环、原子领取、路径越界、manifest 篡改、重启续查、幂等清理和单实例锁。
  - 定向验证通过：12 项测试、Ruff 与 ty 均通过。
  - Windows 双击启动包与中文说明已复制到 `/Volumes/PromptHub-5060Ti/prompt-hub/worker`；复制后源码 SHA-256 与 Mac 一致。
  - 当前等待用户在 Windows 双击 `1-先自检.bat`，随后启动常驻 worker；Mac 尚未收到 `worker-status.json`，因此未虚报真实 ComfyUI/GPU 验收。
  - Windows 启动 worker 后，主机与 445 端口仍在线，但 Mac 原 SMB 挂载的任何目录读取稳定卡住；该异常发生在 worker 持有共享根 `worker.lock` 后，先要求停止 worker 以验证因果。
  - 为避免跨 SMB 文件锁影响 Finder，单实例锁已改为 Windows 本地 `%LOCALAPPDATA%\\PromptHub`；首次测试通过改写 `os.name` 模拟 Windows，导致 macOS `pathlib` 尝试实例化 `WindowsPath`，改为用 `sys.platform` 判断并记录此测试错误。
  - 加固生成包边界：`generation_package` 必须出现在任务 manifest 中并先通过 SHA-256 验证，不能用未登记文件绕过完整性检查。
  - 设备诊断新增 `worker_ready` 与 `worker_status`；页面可区分“SMB bridge ready”和“Windows worker + ComfyUI 自检 ready”。
  - 最终新鲜工程门通过：84/84 pytest、80.95% coverage、86 文件 Ruff format、Ruff lint、ty、整页 JavaScript 与 `git diff --check` 全部通过；SMB 中 worker 源码 SHA-256 与项目版本一致。
  - 正式 8765 已重启并完成浏览器验收：设备页共享状态为 ready，未自检时显示准确下一步，空状态文案已更新，无横向溢出，控制台 0 warning/error。
  - 用户停止 worker 后，Mac SMB 目录读取仍稳定卡住，排除“worker 仍持有共享锁即可解释故障”；Windows ICMP 与 445 端口正常，故障收敛到 macOS 旧挂载会话。
  - `diskutil unmount force` 与 `/sbin/umount -f` 同样等待底层 SMB I/O，未能在当前会话完成断开；已停止继续读取共享目录，避免累积更多阻塞进程。
  - 当前请求用户重启 5060 Ti 主机，使远端 SMB 服务主动断线。重启后先恢复 Finder 挂载，再同步本地锁修正版；尚未投递任何真实 ComfyUI 任务。
  - Windows 整机重启后用户曾再次启动旧 worker；随后再次停止 worker，但原挂载中的文件操作与强制卸载进程仍处于 macOS 内核不可中断等待。
  - 使用 `forcenewsession + soft + nobrowse + nopassprompt` 尝试建立不复用旧会话的新 SMB 挂载，同样停在客户端连接阶段；结合 ping/445 正常，故障进一步定位为 Mac SMB 客户端内核状态，而非 Prompt Hub API、单个挂载点或 Windows 是否在线。
  - 为避免继续累积阻塞操作，停止网络盘测试并请求重启 Mac。修正版尚未同步到 Windows，共享目录中仍是旧 worker；真实任务仍为零。

### 阶段 23 完成：Windows Worker 与 ComfyUI 真实最小闭环
- **状态：** complete
- Mac 重启后确认旧 SMB 挂载和不可中断进程均已清除；Windows ICMP 与 TCP 445 正常。
- Finder 重新挂载 `PromptHub-5060Ti` 成功，Mac 创建、读取并删除测试文件，确认共享可写。
- 将使用 `%LOCALAPPDATA%\\PromptHub` 单实例锁的新版 worker 同步到共享目录；源与目标 SHA-256 均为 `172b8d5388271638efa403d29db5522ed2164d7ad6f4ae6f202bde1daa5ed985`。
- Windows 重新自检成功：Python 3.12.10、协议 `soda-compute-bridge-v2`、角色 `compute_5060ti`、ComfyUI reachable、RTX 5060 Ti 16GB 均由 `worker-status.json` 记录。
- 投递无 GPU 协议探针 `task-20260902T122109Z-6c85d6e5d061`；Worker 在约 2 秒内领取并按预期返回 manifest 缺失错误，验证失败回传链路。
- 新增 `deploy/windows-worker/examples/comfyui-smoke-empty-image-v1.json`，使用 ComfyUI 内置 `EmptyImage → SaveImage` 生成 128×128 蓝色 PNG。
- 投递真实烟雾任务 `task-20260902T122348Z-ec77bc7c56b1`；Windows 在约 1 秒内完成，回传图片、API workflow 与 run log。
- Mac integrity 验收返回 `verified=true`、`errors=[]`、`source_count=1`、`output_count=3`；所有 SHA-256 与结果信封一致。
- 首次完整性调用误用 POST 得到 405；读取 OpenAPI 后改用 GET，验收成功，未修改任务或文件。
- Worker 持续运行期间 SMB 未再卡死。阶段 23 达到完成标准；下一阶段为 Anima / Krea 2 模型级 API workflow 接入。
- 文档更新后的完成前新鲜验证通过：85/85 pytest、80.95% coverage、86 文件 Ruff format、Ruff lint、ty、示例生成包 JSON、整页 JavaScript 与 `git diff --check` 全部通过。

### 阶段 24：Anima / Krea 2 模型级 workflow 审计
- **状态：** in_progress
- 收到用户提供的 `Krea2-for-ares-ocmanager (1).json` 与 `anima-测试-满穗.json`，只读校验为有效 JSON。
- 两份文件均确认是 ComfyUI API Format：Krea 2 为 14 节点，Anima 为 58 节点。
- Krea 2 默认包含 SeedVR2 1920 放大；Anima 默认包含角色 LoRA、SAM3 脸手精修和多段放大，均不适合作为首轮低成本测试的原样参数。
- 决定保留原文件不变，新增受控 Profile 与低成本生成副本；只允许修改显式白名单节点字段。
- 完成关键连线追踪：Anima 参数映射为 `184/75/84/150/135:103/135:104`，基础解码 `148:139`；Krea 2 映射为 `141/121/87/129`，基础解码 `132`。
- 确定低成本编译方式：改接保存节点到基础解码结果，再按输出节点反向裁剪依赖闭包，结构性排除精修与放大分支。
- 确认 Prompt Hub Anima 输出已自带质量前缀；Profile 注入时将清空 workflow 节点 `182`，避免与完整 positive 重复。
- 确定以独立 workflow profile store/router 接入，不把模型节点映射耦合进 `creative.py` 或 Windows worker。
- 确认创作台已有双 Profile 输出与 steps/CFG/seed，可直接增加“发送到 5060 Ti”，不新增重复 Prompt 表单。
- 决定生成包先保存在 Mac 个人库，再按相同哈希复制到 SMB；workflow profile 数据将纳入现有备份范围。
- 新增 `workflow_profiles.py` 与 `workflow_routes.py` 后首次定向格式检查发现一处过长集合需要 Ruff 自动排版；尚未执行 lint/type/test，不将其视为功能完成。
- 已将 Workflow Profile store/router 接入应用构造与 lifespan；下一步补创作台控件及自动测试。
- 创作台右侧已加入 workflow 选择、低成本模式与“发送到 5060 Ti”，会按当前 Anima/Krea 2 Profile 自动过滤，不暴露节点 JSON。
- 首轮静态检查发现新模块需要沿用项目领域异常的 Ruff 例外，并有 import/type 细节；已记录并开始修正，尚未宣称通过。
- 第二轮 Ruff 自动修复 import 后仍报告依赖闭包循环可改为 `extend`；已按等价逻辑修正，等待重新验证。
- Ruff 已通过；ty 发现共享数字解析 helper 不能保证 seed/steps 返回整数，已拆成 `_run_int` 与 `_run_float`，防止类型边界含混。
- 两份用户真实 workflow 在临时目录完成编译审计：Krea 2 为 14→11 节点，Anima 为 58→26 节点；Anima LoRA Manager 分支仍位于依赖闭包内。
- 一次临时审计命令因包含清理命令被安全策略拒绝，未产生文件变更；改用自动释放的临时目录后成功。
- 已加入 Profile 校验、幂等、哈希防篡改、字段替换、低成本裁剪、LoRA 保留、API 投递和备份恢复测试；等待执行。
- 首轮定向测试为 8 pass / 2 fail：UI-workflow 测试夹具形状仍像合法 API 节点，另一个任务投递返回 422；定向测试的全局 coverage 34% 只是选测结果，不作为最终 coverage 结论。已修正首个夹具并为第二个断言保留响应详情，继续定位。
- 复测定位任务 422 为内部 `run_id` 使用大写 `T/Z`，与自身安全 ID 白名单不一致；已改为小写时间分隔符。UI-workflow 拒绝测试现已通过。
- Workflow Profile 4 项定向测试及其 Ruff/ty 已通过。
- 首轮全量验证在 ty 阶段发现既有 Windows worker 测试的 `log_message` 覆写参数名与新版 stdlib stub 不一致；尚未进入 pytest。已按父类签名修正测试替身，不修改生产 worker 行为。
- 第二轮全量验证在 Ruff 阶段指出该测试替身末尾显式 `return` 多余；已删除，继续从头验证。
- 新鲜全量工程门通过：89/89 pytest、80.93% coverage、89 文件 Ruff format、Ruff lint、ty 与 `git diff --check` 全部通过。
- README 与 Mac 操作指南已补充 Workflow Profile、低成本→完整工作流顺序，以及 Profile/run package 纳入备份的边界。
- 正式 8765 已重启加载 Workflow Profile 路由；两份用户 JSON 已原样导入个人库并保留来源 SHA-256。
- 浏览器验收通过：Anima/Krea 2 切换时只显示对应 Profile，低成本说明和发送按钮可用，页面宽度无溢出，console 0 warning/error；首次只读 DOM 检查因浏览器沙箱不提供 `HTMLButtonElement` 构造器失败，改用直接读取 `disabled` 后通过。
- Krea 2 低成本真实任务 `task-20260902T130215Z-2d7d6e4b41c3` 已完成，26 秒回传 512×768 PNG、workflow 与日志；Mac integrity `verified=true`，图片人工查看与原 Prompt 主要元素一致。
- 首次等待脚本误用了 zsh 只读变量 `status`，任务不受影响；改名为 `task_state` 后正常读取结果。
- Anima 首次低成本任务 `task-20260902T130347Z-257730a5d034` 在 ComfyUI 校验阶段失败：随机 seed `4737174999481427` 超过 `Seed (rgthree)` 明确上限 `1125899906842624 (2^50)`。根因位于 Mac 编译器随机范围，不是模型、LoRA 或 Windows 环境。
- 按 systematic-debugging 流程先加入可重复的 seed 上限回归测试，下一步先确认测试在旧实现上失败，再修改生产代码。
- Seed 回归测试已按预期在旧实现失败，并捕获随机上限为 `2^53`；现将编译器随机/显式 seed 与 API 输入统一收紧到 ComfyUI `Seed (rgthree)` 的 `0..2^50`。
- Seed 修复后 5 项 Profile 定向测试、Ruff 与 ty 通过；服务重启后新 Anima 任务 `task-20260902T130550Z-f0560673eff3` 真实完成，6.5 秒回传 PNG/workflow/log，Mac integrity `verified=true`。
- Krea 2 与 Anima 两张图均已只读导入 Mac ComfyUI 结果库，原 SMB 文件未修改。
- 回流解析发现 Anima 源 workflow 的 Image Saver steps/CFG 与真实 sampler 默认值不同；已先加入无显式覆盖场景的元数据同步回归测试，等待确认旧实现失败。
- 元数据同步测试已按预期在旧实现失败；编译器现从实际 steps/CFG literal 与分辨率节点回填 Image Saver，而不是沿用其可能过期的显示值。
- 元数据修复后 6 项 Workflow Profile 定向测试、Ruff 与 ty 通过；固定 seed 42 的 Anima 实机复验完成，Mac 回流正确解析为 12 steps / CFG 1 / 512×768。
- 浏览器最终复核回到用户原有 Anima Profile：显示“Anima / 满穗 · 58 nodes”，发送按钮可用，无横向溢出，console 0 warning/error。
- 浏览器切换验收曾触发当前项目自动保存并将 Profile 暂改为 Krea 2；已将“黄昏图书馆调查员”恢复为 Anima，内容未改，revision 因保存从 R12 增至 R14。
- 开始补阶段 24 一键回流：计划在设备页对 completed ComfyUI 回传先做 integrity，再复制到 Mac 结果库；有 `project_id` 时复用现有安全关联逻辑。重复导入保持幂等，路径再次限制在已挂载 bridge root 内。
- 已增加 `/api/workflow-tasks/{task_id}/import-results` 与设备页“验收并导入图片”；自动测试将模拟完整 Worker 回传，覆盖 SHA-256、Mac 复制、项目关联和重复导入。
- 一键回流首轮 Ruff 指出 router 工厂达到 55 statements / complexity 16；沿用本项目其他领域 router 的集中路由例外，不放宽全局规则，继续执行 type/test。
- ty 发现公开关联 helper 与原 FastAPI 内层 endpoint 同名，Python 闭包解析到了两参数 endpoint；已只重命名 endpoint 函数，URL 与行为不变，消除遮蔽。
- 一键回流定向验证通过：13 项 workflow/comfy/API 测试，Ruff 与 ty 全部通过；模拟 Worker 回传覆盖完整性、Mac 复制、项目关联和重复导入。
- 正式服务重启后，对真实 Anima 回传调用一键回流接口成功识别现有图片为 duplicate，未建立第二份文件。
- 设备页浏览器复核最终显示 6 张任务卡、4 个“验收并导入图片”按钮，无横向溢出，console 0 warning/error；一次等待使用 exact text 匹配整段 task span 超时，读取 DOM 后确认只是选择器过严，页面已正常加载。
- 最终新鲜工程门通过：91/91 pytest、81.02% coverage、89 文件 Ruff format、Ruff lint、ty、整页 JavaScript、正式健康接口、两份来源 SHA-256 与 `git diff --check` 全部通过。
- 已建立正式个人数据备份 `/Users/soda/Documents/Codex/soda-person/backups/prompt-hub/20260902-131855`；24 个文件全部校验通过，两个 SQLite integrity 均为 `ok`，workflow 原件、run packages 与三张本机回流图都在 manifest 中。
- 只读设备检查确认 SMB bridge 为 ready、状态文件中的 ComfyUI 为 reachable；一次未引用查询 URL 被 zsh 当作 glob 拒绝，重新引用后正常读取历史任务。

### 阶段 25：林悔儿真实旧数据集导入
- **状态：** in_progress
- 找到 `/Users/soda/Downloads/linhuier-v012_data.rar`；QQ 下载沙箱中的同名文件与其 SHA-256 完全一致，因此只采用普通 Downloads 版本作为来源。
- 归档安全审计通过：72 张图片、72 份 caption、单一顶层目录、0 个越界路径；Mac 可用空间约 714GB。
- 建立 `/Users/soda/Documents/Codex/soda-person/datasets/incoming/linhuier-v012`，保存原 RAR 副本并解压到独立 `dataset` 目录；复制前后归档 SHA-256 一致。
- 注册只读工作区 `dataset-4af72c6757de431081930100a27cb09e`，后台任务 `job-6be327b172244337ba724d4b2e7c3906` 在约 2 秒完成 72 张扫描。
- 扫描结果为 72 有效、72 caption 配对、0 坏图、0 缺失/孤立 caption、0 完全/近似重复组。
- 确认旧 caption 全部为英文、全部包含 `linhuieroc`，且未命中已知质量/来源污染标签；通过现有 API 将 72 份登记为 Anima reviewed，失败数为 0，未运行 WD14。
- 正式网页只读验收通过：工作区、缩略图、72 张统计、263 个标签、trigger 72 次和 0 冲突提示均正确显示。
- 用户更正中文名为“林悔儿”；已同步更正工作区、LoRA 项目及规划记录，trigger `linhuieroc` 不变。
- 生成两页带文件名的视觉联系表并完成全量缩略图抽查；全部保留为候选，没有自动批准、排除或送训。
- 建立 `lora-5eb67ac1316e435c991dd5ce8e2f4c6c` 角色项目，目标为 Anima，引用 72 张候选图；固定/可控/变量边界与 Civitai 来源已保存。
- 依据明确文件名与人工 caption 为 72 张填写保守覆盖初审，项目仍为 draft；覆盖缺口由 43 项降至 11 项。
- 发现 67 个 `.png` 扩展名文件内部实际为 JPEG；保持原字节不变，留待 Windows AnimaLoraStudio 读取 smoke test。
- 完成新鲜一致性复核：归档双副本 SHA-256、72+72 文件、72 张有效扫描、72 份 reviewed Anima caption、72 张候选资产、11 个覆盖缺口、正确中文名、两页联系表与 `git diff --check` 全部通过。
- 下一步：由用户在页面确认保留/排除、刘海外观边界和本轮覆盖建议，再验证冻结版本与 Windows 数据集交付。
- 已完成原 caption 批量接续：后端提供 preview/apply 两步接口，支持 Anima/Krea 2、全部/已选、默认不覆盖和 draft/reviewed 状态；确认后整批只生成一个快照，原 `.txt` 不变。
- 已完成 LoRA 保守覆盖初审：从文件名、原 caption、现有 Profile caption 和图片横竖尺寸提取明确证据；preview 不写入，apply 只合并新增项并登记 confirmed provenance，不改变候选/保留/排除状态。
- 数据集、LoRA、设备与智能检索页面已清理“明天连接”“M4 再冻结”等过期文案；明确 Mac/Windows 分工与“当前 Worker 仅 ComfyUI 自动闭环”。README、Mac 操作指南和开发计划同步更新。
- 实际浏览器验收：林悔儿 Anima 原 caption 预览为 72 张已有内容、0 变更；Krea 2 预览为 72 张可接续但未确认写入；LoRA 覆盖初审为 18 张、19 个新增建议但未确认应用。正式状态保持 72 Anima reviewed、0 Krea 2、72 candidate、revision 75、11 个缺口。
- 新鲜工程门通过：89 文件 Ruff format、Ruff lint、ty、94/94 pytest、81.15% coverage、整页 JavaScript、98 条 OpenAPI 路径、正式 SQLite `integrity_check=ok` 与 `git diff --check`。
- 浏览器页面 identity/非空/交互检查通过，console 0 warning/error；桌面截图确认覆盖初审操作与矩阵布局无重叠。

## 本阶段错误记录

| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| 首次归档计数直接调用未安装的 `unar`，得到空计数 | 1 | 改用本机已支持 RAR5 的 `bsdtar`，重新从头统计并验证 145 个归档项 |
| 首次 caption 空文件/唯一行统计误用了 `rg` 短参数语义 | 1 | 改为逐文件非空检查与 SHA-256 唯一性统计，确认 0 空文件、72 份内容均不同 |
| 首次同时更新三个规划文件时，`findings.md` 的尾部锚点与实际文本不匹配，补丁整体未应用 | 1 | 读取三个文件的实际尾部后按文件分别应用精确补丁 |
| 首次格式/尺寸摘要的 `jq` 字符串拼接语法错误，管道提前关闭 | 1 | 改用 jq 字符串插值后成功确认 67 JPEG 内容、5 PNG 内容和 72 份 reviewed Anima caption |
| 72 张覆盖写入完成后，摘要脚本读取了不存在的 `coverage_report.gaps` 字段 | 1 | 不重复写入；只读获取真实项目并按 `dimensions[].items` 汇总，确认 revision 75、72 候选和 11 个缺口 |
| 新覆盖 helper 首次补丁插入到 `coverage_report()` 中段，导致 LoRA 创建测试返回 `None` | 1 | 按函数边界移动原报告逻辑，11 项定向测试随后全部通过 |
| 单文件 pytest 功能断言通过但触发全项目 80% coverage 门 | 1 | 定向阶段使用 `--no-cov`，最终以 94 项全量测试和 81.15% coverage 为准 |
| 首轮完整工程门发现 `lora_projects.py` 需要机械格式化，随后测试函数又因新增独立断言超过 statement 限制 | 1 | 运行 Ruff formatter，并把页面回归保留在既有 marker 集合内；从头重跑完整工程门通过 |
| 首轮整页 JavaScript 临时文件清理命令被安全策略拒绝，第二轮临时文件无 `.js` 后缀被 Node 拒绝 | 2 | 使用明确的 `/tmp/prompt-hub-script-check.js` 路径后完成语法检查 |

### 阶段 26：Windows LoRA Manager 只读清单闭环
- **状态：** complete
- Windows 已运行只读检查脚本并生成 `D:\PromptHub-Bridge\prompt-hub\diagnostics\lora-manager-inspection.json`；Mac 首次读取时文件尚未出现在 SMB 目录，约两秒后刷新可见，属于写入/SMB 刷新时序而非路径错误。
- 诊断确认主机 `CHINAMI-5E1E3GQ`、ComfyUI 0.33.0、RTX 5060 Ti 16GB、LoRA 根 `F:\Comfyui\ComfyUI-aki-v3\ComfyUI\models\loras`，共 256 个模型和 375 个预览文件。
- Mac 直接请求 LoRA Manager `/loras/api/list` 仍为空响应；不再把局域网直连私有插件 API作为实现前提。
- 已确定实现边界：Worker 只访问配置登记的 LoRA 根，读取文件名/大小/mtime、可选 `.metadata.json` 与预览，不读取或复制权重；Mac 校验清单输出后再导入现有 `soda-windows-lora-catalog-v1`。
- 一次只读检索命令把 Markdown 反引号直接放进 shell，导致 `comfyui_generate` 被 shell 当作命令并报 `command not found`；未产生文件变更，后续 shell 检索改用无反引号模式或安全引用。
- Worker 已新增 `lora_catalog_snapshot`，LoRA 根目录使用配置白名单 `comfyui-main`；Windows 部署源码与 Mac 源码 SHA-256 一致，任务执行不打开或复制 `.safetensors` 内容。
- 真实任务 `task-20260902T172354Z-8f3dcc8f59e5` 完成，快照为 `catalog-20260902T172356Z-60e595c5d3da`；清单输出 SHA-256 为 `e6143eaa1b579620c8d0af8ce2765488dd2525a2bec7989527be9630f57e53ed`，Mac 完整性结果为 `verified=true`。
- Mac 验收导入 256 个 LoRA：233 个有 sidecar metadata、210 个有预览路径、122 个有 trigger words、233 个带 LoRA Manager 已有 SHA-256。设备页已提供同步、任务状态、完整性校验、验收导入与检索。
- 浏览器实测导入提示为 256 条；搜索 `linhuier` 只返回 `Anima/Character/linhuier-anima_v01.safetensors`，模型族、标签与 Civitai `2885952/3262276` metadata 正确，console 为 0 warning/error。
- 浏览器验收发现导入后搜索框保留但结果恢复全量；已让导入后的刷新沿用当前查询词，并增加页面契约回归断言。
- 新鲜工程门：89 文件 Ruff format、Ruff lint、ty、96/96 pytest、80.60% coverage、整页 JavaScript、100 条 OpenAPI 路径、两库 `integrity_check=ok`、敏感密钥形状扫描与 `git diff --check` 通过。默认 coverage C tracer 曾在 96 项断言完成后的 macOS ONNX Runtime 清理阶段两次以 `recursive_mutex`/134 退出；无 coverage 全量测试稳定，纯 Python tracer 连续两次正常退出并保持相同覆盖率，因此在测试配置固定 `timid=true`。代价是全量测试约增加 6 秒，不改变生产运行。
### 阶段 27：LoRA Manager 预览图同步
- **状态：** in_progress
- 用户已重新开启 Windows 并运行 Worker，开始实现 LoRA Manager 预览图到 Mac 分类页面的同步闭环。
- 已确认本轮不复制 `.safetensors`，只同步受控预览资产；计划覆盖 Worker 输出、Mac 哈希验收与缓存、图片路由、卡片缩略图/大图以及真实跨设备验收。
- 已完成现有扩展点审计：Worker 已解析主预览相对路径但只回传 catalog JSON；Mac 已具备统一结果 manifest 的路径与 SHA-256 校验，可直接复用。
- 运行态诊断：Windows 已开机，但 Mac 的 `/Volumes/PromptHub-5060Ti` 当前未挂载；准备先恢复 Finder SMB 会话，再部署和实测。
- 首次调用 Finder 打开 SMB 地址后 8 秒内未出现挂载点；已停止重复调用，下一步检查 Finder 是否有登录或确认界面。
- Finder SMB 已恢复；共享桥 ready、Worker ready、ComfyUI reachable，白名单根目录含 256 个 LoRA。
- `windows_worker.py` 现会收集同一 LoRA 的全部关联预览，按安全名复制到任务 inbox，并逐张登记 SHA-256、大小、lora_id 与顺序；不会打开或复制权重内容。
- `remote_nodes.py` / `remote_routes.py` 现会在统一完整性校验后把图片原子写入 `remote-nodes/lora-previews`，保存多图映射并提供每次读取都复核哈希的本机图片路由。
- `remote_web.py` 现显示缩略图、图片数量与无图占位；点击卡片图片可打开多图查看器，桌面双列、手机单列。
- README、Mac/Windows 操作指南和 Windows 部署说明已更新，明确预览缓存可重新同步、不进入正式备份，`.safetensors` 始终不复制。
- 定向 Ruff、ty、12 项 Worker/Remote 测试与 4 项 API 页面测试通过；缓存被篡改后图片路由返回 404。
- 新鲜完整工程门通过：89 文件格式、Ruff lint、ty、96/96 pytest、80.55% coverage 与 `git diff --check` 全部正常。
- 新版 Worker 已原子更新到 SMB 的 `prompt_hub_worker.py` 与 `worker.py`，两份 SHA-256 都与 Mac 源码一致：`359b7cd92d63b23a54c2bca1252f55492aabee80ac7a167d5149591d6e9610d5`；`worker-config.json` 未修改。
- Mac 8765 服务已重启。浏览器检查确认 256 张旧清单卡片全部显示“暂无本地预览图”，15 个树根和大图 dialog 均存在，当前 684px 视口无横向溢出；等待重启 Windows Worker 后真实同步图片。
- 最新真实任务 `task-20260903T070722Z-225c41f71aeb` 已由 Windows Worker 完成，Mac 导入快照 `catalog-20260903T070725Z-60e595c5d3da`：256 个 LoRA、221 个有视觉参照、386 张图片，完整性校验通过。
- 浏览器已确认 `linhuier` 多图查看器两张图片完整解码，尺寸为 450×658 与 1664×2432；684px 视口没有横向溢出。
- 一次规划文件补丁使用了不在 `findings.md` 中的锚点而未应用；读取文件实际尾部后改用精确锚点，未覆盖任何内容。
- 浏览器分类树验收确认 15 个根目录；点击 `Anima/style` 后页面状态为“当前 49 / 256 个”，可见卡片标题均属于该目录。
- 首次关闭查看器时误用不存在的 `tab.playwright.click()`；改用可访问性 role 定位按钮后成功关闭。首次统计筛选卡片时误用了不存在的容器 ID，改从可见 `article h3` 与页面状态读取，确认筛选实际正常。
- 展开并点击 `Krea2/style` 后，页面状态为“当前 37 / 256 个”，首批条目为 `0801style`、`Alt-Girl/E-Girl` 等 Krea 2 画风 LoRA，当前桌面视口无横向溢出。
- 内置 Browser 的 `setViewportSize()` 不存在，无法直接改成 390px。Playwright skill 自带 wrapper 先后因无执行权限和 CRLF `pipefail` 失败，直接 `npx playwright-cli open` 又在 30 秒内无可读结果；停止重复该路径，改用现有浏览器能力与 CSS/DOM 响应式审计完成窄屏证据。
- 尝试在内置 Browser 中建立 390px 同源 iframe 时，受控 DOM 代理不允许 `document.createElement()`；未修改页面，改为审计 620px/540px 响应式规则，并保留 684px 无溢出的真实结果。
- 本地缓存审计通过：386 个图片文件（223 WebP、136 PNG、27 JPEG），0 个 `.safetensors`。`linhuier` 的 `000.webp` 与 `001.png` 路由均返回 HTTP 200 和匹配的 Content-Type。
- `Krea2/style` 精确渲染 37 张卡片、37 个预览入口、0 个占位。直接统计发现 19 张首屏外 lazy 图片尚未加载；未误报为损坏，下一步通过真实打开末尾卡片触发滚动与解码。
- 通过通用 `.last()` 打开末尾卡片时，Browser 的 locator 使用了筛选前缓存位置，误点到 `Anima/Character/V1.safetensors` 并把筛选切回 `Anima/Character`；图片本身成功解码，但该结果不作为 Krea 2 证据。后续只用完整可访问名称定位目标。
- 已用完整可访问名称重新定位并打开 `Z3ZZ4 Krea 2`；两张参照图均完整解码（450×644、1280×1832），确认首屏外 lazy-load 图片在真实滚动/打开后可用。
- Worker 最终信封复核：completed，1 个 catalog + 386 个 preview，`weights_read=false`；10 个非支持格式候选按 `unsupported_format` 安全跳过。
- API 与本机事实源一致：256 个条目、221 个带图、386 个唯一 URL；四个 SQLite（正式库、两个历史备份、embedding 库）完整性均为 `ok`。
- 浏览器已关闭查看器并恢复“全部 LoRA 256”；最终状态显示 256/221/386，256 张卡片可见，当前窗口无横向溢出。
- 阶段 27 完成前新鲜工程门通过：98/98 pytest、80.45% coverage、89 文件 Ruff format、Ruff lint、ty 与 `git diff --check` 全部通过。
- 阶段 27 已标记 complete；未执行 commit、push 或创建 PR。

### 阶段 28：GitHub 私有发布基线
- **状态：** in_progress
- 用户已明确授权整理当前代码、commit、创建 GitHub 仓库并 push；默认采用 private，避免公开个人设备信息、成人向工作流细节和仍在演进的工程。
- 本地已有 `main` 与两次历史 commit，尚未配置 remote；GitHub 连接与 `gh` CLI 均确认当前账号为 `cOkieeman`，没有可用组织归属。
- 当前有 23 个 tracked 文件修改及多批新增领域模块/测试/操作文档；下一步先做提交集合安全审计，不把 Prompt Library、模型、SQLite、缓存图、数据集或凭据纳入 Git。
- 一次用于读取技能文件的 JavaScript 包装参数误写，调用在执行 shell 前即失败；修正后正常读取，未改动任何文件。
- GitHub 只读查询确认 `cOkieeman/soda-prompt-hub` 当前不存在，可用于创建新仓库。
- 首次分项密钥形状扫描因 shell 单引号嵌套导致 zsh 解析失败，未执行文件读取；后续改为不含危险嵌套引号的独立规则扫描。
- 发布安全审计确认待提交集合共 98 个文件，无超过 1 MiB 文件，无模型权重、数据集、SQLite、归档或媒体文件；未发现私钥、GitHub Token 或真实 OpenAI Key。
- 宽泛 `sk-` 规则的命中均来自 `task-...` 任务编号；凭据字段命中仅为测试系统拒绝 password/secret 的假数据。
- `.gitignore` 已补充常见模型权重、RAR/7z、Windows worker 本地配置和运行产物；README、Mac/绘图指南、数据集路径占位和 Windows 示例已改为可移植写法，历史进度与测试夹具保留在 private 仓库。
- 二次安全门确认所有新增忽略规则生效、JSON 示例可解析、提交集合仍无超过 1 MiB 文件；发布说明中最后一处真实 Windows 主机名已替换为通用描述。
- 发布前新鲜工程门通过：98/98 pytest、80.45% coverage、89 文件 Ruff format、Ruff lint、ty、`uv lock --check` 与 `git diff --check` 全部通过。
- 首次 staged 大 blob 循环把 zsh 特殊变量 `path` 用作文件名变量，覆盖了命令搜索路径，导致循环内后续 `git` 与末尾 staged diff 检查未执行；暂存本身成功，改用 `file_path` 后从头重跑这两项，不能沿用失败命令的结论。
- staged 复核确认 78 个文件、无超过 1 MiB blob、无私钥或 Token 形状；`git diff --cached --check` 发现 `FINAL_TEST_REPORT.md` 一处 Markdown 行尾空格，已移除并要求重新执行完整工程门。
- 修正行尾后最终工程门再次通过：98/98 pytest、80.45% coverage、89 文件 Ruff format、Ruff lint、ty、锁文件、staged diff、密钥形状与大 blob 检查全部通过。
- 已创建本地发布 commit，并成功创建 private GitHub 仓库 `cOkieeman/soda-prompt-hub`；首次 HTTPS push 在 TLS 握手阶段遇到 `SSL_ERROR_SYSCALL`，不是认证或代码失败，保留本地 commit 后检查连接并重试。
- `gh auth setup-git` 后重试 push 成功；远端确认为 private、默认分支为 `main`，首次发布远端 SHA 与本地 `9871e7ae4e7476a32fa38fa86d41e55f383c6b84` 一致。
- 阶段 28 已完成；本条完成记录将作为独立文档 commit 推送，最终再以新 SHA 复核远端。

### 阶段 29：模型资产与工作流控制台
- **状态：** in_progress
- 用户明确要求先公开仓库再继续开发；完整 Git 历史安全门未发现凭据、模型权重、数据库、数据集、媒体或超过 1 MiB 的对象。
- 历史记录仍含少量本机路径、局域网测试地址与测试主机名，但不含登录凭据；按用户授权将仓库切换为 public。
- GitHub 已复核 `cOkieeman/soda-prompt-hub` 为 `PUBLIC`、默认分支 `main`、未归档。
- 本阶段优先交付 Mac 可用的模型资产事实库与 Workflow 参数接口；Windows 只扫描配置白名单目录并回传 metadata，绝不打开、复制或计算大权重内容哈希。
- 已完成六类模型根、Windows 清单任务、Mac SHA-256 验收、版本化事实库与检索接口的首版实现，并开始补充自动测试。
- 首轮模型清单定向测试中，业务投递、导入、过滤均通过；冲突测试误假设 store 暴露在 `app.state`，已改为直接打开同一临时事实目录，不改生产实现。
- Windows Worker 与 Mac 事实库共 16 项定向测试通过；覆盖多模型根、类型/模型族过滤、回传哈希、同名快照冲突和 Windows 反斜杠路径穿越。
- 设备页已增加独立“ComfyUI 模型资产”区域：六类模型 → 顶层文件夹树、名称/路径/类型/模型族搜索、清单刷新，以及返回任务的验收导入按钮。
- Workflow Profile 编译器开始加入受控模型、附加 LoRA、Sampler 与 Scheduler 覆盖；首轮测试暴露旧极简 fixture 缺少真实节点且无覆盖时仍错误要求采样节点，已改为按需校验并补齐真实依赖链。
- 修正后的 7 项 Workflow Profile 功能测试通过；Ruff 仅提示新增断言使一个既有端到端测试超过 statement 上限，已将跨模型族拒绝拆成独立测试而不放宽规则。
- 创作台的 5060 Ti 区域已加入 Profile 级受控模型、Sampler、Scheduler、最多 4 个附加 LoRA 与强度控件，并把 Width/Height 纳入项目生成参数；选择保存在项目 `generation.workflow_controls`，投递时由服务端重新按当前 Mac 清单解析和校验。
- README 与 Mac/Windows 操作说明已同步模型清单和受控 Workflow 参数边界：留空保留 Profile 原值、附加 LoRA 不删除默认组合、当前两份主工作流只开放真实存在的 UNet/VAE/Text Encoder 节点。
- 首次完整工程门中 102/102 pytest、80.32% coverage、Ruff、ty、锁文件、JSON 与 diff 均通过；整页 JavaScript 检查误用了不存在的 `PAGE` 常量，已改用实际 `INDEX_HTML` 重新提取，不把失败命令当作通过证据。
- Workflow Profile 导入校验已覆盖两份真实工作流中的受控 UNet、VAE、Text Encoder、LoRA Loader 与 Sampler 节点；缺失节点会在导入阶段返回明确领域错误，不再延后到编译时触发普通 `KeyError`。
- 新增 10 组受控节点缺失回归；目标测试的 18 个功能断言通过，单文件命令按预期触发全项目 coverage 门，最终以完整测试证据为准。
- Windows 共享目录中的 `prompt_hub_worker.py`、`worker.py`、README 与示例配置已同步；两份 Worker SHA-256 均与项目源码 `f740a8b9d6e26837d5a2f5645588bce8a814e10477ddc15189fb45aadfad347d` 一致，个人 `worker-config.json` 未被覆盖。
- 浏览器真实交互确认：模型资产页正确显示未同步空状态；Anima/Krea 2 Profile 可切换；Sampler 保存后刷新恢复；附加 `linhuier` LoRA 保存后刷新恢复；Krea 2 下只列出兼容或 unknown LoRA；测试结束已恢复 Anima、默认 Sampler 与无附加 LoRA。
- Browser QA 在 684px 窄窗口发现顶部横向导航会把后半入口藏在滚动区域，已改为 900px 以下五列两行、620px 以下两列布局；复验所有入口直接可见，console 0 warning/error。
- 本机服务已重启并通过 `/api/health`；`prompt-hub doctor` 确认正式数据库与 embedding 数据库完整、WD14 可用、磁盘余量 711.5 GiB、8765 服务正常。
- 当前新鲜工程门：112/112 pytest、80.34% coverage、89 文件 Ruff format、Ruff lint、ty、锁文件、两个 Worker 配置 JSON、整页 JavaScript、服务健康与 `git diff --check` 全部通过。
- 阶段 29 的 Mac 开发与 Windows 部署包已完成；仍等待 Windows 重启新版 Worker，再执行六类目录自检、真实模型清单验收、模型族过滤与最低成本 ComfyUI smoke test，因此阶段保持 `in_progress`。
- 第二次真实模型清单任务 `task-20260903T085351Z-7b335faf9149` 完成并通过 SHA-256 验收，仍为 140 个模型且 `weights_read=false`；但 `SDXL/animagineXLV31...` 与 `Flux1_Dev/fluxKreaDev...` 继续被旧逻辑误分类，证明实际领取任务的是未退出的旧 Worker 进程。
- 为跨进程诊断新增 `worker_build_sha256`：自检状态、成功任务与失败任务均回显启动时加载的脚本 SHA-256；回归测试先以缺失字段失败，修复后定向 pytest、Ruff format/lint 与 ty 通过。
- 新 Worker 已同步到共享目录两份入口，项目源码与两份共享脚本 SHA-256 均为 `11f78bd64957e7f88c7e791e3c351e09f4a74a4fb9c8abaa0c8da831c645fb55`；等待用户彻底关闭所有旧 Worker 窗口后重新启动，再用任务回传指纹确认进程版本。
- 用户关闭旧进程后，新任务 `task-20260903T095310Z-418e3862fe8f` 回传相同 build 指纹；140 个模型完整验收导入，`animagineXL` 正确为 SDXL、两个 `fluxKreaDev` 正确为 Flux，Anima/Krea 2 diffusion model 候选为 12/10。
- 浏览器设备页确认最新快照、六类树、140 个模型与修正后的卡片已显示；创作台 Anima 底模菜单显示 12 个真实 Anima 候选，已知 Flux/SDXL 不进入该菜单。下一步执行低成本 ComfyUI smoke test，并在最终工程门前刷新旧 LoRA catalog 的家族分类。
- 低成本 Anima 真机任务 `task-20260903T095542Z-f811542ce312` 使用 512×768、4 steps、CFG 1.0、seed 123456，Windows 约 7 秒完成；图片、workflow 和运行日志三项 SHA-256 均通过，并成功关联回测试项目。视觉检查确认银发调查员、军装、旧图书馆与黄昏光线均符合槽位。
- Krea 2 页面在同步后未刷新时短暂保留旧 `fluxKreaDev` 候选；源码过滤检查显示逻辑已严格按 `model_family`，整页刷新后两项消失，故不做错误代码修补。测试项目已恢复 Anima，当前 revision 为 R25。
- 新 LoRA 任务 `task-20260903T095635Z-4830806392fe` 回传 256 个 LoRA 与 386 张预览，387 个输出全部通过 SHA-256；Mac 导入后 221 个条目有图，旧 `Wan2.2_Animate` 五项均改为 `unknown`，不再误归 Anima，权重未读取。
- 阶段 29 最终工程门通过：113/113 pytest、80.48% coverage、89 文件 Ruff format、Ruff lint、ty、`uv lock --check`、7 段页面 JavaScript、正式服务健康、数据库诊断与 `git diff --check` 全部通过。
- Windows Worker 项目源码与共享目录两份入口的 SHA-256 一致，均为 `11f78bd64957e7f88c7e791e3c351e09f4a74a4fb9c8abaa0c8da831c645fb55`；操作文档补充 `worker_build_sha256` 的旧进程识别方法。
- 阶段 29 标记为 `complete`：真实模型资产 140 项、Anima/Krea 2 家族过滤、受控 Anima smoke test、结果回流，以及 256 项 LoRA/386 张预览的刷新均已验收。整体路线中的数据集冻结、训练执行、视觉向量与监听收紧等后续事项继续保留，不混入本阶段完成结论。
- 收尾文档更新后重新执行完整验证：113/113 pytest、80.48% coverage、89 文件 Ruff format、Ruff lint、ty、锁文件、7 段页面 JavaScript、正式健康接口、`prompt-hub doctor` 与 `git diff --check` 均通过；共享盘 README 与仓库部署说明一致，未 commit、未 push。

### 阶段 30：LoRA 快速选择与底模视觉预览
- **状态：** in_progress
- 用户指出 256 个 LoRA 使用原生长下拉时需要滚动很久，而且底模控件被长列表拖到下方；要求改为适合大清单的选择方式，并为底模同步 LoRA Manager 风格的示例图。
- 本阶段保持既有档案馆视觉风格，不引入前端框架；模型预览只同步允许格式的小型 sidecar 图片，不读取或复制权重。
- 创作台已改为紧凑 LoRA 选择器：支持名称、路径、Trigger、标签搜索和 Windows 文件夹筛选，结果区最多渲染 60 项并在内部滚动；已选 LoRA 独立显示缩略图、强度与移除按钮，不再把底模区域推到长清单下方。
- 真实浏览器复验：Anima 当前有 116 个兼容 LoRA；搜索 `linhuier` 返回 1 项且显示真实预览，筛选 `Anima/style` 返回 49 项；关闭按钮可见并能收起面板，页面 `scrollWidth` 与 `clientWidth` 均为 684，无横向溢出，控制台无 warning/error。
- 底模预览链已完成源码实现：Windows Worker 只读发现模型同名、`.civitai_bak` 与 `.preview` sidecar 图片；Mac 验收 SHA-256 后缓存到独立 `model-previews`，设备页和创作台通过受控路由显示 Checkpoint / Diffusion Model 示例图或明确无图状态。
- 项目源码、共享目录 `prompt_hub_worker.py` 与 `worker.py` 三份 Worker SHA-256 已核对一致，当前均为 `37be9da8f3b0f0b2d4112250647c31a4a2337607c302d77594eda263c71eae22`。Windows 正在运行的 Worker 自检时间仍为 `2026-09-03T08:44:42Z`，需要重新启动后再刷新并验收真实底模示例图数量。
- 本轮新鲜工程门通过：114/114 pytest、80.48% coverage、89 文件 Ruff format、Ruff lint、ty、`uv lock --check`、7 段页面 JavaScript、正式健康接口、`prompt-hub doctor` 与 `git diff --check` 均正常；当前仅剩新版 Windows Worker 的真实底模图片同步验收。
- Windows 重新启动后，模型清单任务 `task-20260903T104526Z-57c456f19acc` 由新版 Worker 领取；回传 `worker_build_sha256=37be9da8f3b0f0b2d4112250647c31a4a2337607c302d77594eda263c71eae22`，与项目源码及共享目录两份 Worker 完全一致。
- 真实任务发现 140 个模型资产和 161 张 sidecar 示例图（约 224 MB），`weights_read=false`、`weights_copied=false`；Mac 逐文件 SHA-256 验收通过并导入，88 个模型带视觉参照，六类模型计数保持 58 Checkpoint、38 Diffusion Model、14 VAE、9 Text Encoder、6 Upscaler、15 ControlNet。
- 创作台刷新后，默认 `anima-base-v1.0` 显示真实底模示例图；受控图片路由返回 `200 image/png`，页面身份、非空状态、无框架错误层和控制台 0 warning/error 均通过。阶段 30 标记为 `complete`。

### 阶段 31：Civitai 来源链接同步
- **状态：** in_progress
- 用户希望从 Mac 的 LoRA/底模条目直接返回 Civitai 查看模型提示词。计划优先解析 LoRA Manager / Civitai sidecar 中已有 URL 或数字 ID，不联网猜测、不自动下载，也不暴露 Windows 本地路径。
- 初步审计确认真实 LoRA 清单已带 Civitai model/version 数字 ID；模型清单目前未解析 sidecar，需要在 Worker 白名单模型根内增加小型 JSON sidecar 读取，再由 Mac 验收并展示。
- 已先补来源链接回归断言；首个定向 pytest 命令误写了不存在的 `tests/test_api.py::test_home_page`，pytest 在执行前停止。已查询真实测试名为 `test_api_health_stats_search_and_page`，不重复错误命令。
- 继续开发时一次 `apply_patch` 因同一文件被拆成两个 update 区块而在校验阶段拒绝，未写入任何内容；已合并为单一 update 后成功应用。
- 第一轮定向 Ruff 在测试运行前发现新 URL 长度上限使用裸 `2000`；已提取为 `MAX_CIVITAI_URL_LENGTH`，要求从格式化、lint、类型检查和定向测试整组重跑。
- Worker 已实现模型同名小型 sidecar 解析；Mac 的 LoRA/模型清单导入层再次执行 Civitai URL 白名单校验。只接受模型详情页，不接受本地路径、外站、下载 API 或图片 URL。
- 设备页 LoRA/模型卡、创作台底模预览、LoRA 搜索结果与已选 LoRA 均增加独立的 Civitai 来源入口；搜索可使用 model/version ID。
- 真实旧 LoRA 快照兼容验证：256 个 LoRA 中 232 个可返回 Civitai；`linhuier` 搜索唯一命中，并生成精确来源 `https://civitai.com/models/2885952?modelVersionId=3262276`。当前旧模型快照 140 个条目中来源为 0，需新版 Worker 重扫。
- 新版 Worker 已同步到 SMB，项目源码和共享目录两份入口 SHA-256 一致：`1e68ec659948c848001a0f9bf843046418ca236771b0ad04af4af7cfe7db82a9`；个人 `worker-config.json` 未覆盖。
- 定向功能测试 12 项通过；首轮选测因全项目 coverage 门而返回非零，随后用 `--no-cov` 确认功能断言，并以 121 项全量测试和 80.58% coverage 作为覆盖率证据。
- 7 段页面 JavaScript 语法通过；首次提取正则转义错误得到 0 段，改用 `<script>` 分割后从头检查。Browser/Playwright 复验 `linhuier` 页面来源与创作台独立添加按钮，控制台 0 warning/error。
- 首次后台启动本机服务后进程被宿主回收，页面出现连接拒绝；已改用持续工具会话 `56353`，当前 `/api/health` 正常。
- 2026-09-03 再查 Windows `worker-status.json` 仍为旧时间 `2026-09-03T08:44:42Z` 且无 `worker_build_sha256`。阶段保持 in progress，等待用户彻底关闭旧 Worker 窗口并从共享目录重新执行自检与启动脚本。
- 文档更新后的完成前工程门通过：89 文件 Ruff format、Ruff lint、ty、121/121 pytest、80.58% coverage、`uv lock --check`、7 段页面 JavaScript、正式 `/api/health`、doctor 7/7 与 `git diff --check` 全部正常。
- 当前正式 API 复核为 LoRA `256 / 221 有图 / 232 有来源 / 386 张预览`，模型 `140 / 88 有图 / 0 有来源 / 161 张预览`。三份新版 Worker SHA-256 均为 `1e68ec659948c848001a0f9bf843046418ca236771b0ad04af4af7cfe7db82a9`。
- 收尾检索时一次双引号 shell 参数包含 Markdown 反引号，shell 尝试执行两段文字并返回找不到命令；没有文件写入或状态变化，后续已改用不含反引号的精确读取方式。
- 用户重启 Windows 后，Worker 状态时间更新为 `2026-09-03T11:15:58Z`，`worker_build_sha256` 与 Mac、SMB 两份脚本完全一致。
- 投递并完成真实模型任务 `task-20260903T111630Z-59a120348175`：140 个模型、161 张示例图、完整性验收通过；新快照 `models-20260903T111633Z-7c0adb88d329` 有 71 个 Civitai 来源、88 个有图，权重未读取或复制。
- 浏览器初验发现设备页按 model ID `1064295` 返回 0，而后端同一查询正确返回 `chosenMixXL_v41`；根因为前端本地筛选遗漏来源与 metadata ID。新增页面回归标记后测试先失败，再补齐 LoRA/模型筛选字段，目标测试通过。
- Mac 服务已重启到修复版本，持续服务会话为 `4306`。应用内浏览器复验：模型 ID `1064295` 唯一命中 `chosenMixXL_v41`，LoRA ID `2885952` 唯一命中 `linhuier`；两者 Civitai URL 精确正确。
- 创作台默认 Anima 底模显示示例图与 Civitai 来源；设备页显示 140 / 88 / 71 / 161，页面无横向溢出、无错误层、console 0 warning/error。阶段 31 标记 complete。
- 最终新鲜工程门通过：89 文件 Ruff format、Ruff lint、ty、121/121 pytest、80.58% coverage、`uv lock --check`、7 段页面 JavaScript、doctor 7/7、正式 LoRA/模型状态与 `git diff --check` 全部正常；未 commit、未 push。

### 阶段 32：设备页子页面导航

- 用户指出设备页仍把任务、LoRA、底模纵向堆叠，必须翻过完整 LoRA 清单才能看到底模；确认这是页面信息架构问题，不是分类树本身的问题。
- 方案确定为顶部三段式子页面导航：任务状态包含设备登记与任务列表，LoRA 与底模各自独立。切换只改变页面显示，不改清单、项目或 Windows 状态。
- 首次并行读取设计技能时工作目录误写为 `prompt-h-hub`，命令在执行前失败且无文件变化；改用真实路径后完整读取。
- 回归测试先因缺少三个 tab/panel 标记失败；随后在 `remote_web.py` 增加语义化三段导航、互斥面板、真实数量与键盘切换，目标测试转为通过。
- 正式服务已重启到持续会话 `47255`。应用内浏览器实测任务、LoRA、底模切换时只有对应 panel 可见；684px 宽度横向溢出为 0，底模 ID 搜索与示例图弹窗保持正常，console 0 warning/error。
- 完成前新鲜工程门通过：89 文件 Ruff format、Ruff lint、ty、121/121 pytest、80.58% coverage、`uv lock --check`、7 段页面 JavaScript、doctor 7/7 与 `git diff --check` 全部正常。阶段 32 标记 complete；未 commit、未 push。

### 阶段 32 后路线审计

- 应用户要求核对正常开发剩余工作与任务书更新情况；确认阶段 32 已记录，但阶段 8、19、20、22 和 Mac 操作手册仍有被后续真实 Windows 验收取代的历史状态。
- `task_plan.md` 新增阶段 32 后权威剩余清单，按 P0 绘图闭环、P1 资料/视觉、P1 Windows 批量视觉、P2 安全发布和延后视频分组。
- 将局域网 ComfyUI 交付、真实结果元数据回流、Worker 领取/回传/幂等和受控模型参数等已经完成的事项从旧待办中清理；保留真实未完成的 LoRA smoke test、网站缓存、CLIP/SigLIP、批量 VLM、GPU 占用保护和故障演练。
- `MAC_OPERATIONS_GUIDE.md` 同步修正：底模/LoRA/采样参数绑定已经完成，不再列为等待 Windows 的工作。
- 本轮只修改规划与操作文档，不改应用代码、数据库或 Windows Worker；未 commit、未 push。

### 阶段 33：任务状态中文化与职责纠正

- 用户纠正规划边界：Mac 只需交付打好标的数据集；Windows 中的标签终筛、正则、训练、checkpoint 和 LoRA 测试由用户自行操作，不纳入 Prompt Hub 完成条件。
- `embedding_batch` 与 `vlm_caption_batch` 被解释并移到可选增强：前者用于大量图片的相似图向量，后者用于大量 Krea 2 caption 草稿；二者都不是 WD14 打标，也不执行训练。
- 真实浏览器复现任务页：18 条历史任务直接显示 `model_catalog_snapshot`、`lora_catalog_snapshot`、`comfyui_generate`、`ATTEMPT / WORKER / ERROR`，用户无法判断用途和下一步。
- 设备页增加中文任务说明，只把 ComfyUI 出图、LoRA 清单同步和底模清单同步列为当前实际任务；任务卡显示中文状态、用途和操作建议，技术 ID 与原始错误收进可展开详情。
- 两条已知旧失败任务增加可理解的中文原因：seed 超限，以及旧生成包缺少完整性登记；原始错误仍保留在技术详情中供排查。
- 页面回归断言先按预期失败，完成显示层实现并修正底模按钮术语后，`tests/test_api.py` 4/4 通过；仍待完整工程门与真实浏览器 QA。
- 完整工程门通过：121/121 pytest、80.58% coverage、89 文件 Ruff format、Ruff lint、ty、`uv lock --check` 与 `git diff --check` 全部正常。
- 正式服务已重启到持续会话 `63079`。应用内浏览器以 18 条真实任务验证三类中文任务、中文状态、下一步提示、两条友好失败原因与技术信息展开；684px 窗口 `scrollWidth=clientWidth=669`，无横向溢出，console 0 warning/error。
- 浏览器运行时不支持 `tab.playwright.screenshot()`，首次截图调用失败；查询实际 API 后改用 `tab.screenshot()` 成功。两个 locator 级滚动方法分别不支持与超时，改用页面级 `window.scrollTo()` 完成截图定位，没有触发数据写入。
- 首次单文件 JavaScript 检查没有先去掉 `REMOTE_SCRIPT` 模板开头的换行，导致 `<script>` 标签被送入 Node 并在项目脚本解析前失败；改为先 `strip()` 再移除标签后，真实 JavaScript 语法检查通过。
- 阶段 33 标记 complete；任务书的完成边界同步收敛为 Mac 交付打好标的数据集包，Windows 训练与 LoRA 测试不再作为 Prompt Hub 待办。未 commit、未 push。
- 进一步澄清任务数量：顶部数量改为“条”，任务区动态汇总总历史记录、等待/执行中、Windows 已回传和失败/取消，避免把 18 条历史记录误解成 18 个正在运行的任务。

### 阶段 34–39 新开发计划

- 应用户要求重新列出后续计划，并以最新职责边界替换阶段 33 后的临时 P0/P1/P2 清单。
- 新路线包含：阶段 34 引导式数据集交付台、阶段 35 数据集包冻结与一键交付、阶段 36 本地提示词来源中心、阶段 37 Mac 本地视觉检索、阶段 38 灵感到数据集项目总览、阶段 39 稳定性与公开版本收尾。
- Windows 自动训练、正则、checkpoint/LoRA 测试控制台明确不开发；Windows embedding/VLM 批量加速与 MiniMax H3 明确为可选或延后。
- 本轮只更新 `task_plan.md`、`findings.md` 和 `progress.md`，未修改应用代码、数据库或 Windows Worker；未 commit、未 push。

### 阶段 34：引导式数据集交付台（开始）

- 已恢复任务书、发现记录和进度记录，并审计当前 `workspace_web.py`、数据集路由与导出约束。
- 当前真实“林悔儿”工作区为 72 张有效图片、0 坏图、0 重复、72 份原 caption；Anima 72/72 已审核，图片审核状态仍为 72 张未审核。
- 确认阶段 34 以现有成熟 API 为基础重组页面，不改变 WD14、Caption、审核或导出领域逻辑，也不加入 Windows 训练控制。
- 计划实现五步导航、简单/高级模式、Profile 独立状态、阻塞项与下一步动作；阶段状态已切换为 `in_progress`。
- 页面回归测试按测试先行预期失败，证明新增五步与模式标记尚不存在；完成首轮实现后已转为通过。
- 首轮定向 Ruff 只发现测试断言中的中文全角逗号触发 `RUF001`，产品代码没有 lint 错误；已将断言缩短为不含歧义标点的稳定文案。
- 已完成五步导航、自动推荐步骤、Anima/Krea 2 独立状态、八项可交付摘要、阻塞项与下一步按钮。
- 简单模式按当前步骤和 Profile 收起无关工具；高级检查保留全部筛选、任务、WD14、Krea 2、批量标签、快照和交付面板。
- 所有主要写操作都在附近说明“写草稿/建快照/导出副本”，冻结按钮在当前选择含不可交付项时禁用；页面不提供 Windows 训练控制。
- 应用内浏览器真实验收“林悔儿”：Anima 自动落第 4 步并显示 72 张待审核；Krea 2 自动落第 3 步并显示缺 72 份 Caption；第 5 步未就绪时按钮禁用。
- 浏览器 684px 窗口 `scrollWidth=clientWidth=669`，无横向溢出，console 0 warning/error；简单/高级模式互切及 Profile 专属工具显示正确。
- 完成前工程门通过：121/121 pytest、80.58% coverage、89 文件 Ruff format、Ruff lint、ty、`uv lock --check`、整页 JavaScript、doctor 7/7、正式健康接口与 `git diff --check` 全部正常。
- 阶段 34 标记 complete，操作手册同步为新五步流程；未 commit、未 push。

### 阶段 35：数据集包冻结与一键交付（开始）

- 已恢复任务书、发现记录和历史工作树，确认阶段 35 建立在现有独立版本目录与 ZIP 导出能力之上，不重做数据集导出。
- 已确认缺口为正式交付前检查、Caption 审核状态强制、`hashes.sha256`、文件/容量统计、交付历史、Finder 入口和受控 SMB 复制。
- 计划只允许复制到已登记 `compute_5060ti` 节点的挂载根内；前端不提交任意绝对路径，离线、只读或目标已存在时安全停止。
- 真实“林悔儿”只做只读交付前检查和源哈希验证，不替用户把 72 张图片批量标记为保留。
- 阶段状态已切换为 `in_progress`；未 commit、未 push。

### 阶段 35：数据集包冻结与一键交付（完成）

- 后端完成正式交付前检查、Anima/Krea 2 Profile 隔离、Caption 人工确认强制、来源变化检测、`hashes.sha256`、文件与容量统计、交付历史和受控 Finder 打开。
- 完成 5060 Ti 安全复制：目标固定在已登记 SMB 挂载根的 `prompt-hub/datasets/<数据集名>/<version_id>`，临时复制后核对全目录哈希再原子改名；相同版本幂等返回，内容冲突时停止且不覆盖。
- 页面第 5 步增加正式检查、保存到 Mac、按 Profile 分离的交付历史、下载 ZIP、打开 Finder、复制到 5060 Ti，以及中文加载与错误状态。
- 真实“林悔儿”正式工作区只读复核仍为 72 张图片 pending、Anima Caption 72/72 reviewed、Krea 2 Caption 0/72、无正式导出；没有代替用户修改图片审核状态。
- 使用同一批 72 张真实图片建立临时隔离工作区完成端到端冻结：ZIP 147 项，包含 72 张图片、72 份同名 `.txt`、`manifest.json`、`audit.json` 和 `hashes.sha256`；源目录前后聚合 SHA-256 均为 `c3824e1a94b6a8e61700356f57d01a4ec9a81b9f03db3227c5602747746ccb3d`。
- 受限工作区中先确认阶段 35 的 17 项定向测试、Ruff、ty、锁文件、7 段 JavaScript 与 diff 检查通过；7 项 Worker 测试仅因环境禁止绑定本机临时端口失败，待权限恢复后重跑完整工程门。
- 操作手册与 README 已更新为“正式检查 → 保存到 Mac → 在交付历史下载/Finder/复制到 5060 Ti”的实际顺序，并说明离线与哈希冲突不会覆盖。
- 阶段 35 标记为 `complete`；下一阶段为阶段 36 本地提示词来源中心。未 commit、未 push。
- 权限恢复后重新执行完整工程门：124/124 pytest 通过，coverage 80.64%；89 文件 Ruff format、Ruff lint、ty、`uv lock --check`、7 段页面 JavaScript 和 `git diff --check` 全部通过。
- 正式服务已重启到持续会话 `99984`；`/api/health` 正常，doctor 7/7 通过，SQLite 与 embedding integrity 均为 `ok`，磁盘可用约 711.3 GiB。
- 新建干净的应用内浏览器标签页复验真实数据集：桌面 `scrollWidth=clientWidth=1265`，正式“林悔儿”仍无导出版本，冻结按钮因未选择且 72 张图片尚未审核而禁用，console 0 warning/error。原 684px 用户标签页同样无横向溢出，并验证 Anima/Krea 2 历史独立。

### 阶段 36 / 37：本地来源中心与 Mac 视觉检索（开始）

- 用户要求阶段 36 与 37 连续完成，完成后再测试 5060 Ti；本轮不得以 Windows 在线或远程任务作为 Mac 功能完成前提。
- 现有 4 个 Git 源均为干净 `main...origin/main`，本地数据库已有来源、URL、许可、更新时间和 33,631 条索引；阶段 36 复用现有 fast-forward-only 同步与 FTS，不重建个人收藏逻辑。
- `prompt-library/sources/web` 已预留但为空；阶段 36 将新增有站点白名单、许可策略、内容哈希和图片缓存边界的网页摘录事实源，并以增量 upsert 保留个人收藏、评分和备注。
- 现有 `EmbeddingIndexStore` 已支持版本化真实向量、SHA-256 回验、cosine 查询和按源图查相似；阶段 37 补齐 Mac 本地 encoder、素材发现、可恢复后台索引和查询图片入口。
- 本机已有 ONNX Runtime 1.29.0 与 Pillow 12.3.0，没有 Torch/Transformers/MLX。确定使用 `Xenova/clip-vit-base-patch32` 的 vision ONNX（351,685,709 bytes、512 维、224px）作为 24GB Mac 的轻量起点，不引入 PyTorch 常驻开销。
- 前端沿用现有纸张、墨色、signal/acid 与档案卡设计语言，来源中心以“馆藏台账”呈现，视觉检索以“灯箱/联系表”呈现；普通视图使用中文，高级信息收起。
- 阶段 36 后端第一段已落地：新增固定站点策略、HTTPS/账号/端口检查、受控重定向、Content-Type 与 8 MiB 上限、正文/直链图片缓存、SHA-256 与 manifest，并将网页资料按 URL 增量 upsert 到 FTS。
- Civitai、OpenArt、PromptHero 与 Promptomania 当前默认只保存链接、标题和个人备注；GitHub 与 raw.githubusercontent.com 允许受限正文或直链图片缓存。重复保存同一 URL 不删除 `user_marks`。
- 新增 10 项网页摘录测试，覆盖 link-only、GitHub 正文、图片缓存、内容哈希、重复 URL、收藏保留、白名单、路径安全、重定向与容量上限；定向测试 `10 passed`。
- 阶段 36 API 与页面第一版已接通：资料管理页新增网页保存表单、缓存策略说明、来源/许可/更新时间/条目数/视觉数馆藏台账，以及带来源链接与 SHA-256 详情的网页资料卡；API 定向回归 16 项通过。

### 2026-09-04：阶段 36 / 37 收口验收

- 重新启动本地服务后，真实页面显示 1,450 张本地视觉索引：提示词视觉 827、数据集 72、ComfyUI 回流 4、LoRA 预览 386、底模预览 161。
- 收紧上传图片查询的版本边界：只能查询当前固定 CLIP model/revision 生成的索引，不会因其他模型恰好也是 512 维而串用不兼容向量。
- 新增版本隔离、视觉簇分组/类型过滤和页面入口回归；阶段 36/37 相关 28 项测试使用 `--no-cov` 实际通过，完整 coverage 门留到全量工程门复核。
- 应用内浏览器验收因 macOS 锁屏无法接入；Playwright 技能自带包装脚本又因无执行权限与 CRLF 行尾连续失败。已改用 `npx --package @playwright/cli playwright-cli` 直接入口，不修改技能文件；桌面页面已真实渲染，继续完成上传、灯箱、视觉簇、来源中心和窄屏验收。
- 真实上传 Kisegaeningyou 参考图 `1741118591102.png` 查询成功，返回 48 张真实相似图；首张为原图、相似度 100%，其他结果带真实来源、本地媒体路由和内容分级。
- “浏览视觉簇”实际从 240 张近期素材生成 27 个簇，页面按上限展示前 24 簇、237 张卡片，同时出现 Kisegaeningyou 和 Clio Style Library 结果。
- 资料管理页真实显示 6 个来源、33,633 条资料、2,921 个视觉参照和 2 个网页来源；AnimaDex 为已离线缓存，林悔儿 Civitai 条目为只保存链接，均可回看原网址、许可与 SHA-256。
- 684×900 窄屏验收：页面 `innerWidth=684`、`scrollWidth=684`，导航入口全部可见，视觉簇 237 张可见卡片中 0 张损坏图；来源中心同样无横向溢出，6 行来源、2 张网页卡和保存表单均可见。控制台 0 error / 0 warning。
- 阶段 36/37 完成前工程门通过：97 个文件 Ruff format、Ruff lint、ty、142/142 pytest、80.43% coverage、`uv lock --check`、整页 JavaScript、`git diff --check`、正式 SQLite 与 embedding SQLite `integrity_check=ok`。CLIP ONNX 的 351,685,709 bytes 和 SHA-256 均与固定元数据一致；正式健康接口、1,450 张索引和 6 个来源均返回预期状态。
- README、Mac 日常操作手册、总开发计划和任务书已改为当前真实边界：Mac 可独立保存来源、以图找图和浏览视觉簇；Windows embedding 仅是未来超大批加速选项。阶段 36、37 标记 `complete`，下一阶段为 38；未投递、未测试 5060 Ti，未 commit、未 push。
- 页面组合曾把来源中心插到 `managementPage` 外部，HTML 栈检查发现后已改为管理页子节点；最新解析栈明确包含 `managementPage → sourceCaptureForm`，不会在其他页面常驻显示。
- 新增素材发现测试文件时有一次工具输入格式错误；调用在解析阶段停止，未写入文件。已改为独立补丁继续，这不是应用代码失败。
- Hugging Face 先前审计记录的 revision `e6a30b...` 已失效并返回 404；通过模型 API 重新确认当前固定 revision 为 `d15189d...`。首次下载在 296,417,780 bytes 处中断，使用同一目标续传后完成 351,685,709 bytes，SHA-256 为 `fd6e1402...d7d40`。
- CLIP Vision ONNX 已安装到个人模型目录并保存 `model-info.json`；真实加载一张本地图得到 512 维向量，L2 范数约 `0.99999997`，确认模型输出和预处理匹配。
- 首次完整 Mac 索引发现并成功写入 1,450 张、失败 0：提示词视觉 827、数据集 72、创作/ComfyUI 结果 4、LoRA 预览 386、底模预览 161。第二次完整运行新增 0、跳过 1,450，验证增量路径。
- 使用真实创作结果图进行上传查询，返回数据集、LoRA、提示词视觉和 ComfyUI 回流等真实邻居；前 5 项相似度为 1.0、0.8345、0.8289、0.8155、0.8152。80 张样本可整理为 20 个视觉簇。

### 2026-09-04：阶段 38 灵感到数据集项目总览（收尾中）

- 新增项目总览、项目结果同步与来源档案的主体实现已经进入最终验证；继续保留“只同步手动精选、不自动审核、不替用户批准图片、外部数据集独立”的边界。
- 复核发现 `project_revision` 曾重复写入单图来源、但遗漏在工作区 origin；已改到正确层级，并新增“同步后直接打开、项目再次修改后才提示更新”的回归断言。
- 第一次定向 lint 被测试文案中的全角逗号拦截，改为普通逗号后重新运行；Ruff、ty 与阶段 38/API 定向测试 5/5 通过。
- 正式服务已重启为 PID 42156。真实浏览器确认 1462px 为 3×2、684px 为单列且无横向溢出，总览标题不再受全局 `header` 样式影响产生大块留白。
- 浏览器接口不支持直接设置 viewport，已改用现有 684px 应用内窗口和 1462px Edge 窗口分别验收，没有修改产品代码规避工具限制。

### 2026-09-04：阶段 38 灵感到数据集项目总览（完成）

- 创作台完成六阶段事实总览和下一步入口；手动精选结果可建立项目专属数据集工作区，重复同步幂等，项目 revision 变化后才提示更新。
- 每张同步图片与冻结版本完整保留项目、结果图、双 Profile Prompt、ComfyUI workflow、checkpoint、LoRA、seed、尺寸、Steps、CFG 和 SHA-256；工作区与交付版本可返回来源项目/结果图。
- 同步不改变图片 `pending`、`selected`、`approved` 或 Caption reviewed 状态；正式“林悔儿”72 张外部数据集仍保持独立且未替用户审核。
- 浏览器发现并修正结果阶段按钮落点；1462px 为 3×2、684px 为单列且无横向溢出，修正后结果区落点可见，两个窗口 console 0 warning/error。
- 完整工程门首次附加 SQLite 脚本误写为不存在的 `Settings.from_env()`；改用实际 `Settings.from_environment()` 后，正式主库与 embedding 库均为 `integrity_check=ok`。
- 文档更新前的完整门为 143/143 pytest、80.63% coverage、99 文件 Ruff format、Ruff lint、ty、`uv lock --check`、8 段页面 JavaScript、`git diff --check`、doctor 7/7 和正式健康接口通过。阶段 38 标记 complete；未连接或投递 5060 Ti，未 commit、未 push。
- README、Mac 操作手册、总开发计划、任务书和研究记录更新后重新执行最终工程门：143/143 pytest、80.63% coverage、99 文件格式、Ruff lint、ty、锁文件、8 段 JavaScript、doctor 7/7、两库 integrity、正式健康接口与 diff 检查全部通过。

### 2026-09-04：阶段 39 稳定性回归（进行中）

- 只读审计确认四个缺口：项目专属数据集来源未进入备份；冻结时底层 I/O 错误会越过用户提示；磁盘不足缺少无残留测试；SMB 与服务重启缺少连续恢复场景。
- 先写回归并复现：定向测试中 2 项按预期失败，分别证明 `datasets/project-sources` 未备份，以及冻结 I/O 错误直接抛出 500；其余磁盘不足、SMB 离线恢复、服务重启恢复场景已在现有机制上通过。定向运行触发全局 coverage 门低于 80%，这是只运行少数测试导致，不是新增功能失败，最终会执行完整测试集。
- 已做最小修复：备份加入 `datasets/project-sources`；冻结异常统一转为中文可恢复错误并保留半成品清理；数据集和设备普通状态改为中文，保留技术值仅供内部逻辑使用。

### 2026-09-04：阶段 39 自动交付完成，等待人工验收

- 新增 `MANUAL_ACCEPTANCE_GUIDE.md`，按日常创作、Windows 离线、结果到数据集、外部旧数据集、资料更新、项目变化、SMB 断线、服务异常、磁盘不足和备份恢复十种情景说明操作顺序，并提供不修改正式数据的人工验收清单。
- 正式服务在无活动任务时从 PID 42339 重启到 PID 43871。重启后健康接口正常；“黄昏图书馆调查员”仍为 revision 25；“林悔儿”仍为 72 张全部 pending、0 selected、72 Anima reviewed、0 Krea 2，正式数据没有被测试改变。
- 首次正式备份虽然校验成功，但因 `remote-nodes` 整体复制把 846 MB LoRA 和 428 MB 底模预览缓存纳入，体积约 1.37 GB。先增加失败回归，再排除这两类可重建缓存；旧中间备份已移到废纸篓，可恢复。
- 最终正式备份位于 `/Users/soda/Documents/Codex/soda-person/backups/prompt-hub/20260904-stage39-final`：209 个文件、37,196,600 bytes、两个 SQLite 完整性均为 `ok`。隔离恢复位于 `/Users/soda/Documents/Codex/soda-person/restore-tests/prompt-hub-stage39-20260904`，文件哈希、SQLite 和关键事实数量一致。
- 应用内浏览器 684px 验收：无横向溢出，工作区显示“可使用 · 72 张”，设备离线显示“共享目录未挂载”，LoRA 256 个和底模 140 个分别位于独立子页。隔离桌面浏览器 1462px 验收：六张项目卡为 3×2、数据集冻结按钮禁用、控制台 0 warning/error。
- 完成前新鲜工程门：146/146 pytest、80.74% coverage、101 文件 Ruff format、Ruff lint、ty、`uv lock --check`、8 段页面 JavaScript、`git diff --check`、doctor 7/7、正式两库 integrity、敏感信息形状、仓库大文件和二进制资产检查全部通过。
- 阶段 39 功能开发与自动验证完成，等待用户按人工验收清单检查。未 commit、未 push、未创建 PR 或 release tag。

### 2026-09-04：阶段 40 界面语言与操作引导（完成）

- 按真实使用顺序逐页复核普通界面，保留现有纸张、墨色和卡片式视觉风格，不改后端协议或正式数据。
- 首页、创作台、提示词库、智能检索、角色库、数据集、LoRA 数据集、Windows 出图和资料管理的主要标题、按钮、状态与空页面已改成直接中文；Anima、Krea 2、LoRA、WD14、Checkpoint、VAE 等必要专业名词保留。
- 设备连接页明确 Finder 与钥匙串的职责，LoRA 和底模分别说明清单边界；任务按“需要处理”和“历史记录”分组，18 条既有记录不会删除。
- 补充清理项目卡的 V/R、参考卡 REMOVE、WD14 General/Character、原始安全分级值和 LoRA BASE/TRIGGER/TAGS 等开发者式显示。
- 完整工程门通过：146/146 pytest、80.74% coverage、101 文件 Ruff format、Ruff lint、ty、`uv lock --check`、8 段页面 JavaScript、`git diff --check`、doctor 与正式两库完整性检查全部正常。
- 正式服务重启后，应用内浏览器以 669px 逐页检查首页和 9 个功能页，所有页面均无横向溢出，旧文案扫描为空，控制台 0 warning/error。
- 隔离浏览器以 1462px 复核 Windows 出图、创作台、数据集与设备连接；发现 Windows 出图卡片中的竖图按固有宽度撑开网格，补充图片容器和卡片正文的收缩约束后，1462px 与 669px 都恢复为页面宽度内显示，控制台仍为 0 warning/error。
- 正式数据未被验收改动：设备页仍保留 18 条任务，“林悔儿”72 张图片的审核、选择和说明状态不变；未连接 Windows、未发送远程任务。
- 阶段 40 标记 complete，等待用户按 `MANUAL_ACCEPTANCE_GUIDE.md` 人工验收。未 commit、未 push、未创建 PR。
- 2026-09-05：开始阶段 42 个人版 1.0 发布收口。按用户确认先做第一层，不增加新功能，不操作个人数据库、模型、提示词库或 5060 Ti。
- 已将本地 `main` 从 `d2a25fb` 快进到远端 merge commit `ca559ff`，并建立本地分支 `codex/release-v1.0-hardening`；工作树起点干净。
- 本轮计划覆盖版本与产品名、公开 README、完成度/验收文档、CHANGELOG、GitHub Actions 和最终验证；LICENSE 等待用户选择，commit、push、PR、tag、Release 均等待另行确认。
- 首次整块发布补丁因 README 的预期重复行与实际文件不一致而整体拒绝；确认没有部分写入后改为按产品文件、README 和文档分别应用，没有覆盖既有内容。
- 已将软件包版本改为 `1.0.0`，浏览器标题与首页状态统一为 Soda Prompt Hub 个人版 1.0；公开 README 增加通用资料目录示例并清理固定来源数量。
- 已新增 `CHANGELOG.md` 和最小权限 GitHub Actions；完成度审计与候选验收报告改为阶段 34–41 后的真实边界，历史阶段 17–25 的过期状态同步收口。
- `BASELINE.md` 已明确为历史快照；开发计划增加个人版 1.0 状态说明；绘图短流程补充直接发送 5060 Ti 与离线 JSON 两种路径。
- 候选版首次全量测试为 159 通过、1 失败；失败只来自页面测试仍断言旧标题 `Soda Prompt Archive`。根因是产品命名契约同步遗漏，已将同一测试更新为 `Soda Prompt Hub`，等待完整复验。
- 更新标题测试后从头复验：160/160 pytest 通过，coverage 80.13%；105 个文件 Ruff format、Ruff lint、ty、`uv lock --check` 与 `git diff --check` 全部通过；`prompt_hub-1.0.0` wheel/sdist 构建成功，GitHub Actions YAML 本地解析成功。
- 确认没有运行中的后台任务后重启正式 8765 服务。Playwright 桌面首页确认标题与“个人版 1.0”，点击“数据集”成功；390×844 窄屏 `scrollWidth=clientWidth=390`，两种视口控制台 0 warning/error。
- 阶段 42 的实现与本地验证完成，状态改为 `ready_for_owner_decision`。仍未添加 LICENSE，未 commit、push、创建 PR、tag 或 Release。
- 用户确认采用 MIT License；已新增标准 MIT 文本，版权持有人为 `cOkieeman`，并在 README 明确第三方提示词、图片、模型、工作流和数据集不随项目代码重新授权。
- Python 包元数据同步声明 `license = "MIT"`，确保源码许可证与构建产物元数据一致。
- 本轮开始时有数次工具脚本输入不完整/参数错误，均在执行任何文件或系统操作前被拒绝；随后改用最小 `pwd` 调用确认工具恢复，没有产生副作用。
- 阶段 42 本地实现已全部完成；仍未 commit、push、创建 PR、tag 或 Release，等待用户另行确认 Git 发布动作。
- MIT License 与 Python 包元数据加入后重新执行完整验证：160/160 pytest、80.13% coverage、Ruff、ty、锁文件、diff 检查和 `1.0.0` wheel/sdist 构建均通过。
- 2026-09-05：用户明确授权提交并发布个人版 1.0；阶段 42 进入 `publishing`，发布范围包括 commit、push、PR、合并、`v1.0.0` tag 与 GitHub Release。发布前继续执行敏感信息、文件范围和大文件检查。
- 提交前敏感信息与大文件扫描通过；`task-...` 历史任务 ID 被宽泛的 `sk-` 规则误报，人工确认不是密钥。精确暂存 16 个版本、文档、CI、测试与许可证文件，没有个人数据库、模型、图片或连接凭据。
- 已创建提交 `9447661` 并推送分支 `codex/release-v1.0-hardening`；发布 PR #4 的首次 GitHub Actions quality job 全部通过（run `33936005792`，耗时约 1 分 26 秒）。
