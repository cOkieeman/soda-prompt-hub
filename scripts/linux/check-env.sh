#!/usr/bin/env bash
#
# Soda Prompt Hub — Linux 开发环境检查器
#
# 只检查，不安装、不改系统。缺失项会给出简短的处理建议。
#
# 用法:
#   scripts/linux/check-env.sh            # 完整检查
#   scripts/linux/check-env.sh --quiet    # 只输出 WARN / FAIL 与总结
#   scripts/linux/check-env.sh --help
#
# 退出码: 0 = 无 FAIL；1 = 存在 FAIL

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=12
DEFAULT_PORT=8765

QUIET=0
OK_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
    C_OK="$(tput setaf 2)"
    C_WARN="$(tput setaf 3)"
    C_FAIL="$(tput setaf 1)"
    C_INFO="$(tput setaf 6)"
    C_OFF="$(tput sgr0)"
else
    C_OK=""
    C_WARN=""
    C_FAIL=""
    C_INFO=""
    C_OFF=""
fi

usage() {
    cat <<'USAGE'
Soda Prompt Hub — Linux 开发环境检查器

只检查，不安装、不改系统。缺失项会给出简短的处理建议。

用法:
  scripts/linux/check-env.sh            # 完整检查
  scripts/linux/check-env.sh --quiet    # 只输出 WARN / FAIL 与总结
  scripts/linux/check-env.sh --help

退出码: 0 = 无 FAIL；1 = 存在 FAIL
USAGE
}

report() {
    # $1 = color, $2 = tag, $3 = label, $4 = message, $5 = hint
    local color="$1" tag="$2" label="$3" message="${4:-}" hint="${5:-}"
    if [[ -n "${message}" ]]; then
        printf '%s%-6s%s %s — %s\n' "${color}" "${tag}" "${C_OFF}" "${label}" "${message}"
    else
        printf '%s%-6s%s %s\n' "${color}" "${tag}" "${C_OFF}" "${label}"
    fi
    [[ -z "${hint}" ]] || printf '       提示: %s\n' "${hint}"
}

ok() {
    OK_COUNT=$((OK_COUNT + 1))
    [[ "${QUIET}" -eq 1 ]] || report "${C_OK}" "[OK]" "$1" "${2:-}" ""
}

warn() {
    WARN_COUNT=$((WARN_COUNT + 1))
    report "${C_WARN}" "[WARN]" "$1" "${2:-}" "${3:-}"
}

fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    report "${C_FAIL}" "[FAIL]" "$1" "${2:-}" "${3:-}"
}

info() {
    [[ "${QUIET}" -eq 1 ]] || report "${C_INFO}" "[INFO]" "$1" "${2:-}" ""
}

section() {
    [[ "${QUIET}" -eq 1 ]] || printf '\n--- %s ---\n' "$1"
}

have() { command -v "$1" >/dev/null 2>&1; }

version_of() {
    # $1 = command, prints first line of --version, trimmed
    { "$1" --version 2>/dev/null || true; } | head -n1 | tr -d '\r'
}

for arg in "$@"; do
    case "${arg}" in
        -q | --quiet) QUIET=1 ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            printf 'unknown argument: %s\n' "${arg}" >&2
            usage >&2
            exit 2
            ;;
    esac
done

printf 'Soda Prompt Hub — Linux 开发环境检查\n'
printf '时间: %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
printf '项目: %s\n' "${PROJECT_ROOT}"

# ---------------------------------------------------------------- 1. 操作系统
section "操作系统"

KERNEL="$(uname -r)"
ARCH="$(uname -m)"

if [[ "$(uname -s)" == "Linux" ]]; then
    ok "Linux" "kernel ${KERNEL}"
else
    fail "Linux" "当前系统不是 Linux ($(uname -s))" "本项目要求 Linux，或使用 WSL2 Ubuntu"
fi

case "${ARCH}" in
    x86_64 | amd64) ok "Architecture" "${ARCH}（目标架构）" ;;
    aarch64 | arm64) warn "Architecture" "${ARCH}" "当前 CI 与发行目标是 x86_64，arm64 未经验证" ;;
    *) fail "Architecture" "${ARCH}" "仅验证过 x86_64 / aarch64" ;;
