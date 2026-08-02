// ZeroPanel v2.0 - 定时任务管理逻辑

let cronJobs = [];

// 加载任务列表
async function loadCronJobs() {
    try {
        showLoading('加载任务列表...');
        const data = await apiRequest('/api/cron');
        cronJobs = data.jobs || [];
        renderCronList();
    } catch (error) {
        showToast('加载任务列表失败', 'error');
    } finally {
        hideLoading();
    }
}

// 渲染任务列表
function renderCronList() {
    const tbody = document.getElementById('cron-list');
    
    if (cronJobs.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="5">
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" width="48" height="48" stroke="#4a4a6a" stroke-width="2" fill="none">
                            <circle cx="12" cy="12" r="10"/>
                            <polyline points="12 6 12 12 16 14"/>
                        </svg>
                        <p>暂无定时任务，点击上方按钮添加</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = cronJobs.map(job => `
        <tr>
            <td>${job.name}</td>
            <td><code class="cron-expression">${job.schedule}</code></td>
            <td><code class="cron-command">${job.command}</code></td>
            <td>
                <span class="badge ${job.enabled !== false ? 'badge-success' : 'badge-error'}">
                    ${job.enabled !== false ? '启用' : '禁用'}
                </span>
            </td>
            <td>
                <div class="action-btns">
                    <button class="action-btn" onclick="toggleCronJob('${job.id}')">
                        ${job.enabled !== false ? '禁用' : '启用'}
                    </button>
                    <button class="action-btn danger" onclick="deleteCronJob('${job.id}')">
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

// 显示添加任务弹窗
function showCreateCronModal() {
    document.getElementById('create-cron-modal').classList.add('show');
    document.getElementById('cron-name').value = '';
    document.getElementById('cron-template').value = '';
    document.getElementById('cron-minute').value = '*';
    document.getElementById('cron-hour').value = '*';
    document.getElementById('cron-day').value = '*';
    document.getElementById('cron-month').value = '*';
    document.getElementById('cron-week').value = '*';
    document.getElementById('cron-command').value = '';
}

// 隐藏添加任务弹窗
function hideCreateCronModal() {
    document.getElementById('create-cron-modal').classList.remove('show');
}

// 应用 cron 模板
function applyCronTemplate(template) {
    if (!template) return;
    const parts = template.split(' ');
    if (parts.length === 5) {
        document.getElementById('cron-minute').value = parts[0];
        document.getElementById('cron-hour').value = parts[1];
        document.getElementById('cron-day').value = parts[2];
        document.getElementById('cron-month').value = parts[3];
        document.getElementById('cron-week').value = parts[4];
    }
}

// 获取 cron 表达式
function getCronExpression() {
    const minute = document.getElementById('cron-minute').value || '*';
    const hour = document.getElementById('cron-hour').value || '*';
    const day = document.getElementById('cron-day').value || '*';
    const month = document.getElementById('cron-month').value || '*';
    const week = document.getElementById('cron-week').value || '*';
    return `${minute} ${hour} ${day} ${month} ${week}`;
}

// 添加任务
document.getElementById('create-cron-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('cron-name').value;
    const schedule = getCronExpression();
    const command = document.getElementById('cron-command').value;
    
    try {
        showLoading('添加任务中...');
        const data = await apiRequest('/api/cron', {
            method: 'POST',
            body: JSON.stringify({ name, schedule, command })
        });
        
        if (data.success) {
            showToast('任务添加成功', 'success');
            hideCreateCronModal();
            loadCronJobs();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
});

// 启用/禁用任务
async function toggleCronJob(id) {
    try {
        showLoading('切换任务状态...');
        const data = await apiRequest(`/api/cron/${id}/toggle`, { method: 'POST' });
        
        if (data.success) {
            showToast('状态已更新', 'success');
            loadCronJobs();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 删除任务
async function deleteCronJob(id) {
    if (!confirm('确定要删除这个任务吗？')) return;
    
    try {
        showLoading('删除任务中...');
        const data = await apiRequest(`/api/cron/${id}`, { method: 'DELETE' });
        
        if (data.success) {
            showToast('任务已删除', 'success');
            loadCronJobs();
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
document.addEventListener('DOMContentLoaded', loadCronJobs);
