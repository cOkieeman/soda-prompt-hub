# Linux Development Environment

本机 Linux 开发/测试环境的实际状态，用于本地验证 Soda Prompt Hub 的 Linux 兼容性。
本文件**不包含任何密码、Token、API Key 或私钥**。

记录时间：2026-09-14（首次建立）

## Host

| 项目 | 值 |
| --- | --- |
| Windows | Windows 11 25H2（注册表 `ProductName` 仍为 `Windows 10 Home China`），build 26200.9445，x64 |
| 虚拟化 | CPU 虚拟化已开启；安装 WSL2 后宿主 Hypervisor 处于运行状态 |
| 磁盘约束 | C 盘空间紧张，因此 WSL 发行版**安装在 D 盘** |

## Linux Runtime

| 项目 | 值 |
| --- | --- |
| 运行时 | WSL2 |
| WSL 版本 | 2.7.14.0（WSL 内核 6.18.33.2-2） |
| 发行版 | 由 `Ubuntu-24.04` 安装，注册名指定为 `Ubuntu` |
| 安装位置 | `D:\WSL\Ubuntu`（未占用 C 盘数据目录） |
| 当前状态 | Running，VERSION 2 |

## Distribution

| 项目 | 值 |
| --- | --- |
| 发行版 | Ubuntu 24.04.5 LTS（noble） |
| Kernel | 6.18.33.2-microsoft-standard-WSL2 |
| Architecture | x86_64 |

## Toolchain

| 工具 | 版本 | 备注 |
| --- | --- | --- |
| Python | 3.12.3（`/usr/bin/python3`，系统自带，未改动） | 项目要求 `>=3.12` |
| uv | 0.12.13（`~/.local/bin/uv`） | 官方安装脚本下载极慢（约 3 KB/s），改用 `pipx` + 清华 PyPI 镜像安装；包本身来自 PyPI，未使用第三方二进制 |
| Git | 2.43.0（apt） | |
| Node.js | v18.19.1（apt） | **测试套件隐性依赖**，见下节 |
| systemd | 255（255.4-1ubuntu8.17），PID 1 = systemd，`is-system-running` = running | |

## Git identity

| 项目 | 值 |
| --- | --- |
| user.name | `TPSROG` |
| user.email | `com2105514277com@163.com` |

## Node.js 为什么必须安装

`tests/test_pairing_guide.py::test_pairing_address_parser_rejects_credentials_and_subpaths` 使用硬断言
`assert shutil.which("node")`，**缺少 Node 时会失败（而不是跳过）**；另有 12 个 Node 相关测试用
`skipif` 跳过。GitHub 的 `ubuntu-latest` runner 预装 Node，因此上游 CI 看不出这个问题。
本地或自托管的 Linux 环境必须显式安装 Node.js。

## Project

| 项目 | 值 |
| --- | --- |
| 路径 | `~/projects/soda-prompt-hub`（Linux 原生文件系统，非 `/mnt/*`） |
| origin | `https://github.com/TPSROG/soda-prompt-hub.git` |
| upstream | `https://github.com/cOkieeman/soda-prompt-hub.git` |
| `win`（本地桥接） | `/mnt/d/Github/manbo linux` —— 只在本机使用，用于把 Windows 侧的本地提交同步进 WSL，**无需 push 到 GitHub** |
| 基线分支 | `linux/main`（基于 `upstream/main`，`e96249b`） |
| 大小 | 源码树约 12 MB；含 `.venv` 约 262 MB |

同步本地提交到 WSL 的方式（不 push 时使用）：

```bash
git fetch win linux/main && git merge --ff-only win/linux/main
```

## Test command

```bash
cd ~/projects/soda-prompt-hub
uv sync --locked
uv run --no-sync pytest
```

首次实测结果（2026-09-14，WSL2 Ubuntu 24.04）：

