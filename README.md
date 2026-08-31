# Soda Prompt Hub

本机优先的 AI 绘图提示词、风格、标签、wildcard 与视觉参照检索中枢。服务只监听
`127.0.0.1`，资料与索引默认保存在：

`/Users/soda/Documents/Codex/soda-person/prompt-library`

## 日常使用

最简单的方式是双击：

`/Users/soda/Documents/Codex/soda-person/启动-Prompt-Hub.command`

浏览器会打开 <http://127.0.0.1:8765>。关闭终端窗口或按 `Control-C` 即可停止。

绘图 V1 的最短操作顺序见 [DRAWING_V1_GUIDE.md](DRAWING_V1_GUIDE.md)。首页点“新建或继续绘图项目”
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

也可以在终端中启动：

```bash
cd /Users/soda/Documents/Codex/soda-person/projects/prompt-hub
/opt/homebrew/bin/uv run prompt-hub serve --host 127.0.0.1 --port 8765
```

## 更新公共资料

双击：

`/Users/soda/Documents/Codex/soda-person/更新-Prompt-资料库.command`

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
cd /Users/soda/Documents/Codex/soda-person/projects/prompt-hub
/opt/homebrew/bin/uv run prompt-hub stats
/opt/homebrew/bin/uv run prompt-hub search "gothic cathedral" --limit 10
/opt/homebrew/bin/uv run prompt-hub import
```

## WD14 本地图片打标

已安装 `SmilingWolf/wd-swinv2-tagger-v3`，模型位置：

`/Users/soda/Documents/Codex/soda-person/models/wd14/wd-swinv2-tagger-v3`

网页结果图工作台已经接入单图与精选批量打标；也可以用命令独立检查任意图片：

```bash
cd /Users/soda/Documents/Codex/soda-person/projects/prompt-hub
/opt/homebrew/bin/uv run prompt-hub tag-image /绝对路径/图片.png --limit 50
```

命令默认使用 general threshold `0.35`、character threshold `0.85`，只把 JSON 输出到终端，
不会创建或覆盖 `.txt`。本机实测 CoreML 无法完整执行这只 SwinV2 ONNX，所以 `auto` 默认使用
CPU；单张 1024×1536 图片首次加载加推理约 0.7 秒。

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
cd /Users/soda/Documents/Codex/soda-person/projects/prompt-hub
/opt/homebrew/bin/uv run ruff check .
/opt/homebrew/bin/uv run ty check src/
/opt/homebrew/bin/uv run pytest
```
