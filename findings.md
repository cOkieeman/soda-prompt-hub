# 发现与决策

## 2026-09-05 PR #2 外部模型 API 审查

- PR #2 基于 `91fce13`，比当前 `main` 落后 3 个 commit，并与 `creative_web.py`、`creative_web_layout.py` 冲突。
- PR 误删绘图页底部核心函数和事件绑定，导致新建、取材、结果图复盘、数据集导出与 5060 Ti 投递等按钮失效；不能直接合并或 cherry-pick。
- `GET /api/models/config` 返回完整模型配置和明文 API Key；配置路径在个人库无文件时回退到仓库内 tracked `models.json`，存在误提交密钥风险。
- 前端模型保存硬编码 `provider: custom`，却展示 Anthropic/Gemini 等原生端点；后端实际主要走 OpenAI-compatible 协议，产品声明与实现不符。
- 保存按钮会收集全部 `.api-add-btn`，而不是仅收集用户点过“＋”的模型；单选会变成全量添加。
- `_resolve_endpoint()` 没有解析真实 `model_name`，友好配置 ID 可能被错误发送给上游 API。
- PR 分支质量门：98 项测试执行通过但 coverage 78.45% 未达 80%；Ruff format 失败、Ruff lint 294 项、ty 1 项。当前 `main` 为 146/146、coverage 80.74%，格式/lint/ty 全通过。
- 阶段 41 决策：不修补 PR 分支，改为在最新 `main` 上按本地优先架构重做；首版只承诺 LM Studio 与 OpenAI-compatible。

## 2026-09-05 阶段 41 现有架构接入点

- `local_model.py` 当前有四条推理路径：槽位整理、检索词扩展使用 LM Studio 的 OpenAI-compatible `/chat/completions`；结果图分析、Krea 2 caption 使用 LM Studio 原生 `/api/v1/chat`。
- `create_app()` 已持有明确的 `active_settings`，适合构造单一 `ModelConnectionStore`；API 调用可显式传入该 store，避免依赖全局缓存或重新读取环境变量。
- `DatasetCurationStore` 已支持注入 `krea2_captioner`，因此可用闭包把同一个模型 store 传给后台 Krea 2 caption，不需要改动其任务协议。
- 新增独立 `model_connections.py` 与 `model_routes.py`，可以避免继续膨胀 `api.py`，并保持 `/api/local-models` 兼容现有测试和外部调用。
- 新的统一 `/api/models` 只负责合并本地 LM Studio 模型和已保存的外部模型；现有 `/api/local-models` 保留不变。
- 配置文件固定为 `library_root/private/model-connections.json`，不允许回退仓库目录；写入后收紧为用户读写权限。公开响应只返回 `has_api_key`，永不包含 `api_key`。
- 首版 URL 边界为远程必须 HTTPS、HTTP 仅允许 loopback；协议固定标记为 `openai_compatible`。模型列表由后端访问 `/models`，失败时仍允许手工填写模型名称。
- 前端只在现有“本地模型辅助”区域增加折叠式可选管理，不新增第二套失效的模型选择器；`#lmModel` 与 `#visionModel` 继续作为真实任务选择入口。
- 外部推理不能复用 `urlopen()` 的默认重定向策略，否则带 Bearer Key 的请求可能跟随到非预期地址；外部文本和视觉调用统一禁用重定向并限制响应体，LM Studio 本机调用继续保持原行为。
- `external-<16 hex>` 是保留连接 ID。若对应配置已删除，必须在模型解析处立即报错，不能把这个 ID 当作 LM Studio 的真实模型名继续请求。

## 2026-09-03 LoRA Manager 接入探测

- Windows 在线且 SMB/ComfyUI 端口 TCP 可达，但 Mac 当前没有 SMB volume；Finder 需要用户本人重新完成凭据确认。
- 原任务真实挂载记录确认 SMB 专用账户为 `PromptHubWorker`，完整账户为 `CHINAMI-5E1E3GQ\PromptHubWorker`；旧连接信息文件中的 `Administrator` 已过期，Finder 自动填入的 `soda` 只是 Mac 本机用户名。
- ComfyUI HTTP 端口可建立 TCP 连接但没有返回 HTTP payload，因此不把直接访问 8188 作为 LoRA Manager 集成前提。
- UU 远程终端可打开，可在不共享整个 `F:` 盘的情况下只读检查 `F:\Comfyui\ComfyUI-aki-v3\ComfyUI\custom_nodes\comfyui-lora-manager`；实际部署仍通过现有共享桥完成。
- 真实诊断报告已通过 SMB 到达 `diagnostics/lora-manager-inspection.json`：插件存在，ComfyUI LoRA 根目录含 256 个模型文件与 375 个预览文件，`/object_info/LoraLoader` 返回了完整可用 LoRA 名称列表。
- 插件目录没有可用 `.git` HEAD/remote，内部数据采用同名 `.metadata.json` sidecar 约定；因此正式同步不依赖插件私有 API。稳定主链采用 ComfyUI `LoraLoader` 名称 + 白名单根目录文件/sidecar/预览扫描，`/loras/api/list` 只作为未来可选增强。
- Mac 直连 `http://192.168.1.10:8188/loras/api/list` 仍得到 empty reply；Windows 本机访问公开 ComfyUI 接口正常。这再次确认 Worker 应在 Windows 本机读取，Mac 不依赖 8188 局域网访问。
- 为避免读取数十 GB 权重，快照不计算 `.safetensors` 内容 SHA-256；只记录相对路径、文件大小、mtime、可选 sidecar metadata 和预览相对路径。清单 JSON 本身作为 Worker 输出再由 Mac 做 SHA-256 验收。
- 真实任务 `task-20260902T172354Z-8f3dcc8f59e5` 已由 Windows Worker 完成；清单输出 SHA-256 为 `e6143eaa1b579620c8d0af8ce2765488dd2525a2bec7989527be9630f57e53ed`，Mac 回验 `verified=true`。
- 快照 `catalog-20260902T172356Z-60e595c5d3da` 导入 256 条：233 条有 sidecar metadata、210 条有预览路径、122 条有 trigger words、233 条复用 LoRA Manager 已有权重 SHA-256。Mac 只保存标准化只读索引。
- 真实模型族统计为 Anima 74、Illustrious 81、Krea 2 45、Flux 3、SDXL 9、Unknown 44。`linhuier` 可唯一检索到 `Anima/Character/linhuier-anima_v01.safetensors`，Civitai model/version 为 `2885952/3262276`；sidecar 没有 trigger words，因此没有擅自补写 `linhuieroc`。

## 2026-09-02 单一 5060 Ti 计算节点

- 用户取消 4070S，5060 Ti 统一承担 ComfyUI 制图、AnimaLoraStudio 训练、批量 VLM、Embedding 与 WD14 批处理；ComfyUI 内的 LoRA Manager 插件负责 Windows 本机 LoRA 扫描、预览和选用。
- Mac 不直接连接 LoRA Manager。Windows Worker 已在本机读取插件 metadata、预览与 ComfyUI LoRA 目录，并向 Prompt Hub 同步只读标准化清单；训练、Embedding 与 VLM 仍是后续独立适配器。
- 当前正式 `remote-nodes` 目录没有 `nodes.json`、没有历史跨设备任务，Mac 也没有 SMB 挂载；因此无需迁移或删除用户节点数据。
- 旧协议把每个任务绑定到单一角色，不能只改页面文案；需要统一 `compute_5060ti` 角色并将协议升级为 `soda-compute-bridge-v2`。
- 单张 5060 Ti 16GB 不能稳定并行运行 ComfyUI 与 LoRA 训练。Windows worker 应采用单 GPU 串行队列：训练和制图互斥，Embedding/VLM/WD14 只在空闲时执行，不自动中断正在运行的训练。
- SMB 仍只作为传输面，Mac 保存任务事实副本、项目、审核和版本；Windows 密码继续只交给 Finder/macOS Keychain。
- 接入所需最小用户信息是设备名/IP、共享名、ComfyUI 根目录与输出目录、训练工具及其目录、底模/LoRA 目录；不需要在聊天中提供密码。
- 真实 SMB 已通过专用标准用户挂载到 `/Volumes/PromptHub-5060Ti`，五目录可写且 Prompt Hub 诊断为 `ready`；凭据未进入节点 JSON。
- Windows 已确认系统 Python 3.12.10，ComfyUI 在 Windows 本机 `http://127.0.0.1:8188` 可用。首版 worker 可使用 Python 标准库，避免在秋叶整合包环境里额外安装依赖。
- worker 运行在 Windows 本机，因此 ComfyUI 不需要暴露到局域网；Mac 只经 SMB 投递任务，worker 仅访问本机 8188，缩小网络暴露面。

## 2026-09-02 Anima / Krea 2 Workflow Profile 实机结果

- 两份原始 API workflow 已按 SHA-256 导入 Mac `workflow-profiles`：Krea 2 为 `6016f8...b9ade`，Anima 满穗为 `6b0559...9c47b`。
- Krea 2 低成本编译由 14 节点裁到 11 节点，绕过 SeedVR2；任务 `task-20260902T130215Z-2d7d6e4b41c3` 在 Windows ComfyUI 真实完成。
- Krea 2 回传 PNG 为 512×768，画面包含原 Prompt 的海边、亮片比基尼、紫红盘发、浅色瞳与左下签名；基础构图和模型加载有效。
- Krea 2 Mac integrity 为 `verified=true`，PNG SHA-256 `b84cf026...fb48ba`，workflow 与 run log 同时回传。
- 浏览器创作台能按当前 Prompt Profile 精确筛选 workflow：Anima 只显示满穗，Krea 2 只显示 Ares OC Manager；正常视口无横向溢出且 console 无 warning/error。
- Anima 修正 seed 后的任务 `task-20260902T130550Z-f0560673eff3` 在约 6.5 秒完成；512×768 图像保留黑发侧髻、灰眼、发饰与中式服装，角色 LoRA 生效，Mac integrity `verified=true`。
- 回流解析暴露源 workflow 的 Image Saver 元数据与实际 sampler 默认值不一致：保存节点写 10 steps / CFG 5，实际采样节点为 12 / 1。后续编译必须同步保存字段，不能让结果库记录错误参数。
- 修正后的 Anima 固定 seed 任务 `task-20260902T130944Z-43c6a204932d` 再次真实完成，回流 metadata 正确记录 seed 42、12 steps、CFG 1、512×768 与 `anima-base-v1.0`。
- 固定 seed 42 的最终 Anima 图已从 Mac 结果库人工查看，仍稳定呈现满穗的黑发侧髻、灰眼、花饰与灰白中式服装，人物一致性正常。
- 两类真实图均已复制进入 Mac ComfyUI 结果库；源 SMB 图片保持不变。由于烟雾任务使用 workflow 原始 Prompt 而非创作项目，当前结果没有伪造项目关联。

## 2026-09-01 Mac 发布前标签语言闭环审计

