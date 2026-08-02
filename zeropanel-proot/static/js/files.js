// ZeroPanel v2.0 - 文件管理逻辑

let currentPath = '';
let currentEditFile = '';
let selectedFiles = new Set();

const textExtensions = ['txt', 'html', 'css', 'js', 'php', 'py', 'json', 'md', 'conf', 'log', 'ini', 'yml', 'yaml', 'xml', 'sh', 'sql', 'nginx'];
const compressExtensions = ['zip', 'tar', 'gz', 'tgz', 'bz2', 'xz', 'rar', '7z'];

// 加载文件列表
async function loadFiles(path = '') {
    try {
        showLoading('加载文件列表...');
        const data = await apiRequest(`/api/files?path=${encodeURIComponent(path)}`);
        
        if (!data.success && data.message) {
            showToast(data.message, 'error');
            return;
        }
        
        currentPath = data.path;
        selectedFiles.clear();
        updateSelectionActions();
        renderBreadcrumb(data.path, data.parent);
        renderFileList(data.files);
    } catch (error) {
        showToast('加载文件列表失败', 'error');
    } finally {
        hideLoading();
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

// 判断是否为文本文件
function isTextFile(name) {
    const ext = name.split('.').pop().toLowerCase();
    return textExtensions.includes(ext);
}

// 判断是否为压缩文件
function isArchiveFile(name) {
    const ext = name.split('.').pop().toLowerCase();
    return compressExtensions.includes(ext);
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
    
    fileList.innerHTML = files.map((file, index) => {
        const fullPath = `${currentPath}/${file.name}`;
        const isDir = file.type === 'directory';
        const safeName = file.name.replace(/'/g, "\\'");
        const safePath = fullPath.replace(/'/g, "\\'");
        
        return `
        <div class="file-item ${file.type} ${selectedFiles.has(fullPath) ? 'selected' : ''}" data-path="${safePath}">
            <label class="file-checkbox-label" onclick="event.stopPropagation()">
                <input type="checkbox" class="file-checkbox" 
                    ${selectedFiles.has(fullPath) ? 'checked' : ''}
                    onchange="toggleFileSelection('${safePath}', this.checked)">
            </label>
            <div class="file-icon-wrapper" onclick="${isDir ? `navigateTo('${safePath}')` : 'void(0)'}">
                <div class="file-icon ${isDir ? 'folder' : ''}">
                    ${isDir 
                        ? '<svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="2" fill="none"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
                        : '<svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>'
                    }
                </div>
            </div>
            <div class="file-name">${file.name}</div>
            <div class="file-meta">${!isDir ? formatSize(file.size) : ''}</div>
            <div class="action-btns" style="margin-top: 8px;" onclick="event.stopPropagation()">
                ${!isDir && isTextFile(file.name) ? `
                    <button class="action-btn" onclick="editFile('${safePath}')">
                        <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                ` : ''}
                ${!isDir && isArchiveFile(file.name) ? `
                    <button class="action-btn" onclick="extractFile('${safePath}')">
                        <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                    </button>
                ` : ''}
                ${!isDir ? `
                    <button class="action-btn" onclick="downloadFile('${safePath}')">
                        <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                    </button>
                ` : ''}
                <button class="action-btn" onclick="showRenameModal('${safePath}', '${safeName}')">
                    <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
                    </svg>
                </button>
                <button class="action-btn danger" onclick="deleteFile('${safePath}')">
                    <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        </div>
    `}).join('');
}

// 切换文件选择
function toggleFileSelection(path, checked) {
    if (checked) {
        selectedFiles.add(path);
    } else {
        selectedFiles.delete(path);
    }
    updateSelectionActions();
    renderFileListHighlight();
}

// 更新列表选中高亮
function renderFileListHighlight() {
    document.querySelectorAll('.file-item').forEach(item => {
        const path = item.dataset.path;
        item.classList.toggle('selected', selectedFiles.has(path));
    });
}

// 更新选择相关按钮状态
function updateSelectionActions() {
    const extractBtn = document.getElementById('extract-btn');
    const compressBtn = document.getElementById('compress-btn');
    const hasSelection = selectedFiles.size > 0;
    
    if (extractBtn) extractBtn.disabled = !hasSelection;
    if (compressBtn) compressBtn.disabled = !hasSelection;
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
        showLoading('创建目录...');
        const data = await apiRequest('/api/files/mkdir', {
            method: 'POST',
            body: JSON.stringify({ path: currentPath, name })
        });
        
        if (data.success) {
            showToast('目录创建成功', 'success');
            hideMkdirModal();
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
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
    
    showLoading('上传文件中...');
    
    try {
        const data = await apiRequest('/api/files/upload', {
            method: 'POST',
            body: formData
        });
        
        if (data.success) {
            showToast('上传成功', 'success');
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
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
        showLoading('重命名中...');
        const data = await apiRequest('/api/files/rename', {
            method: 'POST',
            body: JSON.stringify({ old_path: currentEditFile, new_name: newName })
        });
        
        if (data.success) {
            showToast('重命名成功', 'success');
            hideRenameModal();
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
});

// 删除文件
async function deleteFile(path) {
    if (!confirm('确定要删除吗？')) return;
    
    try {
        showLoading('删除中...');
        const data = await apiRequest('/api/files/delete', {
            method: 'POST',
            body: JSON.stringify({ path })
        });
        
        if (data.success) {
            showToast('删除成功', 'success');
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
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
        showLoading('读取文件...');
        const data = await apiRequest(`/api/files/read?path=${encodeURIComponent(path)}`);
        
        if (data.success) {
            document.getElementById('edit-file-name').textContent = path.split('/').pop();
            document.getElementById('file-content').value = data.content;
            document.getElementById('edit-modal').classList.add('show');
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
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
        showLoading('保存文件...');
        const data = await apiRequest('/api/files/write', {
            method: 'POST',
            body: JSON.stringify({ path: currentEditFile, content })
        });
        
        if (data.success) {
            showToast('保存成功', 'success');
            hideEditModal();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 解压选中的压缩文件
async function extractSelected() {
    const archives = Array.from(selectedFiles).filter(isArchiveFile);
    if (archives.length === 0) {
        showToast('请先选择至少一个压缩文件', 'warning');
        return;
    }
    
    try {
        showLoading('解压中...');
        const data = await apiRequest('/api/files/extract', {
            method: 'POST',
            body: JSON.stringify({ path: currentPath, files: archives })
        });
        
        if (data.success) {
            showToast('解压成功', 'success');
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 解压单个文件
async function extractFile(path) {
    try {
        showLoading('解压中...');
        const data = await apiRequest('/api/files/extract', {
            method: 'POST',
            body: JSON.stringify({ path: currentPath, files: [path] })
        });
        
        if (data.success) {
            showToast('解压成功', 'success');
            loadFiles(currentPath);
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// 显示压缩弹窗
function showCompressModal() {
    if (selectedFiles.size === 0) {
        showToast('请先选择要压缩的文件/目录', 'warning');
        return;
    }
    document.getElementById('compress-modal').classList.add('show');
    document.getElementById('compress-name').value = '';
    document.getElementById('compress-format').value = 'zip';
}

// 隐藏压缩弹窗
function hideCompressModal() {
    document.getElementById('compress-modal').classList.remove('show');
}

// 压缩文件
async function compressFiles() {
    const name = document.getElementById('compress-name').value.trim();
    const format = document.getElementById('compress-format').value;
    
    if (!name) {
        showToast('请输入压缩包名称', 'warning');
        return;
    }
    
    try {
        showLoading('压缩中...');
        const data = await apiRequest('/api/files/compress', {
            method: 'POST',
            body: JSON.stringify({
                path: currentPath,
                files: Array.from(selectedFiles),
                name,
                format
            })
        });
        
        if (data.success) {
            showToast('压缩成功', 'success');
            hideCompressModal();
            loadFiles(currentPath);
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
document.addEventListener('DOMContentLoaded', () => loadFiles(''));
