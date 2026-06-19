---
title: "第16章-查询优化"
type: docs
weight: 16
---
# 第十六章 查询优化

## 章节概览

查询优化是数据库系统中最具技术深度的子系统之一。当用户提交一条SQL语句后，数据库需要在众多语义等价的执行计划中选择一个代价最低的方案。这个看似简单的目标背后，涉及关系代数理论、代价估算模型、统计信息管理、搜索算法等多个领域的知识。

查询优化的核心问题可以表述为：给定一个关系代数表达式，如何将其转换为一个物理执行计划，使得执行代价最小？这个问题的复杂性在于：(1) 搜索空间巨大——对于n个表的连接，可能的执行计划数量是阶乘级的；(2) 代价估算依赖统计信息，而统计信息本身是近似的；(3) 不同操作的物理实现算法在不同数据特征下有不同的性能表现。

本章将系统介绍查询优化的完整技术栈：从SQL解析到执行计划生成的全流程，代数优化的等价变换规则，基于代价的优化（CBO）的核心机制——代价模型、统计信息、选择性估计，各种连接算法的原理与适用场景，连接顺序优化的动态规划方法，以及物化执行与流水线执行两种执行模型。同时，本章还将深入分析PostgreSQL和MySQL两大主流数据库的查询优化器实现，探讨Hint机制与计划稳定性，以及自适应查询优化和基于机器学习的优化等前沿方向。

通过本章学习，读者将能够：理解查询优化器的内部工作机制；解读和分析EXPLAIN输出；在实际项目中诊断和解决查询性能问题；理解不同数据库优化器设计的权衡与取舍。

***

**关键词：** 查询优化、代价模型、统计信息、连接算法、动态规划、选择性估计、EXPLAIN、Volcano模型

**前置知识：** 关系代数基础、第十三章关系型数据库架构、第十四章索引实现

**参考文献：**
- Selinger, P.G. et al. "Access Path Selection in a Relational Database Management System." ACM SIGMOD, 1979.
- Graefe, G. "Volcano—An Extensible and Parallel Query Evaluation System." IEEE TKDE, 1994.
- Leis, V. et al. "How Good Are Query Optimizers, Really?" VLDB, 2015.


***

# 查询优化：理论基础

## 16.1 查询处理流程概述

数据库接收到一条SQL语句后，需要经过一系列处理阶段才能返回结果。整个查询处理流程可以分为四个主要阶段：

SQL语句
  │
  ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ 解析器   │────▶│ 重写器   │────▶│ 优化器   │────▶│ 执行器   │
│ Parser  │     │ Rewriter│     │Optimizer│     │ Executor│
└─────────┘     └─────────┘     └─────────┘     └─────────┘
  词法分析        规则重写        代价估算        计划执行
  语法分析        视图展开        计划搜索        结果返回
  语义检查        约束展开        计划选择

### 16.1.1 解析阶段（Parsing）

解析阶段将SQL文本转换为内部表示——查询树（Query Tree）或查询图（Query Graph）。这一阶段包含三个子步骤：

**词法分析（Lexical Analysis）**：将SQL文本分割为Token流。例如`SELECT * FROM orders WHERE id = 1`被分割为`[SELECT, *, FROM, orders, WHERE, id, =, 1]`。词法分析器通常基于有限状态自动机实现，需要处理关键字与标识符的区分、字符串字面量、数值常量等。

**语法分析（Syntactic Analysis）**：根据SQL语法规则（通常用BNF或上下文无关文法描述）将Token流构建为语法树。语法分析器通常采用递归下降法或LR分析法。PostgreSQL使用Bison生成的LALR(1)分析器，而一些现代数据库则采用手写的递归下降分析器以获得更好的错误提示。

**语义检查（Semantic Analysis）**：验证语法树的语义正确性。包括：
- 表名和列名是否存在（数据字典查询）
- 数据类型是否兼容（类型检查与隐式转换）
- 聚合函数的使用是否合法（不能在WHERE子句中直接使用聚合）
- 权限检查

解析完成后，得到一棵查询树，其结构大致如下：

查询树示例：SELECT d.name, COUNT(*) FROM employees e JOIN departments d
            ON e.dept_id = d.id WHERE e.salary > 50000 GROUP BY d.name

        [Projection: d.name, COUNT(*)]
                    │
        [Group By: d.name]
                    │
        [Selection: e.salary > 50000]
                    │
        [Join: e.dept_id = d.id]
               /              \
    [Scan: employees e]   [Scan: departments d]

### 16.1.2 重写阶段（Rewriting）

查询重写器基于一组等价变换规则对查询树进行语义保持的变换。重写的目的包括：

**视图展开**：将查询中引用的视图替换为其定义的子查询。

**子查询转换**：将某些子查询转换为连接操作。例如：

```sql
-- 原始查询（子查询）
SELECT * FROM orders WHERE customer_id IN (SELECT id FROM customers WHERE country = 'CN');

-- 重写后（Semi-Join）
SELECT orders.* FROM orders SEMI-JOIN customers ON orders.customer_id = customers.id
WHERE customers.country = 'CN';
```

**常量折叠（Constant Folding）**：在编译期计算常量表达式。例如`WHERE 1 = 1 AND x > 3 + 4`被简化为`WHERE x > 7`。

**谓词化简（Predicate Simplification）**：利用恒真/恒假条件简化查询。例如`WHERE x > 5 AND x > 3`被简化为`WHERE x > 5`。

**等价变换规则**是重写阶段的理论基础，最经典的规则集来自关系代数：

| 规则 | 描述 |
|------|------|
| σ_{c1∧c2}(R) ≡ σ_{c1}(σ_{c2}(R)) | 选择分解 |
| σ_{c1}(σ_{c2}(R)) ≡ σ_{c2}(σ_{c1}(R)) | 选择交换律 |
| π_L(σ_c(R)) ≡ σ_c(π_L(R))，当L包含c中所有属性 | 投影下推 |
| R ⋈_c S ≡ S ⋈_c R | 连接交换律 |
| (R ⋈ S) ⋈ T ≡ R ⋈ (S ⋈ T) | 连接结合律 |

### 16.1.3 优化阶段（Optimization）

查询优化是整个查询处理中最关键也最复杂的阶段。优化器的任务是：在所有与原始查询语义等价的执行计划中，找到一个代价最低的计划。

优化阶段通常分为两个子阶段：

1. **逻辑优化（Logical Optimization）**：基于等价变换规则对查询树进行重写，生成更优的逻辑计划。这一阶段不涉及代价估算，纯粹基于启发式规则。

2. **物理优化（Physical Optimization）**：为逻辑计划中的每个操作选择具体的物理实现算法（如选择用哪种连接算法、是否使用索引），并确定操作之间的执行方式（物化 vs 流水线）。这一阶段依赖代价模型进行定量比较。

### 16.1.4 执行阶段（Execution）

执行引擎按照优化器生成的物理执行计划，调用存储引擎提供的接口获取数据，并执行各种操作（过滤、连接、排序、聚合等），最终返回结果集。

***

## 16.2 代数优化（Heuristic/Rule-Based Optimization）

代数优化基于关系代数的等价变换规则，通过启发式方法对查询树进行重写。这些规则不依赖统计信息和代价估算，而是基于普遍适用的经验法则。

### 16.2.1 选择下推（Predicate Pushdown）

选择下推是最重要也最有效的优化规则之一。其核心思想是：尽早过滤数据，减少中间结果的大小。

**规则**：将选择操作尽可能下推到查询树的叶子节点（即数据源附近）。

优化前：                          优化后：
    π (Projection)                    π (Projection)
    │                                 │
    ⋈ (Join)                          ⋈ (Join)
   / \                               / \
  σ (Selection)   R                 R   σ (Selection)
  │                                     │
  S                                     S

**示例**：

```sql
-- 原始查询
SELECT e.name, d.name
FROM employees e JOIN departments d ON e.dept_id = d.id
WHERE e.salary > 80000;

-- 优化：将 e.salary > 80000 下推到 employees 表扫描之前
-- 这样进入Join的数据量大幅减少
```

选择下推有效的根本原因在于：选择操作通常能大幅减少参与连接的元组数量。假设employees表有100万行，其中salary > 80000的只有1万行，departments表有100行。如果不下推选择，连接操作需要处理100万 × 100 = 1亿次比较；下推后只需处理1万 × 100 = 100万次比较。

**下推的约束条件**：选择谓词中引用的所有属性必须来自它下方的子树。例如`σ_{e.salary > 50 AND d.name = 'Sales'}`不能完全下推到任一子树，但可以分解为两个谓词分别下推。

### 16.2.2 投影下推（Projection Pushdown）

投影下推的目的是尽早去除不需要的列，减少中间结果的宽度，从而降低内存消耗和I/O量。

```sql
-- 原始查询只需要两列
SELECT e.name, e.salary FROM employees e JOIN departments d ON e.dept_id = d.id;

-- 优化：在employees表扫描时就只读取 name, salary, dept_id 三列
-- 在departments表扫描时只读取 id 列
-- 而不是读取整行数据
```

投影下推在列式存储数据库中效果尤为显著，因为列式存储天然支持只读取需要的列。在行式存储中，投影下推的效果取决于是否能利用索引覆盖扫描（Index-Only Scan）。

### 16.2.3 连接重排序（Join Reordering）

当查询涉及多个表的连接时，连接顺序对性能有决定性影响。连接满足交换律和结合律，这意味着对于n个表的连接，有 n! 种不同的连接顺序（考虑交换律后减少为 n!/2 种），以及对应的卡特兰数种不同的树形结构。

三表连接 A ⋈ B ⋈ C 的可能顺序：

1. (A ⋈ B) ⋈ C     先连接A和B，结果再与C连接
2. (A ⋈ C) ⋈ B     先连接A和C，结果再与B连接
3. (B ⋈ C) ⋈ A     先连接B和C，结果再与A连接
4. A ⋈ (B ⋈ C)     先连接B和C，A再与结果连接
5. B ⋈ (A ⋈ C)     先连接A和C，B再与结果连接
6. C ⋈ (A ⋈ B)     先连接A和B，C再与结果连接

连接重排序的核心启发式规则是：**尽早产生小的结果集**。这意味着应该先执行选择性最高的连接（即过滤掉最多数据的连接），将中间结果控制在最小规模。

### 16.2.4 其他代数优化规则

**连接消除（Join Elimination）**：当连接不产生额外信息时消除连接操作。例如外连接中如果外键约束保证了引用完整性，且查询不引用被引用表的任何列，则可以消除该连接。

```sql
-- 如果 orders.customer_id 外键引用 customers.id 且 NOT NULL
SELECT o.* FROM orders o LEFT JOIN customers c ON o.customer_id = c.id;
-- 可以简化为
SELECT o.* FROM orders o;
```

**子查询展平（Subquery Flattening）**：将某些子查询转换为派生表（Derived Table），使其可以参与连接顺序优化。

**公共表达式消除（Common Subexpression Elimination）**：如果同一个子查询在多个位置被引用，只执行一次并共享结果。

***

## 16.3 基于代价的优化（Cost-Based Optimization, CBO）

代数优化基于启发式规则，无法保证生成最优计划。基于代价的优化（CBO）通过定量估算每个候选计划的执行代价，选择代价最低的计划作为最终执行方案。

### 16.3.1 代价模型

代价模型是CBO的核心组件。典型的代价模型将总代价分解为I/O代价和CPU代价两部分：

总代价 = I/O代价 + CPU代价

I/O代价 = 读取页面数 × 单次页面读取时间
CPU代价 = 处理元组数 × 单元组处理时间

更精细的代价模型还会区分：

- **顺序I/O与随机I/O**：随机I/O的代价远高于顺序I/O（传统磁盘上差距约10倍，SSD上差距较小）
- **内存I/O与磁盘I/O**：缓冲池中已有的页面不需要磁盘I/O
- **网络I/O**：分布式场景下节点间的数据传输代价
- **启动代价（Startup Cost）**：操作开始返回第一条结果之前的代价
- **总代价（Total Cost）**：操作完成所有处理的总代价

