---
title: "核心技巧"
type: docs
---
# 系统安全：核心技巧

理论基础告诉我们"什么是安全威胁"，本节解决"如何在日常开发中落地安全"。以下内容围绕三大主题展开：**安全编码实践**（从源头减少漏洞）、**安全配置**（消除部署层面的攻击面）、**代码审计**（在发布前发现隐藏缺陷）。每个主题都包含可直接落地的检查清单和工具链。

---

## 一、安全编码实践

### 1.1 输入验证：一切攻击的起点

OWASP统计显示，超过50%的安全漏洞与输入验证缺失直接相关。攻击者控制输入，就控制了程序行为。

**核心原则：永远不信任外部输入**

```python
# 误区：仅在前端验证
if request.form.get("age").isdigit():
    process_age(int(request.form["age"]))

# 正确：后端二次验证 + 白名单
import re
age_str = request.form.get("age", "")
if not re.fullmatch(r"[0-9]{1,3}", age_str):
    abort(400, "无效的年龄参数")
age = int(age_str)
if not (0 < age < 150):
    abort(400, "年龄超出合理范围")
```

**验证策略对比：**

| 策略 | 做法 | 适用场景 | 风险 |
|------|------|----------|------|
| 白名单 | 只允许已知合法输入 | 文件类型、格式字段、枚举值 | 低，最安全 |
| 黑名单 | 过滤已知危险字符 | 无法穷举时的辅助手段 | 高，易遗漏 |
| 类型检查 | 验证输入类型和范围 | 数值、日期、长度 | 中等 |
| 编码转换 | 输出时统一编码 | 显示型数据 | 仅防注入 |

**文件上传验证（最容易被忽略的攻击面）：**

```python
import os
import magic  # python-magic

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".png"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB

def safe_upload(file_storage):
    # 1. 扩展名检查
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不允许的文件类型: {ext}")
    
    # 2. 文件大小检查
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_SIZE:
        raise ValueError(f"文件过大: {size} bytes")
    
    # 3. MIME类型检查（不可被伪造的魔数检查）
    header = file_storage.read(512)
    file_storage.seek(0)
    mime = magic.from_buffer(header, mime=True)
    if mime not in ("image/jpeg", "image/png", "application/pdf"):
        raise ValueError(f"文件内容与扩展名不匹配: {mime}")
    
    # 4. 随机化文件名，防止路径穿越
    safe_name = f"{secrets.token_hex(16)}{ext}"
    
    # 5. 存储到Web根目录之外
    upload_dir = "/var/data/uploads/"
    file_storage.save(os.path.join(upload_dir, safe_name))
    return safe_name
```

### 1.2 参数化查询：彻底消灭SQL注入

SQL注入之所以危险，是因为它直接操作数据库。参数化查询将SQL结构与数据分离，从根本上杜绝注入。

```python
# 危险：字符串拼接（无论怎么转义都不安全）
cursor.execute(f"SELECT * FROM orders WHERE user_id = {user_id} AND status = '{status}'")

# 安全：参数化查询（所有主流DB-API都支持）
cursor.execute(
    "SELECT * FROM orders WHERE user_id = %s AND status = %s",
    (user_id, status)
)

# 安全：ORM（如SQLAlchemy）自动参数化
session.query(Order).filter(
    Order.user_id == user_id,
    Order.status == status
).all()
```

**动态查询构建的正确方式：**

```python
def search_products(category=None, min_price=None, max_price=None, sort_by="name"):
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = %s"
        params.append(category)
    if min_price is not None:
        query += " AND price >= %s"
        params.append(min_price)
    if max_price is not None:
        query += " AND price <= %s"
        params.append(max_price)
    
    # sort_by必须从白名单中选择，不能参数化
    ALLOWED_SORT = {"name", "price", "created_at"}
    if sort_by not in ALLOWED_SORT:
        sort_by = "name"
    query += f" ORDER BY {sort_by} ASC"
    
    cursor.execute(query, params)
    return cursor.fetchall()
```

### 1.3 输出编码：防御XSS的最后一道防线

无论输入验证做得多好，输出编码都是必不可少的。不同上下文需要不同的编码方式：

