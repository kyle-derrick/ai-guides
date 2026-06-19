---
title: "核心技巧"
type: docs
---
# 分布式锁核心技巧

分布式锁的理论框架告诉我们"该做什么"，而核心技巧决定了"怎么做好"。本节聚焦三个最核心的Redis分布式锁技巧——SET NX EX原子操作、Lua脚本保证原子性、Redlock多节点算法——从工程实践的角度深入讲解它们的实现细节、生产配置、性能调优和常见陷阱。

---

## 一、SET NX EX：原子加锁的工程细节

### 1.1 命令语义与底层实现

`SET key value NX EX seconds` 是Redis分布式锁的基石命令。它在一个原子操作中完成三件事：

- **SET**：设置键值对
- **NX**（Not eXists）：仅当键不存在时才写入，保证互斥性
- **EX**（Expire Seconds）：同时设置过期时间，保证无死锁

Redis在3.0+版本引入了`SET`命令的扩展参数，将`SETNX`和`EXPIRE`合并为单条命令。这解决了早期`SETNX`+`EXPIRE`非原子操作的竞态问题——如果客户端在执行`SETNX`成功后、执行`EXPIRE`前崩溃，锁将永远不会过期，造成死锁。

**为什么是原子的？** Redis采用单线程事件循环模型，`SET NX EX`作为单条命令在事件循环中不会被其他命令打断。命令执行期间不存在线程切换或命令交错，天然保证原子性。

### 1.2 value的设计：唯一标识的选择

锁的value不是随意填的，它承担着"锁持有者身份凭证"的关键角色。释放锁时需要验证value，因此value必须满足：

- **全局唯一**：同一时刻不同客户端获取的value不能相同
- **可验证**：释放锁时客户端能还原自己的value

常见的value设计方案：

| 方案 | 格式示例 | 优点 | 缺点 |
|------|---------|------|------|
| UUID | `550e8400-e29b-41d4-a716-446655440000` | 简单可靠，碰撞概率极低 | 略长，占36字节 |
| UUID+线程ID | `550e8400-...:thread-42` | 可区分同进程不同线程 | 需手动拼接 |
| 时间戳+随机数 | `1672531200000-abc123` | 短小，含时间信息 | 碰撞概率高于UUID |
| 机器IP+PID+随机数 | `192.168.1.5:12345:789` | 可读性好，便于排查 | 长度不确定 |

**生产建议**：使用UUID作为value，简单且碰撞概率可以忽略（2^122种可能）。如果需要排查问题，可以将UUID映射到客户端元数据（IP、PID、线程名）的日志中。

```python
import uuid
import redis

def acquire_lock(conn, lock_key, expire_seconds=30):
    """获取分布式锁"""
    value = str(uuid.uuid4())
    success = conn.set(lock_key, value, nx=True, ex=expire_seconds)
    if success:
        return value
    return None

def release_lock(conn, lock_key, value):
    """释放分布式锁（需要Lua脚本保证原子性，见下节）"""
    # 此处仅为示意，实际应使用Lua脚本
    pass
```

### 1.3 过期时间的设置策略

过期时间是分布式锁设计中最关键的参数之一。设错了，轻则性能下降，重则数据不一致。

**核心原则**：过期时间必须大于业务执行的最大时间，但不能过大以至于故障恢复太慢。

**经验公式**：

expire_time = max(业务P99延迟 × 3, 最小保护时间)

- **乘以3**：留出足够的安全余量，应对GC暂停、网络抖动、Redis慢查询等异常
- **最小保护时间**：即使是极快的操作，也建议至少5秒，防止Redis主从切换期间的竞态

**不同业务场景的推荐值**：

| 业务类型 | 典型执行时间 | 推荐过期时间 | 理由 |
|---------|------------|------------|------|
| 缓存更新 | 10-50ms | 5-10秒 | 操作极快，但需覆盖主从切换窗口 |
| 订单处理 | 100-500ms | 10-30秒 | 正常很快，但可能触发下游调用 |
| 秒杀扣减 | 50-200ms | 10-30秒 | 高并发下需稳定，不能设太短 |
| 数据迁移 | 10s-几分钟 | 300-600秒 | 长任务，建议配合看门狗 |
| 批量同步 | 1-30分钟 | 需看门狗 | 超过5分钟的操作不应依赖固定过期 |

