# Linux 更新指南

> 本文描述如何安全更新本机 Linux 上的 Soda Prompt Hub，并保证用户数据不被改动。

## 更新做了什么

`./deploy/linux/update.sh` 依次执行：

1. 打印更新前的用户数据度量（数据库大小 / 修改时间 / 资料库字节数）；
2. 检查工作区是否干净，有未提交改动时**拒绝更新**（可用 `--force` 覆盖）；
3. `git fetch --prune --tags`，然后 **只允许快进**（`git merge --ff-only`）；
4. `uv sync --locked` 同步依赖；
5. 重新生成已安装的 Core / Worker systemd unit，并收紧 Worker 配置权限；
6. 重启 Core、正在运行的 Worker（或直接运行的 Core 实例）；
7. 轮询 `/api/health` 确认服务恢复；
8. 再次打印数据度量并逐项比对，给出“资料库与数据库未发生改动”的结论。

脚本**不包含任何删除动作**，也不会触碰资料库、数据库、图片、Prompt、Workflow 与模型目录。

## 标准流程

```bash
cd <程序目录>
./deploy/linux/update.sh
# 或
soda-prompt-hub update
```

### 参数

| 参数 | 说明 |
| --- | --- |
| `--ref <分支或标签>` | 快进到指定引用（默认当前分支的上游跟踪分支） |
| `--force` | 允许在工作区有未提交改动时继续 |

### 更新前建议

```bash
# 备份个人资料（可选，但推荐在跨版本更新前做一次）
uv run --no-sync prompt-hub backup --destination ~/soda-backup
```

## 从手动发行包更新

维护者确认对应 `linux/main` 已通过 Linux CI 后，可以手动制作发行包。发行包只替换程序本体，不碰用户数据：

```bash
sha256sum -c SHA256SUMS
tar -xzf soda-prompt-hub-linux-x86_64-<新版本>-<日期>.tar.gz
rsync -a --delete soda-prompt-hub/src/ <程序目录>/src/
rsync -a soda-prompt-hub/deploy/ <程序目录>/deploy/
rsync -a soda-prompt-hub/scripts/ <程序目录>/scripts/
cp soda-prompt-hub/pyproject.toml soda-prompt-hub/uv.lock soda-prompt-hub/RELEASE.json <程序目录>/
cd <程序目录> && ./deploy/linux/install.sh --force
```

源码 tar.gz 不包含 Git 历史，所以包安装使用上面的覆盖方式；只有 `git clone` 安装才使用
`soda-prompt-hub update`。重复运行 `install.sh --force` 会刷新依赖、systemd unit、便利命令、应用菜单入口
和图标，不会删除资料库、数据库或模型。

## 回滚

```bash
cd <程序目录>
git log --oneline -10          # 找到上一个版本提交
git switch --detach <提交>
uv sync --locked
systemctl --user restart soda-prompt-hub
curl http://127.0.0.1:8765/api/health
```

用户数据与程序版本无关，回滚程序不需要动数据。

## 常见问题

| 现象 | 说明 |
| --- | --- |
| `工作区有未提交改动，已停止` | 先提交或 stash 改动；确认无妨再加 `--force` |
| 快进失败（`fatal: Not possible to fast-forward`） | 本地分支与上游分叉了，需要人工合并后再更新 |
| 更新后健康检查失败 | `journalctl --user -u soda-prompt-hub -n 50`；必要时用上面的回滚步骤 |
| 数据统计发生变化 | 若你刚在界面里写入内容属正常；否则请检查差异 |
