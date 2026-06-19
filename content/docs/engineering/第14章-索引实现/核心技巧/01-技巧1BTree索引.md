---
title: "技巧1 B+Tree索引"
type: docs
weight: 1
---
## 技巧1 B+Tree索引——从原理到工程实践的完整指南

B+Tree索引是关系数据库中最核心、最广泛使用的索引结构。MySQL InnoDB的聚簇索引、PostgreSQL的默认索引、Oracle的索引组织表，都以B+Tree为底层数据结构。掌握B+Tree的实现原理与工程技巧，是理解数据库性能优化的基石。

本篇将从数据结构原理出发，逐步深入到节点分裂、并发控制、磁盘布局、性能调优等工程实践层面，帮助读者建立对B+Tree索引的完整认知。

---

### 1. 为什么是B+Tree——索引结构的选择逻辑

在选择索引数据结构之前，需要理解一个核心约束：**数据库索引存储在磁盘上，磁盘I/O是最大的性能瓶颈**。

#### 1.1 磁盘I/O的代价模型

现代磁盘的典型参数：

| 操作类型 | HDD延迟 | SSD延迟 | 说明 |
|----------|---------|---------|------|
| 顺序读 | 0.01ms/MB | 0.001ms/MB | 大块连续读取 |
| 随机读（4KB页） | 5-10ms | 0.05-0.1ms | 单次页面访问 |
| 顺序写 | 0.02ms/MB | 0.002ms/MB | 大块连续写入 |
| 随机写（4KB页） | 8-15ms | 0.1-0.5ms | 涉及擦除和写入 |

关键结论：**单次随机I/O的代价是顺序I/O的数百倍**。因此索引设计的核心目标是——**最小化随机I/O次数**。

#### 1.2 各数据结构的I/O对比

假设存储1亿条记录，每条记录的键值对约100字节：

| 数据结构 | 树高/层数 | 查询I/O次数 | 范围查询 | 写入代价 |
|----------|-----------|-------------|----------|----------|
| 二叉搜索树（BST） | ~27层 | 27次 | 需要中序遍历 | O(log N) |
| 红黑树（内存平衡树） | ~27层 | 27次 | 需要中序遍历 | O(log N) |
| B+Tree（扇出500） | 3层 | 3次 | 沿叶子链表顺序扫描 | O(log_m N) |
| Hash索引 | 1-2层 | 1-2次 | 不支持 | O(1)均摊 |

B+Tree的核心优势：
- **高扇出（Fanout）**：每个节点存储数百个键值，树高极低
- **叶子链表**：天然支持范围查询和排序
- **磁盘友好**：节点大小与磁盘页对齐，一次I/O读取整个节点
- **稳定性**：最坏情况和平均情况的性能差距很小

#### 1.3 B+Tree vs B-Tree

B+Tree是B-Tree最重要的变体，两者的关键差异：

B-Tree：数据分布在所有节点
┌─────────┐
│ K1 | K2 │  ← 非叶子节点也存数据
└────┬──┬─┘
     │  │
  ┌──┘  └──┐
┌──┐    ┌──┐
│K3│    │K4│  ← 叶子节点也存数据
└──┘    └──┘

B+Tree：数据只在叶子节点
┌─────────┐
│ K1 | K2 │  ← 非叶子节点只存键+指针
└────┬──┬─┘
     │  │
  ┌──┘  └──┐
┌─────────────┐  ←──┐
│K3|V3|K4|V4│     │  叶子节点存数据
└──────────┬──┘  │  且通过链表串联
┌─────────────┐  │
│K5|V5|K6|V6│←─┘
└─────────────┘

B+Tree相比B-Tree的三个关键改进：

1. **数据集中在叶子节点**：非叶子节点更小，扇出更高，树高更低
2. **叶子节点通过链表串联**：范围查询只需沿链表顺序扫描
3. **所有查询路径等长**：从根到叶的路径长度一致，查询性能稳定

---

### 2. B+Tree节点结构与磁盘布局

#### 2.1 页面格式设计

B+Tree的每个节点对应磁盘上的一个页面（Page）。以PostgreSQL（默认页大小8KB）为例：

