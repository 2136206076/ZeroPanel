// ZeroPanel v2.0 - PHP 管理逻辑

let phpVersions = [];
let currentVersion = '';
let currentExtensions = [];

// 加载 PHP 版本列表
async function loadPhpVersions() {
    try {
        showLoading('加载 PHP 版本...');
        const data = await apiRequest('/api/php/versions');
        phpVersions = data.versions || [];
        renderPhpVersions();
        
        // 默认选中第一个已安装的版本
        const installed = phpVersions.find(v => v.installed);
        if (installed) {
            selectVersion(installed.version);
        }
    } catch (error) {
        showToast('加载 PHP 版本失败', 'error');
    } finally {
        hideLoading();
    }
}

// 渲染 PHP 版本列表
function renderPhpVersions() {
    const container = document.getElementById('php-versions');
    
    if (phpVersions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无 PHP 版本信息</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = phpVersions.map(v => {
        const disabled = !v.installed && !v.available;
        return `
        <div class="php-version-card ${v.version === currentVersion ? 'active' : ''} ${disabled ? 'php-version-disabled' : ''}" onclick="${disabled ? '' : `selectVersion('${v.version}')`}">
            <div class="php-version-header">
                <span class="php-version-number">PHP ${v.version}</span>
                <span class="badge ${v.installed ? 'badge-success' : (v.available ? 'badge-error' : 'badge-warning')}">
                    ${v.installed ? '已安装' : (v.available ? '未安装' : '源中不可用')}
                </span>
            </div>
            <div class="php-version-status">
                <span class="status-dot ${v.fpm_running ? 'running' : 'stopped'}"></span>
                <span class="status-text">FPM ${v.fpm_running ? '运行中' : '已停止'}</span>
            </div>
            <div class="php-version-actions" onclick="event.stopPropagation()">
                ${v.installed ? `
                    <button class="btn btn-small btn-secondary" onclick="restartFpm('${v.version}')">
                        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                            <polyline points="23 4 23 10 17 10"/>
                            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                        </svg>
                        重启 FPM
                    </button>
                    <button class="btn btn-small btn-danger" onclick="uninstallPhp('${v.version}')">卸载</button>
                ` : (v.available ? `
                    <button class="btn btn-small btn-primary" onclick="installPhp('${v.version}')">安装</button>
                ` : `
                    <span class="php-version-note">当前系统源中无此版本</span>
                `)}
            </div>
        </div>
    `;
    }).join('');
}

// 选择 PHP 版本
async function selectVersion(version) {
    currentVersion = version;
    renderPhpVersions();
    document.getElementById('selected-version').textContent = `PHP ${version}`;
    await loadExtensions(version);
}

// 加载扩展列表
async function loadExtensions(version) {
    const container = document.getElementById('php-extensions');
    container.innerHTML = `
        <div class="empty-state">
            <svg class="spinner" viewBox="0 0 24 24" width="32" height="32" stroke="currentColor" stroke-width="2" fill="none">
                <circle cx="12" cy="12" r="10" stroke-dasharray="50" stroke-dashoffset="20" stroke-linecap="round"/>
            </svg>
            <p>加载扩展中...</p>
        </div>
    `;
    
    try {
        const data = await apiRequest(`/api/php/extensions?version=${encodeURIComponent(version)}`);
        currentExtensions = data.extensions || [];
        renderExtensions();
    } catch (error) {
        container.innerHTML = `
            <div class="empty-state">
                <p>加载扩展失败</p>
            </div>
        `;
    }
}

// 渲染扩展列表
function renderExtensions() {
    const container = document.getElementById('php-extensions');
    
    if (currentExtensions.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无扩展信息</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = currentExtensions.map(ext => `
        <div class="php-extension-item">
            <div class="php-extension-info">
                <span class="php-extension-name">${ext.name}</span>
                <span class="badge ${ext.installed ? 'badge-success' : 'badge-error'}">
                    ${ext.installed ? '已安装' : '未安装'}
                </span>
            </div>
            <button class="btn btn-small ${ext.installed ? 'btn-danger' : 'btn-primary'}" onclick="${ext.installed ? 'uninstallExtension' : 'installExtension'}('${currentVersion}', '${ext.name}')">
                ${ext.installed ? '卸载' : '安装'}
            </button>
        </div>
    `).join('');
}

// 安装 PHP 版本
async function installPhp(version) {
    try {
        showLoading(`正在安装 PHP ${version}...`);
        const data = await apiRequest('/api/php/versions', {
            method: 'POST',
            body: JSON.stringify({ version, action: 'install' })
        });
        
        if (data.success) {
            showToast(`PHP ${version} 安装成功`, 'success');
            loadPhpVersions();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 卸载 PHP 版本
async function uninstallPhp(version) {
    if (!confirm(`确定要卸载 PHP ${version} 吗？`)) return;
    
    try {
        showLoading(`正在卸载 PHP ${version}...`);
        const data = await apiRequest('/api/php/versions', {
            method: 'POST',
            body: JSON.stringify({ version, action: 'uninstall' })
        });
        
        if (data.success) {
            showToast(`PHP ${version} 卸载成功`, 'success');
            loadPhpVersions();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 重启 FPM
async function restartFpm(version) {
    try {
        showLoading('正在重启 FPM...');
        const data = await apiRequest('/api/php/fpm/restart', {
            method: 'POST',
            body: JSON.stringify({ version })
        });
        
        if (data.success) {
            showToast('FPM 重启成功', 'success');
            loadPhpVersions();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 安装扩展
async function installExtension(version, extension) {
    try {
        showLoading(`正在安装 ${extension}...`);
        const data = await apiRequest('/api/php/extensions', {
            method: 'POST',
            body: JSON.stringify({ version, extension, action: 'install' })
        });
        
        if (data.success) {
            showToast(`${extension} 安装成功`, 'success');
            loadExtensions(version);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 卸载扩展
async function uninstallExtension(version, extension) {
    if (!confirm(`确定要卸载 ${extension} 吗？`)) return;
    
    try {
        showLoading(`正在卸载 ${extension}...`);
        const data = await apiRequest('/api/php/extensions', {
            method: 'POST',
            body: JSON.stringify({ version, extension, action: 'uninstall' })
        });
        
        if (data.success) {
            showToast(`${extension} 卸载成功`, 'success');
            loadExtensions(version);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', loadPhpVersions);
