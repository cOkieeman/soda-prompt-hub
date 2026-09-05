# Soda Prompt Hub 个人版 1.0 完成度审计

更新日期：2026-09-05

## 结论

按当前产品边界，绘图与数据集主线已经完整，可以进入功能冻结和日常使用阶段。Prompt Hub 的终点
是从灵感与资料出发，完成远程出图、结果回流、数据集审核和带哈希的交付包；Windows 训练、正则、
最终标签筛选和 LoRA 测试继续由现有工具完成，不属于缺失功能。

## 完成范围

| 能力 | 当前证据 | 判定 |
|---|---|---|
| 创作与 Prompt | 七槽位、OC、视觉参考、Anima/Krea 2 双 Profile、配方与版本链 | 完成 |
| 本地资料 | 33,633 条资料、6 个来源、网页来源卡与个人收藏/评分/备注 | 完成 |
| 视觉检索 | 1,450 张真实 CLIP 索引、上传查相似图、跨来源结果与视觉簇 | 完成 |
| 5060 Ti 出图 | Workflow Profile、模型/LoRA/参数绑定、Worker、结果哈希验收与回流 | 完成 |
| LoRA 与底模浏览 | 只读分类树、预览图、Civitai 来源、创作台安全选择 | 完成 |
| 数据集交付 | 扫描、重复检查、WD14、双 Caption、人工审核、冻结与 Windows 复制 | 完成 |
| 稳定性 | 任务恢复、导出失败清理、SMB 离线恢复、备份与隔离恢复 | 完成 |
| 模型辅助 | LM Studio 本地优先，可选 OpenAI-compatible 外部模型且密钥不回显 | 完成 |

## 明确不纳入个人版 1.0

- 自动启动 AnimaLoraStudio 训练、正则或 checkpoint 管理；
- Prompt Hub 内完成 LoRA 训练与最终测试；
- Windows 批量 Embedding/VLM 加速；
- MiniMax H3 视频项目；
- Anthropic、Gemini 等厂商原生协议。

这些项目只有在真实使用证明有必要时才单独立项，不阻塞个人版 1.0。

## 发布收尾状态

- 软件包版本和页面名称已统一为 Soda Prompt Hub `1.0.0`；
- README 已区分作者的 `soda-person` 默认路径与其他用户的自定义资料目录；
- `CHANGELOG.md` 与 GitHub Actions 自动检查已加入候选版本；
- 自动检查、构建和浏览器结果见 `FINAL_TEST_REPORT.md`；
- LICENSE 已由仓库所有者确认为 MIT；commit、push、tag 与 GitHub Release 等待用户另行确认。

因此当前状态是：**功能和本地发布收口完成，等待 Git 发布动作确认。**
