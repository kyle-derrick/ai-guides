---
title: "14.2 A01：失效的访问控制（Broken Access Control）"
type: docs
weight: 2
---

## 14.2 A01：失效的访问控制（Broken Access Control）

### 14.2.1 定义与本质

失效的访问控制（Broken Access Control）是指Web应用未能正确执行权限策略，导致用户能够超出其预期权限范围执行操作。这种缺陷覆盖了从水平越权读取他人订单、到垂直越权以普通身份调用管理员API、再到通过目录遍历读取服务器敏感文件的整条攻击面。

在2021版OWASP Top 10中，失效的访问控制从2017版的第五位跃升至第一位。这个排名变化并非偶然——OWASP基金会对超过500个 CWE（Common Weakness Enumeration）漏洞进行数据加权后，访问控制相关缺陷出现在 94% 的被测应用中，平均发生率高达 3.81%。这意味着每测试 100 个接口端点，就有将近 4 个存在某种形式的越权漏洞。

**为什么访问控制如此容易失效？** 核心原因在于它的实现复杂度远超大多数开发者的直觉预期：

1. **资源维度爆炸**：一个中等规模的SaaS应用可能有数百个API端点，每个端点面对不同角色、不同数据归属、不同业务状态都需要不同的权限判断。
2. **业务逻辑耦合**：权限规则不是简单的"能不能访问"，而是"在什么上下文下、对什么数据、能做什么操作"。一个审批流程可能要求"只有直属上级才能审批，且金额不能超过其授权额度"。
3. **默认允许的思维惯性**：很多框架和开发者采用"未明确拒绝即允许"的模式，遗漏某条规则就意味着某个接口裸奔。

```mermaid
graph TB
    subgraph 访问控制失效的根因分析
        direction TB
        
        ROOT["访问控制失效<br/>Broken Access Control"]
        
        ROOT --> ARCH["架构层面缺陷"]
        ROOT --> DEV["开发层面缺陷"]
        ROOT --> CONFIG["配置层面缺陷"]
        ROOT --> BIZ["业务逻辑缺陷"]
        
        ARCH --> A1["无集中式授权框架"]
        ARCH --> A2["前后端权限不一致"]
        ARCH --> A3["微服务间信任边界模糊"]
        
        DEV --> D1["仅客户端校验"]
        DEV --> D2["基于可预测标识符"]
        DEV --> D3["权限校验逻辑遗漏"]
        DEV --> D4["CORS配置不当"]
        
        CONFIG --> C1["默认凭据未修改"]
        CONFIG --> C2["目录列表未禁用"]
        CONFIG --> C3["HTTP方法未限制"]
        
        BIZ --> B1["多步骤流程校验不完整"]
        BIZ --> B2["状态机绕过"]
        BIZ --> B3["基于角色的规则遗漏边界条件"]
    end
```

### 14.2.2 核心概念：认证 vs 授权

很多初学者会混淆认证（Authentication）和授权（Authorization），但它们是访问控制的两个完全不同的阶段：

| 维度 | 认证（Authentication） | 授权（Authorization） |
|------|----------------------|---------------------|
| 核心问题 | 你是谁？ | 你能做什么？ |
| 执行时机 | 用户登录时 | 每次资源请求时 |
| 典型机制 | 密码、OAuth、MFA | RBAC、ABAC、ACL |
| 失效后果 | A07: 身份认证失效 | **A01: 失效的访问控制** |
| 检查频率 | 一次（登录时） | 每个请求都必须检查 |

关键区别在于：**认证只验证身份，授权才决定权限**。一个已登录的用户（认证通过）不代表他有权访问所有资源。A01 漏洞的本质是——应用知道"你是谁"，但没有正确判断"你能做什么"。

### 14.2.3 漏洞分类体系

失效的访问控制不是单一漏洞，而是一个漏洞家族。下面按攻击目标和手法进行系统分类。

#### 14.2.3.1 垂直越权（Vertical Privilege Escalation）

**定义**：低权限用户获取高权限用户的操作能力。攻击者从普通用户"升级"为管理员。

**典型场景**：

