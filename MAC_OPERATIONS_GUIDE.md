# Prompt Hub · Mac 日常操作手册

这台 MacBook Air 是整个绘图工作流的中枢：项目、提示词、OC、审核结果、caption 版本、索引、任务状态和备份都以 Mac 为准。5060 Ti 统一负责可以重做的制图与训练计算，不保存唯一事实。

## 现在已经是什么状态

| 设备 | 负责什么 | 当前状态 |
|---|---|---|
| MacBook Air | 创作、资料检索、数据集审核、WD14、LoRA 项目、结果回流、版本和备份 | 可独立使用 |
| 5060 Ti Windows | ComfyUI 出图、LoRA Manager 插件管理、AnimaLoraStudio 训练、批量 Krea 2 caption、CLIP/SigLIP embedding | ComfyUI 出图已接通；其他适配器待开发 |

即使 5060 Ti 关机，Mac 上已经保存的资料、项目、caption、索引和结果仍然可读。当前没有真实 CLIP/SigLIP 索引时，“以图找图”会明确显示等待，不会制造假相似结果。

## 每天怎么启动和关闭

启动：双击 `$HOME/Documents/Codex/soda-person/启动-Prompt-Hub.command`。

页面地址：<http://127.0.0.1:8765/>。

关闭：双击 `$HOME/Documents/Codex/soda-person/停止-Prompt-Hub.command`。不要直接强制退出正在显示“扫描中”“打标中”或“生成草稿中”的任务；先在页面点取消，等状态停止后再关闭。

如果页面打不开，先双击 `$HOME/Documents/Codex/soda-person/诊断-Prompt-Hub.command`。它会检查数据库、embedding 索引、WD14、磁盘空间和 8765 服务。

## 一次绘图创作

1. 打开“创作台”，新建项目或继续旧项目。
2. 写一句中文创作想法，先锁定绝不能改变的角色特征。
3. 点“从本地库智能取材”，从有真实来源的提示词与视觉参照中选择内容。
4. 分别检查角色、服装、动作、构图、场景、灯光、画风七个槽位。
5. 切换 `ANIMA` 与 `KREA 2`：Anima 输出英文 canonical tags，Krea 2 输出英文自然语言，两份内容互不覆盖。
6. 保存项目与配方。Windows 尚未接通时，先导出 Anima + Krea 2 JSON，再手工交给 ComfyUI。
7. 出图回来后进入“结果回流”或创作台“结果图复盘”，核对参数、关联项目，再决定加入数据集、记录失败或建立下一版。

本地模型只负责建议。槽位整理、视觉复盘、WD14 与 Krea 2 VLM 的结果都先进入预览或草稿，确认后才成为正式数据。

## 一次数据集审核

1. 把待整理图片放在一个独立文件夹中；已有同名 `.txt` 可以保留。
2. 打开“数据集”，填写这个文件夹的绝对路径，点“读取并建立工作区”。Prompt Hub 只读扫描，不改原图片和原 `.txt`。
3. 先看坏图、缺 caption、完全重复、近似重复和尺寸统计。
4. 用筛选器缩小范围，再选择图片。页面每次最多渲染 200 张；“选择当前筛选结果”仍会选择全部筛选结果，不只是当前页。
5. 如果目录已经有同名 `.txt`，先用“接续原始 .txt Caption”选择 Anima 或 Krea 2，预览后一次确认；默认只填空白 Profile，并保留一个整批快照。
6. 没有旧标签时，Anima 可运行 WD14 后人工删改；Krea 2 把视觉模型结果保存在草稿栏，人工确认后再写入正式 caption。
7. 将图片标记为“保留 / 待复查 / 排除”，检查标签频率、冲突提示和覆盖偏差。
8. 选择 Anima 或 Krea 2 Profile，导出不可变版本包。

原目录始终是只读来源。移除工作区只移除 Prompt Hub 的派生记录，不会删除源图片。

## 一次 LoRA 训练

Mac 负责把训练要求说清楚并冻结数据，5060 Ti 负责真正训练。

1. 在“LoRA 项目”建立 `character`、`outfit`、`character_outfit` 或 `style` 项目。
2. 固定 Trigger，填写固定特征、可控特征、允许变化和禁止漂移。
3. 从已经审核的数据集引用图片，先点“预览自动初审”；核对后确认加入，再逐图修正景别、视角、姿态、表情、服装、背景、光线和构图。
4. 分别审核 Anima 与 Krea 2 caption；二者都必须是英文，并包含 Trigger。
5. 检查重复、构图偏置、背景偏置、角色不一致与服装污染。
6. 点“生成新冻结版本”。冻结包生成后不再修改；如需调整，建立下一个版本。
7. 把冻结版本交给 5060 Ti 的 AnimaLoraStudio，先做 5–10 step smoke test，确认 CUDA、Torch、训练器、底模路径和显存，再开始正式训练。
8. Windows 回传 checkpoint、测试图、metrics、实际配置和 run log；Mac 将它们关联到原 LoRA run，再决定是否保留。

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
9. 先勾选“低成本测试”投递一张基础图，观察等待领取 → 执行中 → 结果待审核；失败时只用页面“重新投递”。
10. 回传后在任务卡点“验收并导入图片”；通过 SHA-256 后，图片进入 Mac 结果库并自动关联原创作项目。
11. 基础图正确后关闭低成本模式，再验证脸手精修与放大版本，并与原 workflow 人工核对。
12. 在“设备连接”点“从 Windows 同步”；任务返回后点“验收并导入 LoRA 清单”。Mac 会保存文件名、metadata 与经 SHA-256 校验的预览图缓存，卡片可点开查看全部参照图；不会读取或复制 `.safetensors` 权重。
13. 用一个小冻结包做 5–10 step LoRA smoke test。
14. 最后接 `embedding_batch` 与 `vlm_caption_batch`，测试断线、恢复、重复投递和哈希不匹配拒绝。

不要在“设备连接”页面填写 Windows 密码。Prompt Hub 只保存地址、角色和 Mac 挂载路径，密码只交给 Finder / macOS 钥匙串。

## 备份、验证与恢复

重要修改前后双击 `$HOME/Documents/Codex/soda-person/备份-Prompt-Hub.command`。备份包含数据库、embedding 索引、个人资料、结果图、导出版本、数据集工作区、LoRA 项目、Workflow Profile 与设备登记；公共 Git 资料、可重新同步的 LoRA 预览缓存、缩略图与模型权重不重复备份。

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

## 哪些事情现在仍要等 Windows

- 5060 Ti 自动接收 ComfyUI 任务并回传完整结果；
- 5060 Ti 真实 LoRA smoke test 与正式训练；
- Windows Worker 对 LoRA Manager metadata、预览和 ComfyUI LoRA 目录的真实读取适配；
- 真实 CLIP/SigLIP embedding、以图找图与视觉聚类内容；
- 5060 Ti 批量 Krea 2 VLM caption；
- SMB 断线恢复、幂等投递与跨设备最终验收。

这些缺口不影响 Mac 独立完成创作、资料检索、数据集审核、WD14、LoRA 项目准备、结果导入和备份恢复。
