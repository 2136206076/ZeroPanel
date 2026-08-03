# ZeroPanel 项目推广教程

本教程帮助你把 ZeroPanel 推广到不同社区，让更多 Termux / Proot 用户发现并使用这个项目。

---

## 一、推广前准备

### 1.1 确认项目链接

在发布任何内容前，确保以下链接可访问：

```text
GitHub 仓库：https://github.com/2136206076/ZeroPanel

Termux 一键安装：
bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel/install.sh)

Proot 一键安装：
bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel-proot/install.sh)

通用入口（自动识别环境）：
bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/install.sh)
```

### 1.2 准备素材

- **项目截图**：登录页、仪表盘、网站管理、文件管理、数据库管理、PHP 管理（Proot 版）
- **演示视频**：30 秒 ~ 2 分钟，展示一键安装和创建网站流程
- **标题**：准备一个吸引人的标题，例如：
  - "在手机上搭网站？ZeroPanel 让你在 Termux/Proot 里轻松建站"
  - "ZeroPanel：Termux / Proot 上的轻量建站面板"
  - "不用服务器，Android 手机也能跑网站——ZeroPanel 体验"

---

## 二、各平台推广模板

### 2.1 GitHub 仓库首页

仓库首页是流量入口，确保 `README.md` 完整、清晰。主要内容：

- 项目标题和一句话介绍
- 功能对比表
- 一键安装命令
- 截图/动图
- 快速上手
- 常见问题

README 已经写好，直接发布即可。

### 2.2 技术社区发帖模板

#### 适用平台

知乎、CSDN、掘金、博客园、V2EX、Linux 中国、开源中国等。

#### 帖子标题

```text
ZeroPanel：在 Android 手机上用 Termux / Proot 搭建网站的轻量面板
```

#### 帖子正文

```markdown
# ZeroPanel：手机上的轻量建站面板

大家好，我开发了一个叫 **ZeroPanel** 的开源项目，目标是在 Android 手机上提供简单、完整的建站能力。

## 它是什么？

ZeroPanel 是一款面向 ZeroTermux / Termux 和 Proot (Ubuntu/Debian) 的轻量级建站面板。

- **Termux 轻量版**：适合 Android 终端环境，轻量、快速
- **Proot 高级版**：在 Proot 容器内提供接近宝塔面板的体验，支持多 PHP 版本、伪静态、在线文件编辑、定时任务等

## 核心功能

| 功能 | Termux 版 | Proot 版 |
|---|---|---|
| 网站管理 | 支持 | 支持 |
| 数据库管理 | 支持 | 支持 |
| 文件管理 | 支持 | 支持 |
| 在线文件编辑 | - | 支持 |
| 文件在线解压/压缩 | - | 支持 |
| 多 PHP 版本管理 | - | 支持 |
| PHP 扩展在线安装 | - | 支持 |
| 网站伪静态规则 | - | 支持 |
| 网站独立数据库 | - | 支持 |
| 定时任务（crontab） | - | 支持 |
| 系统监控 | 支持 | 支持 |
| 云更新 | 支持 | 支持 |

## 一键安装

### Termux / ZeroTermux

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel/install.sh)
```

### Proot Ubuntu / Debian

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel-proot/install.sh)
```

安装完成后访问 `http://localhost:5000`，默认账号 `admin`，密码 `admin123`。

## 截图

[这里放 3-5 张截图]

## 开源地址

https://github.com/2136206076/ZeroPanel

欢迎大家 Star、Issue、PR，也欢迎把使用体验反馈给我。
```

### 2.3 视频平台脚本模板

#### 适用平台

B站、抖音、快手、YouTube Shorts 等。

#### 视频脚本

```text
【开场】
你知道吗？不需要买服务器，也不需要 root 手机，直接在 Android 上就能搭建一个真正的网站。

【展示】
今天给大家介绍一个开源项目：ZeroPanel。
它是一款运行在 Termux 和 Proot 容器里的轻量建站面板。

【操作演示】
只需要复制这一行命令，粘贴到 Termux 里运行，等待几分钟，面板就装好了。

然后打开浏览器访问 localhost:5000，登录进去。
点击“创建网站”，输入域名和端口，选择 PHP 版本，网站就创建完成了。

【总结】
项目完全开源，GitHub 地址在评论区置顶。
如果你也想在手机上折腾网站，欢迎试试 ZeroPanel。
```

### 2.4 即时通讯社群推广话术

#### 适用场景

QQ 群、微信群、Telegram 群、Discord 等。

#### 简洁版

```text
推荐一个开源项目：ZeroPanel
在 Termux / Proot 里一键搭建网站面板，支持 Nginx + MariaDB + PHP-FPM。
GitHub：https://github.com/2136206076/ZeroPanel
一键安装命令在 README 里，感兴趣的可以试试看。
```

#### 详细介绍版

```text
最近在搞一个开源面板 ZeroPanel，专门给 Android 上的 Termux / Proot 环境用的。

