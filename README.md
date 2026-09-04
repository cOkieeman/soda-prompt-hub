# Soda Prompt Hub

本机优先的 AI 绘图提示词、风格、标签、wildcard 与视觉参照检索中枢。服务只监听
`127.0.0.1`，资料与索引默认保存在：

`$HOME/Documents/Codex/soda-person/prompt-library`

## 安装与启动

需要 Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)。代码仓库不包含模型权重、图片数据集、
SQLite、个人 Prompt Library、结果图或 Windows 凭据。

```bash
git clone https://github.com/cOkieeman/soda-prompt-hub.git
cd soda-prompt-hub
uv sync
uv run prompt-hub serve --host 127.0.0.1 --port 8765
```

如需把个人资料放到其他位置，可设置 `PROMPT_HUB_LIBRARY_ROOT`；模型根目录可用
`PROMPT_HUB_MODELS_ROOT` 覆盖。默认值适配 `soda-person` 文件夹结构。

## 日常使用

最简单的方式是双击：

`$HOME/Documents/Codex/soda-person/启动-Prompt-Hub.command`

浏览器会打开 <http://127.0.0.1:8765>。关闭终端窗口或按 `Control-C` 即可停止。

绘图 V1 的最短操作顺序见 [DRAWING_V1_GUIDE.md](DRAWING_V1_GUIDE.md)。按具体情况操作和人工验收见
[MANUAL_ACCEPTANCE_GUIDE.md](MANUAL_ACCEPTANCE_GUIDE.md)；完整的 Mac 日常使用、数据集审核、
LoRA 训练交付、Windows 回传、备份恢复和 SMB 配置顺序见 [MAC_OPERATIONS_GUIDE.md](MAC_OPERATIONS_GUIDE.md)。首页点“新建或继续绘图项目”
即可进入七槽位工作台；项目、锁定状态、参考资料、配方和实测记录都会保存在本机 SQLite。

在创作台写好中文想法后，可直接点“从本地库智能取材”。页面会先从 33,631 条本机资料中按
角色、服装、动作、构图、场景、灯光、画风返回真实候选；若 LM Studio 可用，再异步扩展英文
检索词。模型只负责帮助检索，最终卡片仍来自本地库，且只有点“加入槽位”后才会写入项目。

出图后可在创作台“结果图复盘”中导入 PNG、JPEG 或 WebP。原图与缩略图只保存在本机
`prompt-library/test-results/prompt-hub`，不会上传云端。选择本地视觉模型后，页面会返回七槽位
观察、优点、问题、下一轮建议，以及 Anima/Krea 2 双格式反推；结果先预览，确认后才写入实测
备注，且只会补充空白、未锁定槽位。24GB Mac 建议复盘时只加载一只视觉模型。

复盘返回后还可以点“由此创建下一版”。Prompt Hub 会建立独立的 V2/V3 项目，保留角色、
七槽位、锁定状态、参考资料和 Steps/CFG/Seed，记录父项目、源结果图与复盘建议；上一轮结果图
不会复制到新项目，旧项目也不会被覆盖。项目列表中的 `V` 是创作轮次，`R` 是自动保存 revision。
进入 V2/V3 后，顶部“本轮迭代对照”会同时显示上一版、当前版和复盘观察，只列出发生变化或有
建议的槽位。点“确认填入”仍只会补充空且未锁定槽位，已有内容与锁定内容不会被替换。

满意的结果图可以直接加入本地数据集：在结果卡点“加入数据集”，选择 `Anima tags` 或
`Krea 2 自然语言`，需要时展开并修改这张图自己的 caption，再点“导出精选数据集 ZIP”。ZIP
包含未重编码的原图、同名 `.txt` 和来源清单 `manifest.json`，保存在
`prompt-library/exports/datasets`。只有手动精选的图片会进入包，不会自动上传 Windows 或云端。

Anima 数据集可以在结果卡点“WD14 自动打标”，或用下方工具栏对最多 24 张精选图片批量打标。
WD14 会保存 rating、general、character 和带置信度的原始结果，但只把 general tags 放入可编辑
草稿。先删改冲突、错误或不需要的标签，再点“确认用作 Anima caption”；确认前不会覆盖已有
caption，Krea 2 自然语言始终独立保存。

