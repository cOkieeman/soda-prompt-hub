# Soda Prompt Hub 绘图使用顺序

## 最短流程

1. 双击 `$HOME/Documents/Codex/soda-person/启动-Prompt-Hub.command`。
2. 首页点“新建或继续绘图项目”。
3. 先用中文写一句创作想法，不希望被检索或改动的槽位点成 `LOCKED`。
4. 点“从本地库智能取材”，先看即时出现的真实资料候选；看到合适的图片或文字再点“加入槽位”。
5. 继续手动调整角色、服装、动作、构图、场景、灯光、画风七个槽位。
6. 在右侧切换 `ANIMA` 或 `KREA 2`，复制对应的 Positive 与 Negative/Avoid。
7. 满意后点“保存为配方”；5060 Ti 在线时可选择 Workflow Profile 和参数后直接发送，离线时仍可导出 Anima + Krea 2 JSON。

## 智能取材怎么工作

1. 中文想法先由内置规则拆成七类英文检索词，例如“黄昏图书馆”会进入场景和灯光。
2. 页面立即搜索本机 SQLite，并按槽位类型、分类、匹配度、视觉参照、收藏和评分排序。
3. 若 LM Studio 正在运行，已加载模型会在后台补充最多 4 个英文检索词，再搜索一次本地库。
4. 模型不会直接制造候选卡片；候选标题、文字、图片、来源和成人分级都必须来自本机资料库。
5. 只有点击某张候选的“加入”按钮，它才会进入对应槽位和视觉参考区；`LOCKED` 槽位整轮跳过。
6. 选择 SFW、Suggestive、Adult 或 Explicit adult 时，候选和图片会按项目分级过滤。合法成人向项目不会被固定按 SFW 处理。

## 从本地资料开始

1. 进入“提示词库”，检索服装、动作、场景、构图或画风。
2. 在卡片上选择要放入的槽位。
3. 点“加入创作”。文字和视觉参照会一起进入当前项目，已有内容不会被整段覆盖。
4. 返回创作台继续调整，来源信息会随项目和导出 JSON 保留。

## 从 OC Manager 开始

1. 在 OC Manager 导出角色或全库 JSON。
2. 进入“角色库”，选择 JSON 并导入本地索引。
3. 找到角色后点“以此角色开始创作”。
4. 角色身份与外观摘要进入角色槽位；角色 Prompt、gallery 和来源会作为创作参考保留。
5. Prompt Hub 只读导入，不会回写或覆盖 OC Manager 原数据。

## Anima 与 Krea 2 的区别

- `ANIMA`：适合英文 Booru/Danbooru 标签。SFW 项目会自动加入成人内容规避词；Adult 与 Explicit adult 不会固定加入 `nsfw`、`nude`。
- `KREA 2`：按创作意图和七槽位组织成连贯描述。若槽位是很长的标签堆叠，页面会提醒用本地模型润色。
- 两个版本来自同一个项目，但不会强行共用同一条成品 Prompt。

## LM Studio 辅助

1. 保持 LM Studio Local Server 开启。
2. 工作台会列出文本模型，`●` 表示已经加载；默认优先已加载模型以避免换模。
3. 写好中文想法并锁定不能变的槽位，点“整理未锁定槽位”。
4. 等待建议预览。确认内容后再点“确认应用”；点“取消”不会修改项目。
5. 在 24GB MacBook Air 上，当前常驻 Qwen3 14B 的七槽位整理约 60 秒；智能取材的本地候选约 1 秒内可见，模型扩展随后完成。日常手工编辑、资料检索和双 Profile 编译不依赖模型。

## Windows / ComfyUI 交付

1. 点“导出 Anima + Krea 2 JSON”。
2. JSON 同时包含项目语义、七槽位、参考资料、参数、实测备注和两个 Profile 输出。
3. 把文件复制到 Windows 后，在对应 ComfyUI 工作流中粘贴 `outputs.anima.positive/negative` 或 `outputs.krea2.positive/negative`。
4. 结果图路径、共享目录地址或链接可逐行记回“实测记录”，再保存为配方。

当前流程完成了标准生成包与手动交付。跨设备自动发送、启动指定 ComfyUI workflow 和结果图自动回传通过 5060 Ti 共享目录与 Worker 完成。

## 结果图复盘与下一轮改进

