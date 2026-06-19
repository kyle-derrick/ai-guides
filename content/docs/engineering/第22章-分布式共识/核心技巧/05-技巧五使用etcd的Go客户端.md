---
title: "技巧五：使用 etcd 的 Go 客户端"
type: docs
weight: 5
---
## 技巧五：使用 etcd 的 Go 客户端

在掌握了选举超时、日志一致性、日志压缩和性能优化等底层机制之后，我们终于来到了最贴近日常开发的环节——如何用 Go 语言操作 etcd。etcd 的官方 Go 客户端（`go.etcd.io/etcd/client/v3`）是生产中使用最广泛的共识协议客户端，Kubernetes 的 API Server、TiKV 的 PD 调度器、CoreDNS 的服务发现，底层都依赖它。

但"能用"和"用好"之间隔着一道鸿沟。初学者写出来的 etcd 客户端代码，往往在测试环境中运行正常，到了生产环境却频繁超时、连接断开、Watch 丢失事件、Lease 意外过期。本技巧的目标就是帮你跨越这道鸿沟——从连接管理到 Lease 机制，从事务操作到错误处理，全面掌握生产级 etcd Go 客户端的使用方法。

### 客户端架构概览

在深入代码之前，先理解 etcd Go 客户端的内部架构。这能帮你理解后续所有配置项的设计意图。

```mermaid
graph TB
    subgraph 应用层["你的 Go 应用"]
        App["业务代码"]
    end

    subgraph 客户端层["etcd clientv3"]
        LB["客户端负载均衡器<br/>(round-robin)"]
        Cache["Watch 缓存<br/>(mvcc store)"]
        LeaseM["Lease 管理器<br/>(keepAlive 心跳)"]
        TxnM["事务构建器<br/>(IF-THEN-ELSE)"]
    end

    subgraph gRPC层["gRPC 传输层"]
        Conn1["gRPC Conn 1<br/>→ node-1:2379"]
        Conn2["gRPC Conn 2<br/>→ node-2:2379"]
        Conn3["gRPC Conn 3<br/>→ node-3:2379"]
    end

    subgraph 集群层["etcd 集群"]
        N1["node-1 (Leader)"]
        N2["node-2 (Follower)"]
        N3["node-3 (Follower)"]
    end

    App --> LB
    LB --> Conn1 &amp; Conn2 &amp; Conn3
    Cache -.-> LB
    LeaseM -.-> LB
    Conn1 --> N1
    Conn2 --> N2
    Conn3 --> N3
```

客户端的核心设计特点：

1. **gRPC 通信**：客户端与 etcd 之间通过 gRPC 双向流通信，支持多路复用、流量控制、TLS 加密
2. **自动负载均衡**：客户端维护到所有节点的 gRPC 连接，默认使用 round-robin 策略将请求分散到各节点，减少 Leader 压力
3. **自动故障转移**：当某个节点不可达时，客户端自动将请求路由到其他节点，应用层无需感知
4. **Watch 缓存**：客户端本地维护 Watch 事件的缓存，支持从断点恢复（通过 revision），避免事件丢失
5. **Lease 心跳复用**：所有通过同一客户端创建的 Lease 共享一个 keepAlive 流，减少网络开销

### 连接管理

连接管理是使用 etcd 客户端的第一步，也是最容易出问题的环节。生产环境中的连接管理需要考虑：超时控制、多节点容错、连接保活、消息大小限制。

#### 基础客户端创建

```go
import (
    "context"
    "fmt"
    "log"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
)

func createEtcdClient() (*clientv3.Client, error) {
    client, err := clientv3.New(clientv3.Config{
        // Endpoints：etcd 集群的所有节点地址
        // 客户端会自动探测 Leader 并在节点间负载均衡
        Endpoints: []string{
            "10.0.0.1:2379",
            "10.0.0.2:2379",
            "10.0.0.3:2379",
        },

        // DialTimeout：建立 gRPC 连接的超时时间
        // 过短会导致启动时连接失败；过长会导致故障时响应慢
        // 推荐：5-10 秒
        DialTimeout: 5 * time.Second,

        // AutoSyncInterval：定期自动同步集群成员列表
        // 设置后客户端会定期从已连接的节点获取最新的集群成员地址
        // 这在节点增减（技巧八）时非常关键
        AutoSyncInterval: 30 * time.Second,

        // 消息大小限制（默认 1.5MB）
        // 当 value 较大时（如存储配置文件、证书）需要调大
        MaxCallSendMsgSize: 4 * 1024 * 1024, // 4MB 发送上限
        MaxCallRecvMsgSize: 4 * 1024 * 1024, // 4MB 接收上限

        // TLS 配置（生产环境必须启用）
        // TLS: tlsConfig,

        // 认证配置（可选）
        // Username: "root",
        // Password: "secret",
    })
    if err != nil {
        return nil, fmt.Errorf("创建 etcd 客户端失败: %w", err)
    }
    return client, nil
}
```

**关键配置说明：**

| 配置项 | 推荐值 | 为什么重要 |
|--------|--------|-----------|
| Endpoints | 所有节点地址 | 客户端会自动在节点间负载均衡，漏填会导致部分节点不被使用 |
| DialTimeout | 5-10s | 太短会在网络抖动时频繁失败；太长会导致故障切换响应慢 |
| AutoSyncInterval | 30s | 节点增减后客户端能自动感知，避免手动重启 |
| MaxCallSendMsgSize | 按需调整 | 默认 1.5MB 对存储大 value 不够用，但也不宜过大（etcd 单个 value 上限 1.5MB） |

#### 生产级客户端（带 TLS 和认证）

