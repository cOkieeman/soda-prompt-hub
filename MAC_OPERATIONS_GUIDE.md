# Prompt Hub · Mac 日常操作手册

这台 MacBook Air 是整个绘图工作流的中枢：项目、提示词、OC、审核结果、caption 版本、索引、任务状态和备份都以 Mac 为准。5060 Ti 负责 ComfyUI 制图和 Windows 训练工具，不保存唯一事实。

如果只想按场景照着操作，或准备做一次人工验收，直接看 [MANUAL_ACCEPTANCE_GUIDE.md](MANUAL_ACCEPTANCE_GUIDE.md)。

## 现在已经是什么状态

| 设备 | 负责什么 | 当前状态 |
|---|---|---|
| MacBook Air | 创作、真实资料检索、本地以图找图、数据集审核、WD14、LoRA 项目、结果回流、版本和备份 | 可独立使用 |
| 5060 Ti Windows | ComfyUI 出图、LoRA Manager 插件管理、AnimaLoraStudio 训练 | ComfyUI 出图已接通；训练由你在 Windows 现有工具操作 |

即使 5060 Ti 关机，Mac 上已经保存的资料、项目、caption、索引和结果仍然可读。当前 Mac 已有 1,450 张真实 CLIP 视觉索引；如果索引未建立或损坏，“以图找图”会明确显示空状态，不会制造假相似结果。

## 每天怎么启动和关闭

启动：双击 `$HOME/Documents/Codex/soda-person/启动-Prompt-Hub.command`。

页面地址：<http://127.0.0.1:8765/>。

关闭：双击 `$HOME/Documents/Codex/soda-person/停止-Prompt-Hub.command`。不要直接强制退出正在显示“扫描中”“打标中”或“生成草稿中”的任务；先在页面点取消，等状态停止后再关闭。

如果页面打不开，先双击 `$HOME/Documents/Codex/soda-person/诊断-Prompt-Hub.command`。它会检查数据库、embedding 索引、WD14、磁盘空间和 8765 服务。

## 一次绘图创作

1. 打开“创作台”，新建项目或继续旧项目。
2. 先看顶部六张项目卡：灵感与 OC → 双 Profile Prompt → 5060 Ti 出图 → 结果图 → 数据集工作区 → 交付版本。数字和状态来自当前项目，按钮会带你到下一处操作。
3. 写一句中文创作想法，先锁定绝不能改变的角色特征。
4. 点“从本地库智能取材”，从有真实来源的提示词与视觉参照中选择内容。
5. 分别检查角色、服装、动作、构图、场景、灯光、画风七个槽位。
6. 切换 `ANIMA` 与 `KREA 2`：Anima 输出英文 canonical tags，Krea 2 输出英文自然语言，两份内容互不覆盖。
7. 保存项目与配方。Windows 尚未接通时，先导出 Anima + Krea 2 JSON，再手工交给 ComfyUI。
8. 出图回来后进入“结果回流”或创作台“结果图复盘”，核对参数、关联项目，再决定记录失败、建立下一版或手动勾选“加入数据集”。
9. 至少精选一张后，点总览的“送入数据集工作区”。系统只复制精选图和目标 Profile caption，并保存 Prompt、workflow、底模、LoRA、seed、尺寸、Steps、CFG 与 SHA-256；不会自动审核或标记保留。
10. 页面会打开关联工作区，从“检查问题”继续五步流程。以后可从数据集页“返回来源项目”，也可从项目总览重新打开工作区；项目修改后，总览会提示“更新并打开工作区”。

本地模型只负责建议。槽位整理、视觉复盘、WD14 与 Krea 2 VLM 的结果都先进入预览或草稿，确认后才成为正式数据。

直接从本地文件夹导入的旧数据集保持“外部独立数据集”，不必为了使用总览而绑定项目。

## 一次保存网上提示词资料