┌──────────────────────────────────────┐
│           Page Header (24 bytes)      │
│  ┌─ page_type: INTERNAL/LEAF         │
│  ├─ lsn: 最后修改的WAL序列号         │
│  ├─ lower: 空闲空间起始偏移           │
│  └─ upper: 空闲空间结束偏移           │
├──────────────────────────────────────┤
│     Item Pointers (槽位数组)          │
│  ┌─ pointer_0: offset | length       │
│  ├─ pointer_1: offset | length       │
│  ├─ ...                              │
│  └─ pointer_N: offset | length       │
├──────────────────────────────────────┤
│           Free Space                 │
├──────────────────────────────────────┤
│     Tuple Data (从尾部向前增长)       │
│  ┌─ key_0 | value_0                  │
│  ├─ key_1 | value_1                  │
│  ├─ ...                              │
│  └─ key_N | value_N                  │
├──────────────────────────────────────┤
│     Special Space (索引特定元数据)    │
└──────────────────────────────────────┘

这种**"两端向中间增长"**的设计使得页面内的记录可以高效插入和删除，不需要整体移动数据。

#### 2.2 内部节点 vs 叶子节点

内部节点和叶子节点的存储格式不同：

**内部节点**：存储键值和子节点指针（在磁盘上是页号）

内部节点布局：
┌──────────────────────────────────────────────┐
│ [P0] [K1] [P1] [K2] [P2] [K3] [P3] ... [Kn] [Pn] │
└──────────────────────────────────────────────┘
  P0: 指向键值 < K1 的子树
  Pi: 指向 Ki < 键值 ≤ Ki+1 的子树
  Pn: 指向键值 > Kn 的子树

**叶子节点**：存储键值对和叶子链表指针

叶子节点布局：
┌──────────────────────────────────────────────────┐
│ [Header] [K1|V1] [K2|V2] ... [Kn|Vn] [NextPtr]   │
└──────────────────────────────────────────────────┘
  NextPtr: 指向下一个叶子节点（用于范围扫描）
  V: 在聚簇索引中是数据行，在二级索引中是主键值

#### 2.3 扇出与树高的关系

B+Tree的扇出（每个节点的最大子节点数）直接决定了树的高度。扇出由页面大小和键值大小决定：

扇出 = 页面大小 / (键值大小 + 指针大小)

示例：
  页面大小 = 8KB (PostgreSQL)
  键 = BIGINT (8 bytes) + 主键指针 (8 bytes) = 16 bytes
  扇出 = 8192 / 16 = 512

  页面大小 = 16KB (InnoDB)
  键 = BIGINT (8 bytes) + 6字节指针 = 14 bytes
  扇出 ≈ 16384 / 14 ≈ 1170

扇出与存储容量的对照表：

| 扇出 | 树高3层 | 树高4层 | 树高5层 |
|------|---------|---------|---------|
| 100 | 100万条 | 1亿条 | 100亿条 |
| 500 | 1.25亿条 | 625亿条 | — |
| 1000 | 10亿条 | 1万亿条 | — |

**关键结论**：对于扇出为500的B+Tree，4层可以存储超过600亿条记录。任何查询最多只需要4次磁盘I/O——这就是B+Tree高效的根本原因。

---

### 3. B+Tree核心操作详解

#### 3.1 搜索操作

搜索从根节点开始，在每一层通过二分查找确定进入的子节点，直到到达叶子节点：

FUNCTION BPlusTree_Search(root, search_key):
    node = root
    
    // 从根到叶，逐层二分查找
    WHILE node.type != LEAF:
        // 在内部节点中二分查找，确定走哪个子节点
        i = BinarySearch(node.keys, search_key)
        node = ReadPage(node.children[i])
    
    // 在叶子节点中精确查找
    i = BinarySearch(node.keys, search_key)
    IF i < node.num_keys AND node.keys[i] == search_key:
        RETURN node.values[i]
    ELSE:
        RETURN NOT_FOUND

**性能分析**：
- 每一层做一次二分查找：O(log m)，m为扇出
- 总层数：O(log_m N)，N为总记录数
- 总I/O次数：等于树高，通常3-4次

**实际示例**（以PostgreSQL为例）：

```sql
-- 创建测试表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- B+Tree索引自动在email列上建立
-- 查看索引结构
SELECT * FROM pg_stat_user_indexes 
WHERE tablename = 'users';

-- 使用EXPLAIN ANALYZE观察索引搜索
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM users WHERE email = 'alice@example.com';
-- 输出中 Buffers: shared hit=3 表示只需3次页面读取
```