```go
import (
    "crypto/tls"
    "crypto/x509"
    "os"

    clientv3 "go.etcd.io/etcd/client/v3"
    "google.golang.org/grpc/credentials"
)

func createSecureClient() (*clientv3.Client, error) {
    // 1. 加载 CA 证书
    caCert, err := os.ReadFile("/etc/etcd/ca.crt")
    if err != nil {
        return nil, fmt.Errorf("读取 CA 证书失败: %w", err)
    }

    caPool := x509.NewCertPool()
    if !caPool.AppendCertsFromPEM(caCert) {
        return nil, fmt.Errorf("解析 CA 证书失败")
    }

    // 2. 加载客户端证书（双向 TLS）
    clientCert, err := tls.LoadX509KeyPair(
        "/etc/etcd/client.crt",
        "/etc/etcd/client.key",
    )
    if err != nil {
        return nil, fmt.Errorf("加载客户端证书失败: %w", err)
    }

    // 3. 构建 TLS 配置
    tlsConfig := &amp;tls.Config{
        Certificates: []tls.Certificate{clientCert},
        RootCAs:      caPool,
        MinVersion:   tls.VersionTLS12,
        // 禁用不安全的密码套件
        CipherSuites: []uint16{
            tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
            tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
        },
    }

    // 4. 创建客户端
    client, err := clientv3.New(clientv3.Config{
        Endpoints:   []string{"10.0.0.1:2379", "10.0.0.2:2379", "10.0.0.3:2379"},
        DialTimeout: 5 * time.Second,
        TLS:         tlsConfig,
    })
    if err != nil {
        return nil, fmt.Errorf("创建安全客户端失败: %w", err)
    }
    return client, nil
}
```

> **生产铁律：** 任何暴露在非可信网络的 etcd 集群都必须启用 TLS。etcd 默认启动时不加密、不认证，任何人连接上来都能读写所有数据。这是生产环境中最常见的安全疏忽。

#### 连接保活与优雅关闭

etcd 客户端底层维护的 gRPC 连接可能因为网络波动而断开。正确的保活策略和优雅关闭流程能避免生产事故：

```go
// 全局客户端管理器
type EtcdManager struct {
    client  *clientv3.Client
    timeout time.Duration
}

func NewEtcdManager(endpoints []string) (*EtcdManager, error) {
    client, err := clientv3.New(clientv3.Config{
        Endpoints:        endpoints,
        DialTimeout:      5 * time.Second,
        DialKeepAliveTime:    10 * time.Second, // 每 10 秒发送 keepalive ping
        DialKeepAliveTimeout: 3 * time.Second,  // keepalive ping 超时时间
    })
    if err != nil {
        return nil, err
    }
    return &amp;EtcdManager{client: client, timeout: 5 * time.Second}, nil
}

// 带超时的操作
func (m *EtcdManager) Put(ctx context.Context, key, value string) error {
    ctx, cancel := context.WithTimeout(ctx, m.timeout)
    defer cancel()

    _, err := m.client.Put(ctx, key, value)
    if err != nil {
        // 区分超时和其他错误
        if ctx.Err() == context.DeadlineExceeded {
            return fmt.Errorf("etcd PUT 超时 (key=%s): %w", key, err)
        }
        return fmt.Errorf("etcd PUT 失败 (key=%s): %w", key, err)
    }
    return nil
}

// 优雅关闭客户端
func (m *EtcdManager) Close() error {
    // 确保所有进行中的 keepAlive 协程被通知停止
    // 这一步非常重要——不关闭会导致 goroutine 泄漏
    return m.client.Close()
}
```

> **goroutine 泄漏陷阱：** etcd 客户端内部会启动多个 goroutine（keepalive、watch 流等）。如果忘记调用 `client.Close()`，这些 goroutine 不会被回收，长时间运行后会耗尽内存和文件描述符。务必使用 `defer client.Close()`。

### 基础操作：GET / PUT / DELETE

#### PUT：写入键值

```go
func basicPutExample(client *clientv3.Client) error {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    // 最简单的 PUT：设置 key="/config/db_host"，value="10.0.0.1"
    resp, err := client.Put(ctx, "/config/db_host", "10.0.0.1")
    if err != nil {
        return fmt.Errorf("PUT 失败: %w", err)
    }

    // resp.Header.Revision：本次写入后的全局 revision
    // revision 是 etcd MVCC 的核心概念，每次写入单调递增
    fmt.Printf("写入成功, 当前 revision: %d\n", resp.Header.Revision)

    // 带选项的 PUT：附带 Lease（后面详解）
    // leaseResp, err := client.Put(ctx, "/service/worker-1", "alive",
    //     clientv3.WithLease(leaseID))

    // 带 PrevKV 的 PUT：返回被覆盖前的旧值
    // 适用于"先读旧值再更新"的场景
    prevResp, err := client.Put(ctx, "/config/db_host", "10.0.0.2",
        clientv3.WithPrevKV())
    if err != nil {
        return err
    }
    if prevResp.PrevKv != nil {
        fmt.Printf("旧值: %s → 新值: %s\n",
            prevResp.PrevKv.Value, "10.0.0.2")
    }

    return nil
}
```

#### GET：读取键值