- 本轮只本地化用户可选择的 canonical tag 与覆盖枚举；Trigger、checkpoint、LoRA 名称、ComfyUI 参数等技术元数据保持原样。
- 界面层允许中文或中英文对照，持久化层继续保存英文 canonical ID；Anima caption、Krea 2 正式 caption 与 LoRA 冻结包仍必须通过英文输出门。
- 审计优先级为 LoRA 项目台、数据集批量编辑、创作台 character candidates、智能检索和 Windows LoRA metadata 页面；不能仅凭全局切换按钮存在就视为闭环。
- 已确认的界面缺口：创作台 WD14 `character candidates` 仍显示裸英文；数据集批量增删仍要求普通用户直接输入英文 tag；智能检索卡片未按资料类型本地化 canonical tag。
- LoRA coverage 选择已采用中文 label + 英文 ID，符合显示/存储边界；但偏置警告当前用维度字典查枚举值，可能显示 `undefined`，需改为从对应 coverage item 查中文 label。
- Windows LoRA snapshot 的模型名、路径、base model 与 trigger 属于技术元数据，必须保持原样；其中 `tags` 可跟随全局按钮切换显示，但 snapshot 底层不能修改。
- 数据集批量操作的安全做法是在 `_normalize_tag()` 中先解析已知中文名，再走既有 Anima tag 规范化；这样中文只作为输入别名，预览、快照和 caption 从第一步起就是英文。
- 对未知中文标签必须返回明确错误，不能自行翻译成未经确认的 canonical tag；高级用户仍可直接输入英文自定义 tag。

## 2026-09-01 Windows 交付桥 Mac 侧收口

- 现有五目录与 compute contract 只定义了协议，尚未有任务投递、状态扫描和显式重试；这些可以在没有真实 Windows 的情况下先完成。
- Mac 需要在本地 `remote-nodes/tasks/<node>/<task>.json` 保存原始任务事实副本，共享目录只作为传输面。这样 Windows 将 outbox 文件移动到 processing/failed 后，Mac 仍可安全重试且不会依赖失败结果中包含完整原 payload。
- 重试应创建新 task ID、增加 `attempt` 并记录 `retry_of`，保留旧失败记录用于审计；不复用 task ID，也不覆盖 failed 文件。
- 任务 JSON 必须拒绝凭据字段，校验目标角色、节点 capability、manifest 相对路径和 SHA-256；模型结果只显示为 returned，仍由既有领域导入接口和人工审核进入 Mac 事实库。

## M2 架构续接

- `BackgroundJobRunner` 已具备 SQLite 持久化、单 worker、重启恢复、取消、自动重试和进度更新；M2 应新增 `dataset_wd14` handler，不另建队列。
- `DatasetWorkspaceStore` 是工作区派生状态的唯一入口，源目录已经由路径校验和只读扫描保护；WD14、caption、snapshot、audit 与 export 元数据应写入工作区目录，而不是源图片旁。
- `api.py` 当前只注册 `dataset_scan` handler；明天接 5060 Ti 时可把相同任务 payload 交给 compute bridge，Mac 仍保留工作区状态和审核决定。
- 现有结果精选区的 `dataset_tagging.py` 已验证 canonical English tag、rating/general/character 分组与人工确认语义，可复用数据形状，但工作区任务需要独立持久化和批量接口。
- M2 的安全边界保持为：WD14 只写 Anima 草稿；Krea 2 caption 独立；中文只用于显示；任何最终训练导出含中文都必须拒绝；原始 `.txt` 不回写。
- 首次写入本节时因误判文档标题导致 patch 未命中；读取实际标题后改用正确锚点，未影响业务文件。
- 长队列不能逐图重复创建 ONNX session；`WD14Tagger` 在任务开始时加载一次模型，之后复用同一 session，现有单图 `tag_image` 包装器保持兼容。
- 仅靠后台任务恢复为 queued 不足以实现真正续跑；逐图结果必须记录原任务 `job_id`，相同任务恢复时才可以安全跳过已完成图片，而新的“全部重跑”仍能覆盖未人工确认草稿。
- Caption snapshot 必须携带 `profile_id`。缺少分支信息会让 Krea 2 回退误写 Anima；旧 `edit-krea2` 快照可按 operation 兼容推断，新快照全部显式记录。
- 工作区导出必须在复制前重新计算源图片 SHA-256，并拒绝未审核、缺 caption、非英文、完全重复和同 stem 冲突；通过后再生成独立版本目录与 ZIP。
- 资料库初始标签预载可能超过 `/api/tags/localize` 的 500 条请求边界；前端应按 500 分批，不放宽服务端输入上限。

## V1.7A 数据集工作台

- 小数据集可能在注册后的同一秒完成扫描，不能只依赖秒级 `updated_at` 判断是否需要加载报告；
  前端还必须以“当前是否已有 report”作为加载条件。
- 审核状态应与扫描报告分离：扫描报告是版本化事实记录，`review.json` 是可编辑人工决策；重新扫描
  不应抹掉已有保留、排除和备注。
- 原图浏览不能接受任意相对路径；必须同时满足路径仍位于来源目录、且图片存在于当前扫描报告。
- 5060 Ti 接入前先固定任务信封、状态流和能力名称，可以避免把 SMB 地址、任务格式和业务状态
  混在同一轮调试；Mac 继续是项目与审核的唯一事实源。

## 阶段 16 工程基线审计

- 项目已经是 Git worktree，分支为 `main`，但 HEAD 尚无 commit；因此不需要重新 `git init`，只需安全筛选文件并创建首个本地快照。
- 当前没有配置 Git remote；本轮基线不会产生任何网络写入。
- 项目目录内未发现 `.env`、私钥、SQLite/DB 文件或大于 10 MiB 的普通待提交文件；敏感关键词只按文件名返回的扫描也无命中。
- 正式资料根目录与代码仓库分离：数据库约 71 MiB，公共 Git 资料约 978 MiB，缩略图约 7.5 MiB；可重建公共资料不需要复制进工程基线。
- `private`、`test-results`、`exports` 当前磁盘占用为 0，但仍应进入备份目录和清单，以保护后续数据布局及恢复流程。
- `.gitignore` 需要新增 `.pytest_cache/`、`.ruff_cache/`、`.playwright-cli/`、`.env*`、密钥/证书、数据库/WAL、日志、备份和本地数据目录规则。
- SQLite `.backup` 可在 8765 保持运行时生成一致快照；本次快照独立校验为 `ok`，无需停止正式服务。
- LM Studio MCP 配置只复制到 Git 仓库外的私有备份目录，Git 中只保留“配置已备份”的记录，不记录配置内容。
- 待提交候选全部为文本代码/文档/测试/锁文件；多规则敏感扫描无命中，且本地数据类型均由实际 `git check-ignore` 证明被排除。
- 基线验证首次暴露 5 个历史格式偏差；使用项目锁定的 Ruff 统一格式化后，完整测试与静态检查均通过，说明可在干净格式状态建立首个 commit。
- 当前环境没有 GitNexus MCP/索引工具；安全重构改用 `rg` 映射 `create_app`、`CreativeStore`、`PromptDatabase` 和路由调用者，并以 43 项回归测试约束行为。
- `api.py` 的数据集路由形成清晰连续边界：数据集 ZIP、精选状态、单图/批量 WD14、审核确认和导出文件；适合作为首个独立 `APIRouter`，对外路径可完全不变。
- 当前 FastAPI 的 `include_router()` 会在 `app.routes` 放置 `_IncludedRouter` 包装器；重构前后路由一致性不能只比较顶层 route 对象，应比较 `app.openapi()["paths"]` 的 path/method 集合并辅以 TestClient 请求。
- 后端拆分后 `api.py` 减少 239 行，OpenAPI 31 条路径及方法集合与基线完全一致；数据集 API 已形成可供 V1.7 扩展的独立边界。
- 前端布局提取后，创作台 HTML 片段和最终组装页面的 SHA-256 均与基线一致；静态拆分可以用最终 bundle hash 比仅检查 DOM 数量更严格地证明无视觉/脚本变化。
- 代码拆分变更暂不自动创建第二个 commit：`230185d` 保持为可直接回退的 V1.6 基线，重构 diff 留给用户确认后再提交。
- `creative_web.py` 已按 CSS、HTML、JavaScript 三个顶层字符串分段，后续可逐段提取；但与 API 同轮大搬移会放大问题定位范围，因此先完成后端路由拆分。

## V1.7 第一段：可恢复任务与只读扫描

- 数据集来源目录继续作为原始事实源；工作区只保存 manifest、扫描报告和派生缩略图，扫描与重新扫描都不移动、不改名、不写回图片或 `.txt`。
- 任务状态必须落在 SQLite，而不是只存在于前端内存；这样服务重启时可把中断的 running 任务恢复为 queued，并保留已完成、失败和取消记录。
- 首版使用单后台 worker：图片解码、缩略图和后续 WD14 都是 CPU/内存密集任务，24GB MacBook Air 上并行多个批任务会降低交互稳定性。
- 自动重试与用户重试语义分开：临时失败按 `max_attempts` 自动重试；已经 failed/canceled 的任务只有显式 retry 才重新排队。
- 只读扫描必须拒绝 `/`、用户主目录、Prompt Hub 资料库根目录和包含工作区的过宽父目录；目录内部符号链接不跟随，避免越界和递归扫描自身产物。
- 同名 caption 采用“同目录、去扩展名一致”的配对规则；图片存在但 `.txt` 缺失与 `.txt` 没有图片分别报告，不能合并成一个笼统错误。
- 完全重复采用文件 SHA-256；近似重复采用 64-bit pHash 与 Hamming distance 5。pHash 基于 32×32 灰度 DCT 低频系数，比分辨率敏感的 dHash 更符合训练集去重目标。
- 扫描报告按时间与随机后缀版本化，重新扫描只更新 workspace 的 current report 指针，旧报告继续保留，便于后续审核与导出追溯。
- 缩略图按原图 SHA-256 前 20 位命名并限制为安全的 `.webp` 路由；前端后续可以直接构建视觉总览，而无需开放任意本地文件路径。
- 当前后台框架已经能承载 V1.7 WD14 长队列，但现有“精选结果图同步 24 张”端点尚未迁移；必须在工作区审核 UI 与逐图状态模型完成后再切换。
- 正式部署后 OpenAPI 为 40 条路径，旧 31 条路径全部保留；首页 bundle hash 与纯重构基线一致，新增能力当前只在后端，不会让现有用户流程突然变化。
- 正式库初始化后台任务表后完整性仍为 `ok`，资料与来源计数不变；任务记录和工作区 manifest 分别承担运行状态与文件事实来源，避免把大型扫描报告塞入主 SQLite。

## V1.6 后续路线审计

- 当前闭环覆盖“创作项目 → 结果图 → 精选 → WD14 草稿 → 人工审核 → caption → ZIP”，但输入仍局限于项目结果图，不是完整训练数据集管理器。
- `api.py`、`creative_web.py` 与 `database.py` 已成为后续变化最集中的文件；继续增加批量任务、数据集浏览和 Windows 状态前应先按领域拆分。
- 当前 Git 工作树中的项目文件均未被跟踪，也没有显示已配置的 remote；在继续大规模开发前需要建立可恢复基线，但 commit/push 必须等待用户明确授权。
- V1.7 的最高价值是导入任意真实数据集目录、检查图片-caption 配对、批量审核、标签统计和重复检测，而不是再增加一个单图按钮。
- 去重首版采用 SHA-256 识别完全重复、pHash 识别近似重复；CLIP embedding 更适合后续相似图检索和视觉聚类，不作为基础去重前置条件。
- ComfyUI 的 PNG 内嵌 workflow 与生成参数可以先通过文件导入回流，不需要先建立 SSH 或直接队列连接。
- Windows 交付首版优先共享目录：4070S 主机接收生成任务，5060 Ti 16GB 主机接收训练包；Mac 保持本地中枢和唯一审核入口。
- Krea 2 自然语言 caption 需要 VLM，而本机 Qwen3.5 9B 视觉实测约一分钟/图，因此必须设计为可恢复队列，并保留未来下放 Windows 的能力。

