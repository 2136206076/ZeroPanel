// ZeroPanel v2.0 - 数据库管理逻辑

let databases = [];
let currentDbName = '';

// 加载数据库列表
async function loadDatabases() {
    try {
        const response = await fetch('/api/databases');
        const data = await response.json();
        databases = data.databases || [];
        renderDatabaseList();
    } catch (error) {
        showToast('加载数据库列表失败', 'error');
    }
}

// 渲染数据库列表
function renderDatabaseList() {
    const tbody = document.getElementById('database-list');
    
    if (databases.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="5">
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" width="48" height="48" stroke="#4a4a6a" stroke-width="2" fill="none">
                            <ellipse cx="12" cy="5" rx="9" ry="3"/>
                            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                        </svg>
                        <p>暂无数据库，点击上方按钮创建</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = databases.map(db => `
        <tr>
            <td>${db.name}</td>
            <td>${db.charset}</td>
            <td>${db.tables}</td>
            <td>${formatSize(db.size)}</td>
            <td>
                <div class="action-btns">
                    <button class="action-btn" onclick="backupDatabase('${db.name}')">
                        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                        备份
                    </button>
                    <button class="action-btn" onclick="showBackupList('${db.name}')">
                        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                        备份列表
                    </button>
                    <button class="action-btn danger" onclick="deleteDatabase('${db.name}')">
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

// 显示创建数据库弹窗
function showCreateDbModal() {
    document.getElementById('create-db-modal').classList.add('show');
    document.getElementById('db-name').value = '';
    document.getElementById('db-user').value = '';
    document.getElementById('db-password').value = '';
}

// 隐藏创建数据库弹窗
function hideCreateDbModal() {
    document.getElementById('create-db-modal').classList.remove('show');
}

// 创建数据库
document.getElementById('create-db-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('db-name').value;
    const charset = document.getElementById('db-charset').value;
    const user = document.getElementById('db-user').value;
    const password = document.getElementById('db-password').value;
    
    try {
        const response = await fetch('/api/databases', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, charset, user, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('数据库创建成功', 'success');
            hideCreateDbModal();
            loadDatabases();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

// 备份数据库
async function backupDatabase(name) {
    showToast('正在备份...', 'warning');
    
    try {
        const response = await fetch(`/api/databases/${name}/backup`);
        const data = await response.json();
        
        if (data.success) {
            showToast('备份成功', 'success');
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 显示备份列表
async function showBackupList(name) {
    currentDbName = name;
    
    try {
        const response = await fetch(`/api/databases/${name}/backups`);
        const data = await response.json();
        
        const tbody = document.getElementById('backup-list');
        const backups = data.backups || [];
        
        if (backups.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="4">
                        <div class="empty-state">
                            <p>暂无备份</p>
                        </div>
                    </td>
                </tr>
            `;
        } else {
            tbody.innerHTML = backups.map(bk => `
                <tr>
                    <td>${bk.file.split('/').pop()}</td>
                    <td>${formatSize(bk.size)}</td>
                    <td>${bk.created_at}</td>
                    <td>
                        <button class="action-btn" onclick="restoreDatabase('${name}', '${bk.file}')">
                            恢复
                        </button>
                    </td>
                </tr>
            `).join('');
        }
        
        document.getElementById('backup-modal').classList.add('show');
    } catch (error) {
        showToast('加载备份列表失败', 'error');
    }
}

// 隐藏备份列表弹窗
function hideBackupModal() {
    document.getElementById('backup-modal').classList.remove('show');
}

// 恢复数据库
async function restoreDatabase(name, file) {
    if (!confirm('确定要恢复这个备份吗？')) return;
    
    try {
        const response = await fetch(`/api/databases/${name}/restore`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('数据库已恢复', 'success');
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 删除数据库
async function deleteDatabase(name) {
    if (!confirm('确定要删除这个数据库吗？此操作不可恢复！')) return;

    try {
        const response = await fetch(`/api/databases/${name}`, { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {
            showToast('数据库已删除', 'success');
            loadDatabases();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 显示导入数据库弹窗
function showImportDbModal() {
    document.getElementById('import-db-modal').classList.add('show');
    document.getElementById('import-db-name').value = '';
    document.getElementById('import-db-file').value = '';
    document.getElementById('import-progress-group').style.display = 'none';
    document.getElementById('import-progress-fill').style.width = '0%';
    document.getElementById('import-db-submit').disabled = false;
    document.getElementById('import-db-submit').textContent = '开始导入';
}

// 隐藏导入数据库弹窗
function hideImportDbModal() {
    document.getElementById('import-db-modal').classList.remove('show');
}

// 提交导入数据库
document.getElementById('import-db-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const name = document.getElementById('import-db-name').value.trim();
    const fileInput = document.getElementById('import-db-file');
    const file = fileInput.files[0];

    if (!name) {
        showToast('请输入目标数据库名', 'error');
        return;
    }
    if (!file) {
        showToast('请选择 SQL 文件', 'error');
        return;
    }
    if (!file.name.toLowerCase().endsWith('.sql')) {
        showToast('只支持 .sql 文件', 'error');
        return;
    }
    if (file.size > 100 * 1024 * 1024) {
        showToast('文件大小超过 100MB', 'error');
        return;
    }

    const submitBtn = document.getElementById('import-db-submit');
    const progressGroup = document.getElementById('import-progress-group');
    const progressFill = document.getElementById('import-progress-fill');
    const progressText = document.getElementById('import-progress-text');

    submitBtn.disabled = true;
    submitBtn.textContent = '导入中...';
    progressGroup.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = '上传中... 0%';

    const formData = new FormData();
    formData.append('name', name);
    formData.append('file', file);

    try {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/databases/import');

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                progressFill.style.width = percent + '%';
                progressText.textContent = '上传中... ' + percent + '%';
            }
        };

        xhr.onload = () => {
            let data;
            try { data = JSON.parse(xhr.responseText); } catch (err) { data = {}; }

            if (xhr.status === 200 && data.success) {
                progressFill.style.width = '100%';
                progressText.textContent = '导入成功！';
                showToast('数据库导入成功', 'success');
                setTimeout(() => {
                    hideImportDbModal();
                    loadDatabases();
                }, 800);
            } else {
                showToast(data.message || '导入失败', 'error');
                submitBtn.disabled = false;
                submitBtn.textContent = '开始导入';
                progressText.textContent = '导入失败：' + (data.message || '');
            }
        };

        xhr.onerror = () => {
            showToast('网络错误', 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = '开始导入';
            progressText.textContent = '网络错误';
        };

        xhr.send(formData);
    } catch (error) {
        showToast('导入失败：' + error.message, 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = '开始导入';
    }
});

// 初始化
document.addEventListener('DOMContentLoaded', loadDatabases);