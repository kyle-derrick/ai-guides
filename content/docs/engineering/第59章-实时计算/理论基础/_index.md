---
title: "理论基础"
type: docs
---
# 实时计算理论基础

实时计算是现代数据工程的核心支柱之一。与传统的批处理不同，实时计算要求系统在数据到达的瞬间完成处理，延迟通常在毫秒到秒级别。本章从流处理架构、窗口机制、状态管理和一致性语义四个维度，系统梳理实时计算的理论根基，为后续章节的工程实践奠定坚实基础。

---

## 一、流处理架构

### 1.1 什么是流处理

流处理（Stream Processing）是一种数据处理范式：数据以连续、无界的事件流形式产生，系统逐条或分微批（micro-batch）地处理这些事件，而不是等待数据积累到一定量后再统一计算。

与批处理的关键区别：

| 维度 | 批处理（Batch） | 流处理（Stream） |
|------|----------------|-----------------|
| 数据边界 | 有界、已知 | 无界、持续到达 |
| 延迟 | 分钟到小时级 | 毫秒到秒级 |
| 吞吐量 | 单次高吞吐 | 持续稳定吞吐 |
| 容错粒度 | 整个作业 | 单条记录/微批次 |
| 典型场景 | 报表生成、ETL | 实时监控、风控、推荐 |

### 1.2 流处理架构演进

#### 第一代：自研系统（2000年代早期）

Google 的 MapReduce 论文催生了 Hadoop 生态，但其本质仍是批处理。企业为满足实时需求，往往在 Hadoop 之上叠加消息队列（如 ActiveMQ）和自定义消费者，架构脆弱且运维成本高。

#### 第二代：专用流处理引擎（2011-2014）

- **Apache Storm**（2011）：首个广泛使用的开源流处理框架。采用 Tuple 流模型，开发者手动管理可靠性（acking 机制）。优点是真正的逐条处理、延迟极低；缺点是编程模型原始、状态管理困难、exactly-once 语义需要开发者自行实现。
- **Apache S4**（2010）：Yahoo 开源的分布式流处理平台，采用事件驱动架构，但社区活跃度低，最终被 Storm 取代。

#### 第三代：统一引擎（2014-至今）

- **Apache Flink**（2014）：以流处理为核心设计理念，将批处理视为流处理的特殊情况（有界流）。提供精确的 exactly-once 语义、强大的状态管理和丰富的窗口机制，成为当前实时计算的事实标准。
- **Apache Spark Streaming / Structured Streaming**（2013/2016）：早期采用微批模型（将流切分为小的批处理作业），Structured Streaming 引入连续处理模式（Continuous Processing），延迟可降至毫秒级。
- **Apache Beam**（2016）：Google 将内部 Dataflow 模型开源后的产物，提供统一的编程模型，可运行在 Flink、Spark、Google Cloud Dataflow 等多种后端之上。

### 1.3 核心架构模式

#### Lambda 架构

Lambda 架构由 Nathan Marz 提出，是最早被广泛采用的实时+离线混合架构：

数据源 → 批处理层（Batch Layer）→ 批视图（Batch View）──┐
        → 速度层（Speed Layer）  → 实时视图（Realtime View）→ 合并视图（Serving Layer）

- **批处理层**：对全量历史数据进行计算，生成精确的批视图。保证准确性但延迟高。
- **速度层**：对最近数据进行近实时计算，生成实时视图。保证时效性但可能有误差。
- **服务层**：合并批视图和实时视图，对外提供查询接口。

Lambda 架构的问题：同一套逻辑需要在两个框架中各实现一次，维护成本翻倍；批视图和实时视图的语义可能不一致。

#### Kappa 架构

Jay Kreps（Kafka 创始人）提出 Kappa 架构，核心思想是去掉批处理层，一切以流处理为核心：

数据源 → 消息队列（Kafka）→ 流处理引擎（Flink/Spark）→ 结果存储

需要重新计算时，不启动批处理作业，而是从 Kafka 的起始位置重新消费数据并重新处理。Kappa 架构的前提是消息队列必须能持久化全量历史数据（如 Kafka 的 log retention）。

Kappa 架构的优势：只需要维护一套流处理代码；但对消息队列的存储能力和流处理引擎的重放能力要求很高。

#### 混合架构（Lakehouse 模式）

现代数据湖仓（Lakehouse）架构融合了两者优势：

