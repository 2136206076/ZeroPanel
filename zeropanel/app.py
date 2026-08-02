#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZeroPanel v2.0 - 轻量级建站面板
专为 ZeroTermux 设计
"""

import os
import re
import json
import time
import uuid
import shutil
import hashlib
import secrets
import string
import subprocess
import sqlite3
import zipfile
import tempfile
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
PANEL_VERSION = '2.0.3'

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
NGINX_CONF_DIR = Path(os.environ.get('PREFIX', '/data/data/com.termux/files/usr')) / 'etc' / 'nginx' / 'conf.d'

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'tar', 'gz', 'sql', 'php', 'html', 'css', 'js', 'json', 'xml', 'md'}

# 允许文件操作的根目录
ALLOWED_ROOTS = [WWW_DIR, DATA_DIR]


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

def run_command(cmd, shell=False):
    """安全执行命令"""
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, '', '命令执行超时'
    except Exception as e:
        return False, '', str(e)

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


def generate_nginx_config(domain, root_path, php_version='8.0', port=8080):
    """生成 Nginx 配置"""
    # 使用统一的 PHP-FPM socket，由 install.sh 配置
    php_sock = '/data/data/com.termux/files/usr/var/run/php-fpm.sock'

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
        '    access_log /data/data/com.termux/files/usr/var/log/nginx/' + domain + '.access.log;',
        '    error_log /data/data/com.termux/files/usr/var/log/nginx/' + domain + '.error.log;',
        '}',
        ''
    ]

    return '\n'.join(config_lines)

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
        cursor.execute('SELECT id, domain, root_path, php_version, status, port, db_name, db_user, db_password, created_at FROM websites ORDER BY created_at DESC')
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
                'db_name': row[6],
                'db_user': row[7],
                'db_password': row[8],
                'created_at': row[9]
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
    create_db = data.get('create_database', False)
    db_password_input = data.get('db_password', '').strip()
    
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
    config_content = generate_nginx_config(domain, root, php_version, port)
    config_file = get_nginx_config_path(domain, port)

    try:
        NGINX_CONF_DIR.mkdir(parents=True, exist_ok=True)
        config_file.write_text(config_content)
    except Exception as e:
        return jsonify({'success': False, 'message': '创建配置失败: ' + str(e)})

    # 可选：创建网站独立数据库
    db_name = ''
    db_user = ''
    db_password = ''
    if create_db:
        safe_domain = re.sub(r'[^a-zA-Z0-9_]', '_', domain)[:32].strip('_')
        if not safe_domain:
            safe_domain = 'site_' + str(int(time.time()))
        db_name = safe_domain
        db_user = safe_domain
        db_password = db_password_input if db_password_input else _random_password()

        db_success, db_error = _create_website_database(db_name, db_user, db_password)
        if not db_success:
            return jsonify({'success': False, 'message': db_error})

    # 保存到数据库
    website_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO websites (id, domain, root_path, php_version, status, port, db_name, db_user, db_password) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (website_id, domain, root, php_version, 'running', port, db_name, db_user, db_password)
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

    return jsonify({'success': True, 'message': '网站创建成功', 'id': website_id})

@app.route('/api/websites/<website_id>', methods=['DELETE'])
@login_required
def api_delete_website(website_id):
    """删除网站"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT domain, root_path, port, db_name, db_user FROM websites WHERE id = ?', (website_id,))
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

    # 删除网站独立数据库
    if db_name:
        _delete_website_database(db_name, db_user)

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
    cursor.execute('SELECT domain, root_path, php_version, port FROM websites WHERE id = ?', (website_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'success': False, 'message': '网站不存在'})

    domain, root_path, php_version, port = row

    config_file = get_nginx_config_path(domain, port)
    disabled_file = get_nginx_disabled_path(domain, port)

    if not config_file.exists():
        # 如果有 .disabled 文件，重命名回来
        if disabled_file.exists():
            disabled_file.rename(config_file)
        else:
            # 配置文件不存在，重新生成
            config_content = generate_nginx_config(domain, root_path, php_version, port)
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


