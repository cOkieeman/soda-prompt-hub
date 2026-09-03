# Mac 本机开发完成度审计

更新日期：2026-09-01

## 目标拆解与证据

| 明确要求 | 当前证据 | 判定 | 下一步 |
|---|---|---|---|
| 保持档案馆前端风格 | 创作、检索、数据集、LoRA、回流和设备页共用 paper/ink/signal/acid 设计变量；桌面与手机浏览器通过 | 已证明 | 后续 Windows 状态页继续复用 |
| 功能与使用逻辑简单 | 首页引导、任务式页面和 `MAC_OPERATIONS_GUIDE.md` 已覆盖四条日常流程 | 已证明 | 明天按手册实走跨设备流程 |
| Tag 中英文显示 | 全局“标签：中英 / TAGS: EN”覆盖资料、WD14 general/character、数据集统计与选择、智能检索、Windows LoRA；LoRA coverage 为中文 + 英文 ID；内部只保存英文 canonical | 已证明 | 长尾未收录翻译时诚实保留英文 |
| Anima 英文 canonical tags | 编译器、caption 标准化、冻结门和非 ASCII 拒绝测试存在 | 已证明 | 用用户真实训练集复验 |
| Krea 2 英文自然语言 | 独立 caption 树、草稿审核、快照和冻结目录存在 | 已证明 | 5060 Ti 批量 VLM 实测 |
| 本地资料 / OC / 创作闭环 | 33,631 条资料、OC JSON 只读导入、双 Profile、版本链与结果复盘完成 | 已证明 | 保持回归 |
| 数据集与 LoRA 准备 | 只读工作区、WD14 长队列、双 caption、覆盖矩阵、不可变冻结包完成；1,000/10,000 张隔离规模通过 | Mac 功能与规模已证明 | 用户真实 24+ LoRA 数据集做发布门 |
| ComfyUI 结果回流 | PNG workflow/参数解析、无 metadata 降级、SHA 去重、项目关联、候选/失败和版本分支完成 | Mac 功能完成 | 明天用真实 Windows PNG 与原 workflow 核对 |
| Windows 设备接口 | 单一 5060 Ti 生成/训练节点、SMB 诊断、五目录、任务投递、本地 ledger、状态扫描、returned 待审核、失败新 ID 重试、compute contract v2 与凭据拒绝完成 | Mac 接口完成 | 配置真实 SMB、worker、单卡调度、断线与幂等恢复 |
| ComfyUI LoRA 远程清单 | metadata snapshot API、不可变 snapshot、只读页面与混合检索分组完成；不复制权重 | Mac 接口完成 | Windows Worker 读取 LoRA Manager metadata、预览和 LoRA 目录 |
| 智能检索与视觉检索 | FTS + 可选真实向量混合召回、四分组、以图找图入口、来源和诚实空状态完成 | Mac 产品层完成 | 5060 Ti 生成真实 CLIP/SigLIP 索引与聚类 |
| Krea 2 VLM 草稿 | 本地可恢复队列、正式/草稿并列、人工确认快照、远程导入与 SHA 回验完成 | Mac 闭环已证明 | 5060 Ti 批量、暂停和恢复 |
| 备份与恢复 | SQLite online backup、SHA manifest、remote-nodes 清单、篡改拒绝、verify 与新目录恢复完成 | 已证明 | 跨设备配置后再做一份新基线 |
| 最终工程检查 | 单节点改造后 77 项测试、81.98% coverage、Ruff、ty、JavaScript、OpenAPI 87 路径通过 | 已证明 | Windows 接入后追加运行态与跨设备验收 |

## 当前结论

明天连接 Windows 前需要的 Mac 本机功能已经收口：它能独立管理事实数据、创作、检索、审核、
版本、结果回流、LoRA 准备、备份和诊断，也已经为统一的 5060 Ti 制图/炼丹节点留好受控接口。

完整跨设备绘图系统仍不能标记为最终发布。以下工作必须在真实 Windows 上完成：

- Finder/Keychain 挂载 5060 Ti SMB；
- 真实 ComfyUI PNG/workflow 回传；
- Windows Worker 对 LoRA Manager metadata、预览和 ComfyUI LoRA 目录的读取适配；
- 5–10 step LoRA smoke test 与 checkpoint 回传；
- 真实 CLIP/SigLIP embedding 和 Krea 2 批量 VLM worker；
- 单卡生成/训练互斥调度、SMB 断线、幂等重试、Windows 重启与跨设备恢复验收。

接口完成不等于远程计算已经发生；当前页面对缺失的真实索引和 LoRA snapshot 都保持明确空状态。