数据源 → Kafka → Flink → 实时表（实时更新）──→ 查询引擎（Trino/Spark）
                  ↓
              数据湖（Iceberg/Hudi/Delta Lake）→ 批量回溯与审计

使用 Apache Iceberg、Apache Hudi 或 Delta Lake 作为存储格式，Flink 负责实时写入和 upsert，支持 ACID 事务。当需要修正逻辑时，可以通过时间旅行（Time Travel）功能回溯历史数据。

### 1.4 数据传输层：消息队列

消息队列是流处理系统的基础设施，负责数据的缓冲、持久化和分发。

#### Apache Kafka

Kafka 是实时计算生态中最重要的组件之一：

- **分区（Partition）**：Topic 被分为多个 Partition，每个 Partition 是一个有序、不可变的消息序列。Partition 是并行度的基本单位——消费者组中的每个消费者负责一个或多个 Partition。
- **副本（Replication）**：每个 Partition 有多个副本，分布在不同的 Broker 上。Leader 副本处理读写，Follower 副本同步数据。通过 ISR（In-Sync Replicas）机制保证数据不丢失。
- **消费者组（Consumer Group）**：同一 Group 内的消费者共同消费一个 Topic，每个 Partition 只被 Group 内的一个消费者消费。不同 Group 独立消费，互不影响。
- **Exactly-once 语义**：Kafka 0.11+ 引入幂等生产者（Idempotent Producer）和事务 API，配合消费者端的 offset 提交，可实现端到端的 exactly-once。

#### Apache Pulsar

Pulsar 是 Apache 基金会的另一款消息系统，架构上将计算和存储分离：

- **BookKeeper 存储层**：消息持久化在 BookKeeper 的 Bookie 节点上，支持分层存储（Tiered Storage），可将冷数据卸载到 S3/HDFS。
- **无损扩容**：由于计算和存储分离，新增 Broker 不需要数据迁移，扩容效率远高于 Kafka。
- **多租户**：原生支持 Tenant → Namespace → Topic 的多级隔离。
- **Pulsar Functions**：内置轻量级流处理能力，适合简单的 ETL 转换。

#### 对比

| 特性 | Kafka | Pulsar |
|------|-------|--------|
| 架构 | 计算存储耦合 | 计算存储分离 |
| 扩容效率 | 需要数据再平衡 | 无需数据迁移 |
| 多租户 | 需要外部工具 | 原生支持 |
| 生态成熟度 | 极高（Flink/Spark 原生集成） | 中等，快速增长 |
| 运维复杂度 | 中等 | 较高（需维护 BookKeeper） |
| 吞吐量 | 极高 | 极高 |

---

## 二、窗口机制

### 2.1 为什么需要窗口

流处理面对的是无界数据流，无法像批处理那样对"全部数据"执行聚合。窗口（Window）机制将无界流切分为有限的数据块，使得聚合操作成为可能。

窗口的核心问题：什么时候开始计算？什么时候触发输出？哪些数据属于这个窗口？

### 2.2 窗口类型

#### 滚动窗口（Tumbling Window）

滚动窗口将数据流切分为固定大小、不重叠的区间。

时间轴:  |----窗口1----|----窗口2----|----窗口3----|
事件:    a b c       d e f       g h i

- 窗口大小固定，如 10 秒
- 每个事件恰好属于一个窗口
- 窗口之间无重叠、无间隙

Flink 示例：

```java
stream
    .keyBy(event -> event.getCategoryId())
    .window(TumblingEventTimeWindows.of(Time.seconds(10)))
    .aggregate(new CountAggregate());
```

#### 滑动窗口（Sliding Window）

滑动窗口有固定大小，但窗口按指定步长（slide）滑动。当步长小于窗口大小时，事件可能属于多个窗口。

时间轴: |---窗口1---|
             |---窗口2---|
                 |---窗口3---|

典型场景：计算最近 1 小时的平均值，每 5 分钟更新一次。窗口大小 1 小时，步长 5 分钟。

Flink 示例：

```java
stream
    .keyBy(event -> event.getCategoryId())
    .window(SlidingEventTimeWindows.of(Time.hours(1), Time.minutes(5)))
    .aggregate(new AverageAggregate());
```

注意：滑动窗口的计算开销与"窗口大小 / 步长"成正比。步长越小，同一事件被重复计算的次数越多。

#### 会话窗口（Session Window）

会话窗口根据事件之间的活跃间隔动态确定窗口边界。如果两个事件之间的间隔超过指定的 gap，则视为不同的会话。

