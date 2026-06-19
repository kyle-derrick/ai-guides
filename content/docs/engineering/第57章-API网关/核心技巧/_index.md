---
title: "核心技巧"
type: docs
weight: 3
---
# 核心技巧

本节聚焦 API 网关在生产环境中最常用的六大核心技术：路径路由、JWT 鉴权、令牌桶限流、熔断降级、协议转换与请求聚合。每一项技术都从原理出发，给出可直接落地的代码实现、配置模板和踩坑经验。

---

## 一、路径路由

路由是 API 网关的第一道工序——每个进来的请求必须被正确匹配并转发到对应的后端服务。路由匹配的速度和灵活性直接决定了网关的吞吐上限和可维护性。

### 1.1 路由匹配的三种模式

| 匹配模式 | 语法示例 | 时间复杂度 | 适用场景 | 性能特征 |
|---------|---------|-----------|---------|---------|
| 精确匹配 | `/api/v1/users` | O(1) 哈希查找 | 固定路径接口 | 最快，纳秒级 |
| 前缀匹配 | `/api/v1/users/**` | O(L) Trie 查找 | RESTful 资源路由 | 快，适合绝大多数场景 |
| 正则匹配 | `/api/v\d+/users/\d+` | O(N) 回溯 | 版本兼容、迁移过渡 | 慢，CPU 密集，高并发下是瓶颈 |

**工程建议**：生产环境路由规则中精确匹配和前缀匹配应占 90% 以上。正则匹配仅用于过渡期的版本兼容路由，匹配完成后应及时清理。

### 1.2 基于路径的路由实现

```python
import re
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class RouteRule:
    """单条路由规则"""
    path_pattern: str                          # 原始路径模式，如 /api/v1/users/{id}
    service: str                               # 目标服务名
    methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    strip_prefix: str = ""                     # 转发前剥离的前缀
    add_prefix: str = ""                       # 转发前添加的前缀
    headers: Dict[str, str] = field(default_factory=dict)  # 注入的请求头
    timeout: int = 30                          # 超时时间（秒）
    retries: int = 3                           # 重试次数
    priority: int = 0                          # 优先级，数值越大越优先
    _compiled: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        # 将 /users/{id} 编译为正则 /users/([^/]+)
        regex_str = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', self.path_pattern)
        self._compiled = re.compile(f'^{regex_str}$')


class PathRouter:
    """基于路径的路由器，支持精确/前缀/正则三种匹配"""

    def __init__(self):
        self.exact_routes: Dict[str, RouteRule] = {}   # 精确匹配哈希表
        self.prefix_routes: List[RouteRule] = []        # 前缀匹配列表（按优先级排序）
        self.regex_routes: List[RouteRule] = []         # 正则匹配列表

    def add_route(self, rule: RouteRule):
        """注册路由规则，自动分类"""
        pattern = rule.path_pattern
        if pattern.endswith('/**'):
            # 前缀匹配：/api/v1/users/**
            rule.path_pattern = pattern[:-3]  # 去掉 /**
            rule.__post_init__()
            self.prefix_routes.append(rule)
            self.prefix_routes.sort(key=lambda r: -r.priority)
        elif '{' not in pattern and '*' not in pattern:
            # 精确匹配
            self.exact_routes[pattern] = rule
        else:
            # 正则匹配
            self.regex_routes.append(rule)
            self.regex_routes.sort(key=lambda r: -r.priority)

    def match(self, method: str, path: str) -> Optional[RouteRule]:
        """
        匹配请求路径，返回优先级最高的匹配规则。
        匹配顺序：精确 → 前缀 → 正则，同级别按 priority 降序。
        """
        # 1. 精确匹配（O(1)）
        rule = self.exact_routes.get(path)
        if rule and method in rule.methods:
            return rule

        # 2. 前缀匹配（O(L)）
        for rule in self.prefix_routes:
            if path.startswith(rule.path_pattern) and method in rule.methods:
                return rule

        # 3. 正则匹配（O(N)）
        for rule in self.regex_routes:
            if rule._compiled.match(path) and method in rule.methods:
                return rule

        return None

    def rewrite_path(self, rule: RouteRule, original_path: str) -> str:
        """根据规则重写请求路径"""
        path = original_path
        if rule.strip_prefix:
            path = path[len(rule.strip_prefix):]
        if rule.add_prefix:
            path = rule.add_prefix + path
        return path or '/'
```

### 1.3 基于主机头的路由（多租户）

多租户场景下，不同租户通过子域名访问同一网关，网关根据 Host 头将请求分发到对应的租户隔离服务。

```python
class HostRouter:
    """基于主机头的路由，支持精确匹配和通配符"""

    def __init__(self):
        self.exact_hosts: Dict[str, str] = {}    # 精确域名 → 服务名
        self.wildcard_hosts: Dict[str, str] = {} # 通配符域名 → 服务名

    def add_route(self, host: str, service: str):
        if host.startswith('*.'):
            self.wildcard_hosts[host[2:]] = service
        else:
            self.exact_hosts[host] = service

    def match(self, host: str) -> Optional[str]:
        # 精确匹配优先
        if host in self.exact_hosts:
            return self.exact_hosts[host]
        # 通配符匹配
        for domain, service in self.wildcard_hosts.items():
            if host.endswith('.' + domain) or host == domain:
                return service
        return None


# 使用示例
router = HostRouter()
router.add_route('api.company.com', 'main-service')           # 精确匹配
router.add_route('*.tenant.internal', 'tenant-service')        # 通配符匹配

# 请求: Host: alice.tenant.internal → 匹配 tenant-service
# 请求: Host: api.company.com       → 匹配 main-service
```