```go
func basicGetExample(client *clientv3.Client) error {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    // 1. 精确查询单个 key
    resp, err := client.Get(ctx, "/config/db_host")
    if err != nil {
        return fmt.Errorf("GET 失败: %w", err)
    }

    for _, kv := range resp.Kvs {
        fmt.Printf("key=%s, value=%s, version=%d, create_rev=%d, mod_rev=%d\n",
            kv.Key, kv.Value, kv.Version, kv.CreateRevision, kv.ModRevision)
    }
    // resp.Count：匹配的 key 数量
    fmt.Printf("匹配 %d 个 key\n", resp.Count)

    // 2. 前缀查询：获取 /config/ 下的所有配置
    // 这是 etcd 最常用的查询模式——按目录结构组织 key
    prefixResp, err := client.Get(ctx, "/config/", clientv3.WithPrefix())
    if err != nil {
        return err
    }
    fmt.Printf("找到 %d 个配置项:\n", prefixResp.Count)
    for _, kv := range prefixResp.Kvs {
        fmt.Printf("  %s = %s\n", kv.Key, kv.Value)
    }

    // 3. 分页查询：数据量大时避免一次拉取过多
    pageResp, err := client.Get(ctx, "/config/",
        clientv3.WithPrefix(),
        clientv3.WithLimit(10),          // 最多返回 10 条
        clientv3.WithLastRev(),          // 从最新 revision 开始
    )
    if err != nil {
        return err
    }
    fmt.Printf("分页查询: 返回 %d 条 (total=%d)\n",
        len(pageResp.Kvs), pageResp.Count)

    // 4. 获取历史版本：etcd 的 MVCC 特性
    // 通过 WithRev() 查询历史 revision 的数据
    // 这在故障回溯、审计日志等场景非常有用
    if resp.Header.Revision > 1 {
        histResp, err := client.Get(ctx, "/config/db_host",
            clientv3.WithRev(resp.Header.Revision-1))
        if err == nil &amp;&amp; len(histResp.Kvs) > 0 {
            fmt.Printf("上一版本的值: %s\n", histResp.Kvs[0].Value)
        }
    }

    // 5. 只查询 key 不查询 value（节省带宽）
    countResp, err := client.Get(ctx, "/service/",
        clientv3.WithPrefix(),
        clientv3.WithCountOnly(),
    )
    if err != nil {
        return err
    }
    fmt.Printf("服务总数: %d\n", countResp.Count)

    return nil
}
```

#### DELETE：删除键值

```go
func basicDeleteExample(client *clientv3.Client) error {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    // 1. 删除单个 key
    delResp, err := client.Delete(ctx, "/config/db_host")
    if err != nil {
        return fmt.Errorf("DELETE 失败: %w", err)
    }
    fmt.Printf("删除了 %d 个 key\n", delResp.Deleted)

    // 2. 前缀删除：删除某个目录下的所有 key
    // 谨慎使用！误用可能导致大面积数据丢失
    prefixDelResp, err := client.Delete(ctx, "/temp/",
        clientv3.WithPrefix())
    if err != nil {
        return err
    }
    fmt.Printf("前缀删除了 %d 个 key\n", prefixDelResp.Deleted)

    // 3. 带条件的删除：只删除特定 version 的 key
    // 典型场景：乐观锁，防止并发覆盖
    condDelResp, err := client.Delete(ctx, "/config/db_host",
        clientv3.WithPrevKV()) // 返回被删除的旧值
    if err != nil {
        return err
    }
    if len(condDelResp.PrevKvs) > 0 {
        fmt.Printf("已删除: %s = %s\n",
            condDelResp.PrevKvs[0].Key, condDelResp.PrevKvs[0].Value)
    }

    return nil
}
```

### 事务操作（Txn）

事务是 etcd 实现原子性条件操作的核心机制，也是分布式锁（技巧六）和选主（技巧七）的底层基石。etcd 的事务模型是 **IF-THEN-ELSE** 结构：如果条件满足，则执行一组操作；否则，执行另一组操作。

#### 原子性条件写入

```go
func txnExample(client *clientv3.Client) error {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    // 场景：只在 key 不存在时才写入（类似 Redis 的 SET NX）
    // IF: /config/db_host 的 version == 0（即 key 不存在）
    // THEN: 创建 /config/db_host = "10.0.0.1"
    // ELSE: 不做任何操作（或执行备选逻辑）
    resp, err := client.Txn(ctx).
        If(clientv3.Compare(
            clientv3.Version("/config/db_host"), "=", 0, // version=0 表示不存在
        )).
        Then(
            clientv3.OpPut("/config/db_host", "10.0.0.1"),
        ).
        Else(
            // key 已存在，不做操作（也可放置其他操作）
        ).
        Commit()
    if err != nil {
        return fmt.Errorf("事务执行失败: %w", err)
    }

    if resp.Succeeded {
        fmt.Println("key 不存在，已成功创建")
    } else {
        fmt.Println("key 已存在，跳过创建")
    }

    return nil
}
```

#### 比较操作详解

etcd 事务支持三种类型的比较操作：

| 比较方法 | 含义 | 典型用途 |
|----------|------|---------|
| `clientv3.Version(key)` | key 的当前版本（删除后为 0） | CAS：只在 key 不存在时写入 |
| `clientv3.CreateRevision(key)` | key 首次创建时的 revision | 按创建顺序判断 |
| `clientv3.ModRevision(key)` | key 最后修改时的 revision | 乐观锁：只在未被修改时更新 |
| `clientv3.Value(key)` | key 的当前 value | 基于值的条件判断 |

比较操作符：`=`、`>`、`<`、`>=`、`<=`

#### 多步事务：原子性批量操作

```go
func multiStepTxn(client *clientv3.Client) error {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    // 场景：原子性地将配置从 A 迁移到 B
    // IF: /config/old_key 存在 AND /config/new_key 不存在
    // THEN: 删除 old_key，创建 new_key
    resp, err := client.Txn(ctx).
        If(
            // 多个条件用 And 连接
            clientv3.Compare(
                clientv3.Version("/config/old_key"), ">", 0),
            clientv3.Compare(
                clientv3.Version("/config/new_key"), "=", 0),
        ).
        Then(
            // 条件满足时执行多个操作（原子性保证）
            clientv3.OpDelete("/config/old_key"),
            clientv3.OpPut("/config/new_key", "migrated-value"),
            clientv3.OpPut("/config/migration_log", "completed"),
        ).
        Else(
            clientv3.OpPut("/config/migration_log", "skipped"),
        ).
        Commit()
    if err != nil {
        return err
    }

    fmt.Printf("事务 %s, revision=%d\n",
        map[bool]string{true: "成功", false: "失败"}[resp.Succeeded],
        resp.Header.Revision)
    return nil
}
```