1. Windows/ComfyUI 出图后，把满意或有问题的 PNG、JPEG、WebP 拿回 Mac；单张不超过 25 MiB。
2. 在原创作项目的“结果图复盘”选择文件并点“导入结果图”。Prompt Hub 会保存本地原图与缩略图。
3. 24GB Mac 先在 LM Studio 卸载日常 Qwen3 14B，再只加载 `Qwen3.5-9B-Uncensored-HauhauCS-Aggressive`；建议 context 4096、parallel 1。
4. 回到页面，模型名左侧出现 `●` 表示已加载；点结果图下方“用本地模型复盘”。实测通常约 1 分钟，复杂图片可等待 1–3 分钟。
5. 先检查七槽位观察、优点、问题、下一轮建议，以及折叠区中的 Anima/Krea 2 反推 Prompt。
6. 点“只写入实测备注”不会改槽位；点“补充空槽位并写入备注”也只补空白且未锁定的槽位，已有内容与 `LOCKED` 内容都不会覆盖。
7. 如果要保留这一轮，点“由此创建下一版”。页面会切换到独立 V2/V3，保留槽位、锁定、参考和生成参数，但不复制旧结果图。
8. V2/V3 顶部会出现“本轮迭代对照”，展示上一版、当前版与复盘观察。若存在可用建议，可点“确认填入空槽位”；系统仍不会替换已有内容或 `LOCKED` 内容。
9. 根据对照继续手动调整，再保存为新配方或导出下一轮 JSON。复盘结束后可卸载视觉模型，重新加载 Qwen3 14B 做日常文字任务。

项目列表中 `V2/V3` 是实际创作轮次，`R2/R3` 只是该项目的保存次数。进入派生项目后，项目名下方会显示它来自哪个版本和哪张结果图，并可打开来源图回看。

版本对照读取的是父项目当前保存状态；如果历史 JSON 缺少父项目，页面会降级为只显示 lineage 中保存的复盘摘要和建议，不影响当前项目编辑。

结果图默认位于 `prompt-library/test-results/prompt-hub`。导入、查看、分析都走本机服务；当前不会自动发送到 Windows，也不会上传网络。

## 从结果图导出 LoRA 数据集

1. 在结果图卡片点“加入数据集”；按钮变成“已加入数据集”才表示入选。
2. 制作 Anima 数据集时，可在单张结果卡点“WD14 自动打标”，也可设置 general/character 阈值后点“打标全部精选”。同步批量一次最多 24 张。
3. 展开 WD14 草稿，检查 rating 与角色候选，删除错误、冲突、不可见或不希望训练的标签。rating 只用于审核，不会加入训练 caption。
4. 点“保存审核草稿”只保存编辑状态；点“确认用作 Anima caption”才会写入这张图的 Anima caption。Krea 2 自然语言不会被改写。
5. 在图库下方选择 `Anima tags` 或 `Krea 2 自然语言`。选择只决定这次导出的 caption 格式，不改变项目的出图 Profile。
6. 默认 caption 使用当前项目对应 Profile 的 Positive prompt。某张图需要单独修正时，也可展开普通 caption 编辑区保存；两个 Profile 的单图覆盖分开保存。
7. 点“导出精选数据集 ZIP”。包内 `dataset` 文件夹包含原图和同名 `.txt`，可直接复制到 Windows 继续筛选或训练；`manifest.json` 记录项目版本、分级、图片来源和 caption 来源。
8. 导出文件同时保存在 `$HOME/Documents/Codex/soda-person/prompt-library/exports/datasets`。移出精选不会删除原图，导出也不会重新编码图片。

当前流程仍不做自动挑图或 SSH 传输：WD14 只生成可审核草稿，入选图片和最终 caption 仍由你确认；完成后可以在数据集工作台复制交付版本，也可以手动处理 ZIP。

## 数据位置与备份

- 主数据库：`$HOME/Documents/Codex/soda-person/prompt-library/database/prompt-library.sqlite`
- V1 迁移前备份：`$HOME/Documents/Codex/soda-person/prompt-library/database/backups/prompt-library-pre-creative-v1-20260830.sqlite`
- 公共资料重建不会删除创作项目、配方、收藏、评分或备注。
- 结果图原图与缩略图：`$HOME/Documents/Codex/soda-person/prompt-library/test-results/prompt-hub`
- 精选数据集 ZIP：`$HOME/Documents/Codex/soda-person/prompt-library/exports/datasets`
