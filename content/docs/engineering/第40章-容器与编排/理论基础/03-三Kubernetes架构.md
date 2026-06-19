---
title: "Kubernetes架构深度解析"
type: docs
weight: 3
---
## 三、Kubernetes架构深度解析

Kubernetes（简称K8s）是Google基于Borg系统经验开源的容器编排平台，已成为云原生基础设施的事实标准。理解其架构不是"背组件名"，而是掌握**声明式控制循环**这一核心设计哲学——你描述期望状态（Desired State），系统持续将实际状态（Actual State）向期望状态收敛。

这一设计哲学的本质是**控制论（Cybernetics）**在软件工程中的应用：设定目标 → 观测偏差 → 执行修正 → 再观测，形成闭环。整个Kubernetes就是围绕这个控制循环构建的——从最顶层的Deployment控制器到底层的kubelet，每一层都在不断地"观测→比较→修正"。

### 3.1 架构全景

Kubernetes采用**控制平面（Control Plane）+ 数据平面（Data Plane）**的经典分布式架构：

```mermaid
graph TB
    subgraph CP["控制平面 (Control Plane)"]
        API["kube-apiserver<br/>集群网关"]
        ETCD["etcd<br/>分布式KV存储"]
        SCH["kube-scheduler<br/>Pod调度器"]
        CCM["kube-controller-manager<br/>控制器管理器"]
        CCM2["cloud-controller-manager<br/>云厂商适配层"]
    end

    subgraph DP["数据平面 (Worker Node)"]
        subgraph N1["Node 1"]
            KL1["kubelet"]
            KP1["kube-proxy"]
            CRT1["Container Runtime<br/>(containerd)"]
            P1A["Pod A"]
            P1B["Pod B"]
        end
        subgraph N2["Node 2"]
            KL2["kubelet"]
            KP2["kube-proxy"]
            CRT2["Container Runtime<br/>(containerd)"]
            P2A["Pod C"]
            P2B["Pod D"]
        end
    end

    API --> ETCD
    API --> SCH
    API --> CCM
    API --> CCM2
    SCH --> API
    CCM --> API
    KL1 --> API
    KL2 --> API
    KP1 -.-> P1A
    KP1 -.-> P1B
    KP2 -.-> P2A
    KP2 -.-> P2B
    KL1 --> CRT1
    KL2 --> CRT2
```

**核心数据流**：用户通过kubectl或API提交声明式配置 → API Server验证并持久化到etcd → Scheduler根据调度策略将Pod分配到Node → 对应Node的kubelet拉起容器 → Controller Manager持续监测实际状态并执行调谐（Reconcile）。

理解这条数据流的关键在于：**所有组件之间不直接通信，只通过API Server交互**。API Server是整个集群的唯一通信中枢，这使得权限控制、审计日志、事件通知等横切关注点可以在一处统一处理。

### 3.2 控制平面组件详解

#### 3.2.1 kube-apiserver：集群的唯一入口

kube-apiserver是整个集群的**网关和中枢**，所有组件（包括kubectl、kubelet、controller-manager、scheduler）都只通过它与集群交互。

**核心职责**：

| 职责 | 说明 | 为什么重要 |
|------|------|-----------|
| **RESTful API网关** | 暴露集群的统一API入口（/api、/apis） | 消费者不需要知道后端存储细节 |
| **认证（Authentication）** | 验证"你是谁"——证书、Token、OIDC | 防止未授权访问集群 |
| **授权（Authorization）** | 判断"你能做什么"——RBAC/ABAC | 实现最小权限原则 |
| **准入控制（Admission Control）** | 请求进入etcd前的"最后检查站" | 可以修改（Mutating）或拦截（Validating）请求 |
| **数据序列化** | 将JSON/YAML对象存储为Protobuf到etcd | 减少存储开销，提升性能 |
| **Watch机制** | 基于etcd的Watch提供事件通知 | 所有组件依赖此机制实现事件驱动 |

**准入控制链**是生产中极其重要但常被忽略的部分。一个请求经过API Server的完整流程：

客户端请求 → 认证(AuthN) → 授权(AuthZ) → 准入控制(Admission) → etcd
                                │
                    ┌───────────┴───────────┐
                    │                       │
              MutatingAdmission        ValidatingAdmission
              (可以修改请求)             (只能校验/拒绝)
              如：注入sidecar           如：资源配额检查
                  自动设置标签
                  注入环境变量

**认证方式详解**：

| 认证方式 | 原理 | 适用场景 |
|---------|------|---------|
| **X.509客户端证书** | CA签名的客户端证书，CN字段标识用户身份 | 组件间通信（kubelet、controller-manager）、kubectl |
| **Bearer Token** | 静态Token文件或ServiceAccount Token | API调用、CI/CD系统 |
| **OIDC** | 基于OAuth 2.0的身份联合 | 企业SSO集成（如GitHub、Google登录） |
| **Webhook** | 外部认证服务回调 | 与企业IAM系统集成 |
| **Proxy** | 请求头中传递认证信息 | 反向代理场景 |

**生产要点**：

- **高可用部署**：至少3个API Server实例，前端负载均衡器（如HAProxy/Nginx/云LB）分发请求。API Server是无状态的，所有状态存在etcd
- **聚合层（Aggregation Layer）**：允许注册自定义API Server扩展原生API，如Prometheus的`/apis/metrics.k8s.io`
- **审计日志（Audit Log）**：生产集群必须开启，记录所有API调用用于安全审计和故障排查
- **请求限流**：API Server内置了API Priority and Fairness（APF），通过并发限制和队列机制防止请求风暴

```yaml
# 启用审计日志示例（kube-apiserver启动参数）
--audit-policy-file=/etc/kubernetes/audit-policy.yaml
--audit-log-path=/var/log/kubernetes/audit.log
--audit-log-maxage=30
--audit-log-maxbackup=10
--audit-log-maxsize=100
```

```yaml
# audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  # 不记录健康检查等低价值请求
  - level: None
    nonResourceURLs: ["/healthz*", "/version", "/readyz"]
  # Secret相关请求用详细级别记录
  - level: RequestResponse
    resources: [{group: "", resources: ["secrets"]}]
  # 其他请求记录元数据
  - level: Metadata
```

#### 3.2.2 etcd：集群的唯一真理来源

etcd是Kubernetes的**分布式键值存储**，保存整个集群的所有状态数据——Pod定义、Service配置、Secret、ConfigMap、节点信息等。它是控制平面中唯一有状态的组件。

**为什么选etcd**：

| 特性 | 说明 |
|------|------|
| **强一致性** | 基于Raft共识协议，写入多数节点后才算成功 |
| **高可用** | 3或5节点集群可容忍1或2个节点故障 |
| **Watch机制** | 支持高效的变化通知，Kubernetes的核心依赖 |
| **高性能** | 单实例可达10K+ writes/sec，满足大规模集群需求 |
| **简单可靠** | Go实现，单二进制部署，10年以上的生产验证 |

**Raft协议工作原理**：

所有写请求 → Leader节点
Leader → 将日志条目复制到多数（N/2+1）Follower
复制成功 → 提交（Commit）→ 应用到状态机 → 返回客户端

Raft协议确保了分布式系统中最重要的特性：**线性一致性写入**。具体来说：

- **Leader**：处理所有写请求，负责日志复制。Leader通过心跳机制维持权威
- **Follower**：被动接收Leader的日志复制。如果超时未收到心跳，转为Candidate发起选举
- **Candidate**：选举期间的临时角色，向其他节点请求投票。获得多数票后成为新Leader