> **事务的局限性：** etcd 事务的条件部分（If）最多包含 128 个比较操作，Then/Else 部分最多包含 128 个操作。这是 etcd 为了避免单个事务占用过多资源而设置的限制。如果你需要的操作超过这个限制，应该拆分为多个事务。

### Watch 机制：实时监听变更

Watch 是 etcd 最强大的特性之一，也是构建实时配置推送、服务发现、事件驱动架构的核心。Watch 基于 etcd 的 MVCC 机制，可以从任意历史 revision 开始监听，保证不丢事件。

#### 基础 Watch

```go
func basicWatchExample(client *clientv3.Client) {
    // Watch 一个特定 key 的变更
    watchCh := client.Watch(context.Background(), "/config/db_host")

    go func() {
        for resp := range watchCh {
            for _, event := range resp.Events {
                switch event.Type {
                case clientv3.EventTypePut:
                    fmt.Printf("[PUT] key=%s, value=%s, revision=%d\n",
                        event.Kv.Key, event.Kv.Value, event.Kv.ModRevision)
                case clientv3.EventTypeDelete:
                    fmt.Printf("[DELETE] key=%s, revision=%d\n",
                        event.Kv.Key, event.Kv.ModRevision)
                }
            }
        }
    }()
    // 注意：如果不启动 goroutine，Watch 会阻塞当前 goroutine
}
```

#### 前缀 Watch（监听目录）

```go
func prefixWatchExample(client *clientv3.Client) {
    // Watch /config/ 下的所有 key 变更
    // 这是实现"配置中心"的核心模式
    watchCh := client.Watch(context.Background(), "/config/",
        clientv3.WithPrefix(),   // 前缀匹配
        clientv3.WithPrevKV(),   // 同时返回变更前的旧值
    )

    go func() {
        for resp := range watchCh {
            for _, event := range resp.Events {
                oldVal := ""
                if event.PrevKv != nil {
                    oldVal = string(event.PrevKv.Value)
                }
                fmt.Printf("[%s] %s: %s → %s (rev=%d)\n",
                    event.Type,
                    event.Kv.Key,
                    oldVal,
                    event.Kv.Value,
                    event.Kv.ModRevision,
                )
            }
        }
    }()
}
```

#### 历史回放 Watch（从指定 revision 开始）

这是 Watch 机制最精妙的特性——支持从任意历史 revision 开始监听。典型应用场景：应用重启后，从上次断开的位置继续接收事件，不丢失任何变更。

```go
func historicalWatchExample(client *clientv3.Client, lastRevision int64) {
    // 从指定 revision 开始监听
    // 这保证了即使 Watch 中断，也不会遗漏事件
    watchCh := client.Watch(context.Background(), "/config/",
        clientv3.WithPrefix(),
        clientv3.WithRev(lastRevision), // 从上次断开的 revision 开始
    )

    go func() {
        for resp := range watchCh {
            // 更新已处理的 revision
            lastRevision = resp.Header.Revision

            for _, event := range resp.Events {
                fmt.Printf("[rev=%d] %s %s = %s\n",
                    event.Kv.ModRevision, event.Type, event.Kv.Key, event.Kv.Value)
            }

            // 检查 Watch 是否因为压缩（compaction）而丢失事件
            if resp.IsProgressNotify() {
                fmt.Printf("进度通知: 当前 revision=%d\n", resp.Header.Revision)
            }
        }
    }()
}
```

#### Watch 的失败恢复与 revision 压缩处理

生产环境中，etcd 会定期压缩历史 revision（技巧三），如果 Watch 的起始 revision 已经被压缩，会收到错误。正确处理这种场景至关重要：

```go
func resilientWatch(client *clientv3.Client) {
    var startRevision int64 = 0 // 0 表示从当前最新 revision 开始

    for {
        watchOpts := []clientv3.WatchOption{
            clientv3.WithPrefix(),
        }
        if startRevision > 0 {
            watchOpts = append(watchOpts, clientv3.WithRev(startRevision))
        }

        watchCh := client.Watch(context.Background(), "/config/", watchOpts...)

        for resp := range watchCh {
            if resp.Err() != nil {
                // Watch 因 revision 压缩等原因中断
                log.Printf("Watch 中断: %v, 将从最新 revision 重新开始", resp.Err())
                startRevision = 0 // 重置为从最新开始
                break
            }

            // 处理正常事件
            for _, event := range resp.Events {
                handleEvent(event)
                startRevision = event.Kv.ModRevision + 1
            }
        }

        // Watch channel 关闭（网络断开等），等待后重试
        log.Println("Watch channel 已关闭，2 秒后重试...")
        time.Sleep(2 * time.Second)
    }
}

func handleEvent(event *clientv3.Event) {
    fmt.Printf("处理事件: %s %s = %s\n", event.Type, event.Kv.Key, event.Kv.Value)
}
```

> **revision 压缩是 Watch 的头号杀手：** etcd 默认在 revision 差距超过 10,000 时自动压缩历史。如果你的 Watch 消费者长时间未处理事件（比如消费者宕机了 1 小时），重启后可能发现起始 revision 已被压缩。解决方案：(1) 缩短压缩间隔的消费者依赖；(2) 收到压缩错误时从最新 revision 重新开始；(3) 使用 WithProgressNotify 定期获取进度，持久化最新 revision。