有视觉资料的卡片会显示本地缩略图。点击图片可打开本地原图；Kisega 聚合标签最多显示
3 个参照，并在图片右上角独立标记 `SFW`、`SUGGESTIVE` 或 `EXPLICIT-ADULT`。选择 Safety
筛选时，图片参照也会一起过滤。

每张卡片还可以保存到个人资料层：

- 点 `☆ SAVE` 收藏，点亮后会变成 `★ SAVED`；
- 点 1–5 颗星记录个人评分，再点当前星级可清除评分；
- 点 `NOTE` 写使用心得、模型适配、构图效果或测试结论；
- 点左栏 `☆ MY SHELF ONLY` 只看自己的收藏。

收藏、评分和备注保存在 `prompt-library/database/prompt-library.sqlite`。它们使用来源与原始条目
编号关联，执行“更新公共资料”或重建索引后仍会保留。这个数据库从 V1.2 起包含不可重建的个人
资料，需要和 `private`、`test-results`、`exports` 一起备份。

## 本地来源中心与以图找图

“资料管理”已集中展示本地 Git 库、网页摘录的来源、许可、更新时间、可检索条目和视觉参照数。
粘贴 GitHub 或 raw 直链时，系统按固定白名单保存允许缓存的正文或图片；Civitai、OpenArt、
PromptHero 与 Promptomania 默认只保存网址和个人备注。每个条目都保留原网址、抓取时间、策略与
SHA-256；重复保存同一 URL 采用增量更新，不会清除个人标记。

“智能检索”包含文字检索、图片查相似图和视觉簇三个独立入口。Mac 本地使用固定版本的
`Xenova/clip-vit-base-patch32` ONNX 视觉 encoder，不需要文字 encoder，也不会把图片上传。当前
正式索引为 1,450 张，覆盖提示词视觉、数据集、ComfyUI 回流、LoRA 预览和底模预览。
建立索引支持进度、暂停/继续、失败恢复和增量更新；没有真实向量时保持空结果，不用随机或颜色
特征伪造相似度。

## 项目总览与数据集来源

创作台顶部现在按六个阶段汇总同一项目：灵感与 OC、Anima/Krea 2 Prompt、5060 Ti 出图、
结果图、数据集工作区和交付版本。每张卡只读取真实数量与最近状态，并把“继续”按钮带到对应
操作区；总览本身不会自动精选、审核、冻结或向 Windows 投递任务。

在结果图中手动勾选“加入数据集”后，点总览里的“送入数据集工作区”。Prompt Hub 会复制原图
和目标 Profile caption 到项目专属只读来源目录，同时记录项目、结果图、Prompt、ComfyUI workflow、
checkpoint、LoRA、seed、尺寸、Steps、CFG 与 SHA-256。重复同步不会重复复制；项目或精选内容更新
后，卡片会提示“更新并打开工作区”。

进入数据集页后，项目来源工作区可以返回原创作项目；冻结版本的 manifest 也保留来源结果图。
新同步的图片仍然是“未审核、未选择”，必须按数据集五步人工确认。直接导入本地文件夹的旧数据集
继续显示为“外部独立数据集”，不要求绑定任何创作项目。

也可以在终端中启动：

```bash
cd "$HOME/Documents/Codex/soda-person/projects/prompt-hub"
uv run prompt-hub serve --host 127.0.0.1 --port 8765
```

## 更新公共资料

双击：

`$HOME/Documents/Codex/soda-person/更新-Prompt-资料库.command`

它会按顺序更新 4 个公共资料源，然后重建本地索引与缺失缩略图。公共 Git 原始目录不要
手工修改；个人 prompt 请放在 `prompt-library/private`。

## 连接 OC Manager

Prompt Hub 使用本地 JSON 交换，不直接连接或覆盖 OC Manager 的用户数据库：

1. 在 OC Manager 中导出单张角色卡、按世界打包，或全库备份 JSON；
2. 打开 Prompt Hub，切换到“角色库”；
3. 点 `CHOOSE OC JSON` 选择文件，再点 `IMPORT TO LOCAL INDEX`；
4. 导入后可按角色名、世界、故事、外观模块和已存 Prompt 检索；
5. 点“以此角色开始创作”把角色资料带入七槽位，或点 `OPEN CHARACTER FILE` 查看完整档案。

支持以下 OC Manager 格式：

- `oc-manager-single-character`
- `oc-manager-world-folders`
- `oc-manager-full-database`
- 旧版角色数组，以及包含 `characters/worlds/lore` 的 AppData JSON