| 输出上下文 | 编码方式 | 示例 |
|-----------|----------|------|
| HTML正文 | HTML实体编码 | `<` → `&lt;` |
| HTML属性 | 属性编码 | `"` → `&#x22;` |
| JavaScript | JS转义 | `'` → `\x27` |
| URL参数 | URL编码 | ` ` → `%20` |
| CSS | CSS转义 | 表达式注入防护 |
| SQL | 参数化查询 | 不做字符串拼接 |

```python
# Python Jinja2 模板：自动上下文感知编码
# {{ user_input }} 自动HTML编码
# {{ user_input | safe }} 危险：跳过编码，仅在确认安全时使用

# JavaScript：DOM操作的安全写入
# 危险
element.innerHTML = userInput;
# 安全
element.textContent = userInput;  // 自动转义HTML

# 危险：eval执行用户输入
eval(userInput);
# 安全：使用JSON解析
JSON.parse(userInput);

# 危险：动态脚本URL
script.src = userInput;
# 安全：白名单域名
const ALLOWED_HOSTS = ["cdn.example.com"];
const url = new URL(userInput);
if (!ALLOWED_HOSTS.includes(url.hostname)) {
    throw new Error("非法脚本来源");
}
```

### 1.4 密码存储：绝不存储明文

```python
import bcrypt

# 存储密码（自动生成随机盐，自动处理盐的编码）
def hash_password(plain: str) -> str:
    # cost factor 12：2^12次迭代，约250ms/次（2024年标准）
    hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12))
    return hashed.decode()

# 验证密码
def verify_password(plain: str, stored: str) -> bool:
    return bcrypt.checkpw(plain.encode(), stored.encode())
```

**密码策略检查清单：**

- 长度：最少8位，推荐12位以上
- 复杂度：大小写+数字+特殊字符的组合
- 禁止常见密码：维护Top 100,000泄露密码黑名单
- 限制登录尝试：5次失败后锁定15分钟
- 密码哈希：bcrypt/scrypt/Argon2，绝不使用MD5/SHA1/SHA256
- 泄露检测：对接Have I Been Pwned API，自动检查用户密码是否已泄露

### 1.5 密钥与凭证管理

```python
# 危险：硬编码密钥
API_KEY = "sk-1234567890abcdef"  # 会进入版本控制！

# 安全：环境变量 + 配置文件（不提交到Git）
import os
API_KEY = os.environ["API_KEY"]

# 更安全：密钥管理服务（KMS/HashiCorp Vault）
from vault import VaultClient
vault = VaultClient()
secret = vault.read_secret("secret/data/api-key")
API_KEY = secret["data"]["api_key"]

# 密钥轮换策略：
# 1. 设置密钥有效期（如90天）
# 2. 自动提醒轮换（到期前14天）
# 3. 同时支持新旧两把密钥（平滑过渡）
# 4. 过期后立即吊销旧密钥
```

### 1.6 序列化安全：防止反序列化攻击

Python pickle、Java Serialized、PHP unserialize——所有二进制序列化格式都可能执行任意代码。

```python
# 危险：pickle反序列化不可信数据
import pickle
data = pickle.loads(untrusted_bytes)  # 可执行任意代码！

# 安全：使用JSON（仅序列化数据，不序列化代码）
import json
data = json.loads(trusted_json_string)

# 如果必须用pickle（如本地缓存）：
# 1. 只反序列化来自可信来源的数据
# 2. 使用RestrictedUnpickler限制可反序列化的类
class RestrictedUnpickler(pickle.Unpickler):
    SAFE_CLASSES = {"builtins": {"set", "frozenset", "dict", "list", "tuple"}}
    
    def find_class(self, module, name):
        if module in self.SAFE_CLASSES and name in self.SAFE_CLASSES[module]:
            return getattr(__import__(module), name)
        raise pickle.Unpickler(f"禁止反序列化 {module}.{name}")
```

---

## 二、安全配置

### 2.1 HTTP安全头部配置

HTTP头部是服务器告诉浏览器如何处理内容的指令。配置正确的安全头部可以显著降低攻击面。