### 1.4 路由热更新与一致性保证

生产环境中路由规则需要频繁变更（新增服务、下线接口、灰度发布）。热更新的核心挑战是**避免路由表在更新过程中出现不一致状态**——部分请求用了新规则、部分用了旧规则。

**推荐方案：Copy-on-Write**

```python
import copy
import threading

class HotReloadRouter:
    """支持热更新的路由器，采用 Copy-on-Write 保证读一致性"""

    def __init__(self):
        self._current = PathRouter()
        self._lock = threading.Lock()

    def match(self, method: str, path: str):
        # 读操作无需加锁，始终读取当前快照
        return self._current.match(method, path)

    def reload(self, new_rules: list):
        """原子替换路由表"""
        with self._lock:
            new_router = PathRouter()
            for rule in new_rules:
                new_router.add_route(rule)
            self._current = new_router  # 原子赋值，读操作零感知
```

### 1.5 路由设计常见误区

| 误区 | 正确做法 | 原因 |
|------|---------|------|
| 所有路由都用正则 | 精确/前缀匹配优先，正则仅用于过渡 | 正则回溯在高并发下吃满 CPU |
| 路由规则无优先级 | 为每条规则设置 priority 字段 | 前缀重叠时需要明确优先级 |
| 路由更新直接改原表 | Copy-on-Write 原子替换 | 避免读写竞争导致 502 |
| 忽略路径末尾斜杠 | `/users` 和 `/users/` 统一处理 | 否则同一资源会产生两条路由 |
| 路由规则散落各处 | 集中管理（配置中心或 Git 仓库） | 分散配置难以审计和回滚 |

---

## 二、JWT 鉴权

JWT（JSON Web Token，RFC 7519）是 API 网关中最常用的认证机制。网关层面做 JWT 验证的好处是：后端服务无需重复实现 token 校验逻辑，且 token 的验证完全在网关本地完成（不需要回查认证服务器），延迟极低。

### 2.1 JWT 的结构与验证流程

JWT 由三部分组成：Header.Payload.Signature，用点号连接。

eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxMjM0NSwicm9sZSI6ImFkbWluIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c

网关验证 JWT 的完整流程：

```mermaid
flowchart TD
    A[客户端携带 Authorization: Bearer xxx] --> B{JWT 格式校验}
    B -->|格式错误| R401[返回 401 Unauthorized]
    B -->|格式正确| C{签名验证<br/>HMAC/RS256}
    C -->|签名无效| R401
    C -->|签名有效| D{过期时间 exp 检查}
    D -->|已过期| R401
    D -->|未过期| E{签发者 iss 校验}
    E -->|不匹配| R401
    E -->|匹配| F{受众 aud 校验<br/>可选}
    F -->|不匹配| R401
    F -->|匹配| G[提取 claims<br/>user_id, role, scope]
    G --> H[注入请求头 X-User-Id 等<br/>转发给后端服务]

    style R401 fill:#dc3545,color:#fff
    style H fill:#28a745,color:#fff
```

### 2.2 网关层 JWT 验证实现

```python
import jwt
import time
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class JWTConfig:
    """JWT 验证配置"""
    secret_key: str                              # HMAC 密钥（HS256）
    public_key: Optional[str] = None            # RSA/EC 公钥（RS256/ES256）
    algorithm: str = "HS256"                     # 签名算法
    issuer: Optional[str] = None                # 签发者校验
    audience: Optional[str] = None              # 受众校验
    clock_skew: int = 30                        # 时钟偏差容忍（秒）
    required_claims: List[str] = None           # 必须包含的 claims

    def __post_init__(self):
        if self.required_claims is None:
            self.required_claims = ["user_id", "role"]


class GatewayJWTValidator:
    """生产级 JWT 验证器"""

    def __init__(self, config: JWTConfig):
        self.config = config
        # 预编译公钥对象（RS256 场景下避免每次验证都解析）
        self._public_key_obj = None
        if config.public_key:
            from cryptography.hazmat.primitives import serialization
            self._public_key_obj = serialization.load_pem_public_key(
                config.public_key.encode()
            )

    def validate(self, token: str) -> Dict:
        """
        验证 JWT 并返回解析后的 claims。
        返回格式: {"valid": True, "claims": {...}} 或 {"valid": False, "error": "..."}
        """
        options = {
            "require_exp": True,               # 必须有 exp
            "require_iat": True,               # 必须有 iat
            "verify_exp": True,                # 验证过期
        }
        if self.config.issuer:
            options["verify_iss"] = True
        if self.config.audience:
            options["verify_aud"] = True

        try:
            key = self.config.public_key or self.config.secret_key
            payload = jwt.decode(
                token,
                key,
                algorithms=[self.config.algorithm],
                issuer=self.config.issuer,
                audience=self.config.audience,
                options=options,
                leeway=self.config.clock_skew,
            )
        except jwt.ExpiredSignatureError:
            return {"valid": False, "error": "token_expired", "status": 401}
        except jwt.InvalidSignatureError:
            return {"valid": False, "error": "invalid_signature", "status": 401}
        except jwt.InvalidIssuerError:
            return {"valid": False, "error": "invalid_issuer", "status": 401}
        except jwt.InvalidAudienceError:
            return {"valid": False, "error": "invalid_audience", "status": 401}
        except jwt.DecodeError:
            return {"valid": False, "error": "malformed_token", "status": 401}

        # 检查必要 claims
        for claim in self.config.required_claims:
            if claim not in payload:
                return {
                    "valid": False,
                    "error": f"missing_claim:{claim}",
                    "status": 401,
                }

        return {"valid": True, "claims": payload}


# ===== 使用示例 =====
config = JWTConfig(
    secret_key="your-256-bit-secret-key-here",
    algorithm="HS256",
    issuer="auth.yourcompany.com",
    required_claims=["user_id", "role", "scope"],
)
validator = GatewayJWTValidator(config)

# 验证 token
result = validator.validate("eyJhbGciOiJIUzI1NiJ9...")
if result["valid"]:
    # 将用户信息注入请求头，后端服务无需再验证 JWT
    headers = {
        "X-User-Id": str(result["claims"]["user_id"]),
        "X-User-Role": result["claims"]["role"],
        "X-User-Scope": ",".join(result["claims"].get("scope", [])),
    }
```