PostgreSQL的代价模型使用无量纲的"代价单位"，通过配置参数将代价单位映射到实际时间：

```sql
-- PostgreSQL代价参数（默认值）
seq_page_cost = 1.0        -- 顺序页面读取的代价
random_page_cost = 4.0     -- 随机页面读取的代价
cpu_tuple_cost = 0.01      -- 处理每个元组的CPU代价
cpu_index_tuple_cost = 0.005  -- 处理每个索引元组的代价
cpu_operator_cost = 0.0025    -- 每个操作符的代价
```

MySQL的代价模型同样基于I/O和CPU代价，但实现方式有所不同。MySQL 8.0引入了更精确的代价模型，区分了内存临时表和磁盘临时表的代价、顺序扫描和随机扫描的代价等。

### 16.3.2 统计信息（Statistics）

准确的统计信息是CBO做出正确决策的基础。数据库系统通过定期或按需收集的统计信息来估算查询的选择性和结果集大小。

**基本统计信息**：

| 统计项 | 描述 | 收集方式 |
|--------|------|----------|
| 表的行数（n_tup） | 表中的元组总数 | 精确计数或近似估算 |
| 页面数（n_page） | 表占用的页面数 | 从存储层获取 |
| 列的不同值数（NDV） | 列中不同值的数量 | 近似算法（HyperLogLog等） |
| 列的最大/最小值 | 列值域的边界 | 全表扫描或采样 |
| 平均列宽 | 列值的平均字节数 | 采样计算 |
| NULL值比例 | 列中NULL值的占比 | 采样计算 |

**直方图（Histogram）**：

直方图描述数据在值域上的分布情况，是选择性估计最重要的工具。常见的直方图类型包括：

**等宽直方图（Equi-width Histogram）**：将值域等分为若干个桶（Bucket），每个桶记录桶内元组数量。等宽直方图实现简单，但在数据分布不均匀时，某些桶可能包含大量元组，而另一些桶几乎是空的，导致估计精度不高。

等宽直方图示例（salary列，范围[30000, 120000]，5个桶）：

桶1 [30000, 48000): ████████████████████ 2000行
桶2 [48000, 66000): ████████████████████████████████████ 3500行
桶3 [66000, 84000): ████████████████ 1500行
桶4 [84000, 102000): ██████ 600行
桶5 [102000, 120000): ██ 200行

总行数 = 7800

**等深直方图（Equi-depth / Equi-height Histogram）**：每个桶包含大致相同数量的元组，桶的宽度可以不等。等深直方图能更好地适应数据倾斜，在实际系统中更常用。

等深直方图示例（salary列，每个桶约1560行）：

桶1 [30000, 38000): ████████████████████ 1560行
桶2 [38000, 52000): ████████████████████ 1560行
桶3 [52000, 65000): ████████████████████ 1560行
桶4 [65000, 85000): ████████████████████ 1560行
桶5 [85000, 120000): ████████████████████ 1560行

**最常见值（Most Common Values, MCV）**：

除了直方图外，数据库还会单独记录出现频率最高的若干值。这对于高度倾斜的分布（如枚举类型、状态码列）特别重要。

MCV列表示例（status列）：
  值         频率
  'active'   0.65
  'inactive' 0.20
  'pending'  0.10
  'deleted'  0.04
  其他       0.01

PostgreSQL使用`pg_statistics`系统表存储统计信息，支持等深直方图和MCV。可以通过`ANALYZE`命令触发统计信息收集：

```sql
-- 收集所有表的统计信息
ANALYZE;

-- 收集特定表的统计信息
ANALYZE employees;

-- 收集特定列的统计信息并指定采样精度
ANALYZE employees (salary, department_id);
```

MySQL使用`information_schema.STATISTICS`和`mysql.innodb_index_stats`存储统计信息。MySQL 8.0支持直方图统计：

```sql
-- 创建直方图
ANALYZE TABLE employees UPDATE HISTOGRAM ON salary WITH 100 BUCKETS;

-- 查看直方图信息
SELECT * FROM information_schema.COLUMN_STATISTICS
WHERE TABLE_NAME = 'employees';
```

**统计信息的收集策略**：

1. **全量扫描**：精确但开销大，适合小表
2. **采样估算**：读取一定比例的页面（如10%），基于采样结果推断整体分布。PostgreSQL默认采样300 * default_statistics_target个元组（约30000个）
3. **增量更新**：在DML操作时增量维护统计信息（如COUNT、SUM等聚合统计），避免全量重新收集

### 16.3.3 选择性估计（Selectivity Estimation）

选择性（Selectivity）是指满足给定条件的元组占总元组数的比例，取值范围为[0, 1]。选择性估计的准确性直接影响优化器对中间结果大小的估算，进而影响连接算法和连接顺序的选择。

**等值谓词的选择性**：

对于等值谓词`column = value`，如果value在MCV列表中，使用该MCV的频率；否则使用均匀分布假设：

sel(col = val) = {
    MCV频率(val)，  如果val在MCV列表中
    (1 - Σ MCV频率) / (NDV - |MCV|)，  否则
}

伪代码实现：

```python
def estimate_equality(predicate, column_stats):
    """
    估计等值谓词 column = value 的选择性
    """
    value = predicate.value
    stats = column_stats

    # 检查是否为NULL
    if value is None:
        return 0.0

    # 检查MCV列表
    if value in stats.mcv_values:
        idx = stats.mcv_values.index(value)
        return stats.mcv_freqs[idx]

    # 不在MCV列表中，使用均匀分布假设
    mcv_total_freq = sum(stats.mcv_freqs)
    remaining_ndv = stats.ndv - len(stats.mcv_values)
    if remaining_ndv <= 0:
        return 0.0

    return (1.0 - mcv_total_freq) / remaining_ndv
```

**范围谓词的选择性**：

对于范围谓词`column > value`或`column BETWEEN low AND high`，使用直方图进行估计：

```python
def estimate_range(predicate, column_stats, total_rows):
    """
    估计范围谓词的选择性
    使用等深直方图进行估计
    """
    histograms = column_stats.histogram  # 桶列表
    low = predicate.low_value  # 范围下界
    high = predicate.high_value  # 范围上界（可为None）

    matching_rows = 0
    for bucket in histograms:
        bucket_low = bucket.min_value
        bucket_high = bucket.max_value
        bucket_count = bucket.num_values

        # 计算桶与范围谓词的重叠比例
        overlap_low = max(low, bucket_low)
        if high is not None:
            overlap_high = min(high, bucket_high)
        else:
            overlap_high = bucket_high

        if overlap_low >= overlap_high:
            continue  # 无重叠

        # 线性插值估算重叠部分的行数
        bucket_width = bucket_high - bucket_low
        if bucket_width > 0:
            overlap_ratio = (overlap_high - overlap_low) / bucket_width
            matching_rows += bucket_count * overlap_ratio

    return matching_rows / total_rows
```

**多谓词组合的选择性**：

当查询包含多个谓词时，需要组合各谓词的选择性。如果谓词之间相互独立，组合选择性等于各选择性的乘积：

sel(P1 AND P2) = sel(P1) × sel(P2)        -- 独立性假设
sel(P1 OR P2)  = sel(P1) + sel(P2) - sel(P1) × sel(P2)
sel(NOT P1)    = 1 - sel(P1)

```python
def estimate_conjunction(predicates, column_stats_map, total_rows):
    """
    估计多个AND连接的谓词的组合选择性
    使用独立性假设
    """
    combined_selectivity = 1.0
    for pred in predicates:
        col_stats = column_stats_map[pred.column]
        sel = estimate_single_predicate(pred, col_stats, total_rows)
        combined_selectivity *= sel

    # 限制在合理范围内
    return max(0.0, min(1.0, combined_selectivity))
```

独立性假设在实际中往往不成立。例如`WHERE city = 'Beijing' AND province = 'Beijing'`，两个条件高度相关，独立性假设会严重高估选择性（认为选择性 = sel(city) × sel(province)），而实际选择性接近sel(province)。更先进的方法包括：

- **多列直方图（Multi-column Histogram）**：对多个列的联合分布建立直方图
- **相关性估计（Correlation Estimation）**：存储列之间的相关系数
- **采样估算（Sampling）**：对小样本执行实际谓词，用采样结果估计全表选择性

### 16.3.4 结果集大小估计

选择性估计的最终目标是估算每个操作的输出行数（Cardinality Estimation）：

输出行数 = 输入行数 × 选择性

对于连接操作：

|A ⋈_c B| ≈ |A| × |B| × sel(c)

其中sel(c)是连接条件c的选择性。对于等值连接`A.x = B.y`：

sel(A.x = B.y) ≈ 1 / max(NDV(A.x), NDV(B.y))

基数估计的误差会在多操作的执行计划中累积和放大。一个常见的问题是**误差传播**：如果一个两表连接的基数估计偏差2倍，那么在此基础上再连接第三个表时，误差可能放大到4倍甚至更多。这是CBO面临的最大挑战之一。

***

## 16.4 连接算法（Join Algorithms）

连接操作是关系数据库中最耗时的操作之一。不同的连接算法在不同的数据规模、索引可用性和内存限制下有截然不同的性能表现。

### 16.4.1 嵌套循环连接（Nested Loop Join, NLJ）

嵌套循环连接是最简单直观的连接算法。对外表（Outer Table）的每一行，扫描内表（Inner Table）查找匹配行。

**朴素嵌套循环连接（Naive Nested Loop Join）**：

算法：NestedLoopJoin(outer, inner, join_pred)
输入：outer - 外表，inner - 内表，join_pred - 连接条件
输出：连接结果集

结果集 ← ∅
FOR EACH row_o IN outer:
    FOR EACH row_i IN inner:
        IF join_pred(row_o, row_i) 为真:
            结果集 ← 结果集 ∪ {row_o || row_i}
RETURN 结果集

**代价分析**：
- 最坏情况：`|outer| × |inner|` 次比较
- I/O代价：`|outer| + |outer| × |inner|`（如果内表不缓存）
- 适合场景：外表很小，内表在连接列上有索引

**索引嵌套循环连接（Index Nested Loop Join）**：

如果内表的连接列上有索引，可以用索引查找替代全表扫描：

算法：IndexNestedLoopJoin(outer, inner, index_on_inner, join_pred)
输入：outer - 外表，inner - 内表，index_on_inner - 内表连接列索引

结果集 ← ∅
FOR EACH row_o IN outer:
    probe_value ← row_o[join_column]
    匹配行集 ← IndexLookup(index_on_inner, probe_value)
    FOR EACH row_i IN 匹配行集:
        IF join_pred(row_o, row_i) 为真:
            结果集 ← 结果集 ∪ {row_o || row_i}
RETURN 结果集

**代价分析**：
- I/O代价：`|outer| × (索引高度 + 匹配行数)`
- 适合场景：外表小，内表连接列有B+树索引
- 典型例子：OLTP中的主键查询关联

**块嵌套循环连接（Block Nested Loop Join, BNLJ）**：

BNLJ用内存缓冲区一次加载外表的多个行（一个Block），减少内表的扫描次数：

算法：BlockNestedLoopJoin(outer, inner, buffer_size)
输入：buffer_size - 可用缓冲区块数

结果集 ← ∅
将outer分为大小为 buffer_size - 2 的块
FOR EACH block_o IN outer_blocks:
    将block_o加载到内存缓冲区
    FOR EACH row_i IN inner:
        FOR EACH row_o IN 缓冲区:
            IF join_pred(row_o, row_i) 为真:
                结果集 ← 结果集 ∪ {row_o || row_i}
RETURN 结果集

**代价分析**：
- I/O代价：`|outer| + ⌈|outer| / (B-2)⌉ × |inner|`，其中B为可用缓冲区块数
- 当B足够大（能容纳整个外表）时，退化为只需扫描内表一次：`|outer| + |inner|`

### 16.4.2 排序归并连接（Sort-Merge Join, SMJ）