- 普通用户直接访问管理员API端点：`POST /api/admin/users/delete`
- 通过修改请求参数绕过前端角色限制：将 `role=user` 改为 `role=admin`
- 利用未鉴权的管理功能接口（开发者假设"不会有人知道这个URL"）

**实战案例**：

```http
# 正常请求 - 普通用户查看自己的资料
GET /api/v1/users/1001/profile
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...

# 攻击请求 - 普通用户尝试调用管理员接口
POST /api/v1/admin/users/1002/delete
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
Content-Type: application/json

{"confirm": true}
```

如果后端仅在前端页面隐藏了"删除用户"按钮，而未在 `/api/v1/admin/users/delete` 接口校验调用者的角色，攻击者通过抓包或直接构造请求即可触发该接口。

**更隐蔽的垂直越权方式**：

```http
# 方法一：HTTP方法绕过
# 后端对 GET 请求做了权限校验，但对 PUT/DELETE 未校验
GET /api/admin/config  → 403 Forbidden
PUT /api/admin/config  → 200 OK  ← 漏洞！

# 方法二：API版本绕过
GET /v2/admin/config   → 403 Forbidden
GET /v1/admin/config   → 200 OK  ← 旧版本未修复！

# 方法三：参数污染
GET /api/admin/config?role=admin   → 200 OK
# 某些框架会将URL参数直接覆盖服务端的权限判断
```

#### 14.2.3.2 水平越权（Horizontal Privilege Escalation）

**定义**：相同权限的用户A访问到用户B的数据。攻击者没有提升权限，但突破了数据隔离边界。

**典型场景**：

- 修改URL中的用户ID查看他人订单：`/orders?user_id=1002`
- 替换API请求中的资源标识符获取他人数据
- 通过遍历订单号、工单号等顺序编号获取全量数据

**实战案例**：

```http
# 用户 A（ID=1001）正常查看自己的订单
GET /api/orders/ORD-20240001
Authorization: Bearer <user_A_token>
Response: {"order_id": "ORD-20240001", "user_id": 1001, "amount": 299.00}

# 用户 A 修改订单号，查看用户 B 的订单
GET /api/orders/ORD-20240002
Authorization: Bearer <user_A_token>
Response: {"order_id": "ORD-20240002", "user_id": 1002, "amount": 1599.00}
# ↑ 如果返回了数据，说明存在水平越权漏洞
```

**水平越权的危害链**：

```mermaid
graph LR
    A["水平越权读取"] --> B["获取他人敏感信息"]
    B --> C["身份冒充/社工攻击"]
    
    D["水平越权写入"] --> E["修改他人数据"]
    E --> F["篡改订单/余额/个人信息"]
    
    G["水平越权删除"] --> H["删除他人资源"]
    H --> I["业务中断/数据丢失"]
    
    style A fill:#ffcdd2
    style D fill:#ffcdd2
    style G fill:#ffcdd2
```

#### 14.2.3.3 IDOR（不安全的直接对象引用）

IDOR是水平越权的一个子类，但它有独特的技术特征，值得单独讨论。

**定义**：应用使用用户可控的、可预测的标识符（数据库主键、自增ID、文件名等）直接引用资源，且未在服务端校验请求者对该资源的所有权。

**为什么IDOR特别常见？** 因为它是最"自然"的编程方式：

```python
# 大多数教程和框架示例都是这样写的
@app.route('/api/files/<int:file_id>')
def get_file(file_id):
    file = File.query.get(file_id)  # 直接用ID查数据库
    return jsonify(file.to_dict())  # 直接返回，不校验归属！
```

这段代码在功能上完全正确，但安全上存在IDOR漏洞——任何已登录用户只需遍历 `file_id` 就能下载所有文件。

**IDOR的三种表现形态**：

| 形态 | 示例 | 危害 |
|------|------|------|
| URL路径中的ID | `/api/users/12345` | 读取/修改他人账户信息 |
| 请求体中的ID | `{"target_user": 12345}` | 以他人名义执行操作 |
| Cookie/Session中的ID | `user_id=12345` | 伪造身份 |

