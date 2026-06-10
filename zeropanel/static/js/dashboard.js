// ZeroPanel v2.0 - 仪表盘逻辑

let statsInterval;

// 加载系统信息
async function loadSystemInfo() {
    try {
        const response = await fetch('/api/system/info');
        const data = await response.json();
        
        document.getElementById('hostname').textContent = data.hostname || '-';
        document.getElementById('uptime').textContent = data.uptime || '-';
        document.getElementById('os').textContent = data.os || '-';
    } catch (error) {
        console.error('加载系统信息失败:', error);
    }
}

// 加载服务状态
async function loadServiceStatus() {
    try {
        const response = await fetch('/api/system/services');
        const data = await response.json();
        
        updateServiceStatus('nginx-status', data.nginx);
        updateServiceStatus('mysql-status', data.mysql);
        updateServiceStatus('php-status', data['php-fpm']);
    } catch (error) {
        console.error('加载服务状态失败:', error);
    }
}

function updateServiceStatus(elementId, isRunning) {
    const statusEl = document.getElementById(elementId);
    if (!statusEl) return;
    
    const dot = statusEl.querySelector('.status-dot');
    const text = statusEl.querySelector('.status-text');
    
    dot.className = 'status-dot ' + (isRunning ? 'running' : 'stopped');
    text.textContent = isRunning ? '运行中' : '已停止';
}

// 加载系统状态
async function loadSystemStats() {
    try {
        const response = await fetch('/api/system/stats');
        const data = await response.json();
        
        updateCircle('cpu-circle', data.cpu_usage);
        updateCircle('memory-circle', data.memory_usage);
        updateCircle('disk-circle', data.disk_usage);
        
        // 更新负载显示
        const loadValue = document.getElementById('load-value');
        if (loadValue && data.load_avg) {
            loadValue.textContent = data.load_avg[0].toFixed(2);
        }
    } catch (error) {
        console.error('加载系统状态失败:', error);
    }
}

// 启动所有服务
async function startServices() {
    showToast('正在启动服务...', 'warning');
    
    try {
        const response = await fetch('/api/system/start-services', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast('服务启动成功', 'success');
            setTimeout(loadServiceStatus, 2000);
        } else {
            showToast('服务启动失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadSystemInfo();
    loadServiceStatus();
    loadSystemStats();
    
    // 定时刷新状态
    statsInterval = setInterval(loadSystemStats, 3000);
});

// 页面离开时停止刷新
window.addEventListener('beforeunload', () => {
    if (statsInterval) {
        clearInterval(statsInterval);
    }
});