排序归并连接先将两个表按连接列排序，然后利用归并操作合并两个有序序列。

算法：SortMergeJoin(R, S, join_col)
输入：R, S - 两个关系，join_col - 连接列

// 阶段1：排序
sorted_R ← Sort(R, by=join_col)
sorted_S ← Sort(S, by=join_col)

// 阶段2：归并
结果集 ← ∅
i ← 0; j ← 0
WHILE i < |sorted_R| AND j < |sorted_S|:
    IF sorted_R[i].join_col < sorted_S[j].join_col:
        i ← i + 1
    ELIF sorted_R[i].join_col > sorted_S[j].join_col:
        j ← j + 1
    ELSE:
        // 处理相同连接值的多行（Merge阶段的重复值处理）
        保存当前位置 j_start ← j
        WHILE i < |sorted_R| AND sorted_R[i].join_col == sorted_S[j_start].join_col:
            j ← j_start
            WHILE j < |sorted_S| AND sorted_S[j].join_col == sorted_R[i].join_col:
                结果集 ← 结果集 ∪ {sorted_R[i] || sorted_S[j]}
                j ← j + 1
            i ← i + 1
RETURN 结果集

**代价分析**：
- 排序阶段：`2 × |R| × ⌈log_{B-1}(|R|/B)⌉ + 2 × |S| × ⌈log_{B-1}(|S|/B)⌉`（外部归并排序的I/O代价）
- 归并阶段：`|R| + |S|`（顺序扫描）
- 适合场景：输入已排序，或需要结果有序的场景

**SMJ的优势**：
1. 如果输入已经排序（如有索引），排序阶段可以跳过
2. 产生有序输出，可能避免后续的排序操作
3. 对等值连接和非等值连接（如范围连接）都适用

### 16.4.3 哈希连接（Hash Join）

哈希连接通过构建哈希表实现高效的等值连接。它分为构建阶段（Build Phase）和探测阶段（Probe Phase）。

**基本哈希连接（Simple Hash Join）**：

算法：HashJoin(build_rel, probe_rel, join_col)
输入：build_rel - 构建侧关系（通常选较小的表），probe_rel - 探测侧关系

// 阶段1：构建哈希表（Build Phase）
哈希表 H ← ∅
FOR EACH row_b IN build_rel:
    key ← hash(row_b[join_col])
    H[key] ← H[key] ∪ {row_b}

// 阶段2：探测（Probe Phase）
结果集 ← ∅
FOR EACH row_p IN probe_rel:
    key ← hash(row_p[join_col])
    IF key IN H:
        FOR EACH row_b IN H[key]:
            IF row_b[join_col] == row_p[join_col]:  // 防止哈希冲突
                结果集 ← 结果集 ∪ {row_b || row_p}
RETURN 结果集

**代价分析**：
- I/O代价：`|build_rel| + |probe_rel|`（各扫描一次）
- 内存需求：需要能容纳整个构建侧的哈希表
- 适合场景：等值连接，构建侧能完全放入内存

**Grace Hash Join（分区哈希连接）**：

当构建侧太大无法完全放入内存时，使用Grace Hash Join。它通过两轮哈希分区，将大关系分解为可以放入内存的小分区：

算法：GraceHashJoin(R, S, join_col, num_partitions)
输入：R, S - 两个关系，num_partitions - 分区数

// ===== 第一轮：分区阶段 =====
// 对R和S使用相同的哈希函数进行分区
FOR EACH row IN R:
    part_id ← hash(row[join_col]) mod num_partitions
    将row写入分区文件 R_part[part_id]

FOR EACH row IN S:
    part_id ← hash(row[join_col]) mod num_partitions
    将row写入分区文件 S_part[part_id]

// ===== 第二轮：连接阶段 =====
结果集 ← ∅
FOR part_id = 0 TO num_partitions - 1:
    // 对每个分区对执行内存哈希连接
    IF R_part[part_id] 可以放入内存:
        在内存中构建 R_part[part_id] 的哈希表
        扫描 S_part[part_id] 进行探测
        将匹配结果加入结果集
    ELSE:
        递归地对 R_part[part_id] 和 S_part[part_id] 执行 Grace Hash Join
RETURN 结果集

**代价分析**：
- I/O代价：`3 × (|R| + |S|)`（分区写入 + 读取分区 + 构建/探测）
- 如果需要递归，代价增加为`(2 × 递归轮数 + 1) × (|R| + |S|)`
- 分区数的选择：`num_partitions = ⌈max(|R|, |S|) / (B - 2)⌉`，确保每个分区可以放入内存

**哈希连接的变体**：

1. **Hybrid Hash Join**：第一轮分区时，将一个分区保留在内存中（通常是第一个分区），避免将其写入磁盘再读回。这在内存充足时能显著减少I/O。

2. **Hash Join with Skew Handling**：当某些哈希分区过大（数据倾斜）时，将这些"热"分区单独处理，可能使用嵌套循环连接替代。

### 16.4.4 连接算法比较

┌──────────────────┬────────────────────┬─────────────────────┬──────────────────┐
│     算法          │  时间复杂度          │  I/O代价             │  最佳适用场景      │
├──────────────────┼────────────────────┼─────────────────────┼──────────────────┤
│ 嵌套循环连接      │ O(|R| × |S|)       │ |R| + |R| × |S|    │ 外表小            │
│ 索引嵌套循环连接  │ O(|R| × log|S|)    │ |R| × (h + 匹配数) │ 内表有索引        │
│ 排序归并连接      │ O(|R|log|R|+|S|log|S|) │ O(|R|+|S|)*    │ 已排序/范围连接    │
│ 哈希连接          │ O(|R| + |S|)       │ |R| + |S|          │ 等值连接，内存充足 │
│ Grace Hash Join  │ O(|R| + |S|)       │ 3 × (|R| + |S|)   │ 等值连接，大表     │
└──────────────────┴────────────────────┴─────────────────────┴──────────────────┘

***

## 16.5 连接顺序优化

对于涉及n个表的连接查询，可能的连接顺序数量随n呈阶乘级增长。如何在庞大的搜索空间中高效地找到近似最优的连接顺序，是查询优化器最核心的算法问题。

### 16.5.1 基于动态规划的连接顺序优化（System R方法）

System R（IBM于1970年代开发的关系数据库系统）首次提出了基于动态规划的连接顺序优化算法，至今仍被大多数商业数据库采用。

核心思想：利用子问题的最优解构建全局最优解。将n个表的连接问题分解为更小子集的连接问题。

算法：DPJoinOrderOptimization(tables, join_preds)
输入：tables - 参与连接的表集合，join_preds - 连接条件

n ← |tables|
// best_plan[S] 存储表集合S的最优连接计划
best_plan ← {}

// 基础情况：单表
FOR EACH table T IN tables:
    best_plan[{T}] ← 选择代价最低的访问路径（全表扫描、索引扫描等）

// 动态规划：从2个表到n个表
FOR size = 2 TO n:
    FOR EACH 大小为size的表子集 S ⊆ tables:
        best_plan[S] ← ∅  (无穷大代价)
        // 尝试将S分割为两个非空子集 S1 和 S2
        FOR EACH 非空真子集 S1 ⊂ S:
            S2 ← S \ S1
            IF S1 < S2:  // 避免重复（利用连接交换律）
                CONTINUE
            // 确保 S1 和 S2 之间存在连接条件
            IF 存在连接条件连接 S1 和 S2:
                // 考虑两种连接顺序：S1 ⋈ S2 和 S2 ⋈ S1
                FOR EACH join_pred IN 连接S1和S2的条件:
                    FOR EACH join_algo IN {NLJ, SMJ, HJ}:
                        plan ← 创建连接计划 best_plan[S1] ⋈_algo best_plan[S2]
                        cost ← 估算plan的代价
                        IF cost < best_plan[S].cost:
                            best_plan[S] ← plan

RETURN best_plan[tables]

**时间复杂度分析**：对于n个表，需要考虑的子集数量为Σ_{k=1}^{n} C(n,k) = 2^n - 1。对于每个大小为k的子集，需要考虑的分割方式约为2^{k-1}种。因此总时间复杂度约为O(3^n)。

当n较小时（通常n ≤ 15），这个算法是可行的。但对于更大的n，搜索空间呈指数级爆炸，需要采用其他策略。

### 16.5.2 贪心算法

当表的数量较多时，可以使用贪心算法快速找到一个"还不错"的连接顺序：

算法：GreedyJoinOrder(tables, join_preds)

// 选择选择性最高的单表作为起点
best_start ← 选择全表扫描代价最低的表
remaining ← tables \ {best_start}
current_plan ← best_start

WHILE remaining 不为空:
    best_next ← ∅
    best_cost ← ∞
    FOR EACH table T IN remaining:
        IF T 与 current_plan 中的表有连接条件:
            cost ← 估算 current_plan ⋈ T 的代价
            IF cost < best_cost:
                best_cost ← cost
                best_next ← T
    current_plan ← current_plan ⋈ best_next
    remaining ← remaining \ {best_next}

RETURN current_plan

贪心算法的时间复杂度为O(n²)，远优于动态规划，但可能错过全局最优解。

### 16.5.3 遗传算法（GEQO）

PostgreSQL在表数量超过阈值（默认geqo_threshold = 12）时使用遗传算法（Genetic Query Optimization, GEQO）搜索连接顺序：

算法：GEQO(tables, join_preds, pop_size, generations)

// 将连接顺序编码为排列（基因）
// 每个基因是一个表的排列，表示连接顺序

// 初始化种群
population ← 随机生成 pop_size 个排列

FOR gen = 1 TO generations:
    // 评估适应度（代价的倒数）
    FOR EACH individual IN population:
        fitness(individual) ← 1 / 估算连接代价(individual)

    // 选择（轮盘赌或锦标赛）
    parents ← Select(population, fitness)

    // 交叉（有序交叉算子 OX）
    offspring ← ∅
    WHILE |offspring| < pop_size:
        (p1, p2) ← 从parents中选择两个父代
        child ← OrderCrossover(p1, p2)
        offspring ← offspring ∪ {child}

    // 变异（随机交换两个位置）
    FOR EACH child IN offspring:
        IF random() < mutation_rate:
            SwapRandomPositions(child)

    population ← offspring

RETURN 适应度最高的个体

GEQO的优势在于搜索时间可控（由种群大小和迭代代数决定），适合表数量很多的场景。缺点是不保证找到最优解，且结果具有随机性。

***

## 16.6 执行模型

### 16.6.1 物化执行模型（Materialized Execution）

物化执行模型中，每个操作符执行完毕后将完整结果写入临时存储（磁盘或内存缓冲区），下一个操作符从临时存储中读取数据。

物化执行的流程：

Scan(employees) → [写入临时文件] → Filter(salary>50000) → [写入临时文件] → Sort(name) → 输出

**优点**：实现简单，每个操作独立执行，便于调试。

**缺点**：如果查询涉及多个操作，会产生大量中间结果的I/O。特别是对于大表，中间结果可能溢出到磁盘，导致性能严重下降。

### 16.6.2 流水线执行模型（Volcano Iterator Model / Pipeline Execution）

流水线执行模型由Graefe在1989年提出的Volcano模型实现。每个操作符实现为一个迭代器（Iterator），提供`open()`、`next()`、`close()`三个接口：

```python
class Iterator:
    def open(self):
        """初始化操作符"""
        pass

    def next(self):
        """返回下一个元组，耗尽时返回 None"""
        pass

    def close(self):
        """清理资源"""
        pass
```

具体的迭代器实现：