#### 3.2 插入操作与节点分裂

插入操作首先搜索到目标叶子节点，然后插入键值对。如果叶子节点已满（空间不足），需要进行**分裂（Split）**：

FUNCTION BPlusTree_Insert(root, key, value):
    // 1. 搜索到目标叶子节点
    path = SearchWithPath(root, key)
    leaf = path.leaf
    
    // 2. 尝试插入
    InsertIntoLeaf(leaf, key, value)
    
    // 3. 如果未满，完成
    IF leaf.num_keys <= MAX_KEYS:
        RETURN
    
    // 4. 叶子已满，需要分裂
    new_leaf = AllocatePage()
    mid = leaf.num_keys / 2
    
    // 将后半部分记录移动到新节点
    CopyKeys(leaf, mid, leaf.num_keys, new_leaf)
    leaf.num_keys = mid
    
    // 维护叶子链表
    new_leaf.next = leaf.next
    leaf.next = new_leaf.page_id
    
    // 5. 将新节点的最小键提升到父节点
    push_up_key = new_leaf.keys[0]
    InsertIntoParent(path, leaf, push_up_key, new_leaf)

**分裂过程的可视化**：

分裂前（叶子节点已满，假设最大容量为4）：
┌──────────────────────────┐
│ K1 | K2 | K3 | K4 | K5   │  ← 新插入K5导致溢出
└──────────────────────────┘

分裂后（中间键提升到父节点）：
┌────────────────┐    ┌────────────────┐
│ K1 | K2 | K3   │ →  │ K4 | K5        │
└────────────────┘    └────────────────┘
    原节点(左)            新节点(右)
         ↑
    父节点插入分隔键 K4

**父节点也可能需要分裂**：如果父节点也满了，分裂会递归向上传播，直到根节点。如果根节点分裂，树的高度增加1：

根节点分裂：
                    [Root]          分裂前
                   /  |  \
                 A    B    C

                    [K2]           分裂后，树高+1
                   / |  \
                 A   B   C   D

**分裂操作的均摊分析**：虽然最坏情况下需要从叶子分裂到根，但每次分裂将一个节点变为两个，下次分裂至少需要插入MAX_KEYS/2个键值才能填满，因此分裂操作的均摊代价为O(1)。

#### 3.3 删除操作与节点合并

删除操作比插入更复杂，因为需要处理节点**下溢（Underflow）**——节点的键值数量低于最小要求：

FUNCTION BPlusTree_Delete(root, key):
    // 1. 搜索到目标叶子节点
    path = SearchWithPath(root, key)
    leaf = path.leaf
    
    // 2. 从叶子节点删除
    DeleteFromLeaf(leaf, key)
    
    // 3. 如果叶子键数量足够，完成
    IF leaf.num_keys >= MIN_KEYS:
        UpdateSeparatorIfNecessary(path)
        RETURN
    
    // 4. 尝试从兄弟节点借键值（重分配）
    sibling = GetLeftSibling(path) OR GetRightSibling(path)
    IF sibling.num_keys > MIN_KEYS:
        RedistributeKeys(leaf, sibling)
        UpdateSeparatorIfNecessary(path)
        RETURN
    
    // 5. 兄弟也没有多余键值，合并
    MergeNodes(leaf, sibling)
    DeleteFromParent(path)

**删除操作的三种情况**：

情况1：删除后键数量充足 → 无额外操作
┌──────────┐
│ K1 | K2 | K3 | K4 │  删除K2后
└──────────┘
  ↓
┌──────────┐
│ K1 | K3 | K4 │      仍满足最小键数要求
└──────────┘

情况2：重分配（从兄弟借一个键）
┌────────┐  ┌────────┐
│ K1 | K2│  │K3|K4|K5│  ← 兄弟有多余
└────────┘  └────────┘
  删除K2后：   借K3过来
┌──────────┐  ┌───────┐
│ K1 | K3  │  │K4 | K5│
└──────────┘  └───────┘

情况3：合并（两个节点合并为一个）
┌──────────┐  ┌───────┐
│ K1 | K2  │  │K3|K4  │  ← 兄弟也没多余
└──────────┘  └───────┘
  合并后：