## V1.6 WD14 网页接入边界

- 自动打标只能生成草稿；模型原始输出、用户编辑值和已确认的 Anima caption 必须区分，避免不可逆覆盖。
- Anima 使用 canonical Booru tags；Krea 2 继续使用英文自然语言，不能把同一份 WD14 逗号标签作为两个 Profile 的 caption。
- rating 适合用于界面分级提示和审核，不进入训练 `.txt`；character 标签与 general 标签分区展示，原创 OC 无 character 命中属于正常情况。
- 确认动作只更新当前图片的 `dataset_captions.anima`；已有人工 caption 在用户明确确认前保持不变。
- 批量打标只针对已精选结果图，并应逐项返回成功/失败，避免一张损坏图片让整批结果不可见。
- 首版继续使用同步 CPU 推理：本机单张约 0.7–0.9 秒，小批量可接受；若后续扩大到完整训练集，再增加后台任务与进度队列。
- 现有 `generation.result_assets` 已承载 `dataset_selected` 与按 Profile 分开的 `dataset_captions`，可兼容新增 `wd14_tagging`，无需数据库 schema 迁移。
- `wd14_tagging` 采用三层信息：原始带置信度结果、可编辑 `draft_tags`、最后确认写入的 `dataset_captions.anima`；重新打标不得自动改变已确认 caption。
- 现有结果图解析函数已按 project_id、存储文件名和私有根目录做路径校验，单图与批量端点应复用它，不接受前端传入任意文件路径。
- 同步 CPU 批量首版应设置小批次上限并展示逐图错误；完整数据集异步队列属于后续扩展，不在本轮隐式引入后台基础设施。
- 单图分析端点已有 `_find_result_asset` + `resolve_result_image` 的安全模板；WD14 端点可沿用相同 404/路径保护和 `creative_store.update_project` 保存方式。
- 结果画廊由 `creative_web.py` 的单页字符串渲染，现有 caption Profile 下拉会切换 Anima/Krea 2；WD14 审核面板必须始终明确标为 Anima，不能跟随该下拉误写 Krea 2。
- 前端 `collectCreative()` 会保留 `generation` 未知字段，因此加入 `wd14_tagging` 后，编辑 Steps/CFG 或自动保存不会丢失打标数据。
- 测试 `Settings` 的模型目录默认位于临时 `library_root.parent/models`，API 测试应 monkeypatch 推理函数并单独覆盖缺模型/坏图片错误，避免测试套件下载真实权重。
- 隔离服务真实端到端验证中，女巫泳装图得到 rating `sensitive=0.982795`、40 个 general 标签、0 个 character；成人向内容未拒绝。
- 真实结果同时包含 `grey_hair` 与 `white_hair`，证明即使总体识别准确，也会出现近义或潜在冲突标签；人工审核层不能省略。
- 真实确认前资产只保留既有 Krea 2 caption；确认后新增 Anima caption 且 Krea 2 原文不变，验证 Profile 隔离有效。
- Anima ZIP 中同名 `.txt` 与确认后的 WD14 审核草稿一致，说明“打标—审核—确认—导出”链路已经闭合。

## WD14 安装调研

- 官方 `SmilingWolf/wd-swinv2-tagger-v3` 支持 rating、character 与 general tags，ONNX 运行要求 `onnxruntime >= 1.17.0`。
- 官方仓库的 ONNX 文件约 467 MB，模型为 98M 参数；相比约 1.26 GB 的 EVA02-Large，更适合作为 24GB Mac 的常用默认打标器。
- 官方模型卡给出的 P=R 阈值约 0.2653；kohya `sd-scripts` 的 WD14 工具默认阈值为 0.35，并说明降低阈值会增加标签但降低准确度。
- 首版目标是得到带置信度的原始标签结果；角色名、版权、rating 等训练策略不在安装阶段自动写入数据集。
- 参考来源：`https://huggingface.co/SmilingWolf/wd-swinv2-tagger-v3`、`https://github.com/kohya-ss/sd-scripts/blob/main/docs/wd14_tagger_README-en.md`。
- 官方 `SmilingWolf/wd-tagger` Space 使用 `onnxruntime` CPU 推理；输入预处理为白底合成、居中补正方形、缩放到模型尺寸、RGB→BGR、float32 NHWC。
- 标签表类别编码为 rating=`9`、general=`0`、character=`4`；官方示例阈值是 general `0.35`、character `0.85`。
- 当前安装目录不存在，适合新建为个人模型层；磁盘余量充足，模型下载不会挤压 1TB SSD 的当前工作空间。
- 下载文件 SHA-256：`model.onnx=e6774bff34d43bd49f75a47db4ef217dce701c9847b546523eb85ff6dbba1db1`；`selected_tags.csv=298633d94d0031d2081c0893f29c82eab7f0df00b08483ba8f29d1e979441217`。
- 本机 `onnxruntime 1.29.0` 暴露 `CoreMLExecutionProvider` 和 `CPUExecutionProvider`；模型元数据与官方规格一致，为 448px NHWC float 输入和 10,861 维输出。
- 最小 CLI 入口比一次性测试脚本更可复用，也能让用户在 V1.6 UI 完成前手动验证任意单图；默认只打印 JSON，不写 `.txt`。
- 实测 CoreML 虽可枚举但不能完整执行 SwinV2 V3 ONNX，在分区节点返回 error code -1；本机默认必须使用 CPUExecutionProvider，不能仅凭 provider 列表判断可用。
- CPUExecutionProvider 对本机 1024×1536 PNG 的完整加载与推理实测约 0.7–0.9 秒，足以支撑下一阶段的交互式单图与小批量打标。
- 安装完成后的职责边界：WD14 负责生成可审核的 Booru 候选标签；Anima caption 可利用这些候选，Krea 2 自然语言仍应由 Profile/本地语言模型转换，不能直接把 WD14 标签串当作最终 Krea 2 描述。
- V1.6 网页接入必须保留“模型建议”和“人工 caption”两层，只有用户确认后才能改变数据集导出内容。

## V1.5 数据集导出审计

- `generation.result_assets` 已能承载每张结果图的附加元数据，适合以兼容方式加入 `dataset_selected` 和 `caption_override`。
- 原图与缩略图均在项目私有结果目录中；导出时必须通过现有安全解析函数取原图，不能信任前端传来的路径。
- `Settings.ensure_directories()` 已创建 `library_root/exports`，可在其下新增 `datasets`，无需迁移正式数据库。
- Anima 适合同名 `.txt` 标签 caption；Krea 2 适合自然语言 caption，两者需要显式选择。
- ZIP 需要包含 `manifest.json`，记录来源项目、版本、Profile、安全级别和资产映射，以便后续审计及在 Windows 上继续处理。
- 单张结果图最大 25 MiB，支持 PNG/JPEG/WebP；导出可直接复制原文件，不需要重新编码或损失画质。
- 现有 API 已有 `_find_result_asset` 与 `resolve_result_image` 两层归属/路径检查，可复用同一安全边界。
- 当前结果画廊只有查看图片与“用本地模型复盘”；V1.5 可以在同一卡片加入精选和 caption 设置，不另造一套图库。
- `compile_prompt(project, profile_id)` 的统一返回字段包含 `positive`、`negative`、`warnings` 与安全级别；数据集 sidecar 只采用 `positive`，完整编译信息留在 manifest。
- caption 覆盖必须按 `anima` / `krea2` 分开保存，否则切换导出 Profile 时会把标签串错误用作自然语言，或反之。
- 为便于直接训练，ZIP 内图片和同名 `.txt` 放在同一个 `dataset/` 文件夹；`manifest.json` 单独放在根目录，不干扰常见训练数据扫描。
- 精选/保存 caption 通过独立 API 立即落库；前端在调用前先保存当前项目，避免延迟自动保存用旧 `generation` 覆盖精选状态。
- 真实浏览器验证证明 Profile 切换只改变 caption 编辑/导出语义，不改变精选集合；未精选的第二张图没有进入 ZIP。
- 手机断点下数据集面板由三列变为单列，页面无横向溢出；结果卡的 caption 继续折叠，未显著增加首次阅读负担。
- 正式部署无需数据库迁移；旧项目没有 `dataset_selected` 时自然表现为“未精选”，保持向后兼容。
- 当前边界仍是手动精选与手动转交 Windows；自动打标、质量评分、去重和 SSH 传输属于后续阶段，不应隐式加入本轮。

## 需求

- 阶段 31 新需求：LoRA 与底模条目需要同步可靠的 Civitai 来源链接，方便用户返回模型页查看推荐提示词；不能根据名称猜链接，也不能把 Windows 本地路径暴露为外链。
- 当前真实 LoRA 快照已经保留 `civitai_model_id` 与 `civitai_version_id`，例如 `linhuier=2885952/3262276`；因此 LoRA 可以无网络、无重新读取权重地构造稳定模型页链接。
- 当前模型资产快照只保留文件后缀，没有读取模型旁的 JSON/Civitai sidecar；Checkpoint / Diffusion Model 需要新增受限 sidecar 解析。常见候选为同 stem 的 `.metadata.json`、`.civitai.info` 与 `.info.json`，必须设置大小上限并只接受 JSON 对象。

- Mac 上的 Prompt Hub 是本地提示词、视觉参考、OC 和创作项目中枢。
- Windows 设备负责 ComfyUI 生成与测试，Mac 先完成创作准备。
- 用户喜欢当前 Prompt Hub 的档案馆视觉风格，但第一次打开不知道从哪里开始。
- 绘梦台的优势是任务导向明确：中文想法、模块化 Prompt、视觉参考、生成、结果复用。
- 绘图阶段至少兼容 Anima 与 Krea 2，不能强行使用一种 Prompt 语法。
- 合法成人向创作必须由项目状态控制，不能固定把 `nsfw`、`nude` 放进 negative prompt。
- 视频常用 MiniMax H3，但明确延后开发。

## 研究发现