角色、角色 Prompt 和世界元数据可从当前标准导出直接导入。世界观索引需要 JSON 本身包含 `lore`；
当前 OC Manager 某些全库导出版本可能没有带这个字段，后续在用户 fork 中补充导出即可，无需改动
Prompt Hub 数据结构。

每次有效导入都会先把原始文件保存到
`prompt-library/sources/imports/oc-manager`，再按稳定的角色 `id` 更新本地索引。同一角色重复导入会
更新资料和角色 Prompt，但不会删除文件中没有出现的其他角色。Prompt Hub 当前不会回写 OC Manager。

## 常用维护命令

```bash
cd "$HOME/Documents/Codex/soda-person/projects/prompt-hub"
uv run prompt-hub stats
uv run prompt-hub search "gothic cathedral" --limit 10
uv run prompt-hub import
```

## WD14 本地图片打标

已安装 `SmilingWolf/wd-swinv2-tagger-v3`，模型位置：

`$HOME/Documents/Codex/soda-person/models/wd14/wd-swinv2-tagger-v3`

网页结果图工作台已经接入单图与精选批量打标；也可以用命令独立检查任意图片：

```bash
cd "$HOME/Documents/Codex/soda-person/projects/prompt-hub"
uv run prompt-hub tag-image /绝对路径/图片.png --limit 50
```

命令默认使用 general threshold `0.35`、character threshold `0.85`，只把 JSON 输出到终端，
不会创建或覆盖 `.txt`。本机实测 CoreML 无法完整执行这只 SwinV2 ONNX，所以 `auto` 默认使用
CPU；单张 1024×1536 图片首次加载加推理约 0.7 秒。

## V1.7 数据集工作台

V1.7 后端已经能把任意本地图片目录注册为只读工作区，并在后台检查 PNG/JPEG/WebP、尺寸、
坏图、同名 `.txt`、缺失 caption、孤立 `.txt`、SHA-256 完全重复和 pHash 近似重复。扫描会生成
安全 WebP 缩略图与版本化 JSON 报告，保存在
`prompt-library/datasets/workspaces`；来源目录中的图片和 `.txt` 不会被移动、改名或覆盖。

后台任务状态保存在 SQLite，支持进度、取消、失败重试和服务重启后恢复。网页主导航的“数据集”
已经可以读取目录、查看缩略图和原图、筛选坏图/caption/重复组/尺寸/格式、批量选择，并保存
“保留 / 待复查 / 排除”审核状态。移除工作区只删除 Prompt Hub 的派生记录，不删除源目录。

工作台每页最多渲染 200 张图片，已经用 1,000 与 10,000 张隔离目录完成扫描和页面验证；翻页不会
改变筛选结果。“选择当前筛选结果”仍选择完整筛选集合，不会只选择当前 200 张。

V1.7B 已把工作区 WD14 接入可恢复后台队列，不再受结果图区域的 24 张同步上限约束。选择图片后
可以运行未打标/失败/多选/整个工作区队列，逐图结果和失败会持久化；同一任务重启后只继续未完成
图片。每张图片分别保存 Anima 英文 canonical tags 与 Krea 2 英文自然语言，批量标签修改会先预览
并生成可回退快照，中文标签只用于显示。

已有同名 `.txt` 时，可以先预览后批量接续到 Anima 或 Krea 2 Profile。默认只填空白 Profile、
状态为“待审核”；确认后整批只生成一个快照，已有内容不会自动覆盖，源 `.txt` 始终不变。

“冻结交付”会先执行正式交付前检查，强制核对坏图、来源变化、图片审核、目标 Profile Caption、
英文格式、完全重复和同名 `.txt` 冲突，并把近似重复单独列为警告。通过后可保存新的 Mac 版本，
固定包含原图副本、同名 `.txt`、`manifest.json`、`audit.json` 和 `hashes.sha256`。交付历史按
Anima/Krea 2 分开显示图片数、文件数、容量和时间，并可下载 ZIP、打开 Finder，或复制到已挂载的
5060 Ti `prompt-hub/datasets/数据集名/版本号`。复制采用临时目录、全目录哈希校验和原子改名；
目标已有不同内容时停止且不覆盖。

## V1.8 LoRA 项目台