**UUID是否能防住IDOR？** 使用UUID（如 `550e8400-e29b-41d4-a716-446655440000`）替代自增ID可以增加猜测难度，但**不能替代权限校验**。如果应用通过其他途径泄露了UUID（如Referer头、日志、前端HTML），攻击者仍然可以利用。UUID只是让枚举变难了，不是让越权消失了。

#### 14.2.3.4 目录遍历（Directory Traversal）

**定义**：通过路径操纵技术访问Web根目录之外的文件系统资源。

**攻击手法**：

```bash
# 基础遍历
GET /static/../../../etc/passwd

# 编码绕过（对过滤 `../` 的防御）
GET /static/%2e%2e/%2e%2e/%2e%2e/etc/passwd
GET /static/..%2f..%2f..%2fetc/passwd
GET /static/....//....//....//etc/passwd    # 双写绕过

# 空字节截断（针对PHP等语言的历史漏洞）
GET /static/../../../etc/passwd%00.jpg

# 绝对路径（如果允许的话）
GET /static?file=/etc/passwd
```

**经典CVE案例——CVE-2021-41773（Apache HTTP Server 2.4.49）**：

Apache 2.4.49 引入了一个路径规范化修复，但由于编码处理缺陷，攻击者可以通过 `%2e` 编码绕过路径遍历保护，读取任意文件：

```bash
curl "http://target/cgi-bin/.%2e/.%2e/.%2e/.%2e/etc/passwd"
# 返回 /etc/passwd 的内容
```

该漏洞影响了全球数十万台Apache服务器，被评为CVSS 7.5（高危），并在漏洞披露后48小时内就出现了大规模利用。

#### 14.2.3.5 方法论级绕过（HTTP Method & Verb Tampering）

**定义**：应用对某些HTTP方法实施了权限校验，但对其他方法未校验。

```http
# 开发者只对GET做了权限检查
GET /api/admin/settings → 403 Forbidden  ✓ 已校验

# 但未对POST/PUT/DELETE/PATCH做校验
POST /api/admin/settings → 200 OK  ← 漏洞！
PUT /api/admin/settings  → 200 OK  ← 漏洞！
DELETE /api/admin/settings → 200 OK  ← 漏洞！
```

#### 14.2.3.6 功能级别访问控制缺失

**定义**：应用在功能菜单层面做了权限控制（前端隐藏按钮），但在API层面未做对应的访问控制。

这是最"经典"的A01漏洞模式。前端通过 `v-if="user.role === 'admin'"` 隐藏了管理按钮，但后端API本身不校验角色。攻击者通过浏览器开发者工具、Burp Suite 或直接 curl 就能调用这些"隐藏"的接口。

#### 14.2.3.7 CORS配置不当导致的越权

**定义**：过于宽松的CORS策略允许恶意网站利用用户的浏览器凭证（Cookie、Session）访问目标API。

```http
# 危险的CORS配置：回显Origin头
GET /api/user/profile HTTP/1.1
Host: vulnerable-site.com
Origin: https://evil-site.com

HTTP/1.1 200 OK
Access-Control-Allow-Origin: https://evil-site.com
Access-Control-Allow-Credentials: true
```

当 `Access-Control-Allow-Credentials: true` 与动态回显的 `Access-Control-Allow-Origin` 组合时，恶意网站可以通过JavaScript跨域读取已登录用户的所有API数据。

### 14.2.4 技术原理深度分析

访问控制失效的根本原因是**服务端未能对每次请求进行充分的授权校验**。要理解这一点，需要深入认识授权模型和常见的实现缺陷。

#### 14.2.4.1 授权模型概述

```mermaid
graph TD
    subgraph 授权模型["主流授权模型"]
        direction TB
        
        RBAC["RBAC<br/>基于角色的访问控制"]
        ABAC["ABAC<br/>基于属性的访问控制"]
        PBAC["PBAC<br/>基于策略的访问控制"]
        ACL["ACL<br/>访问控制列表"]
    end
    
    RBAC --> RBAC_DESC["用户→角色→权限<br/>适合：组织架构清晰的企业应用<br/>典型：admin/editor/viewer"]
    ABAC --> ABAC_DESC["基于用户/资源/环境属性动态判断<br/>适合：复杂细粒度场景<br/>典型：只允许工作时间内访问"]
    PBAC --> PBAC_DESC["集中式策略引擎统一管理<br/>适合：微服务架构<br/>典型：Open Policy Agent"]
    ACL --> ACL_DESC["资源上附加允许访问的主体列表<br/>适合：文件系统/共享场景<br/>典型：Google Docs的分享设置"]
    
    style RBAC fill:#c8e6c9
    style ABAC fill:#bbdefb
    style PBAC fill:#fff9c4
    style ACL fill:#ffcdd2
```

