# Soda Prompt Hub · 动效与交互设计计划书

> 状态：草案 v0.1 · 2026-09-12  
> 工作区：`E:\个人开发项目\soda prompt hub`  
> 关联分支 / PR：`ui/unify-art-direction` · https://github.com/cOkieeman/soda-prompt-hub/pull/16  
> 原则：服务阅读与操作反馈，不做花哨特效；服从现有纸色 / 信号红 / 酸黄编辑式美术。

---

## 0. 这份计划要回答什么

1. **已经做了什么**（美术统一，见 §1）  
2. **动效要解决什么问题**（不是为动而动，见 §2）  
3. **统一的时间 / 缓动 / 层级规则**（见 §3）  
4. **按页面拆的改造清单与优先级**（见 §4）  
5. **怎么验收、怎么分期交付**（见 §5–§6）  
6. **明确不做的事**（见 §7）

---

## 1. 已完成：美术方向统一（Phase 0）

在动效之前，先把「看起来像同一产品」做完。本轮已合入分支 `ui/unify-art-direction`：

| 项 | 说明 |
|---|---|
| 色板 | 收敛到 `--ink` / `--paper` / `--signal` / `--acid` 及扩展 token（`--cream`、`--paper-lift`、`--hard-lift` 等） |
| 控件 | 主按钮 = 信号红 + 奶油字 + 硬阴影 hover；次按钮 = 墨线 → 墨底酸字 |
| 横幅 | 左侧色条（酸黄 / 信号红）+ 纸色底 + 等宽字体；去掉偏 Tailwind 的森林绿 ready 态 |
| 字体 | 展示标题统一 Iowan Old Style 系；分区标签等宽大写字距 |
| 动效克制 | 仅保留既有短 transition / 卡片 `reveal` / 图 hover scale；尊重 `prefers-reduced-motion` |
| 范围 | `base.css`、`creative.css`、以及 search / workspace / lora / comfy / remote / source_center 的样式块 |
| 未改 | API、SQLite schema、Windows Worker 协议、i18n 文意、业务 JS 逻辑 |

**结论：** Phase 0 = 视觉语言统一。后续动效必须站在这套 token 上扩展，禁止另起品牌色或引入第三套控件皮肤。

---

## 2. 动效目标（问题导向）

| 用户问题 | 动效应提供的反馈 |
|---|---|
| 「我点了没有？」 | 指针 / 按钮 80–180ms 内有明确 pressed / hover 变化 |
| 「页面换了吗？」 | 视图切换有可感知但不抢戏的进入（淡入或轻位移），避免硬切茫然 |
| 「任务在跑吗？」 | 进度条 / 任务条用连续进度与状态色，而不是只改文字 |
| 「列表刷新了吗？」 | 卡片入场节奏统一（已有 `reveal` 可系统化），避免整页闪白 |
| 「能不能少分心？」 | 默认短、少、同方向；系统开启「减少动态效果」时全部降级为瞬切或淡入 |

**成功标准（主观）：** 用一天创作台 / 数据集 / 出图流程，感觉「稳、清楚」，而不是「炫」。

---

## 3. 动效设计规范（拟定为 token）

> 落地时优先写进 `base.css` 的自定义属性，功能页只引用，不各自发明时长。

### 3.1 时长

| Token（拟） | 值 | 用途 |
|---|---|---|
| `--motion-instant` | 0ms | reduced-motion / 关键切换兜底 |
| `--motion-fast` | 120ms | hover、焦点、小按钮 |
| `--motion-base` | 180ms | 默认控件（与现网 `.18s` 对齐） |
| `--motion-enter` | 280–350ms | 卡片 / 面板进入（与现网 `reveal .35s` 对齐） |
| `--motion-page` | 220ms | 视图切换（仅透明度或 4–8px 位移） |

禁止：超过 500ms 的装饰性动画；循环呼吸光（除非任务进行中且可暂停）。

### 3.2 缓动

| Token（拟） | 值 | 用途 |
|---|---|---|
| `--ease-standard` | `ease` 或 `cubic-bezier(.2,.75,.2,1)` | 默认；与现网图片 hover 曲线可统一 |
| `--ease-exit` | `ease-in` | 退出略快于进入 |

禁止：弹跳、过度 spring、旋转花活。

### 3.3 层级与手法白名单

**允许**

- 颜色 / 背景 / 边框 transition  
- `translate` ≤ 8px（硬阴影 lift 已存在，保持）  
- `opacity` 淡入  
- 进度条 `value` 变化  
- 列表交错延迟 ≤ 30ms/项，总延迟封顶 200ms  

**默认禁止**

- 整页视差、鼠标跟随光斑  
- 共享元素大飞入、路由级 View Transition 大片编排（若未来做，单独立项）  
- 无限 Lottie / 骨架屏闪光作为装饰  

### 3.4 无障碍