```python
class ScanIterator(Iterator):
    """表扫描迭代器"""
    def __init__(self, table):
        self.table = table
        self.cursor = None

    def open(self):
        self.cursor = self.table.begin_scan()

    def next(self):
        return self.cursor.next()

    def close(self):
        self.table.end_scan(self.cursor)

class FilterIterator(Iterator):
    """过滤迭代器"""
    def __init__(self, child, predicate):
        self.child = child
        self.predicate = predicate

    def open(self):
        self.child.open()

    def next(self):
        while True:
            row = self.child.next()
            if row is None:
                return None
            if self.predicate(row):
                return row

    def close(self):
        self.child.close()

class NestedLoopJoinIterator(Iterator):
    """嵌套循环连接迭代器"""
    def __init__(self, outer, inner, join_pred):
        self.outer = outer
        self.inner = inner
        self.join_pred = join_pred
        self.current_outer = None

    def open(self):
        self.outer.open()
        self.inner.open()
        self.current_outer = self.outer.next()

    def next(self):
        while self.current_outer is not None:
            inner_row = self.inner.next()
            if inner_row is not None:
                if self.join_pred(self.current_outer, inner_row):
                    return self.current_outer + inner_row
            else:
                # 内表耗尽，移到外表下一行
                self.current_outer = self.outer.next()
                self.inner.close()
                self.inner.open()
        return None

    def close(self):
        self.outer.close()
        self.inner.close()
```

流水线的调用方式非常优雅：

```python
# 构建查询计划树
scan_e = ScanIterator(employees)
filter_e = FilterIterator(scan_e, lambda r: r.salary > 50000)
scan_d = ScanIterator(departments)
join = NestedLoopJoinIterator(filter_e, scan_d, lambda r1, r2: r1.dept_id == r2.id)

# 执行：从根节点调用next()，数据自底向上流动
join.open()
while True:
    result = join.next()
    if result is None:
        break
    print(result)
join.close()
```

**流水线的优势**：不需要物化中间结果，减少I/O和内存占用。数据在操作符之间以"拉"（Pull）的方式流动，每个操作符按需获取下一条数据。

**流水线的限制**：某些操作符无法流水线化——例如排序操作必须等待所有输入到达后才能开始输出。Hash Join的构建阶段也必须完整物化构建侧。

实际系统通常结合两种模型：可以流水线化的操作使用流水线，不能流水线化的操作（如排序、Hash Join的构建阶段）使用物化。

***

## 16.7 查询计划的表示与解读

### 16.7.1 执行计划树

执行计划通常表示为一棵树，树的每个节点代表一个物理操作符。树的叶节点是数据访问操作（表扫描、索引扫描），内部节点是处理操作（过滤、连接、排序、聚合）。

一个典型的执行计划树：

              ┌─ Hash Join (e.dept_id = d.id)
              │   Hash Cond: (e.dept_id = d.id)
         ┌────┤
         │    │
         │    └─ Seq Scan on departments d
         │        Filter: (name = 'Engineering')
         │
    ┌────┤
    │    └─ Index Scan on employees e
    │        Index Cond: (salary > 80000)
    │
  Projection: (e.name, d.name)

### 16.7.2 EXPLAIN命令解读

**PostgreSQL EXPLAIN示例**：

```sql
EXPLAIN ANALYZE
SELECT e.name, d.name
FROM employees e
JOIN departments d ON e.dept_id = d.id
WHERE e.salary > 80000;
```

Hash Join  (cost=25.50..580.75 rows=9800 width=48) (actual time=0.852..12.345 rows=9750 loops=1)
  Hash Cond: (e.dept_id = d.id)
  ->  Index Scan using idx_salary on employees e  (cost=0.42..450.20 rows=10000 width=24)
        Index Cond: (salary > 80000)
  ->  Hash  (cost=15.00..15.00 rows=100 width=24)
        ->  Seq Scan on departments d  (cost=0.00..15.00 rows=100 width=24)
              Filter: (name = 'Engineering'::text)
Planning Time: 0.234 ms
Execution Time: 12.567 ms

解读关键信息：

| 字段 | 含义 |
|------|------|
| cost=25.50..580.75 | 启动代价..总代价（无量纲单位） |
| rows=9800 | 优化器估计的输出行数 |
| width=48 | 每行的平均字节数 |
| actual time=0.852..12.345 | 实际启动时间..总时间（毫秒） |
| rows=9750 | 实际输出行数 |
| loops=1 | 操作执行次数 |

**MySQL EXPLAIN示例**：

```sql
EXPLAIN FORMAT=JSON
SELECT e.name, d.name
FROM employees e
JOIN departments d ON e.dept_id = d.id
WHERE e.salary > 80000;
```

MySQL的EXPLAIN输出提供`type`字段表示访问类型：

访问类型从优到劣：
system > const > eq_ref > ref > range > index > ALL

- const: 通过主键或唯一索引查找单行
- eq_ref: 连接中使用主键或唯一索引
- ref: 使用非唯一索引查找
- range: 索引范围扫描
- index: 全索引扫描
- ALL: 全表扫描

***

## 16.8 主流数据库的查询优化器实现

### 16.8.1 PostgreSQL查询优化器

PostgreSQL的查询优化器是开源数据库中最先进的优化器之一，其架构包含以下核心组件：

**Planner/Optimizer架构**：

查询树（Query Tree）
    │
    ▼
┌─────────────────────┐
│ 预处理（Preprocessing）│  子查询拉平、ANY/IN子查询转换
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 路径搜索（Path Search）│  为每个基本关系生成访问路径
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 连接搜索（Join Search）│  动态规划搜索最优连接顺序
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 计划生成（Plan Gen）   │  将最优路径转换为执行计划
└─────────────────────┘

PostgreSQL在路径搜索阶段会为每个基本关系（表或子查询）生成多种访问路径：

```c
// PostgreSQL中的访问路径类型
typedef enum NodeTag {
    T_SeqScan,          // 顺序扫描
    T_IndexScan,        // 索引扫描（返回有序结果）
    T_IndexOnlyScan,    // 仅索引扫描（不需要回表）
    T_BitmapIndexScan,  // 位图索引扫描
    T_BitmapHeapScan,   // 位图堆扫描（多个索引条件的组合）
    T_TidScan,          // TID直接定位扫描
    T_SubqueryScan,     // 子查询扫描
    T_FunctionScan,     // 函数扫描
    T_ValuesScan,       // VALUES扫描
    T_CteScan,          // CTE扫描
    T_ForeignScan,      // 外部表扫描（FDW）
    T_CustomScan,       // 自定义扫描（扩展使用）
} NodeTag;
```

对于每个关系，PostgreSQL生成所有可行的访问路径，存储在`RelOptInfo`结构中：

```c
typedef struct RelOptInfo {
    NodeTag     type;
    RelOptKind  reloptkind;    // 基本关系、连接关系、子查询等
    Index       relid;         // 关系ID
    double      rows;          // 估计的行数
    int         width;         // 平均行宽
    List       *pathlist;      // 所有候选访问路径
    Path       *cheapest_startup_path;  // 最小启动代价路径
    Path       *cheapest_total_path;    // 最小总代价路径
    List       *reltargetlist; // 输出列
    // ... 其他字段
} RelOptInfo;
```

PostgreSQL的连接搜索使用标准的System R动态规划算法，对于超过`geqo_threshold`（默认12个）表的查询切换到遗传算法（GEQO）。

**PostgreSQL的统计信息收集**：

```sql
-- 查看统计信息
SELECT attname, n_distinct, most_common_vals, most_common_freqs,
       histogram_bounds, correlation
FROM pg_stats
WHERE tablename = 'employees';

-- 调整统计精度
ALTER TABLE employees ALTER COLUMN salary SET STATISTICS 1000;
ANALYZE employees;
```

`default_statistics_target`参数控制默认的统计采样精度（默认100，最大10000）。值越高，直方图的桶数越多，MCV列表越长，统计信息越准确，但收集时间也越长。

### 16.8.2 MySQL查询优化器

MySQL 8.0的优化器经历了重大改进，引入了成本模型的重构和优化器追踪（Optimizer Trace）功能。

**MySQL优化器架构**：

SQL语句
    │
    ▼
┌──────────────┐
│ 语法/语义分析  │
└──────┬───────┘
       ▼
┌──────────────┐
│ 预处理         │  常量折叠、子查询转换
└──────┬───────┘
       ▼
┌──────────────┐
│ 优化器         │  基于代价的优化
│ - 访问路径选择  │
│ - 连接优化      │
│ - 代价估算      │
└──────┬───────┘
       ▼
┌──────────────┐
│ 执行计划       │
└──────────────┘

**Optimizer Trace**是MySQL强大的调试工具，可以查看优化器的完整决策过程：

```sql
-- 开启优化器追踪
SET optimizer_trace = 'enabled=on';

-- 执行查询
SELECT e.name, d.name
FROM employees e JOIN departments d ON e.dept_id = d.id
WHERE e.salary > 80000;

-- 查看追踪结果
SELECT * FROM information_schema.optimizer_trace\G
```

Optimizer Trace输出包含以下关键部分：
- `steps.join_preparation`：查询重写阶段
- `steps.join_optimization`：连接优化阶段
- `steps.join_optimization.rows_estimation`：行数估计
- `steps.considered_execution_plans`：候选执行计划及代价
- `steps.chosen_execution_plan`：最终选择的执行计划

**MySQL的索引选择**：

MySQL在选择索引时，除了代价模型外，还有一些特殊的优化规则：

1. **Range优化**：检测WHERE子句中的范围条件，生成`range`类型的访问路径
2. **Index Merge**：将多个索引扫描的结果合并（Union、Intersection、Sort-Union）
3. **MRR（Multi-Range Read）**：对索引扫描得到的主键进行排序后再回表，减少随机I/O
4. **ICP（Index Condition Pushdown）**：将过滤条件下推到存储引擎层，在索引扫描时就进行过滤
5. **BKA（Batched Key Access）**：批量索引查找，通过MRR减少随机I/O

```sql
-- MySQL的索引提示
SELECT * FROM employees FORCE INDEX (idx_salary)
WHERE salary > 50000 AND department_id = 3;

-- 查看MySQL是否使用了ICP
EXPLAIN SELECT * FROM employees
WHERE salary > 50000 AND name LIKE 'Z%';
-- Extra列会显示 "Using index condition" 表示使用了ICP
```

***

## 16.9 Hint与计划稳定性

### 16.9.1 查询Hint

当优化器选择了不理想的执行计划时，可以通过Hint指令强制或建议优化器使用特定的执行策略。

**Oracle Hint**（最丰富的Hint系统）：

```sql
-- 强制使用特定索引
SELECT /*+ INDEX(employees idx_salary) */ * FROM employees WHERE salary > 50000;

-- 强制使用哈希连接
SELECT /*+ USE_HASH(e d) */ e.name, d.name
FROM employees e JOIN departments d ON e.dept_id = d.id;

-- 强制连接顺序
SELECT /*+ LEADING(e d) ORDERED */ e.name, d.name
FROM employees e JOIN departments d ON e.dept_id = d.id;

-- 指定并行度
SELECT /*+ PARALLEL(employees 4) */ COUNT(*) FROM employees;
```

**MySQL Hint**：

```sql
-- 索引Hint
SELECT * FROM employees USE INDEX (idx_salary) WHERE salary > 50000;
SELECT * FROM employees FORCE INDEX (idx_salary) WHERE salary > 50000;
SELECT * FROM employees IGNORE INDEX (idx_salary) WHERE salary > 50000;

-- 连接顺序Hint
SELECT /*+ JOIN_ORDER(e, d) */ e.name, d.name
FROM employees e JOIN departments d ON e.dept_id = d.id;

-- 子查询物化Hint
SELECT * FROM employees WHERE department_id IN
(SELECT /*+ SUBQUERY(MATERIALIZATION) */ id FROM departments);
```

**PostgreSQL的Hint扩展**（pg_hint_plan）：

PostgreSQL原生不支持Hint，但可以通过pg_hint_plan扩展获得类似功能：

```sql
-- 需要安装pg_hint_plan扩展
LOAD 'pg_hint_plan';

/*+ IndexScan(employees idx_salary) */
SELECT * FROM employees WHERE salary > 50000;

/*+ HashJoin(e d) Leading((e d)) */
SELECT e.name, d.name
FROM employees e JOIN departments d ON e.dept_id = d.id;
```

### 16.9.2 计划稳定性（Plan Stability）