### Lease 机制：自动过期与心跳检测

Lease 是 etcd 实现"临时数据"和"心跳检测"的核心机制。每个 Lease 都有一个 TTL（Time To Live），客户端必须定期续租（keepAlive），否则 Lease 到期后，绑定该 Lease 的所有 key 会被自动删除。

#### 创建与使用 Lease

```go
func leaseExample(client *clientv3.Client) error {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    // 创建一个 TTL 为 10 秒的 Lease
    // 意味着：如果 10 秒内没有续租，绑定的 key 会被自动删除
    leaseResp, err := client.Grant(ctx, 10)
    if err != nil {
        return fmt.Errorf("创建 Lease 失败: %w", err)
    }
    leaseID := leaseResp.ID
    fmt.Printf("Lease ID: %d, TTL: %ds\n", leaseID, leaseResp.TTL)

    // 将 key 绑定到 Lease
    // Lease 到期后，这个 key 会被自动删除
    _, err = client.Put(ctx, "/service/worker-1", "alive",
        clientv3.WithLease(leaseID))
    if err != nil {
        return fmt.Errorf("绑定 Lease 失败: %w", err)
    }

    // 启动自动续租（keepAlive）
    // keepAliveCh 会定期收到续租成功的确认
    keepAliveCh, err := client.KeepAlive(context.Background(), leaseID)
    if err != nil {
        return fmt.Errorf("启动 keepAlive 失败: %w", err)
    }

    // 监听续租状态
    go func() {
        for ka := range keepAliveCh {
            if ka == nil {
                // keepAliveCh 关闭，说明 Lease 已过期或客户端断开
                log.Println("Lease keepAlive 已断开，需要重新建立连接和 Lease")
                return
            }
            // 续租成功
            // ka.TTL: 当前 Lease 的剩余 TTL（秒）
            fmt.Printf("Lease 续租成功, TTL=%d\n", ka.TTL)
        }
    }()

    // 等待一段时间后手动撤销 Lease（会删除绑定的 key）
    time.Sleep(30 * time.Second)

    _, err = client.Revoke(ctx, leaseID)
    if err != nil {
        return fmt.Errorf("撤销 Lease 失败: %w", err)
    }
    fmt.Println("Lease 已撤销，绑定的 key 已删除")

    return nil
}
```

#### Lease 的典型应用场景

**场景 1：服务注册与心跳检测**

这是 Lease 最常见的用途——微服务启动时注册自己的地址，通过 keepAlive 保持在线状态。服务下线后（keepAlive 断开），Lease 过期，注册信息自动清除。

```go
// 服务注册器
type ServiceRegistry struct {
    client   *clientv3.Client
    leaseID  clientv3.LeaseID
    serviceKey string
}

func NewServiceRegistry(client *clientv3.Client, serviceName, addr string, ttl int64) (*ServiceRegistry, error) {
    ctx := context.Background()

    // 创建 Lease
    resp, err := client.Grant(ctx, ttl)
    if err != nil {
        return nil, err
    }

    key := fmt.Sprintf("/services/%s/%s", serviceName, addr)

    // 注册服务
    _, err = client.Put(ctx, key, addr, clientv3.WithLease(resp.ID))
    if err != nil {
        return nil, err
    }

    // 启动 keepAlive
    kaCh, err := client.KeepAlive(ctx, resp.ID)
    if err != nil {
        return nil, err
    }

    reg := &amp;ServiceRegistry{
        client:     client,
        leaseID:    resp.ID,
        serviceKey: key,
    }

    // 监控 keepAlive 状态
    go func() {
        for ka := range kaCh {
            if ka == nil {
                log.Printf("服务 %s 的 Lease 已过期，服务已下线", addr)
                return
            }
        }
    }()

    return reg, nil
}

// 注销服务
func (r *ServiceRegistry) Deregister() error {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    _, err := r.client.Revoke(ctx, r.leaseID)
    return err
}
```

**场景 2：分布式任务调度（临时 Worker 注册）**

```go
// Worker 注册：Worker 启动时注册自己，定期续租
// Worker 崩溃后，Lease 过期，调度器自动感知
func registerWorker(client *clientv3.Client, workerID string) error {
    ctx := context.Background()

    // Worker 的 Lease TTL 设为 15 秒
    // keepAlive 默认每 TTL/3 = 5 秒续租一次
    leaseResp, err := client.Grant(ctx, 15)
    if err != nil {
        return err
    }

    key := fmt.Sprintf("/workers/%s", workerID)
    value, _ := json.Marshal(map[string]interface{}{
        "id":       workerID,
        "hostname": os.Getenv("HOSTNAME"),
        "started":  time.Now().Format(time.RFC3339),
    })

    _, err = client.Put(ctx, key, string(value), clientv3.WithLease(leaseResp.ID))
    if err != nil {
        return err
    }

    // keepAlive 保证 Worker 在线
    kaCh, err := client.KeepAlive(ctx, leaseResp.ID)
    if err != nil {
        return err
    }

    // 在后台处理 keepAlive
    go func() {
        for ka := range kaCh {
            if ka == nil {
                log.Println("Worker keepAlive 断开，可能需要重启服务")
                // 在这里可以触发优雅退出或重启逻辑
                return
            }
        }
    }()

    return nil
}
```

#### keepAliveTo：精确控制续租间隔

```go
// KeepAlive 会使用默认间隔（TTL/3）
// KeepAliveTo 允许你自定义续租间隔
func keepAliveWithInterval(client *clientv3.Client, leaseID clientv3.LeaseID) {
    // 每 3 秒续租一次（不使用默认的 TTL/3）
    kaCh, err := client.KeepAliveTo(context.Background(), leaseID, 3*time.Second)
    if err != nil {
        log.Fatal(err)
    }

    go func() {
        for ka := range kaCh {
            if ka == nil {
                log.Println("续租中断")
                return
            }
        }
    }()
}
```

