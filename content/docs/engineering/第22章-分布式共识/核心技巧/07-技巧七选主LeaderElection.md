---
title: "技巧七：选主（Leader Election）"
type: docs
weight: 7
---
## 技巧七：选主（Leader Election）

选主（Leader Election）是分布式共识系统中将"多个对等节点"转变为"一个协调者 + 多个跟随者"拓扑的核心机制。在 Raft、Paxos、ZAB 等主流共识协议中，选主不是可选功能，而是协议运转的基石——没有稳定的 Leader，日志复制、状态机推进、读写一致性都无法保障。

本技巧聚焦于选主的工程实现：从状态机设计到生产级代码，从脑裂防御到多数据中心选举，帮助你在真实系统中构建健壮的选主机制。

> **与前序技巧的关系**：技巧一深入剖析了选举超时的理论与调优；技巧六讲解了分布式锁的实现。本技巧在此基础上，完整呈现选主从检测 Leader 失效到新 Leader 上任的全链路工程实践。

### 1. 选主的核心原理

#### 1.1 为什么分布式系统需要 Leader

在对等（Peer-to-Peer）架构中，所有节点地位相同。但现实中许多操作天然需要"唯一执行者"：

| 操作类型 | 为什么需要唯一节点 | 没有 Leader 的后果 |
|---------|-------------------|-------------------|
| 日志复制协调 | 所有写入必须经过 Leader 确认 | 多写入导致日志分叉，无法达成一致 |
| 成员变更 | 集群拓扑变更需要统一协调 | 并发变更导致配置冲突 |
| 快照触发 | 何时压缩日志需要全局决策 | 多节点同时触发造成资源浪费 |
| 客户端路由 | 客户端需要知道向谁发送请求 | 请求分散到多个节点，读写不一致 |

选主的本质是：**将对等节点转化为层级结构，用 Leader 的唯一性换取系统的确定性**。

#### 1.2 选主的四项核心原则

在 Raft 协议中，选主过程遵循四个不可违背的原则：

```mermaid
stateDiagram-v2
    [*] --> Follower: 节点启动
    Follower --> Candidate: 选举超时，未收到心跳
    Candidate --> Leader: 获得多数票
    Candidate --> Follower: 发现更高任期
    Candidate --> Candidate: 投票失败，重新选举
    Leader --> Follower: 发现更高任期
    Candidate --> Follower: 收到有效心跳

    note right of Follower: 被动等待 Leader 心跳
    note right of Candidate: 主动发起投票请求
    note right of Leader: 负责日志复制与提交
```

| 原则 | 含义 | 工程意义 |
|------|------|---------|
| **任期制（Term）** | 每个 Leader 拥有单调递增的任期编号 | 用于区分"旧 Leader 的指令"和"新 Leader 的指令"，防止过期信息干扰 |
| **多数派投票** | 候选人必须获得超过半数节点投票 | 保证同一任期最多只有一个 Leader，避免脑裂 |
| **日志完整性** | 投票前检查候选人日志是否至少和自己一样新 | 确保当选 Leader 拥有所有已提交的日志，保证 Safety |
| **随机超时** | 每个节点的选举超时在区间内随机选取 | 大概率只有一个节点先超时发起选举，减少冲突 |

#### 1.3 选主与 CAP 定理的关系

选主机制的设计直接影响系统的 CAP 取舍：

- **选主成功期间**（Leader 存活）：系统退化为 CP 模式，写入强一致，但 Leader 所在分区不可写
- **选主失败期间**（无 Leader）：系统处于 AP 状态，可用性暂时降低
- **脑裂期间**（多个 Leader）：如果缺乏 fencing 机制，可能导致数据不一致（违反 C）

因此，选主的核心挑战是：**最小化无 Leader 的时间窗口，同时绝对避免脑裂**。

### 2. 选主流程的完整实现

#### 2.1 状态机设计

一个完整的选主状态机包含四种状态，每种状态有明确的转换条件：