@app.route('/api/websites/<website_id>/db-reset', methods=['POST'])
@login_required
def api_reset_website_db_password(website_id):
    """重置网站数据库密码"""
    data = request.get_json(silent=True) or {}
    new_password = data.get('password', '').strip()
    if not new_password:
        new_password = _random_password()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT db_name, db_user FROM websites WHERE id = ?', (website_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        conn.close()
        return jsonify({'success': False, 'message': '该网站没有独立数据库'})

    db_name, db_user = row

    # 更新 MySQL 用户密码
    safe_user = quote_string(db_user)
    safe_pwd = quote_string(new_password)
    success, _, stderr = mariadb_query(f"ALTER USER {safe_user}@'localhost' IDENTIFIED BY {safe_pwd}")
    if not success:
        # 老版本 MariaDB 不支持 ALTER USER，尝试 SET PASSWORD
        success, _, stderr = mariadb_query(f"SET PASSWORD FOR {safe_user}@'localhost' = PASSWORD({safe_pwd})")
    mariadb_query('FLUSH PRIVILEGES')

    if not success:
        conn.close()
        return jsonify({'success': False, 'message': f'重置密码失败: {stderr}'})

    # 更新本地记录
    cursor.execute('UPDATE websites SET db_password = ? WHERE id = ?', (new_password, website_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': '数据库密码已重置', 'password': new_password})


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


def _random_password(length=16):
    """生成随机密码"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _create_website_database(db_name, db_user, db_password):
    """为网站创建数据库和用户，返回 (success, error)"""
    try:
        name_quoted = quote_identifier(db_name)
    except ValueError:
        return False, '数据库名包含非法字符'

    # 创建数据库
    success, _, stderr = mariadb_query(f'CREATE DATABASE IF NOT EXISTS {name_quoted} CHARACTER SET utf8mb4')
    if not success:
        return False, f'创建数据库失败: {stderr}'

    # 创建用户并授权
    if db_user and db_password:
        if not re.match(r'^[a-zA-Z0-9_]+$', db_user):
            return False, '数据库用户名只能包含字母、数字和下划线'
        safe_user = quote_string(db_user)
        safe_pwd = quote_string(db_password)
        mariadb_query(f"CREATE USER IF NOT EXISTS {safe_user}@'localhost' IDENTIFIED BY {safe_pwd}")
        mariadb_query(f"GRANT ALL PRIVILEGES ON {name_quoted}.* TO {safe_user}@'localhost'")
        mariadb_query('FLUSH PRIVILEGES')

    return True, ''


def _delete_website_database(db_name, db_user):
    """删除网站对应的数据库和用户"""
    if not db_name:
        return True, ''
    try:
        name_quoted = quote_identifier(db_name)
    except ValueError:
        return False, '数据库名包含非法字符'

    mariadb_query(f'DROP DATABASE IF EXISTS {name_quoted}')
    if db_user:
        safe_user = quote_string(db_user)
        mariadb_query(f"DROP USER IF EXISTS {safe_user}@'localhost'")
        mariadb_query('FLUSH PRIVILEGES')
    return True, ''


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
    """写入文件内容"""
    data = request.get_json()
    path = data.get('path', '')
    content = data.get('content', '')

    filepath, allowed = resolve_allowed_path(path)
    if not allowed or filepath is None:
        return jsonify({'success': False, 'message': '非法路径'})

    try:
        filepath.write_text(content, encoding='utf-8')
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'})

    return jsonify({'success': True, 'message': '保存成功'})


@app.route('/api/files/extract', methods=['POST'])
@login_required
def api_extract_file():
    """解压文件"""
    data = request.get_json()
    path = data.get('path', '')
    dest = data.get('dest', '')

    if not path:
        return jsonify({'success': False, 'message': '请选择要解压的文件'})

    safe_path, allowed = resolve_allowed_path(path)
    if not allowed or safe_path is None:
        return jsonify({'success': False, 'message': '文件路径非法'})

    if not safe_path.exists() or not safe_path.is_file():
        return jsonify({'success': False, 'message': '文件不存在'})

    if dest:
        safe_dest, allowed_dest = resolve_allowed_path(dest)
    else:
        safe_dest, allowed_dest = resolve_allowed_path(str(safe_path.parent))

    if not allowed_dest or safe_dest is None:
        return jsonify({'success': False, 'message': '目标路径非法'})

    filename = safe_path.name.lower()
    commands = {
        '.zip': ['unzip', '-q', str(safe_path), '-d', str(safe_dest)],
        '.tar.gz': ['tar', 'zxf', str(safe_path), '-C', str(safe_dest)],
        '.tgz': ['tar', 'zxf', str(safe_path), '-C', str(safe_dest)],
        '.tar.bz2': ['tar', 'jxf', str(safe_path), '-C', str(safe_dest)],
        '.tbz2': ['tar', 'jxf', str(safe_path), '-C', str(safe_dest)],
        '.tar.xz': ['tar', 'Jxf', str(safe_path), '-C', str(safe_dest)],
        '.txz': ['tar', 'Jxf', str(safe_path), '-C', str(safe_dest)],
        '.tar': ['tar', 'xf', str(safe_path), '-C', str(safe_dest)]
    }

    matched_cmd = None
    for ext, cmd in commands.items():
        if filename.endswith(ext):
            matched_cmd = cmd
            break

    if matched_cmd is None:
        return jsonify({'success': False, 'message': '不支持的压缩格式'})

    success, stdout, stderr = run_command(matched_cmd, timeout=120)
    if success:
        return jsonify({'success': True, 'message': '解压成功'})
    return jsonify({'success': False, 'message': f'解压失败: {stderr}'})


@app.route('/api/files/compress', methods=['POST'])
@login_required
def api_compress_file():
    """压缩文件/目录"""
    data = request.get_json()
    paths = data.get('paths', [])
    dest = data.get('dest', '')
    archive_format = data.get('format', 'zip')

    if not paths:
        return jsonify({'success': False, 'message': '请选择要压缩的文件'})

    allowed_paths = []
    for p in paths:
        safe_p, allowed = resolve_allowed_path(p)
        if not allowed or safe_p is None or not safe_p.exists():
            return jsonify({'success': False, 'message': f'路径非法或不存在: {p}'})
        allowed_paths.append(safe_p)

    if not dest:
        return jsonify({'success': False, 'message': '请指定压缩文件名'})

    safe_dest, allowed = resolve_allowed_path(dest)
    if not allowed or safe_dest is None:
        return jsonify({'success': False, 'message': '压缩文件路径非法'})

    base_dir = allowed_paths[0].parent
    names = [p.name for p in allowed_paths]

    try:
        if archive_format == 'zip':
            if not str(safe_dest).lower().endswith('.zip'):
                safe_dest = safe_dest.with_name(safe_dest.name + '.zip')
            cmd = ['zip', '-r', str(safe_dest)] + names
            success, stdout, stderr = run_command(cmd, timeout=120)
        elif archive_format in ('tar.gz', 'tgz'):
            if not str(safe_dest).lower().endswith('.tar.gz'):
                safe_dest = safe_dest.with_name(safe_dest.name + '.tar.gz')
            cmd = ['tar', 'zcf', str(safe_dest)] + names
            success, stdout, stderr = run_command(cmd, timeout=120)
        else:
            return jsonify({'success': False, 'message': '不支持的压缩格式'})

        if success:
            return jsonify({'success': True, 'message': '压缩成功'})
        return jsonify({'success': False, 'message': f'压缩失败: {stderr}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'})


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
    exclude_names = {'data', '__pycache__', '.git', '.venv', 'venv', 'update_backup', 'update_temp'}
    base_resolved = BASE_DIR.resolve()
    backed_count = 0
    errors = []

    with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base_resolved, followlinks=False):
            # 跳过排除目录，避免进入
            dirs[:] = [d for d in dirs if d not in exclude_names and not d.startswith('.')]

            for filename in files:
                file_path = Path(root) / filename
                # 跳过隐藏文件、备份文件和符号链接
                if filename.startswith('.') or file_path.is_symlink():
                    continue

                # 安全校验：确保文件在 BASE_DIR 内
                try:
                    file_path.resolve().relative_to(base_resolved)
                except ValueError:
                    continue

                arcname = file_path.relative_to(base_resolved)
                try:
                    zf.write(file_path, arcname)
                    backed_count += 1
                except Exception as e:
                    errors.append(f'{arcname}: {e}')

    if backed_count == 0:
        raise RuntimeError('备份文件为空，可能面板目录没有可读文件' + ('; ' + '; '.join(errors[:3]) if errors else ''))

    return backed_count


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
        backed_count = _backup_current_version(backup_file)

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
            'message': f'更新完成，已备份 {backed_count} 个文件，请重启面板使更新生效',
            'backup_file': str(backup_file),
            'backed_count': backed_count
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
        script_path = str((BASE_DIR / 'app.py').resolve())
        log_file = str(DATA_DIR / 'panel.log')
        current_pid = os.getpid()
        panel_dir = str(BASE_DIR.resolve())

        # 使用独立子进程执行重启：先停止旧进程，释放端口，再启动新进程
        restart_script = f'''
import os, time, subprocess, signal
pid = {current_pid}
script = {repr(script_path)}
workdir = {repr(panel_dir)}
log = {repr(log_file)}

time.sleep(2)
try:
    os.kill(pid, signal.SIGTERM)
except ProcessLookupError:
    pass

# 等待端口释放
time.sleep(2)

# 启动新进程
with open(log, 'a') as out, open(os.devnull, 'r') as stdin:
    subprocess.Popen(
        ['python3', script],
        cwd=workdir,
        stdin=stdin,
        stdout=out,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
'''
        subprocess.Popen(
            ['python3', '-c', restart_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )

        return jsonify({
            'success': True,
            'message': '面板正在重启，请等待 5-10 秒后刷新页面'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': '重启失败: ' + str(e)})


# ==================== 主程序 ====================

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)