#!/data/data/com.termux/files/usr/bin/bash
# ZeroPanel v2.0 安装脚本
# 专为 ZeroTermux 设计

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # 重置颜色

# 面板目录
PANEL_DIR="$HOME/zeropanel"
WWW_DIR="$HOME/www"
DATA_DIR="$PANEL_DIR/data"

# 下载地址
PANEL_DOWNLOAD_URL="https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel_v2.zip"

# 打印分隔线
print_separator() {
    echo -e "${CYAN}══════════════════════════════════════════════════════════════════${NC}"
}

# 打印标题
print_title() {
    print_separator
    echo -e "                    ${WHITE}ZeroPanel v2.0${NC}"
    echo -e "                ${CYAN}专为 ZeroTermux 设计${NC}"
    print_separator
}

# 打印步骤信息
print_step() {
    local step=$1
    local total=$2
    local message=$3
    echo -e "\n${BLUE}[${step}/${total}]${NC} ${WHITE}${message}${NC}"
}

# 打印成功消息
print_success() {
    echo -e "  ${GREEN}✓${NC} $1"
}

# 打印警告消息
print_warning() {
    echo -e "  ${YELLOW}⚠${NC} $1"
}

# 打印错误消息
print_error() {
    echo -e "  ${RED}✗${NC} $1"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检测 Python 命令
detect_python_cmd() {
    if command_exists python3; then
        echo "python3"
    elif command_exists python; then
        echo "python"
    else
        echo ""
    fi
}

# 主安装流程
main() {
    # 显示欢迎信息
    clear
    print_title
    echo ""
    echo -e "  ${WHITE}欢迎使用 ZeroPanel 安装程序！${NC}"
    echo -e "  本脚本将自动下载、安装并配置 ZeroPanel 建站面板"
    echo ""

    # 检查 Termux 环境
    if [ ! -d "/data/data/com.termux" ]; then
        print_warning "当前可能不在 Termux 环境中"
        echo -e "  ${YELLOW}继续安装可能导致兼容性问题${NC}"
        sleep 2
    fi

    # 检查 PREFIX
    if [ -z "$PREFIX" ]; then
        PREFIX="/data/data/com.termux/files/usr"
        export PREFIX
    fi

    # 获取设备信息
    echo -e "  ${CYAN}检测环境...${NC}"
    local os_name=$(uname -s)
    local os_arch=$(uname -m)
    PYTHON_CMD=$(detect_python_cmd)
    echo -e "    系统: ${WHITE}$os_name ${os_arch}${NC}"
    echo -e "    面板目录: ${WHITE}$PANEL_DIR${NC}"
    echo -e "    网站目录: ${WHITE}$WWW_DIR${NC}"
    echo -e "    Python: ${WHITE}${PYTHON_CMD:-未检测到}${NC}"
    echo ""

    # 确认安装
    echo -e "  ${WHITE}准备开始安装，按 Enter 继续...${NC}"
    read -r

    # 步骤 1: 更新软件源
    print_step 1 9 "更新软件源"
    echo -e "  ${CYAN}正在更新包管理器...${NC}"
    if pkg update -y 2>&1 | tail -n 5; then
        print_success "软件源更新完成"
    else
        print_error "软件源更新失败"
        exit 1
    fi

    # 步骤 2: 安装系统依赖
    print_step 2 9 "安装系统依赖"
    echo -e "  ${CYAN}正在安装 Python、Nginx、MariaDB、PHP-FPM、curl、unzip...${NC}"
    if pkg install -y python nginx mariadb php-fpm curl unzip 2>&1 | tail -n 3; then
        print_success "系统依赖安装完成"
    else
        print_error "系统依赖安装失败"
        exit 1
    fi

    # 步骤 3: 下载面板
    print_step 3 9 "下载面板文件"
    echo -e "  ${CYAN}正在从 GitHub 下载 ZeroPanel...${NC}"
    echo -e "    下载地址: ${WHITE}$PANEL_DOWNLOAD_URL${NC}"

    TMP_DIR=$(mktemp -d)
    ZIP_FILE="$TMP_DIR/zeropanel_v2.zip"

    if curl -fsSL -o "$ZIP_FILE" "$PANEL_DOWNLOAD_URL"; then
        print_success "面板文件下载完成"
    else
        print_error "面板文件下载失败，请检查网络连接"
        rm -rf "$TMP_DIR"
        exit 1
    fi

    # 步骤 4: 解压面板
    print_step 4 9 "部署面板"
    echo -e "  ${CYAN}正在解压到 $PANEL_DIR...${NC}"

    # 如果旧目录存在，备份数据目录（如果有）
    if [ -d "$PANEL_DIR" ]; then
        if [ -d "$PANEL_DIR/data" ]; then
            BACKUP_DIR="$HOME/zeropanel_data_backup_$(date +%Y%m%d%H%M%S)"
            echo -e "  ${YELLOW}检测到旧面板目录，备份数据到 $BACKUP_DIR${NC}"
            cp -r "$PANEL_DIR/data" "$BACKUP_DIR"
        fi
        rm -rf "$PANEL_DIR"
    fi

    mkdir -p "$PANEL_DIR"

    if unzip -q "$ZIP_FILE" -d "$HOME"; then
        print_success "面板部署完成"
    else
        print_error "面板解压失败"
        rm -rf "$TMP_DIR"
        exit 1
    fi

    rm -rf "$TMP_DIR"

    # 步骤 5: 安装 Python 依赖
    print_step 5 9 "安装 Python 依赖"
    echo -e "  ${CYAN}正在安装 Flask 及相关库...${NC}"
    if command_exists pip3; then
        PIP_CMD="pip3"
    elif command_exists pip; then
        PIP_CMD="pip"
    else
        print_error "未找到 pip 命令"
        exit 1
    fi

    if $PIP_CMD install flask flask-cors werkzeug 2>&1 | tail -n 2; then
        print_success "Python 依赖安装完成"
    else
        print_error "Python 依赖安装失败"
        exit 1
    fi

    # 步骤 6: 初始化 MariaDB
    print_step 6 9 "初始化 MariaDB"
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
    print_step 7 9 "配置运行环境"
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
    print_step 8 9 "配置快捷命令"
    echo -e "  ${CYAN}创建 zeropanel 命令...${NC}"

    mkdir -p "$HOME/bin"

    cat > "$HOME/bin/zeropanel" << 'SCRIPT'
#!/data/data/com.termux/files/usr/bin/bash

# ZeroPanel 快捷命令脚本
PANEL_DIR="$HOME/zeropanel"
LOG_FILE="$PANEL_DIR/data/panel.log"
DATA_DIR="$PANEL_DIR/data"

mkdir -p "$DATA_DIR"

# 检测 Python 命令
python_cmd() {
    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
    elif command -v python >/dev/null 2>&1; then
        echo "python"
    else
        echo ""
    fi
}

# 服务检测函数
check_service() {
    local pattern="$1"

    # 使用 /proc 目录检测
    if ls /proc/[0-9]*/cmdline 2>/dev/null | xargs -r grep -l -z "$pattern" 2>/dev/null | head -1 > /dev/null; then
        echo -e "\033[0;32m运行中\033[0m"
        return
    fi

    # 备用：检查 exe 链接名
    for pid_dir in /proc/[0-9]*; do
        [ -d "$pid_dir" ] || continue
        exe_link=$(readlink "$pid_dir/exe" 2>/dev/null || true)
        if [ -n "$exe_link" ] && (echo "$exe_link" | grep -qE "${pattern}$"); then
            echo -e "\033[0;32m运行中\033[0m"
            return
        fi
    done

    echo -e "\033[0;31m已停止\033[0m"
}

check_nginx() {
    check_service "nginx"
}

check_mysql() {
    check_service "(mysqld|mariadbd)"
}

check_php() {
    check_service "php-fpm"
}

check_panel() {
    local py_cmd=$(python_cmd)
    if [ -n "$py_cmd" ] && pgrep -f "$py_cmd app.py" > /dev/null; then
        echo -e "\033[0;32m运行中\033[0m"
    else
        echo -e "\033[0;31m已停止\033[0m"
    fi
}

# 主命令处理
case "$1" in
    start)
        echo -e "\033[1;37m启动 ZeroPanel...\033[0m"
        cd "$PANEL_DIR"
        PY_CMD=$(python_cmd)

        if [ -z "$PY_CMD" ]; then
            echo -e "  \033[0;31m✗\033[0m 未找到 python3 或 python"
            exit 1
        fi

        # 启动面板
        if ! pgrep -f "$PY_CMD app.py" > /dev/null; then
            nohup $PY_CMD app.py > "$LOG_FILE" 2>&1 &
            echo -e "  \033[0;32m✓\033[0m Panel 已启动"
        else
            echo -e "  \033[0;33m⚠\033[0m Panel 已在运行"
        fi

        # 启动 MariaDB
        if ! pgrep -x mysqld > /dev/null && ! pgrep -x mariadbd > /dev/null; then
            if command -v mysqld_safe >/dev/null 2>&1; then
                nohup mysqld_safe > /dev/null 2>&1 &
            elif command -v mysqld >/dev/null 2>&1; then
                nohup mysqld > /dev/null 2>&1 &
            else
                echo -e "  \033[0;33m⚠\033[0m 未找到 MariaDB 启动命令"
            fi
            sleep 3
            echo -e "  \033[0;32m✓\033[0m MariaDB 已启动"
        else
            echo -e "  \033[0;33m⚠\033[0m MariaDB 已在运行"
        fi

        # 启动 PHP-FPM
        if ! pgrep -f "php-fpm" > /dev/null; then
            php-fpm 2>/dev/null
            echo -e "  \033[0;32m✓\033[0m PHP-FPM 已启动"
        else
            echo -e "  \033[0;33m⚠\033[0m PHP-FPM 已在运行"
        fi

        # 启动 Nginx
        if ! pgrep -x nginx > /dev/null; then
            nginx 2>/dev/null
            echo -e "  \033[0;32m✓\033[0m Nginx 已启动"
        else
            echo -e "  \033[0;33m⚠\033[0m Nginx 已在运行"
        fi

        echo ""
        echo -e "\033[1;37mZeroPanel 启动完成！\033[0m"
        echo -e "\033[0;36m访问: http://localhost:5000\033[0m"
        ;;
    stop)
        echo -e "\033[1;37m停止 ZeroPanel...\033[0m"
        PY_CMD=$(python_cmd)
        if [ -n "$PY_CMD" ]; then
            pkill -f "$PY_CMD app.py" 2>/dev/null || true
        fi
        nginx -s stop 2>/dev/null || true
        pkill -x mysqld 2>/dev/null || true
        pkill -x mariadbd 2>/dev/null || true
        pkill -f php-fpm 2>/dev/null || true
        echo -e "  \033[0;32m✓\033[0m ZeroPanel 已停止"
        ;;
    restart)
        "$0" stop
        sleep 2
        "$0" start
        ;;
    status)
        echo -e "\033[1;37m服务状态:\033[0m"
        echo "  Panel:   $(check_panel)"
        echo "  Nginx:   $(check_nginx)"
        echo "  MariaDB: $(check_mysql)"
        echo "  PHP-FPM: $(check_php)"
        echo ""
        echo -e "\033[0;36m访问地址: http://localhost:5000\033[0m"
        ;;
    log)
        if [ -f "$LOG_FILE" ]; then
            echo -e "\033[1;37m最近 50 行日志:\033[0m"
            tail -n 50 "$LOG_FILE"
        else
            echo -e "\033[0;31m日志文件不存在\033[0m"
        fi
        ;;
    restart-nginx)
        echo -e "\033[1;37m重启 Nginx...\033[0m"
        nginx -s stop 2>/dev/null || true
        sleep 1
        nginx 2>/dev/null
        echo -e "  \033[0;32m✓\033[0m Nginx 已重启"
        ;;
    help)
        echo -e "\033[1;37mZeroPanel 命令帮助:\033[0m"
        echo ""
        echo -e "\033[0;36mzeropanel start\033[0m      - 启动面板及相关服务"
        echo -e "\033[0;36mzeropanel stop\033[0m       - 停止面板及相关服务"
        echo -e "\033[0;36mzeropanel restart\033[0m    - 重启面板及相关服务"
        echo -e "\033[0;36mzeropanel status\033[0m     - 查看服务状态"
        echo -e "\033[0;36mzeropanel log\033[0m        - 查看日志"
        echo -e "\033[0;36mzeropanel restart-nginx\033[0m - 重启 Nginx"
        echo -e "\033[0;36mzeropanel help\033[0m       - 显示此帮助"
        ;;
    *)
        echo -e "\033[1;37m用法: zeropanel {start|stop|restart|status|log|restart-nginx|help}\033[0m"
        exit 1
        ;;
