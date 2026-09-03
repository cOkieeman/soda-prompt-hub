# Prompt Hub · Mac 端最终验收报告

更新日期：2026-09-02
范围：Mac 本机绘图中枢、M1–M5、M7 Mac 产品层、M8 Mac 备份，以及 V2.2 单一 5060 Ti 节点改造；不包含尚未接入的 Windows 真实执行环境。

## 结论

Mac 端已改为“只连接一台 5060 Ti”的结构。正式服务运行于
<http://127.0.0.1:8765/>；创作、资料与视觉参照、OC、数据集、WD14、双 caption、LoRA 项目、
ComfyUI 结果回流、智能检索、设备登记、备份恢复和诊断均可在 Mac 独立使用。

本次收口完成了全页面 Tag 语言闭环、Mac 侧共享任务投递、状态 ledger 与失败重试；2026-09-02 又将生成与训练角色合并为协议 v2 的 `compute_5060ti`。

完整跨设备系统仍需真实 Windows SMB、worker 与训练验收，不能把接口预留写成远程功能已经完成。

## 自动验证

| 检查 | 新鲜结果 |
|---|---|
| pytest | 77 / 77 通过 |
| coverage | 81.98%，高于 80% 门槛 |
| Ruff format | 81 个文件均已格式化 |
| Ruff lint | 通过；`search_web.py` 仅使用与其他内嵌页面相同的 E501/RUF001 精确例外 |
| ty | `src/` 与 `tests/` 通过 |
| 整页 JavaScript `node --check` | 通过 |
| `git diff --check` | 通过 |
| OpenAPI | 87 条路径；新增 Tag catalog、remote task list/detail/submit/retry，既有 Windows LoRA、embedding 与 compute contract 路径齐全 |
| 主 SQLite | `integrity_check=ok` |
| Embedding SQLite | `integrity_check=ok`，当前 0 个真实索引 |
| 敏感信息扫描 | 未发现私钥、GitHub token、OpenAI key、Google API key 或 `.env` 文件 |

## 10,000 张数据集规模验收

- 隔离目录分别扫描 1,000 与 10,000 张有效 WebP；SHA-256、pHash 与完全重复组结果正确。
- 扫描报告约 494 KiB / 4.8 MiB；相同 SHA-256 只保存一份缩略图。
- 10,000 张页面固定为 50 页，每页最多渲染 200 张卡片。
- 第 1 页首图 `image-00001.webp`；点击下一页后为 `image-00201.webp`，第 4 页为 `image-00601.webp`。
- “选择当前筛选结果”显示 10,000 张，同时 DOM 仍只有 200 张；清空后恢复 0 张。
- 1280px 桌面 `scrollWidth=1280`；390×844 手机单列宽 322px、`scrollWidth=390`。
- 两种视口控制台均为 0 warning/error。隔离夹具已移到
  `/Users/soda/.Trash/prompt-hub-scale-qa-20260901`。

## 智能检索与设备接口验收

- 正式库查询 `gothic` 显示四个固定分组、24 条提示词资料与 5 条视觉参考，共 29 张结果卡。
- 当前无真实 embedding 时明确显示“等待真实视觉索引”，不使用随机向量、颜色特征或伪结果。
- 数据集“以此图查相似”只有在源 SHA-256 已进入真实索引时启用。
- 设备页只显示一张“5060 Ti · 制图与炼丹节点”卡片；同一节点可接收 ComfyUI、LoRA、Embedding、VLM 与 LoRA 清单任务。
- remote node payload 禁止额外 password 字段；Prompt Hub 只保存地址、角色和 Mac SMB 挂载路径。
- Mac 任务投递测试证明 outbox 原子文件与本地事实副本同时存在；failed 任务重试会创建新 task ID、attempt 2 与 `retry_of`，旧失败文件保持不变。
- task payload 会拒绝 credential/password/token，角色或 capability 不匹配也会拒绝。
- 1280px 任务列表为三列、页面滚动宽 1280px；390px 手机端节点和任务列表均为单列、页面滚动宽 390px；正式浏览器控制台 0 warning/error。