它能干啥？
- 创建网站、绑定端口
- 管理数据库（MariaDB）
- 文件管理、在线编辑
- Proot 版还支持多 PHP 版本、PHP 扩展安装、伪静态、定时任务

安装巨简单，复制命令跑一下就行：
Termux：bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel/install.sh)
Proot：bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel-proot/install.sh)

项目开源在 GitHub，欢迎大家提 Issue、PR、Star：
https://github.com/2136206076/ZeroPanel
```

### 2.5 应用商店 / 酷安 / 贴吧

#### 标题

```text
【开源】ZeroPanel：手机上的 Termux / Proot 建站面板
```

#### 正文

```text
推荐一个能在手机上跑网站的面板 ZeroPanel。

不需要 root，不需要服务器，只需要 Termux 或 Proot 容器。
支持 Nginx、MariaDB、PHP-FPM，Proot 版还能装多版本 PHP、伪静态、定时任务。

安装命令：
Termux：bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel/install.sh)
Proot：bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel-proot/install.sh)

GitHub：https://github.com/2136206076/ZeroPanel

[截图]
```

---

## 三、推广技巧

### 3.1 找准目标用户

优先在以下人群聚集的社区推广：

- ZeroTermux / Termux 用户
- Android 极客 / 折腾党
- 学生党想低成本建站
- Linux 爱好者
- 前端/后端开发者想在手机上测试项目

### 3.2 标题要抓眼球

好的标题能显著提升点击率：

- ✅ "手机变服务器？这款面板让我在 Termux 里搭了 3 个网站"
- ✅ "不用买云服务器，Android 手机就能跑 Nginx + PHP + MySQL"
- ✅ "ZeroPanel：Termux / Proot 上的免费建站面板，一键安装"
- ❌ "介绍一个项目"（太笼统）
- ❌ "我的开源面板"（没有吸引力）

### 3.3 内容要有真实感

- 放真实截图，不要只放文字
- 分享你的使用场景（例如：在手机上测试博客、给同学演示项目）
- 提到遇到的问题和如何解决，增加可信度

### 3.4 互动引导

在文末加上互动引导：

```text
你用过 Termux 吗？有没有在手机上搭过网站？
欢迎在评论区交流使用体验。
```

### 3.5 持续更新

每次发布新版本时，可以发更新帖：

```text
ZeroPanel v2.0.x 更新：修复了 xxx，新增了 xxx
```

---

## 四、常见问题 FAQ（用于回复评论）

**Q1：需要 root 吗？**
A：不需要。Termux 和 Proot 都不需要 root。

**Q2：能在真机上访问吗？**
A：可以。只要手机和访问设备在同一局域网，用手机的局域网 IP + 网站端口即可访问。

**Q3：支持公网访问吗？**
A：可以通过内网穿透工具（如 frp、ngrok、花生壳）实现公网访问，面板本身不提供内网穿透。

**Q4：Proot 是什么？**
A：Proot 是 Termux 里的一个工具，可以在 Android 上运行完整的 Linux 发行版（如 Ubuntu、Debian），不需要 root。

**Q5：安装失败怎么办？**
A：查看面板日志 `zeropanel log`，或到 GitHub 提 Issue，附上错误信息。

---

## 五、推广检查清单

发布前确认：

- [ ] GitHub 仓库可访问
- [ ] README.md 内容完整
- [ ] 一键安装命令可正常复制
- [ ] 已准备 3-5 张截图或 1 个演示视频
- [ ] 帖子标题吸引人
- [ ] 文末有 GitHub 链接和互动引导
- [ ] 已准备好回复常见问题的答案

---

## 六、示例完整帖子

以下是一个可以直接复制到论坛的完整示例：

```markdown
# 不用服务器，Android 手机也能跑网站：ZeroPanel 一键建站面板

## 项目介绍

ZeroPanel 是一款面向 ZeroTermux / Termux 和 Proot (Ubuntu/Debian) 的轻量级建站面板。

我之前一直想在没有电脑的时候也能测试网站，于是做了这个项目。现在只需要在 Termux 里执行一行命令，就能安装一个完整的 Web 面板，支持 Nginx + MariaDB + PHP-FPM。

## 两大版本

- **Termux 轻量版**：占用小，适合 Android 终端环境
- **Proot 高级版**：功能更全，支持多 PHP 版本、伪静态、在线文件编辑、定时任务等

## 一键安装

Termux / ZeroTermux：
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel/install.sh)
```

Proot Ubuntu / Debian：
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/2136206076/ZeroPanel/main/zeropanel-proot/install.sh)
```

安装完成后访问 `http://localhost:5000`，账号 `admin`，密码 `admin123`。

## 我用它做过什么？

- 在手机上测试个人博客
- 给同学演示 PHP 项目
- 临时搭建文件共享页面

## 开源地址

https://github.com/2136206076/ZeroPanel

觉得有用的话欢迎 Star，有问题也可以直接提 Issue。
```

---

祝你推广顺利！
