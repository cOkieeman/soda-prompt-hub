# Soda Prompt Hub 用户指南

用户文档已经按使用目的重新分层。这个文件作为旧链接的兼容入口保留：

- 下载和第一次安装：[两种使用方式快速开始](docs/QUICK_START.md)
- 绘图、结果回流和数据集：[核心工作流](docs/WORKFLOWS.md)
- 启动、备份、恢复和更新：[Mac 使用与维护](docs/MAC_GUIDE.md)
- Windows 单机：[Desktop安装](docs/QUICK_START.md#windows-单机第一次安装)，不另开独立Worker
- Mac管理Windows的执行端：[Windows Worker 完整指南](docs/WINDOWS_WORKER.md)
- 单机与双机的数据位置：[设备与文件关系](docs/ARCHITECTURE.md)
- 新包手动验收：[两模式验收清单](docs/acceptance/manual-1.1.0-20260913.md)
- 常见错误：[常见问题与排错](docs/TROUBLESHOOTING.md)

如果只想快速开始，先读第一份；不需要从头读完全部文档。

## 分镜模块

主导航的“分镜”把故事拆格、网页编辑、MOSS 编译和 Worker 出图放在同一处。项目直接使用
`soda_storyboard` 的项目、页面和角色卡格式；分镜包可以在 Hub、soda-storyboard 插件和
[ComfyUI 分镜节点](https://github.com/cOkieeman/ComfyUI-Soda-Storyboard)之间交换。
完整的版式、角色卡、编辑器和后期用法见核心库的
[0.4.1 使用说明](https://github.com/cOkieeman/soda-storyboard/blob/v0.4.1/docs/guide/README.md)，
交换格式见[分镜包 API](https://github.com/cOkieeman/soda-storyboard/blob/v0.4.1/docs/bundle-api.md)。

### 从故事开始

1. 新建分镜项目，再添加空白页；也可以选择 JSON、Markdown 或文本文件导入为新项目。
   导入支持分镜包、分镜单和 MOSS JSON，原文件保持不变。检查导入报告中的推断和提醒。
2. 如果使用已有 OC，展开“用 OC 生成分镜角色卡”，核对中英文外观、服装款式和颜色，预览后确认保存。
   LoRA 可留空；整页遵守项目的 `lora_policy`，最多使用一个 LoRA，其他角色按文字外观出图。
3. 选择页面，在“AI 拆格”里填写故事、模型和建议格数，先检查方案，再点击“确认写入分镜页”。
   预览不会写进项目，确认会保护已有内容；需要另一版时先新建空白页。
   模型选项来自“设备连接 → 模型服务”中已启用的连接，故事和角色上下文会发送到所选服务。
4. 点击“打开网页编辑器”，在新窗口调整格子、姿势和台词。编辑器随核心 wheel 提供，首次打开可能需要
   允许浏览器弹出窗口。看到“已保存”后回到 Hub，点击“重新读取页面”。编辑器按项目启动，
   可手动停止；Hub 正常退出时会清理它启动的编辑器进程。
5. 校验页面，检查英文翻译清单。AI 英文译文同样先预览，确认后才应用；只翻译场景、动作和道具，
   台词保留原文。修改中文后重新检查过期译文，再编译并预览 MOSS JSON。

项目保存在 Hub 个人资料目录的 `storyboards/projects/` 中，分镜文件沿用核心库格式；删除项目会移入
同级的 `storyboards/trash/` 回收站。
不要同时在插件和 Hub 中确认同一页的修改；若提示版本冲突，重新读取后检查最新内容。

### 出图与结果复盘

在页面的“交给 Worker 出图”选择设备、质量和种子。默认使用核心库的 `minimal` 图，无需先导入自定义工作流；
目标 ComfyUI 仍需具备 MOSS 模型、文本编码器、VAE 和相关节点。按目标设备实际模型文件名填写覆盖项。

使用 Soda-MOSS-v2 时，展开分镜页的“可选：登记 Soda-MOSS-v2 API 工作流”，上传导出的 **API 工作流**；
已有配置需要更换时，明确勾选“替换已登记的工作流”。登记只保存工作流，不会发送生成任务。
导出 API 前把原工作流切到“JSON 直通”。
关键节点映射为：JSON 620、尺寸 150、种子 84、存图 81、负面 75、模型子图 135、采样子图 148。

投递会复用 Hub 的 `comfyui_generate` Worker 通道。完成后点击“回收任务结果”，在出图页复盘，
再从分镜候选图中点击“选为本页成图”。选图会把候选登记并写回页面 `production`；普通复盘与分镜选图各有
明确操作，不会因为 AI 建议自动选图。需要交给插件或节点继续处理时，先选页面，再导出该页分镜包；
多页项目逐页导出，每个包包含该页引用的角色与项目设置。

### 开发环境与离线安装

Hub 的依赖固定为核心库 **0.4.1** 的
[Release wheel](https://github.com/cOkieeman/soda-storyboard/releases/download/v0.4.1/soda_storyboard-0.4.1-py3-none-any.whl)。
联网开发环境照常 `uv sync`。离线环境可把已下载的同版本 wheel 安装进 Hub 的 `.venv`，临时替代网络下载：

```powershell
uv pip install --python .venv/Scripts/python.exe --offline --no-deps ./offline-wheels/soda_storyboard-0.4.1-py3-none-any.whl
uv run --no-sync prompt-hub serve --host 127.0.0.1 --port 8765
```

也可使用 `uv pip install --python .venv/Scripts/python.exe --no-deps "<核心库本地目录>"` 临时验证本地源码；
这可能使用尚未发布的版本，不能替代发布前对 0.4.1 wheel 的验收。离线安装只影响开发环境，
不要把本机路径写入依赖配置；检查时使用 `uv run --no-sync ruff ...`、`uv run --no-sync ty check src/`
和 `uv run --no-sync pytest`，避免重新联网解析依赖。
