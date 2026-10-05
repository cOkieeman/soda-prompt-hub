#!/usr/bin/env bash
#
# Soda Prompt Hub — Linux 部署脚本共用函数。
#
# 本文件只提供函数与常量，不设置 shell 选项、不执行任何动作。
# 由 deploy/linux/*.sh 通过 source 加载；调用方负责 set -Eeuo pipefail。

SPH_SERVICE_NAME="soda-prompt-hub"
SPH_DEFAULT_HOST="127.0.0.1"
SPH_DEFAULT_PORT="8765"

# ---------------------------------------------------------------- 输出
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
    SPH_C_OK="$(tput setaf 2)"
    SPH_C_WARN="$(tput setaf 3)"
    SPH_C_ERR="$(tput setaf 1)"
    SPH_C_INFO="$(tput setaf 6)"
    SPH_C_OFF="$(tput sgr0)"
else
    SPH_C_OK=""
    SPH_C_WARN=""
    SPH_C_ERR=""
    SPH_C_INFO=""
    SPH_C_OFF=""
fi

sph_ok() { printf '%s[ OK ]%s %s\n' "${SPH_C_OK}" "${SPH_C_OFF}" "$*"; }
sph_info() { printf '%s[INFO]%s %s\n' "${SPH_C_INFO}" "${SPH_C_OFF}" "$*"; }
sph_warn() { printf '%s[WARN]%s %s\n' "${SPH_C_WARN}" "${SPH_C_OFF}" "$*" >&2; }
sph_err() { printf '%s[FAIL]%s %s\n' "${SPH_C_ERR}" "${SPH_C_OFF}" "$*" >&2; }
sph_die() {
    sph_err "$*"
    exit 1
}

# ---------------------------------------------------------------- 路径
# 仓库根目录（本文件位于 <repo>/deploy/linux/lib.sh）
sph_repo_root() {
    local dir
    dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
    printf '%s' "${dir}"
}

sph_data_home() {
    printf '%s' "${XDG_DATA_HOME:-${HOME}/.local/share}/soda-prompt-hub"
}

sph_install_env_path() {
    printf '%s/install.env' "$(sph_data_home)"
}

sph_unit_path() {
    printf '%s/systemd/user/%s.service' "${XDG_CONFIG_HOME:-${HOME}/.config}" "${SPH_SERVICE_NAME}"
}

sph_launcher_path() {
    printf '%s/.local/bin/soda-prompt-hub' "${HOME}"
}

sph_desktop_entry_path() {
    printf '%s/applications/soda-prompt-hub.desktop' "${XDG_DATA_HOME:-${HOME}/.local/share}"
}

sph_desktop_icon_path() {
    printf '%s/icons/hicolor/256x256/apps/soda-prompt-hub.png' \
        "${XDG_DATA_HOME:-${HOME}/.local/share}"
}

sph_desktop_log_path() {
    printf '%s/logs/launcher.log' "$(sph_data_home)"
}

sph_worker_launcher_path() {
    printf '%s/.local/bin/soda-worker' "${HOME}"
}

sph_worker_config_path() {
    printf '%s/worker-config.json' "$(sph_data_home)"
}

sph_worker_share_root() {
    printf '%s/worker-share' "$(sph_data_home)"
}

sph_worker_unit_path() {
    printf '%s/systemd/user/soda-worker.service' "${XDG_CONFIG_HOME:-${HOME}/.config}"
}

sph_runtime_dir() {
    printf '%s' "${XDG_RUNTIME_DIR:-/tmp}"
}

sph_pid_file() {
    printf '%s/%s.pid' "$(sph_runtime_dir)" "${SPH_SERVICE_NAME}"
}

