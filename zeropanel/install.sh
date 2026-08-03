#!/data/data/com.termux/files/usr/bin/bash
# ZeroPanel v2.0 - Termux / ZeroTermux 轻量版安装脚本
# 仅适用于 Termux 环境

set -e
set -o pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# 固定路径
PANEL_DIR="$HOME/zeropanel"
WWW_DIR="$HOME/www"
DATA_DIR="$PANEL_DIR/data"
PANEL_DOWNLOAD_URL="https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel_v2.zip"

# 打印分隔线
print_separator() {
    echo -e "${CYAN}══════════════════════════════════════════════════════════════════${NC}"
}

# 打印标题
print_title() {
    print_separator
    echo -e "                    ${WHITE}ZeroPanel v2.0${NC}"
    echo -e "                ${CYAN}Termux / ZeroTermux 轻量版${NC}"
    print_separator
}

# 打印步骤信息
print_step() {
    local step=$1
    local total=$2
    local message=$3
    echo -e "\n${BLUE}[${step}/${total}]${NC} ${WHITE}${message}${NC}"
}

print_success() { echo -e "  ${GREEN}✓${NC} $1"; }
print_warning() { echo -e "  ${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "  ${RED}✗${NC} $1"; }

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

detect_python_cmd() {
    if command_exists python3; then
        echo "python3"
    elif command_exists python; then
        echo "python"
    else
        echo ""
    fi
}

# 环境校验
check_termux_environment() {
    if [ -z "$PREFIX" ]; then
        PREFIX="/data/data/com.termux/files/usr"
        export PREFIX
    fi

    if [ -n "$TERMUX_VERSION" ] || [[ "$PREFIX" == *"com.termux"* ]] || [ -d "/data/data/com.termux" ]; then
        return 0
    fi

    echo ""
    print_error "当前环境不是 Termux / ZeroTermux"
    echo ""
    echo -e "  ${WHITE}本脚本仅支持 Termux / ZeroTermux 环境${NC}"
    echo -e "  ${WHITE}Proot (Ubuntu/Debian) 请使用 zeropanel-proot 版本的安装脚本${NC}"
    echo ""
    exit 1
}

# 卸载流程
uninstall_termux() {
    print_title
    echo ""
    echo -e "  ${YELLOW}卸载 ZeroPanel (Termux 轻量版)${NC}"
    echo ""
    read -p "确定要卸载吗？数据将备份到 ~/zeropanel_data_backup_*. [y/N]: " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        echo -e "  ${CYAN}停止相关服务...${NC}"
        pkill -f "python3 app.py" 2>/dev/null || true
        pkill -f "python app.py" 2>/dev/null || true
        nginx -s stop 2>/dev/null || true
        pkill -x mysqld 2>/dev/null || true
        pkill -x mariadbd 2>/dev/null || true
        pkill -f php-fpm 2>/dev/null || true

        if [ -d "$HOME/zeropanel/data" ]; then
            local backup_dir="$HOME/zeropanel_data_backup_$(date +%Y%m%d%H%M%S)"
            echo -e "  ${YELLOW}备份数据到 $backup_dir${NC}"
            cp -r "$HOME/zeropanel/data" "$backup_dir"
        fi

        echo -e "  ${CYAN}删除面板文件...${NC}"
        rm -rf "$HOME/zeropanel"
        rm -rf "$HOME/www"
        rm -f "$PREFIX/etc/nginx/conf.d/zeropanel*.conf"
        rm -f "$HOME/bin/zeropanel"

        echo ""
        print_separator
        echo -e "              ${GREEN}ZeroPanel 已卸载${NC}"
        print_separator
        echo ""
        [ -n "${backup_dir:-}" ] && echo -e "  ${YELLOW}数据备份: $backup_dir${NC}"
    else
        echo -e "  ${YELLOW}已取消卸载${NC}"
    fi
}

# 安装流程
install_termux() {
    local total_steps=9

    # 步骤 1: 更新软件源
    print_step 1 $total_steps "更新软件源"
    echo -e "  ${CYAN}正在更新包管理器...${NC}"
    if pkg update -y 2>&1 | tail -n 5; then
        print_success "软件源更新完成"
    else
        print_error "软件源更新失败"
        exit 1
    fi

    # 步骤 2: 安装系统依赖
    print_step 2 $total_steps "安装系统依赖"
    echo -e "  ${CYAN}正在安装 Python、Nginx、MariaDB、PHP-FPM、curl、unzip...${NC}"
    if pkg install -y python nginx mariadb php-fpm curl unzip zip 2>&1 | tail -n 3; then
        print_success "系统依赖安装完成"
    else
        print_error "系统依赖安装失败"
        exit 1
    fi

    # 步骤 3: 下载面板
    print_step 3 $total_steps "下载面板文件"
    echo -e "  ${CYAN}正在从 GitHub 下载 ZeroPanel...${NC}"
    echo -e "    下载地址: ${WHITE}$PANEL_DOWNLOAD_URL${NC}"

    local tmp_dir=$(mktemp -d)
    local zip_file="$tmp_dir/zeropanel_v2.zip"

    if curl -fsSL -o "$zip_file" "$PANEL_DOWNLOAD_URL"; then
        print_success "面板文件下载完成"
    else
        print_error "面板文件下载失败，请检查网络连接"
        rm -rf "$tmp_dir"
        exit 1
    fi

    # 步骤 4: 解压面板
    print_step 4 $total_steps "部署面板"
    echo -e "  ${CYAN}正在解压到 $PANEL_DIR...${NC}"

    if [ -d "$PANEL_DIR" ]; then
        if [ -d "$PANEL_DIR/data" ]; then
            local backup_dir="$HOME/zeropanel_data_backup_$(date +%Y%m%d%H%M%S)"
            echo -e "  ${YELLOW}检测到旧面板目录，备份数据到 $backup_dir${NC}"
            cp -r "$PANEL_DIR/data" "$backup_dir"
        fi
        rm -rf "$PANEL_DIR"
    fi

    mkdir -p "$PANEL_DIR"

    if unzip -q "$zip_file" -d "$HOME"; then
        print_success "面板部署完成"
    else
        print_error "面板解压失败"
        rm -rf "$tmp_dir"
        exit 1
    fi

    rm -rf "$tmp_dir"

    # 步骤 5: 安装 Python 依赖
    print_step 5 $total_steps "安装 Python 依赖"
    echo -e "  ${CYAN}正在安装 Flask 及相关库...${NC}"
    local pip_output
    if pip_output=$(pip3 install --break-system-packages flask flask-cors werkzeug 2>&1); then
        print_success "Python 依赖安装完成"
    elif pip_output=$(pip3 install flask flask-cors werkzeug 2>&1); then
        print_success "Python 依赖安装完成"
    else
        print_error "Python 依赖安装失败"
        echo "$pip_output" | tail -n 10
        exit 1
    fi

    # 步骤 6: 初始化 MariaDB
    print_step 6 $total_steps "初始化 MariaDB"
    echo -e "  ${CYAN}检查数据库目录...${NC}"
    if [ ! -d "$PREFIX/var/lib/mysql/mysql" ]; then
        echo -e "  ${CYAN}正在初始化数据库...${NC}"
        if mysql_install_db --ldata="$PREFIX/var/lib/mysql" 2>&1 | tail -n 2; then
            print_success "MariaDB 初始化完成"
        else
            print_error "MariaDB 初始化失败"
            exit 1
        fi
    else
        print_success "MariaDB 已初始化"
    fi

    # 步骤 7: 配置运行环境
    print_step 7 $total_steps "配置运行环境"
    echo -e "  ${CYAN}正在创建目录...${NC}"
    mkdir -p "$WWW_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$PREFIX/etc/nginx/conf.d"
    mkdir -p "$PREFIX/var/log/nginx"
    mkdir -p "$PREFIX/var/run"
    mkdir -p "$PREFIX/var/run/php-fpm"
    print_success "目录创建完成"

    echo -e "  ${CYAN}配置 PHP-FPM Socket...${NC}"
    PHP_FPM_POOL="$PREFIX/etc/php-fpm.d/www.conf"
    PHP_FPM_SOCK="$PREFIX/var/run/php-fpm.sock"

    if [ -f "$PHP_FPM_POOL" ]; then
        cp "$PHP_FPM_POOL" "$PHP_FPM_POOL.bak"
        sed -i "s|^listen =.*|listen = $PHP_FPM_SOCK|" "$PHP_FPM_POOL"
        print_success "PHP-FPM 已配置监听 $PHP_FPM_SOCK"
    else
        print_warning "未找到 $PHP_FPM_POOL，请确认 php-fpm 已正确安装"
    fi

    echo -e "  ${CYAN}写入 Nginx 配置...${NC}"
    NGINX_CONF="$PREFIX/etc/nginx/nginx.conf"

    if [ -f "$NGINX_CONF" ]; then
        cp "$NGINX_CONF" "$NGINX_CONF.bak"
    fi

    rm -f "$PREFIX/etc/nginx/conf.d/default.conf" 2>/dev/null || true
    rm -f "$PREFIX/etc/nginx/sites-enabled/default" 2>/dev/null || true

    cat > "$NGINX_CONF" << EOF
worker_processes 1;
error_log $PREFIX/var/log/nginx/error.log;
pid $PREFIX/var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include $PREFIX/etc/nginx/mime.types;
    default_type application/octet-stream;

    sendfile on;
    keepalive_timeout 65;
    client_max_body_size 100M;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    include $PREFIX/etc/nginx/conf.d/*.conf;
}
EOF
    print_success "Nginx 配置完成"

    # 步骤 8: 创建快捷命令
    print_step 8 $total_steps "配置快捷命令"
    echo -e "  ${CYAN}创建 zeropanel 命令...${NC}"

    mkdir -p "$HOME/bin"

    cat > "$HOME/bin/zeropanel" << 'SCRIPT'
#!/data/data/com.termux/files/usr/bin/bash

PANEL_DIR="$HOME/zeropanel"
LOG_FILE="$PANEL_DIR/data/panel.log"
DATA_DIR="$PANEL_DIR/data"

mkdir -p "$DATA_DIR"

python_cmd() {
    if command -v python3 >/dev/null 2>&1; then echo "python3";
    elif command -v python >/dev/null 2>&1; then echo "python";
    else echo ""; fi
}

check_service() {
    local pattern="$1"
    if ls /proc/[0-9]*/cmdline 2>/dev/null | xargs -r grep -l -z "$pattern" 2>/dev/null | head -1 > /dev/null; then
        echo -e "\033[0;32m运行中\033[0m"; return
    fi
    for pid_dir in /proc/[0-9]*; do
        [ -d "$pid_dir" ] || continue
        exe_link=$(readlink "$pid_dir/exe" 2>/dev/null || true)
        if [ -n "$exe_link" ] && (echo "$exe_link" | grep -qE "${pattern}$"); then
            echo -e "\033[0;32m运行中\033[0m"; return
        fi
    done
    echo -e "\033[0;31m已停止\033[0m"
}

check_panel() {
    local py_cmd=$(python_cmd)
    [ -n "$py_cmd" ] && pgrep -f "$py_cmd app.py" > /dev/null && echo -e "\033[0;32m运行中\033[0m" || echo -e "\033[0;31m已停止\033[0m"
}

case "$1" in
    start)
        echo -e "\033[1;37m启动 ZeroPanel...\033[0m"
        cd "$PANEL_DIR"
        PY_CMD=$(python_cmd)
        [ -z "$PY_CMD" ] && { echo "未找到 python3"; exit 1; }
        if ! pgrep -f "$PY_CMD app.py" > /dev/null; then
            nohup $PY_CMD app.py > "$LOG_FILE" 2>&1 &
            echo "  Panel 已启动"
        fi
        if ! pgrep -x mysqld > /dev/null && ! pgrep -x mariadbd > /dev/null; then
            if command -v mysqld_safe >/dev/null 2>&1; then nohup mysqld_safe > /dev/null 2>&1 &
            elif command -v mysqld >/dev/null 2>&1; then nohup mysqld > /dev/null 2>&1 &
            fi
            sleep 3
        fi
        if ! pgrep -f "php-fpm" > /dev/null; then php-fpm 2>/dev/null || true; fi
        if ! pgrep -x nginx > /dev/null; then nginx 2>/dev/null || true; fi
        echo -e "\033[0;36m访问: http://localhost:5000\033[0m"
        ;;
    stop)
        echo -e "\033[1;37m停止 ZeroPanel...\033[0m"
        PY_CMD=$(python_cmd)
        [ -n "$PY_CMD" ] && pkill -f "$PY_CMD app.py" 2>/dev/null || true
        nginx -s stop 2>/dev/null || true
        pkill -x mysqld 2>/dev/null || true
        pkill -x mariadbd 2>/dev/null || true
        pkill -f php-fpm 2>/dev/null || true
        echo "  已停止"
        ;;
    restart)
        "$0" stop; sleep 2; "$0" start
        ;;
    status)
        echo -e "\033[1;37m服务状态:\033[0m"
        echo "  Panel:   $(check_panel)"
        echo "  Nginx:   $(check_service nginx)"
        echo "  MariaDB: $(check_service '(mysqld|mariadbd)')"
        echo "  PHP-FPM: $(check_service php-fpm)"
        ;;
    log)
        [ -f "$LOG_FILE" ] && tail -n 50 "$LOG_FILE" || echo "日志不存在"
        ;;
    uninstall)
        echo -e "\033[1;37m卸载 ZeroPanel...\033[0m"
        read -p "确定要卸载吗？数据将备份到 ~/zeropanel_data_backup_*. [y/N]: " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            "$0" stop
            if [ -d "$PANEL_DIR/data" ]; then
                backup_dir="$HOME/zeropanel_data_backup_$(date +%Y%m%d%H%M%S)"
                echo "  备份数据到 $backup_dir"
                cp -r "$PANEL_DIR/data" "$backup_dir"
            fi
            rm -rf "$PANEL_DIR"
            rm -rf "$HOME/www"
            rm -f "$PREFIX/etc/nginx/conf.d/zeropanel*.conf"
            rm -f "$HOME/bin/zeropanel"
            echo -e "\033[0;32mZeroPanel 已卸载\033[0m"
        else
            echo "已取消"
        fi
        ;;
    help|*)
        echo "用法: zeropanel {start|stop|restart|status|log|uninstall|help}"
        ;;