Hint的根本问题在于它把执行计划硬编码到应用代码中，当数据分布变化后，原来的Hint可能不再合适。更好的方案是计划稳定性（Plan Stability）或计划管理（Plan Management）。

**SQL Plan Management（Oracle / PostgreSQL）**：

计划管理的工作流程：

1. 计划捕获（Plan Capture）：
   - 记录SQL语句的执行计划
   - 建立SQL Plan Baseline

2. 计划进化（Plan Evolution）：
   - 当优化器生成新计划时，与Baseline比较
   - 只有性能更好的计划才会被加入Baseline

3. 计划选择（Plan Selection）：
   - 执行时从Baseline中选择代价最低的计划
   - 确保不会使用退化的计划

**MySQL的Optimizer Switch**：

MySQL通过`optimizer_switch`系统变量控制优化器行为：

```sql
-- 查看当前优化器开关
SELECT @@optimizer_switch;

-- 关闭某些优化
SET optimizer_switch = 'mrr=off';
SET optimizer_switch = 'index_merge=on,index_merge_union=on';

-- 常用的优化器开关
-- batched_key_access=on/off    BKA优化
-- mrr=on/off                   多范围读优化
-- index_merge=on/off           索引合并优化
-- derived_merge=on/off         派生表合并
-- hashjoin=on/off              哈希连接（MySQL 8.0.18+）
```

***

## 16.10 查询优化的前沿发展

### 16.10.1 自适应查询优化（Adaptive Query Optimization）

传统优化器在查询编译时一次性确定执行计划，无法在执行过程中根据实际情况调整。自适应查询优化通过在执行过程中收集反馈信息，动态调整执行计划。

**Adaptive Query Processing的几种形式**：

1. **Adaptive Join**：在执行时根据实际数据量选择Join算法。例如，如果Hash Join的构建侧实际大小超过预期，可以切换到Sort-Merge Join。SQL Server和PostgreSQL（通过pg_adaptive_join扩展）支持这一特性。

2. **Adaptive Skew Handling**：在Hash Join执行过程中检测数据倾斜，自动对热分区进行特殊处理。

3. **Mid-Query Reoptimization**：在查询执行过程中，如果发现实际行数与估计行数差异过大，重新优化剩余部分的计划。

### 16.10.2 基于机器学习的查询优化

近年来，机器学习技术被引入查询优化领域：

1. **学习型基数估计器**：使用深度学习模型（如DeepDB、Naru）替代传统直方图进行基数估计，能更好地捕捉列之间的相关性。

2. **学习型代价模型**：通过历史查询的执行数据训练代价预测模型，替代手工设计的代价公式。

3. **端到端学习型优化器**：使用强化学习直接学习从查询到执行计划的映射（如Query2Vec + RL）。

4. **索引推荐**：基于工作负载分析，使用机器学习推荐最优的索引配置（如DB2 Design Advisor、PostgreSQL的hypopg扩展）。

***

## 参考文献

- Selinger, P.G. et al. "Access Path Selection in a Relational Database Management System." ACM SIGMOD, 1979.（System R优化器的经典论文）
- Graefe, G. "Volcano—An Extensible and Parallel Query Evaluation System." IEEE TKDE, 1994.（Volcano迭代器模型）
- Graefe, G. "Query Evaluation Techniques for Large Databases." ACM Computing Surveys, 1993.（查询执行技术综述）
- Jarke, M. & Koch, J. "Query Optimization in Database Systems." ACM Computing Surveys, 1984.（查询优化综述）
- Leis, V. et al. "How Good Are Query Optimizers, Really?" VLDB, 2015.（对现代优化器准确性的实证研究）
- Marcus, R. & Papaemmanouil, O. "Deep Reinforcement Learning for Join Order Enumeration." aiDM@SIGMOD, 2018.（RL用于连接顺序优化）
- PostgreSQL官方文档：https://www.postgresql.org/docs/current/parallel-plans.html
- MySQL官方文档：https://dev.mysql.com/doc/refman/8.0/en/execution-plan-information.html

***

# 查询优化：理论基础（完）

***

# 查询优化：核心技巧

## 16.11 诊断与调优方法论

查询性能问题的诊断应遵循系统化的方法论，而非盲目尝试。本节介绍一套从定位问题到验证效果的完整流程。

### 16.11.1 性能诊断四步法

定位慢查询 → 分析执行计划 → 识别瓶颈 → 实施优化 → 验证效果
    ↑                                                    │
    └────────────── 持续监控与迭代 ←─────────────────────┘

**第一步：定位慢查询**

在生产环境中定位性能瓶颈查询，不同数据库提供了不同的工具：

```sql
-- PostgreSQL：开启慢查询日志
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- 记录超过1秒的查询
ALTER SYSTEM SET log_statement = 'none';              -- 不记录所有语句
ALTER SYSTEM SET log_duration = off;

-- MySQL：开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;        -- 阈值1秒
SET GLOBAL log_queries_not_using_indexes = 'ON';  -- 记录未使用索引的查询

-- MySQL：从performance_schema获取实时统计
SELECT DIGEST_TEXT, COUNT_STAR, AVG_TIMER_WAIT/1000000000 AS avg_time_ms,
       SUM_ROWS_EXAMINED, SUM_ROWS_SENT
FROM performance_schema.events_statements_summary_by_digest
ORDER BY AVG_TIMER_WAIT DESC
LIMIT 10;
```

```python
# PostgreSQL：查询pg_stat_statements视图（需要加载扩展）
# CREATE EXTENSION pg_stat_statements;

# 查询最耗时的SQL
# SELECT query, calls, mean_exec_time, total_exec_time,
#        rows, shared_blks_hit, shared_blks_read
# FROM pg_stat_statements
# ORDER BY mean_exec_time DESC
# LIMIT 10;
```

**第二步：获取执行计划**

使用EXPLAIN获取优化器选择的执行计划，重点关注以下几个指标：

```sql
-- PostgreSQL：获取详细执行计划（包含实际运行数据）
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT e.name, d.name, e.salary
FROM employees e
JOIN departments d ON e.dept_id = d.id
WHERE e.salary > 80000 AND d.name = 'Engineering';

-- 输出示例（带实际执行数据）：
-- Hash Join  (cost=25.50..580.75 rows=9800 width=48) (actual time=0.852..12.345 rows=9750 loops=1)
--   Hash Cond: (e.dept_id = d.id)
--   Buffers: shared hit=150 read=25
--   ->  Index Scan using idx_salary on employees e  (cost=0.42..450.20 rows=10000 width=24)
--         Index Cond: (salary > 80000)
--         Buffers: shared hit=120 read=20
--   ->  Hash  (cost=15.00..15.00 rows=100 width=24) (actual time=0.025..0.025 rows=100 loops=1)
--         Buckets: 1024  Batches: 1  Memory Usage: 16kB
--         ->  Seq Scan on departments d  (cost=0.00..15.00 rows=100 width=24) (actual time=0.008..0.015 rows=100 loops=1)
--               Filter: (name = 'Engineering'::text)
--               Rows Removed by Filter: 0
--               Buffers: shared hit=5
-- Planning Time: 0.234 ms
-- Execution Time: 12.567 ms
```

```sql
-- MySQL：获取详细执行计划
EXPLAIN FORMAT=JSON
SELECT e.name, d.name, e.salary
FROM employees e
JOIN departments d ON e.dept_id = d.id
WHERE e.salary > 80000 AND d.name = 'Engineering';
```

**第三步：识别瓶颈**

执行计划中的关键信号及其含义：

| 信号 | 含义 | 可能原因 |
|------|------|----------|
| Seq Scan（全表扫描） | 顺序扫描整张表 | 缺少索引、优化器认为全扫更快 |
| rows 估计值与实际值差距大 | 统计信息不准确 | 需要更新统计信息 |
| Sort → External Merge | 排序溢出到磁盘 | 增加sort_mem或优化查询 |
| Hash → Batch > 1 | Hash Join 分批执行 | 内存不足，考虑增大work_mem |
| Nested Loop 且外表行数巨大 | 嵌套循环效率低下 | 检查索引或更换连接算法 |
| Buffers: shared read 远大于 hit | 大量磁盘读取 | 数据未缓存，考虑增大shared_buffers |
| Sort Method: external merge | 排序溢出到临时文件 | 增大work_mem参数 |
| Hash Batches: 2+ | Hash表分批构建 | 增大work_mem参数 |

**第四步：实施优化并验证**

```sql
-- PostgreSQL：查看优化前后对比
-- 优化前
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 12345;
-- 可能输出：Seq Scan on orders (cost=0.00..15234.00 rows=1000 width=200)
--           actual time=0.050..45.230 rows=1000 loops=1

-- 创建索引
CREATE INDEX idx_orders_customer ON orders(customer_id);

-- 优化后
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 12345;
-- 可能输出：Index Scan using idx_orders_customer on orders (cost=0.42..85.30 rows=1000 width=200)
--           actual time=0.025..1.230 rows=1000 loops=1
```

### 16.11.2 索引优化策略

索引是查询优化中最常用的手段，但索引并非越多越好——每个索引都会增加写入开销和存储空间。

**索引设计原则**：

1. **高选择性列优先**：选择性越高（不同值占比越大），索引效果越好。对于`status`列只有3个值的情况，索引的帮助有限。

2. **最左前缀原则**：复合索引`(a, b, c)`可以服务于`WHERE a = ?`、`WHERE a = ? AND b = ?`、`WHERE a = ? AND b = ? AND c = ?`，但不能直接服务于`WHERE b = ?`。

3. **覆盖索引（Covering Index）**：如果索引包含了查询需要的所有列，则可以使用Index-Only Scan，完全避免回表。这是性能最优的场景之一。

```sql
-- 覆盖索引示例
-- 查询只需要 name 和 salary 两列
SELECT name, salary FROM employees WHERE department_id = 5;

-- 创建覆盖索引：包含查询的所有列
CREATE INDEX idx_emp_cover ON employees(department_id, name, salary);
-- department_id 在索引最左侧用于过滤
-- name 和 salary 存储在索引中，无需回表
```

4. **避免冗余索引**：如果已经有了`(a, b)`索引，`(a)`索引就是冗余的。PostgreSQL可以使用`pg_indexes`视图检测冗余索引。

5. **部分索引（Partial Index，PostgreSQL特有）**：只为满足特定条件的行建立索引，减小索引体积。

```sql
-- 部分索引：只为active状态的订单建索引
CREATE INDEX idx_active_orders ON orders(created_at)
WHERE status = 'active';

-- 查询：只有WHERE status = 'active'时才会使用这个索引
SELECT * FROM orders WHERE status = 'active' AND created_at > '2025-01-01';
```

**索引失效的常见场景**：

```sql
-- 1. 对索引列使用函数
SELECT * FROM employees WHERE YEAR(hire_date) = 2024;   -- 索引失效
SELECT * FROM employees WHERE hire_date >= '2024-01-01'
                         AND hire_date < '2025-01-01';  -- 索引有效

-- 2. 隐式类型转换
SELECT * FROM employees WHERE phone = 13800138000;  -- phone是VARCHAR，传入INT，隐式转换导致索引失效
SELECT * FROM employees WHERE phone = '13800138000'; -- 索引有效

-- 3. LIKE前缀通配
SELECT * FROM employees WHERE name LIKE '%son';  -- 索引失效
SELECT * FROM employees WHERE name LIKE 'John%'; -- 索引有效

-- 4. OR连接不同列
SELECT * FROM employees WHERE salary > 80000 OR department_id = 5;  -- 单列索引可能失效
-- 解决：使用UNION ALL或创建复合索引

-- 5. NOT IN / NOT EXISTS 优化差异
SELECT * FROM employees WHERE department_id NOT IN (SELECT id FROM departments WHERE name = 'Temp');
-- 改写为LEFT JOIN
SELECT e.* FROM employees e
LEFT JOIN departments d ON e.dept_id = d.id AND d.name = 'Temp'
WHERE d.id IS NULL;
```

### 16.11.3 SQL改写技巧