### 错误处理与重试策略

etcd 客户端会遇到各种错误：网络超时、Leader 切换、集群不可用、key 不存在等。生产环境必须实现健壮的错误处理和重试策略。

#### 错误分类与处理

```go
import (
    "go.etcd.io/etcd/client/v3"
    "go.etcd.io/etcd/api/v3/v3rpc/rpccompat"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
)

func classifyEtcdError(err error) string {
    if err == nil {
        return "ok"
    }

    // 1. gRPC 级别的错误
    st, ok := status.FromError(err)
    if ok {
        switch st.Code() {
        case codes.Unavailable:
            return "cluster_unavailable" // 集群不可达，可重试
        case codes.DeadlineExceeded:
            return "timeout"             // 操作超时，可重试
        case codes.Canceled:
            return "context_cancelled"   // 上下文被取消，不可重试
        case codes.Unauthenticated:
            return "auth_failed"         // 认证失败，需要检查凭证
        case codes.PermissionDenied:
            return "permission_denied"   // 权限不足
        case codes.NotFound:
            return "key_not_found"       // key 不存在
        case codes.InvalidArgument:
            return "invalid_request"     // 请求参数错误
        default:
            return fmt.Sprintf("grpc_%s", st.Code())
        }
    }

    // 2. etcd 客户端级别的错误
    switch err {
    case rpccompat.ErrNoCluster:
        return "no_cluster"
    case rpccopat.ErrNoLeader:
        return "no_leader"
    case rpccopat.ErrTooManyRequests:
        return "rate_limited"
    default:
        return "unknown"
    }
}
```

#### 带重试的操作

```go
// 重试配置
type RetryConfig struct {
    MaxRetries  int
    BaseDelay   time.Duration
    MaxDelay    time.Duration
    Retryable   []string // 可重试的错误类型
}

func DefaultRetryConfig() RetryConfig {
    return RetryConfig{
        MaxRetries: 3,
        BaseDelay:  100 * time.Millisecond,
        MaxDelay:   5 * time.Second,
        Retryable:  []string{"cluster_unavailable", "timeout"},
    }
}

// 带重试的 PUT
func putWithRetry(client *clientv3.Client, key, value string, cfg RetryConfig) error {
    var lastErr error

    for attempt := 0; attempt <= cfg.MaxRetries; attempt++ {
        if attempt > 0 {
            // 指数退避
            delay := cfg.BaseDelay * time.Duration(1<<(attempt-1))
            if delay > cfg.MaxDelay {
                delay = cfg.MaxDelay
            }
            log.Printf("重试 %d/%d, 等待 %v", attempt, cfg.MaxRetries, delay)
            time.Sleep(delay)
        }

        ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
        _, err := client.Put(ctx, key, value)
        cancel()

        if err == nil {
            return nil
        }

        lastErr = err
        errType := classifyEtcdError(err)

        // 检查是否可重试
        retryable := false
        for _, r := range cfg.Retryable {
            if errType == r {
                retryable = true
                break
            }
        }

        if !retryable {
            return fmt.Errorf("不可重试的错误: %w", err)
        }
    }

    return fmt.Errorf("重试 %d 次后仍失败: %w", cfg.MaxRetries, lastErr)
}
```

#### etcd 的 compacted revision 错误处理

这是 Watch 和历史查询中最常见的错误：

```go
func handleCompactedRevision(client *clientv3.Client, targetRev int64) ([]*clientv3.Event, error) {
    ctx := context.Background()

    // 先获取当前集群的 revision
    statusResp, err := client.Status(ctx, client.Endpoints()[0])
    if err != nil {
        return nil, err
    }

    compactRev := statusResp.CompactRevision
    if targetRev < compactRev {
        // 目标 revision 已被压缩，无法查询历史数据
        log.Printf("警告: 请求的 revision %d 已被压缩 (当前压缩到 %d)，从最新开始",
            targetRev, compactRev)

        // 策略 1：从最新开始，放弃历史数据
        targetRev = 0

        // 策略 2：如果业务要求必须从特定 revision 开始，则报错
        // return nil, fmt.Errorf("revision %d 已被压缩", targetRev)
    }

    // 从（调整后的）revision 开始 Watch
    watchCh := client.Watch(ctx, "/", clientv3.WithPrefix(),
        clientv3.WithRev(targetRev))

    var events []*clientv3.Event
    for resp := range watchCh {
        if resp.Err() != nil {
            return nil, resp.Err()
        }
        for _, ev := range resp.Events {
            events = append(events, ev)
        }
        // 一次性获取前 100 条变更后退出
        if len(events) >= 100 {
            break
        }
    }
    return events, nil
}
```

### 并发安全与连接复用

etcd 客户端是并发安全的——多个 goroutine 可以共享同一个 client 实例。但有一些重要的注意事项：

#### 连接复用原则

```go
// 正确做法：全局单例客户端，所有 goroutine 共享
var (
    etcdClient *clientv3.Client
    once       sync.Once
)

func GetEtcdClient() *clientv3.Client {
    once.Do(func() {
        var err error
        etcdClient, err = clientv3.New(clientv3.Config{
            Endpoints:   []string{"10.0.0.1:2379", "10.0.0.2:2379", "10.0.0.3:2379"},
            DialTimeout: 5 * time.Second,
        })
        if err != nil {
            log.Fatalf("初始化 etcd 客户端失败: %v", err)
        }
    })
    return etcdClient
}

// 错误做法：每次操作都创建新客户端
// 这会导致：1) 大量 gRPC 连接；2) keepAlive 协程泄漏；3) 资源浪费
func badPractice() {
    client, _ := clientv3.New(clientv3.Config{
        Endpoints: []string{"10.0.0.1:2379"},
    })
    defer client.Close()
    client.Put(context.Background(), "/key", "value")
    // 每次调用都创建+销毁一个客户端，开销巨大
}
```