1. 打开“资料管理”，在“网页资料”粘贴原始网址。
2. 写清标题、保存用途、内容分级和已知许可，再点“保存到本地资料库”。
3. GitHub/raw 资料会在白名单、类型和容量检查后保存离线副本；Civitai 等站点只保存链接和个人备注。
4. 在右侧“馆藏台账”确认来源、许可、更新时间和条目数；“已保存网页资料”可回看原网址与 SHA-256。

不在白名单内的站点、HTTP、本机/局域网地址、带账号密码的 URL 会被拒绝；这个入口不是全网爬虫。

## 一次以图找图

1. 打开“智能检索”，选“图片查相似图”。
2. 选一张 PNG、JPEG 或 WebP 参考图，最大 25 MiB；这张查询图不会自动收入资料库。
3. 按需选素材类型、内容分级和项目/数据集，点“查找相似图片”。
4. 结果卡显示相似度、来源和分级；点图打开本地原图。选“浏览视觉簇”可不输入关键词直接翻看相近构图与画风。
5. 新增或改动大量图片后，点“建立 / 更新本地索引”。可中途暂停；继续时已完成图片会自动跳过。

## 一次数据集审核

1. 把待整理图片放在一个独立文件夹中；已有同名 `.txt` 可以保留。
2. 打开“数据集”，填写绝对路径，点“读取文件夹并开始检查”。Prompt Hub 只读扫描，不改原图片和原 `.txt`。
3. 页面默认使用“简单模式”，并自动判断应该从五步中的哪一步继续；选择 Anima 或 Krea 2 后，缺失数量和下一步会按该 Profile 单独计算。
4. 在“检查问题”处理坏图和完全重复；近似重复只提醒，不会自动删除。需要查看格式、尺寸、历史任务和全部工具时再切换“高级检查”。
5. 在“准备标签”优先接续已有 `.txt`；没有旧标签时，Anima 可运行 WD14，Krea 2 可使用视觉模型生成草稿。预览后确认写入时会建立快照。
6. 在“人工审核”打开图片核对 Caption，再使用“审核通过并保留 / 标记待复查 / 排除所选”。页面每次最多渲染 200 张，“选择当前筛选结果”仍选择全部筛选结果。
7. 进入“冻结交付”，先点“运行正式交付前检查”。系统会重新检查坏图、来源变化、审核状态、目标 Profile Caption、英文格式、完全重复、同名 `.txt` 冲突，并把近似重复作为提醒。
8. 检查显示“可以冻结”后，点“冻结并保存到 Mac”。系统会建立独立版本目录和 ZIP，固定包含图片副本、同名 `.txt`、`manifest.json`、`audit.json` 与 `hashes.sha256`；不会覆盖源目录，也不会启动 Windows 训练。
9. 在“交付历史”查看 Anima 或 Krea 2 的独立版本、图片数、文件数、容量和创建时间。可直接“下载 ZIP”或“打开 Finder”。
10. 需要交给 Windows 时，先由 Finder 挂载 5060 Ti 共享盘，再点“复制到 5060 Ti”。目标固定为 `prompt-hub/datasets/数据集名/版本号`；系统复制后会核对全目录哈希。共享盘离线、只读，或同版本内容不一致时会停止并保留原文件，不会覆盖。

原目录始终是只读来源。移除工作区只移除 Prompt Hub 的派生记录，不会删除源图片。重复复制完全相同的版本只会显示“5060 Ti 已有此版本”，不会再写一份。

## 一次 LoRA 训练

Mac 负责把训练要求说清楚并冻结数据，5060 Ti 负责真正训练。