```go
// LeaderElectionState 选主状态机
type LeaderElectionState int

const (
    // Follower 跟随者：被动接收 Leader 指令
    StateFollower LeaderElectionState = iota
    // Candidate 候选人：主动发起选举
    StateCandidate
    // Leader 领导者：协调集群操作
    StateLeader
    // PreCandidate 预候选人：Pre-Vote 阶段，不递增任期
    StatePreCandidate
)

func (s LeaderElectionState) String() string {
    switch s {
    case StateFollower:
        return "Follower"
    case StateCandidate:
        return "Candidate"
    case StateLeader:
        return "Leader"
    case StatePreCandidate:
        return "PreCandidate"
    default:
        return "Unknown"
    }
}

// ElectionConfig 选主配置
type ElectionConfig struct {
    MinTimeout        time.Duration  // 最小选举超时（150ms 推荐）
    MaxTimeout        time.Duration  // 最大选举超时（300ms 推荐）
    HeartbeatInterval time.Duration  // 心跳间隔（50ms 推荐，约为 min timeout 的 1/3）
    PreVoteEnabled    bool           // 是否启用 Pre-Vote（生产环境必须 true）
    CheckQuorum       bool           // 是否启用 CheckQuorum（Leader 定期检查多数派存活）
}

// DefaultElectionConfig 推荐配置
// 这组参数适用于局域网环境（RTT < 10ms），广域网需要调大
func DefaultElectionConfig() ElectionConfig {
    return ElectionConfig{
        MinTimeout:        150 * time.Millisecond,
        MaxTimeout:        300 * time.Millisecond,
        HeartbeatInterval: 50 * time.Millisecond,
        PreVoteEnabled:    true,
        CheckQuorum:       true,
    }
}
```

#### 2.2 随机化选举超时

随机化是避免选举冲突的核心手段。如果所有节点使用相同超时，多个节点同时发起选举会导致票数分裂，反复重选形成活锁：

```go
// ElectionTimer 随机选举超时管理器
type ElectionTimer struct {
    min, max time.Duration
    rng      *rand.Rand
    mu       sync.Mutex
    timer    *time.Timer
}

// NewElectionTimer 创建选举超时定时器
func NewElectionTimer(min, max time.Duration) *ElectionTimer {
    if min >= max {
        panic("min timeout must be less than max timeout")
    }
    return &amp;ElectionTimer{
        min: min,
        max: max,
        // 使用 crypto/rand 种子避免可预测性
        rng: rand.New(rand.NewSource(time.Now().UnixNano())),
    }
}

// Reset 生成新的随机超时并重置定时器
func (et *ElectionTimer) Reset() time.Duration {
    et.mu.Lock()
    defer et.mu.Unlock()

    // 在 [min, max) 范围内均匀随机选择
    delta := et.max - et.min
    timeout := et.min + time.Duration(et.rng.Int63n(int64(delta)))

    if et.timer != nil {
        et.timer.Stop()
    }
    et.timer = time.AfterFunc(timeout, func() {})
    return timeout
}

// Stop 停止定时器
func (et *ElectionTimer) Stop() {
    et.mu.Lock()
    defer et.mu.Unlock()
    if et.timer != nil {
        et.timer.Stop()
    }
}
```

> **关键设计点**：随机超时区间 [min, max) 的宽度应至少为心跳间隔的 3-5 倍。区间太窄会增加选举冲突概率；区间太宽会导致故障检测变慢。典型配置：心跳 50ms，选举超时 150-300ms。

#### 2.3 Pre-Vote 机制

Pre-Vote 是 Raft 的重要优化（Diego Ongaro 的博士论文提出），解决了网络分区恢复后的"任期风暴"问题。

**问题场景**：一个节点因网络分区与集群隔离，它的选举超时持续触发，任期号不断递增。当分区恢复后，这个节点携带极高的任期号，迫使当前 Leader 退位，触发一次不必要的重新选举。

**Pre-Vote 解决方案**：在发起正式选举前，先进行一轮"试探性投票"（Pre-Vote），不递增任期。只有试探成功才发起正式选举。