**危险误区**：

1. **设太短（如1秒）**：网络抖动或Redis慢查询可能导致锁在业务执行期间过期，其他客户端获取锁后并发冲突
2. **设太长（如1小时）**：客户端崩溃后锁不释放，资源长时间不可用
3. **不设过期时间**：单节点Redis重启后锁数据丢失，但如果是持久化配置的Redis，崩溃后锁残留导致死锁

### 1.4 加锁失败的处理策略

获取锁失败后如何处理，直接决定了系统的可用性和公平性。

**策略一：立即返回失败**

```python
def try_lock_non_blocking(conn, lock_key, value, expire=30):
    """非阻塞尝试：失败立即返回"""
    return conn.set(lock_key, value, nx=True, ex=expire)
```

适用场景：秒杀、限流等需要快速失败的场景。调用方根据返回值决定是重试还是降级。

**策略二：自旋重试**

```python
import time

def try_lock_spin(conn, lock_key, value, expire=30, max_retries=10, retry_interval=0.1):
    """自旋重试：固定间隔重试"""
    for i in range(max_retries):
        if conn.set(lock_key, value, nx=True, ex=expire):
            return True
        time.sleep(retry_interval)
    return False
```

适用场景：对延迟不太敏感但要求最终成功的场景。注意`retry_interval`不能太小，否则会加重Redis负担。推荐间隔0.05-0.2秒。

**策略三：Pub/Sub等待释放通知**

```python
def try_lock_pubsub(conn, lock_key, value, expire=30, timeout=10):
    """订阅释放通知：锁释放时立即尝试获取"""
    pubsub = conn.pubsub()
    channel = f"lock_release:{lock_key}"
    pubsub.subscribe(channel)
    
    if conn.set(lock_key, value, nx=True, ex=expire):
        return True
    
    deadline = time.time() + timeout
    for message in pubsub.listen():
        if message['type'] == 'message':
            if conn.set(lock_key, value, nx=True, ex=expire):
                return True
        if time.time() > deadline:
            break
    return False
```

适用场景：需要低延迟获取锁的场景。Redis的Pub/Sub延迟通常在亚毫秒级。缺点是需要额外维护订阅连接，且存在消息丢失风险（网络分区期间的发布可能丢失）。

**策略四：Redisson的FairSpinLock（混合策略）**

Redisson在高竞争场景下使用"自旋+订阅"混合策略：先自旋N次（默认200ms），如果仍未获取成功，切换为Pub/Sub等待。这样既避免了纯自旋的CPU浪费，又避免了纯Pub/Sub的消息丢失问题。

### 1.5 性能基准与调优

**单节点Redis锁的性能上限**：

| 操作 | QPS（单核） | P99延迟 | 说明 |
|------|-----------|---------|------|
| SET NX EX | ~120,000 | 0.1ms | 无竞争情况 |
| GET + DEL（Lua） | ~120,000 | 0.1ms | 释放锁 |
| SET NX EX（竞争） | 取决于持有时间 | 1-10ms | 有锁等待 |

**调优要点**：

1. **减少锁持有时间**：锁内的操作越快越好。将非必要操作移到锁外，只对临界区加锁
2. **使用Pipeline批量操作**：如果一个业务流程需要多次Redis操作，使用Pipeline减少网络往返
3. **选择合适的序列化方式**：Protobuf > MessagePack > JSON，序列化时间直接影响锁持有时间
4. **监控锁竞争指标**：记录获取锁的等待时间、成功率，设置告警阈值

```python
import time
import statistics

class LockMetrics:
    """分布式锁性能监控"""
    def __init__(self):
        self.acquire_times = []
        self.hold_times = []
    
    def record_acquire(self, wait_time):
        self.acquire_times.append(wait_time)
    
    def record_hold(self, hold_time):
        self.hold_times.append(hold_time)
    
    def report(self):
        if not self.acquire_times:
            return "No data"
        return {
            "acquire_p50": statistics.median(self.acquire_times),
            "acquire_p99": sorted(self.acquire_times)[int(len(self.acquire_times) * 0.99)],
            "acquire_max": max(self.acquire_times),
            "avg_hold_time": statistics.mean(self.hold_times),
            "total_acquire": len(self.acquire_times),
        }
```