1. 在“LoRA 项目”建立 `character`、`outfit`、`character_outfit` 或 `style` 项目。
2. 固定 Trigger，填写固定特征、可控特征、允许变化和禁止漂移。
3. 从已经审核的数据集引用图片，先点“预览自动初审”；核对后确认加入，再逐图修正景别、视角、姿态、表情、服装、背景、光线和构图。
4. 分别审核 Anima 与 Krea 2 caption；二者都必须是英文，并包含 Trigger。
5. 检查重复、构图偏置、背景偏置、角色不一致与服装污染。
6. 点“生成新冻结版本”。冻结包生成后不再修改；如需调整，建立下一个版本。
7. 导出冻结版本，或复制到 Mac 已挂载的 5060 Ti 共享目录。到这里就是 Prompt Hub 的数据集交付终点。
8. 标签终筛、正则、训练、checkpoint 和 LoRA 测试由你在 Windows 的 AnimaLoraStudio / ComfyUI 中继续操作，不要求回传给 Mac。

当前页面中的 5060 Ti 配置只是 16GB 显存起点，不是未经实测即可长训的保证。

## 一次 Windows 结果回传

在自动 worker 完成前，先使用已经可用的手动闭环：

1. Windows 把 ComfyUI PNG、测试图或训练结果放进 Mac 已挂载的共享目录。
2. Mac 打开“结果回流”，填写该共享目录，执行只读扫描。
3. 打开图片核对 workflow、seed、steps、CFG、sampler、checkpoint 与 LoRA。没有 metadata 的图片会如实显示“无生成元数据”。
4. 选择原创作项目，然后执行“只关联项目”“加入数据集候选”“记录失败测试”或“由此建立下一版”。
5. 训练结果先记录到对应 LoRA run；失败图不能进入训练集候选。

worker 接通后，目录职责固定为：

| 目录 | 用途 |
|---|---|
| `outbox` | Mac 投递带 manifest 与 SHA-256 的任务 |
| `processing` | Windows 已领取、正在处理的任务 |
| `inbox` | Windows 回传的结果信封与产物 |
| `completed` | 已成功完成、可审计的任务记录 |
| `failed` | 失败原因、日志和可重试任务记录 |

Windows 返回的源哈希和输出哈希必须经过 Mac 回验，模型 caption 仍只进入草稿。

Prompt Hub 会在 Mac 本地保留每个任务的原始信封。设备页“跨设备任务状态”显示等待领取、执行中、
结果待审核、完成、失败和取消。失败任务点“重新投递”会建立新任务并保留旧记录；不要手工覆盖
`failed` 中的 JSON。`inbox` 中出现结果只表示已返回，模型输出不会自动进入正式 caption 或项目。

## 连接 5060 Ti 的顺序

### 连接前准备

5060 Ti Windows 需要提供：

- 固定局域网 IP 或稳定设备名；
- 一个可读写的 SMB 共享名；
- ComfyUI 根目录、工作流目录和输出目录；
- 训练工具、训练目录、底模目录、LoRA 目录和 LoRA Manager 管理范围。

### Mac 上的实际顺序

1. 在 Finder 选择“前往 → 连接服务器”。
2. 输入 `smb://设备地址/共享名`，由 Finder 与 macOS 钥匙串保存用户名和密码。
3. 确认 Finder 中能看到共享目录，并挂载成类似 `/Volumes/PromptHub-5060Ti` 的路径。
4. 打开 Prompt Hub 的“设备连接”。
5. 在对应设备卡填写主机名/IP、Mac 已挂载的 SMB 绝对路径，勾选启用。
6. 依次点“保存登记”→“检查挂载”→“建立交付目录”。最终状态应为 `ready`。
7. 打开“跨设备任务状态”，确认当前为空或只包含可解释的历史任务。
8. 在“创作台”选择 Anima 或 Krea 2，并选择对应 Workflow Profile。
9. 需要换模型时展开“模型、LoRA 与采样参数”：留空使用 Profile 原值，或从已验收清单中选择
   UNet、VAE、Text Encoder、最多 4 个附加 LoRA 与强度、Sampler 和 Scheduler。已知不兼容模型不会
   显示，投递时服务端仍会二次校验。