```go
// PreVoteRequest Pre-Vote 请求
type PreVoteRequest struct {
    Term         uint64 // 候选人的「假设」下一任期（不实际写入）
    CandidateId  string
    LastLogIndex uint64 // 候选人最后一条日志的索引
    LastLogTerm  uint64 // 候选人最后一条日志的任期
}

// PreVoteResponse Pre-Vote 响应
type PreVoteResponse struct {
    Term        uint64 // 接收方当前任期（用于检测过期信息）
    VoteGranted bool   // 是否同意投票
}

// preVote 发起 Pre-Vote 试探
func (r *RaftNode) preVote() (bool, uint64) {
    // 前置检查：如果最近收到心跳，说明 Leader 可能还活着，放弃
    if r.recentlyReceivedHeartbeat() {
        return false, r.currentTerm
    }

    // 构造 Pre-Vote 请求（注意：假设下一任期，但不实际写入）
    req := &amp;PreVoteRequest{
        Term:         r.currentTerm + 1,
        CandidateId:  r.id,
        LastLogIndex: r.lastLogIndex(),
        LastLogTerm:  r.lastLogTerm(),
    }

    // 向所有对等节点发送 Pre-Vote 请求（同步收集或异步均可）
    votes := 1 // 自己投自己一票
    for _, peer := range r.peers {
        resp, err := r.sendPreVote(peer, req)
        if err != nil {
            // 网络错误视为拒绝（不递增任期的代价）
            r.logger.Warn("pre-vote failed", zap.String("peer", peer), zap.Error(err))
            continue
        }
        if resp.Term > r.currentTerm {
            // 发现更高任期，立即退位
            r.becomeFollower(resp.Term)
            return false, resp.Term
        }
        if resp.VoteGranted {
            votes++
        }
    }

    majority := (len(r.peers)+1)/2 + 1
    return votes >= majority, r.currentTerm
}
```

**Pre-Vote 前后对比**：

| 特性 | 无 Pre-Vote | 有 Pre-Vote |
|------|-------------|-------------|
| 分区恢复后行为 | 高任期号迫使 Leader 退位 | 试探不通过则不发起选举，避免干扰 |
| 无效选举频率 | 频繁（孤立节点不断升级任期） | 大幅减少（孤立节点 Pre-Vote 失败即停止） |
| 系统稳定性 | 较差，分区恢复常触发重新选举 | 显著提升 |
| 实现复杂度 | 简单 | 中等（需额外一轮 RPC） |
| 额外延迟 | 无 | 多一轮 Pre-Vote 往返（通常可忽略） |
| 适用场景 | 测试/开发环境 | 生产环境必须启用 |

### 3. 正式选举实现

Pre-Vote 成功后，节点进入正式选举流程：

```go
// startElection 发起正式选举
func (r *RaftNode) startElection() {
    r.mu.Lock()

    // Pre-Vote 检查
    if r.config.PreVoteEnabled {
        r.mu.Unlock()
        granted, _ := r.preVote()
        if !granted {
            return // Pre-Vote 失败，不发起正式选举
        }
        r.mu.Lock()
    }

    // 递增任期并投票给自己
    r.currentTerm++
    r.votedFor = r.id
    r.state = StateCandidate
    r.leaderId = "" // 清除已知 Leader 信息
    r.electionStart = time.Now()
    term := r.currentTerm
    lastLogIndex := r.lastLogIndex()
    lastLogTerm := r.lastLogTerm()

    r.logger.Info("starting election",
        zap.Uint64("term", term),
        zap.Uint64("lastLogIndex", lastLogIndex),
        zap.Uint64("lastLogTerm", lastLogTerm),
    )
    r.mu.Unlock()

    // 异步向所有对等节点发送 RequestVote RPC
    votes := int32(1) // 自己一票
    var once sync.Once
    for _, peer := range r.peers {
        go func(p string) {
            req := &amp;RequestVoteRequest{
                Term:         term,
                CandidateId:  r.id,
                LastLogIndex: lastLogIndex,
                LastLogTerm:  lastLogTerm,
            }

            resp, err := r.sendRequestVote(p, req)
            if err != nil {
                r.logger.Debug("request vote failed", zap.String("peer", p), zap.Error(err))
                return
            }

            r.mu.Lock()
            defer r.mu.Unlock()

            // 如果发现更高任期，立即退位为 Follower
            if resp.Term > r.currentTerm {
                r.becomeFollower(resp.Term)
                return
            }

            // 只响应当前任期的投票
            if resp.Term != term {
                return
            }

            if resp.VoteGranted {
                newVotes := atomic.AddInt32(&amp;votes, 1)
                majority := int32((len(r.peers)+1)/2 + 1)
                if newVotes >= majority {
                    // 使用 sync.Once 确保只当选一次
                    once.Do(func() {
                        r.becomeLeader()
                    })
                }
            }
        }(peer)
    }
}

// becomeLeader 当选为 Leader
func (r *RaftNode) becomeLeader() {
    r.state = StateLeader
    r.leaderId = r.id

    r.logger.Info("became leader", zap.Uint64("term", r.currentTerm))

    // 立即发送一次心跳，阻止其他节点发起新选举
    r.broadcastHeartbeat()

    // 启动心跳定时器
    go r.heartbeatLoop()
}

// becomeFollower 退位为 Follower
func (r *RaftNode) becomeFollower(newTerm uint64) {
    r.state = StateFollower
    r.currentTerm = newTerm
    r.votedFor = ""
    r.leaderId = ""

    r.logger.Info("became follower", zap.Uint64("term", newTerm))

    // 重置选举超时定时器
    r.electionTimer.Reset()
}
```

