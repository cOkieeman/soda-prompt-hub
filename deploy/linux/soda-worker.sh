#!/usr/bin/env bash
#
# Soda Prompt Hub — Linux Compute Worker 便利命令
#（由 install.sh --with-worker 安装到 ~/.local/bin/soda-worker）
#
# 用法:
#   soda-worker self-test     检查配置、桥接目录与 ComfyUI 是否可达
#   soda-worker once          只处理一个任务后退出（便于验证）
#   soda-worker start         前台常驻运行（Ctrl+C 停止）
#   soda-worker config        打印当前配置文件路径
#   soda-worker logs          跟踪 systemd 用户服务日志

set -Eeuo pipefail

DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/soda-prompt-hub"
ENV_FILE="${DATA_HOME}/install.env"
CONFIG="${SPH_WORKER_CONFIG:-${DATA_HOME}/worker-config.json}"

die() {
    printf '[FAIL] %s\n' "$*" >&2
    exit 1
}

[[ -f "${ENV_FILE}" ]] || die "未找到 ${ENV_FILE}；请先运行仓库里的 deploy/linux/install.sh --with-worker"
# shellcheck disable=SC1090
source "${ENV_FILE}"

REPO="${SPH_REPO:?install.env 缺少 SPH_REPO}"
PYTHON="${REPO}/.venv/bin/python"
[[ -x "${PYTHON}" ]] || die "缺少虚拟环境：${PYTHON}（先运行 deploy/linux/install.sh）"
[[ -f "${CONFIG}" ]] || die "缺少 Worker 配置：${CONFIG}"

case "${1:-}" in
    self-test)
        exec "${PYTHON}" -m prompt_hub.windows_worker --config "${CONFIG}" --self-test
        ;;
    once)
        exec "${PYTHON}" -m prompt_hub.windows_worker --config "${CONFIG}" --once
        ;;
    start)
        exec "${PYTHON}" -m prompt_hub.windows_worker --config "${CONFIG}"
        ;;
    config)
        printf '%s\n' "${CONFIG}"
        ;;
    logs)
        exec journalctl --user -u soda-worker -n 200 -f
        ;;
    -h | --help | help | "")
        sed -n '3,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
        ;;
    *)
        printf '未知子命令：%s\n\n' "$1" >&2
        sed -n '3,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
        exit 2
        ;;
esac