```nginx
# Nginx 安全头部配置
server {
    # 防止MIME类型嗅探
    add_header X-Content-Type-Options "nosniff" always;
    
    # 防止点击劫持（允许同源嵌入）
    add_header X-Frame-Options "SAMEORIGIN" always;
    
    # 启用XSS过滤器（旧浏览器）
    add_header X-XSS-Protection "1; mode=block" always;
    
    # 强制HTTPS（HSTS）
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    
    # 限制Referrer信息泄露
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # 限制功能API
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(self)" always;
    
    # 内容安全策略（最关键的头部）
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';" always;
    
    # 防止缓存敏感数据
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    add_header Pragma "no-cache" always;
}
```

**CSP（Content Security Policy）深度解析：**

| 指令 | 作用 | 推荐值 |
|------|------|--------|
| `default-src` | 所有资源的默认策略 | `'self'` |
| `script-src` | JavaScript来源 | `'self'` + nonce/hash |
| `style-src` | CSS来源 | `'self'` |
| `img-src` | 图片来源 | `'self'` + CDN域名 |
| `connect-src` | AJAX/WebSocket目标 | 业务域名白名单 |
| `frame-ancestors` | 允许嵌入的来源 | `'self'` 或 `none` |
| `form-action` | 表单提交目标 | `'self'` |

### 2.2 TLS/HTTPS配置

```nginx
# Nginx TLS安全配置（2024最佳实践）
server {
    listen 443 ssl http2;
    
    # 使用TLS 1.2和1.3（禁用1.0/1.1）
    ssl_protocols TLSv1.2 TLSv1.3;
    
    # 强加密套件（仅AEAD模式）
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    
    # 启用OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;
    
    # 会话缓存
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;  # 安全：禁用session ticket
    
    # 证书配置
    ssl_certificate /etc/nginx/certs/example.com.pem;
    ssl_certificate_key /etc/nginx/certs/example.com.key;
    
    # DH参数（2048位以上）
    ssl_dhparam /etc/nginx/certs/dhparam.pem;
}
```

**HTTPS迁移检查清单：**

- 全站301重定向HTTP到HTTPS
- HSTS头设置max-age至少1年（生产环境推荐2年）
- 加入HSTS Preload List（浏览器内置白名单）
- 确保所有子域名都支持HTTPS
- 混合内容检测（HTTP资源在HTTPS页面中）
- 证书自动续期（Let's Encrypt + certbot）
- 证书透明度（CT）日志监控

### 2.3 数据库安全配置

```bash
# PostgreSQL安全配置（postgresql.conf）
# 禁用远程密码暴力破解
listen_addresses = '127.0.0.1'  # 仅监听本地

# 日志配置（记录慢查询和异常）
log_min_duration_statement = 1000  # 记录>1秒的查询
log_connections = on
log_disconnections = on
log_failed_login_attempts = on

# 连接限制
max_connections = 100

# SSL强制
ssl = on
ssl_cert_file = '/etc/postgresql/certs/server.crt'
ssl_key_file = '/etc/postgresql/certs/server.key'
```

```sql
-- PostgreSQL角色和权限（最小权限原则）
-- 创建只读角色
CREATE ROLE readonly_role;
GRANT CONNECT ON DATABASE appdb TO readonly_role;
GRANT USAGE ON SCHEMA public TO readonly_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_role;

-- 创建读写角色
CREATE ROLE readwrite_role;
GRANT CONNECT ON DATABASE appdb TO readwrite_role;
GRANT USAGE ON SCHEMA public TO readwrite_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO readwrite_role;

-- 创建应用用户（仅授予必要角色）
CREATE USER app_user WITH PASSWORD 'secure_password_here';
GRANT readwrite_role TO app_user;

-- 禁止应用用户使用DDL
-- 永远不要给应用用户CREATE/DROP/ALTER权限
```

### 2.4 Linux系统安全加固