- 当前 Prompt Hub 已具备约三万条本地资料的检索、视觉缩略图、成人分级、收藏、评分、备注、OC Manager JSON 导入与 LM Studio MCP 检索能力。
- 当前首页优先展示档案统计、来源、重建索引和高级筛选，适合资料管理，不适合作为第一次创作入口。
- 附件中的绘梦台使用角色、服装、动作、构图、场景和灯光六个模块，任务流程清晰；但现有实现主要接通服装参考，构图与画风仍是占位。
- 绘梦台现有整理指令写死为 Anima/Danbooru 标签；Krea 2 官方工作流使用连贯自然语言并包含 Prompt Enhancement 与 LoRA trigger word 逻辑。
- ComfyUI 只是工作流编排环境，Prompt 写法由模型决定。至少需要区分 Booru 标签、传统 CLIP、自然语言和图片编辑指令。
- MiniMax H3 属于多模态视频生成，需要动作时间线、镜头、结尾、音频和参考素材分工，不能塞入静态图片七槽位。
- 当前项目约 3613 行 Python/测试代码；其中 `database.py` 1058 行、`web.py` 761 行，是后续变化风险最高的两个集中模块。
- 当前 FastAPI 暴露健康检查、统计、来源、Prompt 检索、个人标记、OC 导入/检索/详情/世界/设定、媒体文件和重建索引接口。
- 当前 MCP 暴露 Prompt、画风、标签、角色、角色详情、角色 Prompt、世界设定和资料库统计工具。
- 当前数据库包含来源、资料条目、个人标记、OC 导入记录、角色、角色 Prompt、世界、世界设定及两组 FTS5 全文索引；暂时没有创作项目或配方表。
- 基线自动测试共 13 项，覆盖率 86.44%；`ruff` 与 `ty` 均通过。现有测试已覆盖主要 API、导入器、检索、个人标记重建保留和 OC 数据交换。
- 真实库 33,631 条中有 29,974 条 wildcard、2,094 条 tag、735 条 modifier、430 条 caption、397 条 style；视觉最集中在 Kisega tag/caption 与 Clio style。
- 现有 FTS 多词查询采用 AND 语义，`silver hair`、`old library`、`holding letter` 等组合可能无结果，但拆成 `silver`、`hair`、`library`、`reading` 可找到真实资料。
- `military uniform`、`golden hour` 等库中已有精确结果；服装标签和画风卡常带视觉参照，普通 wildcard 多数只有文字。
- 智能取材不能把中文原句直接作为唯一 FTS 查询，需要槽位词典、短语优先与单词回退，再进行类型/分类相关性排序。
- 真实样例“银发调查员穿维多利亚军装，在黄昏图书馆读信，电影感特写”可从本地库返回 37 条分槽候选；`reading`、军装、特写、图书馆和电影感均能进入预期槽位。
- 当前资料库对服装、场景、灯光和画风的视觉覆盖最好；普通动作 wildcard 通常只有文字，因此界面必须允许无图候选，不能误导为每条都有视觉。
- 已加载 Qwen3 14B 能完成检索词扩展，但当前样例的人工规则和已有槽位已覆盖主要概念；模型扩展是增强项，不是即时结果依赖。
- LM Studio 当前安装 6 个 VLM：已加载的 Gemma 4 12B Heretic，以及未加载的 Qwen3.5 9B/27B、Gemma 4 26B、Qwen3.5 35B、Qwen3.8 27B；因此 V1.2 可以真实接入本地看图，不需要先下载新模型。
- 当前项目只把结果图保存为路径/链接字符串，没有本地上传目录、缩略图、媒体安全校验或项目级结果图 API。
- 现有媒体路由只允许 Kisega PNG/WebP 与 Clio JPG，不能直接复用来服务用户结果图；应增加独立的私有结果图根目录和严格后缀/路径校验。
- FastAPI 项目尚未依赖 `python-multipart`。为减少额外依赖和上传解析面，可采用原始图片请求体加文件名参数，与现有 OC JSON 原始请求体导入方式一致。
- 前端原本在保存 Steps/CFG 时会重建整个 `generation` 对象；新增结果图片后必须先展开原对象，否则任何后续编辑都会丢失 `result_assets`。V1.2 已修正为保留未知扩展字段。
- 视觉复盘写回应只填“空且未锁定”槽位；已存在内容即使与图像观察不同也只用于比较，不自动替换，这是保护角色一致性和用户判断的最小安全边界。
- Gemma 4 12B Heretic 虽被 LM Studio 标记为 Vision 且已加载，但真实 768×1024 服装图在 180 秒内未返回；能力标记不等于适合交互式复盘，默认模型应遵循原分工改用 Qwen3.5 9B Vision。
- Qwen3.5 9B 首次请求的 400 正文显示：模型自身约需 11.51GB，但当前 Qwen 14B 与 Gemma 12B 同时驻留，LM Studio 内存保护拒绝再加载。24GB Air 的文字与视觉模型应按任务切换，不能三模常驻。
- Qwen3.5 9B Q8 单独加载约占 9.73 GiB；1400-token、1536px 的完整复盘在 180 秒内未完成，日常请求必须压缩图像和 JSON 长度，不能照搬云端 VLM 输出规模。
- LM Studio 官方模型说明要求把 `/no_think` 放在 Prompt 末尾；首版放在 system 开头，Qwen 视觉请求仍生成 reasoning 并耗尽正文预算。V1.2 已改到用户图像消息末尾。
- Qwen3.5 9B 在单独驻留后能正常接收 1024px 图片，但首次 700-token 实测约 72 秒后正文仍为空，说明 token 被隐藏 reasoning 消耗；仅追加 `/no_think` 对该社区微调并不足以保证最终 JSON。
- LM Studio 官方 OpenAI-compatible 接口支持通过 `response_format.json_schema` 约束结构化输出；视觉复盘应使用 schema 限定七槽位、问题列表与双 Profile Prompt，而不是仅靠文字要求模型输出 JSON。
- 仅给多模态消息的首个文字块追加 `/no_think` 仍不等于 Prompt 末尾，因为其后还有图片块；视觉消息必须调整为“图片在前、文字指令在后”，让控制词成为整条用户消息的最后内容。
- 本机 `/api/v1/models` 明确返回 Qwen3.5 9B Vision 的 reasoning 能力为 `off/on` 且默认 `on`；LM Studio 官方原生 `/api/v1/chat` 支持 `reasoning: "off"`，因此视觉复盘应改走原生接口，由引擎关闭 reasoning，而不是依赖微调模型遵循控制词。
- 原生接口修正输入类型后，Qwen3.5 9B Q8 对真实 768×1024 Kisega 图在约 63 秒返回完整可解析 JSON；七槽位、优缺点、改进建议与 Anima/Krea 2 反推均有有效内容，确认可作为 V1.2 默认复盘模型。
- 8766 临时库浏览器验收中，真实复盘约 60 秒返回；七槽位 7 项、优点/问题/改进 3 组及双 Profile Prompt 均可见，确认“只写入备注”后锁定角色值不变。
- 390×844 下页面 `innerWidth=390`、内容宽 375，无横向溢出；结果图库、槽位与诊断均为单列，控制台 0 warning/error。
- V1.2 虽能把复盘写入同一项目，但用户继续编辑时只有数据库 revision 增长；revision 表示保存次数，不足以表达创作上的 V1/V2/V3。
- 下一步版本分支应保留角色槽位、锁定、参考资料和生成参数，同时清空旧 `result_assets`/`result_images`，并记录父项目与源结果图，才能形成可追踪的绘图迭代链。
- `creative_projects` 当前把项目字段拆成固定列，尚无 lineage 字段；配方保存的是完整导出快照，前端项目列表只显示数据库 `R{revision}`，因此不能把分支关系只放在 UI 临时状态。
- V1.3 需要为现有 SQLite 做可重复的 `lineage_json` 增量迁移；旧项目读取为空 lineage 并显示 V1，新分支从父项目计算 V2/V3，不修改旧项目。
- `generation_json` 已包含 steps/cfg/seed 与结果图。分支时应复制参数，但必须移除 `result_assets` 并清空手填 `result_images`；lineage 作为独立字段保存，避免混淆生成参数职责。
- 后端定向验证确认旧 schema 可自动增加 `lineage_json`；V2 会保留槽位、锁定、参考、steps 与 seed，清空两类结果图，并且父项目原图路由仍然有效。
- 前端版本链应同时显示 `V{iteration}` 与 `R{revision}`，并在派生项目顶部显示来源图链接；这样用户能区分创作轮次和自动保存次数。
- 全量回归确认新增 lineage 迁移与分支功能未破坏现有资料库、OC Manager、取材、结果图和 MCP 行为；32 项测试覆盖率为 87.41%。
- 浏览器验收可通过隔离服务替换视觉分析响应：复盘模型本身已在 V1.2 做过真实图片实测，本轮只需验证新增分支按钮、继承边界、来源链接和响应式布局。
- 隔离库 V1 项目已覆盖分支最易出错的字段：锁定槽位、参考卡、生成参数、手填结果路径和已上传结果资产，适合验证 V2 的保留/清空边界。
- 上传结果图会正常增加数据库 revision，因此浏览器中的首轮创作状态显示为 V1/R2；这进一步证明 V 与 R 必须同时呈现且语义分离。
- V1→V2 浏览器实测成功：父项目保留为 V1/R3，新项目为 V2/R1；来源图链接指向父项目私有媒体路由，V2 结果区为空，锁定、参考和生成参数保持不变。
- 首次自动化超时只是等待文案写成了“已从 V1 创建 V2”，实际页面文案为“已创建 V2”；业务请求与页面切换均已成功，无需修改产品代码。
- V1.3 在 390×844 下沿用单列槽位布局，`innerWidth=390`、`scrollWidth=375`，没有横向溢出；版本来源提示在窄屏仍可见。
- 分支 API 的实际持久化结果与页面一致：V2 保存完整 review 摘要和双 Profile 反推 Prompt，父项目继续持有原结果资产；来源原图路由返回 200，隔离 SQLite 完整性为 `ok`。
- 正式资料库迁移前约 23MB，SQLite 完整性为 `ok`；V1.3 备份已独立落在 `database/backups/prompt-library-pre-v13-lineage-20260831.sqlite` 并验证可读。
- 正式迁移后仍可读取 4 个来源与 33,631 条资料，旧创作项目以空 lineage 兼容为 V1；日常 `qwen3-14b-abliterated` 未被本轮验收切换。
- V1.3 的分支已经可追踪父项目和来源图，但 lineage 目前没有保存 `observed_slots`，派生项目只能看到摘要和改进列表，无法安全地逐槽位应用视觉观察。
- V1.4 应把“版本比较”和“建议应用”放在派生项目自身：父项目用于对照，lineage review 用于候选建议；两者职责不能混用。
- 建议应用继续沿用 V1.2 的保护边界，只填空且未锁定槽位；已有内容即使与视觉观察不同也只显示差异，不自动替换。
- `/api/creative/projects/{project_id}` 已实现并覆盖成功/404，不应重复增加父项目 API；前端可先从已加载项目找父版本，缺失时再调用该端点。
- `apply_result_review` 已有成熟的“空且未锁定”填充逻辑，但它依赖完整 analysis；V1.4 可复用同一领域函数处理 lineage 中保存的 review，避免在前端复制保护规则。
- 前端最近项目默认只取 30 条，父版本可能不在列表内；版本对照应由后端按 `parent_project_id` 精确读取，而不是假设父项目已加载。
- iteration context 适合返回每个槽位的 `previous/current/suggested/status/applicable`，让 UI 只负责呈现和确认；锁定与已有内容判断仍由后端最终复核。
- V1.4 后端全量测试确认：建议只填空槽位，锁定角色和已有服装保持不变；父项目缺失时所有差异状态降级为 `unknown`，页面仍可显示 lineage review。
- 为控制派生项目顶部的信息量，界面只呈现 `status != unchanged` 或存在 `suggested` 的槽位，而不是固定展开七行。
- V1.4 浏览器夹具故意让视觉观察提出 `different character` 与 `white dress`，同时只留空 lighting；正确结果必须只允许应用 `warm rim light`，这是比普通一致数据更有价值的保护测试。
- 首轮渲染中 `suggested` 在七槽位都有值，导致“有建议就显示”实际仍展开七行；更符合低认知负担的条件是“槽位已变化，或 suggested 与 current 不同”。
- 应用端点首次实际写入完全符合保护规则，但 `renderCreativeProject()` 启动的异步 context 刷新会覆盖直接写 DOM 的成功提示；提示必须进入项目级 state，由统一渲染函数读取。
- 修正后桌面对照稳定为 4 行，且成功提示在刷新后保留；再次可应用槽位数为 0，按钮禁用，避免重复写入。
- 390×844 下 iteration change 从桌面四列降为单列，实测列宽 269px、页面滚动宽 375px；长英文角色值可正常换行，不形成横向滚动。
- API 最终状态证明保护发生在服务端而不只是按钮层：父 V1 revision 仍为 1，冲突角色/服装建议均不可应用，V2 仅增加 lighting 与 `[迭代建议已应用] lighting`。
- 正式 V1.4 只扩展新分支 lineage 和派生项目 UI；现有空 lineage 的 V1 项目继续显示 V1/R12，迭代面板隐藏，正式 SQLite 完整性为 `ok`。