┌─────────────────┐
│ K1 | K2 | K3|K4 │  ← 父节点中对应的分隔键被删除
└─────────────────┘

**懒删除策略**：PostgreSQL等系统采用"懒删除"策略——删除操作不立即合并节点，而是将删除的记录标记为"dead"，在后续的VACUUM操作中统一清理。这样减少了删除操作的I/O开销，但增加了空间占用。

---

### 4. 并发控制：Crabbing与Lock Coupling

在并发环境下，多个线程可能同时对B+Tree进行读写操作。分裂和合并操作会修改多个页面，如果不加控制，可能导致指针失效、数据丢失或结构损坏。

#### 4.1 同步原语：Latch vs Lock

理解B+Tree并发控制的前提是区分两种同步机制：

| 特性 | Latch（闩锁） | Lock（锁） |
|------|---------------|------------|
| 保护对象 | 内存中的数据结构（页面） | 逻辑记录（事务级） |
| 持有时间 | 微秒级 | 事务级别（毫秒到秒） |
| 死锁处理 | 通过编程约定避免 | 有完整的死锁检测 |
| 实现方式 | 读写锁（RWLock） | 事务锁管理器 |
| 典型场景 | B+Tree页面访问 | 行级数据修改 |

#### 4.2 Basic Crabbing算法

Crabbing（螃蟹式移动）的核心思想：从根到叶搜索时，每向下移动一层，先获取子节点的Latch，确认安全后再释放父节点的Latch。

FUNCTION Crabbing_Search(root, key):
    path = []
    
    // 获取根节点的读Latch
    Latch(root, READ)
    path.push(root)
    
    node = root
    WHILE node.type != LEAF:
        child = FindChild(node, key)
        Latch(child, READ)
        
        // 检查子节点是否"安全"
        IF IsSafe(child, READ):
            // 安全：释放路径上所有祖先的Latch
            FOR EACH ancestor IN path:
                Unlatch(ancestor)
            path = []
        
        path.push(child)
        node = child
    
    // 在叶子节点中搜索
    result = SearchLeaf(node, key)
    
    FOR EACH n IN path:
        Unlatch(n)
    RETURN result

**"安全"的定义**：
- 对于搜索操作：节点没有溢出或下溢就是安全的
- 对于插入操作：节点有足够空间（num_keys < MAX_KEYS - 1）就是安全的
- 对于删除操作：节点键数量超过最小要求（num_keys > MIN_KEYS + 1）就是安全的

**Crabbing搜索的可视化**：

搜索键 K=25，从根到叶：

步骤1: Latch(根节点) ✓        [10|20|30]
步骤2: Latch(中间节点) ✓      [10|20] → 安全，释放根节点
步骤3: Latch(叶子节点) ✓      [22|25|28] → 安全，释放中间节点
步骤4: 在叶子中找到 K=25

当前持有Latch数：1（仅叶子节点）

#### 4.3 乐观-悲观两阶段优化

Basic Crabbing在每次搜索时都需要获取多个Latch。优化策略是采用**乐观-悲观两阶段**：

FUNCTION Optimistic_Search(root, key):
    // 阶段1：乐观搜索（不加任何Latch）
    node = root
    WHILE node.type != LEAF:
        parent = node
        node = FindChild(node, key)
    
    // 获取叶子节点的Latch并验证
    Latch(node, READ)
    IF IsLeafValid(node, key):
        result = SearchLeaf(node, key)
        Unlatch(node)
        RETURN result
    
    // 阶段2：回退到悲观搜索（使用Crabbing）
    Unlatch(node)
    RETURN Crabbing_Search(root, key)

**为什么乐观搜索在大多数情况下有效？**

B+Tree的分裂和合并是罕见事件。在一个稳定的B+Tree中，一次搜索在向下遍历过程中遇到节点分裂的概率极低。根据Lehman & Yao的不变量，只要最终到达了正确的叶子节点，搜索结果就是正确的。

**性能提升**：在只读工作负载下，乐观搜索可以将搜索延迟降低50-70%，因为完全避免了Latch的获取和释放开销。

#### 4.4 并发插入的Latch顺序

为了避免死锁，PostgreSQL规定了严格的Latch获取顺序：**从上到下（父 → 子）**。

正确的Latch获取顺序：
  1. Parent page (Exclusive Latch)
  2. Current page (Exclusive Latch)
  3. New page (Exclusive Latch) ← 如果需要分配新页面

