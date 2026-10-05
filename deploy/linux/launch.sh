#!/usr/bin/env bash
#
# Soda Prompt Hub — Linux 桌面启动器。
#
# 启动或复用本机 Core，等待健康检查通过，再交给桌面环境的默认浏览器打开。
# 可直接运行，也可由用户级 soda-prompt-hub.desktop 调用。

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

sph_require_linux
sph_require_install_env

LOG_FILE="$(sph_desktop_log_path)"
mkdir -p "$(dirname -- "${LOG_FILE}")"

launcher_log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*" >>"${LOG_FILE}"
}

launcher_notify() {
    local summary="$1" body="$2"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send --app-name="Soda Prompt Hub" "${summary}" "${body}" >/dev/null 2>&1 || true
    fi
}

launcher_fail() {
    launcher_log "FAIL: $*"
    sph_err "$*"
    launcher_notify "Soda Prompt Hub 启动失败" "$*；日志：${LOG_FILE}"
    exit 1
}

if sph_health_ok; then
    launcher_log "复用已运行的服务：$(sph_health_url)"
else
    launcher_log "服务未就绪，开始启动"
    if ! "${SCRIPT_DIR}/start.sh" >>"${LOG_FILE}" 2>&1; then
        launcher_fail "Core 未能启动"
    fi
fi

if ! sph_health_ok; then
    launcher_fail "Core 启动后健康检查未通过"
fi

APP_URL="$(sph_app_url)"
launcher_log "Core 已就绪：${APP_URL}"

if [[ "${PROMPT_HUB_LAUNCHER_SKIP_OPEN:-0}" == "1" ]]; then
    sph_ok "服务已就绪：${APP_URL}"
    launcher_log "按 PROMPT_HUB_LAUNCHER_SKIP_OPEN 跳过浏览器"
    exit 0
fi

if command -v xdg-open >/dev/null 2>&1; then
    OPENER=(xdg-open)
elif command -v gio >/dev/null 2>&1; then
    OPENER=(gio open)
else
    launcher_fail "未找到 xdg-open 或 gio，无法打开默认浏览器"
fi

if ! "${OPENER[@]}" "${APP_URL}" >>"${LOG_FILE}" 2>&1; then
    launcher_fail "默认浏览器未能打开 ${APP_URL}"
fi

launcher_log "已交给默认浏览器打开"
launcher_notify "Soda Prompt Hub" "工作台已就绪"
