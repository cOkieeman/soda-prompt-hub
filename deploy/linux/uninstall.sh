#!/usr/bin/env bash
#
# Soda Prompt Hub — 卸载
#
# 默认只移除 systemd 用户服务与便利命令，**保留全部用户数据**。
# 只有显式加 --purge-data 才会删除资料库与模型目录。
#
# 用法:
#   ./deploy/linux/uninstall.sh [--purge-data] [--yes]

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

PURGE=0
ASSUME_YES=0

while (($# > 0)); do
    case "$1" in
        --purge-data)
            PURGE=1
            shift
            ;;
        --yes)
            ASSUME_YES=1
            shift
            ;;
        -h | --help)
            sed -n '3,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            sph_die "未知参数：$1"
            ;;
    esac
done

sph_require_linux

ENV_FILE="$(sph_install_env_path)"
if sph_load_install_env 2>/dev/null; then
    LIBRARY_ROOT="${SPH_LIBRARY_ROOT:-}"
    MODELS_ROOT="${SPH_MODELS_ROOT:-}"
else
    LIBRARY_ROOT=""
    MODELS_ROOT=""
    sph_warn "未找到安装记录 ${ENV_FILE}；将只清理 systemd 服务与便利命令"
fi

printf 'Soda Prompt Hub — 卸载\n\n'

# ---------------------------------------------------------------- 1. 停止并移除服务
if sph_have_systemd_user && systemctl --user list-unit-files "${SPH_SERVICE_NAME}.service" >/dev/null 2>&1; then
    systemctl --user stop "${SPH_SERVICE_NAME}.service" 2>/dev/null || true
    systemctl --user disable "${SPH_SERVICE_NAME}.service" 2>/dev/null || true
    sph_ok "服务已停止并禁用"
fi

if pid="$(sph_direct_pid)"; then
    kill "${pid}" 2>/dev/null || true
    rm -f "$(sph_pid_file)"
    sph_ok "已停止直接运行的进程（pid ${pid}）"
fi

UNIT_PATH="$(sph_unit_path)"
if [[ -f "${UNIT_PATH}" ]]; then
    rm -f "${UNIT_PATH}"
    sph_ok "已移除 ${UNIT_PATH}"
    if sph_have_systemd_user; then
        systemctl --user daemon-reload
    fi
else
    sph_info "没有 unit 文件需要移除"
fi

# ---------------------------------------------------------------- 1b. Compute Worker
WORKER_UNIT="$(sph_worker_unit_path)"
if sph_have_systemd_user && systemctl --user list-unit-files "soda-worker.service" >/dev/null 2>&1; then
    systemctl --user stop "soda-worker.service" 2>/dev/null || true
    systemctl --user disable "soda-worker.service" 2>/dev/null || true
    sph_ok "Worker 服务已停止并禁用"
fi
if [[ -f "${WORKER_UNIT}" ]]; then
    rm -f "${WORKER_UNIT}"
    sph_ok "已移除 ${WORKER_UNIT}"
    if sph_have_systemd_user; then
        systemctl --user daemon-reload
    fi
fi
WORKER_LAUNCHER="$(sph_worker_launcher_path)"
if [[ -f "${WORKER_LAUNCHER}" ]]; then
    rm -f "${WORKER_LAUNCHER}"
    sph_ok "已移除 ${WORKER_LAUNCHER}"
fi

LAUNCHER="$(sph_launcher_path)"
if [[ -f "${LAUNCHER}" ]]; then
    rm -f "${LAUNCHER}"
    sph_ok "已移除 ${LAUNCHER}"
fi

DESKTOP_ENTRY="$(sph_desktop_entry_path)"
DESKTOP_ICON="$(sph_desktop_icon_path)"
if [[ -f "${DESKTOP_ENTRY}" ]]; then
    rm -f "${DESKTOP_ENTRY}"
    sph_ok "已移除 ${DESKTOP_ENTRY}"
fi
if [[ -f "${DESKTOP_ICON}" ]]; then
    rm -f "${DESKTOP_ICON}"
    sph_ok "已移除 ${DESKTOP_ICON}"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$(dirname -- "${DESKTOP_ENTRY}")" >/dev/null 2>&1 || true
fi

# ---------------------------------------------------------------- 2. 用户数据
printf '\n'
if ((PURGE == 0)); then
    sph_info "已保留用户数据（默认行为）："
    [[ -n "${LIBRARY_ROOT}" ]] && sph_info "  资料库: ${LIBRARY_ROOT}"
    [[ -n "${MODELS_ROOT}" ]] && sph_info "  模型:   ${MODELS_ROOT}"
    sph_info "  Worker: $(sph_worker_config_path) 与 $(sph_worker_share_root)（桥接目录可能含任务与结果）"
    sph_info "如需一并删除，请加 --purge-data（会二次确认）"
else
    if ((ASSUME_YES == 0)); then
        printf '将删除以下目录及其全部内容：\n'
        printf '  资料库: %s\n' "${LIBRARY_ROOT:-（未记录）}"
        printf '  模型:   %s\n' "${MODELS_ROOT:-（未记录）}"
        printf '  Worker: %s\n' "$(sph_worker_share_root)"
        printf '确认请输入 yes：'
        read -r reply
        [[ "${reply}" == "yes" ]] || sph_die "已取消（未删除任何数据）"
    fi

    for target in "${LIBRARY_ROOT}" "${MODELS_ROOT}" "$(sph_worker_share_root)"; do
        [[ -n "${target}" ]] || continue
        if ! safe_target="$(sph_safe_purge_path "${target}")"; then
            sph_warn "跳过可疑路径（解析后不在 ${HOME} 或 /mnt 之下）：${target}"
            continue
        fi
        if [[ -d "${safe_target}" ]]; then
            rm -rf -- "${safe_target}"
            sph_ok "已删除 ${safe_target}"
        fi
    done

    rm -f "${ENV_FILE}"
    rm -f "$(sph_worker_config_path)"
    rmdir "$(sph_data_home)" 2>/dev/null || true
    sph_ok "已移除安装记录"
fi

printf -- '\n===== 卸载完成 =====\n'
sph_info "仓库本体未被删除：${SPH_REPO:-（未记录）}"
sph_info "如需彻底清理，请自行删除该目录"