esac

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    DISTRO="$(. /etc/os-release && printf '%s' "${PRETTY_NAME:-${NAME:-unknown}}")"
    info "Distribution" "${DISTRO}"
    case "${DISTRO}" in
        *Ubuntu* | *Debian*) : ;;
        *) warn "Distribution" "${DISTRO}" "官方 Linux CI 基线是 Ubuntu；其他发行版按“实验”对待" ;;
    esac
else
    warn "Distribution" "/etc/os-release 不可读" "无法确认发行版"
fi

IS_WSL=0
if [[ -n "${WSL_DISTRO_NAME:-}" ]] || grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null; then
    IS_WSL=1
    info "Environment" "WSL2（${WSL_DISTRO_NAME:-未命名发行版}）"
    if mountpoint -q /mnt/c 2>/dev/null || [[ -d /mnt/c/Windows ]]; then
        info "Windows 访问" "/mnt/c 可用"
    else
        warn "Windows 访问" "/mnt/c 不可用" "如需读取 Windows 文件，请确认 /mnt 挂载正常"
    fi
    if [[ -z "${WSL_INTEROP:-}" ]]; then
        info "WSL" "未在互操作会话中（由 wsl.exe 直接启动时才设置，属正常）"
    fi
fi

# ---------------------------------------------------------------- 2. 基础工具
section "基础工具"

for tool in curl git xdg-open; do
    case "${tool}" in
        xdg-open)
            if have xdg-open; then
                ok "文件管理器" "xdg-open 可用"
            else
                warn "文件管理器" "缺少 xdg-open" \
                    "“打开所在文件夹”在 Linux 上依赖它；无桌面会话的 WSL2 属预期缺失"
            fi
            ;;
        *)
            if have "${tool}"; then
                ok "${tool}" "$(version_of "${tool}")"
            else
                fail "${tool}" "未找到" "sudo apt install -y ${tool}"
            fi
            ;;
    esac
done

if have git; then
    GIT_NAME="$(git config --global user.name 2>/dev/null || true)"
    GIT_EMAIL="$(git config --global user.email 2>/dev/null || true)"
    if [[ -n "${GIT_NAME}" && -n "${GIT_EMAIL}" ]]; then
        ok "Git identity" "${GIT_NAME} <${GIT_EMAIL}>"
    else
        warn "Git identity" "Git identity not configured" \
            "本脚本不会代填；请自行执行 git config --global user.name / user.email"
    fi
fi

# ---------------------------------------------------------------- 3. Python / uv
section "Python 与 uv"

if have python3; then
    PY_VERSION="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo unknown)"
    PY_MAJOR="$(python3 -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo 0)"
    PY_MINOR="$(python3 -c 'import sys; print(sys.version_info[1])' 2>/dev/null || echo 0)"
    if [[ "${PY_MAJOR}" -gt "${REQUIRED_PYTHON_MAJOR}" ]] ||
        { [[ "${PY_MAJOR}" -eq "${REQUIRED_PYTHON_MAJOR}" ]] && [[ "${PY_MINOR}" -ge "${REQUIRED_PYTHON_MINOR}" ]]; }; then
        ok "Python" "python3 ${PY_VERSION} ($(command -v python3))"
    else
        warn "Python" "python3 ${PY_VERSION} 低于项目要求 ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}" \
            "不需要动系统 Python；交给 uv 管理即可（uv python install ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}）"
    fi
else
    warn "Python" "未找到 python3" "sudo apt install -y python3；项目依赖由 uv 管理"
fi

if have uv; then
    ok "uv" "$(version_of uv) ($(command -v uv))"
else
    fail "uv" "未找到" "curl -LsSf https://astral.sh/uv/install.sh | sh（或 pipx/包管理器安装）"
fi

if have python3; then
    if python3 -c 'import venv' >/dev/null 2>&1; then
        ok "venv 模块" "可用"
    else
        warn "venv 模块" "python3 -m venv 不可用" "sudo apt install -y python3-venv"
    fi
fi

# ---------------------------------------------------------------- 4. systemd
section "systemd"

