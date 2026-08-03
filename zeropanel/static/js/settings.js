// ZeroPanel v2.0 - 账号设置逻辑

// 加载用户信息
async function loadUserInfo() {
    try {
        const response = await fetch('/api/check-auth');
        const data = await response.json();
        
        if (data.authenticated && data.user) {
            document.getElementById('current-username').textContent = data.user.username;
        }
    } catch (error) {
        console.error('加载用户信息失败:', error);
    }
}

// 密码强度检测
function checkPasswordStrength(password) {
    let strength = 0;
    
    if (password.length >= 6) strength += 1;
    if (password.length >= 10) strength += 1;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength += 1;
    if (/\d/.test(password)) strength += 1;
    if (/[^a-zA-Z0-9]/.test(password)) strength += 1;
    
    return strength;
}

function updatePasswordStrength(password) {
    const strength = checkPasswordStrength(password);
    const fill = document.getElementById('strength-fill');
    const text = document.getElementById('strength-text');
    
    const percent = (strength / 5) * 100;
    fill.style.width = `${percent}%`;
    
    if (strength <= 1) {
        fill.style.background = '#ef4444';
        text.textContent = '弱';
    } else if (strength <= 2) {
        fill.style.background = '#f59e0b';
        text.textContent = '中等';
    } else if (strength <= 3) {
        fill.style.background = '#22c55e';
        text.textContent = '较强';
    } else {
        fill.style.background = '#00d4ff';
        text.textContent = '强';
    }
}

// 监听密码输入
document.getElementById('new-password').addEventListener('input', (e) => {
    updatePasswordStrength(e.target.value);
});