违反此顺序可能导致循环等待 → 死锁

**PostgreSQL的nbtree并发策略**：

PostgreSQL采用"高键（High Key）"机制支持Lehman-Yao风格的无Latch搜索。每个页面存储一个高键（该页面负责的键范围的上界）。搜索时，如果目标键超过高键，说明该页面已分裂，需要沿叶子链表找到正确的页面。

```sql
-- 观察PostgreSQL的B+Tree并发行为
-- 窗口1：长时间运行的写事务
BEGIN;
UPDATE users SET email = 'new@example.com' WHERE id = 1;
-- 不提交，持有行锁

-- 窗口2：同时进行的搜索（不会被阻塞）
SELECT * FROM users WHERE id = 2;
-- B+Tree搜索使用Latch（微秒级），不受行锁影响
```

---

### 5. 磁盘布局优化技术

#### 5.1 前缀压缩（Prefix Compression）

在B+Tree的内部节点中，相邻键值通常有较长的共同前缀。前缀压缩只存储与前一个键的不同部分：

原始键值：
  "www.example.com"
  "www.example.org"
  "www.test.com"

前缀压缩后：
  "www.example.com"     ← 第一个键完整存储
  "\x03org"             ← 只存储不同后缀（共同前缀3字节）
  "\x04test.com"        ← 只存储不同后缀（共同前缀4字节）

空间节省：46 bytes → 24 bytes（节省48%）

**重启点（Restart Point）**：由于前缀压缩使随机访问困难（要解码第N个键必须先解码前面所有键），每隔K个键设置一个重启点，从该点开始存储完整键值，以便支持二分查找：

键序列：[k1, k2, k3, k4, k5, k6, k7, k8]
重启间隔=3

存储布局：
[k1完整][k2压缩][k3压缩] | [k4完整][k5压缩][k6压缩] | [k7完整][k8压缩]

查找k7的步骤：
  1. 在重启点中二分查找 → 找到重启点2
  2. 从k7开始顺序扫描

#### 5.2 差值编码（Delta Encoding）

对于数值型键值，存储相邻键的差值而非完整值。差值通常很小，可以用变长整数（Varint）编码：

原始键值：  1000   1005   1012   1020   1025
差值编码：  1000   5      7      8      5

Varint编码（每个字节的最高位为继续标志）：
  1000 → [0x08 0x68]（2字节）
  5    → [0x05]（1字节）
  7    → [0x07]（1字节）

对比：原始值需要4字节 × 5 = 20字节
      差值编码只需 2+1+1+1+1 = 6字节（节省70%）

#### 5.3 页面预取（Prefetching）

范围查询时，顺序访问叶子节点链表，可以通过预取隐藏磁盘I/O延迟：

预取策略：
  当处理当前叶子节点时，异步发出对下一个（或下N个）叶子节点的读请求

  时间线：
  [处理Leaf 1] [处理Leaf 2] [处理Leaf 3] [处理Leaf 4]
  [异步读Leaf 2] [异步读Leaf 3] [异步读Leaf 4]
  
  异步读取与计算重叠 → I/O延迟被隐藏

在PostgreSQL中，可以通过调整`seq_page_cost`和`random_page_cost`参数影响优化器的预取决策。MySQL InnoDB则支持通过`innodb_read_ahead_threshold`控制预读行为。

#### 5.4 Bulk Loading（批量构建）

为已有表创建索引时，逐条插入的效率很低。Bulk Loading是一种高效的批量构建方法——排序后逐页填充，每个节点只写入一次：

逐条插入：O(N × log_m N) 次I/O
Bulk Loading：O(N/B) 次I/O（B为每页记录数）

示例：1亿条记录，B=500
  逐条插入：约 1亿 × 4 = 4亿次I/O
  Bulk Loading：约 1亿 / 500 = 20万次I/O
  性能差距：约2000倍

```sql
-- PostgreSQL的CREATE INDEX默认使用Bulk Loading
CREATE INDEX idx_users_email ON users(email);
-- 执行过程中会先对数据排序，然后逐页填充B+Tree
-- 可以通过CREATE INDEX CONCURRENTLY避免锁表
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
```

---

### 6. B+Tree在主流数据库中的实现差异

#### 6.1 MySQL InnoDB