if have systemctl; then
    ok "systemctl" "$(systemctl --version 2>/dev/null | head -n1 | tr -d '\r')"

    if [[ -d /run/systemd/system ]]; then
        ok "systemd 运行中" "PID 1 = $(ps -p 1 -o comm= 2>/dev/null || echo systemd)"
        SYSTEM_STATE="$(systemctl is-system-running 2>/dev/null || true)"
        case "${SYSTEM_STATE}" in
            running | degraded) info "系统状态" "${SYSTEM_STATE}" ;;
            "") warn "系统状态" "systemctl is-system-running 无输出" "确认 systemd 已启动" ;;
            *) warn "系统状态" "${SYSTEM_STATE}" "非 running 状态可能影响服务测试" ;;
        esac
    else
        fail "systemd 运行中" "/run/systemd/system 不存在（系统由其他 init 启动）" \
            "WSL2 下在 /etc/wsl.conf 写入 [boot] systemd=true 后执行 wsl --shutdown 并重新进入"
    fi

    if systemctl --user list-units >/dev/null 2>&1; then
        ok "systemctl --user" "可用（可测试 systemd user service）"
        if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
            info "XDG_RUNTIME_DIR" "${XDG_RUNTIME_DIR}"
        else
            warn "XDG_RUNTIME_DIR" "未设置" "systemd --user 可能无法保持会话；确认登录会话或 loginctl enable-linger"
        fi
    else
        fail "systemctl --user" "不可用" \
            "通常表示没有用户级 systemd 会话（WSL2 需 systemd=true 且通过登录会话进入）"
    fi
else
    fail "systemctl" "未找到" "当前环境没有 systemd，无法进行服务化验证"
fi

# ---------------------------------------------------------------- 5. 项目
section "项目"

if [[ -f "${PROJECT_ROOT}/pyproject.toml" ]]; then
    PROJECT_VERSION="$(sed -n 's/^version *= *"\(.*\)"/\1/p' "${PROJECT_ROOT}/pyproject.toml" | head -n1)"
    ok "项目" "prompt-hub ${PROJECT_VERSION:-unknown}"
else
    fail "项目" "${PROJECT_ROOT}/pyproject.toml 不存在" "确认已经在 soda-prompt-hub 仓库根目录运行本脚本"
fi

for path in uv.lock src/prompt_hub .github; do
    if [[ -e "${PROJECT_ROOT}/${path}" ]]; then
        ok "存在" "${path}"
    else
        warn "缺少" "${path}" "仓库内容不完整，检查 clone 是否成功"
    fi
done