| 模型 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| RBAC | 实现简单、易于理解 | 角色爆炸问题、灵活性不足 | 中小企业应用、CMS |
| ABAC | 精细控制、支持复杂规则 | 实现复杂、性能开销大 | 金融系统、医疗系统 |
| PBAC | 统一管理、跨服务一致 | 学习曲线陡峭 | 云原生微服务 |
| ACL | 直观、用户可理解 | 规模大时管理困难 | 文件共享、协作工具 |

#### 14.2.4.2 六大典型失效模式

**模式一：仅客户端权限控制**

```javascript
// 前端代码 — 仅隐藏UI
if (user.role !== 'admin') {
    document.getElementById('admin-panel').style.display = 'none';
}
// 问题：后端API未校验角色，攻击者直接调用API即可
```

防御方式：后端必须在每个API端点独立校验权限，前端控制仅作为用户体验优化。

**模式二：基于URL路径的权限绕过**

```python
# 权限校验逻辑
def check_permission(request):
    path = request.path
    if '/admin/' in path:
        return require_admin(request)
    return True

# 绕过方式：
# GET /Admin/config     ← 大小写变换
# GET /admin%2fconfig   ← URL编码
# GET /admin./config    ← 添加无意义字符
# GET /admin/config;jsessionid=xxx ← 分号注入
```

防御方式：使用规范化的路径匹配（先解码、再标准化），使用框架提供的路由匹配而非字符串搜索。

**模式三：仅校验登录状态，未校验资源归属**

```python
@app.route('/api/documents/<doc_id>')
@login_required  # 只检查了是否登录
def get_document(doc_id):
    doc = Document.query.get(doc_id)
    return jsonify(doc.to_dict())  # 未检查doc.owner == current_user
```

防御方式：在数据访问层强制附加 `WHERE owner_id = current_user.id` 条件。

**模式四：多步骤流程中的校验遗漏**

```http
# 第一步：提交订单（校验了库存和价格）
POST /api/orders
{"product_id": 1, "quantity": 2, "price": 99.00}

# 第二步：应用优惠券（校验了优惠券有效性）
POST /api/orders/123/apply-coupon
{"coupon_id": "VIP50"}

# 第三步：确认支付（未重新校验价格和优惠券！）
POST /api/orders/123/confirm
# 攻击者可以在第二步和第三步之间修改优惠券ID，
# 或将价格从99改为1，而第三步不会重新校验
```

防御方式：每个步骤都必须重新从数据库读取并校验状态，不能信任客户端传入的中间状态。

**模式五：基于Referer/Origin的虚假安全**

```python
# 错误做法：用Referer头做权限判断
def check_access(request):
    referer = request.headers.get('Referer', '')
    if 'trusted-site.com' in referer:
        return True  # Referer头可以被客户端伪造！
    return False
```

防御方式：Referer/Origin头由客户端发送，可以被修改或删除，永远不能作为安全判断的依据。

**模式六：JWT Token中存储权限但未校验签名**

```python
# 从JWT中读取role字段但未验证签名
token = request.headers['Authorization'].split(' ')[1]
payload = jwt.decode(token, options={"verify_signature": False})
if payload['role'] == 'admin':
    grant_access()  # 攻击者可以自己构造JWT！
```

防御方式：始终使用服务端密钥验证JWT签名，权限信息应从数据库/会话中读取而非信任Token中的声明。

### 14.2.5 真实世界案例

#### 案例一：GitHub Enterprise Server 越权漏洞（CVE-2024-4985）

2024年5月，GitHub披露了Enterprise Server的一个严重越权漏洞。攻击者可以通过操纵SAML认证响应中的属性，以任意用户身份访问GitHub Enterprise Server实例。该漏洞CVSS评分 10.0（满分），影响了所有开启了SAML认证的GitHub Enterprise Server实例。