```bash
# SSH安全配置（/etc/ssh/sshd_config）
PermitRootLogin no              # 禁止root直接登录
PasswordAuthentication no       # 仅允许密钥认证
PubkeyAuthentication yes
MaxAuthTries 3                  # 最多3次尝试
ClientAliveInterval 300         # 5分钟无活动断开
ClientAliveCountMax 2
AllowUsers deploy admin         # 仅允许特定用户登录

# 防火墙基础配置（UFW）
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 443/tcp   # HTTPS
ufw allow 80/tcp    # HTTP（重定向用）
ufw enable

# 文件权限
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh/
chmod 600 /etc/shadow
chmod 644 /etc/passwd

# 自动安全更新（Ubuntu/Debian）
apt install unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

**关键文件权限速查表：**

| 文件 | 权限 | 原因 |
|------|------|------|
| `/etc/shadow` | 600 (root:shadow) | 密码哈希，仅root可读 |
| `/etc/passwd` | 644 | 用户信息，系统需读 |
| `/etc/ssh/sshd_config` | 600 (root) | SSH配置，仅root可读 |
| `~/.ssh/` | 700 | SSH目录，仅所有者可访问 |
| `~/.ssh/id_rsa` | 600 | 私钥，仅所有者可读 |
| Web根目录 | 755 | Web服务器需读和执行 |
| 上传目录 | 733 + sticky | 防止用户删除他人文件 |

### 2.5 Docker与容器安全

```dockerfile
# 安全的Dockerfile
FROM python:3.12-slim AS builder

# 1. 使用非root用户运行
RUN groupadd -r appuser &amp;&amp; useradd -r -g appuser appuser

# 2. 安装依赖（多阶段构建减小攻击面）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. 复制应用代码
COPY --chown=appuser:appuser . /app

# 4. 切换到非root用户
USER appuser

# 5. 暴露非特权端口
EXPOSE 8080

# 6. 健康检查
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "app.py"]
```

```bash
# Docker运行安全选项
docker run \
    --read-only \                    # 只读文件系统
    --tmpfs /tmp:rw,noexec,nosuid \  # /tmp不可执行
    --cap-drop ALL \                 # 丢弃所有特权
    --cap-add NET_BIND_SERVICE \     # 仅绑定端口权限
    --security-opt no-new-privileges \ # 禁止提权
    --user 1000:1000 \              # 非root用户
    --network app-network \         # 自定义网络
    my-app:latest
```

**Docker安全检查清单：**

- 使用官方基础镜像，定期更新
- 多阶段构建减小镜像体积和攻击面
- 不在镜像中存储密钥（使用docker secrets或外部KMS）
- 启用Content Trust（Docker Content Trust）
- 限制容器资源（CPU/内存）防止DoS
- 禁用`--privileged`模式
- 使用`docker scan`或Trivy扫描镜像漏洞

### 2.6 CORS（跨域资源共享）配置

```python
# Flask CORS配置（严格模式）
from flask_cors import CORS

# 仅允许特定来源
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://app.example.com", "https://admin.example.com"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["X-Total-Count"],
        "max_age": 600,  # 预检请求缓存10分钟
        "supports_credentials": True  # 携带Cookie时必须为True
    }
})

# 危险：允许任意来源
# CORS(app, origins="*")  # 绝不要这样做！
```

---

## 三、代码审计与安全测试

### 3.1 静态应用安全测试（SAST）

SAST在不运行代码的情况下分析源码，发现潜在漏洞。适合集成到CI/CD流水线。

```bash
# Python: Bandit（最常用的Python安全扫描器）
pip install bandit
bandit -r src/ -f json -o bandit-report.json
bandit -r src/ -ll  # 仅显示中高风险

# JavaScript/TypeScript: Semgrep
pip install semgrep
semgrep --config=p/typescript src/
semgrep --config=p/owasp-top-ten src/  # OWASP Top 10规则集

# Java: SpotBugs + FindSecBugs
spotbugs -textui -effort:max -low target/classes/

# Go: Gosec
gosec -fmt=json -out=gosec-report.json ./...
```

**常见SAST发现及修复优先级：**

| 发现类型 | 严重程度 | 修复优先级 | 示例 |
|----------|----------|------------|------|
| SQL注入 | 严重 | 立即修复 | 字符串拼接SQL |
| 命令注入 | 严重 | 立即修复 | `os.system(user_input)` |
| 硬编码密钥 | 高 | 24小时内 | API_KEY = "sk-xxx" |
| 未验证的重定向 | 高 | 24小时内 | 302跳转用户可控URL |
| 路径穿越 | 高 | 24小时内 | `open(f"/data/{user_input}")` |
| 弱密码哈希 | 中 | 迭代修复 | 使用MD5/SHA1 |
| 不安全的随机数 | 中 | 迭代修复 | `random.random()`用于安全场景 |
| 过时依赖 | 中 | 迭代修复 | 含CVE的第三方库 |

### 3.2 动态应用安全测试（DAST）

DAST在运行时模拟攻击，发现运行时漏洞。适合集成到测试环境。

```bash
# OWASP ZAP（开源Web安全扫描器）
# 扫描已知URL
zap-cli quick-scan -s all -r https://staging.example.com