### 2.3 签名算法选型

| 算法 | 类型 | 密钥长度 | 验证速度 | 安全性 | 适用场景 |
|------|------|---------|---------|--------|---------|
| HS256 | 对称 | 256 bit | 极快（HMAC） | 中 | 内部系统、单体网关 |
| RS256 | 非对称 | 2048 bit RSA | 较慢（公钥验证） | 高 | 多系统共享验证 |
| ES256 | 非对称 | 256 bit ECDSA | 快 | 高 | 移动端、IoT（密钥短） |
| RS512 | 非对称 | 4096 bit RSA | 慢 | 极高 | 金融级安全要求 |

**关键决策**：
- 如果网关是唯一的 JWT 验证者，HS256 足够——密钥只需网关持有，性能最优
- 如果多个服务（网关 + 后端微服务）都需要独立验证 JWT，必须用 RS256 或 ES256——私钥由签发方持有，公钥分发给所有验证方
- 切勿使用 `none` 算法——部分 JWT 库支持无签名模式，生产环境必须显式禁止

### 2.4 JWT 的常见安全陷阱

**陷阱一：密钥硬编码在代码中**

```python
# ❌ 错误：密钥硬编码
SECRET = "my-secret-key"

# ✅ 正确：从环境变量或密钥管理服务加载
import os
SECRET = os.environ["JWT_SECRET_KEY"]
# 更好：从 Vault / AWS Secrets Manager 动态获取
```

**陷阱二：不做 token 吊销**

JWT 是无状态的，过期前无法主动失效。如果用户修改密码或账号被盗，必须有能力立即吊销 token。

```python
class JWTRevocationChecker:
    """基于 Redis 的 token 吊销检查"""

    def __init__(self, redis_client):
        self.redis = redis_client

    def revoke(self, jti: str, ttl: int = 86400):
        """吊销指定 token（jti = JWT 的唯一标识）"""
        self.redis.setex(f"revoked:{jti}", ttl, "1")

    def is_revoked(self, jti: str) -> bool:
        """检查 token 是否已被吊销"""
        return self.redis.exists(f"revoked:{jti}") > 0
```

**陷阱三：claims 中存放敏感信息**

JWT 的 payload 是 Base64 编码而非加密，任何人都可以解码查看内容。切勿在 claims 中存放密码、密钥、身份证号等敏感数据。

**陷阱四：忽略算法混淆攻击**

攻击者可能将 alg 从 RS256 篡改为 HS256，然后用公钥（公钥是公开的）伪造签名。验证时必须显式指定允许的算法列表：

```python
# ❌ 危险：让库自动检测算法
jwt.decode(token, key)

# ✅ 安全：显式指定算法
jwt.decode(token, key, algorithms=["RS256"])
```

### 2.5 JWT 刷新策略

Token 过期后客户端需要获取新 token。两种主流策略：

| 策略 | 流程 | 优点 | 缺点 |
|------|------|------|------|
| 双 Token | 短期 access_token (15min) + 长期 refresh_token (7d) | access_token 短命，泄露影响小 | refresh_token 泄露可被利用 |
| 滑动续期 | 每次请求自动续期，超过 idle 阈值才过期 | 用户无感知 | 长期不活跃的 token 也可能存活 |

推荐生产环境使用**双 Token 策略**，配合 refresh_token 的使用记录和异常检测：

