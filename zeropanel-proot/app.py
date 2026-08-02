#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZeroPanel v2.0 - 轻量级建站面板
专为 ZeroTermux 设计（proot 增强版）
"""

import os
import re
import json
import time
import uuid
import shutil
import hashlib
import subprocess
import sqlite3
import zipfile
import tempfile
import secrets
import string
from datetime import datetime
from functools import wraps
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# 面板版本信息
PANEL_VERSION = '2.0.2'

# 云更新配置
UPDATE_CONFIG = {
    'version_url': 'https://raw.githubusercontent.com/2136206076/ZeroPanel/main/VERSION',
    'download_url': 'https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel_v2.zip',
    'release_notes_url': 'https://raw.githubusercontent.com/2136206076/ZeroPanel/main/CHANGELOG.md'
}

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
CORS(app)

# 配置
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'panel.db'
BACKUP_DIR = DATA_DIR / 'backups'
UPLOAD_DIR = DATA_DIR / 'uploads'
WWW_DIR = Path.home() / 'www'

# ==================== 环境检测与路径适配 ====================

def _detect_proot():
    """检测是否在 proot 容器中运行"""
    try:
        cgroup_file = Path('/proc/1/cgroup')
        if cgroup_file.exists():
            cgroup = cgroup_file.read_text().lower()
            if any(k in cgroup for k in ('lxc', 'docker', 'containerd', 'proot', 'buildd')):
                return True
    except Exception:
        pass
    if os.environ.get('PROOT_DISTRO'):
        return True
    if os.environ.get('container', '').lower() in ('1', 'true', 'yes'):
        return True
    return False


def _detect_debian_ubuntu():
    """检测系统是否为 Ubuntu/Debian"""
    try:
        os_release = Path('/etc/os-release')
        if os_release.exists():
            content = os_release.read_text().lower()
            return 'debian' in content or 'ubuntu' in content
    except Exception:
        pass
    return False


IS_PROOT = _detect_proot()
IS_DEBIAN_UBUNTU = _detect_debian_ubuntu()

if IS_PROOT and IS_DEBIAN_UBUNTU:
    NGINX_CONF_DIR = Path('/etc/nginx/conf.d')
    PHP_FPM_DIR = Path('/etc/php')
    WEB_ROOT_BASE = Path('/var/www')
    # Proot 高级版使用自己的分发包
    UPDATE_CONFIG['download_url'] = 'https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel-proot_v2.zip'
else:
    # Termux 环境：保持原路径
    TERMUX_PREFIX = Path(os.environ.get('PREFIX', '/data/data/com.termux/files/usr'))
    NGINX_CONF_DIR = TERMUX_PREFIX / 'etc' / 'nginx' / 'conf.d'
    PHP_FPM_DIR = TERMUX_PREFIX / 'etc' / 'php'
    WEB_ROOT_BASE = WWW_DIR

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'tar', 'gz', 'sql', 'php', 'html', 'css', 'js', 'json', 'xml', 'md'}

# 允许文件操作的根目录
ALLOWED_ROOTS = [WWW_DIR, DATA_DIR]
if IS_PROOT and IS_DEBIAN_UBUNTU:
    ALLOWED_ROOTS.append(WEB_ROOT_BASE)

# 常用 PHP 扩展列表
COMMON_PHP_EXTENSIONS = [
    'redis', 'mysqli', 'pdo_mysql', 'gd', 'curl', 'mbstring',
    'xml', 'zip', 'bcmath', 'opcache', 'intl', 'fileinfo', 'exif'
]

# 支持的 PHP 版本
SUPPORTED_PHP_VERSIONS = ['7.4', '8.0', '8.1', '8.2', '8.3']


def resolve_allowed_path(path):
    """解析并校验路径，返回 (安全路径, 是否允许)。防止路径遍历。"""
    try:
        resolved = Path(path).resolve()
    except Exception:
        return None, False
    for root in ALLOWED_ROOTS:
        try:
            resolved.relative_to(root)
            return resolved, True
        except ValueError:
            continue
    return resolved, False


def load_or_create_secret_key():
    """加载或创建持久化的会话密钥，避免每次重启后登录失效"""
    secret_file = DATA_DIR / '.secret_key'
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if secret_file.exists():
        return secret_file.read_text().strip()
    key = os.urandom(32).hex()
    secret_file.write_text(key)
    # 限制权限，仅所有者可读写
    try:
        os.chmod(secret_file, 0o600)
    except Exception:
        pass
    return key


app.secret_key = load_or_create_secret_key()

# ==================== 数据库初始化 ====================

def init_db():
    """初始化数据库"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    WWW_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 账号表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS account (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 网站表（先创建）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS websites (
            id TEXT PRIMARY KEY,
            domain TEXT UNIQUE NOT NULL,
            root_path TEXT NOT NULL,
            php_version TEXT DEFAULT '8.0',
            status TEXT DEFAULT 'stopped',
            port INTEGER DEFAULT 8080,
            rewrite_rules TEXT DEFAULT '',
            db_name TEXT DEFAULT '',
            db_user TEXT DEFAULT '',
            db_password TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 迁移：确保 websites 表存在所需列（兼容旧数据库）
    try:
        cursor.execute('PRAGMA table_info(websites)')
        columns = [row[1] for row in cursor.fetchall()]
        if 'port' not in columns:
            cursor.execute('ALTER TABLE websites ADD COLUMN port INTEGER DEFAULT 8080')
        if 'php_version' not in columns:
            cursor.execute("ALTER TABLE websites ADD COLUMN php_version TEXT DEFAULT '8.0'")
        if 'status' not in columns:
            cursor.execute("ALTER TABLE websites ADD COLUMN status TEXT DEFAULT 'stopped'")
        if 'rewrite_rules' not in columns:
            cursor.execute("ALTER TABLE websites ADD COLUMN rewrite_rules TEXT DEFAULT ''")
        if 'db_name' not in columns:
            cursor.execute("ALTER TABLE websites ADD COLUMN db_name TEXT DEFAULT ''")
        if 'db_user' not in columns:
            cursor.execute("ALTER TABLE websites ADD COLUMN db_user TEXT DEFAULT ''")
        if 'db_password' not in columns:
            cursor.execute("ALTER TABLE websites ADD COLUMN db_password TEXT DEFAULT ''")
    except Exception as e:
        print(f'迁移警告: {e}')

    # 数据库备份表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS database_backups (
            id TEXT PRIMARY KEY,
            database_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            size INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 设置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 检查是否存在管理员账号
    cursor.execute('SELECT username FROM account WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        cursor.execute(
            'INSERT INTO account (username, password_hash) VALUES (?, ?)',
            ('admin', generate_password_hash('admin123'))
        )
    
    conn.commit()
    conn.close()

# ==================== 认证装饰器 ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'success': False, 'message': '未登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ==================== 工具函数 ====================

def run_command(cmd, shell=False, timeout=30):
    """安全执行命令"""
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, '', '命令执行超时'
    except Exception as e:
        return False, '', str(e)


def _php_fpm_socket(php_version='8.0'):
    """根据环境返回 PHP-FPM socket 路径"""
    if IS_PROOT and IS_DEBIAN_UBUNTU:
        return f'/run/php/php{php_version}-fpm.sock'
    return f'/data/data/com.termux/files/usr/var/run/php{php_version}-fpm.sock'


def _nginx_log_dir():
    """返回 Nginx 日志目录"""
    if IS_PROOT and IS_DEBIAN_UBUNTU:
        return Path('/var/log/nginx')
    return Path('/data/data/com.termux/files/usr/var/log/nginx')


def _php_fpm_service_name(php_version='8.0'):
    """返回 PHP-FPM 服务名"""
    major, minor = php_version.split('.')
    return f'php{major}{minor}-fpm'


def _is_package_installed(package):
    """检查 Debian/Ubuntu 软件包是否已安装"""
    if not (IS_PROOT and IS_DEBIAN_UBUNTU):
        return False
    success, _, _ = run_command(['dpkg', '-l', package])
    if not success:
        # dpkg -l 对未安装包返回非零，再用 dpkg-query 确认
        success, _, _ = run_command(['dpkg-query', '-W', '-f=${Status}', package])
        if success and 'install ok installed' in _:
            return True
        return False
    return True


def _is_php_fpm_running(php_version='8.0'):
    """检查指定版本的 PHP-FPM 是否正在运行"""
    service = _php_fpm_service_name(php_version)
    success, _, _ = run_command(['pgrep', '-f', service])
    if success:
        return True
    success, _, _ = run_command(['pgrep', '-f', f'php-fpm.*{php_version}'])
    return success