---

## 二、Lua脚本：保证操作原子性

### 2.1 为什么需要Lua脚本

Redis提供了丰富的原子命令（GET、SET、DEL等），但业务逻辑往往需要多个命令的组合。比如"释放锁"需要"GET检查值 + DEL删除"两步，如果用两条独立命令：

GET lock_key  → 返回 "A"（匹配）
-- 此时锁过期，B获取了锁 --
DEL lock_key  → 误删B的锁！

Redis通过Lua脚本解决这个问题：**脚本执行期间不会有其他命令插入**。这是Redis保证Lua原子性的机制——不是加锁，而是将Lua脚本作为一个不可分割的单元在单线程事件循环中执行。

### 2.2 释放锁的标准Lua脚本

这是Redis分布式锁中最重要的一段代码，务必理解每一行：

```lua
-- unlock.lua：标准释放锁脚本
-- KEYS[1]: 锁的key名
-- ARGV[1]: 当前客户端的唯一标识（UUID）

-- 第一步：获取当前锁的值
local current_value = redis.call("GET", KEYS[1])

-- 第二步：比较是否是自己持有的锁
if current_value == ARGV[1] then
    -- 匹配：删除锁，返回1表示释放成功
    redis.call("DEL", KEYS[1])
    return 1
else
    -- 不匹配：可能是别人的锁或已过期，返回0表示释放失败
    return 0
end
```

**调用方式**：

```python
import os

# 读取Lua脚本文件
UNLOCK_SCRIPT = open("unlock.lua").read()

def release_lock(conn, lock_key, value):
    """原子释放分布式锁"""
    script = conn.register_script(UNLOCK_SCRIPT)
    result = script(keys=[lock_key], args=[value])
    return result == 1
```

**为什么不能用GET+DEL两条命令？** 时序如下：

1. 客户端A执行`GET lock_key`，返回"A"，确认是自己的锁
2. 此时锁恰好过期（A的业务执行太慢），Redis自动删除key
3. 客户端B执行`SET lock_key B NX EX 30`，获取锁成功
4. 客户端A执行`DEL lock_key`——删掉了B的锁！
5. 客户端C获取锁成功，现在A和C同时持有锁

Lua脚本将GET和DEL放在同一个不可分割的操作中执行，Redis在脚本执行期间不处理其他命令，从而彻底避免了这种竞态条件。

### 2.3 续期（Renew）的Lua脚本

看门狗需要定期续期，续期操作同样是"检查+续期"的组合，需要原子性：

```lua
-- renew_lock.lua：续期锁脚本
-- KEYS[1]: 锁的key名
-- ARGV[1]: 当前客户端标识
-- ARGV[2]: 新的过期时间（秒）

local current_value = redis.call("GET", KEYS[1])

if current_value == ARGV[1] then
    -- 确认仍是自己持有，续期
    redis.call("EXPIRE", KEYS[1], ARGV[2])
    return 1
else
    -- 锁已被其他客户端获取或已过期，不续期
    return 0
end
```

```python
RENEW_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("EXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
"""

def renew_lock(conn, lock_key, value, expire_seconds):
    script = conn.register_script(RENEW_SCRIPT)
    return script(keys=[lock_key], args=[value, expire_seconds]) == 1
```

### 2.4 可重入锁的Lua脚本

可重入锁允许同一线程多次获取同一把锁，用于递归调用、嵌套方法等场景。使用Redis的Hash结构存储重入信息：