## 技术决策

- Windows worker 使用单文件 Python 3.12 stdlib 实现，不依赖 Prompt Hub 的 FastAPI/NumPy/ONNX 环境；它只允许访问 loopback ComfyUI URL，避免开放 8188 到局域网。
- ComfyUI 远程执行必须使用 API Format workflow。普通网页 workflow JSON 是界面布局格式，不能直接作为 `/prompt` 的 `prompt` 对象；Prompt Hub 生成包固定为 `soda-comfyui-package-v1`。
- Worker 用同盘 `os.replace` 原子领取 outbox 任务，并用系统文件锁限制单实例；提交到 ComfyUI 后立即持久化 `prompt_id`，重启优先续查 history，降低重复排队概率。
- 回传图片不依赖 Windows output 路径直接复制，而是按 ComfyUI history 返回的 filename/subfolder/type 调用 `/view` 下载到任务私有 inbox；Mac 再对源 manifest 和每个输出执行 SHA-256 校验。
- Windows 自检会写 `worker-status.json` 到 bridge 根目录，作为 Mac 判断真实 Python、hostname、协议版本和 ComfyUI 连通性的可审计证据。
- 真实启动后 Mac 对整个 SMB 挂载的目录读取进入不可中断等待；停止 worker 后症状不消失，且 Windows ping 与 TCP 445 始终正常，因此“共享根 byte lock 是直接根因”的首个假设被排除。当前故障定位为已有 macOS SMB 挂载会话失去响应，需要远端 SMB 服务断线或 Windows 重启后再挂载验证。
- Windows 重启、停止旧 worker、强制卸载与 SMB `forcenewsession` 新挂载均无法解除等待，且相关进程进入不可中断状态；当前证据把故障进一步收敛到 Mac SMB 客户端内核状态，需重启 Mac 后再验证。修正版仍保留“锁放 `%LOCALAPPDATA%`”改动，以消除不必要的跨共享锁变量。
- Mac 重启后旧 SMB 挂载与不可中断进程均消失；重新挂载成功。同步 `%LOCALAPPDATA%` 锁修正版并启动 Worker 后，共享目录持续可读写，协议失败探针和 ComfyUI 成功任务均未再次触发卡死。证据证明修正版运行稳定，但不能反向证明共享锁是此前唯一根因。
- ComfyUI 内置 `EmptyImage → SaveImage` 可作为不依赖 checkpoint 的端到端烟雾 workflow：本次 128×128 PNG、API workflow 与 run log 已由 Windows 回传，Mac integrity 返回 `verified=true`、0 errors。
- Windows ComfyUI `system_stats` 显示实际启动参数含 `--listen 0.0.0.0`，与“8188 仅本机监听”的架构目标不一致；Mac 直接访问 192.168.1.10:8188 当前被 Windows 网络层阻断，但仍应在确认现有 OC Preview 用途后收紧启动参数。
- 用户提供的 `Krea2-for-ares-ocmanager (1).json` 与 `anima-测试-满穗.json` 都是可直接提交 `/prompt` 的 ComfyUI API Format；前者 14 个节点，后者 58 个节点，不需要再次要求用户导出。
- Krea 2 工作流的核心参数位于 `141`（正面 Prompt）、`121`（负面 Prompt）、`87`（seed/steps/cfg/sampler/scheduler）、`129`（960×1536）、`123`（Krea 2 UNET）和 `133`（保存）；默认保存的是 `156` SeedVR2 1920 放大结果，首个低成本测试应旁路 SeedVR2。
- Anima“满穗”工作流绑定了 `mansui-anima_v1.1` 等角色/画风 LoRA，并包含 SAM3 脸手精修、普通放大与 Ultimate SD Upscale；它是角色实例工作流，不应直接作为通用 Anima Profile。应从原图生成独立模板并把角色 Prompt/LoRA 视为可替换内容。
- 两个 workflow 都引用 Windows 已安装的自定义节点和模型文件；导入层必须保留原 API JSON 与 SHA-256，Profile 层只允许修改白名单字段，不能重新序列化为自创图结构或静默更换模型。
- Anima 的可控节点已沿真实连线确认：正面内容 `184.wildcard_text/populated_text`，负面 `75.string`，seed `84.seed`，尺寸 `150.width/height`，steps/CFG `135:103.int` / `135:104.float`；基础生成图来自 `148:139`。输出节点 `81` 原本连接 `152:189` Ultimate SD Upscale，低成本模式应改接 `148:139`。
- Krea 2 的可控节点已确认：正面 `141.wildcard_text/populated_text`，负面 `121.text`，seed/steps/CFG/sampler/scheduler `87`，尺寸 `129`；基础生成图来自 `132`。输出节点 `133` 原本连接 `156` SeedVR2，低成本模式应改接 `132`。
- 低成本 Profile 不应只改保存节点后保留整图执行：编译器应从指定输出节点反向计算依赖闭包，只把可达节点写入 API prompt，从结构上排除 SeedVR2、SAM3、脸手 Detailer 与放大节点，同时避免误改模型主链。
- 当前 `Settings` 尚无 workflow profile 数据根；应在 `library_root` 下增加独立目录，使用户工作流属于个人数据和备份范围，不与代码内置测试例子混放。
- Prompt Hub 的 Anima 编译器已经自动加入 `masterpiece, best quality, very aesthetic`，而满穗 workflow 的 `182` 还会再次追加同类前缀；从创作项目运行时应把 `182.string` 清空并把完整编译结果写入 `184`，避免重复权重。原 workflow 的独立手动使用不受影响。
- 现有应用已经把创作编译和 Windows 任务拆成独立领域；阶段 24 应新增独立 workflow profile store/router，由路由编排 `CreativeStore.compile_prompt → workflow package → RemoteNodeStore.submit_task`，不把节点规则塞进现有 `creative.py` 或 worker。
- 创作台前端已经同时维护当前项目、Anima/Krea 2 编译输出和 steps/CFG/seed，因此无需新增第三套 Prompt 编辑器；右侧输出区只需按当前 Profile 选择已导入 workflow，并显式“发送到 5060 Ti”。
- 生成包应先写入 Mac `workflow-profiles/{profile_id}/runs` 作为事实源，再以相同字节和哈希复制到 SMB `packages/generated`；这样 Windows 断线或共享清理后仍可重建和审计任务。
- `maintenance.PERSONAL_ROOTS` 当前未包含 workflow profiles；新增数据根时必须同步纳入备份/恢复测试。
- 现有 ComfyUI result store 已能导入共享目录、解析 PNG metadata，并显式关联创作项目；阶段 24 可在任务回传后复用这条链，而不新建第二套结果图库。

- 混合检索不在 Mac 上临时生成 query embedding：文本 FTS 始终可用；只有调用方提供真实向量且 dimension 与版本化索引兼容时，才增加 cosine 召回。
- “以图找图”用源图片 SHA-256 在 embedding 事实源中定位同模型版本向量，不依赖远程 worker 自行约定 asset ID；同 SHA 的查询图会从结果中排除。
- 检索 UI 固定分为提示词资料、视觉参考、我的数据集和 Windows LoRA。没有真实索引时保留诚实空状态，不隐藏功能边界，也不生成伪结果。

- V1.8 LoRA 项目使用标准文件系统项目根作为交付与备份单元，Prompt Hub 页面负责索引和编辑；避免把明天的 Windows 训练绑定到 Mac SQLite 的内部表结构。
- M3 图片引用不复制原图，M4 冻结时才校验 SHA-256 并复制到不可变版本；Anima 与 Krea 2 始终输出两棵独立 caption 树。
- 5060 Ti 16GB 的 Krea 2 配置只作为资源起点：Raw FP8、Qwen3-VL FP8、28 层 block swap、batch 1；实际驱动、Torch、CUDA 和 AnimaLoraStudio 版本必须在 Windows 上重新验证。
- M5 回流库必须独立于创作项目结果媒体：前者按 SHA-256 保存一次真实来源与 metadata，后者只在用户确认关联时复制到项目私有媒体，避免重复导入和失败图污染数据集。
- ComfyUI `KSampler` 的 positive/negative 通常是节点引用而不是字符串；解析时必须保留 node ID 并追踪到 `CLIPTextEncode`，仅遍历所有文字节点无法可靠区分正负 Prompt。
- 无 metadata 的 JPEG/WebP 仍是合法测试结果，但 UI 与 API 必须返回 `metadata_present=false` / `source=none`，不能用文件名或模型猜测参数。
- M7 在连接 5060 Ti 前的正确完成边界是稳定数据契约：embedding 与 VLM 结果必须回显源 SHA-256、模型 ID/版本，Mac 校验后只保存可重建结果；VLM caption 永远先进入 Krea 2 draft。
- Prompt Hub 当前 venv 没有 torch、transformers、MLX、open_clip 或 sentence-transformers，本机常见缓存中也未发现 CLIP/SigLIP 模型；M7B/M7C 要么增加经过版本固定的真实 runtime/model，要么等待 5060 Ti worker，不能用非语义特征假装完成。
- Krea 2 VLM 队列必须把正式 caption 与模型草稿并排保存。即使已有正式 Krea 2 caption，重新推理也只能读取它作为参考，不能覆盖；确认动作必须单独生成 `profile_id=krea2` 快照。
- 明天 5060 Ti 连接前，Mac 可以先完成向量的“事实源”职责：版本化保存、SHA-256 回验、cosine 查询和来源解释。模型生成仍未完成时，这属于接口完成而不是视觉检索完成。
- embedding 索引使用独立 SQLite，避免把高体积 float32 BLOB 塞进正式资料库；model ID、revision、dimension 共同决定 index ID，因此换模型不会覆盖旧向量。
- 数据集分页采用前端 200 张窗口：当前扫描报告仍一次读取到 Mac 事实源，避免破坏现有筛选和批量语义；DOM、图片 lazy-load 和详情导航只持有当前页，先解决 10,000 张浏览器节点压力。若未来单库超过数万到十万张，再把报告 API 升级为服务端分页。

| 决策 | 理由 |
|------|------|
| 创作项目保存统一语义槽位 | 避免项目被某个模型的最终 Prompt 绑死 |
| 通过模型 Profile 编译输出 | 支持 Anima、Krea 2 及未来模型扩展 |
| 增加画风为第七槽位 | 画风应与角色、服装等内容分离，可支持 Clio 与 LoRA |
| 资料条目允许 tags 与 caption 并存 | 同一视觉资料可以服务标签模型和自然语言模型 |
| 高级筛选和维护功能渐进披露 | 保留能力，同时降低新用户认知负担 |
| 视频只做数据扩展点预留 | 防止当前绘图主线范围膨胀 |
| 首轮不推倒重写后端 | 保护现有数据与已验证功能，先做基线审计再决定前端拆分 |
| 新功能通过新增领域模块接入 | 避免继续扩大 `database.py` 与 `web.py` 的单文件复杂度 |
| 创作数据使用同库增量表并在迁移前备份 | 保留单机管理体验，同时避免触碰既有资料表 |
| LM Studio 作为可选增强而非保存依赖 | 本机服务可用，但项目保存、编译与导出必须离线独立工作 |
| V1.1 不对全库做向量迁移 | 先验证 FTS 编排和真实选择闭环，避免未经评估增加 33k embedding 成本 |
| 模型只生成检索词，资料卡必须来自 SQLite | 保证来源、视觉、分级可追踪，避免模型记忆冒充本地资料 |
| 按项目分级过滤文字与图片 | 保留合法成人向工作流，同时避免 SFW 项目混入更高分级内容 |
| 结果图使用独立私有媒体目录与路由 | 用户生成图不可混入可重建公共资料源，并需要项目级归属与路径隔离 |
| 上传 API 接收原始图片字节而非 multipart | 避免新增解析依赖，前端仍可直接用 `File.arrayBuffer()` 提交 |
| V1.2 不自动卸载/加载 LM Studio 模型 | 模型切换会影响用户其他会话；界面展示真实资源错误，并在使用说明中给出单视觉模型驻留顺序 |
| 视觉复盘使用 LM Studio 原生 Chat 且 reasoning=off | 社区 Qwen 微调不稳定遵循 `/no_think`；原生接口能按模型能力由引擎关闭 reasoning |

