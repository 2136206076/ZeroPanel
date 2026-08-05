# ZeroPanel Proot 高级版更新日志

## v2.0.20

### 修复

- **修复 PHP 版本安装失败问题**
  - 不同 Debian/Ubuntu 官方源提供的 PHP 版本不同（如 Debian 12/bookworm 只有 8.2），此前面板固定列出全部版本，安装源中不存在的版本会报「E: 无法定位软件包 php8.0-fpm」
  - 新增 PHP 版本可用性探测：通过 `apt-cache policy` 检测各版本是否在当前软件源中有候选包，源中不存在的版本在面板中标记「源中不可用」并禁用安装按钮
  - 安装失败且提示「无法定位软件包 / has no installation candidate」时，自动 `apt-get update` 后重试一次
  - 探测结果缓存 30 秒，避免频繁请求拖慢 PHP 管理页加载

---

## v2.0.19

### 新增功能

- **创建网站支持填写 IPv6 地址**
  - 域名校验新增 IPv6 字面量支持（如 `::1`、`2001:db8::1`），与域名、IPv4、localhost 并列
  - 前端创建网站表单的域名提示同步更新
  - 配合 v2.0.18 的 IPv6 双栈监听，IPv6 地址可直接作为站点域名并通过 IPv6 访问
  - 已在 nginx 1.22.1 实测：`server_name 2001:db8::1` 语法通过，IPv6/IPv4 访问均返回站点内容

---

## v2.0.18

### 新增功能

- **Nginx 站点支持 IPv6 双栈监听**
  - 新建站点自动生成 `listen [::]:端口 ipv6only=on;`，与 IPv4 监听共存
  - IPv6 与 IPv4 访问同一站点均可用

---

## v2.0.17

### 新增功能

- **卸载面板支持两种方式**
  - 仅卸载面板程序：删除面板文件，保留网站、数据与相关服务（数据自动移出面板目录，可恢复）
  - 完全卸载：删除面板、数据、网站、Nginx 站点配置与快捷命令，并卸载 Nginx/MariaDB/PHP-FPM 服务及 MariaDB 数据目录（数据先自动备份）
  - 运行 `zeropanel uninstall` 或 `install.sh --uninstall` 后选择卸载方式，均可随时取消

---

## v2.0.16

### 问题修复

- **文件管理默认打开网站根目录 `/var/www`**
  - 网站根目录由 `/var/www/html` 调整为 `/var/www`，文件管理默认打开该目录，所有网站的目录直接列在 `/var/www` 下
  - 创建网站时默认根目录同步为 `/var/www/{域名}`，与文件管理默认目录一致
  - 若已按旧版在 `/var/www/html` 下建站，可在创建网站时手动指定根目录，或将旧目录迁移到 `/var/www` 下

- **安装脚本同步更新**
  - `install.sh` 的 `WWW_DIR` 由 `/var/www/html` 更新为 `/var/www`
  - 卸载时删除的网站根目录同步为 `/var/www`

---

## v2.0.15

### 问题修复

- **文件管理默认打开网站文件目录，不再显示启动目录**
  - 修复打开文件管理时默认显示面板启动目录（如 `/var/www`）的问题，现在默认进入网站文件目录 `/var/www/html`，与创建网站时生成的根目录一致
  - 支持在文件管理中逐级浏览整个文件系统

- **备份文件放安全位置，不再通过文件管理暴露**
  - 面板备份数据目录（`data/backups`）默认对文件管理隐藏，避免在文件管理中误删备份文件
  - 数据库备份恢复、SQL 导入、云更新回滚等内部功能不受影响，仍可正常读取备份

- **面板程序目录保护覆盖实际运行目录**
  - 除标准安装目录（`/var/lib/zeropanel`）外，额外保护面板实际运行目录，兼容手动解压到任意位置运行的情况，避免通过文件管理误删面板文件

---

## v2.0.14

### 新增功能

- **文件管理支持整个文件系统**
  - 文件管理不再局限于网站目录与面板数据目录，可浏览和管理根目录下任意文件
  - 建站文件（`/var/www/html` 下的网站文件）可直接在文件管理中查看、编辑、上传、删除
  - 面包屑导航根路径由旧版硬编码的 `~/www` 修正为实际文件系统根 `/`
  - 面板程序目录（`/var/lib/zeropanel`，不含 `data`）仍受保护，避免通过文件管理误删面板文件；备份、上传等数据文件不受影响

---

## v2.0.13

### 新增功能

- **云更新备份恢复（回滚）**
  - 新增 `/api/system/backups` 备份列表接口，展示云更新前自动生成的版本备份
  - 新增 `/api/system/rollback` 回滚接口，出现问题时可一键恢复到指定备份版本
  - 「账号设置」页面新增「备份恢复」区块，支持查看备份列表、刷新与回滚

### 问题修复

- **修复云更新时「备份文件为空，面板目录没有可读文件」报错**
  - 面板主目录探测增强：优先选择包含 `app.py` 或 `templates`/`static` 的真实代码目录
  - 兼容迁移期旧路径（`/var/lib/zeropanel` 与 `/var/www/zeropanel`），避免误选仅含 `data` 的空壳目录

---

## v2.0.12

### 问题修复

- **修复 PHP 扩展管理页面扩展名全部显示 undefined 的问题**
  - 后端 `/api/php/extensions` 接口返回的扩展对象新增 `name` 字段
  - 前端 `renderExtensions` 使用 `ext.name` 显示扩展名，现在能正确显示

---

## v2.0.11

### 问题修复

- **修复创建网站后文件管理无法访问网站文件的问题**
  - 将 `WEB_ROOT_BASE` 从 `/var/www` 调整为 `/var/www/html`，与 `WWW_DIR` 保持一致
  - 创建网站时生成的网站目录位于 `/var/www/html/{domain}`，文件管理器可直接访问

---

## v2.0.10

### 优化

- **快捷命令帮助信息优化**
  - 输入 `zeropanel` 或 `zeropanel help` 时，显示每个命令的详细介绍
  - 帮助信息包含命令作用说明，例如启动、停止、重启、查看状态、查看日志、卸载等

---

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
