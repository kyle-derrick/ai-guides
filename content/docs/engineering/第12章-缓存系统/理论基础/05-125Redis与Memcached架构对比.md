---
title: "12.5 Redis与Memcached架构对比"
type: docs
weight: 5
---
## 12.5 Redis与Memcached架构对比

### 12.5.1 引言：为什么需要了解两者差异

在前面的小节中，我们讨论了应用层缓存策略、缓存一致性协议，以及缓存穿透、击穿、雪崩三大问题的解决方案。当我们决定在系统中引入分布式缓存时，最常面临的第一个技术选型问题就是：**用 Redis 还是 Memcached？**

这两个系统都诞生于 2000 年代，经过十余年的发展，各自形成了鲜明的架构特征。它们并不是简单的替代关系，而是在不同场景下各有优势。理解它们的架构差异，是做出正确选型决策的基础。

| 对比维度 | Redis | Memcached |
|---------|-------|-----------|
| 首次发布 | 2009年（Redis） | 2003年（Memcached） |
| 作者 | Salvatore Sanfilippo (antirez) | Brad Fitzpatrick (LiveJournal) |
| 开源协议 | BSD | BSD |
| 语言实现 | C语言 | C语言 |
| 最新稳定版 | 7.x（2024+） | 1.6.x |

---

### 12.5.2 数据模型：最根本的差异

#### Redis：丰富的数据结构

Redis 最核心的竞争力在于其丰富的数据结构。它不仅仅是一个键值存储，更是一个数据结构服务器（Data Structure Server）。

**Redis 支持的 8 种核心数据结构：**

| 数据结构 | 底层编码 | 典型用途 | 内存开销（估算） |
|---------|---------|---------|----------------|
| String（字符串） | SDS（Simple Dynamic String） | 缓存值、计数器、分布式锁 | 约32字节头 + 数据 |
| List（列表） | quicklist（ziplist + 链表） | 消息队列、时间线 | 每节点约16字节指针开销 |
| Hash（哈希） | listpack / hashtable | 对象存储、用户信息 | 小用listpack，大转hashtable |
| Set（集合） | intset / hashtable | 标签、去重、交并差运算 | 空集仅需16字节 |
| Sorted Set（有序集合） | listpack / skiplist + hashtable | 排行榜、延迟队列 | skiplist约每节点32字节 |
| Bitmap（位图） | String的位操作 | 用户签到、布隆过滤器 | 每bit占1/8字节 |
| HyperLogLog | 概率算法 | UV统计（误差<1%） | 固定12KB |
| Stream（流） | Radix Tree + listpack | 消息队列、事件溯源 | 按消息数线性增长 |

以一个典型的电商场景为例，同一个 Redis 实例可以同时承担以下职责：

```python
import redis

r = redis.Redis(host='localhost', port=6379, db=0)

# 1. String - 缓存商品详情（最简单的KV场景）
r.set('product:1001', '{"name":"机械键盘","price":299}', ex=3600)

# 2. Sorted Set - 实时销售排行榜
r.zadd('hot_products', {'product:1001': 1523, 'product:1002': 2341})

# 3. Hash - 存储用户购物车（结构化字段）
r.hset('cart:user:8801', mapping={'product:1001': 1, 'product:1002': 2})

# 4. List - 最新订单队列
r.lpush('recent_orders', '{"order_id":"ORD001","amount":299}')

# 5. Set - 用户收藏的品类标签
r.sadd('user:8801:tags', 'electronics', 'gaming', 'peripherals')

# 6. Bitmap - 每日签到（每月仅需31bit ≈ 4字节）
r.setbit('checkin:user:8801:202401', 15, 1)  # 1月16日签到
```

这些操作都是原子性的，无需额外的事务开销。Redis 的数据结构不仅是存储容器，本身也是计算引擎——服务端可以直接执行排序、聚合、交并差等操作，避免了将大量数据拉到客户端再处理的开销。

#### Memcached：纯粹的Key-Value

