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
PANEL_VERSION = '2.0.0'

# 云更新配置
UPDATE_CONFIG = {
    'version_url': 'https://raw.githubusercontent.com/zerotermux/zeropanel/main/VERSION',
    'download_url': 'https://github.com/zerotermux/zeropanel/releases/latest/download/zeropanel_v2.zip',
    'release_notes_url': 'https://raw.githubusercontent.com/zerotermux/zeropanel/main/CHANGELOG.md'
}

app = Flask(__name__)
app.secret_key = os.urandom(24)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 迁移：确保 websites 表存在 port 列（兼容旧数据库）
    try:
        cursor.execute('PRAGMA table_info(websites)')
        columns = [row[1] for row in cursor.fetchall()]
        if 'port' not in columns:
            cursor.execute('ALTER TABLE websites ADD COLUMN port INTEGER DEFAULT 8080')
        if 'php_version' not in columns:
            cursor.execute("ALTER TABLE websites ADD COLUMN php_version TEXT DEFAULT '8.0'")
        if 'status' not in columns:
            cursor.execute("ALTER TABLE websites ADD COLUMN status TEXT DEFAULT 'stopped'")
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
        # CPU 使用率
        stat_file = Path('/proc/stat')
        if stat_file.exists():
            with open(stat_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('cpu ') or line.startswith('cpu\t'):
                        parts = line.split()
                        if len(parts) >= 8:
                            try:
                                user = int(parts[1])
                                nice = int(parts[2])
                                system = int(parts[3])
                                idle = int(parts[4])
                                iowait = int(parts[5])
                                irq = int(parts[6])
                                softirq = int(parts[7])
                                total = user + nice + system + idle + iowait + irq + softirq
                                if total > 0:
                                    stats['cpu_usage'] = round((1 - idle / total) * 100, 1)
                            except:
                                pass
                        break
        
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

def generate_nginx_config(domain, root_path, php_version='8.0', port=8080):
    """生成 Nginx 配置"""
    php_sock = '/data/data/com.termux/files/usr/var/run/php-fpm-' + php_version + '.sock'

    config_lines = [
        'server {',
        '    listen ' + str(port) + ';',
        '    server_name ' + domain + ';',
        '    root ' + root_path + ';',
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
        cursor.execute('SELECT id, domain, root_path, php_version, status, port, created_at FROM websites ORDER BY created_at DESC')
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
                'created_at': row[6]
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
    config_file = NGINX_CONF_DIR / (safe_domain + '_' + str(port) + '.conf')

    try:
        NGINX_CONF_DIR.mkdir(parents=True, exist_ok=True)
        config_file.write_text(config_content)
    except Exception as e:
        return jsonify({'success': False, 'message': '创建配置失败: ' + str(e)})

    # 保存到数据库
    website_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO websites (id, domain, root_path, php_version, status, port) VALUES (?, ?, ?, ?, ?, ?)',
            (website_id, domain, root, php_version, 'running', port)
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
    cursor.execute('SELECT domain, root_path, port FROM websites WHERE id = ?', (website_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'success': False, 'message': '网站不存在'})

    domain, root_path, port = row

    # 删除 Nginx 配置
    safe_domain = domain.replace(':', '_').replace('/', '_')
    config_file = NGINX_CONF_DIR / (safe_domain + '_' + str(port) + '.conf')
    if config_file.exists():
        config_file.unlink()

    # 兼容旧配置文件命名
    old_config_file = NGINX_CONF_DIR / (domain + '.conf')
    if old_config_file.exists():
        old_config_file.unlink()

    # 还可能存在 .conf.disabled 文件
    disabled_file = NGINX_CONF_DIR / (safe_domain + '_' + str(port) + '.conf.disabled')
    if disabled_file.exists():
        disabled_file.unlink()

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
    safe_domain = domain.replace(':', '_').replace('/', '_')

    # 检查配置文件（支持新格式 safe_domain_port.conf）
    config_file = NGINX_CONF_DIR / (safe_domain + '_' + str(port) + '.conf')
    disabled_file = NGINX_CONF_DIR / (safe_domain + '_' + str(port) + '.conf.disabled')

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
    safe_domain = domain.replace(':', '_').replace('/', '_')
    config_file = NGINX_CONF_DIR / (safe_domain + '_' + str(port) + '.conf')

    # 重命名配置文件以停止网站
    if config_file.exists():
        config_file.rename(NGINX_CONF_DIR / (safe_domain + '_' + str(port) + '.conf.disabled'))

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
    # 先停止再启动
    api_stop_website(website_id)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT domain FROM websites WHERE id = ?', (website_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        domain = row[0]
        config_file = NGINX_CONF_DIR / f'{domain}.conf.disabled'
        if config_file.exists():
            config_file.rename(config_file.with_suffix(''))
    
    return api_start_website(website_id)

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
    for cmd in dump_candidates:
        try:
            with open(output_file, 'w') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=120)
            if result.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
                return True, ''
        except FileNotFoundError:
            continue
        except Exception as e:
            last_error = str(e)
            continue
    return False, '备份失败：未找到可用的 mysqldump/mariadb-dump 命令'


def mariadb_restore(db_name, input_file):
    """从文件恢复数据库"""
    restore_candidates = [
        ['mariadb', '-u', 'root', db_name],
        ['mysql', '-u', 'root', db_name],
        ['mariadb', db_name],
        ['mysql', db_name],
    ]
    for cmd in restore_candidates:
        try:
            with open(input_file, 'r') as f:
                result = subprocess.run(cmd, stdin=f, capture_output=True, timeout=120)
            if result.returncode == 0:
                return True, ''
        except FileNotFoundError:
            continue
        except Exception as e:
            last_error = str(e)
            continue
    return False, '恢复失败：未找到可用的 mariadb/mysql 命令'


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
                # 获取数据库大小
                size_success, size_stdout, _ = mariadb_query(
                    "SELECT SUM(data_length + index_length) FROM information_schema.tables WHERE table_schema = '" + db + "'"
                )
                size = 0
                if size_success and size_stdout:
                    try:
                        lines = size_stdout.strip().split('\n')
                        if len(lines) >= 2 and lines[1]:
                            size = int(float(lines[1]))
                    except:
                        pass

                # 获取表数量
                tables_success, tables_stdout, _ = mariadb_query(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '" + db + "'"
                )
                tables = 0
                if tables_success and tables_stdout:
                    try:
                        lines = tables_stdout.strip().split('\n')
                        if len(lines) >= 2 and lines[1]:
                            tables = int(lines[1])
                    except:
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

    # 创建数据库
    success, _, stderr = mariadb_query('CREATE DATABASE `' + name + '` CHARACTER SET ' + charset)
    if not success:
        return jsonify({'success': False, 'message': '创建数据库失败: ' + stderr})

    # 创建用户并授权（可选）
    if user and password:
        # 清理用户名密码中的引号
        safe_user = user.replace("'", "").replace('"', '')
        safe_pwd = password.replace("'", "\\'")
        mariadb_query("CREATE USER IF NOT EXISTS '" + safe_user + "'@'localhost' IDENTIFIED BY '" + safe_pwd + "'")
        mariadb_query("GRANT ALL PRIVILEGES ON `" + name + "`.* TO '" + safe_user + "'@'localhost'")
        mariadb_query('FLUSH PRIVILEGES')

    return jsonify({'success': True, 'message': '数据库创建成功'})


@app.route('/api/databases/<name>', methods=['DELETE'])
@login_required
def api_delete_database(name):
    """删除数据库"""
    success, _, stderr = mariadb_query('DROP DATABASE IF EXISTS `' + name + '`')
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

    backup_path = Path(backup_file)
    if not backup_path.exists():
        return jsonify({'success': False, 'message': '备份文件不存在'})

    # 先确保数据库存在
    mariadb_query('CREATE DATABASE IF NOT EXISTS `' + name + '`')

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
    # 支持两种方式：上传文件 或 指定已存在的文件路径
    db_name = request.form.get('name') or (request.json.get('name') if request.is_json else '')
    if not db_name:
        return jsonify({'success': False, 'message': '请提供目标数据库名'})

    tmp_path = None
    if 'file' in request.files:
        f = request.files['file']
        if not f.filename:
            return jsonify({'success': False, 'message': '未选择文件'})
        if not f.filename.lower().endswith('.sql'):
            return jsonify({'success': False, 'message': '只支持 .sql 文件'})
        # 保存到临时目录
        tmp_dir = DATA_DIR / 'tmp'
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / ('import_' + str(int(time.time())) + '_' + f.filename)
        f.save(str(tmp_path))
    else:
        # JSON 方式：指定文件路径
        data = request.get_json(silent=True) or {}
        sql_path = data.get('path', '')
        if not sql_path:
            return jsonify({'success': False, 'message': '请提供 SQL 文件'})
        tmp_path = Path(sql_path)
        if not tmp_path.exists():
            return jsonify({'success': False, 'message': 'SQL 文件不存在'})

    # 确保数据库存在
    mariadb_query('CREATE DATABASE IF NOT EXISTS `' + db_name + '`')

    success, error = mariadb_restore(db_name, tmp_path)
    # 清理临时文件（仅限上传产生的临时文件）
    try:
        if 'file' in request.files and tmp_path and tmp_path.exists():
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
    
    # 安全检查：防止路径遍历
    try:
        path = str(Path(path).resolve())
        if not path.startswith(str(WWW_DIR)) and not path.startswith(str(DATA_DIR)):
            path = str(WWW_DIR)
    except:
        path = str(WWW_DIR)
    
    path_obj = Path(path)
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
    
    return jsonify({
        'path': path,
        'parent': str(path_obj.parent) if path_obj != WWW_DIR else None,
        'files': files
    })

@app.route('/api/files/upload', methods=['POST'])
@login_required
def api_upload_file():
    """上传文件"""
    path = request.form.get('path', str(WWW_DIR))
    
    # 安全检查
    try:
        path = str(Path(path).resolve())
        if not path.startswith(str(WWW_DIR)) and not path.startswith(str(DATA_DIR)):
            return jsonify({'success': False, 'message': '非法路径'})
    except:
        return jsonify({'success': False, 'message': '非法路径'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有选择文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'})
    
    filename = secure_filename(file.filename)
    filepath = Path(path) / filename
    
    try:
        file.save(filepath)
    except Exception as e:
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'})
    
    return jsonify({'success': True, 'message': '上传成功'})

@app.route('/api/files/download')
@login_required
def api_download_file():
    """下载文件"""
    path = request.args.get('path', '')
    
    # 安全检查
    try:
        path = str(Path(path).resolve())
        if not path.startswith(str(WWW_DIR)) and not path.startswith(str(DATA_DIR)):
            return jsonify({'success': False, 'message': '非法路径'})
    except:
        return jsonify({'success': False, 'message': '非法路径'})
    
    filepath = Path(path)
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
    
    # 安全检查
    try:
        path = str(Path(path).resolve())
        if not path.startswith(str(WWW_DIR)) and not path.startswith(str(DATA_DIR)):
            return jsonify({'success': False, 'message': '非法路径'})
    except:
        return jsonify({'success': False, 'message': '非法路径'})
    
    new_dir = Path(path) / name
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
    
    # 安全检查
    try:
        old_path = str(Path(old_path).resolve())
        if not old_path.startswith(str(WWW_DIR)) and not old_path.startswith(str(DATA_DIR)):
            return jsonify({'success': False, 'message': '非法路径'})
    except:
        return jsonify({'success': False, 'message': '非法路径'})
    
    old_file = Path(old_path)
    new_file = old_file.parent / new_name
    
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
    
    # 安全检查
    try:
        path = str(Path(path).resolve())
        if not path.startswith(str(WWW_DIR)) and not path.startswith(str(DATA_DIR)):
            return jsonify({'success': False, 'message': '非法路径'})
    except:
        return jsonify({'success': False, 'message': '非法路径'})
    
    filepath = Path(path)
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
    
    # 安全检查
    try:
        path = str(Path(path).resolve())
        if not path.startswith(str(WWW_DIR)) and not path.startswith(str(DATA_DIR)):
            return jsonify({'success': False, 'message': '非法路径'})
    except:
        return jsonify({'success': False, 'message': '非法路径'})
    
    filepath = Path(path)
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
    
    # 安全检查
    try:
        path = str(Path(path).resolve())
        if not path.startswith(str(WWW_DIR)) and not path.startswith(str(DATA_DIR)):
            return jsonify({'success': False, 'message': '非法路径'})
    except:
        return jsonify({'success': False, 'message': '非法路径'})
    
    filepath = Path(path)
    try:
        filepath.write_text(content, encoding='utf-8')
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'})
    
    return jsonify({'success': True, 'message': '保存成功'})

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

        # 备份当前文件
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in BASE_DIR.iterdir():
                if file_path.is_file() and file_path.suffix in ('.py', '.sh', '.txt'):
                    if file_path.name not in ('panel.db',):
                        zf.write(file_path, file_path.name)

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
        with urlopen(req, timeout=60) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 8192
            with open(zip_path, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

        # 3. 解压并更新文件
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                # 安全检查：只解压 zeropanel 目录下的文件
                if member.startswith('zeropanel/'):
                    target_name = member[10:]  # 去掉 zeropanel/ 前缀
                    if target_name:
                        target_path = BASE_DIR / target_name
                        # 确保目标目录存在
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            zf.extract(member, update_dir)
                            # 移动到目标位置
                            extracted = update_dir / member
                            if extracted.is_file():
                                shutil.copy2(extracted, target_path)
                        except Exception:
                            pass

        # 4. 清理临时文件
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

        if not backup_file or not Path(backup_file).exists():
            return jsonify({'success': False, 'message': '备份文件不存在'})

        backup_path = Path(backup_file)

        # 解压备份
        with zipfile.ZipFile(backup_path, 'r') as zf:
            for member in zf.namelist():
                target_path = BASE_DIR / member
                try:
                    zf.extract(member, BASE_DIR)
                    if (BASE_DIR / member).is_file():
                        shutil.copy2(BASE_DIR / member, target_path)
                except Exception:
                    pass

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
            ['python', script_path],
            cwd=str(BASE_DIR),
            stdout=open(log_file, 'a'),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )

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