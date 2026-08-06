#!/bin/bash
# ZeroPanel v2.0 - Proot (Ubuntu/Debian) 高级版安装脚本
# 仅适用于 Proot 容器内的 Ubuntu / Debian 环境
# 安装时自动识别系统版本，并为受支持的 Debian/Ubuntu 自动添加 PHP 多版本源 (SURY)

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
PANEL_DIR="/var/lib/zeropanel"
WWW_DIR="/var/www"
DATA_DIR="$PANEL_DIR/data"
# 统一备份根目录：云更新备份与卸载备份共用（与面板目录平级，卸载不影响）
BACKUP_ROOT="/var/lib/zeropanel_backups"
PANEL_DOWNLOAD_URL="https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel-proot_v2.zip"

# 打印分隔线
print_separator() {
    echo -e "${CYAN}══════════════════════════════════════════════════════════════════${NC}"
}

# 打印标题
print_title() {
    print_separator
    echo -e "                    ${WHITE}ZeroPanel v2.0${NC}"
    echo -e "                ${CYAN}Proot (Ubuntu/Debian) 高级版${NC}"
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

# 备份面板数据到统一备份目录（与云更新备份共用同一目录），返回备份路径
backup_panel_data() {
    local stamp=$(date +%Y%m%d%H%M%S)
    mkdir -p "$BACKUP_ROOT"
    local dest="$BACKUP_ROOT/zeropanel_data_${stamp}.tar.gz"
    if command_exists tar && tar -czf "$dest" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")" >/dev/null 2>&1; then
        echo "$dest"
    else
        local dir_dest="$BACKUP_ROOT/zeropanel_data_${stamp}"
        if cp -r "$DATA_DIR" "$dir_dest" >/dev/null 2>&1; then
            echo "$dir_dest"
        else
            echo ""
        fi
    fi
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
check_proot_environment() {
    local distro=""

    if [ -f "/etc/os-release" ]; then
        distro=$(grep -E '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
    fi

    if [ "$distro" = "debian" ] || [ "$distro" = "ubuntu" ]; then
        return 0
    fi

    echo ""
    print_error "当前环境不是 Proot 容器内的 Ubuntu / Debian"
    echo ""
    echo -e "  ${WHITE}本脚本仅支持 Proot 容器内的 Ubuntu / Debian 环境${NC}"
    echo -e "  ${WHITE}Termux / ZeroTermux 请使用 zeropanel 版本的安装脚本${NC}"
    echo ""
    exit 1
}

# 检测操作系统发行版与版本代号
detect_os() {
    OS_ID=""
    OS_VERSION_ID=""
    OS_CODENAME=""

    if [ -f "/etc/os-release" ]; then
        OS_ID=$(grep -E '^ID=' /etc/os-release | head -1 | cut -d= -f2 | tr -d '"')
        OS_VERSION_ID=$(grep -E '^VERSION_ID=' /etc/os-release | head -1 | cut -d= -f2 | tr -d '"')
        OS_CODENAME=$(grep -E '^VERSION_CODENAME=' /etc/os-release | head -1 | cut -d= -f2 | tr -d '"')
    fi

    if [ -z "$OS_CODENAME" ] && command_exists lsb_release; then
        OS_CODENAME=$(lsb_release -sc 2>/dev/null)
    fi

    [ -z "$OS_ID" ] && OS_ID="unknown"
    [ -z "$OS_VERSION_ID" ] && OS_VERSION_ID="unknown"
    [ -z "$OS_CODENAME" ] && OS_CODENAME="unknown"
    return 0
}

# 判断系统是否在 PHP 多版本源 (SURY) 支持列表内
is_sury_supported() {
    case "${OS_ID}:${OS_CODENAME}" in
        debian:buster|debian:bullseye|debian:bookworm|debian:trixie|debian:sid)
            return 0 ;;
        ubuntu:focal|ubuntu:jammy|ubuntu:noble)
            return 0 ;;
        *)
            return 1 ;;
    esac
}

