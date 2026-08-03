#!/bin/bash
# ZeroPanel v2.0 统一安装入口
# 自动检测环境并调用对应版本的安装脚本

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

print_separator() {
    echo -e "${CYAN}══════════════════════════════════════════════════════════════════${NC}"
}

print_title() {
    print_separator
    echo -e "                    ${WHITE}ZeroPanel v2.0${NC}"
    echo -e "                ${CYAN}智能环境安装入口${NC}"
    print_separator
}

# 检测环境类型
detect_environment() {
    local distro=""

    if [ -f "/etc/os-release" ]; then
        distro=$(grep -E '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
    fi

    if [ "$distro" = "debian" ] || [ "$distro" = "ubuntu" ]; then
        echo "proot"
        return
    fi

    if [ -n "$TERMUX_VERSION" ] || [ -n "$PREFIX" ] && [[ "$PREFIX" == *"com.termux"* ]] || [ -d "/data/data/com.termux" ]; then
        echo "termux"
        return
    fi

    echo "unsupported"
}

main() {
    print_title
    echo ""

    local env_type
    env_type=$(detect_environment)

    case "$env_type" in
        proot)
            echo -e "  ${GREEN}检测到 Proot (Ubuntu/Debian) 环境${NC}"
            echo -e "  ${WHITE}将下载并执行 Proot 高级版安装脚本${NC}"
            echo ""

            local tmp_script
            tmp_script=$(mktemp)
            if curl -fsSL -o "$tmp_script" "https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel-proot/install.sh"; then
                chmod +x "$tmp_script"
                bash "$tmp_script" "$@"
                rm -f "$tmp_script"
            else
                echo -e "  ${RED}下载 Proot 版安装脚本失败，请检查网络${NC}"
                exit 1
            fi
            ;;
        termux)
            echo -e "  ${GREEN}检测到 Termux / ZeroTermux 环境${NC}"
            echo -e "  ${WHITE}将下载并执行 Termux 轻量版安装脚本${NC}"
            echo ""

            local tmp_script
            tmp_script=$(mktemp)
            if curl -fsSL -o "$tmp_script" "https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel/install.sh"; then
                chmod +x "$tmp_script"
                bash "$tmp_script" "$@"
                rm -f "$tmp_script"
            else
                echo -e "  ${RED}下载 Termux 版安装脚本失败，请检查网络${NC}"
                exit 1
            fi
            ;;
        unsupported)
            echo -e "  ${RED}错误：当前环境不受支持${NC}"
            echo ""
            echo -e "  ${WHITE}ZeroPanel 支持以下环境：${NC}"
            echo -e "    ${CYAN}1. ZeroTermux / Termux${NC}（Android 终端模拟器）"
            echo -e "    ${CYAN}2. Proot 容器内的 Ubuntu / Debian${NC}"
            echo ""
            echo -e "  ${YELLOW}请根据环境选择对应版本：${NC}"
            echo -e "    ${CYAN}Termux:${NC}  bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel/install.sh)"
            echo -e "    ${CYAN}Proot:${NC}   bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel-proot/install.sh)"
            echo ""
            exit 1
            ;;
    esac
}

main "$@"