```lua
-- reentrant_lock.lua：可重入加锁脚本
-- KEYS[1]: 锁的key名
-- ARGV[1]: 客户端标识（线程ID + UUID）
-- ARGV[2]: 过期时间（秒）

-- 检查锁是否已被自己持有
local current = redis.call("HGET", KEYS[1], ARGV[1])

if current then
    -- 已持有：重入计数+1，刷新过期时间
    redis.call("HINCRBY", KEYS[1], ARGV[1], 1)
    redis.call("EXPIRE", KEYS[1], ARGV[2])
    return 1
else
    -- 检查锁是否被其他客户端持有
    local exists = redis.call("EXISTS", KEYS[1])
    if exists == 0 then
        -- 锁不存在：首次获取
        redis.call("HSET", KEYS[1], ARGV[1], 1)
        redis.call("EXPIRE", KEYS[1], ARGV[2])
        return 1
    else
        -- 被其他客户端持有：获取失败
        return 0
    end
end
```

```lua
-- reentrant_unlock.lua：可重入释放脚本
-- KEYS[1]: 锁的key名
-- ARGV[1]: 客户端标识

local count = redis.call("HINCRBY", KEYS[1], ARGV[1], -1)

if count == 0 then
    -- 重入计数归零，删除整个锁
    redis.call("DEL", KEYS[1])
    return 1
elseif count > 0 then
    -- 还有重入层级，仅减少计数
    return 1
else
    -- 异常：计数为负（说明释放了不属于自己的锁）
    redis.call("HSET", KEYS[1], ARGV[1], 0)
    return 0
end
```

**关键设计决策**：

- **为什么用Hash而非String？** Hash的field可以存储多个客户端的重入信息，支持"锁转让"（虽然不推荐）。String只能存一个value，无法表示重入计数。
- **每次重入都要刷新过期时间**：防止重入次数多时锁提前过期。但如果外层调用已经设置了固定的leaseTime，也可以不刷新（由看门狗统一管理）。
- **重入计数归零时删除整个key**：不是只删field，而是DEL整个Hash。因为如果只删field，可能残留其他已崩溃客户端的field。

### 2.5 Lua脚本的调试与测试

Lua脚本的错误不会像普通Redis命令那样返回明确的错误信息，调试起来比较困难。以下是一些实用技巧：

**技巧一：使用redis.log记录调试信息**

```lua
-- 在Lua脚本中添加日志（需要Redis配置lua-replicate-commands yes）
redis.log(redis.LOG_DEBUG, "Lock key: " .. KEYS[1] .. ", value: " .. ARGV[1])
redis.log(redis.LOG_DEBUG, "Current value: " .. tostring(current_value))
```

日志会写入Redis的日志文件，可通过`redis-cli CONFIG GET logfile`查看路径。

**技巧二：单独测试Lua脚本**

```bash
# 使用redis-cli直接加载并执行Lua脚本
cat unlock.lua | redis-cli --eval /dev/stdin lock_key , client_uuid

# 注意：KEYS和ARGV之间用空格+逗号分隔，逗号前后有空格
```

**技巧三：编写单元测试**

```python
import pytest
import redis

@pytest.fixture
def redis_client():
    return redis.Redis(host='localhost', port=6379, db=15)  # 用db=15隔离测试

def test_release_lock_success(redis_client):
    """测试：正确释放自己持有的锁"""
    redis_client.set("test_lock", "client_A", nx=True, ex=30)
    result = release_lock(redis_client, "test_lock", "client_A")
    assert result == True
    assert redis_client.get("test_lock") is None

def test_release_lock_wrong_owner(redis_client):
    """测试：不能释放别人的锁"""
    redis_client.set("test_lock", "client_A", nx=True, ex=30)
    result = release_lock(redis_client, "test_lock", "client_B")
    assert result == False
    assert redis_client.get("test_lock") == b"client_A"

def test_release_expired_lock(redis_client):
    """测试：锁过期后释放返回失败"""
    redis_client.set("test_lock", "client_A", nx=True, ex=1)
    import time
    time.sleep(1.5)  # 等待过期
    result = release_lock(redis_client, "test_lock", "client_A")
    assert result == False
```

### 2.6 Lua脚本的性能优化

**缓存脚本句柄**：`register_script`返回的脚本对象可以被缓存和复用，避免每次执行都发送脚本文本：