Memcached 的设计哲学是极致的简单。它只支持一种数据结构：**字符串键值对**。所有值在存储前都被序列化为字节流，客户端负责序列化和反序列化。

# Memcached 存储模型
SET product:1001 <JSON序列化字符串> 3600
GET product:1001  → <JSON序列化字符串>  → 客户端反序列化

这种设计的好处是：
- **协议极其简单**：文本协议（Text Protocol）仅需 3 条命令（set/get/delete）即可操作
- **服务端零计算**：不执行任何数据结构运算，CPU 开销极低
- **多语言客户端一致**：不同语言的客户端序列化结果可以互通

```python
import pymemcache

mc = pymemcache.Client(('localhost', 11211))

# 所有数据都以字符串形式存储
mc.set('product:1001', '{"name":"机械键盘","price":299}', expire=3600)
mc.set('user:8801:cart', '{"1001":1,"1002":2}', expire=7200)

# 需要自行处理序列化/反序列化
import json
cart_raw = mc.get('user:8801:cart')
cart = json.loads(cart_raw) if cart_raw else {}
```

> **关键认知**：Memcached 不是"功能弱的 Redis"，而是"专注做一件事做到极致"。对于纯 KV 缓存场景，Memcached 的简单性反而是优势——更少的代码意味着更少的 bug 和更可预测的性能。

---

### 12.5.3 内存管理模型：Slab Allocator vs Redis 内存分配器

这是两者在底层实现上最显著的差异之一，直接影响内存利用率和缓存命中率。

#### Memcached 的 Slab Allocator

Memcached 使用 **Slab Allocator** 进行内存管理，这是一种经典的内存池技术：

Slab Allocator 工作流程：

[1MB 内存页]
    │
    ├── Slab Class 1 (chunk: 96B)  → 可存10922个chunk
    ├── Slab Class 2 (chunk: 120B) → 可存8738个chunk
    ├── Slab Class 3 (chunk: 152B) → 可存6898个chunk
    ├── ...
    └── Slab Class N (chunk: 1MB)  → 可存1个chunk

写入流程：
1. 计算数据大小 → 找到最小能容纳的 Slab Class
2. 从该 Class 的空闲链表中分配一个 chunk
3. 写入数据，剩余空间不可被其他 Class 使用

**Slab 碎片问题（Slab Wastage）**：

假设 Slab Class 1 的 chunk 为 96 字节，当你存储一个 50 字节的值时，剩余的 46 字节无法被其他 Slab Class 使用，造成约 48% 的内部碎片。

示例：Slab 碎片浪费

Slab Class 1: chunk = 96B
├── 存储 50B 数据 → 浪费 46B (47.9%)
├── 存储 95B 数据 → 浪费  1B  (1.1%)
└── 存储 96B 数据 → 浪费  0B  (0%)

Slab Class 2: chunk = 120B  
├── 存储 97B 数据 → 浪费 23B (19.2%)
└── 存储 120B 数据 → 浪费 0B  (0%)

Memcached 通过 **Slab Automover**（1.4.31+）来缓解这个问题：当某个 Slab Class 的空闲 chunk 超过阈值时，将整页内存重新分配给其他更需要的 Class。但这仍然是补丁式的优化，无法根本解决碎片问题。

#### Redis 的内存分配器策略

Redis 在编译时可以选择底层内存分配器：

| 分配器 | 特点 | 适用场景 |
|-------|------|---------|
| **jemalloc**（默认） | 减少内存碎片，多线程友好 | 通用场景，推荐默认选择 |
| **tcmalloc** | Google 出品，线程本地缓存 | 高并发场景 |
| **libc malloc** | 系统默认分配器 | 调试/兼容性需求 |

Redis 在分配器之上还有自己的内存管理策略：

Redis 内存管理层次：

应用层   ── 对象系统（robj）
              │
              ├── 对象编码（int/embstr/raw/ziplist/...）
              │   同一种数据类型根据大小自动选择更紧凑的编码
              │
