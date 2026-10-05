#!/usr/bin/env bash
#
# Soda Prompt Hub — 状态检查
#
# 输出：安装记录、systemd 用户服务状态、进程、监听地址、健康检查、数据占用、最近日志。

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

sph_require_linux
sph_require_install_env

printf 'Soda Prompt Hub — 状态\n\n'

printf -- '--- 安装记录 ---\n'
printf '  仓库:     %s\n' "${SPH_REPO}"
printf '  资料库:   %s\n' "${SPH_LIBRARY_ROOT}"
printf '  模型:     %s\n' "${SPH_MODELS_ROOT}"
printf '  监听:     %s:%s\n' "${SPH_HOST}" "${SPH_PORT}"
printf '  安装时间: %s\n' "${SPH_INSTALLED_AT:-未知}"
printf '  记录文件: %s\n' "$(sph_install_env_path)"

printf -- '\n--- 服务 ---\n'
if sph_service_installed; then
    printf '  unit: %s\n' "$(sph_unit_path)"
    if sph_have_systemd_user; then
        printf '  状态: %s\n' "$(sph_service_state)"
        main_pid="$(systemctl --user show -p MainPID --value "${SPH_SERVICE_NAME}.service" 2>/dev/null || echo 0)"
        [[ "${main_pid}" == "0" ]] || printf '  主进程: %s\n' "${main_pid}"
    else
        printf '  状态: systemd 用户会话不可用（unavailable）\n'
    fi
else
    printf '  未安装 systemd 用户服务\n'
fi

if pid="$(sph_direct_pid)"; then
    printf '  直接运行的进程: %s（pid 文件 %s）\n' "${pid}" "$(sph_pid_file)"
fi

printf -- '\n--- 监听与健康检查 ---\n'
if command -v ss >/dev/null 2>&1; then
    listeners="$(ss -ltn 2>/dev/null | awk -v p=":${SPH_PORT}" '$4 ~ p"$" {print $4}' | tr '\n' ' ')"
    if [[ -n "${listeners}" ]]; then
        printf '  监听地址: %s\n' "${listeners}"
    else
        printf '  监听地址: 端口 %s 上没有监听\n' "${SPH_PORT}"
    fi
fi

if command -v curl >/dev/null 2>&1; then
    if sph_health_ok; then
        printf '  健康检查: ok\n'
        curl -fsS --max-time 3 "$(sph_health_url)" 2>/dev/null | head -c 400
        printf '\n'
    else
        printf '  健康检查: 失败（%s 无响应）\n' "$(sph_health_url)"
    fi
else
    printf '  健康检查: 跳过（缺少 curl）\n'
fi

printf -- '\n--- 数据 ---\n'
printf '  %s\n' "$(sph_data_usage)"

printf -- '\n--- 最近日志 ---\n'
if sph_service_installed && sph_have_systemd_user && command -v journalctl >/dev/null 2>&1; then
    journalctl --user -u "${SPH_SERVICE_NAME}" -n 5 --no-pager 2>/dev/null || true
elif [[ -f "$(sph_data_home)/logs/serve.log" ]]; then
    tail -n 5 "$(sph_data_home)/logs/serve.log" || true
else
    printf '  （无日志可显示）\n'
fi
