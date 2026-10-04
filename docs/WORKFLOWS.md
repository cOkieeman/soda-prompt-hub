# 核心工作流

以下操作在运行WebUI服务的设备完成：Windows单机保存在Windows，Mac双机模式保存在Mac。
安装和两套下载入口见[快速开始](QUICK_START.md)。

## 场景一：从灵感到一张图

1. 在“创作台”新建项目，写一句中文想法或从 OC Manager 角色开始。
2. 用七个槽位整理角色、服装、动作、构图、场景、灯光和画风；先锁定不能改变的内容。
3. 点“从本地库智能取材”，只选择有真实来源的提示词与视觉参考。
4. 检查 Anima 与 Krea 2 两种输出。Anima 使用英文 canonical tags，Krea 2 使用英文自然语言。
5. 选择 Workflow Profile、底模、LoRA、尺寸、Steps、CFG、Sampler、Scheduler 和 Seed。
6. Windows 在线时发送给 ComfyUI；Windows 离线时导出 JSON，稍后手工使用。

需要模型帮助时，先在“设备连接 → 模型服务”配置URL、Key和模型，再点“AI补全”。
等待建议返回、检查内容后才“确认应用”；不自动覆盖锁定项，失败看提示而不是重复提交。外部API可能计费。

## 场景二：Windows 出图与结果回流

两种启动顺序：

```text
Windows单机：ComfyUI → Soda Prompt Hub（自动管理Core/Worker）→ 检查本机状态 → 投递
Mac管理Windows：Windows ComfyUI + 独立Worker → Mac Prompt Hub → 检查共享/实时心跳 → 投递
```

1. 先用低成本测试确认 workflow 能运行。
2. 任务卡依次显示等待领取、执行中、结果待接收、已完成或失败。
3. Worker 返回后，在任务卡点接收。运行WebUI的管理端会核对任务编号、大小和 SHA-256。
4. 图片进入结果库后，再关联项目、记录失败、建立下一版或加入数据集。

`inbox` 中出现文件不等于已经导入；只有管理端校验通过后才进入正式记录。

## 场景三：从结果图到打好标的数据集

1. 在结果图中手动勾选满意图片“加入数据集”。
2. 从项目总览点“送入数据集工作区”。
3. 检查坏图、完全重复、近似重复和已有 `.txt`。
4. Anima 使用 WD14 生成标签草稿；Krea 2 使用视觉模型生成自然语言草稿。
5. 人工核对 Caption，并标记保留、待复查或排除。
6. 运行正式交付前检查。
7. 冻结为独立版本，得到图片、同名 `.txt`、`manifest.json`、`audit.json` 和 `hashes.sha256`。
8. Windows单机直接打开本地文件夹或下载ZIP；Mac双机模式可另复制到已挂载的Windows共享目录。

这里是Prompt Hub的交付终点。标签终筛、正则和训练在Windows的AnimaLoraStudio等工具中继续，不自动开始训练。

## 场景四：整理已有数据集

1. 在“数据集”填写图片文件夹的绝对路径。
2. Prompt Hub 只读扫描，不移动、不改名、不覆盖图片和原 `.txt`。
3. 按“检查问题 → 准备标签 → 人工审核 → 冻结交付”继续。
4. 移除工作区只删除 Prompt Hub 的派生记录，不删除源目录。

## 场景五：建立 LoRA 数据准备项目

1. 选择 `character`、`outfit`、`character_outfit` 或 `style`。
2. 固定 Trigger，说明固定特征、可控特征、允许变化和禁止漂移。
3. 从已审核的数据集引用图片，并检查角度、姿态、表情、服装、背景和构图覆盖。
4. 分别审核 Anima 与 Krea 2 Caption。
5. 生成新的冻结版本，在Windows本地使用或从Mac交付给Windows。

Prompt Hub 不自动运行正式训练，也不管理 CUDA、Torch 或训练器进程。

## 场景六：同步 Windows 的 LoRA 和底模

1. 保持 Windows ComfyUI 与 Worker 运行。
2. 在“设备连接”切换到 LoRA 或底模子页面，点“更新清单”，观察任务阶段与失败原因。
3. 任务返回后，在“任务状态”验收并导入。
4. 管理端保存名称、分类、相对路径、metadata、Civitai 来源和经校验的预览图。

权重仍留在 Windows，不会复制 `.safetensors`、Checkpoint、UNet 或 VAE 到 Mac。

## 场景七：Windows 关机时继续工作

仍可在 Mac 查资料、写 Prompt、导入 OC、复盘既有结果、整理数据集、运行 WD14、冻结交付版本。
远程出图、刷新 Windows 模型清单和把交付包复制到共享盘，需要等 Windows 再次开机。

## 场景八：拉取画风图库

Prompt Hub 内置 Krea2、Anima 和 Illustrious / NoobAI Style Explorer 的 GitHub URL，与原有五个来源共用拉取和更新入口。首次使用在首页或资料管理点击“拉取”，已有仓库使用“检查并更新”。三套仓库保存到资料目录的 `sources/git`，拉取后自动重建索引，可使用来源筛选、检索、本地预览、收藏、备注和“加入创作”。无需额外配置文件即可拉取。

若远端图片缺失，可选地在 `sources/style-explorers.json` 登记历史图片备份。配置格式为 `soda-style-explorers-v1`，`libraries` 可包含 `krea2-style-explorer`、`anima-style-explorer`、`illustrious-style-explorer`。每项的 `path` 是备份绝对路径，`revision` 是完整 40 位 Git revision。目录需包含 `app/data.js` 和 `images`。该配置只提供备用预览，不改变 GitHub 来源及其拉取目录。

预览优先使用当前 Git 仓库的图片，缺失时按画风提示词或画师名称精确匹配历史备份，不按可能变化的条目 ID 错配图片。使用历史预览时来源说明会提示版本限制，条目 metadata 记录图片版本。备份不参与 Git 更新，也不会被覆盖；个人收藏仍保存在 Hub 的资料目录。

导入器只解析 `const galleryData = [...]` 的 JSON 数据，不执行第三方 JavaScript。图片通过现有受路径和扩展名限制的 `/media` 接口读取；缺失的图片不会生成虚假的预览链接。图片未有明确分级时记为“尚未分级”。

Krea2 保留自然语言画风描述，Anima 和 Illustrious 保留原有画师文字；不同底模的画风效果需分别测试。仓库拉取不保证仓库之外的 CDN 图片或完整数据集也可用；AnimaDex 完整导出和 Krea 完整 CSV 仍属于单独的数据下载。