if [[ -d "${PROJECT_ROOT}/.git" ]] && have git; then
    BRANCH="$(git -C "${PROJECT_ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
    HEAD_SHA="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    ok "Git 工作区" "branch=${BRANCH} head=${HEAD_SHA}"
    if git -C "${PROJECT_ROOT}" remote get-url upstream >/dev/null 2>&1; then
        info "upstream" "$(git -C "${PROJECT_ROOT}" remote get-url upstream)"
    else
        warn "upstream remote" "未配置" "git remote add upstream https://github.com/cOkieeman/soda-prompt-hub.git"
    fi
    if git -C "${PROJECT_ROOT}" remote get-url origin >/dev/null 2>&1; then
        info "origin" "$(git -C "${PROJECT_ROOT}" remote get-url origin)"
    fi
fi

if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    VENV_PY="$("${PROJECT_ROOT}/.venv/bin/python" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo unknown)"
    ok "虚拟环境" ".venv (Python ${VENV_PY})"
    MISSING_MODULES=""
    for module in fastapi uvicorn pytest; do
        if ! "${PROJECT_ROOT}/.venv/bin/python" -c "import ${module}" >/dev/null 2>&1; then
            MISSING_MODULES="${MISSING_MODULES} ${module}"
        fi
    done
    if [[ -z "${MISSING_MODULES}" ]]; then
        ok "依赖" "fastapi / uvicorn / pytest 均可导入"
    else
        fail "依赖" "缺少模块:${MISSING_MODULES}" "在项目根目录执行 uv sync"
    fi
else
    warn "虚拟环境" ".venv 不存在或不可执行" "在项目根目录执行 uv sync"
fi

# ---------------------------------------------------------------- 6. 数据目录
section "数据目录"

LIBRARY_ROOT="${PROMPT_HUB_LIBRARY_ROOT:-}"
MODELS_ROOT="${PROMPT_HUB_MODELS_ROOT:-}"

check_writable_dir() {
    # $1 = label, $2 = path, $3 = 建议
    local label="$1" path="$2" hint="$3" probe
    if [[ -z "${path}" ]]; then
        warn "${label}" "未设置" "${hint}"
        return
    fi
    if mkdir -p -- "${path}" 2>/dev/null &&
        probe="$(mktemp -- "${path%/}/.check-env-XXXXXX" 2>/dev/null)"; then
        rm -f -- "${probe}"
        ok "${label}" "${path}（可写）"
    else
        fail "${label}" "${path} 不可创建或不可写" "检查目录权限与所在文件系统"
    fi
}

check_writable_dir "资料库目录" "${LIBRARY_ROOT}" \
    "未设置；程序会回退到 ~/Documents/Soda Prompt Hub/prompt-library（不符合 Linux XDG 习惯）"
check_writable_dir "模型目录" "${MODELS_ROOT}" \
    "未设置；程序会回退到 <资料库父目录>/models"

if [[ -n "${LIBRARY_ROOT}" ]] && [[ "${LIBRARY_ROOT}" == /mnt/* ]]; then
    warn "资料库位置" "${LIBRARY_ROOT} 位于 /mnt/* " "跨文件系统访问较慢，建议放在 Linux 原生文件系统"
fi

# ---------------------------------------------------------------- 7. 运行条件
section "运行条件"

if have ss; then
    if ss -ltn 2>/dev/null | grep -qE "[:.]${DEFAULT_PORT}\b"; then
        warn "端口 ${DEFAULT_PORT}" "已被占用" "若有旧实例先停止，或改用 --port 指定其他端口"
    else
        ok "端口 ${DEFAULT_PORT}" "空闲"
    fi
elif have python3; then
    if python3 - "${DEFAULT_PORT}" <<'PY' >/dev/null 2>&1
import socket, sys
s = socket.socket()
s.settimeout(0.5)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
    then
        warn "端口 ${DEFAULT_PORT}" "已有服务在监听（可能正在运行）" ""
    else
        ok "端口 ${DEFAULT_PORT}" "空闲"
    fi
fi

if have curl; then
    if curl -fsS --max-time 3 "http://127.0.0.1:${DEFAULT_PORT}/api/health" >/dev/null 2>&1; then
        ok "健康检查" "http://127.0.0.1:${DEFAULT_PORT}/api/health 返回成功"
    else
        info "健康检查" "服务未运行（未启动时属正常）"
    fi
fi

DISK_TARGET="${LIBRARY_ROOT:-${HOME}}"
if [[ -d "${DISK_TARGET}" ]]; then
    FREE_KB="$(df -Pk -- "${DISK_TARGET}" 2>/dev/null | awk 'NR==2 {print $4}' || true)"
    if [[ -n "${FREE_KB}" ]]; then
        FREE_GB=$((FREE_KB / 1024 / 1024))
        if [[ "${FREE_GB}" -lt 5 ]]; then
            warn "磁盘空间" "${DISK_TARGET} 剩余约 ${FREE_GB} GB" "资料库与模型需要空间，建议先清理"
        else
            ok "磁盘空间" "${DISK_TARGET} 剩余约 ${FREE_GB} GB"
        fi
    fi
fi

# ---------------------------------------------------------------- 总结
printf '\n===== 总结 =====\n'
printf 'OK: %d   WARN: %d   FAIL: %d\n' "${OK_COUNT}" "${WARN_COUNT}" "${FAIL_COUNT}"

if [[ "${FAIL_COUNT}" -gt 0 ]]; then
    printf '结果: 环境尚未就绪，请先处理上面的 [FAIL] 项。\n'
    exit 1
fi

if [[ "${WARN_COUNT}" -gt 0 ]]; then
    printf '结果: 可以使用，但存在 %d 项提醒。\n' "${WARN_COUNT}"
else
    printf '结果: 环境检查全部通过。\n'
fi

printf '下一步: uv sync && uv run pytest && uv run --no-sync prompt-hub serve --host 127.0.0.1 --port %d\n' "${DEFAULT_PORT}"