esac
SCRIPT

    chmod +x "$HOME/bin/zeropanel"
    print_success "快捷命令创建完成"

    touch "$HOME/.bashrc"
    if ! grep -q 'export PATH="$HOME/bin:$PATH"' "$HOME/.bashrc"; then
        echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
    fi
    export PATH="$HOME/bin:$PATH"

    # 步骤 9: 启动服务
    print_step 9 $total_steps "启动服务"
    PY_CMD=$(detect_python_cmd)

    if ! pgrep -x mysqld > /dev/null && ! pgrep -x mariadbd > /dev/null; then
        echo -e "  ${CYAN}启动 MariaDB...${NC}"
        if command_exists mysqld_safe; then nohup mysqld_safe > /dev/null 2>&1 &
        elif command_exists mysqld; then nohup mysqld > /dev/null 2>&1 &
        else print_warning "未找到 MariaDB 启动命令"; fi
        sleep 3
    fi

    if ! pgrep -f php-fpm > /dev/null; then
        echo -e "  ${CYAN}启动 PHP-FPM...${NC}"
        php-fpm 2>/dev/null || print_warning "PHP-FPM 启动失败"
    fi

    if ! pgrep -x nginx > /dev/null; then
        echo -e "  ${CYAN}启动 Nginx...${NC}"
        nginx 2>/dev/null || print_warning "Nginx 启动失败"
    fi

    if [ -n "$PY_CMD" ] && ! pgrep -f "$PY_CMD app.py" > /dev/null; then
        echo -e "  ${CYAN}启动 ZeroPanel...${NC}"
        cd "$PANEL_DIR"
        nohup "$PY_CMD" app.py > "$DATA_DIR/panel.log" 2>&1 &
        sleep 2
    fi

    print_success "服务启动完成"
}