**Leader选举过程**：

Follower超时 → 变为Candidate → 递增任期号(Term) → 请求投票
├── 获得多数票 → 成为Leader → 开始复制日志
└── 收到新Leader心跳 → 回退为Follower
    └── 投票冲突 → 降级为Follower

**etcd集群规模建议**：

| 集群规模 | etcd节点数 | 容忍故障数 | 适用场景 |
|---------|-----------|-----------|---------|
| 小型（<50 Node） | 3 | 1 | 开发测试、边缘部署 |
| 中型（50-500 Node） | 3-5 | 1-2 | 中等规模生产 |
| 大型（>500 Node） | 5 | 2 | 大规模生产环境 |

**生产关键配置**：

```bash
# etcd推荐启动参数
etcd \
  --name=etcd0 \
  --data-dir=/var/lib/etcd \
  --wal-dir=/var/lib/etcd/wal \
  --snapshot-count=10000 \
  --heartbeat-interval=100 \
  --election-timeout=1000 \
  --max-snapshots=5 \
  --max-wals=5 \
  --quota-backend-bytes=8589934592  # 8GB存储上限
```

**备份与恢复**是etcd运维中最关键的操作：

```bash
# 定期备份（建议每小时自动执行）
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd-$(date +%Y%m%d-%H%M).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# 验证备份完整性
ETCDCTL_API=3 etcdctl snapshot status /backup/etcd-snapshot.db --write-table

# 灾难恢复（仅在完全丢失时使用）
ETCDCTL_API=3 etcdctl snapshot restore /backup/etcd-snapshot.db \
  --data-dir=/var/lib/etcd-restored
```

**etcd性能调优要点**：

- **磁盘IO是第一瓶颈**：必须使用SSD，推荐IOPS > 10000。etcd对磁盘延迟极为敏感，HDD会导致集群性能急剧下降
- **专用磁盘**：etcd数据盘不要与其他服务共享，避免IO争用
- **WAL预分配**：使用`fallocate`预分配WAL文件空间减少延迟抖动
- **监控etcd指标**：
  - `etcd_disk_wal_fsync_duration_seconds` — WAL同步延迟，P99应 < 10ms
  - `etcd_server_leader_changes_seen_total` — Leader切换次数，频繁切换说明网络或磁盘有问题
  - `etcd_server_proposals_failed_total` — 提案失败数，持续增长说明集群不稳定
  - `etcd_debugging_mvcc_db_total_size_in_bytes` — 数据库大小，接近quota-backend-bytes时需要压缩

```bash
# etcd碎片整理（定期执行）
ETCDCTL_API=3 etcdctl defrag --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# etcd数据压缩（释放已删除key的空间）
ETCDCTL_API=3 etcdctl compact $(ETCDCTL_API=3 etcdctl endpoint status --write-out=json | jq -r '.[0].status.header.revision')
```

#### 3.2.3 kube-scheduler：智能调度器

kube-scheduler负责将未调度的Pod分配到最合适的Node。它不直接执行——只做决策并通过API Server通知kubelet。

**调度流程分三个阶段**：

```mermaid
graph LR
    A["过滤（Filtering）<br/>排除不合适的节点"] --> B["打分（Scoring）<br/>给候选节点评分"] --> C["绑定（Binding）<br/>将Pod分配到最优节点"]
```

**过滤阶段**（硬性条件，不满足直接排除）：

| 过滤器 | 作用 | 典型场景 |
|--------|------|---------|
| NodeResourcesFit | 检查节点CPU/内存是否足够 | 所有Pod调度 |
| PodFitsHostPorts | 检查端口是否冲突 | hostPort场景 |
| PodFitsNodes | 处理nodeSelector | 指定节点部署 |
| NodeAffinity | 处理节点亲和性硬约束 | 必须调度到特定标签节点 |
| TaintToleration | 检查污点与容忍匹配 | 独占节点、GPU节点 |

**打分阶段**（软性偏好，权重越高影响越大）：

| 打分器 | 作用 | 默认权重 |
|--------|------|---------|
| LeastAllocated | 倾向资源利用率低的节点（默认） | 1 |
| MostAllocated | 倾向资源利用率高的节点（装箱） | 1 |
| NodeAffinity | 匹配preferredDuringScheduling | 1 |
| ImageLocality | 倾向已有镜像的节点 | 1 |
| InterPodAffinity | Pod间亲和性匹配 | 1 |

**调度策略配置示例**：

```yaml
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
profiles:
- schedulerName: default-scheduler
  plugins:
    score:
      disabled:
      - name: NodeResourcesFit  # 禁用默认的"最少资源"策略
      enabled:
      - name: NodeResourcesMostAllocated  # 启用"最多资源"策略（装箱）
        weight: 2
  pluginConfig:
  - name: NodeResourcesMostAllocated
    args:
      resources:
      - name: cpu
        weight: 1
      - name: memory
        weight: 1
```

**亲和性、反亲和性与污点容忍**：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-app
spec:
  # 节点亲和性（硬性：必须满足）
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: zone
            operator: In
            values: ["us-east-1a", "us-east-1b"]

    # 节点亲和性（软性：尽量满足）
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 80
        preference:
          matchExpressions:
          - key: disk-type
            operator: In
            values: ["ssd"]

    # Pod反亲和性：同类型的Pod尽量分散
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values: ["web"]
        topologyKey: kubernetes.io/hostname

  # 污点容忍
  tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "gpu"
    effect: "NoSchedule"
    tolerationSeconds: 3600  # 最多容忍1小时