继续并强化：

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
  }
}
```

任何新增 `@keyframes` 必须能被上述规则关掉，或提供等价静态态。

---

## 4. 页面改造清单（按优先级）

### P0 · 全局壳（`base.css` / `base.js` / `index.html`）

| 项 | 现状 | 计划 |
|---|---|---|
| 导航当前页 | 瞬间换色 | 保持短 transition，统一 `--motion-fast` |
| `setView` 切页 | `hidden` 硬切 | 可选：离场 opacity→0 再 hidden，入场短 fade；默认仍要快 |
| 主/次按钮 hover | 已有 lift | 收成 utility（`.ui-btn-primary` 等），各页复用 |
| 焦点环 | 酸黄 outline | 保持；确认所有新控件不丢 `:focus-visible` |

### P1 · 高频创作路径

| 页面 | 关键反馈点 | 计划动作 |
|---|---|---|
| 创作台 | 槽位锁定、加入参考、Profile 切换、保存态 | 锁定切换 120ms 色变；保存态文案旁可加短脉冲（可关） |
| 提示词库 / 角色库 | 结果卡 `reveal` | 统一 delay 规则；刷新时先淡出旧卡再入场 |
| 智能检索 | 模式切换、任务进度 | 模式按钮状态与任务条进度动画对齐全局 token |

### P2 · 任务与设备

| 页面 | 关键反馈点 | 计划动作 |
|---|---|---|
| Windows 出图 / 设备连接 | 任务队列、连接状态 | 状态色只用 signal/acid/ink；进度条用 `--signal` accent |
| 数据集 / LoRA | 批量作业、冻结交付 | 作业条与检索页同一套 job UI 动效 |

### P3 · 资料管理 / 首页引导

| 页面 | 计划 |
|---|---|
| 首页资料安装 | 进度条已有；补「完成」一瞬的非循环确认 |
| 资料管理同步行 | ready/dirty/failed 色与动效跟 Phase 0 色板一致（已部分完成） |

---

## 5. 分期交付

| 阶段 | 内容 | 产出 | 验收 |
|---|---|---|---|
| **Phase 0** ✅ | 美术 token / 控件 / 横幅统一 | PR #16 | 各主视图目测同一产品 |
| **Phase 1** | `base.css` 运动 token + 按钮/卡片 utility；文档化 | 本计划落地 CSS 变量 | reduced-motion 回归；无新依赖 |
| **Phase 2** | `setView` 轻量进入；创作台关键反馈 | 小 diff，行为不变 | 手测创作闭环不卡顿 |
| **Phase 3** | 任务条 / 进度组件统一 | job UI 共用样式 | 出图 / 索引 / 打标三条路径一致 |
| **Phase 4** | （可选）录屏对比 + 验收清单勾选 | `docs/design/` 更新 | 人工走 `MANUAL_ACCEPTANCE_GUIDE` 相关页 |

每阶段：**先改 CSS / 极薄 JS → 本地 `prompt-hub serve` 目测 → 再推分支**。不引入打包器和动效库。

---

## 6. 验收清单（动效专用）

- [ ] 未开「减少动态效果」时：按钮 hover ≤ 180ms，可感知  
- [ ] 开启「减少动态效果」时：无位移 / 无持续动画，功能全部可用  
- [ ] 视图切换不出现白闪超过一帧的失控感（允许极短淡入）  
- [ ] 任务进行中：进度可见；结束后无残留循环动画  
- [ ] 与 Phase 0 色板无冲突（无第三套绿 / 蓝体系）  
- [ ] 不新增 npm 依赖；`web.py` 拼装路径仍可用  

---

## 7. 明确不做

- 不为「显得高级」加装饰性动效  
- 不引入 Framer Motion / GSAP / Lottie 等库（除非单独立项并改架构）  
- 不把视频创作（MiniMax H3）的时间轴动效混进本计划  
- 不在本计划内改业务 API、Worker 协议、训练流程  

---

## 8. 工作区与协作约定

| 项 | 约定 |
|---|---|
| 本机正式目录 | `E:\个人开发项目\soda prompt hub` |
| 远程 | `https://github.com/cOkieeman/soda-prompt-hub` |
| 当前设计分支 | `ui/unify-art-direction` |
| 计划书路径 | `docs/design/motion-design-plan.md`（本文件） |
| 临时目录 | 禁止再用用户主目录临时 clone 当正式区；一次性推送后应迁回本目录 |

---

## 9. 下一步（待你拍板后执行）

1. Phase 1：把 §3 token 写进 `base.css`，按钮/横幅改用 utility（纯 CSS，行为不变）  
2. 出一页「动效前后」对照说明（可附截图，可选）  
3. Phase 2 起按 §4 P1 页面逐项改，每项可单独小提交  

---

*本计划书补齐「先有目标与分期，再改界面」的记录。Phase 0 美术统一已发生；动效本体从 Phase 1 起按本文执行。*