很多时候，不改变索引和配置，仅通过改写SQL就能获得数量级的性能提升。

**子查询转连接（Subquery to Join）**：

```sql
-- 慢：相关子查询（可能对每一行执行一次子查询）
SELECT e.name, e.salary
FROM employees e
WHERE e.salary > (SELECT AVG(salary) FROM employees WHERE dept_id = e.dept_id);

-- 快：改写为窗口函数连接
SELECT e.name, e.salary
FROM employees e
JOIN (
    SELECT dept_id, AVG(salary) AS avg_salary
    FROM employees
    GROUP BY dept_id
) d ON e.dept_id = d.dept_id
WHERE e.salary > d.avg_salary;

-- 更快：使用窗口函数（避免子查询的临时表）
SELECT name, salary
FROM (
    SELECT name, salary,
           AVG(salary) OVER (PARTITION BY dept_id) AS avg_salary
    FROM employees
) t
WHERE salary > avg_salary;
```

**分页查询优化**：

```sql
-- 慢：OFFSET分页在深度分页时性能急剧下降
SELECT * FROM orders ORDER BY id LIMIT 20 OFFSET 100000;
-- 优化器需要扫描100020行，然后丢弃前100000行

-- 快：使用书签分页（Keyset Pagination）
SELECT * FROM orders
WHERE id > 100000  -- 上一页最后一条记录的id
ORDER BY id
LIMIT 20;
-- 只需扫描20行，利用主键索引
```

**EXISTS vs IN**：

```sql
-- 对于小的子查询结果集，IN可能更快（数据库可以建立哈希表）
SELECT * FROM employees WHERE dept_id IN (1, 2, 3);

-- 对于大的子查询结果集，EXISTS通常更快（找到即返回）
SELECT e.* FROM employees e
WHERE EXISTS (SELECT 1 FROM departments d WHERE d.id = e.dept_id AND d.active = true);

-- MySQL 8.0+中，优化器通常能自动选择最优方式，但了解差异有助于调试
```

**UNION ALL vs UNION**：

```sql
-- 慢：UNION会去重（排序操作）
SELECT name FROM employees WHERE dept_id = 1
UNION
SELECT name FROM employees WHERE dept_id = 2;

-- 快：如果确定无重复，使用UNION ALL避免去重排序
SELECT name FROM employees WHERE dept_id = 1
UNION ALL
SELECT name FROM employees WHERE dept_id = 2;
```

**批量操作替代逐行操作**：

```sql
-- 慢：逐行UPDATE
UPDATE employees SET salary = salary * 1.1 WHERE dept_id = 5;
-- 在某些场景下，批量更新比逐行更新快数十倍

-- 优化：确保UPDATE语句使用的列有索引
-- 如果WHERE条件的列没有索引，UPDATE会锁定大量行
CREATE INDEX IF NOT EXISTS idx_emp_dept ON employees(dept_id);
UPDATE employees SET salary = salary * 1.1 WHERE dept_id = 5;

-- 批量INSERT优化
-- 慢：逐条INSERT
INSERT INTO orders VALUES (1, 'A', 100.00);
INSERT INTO orders VALUES (2, 'B', 200.00);
-- ... 一万次

-- 快：批量INSERT（PostgreSQL支持VALUES多行插入）
INSERT INTO orders VALUES
  (1, 'A', 100.00),
  (2, 'B', 200.00),
  (3, 'C', 150.00),
  -- ... 一次提交
;

-- MySQL批量INSERT
INSERT INTO orders (id, name, amount) VALUES
  (1, 'A', 100.00),
  (2, 'B', 200.00),
  (3, 'C', 150.00);
-- 注意：MySQL单次INSERT最大行数受max_allowed_packet限制
```

### 16.11.4 参数调优

数据库参数配置对查询性能有显著影响。以下是最关键的查询相关参数：

**PostgreSQL关键参数**：

| 参数 | 默认值 | 作用 | 调优建议 |
|------|--------|------|----------|
| shared_buffers | 128MB | 共享缓冲区大小 | 设为系统内存的25%，但不超过40% |
| work_mem | 4MB | 排序/哈希操作的工作内存 | 根据并发连接数调整，并发少可增大 |
| effective_cache_size | 4GB | 预估可用缓存大小 | 设为系统内存的50%-75% |
| random_page_cost | 4.0 | 随机I/O代价系数 | SSD设为1.1-1.5 |
| seq_page_cost | 1.0 | 顺序I/O代价系数 | 通常保持默认 |
| default_statistics_target | 100 | 统计采样精度 | 列分布倾斜大时增大到200-1000 |
| maintenance_work_mem | 64MB | 维护操作内存 | ANALYZE、CREATE INDEX等操作的内存 |
| max_parallel_workers_per_gather | 2 | 每个查询节点的最大并行worker | 根据CPU核心数调整 |

**MySQL关键参数**：

| 参数 | 默认值 | 作用 | 调优建议 |
|------|--------|------|----------|
| innodb_buffer_pool_size | 128MB | InnoDB缓冲池 | 设为系统内存的60%-80% |
| join_buffer_size | 256KB | 连接操作缓冲区 | BNLJ使用，增大可减少内表扫描次数 |
| sort_buffer_size | 256KB | 排序缓冲区 | 每个连接独立分配，不宜过大 |
| read_rnd_buffer_size | 256KB | 随机读缓冲区 | MRR使用 |
| tmp_table_size | 16MB | 内存临时表大小上限 | 超出后转磁盘临时表 |
| max_heap_table_size | 16MB | MEMORY引擎表最大大小 | 与tmp_table_size配合使用 |

***

# 查询优化：实战案例

## 16.12 案例分析

本节通过五个完整的真实场景案例，展示查询优化从问题定位到效果验证的完整过程。

### 案例1：连接顺序优化——百万级订单查询加速

**场景描述**：电商平台的订单报表查询，涉及三表连接，生产环境响应时间超过30秒。

**原始查询**：

```sql
-- 订单详情报表：查询某时间段内每个客户的订单数和总金额
SELECT c.name, c.level, COUNT(o.id) AS order_count, SUM(o.amount) AS total_amount
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
WHERE o.created_at BETWEEN '2025-01-01' AND '2025-06-30'
  AND c.level >= 3
GROUP BY c.name, c.level
ORDER BY total_amount DESC
LIMIT 20;
```

**表规模**：customers = 500万行，orders = 2000万行，order_items = 8000万行。

**问题诊断**：

```sql
EXPLAIN ANALYZE
SELECT c.name, c.level, COUNT(o.id) AS order_count, SUM(o.amount) AS total_amount
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
WHERE o.created_at BETWEEN '2025-01-01' AND '2025-06-30'
  AND c.level >= 3
GROUP BY c.name, c.level
ORDER BY total_amount DESC
LIMIT 20;

-- 优化器输出（简化）：
-- Sort  (cost=5823456.78..5823456.83 rows=20 width=56)
--   ->  HashAggregate  (cost=5823450.23..5823455.12 rows=325000 width=56)
--         Group Key: c.name, c.level
--         ->  Hash Join  (cost=2345.67..5821234.56 rows=4250000 width=28)
--               Hash Cond: (o.customer_id = c.id)
--               ->  Hash Join  (cost=890.12..5819567.89 rows=4250000 width=16)
--                     Hash Cond: (oi.order_id = o.id)
--                     ->  Seq Scan on order_items oi  (cost=0.00..4567890.12 rows=80000000 width=8)
--                     ->  Hash  (cost=456.78..456.78 rows=10000000 width=16)
--                           ->  Index Scan using idx_orders_created on orders o
--                                 Index Cond: (created_at BETWEEN ...)
--                                 rows=10000000 (实际只返回4250000)
--               ->  Hash  (cost=1234.56..1234.56 rows=50000 width=20)
--                     ->  Seq Scan on customers c
--                           Filter: (level >= 3)
--                           rows=1500000 (估计)
-- Execution Time: 32456.789 ms
```

**问题分析**：优化器选择了先扫描order_items全表（8000万行），再与orders连接。实际上，orders的时间过滤已经能大幅减少数据量，应该先过滤orders再连接order_items。

**优化方案**：

```sql
-- 方案1：使用Hint强制连接顺序（MySQL）
SELECT /*+ JOIN_ORDER(o, c, oi) LEADING(o, c, oi) */
       c.name, c.level, COUNT(o.id) AS order_count, SUM(o.amount) AS total_amount
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
WHERE o.created_at BETWEEN '2025-01-01' AND '2025-06-30'
  AND c.level >= 3
GROUP BY c.name, c.level
ORDER BY total_amount DESC
LIMIT 20;

-- 方案2：使用CTE引导优化器（PostgreSQL）
WITH filtered_orders AS (
    SELECT id, customer_id, amount
    FROM orders
    WHERE created_at BETWEEN '2025-01-01' AND '2025-06-30'
),
filtered_customers AS (
    SELECT id, name, level
    FROM customers
    WHERE level >= 3
)
SELECT fc.name, fc.level, COUNT(fo.id), SUM(fo.amount)
FROM filtered_orders fo
JOIN filtered_customers fc ON fo.customer_id = fc.id
JOIN order_items oi ON fo.id = oi.order_id
GROUP BY fc.name, fc.level
ORDER BY SUM(fo.amount) DESC
LIMIT 20;
```

**效果**：查询时间从32.4秒降至2.1秒，性能提升15倍。

### 案例2：统计信息过期导致全表扫描

**场景描述**：用户管理系统中，一个原本毫秒级响应的查询突然变慢到数秒。

**变慢的查询**：

```sql
SELECT * FROM users WHERE status = 'active' AND last_login > '2025-06-01';
```

**问题诊断**：

```sql
EXPLAIN ANALYZE SELECT * FROM users WHERE status = 'active' AND last_login > '2025-06-01';

-- 输出：
-- Seq Scan on users  (cost=0.00..125678.90 rows=500000 width=200)
--   Filter: ((status = 'active') AND (last_login > '2025-06-01'))
--   Rows Removed by Filter: 4500000
--   actual time=0.050..890.123 rows=500000 loops=1
-- Execution Time: 890.234 ms

-- 问题：优化器估计rows=500000，实际也是500000，但选择了Seq Scan
-- 原因：users表最近做过大批量数据导入，统计信息未更新
-- 优化器认为表中有500万行，50万行匹配（10%），全表扫描比索引扫描更划算
-- 实际上统计信息已经过时，status='active'只有2万行
```

**根因**：大批量数据导入后未执行ANALYZE，优化器基于过时的统计信息做出了错误判断。

**解决方案**：

```sql
-- 立即解决：更新统计信息
ANALYZE users;

-- 验证统计信息是否准确
SELECT attname, n_distinct, most_common_vals, most_common_freqs,
       histogram_bounds
FROM pg_stats
WHERE tablename = 'users' AND attname = 'status';

-- 再次查看执行计划
EXPLAIN ANALYZE SELECT * FROM users WHERE status = 'active' AND last_login > '2025-06-01';
-- 现在优化器选择了Index Scan：
-- Index Scan using idx_users_status_login on users
--   Index Cond: ((status = 'active') AND (last_login > '2025-06-01'))
--   actual time=0.025..8.456 rows=20000 loops=1
-- Execution Time: 8.567 ms

-- 长期解决：设置自动统计收集
-- PostgreSQL默认在autovacuum中自动收集统计信息
-- 确认autovacuum已开启
SHOW autovacuum;
-- 如果关闭了，重新开启
ALTER SYSTEM SET autovacuum = on;

-- 对于频繁更新的大表，降低触发阈值
ALTER TABLE users SET (autovacuum_vacuum_scale_factor = 0.05);  -- 默认0.2
ALTER TABLE users SET (autovacuum_analyze_scale_factor = 0.02);  -- 默认0.1
```

**效果**：查询时间从890ms降至8.5ms，性能提升100倍。关键教训：大批量DML操作后必须执行ANALYZE。

### 案例3：缺失索引导致的排序溢出

**场景描述**：后台管理系统的报表查询需要对大量数据排序，频繁出现磁盘临时文件。