```

**污点效果三兄弟**：

| 效果 | 含义 | 对已运行Pod的影响 |
|------|------|-----------------|
| `NoSchedule` | 不允许新Pod调度到此节点 | 不影响已运行的Pod |
| `PreferNoSchedule` | 尽量不调度，但非强制 | 不影响已运行的Pod |
| `NoExecute` | 驱逐已运行的Pod | 已运行的Pod如果没有容忍，会被驱逐 |

#### 3.2.4 kube-controller-manager：持续调谐的中枢

kube-controller-manager运行着一组独立的控制器（Controller），每个控制器负责一类资源的**调谐循环（Reconcile Loop）**——这是Kubernetes最核心的设计模式。

**核心控制器及其职责**：

| 控制器 | 监听资源 | 调谐逻辑 |
|--------|---------|---------|
| **DeploymentController** | Deployment, ReplicaSet | 确保Pod副本数符合期望，管理滚动更新 |
| **ReplicaSetController** | ReplicaSet, Pod | 确保指定数量的Pod副本运行 |
| **NodeController** | Node | 监测节点健康状态，处理节点故障（标记NotReady、驱逐Pod） |
| **JobController** | Job, Pod | 管理一次性的计算任务，确保指定数量的Pod成功完成 |
| **ServiceController** | Service, Endpoints | 为Service创建负载均衡器（云环境） |
| **EndpointController** | Service, Pod | 维护Service到Pod的映射关系 |
| **PVController** | PV, PVC, StorageClass | 处理持久卷的绑定和回收 |
| **NamespaceController** | Namespace | 处理命名空间删除时的资源清理 |
| **ServiceAccountController** | ServiceAccount, Namespace | 为每个命名空间创建默认ServiceAccount |

**调谐循环的本质**：

永远循环 {
    当前状态 = 观测(目标资源)
    期望状态 = 读取(资源规格)
    if 当前状态 != 期望状态 {
        执行操作使 当前状态 → 期望状态
    }
    sleep(等待下次通知或定时)
}

这个模式确保了Kubernetes的**自愈能力**：如果你手动删除一个由Deployment管理的Pod，ReplicaSetController会立即发现副本数不符，创建新Pod补足缺口。

**自愈能力的三个层次**：

1. **容器级**：kubelet通过livenessProbe检测容器死锁，自动重启容器
2. **Pod级**：ReplicaSetController发现Pod消失，创建新Pod补充
3. **Node级**：NodeController检测节点NotReady，超时后驱逐Pod并在其他节点重新调度

**重要调优参数**：

```bash
# kube-controller-manager关键启动参数
--concurrent-replicasets=10           # 并发处理ReplicaSet的数量
--concurrent-deployment-syncs=10      # 并发处理Deployment的数量
--node-monitor-period=5s              # 节点健康检查间隔
--pod-eviction-timeout=5m             # 节点NotReady后驱逐Pod的超时
--terminated-pod-gc-threshold=12500   # 回收已终止Pod的阈值
```

#### 3.2.5 cloud-controller-manager：云厂商适配层

cloud-controller-manager（CCM）将Kubernetes核心逻辑与云厂商的API解耦，使Kubernetes能在不同云环境间移植：

- **Node Controller**：通过云API获取节点列表，标记删除的节点
- **Route Controller**：在云网络中配置Pod路由规则
- **Service Controller**：创建云负载均衡器（如AWS ELB、GCP Load Balancer）

主流云托管Kubernetes服务（EKS、GKE、AKS）已内置CCM，自建集群如不使用云环境可省略此组件。

**CCM与核心kube-controller-manager的职责分离**：

kube-controller-manager（核心逻辑）
  └── 不依赖任何云厂商API，纯Kubernetes逻辑

cloud-controller-manager（云适配层）
  ├── Node Controller → 调用云API获取节点信息
  ├── Route Controller → 配置云网络路由
  └── Service Controller → 创建云负载均衡器

这种分离使得Kubernetes可以在裸金属（Bare Metal）、私有云、公有云之间无缝切换，不会因为云厂商API变更而影响核心逻辑。

### 3.3 数据平面组件

#### 3.3.1 kubelet：Node上的Agent

kubelet运行在每个Worker Node上，是控制平面与容器运行时之间的桥梁：

**核心职责**：

1. **Pod生命周期管理**：接收PodSpec，创建/停止容器
2. **健康检查执行**：按配置执行livenessProbe、readinessProbe、startupProbe
3. **资源上报**：定期向API Server报告节点资源使用情况（CPU、内存、磁盘、网络）
4. **容器日志收集**：管理容器日志，对接日志驱动
5. **容器执行器接口**：通过CRI（Container Runtime Interface）与containerd/CRI-O通信

**kubelet的关键工作流程**：

API Server ←→ kubelet（Watch机制）
   ↓              ↓
etcd存储      kubelet执行
   ↓              ↓
PodSpec       创建/管理容器
              ├── 拉取镜像
              ├── 创建容器
              ├── 执行健康检查
              ├── 挂载卷
              └── 上报状态

**kubelet关键配置**：

```yaml
# /var/lib/kubelet/config.yaml（kubelet配置文件）
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
clusterDomain: cluster.local
clusterDNS:
- 10.96.0.10
maxPods: 110                    # 每个节点最多运行的Pod数
podsPerCore: 0                  # 0表示不限制（按maxPods限制）
evictionHard:                   # 资源不足时的驱逐阈值
  memory.available: "500Mi"
  nodefs.available: "10%"
  imagefs.available: "15%"
evictionSoft:                   # 软驱逐（触发告警但不立即驱逐）
  memory.available: "1Gi"
  nodefs.available: "15%"
  imagefs.available: "20%"
evictionSoftGracePeriod:
  memory.available: "1m30s"
  nodefs.available: "1m30s"
containerRuntimeEndpoint: "unix:///var/run/containerd/containerd.sock"
```

**资源驱逐机制详解**：

当节点资源不足时，kubelet会按照以下优先级驱逐Pod：

驱逐顺序（从最先到最后）：
1. BestEffort Pod（未设置requests/limits）→ 内存使用量最高的先驱逐
2. Burstable Pod（requests < limits）→ 内存使用量超过requests的先驱逐
3. Guaranteed Pod（requests = limits）→ 内存使用量超过requests的先驱逐

这就是为什么生产环境必须为所有Pod设置requests和limits——不设置会导致Pod变为BestEffort级别，在资源紧张时最先被驱逐。

#### 3.3.2 kube-proxy：网络代理

kube-proxy维护节点上的网络规则，实现Service的负载均衡和流量转发。它有三种工作模式：

| 模式 | 实现方式 | 性能 | 适用场景 |
|------|---------|------|---------|
| **iptables** | 在iptables中创建DNAT规则（默认） | 中等（规则多时线性扫描） | 小中型集群，规则数 < 5000 |
| **IPVS** | 使用Linux内核的IPVS模块 | 高（O(1)哈希查找） | 大型集群，Service数量 > 1000 |
| **eBPF** | Cilium的eBPF方案 | 最高（绕过iptables/netfilter） | 高性能需求，需内核 >= 4.19 |

```bash
# 启用IPVS模式（kube-proxy启动参数）
--proxy-mode=ipvs
# kube-proxy会自动在IPVS中创建规则，无需手动配置
```

**Service到Pod的流量路径**：

客户端 → ClusterIP:Port
       → kube-proxy规则（iptables/IPVS）
       → 负载均衡选择后端Pod
       → Pod IP:Port

**iptables模式的局限性**：

- 规则线性扫描：Service越多，匹配越慢。1000个Service时，每次匹配需要扫描上千条规则
- 连接跟踪（conntrack）表有上限：大型集群可能耗尽conntrack表
- 不支持外部流量负载均衡的高级算法

**IPVS模式的优势**：

- 支持多种负载均衡算法：轮询（rr）、加权轮询（wrr）、最少连接（lc）、加权最少连接（wlc）
- O(1)哈希查找：无论Service数量多少，查找时间恒定
- 原生支持连接数限制和慢启动

#### 3.3.3 Container Runtime（容器运行时）

Kubernetes通过CRI（Container Runtime Interface）抽象容器运行时。主流选择：

| 运行时 | 特点 | 使用场景 |
|--------|------|---------|
| **containerd** | Docker开源的轻量运行时，K8s默认 | 绝大多数生产场景 |
| **CRI-O** | Red Hat维护，专注K8s的CRI实现 | OpenShift生态 |
| **gVisor (runsc)** | Google的用户态内核，强隔离 | 多租户/安全敏感场景 |
| **Kata Containers** | 轻量虚拟机运行时 | 强隔离+容器性能需求 |

```bash
# containerd配置示例（/etc/containerd/config.toml）
[plugins."io.containerd.grpc.v1.cri".containerd.runtypes.runc]
  runtime_type = "io.containerd.runc.v2"
[plugins."io.containerd.grpc.v1.cri".containerd.runtypes.gvisor]
  runtime_type = "io.containerd.runsc.v1"
