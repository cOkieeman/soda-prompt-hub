# Soda Prompt Hub · 前端审计报告

> 日期：2026-09-12  
> 分支：`ui/unify-art-direction`  
> 范围：SPA 壳层 + 各功能视图（无 bundler / 无 React）  
> 关联：`docs/design/motion-design-plan.md` · `docs/design/ui-art-unification-log.md`

---

## 1. 架构总览

前端是 **服务端拼装的单页应用**：浏览器只拿到一份 HTML，样式与脚本以内联 `<style>` / `<script>` 形式注入。

| 层 | 路径 | 职责 |
|---|---|---|
| 拼装入口 | `src/prompt_hub/web.py` | 读取 `web_assets/*`，把各 `*_web.py` 的 HTML/CSS/JS 字符串插入 `</head>`、`managementPage` 前、`</body>` |
| 资源读取 | `src/prompt_hub/web_resources.py` | `importlib.resources` 读包内 `web_assets` |
| 壳层资产 | `src/prompt_hub/web_assets/` | `index.html`、`base.css`、`base.js`、`i18n.js`；创作台另有 `creative.css` / `creative.js` |
| 功能模块 | `*_web.py` + `creative_web_layout.py` | 多数功能仍用 Python 三引号字符串承载 HTML/CSS/JS |

**数据流：** `prompt-hub serve` → `render_index_html(device_name)` → 浏览器 `fetch('/api/...')`。无路由库；视图切换靠 `hidden` + `base.js` 的 `setView`。

**结论：** 架构清晰、零构建，但 **资产分裂不对称**——创作台已外置到 `web_assets`，其余功能仍埋在 Python 字符串里，审计与样式复用成本偏高。

---

## 2. 页面地图（`data-view`）

| View | DOM 根 | 主要模块 | 说明 |
|---|---|---|---|
| `home` | `#homePage` | `index.html` + `base.js` | 引导、资料安装进度、版本状态 |
| `creative` | `#creativePage` | `creative_web*` + `creative.css/js` | 三栏创作台、槽位、WD14、工作流投递 |
| `prompts` / `characters` | `#archiveWorkspace` | `index.html` + `base.js` | 共用侧栏检索；角色模式切换筛选与 OC 导入 |
| `discover` | `#discoveryPage` | `search_web.py` | 文字 / 以图搜图 / 聚类；视觉模型与索引任务 |
| `datasets` | `#workspacePage` | `workspace_web.py` | 数据集工作区、导入进度、批量作业 |
| `lora` | `#loraPage` | `lora_web.py` | LoRA 项目与交付 |
| `comfy` | `#comfyPage` | `comfy_web.py` | Windows 出图结果导入与审核 |
| `remote` | `#remotePage` | `remote_web.py` | 设备连接、任务队列、端点与清单 |
| `management` | `#managementPage` + Source Center | `index.html` + `source_center_web.py` | 资料同步 + 来源中心 |

主导航：`.app-nav` / `.app-nav-button[data-view]`；当前页用 `aria-current="page"`。

---

## 3. 资产分裂状态

| 已外置 (`web_assets/`) | 仍内嵌在 Python 字符串 |
|---|---|
| `index.html`, `base.css`, `base.js`, `i18n.js` | `search_web.py`（SEARCH_*） |
| `creative.css`, `creative.js` | `workspace_web.py`（~826 行，STYLES+HTML+SCRIPT） |
| `creative_web.py` 仅薄封装读 layout/assets | `lora_web.py`, `comfy_web.py`, `remote_web.py`, `source_center_web.py` |

`creative_web_layout.py` 负责创作台 DOM 结构；样式/脚本已拆出，是迁移范本。

**风险：** 在 Python 里改 CSS 无语法高亮、易漏引号转义；`workspace_web.py` / `remote_web.py` / `creative.js` 体量最大，回归成本高。

---

## 4. 设计 Token 漂移（剩余）

Phase 0 已引入 `--ink / --paper / --signal / --acid` 及 `--paper-lift/wash/panel`、`--field`、`--hard-lift`、`.ui-btn*`、`.ui-banner*`。审计时仍见：

1. **`--cream: var(--cream)` 循环定义（已在本轮修复为 `#fff8eb`）**  
   Phase 0 把原硬编码 `#fff8eb` 提成 token 时写成自引用，导致主按钮奶油字在部分引擎回退异常。

2. **硬编码纸色 / 墨色残片**  
   - `#ded7c7`、`#e6dfd0`、`#dfd8c8`、`#e4ddce`（`base.css` 备注、角色详情、AnimaDex 筛选）  
   - `#171714`、`#292824`、`#20211e`（曾用于数据集任务条 / WD14 工具条；任务条本轮改为 `paper-panel`，WD14 改为 `var(--ink)` + 左边强调条）  
   - 标签类别色 `.tag-cat-*` 仍用 Tailwind 式蓝/绿/紫（`.tag-cat-0`…），与编辑式色板冲突

3. **控件皮肤重复**  
   `.home-primary`、`.search-button`、`.discovery-search button`、`.dataset-primary`、`.comfy-button.signal`、`.lora-primary`、`.rail-button.primary` 等仍各自声明「信号红 + 硬阴影 hover」，未全部改为组合 `.ui-btn.ui-btn-primary`。视觉已接近，**选择器债**仍在。