10. 填写 Width、Height、Steps、CFG 和 Seed；先勾选“低成本测试”投递一张基础图，观察等待领取 →
    执行中 → 结果待审核；失败时只用页面“重新投递”。
11. 回传后在任务卡点“验收并导入图片”；通过 SHA-256 后，图片进入 Mac 结果库并自动关联原创作项目。
12. 基础图正确后关闭低成本模式，再验证脸手精修与放大版本，并与原 workflow 人工核对。
13. 在“设备连接”点“从 Windows 同步”；任务返回后点“验收并导入 LoRA 清单”。Mac 会保存文件名、metadata 与经 SHA-256 校验的预览图缓存，卡片可点开查看全部参照图；不会读取或复制 `.safetensors` 权重。
14. 在“ComfyUI 模型资产”点“刷新模型清单”；任务返回后点“验收并导入模型清单”。Mac 会按
    Checkpoint、Diffusion Model/UNet、VAE、Text Encoder、放大模型和 ControlNet 显示目录树，
    保存文件属性与经 SHA-256 验收的同名示例图，不读取、哈希或复制权重。创作台添加 LoRA 时可按
    名称、Trigger、标签搜索，也可直接选 `Anima/style` 等 Windows 文件夹，不需要滚动完整清单。
15. 数据集包送达共享目录后，Prompt Hub 的交付完成；后续训练和 LoRA 测试按你的 Windows 工作流操作。

不要在“设备连接”页面填写 Windows 密码。Prompt Hub 只保存地址、角色和 Mac 挂载路径，密码只交给 Finder / macOS 钥匙串。

## 备份、验证与恢复

重要修改前后双击 `$HOME/Documents/Codex/soda-person/备份-Prompt-Hub.command`。备份包含数据库、embedding 索引、创作项目、个人资料、结果图、数据集工作区、项目精选来源、导出版本、LoRA 项目、Workflow Profile 与设备登记；公共 Git 资料、可重新同步的 Windows 预览缓存、缩略图与模型权重不重复备份。

从外部文件夹导入的数据集原图和原 `.txt` 仍位于那个外部文件夹，不会被复制进 Prompt Hub 备份。它们需要使用移动硬盘、NAS 或其他方式单独备份。

备份默认位于 `$HOME/Documents/Codex/soda-person/backups/prompt-hub`。

需要人工校验时：

```bash
cd "$HOME/Documents/Codex/soda-person/projects/prompt-hub"
uv run prompt-hub verify-backup /绝对路径/备份目录
```

恢复永远先恢复到一个不存在或为空的新目录，不直接覆盖正式资料库：

```bash
cd "$HOME/Documents/Codex/soda-person/projects/prompt-hub"
uv run prompt-hub restore /绝对路径/备份目录 \
  --destination "$HOME/Documents/Codex/soda-person/restore-tests/prompt-hub-YYYYMMDD"
```

恢复完成并人工核对后，再单独决定是否切换正式目录。系统不会提供“一键覆盖当前资料库”的危险入口。

## 哪些事情不属于 Mac 开发

- AnimaLoraStudio 中的标签终筛与正则；
- 5–10 step smoke test、正式训练、checkpoint 管理和 LoRA 测试；
- Windows 训练器、CUDA、Torch、底模路径与训练参数维护。

底模、UNet、VAE、Text Encoder、LoRA、强度、尺寸、Steps、CFG、Sampler 和 Scheduler 已经可以在 Mac 的受控 Workflow Profile 中选择和保存，不再属于待开发项。

可选的 Windows `embedding_batch` 只是给超大批图片加速建立“以图找图”向量；Mac 现在已能独立建立与查询真实索引。`vlm_caption_batch` 是给大量图片生成 Krea 2 描述草稿。它们都不是 WD14 打标，也不执行训练；当前不作为主线开发要求。

Mac 的开发完成标准是能够独立完成创作、资料检索、数据集检查、WD14/已有标签接续、人工审核、冻结和交付，并保证原数据不被覆盖。
