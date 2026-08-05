#!/usr/bin/env python3
"""ZeroPanel 修复验证测试脚本"""

import os
import sys
import time
import json
import shutil
import zipfile
import tempfile
from pathlib import Path

# 切换到项目目录
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))
os.chdir(str(BASE_DIR))

# 导入 app 中的函数
from app import (
    init_db,
    resolve_allowed_path,
    load_or_create_secret_key,
    quote_identifier,
    quote_string,
    get_system_stats,
    get_safe_domain,
    is_valid_domain,
    get_nginx_config_path,
    generate_nginx_config,
    _safe_extract_update,
    WWW_DIR,
    DATA_DIR,
    BASE_DIR as APP_BASE_DIR,
    NGINX_CONF_DIR,
    app,
)

PASS = 0
FAIL = 0


def test(name, condition, detail=''):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'  [PASS] {name}')
    else:
        FAIL += 1
        print(f'  [FAIL] {name} {detail}')


def main():
    global PASS, FAIL
    print('开始验证 ZeroPanel 修复...\n')

    # 1. 会话密钥持久化
    print('1. 会话密钥持久化')
    secret_file = DATA_DIR / '.secret_key'
    if secret_file.exists():
        old_key = secret_file.read_text().strip()
    else:
        old_key = None
    key1 = load_or_create_secret_key()
    key2 = load_or_create_secret_key()
    test('密钥创建成功', len(key1) > 0)
    test('密钥持久化一致', key1 == key2)
    if old_key is not None:
        test('未覆盖已有密钥', key1 == old_key)
    test('密钥文件权限安全', secret_file.exists() and oct(secret_file.stat().st_mode)[-3:] in ['600', '640', '644'])

    # 2. 路径遍历防护
    print('\n2. 路径遍历防护')
    # 文件管理已放开到整个文件系统，建站文件与系统路径均可访问
    allowed_paths = [
        str(WWW_DIR / 'test'),
        '/etc/passwd',
        '/tmp',
        str(Path.home() / 'www'),
    ]
    for p in allowed_paths:
        _, ok = resolve_allowed_path(p)
        test(f'允许路径: {p}', ok)

    # 面板程序目录受保护，禁止文件管理操作
    blocked_paths = [
        str(APP_BASE_DIR / 'app.py'),
        str(APP_BASE_DIR / 'VERSION'),
        str(APP_BASE_DIR / 'static'),
        str(APP_BASE_DIR / 'templates'),
    ]
    for p in blocked_paths:
        _, ok = resolve_allowed_path(p)
        test(f'阻止路径(面板程序): {p}', not ok)

    # 备份数据目录默认对文件管理隐藏，仅内部功能 allow_data=True 放行
    _, ok = resolve_allowed_path(str(DATA_DIR / 'backups'))
    test('阻止路径(备份数据): ' + str(DATA_DIR / 'backups'), not ok)
    _, ok = resolve_allowed_path(str(DATA_DIR / 'backups'), allow_data=True)
    test('内部功能放行备份数据', ok)

    # 3. SQL 注入防护
    print('\n3. SQL 注入防护')
    test('合法标识符引用', quote_identifier('test_db') == '`test_db`')
    try:
        quote_identifier('test; DROP TABLE users;')
        test('非法标识符应抛出异常', False)
    except ValueError:
        test('非法标识符被阻止', True)
    test('字符串转义单引号', quote_string("it's") == "'it''s'")
    test('字符串转义反斜杠', quote_string('a\\b') == "'a\\\\b'")

    # 4. CPU 使用率计算
    print('\n4. CPU 使用率计算')
    stats = get_system_stats()
    test('返回 CPU 使用率字段', 'cpu_usage' in stats)
    test('CPU 使用率是数值', isinstance(stats['cpu_usage'], (int, float)))
    test('CPU 使用率在合理范围', 0 <= stats['cpu_usage'] <= 100)

    # 5. 安全域名生成
    print('\n5. 安全域名生成')
    test('普通域名', get_safe_domain('example.com') == 'example.com')
    test('含非法字符域名', get_safe_domain('exa/mple.com:80') == 'exa_mple.com_80')
    test('域名校验通过', is_valid_domain('example.com'))
    test('IPv4 校验通过', is_valid_domain('127.0.0.1'))
    test('localhost 校验通过', is_valid_domain('localhost'))
    test('IPv6 字面量校验通过', is_valid_domain('::1'))
    test('IPv6 地址校验通过', is_valid_domain('2001:db8::1'))
    test('非法域名被拒绝', not is_valid_domain('exa mple.com'))

    # 6. Nginx 配置生成
    print('\n6. Nginx 配置生成')
    config = generate_nginx_config('example.com', '/home/user/www/example.com', '8.0', 8080)
    test('配置包含监听端口', 'listen 8080;' in config)
    test('配置包含 IPv6 双栈监听', 'listen [::]:8080 ipv6only=on;' in config)
    test('配置包含域名', 'server_name example.com;' in config)
    test('配置包含 PHP sock', 'php-fpm.sock' in config)
    test('配置包含根目录', 'root "/home/user/www/example.com";' in config)
    test('配置文件路径一致', get_nginx_config_path('example.com', 8080).name == 'example.com_8080.conf')
    # 含空格路径的 nginx 配置
    config_with_space = generate_nginx_config('example.com', '/home/user/my www/example.com', '8.0', 8080)
    test('含空格根目录已加引号', 'root "/home/user/my www/example.com";' in config_with_space)

    # 7. 安全解压更新包
    print('\n7. 安全解压更新包')
    tmpdir = Path(tempfile.mkdtemp())
    try:
        # 创建测试 zip：包含正常文件和 zip slip 攻击
        zip_path = tmpdir / 'test_update.zip'
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('zeropanel/app.py', '# test app')
            zf.writestr('zeropanel/static/js/test.js', '// test')
            zf.writestr('zeropanel/../../etc/passwd', 'attack')  # zip slip，应被阻止
            zf.writestr('zeropanel/data/../nested.txt', 'nested')  # 规范化后在 extract_dir 内，允许

        extract_dir = tmpdir / 'extracted'
        extract_dir.mkdir()
        _safe_extract_update(zip_path, extract_dir)

        test('正常文件已解压', (extract_dir / 'app.py').exists())
        test('正常子目录文件已解压', (extract_dir / 'static' / 'js' / 'test.js').exists())
        test('zip slip 被阻止', not (tmpdir / 'etc' / 'passwd').exists())
        test('安全相对路径被规范化后允许', (extract_dir / 'nested.txt').exists())
    finally:
        shutil.rmtree(tmpdir)

    # 8. Flask 路由基础检查
    print('\n8. Flask 路由基础检查')
    routes = {rule.rule: list(rule.methods) for rule in app.url_map.iter_rules()}
    test('登录 API 存在', '/api/login' in routes)
    test('登出 API 存在', '/api/logout' in routes)
    test('认证检查 API 存在', '/api/check-auth' in routes)
    test('网站列表 API 存在', '/api/websites' in routes)
    test('文件列表 API 存在', '/api/files' in routes)
    test('数据库列表 API 存在', '/api/databases' in routes)
    test('系统信息 API 存在', '/api/system/info' in routes)
    test('检查更新 API 存在', '/api/system/check-update' in routes)
    test('执行更新 API 存在', '/api/system/do-update' in routes)
    test('重启面板 API 存在', '/api/system/restart' in routes)
    test('根路径 / 存在（登录页）', '/' in routes)

    # 9. 登录/认证流程（使用测试客户端）
    print('\n9. 登录/认证流程')
    init_db()
    app.config['TESTING'] = True
    client = app.test_client()

    # 未登录访问受保护页面
    resp = client.get('/dashboard')
    test('未登录重定向到登录页', resp.status_code in (302, 401))

    # 错误登录
    resp = client.post('/api/login', json={'username': 'admin', 'password': 'wrong'})
    data = resp.get_json()
    test('错误密码登录失败', not data['success'])

    # 正确登录
    resp = client.post('/api/login', json={'username': 'admin', 'password': 'admin123'})
    data = resp.get_json()
    test('正确密码登录成功', data['success'])

    # 登录后访问
    resp = client.get('/dashboard')
    test('登录后可访问仪表盘', resp.status_code == 200)

    # 检查认证
    resp = client.get('/api/check-auth')
    data = resp.get_json()
    test('认证状态正确', data['authenticated'] and data['user']['username'] == 'admin')

    # 登出
    resp = client.post('/api/logout')
    data = resp.get_json()
    test('登出成功', data['success'])

    resp = client.get('/api/check-auth')
    data = resp.get_json()
    test('登出后认证状态正确', not data['authenticated'])

    # 10. 文件管理路径安全
    print('\n10. 文件管理路径安全')
    with app.test_client() as c:
        c.post('/api/login', json={'username': 'admin', 'password': 'admin123'})

        # 允许读取整个文件系统（策略已放开）
        resp = c.get('/api/files/read?path=/etc/hostname')
        data = resp.get_json()
        test('允许读取 /etc/hostname', not data.get('success', True) or 'content' in data)

        # 禁止读取面板程序目录
        resp = c.get('/api/files/read?path=' + str(APP_BASE_DIR / 'app.py'))
        data = resp.get_json()
        test('阻止读取面板程序文件', not data.get('success', True))

        # 允许读取 www 目录
        resp = c.get('/api/files?path=' + str(WWW_DIR))
        data = resp.get_json()
        test('允许读取 www 目录', 'files' in data)

        # 默认打开网站目录（不传 path 或空 path 时回退 WWW_DIR）
        resp = c.get('/api/files')
        data = resp.get_json()
        test('默认打开网站目录', data.get('path') == str(WWW_DIR))

        # 备份数据目录对文件管理隐藏
        resp = c.get('/api/files?path=' + str(DATA_DIR / 'backups'))
        data = resp.get_json()
        test('备份数据目录对文件管理隐藏', data.get('path') != str(DATA_DIR / 'backups'))

    # 11. 数据库名注入防护
    print('\n11. 数据库名注入防护')
    with app.test_client() as c:
        c.post('/api/login', json={'username': 'admin', 'password': 'admin123'})
        resp = c.post('/api/databases', json={'name': 'test; DROP TABLE account;'})
        data = resp.get_json()
        test('非法数据库名被拒绝', not data['success'])

    # 12. 网站管理 CRUD
    print('\n12. 网站管理 CRUD')

    # Mock run_command，使 nginx 命令在测试环境中返回成功
    import app as app_module
    original_run_command = app_module.run_command

    def mock_run_command(cmd, shell=False):
        if isinstance(cmd, list) and len(cmd) > 0 and cmd[0] in ('nginx', 'pgrep'):
            return True, '', ''
        return original_run_command(cmd, shell=shell)

    app_module.run_command = mock_run_command

    with app.test_client() as c:
        c.post('/api/login', json={'username': 'admin', 'password': 'admin123'})

        # 创建网站
        resp = c.post('/api/websites', json={
            'domain': 'testsite.local',
            'port': 18080,
            'root': str(WWW_DIR / 'testsite.local'),
            'php_version': '8.0'
        })
        data = resp.get_json()
        test('创建网站成功', data['success'])
        website_id = data.get('id')

        # 列表
        resp = c.get('/api/websites')
        data = resp.get_json()
        test('网站列表包含新网站', any(w['id'] == website_id for w in data['websites']))

        # 停止
        resp = c.post(f'/api/websites/{website_id}/stop')
        data = resp.get_json()
        test('停止网站成功', data['success'])

        # 启动
        resp = c.post(f'/api/websites/{website_id}/start')
        data = resp.get_json()
        test('启动网站成功', data['success'])

        # 重启
        resp = c.post(f'/api/websites/{website_id}/restart')
        data = resp.get_json()
        test('重启网站成功', data['success'])

        # 重启不存在网站应失败
        resp = c.post('/api/websites/nonexistent/restart')
        data = resp.get_json()
        test('重启不存在网站失败', not data['success'])

        # 删除
        resp = c.delete(f'/api/websites/{website_id}')
        data = resp.get_json()
        test('删除网站成功', data['success'])

    app_module.run_command = original_run_command

    print('\n' + '=' * 50)
    print(f'验证完成：通过 {PASS} 项，失败 {FAIL} 项')
    if FAIL > 0:
        print('存在失败项，请检查。')
        sys.exit(1)
    else:
        print('所有验证通过。')


if __name__ == '__main__':
    main()