# 添加 PHP 多版本源 (SURY)，使面板可安装任意 PHP 版本
add_php_repo() {
    local keyring_deb="/tmp/debsuryorg-archive-keyring.deb"

    if [ -z "$OS_CODENAME" ] || [ "$OS_CODENAME" = "unknown" ]; then
        print_warning "无法识别系统版本代号，跳过第三方源"
        return 1
    fi

    # 确保密钥包依赖已安装
    apt-get install -y ca-certificates curl >/dev/null 2>&1 || true

    if [ ! -f "/usr/share/keyrings/debsuryorg-archive-keyring.gpg" ]; then
        echo -e "  ${CYAN}下载 PHP 源密钥...${NC}"
        if ! curl -fsSL -o "$keyring_deb" "https://packages.sury.org/debsuryorg-archive-keyring.deb"; then
            print_warning "PHP 源密钥下载失败，跳过第三方源"
            return 1
        fi

        if ! dpkg -i "$keyring_deb" >/dev/null 2>&1; then
            # 依赖问题：尝试修复后重装
            apt-get install -y -f >/dev/null 2>&1 || true
            dpkg -i "$keyring_deb" >/dev/null 2>&1 || {
                print_warning "PHP 源密钥安装失败，跳过第三方源"
                return 1
            }
        fi

        if [ ! -f "/usr/share/keyrings/debsuryorg-archive-keyring.gpg" ]; then
            print_warning "PHP 源密钥文件未生成，跳过第三方源"
            return 1
        fi
    else
        print_success "PHP 源密钥已存在"
    fi

    echo -e "  ${CYAN}写入 PHP 源文件: /etc/apt/sources.list.d/php.sury.org.list${NC}"
    echo "deb [signed-by=/usr/share/keyrings/debsuryorg-archive-keyring.gpg] https://packages.sury.org/php/ ${OS_CODENAME} main" > /etc/apt/sources.list.d/php.sury.org.list
    print_success "PHP 多版本源已添加"
    return 0
}

# 仅卸载面板程序文件（保留网站、数据、相关服务）
uninstall_panel_only() {
    print_title
    echo ""
    echo -e "  ${YELLOW}仅卸载面板程序文件${NC}"
    echo -e "  ${WHITE}保留内容:${NC}"
    echo -e "    - 网站文件: ${CYAN}$WWW_DIR${NC}"
    echo -e "    - 相关服务: Nginx / MariaDB / PHP-FPM"
    echo -e "  ${WHITE}面板数据:${NC} 可选择备份到统一备份目录，或直接删除"
    echo ""
    read -p "确定仅卸载面板程序？ [y/N]: " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        echo -e "  ${CYAN}停止面板进程...${NC}"
        pkill -f "python3 app.py" 2>/dev/null || true
        pkill -f "python app.py" 2>/dev/null || true
        sleep 1

        local data_backup_path=""
        if [ -d "$PANEL_DIR/data" ]; then
            echo ""
            read -p "是否备份面板数据到统一备份目录 $BACKUP_ROOT ？[Y/n]: " do_backup
            if [ -z "$do_backup" ] || [ "$do_backup" = "y" ] || [ "$do_backup" = "Y" ]; then
                data_backup_path=$(backup_panel_data)
                if [ -n "$data_backup_path" ]; then
                    echo -e "  ${GREEN}✓${NC} 面板数据已备份到: ${CYAN}$data_backup_path${NC}"
                else
                    print_warning "备份失败，将继续卸载"
                fi
            else
                echo -e "  ${YELLOW}未备份，面板数据将被删除${NC}"
            fi
        fi

        echo -e "  ${CYAN}删除面板程序文件...${NC}"
        rm -rf "$PANEL_DIR"

        echo ""
        print_separator
        echo -e "              ${GREEN}面板程序已卸载${NC}"
        print_separator
        echo ""
        echo -e "  ${WHITE}已保留:${NC}"
        echo -e "    - 网站文件: ${CYAN}$WWW_DIR${NC}"
        echo -e "    - 相关服务: Nginx / MariaDB / PHP-FPM"
        if [ -n "$data_backup_path" ]; then
            echo -e "    - 面板数据备份: ${CYAN}$data_backup_path${NC}"
            echo ""
            echo -e "  ${YELLOW}如需恢复：重新运行安装脚本后，解压该备份到 ${CYAN}$PANEL_DIR/data${NC}"
        else
            echo -e "    - 面板数据: ${YELLOW}未备份（已删除）${NC}"
        fi
    else
        echo -e "  ${YELLOW}已取消卸载${NC}"
    fi
}