#### Watch 并发安全

```go
func concurrentWatchExample(client *clientv3.Client) {
    var wg sync.WaitGroup

    // 多个 Watch 可以并发运行，共享同一个客户端
    prefixes := []string{"/config/", "/services/", "/locks/"}

    for _, prefix := range prefixes {
        wg.Add(1)
        go func(p string) {
            defer wg.Done()

            watchCh := client.Watch(context.Background(), p,
                clientv3.WithPrefix())

            for resp := range watchCh {
                for _, event := range resp.Events {
                    fmt.Printf("[%s] %s %s\n", p, event.Type, event.Kv.Key)
                }
            }
        }(prefix)
    }

    wg.Wait()
}
```

### 完整实战：配置中心

将前面的所有知识点综合，实现一个生产级的配置中心客户端：

```go
package configcenter

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "sync"
    "time"

    clientv3 "go.etcd.io/etcd/client/v3"
)

// ConfigCenter 基于 etcd 的配置中心
type ConfigCenter struct {
    client   *clientv3.Client
    prefix   string
    mu       sync.RWMutex
    configs  map[string]string // 本地缓存
    watchers map[string]clientv3.WatchChan
}

// NewConfigCenter 创建配置中心
func NewConfigCenter(endpoints []string, prefix string) (*ConfigCenter, error) {
    client, err := clientv3.New(clientv3.Config{
        Endpoints:            endpoints,
        DialTimeout:          5 * time.Second,
        DialKeepAliveTime:    10 * time.Second,
        DialKeepAliveTimeout: 3 * time.Second,
        AutoSyncInterval:     30 * time.Second,
    })
    if err != nil {
        return nil, fmt.Errorf("创建 etcd 客户端失败: %w", err)
    }

    cc := &amp;ConfigCenter{
        client:   client,
        prefix:   prefix,
        configs:  make(map[string]string),
        watchers: make(map[string]clientv3.WatchChan),
    }

    // 初始化：加载所有现有配置
    if err := cc.loadAll(); err != nil {
        client.Close()
        return nil, fmt.Errorf("加载配置失败: %w", err)
    }

    // 启动 Watch 监听配置变更
    cc.startWatch()

    return cc, nil
}

// loadAll 加载所有配置到本地缓存
func (cc *ConfigCenter) loadAll() error {
    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()

    resp, err := cc.client.Get(ctx, cc.prefix, clientv3.WithPrefix())
    if err != nil {
        return err
    }

    cc.mu.Lock()
    defer cc.mu.Unlock()

    for _, kv := range resp.Kvs {
        key := string(kv.Key)
        value := string(kv.Value)
        cc.configs[key] = value
    }

    log.Printf("配置中心: 加载了 %d 个配置项", len(cc.configs))
    return nil
}

// startWatch 启动配置变更监听
func (cc *ConfigCenter) startWatch() {
    go func() {
        for {
            watchCh := cc.client.Watch(context.Background(), cc.prefix,
                clientv3.WithPrefix(),
                clientv3.WithPrevKV(),
            )

            for resp := range watchCh {
                if resp.Err() != nil {
                    log.Printf("Watch 错误: %v, 3 秒后重建", resp.Err())
                    time.Sleep(3 * time.Second)
                    break
                }

                for _, event := range resp.Events {
                    key := string(event.Kv.Key)

                    cc.mu.Lock()
                    switch event.Type {
                    case clientv3.EventTypePut:
                        cc.configs[key] = string(event.Kv.Value)
                        log.Printf("配置更新: %s = %s", key, event.Kv.Value)
                    case clientv3.EventTypeDelete:
                        delete(cc.configs, key)
                        log.Printf("配置删除: %s", key)
                    }
                    cc.mu.Unlock()
                }
            }
        }
    }()
}

// Get 获取配置值
func (cc *ConfigCenter) Get(key string) (string, bool) {
    cc.mu.RLock()
    defer cc.mu.RUnlock()
    val, ok := cc.configs[cc.prefix+key]
    return val, ok
}

// GetAs 获取配置值并反序列化
func (cc *ConfigCenter) GetAs(key string, target interface{}) error {
    val, ok := cc.Get(key)
    if !ok {
        return fmt.Errorf("配置 %s 不存在", key)
    }
    return json.Unmarshal([]byte(val), target)
}

// Set 设置配置值
func (cc *ConfigCenter) Set(ctx context.Context, key, value string) error {
    _, err := cc.client.Put(ctx, cc.prefix+key, value)
    return err
}

// Close 关闭配置中心
func (cc *ConfigCenter) Close() error {
    return cc.client.Close()
}
```

**使用示例：**

```go
func main() {
    cc, err := NewConfigCenter(
        []string{"10.0.0.1:2379", "10.0.0.2:2379", "10.0.0.3:2379"},
        "/myapp/config/",
    )
    if err != nil {
        log.Fatal(err)
    }
    defer cc.Close()

    // 读取配置
    dbHost, ok := cc.Get("db_host")
    if ok {
        fmt.Println("数据库地址:", dbHost)
    }

    // 反序列化复杂配置
    type DBConfig struct {
        Host     string `json:"host"`
        Port     int    `json:"port"`
        Username string `json:"username"`
    }
    var dbCfg DBConfig
    if err := cc.GetAs("database", &amp;dbCfg); err != nil {
        fmt.Println("解析数据库配置失败:", err)
    }

    // 写入配置（会被 Watch 自动同步到本地缓存）
    ctx := context.Background()
    cc.Set(ctx, "db_host", "10.0.0.2")
}
```