InnoDB的B+Tree实现有以下特点：

**聚簇索引**：InnoDB使用主键作为聚簇索引，数据行直接存储在聚簇索引的叶子节点中。二级索引的叶子节点存储的是主键值，需要通过主键"回表"获取完整行数据。

InnoDB索引结构：

聚簇索引（主键B+Tree）：
  叶子节点 → 完整行数据

二级索引（如idx_email）：
  叶子节点 → (email值, 主键id)
                ↓ 回表查询
  聚簇索引叶子节点 → 完整行数据

```sql
-- InnoDB的索引大小限制
-- 单个索引键的最大长度为3072字节
-- 需要innodb_large_prefix=ON且ROW_FORMAT=DYNAMIC

-- 查看InnoDB索引信息
SELECT 
    index_name, 
    column_name, 
    seq_in_index,
    cardinality
FROM information_schema.STATISTICS
WHERE table_name = 'users'
ORDER BY index_name, seq_in_index;
```

**自适应哈希索引（AHI）**：InnoDB自动监控B+Tree的搜索模式，对频繁访问的页面在内存中建立哈希索引，将O(log N)的搜索加速为O(1)。

```sql
-- 查看AHI的使用状态
SHOW ENGINE INNOODB STATUS\G
-- 在"SEMAPHORES"部分查看哈希表的大小和命中率
```

#### 6.2 PostgreSQL

PostgreSQL的B+Tree实现（nbtree）与InnoDB有几个关键差异：

**非聚簇索引**：PostgreSQL不使用聚簇索引（CLUSTER命令只是物理重排，不是持续维护的）。所有索引的叶子节点都存储指向数据行的TID（页面号 + 槽位号）。

PostgreSQL索引结构：

B+Tree叶子节点 → (key, tid)
                       ↓
数据页面: ItemPointers[slot_id] → 实际行数据

所有索引访问模式相同，都需要一次额外的页面访问

```sql
-- PostgreSQL的Index-Only Scan（等效于覆盖索引）
CREATE INDEX idx_orders_covering 
ON orders(user_id, status) INCLUDE (amount);

EXPLAIN (ANALYZE, BUFFERS)
SELECT user_id, status, amount FROM orders WHERE user_id = 100;
-- Extra: Index Only Scan（如果所需数据全在索引中）
-- Buffers: shared hit=2（只需读取索引页面，无需访问数据页面）
```

**并发布局**：PostgreSQL的nbtree采用高键（High Key）机制和乐观搜索，支持高并发读操作。写操作通过右分割（Right-Split）策略——新记录总是尝试插入到最右叶子节点，减少了分裂时的Latch竞争。

#### 6.3 SQLite

SQLite的B-Tree实现更简洁，但有一些独特设计：

- **单文件存储**：整个数据库是一个文件，B+Tree的页面直接对应文件中的4KB页面
- **变长记录**：支持高效的变长键值存储
- **溢出页面**：超过单个页面大小的记录存储在溢出页面链中
- **自动VACUUM**：删除操作后自动回收页面空间

---

### 7. B+Tree性能诊断与调优

#### 7.1 索引膨胀与碎片化

频繁的插入和删除操作会导致B+Tree的页面碎片化——页面使用率下降，浪费磁盘空间和缓存空间。

```sql
-- PostgreSQL：检查索引膨胀
SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size,
    round(100 * (1 - 
        (SELECT avg_leaf_density) 
        FROM pgstatindex(indexname::regclass)
    ), 2) AS bloat_pct
FROM pg_stat_user_indexes
WHERE tablename = 'orders';

-- PostgreSQL：重建索引消除碎片
REINDEX INDEX idx_orders_user_time;
-- 或在线重建（不阻塞写入）
REINDEX INDEX CONCURRENTLY idx_orders_user_time;
```

```sql
-- MySQL InnoDB：检查索引碎片
SELECT
    table_name,
    index_name,
    stat_value * @@innodb_page_size AS index_size_bytes,
    (stat_value * @@innodb_page_size) / 1024 / 1024 AS index_size_mb
FROM mysql.innodb_index_stats
WHERE table_name = 'orders' AND stat_name = 'size';

-- MySQL：优化表（重建索引）
ALTER TABLE orders ENGINE=InnoDB;  -- 重建表和所有索引
-- 或使用OPTIMIZE TABLE
OPTIMIZE TABLE orders;
```

