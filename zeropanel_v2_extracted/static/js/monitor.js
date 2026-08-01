// ZeroPanel v2.0 - 系统监控逻辑

let cpuData = [];
let memoryData = [];
let monitorInterval;
const maxDataPoints = 30;

// 简单图表绘制
class SimpleChart {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.data = [];
        this.resize();
        
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
    }
    
    update(data) {
        this.data = data;
        this.draw();
    }
    
    draw() {
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;
        
        // 清空画布
        ctx.clearRect(0, 0, width, height);
        
        // 绘制网格
        ctx.strokeStyle = '#2a2a4a';
        ctx.lineWidth = 1;
        
        for (let i = 0; i <= 4; i++) {
            const y = (height / 4) * i;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }
        
        if (this.data.length < 2) return;
        
        // 绘制曲线
        const max = 100;
        const stepX = width / (maxDataPoints - 1);
        
        ctx.strokeStyle = '#00d4ff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        for (let i = 0; i < this.data.length; i++) {
            const x = i * stepX;
            const y = height - (this.data[i] / max) * height;
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        ctx.stroke();
        
        // 绘制填充区域
        ctx.fillStyle = 'rgba(0, 212, 255, 0.1)';
        ctx.beginPath();
        ctx.moveTo(0, height);
        
        for (let i = 0; i < this.data.length; i++) {
            const x = i * stepX;
            const y = height - (this.data[i] / max) * height;
            ctx.lineTo(x, y);
        }
        
        ctx.lineTo((this.data.length - 1) * stepX, height);
        ctx.closePath();
        ctx.fill();
    }
}

let cpuChart, memoryChart;

// 加载监控数据
async function loadMonitorData() {
    try {
        const response = await fetch('/api/system/stats');
        const data = await response.json();
        
        // 更新 CPU 数据
        cpuData.push(data.cpu_usage);
        if (cpuData.length > maxDataPoints) cpuData.shift();
        cpuChart.update(cpuData);
        document.getElementById('cpu-current').textContent = `${Math.round(data.cpu_usage)}%`;
        
        // 更新内存数据
        memoryData.push(data.memory_usage);
        if (memoryData.length > maxDataPoints) memoryData.shift();
        memoryChart.update(memoryData);
        document.getElementById('memory-current').textContent = `${Math.round(data.memory_usage)}%`;
        
        // 更新网络流量
        document.getElementById('network-in').textContent = formatNetwork(data.network_in);
        document.getElementById('network-out').textContent = formatNetwork(data.network_out);
        
        // 更新负载
        if (data.load_avg) {
            updateLoadBar('load-1', 'load-1-value', data.load_avg[0]);
            updateLoadBar('load-5', 'load-5-value', data.load_avg[1]);
            updateLoadBar('load-15', 'load-15-value', data.load_avg[2]);
        }
        
        // 更新时间显示
        const now = new Date();
        document.getElementById('update-info').textContent = `更新于 ${now.toLocaleTimeString()}`;
        
    } catch (error) {
        console.error('加载监控数据失败:', error);
    }
}

function updateLoadBar(barId, valueId, value) {
    const bar = document.getElementById(barId);
    const valueEl = document.getElementById(valueId);
    
    if (!bar || !valueEl) return;
    
    // 假设最大负载为 4
    const percent = Math.min((value / 4) * 100, 100);
    bar.style.width = `${percent}%`;
    valueEl.textContent = value.toFixed(2);
    
    // 根据负载改变颜色
    if (percent > 75) {
        bar.style.background = 'linear-gradient(90deg, #ef4444, #ff6b6b)';
    } else if (percent > 50) {
        bar.style.background = 'linear-gradient(90deg, #f59e0b, #ffaa00)';
    } else {
        bar.style.background = 'linear-gradient(90deg, #00d4ff, #0099cc)';
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化图表
    cpuChart = new SimpleChart(document.getElementById('cpu-chart'));
    memoryChart = new SimpleChart(document.getElementById('memory-chart'));
    
    // 加载初始数据
    loadMonitorData();
    
    // 定时刷新
    monitorInterval = setInterval(loadMonitorData, 2000);
});

// 页面离开时停止刷新
window.addEventListener('beforeunload', () => {
    if (monitorInterval) {
        clearInterval(monitorInterval);
    }
});