```python
def refresh_access_token(refresh_token: str) -> dict:
    """刷新 access token"""
    # 1. 验证 refresh token
    result = validator.validate(refresh_token)
    if not result["valid"]:
        return {"error": "invalid_refresh_token"}

    claims = result["claims"]

    # 2. 检查 refresh token 是否已被使用（防重放）
    jti = claims["jti"]
    if redis.exists(f"refresh_used:{jti}"):
        # 可能被盗用，吊销该用户所有 token
        revoke_all_user_tokens(claims["user_id"])
        return {"error": "refresh_token_reused"}

    # 3. 标记已使用
    redis.setex(f"refresh_used:{jti}", 86400 * 7, "1")

    # 4. 生成新的 access token
    new_access = generate_token(
        user_id=claims["user_id"],
        role=claims["role"],
        expires_in=900,  # 15分钟
    )
    return {"access_token": new_access}
```

---

## 三、令牌桶限流

限流是 API 网关保护后端服务不被过载的关键机制。令牌桶（Token Bucket）是目前最广泛使用的限流算法，在精度和灵活性之间取得了最佳平衡。

### 3.1 四种主流限流算法对比

| 算法 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| 固定窗口 | 固定时间段内计数 | 实现简单 | 窗口边界突发问题（2倍流量穿透） | 简单场景、内部 API |
| 滑动窗口 | 滑动时间窗口内计数 | 无边界问题 | 内存开销大（每请求存时间戳） | 精确计数场景 |
| **令牌桶** | 定速生成令牌，请求消耗令牌 | 允许突发、平滑限流 | 参数调优需要经验 | **通用首选** |
| 漏桶 | 固定速率处理请求队列 | 输出完全平滑 | 无法处理合理突发 | 对外开放 API |

**为什么令牌桶是首选**：它允许短时间内处理突发流量（桶中有积累的令牌），同时维持长期的平均速率限制。这最符合真实 API 流量特征——用户操作通常是突发性的（打开页面时并发请求多个接口），而非均匀分布。

### 3.2 令牌桶算法原理

```mermaid
flowchart LR
    subgraph 令牌桶
        B[桶容量 C<br/>最大令牌数]
        T[令牌生成器<br/>速率 R 个/秒]
        Q[当前令牌数]
    end
    
    REQ[新请求] --> CHECK{令牌数 > 0?}
    CHECK -->|是| CONSUME[消耗 1 个令牌<br/>放行请求]
    CHECK -->|否| REJECT[拒绝请求<br/>返回 429]
    
    T -->|每秒注入 R 个| Q
    Q --> CHECK

    style REJECT fill:#dc3545,color:#fff
    style CONSUME fill:#28a745,color:#fff
```

关键参数：
- **桶容量（Capacity / Burst）**：允许的最大突发量。设为 100 表示允许瞬间处理 100 个请求
- **生成速率（Rate）**：每秒匀速放入桶中的令牌数。设为 50 表示长期平均 50 QPS

### 3.3 单机令牌桶实现

```python
import time
import threading


class TokenBucket:
    """线程安全的令牌桶"""

    def __init__(self, capacity: int, rate: float):
        """
        Args:
            capacity: 桶容量（最大令牌数，即允许的突发量）
            rate: 令牌生成速率（个/秒）
        """
        self.capacity = capacity
        self.rate = rate
        self.tokens = capacity          # 初始满桶
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """
        尝试消耗令牌。
        Returns: True 表示放行，False 表示拒绝。
        """
        with self._lock:
            now = time.monotonic()
            # 补充令牌
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate,
            )
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    @property
    def remaining(self) -> int:
        return int(self.tokens)


class SlidingWindowLimiter:
    """滑动窗口限流器（精确但内存开销大）"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list = []  # 存储每个请求的时间戳
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = time.time()
        with self._lock:
            # 清除窗口外的过期记录
            cutoff = now - self.window_seconds
            self.requests = [t for t in self.requests if t > cutoff]
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False
```

### 3.4 分布式令牌桶（Redis 实现）

单机限流在多实例部署时无法保证全局一致。分布式限流通常借助 Redis 的原子操作来实现。

```lua
-- Redis Lua 脚本：分布式令牌桶（原子操作）
-- KEYS[1] = 令牌桶的 key，如 "ratelimit:api_v1_users"
-- ARGV[1] = 桶容量 capacity
-- ARGV[2] = 生成速率 rate（令牌/秒）
-- ARGV[3] = 当前时间戳（秒，浮点数）
-- ARGV[4] = 本次消耗的令牌数

local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

-- 获取当前桶状态
local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

-- 首次访问，初始化满桶
if tokens == nil then
    tokens = capacity
    last_refill = now
end

-- 计算并补充令牌
local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * rate)

-- 尝试消费
local allowed = 0
if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
end

-- 写回桶状态，设置 TTL 防止内存泄漏（2倍窗口时间）
redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2 + 10)

-- 返回：是否允许 + 剩余令牌 + 重填时间
return {allowed, math.floor(tokens), 0}
```

对应的 Python 调用代码：

