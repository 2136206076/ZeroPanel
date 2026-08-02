// ZeroPanel v2.0 - 文件管理逻辑

let currentPath = '';
let currentEditFile = '';

// 加载文件列表
async function loadFiles(path = '') {
    try {
        const response = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
        const data = await response.json();
        
        if (!data.success && data.message) {
            showToast(data.message, 'error');
            return;
        }
        
        currentPath = data.path;
        renderBreadcrumb(data.path, data.parent);
        renderFileList(data.files);
    } catch (error) {
        showToast('加载文件列表失败', 'error');
    }
}

// 渲染面包屑导航
function renderBreadcrumb(path, parent) {
    const breadcrumb = document.getElementById('breadcrumb');
    const parts = path.split('/');
    const homePath = '~/www';
    
    let html = `<a href="#" onclick="navigateTo('')">${homePath}</a>`;
    
    let accumulatedPath = '';
    for (let i = 0; i < parts.length; i++) {
        if (parts[i]) {
            accumulatedPath += '/' + parts[i];
            html += ` <span style="color: var(--text-muted)">/</span> <a href="#" onclick="navigateTo('${accumulatedPath}')">${parts[i]}</a>`;
        }
    }
    
    breadcrumb.innerHTML = html;
}

// 渲染文件列表
function renderFileList(files) {
    const fileList = document.getElementById('file-list');
    
    if (files.length === 0) {
        fileList.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" width="48" height="48" stroke="#4a4a6a" stroke-width="2" fill="none">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <p>目录为空</p>
            </div>
        `;
        return;
    }
    
    fileList.innerHTML = files.map(file => `
        <div class="file-item ${file.type}" onclick="${file.type === 'directory' ? `navigateTo('${currentPath}/${file.name}')` : ''}">
            <div class="file-icon ${file.type === 'directory' ? 'folder' : ''}">
                ${file.type === 'directory' 
                    ? '<svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="2" fill="none"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
                    : '<svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>'
                }
            </div>
            <div class="file-name">${file.name}</div>
            <div class="file-meta">${file.type === 'file' ? formatSize(file.size) : ''}</div>
            <div class="action-btns" style="margin-top: 8px;">
                ${file.type === 'file' ? `
                    <button class="action-btn" onclick="editFile('${currentPath}/${file.name}')">
                        <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="action-btn" onclick="downloadFile('${currentPath}/${file.name}')">
                        <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                    </button>
                    ${isArchiveFile(file.name) ? `
                    <button class="action-btn" onclick="showExtractModal('${currentPath}/${file.name}')">
                        <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="17 8 12 3 7 8"/>
                            <line x1="12" y1="3" x2="12" y2="15"/>
                        </svg>
                    </button>
                    ` : ''}
                ` : ''}
                <button class="action-btn" onclick="showRenameModal('${currentPath}/${file.name}', '${file.name}')">
                    <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
                    </svg>
                </button>
                <button class="action-btn" onclick="compressItem('${currentPath}/${file.name}', '${file.name}')">
                    <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="17 8 12 3 7 8"/>
                        <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                </button>
                <button class="action-btn danger" onclick="deleteFile('${currentPath}/${file.name}')">
                    <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

// 导航到指定目录
function navigateTo(path) {
    loadFiles(path);
}

// 显示新建目录弹窗
function showMkdirModal() {
    document.getElementById('mkdir-modal').classList.add('show');
    document.getElementById('dir-name').value = '';
}

// 隐藏新建目录弹窗
function hideMkdirModal() {
    document.getElementById('mkdir-modal').classList.remove('show');
}

// 创建目录
document.getElementById('mkdir-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('dir-name').value;
    
    try {
        const response = await fetch('/api/files/mkdir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: currentPath, name })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('目录创建成功', 'success');
            hideMkdirModal();
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

// 触发上传
function triggerUpload() {
    document.getElementById('file-input').click();
}

// 上传文件
async function uploadFile(input) {
    const file = input.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('path', currentPath);
    
    showToast('正在上传...', 'warning');
    
    try {
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('上传成功', 'success');
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
    
    input.value = '';
}

// 显示重命名弹窗
function showRenameModal(path, currentName) {
    currentEditFile = path;
    document.getElementById('rename-modal').classList.add('show');
    document.getElementById('new-name').value = currentName;
}

// 隐藏重命名弹窗
function hideRenameModal() {
    document.getElementById('rename-modal').classList.remove('show');
}

// 重命名文件
document.getElementById('rename-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const newName = document.getElementById('new-name').value;
    
    try {
        const response = await fetch('/api/files/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_path: currentEditFile, new_name: newName })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('重命名成功', 'success');
            hideRenameModal();
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

// 删除文件
async function deleteFile(path) {
    if (!confirm('确定要删除吗？')) return;
    
    try {
        const response = await fetch('/api/files/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('删除成功', 'success');
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 下载文件
function downloadFile(path) {
    window.location.href = `/api/files/download?path=${encodeURIComponent(path)}`;
}

// 编辑文件
async function editFile(path) {
    currentEditFile = path;
    
    try {
        const response = await fetch(`/api/files/read?path=${encodeURIComponent(path)}`);
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('edit-file-name').textContent = path.split('/').pop();
            document.getElementById('file-content').value = data.content;
            document.getElementById('edit-modal').classList.add('show');
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 隐藏编辑弹窗
function hideEditModal() {
    document.getElementById('edit-modal').classList.remove('show');
}

// 保存文件
async function saveFile() {
    const content = document.getElementById('file-content').value;
    
    try {
        const response = await fetch('/api/files/write', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: currentEditFile, content })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('保存成功', 'success');
            hideEditModal();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 判断是否为压缩文件
function isArchiveFile(filename) {
    const archives = ['.zip', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz', '.tar'];
    const lower = filename.toLowerCase();
    return archives.some(ext => lower.endsWith(ext));
}

// 显示解压弹窗
function showExtractModal(path) {
    currentEditFile = path;
    document.getElementById('extract-modal').classList.add('show');
    document.getElementById('extract-dest').value = currentPath;
}

// 隐藏解压弹窗
function hideExtractModal() {
    document.getElementById('extract-modal').classList.remove('show');
}

// 解压文件
document.getElementById('extract-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const dest = document.getElementById('extract-dest').value;

    try {
        const response = await fetch('/api/files/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: currentEditFile, dest })
        });

        const data = await response.json();
        if (data.success) {
            showToast('解压成功', 'success');
            hideExtractModal();
            loadFiles(dest || currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
});

// 压缩文件/目录
async function compressItem(path, name) {
    const dest = currentPath + '/' + name + '.zip';
    if (!confirm(`确定要压缩 ${name} 为 ${name}.zip 吗？`)) return;

    try {
        const response = await fetch('/api/files/compress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths: [path], dest, format: 'zip' })
        });

        const data = await response.json();
        if (data.success) {
            showToast('压缩成功', 'success');
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => loadFiles(''));