```python
# ❌ 错误：每次释放锁都发送脚本文本
def release_bad(conn, lock_key, value):
    script = conn.register_script(UNLOCK_SCRIPT)
    return script(keys=[lock_key], args=[value])

# ✅ 正确：缓存脚本句柄，复用执行
class DistributedLock:
    def __init__(self, conn):
        self.conn = conn
        self._unlock_script = conn.register_script(UNLOCK_SCRIPT)
        self._renew_script = conn.register_script(RENEW_SCRIPT)
    
    def release(self, lock_key, value):
        return self._unlock_script(keys=[lock_key], args=[value]) == 1
    
    def renew(self, lock_key, value, expire):
        return self._renew_script(keys=[lock_key], args=[value, expire]) == 1
```

**控制脚本长度**：Redis的`lua-time-limit`（默认5秒）限制了单个Lua脚本的最大执行时间。超时后Redis会记录告警日志但不会强制终止。确保脚本中没有循环、没有大量KEYS访问，保持在微秒级完成。

---

## 三、Redlock算法：多节点锁的实现与取舍

### 3.1 为什么需要Redlock

单节点Redis锁在以下场景存在安全隐患：

1. **主从切换**：Master宕机，Slave提升为新Master，但锁数据尚未同步到Slave，新Master上锁不存在，其他客户端可以获取锁
2. **Redis持久化**：如果RDB间隔较长，Redis重启后锁数据丢失
3. **网络分区**：客户端与Master之间的网络分区导致锁状态不一致

Redlock通过在多个**独立的**Redis节点上同时获取锁来解决这些问题。只要大多数节点上锁成功，即使个别节点故障，锁的一致性仍然有保障。

### 3.2 算法详细步骤

输入：N个独立的Redis节点（通常N=5），锁key，过期时间
输出：锁是否获取成功，有效时间

步骤1：记录开始时间 T1 = now()

步骤2：依次向N个节点发送 SET key value NX EX expire 命令
        对每个节点设置超时时间（如5ms），避免在故障节点上阻塞
        记录成功获取锁的节点数量 success_count

步骤3：计算获取锁消耗的总耗时 elapsed = now() - T1

步骤4：判断获取锁是否成功：
        条件1：success_count >= N/2 + 1（即过半数节点成功）
        条件2：elapsed < expire（总耗时未超过锁的过期时间）
        两个条件同时满足 → 获取锁成功

步骤5：计算锁的有效时间 valid_time = expire - elapsed
        如果 valid_time <= 0 → 即使成功也算失败（保护时间不够用）

步骤6：如果获取锁失败，向所有节点发送 DEL key 释放锁

**为什么是5个节点？** N=5时，至少需要3个节点成功。这意味着可以容忍2个节点同时故障。在实际生产中，5个Redis实例通常分布在不同的物理机或可用区上，单点故障不会影响锁的安全性。

### 3.3 完整的Python实现

```python
import time
import uuid
import redis

class Redlock:
    """Redlock分布式锁实现"""
    
    def __init__(self, nodes, lock_key, expire_seconds=30):
        """
        nodes: Redis连接列表，如 [redis.Redis(host='r1'), redis.Redis(host='r2'), ...]
        lock_key: 锁的key名
        expire_seconds: 锁的过期时间
        """
        self.nodes = nodes
        self.lock_key = lock_key
        self.expire = expire_seconds
        self.quorum = len(nodes) // 2 + 1  # 多数派阈值
        self.value = str(uuid.uuid4())  # 锁的唯一标识
        self._unlock_script = None
    
    def _acquire_node(self, conn):
        """在单个节点上尝试获取锁"""
        try:
            return conn.set(self.lock_key, self.value, nx=True, ex=self.expire)
        except redis.RedisError:
            return False
    
    def _release_node(self, conn):
        """在单个节点上释放锁"""
        try:
            if self._unlock_script is None:
                self._unlock_script = conn.register_script(
                    'if redis.call("GET", KEYS[1]) == ARGV[1] then '
                    'return redis.call("DEL", KEYS[1]) else return 0 end'
                )
            self._unlock_script(keys=[self.lock_key], args=[self.value])
        except redis.RedisError:
            pass
    
    def acquire(self):
        """获取Redlock，返回锁的有效时间（毫秒）或None"""
        start_time = time.time() * 1000  # 毫秒
        acquired_count = 0
        
        for conn in self.nodes:
            if self._acquire_node(conn):
                acquired_count += 1
        
        elapsed = time.time() * 1000 - start_time
        validity = self.expire * 1000 - elapsed  # 毫秒
        
        if acquired_count >= self.quorum and validity > 0:
            return validity
        else:
            # 获取失败，释放所有节点上的锁
            for conn in self.nodes:
                self._release_node(conn)
            return None
    
    def release(self):
        """释放所有节点上的锁"""
        for conn in self.nodes:
            self._release_node(conn)
```