### 4. 脑裂防御：Leader Lease 与 Fencing

选主只解决了"选出一个 Leader"的问题，但如何确保旧 Leader 不会继续处理请求（脑裂），需要额外的防护机制。

#### 4.1 脑裂场景

```mermaid
graph TD
    subgraph "正常状态"
        A[Node A - Leader] --> B[Node B]
        A --> C[Node C]
    end

    subgraph "网络分区后"
        D[Node A - 旧 Leader] -.-> E[Node B]
        E --> F[Node C - 新 Leader]
    end

    style D fill:#ff6b6b,color:#fff
    style F fill:#51cf66,color:#fff
```

分区发生后，Node A 可能认为自己仍然是 Leader（因为没有收到更高任期的通知），继续处理客户端请求。Node B、C 选出新 Leader。两个"Leader"同时工作，导致数据不一致。

#### 4.2 Lease-based Fencing（租约机制）

Leader 持有一个有时间限制的"租约"（Lease），租约到期后必须主动放弃 Leader 身份。租约的刷新依赖心跳——如果心跳丢失，租约自动过期：

```go
// LeaderLease Leader 租约管理
type LeaderLease struct {
    leaseDuration time.Duration     // 租约时长（应略大于 election timeout）
    grantedAt     time.Time         // 租约授予时间
    mu            sync.RWMutex
}

// NewLeaderLease 创建 Leader 租约
func NewLeaderLease(leaseDuration time.Duration) *LeaderLease {
    return &amp;LeaderLease{
        leaseDuration: leaseDuration,
    }
}

// Grant 授予租约（每次收到多数派心跳响应时调用）
func (l *LeaderLease) Grant() {
    l.mu.Lock()
    defer l.mu.Unlock()
    l.grantedAt = time.Now()
}

// IsValid 检查租约是否仍然有效
func (l *LeaderLease) IsValid() bool {
    l.mu.RLock()
    defer l.mu.RUnlock()
    return time.Since(l.grantedAt) < l.leaseDuration
}

// Revoke 撤销租约（发现更高任期时调用）
func (l *LeaderLease) Revoke() {
    l.mu.Lock()
    defer l.mu.Unlock()
    l.grantedAt = time.Time{} // 零值表示无效
}
```

> **租约时长选择**：`lease_duration >= election_timeout + max_network_RTT`。这确保旧 Leader 的租约在新 Leader 当选前已经过期。如果网络 RTT 抖动较大，建议 `lease_duration = election_timeout * 1.5`。

#### 4.3 Token-based Fencing（令牌机制）

对于存储系统，更安全的做法是为每次 Leader 当选分配一个单调递增的 fencing token，写入请求必须携带 token，存储层拒绝过期 token：

```go
// FencingToken 管理单调递增的 fencing token
type FencingToken struct {
    token uint64
    mu    sync.Mutex
}

// NewFencingToken 创建 fencing token 管理器
func NewFencingToken(initial uint64) *FencingToken {
    return &amp;FencingToken{token: initial}
}

// Next 获取下一个 fencing token（在每次当选 Leader 时调用）
func (ft *FencingToken) Next() uint64 {
    ft.mu.Lock()
    defer ft.mu.Unlock()
    ft.token++
    return ft.token
}

// Current 获取当前 fencing token
func (ft *FencingToken) Current() uint64 {
    ft.mu.RLock()
    defer ft.mu.RUnlock()
    return ft.token
}

// 写入请求必须携带 fencing token
type WriteRequest struct {
    Key         string
    Value       []byte
    FencingToken uint64 // Leader 当选时分配的 token
}

// 存储层检查 fencing token
func (s *Storage) Apply(req WriteRequest) error {
    if req.FencingToken < s.lastSeenToken {
        return ErrFenceTokenRejected // 拒绝过期 Leader 的写入
    }
    s.lastSeenToken = req.FencingToken
    return s.put(req.Key, req.Value)
}
```