分配器层 ── jemalloc / tcmalloc / libc
              │
              └── 操作系统页

**关键差异**：Redis 的数据结构可以根据数据量自动切换底层编码。例如，一个 Hash 在元素少于 128 个且值小于 64 字节时使用 `listpack`（紧凑编码），超过阈值后自动转为 `hashtable`（查询效率从 O(N) 变为 O(1)）。

```python
# Redis 自动编码切换示例
import redis
r = redis.Redis()

# 小 Hash → 使用 listpack 编码（内存紧凑）
for i in range(100):
    r.hset('small_hash', f'key{i}', f'value{i}')
r.object('encoding', 'small_hash')  # → 'listpack'

# 大 Hash → 自动转为 hashtable 编码（查询高效）
for i in range(200):
    r.hset('large_hash', f'key{i}', f'value{i}')
r.object('encoding', 'large_hash')  # → 'hashtable'
```

---

### 12.5.4 多线程模型：单线程 vs 多线程

#### Redis 的单线程 + I/O多路复用

Redis 的核心命令执行是**单线程**的。这个设计看似"落后"，实则是刻意为之的架构选择：

Redis 单线程架构：

  客户端A ──┐
  客户端B ──┤              ┌─────────────────────────┐
  客户端C ──┼── epoll ──→  │  单线程事件循环            │
  客户端D ──┤              │  (读请求 → 命令执行 → 写响应) │
  客户端E ──┘              └─────────────────────────┘
                                        │
                              网络 I/O + 命令执行
                              全在一个线程中完成

**为什么单线程反而更快？**
- 无锁设计：不需要锁竞争、不需要 CAS 操作，减少了 CPU 缓存失效
- 无上下文切换：避免线程间切换的开销（约 1-10μs/次）
- 数据局部性：所有操作在同一个线程中执行，CPU 缓存命中率高
- 原子性保证：命令天然串行执行，无需额外的并发控制

**Redis 6.0 引入的多线程 I/O**：

Redis 6.0 并没有改变"单线程执行命令"的核心模型，而是将网络 I/O 部分多线程化：

Redis 6.0+ 多线程 I/O 架构：

  客户端请求 ──→ [I/O线程1] ──┐
  客户端请求 ──→ [I/O线程2] ──┼──→ [主线程: 命令执行] ──→ [I/O线程] ──→ 响应
  客户端请求 ──→ [I/O线程3] ──┘

  多线程部分：读取请求、解析协议、写入响应
  单线程部分：命令执行（Redis 的核心竞争力所在）

这解决了大量客户端连接时的网络读写瓶颈（如 10000+ 并发连接），但命令执行仍然是串行的。

#### Memcached 的多线程模型

Memcached 从诞生之初就是**多线程**的：

Memcached 多线程架构：

  主线程（监听端口、接受连接）
      │
      ├── 工作线程1（处理请求、执行命令）
      ├── 工作线程2（处理请求、执行命令）
      ├── 工作线程3（处理请求、执行命令）
      └── 工作线程4（处理请求、执行命令）

  锁竞争管理：
  ├── Slab 级别锁（不同 Slab Class 不互相阻塞）
  ├── LRU 锁（淘汰时需要获取）
  └── Hash 表锁（分段锁，减少冲突）

**多线程带来的实际收益**：
- 在多核 CPU 上，Memcached 可以充分利用多个核心
- 单实例 QPS 可轻松达到 20 万+（Redis 单线程约 10 万 QPS）
- 但线程间锁竞争会带来额外开销，实际加速比通常为 2-3x/核，而非线性增长

**两者的本质区别**：

| 维度 | Redis 单线程 | Memcached 多线程 |
|------|------------|-----------------|
| 命令执行 | 串行，无锁 | 并行，有锁 |
| 适用场景 | 命令复杂（排序、聚合） | 简单 KV 操作 |
| 多核利用率 | 需要多实例（每核一个） | 单实例即可利用多核 |
| 可预测性 | 性能稳定，抖动小 | 受锁竞争影响，偶有毛刺 |
| 运维复杂度 | 多实例需要集群管理 | 单实例更简单 |