### 3.4 工程实践中的关键细节

**细节一：单节点超时设置**

向每个Redis节点发送命令时，必须设置连接超时和读写超时（推荐5ms）。否则，如果某个节点故障或网络延迟很高，客户端会阻塞在该节点上，导致整体获取锁的耗时大幅增加，最终valid_time不足。

```python
# 设置超时
conn = redis.Redis(
    host='redis-node-1',
    port=6379,
    socket_timeout=0.005,     # 5ms读写超时
    socket_connect_timeout=0.005  # 5ms连接超时
)
```

**细节二：时钟漂移的处理**

Redlock依赖时间来判断锁是否有效。如果节点间的系统时钟发生跳变（如NTP同步），可能导致判断失准。工程建议：

- 在所有Redis节点上禁用NTP的`step`模式（大跳），只允许`slew`模式（微调）
- 使用单调时钟而非系统时钟计算elapsed
- 在valid_time计算中留出额外的安全余量（如减去一个可配置的`clock_drift_factor`，默认0.01，即时钟漂移1%）

```python
# 考虑时钟漂移的valid_time计算
clock_drift_factor = 0.01  # 1%时钟漂移
validity = self.expire * 1000 - elapsed - (self.expire * 1000 * clock_drift_factor)
```

**细节三：重试策略**

Redlock获取失败后的重试需要谨慎设计：

```python
def acquire_with_retry(self, max_retries=3, retry_delay_ms=200):
    """带重试的Redlock获取"""
    for attempt in range(max_retries):
        validity = self.acquire()
        if validity is not None:
            return validity
        if attempt < max_retries - 1:
            time.sleep(retry_delay_ms / 1000.0)
    return None
```

重试间隔建议使用固定延迟（如200ms）而非指数退避，因为Redlock的延迟主要是获取锁的网络传播时间，不需要指数增长。重试次数不宜过多（3次足够），否则在节点故障时会造成不必要的等待。

### 3.5 Redlock的争议与替代方案

Martin Kleppmann在2016年发表的"How to do distributed locking"一文对Redlock提出了根本性挑战：

**Kleppmann的核心论点**：

1. **GC暂停问题**：客户端获取锁后，如果发生长时间GC暂停（如10秒），锁过期后其他客户端获取锁并修改数据。GC恢复后，原客户端认为自己仍持有锁，继续操作——数据不一致
2. **时钟跳跃**：如果某个节点的系统时钟突然向前跳跃（如NTP校准），可能导致锁提前过期
3. **Redlock不是"强一致"的**：它依赖时间假设而非共识协议，在FLP不可能定理的框架下，异步系统中不存在完美的分布式锁

**Antirez的回应**：

1. GC暂停问题对所有分布式锁（包括ZooKeeper）都存在，这是分布式系统的固有问题
2. 生产环境应该严格控制时钟漂移，NTP的slew模式不会导致大的跳跃
3. Fencing Token需要存储层支持，实际中很多存储层（如Redis、MySQL的某些引擎）不具备递增token检查的能力

**工程选型建议**：

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| 普通业务互斥 | 单节点Redis锁 | 简单高效，覆盖99%场景 |
| 需要高可用 | Redis单节点 + 哨兵 | 哨兵自动故障转移 |
| 金融级安全 | ZooKeeper/etcd锁 | 基于共识协议，强一致 |
| 性能+安全兼顾 | 单节点Redis锁 + Fencing Token | 分布式锁做互斥，Fencing Token做兜底 |
| 跨机房部署 | etcd锁 | Raft协议天然支持跨机房 |

### 3.6 Redlock vs 单节点锁的性能对比