事件:  --a--b-----c--d-e--f-----------g--h--
              ↑ gap↑         ↑ gap ↑
会话窗口: |---窗口1---|  |窗口2|  |---窗口3---|

典型场景：用户行为分析。一个用户在 30 分钟内持续操作算一个会话，超过 30 分钟无操作则会话结束。

Flink 示例：

```java
stream
    .keyBy(event -> event.getUserId())
    .window(EventTimeSessionWindows.withGap(Time.minutes(30)))
    .aggregate(new SessionAggregate());
```

#### 全局窗口（Global Window）

全局窗口将所有具有相同 key 的事件放入同一个窗口。它本身不会触发计算，需要配合自定义的触发器（Trigger）来决定何时输出结果。

典型场景：需要根据业务逻辑灵活控制输出时机的情况。

### 2.3 时间语义

时间是窗口机制的核心维度，流处理中有三种时间概念：

| 时间类型 | 定义 | 特点 |
|---------|------|------|
| 事件时间（Event Time） | 事件在数据源中产生的时间 | 与处理速度无关，可重现，但需要等待乱序事件 |
| 处理时间（Processing Time） | 事件到达处理引擎的时间 | 实现简单，但受处理延迟影响，结果不可重现 |
| 摄入时间（Ingestion Time） | 事件进入消息队列的时间 | 介于两者之间，但丢失了原始时间精度 |

**为什么事件时间如此重要？**

假设一个监控系统在 10:00:00 收到一条 09:59:50 产生的事件（网络延迟 10 秒）。如果使用处理时间，这个事件会被归入 10:00:00-10:00:10 的窗口；如果使用事件时间，则正确归入 09:59:50-10:00:00 的窗口。

事件时间还保证了重放（Replay）的一致性——从 Kafka 重新消费数据时，事件时间是固定的，计算结果可重现。

#### 乱序事件与 Watermark

现实中的事件流几乎不可能严格按时间排序。网络延迟、分布式系统的时钟偏差、消息重试等原因都会导致事件乱序到达。

**Watermark（水位线）** 是 Flink 中处理乱序事件的核心机制。Watermark 是一个单调递增的时间戳，表示"时间戳小于 Watermark 的事件已经全部到达"。

事件流:  e1(t=1)  e3(t=3)  e2(t=2)  e5(t=5)  e4(t=4)
Watermark:              W(2)         W(4)

当 Watermark 到达某个窗口的结束时间时，该窗口被触发计算。

Watermark 的生成策略：

- **固定延迟**：允许固定时间的延迟。如 `WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofSeconds(5))` 表示允许最多 5 秒的乱序。
- **周期性生成**：每隔固定时间从事件流中提取最大时间戳并减去延迟。

延迟事件（Late Event）：如果事件到达时其所属窗口已经触发，则该事件被视为迟到事件。处理方式包括：
- 丢弃（默认行为）
- 输出到侧输出流（Side Output）
- 触发窗口重新计算（Flink 的 allowedLateness）

### 2.4 窗口聚合

窗口聚合是窗口机制最核心的应用。常见聚合类型：

- **增量聚合**：每到达一条事件就更新中间结果，如 `ReduceFunction`、`AggregateFunction`。内存占用小，适合大规模数据。
- **全量窗口聚合**：缓存窗口内所有事件，窗口触发时一次性计算，如 `ProcessWindowFunction`。灵活但内存开销大。

---

## 三、状态管理

### 3.1 为什么需要状态

流处理任务通常需要记住之前事件的信息。例如：

- 计算滑动平均值：需要记住之前 N 个值
- 检测欺诈模式：需要记住用户最近的行为序列
- 去重：需要记住已经处理过的事件 ID

这些需要记住的信息就是**状态（State）**。

### 3.2 状态类型

#### 算子状态（Operator State）

算子状态绑定到特定的算子实例。当任务重新分配时（如扩缩容），状态按照预定义的策略重新分配。

典型应用：Kafka Source 的 offset 存储——每个算子实例存储自己负责的 Partition 的 offset。

#### 键控状态（Keyed State）

键控状态与某个 key 绑定。只有在 `keyBy()` 之后才能使用键控状态。状态按 key 分区存储，同一个 key 的所有状态在一个 TaskManager 上。

键控状态是流处理中最常用的状态类型。

#### 常用状态原语