---

### 12.5.5 持久化与复制

#### Redis：丰富的持久化方案

Redis 提供三种持久化机制，可以组合使用：

**1. RDB（Redis Database）快照**

RDB 持久化原理：
┌─────────────────────────────────────────┐
│  Redis 主进程 fork() 创建子进程           │
│  ├── 子进程遍历内存数据 → 写入临时文件      │
│  ├── 使用 COW（Copy-On-Write）避免阻塞      │
│  └── 写完后原子替换旧 RDB 文件             │
└─────────────────────────────────────────┘

触发条件（可配置）：
- save 900 1      → 900秒内有1次修改则触发
- save 300 10     → 300秒内有10次修改则触发
- save 60 10000   → 60秒内有10000次修改则触发

优点：恢复速度快、文件紧凑
缺点：最后一次快照后的数据可能丢失

**2. AOF（Append Only File）日志**

AOF 持久化原理：
┌─────────────────────────────────────────┐
│  每条写命令 → 追加到 AOF 文件末尾           │
│                                         │
│  SET key1 value1                        │
│  INCR counter                           │
│  LPUSH queue item1                      │
│                                         │
│  重写策略（避免文件过大）：                  │
│  ├── always  → 每条命令都 fsync（最安全）    │
│  ├── everysec → 每秒 fsync（推荐默认）      │
│  └── no → 由 OS 决定何时 fsync（最快）      │
└─────────────────────────────────────────┘

优点：数据安全性高（最多丢失1秒数据）
缺点：文件体积大、恢复速度慢

**3. 混合持久化（Redis 4.0+）**

混合持久化：RDB + AOF 的最佳组合

重启恢复时：
1. 先加载 RDB 部分（速度快）
2. 再重放 RDB 之后的 AOF 命令（数据完整）

开启方式：aof-use-rdb-preamble yes

#### Memcached：无原生持久化

Memcached 的设计理念是**纯内存、可丢失**。它不提供任何原生的持久化机制。数据在进程重启后全部丢失。

这并非缺陷，而是设计哲学的体现：
- Memcached 被设计为"前端缓存"而非"数据存储"
- 下游数据库是数据的最终持久化位置
- 缓存重建是常态，Memcached 的设计者认为恢复缓存比重建它更复杂

**复制支持**：

| 能力 | Redis | Memcached |
|------|-------|-----------|
| 主从复制 | 原生支持，支持级联复制 | 不支持 |
| 故障转移 | Sentinel 自动切换 | 不支持 |
| 数据分片 | Cluster 自动分片 | 客户端一致性哈希 |
| 持久化 | RDB / AOF / 混合 | 无 |

---

### 12.5.6 集群与高可用方案

#### Redis 高可用架构

Redis 三种部署架构演进：

Level 1: 单机模式
┌──────────┐
│  Redis    │ ← 无冗余，单点故障
│  单实例    │
└──────────┘

Level 2: 主从复制
┌──────────┐     ┌──────────┐
│  Master   │ ──→ │  Slave   │
│  读写     │     │  只读     │
└──────────┘     └──────────┘
  问题：手动故障转移，数据可能丢失

Level 3: Sentinel 哨兵
┌──────────┐
│ Sentinel  │ ← 监控主节点，自动故障转移
│  集群     │
└──────────┘
  ├── 监控（每秒 PING）
  ├── 通知（故障时通知管理员/客户端）
  └── 自动故障转移（选举新 Master）

Level 4: Redis Cluster
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Master1  │  │ Master2  │  │ Master3  │
│ slot0-5460│ │slot5461-│  │slot10923-│
│          │  │  10922  │  │  16383   │
└─────────┘  └─────────┘  └─────────┘
     │            │            │
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Slave1   │  │ Slave2   │  │ Slave3   │
└─────────┘  └─────────┘  └─────────┘