| 指标 | 单节点Redis锁 | Redlock（5节点） |
|------|-------------|-----------------|
| 获取锁延迟 | 0.1ms | 1-5ms（串行获取5个节点） |
| 最大QPS | ~120,000 | ~15,000-30,000 |
| 可用性 | 单点故障时不可用 | 容忍2个节点故障 |
| 一致性 | 主从切换时可能丢锁 | 过半节点一致 |
| 运维复杂度 | 低 | 高（5个独立节点） |

**结论**：Redlock的性能约为单节点的1/4-1/8，且运维复杂度显著增加。在大多数业务场景中，单节点Redis锁配合合理的过期时间和Fencing Token已经足够。Redlock适用于"不能接受任何锁失效可能"但又不想引入ZooKeeper/etcd的场景。

---

## 四、综合实战：从零构建生产级Redis分布式锁

### 4.1 完整的分布式锁客户端

以下是综合以上技巧的生产级实现，包含所有核心功能：

```python
import uuid
import time
import threading
import redis

class DistributedLock:
    """生产级Redis分布式锁"""
    
    # Lua脚本
    LOCK_SCRIPT = """
    if redis.call("EXISTS", KEYS[1]) == 0 then
        redis.call("HSET", KEYS[1], ARGV[1], 1)
        redis.call("EXPIRE", KEYS[1], ARGV[2])
        return 1
    elseif redis.call("HGET", KEYS[1], ARGV[1]) then
        redis.call("HINCRBY", KEYS[1], ARGV[1], 1)
        redis.call("EXPIRE", KEYS[1], ARGV[2])
        return 1
    else
        return 0
    end
    """
    
    UNLOCK_SCRIPT = """
    if redis.call("HGET", KEYS[1], ARGV[1]) then
        local count = redis.call("HINCRBY", KEYS[1], ARGV[1], -1)
        if count == 0 then
            redis.call("DEL", KEYS[1])
        end
        return 1
    else
        return 0
    end
    """
    
    RENEW_SCRIPT = """
    if redis.call("HGET", KEYS[1], ARGV[1]) then
        redis.call("EXPIRE", KEYS[1], ARGV[2])
        return 1
    else
        return 0
    end
    """
    
    def __init__(self, redis_client, key, expire=30, watchdog=True):
        self.conn = redis_client
        self.key = key
        self.expire = expire
        self.watchdog_enabled = watchdog
        self.client_id = f"{uuid.uuid4()}:{threading.current_thread().ident}"
        
        # 预编译Lua脚本
        self._lock_script = self.conn.register_script(self.LOCK_SCRIPT)
        self._unlock_script = self.conn.register_script(self.UNLOCK_SCRIPT)
        self._renew_script = self.conn.register_script(self.RENEW_SCRIPT)
        
        # Watchdog线程
        self._watchdog_thread = None
        self._stop_event = threading.Event()
    
    def acquire(self, blocking=True, timeout=None):
        """获取锁"""
        start = time.time()
        while True:
            result = self._lock_script(
                keys=[self.key], args=[self.client_id, self.expire]
            )
            if result == 1:
                self._start_watchdog()
                return True
            
            if not blocking:
                return False
            
            if timeout and (time.time() - start) >= timeout:
                return False
            
            time.sleep(0.05)  # 50ms自旋间隔
    
    def release(self):
        """释放锁"""
        self._stop_watchdog()
        return self._unlock_script(keys=[self.key], args=[self.client_id]) == 1
    
    def _start_watchdog(self):
        """启动看门狗线程"""
        if not self.watchdog_enabled:
            return
        self._stop_event.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True
        )
        self._watchdog_thread.start()
    
    def _watchdog_loop(self):
        """看门狗循环：每expire/3秒续期一次"""
        interval = self.expire / 3.0
        while not self._stop_event.wait(interval):
            result = self._renew_script(
                keys=[self.key], args=[self.client_id, self.expire]
            )
            if result == 0:
                break  # 锁已丢失，停止续期
    
    def _stop_watchdog(self):
        """停止看门狗"""
        self._stop_event.set()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=1)
```

### 4.2 使用示例