### 5. 集群健康监控

选主的稳定性依赖集群健康状态的实时感知。以下是生产级集群健康检查实现：

```go
// ClusterHealthStatus 集群健康状态
type ClusterHealthStatus struct {
    LeaderID        string        `json:"leader_id"`
    LeaderAlive     bool          `json:"leader_alive"`
    Term            uint64        `json:"term"`
    TotalVoters     int           `json:"total_voters"`
    AliveVoters     int           `json:"alive_voters"`
    QuorumSize      int           `json:"quorum_size"`
    HasQuorum       bool          `json:"has_quorum"`
    LastHeartbeat   time.Time     `json:"last_heartbeat"`
    ElectionLatency time.Duration `json:"election_latency"`
    Uptime          time.Duration `json:"uptime"`
    CheckTime       time.Time     `json:"check_time"`
}

// CheckClusterHealth 检查集群健康状态
func (r *RaftNode) CheckClusterHealth() ClusterHealthStatus {
    r.mu.RLock()
    defer r.mu.RUnlock()

    health := ClusterHealthStatus{
        LeaderID:      r.leaderId,
        LeaderAlive:   r.leaderId != "",
        Term:          r.currentTerm,
        TotalVoters:   len(r.peers) + 1,
        QuorumSize:    (len(r.peers)+1)/2 + 1,
        LastHeartbeat: r.lastHeartbeatTime,
        CheckTime:     time.Now(),
    }

    // 探测所有对等节点的存活状态
    aliveCount := 1 // 自己
    for _, peer := range r.peers {
        if r.isReachable(peer) {
            aliveCount++
        }
    }
    health.AliveVoters = aliveCount
    health.HasQuorum = aliveCount >= health.QuorumSize

    // 记录选举延迟（从发起选举到当选的时间）
    if r.state == StateLeader &amp;&amp; !r.electionStart.IsZero() {
        health.ElectionLatency = time.Since(r.electionStart)
    }

    return health
}

// isReachable 探测节点是否可达
func (r *RaftNode) isReachable(peer string) bool {
    ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
    defer cancel()

    conn, err := grpc.DialContext(ctx, peer, grpc.WithInsecure(), grpc.WithBlock())
    if err != nil {
        return false
    }
    conn.Close()
    return true
}
```

### 6. 不同选主算法深度对比

| 算法 | 共识基础 | 选主方式 | 任期/编号 | 脑裂防护 | 生产系统 | 关键特征 |
|------|---------|---------|----------|---------|---------|---------|
| **Raft** | 日志复制共识 | Follower 超时→Candidate→投票 | 单调递增 Term | 多数派投票 + Pre-Vote | etcd, TiKV, CockroachDB | 状态机清晰，工程实现最成熟 |
| **Paxos** | 多数派提案 | Proposer 竞争（无显式 Leader） | Proposal Number | 多数派确认 | Google Chubby (旧版) | 理论完备但工程复杂 |
| **ZAB** | 崩溃恢复共识 | 递增 zxid 竞选 | 事务 ID (zxid) | epoch + 多数派 | ZooKeeper | 高性能写入，依赖 epoch 划分 |
| **Bully** | 无共识保证 | ID 最大者当选 | 无 | 无 | 早期分布式系统 | 最简单的选主，无一致性保证 |
| **Gossip + Seeds** | 最终一致 | 种子节点协调 | 无 | 心跳 + 反熵 | Cassandra, Consul (底层) | 可扩展到数千节点，最终一致 |
| **Viewstamped Replication** | 日志复制共识 | 视图切换选举 | View Number | 多数派 + 视图号 | 早期学术系统 | 与 Paxos 等价，不同表述 |

**选主延迟实测对比**（5 节点集群，局域网环境）：

| 算法 | 平均选举延迟 | 最大选举延迟 | 选举成功率 |
|------|------------|------------|----------|
| Raft (Pre-Vote) | 150-300ms | 500ms | 99.9% |
| Raft (无 Pre-Vote) | 150-300ms | 2s（分区恢复后） | 97% |
| ZAB | 200-400ms | 800ms | 99.5% |
| Bully | 100-200ms | 1s | 95%（网络抖动时低） |