```python
import time
import redis

class DistributedRateLimiter:
    """基于 Redis 的分布式令牌桶限流器"""

    LUA_SCRIPT = """
    -- (上面的 Lua 脚本内容)
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._script = self.redis.register_script(self.LUA_SCRIPT)

    def is_allowed(
        self,
        key: str,
        capacity: int,
        rate: float,
        tokens: int = 1,
    ) -> dict:
        """
        检查请求是否被允许。

        Args:
            key: 限流维度的唯一标识，如 "ratelimit:user:12345"
            capacity: 桶容量
            rate: 令牌生成速率（个/秒）
            tokens: 本次消耗的令牌数

        Returns:
            {"allowed": True/False, "remaining": int, "retry_after": float}
        """
        result = self._script(
            keys=[key],
            args=[capacity, rate, time.time(), tokens],
        )
        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after = 0.0 if allowed else (1.0 / rate)

        return {
            "allowed": allowed,
            "remaining": remaining,
            "retry_after": retry_after,
        }
```

### 3.5 分层限流策略

生产环境中单一维度的限流远远不够，需要在三个层次分别设置限流：

```mermaid
flowchart TD
    REQ[客户端请求] --> G[全局限流<br/>保护整体基础设施<br/>例: 10000 QPS]
    G -->|通过| R[路由级限流<br/>保护特定服务<br/>例: 用户接口 500 QPS]
    R -->|通过| C[消费者级限流<br/>防止单一调用方滥用<br/>例: 每用户 60次/分钟]
    C -->|通过| PASS[放行到后端服务]
    
    G -->|拒绝| R429_G[429 + Retry-After]
    R -->|拒绝| R429_R[429 + Retry-After]
    C -->|拒绝| R429_C[429 + Retry-After]

    style R429_G fill:#dc3545,color:#fff
    style R429_R fill:#ff6b35,color:#fff
    style R429_C fill:#ffc107,color:#000
    style PASS fill:#28a745,color:#fff
```

| 限流层级 | 限流维度 | 典型配置 | 保护目标 |
|---------|---------|---------|---------|
| 全局 | 按网关实例 | 10000 QPS，桶容量 2000 | 网关自身和后端基础设施 |
| 路由级 | 按 API 路径 | 每接口 100-5000 QPS | 各微服务的处理能力 |
| 消费者级 | 按 API Key / 用户 ID | 每调用方 60 次/分钟 | 防止单一客户端滥用 |

### 3.6 限流响应头规范

符合标准的限流响应应该返回以下 Header，让客户端知道限流状态并做出合理退避：

```python
def rate_limit_response(retry_after: float, remaining: int, limit: int, reset_at: int):
    """构造标准限流响应"""
    return {
        "status": 429,
        "headers": {
            "Content-Type": "application/json",
            "Retry-After": str(int(retry_after)),        # 建议重试等待秒数
            "X-RateLimit-Limit": str(limit),              # 窗口内总配额
            "X-RateLimit-Remaining": str(remaining),      # 剩余配额
            "X-RateLimit-Reset": str(reset_at),           # 配额重置时间戳
        },
        "body": {
            "error": "rate_limit_exceeded",
            "message": f"请求过于频繁，请在 {int(retry_after)} 秒后重试",
        },
    }
```

客户端退避策略建议：

第 1 次 429 → 等待 Retry-After 秒后重试
第 2 次 429 → 等待 Retry-After × 2 秒（指数退避）
第 3 次 429 → 等待 Retry-After × 4 秒，同时上报异常
超过 3 次 429 → 停止重试，向用户展示"服务繁忙"

---

## 四、熔断降级

当后端服务出现故障或响应过慢时，熔断器可以快速失败，避免故障蔓延到整个系统。

### 4.1 熔断器状态机

```mermaid
stateDiagram-v2
    [*] --> Closed: 初始状态
    Closed --> Open: 失败次数 ≥ 阈值<br/>（如 5 次/10秒）
    Open --> HalfOpen: 冷却时间到期<br/>（如 30 秒）
    HalfOpen --> Closed: 探测请求成功
    HalfOpen --> Open: 探测请求失败
    Closed --> Closed: 请求成功<br/>（重置失败计数）
```

三种状态的行为：

| 状态 | 请求处理 | 失败计数 | 说明 |
|------|---------|---------|------|
| Closed（关闭） | 正常转发 | 持续计数 | 正常工作态，失败达到阈值则熔断 |
| Open（打开） | 直接返回 503 | 不计数 | 快速失败，保护后端不被持续冲击 |
| Half-Open（半开） | 放行少量探测请求 | 探测结果决定 | 验证后端是否恢复，成功则关闭熔断 |

### 4.2 熔断器实现