```

**CRI架构**：

kubelet → gRPC调用 → CRI接口 → containerd/CRI-O → OCI运行时(runc/gVisor/Kata)
                    ↓
              镜像管理（拉取、存储）
              容器管理（创建、启动、停止）
              网络管理（CNI插件）

### 3.4 Pod生命周期深度解析

Pod是Kubernetes的**最小调度单元**——它不是容器，而是包含一个或多个容器的逻辑主机。理解Pod生命周期是掌握Kubernetes的关键。

**Pod的完整生命周期阶段**：

Pending → Running → Succeeded/Failed
              ↑
         Unknown（节点失联）

| 阶段 | 含义 | 常见原因 |
|------|------|---------|
| **Pending** | 已接受但尚未运行 | 等待调度、等待拉取镜像、等待PVC绑定 |
| **Running** | 至少一个容器在运行 | 正常工作状态 |
| **Succeeded** | 所有容器正常退出 | Job/CronJob完成 |
| **Failed** | 至少一个容器异常退出 | 应用崩溃、OOMKilled |
| **Unknown** | 无法获取Pod状态 | 节点失联（网络断开、kubelet挂掉） |

**Pod启动的详细流程**：

```mermaid
graph TD
    A["Pod创建请求"] --> B{"有initContainer?"}
    B -->|是| C["顺序执行initContainer"]
    C --> D{"initContainer全部成功?"}
    D -->|否| E["Pod保持Pending<br/>直到init成功"]
    D -->|是| F["启动mainContainer"]
    B -->|否| F
    F --> G["startupProbe<br/>(如配置)"]
    G -->|失败| H["kubelet重启容器"]
    G -->|通过| I["livenessProbe<br/>readinessProbe启动"]
    I --> J{"readinessProbe通过?"}
    J -->|是| K["加入Service Endpoints<br/>开始接收流量"]
    J -->|否| L["保持Running但<br/>不接收流量"]
```

**三种探针的职责对比**：

| 探针 | 检测失败后的动作 | 用途 | 典型配置 |
|------|----------------|------|---------|
| **livenessProbe** | 重启容器 | 检测应用是否"活着"（死锁、无限循环） | HTTP GET /healthz，每10秒 |
| **readinessProbe** | 从Service Endpoints移除 | 检测应用是否"准备好"接收流量 | HTTP GET /ready，每5秒 |
| **startupProbe** | 重启容器 | 检测慢启动应用是否完成初始化 | TCP Socket，每3秒，最多失败30次 |

**探针的工作原理**：

livenessProbe:
  失败 → 容器重启 → 重新执行startupProbe（如配置）→ 再执行livenessProbe
  用途：检测"死锁"——进程活着但不响应请求

readinessProbe:
  失败 → 从Service Endpoints移除 → 不接收新流量
  恢复 → 加回Endpoints → 重新接收流量
  用途：检测"初始化中"——Pod启动了但还没准备好（如预热缓存）

startupProbe:
  运行期间livenessProbe和readinessProbe被禁用
  通过后才启动livenessProbe和readinessProbe
  用途：检测"慢启动"——Java应用、大型数据加载

**完整的生产级Pod定义**：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-app
  labels:
    app: web
    version: v2
spec:
  # 调度约束
  nodeSelector:
    disk-type: ssd
  tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "web"
    effect: "NoSchedule"
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
            - key: app
              operator: In
              values: ["web"]
          topologyKey: kubernetes.io/hostname

  # 初始化容器（顺序执行，全部成功后才启动主容器）
  initContainers:
  - name: wait-for-db
    image: busybox:1.36
    command: ['sh', '-c', 'until nc -z postgres-service 5432; do sleep 2; done']
    resources:
      limits:
        cpu: "50m"
        memory: "32Mi"

  # 主容器
  containers:
  - name: web
    image: nginx:1.25-alpine
    ports:
    - containerPort: 8080
      name: http
      protocol: TCP
    # 资源管理（生产必须设置）
    resources:
      requests:      # 调度依据——保证获得的最低资源
        cpu: "250m"  # 0.25核
        memory: "256Mi"
      limits:        # 硬性上限——超过则OOMKilled/CPU限流
        cpu: "1000m" # 1核
        memory: "512Mi"

    # 启动探针——慢启动应用必须配置
    startupProbe:
      httpGet:
        path: /healthz
        port: 8080
      failureThreshold: 30   # 最多等30×3=90秒
      periodSeconds: 3

    # 存活探针
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      initialDelaySeconds: 0   # startupProbe通过后立即生效
      periodSeconds: 10
      timeoutSeconds: 3
      failureThreshold: 3

    # 就绪探针
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 0
      periodSeconds: 5
      timeoutSeconds: 2
      failureThreshold: 3

    # 安全上下文
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
      readOnlyRootFilesystem: true
      allowPrivilegeEscalation: false
      capabilities:
        drop: ["ALL"]

    # 生命周期钩子
    lifecycle:
      preStop:
        exec:
          command: ["/bin/sh", "-c", "sleep 15"]  # 优雅关闭，等待流量排空

    # 挂载
    volumeMounts:
    - name: nginx-config
      mountPath: /etc/nginx/conf.d
      readOnly: true
    - name: tmp
      mountPath: /tmp

  volumes:
  - name: nginx-config
    configMap:
      name: nginx-config
  - name: tmp
    emptyDir:
      sizeLimit: "100Mi"
```

**Pod资源管理机制**：

- **requests**：调度依据。Scheduler根据所有Pod的requests总和决定Node是否有足够资源
- **limits**：运行时硬限制。CPU超限被限流（throttle），内存超限被OOMKilled
- **QoS等级**：根据requests和limits的比例自动分为Guaranteed/BestEffort/Burstable三类，OOM时BestEffort最先被杀

| QoS等级 | 条件 | OOM优先级 | 典型场景 |
|---------|------|-----------|---------|
| **Guaranteed** | requests = limits（CPU和内存都设置） | 最低（最后被杀） | 核心数据库、关键服务 |
| **Burstable** | requests < limits | 中等 | Web服务、API网关 |
| **BestEffort** | 未设置requests和limits | 最高（最先被杀） | 仅开发/测试 |

**CPU限流的底层原理**：

limits.cpu = "1000m"（1核）
requests.cpu = "250m"（0.25核）

实际行为：
├── CPU请求（250m）：保证获得，不会被其他Pod抢占
├── CPU上限（1000m）：不能超过，超过会被throttle
└── CPU限流实现：Linux CGroup的CFS quota
    └── throttled周期内，进程被暂停，直到下一个周期恢复

### 3.5 Service与服务发现

Service为一组Pod提供**稳定的网络访问入口**和**负载均衡**。它屏蔽了Pod的动态变化（Pod会被创建、删除、IP会变）。

**Service的四种类型**：

```yaml
---
# 1. ClusterIP（默认）—— 集群内部访问
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  type: ClusterIP
  selector:
    app: backend
  ports:
  - port: 80           # Service端口
    targetPort: 8080    # Pod端口
    protocol: TCP

---
# 2. NodePort —— 每个节点开放固定端口
apiVersion: v1
kind: Service
metadata:
  name: backend-nodeport
spec:
  type: NodePort
  selector:
    app: backend
  ports:
  - port: 80
    targetPort: 8080
    nodePort: 30080     # 范围：30000-32767
---
# 访问方式：<任意节点IP>:30080

---
# 3. LoadBalancer —— 云厂商负载均衡器
apiVersion: v1
kind: Service
metadata:
  name: backend-lb
  annotations:
    # AWS NLB配置示例
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
spec:
  type: LoadBalancer
  selector:
    app: backend
  ports:
  - port: 80
    targetPort: 8080
---
# 自动创建云LB，外部流量通过LB IP进入

---
# 4. ExternalName —— 映射到外部DNS名称
apiVersion: v1
kind: Service
metadata:
  name: external-db
spec:
  type: ExternalName
  externalName: db.example.com  # 集群内通过external-db访问时解析为db.example.com
```

