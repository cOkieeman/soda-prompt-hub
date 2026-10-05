#!/usr/bin/env bash
#
# Soda Prompt Hub — 便利命令（由 install.sh 安装到 ~/.local/bin/soda-prompt-hub）
#
# 用法:
#   soda-prompt-hub open            启动服务并在默认浏览器打开
#   soda-prompt-hub status          查看服务与资料库状态
#   soda-prompt-hub start|stop|restart
#   soda-prompt-hub logs            跟踪 systemd 用户日志
#   soda-prompt-hub serve           前台运行（Ctrl+C 退出）
#   soda-prompt-hub update          安全更新（不动用户数据）
#   soda-prompt-hub install|uninstall
#   soda-prompt-hub version

set -Eeuo pipefail

DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/soda-prompt-hub"
ENV_FILE="${DATA_HOME}/install.env"

die() {
    printf '[FAIL] %s\n' "$*" >&2
    exit 1
}

[[ -f "${ENV_FILE}" ]] || die "未找到 ${ENV_FILE}；请先运行仓库里的 deploy/linux/install.sh"
# shellcheck disable=SC1090
source "${ENV_FILE}"

REPO="${SPH_REPO:?install.env 缺少 SPH_REPO}"
[[ -d "${REPO}" ]] || die "安装记录指向的目录不存在：${REPO}"

usage() {
    sed -n '3,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

run_deploy() {
    local script="${REPO}/deploy/linux/$1"
    shift
    [[ -x "${script}" ]] || die "缺少脚本：${script}"
    exec "${script}" "$@"
}

case "${1:-}" in
    open)
        shift
        run_deploy launch.sh "$@"
        ;;
    status)
        shift
        run_deploy status.sh "$@"
        ;;
    start | stop | restart)
        action="$1"
        shift
        run_deploy "${action}.sh" "$@"
        ;;
    logs)
        shift
        if command -v journalctl >/dev/null 2>&1; then
            exec journalctl --user -u soda-prompt-hub -n 200 -f
        fi
        exec tail -n 200 -f "${DATA_HOME}/logs/serve.log"
        ;;
    serve)
        shift
        export PROMPT_HUB_LIBRARY_ROOT="${SPH_LIBRARY_ROOT}"
        export PROMPT_HUB_MODELS_ROOT="${SPH_MODELS_ROOT}"
        exec "${REPO}/.venv/bin/prompt-hub" serve --host "${SPH_HOST}" --port "${SPH_PORT}" "$@"
        ;;
    update)
        shift
        run_deploy update.sh "$@"
        ;;
    install)
        shift
        run_deploy install.sh "$@"
        ;;
    uninstall)
        shift
        run_deploy uninstall.sh "$@"
        ;;
    version)
        exec "${REPO}/.venv/bin/python" -c \
            "import prompt_hub; print(prompt_hub.__version__)"
        ;;
    -h | --help | help | "")
        usage
        ;;
    *)
        printf '未知子命令：%s\n\n' "$1" >&2
        usage >&2
        exit 2
        ;;
esac