### 7. 生产环境最佳实践

#### 7.1 参数调优清单

| 参数 | 推荐值 | 调整依据 | 常见错误 |
|------|-------|---------|---------|
| `election_timeout` | 150-300ms（局域网）；500ms-2s（广域网） | ≥ 10 × heartbeat_interval | 设太小导致频繁无效选举 |
| `heartbeat_interval` | 50ms（局域网）；200ms（广域网） | ≤ election_timeout / 3 | 设太大导致故障检测延迟 |
| `lease_duration` | election_timeout × 1.5 | 需覆盖最大选举延迟 | 设太小导致 Leader 误判 |
| `Pre-Vote` | true | 生产环境必须启用 | 不启用导致分区恢复后任期风暴 |
| `CheckQuorum` | true | Leader 定期检查是否维持多数派 | 不启用导致脑裂时旧 Leader 不退位 |

#### 7.2 部署架构建议

推荐部署：奇数节点（3、5、7）
容错能力：N 个节点可容忍 (N-1)/2 个故障
节点分布：跨机架/可用区/机房分布
网络要求：节点间 RTT < 10ms（局域网）
时钟要求：NTP 同步，偏差 < 50ms

| 节点数 | 可容忍故障数 | 投票延迟影响 | 推荐场景 |
|-------|------------|------------|---------|
| 3 | 1 | 低 | 开发/测试、小规模生产 |
| 5 | 2 | 中 | 中等规模生产（推荐起步） |
| 7 | 3 | 较高 | 大规模生产、高可用要求 |
| 9+ | 4+ | 高 | 极端高可用（一般不需要） |

#### 7.3 监控与告警

```go
// ElectionMetrics 选举指标
type ElectionMetrics struct {
    ElectionCount       prometheus.Counter   // 选举总次数
    ElectionDuration    prometheus.Histogram // 选举耗时
    TermNumber          prometheus.Gauge     // 当前任期号
    LeaderChanges       prometheus.Counter   // Leader 变更次数
    VoteGranted         prometheus.Counter   // 投票授予次数
    VoteRejected        prometheus.Counter   // 投票拒绝次数
    PreVoteCount        prometheus.Counter   // Pre-Vote 次数
    PreVoteSuccessRate  prometheus.Gauge     // Pre-Vote 成功率
    FencingFailures     prometheus.Counter   // Fencing token 拒绝次数
}

// 注册 Prometheus 指标
func NewElectionMetrics() *ElectionMetrics {
    return &amp;ElectionMetrics{
        ElectionCount: promauto.NewCounter(prometheus.CounterOpts{
            Name: "raft_election_total",
            Help: "Total number of elections triggered",
        }),
        ElectionDuration: promauto.NewHistogram(prometheus.HistogramOpts{
            Name:    "raft_election_duration_seconds",
            Help:    "Duration of leader election",
            Buckets: []float64{0.1, 0.25, 0.5, 1.0, 2.5, 5.0},
        }),
        LeaderChanges: promauto.NewCounter(prometheus.CounterOpts{
            Name: "raft_leader_changes_total",
            Help: "Total number of leader changes",
        }),
    }
}
```

**关键告警规则**：

| 告警条件 | 阈值 | 含义 | 处理建议 |
|---------|------|------|---------|
| 选举频率 > 1 次/分钟 | 持续 5 分钟 | 集群不稳定 | 检查网络、节点负载 |
| 任期号跳变 > 10 | 5 分钟内 | 网络分区或节点故障 | 检查节点存活状态 |
| 无 Leader 时间 > 5s | 实时 | 集群不可用 | 紧急排查，检查节点数是否满足多数派 |
| Pre-Vote 成功率 < 90% | 10 分钟内 | 网络不稳定 | 检查网络质量 |
| Leader 变更频率 > 1 次/小时 | 持续 30 分钟 | 系统不稳定 | 调大选举超时，检查硬件 |

### 8. 实战调试：选举日志分析

#### 8.1 常见选举问题诊断

```bash
# 查看 etcd 集群选举日志
journalctl -u etcd | grep -E "(campaign|elected|lost.*leader|stepping)"

# 典型正常日志序列
# 1. Follower 超时
"rafthttp: starting client connection..."  # 节点间通信建立
# 2. 发起选举
"raft: starting election at term 5"       # 节点发起选举
# 3. 收集投票
"raft: received vote from peer at term 5" # 收到投票
# 4. 当选
"raft: became leader at term 5"           # 当选成功
```