| 状态类型 | 数据结构 | 适用场景 |
|---------|---------|---------|
| ValueState | 单个值 | 记录某个指标的最新值 |
| ListState | 值列表 | 收集一段时间内的事件 |
| MapState | 键值映射 | 需要按 key 查询的聚合 |
| ReducingState | 可约值 | 增量聚合（需提供 ReduceFunction） |
| AggregatingState | 聚合值 | 增量聚合（需提供 AggregateFunction） |

### 3.3 状态后端（State Backend）

状态后端决定了状态如何存储和访问：

#### HashMapStateBackend（原 MemoryStateBackend）

将状态存储在 JVM 堆内存中。读写速度最快，但受限于 JVM 内存大小，不适合大规模状态。JobManager 端存储 Checkpoint 的元数据。

适用场景：开发调试、状态量小的作业。

#### EmbeddedRocksDBStateBackend

将状态存储在本地的 RocksDB 实例中（基于 LSM-Tree），数据序列化后写入磁盘。支持增量 Checkpoint，状态大小可以超过内存。

适用场景：生产环境、状态量大的作业（如万亿级别的事件计数）。

| 特性 | HashMapStateBackend | RocksDBStateBackend |
|------|--------------------|--------------------|
| 存储位置 | JVM 堆内存 | 本地磁盘（RocksDB） |
| 读写速度 | 极快 | 较快（序列化/反序列化开销） |
| 状态大小限制 | JVM 内存 | 磁盘空间 |
| 增量 Checkpoint | 不支持 | 支持 |
| GC 压力 | 大状态时高 | 低（数据在堆外） |

### 3.4 Checkpoint 机制

Checkpoint 是 Flink 实现容错的核心机制。其原理基于 Chandy-Lamport 分布式快照算法：

1. **JobManager 定期发送 Barrier**：Barrier 是一种特殊事件，沿着数据流方向传播。
2. **算子接收 Barrier 后快照自身状态**：当算子从所有上游接收到同一编号的 Barrier 后，将当前状态持久化到外部存储（如 HDFS、S3）。
3. **Barrier 对齐（Exactly-once 模式）**：如果一个算子有多个上游输入，它需要等待所有上游的 Barrier 到齐后才进行快照，确保状态的一致性。
4. **完成 Checkpoint**：所有算子完成快照后，JobManager 记录该 Checkpoint 的元数据。

**增量 Checkpoint**：RocksDB 后端支持增量 Checkpoint，只传输自上次 Checkpoint 以来变更的 SST 文件，大幅减少 Checkpoint 的数据量和耗时。

### 3.5 Savepoint

Savepoint 是用户手动触发的全局一致性快照，与 Checkpoint 格式相同但用途不同：

- **Checkpoint**：系统自动触发，用于故障恢复。可以被作业自动消费。
- **Savepoint**：用户手动触发，用于版本升级、作业迁移、调整并行度等运维操作。

Savepoint 命令示例：

```bash
# 触发 Savepoint
bin/flink savepoint :jobId [:targetDirectory]

# 从 Savepoint 恢复
bin/flink run -s [:savepointPath] [:runArgs]
```

---

## 四、Exactly-Once 语义

### 4.1 一致性语义分类

流处理系统提供三种一致性语义：

| 语义 | 含义 | 实现难度 | 典型场景 |
|------|------|---------|---------|
| At-Most-Once | 每条消息最多处理一次（可能丢失） | 低 | 日志收集、监控告警 |
| At-Least-Once | 每条消息至少处理一次（可能重复） | 中 | 大多数业务场景 |
| Exactly-Once | 每条消息恰好处理一次 | 高 | 金融交易、计费系统 |

注意：Exactly-Once 在分布式系统中并非"真"的 Exactly-Once，而是**Effectively-Once**（有效一次），即通过幂等性或事务机制，使得重复处理的结果与处理一次相同。

### 4.2 实现 Exactly-Once 的关键技术

#### 幂等性写入

如果下游存储支持幂等写入（如同一条数据写入多次的结果与写入一次相同），则即使上游重复投递消息，结果也是正确的。

- **数据库 UPSERT**：相同主键的多次插入等价于一次。
- **Kafka 幂等生产者**：Producer 配置 `enable.idempotence=true`，Kafka 自动去重。
- **Redis SET 操作**：天然幂等。

#### 事务性写入

Flink 的 Two-Phase Commit（2PC）协议实现端到端 exactly-once：

1. **Pre-Commit**：算子完成计算，将结果写入临时缓冲区。
2. **Commit**：所有算子确认完成后，将缓冲区的数据一次性提交到下游。
3. **Abort**：如果任何算子失败，回滚所有已提交的数据。