主导航“LoRA 项目”用于在 Mac 上管理角色、服装、角色与签名服装一体、画风四类训练项目。
每个项目都要先固定 Trigger，并分别填写固定特征、可控特征、允许变化和禁止漂移。项目可以只读
关联 OC Manager 角色，也可以从已扫描的数据集工作区引用图片；引用只保存工作区 ID、相对路径、
SHA-256 和审核判断，不复制或改写来源。

逐图可标记候选、保留、排除、待补图或正则图，并填写景别、视角、姿态、表情、服装、背景、
光线和构图。“预览自动初审”会依据文件名、原 caption、现有 Profile caption 与图片横竖尺寸给出
保守建议；只有用户确认后才合并，且不会覆盖人工标记或改变图片状态。页面同时提示完全重复、
背景/姿态/构图偏置和人工标记的角色不一致或服装污染风险。

“生成新冻结版本”只接受已保留或正则图片，并强制 Anima 与 Krea 2 caption 分别为英文、已人工
审核且包含当前 Trigger。每次冻结都会在项目 `07_导出` 下新建不可变版本，分别输出 `Anima` 与
`Krea2` 的 train/reg 树、manifest、固定测试 prompt 和 5060 Ti 16GB 配置草案。Krea 2 草案明确
使用 Raw FP8、Qwen3-VL FP8、28 层 block swap、batch 1 和关闭 tag shuffle；交付 Windows 后仍需
由 AnimaLoraStudio 在真实驱动、Torch、CUDA、底模和权重路径下先做 5–10 step smoke test。

版本导出只读取已标记“保留”的图片，不写回来源目录。Anima 与 Krea 2 分别生成独立目录/ZIP，
包含同名图片与 `.txt`、`manifest.json`、`audit.json` 和哈希。节点协议可在
`/api/compute/contract` 查看；当前 Worker 已支持 ComfyUI 生成，训练仍由 Windows
AnimaLoraStudio 独立执行，Prompt Hub 不保存 Windows 登录凭据。

## V1.9 ComfyUI 结果回流

主导航“结果回流”负责把 ComfyUI 生成图带回 Mac。可以上传单张 PNG/JPEG/WebP，也可以只读
扫描本地或后续 SMB 挂载的输出目录。Prompt Hub 会按 SHA-256 去重，并从图片中读取真实存在的
ComfyUI `prompt` / `workflow`、seed、steps、CFG、sampler、scheduler、checkpoint、LoRA、尺寸与
正负 Prompt。普通 JPEG/WebP 没有这些字段时会明确显示“无生成元数据”，不会猜测或补写。

日常顺序固定为：导入 → 核对参数 → 选择创作项目 → 只关联 / 加入数据集候选 / 记录失败测试 /
创建下一版。只有“加入数据集候选”会设置 `dataset_selected=true`，之后仍需到创作台人工审核
Anima 或 Krea 2 caption；失败测试不会进入训练集。由回流图创建下一版时，原始 metadata 会进入
lineage，父项目与旧结果图保持不变。

`/api/compute/contract` 已定义 `comfyui_generate`、`lora_train`、`embedding_batch`、
`vlm_caption_batch`、`lora_catalog_snapshot` 与 `model_catalog_snapshot` 的任务/结果字段、SHA-256
回验规则及 worker 注册字段。
5060 Ti 的 SMB 节点和 Worker 已完成 ComfyUI 生成及 LoRA 只读清单实测；训练、Embedding 与 VLM
仍按同一协议逐项接入，不需要把密钥或 Windows 路径写进项目 JSON。

## V2.1 Mac 资料更新、Krea 2 草稿与视觉检索

“资料管理”可安全更新公共 Git 提示词库：只对干净且配置 upstream 的仓库执行 fast-forward-only，
有本地改动时会跳过，完成后重建本地索引。不会覆盖个人收藏、评分、备注或公共仓库中的本地修改。

“数据集工作台”的 Krea 2 视觉草稿队列会调用 LM Studio 视觉模型。模型结果只进入独立草稿，图片
详情同时显示正式 Krea 2 caption 与草稿；“只保存草稿”不会改变正式 caption，只有“确认写入
Krea 2”才创建可回退快照。Anima/WD14 始终保持独立。若 Qwen3 14B 正在驻留导致内存不足，请先
在 LM Studio 手工切换到 Qwen3.5 9B Vision；Prompt Hub 不会擅自卸载用户模型。