### 常见误区与最佳实践

#### 误区 1：不关闭客户端导致 goroutine 泄漏

```go
// 错误：客户端不关闭
func bad() {
    client, _ := clientv3.New(clientv3.Config{...})
    client.Put(ctx, "/key", "value")
    // client 从未 Close，内部 goroutine 泄漏
}

// 正确：始终使用 defer Close
func good() {
    client, err := clientv3.New(clientv3.Config{...})
    if err != nil {
        log.Fatal(err)
    }
    defer client.Close()
    client.Put(ctx, "/key", "value")
}
```

#### 误区 2：Watch 不处理 channel 关闭

```go
// 错误：只在启动时 Watch 一次
func bad() {
    watchCh := client.Watch(ctx, "/config/", clientv3.WithPrefix())
    for resp := range watchCh {
        // 如果网络断开，channel 会关闭，循环退出
        // 但没有重新 Watch，后续变更全部丢失
    }
}

// 正确：循环重建 Watch
func good() {
    for {
        watchCh := client.Watch(ctx, "/config/", clientv3.WithPrefix())
        for resp := range watchCh {
            // 处理事件
        }
        log.Println("Watch 断开，重建中...")
        time.Sleep(time.Second)
    }
}
```

#### 误区 3：Lease 不监控 keepAlive 状态

```go
// 错误：启动 keepAlive 后就不管了
func bad() {
    leaseResp, _ := client.Grant(ctx, 10)
    client.Put(ctx, "/key", "value", clientv3.WithLease(leaseResp.ID))
    client.KeepAlive(ctx, leaseResp.ID)
    // keepAlive 失败时没有任何处理
}

// 正确：监控 keepAlive 状态并处理失败
func good() {
    leaseResp, _ := client.Grant(ctx, 10)
    client.Put(ctx, "/key", "value", clientv3.WithLease(leaseResp.ID))
    kaCh, _ := client.KeepAlive(ctx, leaseResp.ID)

    go func() {
        for ka := range kaCh {
            if ka == nil {
                log.Println("keepAlive 断开！需要重建 Lease")
                // 在这里触发重建逻辑
                return
            }
        }
    }()
}
```

#### 误区 4：所有操作使用同一个超时时间

```go
// 不同操作应使用不同的超时时间
func goodTimeouts(client *clientv3.Client) {
    // 快速读取：2 秒超时（读操作应该快）
    readCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
    defer cancel()
    client.Get(readCtx, "/config/key")

    // 写入：5 秒超时（写操作需要等 Leader 确认）
    writeCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()
    client.Put(writeCtx, "/config/key", "value")

    // 大批量操作：30 秒超时
    batchCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()
    // ... 批量操作
}
```

#### 最佳实践清单

| 实践 | 原因 |
|------|------|
| 全局单例客户端 | 避免重复创建 gRPC 连接和 goroutine |
| 必须 defer Close | 防止 goroutine 和连接泄漏 |
| 设置合理超时 | 读操作 2s、写操作 5s、批量操作 30s |
| 启用 AutoSyncInterval | 节点变更后自动感知，无需重启 |
| Watch 必须处理 channel 关闭 | 防止事件丢失 |
| keepAlive 必须监控状态 | Lease 过期后及时重建 |
| 前缀查询用 WithPrefix | 避免全量扫描，性能最优 |
| 大 value 限制在 1.5MB | etcd 的 value 大小硬限制 |
| 生产环境启用 TLS | 防止数据泄露和未授权访问 |
| 错误处理区分重试与不可重试 | 超时和集群不可用可重试；权限错误不可重试 |

### 与 v2 客户端的对比

etcd 同时提供 v2 和 v3 两个版本的客户端，但它们有本质区别：

| 特性 | v2 客户端 | v3 客户端 |
|------|----------|----------|
| 协议 | HTTP REST | gRPC |
| 数据存储 | 内存 | 磁盘（BoltDB） |
| Watch | 基于轮询 | 基于 gRPC 流，实时推送 |
| 事务 | 不支持 | IF-THEN-ELSE 原子事务 |
| Revision | 不支持 | 全局单调递增 revision |
| Lease | 不支持 | TTL + keepAlive |
| 前缀查询 | 支持 | 支持，性能更好 |
| 推荐 | 仅用于遗留系统 | **所有新项目必须使用 v3** |

> **不要使用 v2 客户端开发新项目。** v2 客户端已经停止维护，功能和性能都不如 v3。etcd 3.x 版本的推荐 API 是 v3。

### 本技巧小结

etcd Go 客户端看似简单，但生产级使用需要掌握的关键点很多：

1. **连接管理**：全局单例、合理超时、keepAlive 保活、TLS 加密
2. **基础操作**：GET/PUT/DELETE 的各种选项（前缀、分页、历史版本、WithPrevKV）
3. **事务机制**：IF-THEN-ELSE 原子操作，三种比较类型，128 操作限制
4. **Watch 机制**：前缀 Watch、历史回放 Watch、失败重建、revision 压缩处理
5. **Lease 机制**：自动过期、keepAlive 续租、服务注册、心跳检测
6. **错误处理**：错误分类、指数退避重试、compacted revision 处理
7. **并发安全**：客户端并发安全但要注意连接复用

掌握这些知识点后，你就能用 etcd Go 客户端构建生产级的分布式应用。接下来的技巧六（分布式锁）和技巧七（选主）将直接使用本技巧的事务、Lease 和 Watch 能力，构建更复杂的分布式协调原语。