# 主动扫描（包含攻击性测试）
zap-cli active-scan https://staging.example.com

# Nikto（快速基础扫描）
nikto -h https://staging.example.com -o nikto-report.html

# Nuclei（基于模板的快速扫描）
nuclei -u https://staging.example.com -t cves/ -severity critical,high
```

### 3.3 依赖漏洞扫描

```bash
# Python: Safety / pip-audit
pip install pip-audit
pip-audit
pip-audit --fix  # 自动修复有补丁的漏洞

# JavaScript: npm audit
npm audit
npm audit fix

# Go: govulncheck
go install golang.org/x/vuln/cmd/govulncheck@latest
govulncheck ./...

# 通用：OWASP Dependency-Check
dependency-check --project "MyApp" --scan ./src/ --out ./report/
```

**依赖安全策略：**

- 固定版本（锁文件）：`requirements.txt` 使用 `==`，`package-lock.json` 不删除
- 定期扫描：CI/CD中集成依赖扫描，每周自动运行
- 漏洞分级响应：Critical/High在24小时内修复，Medium在一周内
- 依赖来源审查：优先使用官方包、Stars多、维护活跃的库
- 最小依赖原则：评估每个依赖的必要性，减少攻击面

### 3.4 安全编码检查清单

在代码审查（Code Review）时，逐项确认：

输入处理
□ 所有外部输入都经过验证（类型、范围、格式）
□ SQL查询使用参数化查询或ORM
□ 文件上传验证了大小、类型、内容
□ 无路径穿越风险（../ 等）

认证与授权
□ 密码使用bcrypt/scrypt/Argon2存储
□ 敏感操作需要二次验证（2FA）
□ API端点有权限检查
□ Session/JWT正确配置过期时间

密码与密钥
□ 无硬编码密钥/密码
□ 密钥通过环境变量或KMS管理
□ 证书私钥不进入版本控制

输出处理
□ HTML输出经过上下文感知编码
□ 错误信息不泄露内部实现细节
□ 日志中不记录敏感数据（密码、token、PII）

依赖与配置
□ 第三方库无已知高危漏洞
□ 默认配置已修改（如默认密码）
□ 安全头部已配置（CSP、HSTS等）
□ CORS配置限制了允许的来源

### 3.5 安全日志与审计

```python
import logging
import json
from datetime import datetime, timezone

# 安全日志配置
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)