# 完全卸载（删除面板、数据、网站，并卸载相关服务）
uninstall_full() {
    print_title
    echo ""
    echo -e "  ${RED}完全卸载 ZeroPanel 及所有相关组件${NC}"
    echo -e "  ${WHITE}将删除:${NC}"
    echo -e "    - 面板程序与数据: ${CYAN}$PANEL_DIR${NC}"
    echo -e "    - 网站文件: ${CYAN}$WWW_DIR${NC}"
    echo -e "    - Nginx 站点配置: ${CYAN}/etc/nginx/conf.d/zeropanel*.conf${NC}"
    echo -e "    - 快捷命令: ${CYAN}/usr/local/bin/zeropanel${NC}"
    echo -e "    - 相关服务: ${CYAN}Nginx / MariaDB / PHP-FPM${NC}"
    echo -e "    - MariaDB 数据目录: ${CYAN}/var/lib/mysql${NC}"
    echo ""
    read -p "此操作不可恢复！确认完全卸载？[y/N]: " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        echo -e "  ${CYAN}停止相关服务...${NC}"
        service nginx stop 2>/dev/null || true
        service mysql stop 2>/dev/null || true
        service mariadb stop 2>/dev/null || true
        service php*-fpm stop 2>/dev/null || true
        pkill -f "python3 app.py" 2>/dev/null || true
        pkill -f "python app.py" 2>/dev/null || true
        sleep 2

        local data_backup_path=""
        if [ -d "$PANEL_DIR/data" ]; then
            echo ""
            read -p "是否备份面板数据到统一备份目录 $BACKUP_ROOT ？[Y/n]: " do_backup
            if [ -z "$do_backup" ] || [ "$do_backup" = "y" ] || [ "$do_backup" = "Y" ]; then
                data_backup_path=$(backup_panel_data)
                if [ -n "$data_backup_path" ]; then
                    echo -e "  ${GREEN}✓${NC} 面板数据已备份到: ${CYAN}$data_backup_path${NC}"
                else
                    print_warning "备份失败，将继续卸载"
                fi
            else
                echo -e "  ${YELLOW}未备份，面板数据将被删除${NC}"
            fi
        fi

        echo -e "  ${CYAN}删除面板、网站与配置...${NC}"
        rm -rf "$PANEL_DIR"
        rm -rf "$WWW_DIR"
        rm -f /etc/nginx/conf.d/zeropanel*.conf
        rm -f /usr/local/bin/zeropanel
        rm -f /etc/apt/sources.list.d/php.sury.org.list

        echo -e "  ${CYAN}卸载相关服务 (nginx / mariadb-server / php-fpm / php-mysql)...${NC}"
        DEBIAN_FRONTEND=noninteractive apt-get remove -y --purge nginx mariadb-server php-fpm php-mysql 2>&1 | tail -n 3 || true
        rm -rf /var/lib/mysql

        echo ""
        print_separator
        echo -e "              ${GREEN}ZeroPanel 已完全卸载${NC}"
        print_separator
        echo ""
        if [ -n "${data_backup_path:-}" ]; then
            echo -e "  ${YELLOW}面板数据备份: ${CYAN}$data_backup_path${NC}"
            echo -e "  ${YELLOW}如需恢复：重新安装面板后，解压该备份到 ${CYAN}$PANEL_DIR/data${NC}"
        fi
    else
        echo -e "  ${YELLOW}已取消卸载${NC}"
    fi
}