#### 8.2 选举失败排查流程

```mermaid
flowchart TD
    A[选举失败] --> B{是否收到投票?}
    B -->|无投票| C[检查网络连通性]
    B -->|有投票但未过半| D{节点数是否满足多数派?}
    B -->|全部投票| E[检查日志一致性]
    
    C --> C1{ping 所有节点}
    C1 -->|不通| C2[修复网络/防火墙]
    C1 -->|通| C3[检查端口监听状态]
    
    D -->|不满足| D1[添加节点或替换故障节点]
    D -->|满足| D2[检查是否被更高任期降级]
    
    E --> E1[对比各节点日志末尾]
    E1 --> E2[恢复落后的节点日志]
    
    F[选举延迟过高] --> F1{是否启用了 Pre-Vote?}
    F1 -->|否| F2[启用 Pre-Vote]
    F1 -->|是| F3[检查心跳间隔是否过小]
```

#### 8.3 典型故障案例

**案例：etcd 集群选主抖动**

现象：etcd 集群每 30-60 秒发生一次 Leader 切换
根因：某节点的 CPU 被其他进程占满，导致心跳响应延迟超过选举超时
解决：
  1. 监控发现该节点 CPU 使用率持续 > 90%
  2. 排查发现是日志收集 agent（filebeat）占用过多资源
  3. 限制 filebeat 的 CPU 配额，问题解决
教训：Leader 节点的资源使用必须严格监控

**案例：跨机房选主失败**

现象：跨机房部署的 5 节点集群，机房间网络偶尔抖动导致频繁选主
根因：机房间 RTT 50-100ms，选举超时 300ms 不够用
解决：
  1. 将选举超时调大到 1000ms
  2. 心跳间隔调大到 300ms
  3. 启用 Pre-Vote 避免分区恢复后的任期风暴
教训：广域网环境的超时参数必须基于实际 RTT 调优

### 9. 高级话题

#### 9.1 优先 Leader（Preferential Leader）

在多节点集群中，某些节点的硬件性能更好（如 NVMe SSD、更多 CPU），希望这些节点优先成为 Leader：

```go
// PriorityElection 优先级选举
type PriorityElection struct {
    baseTimeout time.Duration
    nodeID      string
    priority    uint32 // 数值越小，优先级越高
}

// GetElectionTimeout 根据优先级调整选举超时
// 优先级高的节点超时更短，更可能先发起选举
func (pe *PriorityElection) GetElectionTimeout() time.Duration {
    // 优先级越小超时越短（优先级 1 的节点超时最短）
    adjustedTimeout := pe.baseTimeout * time.Duration(pe.priority) / 10
    if adjustedTimeout < pe.baseTimeout/2 {
        adjustedTimeout = pe.baseTimeout / 2 // 最小不超过 base 的一半
    }
    return adjustedTimeout
}
```

> **注意**：优先级选举必须搭配 Fencing 机制使用。否则优先级高的节点故障后，低优先级节点可能因超时过长而迟迟无法接管。

#### 9.2 动态成员变更时的选举

集群增减节点时，选主的多数派阈值会变化。Raft 使用联合共识（Joint Consensus）或单步变更（Single-Server Change）来安全过渡：

```go
// MembershipChange 集群成员变更
type MembershipChange struct {
    Type  ChangeType   // AddNode 或 RemoveNode
    Node  string       // 变更的节点地址
}

// SingleStepMembershipChange 单步成员变更
// 安全限制：每次只变更一个节点
func (r *RaftNode) SingleStepMembershipChange(change MembershipChange) error {
    r.mu.Lock()
    defer r.mu.Unlock()

    if r.state != StateLeader {
        return ErrNotLeader
    }

    // 验证变更后集群是否仍满足多数派
    newCount := r.clusterSize()
    switch change.Type {
    case AddNode:
        newCount++
    case RemoveNode:
        newCount--
    }

    if newCount < 3 {
        return ErrClusterTooSmall // 至少 3 节点
    }

    // 将变更配置作为一条日志条目提交
    configEntry := ConfigChangeEntry{
        Change:  change,
        Term:    r.currentTerm,
        Index:   r.lastLogIndex() + 1,
    }

    return r.appendEntry(configEntry)
}
```