Flink 的 Kafka Sink 集成了 2PC 协议：

```java
KafkaSink.<String>builder()
    .setBootstrapServers("localhost:9092")
    .setRecordSerializer(...)
    .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
    .setTransactionalIdPrefix("flink-tx")
    .build();
```

#### Flink Checkpoint + Sink 组合

Flink 内部的 Exactly-Once 通过 Checkpoint 保证状态一致性，而端到端的 Exactly-Once 需要 Sink 也参与：

- **内部一致性**：Checkpoint 机制保证算子状态和流经算子的数据是一致的快照。
- **外部一致性**：Sink 需要支持事务或幂等性。

Flink 内置的 Sink 如 Kafka Sink、File Sink 都支持 Exactly-Once。对于自定义 Sink，可以实现 `TwoPhaseCommitSinkFunction` 接口。

### 4.3 Exactly-Once 的代价

Exactly-Once 并非免费午餐：

- **性能开销**：Barrier 对齐会增加延迟（特别是在反压情况下）；事务提交需要额外的网络往返。
- **状态大小**：Checkpoint 需要持久化所有状态，状态越大，Checkpoint 耗时越长。
- **下游约束**：下游必须支持幂等性或事务，增加了架构复杂度。
- **恢复时间**：从 Checkpoint 恢复需要重新处理从上次 Checkpoint 到故障发生期间的所有数据。

实际工程中，需要根据业务需求权衡：

金融交易、计费：必须 Exactly-Once
实时推荐、搜索：At-Least-Once + 幂等通常足够
日志收集、监控：At-Most-Once 可接受

### 4.4 端到端 Exactly-Once 的完整路径

一条消息从产生到被正确处理的完整链路：

数据源（Kafka，支持重放）
  ↓ 幂等生产者 / 事务性生产者
Kafka Topic（持久化存储，支持 Consumer Offset 管理）
  ↓ Flink Source（记录 Offset 到状态中，通过 Checkpoint 保证一致性）
Flink 处理算子（状态通过 Checkpoint 一致性快照）
  ↓ Two-Phase Commit / 幂等写入
下游存储（支持 UPSERT 或事务提交）

---

## 五、理论延伸与工程思考

### 5.1 背压（Backpressure）机制

当下游处理速度跟不上上游数据产生速度时，就会产生背压。Flink 通过基于信用的流控（Credit-based Flow Control）机制处理背压：

- 下游向上游发送可用缓冲区的信用值（Credit）
- 上游根据信用值决定发送多少数据
- 当信用为零时，上游暂停发送，数据堆积在上游算子的缓冲区中

背压是健康信号而非异常——它说明系统在自动调节流量。但持续的背压意味着需要扩容或优化处理逻辑。

### 5.2 CEP（Complex Event Processing）

复杂事件处理是从简单事件流中识别出有意义的模式。Flink CEP 库支持定义复杂的模式序列：

```java
Pattern<Event, ?> pattern = Pattern.<Event>begin("start")
    .where(new SimpleCondition<Event>() {
        public boolean filter(Event event) {
            return event.getType().equals("FAIL");
        }
    })
    .timesOrMore(3)
    .within(Time.minutes(5));
```

上述模式匹配 5 分钟内连续出现 3 次或更多 FAIL 事件的情况——典型的故障检测场景。

### 5.3 事件驱动架构中的流处理

在事件驱动架构（Event-Driven Architecture）中，流处理是核心计算层：

命令 → 聚合根 → 事件 → Event Store（Kafka）→ 流处理 → 读模型/视图
                              ↓
                        CQRS 读写分离

流处理引擎负责从事件流中投影（Project）出不同维度的读模型，实现命令查询职责分离（CQRS）。

---

## 本章小结

本章从四个核心维度系统阐述了实时计算的理论基础：

1. **流处理架构**：从 Lambda 到 Kappa 再到 Lakehouse，架构演进的核心驱动力是降低复杂度和提升一致性。
2. **窗口机制**：滚动、滑动、会话窗口配合事件时间和 Watermark，解决了无界数据的有限计算问题。
3. **状态管理**：键控状态、算子状态、Checkpoint 机制共同构建了容错的基石。
4. **Exactly-Once 语义**：通过幂等性、事务性写入和 Checkpoint 的组合，实现端到端的一致性保证。

理论是实践的根基。掌握了这些核心概念，后续章节中无论是 Flink 的深入使用、实时数仓的构建，还是流批一体的工程实践，都将水到渠成。
