# Soda Prompt Hub V1.3 历史基线

记录日期：2026-08-30

本文件保留进入创作台开发前的历史能力快照，不代表当前发布状态。个人版 1.0 的现状以
`completion_audit.md` 和 `FINAL_TEST_REPORT.md` 为准。

## 运行基线

- 服务地址：`http://127.0.0.1:8765`
- 服务状态：`ok`
- 数据库：`$HOME/Documents/Codex/soda-person/prompt-library/database/prompt-library.sqlite`
- Python：3.12
- Web：FastAPI 返回内嵌 HTML/CSS/JavaScript
- 数据：SQLite + FTS5
- MCP：stdio server

## 真实资料基线

| 项目 | 数量 |
|------|-----:|
| 来源 | 4 |
| 总条目 | 33,631 |
| Caption | 430 |
| Modifier | 735 |
| Prompt | 1 |
| Style | 397 |
| Tag | 2,094 |
| Wildcard | 29,974 |
| SFW | 33,497 |
| Suggestive | 122 |
| Explicit Adult | 12 |
| 收藏/评分/备注 | 0 / 0 / 0 |
| OC 角色/世界/Prompt/设定 | 0 / 0 / 0 / 0 |

已索引来源：

1. Clio Style Library；
2. Kisegaeningyou；
3. Krea Open Prompts；
4. SD Wildcards。

## API 兼容边界

现有接口在后续阶段不得无迁移地删除或改变返回语义：

- `GET /`
- `GET /api/health`
- `GET /api/stats`
- `GET /api/sources`
- `GET /api/search`
- `PUT /api/marks`
- `POST /api/import`
- `POST /api/oc-manager/import`
- `GET /api/oc-manager/characters`
- `GET /api/oc-manager/characters/{character_id}`
- `GET /api/oc-manager/worlds`
- `GET /api/oc-manager/lore`
- `GET /media/{source_id}/{variant}/{relative_path}`

## 数据兼容边界

现有 SQLite 表：

- `sources`
- `entries`
- `user_marks`
- `oc_imports`
- `oc_characters`
- `oc_prompts`
- `oc_worlds`
- `oc_lore`
- `entries_fts`
- `oc_characters_fts`

创作功能应新增自己的表和模块，不复用或重定义 `entries`、`user_marks`、`oc_*` 的原始职责。

## MCP 兼容边界

现有工具：

- `search_prompts`
- `search_styles`
- `search_tags`
- `search_characters`
- `get_character_profile`
- `get_character_prompts`
- `search_world_lore`
- `library_stats`

## 页面行为基线

### Prompt 资料库

- 关键词检索；
- Type、Safety、Source 筛选；
- 本地视觉缩略图和原图打开；
- SFW、Suggestive、Explicit Adult 分级；
- 收藏、1–5 星评分和个人备注；
- 只看个人收藏；
- 查看来源链接；
- 重建本地索引。

### OC 资料库

- 导入 OC Manager JSON；
- 按角色、世界、故事和外观检索；
- 查看角色详情、Prompt、图库和关系数量；
- 重复导入按角色 ID 更新；
- 不回写 OC Manager。

## 自动测试基线

验证命令：

```bash
/opt/homebrew/bin/uv run pytest
/opt/homebrew/bin/uv run ruff check .
/opt/homebrew/bin/uv run ty check src/
```

2026-08-30 结果：

- pytest：13 passed；
- 总覆盖率：86.44%；
- ruff：通过；
- ty：通过。

## 阶段回归清单

每次功能阶段完成后至少确认：

- [ ] 主页可打开，静态资源无 404；
- [ ] `/api/health` 返回 `ok`；
- [ ] Prompt 空查询与关键词查询可用；
- [ ] Type、Safety、Source 筛选可用；
- [ ] 视觉缩略图和原图路由可用；
- [ ] 收藏、评分和备注可保存；
- [ ] 重建索引后个人标记仍保留；
- [ ] OC JSON 可导入并检索；
- [ ] OC 详情、世界和设定接口可用；
- [ ] MCP 现有工具名称和参数保持兼容；
- [ ] pytest、ruff、ty 全部通过；
- [ ] 真实资料库不被测试写入或清空。

## 架构结论

- 后端 API 与数据层已有较好测试，可作为稳定基础继续扩展。
- `database.py` 和 `web.py` 已经较大，新创作项目与 Profile 应进入独立模块。
- 前端不推倒重写；先把内嵌资源渐进拆分并保持视觉一致，再增加“开始创作”。
- 新增数据库能力采用可重复执行的增量建表，不破坏现有表和 FTS 索引。