4. **横幅 / 状态条**  
   `.archive-notice`、`.source-sync-message`、`.discovery-status`、`.comfy-status`、`.remote-message`、`.lineage-notice`、`.tag-completion-banner` 同为「左边条 + 纸底 + 等宽」，类名不统一。本轮补充 `.ui-job` / `.ui-status-strip` 与共享 job 规则，但 HTML class 尚未全面改名（刻意避免大改 DOM）。

5. **动效时长字面量**  
   大量 `.18s` / `.35s` / `.15s` 散布在 feature CSS。本轮已迁到 `--motion-*` / `--ease-*`。

---

## 5. 无障碍（a11y）

| 项 | 状态 | 备注 |
|---|---|---|
| `:focus-visible` 酸黄描边 | 好 | `base.css` 全局覆盖 button/input/select/textarea/a |
| 导航 `aria-current` / 菜单 `aria-expanded` | 好 | `setView` / `setNavMenu` |
| `prefers-reduced-motion` | 好（本轮加强） | 关闭 animation/transition，并显式处理 `.view-enter` |
| 语义结构 | 中 | 大量 `<button>` 正确；部分状态仅改 `textContent`，无 `aria-live`（如 `#creativeSaveState`、`#comfyStatus`） |
| 对比度 | 中 | 墨底淡字 `--on-ink-faint` 在小字号等宽上偏弱；信号红上奶油字一般可接受 |
| 减少动态 | 好 | 视图进入、卡片 `reveal`、图片 hover scale 均可被关掉 |

**建议：** 给关键状态节点加 `role="status"`（首页安装进度已有）；创作台保存态可考虑 `aria-live="polite"`。

---

## 6. 动效状态（审计时点 → 本轮）

| 能力 | 审计前 | 本轮（Phase 1–3） |
|---|---|---|
| 运动 token | 无 | `--motion-instant/fast/base/enter/page` + `--ease-standard/exit` |
| 控件 utility | `.ui-btn*` / `.ui-banner*` 已有 | 补强；feature 时长改引用 token |
| `setView` | `hidden` 硬切 | `.view-enter` 短淡入+6px；reduced-motion 瞬切 |
| 创作台反馈 | 锁定/Tab 仅改 class | 120ms 色变；保存态 `.is-flash` ≤180ms |
| 任务条 | 检索 signal / 数据集 acid+墨底 不一致 | 统一左边条 + `paper-panel` + `accent-color: var(--signal)` |
| 花哨库 | 无 | 保持无 Framer/GSAP/Lottie |

未做（留给 Phase 4+）：列表刷新淡出再入场、交错 delay 系统化、录屏验收清单勾选。

---

## 7. 风险热点（Top）

1. **`workspace_web.py` 单体过大**  
   HTML/CSS/JS 同文件，作业轮询、导入、浏览对话框耦合；样式回归面最宽。

2. **`creative.js`（900+ 行）+ 自动保存 / compile 双定时器**  
   任何 DOM/class 动效必须避开打断 `queueCreativeSave` / `compileCreative` / workflow send。本轮仅 CSS + 保存态 class 闪烁。

3. **Token 自引用与硬编码双轨**  
   `--cream` 事故说明 Phase 0 迁移缺少一次性「字面量清扫」；标签类别色仍是第三套色板。

4. **资产分裂**  
   改全局视觉要同时搜 `web_assets/*.css` 与全部 `*_web.py` 字符串；易漏 `remote_web` / `source_center_web`。

5. **图片 hover `scale(1.035)`**  
   时长已收进 `--motion-enter`，但仍是唯一偏「营销站」的运动；与编辑式克制略冲，建议后续降到 ≤ `--motion-base` 或仅亮度变化。

---

## 8. 建议的下一步清理（优先级）

| 优先级 | 项 | 说明 |
|---|---|---|
| P0 | 继续消灭硬编码纸色 | `#ded7c7` 等 → `--paper-deep` / `--paper-wash` |
| P1 | 把 `search` / `comfy` / `lora` CSS 外置到 `web_assets/` | 仿 `creative.css`；`web.py` 拼装方式可不变 |
| P1 | HTML 逐步挂上 `.ui-btn` / `.ui-job` | 先新控件，再删重复选择器 |
| P2 | `.tag-cat-*` 改编辑式色 | 用 ink/signal/acid 透明度，去掉蓝绿紫 |
| P2 | 状态节点 `aria-live` | 保存、出图状态、任务完成 |
| P3 | 拆 `workspace_web.py` / `creative.js` | 按「样式 / 布局 / 行为」分文件，仍不引入打包器 |
| P3 | Phase 4 验收 | 按 `motion-design-plan.md` §6 录屏 + `MANUAL_ACCEPTANCE_GUIDE` |

---

## 9. 本轮改动索引（实现对照）

- `web_assets/base.css`：修复 `--cream`；运动 token；`.ui-job` / `.view-enter`；强化 reduced-motion  
- `web_assets/base.js`：`setView` → `playViewEnter`  
- `web_assets/creative.css` / `creative.js`：槽位锁定、Profile Tab、保存态反馈；WD14 条对齐 job 语言  
- `search_web.py` / `workspace_web.py` / `comfy_web.py` / `remote_web.py` / `lora_web.py` / `source_center_web.py`：时长 token 化；任务/状态条视觉对齐  
- `docs/design/motion-design-plan.md`：Phase 0–3 状态更新  

---

*本报告描述审计发现与本轮落地范围；不改变 API、schema、Worker 协议或 i18n 文意。*