数据分片：16384 个 slot，CRC16(key) % 16384 确定 slot
节点间通信：Gossip 协议

**Redis Cluster 核心机制**：
- **数据分片**：16384 个 slot 均匀分布在 N 个主节点上
- **节点通信**：Gossip 协议，每个节点维护集群状态
- **故障转移**：类似 Sentinel，从节点投票选举新主节点
- **客户端路由**：客户端缓存 slot → 节点映射，MOVED/ASK 重定向

#### Memcached 集群模式

Memcached 集群（纯客户端分片）：

┌──────────┐  ┌──────────┐  ┌──────────┐
│ Memcached │  │ Memcached │  │ Memcached │
│ 节点 A    │  │ 节点 B    │  │ 节点 C    │
│ (独立)    │  │ (独立)    │  │ (独立)    │
└──────────┘  └──────────┘  └──────────┘
      ↑              ↑              ↑
      └──────────────┼──────────────┘
                     │
              ┌─────────────┐
              │  客户端       │
              │  一致性哈希   │
              │  自行路由     │
              └─────────────┘

节点之间完全不知道彼此的存在
所有分片逻辑在客户端完成

**一致性哈希的工作原理**：

一致性哈希环：

        Node A (hash=0)
           │
     ······●·····················
    ·                           ·
   ·    Key1 → Node A            ·
  ·    Key2 → Node C              ·
 ·                                  ·
Node D ●                             ● Node B
 ·    Key3 → Node B                  ·
  ·                                  ·
   ·                                ·
    ·                              ·
     ·····························
           │
        Node C (hash=270°)

当添加/移除节点时，只影响相邻节点的数据分布
而非像取模哈希那样导致全量重新映射

**节点故障处理**：
- Memcached 节点宕机后，该节点上的缓存全部丢失
- 客户端需要实现"失败后回源"的逻辑：GET 缓存失败 → 查数据库 → 写回其他节点
- 热点 key 可以在多个节点上冗余存储（客户端同时 SET 到多个节点）

#### 高可用方案对比

| 能力 | Redis | Memcached |
|------|-------|-----------|
| 自动故障转移 | Sentinel / Cluster 支持 | 不支持（需客户端处理） |
| 数据分片 | Cluster 自动管理 | 客户端一致性哈希 |
| 节点发现 | Cluster Gossip 协议 | 配置文件/服务发现 |
| 数据冗余 | 主从复制 | 无 |
| 扩缩容 | Cluster 在线 resharding | 客户端重新映射 |
| 运维复杂度 | 较高（需要维护集群） | 较低（节点独立） |

---

### 12.5.7 性能基准对比

#### 纯 GET/SET 性能

在简单的键值对场景下，Memcached 通常略优于 Redis，主要原因是：
- Memcached 多线程模型在多核 CPU 上的天然优势
- 协议更简单，解析开销更小
- 服务端零计算，无数据结构维护开销

典型基准测试结果（参考值，实际受硬件和配置影响较大）：

测试环境：8核CPU / 32GB RAM / 网络延迟<0.1ms
Key大小：64字节 / Value大小：1KB / 100个并发连接

┌───────────────────┬──────────────┬──────────────┐
│ 操作               │ Redis 7.x    │ Memcached 1.6│
├───────────────────┼──────────────┼──────────────┤
│ 单实例 GET QPS     │ ~120,000     │ ~200,000     │
│ 单实例 SET QPS     │ ~100,000     │ ~180,000     │
│ 延迟 P99 (GET)     │ ~0.3ms       │ ~0.2ms       │
│ 内存效率(1KB值)    │ ~1.0x        │ ~0.8x        │
└───────────────────┴──────────────┴──────────────┘

注：Redis 在使用 Pipeline 和 Lua 脚本后，批量操作吞吐量
    可提升 5-10 倍，远超 Memcached 的简单批量操作。