当前 Mac 已安装固定 revision 的 CLIP 视觉 encoder，并按模型 ID、revision 和 dimension 维护独立
版本。用户上传图片时只查询当前 encoder 的精确索引，不会与其他同维模型串用。通用的版本化
导入与查询接口仍保留；5060 Ti `embedding_batch` 只作为未来超大批加速选项，不是日常使用前提。
远程 Krea 2 草稿提交到 `/api/dataset-workspaces/{workspace_id}/krea2-vlm/import`，仍然只进入待确认草稿。

主导航“智能检索”已经把结果分为提示词资料、视觉参考、我的数据集和 Windows LoRA。FTS 关键词
检索始终可用；只有存在真实、版本兼容的 embedding 时才合并 cosine 结果。数据集详情的“以此图
查相似”同样只在源图 SHA-256 已进入真实索引后启用，不用颜色或随机向量冒充语义相似。

## Windows 设备接口

主导航“设备连接”只保留一个 5060 Ti 制图与炼丹节点。它运行 ComfyUI、ComfyUI 内的 LoRA Manager
插件，以及独立的 AnimaLoraStudio；批量 VLM 与 Embedding 只在 Mac 本地速度不足时再作为可选加速。Prompt Hub 只登记设备角色、主机名和 Mac 已挂载的
SMB 路径，不保存 Windows 用户名或密码。Finder 挂载完成后，页面可以检查
目录并建立 `prompt-hub/outbox`、`inbox`、`processing`、`completed`、`failed` 五个交付目录。

Mac 已实现共享目录任务投递、任务状态扫描和失败重试。每次投递都会在 Mac 的 `remote-nodes/tasks`
保留原始事实副本；失败重试创建新 task ID、增加 attempt 并保留 `retry_of`，不会覆盖旧失败记录。
“跨设备任务状态”只展示 queued/running/returned/completed/failed/canceled；returned 结果仍需走领域
导入接口和人工审核。API 为 `/api/remote-nodes/{node_id}/tasks` 与
`/api/remote-nodes/{node_id}/tasks/{task_id}/retry`。任务 payload 会拒绝密码、token 和凭据字段。

单卡任务默认串行，已部署 Worker 使用同一 GPU 锁执行当前支持的 ComfyUI 生成、LoRA 清单和模型
资产清单任务。
训练、Embedding、批量 Caption 与 WD14 适配器接入后继续共用该锁；训练优先级和不可抢占边界届时
再做真实负载验收。

LoRA Manager 只负责 ComfyUI 本机的 LoRA 扫描、预览和选用，不直接连接 Mac，也不负责训练。
Windows Worker 的 `lora_catalog_snapshot` 会读取 ComfyUI `LoraLoader` 名称、白名单 LoRA 根目录、
同名 `.metadata.json` 及关联的封面/示例图，规范化后作为独立输出回传。设备页先逐文件校验
SHA-256，用户再点“验收并导入 LoRA 清单”。Mac 将预览图放进独立 `remote-nodes/lora-previews`
缓存，在分类卡片显示主图并支持查看同一 LoRA 的全部参照图；无图条目保留占位。整个过程不复制
`.safetensors`，也不读取权重内容。sidecar 中有可靠的 Civitai model/version ID 或模型页 URL 时，
设备页和创作台会显示“查看 Civitai / 提示词”；本地路径、下载 API 和其他站点不会变成链接。

设备页的“ComfyUI 模型资产”是另一份只读事实清单。Windows Worker 只扫描配置白名单中的
Checkpoint、Diffusion Model/UNet、VAE、Text Encoder、放大模型和 ControlNet 目录，回传名称、
相对路径、类型、大小、修改时间及同名 sidecar 示例图；不会打开、哈希或复制权重。任务返回后点
“验收并导入模型清单”，即可在 Mac 上按“模型类型 → 顶层文件夹”浏览、搜索和查看底模示例图。
Worker 也会在同名 `.metadata.json`、`.civitai.info`、`.info.json` 或 `.json` 中查找 Civitai 来源，
有可信来源的底模会出现同样的返回入口。
创作台可把选中的底模安全写入 Profile 声明的 Workflow 节点；大量 LoRA 通过搜索和 Windows
文件夹筛选器添加，不再使用包含整份清单的超长原生下拉框。

### Anima / Krea 2 Workflow Profile