## Tag 语言与英文输出验收

- 全局按钮明确为“标签：中英 / TAGS: EN”；未收录的长尾 tag 保留英文，不伪造中文翻译。
- 正式资料卡实测 `黄色夹克 (yellow jacket)` 切换为 `yellow jacket`；中英模式显示“标准英文输出”，英文模式取消该前缀。
- 数据集批量编辑支持已知中文别名，测试中的“白发 / 一名女孩”在预览、快照与 caption 中转换为 `white_hair / 1girl`，输出全部 ASCII。
- 数据集中文候选 catalog 为 86 项；未知中文会返回明确错误，高级英文自定义 tag 仍可使用。
- WD14 character candidates、智能检索和 Windows LoRA metadata tags 均接全局切换；Trigger、底模、路径、checkpoint 等技术元数据保持原样。
- LoRA coverage 显示“中文（英文 ID）”，项目 JSON 保存英文 ID；偏置警告不再出现 `undefined`。

## 备份、恢复与诊断

最终基线：

`/Users/soda/Documents/Codex/soda-person/backups/prompt-hub/mac-pre-windows-final-20260901`

- manifest 明确包含 database、embedding、private、imports/web/api、test-results、dataset workspace、
  LoRA projects、exports 与 remote-nodes。
- 两个 SQLite 快照均使用 online backup，immutable 只读完整性检查为 `ok`。
- verify-backup 通过，文件 SHA-256 无缺失、无意外、无不匹配。
- 已真实恢复到新目录并再次校验；恢复夹具移到
  `/Users/soda/.Trash/prompt-hub-final-restore-qa-20260901`。
- 正式 `doctor` 7 项全部通过：两库、WD14、目录、磁盘和 8765 服务正常；磁盘剩余约 711.6 GiB。

## 文档与日常入口

- 完整操作手册：`MAC_OPERATIONS_GUIDE.md`。
- 绘图短流程：`DRAWING_V1_GUIDE.md`。
- 双击入口：启动、停止、备份、诊断、更新公共资料。
- 操作手册覆盖一次创作、一次数据集审核、一次 LoRA 训练、一次 Windows 回传，以及明天 SMB 配置顺序。

## 连接 5060 Ti 的顺序

1. 确认 5060 Ti Windows 的固定 IP/设备名与 SMB 共享名。
2. Finder 挂载共享目录，凭据只交给 macOS Keychain。
3. 在“设备连接”填写 host 和 `/Volumes/...` 路径，执行保存 → 检查 → 建立目录。
4. 在“跨设备任务状态”确认 ledger 可刷新，再投递一个最小任务观察 queued → running → returned。
5. 先回传一张真实 ComfyUI PNG，与原 workflow 人工核对。
6. 由 Windows Worker 读取 LoRA Manager metadata 与 ComfyUI LoRA 目录，生成只读清单；Mac 不复制权重。
7. 用一个冻结包做 5–10 step LoRA smoke test。
8. 接 `embedding_batch` 与 `vlm_caption_batch`，所有结果回显源 SHA-256。
9. 最后测试 SMB 断线、Windows 重启、重复投递、失败重试与幂等回传。

## 尚未完成的跨设备验收门

- 用户真实 24+ 图片 LoRA 数据集的长任务取消、重启恢复和冻结发布验收；
- 5060 Ti 的真实 SMB 任务流、单卡串行调度、在线状态、磁盘状态与结果关联；
- Windows Worker 对 LoRA Manager metadata、预览和 ComfyUI LoRA 目录的真实读取；
- 真实 CLIP/SigLIP 相似结果与视觉聚类；
- 5060 Ti 批量 Krea 2 VLM、暂停与恢复；
- Windows 离线、网络中断、磁盘不足和跨设备备份恢复。