## 遇到的问题

| 问题 | 解决方案 |
|------|---------|
| 当前 Git 仓库文件均为未跟踪状态 | 本轮只增加规划文档，不执行清理、commit 或其他 Git 修改 |
| 当前网页代码集中在 `src/prompt_hub/web.py` | 在阶段 0 审计复杂度，再确定渐进拆分方案 |

## 资源

- `完整工作流程说明.md`：绘梦台当前工作流与设备路径说明。
- `绘梦台-完整源码-20260830.zip`：绘梦台 React/FastAPI 源码、设计截图和教学工作流。
- ComfyUI 官方文档：SD、FLUX、Qwen-Image、Z-Image、Krea 2 与视频工作流参考。
- MiniMax H3 官方仓库：未来视频 Profile 的基础与全参考 Prompt 指南。
- LM Studio 官方 Qwen 模型说明：`/no_think` 需要追加到 Prompt 末尾，用于关闭 reasoning。
- 真实资料库迁移前备份：`prompt-library-pre-creative-v1-20260830.sqlite`，SQLite `integrity_check` 为 `ok`。
- 本机 LM Studio OpenAI 兼容接口：`127.0.0.1:1234/v1`，当前可列出 10 个已安装模型。
- LM Studio 实测同时加载 Qwen3 14B 与 Gemma 4 12B 时，Heretic 七槽位请求 120 秒超时；工作台默认应优先已加载文本模型，并限制为短 JSON、短超时，不把模型调用作为保存依赖。
- 改为优先已加载模型后，Qwen3 14B 在约 60 秒返回七槽位建议；确认应用时锁定角色保持不变，其余槽位成功写入项目 R6。

## 视觉/浏览器发现

- 绘梦台的已实现桌面界面把参考库、六槽位、生成参数和结果放在同一工作台，按钮均围绕动作命名。
- 当前 Prompt Hub 使用纸张、档案卡、橙色强调色和私人资料馆语言，审美辨识度高。
- 当前 Prompt Hub 的首屏重点是档案状态和检索管理，缺少显式步骤、示例任务和创作结果出口。
- 浏览器基线确认窄屏时头部先完整展示档案标题与统计，用户必须继续向下滚动才能看到检索入口；这进一步放大了“第一眼不知道做什么”的问题。
- 当前页面的纸张、黑墨、酸绿色数字、橙红印章和衬线标题已经形成稳定设计语言，阶段 1 应新增导航和创作首页，不应更换配色或字体体系。
- 当前页面初始空查询会立即加载 30 条索引卡片，视觉信息量较大；创作首页应先给出少量明确动作，再让用户主动进入完整资料库。
- 阶段 1 桌面首屏已将创作问题、两个真实入口、Anima/Krea 2 目标和三步流程放在一个视口内，同时保留原有纸张/黑墨设计语言。
- 顶级导航的四个入口均可正确切换：提示词库显示 30 条检索结果，角色库显示 OC 导入区，资料管理显示 4 个来源，返回开始创作可恢复首页。
- 资料管理与日常检索已分离，重建索引按钮不会再作为用户第一次打开时的首要动作。
- 手机宽度下导航改为两行四格，四个入口同时可见；390px 测试无页面横向溢出。
- Type、Safety、Source 默认收进“高级筛选”，保留完整能力但降低首次使用信息量。
- 首页示例任务可直接检索 `victorian military uniform`，真实资料库返回 2 条结果，示例不是静态假数据。
- 阶段 1 浏览器验证期间控制台无 warning/error；内联 SVG favicon 消除了页面图标 404。
- 绘图 V1 在桌面端完成新建、自动保存、锁定、成人模式、双 Profile、配方、资料卡加入创作和本地模型建议实测。
- 390×844 独立浏览器验证 `innerWidth=390`、`scrollWidth=390`，七槽位均存在，控制台 0 error / 0 warning。
- V1.1 候选面板桌面端与手机端均保持现有档案馆风格；手机端候选由两列降为单列，测试内容宽 375px，无横向溢出。
- 本地快速检索约 1 秒内显示 23 条候选与 9 张真实缩略图，Qwen3 14B 随后完成检索词扩展；全过程控制台 0 error / 0 warning。
- V1.2 结果图卡片、本地模型状态、视觉复盘预览与确认写回在桌面/手机浏览器均完成真实交互；手机截图确认档案馆风格与单列阅读顺序保持一致。

## 2026-09-02：林悔儿真实旧数据集

- 用户提供的旧训练数据集位于 `/Users/soda/Downloads/linhuier-v012_data.rar`，RAR5，约 145MB；归档 SHA-256 为 `7e928c35763ef6c1d47ce86815258e290be2951c4211a3defcf2b3802061265c`。
- 归档含单一顶层目录、72 张图片和 72 份同名 `.txt`；没有绝对路径或 `..` 越界项。工作副本保存在 `/Users/soda/Documents/Codex/soda-person/datasets/incoming/linhuier-v012`，下载原件未修改。
- Prompt Hub 工作区为 `dataset-4af72c6757de431081930100a27cb09e`。真实扫描结果：72/72 图片可解码、72/72 caption 配对、0 坏图、0 缺失 caption、0 孤立 caption、0 完全重复组、0 pHash 近似重复组。
- 旧 caption 均为英文 Booru/WD14 风格、内容非空且彼此不同，统一 trigger `linhuieroc` 出现 72 次；未发现 `newest`、`safe`、质量分、画师、水印等已知污染标签。
- 数据集扫描报告保留源 `.txt`，可编辑 Anima/Krea 2 caption 则保存在独立 curation 状态中；这是防止未知 `.txt` 被误判模型族的边界。此次依据目录名、内容结构和用户说明，将旧 caption 明确登记为 Anima reviewed，Krea 2 仍为空。
- 真实网页显示 72 张 Anima caption、263 个唯一标签和 0 个现有冲突规则提示；高频身份锚点包括 `linhuieroc`、`brown hair`、`very long hair`、`single side bun`、`sidelocks`。
- 原 caption 批量接续现已独立于逐图编辑：可选择 Anima/Krea 2、全部/已选范围、是否覆盖与审核状态；预览不写入，确认后整批只生成一个快照。默认只填空白 Profile 并标为 draft。
- 产品职责已收敛：Mac 负责灵感、提示词、远程绘图、结果复盘、数据集素材整理与交付、LoRA 下载编排和训练后测试；Windows AnimaLoraStudio 负责正则、最终标签筛选和训练，不在 Mac 重建训练控制台。
- 用户更正角色中文名为“林悔儿”；工作区、LoRA 项目和规划记录已统一更名，既有 trigger `linhuieroc` 保持不变。
- 两页带文件名的视觉联系表保存在数据集 `review` 目录。整体身份稳定，现代/古风服装、室内外场景和多种画风变化丰富；前半批偏单眼遮挡，末批增加双眼可见与分缝刘海，适合作为需要人工确认的可控外观边界，不自动判为漂移。
- 67 个 `.png` 扩展名文件实际解码格式为 JPEG，另外 5 个为真实 PNG。该旧数据集曾实际训练，但交付 Windows 时仍需让 AnimaLoraStudio 做读取 smoke test；当前不重编码或改名。
- 已建立 draft 角色项目 `lora-5eb67ac1316e435c991dd5ce8e2f4c6c`，目标仅为 Anima，引用 72 张候选图。保守的文件名/caption 初审把覆盖缺口从未标注时的 43 项降为 11 项；缺少局部细节、仰视、回头、四类强表情、逆光和三类构图证据。
- 新增的规则初审只识别明确英文短语和横竖尺寸，预览结果不会写项目。对林悔儿现有 72 张项目试跑后，发现 18 张可再补 19 个覆盖项；当前仍保持 revision 75、72 张 candidate、0 条已确认规则初审，等待用户在页面确认。
- 页面职责文案已改为现实状态：Mac 负责版本与交付，Windows AnimaLoraStudio 负责最终筛标、正则和训练；当前自动 Worker 明确支持 ComfyUI 生成与 LoRA 只读清单，不把训练、Embedding、VLM 的协议预留写成已上线能力。

## 2026-09-03：LoRA Manager 预览图真实验收

- 最新真实缓存为 256 个 LoRA、221 个有视觉参照、386 张图片；`linhuier` 多图查看器中的两张图片均已完成浏览器解码，尺寸分别为 450×658 与 1664×2432。
- 684px 当前窗口下，多图查看器打开时 `documentElement.scrollWidth=669`，页面没有横向溢出。
- 目录树真实数据结构正确：根目录 15 类；`Anima/style` 显示并筛选为 49/256 个，筛选后的首批卡片路径均属于 `Anima/style`；列表内同时存在真实图片卡片与“暂无本地预览图”占位。
- `Krea2` 展开后包含 45 个 LoRA，其中 `Krea2/style` 为 37 个；点击后页面状态精确显示“当前 37 / 256 个”，首批卡片均为真实 Krea 2 画风条目，桌面宽度无溢出。
- 最新快照缓存目录实有 386 个文件：223 WebP、136 PNG、27 JPEG，`.safetensors` 为 0。`linhuier` 两个预览接口分别返回 200 + `image/webp` 和 200 + `image/png`。
- 响应式源码在 620px 将 LoRA 卡片与预览查看器改为单列，在 540px 将目录树与结果区改为上下布局；内置 Browser 当前 684px 实测无溢出，但其只读 DOM 代理禁止创建 390px iframe，因此本轮没有把 iframe 结果冒充成真实手机证据。
- `Krea2/style` DOM 精确包含 37 张卡片和 37 个预览入口、0 个无图占位；首屏外 19 张 `loading=lazy` 图片尚未解码，属于浏览器未滚动触发加载，不能按坏图统计。需滚动/打开末尾卡片后再核对实际解码。
- 使用完整可访问名称打开 `Krea2/style/z3zz4-k2-4_c1-st5000.safetensors` 后，两张末尾参照图均完整解码（450×644、1280×1832），证明 lazy-load 项在进入视区后可正常加载。
- Worker 最终信封为 completed，共 387 个输出（1 catalog + 386 preview）；记录 `weights_read=false`，10 个候选因 `unsupported_format` 跳过，预览总字节 442,815,681。
- API 返回 256 个 LoRA、221 个带图条目、386 个唯一预览 URL；`linhuier` 唯一对应 `Anima/Character/linhuier-anima_v01.safetensors` 并有 2 张图。正式库、两个历史备份库与 embedding 库的 SQLite `integrity_check` 均为 `ok`。

## 2026-09-03：模型资产真机复验