#### Pipeline 批量操作

Redis 的 Pipeline 是性能杀手锏——它将多个命令打包发送，减少网络往返：

```python
import redis
import time

r = redis.Redis()

# 无 Pipeline：逐条发送，10000次操作需要10000次网络往返
start = time.time()
for i in range(10000):
    r.set(f'key{i}', f'value{i}')
print(f"逐条写入: {time.time()-start:.2f}s")  # 约 5-10 秒

# 有 Pipeline：打包发送，10000次操作只需1次网络往返
start = time.time()
pipe = r.pipeline(transaction=False)  # 非事务 Pipeline
for i in range(10000):
    pipe.set(f'key{i}', f'value{i}')
pipe.execute()
print(f"Pipeline写入: {time.time()-start:.2f}s")  # 约 0.1-0.3 秒
```

#### Lua 脚本

Redis 支持服务端 Lua 脚本执行，可以将多个操作原子化：

```lua
-- 分布式锁的原子化实现（SETNX + EXPIRE）
local key = KEYS[1]
local value = ARGV[1]
local ttl = tonumber(ARGV[2])

-- 原子操作：不存在则设置 + 设置过期时间
local result = redis.call('SET', key, value, 'NX', 'EX', ttl)
if result then
    return 1  -- 加锁成功
else
    return 0  -- 加锁失败
end
```

Memcached 没有类似的服务端计算能力，所有原子操作都需要通过 CAS（Check-And-Set）在客户端实现。

---

### 12.5.8 适用场景选型指南

#### 选择 Redis 的场景

Redis 最佳适用场景：

1. 复杂数据结构需求
   ├── 排行榜 / 计数器（Sorted Set）
   ├── 用户会话管理（Hash）
   ├── 消息队列（List / Stream）
   ├── 地理位置服务（GEO）
   └── 全文搜索（RediSearch 模块）

2. 需要数据持久化
   ├── 缓存数据丢失代价高
   ├── 需要重启后快速恢复
   └── 同时作为缓存和轻量级数据库

3. 需要发布订阅
   ├── 实时通知系统
   ├── 配置中心
   └── 事件驱动架构

4. 需要原子操作
   ├── 分布式锁
   ├── 原子计数器
   └── 限流器

5. 需要高可用
   ├── 不能接受缓存全量丢失
   ├── 需要自动故障转移
   └── 需要在线扩缩容

#### 选择 Memcached 的场景

Memcached 最佳适用场景：

1. 纯粹的缓存加速
   ├── 数据库查询结果缓存
   ├── 页面片段缓存（HTML碎片）
   ├── API 响应缓存
   └── 计算结果缓存

2. 对内存效率要求极高
   ├── 大量小对象存储
   ├── 需要最大化缓存容量
   └── 值大小相对均匀（减少Slab碎片）

3. 已有成熟的客户端分片方案
   ├── 架构中已使用一致性哈希
   ├── 客户端有完善的容错逻辑
   └── 团队对 Memcached 运维经验丰富

4. 对多核CPU利用率要求高
   ├── 单实例需要处理大量并发
   ├── 不想部署多个Redis实例
   └── 延迟敏感且请求简单

5. 可接受缓存丢失
   ├── 缓存数据可从数据库重建
   ├── 缓存雪崩影响可控
   └── 冷启动预热有成熟方案

#### 决策流程

技术选型决策树：

开始
  │
  ├── 需要复杂数据结构？ ──Yes──→ 选 Redis
  │
  ├── 需要数据持久化？ ──Yes──→ 选 Redis
  │
  ├── 需要发布订阅/Pub-Sub？ ──Yes──→ 选 Redis
  │
  ├── 需要原子操作/事务？ ──Yes──→ 选 Redis
  │
  ├── 需要自动故障转移/高可用？ ──Yes──→ 选 Redis
  │
  ├── 纯KV缓存 + 多核利用率优先？ ──Yes──→ 选 Memcached
  │
  ├── 值大小均匀 + 内存效率优先？ ──Yes──→ 选 Memcached
  │
  └── 无法确定 ──→ 选 Redis（生态更丰富，未来扩展性更好）