**根因分析**：SAML断言中用户属性的解析逻辑存在缺陷，攻击者可以通过注入XML特制内容，伪造用户身份。授权系统信任了被篡改的SAML断言，未做独立的二次验证。

#### 案例二：Parler 数据泄露（2021年1月）

社交媒体平台Parler的API存在IDOR漏洞。其帖子API使用顺序递增的整数ID：

```text
GET /api/v1/posts/100001
GET /api/v1/posts/100002
GET /api/v1/posts/100003
...
```

攻击者编写脚本遍历所有帖子ID，在平台关闭前的数小时内抓取了超过 99% 的公开帖子（约70TB数据），包含大量带有GPS元数据的用户上传图片。

**根因分析**：使用自增ID + 无速率限制 + 无认证校验 = 一键爬取全量数据。

#### 案例三：Facebook OAuth 越权漏洞（2018年）

安全研究员发现Facebook的OAuth流程中存在逻辑缺陷。在授权回调阶段，如果同时传入两个 `redirect_uri` 参数（一个合法、一个恶意），Facebook的验证器只检查第一个参数，但实际跳转使用的是第二个：

```text
https://www.facebook.com/v3.1/dialog/oauth?
  client_id=APP_ID&
  redirect_uri=https://legitimate-app.com/callback&
  redirect_uri=https://evil.com/steal_token
```

**根因分析**：参数验证逻辑与参数使用逻辑对同一字段的处理不一致，验证了A但使用了B。

### 14.2.6 攻击检测与渗透测试

#### 14.2.6.1 手动测试清单

以下是检测A01漏洞的系统化测试步骤：

**1. 角色矩阵测试**

创建测试矩阵，用不同角色的账号逐一访问每个API端点：

```sql
端点            | admin | editor | viewer | 匿名
GET /api/users  |  200  |  403   |  403   | 401
POST /api/users |  200  |  200?  |  403   | 401  ← editor能创建用户？
DELETE /api/... |  200  |  200?  |  200?  | 401  ← 低权限能删除？
```

**2. ID遍历测试**

```text
# 对每个接受ID参数的接口进行遍历
for id in range(1, 100):
    resp = requests.get(f'/api/orders/{id}', headers={'Authorization': f'Bearer {other_user_token}'})
    if resp.status_code == 200:
        print(f'IDOR: order {id} accessible by unauthorized user')
```

**3. HTTP方法测试**

```text
# 对每个端点尝试所有HTTP方法
methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD', 'TRACE']
for method in methods:
    resp = requests.request(method, '/api/admin/config', headers=low_priv_headers)
    if resp.status_code == 200:
        print(f'Method bypass: {method} allowed')
```

**4. 路径遍历测试**

```text
# 使用Burp Suite的Intruder模块对文件下载接口进行遍历攻击
payloads = [
    '../../../etc/passwd',
    '..%2f..%2f..%2fetc/passwd',
    '%2e%2e/%2e%2e/%2e%2e/etc/passwd',
    '....//....//....//etc/passwd',
]
```

#### 14.2.6.2 自动化检测工具

| 工具 | 类型 | 适用场景 | 特点 |
|------|------|---------|------|
| Burp Suite | 商业 | 手动+半自动 | Autorize插件自动检测越权 |
| AuthMatrix (Burp插件) | 免费 | 角色矩阵测试 | 自动化多角色对比测试 |
| OWASP ZAP | 免费 | 自动扫描 | 内置访问控制扫描规则 |
| Nuclei | 免费 | 模板化扫描 | 大量社区模板覆盖已知漏洞 |
| ffuf | 免费 | 路径/参数Fuzz | 高性能目录遍历检测 |
| Arjun | 免费 | 隐藏参数发现 | 自动发现未文档化的参数 |

**Burp Suite Autorize 插件使用流程**：

1. 配置低权限用户的Cookie/Token到Autorize
2. 用高权限账号正常浏览应用，Autorize自动截取所有请求
3. 用低权限凭据重放每个请求
4. Autorize对比两次响应，标记出低权限账号也能成功访问的端点
5. 人工验证标记结果，排除误报