创作台右侧会按当前 Prompt 类型只显示匹配的 ComfyUI Workflow Profile。选择 Profile 后点“发送到
5060 Ti”，系统会先保存当前项目，在 Mac 的 `workflow-profiles/<profile>/runs` 留下不可丢失的生成
包，再复制同字节、同 SHA-256 的包到 SMB 并建立任务。原始 workflow 不会被改写，Prompt、negative、
seed、尺寸、steps、CFG、Sampler、Scheduler、底模/UNet、VAE、Text Encoder 与附加 LoRA 只允许
写入当前 Profile 明确声明的节点字段。

展开“模型、LoRA 与采样参数”即可调整当前 Profile。模型和 LoRA 选项来自 Mac 已验收的 Windows
清单；已知模型族不兼容的条目不会显示，服务端投递时还会再次校验。留空表示继续使用 Profile
原始值。附加 LoRA 最多 4 个，不会删除工作流原有的基础/工具 LoRA；每个项目分别保存 Anima 与
Krea 2 的选择。当前两份真实工作流的主模型都是 Diffusion Model/UNet，所以 Checkpoint 只在资产
页可浏览，不会被错误绑定到不存在的主 Checkpoint 节点。

首轮建议勾选“低成本测试”：Krea 2 跳过 SeedVR2 放大，Anima 满穗跳过 SAM3 脸手精修和 Ultimate
SD Upscale，只验证基础模型、LoRA、Prompt 与构图。基础图正确后再关闭低成本模式。Profile 原件、
节点映射和历次生成包属于 Mac 个人事实数据，会随 Prompt Hub 备份保存。

Worker 回传后，在“设备连接 → 跨设备任务状态”点“验收并导入图片”。系统会先验证源生成包和每个
输出文件的 SHA-256，再复制到 Mac 结果库；从创作台发出的任务会自动关联回原创作项目，之后可在
“结果回流”中加入数据集候选或建立下一版。重复点击只返回 duplicate，不会重复保存图片。

## 备份、恢复与诊断

双击 `$HOME/Documents/Codex/soda-person/备份-Prompt-Hub.command` 建立带 SHA-256 manifest 与
SQLite integrity 结果的备份；双击 `$HOME/Documents/Codex/soda-person/诊断-Prompt-Hub.command`
检查数据库、embedding 索引、WD14、磁盘与服务。CLI 还提供 `verify-backup` 和只允许恢复到新目录的
`restore`。完整顺序见 [MAC_OPERATIONS_GUIDE.md](MAC_OPERATIONS_GUIDE.md)，不使用终端的情景说明和
人工验收清单见 [MANUAL_ACCEPTANCE_GUIDE.md](MANUAL_ACCEPTANCE_GUIDE.md)。外部原始数据集不在
Prompt Hub 备份内，需要单独备份。

## LM Studio

MCP 名称为 `soda-prompt-hub`，提供：

- `search_prompts`
- `search_styles`
- `search_tags`
- `library_stats`
- `search_characters`
- `get_character_profile`
- `get_character_prompts`
- `search_world_lore`

三个搜索工具均支持 `favorites_only=true`，并会在结果中返回收藏、个人评分和备注。MCP 仍为
只读：个人资料目前只在本地网页中编辑。四个 OC 工具读取 Prompt Hub 中最近导入的 OC Manager
本地副本，不会写回角色卡。

如果 LM Studio 已经打开，请在 MCP/Integrations 页面重载配置，或退出后重新打开。创作台还会
发现本机 OpenAI 兼容接口中的文本模型；“整理未锁定槽位”先显示建议预览，只有点“确认应用”后
才写入项目。“智能取材”则先即时搜索本地库，再让已加载模型补充检索词；它不会用模型输出冒充
资料卡，也不会修改公共资料条目或检索锁定槽位。

视觉复盘推荐使用 `Qwen3.5-9B-Uncensored-HauhauCS-Aggressive`。在当前 24GB MacBook Air
上应先卸载 Qwen3 14B 等文字模型，再以 4096 context、parallel 1 加载这只视觉模型；真实
1024px 图片实测约 63 秒返回完整复盘。复盘结束后可卸载视觉模型，再恢复日常文字模型。

## 开发验证

```bash
cd "$HOME/Documents/Codex/soda-person/projects/prompt-hub"
uv run ruff format --check .
uv run ruff check .
uv run ty check src/
uv run pytest
```