# 不要记录敏感数据！
def log_security_event(event_type, user_id, details, success):
    """
    记录安全事件：登录、权限变更、数据访问等
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "success": success,
        "ip_address": get_client_ip(),
        "user_agent": request.headers.get("User-Agent", ""),
        # 敏感字段脱敏
        "details": mask_sensitive_fields(details),
    }
    security_logger.info(json.dumps(event))

def mask_sensitive_fields(data):
    """对敏感字段进行脱敏处理"""
    SENSITIVE_KEYS = {"password", "token", "secret", "credit_card", "ssn"}
    masked = {}
    for key, value in data.items():
        if any(s in key.lower() for s in SENSITIVE_KEYS):
            masked[key] = "***MASKED***"
        else:
            masked[key] = value
    return masked

# 使用示例
log_security_event("login_attempt", "user_123", {"method": "password"}, True)
log_security_event("permission_change", "user_123", {"target": "user_456", "role": "admin"}, True)
log_security_event("data_export", "user_123", {"table": "users", "count": 1000}, True)
```

**必须记录的安全事件：**

- 登录成功/失败（含尝试次数）
- 密码修改/重置
- 权限变更（角色授予/撤销）
- 敏感数据访问和导出
- API密钥创建/吊销
- 异常请求（400/403/404密集出现）
- 系统配置变更

**日志存储安全：**

- 日志文件权限设置为640（仅root和日志组可读）
- 日志传输加密（TLS）
- 日志保留策略：安全日志至少保留1年
- 日志完整性保护：定期计算哈希，防止篡改
- 集中日志管理：ELK Stack或Splunk，便于关联分析

---

## 四、安全开发工作流

### 4.1 安全的Git实践

```bash
# .gitignore 安全配置（必须包含）
*.pem
*.key
*.p12
*.pfx
.env
.env.*
*.sqlite
id_rsa
id_ed25519

# 使用git-secrets防止意外提交（安装：brew install git-secrets）
git secrets --install
git secrets --register-aws  # 注册AWS密钥模式
git secrets --add '-----BEGIN.*PRIVATE KEY-----'  # 自定义模式

# pre-commit hook（自动检查）
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/nightwatchcybersecurity/git-secrets
    rev: master
    hooks:
      - id: git-secrets
```

### 4.2 CI/CD安全集成

```yaml
# GitHub Actions安全扫描流水线
name: Security Scan
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: SAST - Bandit
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json
          bandit -r src/ -ll  # 中高风险失败
      
      - name: Dependency Audit
        run: |
          pip install pip-audit
          pip-audit --strict
      
      - name: Secret Detection
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
      
      - name: Container Scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'my-app:${{ github.sha }}'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'
```

### 4.3 安全事件响应流程

检测 → 遏制 → 根除 → 恢复 → 总结
 │       │       │       │       │
 │       │       │       │       └── 漏洞复盘，更新防御
 │       │       │       └── 从备份恢复，验证系统正常
 │       │       └── 定位根因，修复漏洞
 │       └── 隔离受影响系统，吊销凭证
 └── 发现异常，确认攻击范围

**响应时间要求：**

| 事件级别 | 响应时间 | 示例 |
|----------|----------|------|
| P0-致命 | 15分钟 | 数据库泄露、勒索软件 |
| P1-严重 | 1小时 | 任意代码执行、权限提升 |
| P2-重要 | 4小时 | 信息泄露、XSS存储型 |
| P3-一般 | 24小时 | 低风险配置错误 |

---

## 五、常见安全误区

| 误区 | 事实 | 正确做法 |
|------|------|----------|
| "我们的系统太小，不会被攻击" | 自动化扫描器不分大小 | 所有系统都需安全防护 |
| "防火墙能保护一切" | 防火墙无法防御应用层攻击 | 纵深防御，多层叠加 |
| "加密就能保证安全" | 加密不防SQL注入/XSS | 加密仅保护传输和存储 |
| "HTTPS = 安全" | HTTPS只保护传输通道 | 还需输入验证、权限控制 |
| "我做了转义所以安全" | 不同上下文需要不同编码 | 上下文感知输出编码 |
| "开源库一定安全" | 开源≠无漏洞，log4j事件证明 | 定期扫描+及时更新 |
| "密码策略越复杂越好" | 过于复杂的密码用户写便签 | 长度优先，支持密码管理器 |

---

## 六、安全工具速查表

| 工具 | 类型 | 语言/平台 | 用途 |
|------|------|-----------|------|
| Bandit | SAST | Python | Python代码安全扫描 |
| Semgrep | SAST | 多语言 | 通用代码模式匹配 |
| OWASP ZAP | DAST | Web | Web应用漏洞扫描 |
| Trivy | 容器扫描 | Docker/K8s | 镜像和依赖漏洞 |
| pip-audit | 依赖扫描 | Python | Python依赖CVE检查 |
| npm audit | 依赖扫描 | Node.js | npm依赖漏洞检查 |
| git-secrets | 密钥检测 | Git | 防止密钥提交到仓库 |
| TruffleHog | 密钥检测 | Git | 深度扫描Git历史中的密钥 |
| Certbot | 证书管理 | Let's Encrypt | 自动HTTPS证书 |
| ClamAV | 恶意软件 | Linux | 文件和邮件病毒扫描 |
| Lynis | 系统审计 | Linux | 系统安全配置检查 |

---

*系统安全核心技巧的本质是：在开发的每个环节都问自己"如果攻击者控制了这个输入/环境，会发生什么？"——然后用验证、编码、最小权限、纵深防御来堵住每一条路径。*
