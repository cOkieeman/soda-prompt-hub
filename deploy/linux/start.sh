#!/usr/bin/env bash
#
# Soda Prompt Hub — 启动服务
#
# 有 systemd 用户会话时走 systemctl --user start；
# 否则以前台后台进程方式启动，并把日志写入 <数据目录>/logs/serve.log。

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

sph_require_linux
sph_require_install_env

if sph_service_installed && sph_have_systemd_user; then
    if sph_service_active; then
        sph_ok "服务已在运行：$(sph_health_url)"
        exit 0
    fi
    sph_systemd_start
    if sph_wait_health 30; then
        sph_ok "已启动：$(sph_health_url)"
    else
        sph_err "服务已提交启动，但健康检查未通过"
        sph_info "排查：systemctl --user status ${SPH_SERVICE_NAME} ; journalctl --user -u ${SPH_SERVICE_NAME} -n 50"
        exit 1
    fi
    exit 0
fi

# --- 无 systemd：直接以进程方式运行 ---
if pid="$(sph_direct_pid)"; then
    sph_ok "已在运行（pid ${pid}）：$(sph_health_url)"
    exit 0
fi

LOG_DIR="$(sph_data_home)/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/serve.log"

export PROMPT_HUB_LIBRARY_ROOT="${SPH_LIBRARY_ROOT}"
export PROMPT_HUB_MODELS_ROOT="${SPH_MODELS_ROOT}"

nohup "${SPH_REPO}/.venv/bin/prompt-hub" serve \
    --host "${SPH_HOST}" --port "${SPH_PORT}" \
    >>"${LOG_FILE}" 2>&1 &
echo $! >"$(sph_pid_file)"

if sph_wait_health 30; then
    sph_ok "已启动（pid $(cat "$(sph_pid_file)")）：$(sph_health_url)"
    sph_info "日志：${LOG_FILE}"
else
    sph_err "启动后健康检查未通过；日志尾部："
    tail -n 20 "${LOG_FILE}" >&2 || true
    exit 1
fi
