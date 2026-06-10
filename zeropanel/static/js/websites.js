// ZeroPanel v2.0 - 网站管理逻辑

let websites = [];

// 加载网站列表
async function loadWebsites() {
    try {
        const response = await fetch('/api/websites');
        const data = await response.json();
        websites = data.websites || [];
        renderWebsiteList();
    } catch (error) {
        showToast('加载网站列表失败', 'error');
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
    document.getElementById('root').value = '';
}

// 隐藏创建弹窗
function hideCreateModal() {
    document.getElementById('create-modal').classList.remove('show');
}

// 创建网站
document.getElementById('create-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const domain = document.getElementById('domain').value;
    const port = document.getElementById('port').value;
    const root = document.getElementById('root').value;
    const php_version = document.getElementById('php_version').value;
    
    try {
        const response = await fetch('/api/websites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain, port: parseInt(port), root, php_version })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('网站创建成功', 'success');
            hideCreateModal();
            loadWebsites();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

// 启动网站
async function startWebsite(id) {
    try {
        const response = await fetch(`/api/websites/${id}/start`, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast('网站已启动', 'success');
            loadWebsites();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 停止网站
async function stopWebsite(id) {
    try {
        const response = await fetch(`/api/websites/${id}/stop`, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast('网站已停止', 'success');
            loadWebsites();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 删除网站
async function deleteWebsite(id) {
    if (!confirm('确定要删除这个网站吗？')) return;
    
    try {
        const response = await fetch(`/api/websites/${id}`, { method: 'DELETE' });
        const data = await response.json();
        
        if (data.success) {
            showToast('网站已删除', 'success');
            loadWebsites();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', loadWebsites);