esac
SCRIPT

    chmod +x "$HOME/bin/zeropanel"
    print_success "快捷命令创建完成"

    # 更新 PATH
    echo -e "  ${CYAN}配置环境变量...${NC}"
    touch "$HOME/.bashrc"
    if ! grep -q 'export PATH="$HOME/bin:$PATH"' "$HOME/.bashrc"; then
        echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
        print_success "PATH 已添加到 .bashrc"
    else
        print_success "PATH 已配置"
    fi
    export PATH="$HOME/bin:$PATH"

    # 步骤 9: 启动服务
    print_step 9 9 "启动服务"

    PY_CMD=$(detect_python_cmd)

    # 启动 MariaDB
    if ! pgrep -x mysqld > /dev/null && ! pgrep -x mariadbd > /dev/null; then
        echo -e "  ${CYAN}启动 MariaDB...${NC}"
        if command_exists mysqld_safe; then
            nohup mysqld_safe > /dev/null 2>&1 &
        elif command_exists mysqld; then
            nohup mysqld > /dev/null 2>&1 &
        else
            print_warning "未找到 MariaDB 启动命令"
        fi
        sleep 3
    fi

    # 启动 PHP-FPM
    if ! pgrep -f php-fpm > /dev/null; then
        echo -e "  ${CYAN}启动 PHP-FPM...${NC}"
        php-fpm 2>/dev/null || print_warning "PHP-FPM 启动失败，请检查配置"
    fi

    # 启动 Nginx
    if ! pgrep -x nginx > /dev/null; then
        echo -e "  ${CYAN}启动 Nginx...${NC}"
        nginx 2>/dev/null || print_warning "Nginx 启动失败，请检查配置"
    fi

    # 启动面板
    if [ -n "$PY_CMD" ] && ! pgrep -f "$PY_CMD app.py" > /dev/null; then
        echo -e "  ${CYAN}启动 ZeroPanel...${NC}"
        cd "$PANEL_DIR"
        nohup "$PY_CMD" app.py > "$DATA_DIR/panel.log" 2>&1 &
        sleep 2
    fi

    # 安装完成
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
    echo -e "    ${BLUE}zeropanel start${NC}    - 启动面板"
    echo -e "    ${BLUE}zeropanel stop${NC}     - 停止面板"
    echo -e "    ${BLUE}zeropanel restart${NC}  - 重启面板"
    echo -e "    ${BLUE}zeropanel status${NC}   - 查看状态"
    echo -e "    ${BLUE}zeropanel log${NC}      - 查看日志"
    echo -e "    ${BLUE}zeropanel help${NC}     - 显示帮助"
    echo ""
    echo -e "  ${YELLOW}提示：如果新终端无法使用 zeropanel 命令，请执行：source ~/.bashrc${NC}"
    echo ""
    print_separator
    echo -e "              ${CYAN}感谢使用 ZeroPanel！${NC}"
    echo -e "         ${CYAN}祝您建站愉快！${NC}"
    print_separator

    # 验证命令
    echo ""
    echo -e "  ${CYAN}验证命令可用性...${NC}"
    zeropanel status
}

# 执行主函数
main
