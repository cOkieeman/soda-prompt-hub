# 画风与构图资料来源

本轮根据《ComfyUI 画风、构图与 LoRA 配置指南》筛选资料源，并于 2026-10-05 核对上游数据。
Prompt Hub 负责检索、收藏、记录和组织提示词；ComfyUI 节点在绘图设备端运行。

## 已接入的新增来源

| 来源 | 导入内容 | 模型与预览 |
| --- | --- | --- |
| [Krea2 Style Explorer](https://github.com/ThetaCursed/Krea2-Style-Explorer) | `app/data.js` 中的完整风格描述；本次验证 1,596 条 | 标记为 `krea2`，上游目标为 Krea 2 Turbo；关联本地 `images/<folder>/<id>.webp` |
| [Anima Style Explorer](https://github.com/ThetaCursed/Anima-Style-Explorer) | 画师标签索引 | `anima`；缺失预览时仍导入文字；历史图片按画师名匹配并注明版本 |
| [Illustrious / NoobAI Style Explorer](https://github.com/ThetaCursed/Illustrious-NoobAI-Style-Explorer) | 画师标签索引 | `illustrious-noobai`；仅关联实际存在的本地 WebP |
| [Neons Style Explorer](https://github.com/Neon-Sparks/ComfyUI-NeonsStyleExplorer) | `styles/*.json` 中的自然语言描述、负面描述、标签、别名与轴分类；本次验证 1,419 条 | 模型兼容性未验证，不指定模型；上游不附带风格预览图 |

Krea2 Style Explorer 和已有的 Krea Open Prompts 是独立来源。前者提供 Krea 2 Turbo 风格描述，
后者提供通用修饰词和预设，不能因为名字相近就认为它们的数据或模型相同。

Neons 的 `style` 作为画风条目，`format` 作为构图修饰词，`finish` 作为质感修饰词。
自然语言保存在正文，负面描述保存在负面提示词字段，Danbooru 标签及别名保留在 metadata 中，
不会自动把两种语法混进同一个 Prompt。`10_other.json` / `Extra` 中重复收录的 Krea2 内容跳过。
这只使用上游数据文件，不执行上游 Python 或 JavaScript，也不安装 ComfyUI 插件依赖。

新增来源均沿用上游稳定 ID，因此条目重排后收藏、评分和备注仍对应原条目。
Git 来源链接包含导入时的 commit。只读本地映射记录目录文本的 SHA-256，不伪造 Git 版本链接。没有内容分级信息的条目标记为 `unrated`，
在“全部分级”下可见，不自动归为“普通”。Neons 的模型兼容性须在实际工作流中测试。

## 在工作台使用

1. 使用包含本次改动的 Core，打开“提示词库”上方的资料来源更新区域。
2. 找到 **Krea2 Style Explorer** 或 **Neons Style Explorer**，分别点击“拉取”。
3. 拉取结束后自动建立索引，在来源筛选中选择对应资料库。
4. 搜索并收藏条目。Krea2 本地预览文件存在时可用“只看带图”；Neons 没有预览，查看它时需关闭此筛选。
5. 后续使用“检查并更新”同步上游，或在来源数据已准备好时重建索引。

Krea2 图库包含较多 WebP 图片，首次拉取需要网络和磁盘空间；应用首次资料库安装操作也会包含新增来源。
来源文件损坏、格式不支持、重复 ID 或已索引来源扫描为空时，会报告失败并保留该来源原有索引。
缺失的 Krea2 图片不生成空预览卡；媒体接口仍限制目录和格式，并拒绝越界路径。

## 指南中其他仓库的用途

| 仓库或资源 | 本轮判断 |
| --- | --- |
| [AnimaDex](https://github.com/zetaneko/AnimaDex) | 已有角色、画师和作品导入器，继续使用，避免重复接入 |
| Anima Style Explorer | 已接入。当前预览已拆到独立资产库，可复用准备好的本地离线目录 |
| Illustrious-NoobAI Style Explorer | 已作为独立模型资料源接入 |
| [BooruTagCart](https://github.com/xhoxye/BooruTagCart) | 中文标签词典值得后续评估；现有标签补全已有相似能力，先核对重复、翻译来源和代码／数据许可证 |
| [ComfyUI LoRA Manager](https://github.com/willmiao/ComfyUI-Lora-Manager) | 适合绘图设备上的 LoRA 预览与元数据管理；Prompt Hub 已有底模／LoRA 只读目录，后续可评估元数据互通 |
| [XY KSampler Plot](https://github.com/Ynead/xy_ksampler_plot) | 适合设备端权重对比；须先验证模型、采样器和节点兼容，再考虑接成 Workflow Profile |
| [rgthree-comfy](https://github.com/rgthree/rgthree-comfy)、[ComfyUI Manager](https://github.com/ltdrdata/ComfyUI-Manager) | 设备端工作流整理与插件管理工具，不是提示词数据源 |
| [anima-t8](https://github.com/T8mars/comfyui-anima-t8)、[anima-style-nodes](https://github.com/fulletLab/comfyui-anima-style-nodes)、[Anima-Tools](https://github.com/nregret/Comfyui-Anima-Tools)、[Anima Artist Mixer](https://github.com/An1X3R/Anima-Artist-Mixer) | 先在 Anima 工作流中按需选用，避免同时引入多个重叠面板；本轮未验证节点运行 |
| FilmGrab、ShotDeck、PureRef、Eagle 等 | 作为构图参考或素材管理入口使用，本轮不批量采集图片 |

## 验证与边界

- Krea2 数据核对版本：`eb690aa57bc6974af6b4b3b8c5a780195bcadf78`。
- Neons 数据核对版本：`00525c6c1dcebae042cf50504780f20c2f2e2e90`。
- 真实文本目录解析得到 3,015 条唯一来源内 ID 的记录；测试库另验证搜索、收藏、重建和本地预览。
- 公共仓库仍由用户按需拉取。上述数量只代表核对版本，上游更新后可能变化。
- 代码／目录许可按上游 MIT 及 Neons `THIRD-PARTY-NOTICES.md` 保留；预览图、后续模型及 LoRA 的使用条件仍需分别核实。
- 未生成图片，未验证 GPU、ControlNet、LoRA 权重或实际模型的画风表现。

## 复用已有本地图库

Mac 体验验收版可在“设置 → 资料管理”中操作：

1. 在对应资料库旁点“使用已有文件夹”或“更换目录”。
2. 填写当前电脑能访问的绝对目录；Mac 共享目录须先挂载。
3. 保存映射，再点“刷新本地资料”建立索引。保存路径本身不会下载或重建资料。

这个入口支持下列九个已适配来源，不会把任意图片文件夹当成提示词库。
AnimaDex 的外部资料目录可在同一表单设置。
全部使用本地映射时，隐藏全局联网更新按钮；每个来源仍可查看路径和原始来源。

配置仍保存在资料库的 `sources/local-sources.json` 中，也可手动设置来源绝对路径：

```json
{
  "format": "soda-local-sources-v1",
  "sources": {
    "anima-style-explorer": {"path": "E:\\个人开发项目\\画风库\\repositories\\Anima-Style-Explorer"},
    "krea2-style-explorer": {"path": "E:\\个人开发项目\\画风库\\repositories\\Krea2-Style-Explorer"}
  }
}
```

全部九个内置来源都支持这种映射。AnimaDex 的条目还可指定绝对 `data_path` 指向包含 `import/characters.csv`、`import/artists.csv` 和缩略图的外部资料目录。映射目录可以没有 `.git`；程序读取目录数据并建立自己的索引，
不复制完整图片，不执行第三方代码，不运行 Git fetch、merge 或 clone。点击刷新仅重建索引。
目录断开、配置无效时报告错误并保留原有索引，不会自动重新下载。Mac 须使用已挂载共享的绝对路径，
例如 `/Volumes/PromptHub-5060Ti/Public-Style-Libraries/repositories/Anima-Style-Explorer`。

可选历史预览仍使用 `sources/style-explorers.json` 的 `soda-style-explorers-v1` 配置：
`libraries` 以来源 ID 为键，包含历史目录的绝对 `path` 和完整 40 位 Git `revision`。
配置损坏只关闭历史预览；当前来源导入不受影响。历史预览按正文匹配，不按可被重复使用的数字 ID 匹配。
图片分区字段缺失只影响预览；有效文字仍会保留。

### GitHub URL 与本地映射共存

资料管理里的每个预设资料库都可通过“选择来源”切换读取方式。选择 GitHub URL 后，下载与更新只操作 Hub 管理的仓库目录；选择本地映射后，按用户填写的绝对路径只读建立索引。两种目录和上次填写的映射路径都会保留，切换设置不会自动下载、删除文件或重建索引。保存后按所选方式点击下载、检查更新或刷新本地资料。旧映射配置未填写 mode 时仍按本地映射读取。