- 新 Worker 任务 `task-20260903T095310Z-418e3862fe8f` 首次回传 `worker_build_sha256=11f78bd64957e7f88c7e791e3c351e09f4a74a4fb9c8abaa0c8da831c645fb55`，与 Mac 和 SMB 上两份脚本一致，证明实际接任务的常驻进程已换版。
- 新模型快照 `models-20260903T095311Z-7c0adb88d329` 含 140 个模型；六类计数为 checkpoint 58、diffusion model 38、VAE 14、text encoder 9、upscaler 6、ControlNet 15；回传 SHA-256 完整性通过，明确 `metadata_only=true`、`weights_read=false`。
- 两个真实误分类样本已修正：`SDXL/animagineXLV31_v31.safetensors` 为 `sdxl`；`Flux1_Dev/fluxKreaDevNsfwFp8_v10*.safetensors` 为 `flux`。真正的 Anima/Krea 2 diffusion model 候选分别为 12/10。
- 浏览器设备页已显示最新 140 个模型、六类树状导航及正确分类卡片；整页刷新后，创作台 Anima 底模候选显示 12 个真实 Anima diffusion model，已知 Flux/SDXL 不进入 Anima 候选。
- 模型同步后未整页刷新时，创作台仍持有页面启动时的旧清单，曾短暂显示两个 `fluxKreaDev` 候选；源码过滤本身正确，刷新后两项消失，因此没有误改过滤规则。后续可考虑让导入动作广播状态更新，但不属于数据正确性问题。
- 低成本 Anima smoke test 使用 512×768、4 steps、CFG 1.0、seed 123456；Windows 约 7 秒完成并回传图片、workflow 和日志，三项 SHA-256 全部通过。结果图为银发成年女性调查员、深色军装、手套、旧图书馆与黄昏侧光，符合项目槽位，并已关联测试项目。
- 新 LoRA 快照 `catalog-20260903T095639Z-60e595c5d3da` 再次验收 256 个 LoRA、386 张预览、221 个有图条目；旧 `Wan2.2_Animate` 五项现均为 `unknown`，不再误归 Anima。权重未读取。

## 2026-09-03：Civitai 来源链接同步

- Civitai 来源只从 LoRA Manager / Civitai sidecar 的已有 URL、`modelId` 与 `modelVersionId` 提取；不根据文件名或模型名联网猜测。
- 规范化后只接受 `civitai.com`、`www.civitai.com`、`civitai.red`、`www.civitai.red` 的 `/models/<数字ID>` 页面，可保留数字 `modelVersionId`；本地路径、`file://`、外站、下载 API 与图片 URL 全部拒绝。
- Windows Worker 现在会在每个模型权重旁只读查找 `.metadata.json`、`.civitai.info`、`.info.json`、`.json` 小型 sidecar，并把安全 `source_url` 放入模型清单；不会读取、哈希或复制权重。
- Mac 在导入清单时会再次校验来源。旧 LoRA 快照未显式保存 `source_url` 时，可从已验收 metadata 的 model/version ID 动态生成来源页面，保持向后兼容。
- 当前真实 LoRA 索引为 256 个，其中 232 个可返回 Civitai、221 个有视觉参照、386 张预览图；`linhuier` 的来源为 `https://civitai.com/models/2885952?modelVersionId=3262276`。
- 当前模型索引为 140 个，其中 88 个有示例图、161 张示例图，但旧快照尚无来源链接；必须由新版 Windows Worker 重新扫描 sidecar 后才能得到真实数量。
- 页面把“查看 Civitai / 提示词”与预览图、选择/添加操作分开，避免点击来源时误选 LoRA 或切换底模；搜索同时支持 Civitai model/version ID。
- 2026-09-03 最新 `worker-status.json` 仍停在 `2026-09-03T08:44:42Z` 且没有 `worker_build_sha256`，证明 Windows 仍在运行旧进程，不能把底模 0 个来源误报为真实无来源。
- Windows 重启后 `worker-status.json` 更新时间为 `2026-09-03T11:15:58Z`，构建指纹与 Mac、SMB 两份入口一致：`1e68ec659948c848001a0f9bf843046418ca236771b0ad04af4af7cfe7db82a9`。
- 真实模型任务 `task-20260903T111630Z-59a120348175` 扫描 140 个模型与 161 张示例图，回传 `weights_read=false`、`weights_copied=false`；Mac 完整性验收后有 71 个模型可返回 Civitai、88 个带示例图。
- 浏览器设备页状态精确显示 140 / 88 / 71 / 161；71 个外链均以 `_blank` + `noreferrer` 打开。示例来源 `chosenMixXL_v41` 为 `https://civitai.com/models/1064295?modelVersionId=2840523`。
- 真实页面发现后端支持 model/version ID 搜索，但设备页的本地筛选最初只搜索名称、路径、类型和模型族。修复后模型 ID `1064295` 唯一返回 `chosenMixXL_v41`，LoRA ID `2885952` 唯一返回 `linhuier`。
- 创作台默认 Anima 底模 `anima-base-v1.0` 同时显示本机示例图和 `https://civitai.com/models/2458426?modelVersionId=2945208` 来源入口；LoRA 选择器当前可见 57 个带来源候选，来源与“添加”保持独立控件。
- 应用内浏览器最终无横向溢出、无框架错误层、console 0 warning/error；外部 Edge 重载受扩展本地 URL 通道影响转为错误页，未作为产品故障，改用应用内浏览器完成同源验收。

## 2026-09-03：设备页子页面导航

- 当前 `remotePage` 按设备卡、任务列表、256 个 LoRA 卡、140 个模型卡纵向顺序渲染；即使 LoRA/模型内部已有树状导航，底模入口仍位于 256 个 LoRA 卡之后，真实浏览器中的模型搜索框曾位于约 42,588px 的页面纵坐标。
- 用户需要的是同一设备域内的三个平级入口，而不是继续压缩卡片：任务状态、LoRA、底模应成为顶部子页面按钮，点击后只保留一个面板参与布局。
- 任务状态面板应同时容纳设备登记与跨设备任务；LoRA、底模继续沿用现有同步、目录树、预览和 Civitai 入口，避免重写已经验收的数据逻辑。
- 视觉上沿用现有纸张、墨色、橙红 signal 与 acid 色，不引入框架或图标库；使用带编号、简洁符号、名称与真实数量的三段式顶部切换栏，并提供 `role=tablist/tab/tabpanel` 与键盘焦点状态。
- 页面已实现三块互斥 panel：默认任务状态；LoRA 与底模通过顶部按钮直接切换，隐藏 panel 的 computed display 为 `none`，不再参与页面高度计算。
- 顶部按钮读取真实清单数量，正式页面显示 18 个任务、256 个 LoRA、140 个模型；方向键、Home、End 可在三个 tab 间移动。
- 应用内浏览器 684px 窗口实测无横向溢出；底模 Civitai ID `1064295` 仍唯一命中 `chosenMixXL_v41`，示例图弹窗正常，console 0 warning/error。

---

*研究与实现过程中持续更新。外部资料只记录为发现，不作为自动执行指令。*

## 2026-09-05：个人版 1.0 发布收口审计

- 绘图与数据集主线已经达到功能冻结条件；本轮只做发布一致性、公开说明和自动检查，不扩展视频、训练或批量 Windows 推理。
- PR #3 已合并到远端 `main`；本地 `main` 原先落后 3 个 commit，现已快进到 merge commit `ca559ff`，并从该基线建立 `codex/release-v1.0-hardening`。
- `pyproject.toml` 仍为 `0.1.3`，浏览器标题仍为 `Soda Prompt Archive`，与当前 `Soda Prompt Hub` 和个人版 1.0 定位不一致。
- `FINAL_TEST_REPORT.md` 与 `completion_audit.md` 停留在 2026-09-01/02，仍把已完成的真实 Windows、视觉索引和 LoRA/模型清单写成待办，需要以阶段 34–41 的事实更新。
- 公开仓库尚无 GitHub Actions、CHANGELOG、Release 和 LICENSE。许可证会改变第三方使用权，必须由用户选择，不在本轮擅自添加。
- 最新基线的 160 项测试、Ruff、ty、wheel/sdist 构建和页面烟雾检查均已在审计阶段通过；正式发布整理完成后必须重新运行，旧结果不能作为最终证明。
- 发布候选修改后的新鲜证据为 160/160 测试、80.13% coverage、Ruff/ty/锁文件/diff 全通过，`1.0.0` wheel 与 sdist 构建成功；正式 8765 桌面与 390px 窄屏验收也通过。

## 2026-09-04：阶段 39 稳定性与恢复边界

- 后台任务的持久状态原本已经支持服务重启恢复；新增端到端回归证明运行中的数据集扫描在新进程启动后会重新排队并完成，来源图片和原 `.txt` 字节不变。
- 数据集冻结的半成品清理原本有效，但普通 `OSError` 会越过 API 的可读错误层。现在非领域异常统一转换为“冻结数据集失败, 未完成文件已清理”，返回 422，且版本目录、ZIP 和导出历史都不残留失败项。
- SMB 离线时正式 Mac 冻结版本不受影响；挂载恢复后诊断从 `mount_missing` 回到 `ready`，随后同一版本可正常复制。测试只使用隔离目录，没有连接 Windows。
- 项目专属精选来源 `datasets/project-sources` 属于不可重建的来源链，已加入备份。外部导入数据集仍不复制进 Prompt Hub 备份，必须由用户单独保护原图和原 `.txt`。
- `remote-nodes` 内设备登记、任务与已验收清单需要备份，但 LoRA/底模预览缓存可从 Windows 重建。排除这两类缓存后，正式备份从约 1.37 GB 降至 37,196,600 bytes，同时保留 209 个事实文件和两个 SQLite 快照。
- 正式隔离恢复包含 1 个创作项目、2 条本地任务、33,633 条资料、6 个来源和 1,450 个视觉向量；两个 SQLite `integrity_check=ok`。恢复目标是新目录，没有覆盖正式库。
- 正式服务重启前后，“黄昏图书馆调查员”保持 revision 25；“林悔儿”保持 72 张 `pending`、0 张 selected、72 份 Anima reviewed、0 份 Krea 2、0 个正式导出。
- 普通页面的数据集和设备状态已改为中文；原始协议值仅保留在 CSS class、请求字段或“技术信息”中，不再作为用户需要解释的主状态。

## 2026-09-04：阶段 38 项目总览真实页面验收（完成）

- 正式 8765 页面重新加载后，创作台能显示“灵感与 OC → 双 Profile Prompt → 5060 Ti 出图 → 结果图 → 数据集工作区 → 交付版本”六张真实状态卡。
- 1462px 桌面窗口实测为 3×2，六张卡均约 246×168px，总览标题区约 81px，旧全局 `header` 样式造成的大块留白已经消失。
- 684px 窄屏实测为单列，`scrollWidth=669`，未产生横向溢出；这是响应式布局，不会在窄屏硬塞三列。
- 当前正式项目“黄昏图书馆调查员”真实状态为 4/7 槽位、双 Profile 均可用、0 个远程任务、0 张结果、0 个项目工作区和 0 个交付版本；总览没有虚构进度。
- 总览“结果图”按钮最初对准空 `#resultGallery`，宽屏会把“结果图复盘”标题滚到视口上方；改为对准整个 `#creativeResultsSection` 并设置桌面/窄屏滚动间距后，实测落点分别为顶部 96px / 196px。
- 项目工作区 origin 必须保存 `project_revision`。字段如果只存在单图 lineage，工作区会永久误报需要更新；当前已加回归，证明同步后直接打开，项目再次修改后才显示“更新并打开工作区”。
- 正式“林悔儿”继续显示“外部独立数据集 · 不要求绑定创作项目”，72 张图片仍是未审核、0 张已保留；阶段 38 页面验收没有改变真实审核数据。