def _random_password(length=16):
    """生成随机密码"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_system_info():
    """获取系统信息"""
    info = {
        'hostname': 'localhost',
        'os': 'Android/Termux',
        'kernel': 'Linux',
        'uptime': '0',
        'cpu_model': 'Unknown',
        'cpu_cores': 1,
        'total_memory': 0,
        'total_disk': 0
    }
    
    try:
        # 获取主机名
        success, stdout, _ = run_command(['hostname'])
        if success and stdout:
            info['hostname'] = stdout
        
        # 获取系统信息
        success, stdout, _ = run_command(['uname', '-a'])
        if success and stdout:
            parts = stdout.split()
            if len(parts) >= 3:
                info['kernel'] = parts[2]
        
        # 获取 CPU 核心数
        cpu_file = Path('/proc/cpuinfo')
        if cpu_file.exists():
            cores = 0
            with open(cpu_file, 'r') as f:
                for line in f:
                    if line.startswith('processor'):
                        cores += 1
            if cores > 0:
                info['cpu_cores'] = cores
        
        # 获取内存信息
        mem_file = Path('/proc/meminfo')
        if mem_file.exists():
            with open(mem_file, 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        info['total_memory'] = int(line.split()[1]) * 1024
                        break
        
        # 获取磁盘信息
        success, stdout, _ = run_command(['df', '-B1', '/'])
        if success and stdout:
            lines = stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 2:
                    info['total_disk'] = int(parts[1])
        
        # 获取运行时间
        uptime_file = Path('/proc/uptime')
        if uptime_file.exists():
            with open(uptime_file, 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                info['uptime'] = f'{days}天 {hours}小时 {minutes}分钟'
        
        # 识别系统类型
        if IS_PROOT and IS_DEBIAN_UBUNTU:
            try:
                os_release = Path('/etc/os-release').read_text()
                for line in os_release.splitlines():
                    if line.startswith('PRETTY_NAME='):
                        info['os'] = line.split('=', 1)[1].strip('"')
                        break
            except Exception:
                info['os'] = 'Linux (proot)'
        elif os.environ.get('PREFIX', '').find('termux') != -1:
            info['os'] = 'Android/Termux'
    except Exception:
        pass
    
    return info

def get_system_stats():
    """获取系统实时状态"""
    stats = {
        'cpu_usage': 0,
        'memory_usage': 0,
        'memory_used': 0,
        'disk_usage': 0,
        'disk_used': 0,
        'network_in': 0,
        'network_out': 0,
        'load_avg': [0, 0, 0]
    }
    
    try:
        # CPU 使用率：采样两次 /proc/stat，计算间隔内的使用率
        stat_file = Path('/proc/stat')
        if stat_file.exists():
            def read_cpu_times():
                with open(stat_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('cpu ') or line.startswith('cpu\t'):
                            parts = line.split()
                            if len(parts) >= 8:
                                try:
                                    return sum(int(x) for x in parts[1:8])
                                except ValueError:
                                    return None
                return None

            total1 = read_cpu_times()
            idle1 = None
            if total1 is not None:
                with open(stat_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('cpu ') or line.startswith('cpu\t'):
                            parts = line.split()
                            idle1 = int(parts[4])
                            break
            if total1 is not None and idle1 is not None:
                time.sleep(0.3)
                total2 = read_cpu_times()
                idle2 = None
                if total2 is not None:
                    with open(stat_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('cpu ') or line.startswith('cpu\t'):
                                parts = line.split()
                                idle2 = int(parts[4])
                                break
                if total2 is not None and idle2 is not None:
                    total_delta = total2 - total1
                    idle_delta = idle2 - idle1
                    if total_delta > 0:
                        stats['cpu_usage'] = round((1 - idle_delta / total_delta) * 100, 1)
        
        # 内存使用
        mem_file = Path('/proc/meminfo')
        if mem_file.exists():
            mem_total = 0
            mem_available = 0
            with open(mem_file, 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        try:
                            mem_total = int(line.split()[1]) * 1024
                        except:
                            pass
                    elif line.startswith('MemAvailable:'):
                        try:
                            mem_available = int(line.split()[1]) * 1024
                        except:
                            pass
                if mem_total > 0:
                    stats['memory_used'] = mem_total - mem_available
                    stats['memory_usage'] = round((mem_total - mem_available) / mem_total * 100, 1)
        
        # 磁盘使用
        success, stdout, _ = run_command(['df', '-k', '/'])
        if success and stdout:
            lines = stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    try:
                        total = int(parts[1]) * 1024
                        used = int(parts[2]) * 1024
                        stats['disk_used'] = used
                        stats['disk_usage'] = round(used / total * 100, 1) if total > 0 else 0
                    except:
                        pass
        
        # 网络流量
        net_file = Path('/proc/net/dev')
        if net_file.exists():
            with open(net_file, 'r') as f:
                lines = f.readlines()
                for line in lines[2:]:  # 跳过标题行
                    if ':' in line:
                        iface, data = line.split(':')
                        if iface.strip() != 'lo':  # 排除回环
                            parts = data.split()
                            if len(parts) >= 16:
                                stats['network_in'] += int(parts[0])
                                stats['network_out'] += int(parts[8])
        
        # 负载
        load_file = Path('/proc/loadavg')
        if load_file.exists():
            with open(load_file, 'r') as f:
                parts = f.read().split()[:3]
                stats['load_avg'] = [float(x) for x in parts]
    except Exception:
        pass
    
    return stats

def get_service_status():
    """获取服务状态"""
    services = {
        'nginx': False,
        'mysql': False,
        'php-fpm': False
    }

    # 检查 Nginx（使用 /proc 目录 + pgrep 双重检测）
    try:
        for proc_dir in Path('/proc').glob('[0-9]*'):
            try:
                cmdline = (proc_dir / 'cmdline').read_text().strip('\x00')
                exe = (proc_dir / 'exe').readlink().name if (proc_dir / 'exe').exists() else ''
                if 'nginx' in cmdline or 'nginx' in exe:
                    services['nginx'] = True
                    break
            except (PermissionError, OSError):
                continue
    except Exception:
        pass
    if not services['nginx']:
        success, _, _ = run_command(['pgrep', '-f', 'nginx'])
        services['nginx'] = success

    # 检查 MySQL/MariaDB
    try:
        for proc_dir in Path('/proc').glob('[0-9]*'):
            try:
                cmdline = (proc_dir / 'cmdline').read_text().strip('\x00')
                exe = (proc_dir / 'exe').readlink().name if (proc_dir / 'exe').exists() else ''
                if 'mysqld' in cmdline or 'mariadbd' in cmdline or 'mysqld' in exe or 'mariadbd' in exe:
                    services['mysql'] = True
                    break
            except (PermissionError, OSError):
                continue
    except Exception:
        pass
    if not services['mysql']:
        success, _, _ = run_command(['pgrep', '-f', 'mysqld'])
        if not success:
            success, _, _ = run_command(['pgrep', '-f', 'mariadbd'])
        services['mysql'] = success

    # 检查 PHP-FPM
    try:
        for proc_dir in Path('/proc').glob('[0-9]*'):
            try:
                cmdline = (proc_dir / 'cmdline').read_text().strip('\x00')
                exe = (proc_dir / 'exe').readlink().name if (proc_dir / 'exe').exists() else ''
                if 'php-fpm' in cmdline or 'php-fpm' in exe:
                    services['php-fpm'] = True
                    break
            except (PermissionError, OSError):
                continue
    except Exception:
        pass
    if not services['php-fpm']:
        success, _, _ = run_command(['pgrep', '-f', 'php-fpm'])
        services['php-fpm'] = success

    return services

def get_safe_domain(domain):
    """生成可用于文件名的安全域名"""
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', domain)


def get_nginx_config_path(domain, port=8080):
    """获取 Nginx 配置文件路径"""
    safe_domain = get_safe_domain(domain)
    return NGINX_CONF_DIR / f'{safe_domain}_{port}.conf'


def get_nginx_disabled_path(domain, port=8080):
    """获取停止状态的 Nginx 配置文件路径"""
    safe_domain = get_safe_domain(domain)
    return NGINX_CONF_DIR / f'{safe_domain}_{port}.conf.disabled'


def generate_nginx_config(domain, root_path, php_version='8.0', port=8080, rewrite_rules=''):
    """生成 Nginx 配置"""
    php_sock = _php_fpm_socket(php_version)
    log_dir = _nginx_log_dir()

    config_lines = [
        'server {',
        '    listen ' + str(port) + ';',
        '    server_name ' + domain + ';',
        '    root "' + root_path.replace('"', '\\"') + '";',
        '    index index.php index.html index.htm;',
        '',
        '    location / {',
        '        try_files $uri $uri/ /index.php?$query_string;',
        '    }',
        '',
    ]

    # 插入自定义伪静态规则
    if rewrite_rules and rewrite_rules.strip():
        for line in rewrite_rules.strip().splitlines():
            config_lines.append('    ' + line)
        config_lines.append('')

    config_lines.extend([
        '    location ~ \\.php$ {',
        '        fastcgi_pass unix:' + php_sock + ';',
        '        fastcgi_index index.php;',
        '        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;',
        '        include fastcgi_params;',
        '    }',
        '',
        '    location ~ /\\.ht {',
        '        deny all;',
        '    }',
        '',
        '    access_log ' + str(log_dir / (domain + '.access.log')) + ';',
        '    error_log ' + str(log_dir / (domain + '.error.log')) + ';',
        '}',
        ''
    ])

    return '\n'.join(config_lines)


# ==================== 数据库站点辅助函数 ====================

def _create_website_database(website_id, domain):
    """为网站创建独立数据库和用户，返回 (db_name, db_user, db_password)"""
    safe_domain = re.sub(r'[^a-zA-Z0-9_]', '_', domain).strip('_')[:30]
    if not safe_domain:
        safe_domain = 'site'
    short_id = re.sub(r'[^a-zA-Z0-9]', '', website_id)[:8]
    db_name = f'site_{safe_domain}_{short_id}'
    db_user = f'user_{safe_domain}_{short_id}'
    db_password = _random_password(16)

    # 使用 mariadb_query 创建数据库和用户
    success, _, stderr = mariadb_query(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4")
    if not success:
        raise RuntimeError(f'创建数据库失败: {stderr}')

    success, _, stderr = mariadb_query(
        f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_password}'"
    )
    if not success:
        raise RuntimeError(f'创建数据库用户失败: {stderr}')

    success, _, stderr = mariadb_query(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost'")
    if not success:
        raise RuntimeError(f'授权数据库失败: {stderr}')

    mariadb_query('FLUSH PRIVILEGES')
    return db_name, db_user, db_password


def _delete_website_database(db_name, db_user):
    """删除网站对应的数据库和用户"""
    if db_name and re.match(r'^[a-zA-Z0-9_]+$', db_name):
        mariadb_query(f"DROP DATABASE IF EXISTS `{db_name}`")
    if db_user and re.match(r'^[a-zA-Z0-9_]+$', db_user):
        mariadb_query(f"DROP USER IF EXISTS '{db_user}'@'localhost'")
    mariadb_query('FLUSH PRIVILEGES')


def _reset_website_database_password(db_user):
    """重置网站数据库用户密码"""
    if not db_user or not re.match(r'^[a-zA-Z0-9_]+$', db_user):
        raise RuntimeError('非法的数据库用户名')
    new_password = _random_password(16)
    success, _, stderr = mariadb_query(
        f"ALTER USER '{db_user}'@'localhost' IDENTIFIED BY '{new_password}'"
    )
    if not success:
        raise RuntimeError(f'重置密码失败: {stderr}')
    mariadb_query('FLUSH PRIVILEGES')
    return new_password


# ==================== 路由：页面 ====================

@app.route('/')
def index():
    """登录页面"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """仪表盘"""
    return render_template('dashboard.html')

@app.route('/websites')
@login_required
def websites():
    """网站管理"""
    return render_template('websites.html')

@app.route('/databases')
@login_required
def databases():
    """数据库管理"""
    return render_template('databases.html')

@app.route('/files')
@login_required
def files():
    """文件管理"""
    return render_template('files.html')

@app.route('/monitor')
@login_required
def monitor():
    """系统监控"""
    return render_template('monitor.html')

@app.route('/settings')
@login_required
def settings():
    """账号设置"""
    return render_template('settings.html')

@app.route('/php')
@login_required
def php_page():
    """PHP 版本与扩展管理"""
    return render_template('php.html')

@app.route('/cron')
@login_required
def cron_page():
    """定时任务管理"""
    return render_template('cron.html')

# ==================== API：认证 ====================

@app.route('/api/login', methods=['POST'])
def api_login():
    """登录"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM account WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row and check_password_hash(row[0], password):
        session['user'] = username
        session.permanent = data.get('remember', False)
        return jsonify({'success': True, 'message': '登录成功'})
    
    return jsonify({'success': False, 'message': '用户名或密码错误'})

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """登出"""
    session.pop('user', None)
    return jsonify({'success': True})