#### 7.2 未使用索引的识别

```sql
-- PostgreSQL：找出未使用的索引
SELECT
    indexrelname AS index_name,
    relname AS table_name,
    idx_scan AS scans,  -- 索引扫描次数
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0  -- 从未被使用
ORDER BY pg_relation_size(indexrelid) DESC;

-- MySQL：找出未使用的索引
SELECT
    object_schema,
    object_name,
    index_name
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE index_name IS NOT NULL
  AND count_star = 0  -- 从未被使用
  AND object_schema = 'your_database';
```

#### 7.3 缓存命中率

```sql
-- PostgreSQL：索引缓存命中率
SELECT
    indexrelname AS index_name,
    idx_blks_hit AS cache_hit,
    idx_blks_read AS disk_read,
    ROUND(idx_blks_hit::numeric / 
          NULLIF(idx_blks_hit + idx_blks_read, 0) * 100, 2) AS hit_ratio
FROM pg_statio_user_indexes
WHERE relname = 'orders';

-- 命中率 < 95% 说明缓存不足，需要增加shared_buffers或缩小索引
```

```sql
-- MySQL InnoDB：Buffer Pool命中率
SHOW ENGINE INNOODB STATUS\G
-- 查看 BUFFER POOL AND MEMORY 部分
-- "Buffer pool hit rate" 应该 > 99%
```

---

### 8. 常见误区与纠正

#### 误区一：给每个WHERE列都建单列索引

错误做法：
CREATE INDEX idx_user ON orders(user_id);
CREATE INDEX idx_status ON orders(status);
CREATE INDEX idx_time ON orders(created_at);

-- 查询：WHERE user_id = ? AND status = ? ORDER BY created_at
-- 结果：Index Merge，无法利用排序，性能差

正确做法：
CREATE INDEX idx_user_status_time ON orders(user_id, status, created_at);
-- 一条联合索引同时覆盖过滤和排序

**根因**：多个单列索引只能通过Index Merge取交集，效率远不如一条设计合理的联合索引。

#### 误区二：UUID作为主键性能一样好

自增主键的插入：顺序追加，几乎不发生页面分裂
  [Page1: 1,2,3,4,5] → [Page1: 1,2,3,4,5] + [Page2: 6,7]
  只需要在末尾追加

UUID主键的插入：随机插入，频繁触发页面分裂
  [Page1: aaa,bbb,ccc,ddd] + 插入eee(随机位置)
  → 可能需要分裂Page1，将部分数据移到新页面
  → 写放大严重，页面碎片率高

**解决方案**：使用UUID v7（基于时间戳的有序UUID）或ULID，兼顾唯一性和插入顺序性。

#### 误区三：EXPLAIN显示使用了索引就万事大吉

-- 看似使用了索引，实际效果很差
EXPLAIN SELECT * FROM orders WHERE user_id > 0;
-- type: range, key: idx_user_id
-- 但 rows: 5000000, Extra: Using where
-- → 几乎扫描了整个索引，还不如全表扫描

-- 真正有效的索引使用
EXPLAIN SELECT * FROM orders WHERE user_id = 100;
-- type: ref, rows: 150, key: idx_user_id
-- → 精确定位，高效查询

**关键指标**：不仅要看`key`（是否使用了索引），还要看`rows`（扫描行数）和`Extra`（是否回表、是否排序）。

#### 误区四：聚簇索引一定比二级索引快

场景：范围查询返回大量数据

聚簇索引范围查询：
  扫描叶子节点（顺序I/O）→ 直接获取数据行 → 高效

二级索引+回表：
  扫描二级索引叶子 → 对每条记录回表到聚簇索引 → 随机I/O
  → 如果返回行数很多，随机I/O的开销可能超过顺序扫描

**经验法则**：如果查询返回超过表总行数的10-20%，全表扫描可能比二级索引+回表更高效。

---

### 9. 实用SQL速查表

#### 9.1 索引信息查询