---

### 12.5.9 混合架构：Redis + Memcached

在大型系统中，两种缓存并不互斥。Facebook 是混合架构的经典案例：

Facebook 缓存架构（已公开）：

┌─────────────────────────────────────────┐
│               应用层                      │
├─────────────────────────────────────────┤
│         Memcached 层（热数据）            │
│  ├── 命中率 > 99%                       │
│  ├── 数百万个 Memcached 实例              │
│  ├── 存储最频繁访问的数据                  │
│  └── 纯KV，无需持久化                    │
├─────────────────────────────────────────┤
│           Redis 层（温数据）              │
│  ├── 存储需要排序/计数的数据               │
│  ├── 消息队列和实时功能                   │
│  ├── 需要持久化的关键缓存                  │
│  └── Pub/Sub 实时通知                    │
├─────────────────────────────────────────┤
│         持久化存储层（MySQL/TAO）          │
│  ├── 用户关系图谱                        │
│  ├── 照片、帖子等内容                     │
│  └── 事务性操作                          │
└─────────────────────────────────────────┘

请求流向：应用 → Memcached(命中？) → Redis(命中？) → 数据库

**混合架构的典型设计**：

```python
class CacheManager:
    """多级缓存管理器：L1=Memcached, L2=Redis, L3=数据库"""
    
    def __init__(self):
        self.memcached = pymemcache.Client(('mc-host', 11211))
        self.redis = redis.Redis(host='redis-host', port=6379)
    
    def get(self, key: str):
        # L1: Memcached（最快，纯KV缓存）
        value = self.memcached.get(key)
        if value:
            return json.loads(value), 'memcached'
        
        # L2: Redis（支持复杂结构，有持久化）
        value = self.redis.get(key)
        if value:
            # 回填到 L1
            self.memcached.set(key, value, expire=300)
            return json.loads(value), 'redis'
        
        # L3: 数据库
        value = self.fetch_from_db(key)
        if value:
            serialized = json.dumps(value)
            self.redis.setex(key, 3600, serialized)
            self.memcached.set(key, serialized, expire=300)
            return value, 'database'
        
        return None, 'miss'
```

---

### 12.5.10 常见误区与纠正

| 误区 | 事实 | 纠正 |
|------|------|------|
| "Redis 总比 Memcached 快" | 纯 KV 场景下 Memcached 更快 | 根据场景选择，不要一刀切 |
| "Memcached 不能用于生产" | Facebook、Twitter、Wikipedia 大量使用 | Memcached 在纯缓存场景依然是最佳选择 |
| "Redis 单线程所以性能差" | Redis 6.0+ 支持多线程 I/O，Pipeline 性能极高 | 理解"单线程"的真正含义 |
| "两者内存占用差不多" | Memcached 内存效率通常更高（无数据结构开销） | 大规模部署时内存成本差异显著 |
| "Redis 能替代所有场景" | Redis 不适合存储超大 value（>100MB 性能下降明显） | 超大文件用对象存储，不要塞 Redis |
| "Memcached 没有集群支持" | 客户端一致性哈希就是集群方案 | 集群不一定需要服务端支持 |

---

### 12.5.11 本节小结

Redis 和 Memcached 是分布式缓存领域的两大支柱。选择哪一种，不取决于"哪个更流行"，而取决于你的具体需求：

- **需要丰富数据结构、持久化、高可用、原子操作** → Redis
- **需要极致的纯 KV 缓存性能、多核利用率、内存效率** → Memcached
- **大型系统** → 混合架构，各取所长

Redis 的生态更活跃、功能更丰富，是大多数新项目的默认选择。但在大规模纯缓存场景下，Memcached 的简洁性和性能依然不可替代。理解两者的架构差异，才能在实际工程中做出最优决策。