# 主流程
main() {
    clear
    print_title
    echo ""

    # 卸载模式
    case "$1" in
        --uninstall|uninstall|-u)
            check_termux_environment
            uninstall_termux
            return
            ;;
    esac

    echo -e "  ${WHITE}欢迎使用 ZeroPanel Termux 轻量版安装程序！${NC}"
    echo ""

    check_termux_environment

    echo -e "  ${GREEN}检测到 Termux / ZeroTermux 环境${NC}"
    echo -e "  ${WHITE}按 Enter 继续...${NC}"
    read -r
    install_termux

    # 安装完成提示
    echo ""
    print_separator
    echo -e "                    ${GREEN}安装完成！${NC}"
    print_separator
    echo ""
    echo -e "  ${WHITE}访问地址:${NC} ${GREEN}http://localhost:5000${NC}"
    echo ""
    echo -e "  ${WHITE}默认账号:${NC} ${CYAN}admin${NC}"
    echo -e "  ${WHITE}默认密码:${NC} ${CYAN}admin123${NC}"
    echo ""
    echo -e "  ${WHITE}快捷命令:${NC}"
    echo -e "    ${BLUE}zeropanel start${NC}      - 启动面板"
    echo -e "    ${BLUE}zeropanel stop${NC}       - 停止面板"
    echo -e "    ${BLUE}zeropanel restart${NC}    - 重启面板"
    echo -e "    ${BLUE}zeropanel status${NC}     - 查看状态"
    echo -e "    ${BLUE}zeropanel log${NC}        - 查看日志"
    echo -e "    ${BLUE}zeropanel uninstall${NC}  - 卸载面板"
    echo -e "    ${BLUE}zeropanel help${NC}       - 显示帮助"
    echo ""
    print_separator
    echo -e "              ${CYAN}感谢使用 ZeroPanel！${NC}"
    print_separator

    echo ""
    echo -e "  ${CYAN}验证命令可用性...${NC}"
    zeropanel status
}

main "$@"