sph_abs_path() {
    # 把相对路径转成绝对路径（不要求目标存在）
    local path="$1"
    case "${path}" in
        /*) printf '%s' "${path}" ;;
        "~"/*) printf '%s%s' "${HOME}" "${path#\~}" ;;
        *) printf '%s/%s' "$(pwd)" "${path}" ;;
    esac
}

sph_desktop_exec_quote() {
    # Desktop Entry 的 Exec 使用自己的参数语法；引号内的这些字符仍需反斜杠转义，
    # 百分号则必须写成 %% 才不会被当作 field code。
    local value="$1"
    case "${value}" in
        *$'\n'* | *$'\r'*)
            sph_err "Desktop Entry 路径不能包含换行符"
            return 1
            ;;
    esac
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//\`/\\\`}"
    value="${value//\$/\\\$}"
    value="${value//%/%%}"
    printf '"%s"' "${value}"
}

sph_write_desktop_entry() {
    local template="$1" output="$2" launcher="$3"
    local line launcher_exec
    [[ -f "${template}" ]] || {
        sph_err "缺少 Desktop Entry 模板：${template}"
        return 1
    }
    launcher_exec="$(sph_desktop_exec_quote "${launcher}")" || return 1
    mkdir -p "$(dirname -- "${output}")"
    while IFS= read -r line || [[ -n "${line}" ]]; do
        if [[ "${line}" == "Exec=__SPH_LAUNCHER_EXEC__ open" ]]; then
            printf 'Exec=%s open\n' "${launcher_exec}"
        else
            printf '%s\n' "${line}"
        fi
    done <"${template}" >"${output}"
    if grep -q "__SPH_LAUNCHER_EXEC__" "${output}"; then
        sph_err "Desktop Entry 模板仍有未替换占位符"
        rm -f "${output}"
        return 1
    fi
    chmod 0644 "${output}"
}

sph_install_desktop_integration() {
    local repo="$1"
    local entry icon launcher
    entry="$(sph_desktop_entry_path)"
    icon="$(sph_desktop_icon_path)"
    launcher="$(sph_launcher_path)"
    [[ -x "${launcher}" ]] || {
        sph_err "缺少已安装的便利命令：${launcher}"
        return 1
    }
    [[ -f "${repo}/deploy/linux/soda-prompt-hub.png" ]] || {
        sph_err "缺少桌面图标：${repo}/deploy/linux/soda-prompt-hub.png"
        return 1
    }
    mkdir -p "$(dirname -- "${icon}")"
    install -m 0644 "${repo}/deploy/linux/soda-prompt-hub.png" "${icon}"
    sph_write_desktop_entry \
        "${repo}/deploy/linux/soda-prompt-hub.desktop" \
        "${entry}" \
        "${launcher}" || return 1
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$(dirname -- "${entry}")" >/dev/null 2>&1 || true
    fi
}

sph_safe_purge_path() {
    # Resolve dot segments and symlinked parents before allowing recursive deletion.
    # Linux deployments rely on GNU realpath; -m also handles paths that disappeared
    # between reading install.env and running the uninstaller.
    local target="$1" canonical_target canonical_home
    command -v realpath >/dev/null 2>&1 || return 1
    canonical_target="$(realpath -m -- "${target}")" || return 1
    canonical_home="$(realpath -m -- "${HOME}")" || return 1
    case "${canonical_target}" in
        "${canonical_home}"/* | /mnt/*)
            printf '%s' "${canonical_target}"
            ;;
        *) return 1 ;;
    esac
}

# ---------------------------------------------------------------- 安装记录
# install.env 由 install.sh 写入，其余脚本读取。缺失时返回非零。
sph_load_install_env() {
    local env_file
    env_file="$(sph_install_env_path)"
    [[ -f "${env_file}" ]] || return 1
    # shellcheck disable=SC1090
    source "${env_file}"
    : "${SPH_REPO:?install.env 缺少 SPH_REPO}"
    : "${SPH_HOST:=${SPH_DEFAULT_HOST}}"
    : "${SPH_PORT:=${SPH_DEFAULT_PORT}}"
    return 0
}

sph_require_install_env() {
    sph_load_install_env || sph_die "未找到安装记录 $(sph_install_env_path)；请先运行 ./deploy/linux/install.sh"
    [[ -d "${SPH_REPO}" ]] || sph_die "安装记录指向的目录不存在：${SPH_REPO}（请重新运行 install.sh）"
}

# ---------------------------------------------------------------- 环境探测
sph_require_linux() {
    [[ "$(uname -s)" == "Linux" ]] || sph_die "该脚本只支持 Linux（当前：$(uname -s)）"
}

sph_require_cmd() {
    command -v "$1" >/dev/null 2>&1 || sph_die "缺少命令：$1${2:+（$2）}"
}

sph_have_systemd_user() {
    command -v systemctl >/dev/null 2>&1 || return 1
    [[ -d /run/systemd/system ]] || return 1
    systemctl --user list-units >/dev/null 2>&1
}

sph_service_installed() {
    [[ -f "$(sph_unit_path)" ]]
}

sph_service_active() {
    sph_have_systemd_user || return 1
    systemctl --user is-active --quiet "${SPH_SERVICE_NAME}.service"
}

sph_service_state() {
    # 输出 systemd 的 ActiveState，或 "unavailable" / "not-installed"
    if sph_service_installed; then
        if sph_have_systemd_user; then
            systemctl --user show -p ActiveState --value "${SPH_SERVICE_NAME}.service" 2>/dev/null || echo unknown
        else
            echo "unavailable"
        fi
    else
        echo "not-installed"
    fi
}

# ---------------------------------------------------------------- 运行与健康检查
sph_venv_python() {
    printf '%s/.venv/bin/python' "${SPH_REPO}"
}

sph_serve_command() {
    # 优先使用虚拟环境里的入口脚本，避免运行时依赖 uv
    if [[ -x "${SPH_REPO}/.venv/bin/prompt-hub" ]]; then
        printf '%s' "${SPH_REPO}/.venv/bin/prompt-hub"
    else
        printf 'uv'
    fi
}

sph_client_host() {
    local host="${SPH_HOST:-${SPH_DEFAULT_HOST}}"
    case "${host}" in
        "::") printf '[::1]' ;;
        *:*) printf '[%s]' "${host}" ;;
        *) printf '%s' "${host}" ;;
    esac
}

sph_app_url() {
    printf 'http://%s:%s' "$(sph_client_host)" "${SPH_PORT:-${SPH_DEFAULT_PORT}}"
}

sph_health_url() {
    printf '%s/api/health' "$(sph_app_url)"
}

sph_health_ok() {
    local url
    url="$(sph_health_url)"
    command -v curl >/dev/null 2>&1 || return 1
    curl -fsS --max-time 3 "${url}" 2>/dev/null | grep -q '"status"'
}

sph_wait_health() {
    # $1 = 等待秒数（默认 20）
    local timeout="${1:-20}" waited=0
    command -v curl >/dev/null 2>&1 || return 2
    while ((waited < timeout)); do
        if sph_health_ok; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

sph_direct_pid() {
    local pid_file
    pid_file="$(sph_pid_file)"
    [[ -f "${pid_file}" ]] || return 1
    local pid
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    [[ -n "${pid}" ]] || return 1
    kill -0 "${pid}" 2>/dev/null || return 1
    printf '%s' "${pid}"
}

sph_data_usage() {
    # 用于 update.sh 证明用户数据未被改动：数据库大小 + mtime + 资料库字节数
    local library="${SPH_LIBRARY_ROOT:-$(sph_data_home)/library}"
    local db="${library}/database/prompt-library.sqlite"
    if [[ -f "${db}" ]]; then
        printf 'db_size=%s db_mtime=%s library_bytes=%s' \
            "$(stat -c %s "${db}")" \
            "$(stat -c %Y "${db}")" \
            "$(du -sb "${library}" 2>/dev/null | cut -f1)"
    else
        printf 'db_size=absent db_mtime=absent library_bytes=%s' \
            "$(du -sb "${library}" 2>/dev/null | cut -f1 || echo 0)"
    fi
}

# ---------------------------------------------------------------- systemd 操作
sph_systemd_escape() {
    # Escape one systemd value. Percent is a specifier prefix in unit settings.
    local value="$1"
    case "${value}" in
        *$'\n'* | *$'\r'*)
            sph_err "systemd 配置值不能包含换行符"
            return 1
            ;;
    esac
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//%/%%}"
    printf '%s' "${value}"
}

sph_systemd_quote() {
    local value
    value="$(sph_systemd_escape "$1")" || return 1
    printf '"%s"' "${value}"
}

sph_systemd_exec_quote() {
    # ExecStart also expands $VAR; $$ passes a literal dollar sign.
    local value="$1"
    value="${value//\$/\$\$}"
    sph_systemd_quote "${value}"
}

sph_write_core_unit() {
    local template="$1" output="$2" repo="$3" library="$4" models="$5" host="$6" port="$7"
    local content repo_value library_env models_env core_exec host_value port_value
    [[ -f "${template}" ]] || {
        sph_err "缺少服务模板：${template}"
        return 1
    }
    content="$(<"${template}")"
    repo_value="$(sph_systemd_escape "${repo}")" || return 1
    library_env="$(sph_systemd_quote "PROMPT_HUB_LIBRARY_ROOT=${library}")" || return 1
    models_env="$(sph_systemd_quote "PROMPT_HUB_MODELS_ROOT=${models}")" || return 1
    core_exec="$(sph_systemd_exec_quote "${repo}/.venv/bin/prompt-hub")" || return 1
    host_value="$(sph_systemd_exec_quote "${host}")" || return 1
    port_value="$(sph_systemd_exec_quote "${port}")" || return 1
    content="${content//__SPH_REPO__/"${repo_value}"}"
    content="${content//__SPH_LIBRARY_ENV__/"${library_env}"}"
    content="${content//__SPH_MODELS_ENV__/"${models_env}"}"
    content="${content//__SPH_CORE_EXEC__/"${core_exec}"}"
    content="${content//__SPH_HOST__/"${host_value}"}"
    content="${content//__SPH_PORT__/"${port_value}"}"
    printf '%s\n' "${content}" >"${output}"
    chmod 0644 "${output}"
}

sph_write_worker_unit() {
    local template="$1" output="$2" repo="$3" config="$4"
    local content repo_value worker_python config_value
    [[ -f "${template}" ]] || {
        sph_err "缺少 Worker 服务模板：${template}"
        return 1
    }
    content="$(<"${template}")"
    repo_value="$(sph_systemd_escape "${repo}")" || return 1
    worker_python="$(sph_systemd_exec_quote "${repo}/.venv/bin/python")" || return 1
    config_value="$(sph_systemd_exec_quote "${config}")" || return 1
    content="${content//__SPH_REPO__/"${repo_value}"}"
    content="${content//__SPH_WORKER_PYTHON__/"${worker_python}"}"
    content="${content//__SPH_WORKER_CONFIG__/"${config_value}"}"
    printf '%s\n' "${content}" >"${output}"
    chmod 0644 "${output}"
}

sph_systemd_start() {
    systemctl --user start "${SPH_SERVICE_NAME}.service"
}

sph_systemd_stop() {
    systemctl --user stop "${SPH_SERVICE_NAME}.service"
}

sph_systemd_restart() {
    systemctl --user restart "${SPH_SERVICE_NAME}.service"
}

sph_systemd_enable() {
    systemctl --user enable "${SPH_SERVICE_NAME}.service" >/dev/null
}

sph_systemd_daemon_reload() {
    systemctl --user daemon-reload
}