// 修改密码
document.getElementById('password-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const oldPassword = document.getElementById('old-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    if (newPassword !== confirmPassword) {
        showToast('两次密码输入不一致', 'error');
        return;
    }
    
    if (newPassword.length < 6) {
        showToast('密码长度至少6位', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/account/password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                old_password: oldPassword,
                new_password: newPassword,
                confirm_password: confirmPassword
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('密码修改成功', 'success');
            document.getElementById('password-form').reset();
            document.getElementById('strength-fill').style.width = '0';
            document.getElementById('strength-text').textContent = '密码强度';
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

// 初始化
document.addEventListener('DOMContentLoaded', loadUserInfo);

// ==================== 云更新功能 ====================

let updateData = null;
let backupFile = null;

// 加载版本信息
async function loadVersion() {
    try {
        const response = await fetch('/api/system/version');
        const data = await response.json();
        document.getElementById('current-version').textContent = 'v' + data.version;
    } catch (error) {
        console.error('获取版本信息失败:', error);
    }
}

// 检查更新
async function checkUpdate() {
    const btn = document.getElementById('check-update-btn');
    btn.disabled = true;
    btn.innerHTML = '<svg class="spin" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><circle cx="12" cy="12" r="10" stroke-dasharray="31.4" stroke-dashoffset="10"/></svg> 检查中...';

    try {
        const response = await fetch('/api/system/check-update');
        const data = await response.json();

        document.getElementById('latest-version').textContent = 'v' + (data.latest_version || '未知');

        if (data.success) {
            updateData = data;

            if (data.is_update_available) {
                document.getElementById('update-status').innerHTML = '<span class="badge badge-success">有新版本</span>';
                document.getElementById('update-actions').style.display = 'flex';

                // 显示更新日志
                if (data.release_notes) {
                    document.getElementById('release-notes').innerHTML = formatReleaseNotes(data.release_notes);
                    document.getElementById('update-log').style.display = 'block';
                }

                showToast('发现新版本: v' + data.latest_version, 'info');
            } else {
                document.getElementById('update-status').innerHTML = '<span class="badge badge-success">已是最新</span>';
                showToast('当前已是最新版本', 'success');
            }
        } else {
            document.getElementById('update-status').innerHTML = '<span class="badge badge-error">' + (data.error || '检查失败') + '</span>';
            showToast(data.error || '检查更新失败', 'error');
        }
    } catch (error) {
        document.getElementById('update-status').innerHTML = '<span class="badge badge-error">网络错误</span>';
        showToast('网络连接失败', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> 检查更新';
    }
}

// 格式化更新日志
function formatReleaseNotes(notes) {
    if (!notes) return '';
    return notes.split('\n').map(line => {
        line = line.trim();
        if (line.startsWith('-') || line.startsWith('*')) {
            return '<li>' + line.substring(1).trim() + '</li>';
        }
        if (line.match(/^\d+\./)) {
            return '<li>' + line.replace(/^\d+\.\s*/, '') + '</li>';
        }
        if (line) {
            return '<p>' + line + '</p>';
        }
        return '';
    }).join('');
}

// 执行更新
async function doUpdate() {
    if (!updateData || !updateData.download_url) {
        showToast('无可用更新', 'error');
        return;
    }

    if (!confirm('确定要更新到 v' + updateData.latest_version + ' 吗？\n更新前会自动备份当前版本。')) {
        return;
    }

    const btn = document.getElementById('do-update-btn');
    const progress = document.getElementById('update-progress');

    btn.disabled = true;
    btn.innerHTML = '<svg class="spin" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><circle cx="12" cy="12" r="10" stroke-dasharray="31.4" stroke-dashoffset="10"/></svg> 更新中...';
    progress.style.display = 'block';
    updateProgress(10, '正在下载更新包...');

    try {
        const response = await fetch('/api/system/do-update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                download_url: updateData.download_url
            })
        });

        const data = await response.json();

        if (data.success) {
            backupFile = data.backup_file;
            updateProgress(100, '更新包下载完成');
            showToast('更新包下载完成，请点击"重启面板"使更新生效', 'success');

            // 显示重启按钮
            document.getElementById('restart-btn').style.display = 'inline-flex';
        } else {
            showToast(data.message || '更新失败', 'error');
            btn.disabled = false;
            btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> 一键更新';
            progress.style.display = 'none';
        }
    } catch (error) {
        showToast('更新失败: ' + error.message, 'error');
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> 一键更新';
        progress.style.display = 'none';
    }
}

// 更新进度条
function updateProgress(percent, text) {
    document.getElementById('progress-fill').style.width = percent + '%';
    document.getElementById('progress-text').textContent = text;
}

// 重启面板
async function restartPanel() {
    if (!confirm('确定要重启面板吗？')) {
        return;
    }

    const btn = document.getElementById('restart-btn');
    btn.disabled = true;
    btn.innerHTML = '<svg class="spin" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><circle cx="12" cy="12" r="10" stroke-dasharray="31.4" stroke-dashoffset="10"/></svg> 重启中...';

    try {
        const response = await fetch('/api/system/restart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            showToast('面板正在重启，请稍后刷新页面...', 'success');

            // 延迟跳转登录页
            setTimeout(() => {
                window.location.href = '/';
            }, 3000);
        } else {
            showToast(data.message || '重启失败', 'error');
            btn.disabled = false;
            btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> 重启面板';
        }
    } catch (error) {
        showToast('重启失败: ' + error.message, 'error');
        btn.disabled = false;
        btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> 重启面板';
    }
}

// 加载备份列表
async function loadBackups() {
    try {
        const response = await fetch('/api/system/backups');
        const data = await response.json();
        const container = document.getElementById('backup-list');

        if (!data.success) {
            container.innerHTML = `<p class="text-secondary" style="font-size: 13px;">获取备份列表失败: ${data.message || '未知错误'}</p>`;
            return;
        }

        const backups = data.backups || [];
        if (backups.length === 0) {
            container.innerHTML = '<p class="text-secondary" style="font-size: 13px;">暂无备份文件</p>';
            return;
        }

        let html = '<div style="max-height: 200px; overflow-y: auto; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 8px;">';
        backups.forEach(backup => {
            const size = backup.size < 1024 ? backup.size + ' B' :
                backup.size < 1024 * 1024 ? (backup.size / 1024).toFixed(1) + ' KB' :
                (backup.size / (1024 * 1024)).toFixed(1) + ' MB';
            html += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <div style="font-size: 13px;">
                        <div style="color: #e2e8f0;">${backup.filename}</div>
                        <div style="color: #94a3b8; font-size: 11px;">${backup.created} · ${size}</div>
                    </div>
                    <button class="btn btn-small btn-danger" onclick="rollback('${backup.path}')">回滚</button>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    } catch (error) {
        document.getElementById('backup-list').innerHTML = `<p class="text-secondary" style="font-size: 13px;">获取备份列表失败: ${error.message}</p>`;
    }
}

// 回滚到指定备份
async function rollback(backupPath) {
    if (!confirm('确定要回滚到该备份版本吗？\n回滚后会覆盖当前面板程序文件，请谨慎操作。')) {
        return;
    }

    try {
        const response = await fetch('/api/system/rollback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ backup_file: backupPath })
        });

        const data = await response.json();
        if (data.success) {
            showToast('回滚成功，请重启面板使恢复生效', 'success');
            document.getElementById('restart-btn').style.display = 'inline-flex';
        } else {
            showToast(data.message || '回滚失败', 'error');
        }
    } catch (error) {
        showToast('回滚失败: ' + error.message, 'error');
    }
}

// 页面加载完成后自动检查更新并加载备份列表
document.addEventListener('DOMContentLoaded', () => {
    loadVersion();
    checkUpdate();
    loadBackups();
});