**Service类型选择决策树**：

需要集群外部访问？
├── 否 → ClusterIP（默认，最常用）
├── 是 → 直接暴露节点？
│   ├── 是 → NodePort（简单但不优雅，端口范围有限）
│   └── 否 → 有云环境？
│       ├── 是 → LoadBalancer（自动创建云LB，有成本）
│       └── 否 → Ingress Controller（推荐，见下文）

**Headless Service（无头服务）**：当`clusterIP: None`时，DNS直接返回所有后端Pod的IP列表，不进行负载均衡。适用于StatefulSet（如数据库集群）：

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql
spec:
  clusterIP: None          # 无头服务
  selector:
    app: mysql
  ports:
  - port: 3306
---
# DNS查询结果：mysql.default.svc.cluster.local
# → 10.244.1.5, 10.244.2.8, 10.244.3.12
# StatefulSet中每个Pod有固定DNS：
# mysql-0.mysql.default.svc.cluster.local → 10.244.1.5
# mysql-1.mysql.default.svc.cluster.local → 10.244.2.8
```

**CoreDNS：集群的DNS服务**：

CoreDNS是Kubernetes集群内部的DNS服务，负责将Service名称解析为ClusterIP。它运行在`kube-system`命名空间，是集群中每个Pod的DNS服务器。

DNS解析路径（Pod内部）：
app-pod → CoreDNS（10.96.0.10）→ 解析 Service名称 → 返回ClusterIP

DNS记录类型：
├── A记录：服务名 → ClusterIP
│   └── backend-service.default.svc.cluster.local → 10.96.45.123
├── SRV记录：服务名+端口 → Pod地址（Headless Service）
│   └── _mysql._tcp.mysql.default.svc.cluster.local → mysql-0.mysql...
├── PTR记录：IP → 反向解析
└── ExternalName记录：CNAME别名
    └── external-db.default.svc.cluster.local → db.example.com

**服务发现的两种方式**：

| 方式 | 原理 | 适用场景 |
|------|------|---------|
| **DNS发现** | 通过CoreDNS解析Service名称获取ClusterIP | 标准方式，适合大多数场景 |
| **环境变量** | kubelet将同命名空间的Service信息注入为环境变量 | 旧式方式，有顺序依赖问题 |

### 3.6 Ingress与流量管理

Ingress是Kubernetes中管理**HTTP/HTTPS流量入口**的资源，它通过Ingress Controller实现L7（应用层）的路由规则。Service是L4（传输层）负载均衡，而Ingress是L7（应用层）负载均衡——Ingress可以基于域名、路径、Header进行路由。

**Ingress vs Service的选择**：

| 特性 | Service (LoadBalancer) | Ingress |
|------|----------------------|---------|
| 层级 | L4（TCP/UDP） | L7（HTTP/HTTPS） |
| 路由能力 | 单一端口映射 | 基于域名/路径/Header路由 |
| TLS终止 | 不支持 | 支持（TLS Termination） |
| 成本 | 每个Service一个云LB | 一个Ingress Controller处理所有流量 |
| 适用场景 | 非HTTP协议（TCP、gRPC） | HTTP/HTTPS Web应用 |

```yaml
# 基本Ingress配置
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-ingress
  annotations:
    # NGINX Ingress Controller特定注解
    nginx.ingress.kubernetes.io/rewrite-target: /$2
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
spec:
  ingressClassName: nginx  # 指定使用的Ingress Controller
  tls:
  - hosts:
    - app.example.com
    - api.example.com
    secretName: tls-secret  # 包含TLS证书的Secret
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-backend
            port:
              number: 8080
  - host: app.example.com
    http:
      paths:
      - path: /api(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: api-backend
            port:
              number: 8080
```

**常见Ingress Controller对比**：

| Ingress Controller | 特点 | 适用场景 |
|-------------------|------|---------|
| **NGINX Ingress** | 最流行，社区版和商业版 | 通用场景，大多数生产环境 |
| **Traefik** | 自动发现服务，内置Let's Encrypt | 自动化部署，微服务 |
| **AWS ALB Ingress** | 直接创建AWS ALB | AWS环境 |
| **Istio Gateway** | 与Istio服务网格集成 | 服务网格场景 |

**pathType三种模式**：

| pathType | 行为 | 示例 |
|----------|------|------|
| `Prefix` | 按前缀匹配，`/api`匹配`/api`、`/api/v1`、`/api/users` | 大多数场景 |
| `Exact` | 精确匹配，`/api`只匹配`/api` | 需要精确控制的路径 |
| `ImplementationSpecific` | 由Ingress Controller决定匹配逻辑 | 需要正则等高级匹配 |

### 3.7 工作负载资源

Kubernetes通过不同的工作负载资源管理Pod的生命周期。选择正确的资源类型是架构设计的基础决策。

**工作负载选择决策树**：

你的应用是什么类型？
├── 无状态Web应用/API → Deployment
├── 有状态应用（数据库、消息队列）→ StatefulSet
├── 节点级基础设施（日志、监控、网络）→ DaemonSet
├── 一次性任务 → Job
├── 定时任务 → CronJob
└── 不确定 → 从Deployment开始，它是默认选择

#### 3.7.1 Deployment：无状态应用的首选

Deployment管理ReplicaSet，提供声明式更新、滚动回滚、暂停恢复等能力。它是Kubernetes中**使用频率最高**的工作负载资源。

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: production
spec:
  replicas: 3
  # 滚动更新策略
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1          # 更新时最多比期望多1个Pod
      maxUnavailable: 0    # 更新时不允许任何Pod不可用
  # 也可以使用Recreate策略（一次性停掉所有旧Pod再创建新Pod）
  # strategy:
  #   type: Recreate       # 适合不支持多版本并行的数据库等场景
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
        version: v2
    spec:
      containers:
      - name: nginx
        image: nginx:1.26
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "256Mi"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 80
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 80
          periodSeconds: 5
```

**滚动更新过程详解**（maxSurge=1, maxUnavailable=0）：

t0: [v1] [v1] [v1]              # 稳定态：3个v1 Pod
t1: [v1] [v1] [v1] [v2]         # 创建1个v2（超出1个）
t2: [v1] [v1] [v2]              # v2就绪后删除1个v1
t3: [v1] [v1] [v2] [v2]         # 再创建1个v2
t4: [v1] [v2] [v2]              # v2就绪后删除1个v1
t5: [v1] [v2] [v2] [v2]         # 再创建1个v2
t6: [v2] [v2] [v2]              # 删除最后1个v1，更新完成

**回滚机制**（生产中极其重要）：

```bash
# 查看更新历史
kubectl rollout history deployment/nginx-deployment
# REVISION  CHANGE-CAUSE
# 1         kubectl apply --filename=deployment.yaml --record
# 2         kubectl apply --filename=deployment-v2.yaml --record

# 回滚到上一个版本
kubectl rollout undo deployment/nginx-deployment

# 回滚到指定版本
kubectl rollout undo deployment/nginx-deployment --to-revision=1

# 查看回滚状态
kubectl rollout status deployment/nginx-deployment

# 暂停/恢复滚动更新（用于一次性修改多个字段）
kubectl rollout pause deployment/nginx-deployment
kubectl set image deployment/nginx-deployment nginx=nginx:1.27
kubectl set resources deployment/nginx-deployment -c=nginx --limits=cpu=2000m
kubectl rollout resume deployment/nginx-deployment
```

#### 3.7.2 StatefulSet：有状态应用

StatefulSet为有状态应用（数据库、消息队列、分布式存储）提供**稳定的网络标识**和**持久存储**：

| 特性 | Deployment | StatefulSet |
|------|-----------|-------------|
| Pod名称 | 随机后缀（nginx-7fb96c846-x2j4k） | 有序编号（nginx-0, nginx-1, nginx-2） |
| 启动顺序 | 并行启动 | 严格顺序（nginx-0 → nginx-1 → nginx-2） |
| 网络标识 | 随IP变化 | 固定DNS（nginx-0.nginx.headless-svc） |
| 存储 | Pod删除后丢失 | 每个Pod绑定独立PVC，Pod重调度后保持 |
| 扩缩容 | 任意增减 | 按编号顺序增减（先增2再增3，先减3再减2） |

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: mysql-headless    # 必须指定Headless Service
  replicas: 3
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
      - name: mysql
        image: mysql:8.0
        ports:
        - containerPort: 3306
        volumeMounts:
        - name: mysql-data
          mountPath: /var/lib/mysql
        env:
        - name: MYSQL_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mysql-secret
              key: root-password
  volumeClaimTemplates:          # 每个Pod自动创建独立PVC
  - metadata:
      name: mysql-data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 20Gi
---
# Headless Service
apiVersion: v1
kind: Service
metadata:
  name: mysql-headless
spec:
  clusterIP: None
  selector:
    app: mysql
  ports:
  - port: 3306
```

#### 3.7.3 DaemonSet：每节点一个Pod

DaemonSet确保每个（或指定）节点运行一个Pod副本，适用于**节点级基础设施服务**：

| 典型用途 | 工具 |
|---------|------|
| 日志收集 | Fluentd/Filebeat |
| 节点监控 | Node Exporter、cAdvisor |
| 网络插件 | Calico Agent、Cilium Agent |
| 存储插件 | NFS Provisioner、Ceph Agent |
| 安全扫描 | Falco Agent |

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      # 排除控制平面节点
      tolerations:
      - key: node-role.kubernetes.io/control-plane
        effect: NoSchedule
      containers:
      - name: node-exporter
        image: prom/node-exporter:v1.7.0
        ports:
        - containerPort: 9100
        resources:
          requests:
            cpu: "50m"
            memory: "64Mi"
          limits:
            cpu: "200m"
            memory: "128Mi"
        volumeMounts:
        - name: proc
          mountPath: /host/proc
          readOnly: true
        - name: sys
          mountPath: /host/sys
          readOnly: true
      volumes:
      - name: proc
        hostPath:
          path: /proc
      - name: sys
        hostPath:
          path: /sys
```

#### 3.7.4 Job与CronJob：批处理任务

```yaml
# Job —— 一次性任务
apiVersion: batch/v1
kind: Job
metadata:
  name: data-migration
spec:
  completions: 5        # 需要5次成功完成
  parallelism: 2        # 同时运行2个Pod
  backoffLimit: 3       # 失败重试3次后标记为Failed
  activeDeadlineSeconds: 3600  # 1小时后强制终止
  template:
    spec:
      containers:
      - name: migrate
        image: myapp/migrate:v1
        command: ["python", "migrate.py"]
      restartPolicy: Never  # Job必须设为Never或OnFailure

---
# CronJob —— 定时任务
apiVersion: batch/v1
kind: CronJob
metadata:
  name: database-backup
spec:
  schedule: "0 2 * * *"          # 每天凌晨2点
  concurrencyPolicy: Forbid      # 禁止并发执行
  successfulJobsHistoryLimit: 3  # 保留最近3次成功记录
  failedJobsHistoryLimit: 5      # 保留最近5次失败记录
  startingDeadlineSeconds: 300   # 错过调度时间5分钟内仍可执行
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:16
            command: ["pg_dumpall", "-U", "postgres"]
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

**CronJob的concurrencyPolicy详解**：

| 策略 | 行为 |
|------|------|
| `Allow`（默认） | 允许并发运行多个Job |
| `Forbid` | 如果上一次Job未完成，跳过本次调度 |
| `Replace` | 取消正在运行的Job，启动新的 |

### 3.8 存储子系统：PV、PVC与StorageClass

存储是Kubernetes中最复杂的子系统之一。理解PV/PVC/StorageClass的关系是管理有状态应用的关键。

**存储架构三层模型**：

开发者视角：PVC（我需要10GB SSD存储）
    ↓ 声明式请求
管理员视角：StorageClass（定义存储类型和供应方式）
    ↓ 自动创建
基础设施：PV（实际的存储资源）
    ↓ 绑定
底层存储：NFS/Ceph/EBS/GCP PD/Azure Disk

| 组件 | 角色 | 生命周期 |
|------|------|---------|
| **PV（PersistentVolume）** | 集群级存储资源，管理员创建或动态供应 | 独立于Pod存在 |
| **PVC（PersistentVolumeClaim）** | 开发者的存储申请，声明需要多少/什么类型的存储 | 绑定PV，Pod删除后保留 |
| **StorageClass** | 定义存储的"套餐"，支持动态供应PV | 集群级，管理员定义 |

**StorageClass + PVC + PV的动态供应流程**：

```yaml
# 1. StorageClass定义（管理员创建）
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs  # 或其他CSI驱动
parameters:
  type: gp3
  iopsPerGB: "50"
reclaimPolicy: Retain       # Pod删除后保留数据（Delete则自动删除）
allowVolumeExpansion: true  # 允许在线扩容
volumeBindingMode: WaitForFirstConsumer  # 延迟绑定，等Pod调度后再创建
```

```yaml
# 2. PVC申请（开发者创建）
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data
spec:
  accessModes: ["ReadWriteOnce"]  # 单节点读写
  storageClassName: fast-ssd      # 引用StorageClass
  resources:
    requests:
      storage: 50Gi
```

```yaml
# 3. Pod挂载PVC
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  containers:
  - name: app
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: app-data
```

**访问模式对比**：

| 模式 | 缩写 | 含义 | 典型场景 |
|------|------|------|---------|
| ReadWriteOnce | RWO | 单节点读写 | 数据库、单实例应用 |
| ReadOnlyMany | ROX | 多节点只读 | 静态文件、配置共享 |
| ReadWriteMany | RWX | 多节点读写 | 共享文件系统（NFS、CephFS） |
| ReadWriteOncePod | RWOP | 单Pod读写（K8s 1.27+） | 独占存储的数据库 |

**存储回收策略**：

| 策略 | 行为 |
|------|------|
| `Retain` | PVC删除后，PV保留，数据不丢失，需手动清理 |
| `Delete` | PVC删除后，PV和底层存储一起删除 |
| `Recycle`（已弃用） | 清空数据后变为Available，供新PVC绑定 |

**CSI（Container Storage Interface）**：

CSI是Kubernetes存储的标准化接口，使第三方存储厂商可以开发自己的存储驱动而不需要修改Kubernetes核心代码。

CSI架构：
kubelet → CSI Driver → 存储后端（AWS EBS、Ceph、NFS等）
        ├── Node Plugin（节点级：挂载/卸载卷）
        └── Controller Plugin（集群级：创建/删除/快照卷）

主流CSI驱动：

| CSI Driver | 存储后端 | 特点 |
|-----------|---------|------|
| **aws-ebs-csi-driver** | AWS EBS | 云原生块存储 |
| **gce-pd-csi-driver** | GCP Persistent Disk | Google云块存储 |
| **csi-driver-nfs** | NFS | 轻量共享存储 |
| **rook-ceph** | Ceph | 分布式存储，支持块/文件/对象 |

### 3.9 配置管理：ConfigMap与Secret

将配置与镜像解耦是容器化的基本原则。Kubernetes通过ConfigMap和Secret管理非敏感和敏感配置。

**创建方式对比**：

```bash
# ConfigMap创建
kubectl create configmap app-config \
  --from-literal=DB_HOST=mysql \
  --from-literal=DB_PORT=3306 \
  --from-file=config.properties \
  --from-literal=LOG_LEVEL=info

# Secret创建
kubectl create secret generic db-secret \
  --from-literal=DB_PASSWORD=SuperSecret123 \
  --from-file=ca.crt=/path/to/ca.crt

# 从YAML创建（推荐，可Git管理）
kubectl apply -f configmap.yaml
```

**挂载方式选择**：

```yaml
containers:
- name: app
  env:
  # 方式1：单个值注入为环境变量
  - name: DB_HOST
    valueFrom:
      configMapKeyRef:
        name: app-config
        key: DB_HOST

  # 方式2：整个ConfigMap的所有键值对注入为环境变量
  envFrom:
  - configMapRef:
      name: app-config
  - secretRef:
      name: db-secret

  volumeMounts:
  # 方式3：挂载为文件
  - name: config-volume
    mountPath: /etc/config
    readOnly: true
  - name: secret-volume
    mountPath: /etc/secrets
    readOnly: true

volumes:
- name: config-volume
  configMap:
    name: app-config
    items:
    - key: nginx.conf
      path: nginx.conf    # 只挂载指定的key
- name: secret-volume
  secret:
    secretName: db-secret
    defaultMode: 0400     # 文件权限：仅所有者可读
```

**配置热更新**：挂载为文件的ConfigMap/Secret修改后，kubelet会在一定延迟内（默认1分钟）更新挂载的文件。但环境变量不会更新，需要重启Pod才能生效。

**ConfigMap vs Secret的安全差异**：

| 特性 | ConfigMap | Secret |
|------|-----------|--------|
| 存储格式 | 明文 | Base64编码（注意：不是加密） |
| etcd存储 | 明文存储 | Base64存储（可配置etcd加密） |
| 适用场景 | 非敏感配置（端口、日志级别） | 敏感信息（密码、证书、密钥） |
| 审计 | 不受特别关注 | 应限制访问权限 |

**Secret的安全增强**：

```bash
# 1. 启用etcd加密（在API Server启动参数中配置）
--encryption-provider-config=/etc/kubernetes/encryption-config.yaml

# encryption-config.yaml示例
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources: ["secrets"]
    providers:
    - aescbc:
        keys:
        - name: key1
          secret: <base64-encoded-32-byte-key>
    - identity: {}  # 回退到明文（读取旧数据时需要）
```

### 3.10 自动扩缩体系

Kubernetes提供多层级的弹性能力：

| 层级 | 组件 | 扩缩对象 | 触发方式 |
|------|------|---------|---------|
| **Pod级** | HPA（Horizontal Pod Autoscaler） | Pod副本数 | CPU/内存/自定义指标 |
| **Pod级** | VPA（Vertical Pod Autoscaler） | Pod的CPU/内存request/limit | 历史资源使用分析 |
| **Pod级** | KEDA | Pod副本数 | 事件驱动（消息队列长度、Prometheus指标等） |
| **Node级** | Cluster Autoscaler | 集群节点数 | Pod因资源不足Pending |
| **Node级** | Karpenter | 集群节点数 | 按需创建最匹配的节点 |

**HPA配置示例**：

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: nginx-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nginx-deployment
  minReplicas: 2          # 最少2个Pod
  maxReplicas: 20         # 最多20个Pod
  metrics:
  # 基于CPU使用率
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # CPU使用率超过70%时扩容
  # 基于内存使用率
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  # 基于自定义指标（需要Prometheus Adapter）
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"  # 每个Pod平均QPS超过1000时扩容
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30  # 扩容稳定窗口30秒
      policies:
      - type: Pods
        value: 4             # 每次最多增加4个Pod
        periodSeconds: 60    # 在60秒内
    scaleDown:
      stabilizationWindowSeconds: 300  # 缩容稳定窗口5分钟（防止抖动）
      policies:
      - type: Percent
        value: 10            # 每次最多减少10%
        periodSeconds: 60
```

**HPA的工作原理**：

指标采集（默认30秒） → 计算期望副本数 → 执行扩缩

期望副本数 = ceil(当前副本数 × (当前指标值 / 目标指标值))

示例：当前CPU使用率85%，目标70%，当前3个Pod
期望 = ceil(3 × 85/70) = ceil(3.64) = 4个Pod

**KEDA（事件驱动扩缩）**示例：

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: queue-consumer-scaler
spec:
  scaleTargetRef:
    name: queue-consumer
  pollingInterval: 15
  cooldownPeriod: 60
  minReplicaCount: 0        # 可以缩到0（HPA不能）
  maxReplicaCount: 100
  triggers:
  - type: rabbitmq
    metadata:
      queueName: orders
      queueLength: "10"      # 每个Pod最多处理10条消息
      amqpURI: "amqp://user:***@rabbitmq.default.svc:5672"
  - type: prometheus
    metadata:
      serverAddress: "http://prometheus:9090"
      metricName: pending_messages
      query: 'sum(pending_messages{queue="orders"})'
      threshold: "50"
```

### 3.11 Namespace与资源隔离

Namespace是Kubernetes的**逻辑隔离机制**，用于多团队、多环境的资源划分：

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    env: production
    team: platform

---
# 资源配额——防止单个命名空间耗尽集群资源
apiVersion: v1
kind: ResourceQuota
metadata:
  name: prod-quota
  namespace: production
spec:
  hard:
    requests.cpu: "20"        # 最多请求20核CPU
    requests.memory: "40Gi"   # 最多请求40Gi内存
    limits.cpu: "40"          # 最多使用40核CPU
    limits.memory: "80Gi"     # 最多使用80Gi内存
    pods: "100"               # 最多100个Pod
    services: "20"            # 最多20个Service
    persistentvolumeclaims: "50"

---
# 默认资源限制——未设置request/limit的Pod自动使用
apiVersion: v1
kind: LimitRange
metadata:
  name: prod-limits
  namespace: production
spec:
  limits:
  - type: Container
    default:                  # 默认limits
      cpu: "500m"
      memory: "256Mi"
    defaultRequest:           # 默认requests
      cpu: "100m"
      memory: "128Mi"
    max:                      # 容器最大资源
      cpu: "4"
      memory: "8Gi"
    min:                      # 容器最小资源
      cpu: "50m"
      memory: "64Mi"
```

### 3.12 RBAC权限控制

RBAC（Role-Based Access Control）是Kubernetes的权限管理机制，实现**最小权限原则**：

```yaml
# Role——命名空间级权限
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: production
rules:
- apiGroups: [""]              # "" 表示核心API组
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list"]
  resourceNames: ["nginx-deployment"]  # 限定只能操作特定资源

---
# RoleBinding——将Role绑定到用户/组/ServiceAccount
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods
  namespace: production
subjects:
- kind: User
  name: dev-team
  apiGroup: rbac.authorization.k8s.io
- kind: ServiceAccount
  name: ci-bot
  namespace: ci

---
# ClusterRole——集群级权限（跨命名空间）
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cluster-reader
rules:
- apiGroups: [""]
  resources: ["nodes", "namespaces", "persistentvolumes"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["storage.k8s.io"]
  resources: ["storageclasses"]
  verbs: ["get", "list"]

---
# ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: read-cluster
subjects:
- kind: Group
  name: sre-team
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: cluster-reader
  apiGroup: rbac.authorization.k8s.io
```

**常见权限设计模式**：

| 角色 | 权限范围 | 适用对象 |
|------|---------|---------|
| **开发者** | 可读/写自己命名空间的Pod、Deployment | 开发团队 |
| **运维** | 可读所有命名空间，可写Node、Namespace | SRE团队 |
| **CI/CD** | 可读/写Deployment、可触发滚动更新 | CI/CD系统ServiceAccount |
| **审计** | 只读所有资源（包括Secret） | 安全审计系统 |

**RBAC权限拒绝排查**：

```bash
# 检查当前用户的权限
kubectl auth can-i list pods --namespace=production
kubectl auth can-i create deployments --namespace=production

# 检查某个ServiceAccount的权限
kubectl auth can-i list pods --as=system:serviceaccount:ci:ci-bot

# 生成RBAC策略（安全审计用）
kubectl auth can-i --list --as=system:serviceaccount:ci:ci-bot
```

### 3.13 网络策略（NetworkPolicy）

NetworkPolicy通过标签选择器控制Pod间、Pod与外部间的网络流量，实现**零信任网络**：

```yaml
# 默认拒绝所有入站流量（需要CNI插件支持，如Calico/Cilium）
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: production
spec:
  podSelector: {}            # 匹配命名空间内所有Pod
  policyTypes:
  - Ingress

---
# 只允许前端访问后端，只允许后端访问数据库
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend     # 只允许frontend的Pod访问
    ports:
    - port: 8080
      protocol: TCP
  - from:
    - podSelector:
        matchLabels:
          app: backend      # 后端之间可以互访
    ports:
    - port: 8080
      protocol: TCP

---
# 允许后端访问外部（默认所有Pod都可以出站，但可以用Egress策略限制）
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-egress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database     # 只能访问数据库
    ports:
    - port: 5432
      protocol: TCP
  - to:                      # 允许DNS查询
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - port: 53
      protocol: UDP
```

**NetworkPolicy的生效条件**：

- 需要CNI插件支持（Calico、Cilium、Weave Net等），默认的kubenet不支持
- 没有匹配任何NetworkPolicy的Pod默认允许所有流量
- 一旦命名空间内有任何NetworkPolicy选中了Pod，该Pod的未被允许的流量就会被拒绝

### 3.14 Pod安全标准（Pod Security Standards）

Kubernetes 1.25+引入了Pod安全标准（PSS），取代了已弃用的PodSecurityPolicy。它定义了三个安全级别：

| 安全级别 | 限制强度 | 典型场景 |
|---------|---------|---------|
| **Privileged** | 无限制（默认） | 开发环境、系统组件 |
| **Baseline** | 限制已知的特权升级 | 大多数生产工作负载 |
| **Restricted** | 最严格的安全限制 | 安全敏感型应用 |

```yaml
# 在命名空间上启用Pod安全标准
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted    # 强制执行最严格级别
    pod-security.kubernetes.io/audit: restricted       # 审计级别
    pod-security.kubernetes.io/warn: restricted        # 警告级别
```

**Baseline级别禁止的操作**：

❌ 不允许特权容器
❌ 不允许hostNetwork/hostPID/hostIPC
❌ 不允许添加Linux Capabilities（除了NET_BIND_SERVICE）
❌ 不允许以root用户运行
❌ 不允许使用hostPath卷
❌ 不允许设置SELinux/AppArmor为unconfined

**Restricted级别的额外限制**：

❌ 必须以非root运行（runAsNonRoot: true）
❌ 必须丢弃所有Capabilities（drop: ["ALL"]）
❌ 必须设置seccompProfile: RuntimeDefault
❌ 只允许特定的volume类型（configMap, emptyDir, secret, projected）
❌ 必须设置readOnlyRootFilesystem: true

**Pod安全标准检查清单**：

```yaml
# 符合Restricted级别的Pod模板
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: myapp:latest
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
    volumeMounts:
    - name: tmp
      mountPath: /tmp
  volumes:
  - name: tmp
    emptyDir: {}  # 使用允许的卷类型
```

### 3.15 核心架构设计模式总结

| 设计模式 | Kubernetes实现 | 解决的问题 |
|---------|---------------|-----------|
| **声明式管理** | 所有资源通过YAML定义期望状态 | 可审计、可版本控制、可回滚 |
| **控制循环** | Controller Manager持续调谐 | 自愈、自动修复偏差 |
| **服务发现** | Service + CoreDNS | 解耦服务消费者和提供者 |
| **滚动更新** | Deployment strategy | 零停机发布 |
| **自愈** | livenessProbe + ReplicaSet | 自动重启故障容器 |
| **弹性** | HPA + Cluster Autoscaler | 按需伸缩，控制成本 |
| **最小权限** | RBAC + NetworkPolicy + SecurityContext + PSS | 纵深防御，减小攻击面 |
| **配置分离** | ConfigMap + Secret | 镜像不变，配置可变 |
| **资源隔离** | Namespace + ResourceQuota + LimitRange | 多租户资源公平分配 |
| **存储抽象** | PV + PVC + StorageClass + CSI | 存储与计算解耦 |
| **网络抽象** | Service + Ingress + NetworkPolicy | 流量管理与安全隔离 |

**常见误区提醒**：

1. **不要在Pod中硬编码环境差异**——使用ConfigMap/Secret + 环境变量或Volume挂载
2. **必须设置resources.requests和limits**——否则一个失控的Pod可能耗尽整机资源
3. **livenessProbe不要用依赖外部服务的检查**——否则外部服务故障会导致级联重启
4. **生产环境必须配置Pod反亲和性**——否则多个同服务Pod可能被调度到同一Node，单节点故障全部不可用
5. **滚动更新时设置maxUnavailable=0**——避免更新期间服务容量下降
6. **Secret不是加密，只是Base64编码**——生产中应结合etcd加密或外部密钥管理（Vault）
7. **NetworkPolicy不是默认启用的**——需要CNI插件支持（Calico/Cilium），kubenet不支持
8. **PVC不是数据备份**——Pod删除后PVC可能保留，但PVC删除后PV的数据取决于reclaimPolicy
9. **Headless Service不是ClusterIP=None的简写**——它改变了DNS解析行为，适用于StatefulSet
10. **Pod Security Standards是命名空间级的**——不能对单个Pod设置，需要在Namespace标签上配置

---

*上一节：[Docker深度解析](/docs/engineering/第40章-容器与编排/理论基础/02-二Docker深度解析.md)*

*下一节：[关键指标与选型](/docs/engineering/第40章-容器与编排/理论基础/04-四关键指标与选型.md)*