```python
# 初始化
conn = redis.Redis(host='localhost', port=6379, db=0)

# 创建锁实例
lock = DistributedLock(conn, "order:process:12345", expire=30, watchdog=True)

# 获取锁
if lock.acquire(blocking=True, timeout=5):
    try:
        # 执行业务逻辑
        process_order("12345")
    finally:
        lock.release()
else:
    print("获取锁超时，降级处理")
```

### 4.3 生产环境检查清单

在上线分布式锁前，逐项检查：

- [ ] **value使用UUID**，确保唯一性和可追溯性
- [ ] **过期时间合理**，大于业务P99延迟的3倍
- [ ] **释放锁使用Lua脚本**，保证GET+DEL原子性
- [ ] **看门狗已启用**，防止业务未完成锁就过期
- [ ] **Redis持久化配置**，AOF每秒刷盘，防止重启丢锁
- [ ] **Redis超时设置**，避免在故障节点上阻塞
- [ ] **监控告警**，锁获取成功率、等待时间、持有时间
- [ ] **降级方案**，获取锁失败时有兜底处理
- [ ] **Fencing Token**（高安全场景），存储层做二次校验
- [ ] **日志记录**，锁的获取/释放/超时都记录日志

---

## 五、常见误区与最佳实践

### 5.1 误区一：用SETNX+EXPIRE代替SET NX EX

```bash
# ❌ 错误：非原子操作
SETNX lock_key value
EXPIRE lock_key 30
# 如果SETNX后客户端崩溃，EXPIRE不会执行，锁永不过期

# ✅ 正确：原子操作
SET lock_key value NX EX 30
```

### 5.2 误区二：用DEL释放锁而非Lua脚本

```python
# ❌ 错误：GET和DEL之间存在竞态窗口
if conn.get("lock_key") == my_value:
    conn.delete("lock_key")  # 此时可能已过期并被其他客户端获取

# ✅ 正确：使用Lua脚本原子释放
conn.eval(LUA_UNLOCK, 1, "lock_key", my_value)
```

### 5.3 误区三：不处理锁续期

```python
# ❌ 错误：固定过期时间，业务慢时锁提前过期
lock = acquire("order:123", expire=10)
process_order()  # 如果执行了12秒，锁已过期

# ✅ 正确：启用看门狗自动续期
lock = DistributedLock(conn, "order:123", expire=30, watchdog=True)
```

### 5.4 误区四：忽略Fencing Token

```python
# ❌ 错误：完全依赖分布式锁保证安全
lock = acquire("balance:user:1")
balance = get_balance("user:1")
new_balance = balance - 100  # 如果此时锁已失效，余额可能不正确
set_balance("user:1", new_balance)

# ✅ 正确：使用CAS或Fencing Token做二次校验
lock, token = acquire_with_token("balance:user:1")
balance = get_balance("user:1")
set_balance_with_token("user:1", balance - 100, token)
# 存储层验证token单调递增，拒绝旧token的写入
```

### 5.5 误区五：在Redis Cluster中直接使用Redlock

Redis Cluster本身提供了`SET`命令的分布式特性（通过hash slot分配），但Cluster的`SET`只在一个节点上执行，不等于在多个独立节点上同时获取锁。不要混淆Cluster的高可用和Redlock的多节点锁。

在Redis Cluster环境中，如果需要跨节点的锁一致性，应该：
- 使用所有slot的key（如固定`{lock}`前缀确保hash到同一slot）
- 或者使用独立的Sentinel/单节点Redis做锁服务
- 或者改用ZooKeeper/etcd

### 5.6 最佳实践速查

| 原则 | 做法 | 反模式 |
|------|------|--------|
| 原子加锁 | `SET NX EX` | `SETNX` + `EXPIRE` |
| 原子释放 | Lua脚本检查+删除 | GET + DEL |
| 自动续期 | Watchdog线程 | 手动固定超时 |
| 锁持有者验证 | UUID作为value | 不验证直接删除 |
| 锁粒度 | 资源实例级别 | 全局锁 |
| 超时处理 | 快速失败+降级 | 无限等待 |
| 幂等设计 | Token+版本号 | 完全信任锁 |
| 监控 | 锁等待/持有时间 | 无监控 |