@app.route('/api/check-auth')
def api_check_auth():
    """检查登录状态"""
    if 'user' in session:
        return jsonify({'authenticated': True, 'user': {'username': session['user']}})
    return jsonify({'authenticated': False})

@app.route('/api/account/password', methods=['POST'])
@login_required
def api_change_password():
    """修改密码"""
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    if not old_password or not new_password or not confirm_password:
        return jsonify({'success': False, 'message': '所有字段不能为空'})
    
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': '两次密码输入不一致'})
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': '密码长度至少6位'})
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM account WHERE username = ?', (session['user'],))
    row = cursor.fetchone()
    
    if not row or not check_password_hash(row[0], old_password):
        conn.close()
        return jsonify({'success': False, 'message': '原密码错误'})
    
    cursor.execute(
        'UPDATE account SET password_hash = ?, updated_at = ? WHERE username = ?',
        (generate_password_hash(new_password), datetime.now(), session['user'])
    )
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': '密码修改成功'})

# ==================== API：网站管理 ====================

@app.route('/api/websites')
@login_required
def api_list_websites():
    """获取网站列表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, domain, root_path, php_version, status, port, rewrite_rules, '
            'db_name, db_user, db_password, created_at FROM websites ORDER BY created_at DESC'
        )
        rows = cursor.fetchall()
        conn.close()

        websites = []
        for row in rows:
            websites.append({
                'id': row[0],
                'domain': row[1],
                'root_path': row[2],
                'php_version': row[3],
                'status': row[4],
                'port': row[5],
                'rewrite_rules': row[6] or '',
                'db_name': row[7] or '',
                'db_user': row[8] or '',
                'db_password': row[9] or '',
                'created_at': row[10]
            })

        return jsonify({'websites': websites})
    except Exception as e:
        return jsonify({'websites': [], 'error': str(e)})

@app.route('/api/websites', methods=['POST'])
@login_required
def api_create_website():
    """创建网站"""
    data = request.get_json()
    domain = data.get('domain', '').strip()
    port = data.get('port', 8080)
    root = data.get('root', '').strip()
    php_version = data.get('php_version', '8.0')
    rewrite_rules = data.get('rewrite_rules', '')
    create_database = data.get('create_database', False)
    
    if not domain:
        return jsonify({'success': False, 'message': '域名不能为空'})
    
    # 验证端口范围
    try:
        port = int(port)
    except:
        return jsonify({'success': False, 'message': '端口格式不正确'})
    
    if port < 1024 or port > 65535:
        return jsonify({'success': False, 'message': '端口范围必须在 1024-65535 之间'})
    
    # 验证域名格式（支持域名、IP地址、localhost，不再允许带端口）
    domain_pattern = r'^[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})*$'
    ip_pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$'
    localhost_pattern = r'^localhost$'
    
    if not (re.match(domain_pattern, domain) or re.match(ip_pattern, domain) or re.match(localhost_pattern, domain)):
        return jsonify({'success': False, 'message': '域名格式不正确，支持域名、IP地址、localhost（不带端口）'})
    
    # 检查端口是否已被其他网站使用
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM websites WHERE port = ?', (port,))
    port_count = cursor.fetchone()[0]
    conn.close()
    
    if port_count > 0:
        return jsonify({'success': False, 'message': f'端口 {port} 已被其他网站使用，请选择其他端口'})
    
    # 生成安全的目录和配置文件名
    safe_domain = domain.replace(':', '_').replace('/', '_')

    # 设置默认根目录
    if not root:
        if IS_PROOT and IS_DEBIAN_UBUNTU:
            root = str(WEB_ROOT_BASE / safe_domain)
        else:
            root = str(WWW_DIR / safe_domain)

    # 创建网站目录
    root_path = Path(root)
    try:
        root_path.mkdir(parents=True, exist_ok=True)
        # 创建默认 index.html
        (root_path / 'index.html').write_text(
            '<!DOCTYPE html>\n'
            '<html>\n<head>\n'
            '<title>Welcome to ' + domain + '</title>\n'
            '</head>\n<body>\n'
            '<h1>Welcome to ' + domain + '</h1>\n'
            '<p>访问地址: http://' + domain + ':' + str(port) + '</p>\n'
            '</body>\n</html>\n'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': '创建目录失败: ' + str(e)})

    # 生成 Nginx 配置
    config_content = generate_nginx_config(domain, root, php_version, port, rewrite_rules)
    config_file = get_nginx_config_path(domain, port)

    try:
        NGINX_CONF_DIR.mkdir(parents=True, exist_ok=True)
        config_file.write_text(config_content)
    except Exception as e:
        return jsonify({'success': False, 'message': '创建配置失败: ' + str(e)})

    # 保存到数据库
    website_id = str(uuid.uuid4())
    db_name = ''
    db_user = ''
    db_password = ''

    if create_database and (IS_PROOT and IS_DEBIAN_UBUNTU):
        try:
            db_name, db_user, db_password = _create_website_database(website_id, domain)
        except Exception as e:
            return jsonify({'success': False, 'message': '创建数据库失败: ' + str(e)})

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO websites (id, domain, root_path, php_version, status, port, rewrite_rules, '
            'db_name, db_user, db_password) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (website_id, domain, root, php_version, 'running', port, rewrite_rules,
             db_name, db_user, db_password)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': '域名已存在'})
    conn.close()

    # 重新加载 Nginx 配置（如果 Nginx 已在运行）
    try:
        reload_result = subprocess.run(['nginx', '-s', 'reload'], capture_output=True, timeout=5)
        if reload_result.returncode != 0:
            # Nginx 未运行，尝试启动它
            subprocess.run(['nginx'], capture_output=True, timeout=5)
    except Exception:
        pass

    result = {'success': True, 'message': '网站创建成功', 'id': website_id}
    if db_name:
        result['database'] = {
            'db_name': db_name,
            'db_user': db_user,
            'db_password': db_password
        }
    return jsonify(result)

@app.route('/api/websites/<website_id>', methods=['DELETE'])
@login_required
def api_delete_website(website_id):
    """删除网站"""
    data = request.get_json(silent=True) or {}
    delete_database = data.get('delete_database', False)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT domain, root_path, port, db_name, db_user FROM websites WHERE id = ?',
        (website_id,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'success': False, 'message': '网站不存在'})

    domain, root_path, port, db_name, db_user = row

    # 删除 Nginx 配置（正常和停止状态）
    config_file = get_nginx_config_path(domain, port)
    disabled_file = get_nginx_disabled_path(domain, port)
    if config_file.exists():
        config_file.unlink()
    if disabled_file.exists():
        disabled_file.unlink()

    # 兼容旧配置文件命名
    old_config_file = NGINX_CONF_DIR / (get_safe_domain(domain) + '.conf')
    if old_config_file.exists():
        old_config_file.unlink()

    # 可选删除数据库
    if delete_database and db_name:
        try:
            _delete_website_database(db_name, db_user)
        except Exception:
            pass

    # 从数据库删除
    cursor.execute('DELETE FROM websites WHERE id = ?', (website_id,))
    conn.commit()
    conn.close()

    # 重新加载 Nginx 配置
    try:
        subprocess.run(['nginx', '-s', 'reload'], capture_output=True, timeout=5)
    except Exception:
        pass

    return jsonify({'success': True, 'message': '网站已删除'})

@app.route('/api/websites/<website_id>/start', methods=['POST'])
@login_required
def api_start_website(website_id):
    """启动网站"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT domain, root_path, php_version, port, rewrite_rules FROM websites WHERE id = ?',
        (website_id,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'success': False, 'message': '网站不存在'})

    domain, root_path, php_version, port, rewrite_rules = row

    config_file = get_nginx_config_path(domain, port)
    disabled_file = get_nginx_disabled_path(domain, port)

    if not config_file.exists():
        # 如果有 .disabled 文件，重命名回来
        if disabled_file.exists():
            disabled_file.rename(config_file)
        else:
            # 配置文件不存在，重新生成
            config_content = generate_nginx_config(domain, root_path, php_version, port, rewrite_rules or '')
            try:
                NGINX_CONF_DIR.mkdir(parents=True, exist_ok=True)
                config_file.write_text(config_content)
            except Exception as e:
                conn.close()
                return jsonify({'success': False, 'message': '创建配置失败: ' + str(e)})

    # 重载 Nginx
    success, _, stderr = run_command(['nginx', '-s', 'reload'])
    if not success:
        # 尝试启动 Nginx
        success, _, stderr = run_command(['nginx'])
        if not success:
            conn.close()
            return jsonify({'success': False, 'message': 'Nginx 启动失败: ' + str(stderr)})

    cursor.execute('UPDATE websites SET status = ? WHERE id = ?', ('running', website_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '网站已启动'})

