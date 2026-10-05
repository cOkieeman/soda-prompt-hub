#!/usr/bin/env bash
#
# Soda Prompt Hub — 安全更新
#
# 更新代码 → 同步依赖 → 重启服务，并打印“用户数据未改动”的实测证据。
# 不会删除、移动或重建资料库、数据库、图片、Prompt、Workflow 与模型目录。
#
# 用法:
#   ./deploy/linux/update.sh [--ref <分支或标签>] [--force]
#
#   --ref    指定要快进的引用（默认：当前分支的上游跟踪分支）
#   --force  允许在工作区有未提交改动时继续（默认拒绝）

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

TARGET_REF=""
FORCE=0

while (($# > 0)); do
    case "$1" in
        --ref)
            TARGET_REF="${2:?--ref 需要一个参数}"
            shift 2
            ;;
        --force)
            FORCE=1
            shift
            ;;
        -h | --help)
            sed -n '3,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            sph_die "未知参数：$1"
            ;;
    esac
done

sph_require_linux
sph_require_install_env
sph_require_cmd git "更新需要 git"

cd "${SPH_REPO}"

BEFORE="$(sph_data_usage)"
BEFORE_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

printf 'Soda Prompt Hub — 更新\n'
printf '仓库: %s\n' "${SPH_REPO}"
printf '分支: %s（当前 %s）\n\n' "${BRANCH}" "${BEFORE_COMMIT}"
printf '更新前数据: %s\n' "${BEFORE}"

printf -- '\n--- 工作区检查 ---\n'
if [[ -n "$(git status --porcelain)" ]]; then
    if ((FORCE == 0)); then
        sph_err "工作区有未提交改动，已停止（避免覆盖你的修改）"
        git status --short | head -20 >&2
        sph_info "确认无妨可加 --force"
        exit 1
    fi
    sph_warn "工作区有未提交改动，按 --force 继续"
else
    sph_ok "工作区干净"
fi

printf -- '\n--- 拉取更新 ---\n'
git fetch --prune --tags
if [[ -n "${TARGET_REF}" ]]; then
    sph_info "快进到 ${TARGET_REF}"
    git merge --ff-only "${TARGET_REF}"
else
    git merge --ff-only
fi
AFTER_COMMIT="$(git rev-parse --short HEAD)"
sph_ok "${BEFORE_COMMIT} → ${AFTER_COMMIT}"

printf -- '\n--- 同步依赖（uv sync --locked）---\n'
uv sync --locked
sph_ok "依赖已同步"

# Reload helpers from the updated checkout before regenerating installed units.
# This keeps future template changes in sync with files already under ~/.config.
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

printf -- '\n--- 更新命令与桌面入口 ---\n'
LAUNCHER="$(sph_launcher_path)"
mkdir -p "$(dirname -- "${LAUNCHER}")"
install -m 0755 "${SCRIPT_DIR}/soda-prompt-hub.sh" "${LAUNCHER}"
sph_install_desktop_integration "${SPH_REPO}" || sph_die "无法更新桌面入口"
sph_ok "便利命令与桌面入口已更新"

printf -- '\n--- 更新服务配置 ---\n'
UNITS_REFRESHED=0
if sph_service_installed; then
    sph_write_core_unit \
        "${SCRIPT_DIR}/${SPH_SERVICE_NAME}.service" \
        "$(sph_unit_path)" \
        "${SPH_REPO}" \
        "${SPH_LIBRARY_ROOT}" \
        "${SPH_MODELS_ROOT}" \
        "${SPH_HOST}" \
        "${SPH_PORT}" || sph_die "无法更新 systemd 用户服务"
    sph_ok "Core unit 已更新"
    UNITS_REFRESHED=1
fi

WORKER_UNIT="$(sph_worker_unit_path)"
WORKER_CONFIG="$(sph_worker_config_path)"
if [[ -f "${WORKER_UNIT}" ]]; then
    if [[ -f "${WORKER_CONFIG}" ]]; then
        chmod 0600 "${WORKER_CONFIG}"
        sph_write_worker_unit \
            "${SCRIPT_DIR}/soda-worker.service" \
            "${WORKER_UNIT}" \
            "${SPH_REPO}" \
            "${WORKER_CONFIG}" || sph_die "无法更新 Worker systemd 用户服务"
        sph_ok "Worker unit 已更新"
        UNITS_REFRESHED=1
    else
        sph_warn "已安装 Worker unit，但缺少 ${WORKER_CONFIG}；跳过 Worker unit 更新"
    fi
fi

printf -- '\n--- 重启服务 ---\n'
RESTARTED=0
if sph_have_systemd_user; then
    if ((UNITS_REFRESHED == 1)); then
        sph_systemd_daemon_reload
    fi
    if sph_service_installed; then
        sph_systemd_restart
        sph_ok "systemd 用户服务已重启"
        RESTARTED=1
    fi
    if [[ -f "${WORKER_UNIT}" ]] && systemctl --user is-active --quiet "soda-worker.service"; then
        systemctl --user restart "soda-worker.service"
        sph_ok "Worker 用户服务已重启"
    fi
fi
if pid="$(sph_direct_pid)"; then
    "${SCRIPT_DIR}/stop.sh" >/dev/null
    "${SCRIPT_DIR}/start.sh" >/dev/null
    sph_ok "直接运行的实例已重启"
    RESTARTED=1
fi
if ((RESTARTED == 0)); then
    sph_info "当前没有运行中的实例；请用 start.sh 或 systemctl --user start 启动"
fi

printf -- '\n--- 健康检查 ---\n'
if ((RESTARTED == 1)); then
    if sph_wait_health 30; then
        sph_ok "服务已就绪：$(sph_health_url)"
    else
        sph_err "健康检查未通过"
        sph_info "排查：journalctl --user -u ${SPH_SERVICE_NAME} -n 50"
        exit 1
    fi
fi

printf -- '\n--- 用户数据核对 ---\n'
AFTER="$(sph_data_usage)"
printf '更新前: %s\n' "${BEFORE}"
printf '更新后: %s\n' "${AFTER}"
if [[ "${BEFORE}" == "${AFTER}" ]]; then
    sph_ok "资料库与数据库未发生改动（大小与 mtime 完全一致）"
else
    sph_warn "数据统计发生变化：若你刚在界面里写入内容属正常；否则请检查上面的差异"
fi

printf -- '\n===== 更新完成 =====\n'
printf '版本提交: %s\n' "${AFTER_COMMIT}"