```sql
-- PostgreSQL
-- 查看所有索引及其大小
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS size
FROM pg_stat_user_indexes
JOIN pg_indexes USING (schemaname, tablename, indexname)
ORDER BY pg_relation_size(indexname::regclass) DESC;

-- 查看索引列定义
SELECT
    indexname,
    array_agg(attname ORDER BY array_position(indkey, attid)) AS columns
FROM pg_stat_user_indexes
JOIN pg_index ON indexrelid = pg_stat_user_indexes.indexrelid
JOIN pg_attribute ON attrelid = pg_stat_user_indexes.indrelid
WHERE attnum = ANY(indkey)
GROUP BY indexname;

-- MySQL
-- 查看索引信息
SHOW INDEX FROM orders;
SELECT
    index_name,
    column_name,
    seq_in_index,
    non_unique
FROM information_schema.STATISTICS
WHERE table_name = 'orders'
ORDER BY index_name, seq_in_index;
```

#### 9.2 EXPLAIN解读速查

```sql
-- PostgreSQL EXPLAIN关键字段
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM users WHERE email = 'test@example.com';

-- type/access方法：
--   Index Scan     → 索引扫描 + 回表
--   Index Only Scan → 纯索引扫描（覆盖索引，无回表）
--   Bitmap Index Scan → 位图索引扫描（多条件组合）
--   Seq Scan       → 全表扫描

-- Buffers字段：
--   shared hit  → 从缓存读取（快）
--   shared read → 从磁盘读取（慢）

-- MySQL EXPLAIN关键字段
EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';

-- type字段（从快到慢）：
--   system > const > eq_ref > ref > range > index > ALL
-- key字段：实际使用的索引
-- rows：预估扫描行数（越小越好）
-- Extra：
--   Using index      → 覆盖索引
--   Using where      → 需要额外过滤
--   Using filesort   → 需要额外排序（性能杀手）
--   Using temporary  → 使用临时表（性能杀手）
```

---

### 10. 设计B+Tree索引的决策框架

索引设计决策流程：

1. 分析查询模式
   ├── 高频查询的WHERE条件有哪些？
   ├── 需要范围查询还是等值查询？
   ├── 是否需要ORDER BY？
   └── 查询返回哪些列？

2. 确定索引类型
   ├── 等值查询 → 联合索引（高区分度列在前）
   ├── 等值+范围 → 等值列在前，范围列在后
   ├── 排序需求 → ORDER BY列追加到索引末尾
   └── 覆盖查询 → 将SELECT列追加到索引末尾（或用INCLUDE）

3. 评估维护开销
   ├── 索引数量：不超过5-8个/表
   ├── 写入频率：写密集型减少索引数量
   └── 索引大小：关注Buffer Pool占用

4. 验证效果
   ├── EXPLAIN确认索引被使用
   ├── 观察rows和Buffers
   ├── 对比优化前后的查询延迟
   └── 定期审查未使用的索引

| 查询模式 | 推荐索引 | 示例 |
|----------|----------|------|
| `WHERE a = ?` | 单列索引 | `INDEX(a)` |
| `WHERE a = ? AND b = ?` | 联合索引 | `INDEX(a, b)` |
| `WHERE a = ? AND b = ? ORDER BY c` | 联合索引 | `INDEX(a, b, c)` |
| `WHERE a = ? AND b > ?` | 联合索引 | `INDEX(a, b)` |
| `SELECT a, b FROM t WHERE c = ?` | 覆盖索引 | `INDEX(c) INCLUDE(a, b)` |
| `WHERE a LIKE 'abc%'` | 前缀索引 | `INDEX(a)` |
| `WHERE YEAR(d) = 2024` | 函数索引 | `INDEX(YEAR(d))` |

---

### 本篇小结

B+Tree索引之所以成为关系数据库的标配索引结构，源于三个核心优势：

1. **低树高**：高扇出保证3-4层即可覆盖数十亿记录，查询只需3-4次磁盘I/O
2. **范围查询**：叶子节点链表天然支持有序范围扫描
3. **稳定性**：最坏情况和平均情况的性能差距极小

工程实践中需要关注的关键技术点：

- **节点分裂**：理解分裂传播的机制，避免频繁分裂导致的性能抖动
- **并发控制**：掌握Crabbing算法的原理，合理选择乐观/悲观策略
- **空间优化**：利用前缀压缩和差值编码提高页面使用率
- **碎片管理**：定期监控索引碎片率，适时进行REINDEX
- **联合索引设计**：遵循最左前缀原则，等值列在前、范围列在后

掌握这些技术，才能在实际项目中设计出高效、可靠的B+Tree索引策略。