@app.route('/api/websites/<website_id>/stop', methods=['POST'])
@login_required
def api_stop_website(website_id):
    """停止网站"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT domain, port FROM websites WHERE id = ?', (website_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'success': False, 'message': '网站不存在'})

    domain, port = row
    config_file = get_nginx_config_path(domain, port)
    disabled_file = get_nginx_disabled_path(domain, port)

    # 重命名配置文件以停止网站
    if config_file.exists():
        config_file.rename(disabled_file)

    # 重载 Nginx
    run_command(['nginx', '-s', 'reload'])

    cursor.execute('UPDATE websites SET status = ? WHERE id = ?', ('stopped', website_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '网站已停止'})

@app.route('/api/websites/<website_id>/restart', methods=['POST'])
@login_required
def api_restart_website(website_id):
    """重启网站"""
    stop_result = api_stop_website(website_id)
    # 如果停止失败，直接返回错误（jsonify 默认状态码为 200，需检查 success 字段）
    if hasattr(stop_result, 'get_json'):
        stop_data = stop_result.get_json()
        if stop_data and not stop_data.get('success', True):
            return stop_result

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT domain, port FROM websites WHERE id = ?', (website_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        domain, port = row
        disabled_file = get_nginx_disabled_path(domain, port)
        config_file = get_nginx_config_path(domain, port)
        if disabled_file.exists():
            disabled_file.rename(config_file)

    return api_start_website(website_id)


@app.route('/api/websites/<website_id>', methods=['PUT'])
@login_required
def api_update_website(website_id):
    """编辑网站（目前支持修改伪静态规则）"""
    data = request.get_json()
    rewrite_rules = data.get('rewrite_rules')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT domain, root_path, php_version, port, rewrite_rules FROM websites WHERE id = ?',
        (website_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'message': '网站不存在'})

    domain, root_path, php_version, port, current_rules = row

    if rewrite_rules is not None and rewrite_rules != current_rules:
        cursor.execute(
            'UPDATE websites SET rewrite_rules = ? WHERE id = ?',
            (rewrite_rules, website_id)
        )
        conn.commit()

        # 重新生成配置文件
        config_file = get_nginx_config_path(domain, port)
        if config_file.exists():
            config_content = generate_nginx_config(domain, root_path, php_version, port, rewrite_rules)
            try:
                config_file.write_text(config_content)
                run_command(['nginx', '-s', 'reload'])
            except Exception as e:
                conn.close()
                return jsonify({'success': False, 'message': '更新配置失败: ' + str(e)})

    conn.close()
    return jsonify({'success': True, 'message': '网站已更新'})


@app.route('/api/websites/<website_id>/db', methods=['GET'])
@login_required
def api_get_website_db(website_id):
    """获取网站独立数据库信息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT domain, db_name, db_user, db_password FROM websites WHERE id = ?',
        (website_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'success': False, 'message': '网站不存在'})

    domain, db_name, db_user, db_password = row
    return jsonify({
        'success': True,
        'domain': domain,
        'db_name': db_name or '',
        'db_user': db_user or '',
        'db_password': db_password or ''
    })


@app.route('/api/websites/<website_id>/db', methods=['POST'])
@login_required
def api_manage_website_db(website_id):
    """管理网站独立数据库"""
    data = request.get_json()
    action = data.get('action', '')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT domain, db_name, db_user, db_password FROM websites WHERE id = ?',
        (website_id,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'success': False, 'message': '网站不存在'})

    domain, db_name, db_user, db_password = row

    if action == 'create':
        if db_name:
            conn.close()
            return jsonify({'success': False, 'message': '数据库已存在'})
        try:
            new_db_name, new_db_user, new_db_password = _create_website_database(website_id, domain)
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': str(e)})
        cursor.execute(
            'UPDATE websites SET db_name = ?, db_user = ?, db_password = ? WHERE id = ?',
            (new_db_name, new_db_user, new_db_password, website_id)
        )
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'message': '数据库创建成功',
            'database': {
                'db_name': new_db_name,
                'db_user': new_db_user,
                'db_password': new_db_password
            }
        })

    elif action == 'delete':
        if db_name:
            try:
                _delete_website_database(db_name, db_user)
            except Exception as e:
                conn.close()
                return jsonify({'success': False, 'message': f'删除数据库失败: {str(e)}'})
        cursor.execute(
            'UPDATE websites SET db_name = ?, db_user = ?, db_password = ? WHERE id = ?',
            ('', '', '', website_id)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '数据库已删除'})

    elif action == 'reset_password':
        if not db_user:
            conn.close()
            return jsonify({'success': False, 'message': '数据库用户不存在'})
        try:
            new_password = _reset_website_database_password(db_user)
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': str(e)})
        cursor.execute(
            'UPDATE websites SET db_password = ? WHERE id = ?',
            (new_password, website_id)
        )
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'message': '密码已重置',
            'db_password': new_password
        })

    conn.close()
    return jsonify({'success': False, 'message': '未知的操作类型'})


@app.route('/api/rewrite/templates')
@login_required
def api_rewrite_templates():
    """返回常见伪静态模板"""
    templates = {
        'WordPress': 'try_files $uri $uri/ /index.php?$args;',
        'ThinkPHP': (
            'if (!-e $request_filename) {\n'
            '    rewrite ^(.*)$ /index.php?s=$1 last;\n'
            '    break;\n'
            '}'
        ),
        'Laravel': 'try_files $uri $uri/ /index.php?$query_string;',
        'Typecho': (
            'if (!-e $request_filename) {\n'
            '    rewrite ^(.*)$ /index.php$1 last;\n'
            '}'
        )
    }
    return jsonify({'success': True, 'templates': templates})


# ==================== 数据库工具函数 ====================

def run_mariadb_command(args):
    """运行 MariaDB/MySQL 命令，自动选择可用的二进制文件"""
    # 候选命令优先级：mariadb > mysql
    cmd_candidates = [
        ['mariadb'] + args,
        ['mysql'] + args,
    ]
    for cmd in cmd_candidates:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True, result.stdout.strip(), result.stderr.strip()
            # 即使失败也返回，让调用方看到错误信息
            return False, result.stdout.strip(), result.stderr.strip()
        except FileNotFoundError:
            continue
        except Exception as e:
            return False, '', str(e)
    return False, '', '未找到可用的 MariaDB/MySQL 命令'


def run_mariadb_shell():
    """通过 shell 运行 mariadb，使用 -u root 参数"""
    # 直接用 -u root 参数尝试运行
    try:
        result = subprocess.run(
            ['mariadb', '-u', 'root'],
            capture_output=True, text=True, timeout=30,
            input=''
        )
        if result.returncode == 0:
            return True
        return False
    except Exception:
        return False


