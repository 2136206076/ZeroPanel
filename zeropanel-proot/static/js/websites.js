// ZeroPanel v2.0 - 网站管理逻辑

let websites = [];
let rewriteTemplates = {};
let currentDbInfoId = '';

// 伪静态规则模板
const builtInTemplates = {
    wordpress: `location / {
    try_files $uri $uri/ /index.php?$args;
}`,
    thinkphp: `location / {
    if (!-e $request_filename) {
        rewrite ^(.*)$ /index.php?s=$1 last;
    }
}`,
    laravel: `location / {
    try_files $uri $uri/ /index.php?$query_string;
}`,
    typecho: `location / {
    index index.php index.html;
    if (-f $request_filename/index.html) {
        rewrite (.*) $1/index.html break;
    }
    if (-f $request_filename/index.php) {
        rewrite (.*) $1/index.php;
    }
    if (!-f $request_filename) {
        rewrite (.*) /index.php;
    }
}`
};

// 加载网站列表
async function loadWebsites() {
    try {
        showLoading('加载网站列表...');
        const data = await apiRequest('/api/websites');
        websites = data.websites || [];
        renderWebsiteList();
    } catch (error) {
        showToast('加载网站列表失败', 'error');
    } finally {
        hideLoading();
    }
}

// 加载伪静态模板
async function loadRewriteTemplates() {
    try {
        const data = await apiRequest('/api/rewrite/templates');
        if (data.success && data.templates) {
            rewriteTemplates = { ...builtInTemplates, ...data.templates };
        } else {
            rewriteTemplates = builtInTemplates;
        }
    } catch (error) {
        rewriteTemplates = builtInTemplates;
    }
}

// 渲染网站列表
function renderWebsiteList() {
    const tbody = document.getElementById('website-list');
    
    if (websites.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="7">
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" width="48" height="48" stroke="#4a4a6a" stroke-width="2" fill="none">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="2" y1="12" x2="22" y2="12"/>
                            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                        </svg>
                        <p>暂无网站，点击上方按钮创建</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = websites.map(site => `
        <tr>
            <td>${site.domain}</td>
            <td>:${site.port || '8080'}</td>
            <td>${site.root_path}</td>
            <td>PHP ${site.php_version}</td>
            <td>
                <span class="badge ${site.status === 'running' ? 'badge-success' : 'badge-error'}">
                    ${site.status === 'running' ? '运行中' : '已停止'}
                </span>
            </td>
            <td>${site.created_at || '-'}</td>
            <td>
                <div class="action-btns">
                    <button class="action-btn" onclick="showDbInfoModal('${site.id}', event)">
                        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                            <ellipse cx="12" cy="5" rx="9" ry="3"/>
                            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                        </svg>
                        数据库信息
                    </button>
                    <button class="action-btn" onclick="startWebsite('${site.id}')">
                        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                            <polygon points="5 3 19 12 5 21 5 3"/>
                        </svg>
                        启动
                    </button>
                    <button class="action-btn" onclick="stopWebsite('${site.id}')">
                        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                            <rect x="6" y="4" width="4" height="16"/>
                            <rect x="14" y="4" width="4" height="16"/>
                        </svg>
                        停止
                    </button>
                    <button class="action-btn danger" onclick="deleteWebsite('${site.id}')">
                        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                        删除
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

// 显示创建弹窗
function showCreateModal() {
    document.getElementById('create-modal').classList.add('show');
    document.getElementById('domain').value = '';
    document.getElementById('port').value = '8080';
    document.getElementById('root').value = '';
    document.getElementById('php_version').value = '8.0';
    document.getElementById('create_database').checked = false;
    document.getElementById('rewrite_template').value = '';
    document.getElementById('rewrite_rules').value = '';
    document.getElementById('create-db-group').style.display = 'block';
}

// 隐藏创建弹窗
function hideCreateModal() {
    document.getElementById('create-modal').classList.remove('show');
}

// 应用伪静态模板
function applyRewriteTemplate(template) {
    const textarea = document.getElementById('rewrite_rules');
    if (!template) {
        return;
    }
    const rules = rewriteTemplates[template] || builtInTemplates[template] || '';
    if (rules) {
        textarea.value = rules;
    }
}

// 创建网站
document.getElementById('create-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const domain = document.getElementById('domain').value;
    const port = document.getElementById('port').value;
    const root = document.getElementById('root').value;
    const php_version = document.getElementById('php_version').value;
    const create_database = document.getElementById('create_database').checked;
    const rewrite_rules = document.getElementById('rewrite_rules').value;
    
    try {
        showLoading('正在创建网站...');
        const data = await apiRequest('/api/websites', {
            method: 'POST',
            body: JSON.stringify({
                domain,
                port: parseInt(port),
                root,
                php_version,
                create_database,
                rewrite_rules
            })
        });
        
        if (data.success) {
            showToast('网站创建成功', 'success');
            hideCreateModal();
            loadWebsites();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
});

// 显示数据库信息弹窗
async function showDbInfoModal(id, event) {
    if (event) event.stopPropagation();
    currentDbInfoId = id;
    
    const list = document.getElementById('db-info-list');
    list.innerHTML = `
        <div class="empty-state">
            <svg class="spinner" viewBox="0 0 24 24" width="32" height="32" stroke="currentColor" stroke-width="2" fill="none">
                <circle cx="12" cy="12" r="10" stroke-dasharray="50" stroke-dashoffset="20" stroke-linecap="round"/>
            </svg>
            <p>加载中...</p>
        </div>
    `;
    document.getElementById('db-info-modal').classList.add('show');
    
    try {
        const data = await apiRequest(`/api/websites/${id}/db`);
        if (data.success && data.database) {
            const db = data.database;
            list.innerHTML = `
                <div class="info-row">
                    <span class="info-label">数据库名</span>
                    <span class="info-value">${db.name || '-'}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">用户名</span>
                    <span class="info-value">${db.username || '-'}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">密码</span>
                    <span class="info-value">${db.password || '-'}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">状态</span>
                    <span class="info-value">${db.exists ? '已创建' : '未创建'}</span>
                </div>
            `;
        } else {
            list.innerHTML = `
                <div class="empty-state">
                    <p>${data.message || '暂无数据库信息'}</p>
                </div>
            `;
        }
    } catch (error) {
        list.innerHTML = `
            <div class="empty-state">
                <p>加载数据库信息失败</p>
            </div>
        `;
    }
}

// 隐藏数据库信息弹窗
function hideDbInfoModal() {
    document.getElementById('db-info-modal').classList.remove('show');
}

// 启动网站
async function startWebsite(id) {
    try {
        showLoading('正在启动网站...');
        const data = await apiRequest(`/api/websites/${id}/start`, { method: 'POST' });
        
        if (data.success) {
            showToast('网站已启动', 'success');
            loadWebsites();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 停止网站
async function stopWebsite(id) {
    try {
        showLoading('正在停止网站...');
        const data = await apiRequest(`/api/websites/${id}/stop`, { method: 'POST' });
        
        if (data.success) {
            showToast('网站已停止', 'success');
            loadWebsites();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 删除网站
async function deleteWebsite(id) {
    if (!confirm('确定要删除这个网站吗？')) return;
    
    try {
        showLoading('正在删除网站...');
        const data = await apiRequest(`/api/websites/${id}`, { method: 'DELETE' });
        
        if (data.success) {
            showToast('网站已删除', 'success');
            loadWebsites();
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
document.addEventListener('DOMContentLoaded', () => {
    loadWebsites();
    loadRewriteTemplates();
});
