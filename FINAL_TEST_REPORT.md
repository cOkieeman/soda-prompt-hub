# Soda Prompt Hub 个人版 1.0 候选验收报告

更新日期：2026-09-05

候选版本：`1.0.0`

范围：Mac 本地中枢、LM Studio/外部模型辅助、5060 Ti ComfyUI 出图、结果回流、资料与视觉检索、
LoRA/底模只读清单，以及数据集冻结交付。

## 总结

个人版 1.0 的两条主要工作流已经闭合：

1. `灵感/OC/资料 → Anima/Krea 2 Prompt → 5060 Ti 出图 → 结果回流 → 版本复盘`
2. `素材/结果图 → 数据集检查 → WD14/已有标签 → 人工审核 → 冻结 → 数据集交付包`

Prompt Hub 不启动 Windows 训练，也不替代 AnimaLoraStudio 和 ComfyUI LoRA Manager。训练、正则、
最终标签筛选和 LoRA 测试不属于本候选版的完成门。

## 自动检查

| 检查 | 候选版结果 |
|---|---|
| pytest | 160 / 160 通过 |
| 覆盖率 | 80.13%，达到 80% 门槛 |
| Ruff format / lint | 105 个文件格式正确，lint 通过 |
| ty | `src/` 通过 |
| 锁文件 | `uv lock --check` 通过，项目版本为 `1.0.0` |
| Python wheel / sdist | `prompt_hub-1.0.0` 两种包均构建成功 |
| GitHub Actions | PR #4 的远端 quality job 已通过（format、lint、ty、pytest、build） |
| `git diff --check` | 通过 |

GitHub Actions 会在 push 到 `main` 或提交 PR 时运行同一组格式、lint、类型、测试和构建检查。
发布 PR #4 的首次远端运行已通过，结果见 GitHub Actions run `33936005792`。

## 浏览器验收

- 地址：`http://127.0.0.1:8765/`；标题为 `Soda Prompt Hub`。
- 桌面首屏显示原有导航和绘图入口，页面能找到“个人版 1.0”及新的设备分工说明。
- 点击“数据集”后显示真实“数据集工作台”和现有工作区，没有白屏或错误覆盖层。
- 390×844 窄屏中 `scrollWidth = clientWidth = 390`，无横向溢出。
- 桌面和窄屏控制台均为 0 warning / 0 error。

## 产品验收

- 首页直接说明产品用途、日常绘图顺序与 Mac/5060 Ti 分工。
- 创作台保存项目语义，并分别生成 Anima 标签与 Krea 2 自然语言 Prompt。
- 本地资料、网页来源卡、OC、视觉参照和 CLIP 相似图都保留真实来源。
- Workflow Profile 只修改声明过的 ComfyUI 节点，模型族不兼容时服务端拒绝投递。
- Windows Worker 回传的图片、workflow、日志和清单先校验 SHA-256，再进入 Mac 事实库。
- 数据集源目录只读；冻结版本包含图片副本、同名 `.txt`、`manifest.json`、`audit.json` 和
  `hashes.sha256`，不会覆盖旧版本。
- API Key 只保存在个人私有目录，列表接口和网页不返回明文。

## 数据与恢复边界

Prompt Hub 备份包含数据库、embedding 索引、创作项目、个人资料、结果图、项目来源、数据集工作区、
冻结版本、LoRA 项目、Workflow Profile、设备登记和任务事实。公共 Git 资料、可重建缩略图、Windows
预览缓存、模型权重以及外部原始数据集不重复备份。

外部原始图片和 `.txt` 仍需用户单独备份；“工作区已备份”不代表外部源目录已经复制。

## 发布前剩余动作

1. 合并已通过远端 CI 的发布 PR #4；
2. 在合并后的 `main` 创建 `v1.0.0` tag 和 GitHub Release；
3. 核对仓库首页、MIT License、Release 与默认分支状态。

## 后续优化但不阻塞发布

- 按真实维护频率拆分 `dataset_curation.py`、`remote_nodes.py` 和 `windows_worker.py`；
- 将内嵌前端资源逐步拆为可独立测试的静态文件；
- 为数据库结构引入显式 schema 版本和迁移记录；
- 根据一周实际使用反馈优化窄屏导航和数据集工作区首屏顺序。