| 项目 | 值 |
| --- | --- |
| 结果 | **543 passed, 9 skipped, 0 failed** |
| 覆盖率 | 83.41%（项目门槛 80%） |
| 耗时 | 约 126 秒 |
| 跳过原因 | 全部为 macOS 专属（代码签名、便携启动器、`/bin/zsh`、进程身份） |
| 依赖安装 | `uv sync --locked` 约 10.6 秒，`uv.lock` 无改动 |

## Run command

```bash
cd ~/projects/soda-prompt-hub
uv run --no-sync prompt-hub serve --host 127.0.0.1 --port 8765
curl http://127.0.0.1:8765/api/health
```

实测（2026-09-14）：`GET /` = 200，`/api/health` = `status: ok`，`/api/stats` 正常，
监听地址为 `127.0.0.1:8765`（未暴露到 `0.0.0.0`）。

## 数据目录策略

程序默认写入 `~/Documents/Soda Prompt Hub/prompt-library`（会在 Linux 上新建 `~/Documents`，
不符合 XDG 惯例）。本地开发与后续 `deploy/linux` 安装脚本一律通过环境变量显式指定：

```bash
export PROMPT_HUB_LIBRARY_ROOT="$HOME/.local/share/soda-prompt-hub"
export PROMPT_HUB_MODELS_ROOT="$HOME/.local/share/soda-prompt-hub/models"
```

## 网络要点

| 现象 | 说明 |
| --- | --- |
| `wsl.exe` 提示“检测到 localhost 代理配置，但未镜像到 WSL” | Windows 侧配了代理，WSL NAT 模式不支持 localhost 代理；实测 WSL 内直连可用，无需处理 |
| `releases.astral.sh` | 约 3 KB/s，几乎不可用，避免用它下载工具 |
| Ubuntu 源 / 清华 PyPI 镜像 | 数 MB/s，可用 |
| PyPI 官方源 | `uv sync --locked` 实测 10.6 秒完成约 50 个包，可用 |
| GitHub | `git clone` 与 `git ls-remote` 正常 |

## WSL 特定限制（影响后续阶段）

1. **`Linger=no`**：`systemctl --user` 可用，但用户级服务在会话结束后会停止。后续 `deploy/linux`
   的 systemd user service 若要常驻，需在安装器中**可选地**执行 `loginctl enable-linger`（不默认开启）。
2. **没有桌面会话**：未安装 `xdg-open`，“打开所在文件夹”会走失败分支。可用于验证“失败时返回可读
   错误而不是崩溃”，但不能验证图形化打开行为。
3. **`/mnt/*` 性能与权限**：Soda Prompt Hub 的工作目录固定在 Linux 原生文件系统，不使用 `/mnt/*`。
4. **与真实 Ubuntu 服务器仍有差异**：CI 用 GitHub `ubuntu-latest` 交叉验证，WSL 只作日常开发。

## 环境自检

```bash
scripts/linux/check-env.sh
```

检查内核、发行版、架构、Python/uv、Git 身份、systemd 与 `systemctl --user`、项目完整性、
依赖可导入性、数据目录可写性、端口 8765 与磁盘剩余；只检查不安装。

## 已做过的环境改动（便于回滚）

| 改动 | 位置 | 说明 |
| --- | --- | --- |
| 创建用户 `voldm`（uid 1000），加入 sudo/adm/cdrom/dip/plugdev/users | WSL `Ubuntu` | 服务不以 root 运行 |
| 无密码 sudo | `/etc/sudoers.d/90-soda-dev` | 仅本机开发用；可 `sudo passwd voldm` 设置密码后删除该文件 |
| `[boot] systemd=true`（镜像自带）、`[user] default=voldm`、`[interop] appendWindowsPath=false` | `/etc/wsl.conf` | 避免 Windows 的 python/git/uv 混入 WSL 的 PATH |
| apt / pipx 安装 | WSL `Ubuntu` | `git curl wget build-essential pkg-config ca-certificates unzip zip jq tree file nodejs pipx` |

**未改动**：Windows PATH、注册表、防火墙、代理、VPN、Docker 配置，以及 Windows 上既有的 Python / Git 安装。