```python
import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Any


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """生产级熔断器"""
    name: str                                     # 熔断器名称（对应后端服务）
    failure_threshold: int = 5                    # 触发熔断的失败次数
    failure_window: float = 10.0                  # 失败计数窗口（秒）
    recovery_timeout: float = 30.0                # 熔断恢复等待时间（秒）
    half_open_max_calls: int = 3                  # 半开状态的探测请求数
    success_threshold: int = 2                    # 半开状态成功次数阈值

    # 运行时状态
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    failure_start: float = field(default=0, init=False)
    last_state_change: float = field(default_factory=time.monotonic, init=False)
    half_open_successes: int = field(default=0, init=False)
    half_open_calls: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def allow_request(self) -> bool:
        """判断是否允许本次请求通过"""
        with self._lock:
            now = time.monotonic()

            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # 检查是否过了冷却期
                if now - self.last_state_change >= self.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls < self.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False

            return False

    def record_success(self):
        """记录成功"""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                # 重置失败计数
                self.failure_count = 0
                self.failure_start = 0

            elif self.state == CircuitState.HALF_OPEN:
                self.half_open_successes += 1
                if self.half_open_successes >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def record_failure(self):
        """记录失败"""
        with self._lock:
            now = time.monotonic()

            if self.state == CircuitState.CLOSED:
                # 滑动窗口内的失败计数
                if now - self.failure_start > self.failure_window:
                    self.failure_count = 1
                    self.failure_start = now
                else:
                    self.failure_count += 1

                if self.failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

            elif self.state == CircuitState.HALF_OPEN:
                # 探测失败，重新熔断
                self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.monotonic()

        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.failure_start = 0
            self.half_open_successes = 0
            self.half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.half_open_successes = 0
            self.half_open_calls = 0

        # 实际项目中此处应发送指标到 Prometheus
        print(f"[CircuitBreaker:{self.name}] {old_state.value} → {new_state.value}")


# ===== 使用示例 =====
breaker = CircuitBreaker(
    name="order-service",
    failure_threshold=5,         # 10秒内5次失败触发熔断
    failure_window=10.0,
    recovery_timeout=30.0,       # 熔断30秒后尝试恢复
)

def call_order_service(request):
    if not breaker.allow_request():
        return {"status": 503, "error": "service_temporarily_unavailable"}
    try:
        result = do_rpc_call("order-service", request)
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure()
        return {"status": 502, "error": str(e)}
```

### 4.3 降级策略

熔断后不是简单返回错误，而应该返回有意义的降级响应：

| 降级策略 | 实现方式 | 适用场景 |
|---------|---------|---------|
| 返回缓存数据 | 从 Redis/本地缓存返回最近一次成功响应 | 查询类接口（商品列表、推荐） |
| 返回默认值 | 返回空数据或占位数据 | 非核心功能（评分、评论数） |
| 功能开关关闭 | 整个功能模块降级不可用 | 个性化推荐、实时库存 |
| 异步处理 | 请求入队列，稍后处理 | 下单、支付等可延迟操作 |
| 就近路由 | 切换到备用服务或本地副本 | 多活架构下的容灾切换 |

```python
class DegradationHandler:
    """降级策略管理器"""

    def __init__(self, cache_client):
        self.cache = cache_client
        self.strategies = {}

    def register(self, service: str, strategy: str, fallback: Any = None):
        self.strategies[service] = {"strategy": strategy, "fallback": fallback}

    def handle(self, service: str, request: dict) -> dict:
        config = self.strategies.get(service, {})
        strategy = config.get("strategy", "error")

        if strategy == "cache":
            cache_key = f"fallback:{service}:{request.get('path', '')}"
            cached = self.cache.get(cache_key)
            if cached:
                return {"status": 200, "data": cached, "degraded": True}
            return {"status": 503, "error": "service_unavailable"}

        if strategy == "default":
            return {"status": 200, "data": config["fallback"], "degraded": True}

        if strategy == "queue":
            self.enqueue(request)
            return {"status": 202, "message": "请求已接收，稍后处理"}

        return {"status": 503, "error": "service_unavailable"}


# 注册降级策略
handler = DegradationHandler(cache_client=redis_client)
handler.register("product-service", "cache")          # 商品查询走缓存降级
handler.register("recommend-service", "default", [])  # 推荐服务返回空列表
handler.register("notification-service", "queue")      # 通知服务异步处理
```

---

## 五、协议转换

微服务架构中不同服务可能使用不同的通信协议，API 网关需要在协议之间做无缝转换。

### 5.1 HTTP ↔ gRPC 转换

gRPC 在内部服务间通信中越来越流行（高性能、强类型），但外部客户端通常只支持 HTTP/JSON。网关负责将 HTTP/JSON 请求转换为 gRPC 调用。

```python
import json
import grpc
from google.protobuf.json_format import MessageToJson, Parse

# gRPC 服务定义（以订单服务为例）
# service OrderService {
#   rpc GetOrder (GetOrderRequest) returns (Order);
#   rpc CreateOrder (CreateOrderRequest) returns (Order);
# }

class GRPCProxy:
    """HTTP/JSON 到 gRPC 的协议转换器"""

    def __init__(self, grpc_channel: grpc.Channel):
        self.channel = grpc_channel

    async def handle_http_to_grpc(
        self,
        http_method: str,
        path: str,
        body: bytes,
        proto_request_class,     # protobuf 请求类
        grpc_method,             # gRPC 方法
    ) -> dict:
        """将 HTTP/JSON 请求转换为 gRPC 调用"""
        # 1. JSON → Protobuf
        json_data = json.loads(body) if body else {}
        proto_request = proto_request_class()
        Parse(json.dumps(json_data), proto_request)

        # 2. 调用 gRPC 服务
        try:
            stub = grpc_service_stub(self.channel)
            response = await getattr(stub, grpc_method)(proto_request)

            # 3. Protobuf → JSON
            response_json = MessageToJson(
                response,
                including_default_value_fields=True,
                preserving_proto_field_name=True,
            )
            return {
                "status": 200,
                "body": json.loads(response_json),
            }
        except grpc.RpcError as e:
            return {
                "status": self._grpc_status_to_http(e.code()),
                "body": {"error": e.details()},
            }

    @staticmethod
    def _grpc_status_to_http(grpc_status):
        mapping = {
            grpc.StatusCode.NOT_FOUND: 404,
            grpc.StatusCode.INVALID_ARGUMENT: 400,
            grpc.StatusCode.UNAUTHENTICATED: 401,
            grpc.StatusCode.PERMISSION_DENIED: 403,
            grpc.StatusCode.UNAVAILABLE: 503,
            grpc.StatusCode.DEADLINE_EXCEEDED: 504,
            grpc.StatusCode.INTERNAL: 500,
        }
        return mapping.get(grpc_status, 500)
```