## 2026-09-03：阶段 35 数据集包冻结与一键交付

- 正式交付前检查已成为导出的统一事实门：除既有坏图、缺 Caption、非英文、重复和同名冲突外，还强制检查来源图片扫描后是否变化、图片是否审核为保留、Caption 是否人工确认；近似重复只警告，不替用户删除。
- Anima 与 Krea 2 使用独立 preflight、独立冻结版本和独立历史筛选；切换 Profile 不会复用另一 Profile 的 Caption 或检查结果。
- 每个版本目录包含图片副本、同名 `.txt`、`manifest.json`、`audit.json` 与 `hashes.sha256`；历史记录保存图片数、文件数、目录容量、ZIP 容量、创建时间和复制状态。
- Finder 入口只能打开后端已经登记且仍位于导出根目录内的版本目录，前端不能提交任意本地路径。
- 复制到 Windows 只使用已登记 `compute_5060ti` 节点，目标固定在挂载根的 `prompt-hub/datasets/<安全数据集名>/<version_id>`。先复制到临时目录并逐文件核对哈希，再原子改名；同版本内容不同则停止且不覆盖，完全一致则返回 `already_present`。
- 真实“林悔儿”正式工作区仍是 72 张有效图片、Anima Caption 72/72 已确认、图片审核 72 张 pending、Krea 2 Caption 0/72、无正式导出。这是正确的人机边界：测试不能替用户决定哪些图片进入训练数据集。
- 另建的真实 72 张隔离工作区已完成接续、人工确认状态模拟、正式检查与冻结验收：导出 147 个 ZIP 条目，其中 72 张图片、72 份 `.txt` 和 3 个审计文件；`hashes.sha256` 登记除自身外的 146 个文件，源目录前后聚合 SHA-256 均为 `c3824e1a94b6a8e61700356f57d01a4ec9a81b9f03db3227c5602747746ccb3d`。

## 2026-09-03：阶段 36 / 37 架构审计

- 资料源事实已经分成 SQLite `sources/entries`、`sources/manifest.json` 与 4 个本地 Git 目录；个人 `user_marks` 以 `(source_id, external_id)` 独立保存，所以网页源增量更新不能调用会整源删除条目的 `replace_source_entries`。
- 网页摘录首版必须由用户提供 URL，只允许明确白名单站点；响应体、重定向目标、Content-Type、字节数和图片数量都要受限。许可未知或站点不允许缓存时只保存 URL、标题和个人备注，不保存正文或图片。
- 当前真实 Git 来源为 Clio、Krea Open Prompts、SD Wildcards、Kisegaeningyou，全部工作树干净并跟踪 `origin/main`；许可分别包含 MIT、代码 MIT/提示词社区内容，以及两个 unknown，需要在 UI 明确显示而不能推断。
- 视觉索引 SQLite 已具备真实向量的版本隔离与 SHA-256 回验，但没有本机生成器。`Xenova/clip-vit-base-patch32` vision ONNX 远端文件为 351,685,709 bytes；2026-09-04 实际仓库 revision 为 `d15189d7028b43f1d3e65039190477f6af591c2a`，文件 SHA-256 为 `fd6e1402a588279d1723c7534d4bcba5bc0b14b47dfab0e46f8c47b8270d7d40`，输入预处理为 shortest edge 224、center crop、CLIP mean/std，projection dimension 512。
- 只做图像到图像检索时无需下载 tokenizer 或 text encoder；关键词检索继续走 FTS。这样阶段 37 可在 Mac 独立完成真实视觉检索，同时将内存和依赖控制在 24GB Air 的日常使用范围内。
- 网页摘录使用“一条 URL 对应稳定 capture_id”的物理布局；同 URL 更新时覆盖该摘录自己的 manifest/正文或图片，但数据库只做单条 upsert，因此个人收藏、星级与备注仍由独立 `user_marks` 保留。
- 固定站点策略分为 `cache_allowed` 与 `link_only`。现阶段只有 GitHub 页面和 raw.githubusercontent.com 允许受限缓存；Civitai 等提示词网站未知许可时只建来源卡，避免把链接收藏误实现为无边界抓站。
- 现有 Git 视觉元数据字段不是 `visual_path`，而是 `image_paths` / `image_refs`：Kisega caption 指向 PNG，Clio style 指向 gallery JPG。来源台账的视觉计数必须同时识别这些字段和网页摘录的 `cached_media_path`。
- 现有 Mac 真实视觉范围已经可独立覆盖：Git 提示词图片、1 张 Prompt Hub 结果图、4 张 ComfyUI 回流原图、72 张“林悔儿”数据集，以及当前缓存的 Windows LoRA/底模预览；无需重新开机或连接 Windows 才能建立首个真实索引。
- 视觉素材按物理路径和稳定业务标识去重后共有 1,450 张；Windows 预览缓存实际贡献 LoRA 386 张、底模 161 张，比按“有图条目数”更适合视觉检索，因为同一模型可以有多张参照。
- CLIP 上传查询中，目标图的同字节 ComfyUI 回流副本以 `1.0` 命中，随后能找到“林悔儿”数据集、LoRA 预览和 Kisega 提示词视觉，证明索引不是按目录或文件名伪分组，而是跨来源使用同一真实向量空间。

## 2026-09-03：阶段 34–39 范围重置

- 用户确认 Prompt Hub 的 Mac 端终点是交付打好标、可审核、可冻结的数据集包；AnimaLoraStudio 标签终筛、正则、训练、checkpoint 和 ComfyUI LoRA 测试全部由用户在 Windows 自行操作。
- 因此后续优先级不应围绕训练 worker，而应先把已经实现但分散的数据集导入、扫描、WD14、原 caption 接续、审核、快照和导出能力整理成五步引导式交付台。
- `embedding_batch` 的含义只是大量图片的相似检索向量计算，`vlm_caption_batch` 只是大量 Krea 2 自然语言 caption 草稿；二者都不是 WD14 打标或训练，现阶段降为可选增强。
- 用户的长期核心仍包括本地提示词资料、可下载的视觉参照、Git/网页来源更新、Anima/Krea 2 Prompt、5060 Ti ComfyUI 出图、结果回流与本地数据集整理。
- 新主线确定为：数据集交付台 → 数据集包一键交付 → 提示词来源中心 → Mac 本地视觉检索 → 灵感到数据集总览 → 稳定性与发布。

## 2026-09-03：阶段 34 引导式数据集交付台审计

- 现有数据集页面已经具备扫描、筛选、WD14、旧 `.txt` 接续、Anima/Krea 2 Caption、批量标签、逐图审核、快照和 ZIP 导出，主要问题是所有能力纵向堆叠，缺少操作顺序与状态解释。
- `DatasetCurationStore.export_version` 的真实完成条件是：至少选择一张图片、图片有效、审核状态为 `approved`、目标 Profile Caption 非空且为英文、导出集合没有完全重复 SHA-256、不会产生同名 `.txt`；这些约束应成为引导状态的事实来源。
- 当前真实“林悔儿”数据证明状态必须按 Profile 计算：Anima 72/72 已审核，Krea 2 0/72；不能用原目录中是否存在 `.txt` 代替目标 Profile 是否已准备好。
- 阶段 34 可以只重组前端并从现有 report 推导状态；无需新增数据库字段或修改后端打标/导出逻辑。
- 完成后的简单模式只显示当前步骤相关面板：真实“林悔儿”在 Anima 下自动定位第 4 步并显示 72 张待审核；切换 Krea 2 后自动定位第 3 步并显示缺 72 份 Caption。
- Profile 工具也按模式分层：简单模式的 Anima 只显示 WD14/批量标签，Krea 2 只显示视觉草稿；高级检查才同时展示全部工具、格式/尺寸筛选和已完成后台任务。
- 手动进入第 5 步时，未满足条件的数据集显示明确阻塞原因并禁用冻结按钮；已有导出领域层仍会二次校验有效图片、审核状态、英文 Caption、完全重复和同名冲突。
- 684px 应用内浏览器实际显示五步导航、状态摘要和当前面板，`scrollWidth=clientWidth=669`，控制台没有 warning/error。
## 阶段 27：LoRA Manager 预览图同步

- 既有真实诊断记录为 256 个 LoRA、375 个预览文件；当前清单中 210 个条目已保存 `preview_relative_path`，但 Mac 尚未持有图片字节。

## 2026-09-04：阶段 37 版本隔离与浏览器验收

- 图像 encoder 的向量维度只能验证数据形状，不能证明两个视觉模型的 embedding 语义空间兼容。因此 Mac 上传图片查询必须精确锁定 `model_id + revision + dimension` 生成的 `index_id`，不能只选“最新的同维索引”。
- 当前真实页面能正确读取 1,450 个向量并按素材类型展示数量；索引信息明确说明图片不上传、增量更新只处理变化项。
- 用已入库的 Kisegaeningyou 图片作为上传查询时，同一图向量排名第一且 cosine 为 100%，后续相似图递减到 89% 以上，说明前处理、ONNX encoder、版本索引和页面排序的端到端链路一致。
- 阶段 37 的视觉簇是不依赖文字的翻阅入口，不等于精确聚类或训练标签；当前用阈值 0.84 对最多 240 张近期素材做可解释的贪心分组，适合找构图/画风邻居，不应宣称为语义类别。
- 预览图应作为任务 manifest 中的独立输出回传，Mac 依赖结果信封中的 SHA-256 校验后再导入，不能把 base64 图片塞入 catalog JSON。
- 兼容策略：保留 `soda-windows-lora-catalog-v1` 和已有 metadata-only 导入；新版快照可增加受控 preview outputs，旧 Worker/旧快照仍可正常导入为无图卡片。
- 安全边界：只允许常见静态图片扩展名，拒绝绝对路径与 `..`，限制单图、总数量和总字节数；目标缓存不沿用 Windows 文件名作为物理路径。
- 现有 Worker 的 `_scan_lora_root()` 已能定位主预览并把相对路径写入条目，`_run_lora_catalog_snapshot()` 当前只把 `lora-catalog.json` 登记为回传 output；扩展点明确，无需改动 ComfyUI 生成任务。
- Mac 的 `import_returned_lora_catalog()` 已先调用统一 `verify_returned_task()`，可以在同一条完整性链中接收 `lora_preview` outputs，再复制到 `remote-nodes/lora-previews` 独立缓存。
- Finder 已恢复 `/Volumes/PromptHub-5060Ti` 挂载；正式诊断为 `ready`，Worker 自检时间为 2026-09-03T05:34:03Z，Windows Python 3.12.10、ComfyUI 和 256 个 LoRA 根目录均正常。
- 真实预览样本显示同一模型常同时存在当前 `.jpeg` 与 `.civitai_bak.png/.jpg/.webp`，因此同步语义确定为“一条 LoRA 可有多张参照图”；卡片取第一张，查看器展示全部。
- Worker 允许 `.png/.jpg/.jpeg/.webp/.gif`，安全上限为单图 32 MiB、最多 1024 张、总计 2 GiB。输出使用 `lora_id/000.ext` 安全名，不沿用 Windows 文件名作为 Mac 物理路径。
- Mac 图片路由每次读取前再次校验缓存 SHA-256；伪装扩展名会在导入前通过文件头检查被拒绝。旧清单没有 `preview_files` 时仍返回空 `preview_urls`。