def mariadb_query(sql):
    """运行一个 SQL 查询，优先使用 mariadb -u root"""
    try:
        result = subprocess.run(
            ['mariadb', '-u', 'root', '-e', sql],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, result.stdout.strip(), ''
        return False, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        try:
            # 回退到 mysql
            result = subprocess.run(
                ['mysql', '-u', 'root', '-e', sql],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return True, result.stdout.strip(), ''
            return False, result.stdout.strip(), result.stderr.strip()
        except FileNotFoundError:
            # 再尝试不带 -u root
            try:
                result = subprocess.run(
                    ['mariadb', '-e', sql],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    return True, result.stdout.strip(), ''
                return False, result.stdout.strip(), result.stderr.strip()
            except FileNotFoundError:
                return False, '', '未找到 mariadb/mysql 命令'
    except Exception as e:
        return False, '', str(e)


def mariadb_dump(db_name, output_file):
    """备份数据库到文件"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dump_candidates = [
        ['mariadb-dump', '-u', 'root', db_name],
        ['mariadbdump', '-u', 'root', db_name],
        ['mysqldump', '-u', 'root', db_name],
        ['mariadb-dump', db_name],
        ['mysqldump', db_name],
    ]
    last_error = '备份失败：未找到可用的 mysqldump/mariadb-dump 命令'
    for cmd in dump_candidates:
        try:
            with open(output_file, 'w') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=120)
            if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
                return True, ''
            last_error = result.stderr.decode('utf-8', errors='ignore').strip() if result.stderr else '备份命令执行失败'
        except FileNotFoundError:
            continue
        except Exception as e:
            last_error = str(e)
            continue
    return False, last_error


def mariadb_restore(db_name, input_file):
    """从文件恢复数据库"""
    restore_candidates = [
        ['mariadb', '-u', 'root', db_name],
        ['mysql', '-u', 'root', db_name],
        ['mariadb', db_name],
        ['mysql', db_name],
    ]
    last_error = '恢复失败：未找到可用的 mariadb/mysql 命令'
    for cmd in restore_candidates:
        try:
            with open(input_file, 'r') as f:
                result = subprocess.run(cmd, stdin=f, capture_output=True, timeout=120)
            if result.returncode == 0:
                return True, ''
            last_error = result.stderr.decode('utf-8', errors='ignore').strip() if result.stderr else '恢复命令执行失败'
        except FileNotFoundError:
            continue
        except Exception as e:
            last_error = str(e)
            continue
    return False, last_error


def quote_identifier(name):
    """安全地引用 SQL 标识符（数据库名、表名等），仅允许基本字符。"""
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValueError('非法的数据库标识符')
    return '`' + name + '`'


def quote_string(value):
    """安全地转义 SQL 字符串字面量。"""
    return "'" + value.replace("'", "''").replace("\\", "\\\\") + "'"


# ==================== API：数据库管理 ====================

@app.route('/api/databases')
@login_required
def api_list_databases():
    """获取数据库列表"""
    success, stdout, stderr = mariadb_query('SHOW DATABASES')

    databases = []
    if success and stdout:
        for db in stdout.split('\n')[1:]:
            db = db.strip()
            if db and db not in ('information_schema', 'mysql', 'performance_schema'):
                try:
                    db_quoted = quote_identifier(db)
                except ValueError:
                    continue

                # 获取数据库大小
                size_sql = f"SELECT SUM(data_length + index_length) FROM information_schema.tables WHERE table_schema = {db_quoted}"
                size_success, size_stdout, _ = mariadb_query(size_sql)
                size = 0
                if size_success and size_stdout:
                    try:
                        lines = size_stdout.strip().split('\n')
                        if len(lines) >= 2 and lines[1]:
                            size = int(float(lines[1]))
                    except Exception:
                        pass

                # 获取表数量
                tables_sql = f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = {db_quoted}"
                tables_success, tables_stdout, _ = mariadb_query(tables_sql)
                tables = 0
                if tables_success and tables_stdout:
                    try:
                        lines = tables_stdout.strip().split('\n')
                        if len(lines) >= 2 and lines[1]:
                            tables = int(lines[1])
                    except Exception:
                        pass

                databases.append({
                    'name': db,
                    'charset': 'utf8mb4',
                    'size': size,
                    'tables': tables
                })

    return jsonify({'databases': databases})


@app.route('/api/databases', methods=['POST'])
@login_required
def api_create_database():
    """创建数据库"""
    data = request.get_json()
    name = data.get('name', '').strip()
    charset = data.get('charset', 'utf8mb4')
    user = data.get('user', '').strip()
    password = data.get('password', '')

    if not name:
        return jsonify({'success': False, 'message': '数据库名不能为空'})

    # 验证数据库名
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        return jsonify({'success': False, 'message': '数据库名只能包含字母、数字和下划线'})

    # 验证字符集白名单
    allowed_charsets = {'utf8mb4', 'utf8', 'latin1', 'gbk', 'gb2312'}
    if charset not in allowed_charsets:
        return jsonify({'success': False, 'message': '不支持的字符集'})

    # 创建数据库
    try:
        db_quoted = quote_identifier(name)
    except ValueError:
        return jsonify({'success': False, 'message': '数据库名包含非法字符'})

    success, _, stderr = mariadb_query(f'CREATE DATABASE {db_quoted} CHARACTER SET {charset}')
    if not success:
        return jsonify({'success': False, 'message': '创建数据库失败: ' + stderr})

    # 创建用户并授权（可选）
    if user and password:
        if not re.match(r'^[a-zA-Z0-9_]+$', user):
            return jsonify({'success': False, 'message': '数据库用户名只能包含字母、数字和下划线'})
        safe_user = quote_string(user)
        safe_pwd = quote_string(password)
        mariadb_query(f"CREATE USER IF NOT EXISTS {safe_user}@'localhost' IDENTIFIED BY {safe_pwd}")
        mariadb_query(f"GRANT ALL PRIVILEGES ON {db_quoted}.* TO {safe_user}@'localhost'")
        mariadb_query('FLUSH PRIVILEGES')

    return jsonify({'success': True, 'message': '数据库创建成功'})


@app.route('/api/databases/<name>', methods=['DELETE'])
@login_required
def api_delete_database(name):
    """删除数据库"""
    try:
        db_quoted = quote_identifier(name)
    except ValueError:
        return jsonify({'success': False, 'message': '数据库名包含非法字符'})

    success, _, stderr = mariadb_query(f'DROP DATABASE IF EXISTS {db_quoted}')
    if not success:
        return jsonify({'success': False, 'message': '删除数据库失败: ' + stderr})

    return jsonify({'success': True, 'message': '数据库已删除'})


@app.route('/api/databases/<name>/backup')
@login_required
def api_backup_database(name):
    """备份数据库"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = BACKUP_DIR / (name + '_' + timestamp + '.sql')

    success, error = mariadb_dump(name, backup_file)
    if not success:
        return jsonify({'success': False, 'message': '备份失败: ' + error})

    # 保存备份记录
    backup_id = str(uuid.uuid4())
    file_size = backup_file.stat().st_size if backup_file.exists() else 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO database_backups (id, database_name, file_path, size) VALUES (?, ?, ?, ?)',
        (backup_id, name, str(backup_file), file_size)
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '备份成功', 'file': str(backup_file)})


@app.route('/api/databases/<name>/restore', methods=['POST'])
@login_required
def api_restore_database(name):
    """恢复数据库"""
    data = request.get_json()
    backup_file = data.get('file', '')

    if not backup_file:
        return jsonify({'success': False, 'message': '请选择备份文件'})

    backup_path, allowed = resolve_allowed_path(backup_file)
    if not allowed or backup_path is None or not backup_path.exists():
        return jsonify({'success': False, 'message': '备份文件不存在或路径非法'})

    try:
        db_quoted = quote_identifier(name)
    except ValueError:
        return jsonify({'success': False, 'message': '数据库名包含非法字符'})

    # 先确保数据库存在
    mariadb_query(f'CREATE DATABASE IF NOT EXISTS {db_quoted}')

    success, error = mariadb_restore(name, backup_path)
    if not success:
        return jsonify({'success': False, 'message': '恢复失败: ' + error})

    return jsonify({'success': True, 'message': '数据库已恢复'})

@app.route('/api/databases/<name>/backups')
@login_required
def api_list_database_backups(name):
    """获取数据库备份列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, file_path, size, created_at FROM database_backups WHERE database_name = ? ORDER BY created_at DESC',
        (name,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    backups = []
    for row in rows:
        backups.append({
            'id': row[0],
            'file': row[1],
            'size': row[2],
            'created_at': row[3]
        })

    return jsonify({'backups': backups})

@app.route('/api/databases/import', methods=['POST'])
@login_required
def api_import_database():
    """导入 .sql 文件到数据库"""
    is_upload = bool(request.files.get('file'))

    if is_upload:
        db_name = request.form.get('name', '').strip()
    else:
        data = request.get_json(silent=True) or {}
        db_name = data.get('name', '').strip()

    if not db_name:
        return jsonify({'success': False, 'message': '请提供目标数据库名'})

    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        return jsonify({'success': False, 'message': '数据库名只能包含字母、数字和下划线'})

    tmp_path = None
    is_temp = False
    if is_upload:
        f = request.files['file']
        if not f.filename:
            return jsonify({'success': False, 'message': '未选择文件'})
        if not f.filename.lower().endswith('.sql'):
            return jsonify({'success': False, 'message': '只支持 .sql 文件'})
        # 保存到临时目录
        tmp_dir = DATA_DIR / 'tmp'
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / ('import_' + str(int(time.time())) + '_' + secure_filename(f.filename))
        f.save(str(tmp_path))
        is_temp = True
    else:
        # JSON 方式：指定文件路径
        data = request.get_json(silent=True) or {}
        sql_path = data.get('path', '')
        if not sql_path:
            return jsonify({'success': False, 'message': '请提供 SQL 文件'})
        tmp_path, allowed = resolve_allowed_path(sql_path)
        if not allowed or tmp_path is None or not tmp_path.exists():
            return jsonify({'success': False, 'message': 'SQL 文件不存在或路径非法'})

    try:
        db_quoted = quote_identifier(db_name)
    except ValueError:
        return jsonify({'success': False, 'message': '数据库名包含非法字符'})

    # 确保数据库存在
    mariadb_query(f'CREATE DATABASE IF NOT EXISTS {db_quoted}')

    success, error = mariadb_restore(db_name, tmp_path)
    # 清理临时文件（仅限上传产生的临时文件）
    if is_temp and tmp_path and tmp_path.exists():
        try:
            tmp_path.unlink()
        except Exception:
            pass

    if not success:
        return jsonify({'success': False, 'message': '导入失败: ' + error})

    return jsonify({'success': True, 'message': '数据库已成功导入'})


# ==================== API：PHP 版本与扩展管理 ====================

@app.route('/api/php/versions')
@login_required
def api_php_versions():
    """返回系统已安装和可安装的 PHP 版本列表"""
    versions = []
    for ver in SUPPORTED_PHP_VERSIONS:
        package = f'php{ver}-fpm'
        installed = False
        if IS_PROOT and IS_DEBIAN_UBUNTU:
            installed = _is_package_installed(package)
        else:
            # Termux 下检查 php-fpm 命令是否可用（不区分版本）
            success, _, _ = run_command(['which', f'php{ver}-fpm'])
            if not success:
                success, _, _ = run_command(['which', 'php-fpm'])
            installed = success
        versions.append({
            'version': ver,
            'installed': installed,
            'fpm_running': _is_php_fpm_running(ver) if installed else False
        })
    return jsonify({'success': True, 'versions': versions})


@app.route('/api/php/versions', methods=['POST'])
@login_required
def api_manage_php_version():
    """安装或卸载 PHP 版本"""
    data = request.get_json()
    version = data.get('version', '').strip()
    action = data.get('action', '')

    if version not in SUPPORTED_PHP_VERSIONS:
        return jsonify({'success': False, 'message': '不支持的 PHP 版本'})

    if action not in ('install', 'uninstall'):
        return jsonify({'success': False, 'message': '操作类型错误'})

    if not (IS_PROOT and IS_DEBIAN_UBUNTU):
        return jsonify({'success': False, 'message': '当前环境不支持 apt 管理 PHP 版本'})

    package = f'php{version}-fpm'
    if action == 'install':
        success, stdout, stderr = run_command(['apt-get', 'install', '-y', package], timeout=300)
    else:
        success, stdout, stderr = run_command(['apt-get', 'remove', '--purge', '-y', package], timeout=300)

    if not success:
        return jsonify({'success': False, 'message': f'PHP {version} {action} 失败: {stderr or stdout}'})

    return jsonify({'success': True, 'message': f'PHP {version} {"安装" if action == "install" else "卸载"}成功'})


@app.route('/api/php/extensions')
@login_required
def api_php_extensions():
    """列出某 PHP 版本的已安装/可安装扩展"""
    version = request.args.get('version', '8.0')
    if version not in SUPPORTED_PHP_VERSIONS:
        return jsonify({'success': False, 'message': '不支持的 PHP 版本'})

    extensions = []
    if IS_PROOT and IS_DEBIAN_UBUNTU:
        success, stdout, _ = run_command([f'php{version}', '-m'])
        installed_modules = set()
        if success and stdout:
            installed_modules = {line.strip().lower() for line in stdout.splitlines() if line.strip()}

        for ext in COMMON_PHP_EXTENSIONS:
            installed = ext.lower() in installed_modules
            extensions.append({
                'extension': ext,
                'installed': installed,
                'package': f'php{version}-{ext}'
            })
    else:
        # Termux 环境：统一检查 php -m
        success, stdout, _ = run_command(['php', '-m'])
        installed_modules = set()
        if success and stdout:
            installed_modules = {line.strip().lower() for line in stdout.splitlines() if line.strip()}
        for ext in COMMON_PHP_EXTENSIONS:
            extensions.append({
                'extension': ext,
                'installed': ext.lower() in installed_modules,
                'package': ext
            })

    return jsonify({'success': True, 'extensions': extensions})


@app.route('/api/php/extensions', methods=['POST'])
@login_required
def api_manage_php_extension():
    """安装或卸载 PHP 扩展"""
    data = request.get_json()
    version = data.get('version', '').strip()
    extension = data.get('extension', '').strip().lower()
    action = data.get('action', '')

    if version not in SUPPORTED_PHP_VERSIONS:
        return jsonify({'success': False, 'message': '不支持的 PHP 版本'})

    if not extension or extension not in [e.lower() for e in COMMON_PHP_EXTENSIONS]:
        return jsonify({'success': False, 'message': '不支持的扩展'})

    if action not in ('install', 'uninstall'):
        return jsonify({'success': False, 'message': '操作类型错误'})

    if not (IS_PROOT and IS_DEBIAN_UBUNTU):
        return jsonify({'success': False, 'message': '当前环境不支持 apt 管理 PHP 扩展'})

    package = f'php{version}-{extension}'
    if action == 'install':
        success, stdout, stderr = run_command(['apt-get', 'install', '-y', package], timeout=300)
    else:
        success, stdout, stderr = run_command(['apt-get', 'remove', '--purge', '-y', package], timeout=300)

    if not success:
        return jsonify({'success': False, 'message': f'{package} {action} 失败: {stderr or stdout}'})

    return jsonify({'success': True, 'message': f'{package} {"安装" if action == "install" else "卸载"}成功'})


@app.route('/api/php/fpm/restart', methods=['POST'])
@login_required
def api_restart_php_fpm():
    """重启指定 PHP-FPM"""
    data = request.get_json() or {}
    version = data.get('version', '8.0')

    if version not in SUPPORTED_PHP_VERSIONS:
        return jsonify({'success': False, 'message': '不支持的 PHP 版本'})

    service = _php_fpm_service_name(version)

    # 先尝试 service 命令
    success, _, stderr = run_command(['service', service, 'restart'], timeout=30)
    if success:
        return jsonify({'success': True, 'message': f'PHP {version} FPM 已重启'})

    # 失败则尝试 systemctl
    success, _, stderr2 = run_command(['systemctl', 'restart', service], timeout=30)
    if success:
        return jsonify({'success': True, 'message': f'PHP {version} FPM 已重启'})

    # 最后尝试 kill 后手动启动
    run_command(['pkill', '-f', service])
    success, _, stderr3 = run_command([f'php-fpm{version}'], timeout=10)
    if not success:
        # 某些系统命令名为 php8.0-fpm
        success, _, stderr3 = run_command([service], timeout=10)

    if success:
        return jsonify({'success': True, 'message': f'PHP {version} FPM 已重启'})

    return jsonify({
        'success': False,
        'message': f'重启 PHP {version} FPM 失败: {stderr or stderr2 or stderr3}'
    })


# ==================== API：文件管理 ====================

@app.route('/api/files')
@login_required
def api_list_files():
    """获取文件列表"""
    path = request.args.get('path', str(WWW_DIR))

    path_obj, allowed = resolve_allowed_path(path)
    if not allowed or path_obj is None:
        path_obj = WWW_DIR

    if not path_obj.exists():
        path_obj.mkdir(parents=True, exist_ok=True)

    files = []
    try:
        for item in path_obj.iterdir():
            stat = item.stat()
            files.append({
                'name': item.name,
                'type': 'directory' if item.is_dir() else 'file',
                'size': stat.st_size if item.is_file() else 0,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'permissions': oct(stat.st_mode)[-3:]
            })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

    # 排序：目录在前，然后按名称排序
    files.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))

    www_resolved = WWW_DIR.resolve()
    is_root = path_obj.resolve() == www_resolved

    return jsonify({
        'path': str(path_obj),
        'parent': str(path_obj.parent) if not is_root else None,
        'files': files
    })

@app.route('/api/files/upload', methods=['POST'])
@login_required
def api_upload_file():
    """上传文件"""
    path = request.form.get('path', str(WWW_DIR))

    base_path, allowed = resolve_allowed_path(path)
    if not allowed or base_path is None:
        return jsonify({'success': False, 'message': '非法路径'})

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有选择文件'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'})

    filename = secure_filename(file.filename)
    filepath = base_path / filename

    # 校验最终路径仍在允许范围内（避免文件名中包含 ../）
    final_path, final_allowed = resolve_allowed_path(filepath)
    if not final_allowed or final_path is None:
        return jsonify({'success': False, 'message': '非法文件名'})

    try:
        file.save(final_path)
    except Exception as e:
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'})

    return jsonify({'success': True, 'message': '上传成功'})

@app.route('/api/files/download')
@login_required
def api_download_file():
    """下载文件"""
    path = request.args.get('path', '')

    filepath, allowed = resolve_allowed_path(path)
    if not allowed or filepath is None:
        return jsonify({'success': False, 'message': '非法路径'})

    if not filepath.exists() or not filepath.is_file():
        return jsonify({'success': False, 'message': '文件不存在'})

    return send_file(filepath, as_attachment=True)

@app.route('/api/files/mkdir', methods=['POST'])
@login_required
def api_mkdir():
    """创建目录"""
    data = request.get_json()
    path = data.get('path', '')
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'success': False, 'message': '目录名不能为空'})

    base_path, allowed = resolve_allowed_path(path)
    if not allowed or base_path is None:
        return jsonify({'success': False, 'message': '非法路径'})

    new_dir, dir_allowed = resolve_allowed_path(base_path / name)
    if not dir_allowed or new_dir is None:
        return jsonify({'success': False, 'message': '非法目录名'})

    try:
        new_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'})

    return jsonify({'success': True, 'message': '目录创建成功'})

@app.route('/api/files/rename', methods=['POST'])
@login_required
def api_rename_file():
    """重命名文件/目录"""
    data = request.get_json()
    old_path = data.get('old_path', '')
    new_name = data.get('new_name', '').strip()

    if not new_name:
        return jsonify({'success': False, 'message': '新名称不能为空'})

    old_file, allowed = resolve_allowed_path(old_path)
    if not allowed or old_file is None:
        return jsonify({'success': False, 'message': '非法路径'})

    new_file, new_allowed = resolve_allowed_path(old_file.parent / new_name)
    if not new_allowed or new_file is None:
        return jsonify({'success': False, 'message': '非法新名称'})

    try:
        old_file.rename(new_file)
    except Exception as e:
        return jsonify({'success': False, 'message': f'重命名失败: {str(e)}'})

    return jsonify({'success': True, 'message': '重命名成功'})

@app.route('/api/files/delete', methods=['POST'])
@login_required
def api_delete_file():
    """删除文件/目录"""
    data = request.get_json()
    path = data.get('path', '')

    filepath, allowed = resolve_allowed_path(path)
    if not allowed or filepath is None:
        return jsonify({'success': False, 'message': '非法路径'})

    try:
        if filepath.is_dir():
            shutil.rmtree(filepath)
        else:
            filepath.unlink()
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})

    return jsonify({'success': True, 'message': '删除成功'})

@app.route('/api/files/read')
@login_required
def api_read_file():
    """读取文件内容"""
    path = request.args.get('path', '')

    filepath, allowed = resolve_allowed_path(path)
    if not allowed or filepath is None:
        return jsonify({'success': False, 'message': '非法路径'})

    if not filepath.exists() or not filepath.is_file():
        return jsonify({'success': False, 'message': '文件不存在'})

    # 检查文件大小
    if filepath.stat().st_size > 1024 * 1024:  # 1MB
        return jsonify({'success': False, 'message': '文件过大，请使用下载功能'})

    try:
        content = filepath.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return jsonify({'success': False, 'message': '无法读取此文件类型'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取失败: {str(e)}'})

    return jsonify({'success': True, 'content': content})

@app.route('/api/files/write', methods=['POST'])
@login_required
def api_write_file():
    """写入文件内容，支持大文件分块写入"""
    data = request.get_json()
    path = data.get('path', '')
    content = data.get('content', '')

    filepath, allowed = resolve_allowed_path(path)
    if not allowed or filepath is None:
        return jsonify({'success': False, 'message': '非法路径'})

    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        content_bytes = content.encode('utf-8')
        chunk_size = 1024 * 1024  # 1MB
        if len(content_bytes) > chunk_size:
            with open(filepath, 'wb') as f:
                for i in range(0, len(content_bytes), chunk_size):
                    f.write(content_bytes[i:i + chunk_size])
        else:
            filepath.write_text(content, encoding='utf-8')
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'})

    return jsonify({'success': True, 'message': '保存成功'})


@app.route('/api/files/extract', methods=['POST'])
@login_required
def api_extract_file():
    """解压文件"""
    data = request.get_json()
    path = data.get('path', '').strip()
    dest = data.get('dest', '').strip()

    if not path or not dest:
        return jsonify({'success': False, 'message': '路径和目标目录不能为空'})

    src_path, src_allowed = resolve_allowed_path(path)
    dest_path, dest_allowed = resolve_allowed_path(dest)

    if not src_allowed or src_path is None or not src_path.exists():
        return jsonify({'success': False, 'message': '压缩文件不存在或路径非法'})
    if not dest_allowed or dest_path is None:
        return jsonify({'success': False, 'message': '目标目录路径非法'})

    dest_path.mkdir(parents=True, exist_ok=True)
    lower_name = src_path.name.lower()

    try:
        if lower_name.endswith('.zip'):
            success, stdout, stderr = run_command(
                ['unzip', '-o', str(src_path), '-d', str(dest_path)],
                timeout=300
            )
        elif lower_name.endswith('.tar.gz') or lower_name.endswith('.tgz'):
            success, stdout, stderr = run_command(
                ['tar', '-xzf', str(src_path), '-C', str(dest_path)],
                timeout=300
            )
        elif lower_name.endswith('.tar.bz2') or lower_name.endswith('.tbz2'):
            success, stdout, stderr = run_command(
                ['tar', '-xjf', str(src_path), '-C', str(dest_path)],
                timeout=300
            )
        elif lower_name.endswith('.tar.xz') or lower_name.endswith('.txz'):
            success, stdout, stderr = run_command(
                ['tar', '-xJf', str(src_path), '-C', str(dest_path)],
                timeout=300
            )
        elif lower_name.endswith('.tar'):
            success, stdout, stderr = run_command(
                ['tar', '-xf', str(src_path), '-C', str(dest_path)],
                timeout=300
            )
        else:
            return jsonify({'success': False, 'message': '不支持的压缩格式'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'解压失败: {str(e)}'})

    if not success:
        return jsonify({'success': False, 'message': f'解压失败: {stderr or stdout}'})

    return jsonify({'success': True, 'message': '解压成功', 'dest': str(dest_path)})


@app.route('/api/files/compress', methods=['POST'])
@login_required
def api_compress_file():
    """压缩文件/目录"""
    data = request.get_json()
    paths = data.get('paths', [])
    name = data.get('name', '').strip()
    fmt = data.get('format', 'zip')

    if not paths:
        return jsonify({'success': False, 'message': '请选择要压缩的文件'})
    if not name:
        return jsonify({'success': False, 'message': '压缩文件名不能为空'})
    if fmt not in ('zip', 'tar.gz'):
        return jsonify({'success': False, 'message': '仅支持 zip 和 tar.gz 格式'})

    # 校验所有源路径
    resolved_paths = []
    for p in paths:
        resolved, allowed = resolve_allowed_path(p)
        if not allowed or resolved is None or not resolved.exists():
            return jsonify({'success': False, 'message': f'路径非法或不存在: {p}'})
        resolved_paths.append(resolved)

    # 压缩包保存到第一个源路径的父目录
    output_dir = resolved_paths[0].parent
    output_file = output_dir / name
    output_file_resolved, allowed = resolve_allowed_path(output_file)
    if not allowed or output_file_resolved is None:
        return jsonify({'success': False, 'message': '压缩包保存路径非法'})

    # 文件名安全处理
    safe_name = secure_filename(name)
    if not safe_name:
        return jsonify({'success': False, 'message': '压缩文件名不合法'})
    output_file = output_dir / safe_name

    try:
        if fmt == 'zip':
            if not name.lower().endswith('.zip'):
                output_file = output_dir / (safe_name + '.zip')
            cmd = ['zip', '-r', str(output_file)] + [str(p) for p in resolved_paths]
            success, stdout, stderr = run_command(cmd, timeout=300)
        else:
            if not name.lower().endswith('.tar.gz'):
                output_file = output_dir / (safe_name + '.tar.gz')
            cmd = ['tar', '-czf', str(output_file), '-C', str(output_dir)]
            relative_paths = [str(p.relative_to(output_dir)) for p in resolved_paths]
            cmd.extend(relative_paths)
            success, stdout, stderr = run_command(cmd, timeout=300)
    except Exception as e:
        return jsonify({'success': False, 'message': f'压缩失败: {str(e)}'})

    if not success:
        return jsonify({'success': False, 'message': f'压缩失败: {stderr or stdout}'})

    return jsonify({'success': True, 'message': '压缩成功', 'file': str(output_file)})


# ==================== API：定时任务 ====================

def _cron_id(name, schedule, command):
    """根据任务内容生成稳定 ID"""
    return hashlib.md5(f'{name}|{schedule}|{command}'.encode()).hexdigest()[:12]


def _parse_crontab():
    """解析当前用户的 crontab，返回任务列表"""
    tasks = []
    success, stdout, _ = run_command(['crontab', '-l'])
    if not success:
        return tasks

    lines = stdout.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        marker = '# ZeroPanel:'
        if line.startswith(marker):
            name = line[len(marker):].strip()
            i += 1
            if i >= len(lines):
                break
            task_line = lines[i]
            enabled = not task_line.strip().startswith('#')
            # 去除可能的前导注释
            clean_line = task_line.strip()
            if clean_line.startswith('#'):
                clean_line = clean_line[1:].strip()
            parts = clean_line.split(None, 5)
            if len(parts) >= 6:
                schedule = ' '.join(parts[:5])
                command = parts[5]
                task_id = _cron_id(name, schedule, command)
                tasks.append({
                    'id': task_id,
                    'name': name,
                    'schedule': schedule,
                    'command': command,
                    'enabled': enabled
                })
        i += 1
    return tasks


def _write_crontab(tasks):
    """将任务列表写回 crontab"""
    lines = []
    for task in tasks:
        lines.append(f'# ZeroPanel: {task["name"]}')
        if task.get('enabled', True):
            lines.append(f'{task["schedule"]} {task["command"]}')
        else:
            lines.append(f'# {task["schedule"]} {task["command"]}')
    content = '\n'.join(lines) + '\n'

    try:
        result = subprocess.run(
            ['crontab', '-'],
            input=content,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stderr.strip()
    except Exception as e:
        return False, str(e)


@app.route('/api/cron')
@login_required
def api_list_cron():
    """列出当前用户的 crontab 任务"""
    tasks = _parse_crontab()
    return jsonify({'success': True, 'tasks': tasks})


@app.route('/api/cron', methods=['POST'])
@login_required
def api_create_or_update_cron():
    """创建或更新定时任务"""
    data = request.get_json()
    name = data.get('name', '').strip()
    schedule = data.get('schedule', '').strip()
    command = data.get('command', '').strip()
    enabled = data.get('enabled', True)

    if not name or not schedule or not command:
        return jsonify({'success': False, 'message': '名称、调度表达式和命令不能为空'})

    # 简单校验 schedule 格式：5 个字段
    if len(schedule.split()) != 5:
        return jsonify({'success': False, 'message': '调度表达式格式错误，应为 5 个字段'})

    tasks = _parse_crontab()
    new_task = {
        'id': _cron_id(name, schedule, command),
        'name': name,
        'schedule': schedule,
        'command': command,
        'enabled': bool(enabled)
    }

    # 如果存在同名任务则更新
    updated = False
    for i, task in enumerate(tasks):
        if task['name'] == name:
            tasks[i] = new_task
            updated = True
            break
    if not updated:
        tasks.append(new_task)

    success, stderr = _write_crontab(tasks)
    if not success:
        return jsonify({'success': False, 'message': '保存任务失败: ' + stderr})

    return jsonify({'success': True, 'message': '任务已保存', 'task': new_task})


@app.route('/api/cron/<task_id>', methods=['DELETE'])
@login_required
def api_delete_cron(task_id):
    """删除定时任务"""
    tasks = _parse_crontab()
    new_tasks = [t for t in tasks if t['id'] != task_id]
    if len(new_tasks) == len(tasks):
        return jsonify({'success': False, 'message': '任务不存在'})

    success, stderr = _write_crontab(new_tasks)
    if not success:
        return jsonify({'success': False, 'message': '删除任务失败: ' + stderr})

    return jsonify({'success': True, 'message': '任务已删除'})


@app.route('/api/cron/<task_id>/toggle', methods=['POST'])
@login_required
def api_toggle_cron(task_id):
    """启用/禁用定时任务"""
    tasks = _parse_crontab()
    found = False
    for task in tasks:
        if task['id'] == task_id:
            task['enabled'] = not task['enabled']
            found = True
            break

    if not found:
        return jsonify({'success': False, 'message': '任务不存在'})

    success, stderr = _write_crontab(tasks)
    if not success:
        return jsonify({'success': False, 'message': '切换任务状态失败: ' + stderr})

    return jsonify({'success': True, 'message': '任务状态已切换'})


# ==================== API：系统监控 ====================

@app.route('/api/system/info')
@login_required
def api_system_info():
    """获取系统信息"""
    return jsonify(get_system_info())

@app.route('/api/system/stats')
@login_required
def api_system_stats():
    """获取系统实时状态"""
    return jsonify(get_system_stats())

@app.route('/api/system/services')
@login_required
def api_system_services():
    """获取服务状态"""
    return jsonify(get_service_status())

@app.route('/api/system/start-services', methods=['POST'])
@login_required
def api_start_services():
    """启动所有服务"""
    results = {}

    # 检查当前状态
    current_status = get_service_status()

    # 启动 MariaDB/MySQL
    if not current_status.get('mysql', False):
        try:
            subprocess.Popen(['mysqld_safe'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            results['mysql'] = {'success': True, 'message': 'MariaDB 启动中...'}
        except Exception as e:
            results['mysql'] = {'success': False, 'message': str(e)}
    else:
        results['mysql'] = {'success': True, 'message': 'MariaDB 已在运行'}

    # 启动 PHP-FPM
    if not current_status.get('php-fpm', False):
        success, _, stderr = run_command(['php-fpm'])
        results['php-fpm'] = {'success': success, 'message': 'PHP-FPM 已启动' if success else stderr}
    else:
        results['php-fpm'] = {'success': True, 'message': 'PHP-FPM 已在运行'}

    # 启动 Nginx
    if not current_status.get('nginx', False):
        success, _, stderr = run_command(['nginx'])
        results['nginx'] = {'success': success, 'message': 'Nginx 已启动' if success else stderr}
    else:
        results['nginx'] = {'success': True, 'message': 'Nginx 已在运行'}

    return jsonify({'success': True, 'results': results})

# ==================== 云更新功能 ====================

@app.route('/api/system/version')
def api_get_version():
    """获取当前面板版本"""
    return jsonify({
        'version': PANEL_VERSION,
        'name': 'ZeroPanel v' + PANEL_VERSION
    })


@app.route('/api/system/check-update')
def api_check_update():
    """检查更新 - 从VERSION文件读取版本号"""
    try:
        # 1. 获取远程版本号
        headers = {
            'User-Agent': 'ZeroPanel/' + PANEL_VERSION,
            'Accept': 'text/plain'
        }
        req = Request(UPDATE_CONFIG['version_url'], headers=headers)
        with urlopen(req, timeout=10) as response:
            latest_version = response.read().decode('utf-8').strip()

        if not latest_version:
            return jsonify({
                'success': False,
                'error': '无法获取版本信息'
            })

        # 2. 获取更新日志
        release_notes = ''
        try:
            req_notes = Request(UPDATE_CONFIG['release_notes_url'], headers=headers)
            with urlopen(req_notes, timeout=10) as response:
                release_notes = response.read().decode('utf-8').strip()
        except Exception:
            pass

        # 3. 比较版本号
        def parse_version(v):
            """解析版本号为整数列表"""
            parts = []
            for part in v.split('.'):
                try:
                    parts.append(int(''.join(filter(str.isdigit, part))))
                except:
                    parts.append(0)
            return parts

        current = parse_version(PANEL_VERSION)
        latest = parse_version(latest_version)

        is_update_available = latest > current

        return jsonify({
            'success': True,
            'current_version': PANEL_VERSION,
            'latest_version': latest_version,
            'is_update_available': is_update_available,
            'download_url': UPDATE_CONFIG['download_url'],
            'release_notes': release_notes,
            'version_url': UPDATE_CONFIG['version_url']
        })
    except HTTPError as e:
        return jsonify({
            'success': False,
            'error': '网络请求失败: HTTP ' + str(e.code)
        })
    except URLError as e:
        return jsonify({
            'success': False,
            'error': '网络连接失败，请检查网络'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': '检查更新失败: ' + str(e)
        })


def _backup_current_version(backup_file):
    """备份当前面板代码文件到 ZIP"""
    exclude_names = {'data', '__pycache__', '.git', '.venv', 'venv'}
    with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in BASE_DIR.rglob('*'):
            if not file_path.is_file():
                continue
            # 跳过数据目录、缓存、虚拟环境等
            if any(part in exclude_names for part in file_path.parts):
                continue
            arcname = file_path.relative_to(BASE_DIR)
            zf.write(file_path, arcname)


def _safe_extract_update(zip_path, target_dir):
    """安全解压更新包，支持根目录布局或 zeropanel/ 子目录布局"""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        members = zf.namelist()
        has_root_prefix = any(m.startswith('zeropanel/') for m in members)
        prefix = 'zeropanel/' if has_root_prefix else ''
        prefix_len = len(prefix)

        for member in members:
            if not member.startswith(prefix):
                continue
            target_name = member[prefix_len:]
            if not target_name or target_name.endswith('/'):
                continue
            # 防止 zip slip
            extracted_path = target_dir / target_name
            try:
                extracted_path.resolve().relative_to(target_dir.resolve())
            except ValueError:
                continue
            extracted_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(extracted_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)


@app.route('/api/system/do-update', methods=['POST'])
@login_required
def api_do_update():
    """执行云更新"""
    try:
        data = request.get_json() or {}
        download_url = data.get('download_url')

        if not download_url:
            return jsonify({'success': False, 'message': '缺少下载链接'})

        # 1. 创建备份
        backup_dir = DATA_DIR / 'update_backup'
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir / ('backup_' + timestamp + '.zip')
        _backup_current_version(backup_file)

        # 2. 下载新版本
        update_dir = DATA_DIR / 'update_temp'
        if update_dir.exists():
            shutil.rmtree(update_dir)
        update_dir.mkdir(parents=True, exist_ok=True)

        headers = {
            'User-Agent': 'ZeroPanel/' + PANEL_VERSION
        }
        req = Request(download_url, headers=headers)

        zip_path = update_dir / 'update.zip'
        with urlopen(req, timeout=120) as response:
            with open(zip_path, 'wb') as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)

        # 3. 校验下载文件
        if not zip_path.exists() or zip_path.stat().st_size == 0:
            raise zipfile.BadZipFile('下载文件为空')

        # 4. 解压到临时目录
        extract_dir = update_dir / 'extracted'
        extract_dir.mkdir(parents=True, exist_ok=True)
        _safe_extract_update(zip_path, extract_dir)

        # 5. 覆盖到 BASE_DIR
        for file_path in extract_dir.rglob('*'):
            if not file_path.is_file():
                continue
            target_path = BASE_DIR / file_path.relative_to(extract_dir)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, target_path)

        # 6. 清理临时文件
        shutil.rmtree(update_dir)

        return jsonify({
            'success': True,
            'message': '更新包下载完成，请重启面板使更新生效',
            'backup_file': str(backup_file)
        })

    except HTTPError as e:
        return jsonify({'success': False, 'message': '下载失败: HTTP ' + str(e.code)})
    except URLError as e:
        return jsonify({'success': False, 'message': '下载失败: ' + str(e.reason)})
    except zipfile.BadZipFile:
        return jsonify({'success': False, 'message': '下载的文件不是有效的 ZIP 压缩包'})
    except Exception as e:
        return jsonify({'success': False, 'message': '更新失败: ' + str(e)})


@app.route('/api/system/rollback', methods=['POST'])
@login_required
def api_rollback():
    """回滚更新"""
    try:
        data = request.get_json() or {}
        backup_file = data.get('backup_file')

        backup_path, allowed = resolve_allowed_path(backup_file)
        if not allowed or backup_path is None or not backup_path.exists():
            return jsonify({'success': False, 'message': '备份文件不存在或路径非法'})

        # 解压备份（防止 zip slip）
        with zipfile.ZipFile(backup_path, 'r') as zf:
            for member in zf.namelist():
                if member.endswith('/'):
                    continue
                target_path = BASE_DIR / member
                try:
                    target_path.resolve().relative_to(BASE_DIR.resolve())
                except ValueError:
                    continue
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)

        return jsonify({
            'success': True,
            'message': '回滚完成，请重启面板使回滚生效'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': '回滚失败: ' + str(e)})


@app.route('/api/system/restart', methods=['POST'])
@login_required
def api_restart_panel():
    """重启面板"""
    try:
        # 获取当前脚本路径
        script_path = str(BASE_DIR / 'app.py')
        log_file = str(DATA_DIR / 'panel.log')

        # 停止当前进程
        current_pid = os.getpid()

        # 启动新的进程
        subprocess.Popen(
            ['python3', script_path],
            cwd=str(BASE_DIR),
            stdout=open(log_file, 'a'),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )

        # 延迟终止当前进程，让新进程有时间启动并响应请求
        subprocess.Popen(['python3', '-c', f'import time, os; time.sleep(2); os.kill({current_pid}, 15)'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

        return jsonify({
            'success': True,
            'message': '面板正在重启...'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': '重启失败: ' + str(e)})


# ==================== 主程序 ====================

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