### 5.2 REST ↔ GraphQL 转换

当后端提供 GraphQL 接口，而外部客户端只支持 REST 时，网关可以做 REST-to-GraphQL 的自动转换：

```python
class RESTToGraphQLProxy:
    """REST 风格请求转 GraphQL"""

    # REST 路径 → GraphQL 映射规则
    ROUTE_MAP = {
        ("GET", "/api/v1/users/{id}"): {
            "query": "query GetUser($id: ID!) { user(id: $id) { id name email } }",
            "extract_path": "data.user",
        },
        ("GET", "/api/v1/orders"): {
            "query": "query ListOrders($first: Int!) { orders(first: $first) { id status total } }",
            "extract_path": "data.orders",
        },
    }

    def __init__(self, graphql_endpoint: str):
        self.endpoint = graphql_endpoint

    async def proxy(self, method: str, path: str, query_params: dict) -> dict:
        route_key = (method, self._normalize_path(path))
        route = self.ROUTE_MAP.get(route_key)
        if not route:
            return {"status": 404, "error": "no GraphQL mapping"}

        # 提取路径变量
        variables = self._extract_variables(path, route_key[1])
        variables.update(query_params)

        # 发送 GraphQL 请求
        payload = {
            "query": route["query"],
            "variables": variables,
        }
        response = await self._call_graphql(payload)

        # 提取嵌套数据
        data = response.get("data", {})
        for key in route["extract_path"].split("."):
            data = data.get(key, {})

        return {"status": 200, "body": data}
```

### 5.3 WebSocket 代理

API 网关还需要处理 WebSocket 长连接的代理，这与 HTTP 请求的处理有本质区别——网关需要维护连接状态。

```python
# WebSocket 代理的核心逻辑（以 aiohttp 为例）
class WebSocketProxy:
    """WebSocket 连接代理"""

    async def handle_upgrade(self, request, upstream_url):
        """处理 WebSocket 升级请求"""
        # 1. 验证认证（JWT 通常在查询参数或初始帧中）
        token = request.query.get("token")
        if not token or not self.validate_ws_token(token):
            return Response(status=401)

        # 2. 建立到上游的 WebSocket 连接
        upstream_ws = await aiohttp.ClientSession().ws_connect(upstream_url)

        # 3. 双向消息转发
        async def client_to_upstream():
            async for msg in request.ws_connection:
                await upstream_ws.send_str(msg.data)

        async def upstream_to_client():
            async for msg in upstream_ws:
                await request.ws_connection.send_str(msg.data)

        await asyncio.gather(client_to_upstream(), upstream_to_client())
```

---

## 六、请求聚合（BFF 模式）

BFF（Backend For Frontend）模式让网关承担请求聚合的职责：客户端发起一次请求，网关在后端并行调用多个服务，聚合结果后返回。

### 6.1 BFF 的价值

没有 BFF 时，移动端为了渲染一个页面可能需要串行调用 5-6 个接口，总延迟 = 各接口延迟之和。有了 BFF 后：

```mermaid
sequenceDiagram
    participant M as 移动端
    participant G as API网关/BFF
    participant U as 用户服务
    participant O as 订单服务
    participant P as 商品服务
    participant R as 推荐服务

    rect rgb(255, 230, 230)
    Note over M,R: 无BFF：串行调用，总延迟 = 200+300+150+400+200 = 1250ms
    M->>U: GET /user/profile (200ms)
    U-->>M: 用户信息
    M->>O: GET /orders?user_id=1 (300ms)
    O-->>M: 订单列表
    M->>P: GET /products?ids=... (150ms)
    P-->>M: 商品详情
    end

    rect rgb(230, 255, 230)
    Note over M,R: 有BFF：并行调用，总延迟 = max(200,300,150,400,200) = 400ms
    M->>G: GET /home/summary (单次请求)
    par 并行调用
        G->>U: GET /user/profile
        G->>O: GET /orders?user_id=1
        G->>P: GET /products?ids=...
        G->>R: GET /recommendations
    end
    U-->>G: 用户信息
    O-->>G: 订单列表
    P-->>G: 商品详情
    R-->>G: 推荐列表
    G-->>M: 聚合后的完整数据
    end
```

### 6.2 请求聚合实现