**问题查询**：

```sql
-- 用户活跃度报表
SELECT u.name, u.email, COUNT(l.id) AS login_count,
       MAX(l.login_time) AS last_login
FROM users u
JOIN login_logs l ON u.id = l.user_id
WHERE l.login_time >= '2025-01-01'
GROUP BY u.id, u.name, u.email
ORDER BY login_count DESC
LIMIT 50;
```

**诊断过程**：

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT u.name, u.email, COUNT(l.id) AS login_count, MAX(l.login_time) AS last_login
FROM users u
JOIN login_logs l ON u.id = l.user_id
WHERE l.login_time >= '2025-01-01'
GROUP BY u.id, u.name, u.email
ORDER BY login_count DESC
LIMIT 50;

-- 关键输出：
-- Limit  (cost=1234567.89..1234567.90 rows=50 width=80) (actual time=4567.890..4567.910 rows=50 loops=1)
--   ->  Sort  (cost=1234567.89..1236789.01 rows=500000 width=80) (actual time=4567.890..4567.900 rows=50 loops=1)
--         Sort Key: (COUNT(l.id)) DESC
--         Sort Method: external merge  Disk: 12345kB  <-- 问题在这里！排序溢出到磁盘
--         ->  HashAggregate  (cost=890123.45..1234567.89 rows=500000 width=80)
--               Group Key: u.id, u.name, u.email
--               Batches: 2  Memory Usage: 65537kB  <-- Hash聚合也分批了
```

**问题分析**：

1. `login_logs`表缺少`(login_time, user_id)`复合索引，导致大量行需要在内存中处理
2. `work_mem`默认4MB不足以容纳聚合和排序的中间结果
3. Hash聚合分2批执行（Batches: 2），排序溢出到磁盘（Sort Method: external merge）

**优化方案**：

```sql
-- 1. 创建复合索引（关键）
CREATE INDEX idx_login_logs_time_user ON login_logs(login_time, user_id);
-- login_time在前用于范围过滤，user_id在后用于连接

-- 2. 对特定查询增大work_mem
SET LOCAL work_mem = '64MB';  -- 仅对当前事务生效
-- 或在查询级别设置
SET work_mem = '64MB';
-- ... 执行查询 ...
RESET work_mem;

-- 3. 考虑使用物化视图缓存报表数据（适用于固定报表）
CREATE MATERIALIZED VIEW mv_user_login_stats AS
SELECT u.id, u.name, u.email, COUNT(l.id) AS login_count,
       MAX(l.login_time) AS last_login
FROM users u
JOIN login_logs l ON u.id = l.user_id
WHERE l.login_time >= '2025-01-01'
GROUP BY u.id, u.name, u.email;

-- 定期刷新
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_login_stats;
```

**效果**：查询时间从4.5秒降至0.3秒，消除了磁盘临时文件的使用。

### 案例4：选择性估计偏差导致的连接算法错误

**场景描述**：人力资源系统的复杂查询，优化器选择了错误的连接算法。

**问题查询**：

```sql
-- 查找2024年后入职且薪资高于部门平均值的员工
SELECT e.name, e.salary, d.name AS dept_name
FROM employees e
JOIN departments d ON e.dept_id = d.id
WHERE e.hire_date >= '2024-01-01'
  AND e.salary > (SELECT AVG(salary) FROM employees e2 WHERE e2.dept_id = e.dept_id);
```

**诊断**：

```sql
EXPLAIN ANALYZE
SELECT e.name, e.salary, d.name AS dept_name
FROM employees e
JOIN departments d ON e.dept_id = d.id
WHERE e.hire_date >= '2024-01-01'
  AND e.salary > (SELECT AVG(salary) FROM employees e2 WHERE e2.dept_id = e.dept_id);

-- 优化器选择了Nested Loop Join：
-- Nested Loop  (cost=2345.67..567890.12 rows=100 width=48)
--   ->  Index Scan using idx_hire_date on employees e
--         Filter: (salary > (SubPlan 1))
--   ->  Index Scan using idx_emp_pk on departments d
--         Index Cond: (id = e.dept_id)
-- Execution Time: 15234.567 ms

-- 问题：Nested Loop对100万行外表执行相关子查询，效率极低
```

**根因**：相关子查询导致每行都要执行一次子查询，优化器没有将其转换为JOIN。

**优化方案**：

```sql
-- 将相关子查询改写为JOIN
SELECT e.name, e.salary, d.name AS dept_name
FROM employees e
JOIN departments d ON e.dept_id = d.id
JOIN (
    SELECT dept_id, AVG(salary) AS avg_salary
    FROM employees
    GROUP BY dept_id
) dept_avg ON e.dept_id = dept_avg.dept_id
WHERE e.hire_date >= '2024-01-01'
  AND e.salary > dept_avg.avg_salary;

-- 优化后执行计划：
-- Hash Join  (cost=456.78..89012.34 rows=100 width=48)
--   ->  Index Scan using idx_hire_date on employees e
--         Filter: (salary > ...)
--   ->  Hash  (cost=345.67..345.67 rows=100 width=12)
--         ->  HashAggregate  (cost=234.56..345.67 rows=100 width=12)
--               ->  Seq Scan on employees
-- Execution Time: 156.789 ms
```

**效果**：查询时间从15.2秒降至156ms，性能提升97倍。

### 案例5：列存储场景下的投影下推优化

**场景描述**：数据分析平台的宽表查询，表有200列，但查询只需要5列。

**问题查询**：

```sql
-- 分析平台宽表：200+列的日志表
SELECT event_type, user_id, COUNT(*) as cnt, AVG(duration) as avg_dur
FROM event_logs
WHERE event_date = '2025-06-25'
GROUP BY event_type, user_id
ORDER BY cnt DESC
LIMIT 100;
```

**诊断**：

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT event_type, user_id, COUNT(*) as cnt, AVG(duration) as avg_dur
FROM event_logs
WHERE event_date = '2025-06-25'
GROUP BY event_type, user_id
ORDER BY cnt DESC
LIMIT 100;

-- 输出：
-- Limit  (cost=123456.78..123456.83 rows=100 width=32) (actual time=890.123..890.150 rows=100 loops=1)
--   ->  Sort  (cost=123456.78..123489.01 rows=50000 width=32) (actual time=890.123..890.140 rows=100 loops=1)
--         Sort Key: (COUNT(*)) DESC
--         Sort Method: top-N heapsort  Memory: 30kB
--         ->  HashAggregate  (cost=123234.56..123456.78 rows=50000 width=32)
--               Group Key: event_type, user_id
--               Batches: 1  Memory Usage: 12345kB
--               ->  Seq Scan on event_logs  (cost=0.00..112345.67 rows=500000 width=20)
--                     Filter: (event_date = '2025-06-25')
--                     Rows Removed by Filter: 9500000
--                     Buffers: shared hit=123 read=45678  <-- 大量磁盘读取！
-- Planning Time: 0.456 ms
-- Execution Time: 890.567 ms
```

**问题**：event_logs表有200列，每行数据量大，即使只读取4列，行式存储也要读取整行。导致大量磁盘I/O（Buffers: shared read=45678）。

**优化方案**：

```sql
-- 方案1：在列式存储（如Citus或TimescaleDB的压缩表）中查询
-- 列式存储天然支持只读取需要的列

-- 方案2：为常用查询创建物化视图
CREATE MATERIALIZED VIEW mv_event_summary AS
SELECT event_type, user_id, event_date, COUNT(*) as cnt, AVG(duration) as avg_dur
FROM event_logs
GROUP BY event_type, user_id, event_date;

-- 在物化视图上查询，数据量大幅减少
SELECT event_type, user_id, cnt, avg_dur
FROM mv_event_summary
WHERE event_date = '2025-06-25'
ORDER BY cnt DESC
LIMIT 100;

-- 方案3：使用投影下推的Partial Index
CREATE INDEX idx_event_logs_summary ON event_logs(event_date, event_type, user_id)
INCLUDE (duration);
-- INCLUDE子句将duration列存储在索引叶节点中
-- 查询可以使用Index-Only Scan，完全避免回表
```

**效果**：查询时间从890ms降至45ms，磁盘读取从45678页降至23页。

***

# 查询优化：常见误区

## 16.13 常见误区与纠正

### 误区1：优化器总是能选择最优计划

**误区描述**：很多开发者认为数据库优化器足够智能，不需要人工干预。

**事实**：优化器基于统计信息和代价模型做决策，当统计信息不准确、代价模型不匹配实际硬件特性、或SQL写法过于复杂时，优化器可能做出次优甚至错误的选择。

**典型案例**：

```sql
-- 优化器选择了Nested Loop而不是Hash Join
-- 因为它低估了连接结果的行数
SELECT COUNT(*) FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'pending';

-- EXPLAIN显示：
-- Nested Loop  (cost=12.34..5678.90 rows=10 width=8)  -- 估计10行
--   actual rows=150000  -- 实际15万行！
-- 代价估算偏差导致选择了错误的连接算法

-- 纠正方法：
-- 1. 更新统计信息
ANALYZE orders;
ANALYZE customers;

-- 2. 调整相关列的统计精度
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 500;
ANALYZE orders;

-- 3. 如果仍不满意，使用Hint强制连接算法
SELECT /*+ USE_HASH(o c) */ COUNT(*) FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'pending';
```

### 误区2：索引越多越好

**误区描述**：为了提升查询性能，给每个WHERE条件列都创建索引。

**事实**：每个索引都有代价：

```sql
-- 写入代价演示
-- 创建5个索引后
CREATE INDEX idx1 ON t(col1);
CREATE INDEX idx2 ON t(col2);
CREATE INDEX idx3 ON t(col3);
CREATE INDEX idx4 ON t(col4);
CREATE INDEX idx5 ON t(col5);

-- 一次INSERT操作需要同时更新5个索引
-- 如果表有100万行，每次INSERT的索引维护代价约为 O(5 × log(1000000)) ≈ 100次磁盘操作
-- 相比无索引的1次磁盘操作，写入性能下降约100倍

-- 过多索引还导致：
-- 1. ANALYZE收集统计信息的时间增加
-- 2. 缓冲池被索引页占满，热数据被挤出缓存
-- 3. 优化器搜索空间增大，可能选择次优索引

-- 纠正方法：
-- 1. 定期审查索引使用情况
-- PostgreSQL：
SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE relname = 'orders'
ORDER BY idx_scan DESC;

-- MySQL：
SELECT object_schema, object_name, index_name, count_star
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema = 'your_db'
ORDER BY count_star ASC;  -- 找出从未使用的索引

-- 2. 删除未使用的索引
DROP INDEX idx_unused ON t;

-- 3. 合并功能相似的索引
-- 删除 (a) 索引，保留 (a, b) 索引（因为(a,b)可以服务于WHERE a = ?）
```

### 误区3：EXPLAIN中的rows估计值不重要

**误区描述**：认为EXPLAIN中的rows只是估计，实际执行才会准确。

**事实**：rows估计值是优化器决策的基础。估计值与实际值的偏差直接反映统计信息的准确性：

```sql
-- 检查估计值与实际值的偏差
EXPLAIN (ANALYZE)
SELECT * FROM orders WHERE status = 'shipped' AND amount > 100;

-- 输出中关注：
-- Index Scan using idx_status on orders
--   Filter: (amount > 100)
--   Rows Removed by Filter: 45000
--   rows=50000  (估计50000行)
--   actual rows=5000  (实际只有5000行！)

-- 估计值50000 vs 实际值5000，偏差10倍
-- 这意味着后续的连接操作也会有10倍以上的基数估计偏差
-- 可能导致完全不同的执行计划选择

-- 纠正方法：
-- 1. 更新统计信息
ANALYZE orders;

-- 2. 增加status列的统计精度
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
ANALYZE orders;

-- 3. 检查直方图是否准确
SELECT most_common_vals, most_common_freqs, histogram_bounds
FROM pg_stats
WHERE tablename = 'orders' AND attname = 'status';
```

### 误区4：子查询一定比JOIN慢