# 卸载流程（选择卸载方式）
uninstall_proot() {
    print_title
    echo ""
    echo -e "  ${YELLOW}卸载 ZeroPanel (Proot 高级版)${NC}"
    echo ""
    echo -e "  ${WHITE}请选择卸载方式:${NC}"
    echo ""
    echo -e "    ${CYAN}1)${NC} 仅卸载面板程序  - 删除面板文件，保留网站、数据与相关服务"
    echo -e "    ${CYAN}2)${NC} 完全卸载        - 删除面板、数据、网站，并卸载 Nginx/MariaDB/PHP-FPM 服务"
    echo ""
    read -p "请输入选项 (1/2)，直接回车取消: " mode
    case "$mode" in
        1) uninstall_panel_only ;;
        2) uninstall_full ;;
        *) echo -e "  ${YELLOW}已取消卸载${NC}" ;;
    esac
}

# 安装流程
install_proot() {
    local total_steps=9

    # 步骤 1: 检测系统并配置软件源
    print_step 1 $total_steps "检测系统并配置软件源"
    detect_os
    echo -e "  检测到系统: ${WHITE}${OS_ID} ${OS_VERSION_ID} (${OS_CODENAME})${NC}"

    echo -e "  ${CYAN}apt-get update (官方源)...${NC}"
    if ! apt-get update -y 2>&1 | tail -n 5; then
        print_error "软件源更新失败"
        exit 1
    fi
    print_success "官方软件源更新完成"

    PHP_REPO_ADDED=0
    if is_sury_supported "$OS_ID" "$OS_CODENAME"; then
        echo -e "  ${CYAN}添加 PHP 多版本源 (SURY)...${NC}"
        if add_php_repo; then
            PHP_REPO_ADDED=1
            if ! apt-get update -y 2>&1 | tail -n 5; then
                print_warning "PHP 源更新失败，移除第三方源后继续（仅可使用官方源自带的 PHP 版本）"
                rm -f /etc/apt/sources.list.d/php.sury.org.list
                PHP_REPO_ADDED=0
                apt-get update -y >/dev/null 2>&1 || true
            else
                print_success "PHP 多版本源更新完成"
            fi
        fi
    else
        print_warning "系统 ($OS_ID $OS_CODENAME) 不在 PHP 多版本源支持列表，仅可使用官方源自带的 PHP 版本"
    fi

    # 步骤 2: 安装系统依赖
    print_step 2 $total_steps "安装系统依赖"
    echo -e "  ${CYAN}正在安装 Nginx、MariaDB、PHP-FPM、Python3...${NC}"
    local deps="python3 python3-pip nginx mariadb-server php-fpm php-mysql curl unzip cron"
    if [ "$PHP_REPO_ADDED" = "1" ]; then
        echo -e "  ${YELLOW}已启用 PHP 多版本源，将同时安装面板默认使用的 PHP 8.0 及常用扩展${NC}"
        deps="$deps php8.0-fpm php8.0-mysql php8.0-curl php8.0-gd php8.0-mbstring php8.0-xml php8.0-zip php8.0-bcmath php8.0-opcache php8.0-intl"
    fi
    if apt-get install -y $deps 2>&1 | tail -n 3; then
        print_success "系统依赖安装完成"
    else
        print_error "系统依赖安装失败"
        exit 1
    fi

    # 步骤 3: 下载面板
    print_step 3 $total_steps "下载高级版面板"
    echo -e "  ${CYAN}正在下载 ZeroPanel Proot 版...${NC}"
    echo -e "    地址: ${WHITE}$PANEL_DOWNLOAD_URL${NC}"

    local tmp_dir=$(mktemp -d)
    local zip_file="$tmp_dir/zeropanel-proot_v2.zip"

    if curl -fsSL -o "$zip_file" "$PANEL_DOWNLOAD_URL"; then
        print_success "面板下载完成"
    else
        print_error "面板下载失败，请检查网络"
        rm -rf "$tmp_dir"
        exit 1
    fi

    # 步骤 4: 部署面板
    print_step 4 $total_steps "部署面板"
    echo -e "  ${CYAN}正在解压到 $PANEL_DIR...${NC}"

    if [ -d "$PANEL_DIR" ]; then
        if [ -d "$PANEL_DIR/data" ]; then
            local backup_dir="/var/lib/zeropanel_data_backup_$(date +%Y%m%d%H%M%S)"
            echo -e "  ${YELLOW}备份数据到 $backup_dir${NC}"
            cp -r "$PANEL_DIR/data" "$backup_dir"
        fi
        rm -rf "$PANEL_DIR"
    fi

    local extract_tmp=$(mktemp -d)
    if unzip -q "$zip_file" -d "$extract_tmp"; then
        # zip 顶层目录为 zeropanel-proot，需移动到 /var/lib/zeropanel
        rm -rf "$PANEL_DIR"
        mv "$extract_tmp/zeropanel-proot" "$PANEL_DIR"
        print_success "面板部署完成"
    else
        print_error "面板解压失败"
        rm -rf "$tmp_dir" "$extract_tmp"
        exit 1
    fi
    rm -rf "$tmp_dir" "$extract_tmp"

    # 步骤 5: 安装 Python 依赖
    print_step 5 $total_steps "安装 Python 依赖"
    echo -e "  ${CYAN}正在安装 Flask 及相关库...${NC}"
    local pip_output
    if pip_output=$(pip3 install --break-system-packages flask flask-cors werkzeug 2>&1); then
        print_success "Python 依赖安装完成"
    elif pip_output=$(pip3 install flask flask-cors werkzeug 2>&1); then
        print_success "Python 依赖安装完成"
    elif pip_output=$(apt-get install -y python3-flask python3-flask-cors python3-werkzeug 2>&1); then
        print_success "Python 依赖安装完成"
    else
        print_error "Python 依赖安装失败"
        echo "$pip_output" | tail -n 10
        exit 1
    fi

    # 步骤 6: 初始化 MariaDB
    print_step 6 $total_steps "初始化 MariaDB"
    echo -e "  ${CYAN}启动并配置 MariaDB...${NC}"
    if ! pgrep -x mysqld > /dev/null && ! pgrep -x mariadbd > /dev/null; then
        service mysql start 2>/dev/null || service mariadb start 2>/dev/null || mysqld_safe > /dev/null 2>&1 &
        sleep 3
    fi

    # 设置 root 无密码访问（本地开发环境）
    mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '';" 2>/dev/null || true
    mysql -u root -e "UPDATE mysql.user SET plugin='mysql_native_password' WHERE User='root'; FLUSH PRIVILEGES;" 2>/dev/null || true
    print_success "MariaDB 初始化完成"

    # 步骤 7: 配置 PHP-FPM 和 Nginx
    print_step 7 $total_steps "配置运行环境"
    echo -e "  ${CYAN}创建目录...${NC}"
    mkdir -p "$WWW_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "/etc/nginx/conf.d"
    mkdir -p "/var/log/nginx"
    mkdir -p "/run/php"
    print_success "目录创建完成"

    echo -e "  ${CYAN}配置 PHP-FPM...${NC}"
    # 查找可用的 PHP-FPM 版本，每个版本使用独立 socket
    for ver in 8.4 8.3 8.2 8.1 8.0 7.4; do
        local pool_conf="/etc/php/${ver}/fpm/pool.d/www.conf"
        if [ -f "$pool_conf" ]; then
            cp "$pool_conf" "$pool_conf.bak"
            sed -i "s|^listen =.*|listen = /run/php/php${ver}-fpm.sock|" "$pool_conf"
        fi
    done
    print_success "PHP-FPM 已配置独立 socket"

    echo -e "  ${CYAN}配置 Nginx...${NC}"
    if [ -f "/etc/nginx/nginx.conf" ]; then
        cp "/etc/nginx/nginx.conf" "/etc/nginx/nginx.conf.bak"
    fi
    rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

    cat > /etc/nginx/nginx.conf << 'EOF'
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    sendfile on;
    keepalive_timeout 65;
    client_max_body_size 100M;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    include /etc/nginx/conf.d/*.conf;
}
EOF
    print_success "Nginx 配置完成"

    # 步骤 8: 创建快捷命令
    print_step 8 $total_steps "配置快捷命令"
    echo -e "  ${CYAN}创建 zeropanel 命令...${NC}"

    mkdir -p "/usr/local/bin"
    cat > /usr/local/bin/zeropanel << SCRIPT
#!/bin/bash
PANEL_DIR="$PANEL_DIR"
LOG_FILE="$PANEL_DIR/data/panel.log"
DATA_DIR="$PANEL_DIR/data"
WWW_DIR="/var/www"
BACKUP_ROOT="$BACKUP_ROOT"
mkdir -p "\$DATA_DIR"

backup_panel_data() {
    local stamp=\$(date +%Y%m%d%H%M%S)
    mkdir -p "\$BACKUP_ROOT"
    local dest="\$BACKUP_ROOT/zeropanel_data_\${stamp}.tar.gz"
    if command -v tar >/dev/null 2>&1 && tar -czf "\$dest" -C "\$(dirname "\$DATA_DIR")" "\$(basename "\$DATA_DIR")" >/dev/null 2>&1; then
        echo "\$dest"
    else
        local dir_dest="\$BACKUP_ROOT/zeropanel_data_\${stamp}"
        if cp -r "\$DATA_DIR" "\$dir_dest" >/dev/null 2>&1; then
            echo "\$dir_dest"
        else
            echo ""
        fi
    fi
}

python_cmd() {
    if command -v python3 >/dev/null 2>&1; then echo "python3";
    elif command -v python >/dev/null 2>&1; then echo "python";
    else echo ""; fi
}

case "\$1" in
    start)
        echo -e "\033[1;37m启动 ZeroPanel...\033[0m"
        PY_CMD=\$(python_cmd)
        [ -z "\$PY_CMD" ] && { echo "未找到 python3"; exit 1; }

        # Proot 无 systemd，直接启动 daemon
        if ! pgrep -x mysqld >/dev/null && ! pgrep -x mariadbd >/dev/null; then
            if command -v mysqld_safe >/dev/null 2>&1; then
                nohup mysqld_safe > /dev/null 2>&1 &
            elif command -v mysqld >/dev/null 2>&1; then
                nohup mysqld > /dev/null 2>&1 &
            fi
            sleep 2
        fi

        if ! pgrep -x nginx >/dev/null; then
            nginx 2>/dev/null || true
        fi

        for ver in 8.4 8.3 8.2 8.1 8.0 7.4; do
            if command -v "php\${ver//./}-fpm" >/dev/null 2>&1 && ! pgrep -f "php\${ver//./}-fpm" >/dev/null; then
                "php\${ver//./}-fpm" 2>/dev/null || true
            elif command -v "php-fpm\$ver" >/dev/null 2>&1 && ! pgrep -f "php-fpm\$ver" >/dev/null; then
                "php-fpm\$ver" 2>/dev/null || true
            fi
        done

        cd "\$PANEL_DIR"
        if ! pgrep -f "\$PY_CMD app.py" > /dev/null; then
            nohup \$PY_CMD app.py > "\$LOG_FILE" 2>&1 &
        fi
        echo -e "\033[0;36m访问: http://localhost:5000\033[0m"
        ;;
    stop)
        echo -e "\033[1;37m停止 ZeroPanel...\033[0m"
        PY_CMD=\$(python_cmd)
        [ -n "\$PY_CMD" ] && pkill -f "\$PY_CMD app.py" 2>/dev/null || true
        nginx -s stop 2>/dev/null || true
        pkill -x mysqld 2>/dev/null || true
        pkill -x mariadbd 2>/dev/null || true
        pkill -f php-fpm 2>/dev/null || true
        ;;
    restart)
        "\$0" stop; sleep 2; "\$0" start
        ;;
    status)
        echo -e "\033[1;37m服务状态:\033[0m"
        echo "  Panel:   \$(pgrep -f 'python3 app.py' >/dev/null && echo '运行中' || echo '已停止')"
        echo "  Nginx:   \$(pgrep -x nginx >/dev/null && echo '运行中' || echo '已停止')"
        echo "  MariaDB: \$(pgrep -x mysqld >/dev/null || pgrep -x mariadbd >/dev/null && echo '运行中' || echo '已停止')"
        echo "  PHP-FPM: \$(pgrep -f php-fpm >/dev/null && echo '运行中' || echo '已停止')"
        ;;
    log)
        [ -f "\$LOG_FILE" ] && tail -n 50 "\$LOG_FILE" || echo "日志不存在"
        ;;
    uninstall)
        echo -e "\033[1;37m卸载 ZeroPanel...\033[0m"
        echo ""
        echo -e "  \033[0;36m1)\033[0m 仅卸载面板程序  - 删除面板文件，保留网站、数据与相关服务"
        echo -e "  \033[0;36m2)\033[0m 完全卸载        - 删除面板、数据、网站，并卸载 Nginx/MariaDB/PHP-FPM 服务"
        echo ""
        read -p "请输入选项 (1/2)，直接回车取消: " mode
        case "\$mode" in
            1)
                PY_CMD=\$(python_cmd)
                [ -n "\$PY_CMD" ] && pkill -f "\$PY_CMD app.py" 2>/dev/null || true
                sleep 1
                data_backup_path=""
                if [ -d "\$PANEL_DIR/data" ]; then
                    read -p "  是否备份面板数据到 \$BACKUP_ROOT ？[Y/n]: " do_backup
                    if [ -z "\$do_backup" ] || [ "\$do_backup" = "y" ] || [ "\$do_backup" = "Y" ]; then
                        data_backup_path=\$(backup_panel_data)
                        if [ -n "\$data_backup_path" ]; then
                            echo "  面板数据已备份到: \$data_backup_path"
                        else
                            echo "  [警告] 备份失败，将继续卸载"
                        fi
                    else
                        echo "  未备份，面板数据将被删除"
                    fi
                fi
                rm -rf "\$PANEL_DIR"
                echo -e "\033[0;32m面板程序已卸载（网站与服务保留）\033[0m"
                echo "  网站: \$WWW_DIR"
                if [ -n "\$data_backup_path" ]; then
                    echo "  数据备份: \$data_backup_path"
                    echo "  恢复: 重新运行安装脚本后，解压该备份到 \$PANEL_DIR/data"
                else
                    echo "  面板数据: 未备份（已删除）"
                fi
                ;;
            2)
                "\$0" stop
                data_backup_path=""
                if [ -d "\$PANEL_DIR/data" ]; then
                    read -p "  是否备份面板数据到 \$BACKUP_ROOT ？[Y/n]: " do_backup
                    if [ -z "\$do_backup" ] || [ "\$do_backup" = "y" ] || [ "\$do_backup" = "Y" ]; then
                        data_backup_path=\$(backup_panel_data)
                        if [ -n "\$data_backup_path" ]; then
                            echo "  面板数据已备份到: \$data_backup_path"
                        else
                            echo "  [警告] 备份失败，将继续卸载"
                        fi
                    else
                        echo "  未备份，面板数据将被删除"
                    fi
                fi
                rm -rf "\$PANEL_DIR"
                rm -rf "\$WWW_DIR"
                rm -f /etc/nginx/conf.d/zeropanel*.conf
                rm -f /usr/local/bin/zeropanel
                rm -f /etc/apt/sources.list.d/php.sury.org.list
                echo -e "\033[1;37m卸载相关服务 (nginx / mariadb-server / php-fpm / php-mysql)...\033[0m"
                DEBIAN_FRONTEND=noninteractive apt-get remove -y --purge nginx mariadb-server php-fpm php-mysql 2>&1 | tail -n 3 || true
                rm -rf /var/lib/mysql
                echo -e "\033[0;32mZeroPanel 已完全卸载\033[0m"
                if [ -n "\$data_backup_path" ]; then
                    echo "  数据备份: \$data_backup_path"
                    echo "  恢复: 重新安装面板后，解压该备份到 \$PANEL_DIR/data"
                fi
                ;;
            *)
                echo "已取消"
                ;;
        esac
        ;;
    help|*)
        echo ""
        echo -e "\033[1;37mZeroPanel 快捷命令帮助\033[0m"
        echo ""
        echo -e "  \033[0;36mzeropanel start\033[0m      启动面板及相关服务（Nginx / MariaDB / PHP-FPM）"
        echo -e "  \033[0;36mzeropanel stop\033[0m       停止面板及相关服务"
        echo -e "  \033[0;36mzeropanel restart\033[0m    重启面板"
        echo -e "  \033[0;36mzeropanel status\033[0m     查看面板及服务运行状态"
        echo -e "  \033[0;36mzeropanel log\033[0m        查看面板运行日志（最后 50 行）"
        echo -e "  \033[0;36mzeropanel uninstall\033[0m  卸载面板（选择仅卸载面板或完全卸载）"
        echo -e "  \033[0;36mzeropanel help\033[0m       显示本帮助信息"
        echo ""
        ;;
esac
SCRIPT
    chmod +x /usr/local/bin/zeropanel
    print_success "快捷命令创建完成"

    # 步骤 9: 启动服务
    print_step 9 $total_steps "启动服务"
    echo -e "  ${CYAN}启动相关服务...${NC}"

    # Proot 无 systemd，直接启动 daemon
    if ! pgrep -x mysqld >/dev/null && ! pgrep -x mariadbd >/dev/null; then
        if command -v mysqld_safe >/dev/null 2>&1; then
            nohup mysqld_safe > /dev/null 2>&1 &
        elif command -v mysqld >/dev/null 2>&1; then
            nohup mysqld > /dev/null 2>&1 &
        fi
        sleep 2
    fi

    if ! pgrep -x nginx >/dev/null; then
        nginx 2>/dev/null || true
    fi

    for ver in 8.4 8.3 8.2 8.1 8.0 7.4; do
        if command -v "php${ver//./}-fpm" >/dev/null 2>&1 && ! pgrep -f "php${ver//./}-fpm" >/dev/null; then
            "php${ver//./}-fpm" 2>/dev/null || true
        elif command -v "php-fpm$ver" >/dev/null 2>&1 && ! pgrep -f "php-fpm$ver" >/dev/null; then
            "php-fpm$ver" 2>/dev/null || true
        fi
    done

    PY_CMD=$(detect_python_cmd)
    if [ -n "$PY_CMD" ]; then
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
            check_proot_environment
            uninstall_proot
            return
            ;;
    esac

    echo -e "  ${WHITE}欢迎使用 ZeroPanel Proot 高级版安装程序！${NC}"
    echo ""

    check_proot_environment

    echo -e "  ${GREEN}检测到 Proot (Ubuntu/Debian) 环境${NC}"
    echo -e "  ${WHITE}按 Enter 继续...${NC}"
    read -r
    install_proot

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
    echo -e "    ${BLUE}zeropanel uninstall${NC}  - 卸载面板（可选择仅卸载面板或完全卸载）"
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
