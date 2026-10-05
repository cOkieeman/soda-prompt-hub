# Linux 安装指南

> 状态：**Experimental**（实验性，非官方构建）。核心功能可用，Compute Worker 不在此范围内。
> 支持范围与证据见 [兼容性审计](COMPATIBILITY_AUDIT.md)，开发环境见 [开发环境](DEV_ENVIRONMENT.md)。

## 前置条件

| 项目 | 要求 |
| --- | --- |
| 系统 | Linux，systemd（`systemctl --user` 可用）；已在 Ubuntu 24.04 LTS 实测 |
| 架构 | x86_64（其他架构未验证） |
| Python | 3.12 或更高（由 `uv` 准备，不需要改系统 Python） |
| `uv` | 必需（`curl -LsSf https://astral.sh/uv/install.sh \| sh` 或 `pipx install uv`） |
| `git` | 更新功能需要；仅安装可不装 |
| `curl` | 安装后的健康检查需要 |

先自检：

```bash
scripts/linux/check-env.sh
```

该脚本只检查不安装，缺失项会给出处理建议。

## 方式 A：从源码安装（推荐）

```bash
git clone https://github.com/TPSROG/soda-prompt-hub.git
cd soda-prompt-hub
./deploy/linux/install.sh
```

安装脚本会依次完成：

1. 检查 Linux 环境、`uv`、`git`、`curl`、Python；
2. 创建用户数据目录（默认 `~/.local/share/soda-prompt-hub/{library,models}`）；
3. 在仓库内执行 `uv sync --locked`，生成 `<仓库>/.venv`；
4. 安装便利命令 `~/.local/bin/soda-prompt-hub`；
5. 写入 systemd **用户**服务 `~/.config/systemd/user/soda-prompt-hub.service` 并启用、启动；
6. 轮询 `/api/health` 直到服务就绪（最多 30 秒）。

不需要 `sudo`，不会修改系统级配置，也不会删除任何用户数据。

### 常用参数

| 参数 | 说明 |
| --- | --- |
| `--port <端口>` | 监听端口，默认 `8765` |
| `--host <地址>` | 监听地址，默认 `127.0.0.1`；填非回环地址会给出警告 |
| `--library-root <路径>` | 资料库根目录，默认 `$XDG_DATA_HOME/soda-prompt-hub/library` |
| `--models-root <路径>` | 模型根目录，默认 `<资料库父目录>/models` |
| `--no-service` | 只准备依赖与目录，不安装 systemd 服务 |
| `--enable-linger` | 额外执行 `loginctl enable-linger`（注销后服务继续运行） |
| `--force` | 已存在安装记录时允许改配置（不会删除数据） |

重复执行 `install.sh` 是安全的：它会沿用既有数据目录，只更新服务配置并重启。

## 方式 B：从 tar.gz 发行包安装

```bash
sha256sum -c SHA256SUMS
tar -xzf soda-prompt-hub-linux-x86_64-<版本>-<日期>.tar.gz
cd soda-prompt-hub
./deploy/linux/install.sh
```

发行包内已包含 `deploy/`、`scripts/`、`docs/` 与程序本体，安装方式与源码一致。

维护者可从已通过 CI 的 `linux/main` 构建可复现的源码包：

```bash
uv run python scripts/build_linux_release.py \
  --output-dir dist/linux \
  --architecture x86_64 \
  --build-date "$(date -u +%Y%m%d)"
```

## 安装位置

| 内容 | 路径 |
| --- | --- |
| 程序（仓库本体） | 你 `git clone` 或解压的位置 |
| Python 环境 | `<程序目录>/.venv` |
| 用户数据 | `~/.local/share/soda-prompt-hub/{library,models}` |
| 安装记录 | `~/.local/share/soda-prompt-hub/install.env` |
| systemd 服务 | `~/.config/systemd/user/soda-prompt-hub.service` |
| 便利命令 | `~/.local/bin/soda-prompt-hub` |
| 应用菜单入口 | `$XDG_DATA_HOME/applications/soda-prompt-hub.desktop` |
| 应用图标 | `$XDG_DATA_HOME/icons/hicolor/256x256/apps/soda-prompt-hub.png` |

程序与用户数据完全分离：重新安装或更新程序不会移动、删除提示词、图片、数据库或模型。

## 验证

```bash
systemctl --user status soda-prompt-hub
curl http://127.0.0.1:8765/api/health
soda-prompt-hub status
soda-prompt-hub open
```

也可以从应用菜单点击 **Soda Prompt Hub**。轻量启动器会在服务就绪后打开
<http://127.0.0.1:8765>；启动日志保存在
`$XDG_DATA_HOME/soda-prompt-hub/logs/launcher.log`。

## 日常使用

| 操作 | 命令 |
| --- | --- |
| 查看状态 | `soda-prompt-hub status` |
| 启动 / 停止 / 重启 | `soda-prompt-hub start` / `stop` / `restart` |
| 查看日志 | `soda-prompt-hub logs`（等价于 `journalctl --user -u soda-prompt-hub -f`） |
| 前台运行（调试） | `soda-prompt-hub serve` |
| 版本 | `soda-prompt-hub version` |
| 更新 | `soda-prompt-hub update`，见 [更新指南](UPDATE.md) |

### 让服务在注销后继续运行

默认不开启 `linger`：注销当前用户会话后，用户级服务会随之停止。需要常驻时：

```bash
./deploy/linux/install.sh --enable-linger
# 或
loginctl enable-linger "$USER"
```

## 数据目录与会话

程序默认只监听 `127.0.0.1`，不对外暴露。资料库位置由环境变量决定：

```bash
export PROMPT_HUB_LIBRARY_ROOT="$HOME/.local/share/soda-prompt-hub/library"
export PROMPT_HUB_MODELS_ROOT="$HOME/.local/share/soda-prompt-hub/models"
```

systemd 服务已通过 `Environment=` 注入这两个变量；手工前台运行时请自行导出。

## 卸载

```bash
./deploy/linux/uninstall.sh              # 停止服务、移除 unit 与便利命令，保留用户数据
./deploy/linux/uninstall.sh --purge-data # 连资料库与模型一起删除（会二次确认）
```

## 排错

| 现象 | 处理 |
| --- | --- |
| `未找到安装记录` | 先运行 `./deploy/linux/install.sh` |
| 健康检查未通过 | `systemctl --user status soda-prompt-hub`、`journalctl --user -u soda-prompt-hub -n 50` |
| 端口被占用 | 换 `--port`，或用 `ss -ltnp` 找出占用者 |
| 没有 systemd 用户会话（容器等） | 用 `--no-service` 安装，再用 `start.sh` / `stop.sh` 以进程方式管理 |
| 状态显示 `unavailable` | 当前会话连不上 `systemd --user`；在 WSL2 中确认 `/etc/wsl.conf` 有 `[boot] systemd=true` |
| `uv` 下载很慢 | 可改用发行源或镜像安装 `uv`，安装脚本本身不下载 `uv` |

## 与官方版本的关系

本 Linux 构建**由社区维护，不是官方发行**。上游项目、许可证与全部平台说明见仓库根目录
`README.md` 与 `LICENSE`。