### 14.2.7 防御策略与最佳实践

#### 14.2.7.1 架构层面

**1. 采用集中式授权框架**

不要在每个Controller中手写权限校验。使用中间件/拦截器/装饰器统一处理：

```python
# 好的做法：使用装饰器统一校验
@app.route('/api/admin/users')
@require_role('admin')  # 集中式权限校验
def list_users():
    return User.query.all()

# 配合数据层过滤
@app.route('/api/orders/<int:order_id>')
@login_required
def get_order(order_id):
    # 不仅校验登录，还校验数据归属
    order = Order.query.filter_by(
        id=order_id,
        user_id=current_user.id  # 强制附加归属条件
    ).first_or_404()
    return jsonify(order.to_dict())
```

**2. 遵循最小权限原则（Principle of Least Privilege）**

每个用户、服务、进程只应拥有完成其工作所必需的最小权限集合。默认拒绝所有访问，仅在明确匹配权限规则时才允许。

**3. 默认拒绝（Deny by Default）**

```python
# 错误：默认允许
def check_access(user, resource):
    if resource.is_restricted and user.role not in resource.allowed_roles:
        return False
    return True  # 未列出的资源默认允许！

# 正确：默认拒绝
def check_access(user, resource):
    permission = Permission.query.filter_by(
        user_id=user.id,
        resource_id=resource.id,
        action='read'
    ).first()
    return permission is not None  # 未明确授权的默认拒绝
```

#### 14.2.7.2 编码层面

**1. 使用不可预测的资源标识符**

```python
import uuid

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.UUID, default=uuid.uuid4, unique=True, index=True)
    # API中使用 public_id，数据库内部用自增id

@app.route('/api/orders/<uuid:public_id>')
def get_order(public_id):
    order = Order.query.filter_by(public_id=public_id).first_or_404()
    check_ownership(order)
    return jsonify(order.to_dict())
```

**2. 实施速率限制与审计日志**

```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=get_remote_address)

@app.route('/api/documents/<doc_id>')
@limiter.limit("100/minute")  # 限制请求频率，防止遍历
@login_required
def get_document(doc_id):
    doc = get_document_with_auth(doc_id, current_user)
    audit_log('document_access', user=current_user.id, resource=doc_id)
    return jsonify(doc.to_dict())
```

**3. 安全的CORS配置**

```python
from flask_cors import CORS

# 正确做法：明确指定允许的源
CORS(app, resources={
    "/api/*": {
        "origins": ["https://app.example.com"],
        "supports_credentials": True,
        "methods": ["GET", "POST"],
        "max_age": 3600
    }
})

# 绝对不要这样做：
# CORS(app, origins="*", supports_credentials=True)
```

#### 14.2.7.3 运维层面

| 措施 | 说明 | 优先级 |
|------|------|--------|
| 禁用目录列表 | Nginx: `autoindex off;` Apache: `Options -Indexes` | 高 |
| 移除默认页面 | 删除Tomcat/Express等框架的默认管理页面 | 高 |
| 限制HTTP方法 | 只允许业务需要的方法（如只允许GET/POST） | 中 |
| WAF规则配置 | 部署路径遍历、越权访问的检测规则 | 中 |
| API网关统一鉴权 | 在网关层（Kong/Nginx）统一注入权限校验 | 高 |
| 日志监控告警 | 对异常访问模式（同一用户短时间访问大量不同ID）触发告警 | 高 |

### 14.2.8 与其他OWASP类别的关联

A01不是孤立存在的，它与其他漏洞类别存在复杂的交叉关系：

```mermaid
graph LR
    A01["A01 失效的访问控制"]
    A02["A02 加密机制失效"]
    A03["A03 注入"]
    A04["A04 不安全设计"]
    A05["A05 安全配置错误"]
    A07["A07 身份认证失效"]
    A10["A10 SSRF"]
    
    A07 -->|"认证是授权的前提"| A01
    A01 -->|"SQL注入绕过权限查询"| A03
    A03 -->|"注入伪造权限数据"| A01
    A05 -->|"错误配置导致权限绕过"| A01
    A01 -->|"越权读取敏感数据"| A02
    A04 -->|"设计阶段未考虑权限模型"| A01
    A01 -->|"越权触发内部请求"| A10
    
    style A01 fill:#ffcdd2
```

