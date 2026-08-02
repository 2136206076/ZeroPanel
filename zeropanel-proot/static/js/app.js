// ZeroPanel v2.0 - 全局工具函数

// Toast 通知系统
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const iconSvg = type === 'success' 
        ? '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
        : type === 'error'
        ? '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
        : '<svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    
    toast.innerHTML = `
        <div class="toast-icon">${iconSvg}</div>
        <div class="toast-message">${message}</div>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 退出登录
async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        window.location.href = '/';
    } catch (error) {
        showToast('退出失败', 'error');
    }
}

// 切换侧边栏
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.toggle('collapsed');
}

// 格式化文件大小
function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 格式化网络流量
function formatNetwork(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 通用 API 请求封装
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Accept': 'application/json',
            ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
            ...options.headers
        }
    };
    
    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API request failed:', url, error);
        throw error;
    }
}

// 显示全局加载遮罩
function showLoading(message = '加载中...') {
    let loader = document.getElementById('global-loading');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'global-loading';
        loader.innerHTML = `
            <div class="loading-overlay"></div>
            <div class="loading-content">
                <svg class="spinner" viewBox="0 0 24 24" width="32" height="32" stroke="currentColor" stroke-width="2" fill="none">
                    <circle cx="12" cy="12" r="10" stroke-dasharray="50" stroke-dashoffset="20" stroke-linecap="round"/>
                </svg>
                <span class="loading-text">${message}</span>
            </div>
        `;
        document.body.appendChild(loader);
    } else {
        loader.querySelector('.loading-text').textContent = message;
        loader.classList.remove('hidden');
    }
}

// 隐藏全局加载遮罩
function hideLoading() {
    const loader = document.getElementById('global-loading');
    if (loader) {
        loader.classList.add('hidden');
    }
}

// 更新圆形进度条
function updateCircle(elementId, value) {
    const circle = document.getElementById(elementId);
    if (!circle) return;
    
    const svg = circle.querySelector('svg');
    const circleEl = svg.querySelectorAll('circle')[1];
    const valueEl = circle.querySelector('.stat-value');
    
    const radius = 45;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (value / 100) * circumference;
    
    circleEl.style.strokeDasharray = `${circumference - offset} ${circumference}`;
    valueEl.textContent = `${Math.round(value)}%`;
    
    // 根据值改变颜色
    if (value > 80) {
        circleEl.style.stroke = '#ef4444';
    } else if (value > 60) {
        circleEl.style.stroke = '#f59e0b';
    } else {
        circleEl.style.stroke = '#00d4ff';
    }
}

// 检查登录状态
async function checkAuth() {
    try {
        const response = await fetch('/api/check-auth');
        const data = await response.json();
        
        if (!data.authenticated) {
            window.location.href = '/';
            return false;
        }
        
        // 更新用户名显示
        const usernameDisplay = document.getElementById('username-display');
        if (usernameDisplay && data.user) {
            usernameDisplay.textContent = data.user.username;
        }
        
        return true;
    } catch (error) {
        window.location.href = '/';
        return false;
    }
}

// 页面加载时检查登录状态
if (!document.body.classList.contains('login-page')) {
    checkAuth();
}