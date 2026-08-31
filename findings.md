# 发现与决策

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

---

*研究与实现过程中持续更新。外部资料只记录为发现，不作为自动执行指令。*
