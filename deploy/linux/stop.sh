#!/usr/bin/env bash
#
# Soda Prompt Hub — 停止服务

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

sph_require_linux
sph_require_install_env

STOPPED=0

if sph_service_installed && sph_have_systemd_user; then
    if sph_service_active; then
        sph_systemd_stop
        sph_ok "已停止 systemd 用户服务"
    else
        sph_info "systemd 服务本来就未运行"
    fi
    STOPPED=1
fi

if pid="$(sph_direct_pid)"; then
    kill "${pid}" 2>/dev/null || true
    for _ in $(seq 1 10); do
        kill -0 "${pid}" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "${pid}" 2>/dev/null; then
        sph_warn "进程 ${pid} 未在 10 秒内退出，发送 SIGKILL"
        kill -9 "${pid}" 2>/dev/null || true
    fi
    sph_ok "已停止直接运行的进程（pid ${pid}）"
    STOPPED=1
fi

rm -f "$(sph_pid_file)"

if ((STOPPED == 0)); then
    sph_info "没有发现正在运行的实例（$(sph_health_url) 未响应，也没有 pid 文件）"
fi