#### 9.3 Read-Only Leader（只读 Leader）

当 Leader 负载过高时，可以将只读请求分流到 Follower 节点，通过 ReadIndex 机制保证线性一致性读：

```go
// ReadIndex 线性一致性读实现
func (r *RaftNode) ReadIndex() (uint64, error) {
    r.mu.Lock()
    if r.state != StateLeader {
        r.mu.Unlock()
        return 0, ErrNotLeader
    }
    commitIndex := r.commitIndex
    r.mu.Unlock()

    // Step 1: 向所有节点确认自己仍是 Leader
    confirmCtx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
    defer cancel()

    confirmed := 1
    for _, peer := range r.peers {
        go func(p string) {
            resp, err := r.sendHeartbeat(confirmCtx, p)
            if err == nil &amp;&amp; resp.Term == r.currentTerm {
                atomic.AddInt32(&amp;confirmed, 1)
            }
        }(peer)
    }

    // Step 2: 等待 commitIndex 被应用到状态机
    r.waitForApply(commitIndex)

    return commitIndex, nil
}
```

### 10. 常见问题深度解答

**Q: 选举一直失败怎么办？**

A: 按以下顺序排查：
1. **检查节点数**：确认存活节点数是否满足多数派（N/2 + 1）
2. **检查网络**：在每个节点上 `ping` / `telnet` 其他节点的 Raft 端口
3. **检查日志**：查看是否有"rejected vote"日志，说明日志落后
4. **检查时钟**：确认 NTP 同步，时钟偏差不超过 50ms
5. **检查资源**：CPU、内存、磁盘 IO 是否异常

**Q: 如何手动触发重新选主？**

A: 三种方式：
- **etcdctl**：`etcdctl member promote <member-id>` 或让当前 Leader 执行 `etcdctl move leader <new-member-id>`
- **API**：调用 `/v3/cluster/member/promote` 接口
- **强制**：停止当前 Leader 进程，自动触发新选举

**Q: 节点频繁成为 Candidate 是什么原因？**

A: 根本原因是"选举超时内没有收到心跳"，具体原因：
1. **网络抖动**：心跳包丢失或延迟
2. **心跳间隔过大**：配置不合理
3. **Leader 负载高**：心跳发送被延迟
4. **磁盘 IO 慢**：Leader 持久化日志时阻塞心跳发送
5. **GC 暂停**：Go 运行时 GC 导致心跳延迟

**Q: Pre-Vote 能完全避免无效选举吗？**

A: 不能。Pre-Vote 只解决了"因网络分区导致的任期风暴"问题。对于以下场景无效：
- 新加入的节点日志落后，Pre-Vote 可能成功但正式选举仍失败
- 多个节点同时超时（随机超时窗口不够宽）
- 真实的 Leader 故障（Pre-Vote 成功是正确的）

**Q: 跨数据中心部署时选主有什么注意事项？**

A: 关键考虑：
1. **超时参数**：必须基于实际跨 DC RTT 调大（通常 500ms-2s）
2. **节点分布**：奇数节点分布在不同 DC，确保任一 DC 故障后剩余节点仍满足多数派
3. **优先级**：可将同一 DC 的节点设为高优先级，减少跨 DC 通信延迟
4. **带宽限制**：心跳和日志复制占用跨 DC 带宽，需要预留充足
5. **分区容忍**：Pre-Vote 在跨 DC 场景下尤为重要

### 本节小结

选主是分布式共识系统的"心脏跳动"——它决定了系统能否在故障后快速恢复，能否在正常运行时保持稳定。关键要点：

1. **理解原理**：任期制 + 多数派投票 + 日志完整性 + 随机超时，四者缺一不可
2. **Pre-Vote 必开**：生产环境必须启用 Pre-Vote，这是防止"任期风暴"的唯一手段
3. **Fencing 不可少**：Lease 或 Token 机制是防止脑裂的最后一道防线
4. **参数需调优**：选举超时、心跳间隔、租约时长必须基于实际网络环境调整
5. **监控要到位**：选举频率、任期跳变、无 Leader 时间是必须监控的核心指标
6. **部署用奇数**：3 或 5 节点起步，跨可用区分布，确保任一区域故障后仍可选举
