# ZeroPanel Proot 高级版更新日志

## v2.0.9

### 重要变更

- **面板程序目录迁移到更安全的位置**
  - Proot 高级版面板程序目录从 `/var/www/zeropanel` 迁移到 `/var/lib/zeropanel`
  - 网站目录保持 `/var/www/html` 不变
  - 文件管理器的允许范围限定为 `/var/www/html` 和 `/var/lib/zeropanel/data`
  - 避免在文件管理器中直接看到并误删面板程序文件（`app.py`、`static`、`templates` 等）

---

## v2.0.8

### 重要变更

- **独立版本体系**
  - Proot 高级版与 Termux 轻量版开始使用独立的版本号和更新日志
  - 云更新将读取 `zeropanel-proot/VERSION` 和 `zeropanel-proot/CHANGELOG.md`
  - 两个版本可以独立演进，互不影响

- **Proot 量身定制**
  - `zeropanel-proot/app.py` 移除所有 Termux 兼容分支和检测逻辑
  - 固定 Proot (Ubuntu/Debian) 路径：`/var/www/zeropanel`、`/var/www/html`、`/etc/nginx/conf.d` 等
  - `zeropanel-proot/install.sh` 现在只处理 Proot 环境，环境校验失败时明确提示应使用 Termux 版

### 新增功能

- **无 systemd 服务管理**
  - 针对 Proot 容器没有 systemd 的特点，直接使用原生守护进程启动服务
  - MariaDB: `mysqld_safe` 直接启动
  - Nginx: `nginx` 直接启动，`nginx -s reload` 重载配置
  - PHP-FPM: `php{ver}-fpm` 直接启动
  - 服务状态统一使用 `pgrep` 检测，不再依赖 `service` / `systemctl`

- **PHP 多版本独立 socket**
  - 每个 PHP 版本使用独立的 unix socket
  - 例如：`/run/php/php7.4-fpm.sock`、`/run/php/php8.0-fpm.sock`
  - 网站配置自动绑定对应版本的 socket

### 问题修复

- **云更新解压路径兼容**
  - 修复 `_safe_extract_update` 对 zip 包根目录前缀的识别
  - 同时支持 `zeropanel-proot/` 和 `zeropanel/` 两种根目录布局

---

## v2.0.7

### 新增功能

- **一键卸载**
  - 安装脚本新增 `--uninstall` / `uninstall` / `-u` 参数
  - 快捷命令 `zeropanel uninstall` 支持直接卸载
  - 卸载前自动备份 `data` 目录到带时间戳的备份文件夹
  - 卸载时先停止相关服务，避免残留进程

---

## v2.0.6

### 问题修复

- **Proot 版安装部署路径错误**
  - 修复安装完成后面板无法启动的问题
  - 原因：`zeropanel-proot_v2.zip` 顶层目录为 `zeropanel-proot/`，原脚本解压到 `/var/www` 后生成 `/var/www/zeropanel-proot/`，与 `PANEL_DIR=/var/www/zeropanel` 不一致
  - 修复：解压到临时目录后，将 `zeropanel-proot` 移动到 `/var/www/zeropanel`

---

## v2.0.5

### 问题修复

- **安装脚本环境检测**
  - 修复 Proot 容器内 Ubuntu/Debian 环境被识别为“未知/不支持”的问题
  - 新逻辑直接依据 `/etc/os-release` 的 `ID` 判断：Debian/Ubuntu 直接视为 Proot
  - 保留 Termux 检测（`TERMUX_VERSION`、`PREFIX`、`/data/data/com.termux`），避免误识别

---

## v2.0.4

### 问题修复

- **系统监控**
  - 修复 CPU 使用率始终显示 0% 的问题
    - 优先读取 `/proc/stat` 总 `cpu` 行
    - 若内核未提供总 cpu 行，自动累加 `cpu0`、`cpu1` 等单核数据
  - 修复磁盘使用率始终显示 100% 的问题
    - 弃用 `df -k /` 命令解析，改用跨平台更稳定的 `os.statvfs('/')`
    - 避免不同 Android/Termux/Busybox 环境下 `df` 输出格式差异导致解析错误

---

## v2.0.3

### 问题修复

- **云更新自动备份**
  - 修复自动备份压缩包为空的问题
  - 使用 `os.walk()` 重新实现目录遍历，确保所有面板代码文件正确写入 ZIP
  - 新增备份文件数量校验，备份为空时直接报错提示
  - 排除 `data`、`__pycache__`、`.git`、`.venv`、`update_backup`、`update_temp` 等目录

- **面板重启**
  - 修复云更新后点击面板重启无效的问题
  - 使用独立子进程执行两步重启：先结束旧进程释放端口，再启动新进程
  - 新增 `start_new_session=True` 保证重启进程在父进程退出后仍能存活
  - 优化日志重定向，重启过程写入 `data/panel.log`

- **版本与更新地址**
  - 版本号统一升级为 `2.0.3`
  - 修正 Proot 高级版与 Termux 普通版各自的云更新分发包地址
  - 修正 GitHub raw 内容地址格式，避免 404 错误

---

## v2.0.2

### 新增功能

- **Proot 高级版上线**
  - 支持 Proot 容器内的 Ubuntu / Debian 环境
  - 支持多 PHP 版本管理
  - 支持 PHP 扩展在线安装
  - 支持网站伪静态规则
  - 支持文件在线解压、压缩、编辑
  - 支持网站独立数据库
  - 支持定时任务（crontab）

---

## v2.0.0

### 新增功能

- **网站管理**
  - 支持创建、编辑、删除网站
  - 可指定端口号（默认 8080）
  - 支持 PHP 版本选择
  - 自动生成 Nginx 配置文件

- **数据库管理**
  - 创建、删除数据库
  - 支持设置字符集（utf8mb4/utf8/latin1）
  - 数据库备份与恢复
  - 导入 .sql 文件功能

- **文件管理**
  - 文件列表查看
  - 文件上传与下载
  - 目录创建
  - 文件删除

- **系统监控**
  - CPU 使用率显示
  - 内存使用情况
  - 磁盘空间监控
  - 系统负载显示
  - 网络流量统计

- **云更新**
  - 自动检查新版本
  - 一键更新功能
  - 自动备份当前版本
  - 更新日志展示

- **安全特性**
  - 用户登录认证
  - 密码修改功能
  - 会话管理

### 技术改进

- 使用 Flask Web 框架
- SQLite 数据库存储配置
- 响应式设计，支持移动端访问
- 现代化 UI 界面

### 兼容性

- 专为 ZeroTermux 设计
- 无需 root 权限运行
- 支持 Nginx、MariaDB、PHP-FPM 服务管理