- **A07→A01**：如果认证被攻破（如Session劫持），攻击者获得了合法身份，此时即使授权逻辑正确，也可能因为以"合法用户"身份执行了不该执行的操作而产生越权。
- **A01↔A03**：SQL注入可以绕过权限查询（如 `WHERE user_id=1 OR 1=1`），直接返回未授权数据。
- **A05→A01**：Nginx配置 `autoindex on` 不需要任何认证就能列出所有文件，这既是配置错误也是访问控制缺失。

### 14.2.9 进阶话题：零信任架构与访问控制

传统的访问控制基于"内网可信"的假设——一旦通过了网络边界（VPN、防火墙），内部服务之间的调用默认信任。零信任架构（Zero Trust Architecture）彻底否定了这一假设。

**零信任的三大原则**：

1. **永不信任，始终验证（Never Trust, Always Verify）**：每个请求都必须经过认证和授权，无论它来自内网还是外网。
2. **最小权限访问（Least Privilege Access）**：仅授予完成当前操作所需的最小权限，且权限有时效性。
3. **持续验证（Continuous Verification）**：不是登录时验证一次就结束，而是在整个会话过程中持续评估风险。

**零信任在技术层面的落地**：

```mermaid
graph TB
    subgraph 零信任访问控制架构
        direction TB
        
        CLIENT["客户端请求"]
        
        CLIENT --> IDENTITY["身份验证层<br/>mTLS + JWT + MFA"]
        IDENTITY --> POLICY["策略决策点<br/>OPA / Casbin / Cedar"]
        POLICY --> CONTEXT["上下文评估"]
        
        CONTEXT --> C1["设备状态"]
        CONTEXT --> C2["地理位置"]
        CONTEXT --> C3["行为分析"]
        CONTEXT --> C4["时间策略"]
        
        POLICY -->|允许| SERVICE["目标服务"]
        POLICY -->|拒绝| DENY["拒绝并记录"]
    end
```

在零信任模型下，即使攻击者获取了有效的JWT Token，如果其请求来自异常地理位置、异常设备或异常时间段，策略引擎仍然可以拒绝访问。这比传统RBAC的"有Token就放行"强得多。

### 14.2.10 常见误区与纠正

| 误区 | 真相 |
|------|------|
| "前端隐藏按钮就够了" | 前端控制可被绕过，后端必须独立校验 |
| "用了UUID就不会有IDOR" | UUID增加枚举难度但不替代权限校验 |
| "内网API不需要鉴权" | 内网不代表安全，零信任是趋势 |
| "RESTful框架自动处理了权限" | 框架提供的是路由机制，权限逻辑需自行实现 |
| "JWT中的role字段可信" | JWT中的声明应被视为用户输入，需从数据库二次验证 |
| "OAuth能防越权" | OAuth只解决认证和令牌颁发，授权逻辑仍需自行实现 |
| "WAF能防住所有越权" | WAF主要防已知攻击模式，逻辑越权需要业务层面的校验 |
| "权限校验太影响性能" | 数据库查询只需毫秒级，远低于一次安全事件的损失 |

### 14.2.11 本节小结

失效的访问控制是OWASP Top 10中排名第一的漏洞类别，其核心问题在于应用未能在服务端对每个请求进行充分的授权校验。从垂直越权到水平越权、从IDOR到目录遍历，这些漏洞的技术形态各异，但根因相同——**信任了不该信任的东西**（客户端输入、可预测标识符、HTTP头、中间状态）。

防御的核心原则是：

1. **服务端强制校验**：所有权限判断必须在服务端完成，前端控制仅用于用户体验
2. **默认拒绝**：未明确授权的操作一律拒绝
3. **每次请求都校验**：不能只在登录时校验一次，也不能只校验部分端点
4. **数据归属校验**：不仅校验"能不能访问这个接口"，还要校验"能不能访问这条数据"
5. **集中式管理**：使用统一的授权框架，避免在各处散落校验逻辑