**误区描述**：所有子查询都应该改写为JOIN。

**事实**：MySQL 5.6+和PostgreSQL都对子查询做了大量优化，某些场景下子查询反而更快：

```sql
-- 场景1：EXISTS通常比IN+JOIN更高效（MySQL优化更好）
-- 慢：IN子查询可能导致临时表
SELECT * FROM products WHERE id IN (SELECT product_id FROM order_items WHERE quantity > 10);

-- 快：EXISTS短路求值，找到即返回
SELECT * FROM products p WHERE EXISTS (
    SELECT 1 FROM order_items oi WHERE oi.product_id = p.id AND oi.quantity > 10
);

-- 场景2：派生表（子查询作为FROM子句的表）有时比JOIN更清晰
-- MySQL 8.0的派生表合并优化会自动将子查询"展开"
SELECT d.dept_name, t.avg_salary
FROM departments d
JOIN (SELECT dept_id, AVG(salary) AS avg_salary FROM employees GROUP BY dept_id) t
ON d.id = t.dept_id;

-- 场景3：标量子查询在SELECT列表中
-- 这个场景下JOIN会改变结果集（产生笛卡尔积的膨胀）
SELECT name, (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.id) AS order_count
FROM customers c;
-- 如果改写为JOIN，会因为COUNT的问题产生错误结果
```

### 误区5：增加内存参数一定能提速

**误区描述**：增大work_mem、sort_buffer_size等内存参数就能提升查询性能。

**事实**：内存参数的设置需要考虑并发场景：

```sql
-- 危险的设置方式
SET work_mem = '256MB';  -- 全局设置，每个连接的每个排序操作都分配256MB
-- 如果有100个并发连接，每个连接有3个排序操作：
-- 100 × 3 × 256MB = 76.8GB 内存
-- 远超服务器内存，导致频繁swap，性能反而急剧下降

-- 正确的设置方式：
-- 1. 设置保守的全局值
SET work_mem = '16MB';  -- 全局默认值

-- 2. 对特定查询/事务增大
SET LOCAL work_mem = '128MB';  -- 仅当前事务
-- 执行需要大排序的查询
RESET work_mem;  -- 事务结束后恢复

-- 3. 在应用层使用SET LOCAL
-- BEGIN;
-- SET LOCAL work_mem = '128MB';
-- SELECT ... ORDER BY ... LIMIT 100000;  -- 需要大内存排序
-- COMMIT;  -- work_mem自动恢复
```

### 误区6：EXPLAIN ANALYZE的执行时间就是查询的真实性能

**误区描述**：EXPLAIN ANALYZE显示的执行时间就是生产环境的性能。

**事实**：EXPLAIN ANALYZE会真正执行查询，但存在以下差异：

```sql
-- 1. 缓存效应：第一次执行时数据从磁盘读取，后续执行可能全在缓存中
-- 第一次
EXPLAIN ANALYZE SELECT * FROM large_table WHERE id = 12345;
-- Execution Time: 45.678 ms（磁盘读取）

-- 第二次（数据已缓存）
EXPLAIN ANALYZE SELECT * FROM large_table WHERE id = 12345;
-- Execution Time: 0.123 ms（全缓存命中）

-- 2. 锁等待：EXPLAIN ANALYZE不考虑锁等待时间
-- 在高并发环境下，实际执行时间会包含锁等待

-- 3. 网络延迟：EXPLAIN ANALYZE不包含客户端-服务器之间的网络传输时间

-- 4. 结果集大小：EXPLAIN ANALYZE将结果发送回客户端，
-- 大结果集的网络传输时间可能远超执行时间

-- 正确的性能评估方法：
-- 1. 使用pg_stat_statements查看平均执行时间
-- 2. 在生产环境使用APM工具监控
-- 3. 考虑并发场景下的实际表现
```

***

# 查询优化：练习方法

## 16.14 实验与练习

### 实验环境搭建

```sql
-- 创建实验数据库和测试表
CREATE DATABASE query_optimization_lab;
\c query_optimization_lab

-- 创建employees表（100万行）
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(200),
    department_id INT,
    salary NUMERIC(10,2),
    hire_date DATE,
    status VARCHAR(20),
    bio TEXT
);

-- 创建departments表（100行）
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    budget NUMERIC(15,2),
    manager_id INT
);

-- 创建orders表（500万行）
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INT,
    amount NUMERIC(10,2),
    status VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 使用pgBench或自定义脚本填充测试数据
-- 参考第十四章索引实现中的数据生成方法
```

### 练习题

**练习1：EXPLAIN输出解读**

给定以下EXPLAIN输出，回答问题：

Hash Join  (cost=234.56..8901.23 rows=50000 width=48) (actual time=1.234..45.678 rows=48500 loops=1)
  Hash Cond: (o.customer_id = c.id)
  ->  Seq Scan on orders o  (cost=0.00..6543.21 rows=100000 width=24)
        Filter: (created_at > '2025-01-01')
        Rows Removed by Filter: 400000
  ->  Hash  (cost=123.45..123.45 rows=5000 width=24)
        Buckets: 8192  Batches: 1  Memory Usage: 352kB
        ->  Seq Scan on customers c  (cost=0.00..123.45 rows=5000 width=24)
Planning Time: 0.567 ms
Execution Time: 45.890 ms

问题：
1. orders表中`created_at > '2025-01-01'`的选择性是多少？
2. Hash Join的构建侧是哪个表？为什么选择这个表作为构建侧？
3. 如果将customers表的5000行改为500000行，执行计划会如何变化？
4. Memory Usage: 352kB说明了什么？如果增大到352MB会有什么影响？

**练习2：统计信息与选择性估计**

```sql
-- 给定以下统计信息
-- employees.salary:
--   n_distinct = 15000
--   most_common_vals = {50000, 60000, 75000, 80000}
--   most_common_freqs = {0.15, 0.12, 0.10, 0.08}
--   total_rows = 1000000

-- 估算以下查询的选择性：
-- 1. SELECT * FROM employees WHERE salary = 60000;
-- 2. SELECT * FROM employees WHERE salary = 95000;
-- 3. SELECT * FROM employees WHERE salary > 80000;
-- 4. SELECT * FROM employees WHERE salary > 50000 AND salary < 70000;
```

**练习3：索引设计**

```sql
-- 给定以下查询工作负载，设计最优的索引方案
-- 表：orders(id, customer_id, product_id, amount, status, created_at)
-- 查询1：SELECT * FROM orders WHERE customer_id = ? AND status = 'pending'
-- 查询2：SELECT * FROM orders WHERE created_at BETWEEN ? AND ? ORDER BY amount DESC
-- 查询3：SELECT customer_id, SUM(amount) FROM orders WHERE status = 'shipped' GROUP BY customer_id
-- 查询4：SELECT * FROM orders WHERE amount > 1000 AND product_id = ?

-- 要求：
-- 1. 为每个查询设计索引
-- 2. 检查是否有冗余索引
-- 3. 评估每个索引的覆盖情况（是否需要回表）
-- 4. 考虑写入性能的影响
```

**练习4：查询改写**

```sql
-- 将以下慢查询改写为等价的高性能查询

-- 原始查询1（慢）
SELECT c.name, COUNT(DISTINCT o.id) as order_count
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
WHERE c.created_at >= '2025-01-01'
  AND oi.quantity > 5
GROUP BY c.name
HAVING COUNT(DISTINCT o.id) > 10;

-- 原始查询2（慢）
SELECT * FROM products
WHERE id IN (
    SELECT product_id FROM order_items
    WHERE order_id IN (
        SELECT id FROM orders WHERE status = 'cancelled'
    )
);

-- 原始查询3（慢）
SELECT u.name, MAX(l.login_time) as last_login
FROM users u, login_logs l
WHERE u.id = l.user_id
  AND l.login_time > DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY u.name;
```

**练习5：执行计划对比**

```sql
-- 对以下三种写法获取EXPLAIN输出并对比
-- 表：employees(id, name, department_id, salary, hire_date)

-- 写法A：子查询
SELECT * FROM employees WHERE department_id IN
    (SELECT id FROM departments WHERE budget > 1000000);

-- 写法B：JOIN
SELECT e.* FROM employees e
JOIN departments d ON e.department_id = d.id
WHERE d.budget > 1000000;

-- 写法C：EXISTS
SELECT * FROM employees e WHERE EXISTS
    (SELECT 1 FROM departments d WHERE d.id = e.department_id AND d.budget > 1000000);

-- 对比项目：
-- 1. 哪种写法生成的执行计划最简洁？
-- 2. 哪种写法使用了连接算法？
-- 3. 在不同数据规模下（小表 vs 大表），三种写法的性能差异？
-- 4. 优化器是否将子查询自动转换为JOIN？
```

***

# 本章小结

## 16.15 核心要点回顾

本章系统介绍了数据库查询优化的完整技术栈，从理论基础到实战应用，涵盖了查询优化器的内部机制和性能调优方法论。

### 核心知识体系

查询优化
├── 查询处理流程：解析 → 重写 → 优化 → 执行
├── 代数优化（规则驱动）
│   ├── 选择下推：尽早过滤数据
│   ├── 投影下推：尽早裁剪列
│   ├── 连接重排序：小结果集优先
│   ├── 连接消除：消除不必要的连接
│   └── 子查询展平：参与连接顺序优化
├── 基于代价的优化（CBO）
│   ├── 代价模型：I/O代价 + CPU代价
│   ├── 统计信息：NDV、直方图、MCV
│   ├── 选择性估计：等值、范围、多谓词组合
│   └── 基数估计：误差传播是最大挑战
├── 连接算法
│   ├── 嵌套循环连接：外表小 + 内表有索引
│   ├── 排序归并连接：已排序 / 范围连接
│   └── 哈希连接：等值连接 + 内存充足
├── 连接顺序优化
│   ├── 动态规划（System R）：n ≤ 15
│   ├── 贪心算法：n 较大时的快速近似
│   └── 遗传算法（GEQO）：n > 12 时使用
├── 执行模型
│   ├── 物化执行：实现简单，中间结果I/O大
│   └── 流水线执行（Volcano）：按需拉取，减少I/O
├── 诊断与调优
│   ├── EXPLAIN解读：关注代价、行数估计、实际行数
│   ├── 索引策略：覆盖索引、部分索引、避免冗余
│   ├── SQL改写：子查询转JOIN、分页优化、批量操作
│   └── 参数调优：work_mem、shared_buffers、innodb_buffer_pool_size
└── 前沿发展
    ├── 自适应查询优化：执行时动态调整
    └── 机器学习优化：学习型基数估计器、代价模型

### 关键实践原则

1. **先诊断，后优化**：使用EXPLAIN ANALYZE获取实际执行数据，基于数据做决策，而非凭直觉猜测。

2. **统计信息是一切的基础**：CBO的决策质量完全依赖统计信息的准确性。大批量DML操作后务必执行ANALYZE。

3. **索引要精准，不要贪多**：设计索引时考虑查询模式、选择性、覆盖情况，定期清理未使用的索引。

4. **SQL改写往往比加索引更有效**：连接替代子查询、避免SELECT *、使用批量操作等SQL层面的优化往往能带来数量级的性能提升。

5. **理解优化器的局限性**：优化器不是万能的，在统计信息不准、代价模型偏差、复杂查询等场景下，需要人工干预（Hint、计划稳定性）。

### 性能优化的优先级

在实际项目中，应按以下优先级进行查询优化：

| 优先级 | 措施 | 预期效果 | 实施成本 |
|--------|------|----------|----------|
| 1 | SQL改写 | 10-1000倍提升 | 低 |
| 2 | 创建合适索引 | 10-100倍提升 | 低-中 |
| 3 | 更新统计信息 | 2-100倍提升 | 低 |
| 4 | 参数调优 | 1.5-5倍提升 | 低 |
| 5 | 架构优化（物化视图、分区表） | 5-50倍提升 | 中-高 |
| 6 | 硬件升级（SSD、增加内存） | 2-10倍提升 | 高 |

***