```python
import asyncio
import aiohttp
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class ServiceCall:
    """单个后端服务调用定义"""
    name: str                     # 调用名称（用于结果映射）
    method: str                   # HTTP 方法
    url: str                      # 服务地址
    headers: Dict[str, str] = None
    body: Any = None
    timeout: float = 5.0          # 超时时间
    fallback: Any = None          # 降级返回值


class RequestAggregator:
    """请求聚合器"""

    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    async def aggregate(
        self,
        calls: List[ServiceCall],
        merge_strategy: str = "merge",  # merge | pick | custom
    ) -> dict:
        """
        并行调用多个后端服务，聚合结果。

        Args:
            calls: 待调用的服务列表
            merge_strategy: 结果合并策略
                - merge: 所有结果合并为一个字典
                - pick: 返回第一个成功的结果
        """
        async def _call_one(call: ServiceCall):
            try:
                timeout = aiohttp.ClientTimeout(total=call.timeout)
                async with self.session.request(
                    call.method,
                    call.url,
                    headers=call.headers or {},
                    json=call.body,
                    timeout=timeout,
                ) as resp:
                    data = await resp.json()
                    return call.name, {"ok": True, "data": data}
            except Exception as e:
                if call.fallback is not None:
                    return call.name, {"ok": True, "data": call.fallback, "degraded": True}
                return call.name, {"ok": False, "error": str(e)}

        # 并行发起所有请求
        tasks = [_call_one(c) for c in calls]
        results = await asyncio.gather(*tasks)

        if merge_strategy == "pick":
            for name, result in results:
                if result["ok"]:
                    return result["data"]
            return {"error": "all services failed"}

        # merge 策略：合并所有结果
        merged = {}
        errors = []
        for name, result in results:
            if result["ok"]:
                merged[name] = result["data"]
                if result.get("degraded"):
                    merged[f"_degraded_{name}"] = True
            else:
                errors.append({"service": name, "error": result["error"]})

        if errors:
            merged["_errors"] = errors

        return merged


# ===== 使用示例：首页聚合接口 =====
async def home_summary(user_id: str):
    async with RequestAggregator() as agg:
        return await agg.aggregate([
            ServiceCall(
                name="profile",
                method="GET",
                url=f"http://user-service/api/users/{user_id}",
                timeout=3.0,
                fallback={"name": "用户"},
            ),
            ServiceCall(
                name="recent_orders",
                method="GET",
                url=f"http://order-service/api/orders?user_id={user_id}&amp;limit=5",
                timeout=5.0,
                fallback=[],
            ),
            ServiceCall(
                name="recommendations",
                method="GET",
                url=f"http://recommend-service/api/recs?user_id={user_id}&amp;limit=10",
                timeout=4.0,
                fallback=[],
            ),
            ServiceCall(
                name="notifications",
                method="GET",
                url=f"http://notify-service/api/unread?user_id={user_id}",
                timeout=2.0,
                fallback={"count": 0},
            ),
        ])
```

### 6.3 聚合结果的错误处理原则

| 原则 | 说明 |
|------|------|
| 部分失败不等于全部失败 | 4 个调用中 3 个成功，应返回成功的 3 个结果 + 错误标记 |
| 核心服务失败应整体失败 | 用户信息是核心，失败则整个聚合接口返回失败 |
| 非核心服务失败可降级 | 推荐、通知等失败时返回空列表或默认值 |
| 始终设置独立超时 | 每个调用的超时应短于聚合接口的总超时 |
| 前端感知降级状态 | 通过 `_degraded_xxx` 标记让前端知道哪些模块数据不完整 |

---

## 七、技术选型速查

面对具体场景时，快速选择合适的技术组合：

| 场景 | 路由策略 | 认证方式 | 限流算法 | 熔断策略 | 协议 |
|------|---------|---------|---------|---------|------|
| 企业内部 API | 路径 + 主机头 | JWT + IP 白名单 | 令牌桶 | 快速熔断 | HTTP |
| 开放平台 API | 路径精确匹配 | API Key + OAuth2 | 滑动窗口 | 熔断 + 降级 | HTTP |
| 移动端 BFF | 路径前缀 | JWT | 令牌桶 + 消费者限流 | 缓存降级 | HTTP + WebSocket |
| IoT 设备接入 | 设备 ID 路由 | mTLS + 设备证书 | 令牌桶（宽松） | 直接拒绝 | MQTT ↔ HTTP |
| 金融支付网关 | 严格精确路由 | JWT + 签名校验 | 严格限流 | 不降级，直接报错 | HTTPS + gRPC |
| 实时数据推送 | WebSocket 路由 | JWT（升级时验证） | 连接数限制 | 连接断开重连 | WebSocket |

---

## 本节小结

六大核心技术的关系可以用一句话概括：**路由决定请求去哪里，鉴权决定谁能去，限流决定去多少，熔断决定出事怎么办，协议转换决定怎么说，聚合决定怎么合**。掌握这六项技术，就能应对 90% 的 API 网关设计场景。

关键实践原则：
1. **路由优先用精确/前缀匹配**，正则只在过渡期使用，用完即删
2. **JWT 验证放在网关层**，后端服务通过请求头获取用户信息，不再重复验证
3. **限流必须分层**，全局 + 路由 + 消费者三级配合
4. **熔断器要有降级策略**，熔断不是报错，是优雅地返回有意义的替代数据
5. **协议转换要关注序列化性能**，Protobuf 比 JSON 快 5-10 倍
6. **请求聚合要设独立超时**，慢接口不能拖垮整个聚合响应
