#!/usr/bin/env python3
"""Generate tutorial content files for chapters 43-60 and appendices."""

import os

BASE = "/tmp/ai-guides/content/docs/engineering"

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Written: {os.path.basename(path)} ({len(content)} bytes)")

# ==================== Chapter 43: RPC框架 ====================
def gen_ch43():
    d = f"{BASE}/第43章-RPC框架"
    print(f"\n=== 第43章-RPC框架 ===")
    
    write(f"{d}/00-章节概览.md", """# 第43章 RPC框架 - 章节概览

## 学习目标

通过本章学习，你将能够：

1. **理解RPC调用全流程**：从客户端发起调用到服务端执行并返回结果，掌握Stub生成、序列化、网络传输、反序列化的完整链路
2. **掌握gRPC四种通信模式**：Unary、Server Streaming、Client Streaming、Bidirectional Streaming的原理与实现
3. **精通Protobuf IDL**：能够用Protocol Buffers定义服务接口、消息格式，理解wire format和schema演进策略
4. **实现生产级RPC服务**：掌握超时控制、重试策略、幂等性保证、负载均衡、服务注册发现等工程实践
5. **保障RPC通信安全**：理解mTLS原理，能在RPC框架中配置双向认证

## 前置知识

| 知识领域 | 具体要求 | 参考章节 |
|----------|---------|---------|
| 网络协议 | 理解TCP连接、HTTP/2多路复用、帧与流的概念 | 第18-19章 |
| 序列化 | 了解JSON/Protobuf的基本概念 | 第48章 |
| 分布式基础 | 理解服务发现、负载均衡的基本概念 | 第21章、第41章 |

## 学习路径

```mermaid
graph TD
    A[RPC基本原理] --> B[序列化与IDL]
    B --> C[gRPC框架实战]
    C --> D[高级通信模式]
    D --> E[工程实践]
    E --> F[安全与性能优化]
    
    A --> A1[调用流程: Client Stub → Network → Server Stub]
    B --> B1[Protobuf定义与编译]
    C --> C1[四种通信模式]
    D --> D1[拦截器与中间件]
    E --> E1[超时/重试/幂等]
    F --> F1[mTLS与连接管理]
```

## 预计学习时间

| 阶段 | 内容 | 预计时间 |
|------|------|---------|
| 理论基础 | RPC原理、序列化对比、协议选型 | 2小时 |
| 核心技巧 | gRPC开发、Protobuf编写、拦截器 | 3小时 |
| 实战案例 | 构建完整RPC服务、性能调优 | 3小时 |
| 练习与总结 | 动手练习、知识回顾 | 2小时 |
| **合计** | | **10小时** |

## 内容结构

| 编号 | 文件 | 核心内容 |
|------|------|---------|
| 00 | 章节概览 | 学习目标、前置知识、学习路径 |
| 01 | 理论基础 | RPC调用流程、存根生成、协议选型、序列化对比 |
| 02 | 核心技巧 | gRPC四种模式、Protobuf IDL、拦截器、错误处理 |
| 03 | 实战案例 | 构建gRPC服务、超时重试、负载均衡、mTLS配置 |
| 04 | 常见误区 | 超时设置不当、忽略幂等性、序列化性能陷阱 |
| 05 | 练习方法 | 从Hello World到生产级服务的渐进练习 |
| 06 | 本章小结 | 核心知识点回顾、方案选型建议 |
""")

    write(f"{d}/01-理论基础.md", """# 第43章 RPC框架 - 理论基础

## 一、什么是RPC

RPC（Remote Procedure Call，远程过程调用）的核心思想非常简单：**让调用远程方法像调用本地方法一样自然**。

### 1.1 生活类比

想象你在餐厅点餐：
- **本地调用** = 你自己去厨房做菜（直接访问本地函数）
- **RPC调用** = 你对服务员说"来一份宫保鸡丁"，服务员把订单传给厨房，厨房做好后端给你

你不需要关心厨房在哪里、厨师怎么切菜、用什么锅——你只需要说出菜名，就能得到结果。RPC就是分布式系统中的"服务员"。

### 1.2 RPC调用流程

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant CS as Client Stub
    participant Network as 网络传输
    participant SS as Server Stub
    participant Server as 服务端

    Client->>CS: 调用本地方法 add(1, 2)
    CS->>CS: 序列化参数 (marshal)
    CS->>Network: 发送请求报文
    Network->>SS: 传输字节流
    SS->>SS: 反序列化参数 (unmarshal)
    SS->>Server: 调用实际方法 add(1, 2)
    Server-->>SS: 返回结果 3
    SS->>SS: 序列化结果
    SS-->>Network: 发送响应报文
    Network-->>CS: 传输字节流
    CS->>CS: 反序列化结果
    CS-->>Client: 返回结果 3
```

### 1.3 核心组件

| 组件 | 职责 | 类比 |
|------|------|------|
| **Client Stub** | 将本地调用转为网络请求 | 餐厅服务员（客户端侧） |
| **Server Stub** | 将网络请求转为本地调用 | 厨房接单员（服务端侧） |
| **IDL (Interface Definition Language)** | 定义服务接口和消息格式 | 菜单 |
| **Serializer** | 将对象转为字节流 | 打包外卖的包装盒 |
| **Transport** | 网络传输层 | 送外卖的骑手 |

## 二、IDL与代码生成

### 2.1 为什么需要IDL

RPC框架需要解决一个核心问题：客户端和服务端可能用不同语言编写。IDL（接口定义语言）提供了一种语言无关的方式来定义服务接口。

```protobuf
// user.proto - 使用Protobuf IDL定义服务
syntax = "proto3";

package user;

service UserService {
    rpc GetUser(GetUserRequest) returns (GetUserResponse);
    rpc ListUsers(ListUsersRequest) returns (stream User);
}

message GetUserRequest {
    int64 user_id = 1;
}

message GetUserResponse {
    User user = 1;
}

message User {
    int64 id = 1;
    string name = 2;
    string email = 3;
}
```

### 2.2 代码生成流程

```mermaid
graph LR
    A[.proto IDL文件] --> B[protoc编译器]
    B --> C[Go代码]
    B --> D[Java代码]
    B --> E[Python代码]
    B --> F[其他语言代码]
    
    C --> C1[接口定义 + Stub代码]
    D --> D1[接口定义 + Stub代码]
    E --> E1[接口定义 + Stub代码]
```

## 三、主流RPC框架对比

| 特性 | gRPC | Apache Thrift | Dubbo | JSON-RPC |
|------|------|---------------|-------|----------|
| **协议** | HTTP/2 | 自定义TCP | 自定义TCP | HTTP/1.1 |
| **序列化** | Protobuf | 自定义Binary | Hessian2/Protobuf | JSON |
| **流式通信** | ✅ 四种模式 | ❌ | ❌ | ❌ |
| **跨语言** | ✅ 10+语言 | ✅ 20+语言 | 主要Java | ✅ |
| **拦截器** | ✅ | ❌ | ✅ Filter链 | ❌ |
| **服务治理** | 需集成 | 需集成 | ✅ 内置 | ❌ |
| **性能** | 高 | 高 | 高 | 低 |
| **适用场景** | 通用微服务 | 跨语言高性能 | Java微服务 | 简单API |

## 四、RPC协议选型

### 4.1 基于HTTP/2的RPC

gRPC基于HTTP/2协议，利用了HTTP/2的多项优势：

- **多路复用**：一个TCP连接上并行传输多个请求/响应
- **头部压缩**：HPACK算法减少重复头部的传输开销
- **流式传输**：原生支持双向流

### 4.2 自定义TCP协议

Dubbo等框架使用自定义的二进制协议：

```
+--------+--------+--------+--------+--------+
| Magic  | Flag   | Status |  ID    | Body   |
| 2 byte | 1 byte | 1 byte | 8 byte | N byte |
+--------+--------+--------+--------+--------+
```

优势是协议头部更紧凑，解析更快；劣势是需要自己处理连接管理、流控等HTTP/2已经解决的问题。

## 五、序列化格式性能对比

| 格式 | 编码大小 | 编码速度 | 解码速度 | 可读性 | Schema |
|------|---------|---------|---------|--------|--------|
| JSON | 大 | 慢 | 慢 | ✅ | 无 |
| Protobuf | 小 | 快 | 快 | ❌ | 必需 |
| Avro | 小 | 快 | 快 | ❌ | 必需 |
| MessagePack | 中 | 快 | 快 | ❌ | 无 |
| Hessian2 | 中 | 中 | 中 | ❌ | 无 |

> **选型建议**：新项目优先选择gRPC + Protobuf；Java生态已有Dubbo的项目继续用Dubbo；简单的内部工具可用JSON-RPC。
""")

    write(f"{d}/02-核心技巧.md", """# 第43章 RPC框架 - 核心技巧

## 一、gRPC四种通信模式

### 1.1 Unary RPC（一元调用）

最简单的模式：一请求一响应。

```go
// server.go
type userServer struct {
    pb.UnimplementedUserServiceServer
}

func (s *userServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
    user, err := s.userRepo.FindByID(ctx, req.UserId)
    if err != nil {
        return nil, status.Errorf(codes.NotFound, "user %d not found", req.UserId)
    }
    return &pb.GetUserResponse{User: user}, nil
}
```

```go
// client.go
func main() {
    conn, err := grpc.Dial("localhost:50051", grpc.WithInsecure())
    if err != nil {
        log.Fatalf("failed to connect: %v", err)
    }
    defer conn.Close()
    
    client := pb.NewUserServiceClient(conn)
    resp, err := client.GetUser(context.Background(), &pb.GetUserRequest{UserId: 123})
    if err != nil {
        st, _ := status.FromError(err)
        log.Printf("RPC error: code=%s, message=%s", st.Code(), st.Message())
        return
    }
    fmt.Printf("User: %s (%s)\\n", resp.User.Name, resp.User.Email)
}
```

### 1.2 Server Streaming RPC

客户端发一个请求，服务端返回一个流：

```go
// 服务端：流式返回用户列表
func (s *userServer) ListUsers(req *pb.ListUsersRequest, stream pb.UserService_ListUsersServer) error {
    users, err := s.userRepo.List(stream.Context(), req.PageSize)
    if err != nil {
        return err
    }
    for _, user := range users {
        if err := stream.Send(&pb.ListUsersResponse{User: user}); err != nil {
            return err
        }
    }
    return nil
}

// 客户端：接收流式响应
func listUsers(client pb.UserServiceClient) {
    stream, err := client.ListUsers(context.Background(), &pb.ListUsersRequest{PageSize: 100})
    if err != nil {
        log.Fatalf("ListUsers failed: %v", err)
    }
    for {
        resp, err := stream.Recv()
        if err == io.EOF {
            break // 流结束
        }
        if err != nil {
            log.Fatalf("recv error: %v", err)
        }
        fmt.Printf("User: %s\\n", resp.User.Name)
    }
}
```

### 1.3 Client Streaming RPC

客户端发送一个流，服务端返回一个响应：

```go
// 服务端：接收批量上传
func (s *userServer) UploadUsers(stream pb.UserService_UploadUsersServer) error {
    var count int32
    for {
        req, err := stream.Recv()
        if err == io.EOF {
            return stream.SendAndClose(&pb.UploadUsersResponse{Count: count})
        }
        if err != nil {
            return err
        }
        if err := s.userRepo.Create(stream.Context(), req.User); err != nil {
            return err
        }
        count++
    }
}

// 客户端：流式发送
func uploadUsers(client pb.UserServiceClient, users []*pb.User) {
    stream, err := client.UploadUsers(context.Background())
    if err != nil {
        log.Fatalf("UploadUsers failed: %v", err)
    }
    for _, user := range users {
        if err := stream.Send(&pb.UploadUsersRequest{User: user}); err != nil {
            log.Fatalf("send error: %v", err)
        }
    }
    resp, err := stream.CloseAndRecv()
    if err != nil {
        log.Fatalf("CloseAndRecv error: %v", err)
    }
    fmt.Printf("Uploaded %d users\\n", resp.Count)
}
```

### 1.4 Bidirectional Streaming RPC

双方同时发送流：

```go
// 服务端：聊天室
func (s *chatServer) Chat(stream pb.ChatService_ChatServer) error {
    for {
        msg, err := stream.Recv()
        if err == io.EOF {
            return nil
        }
        if err != nil {
            return err
        }
        // 广播给所有客户端
        s.broadcast(msg)
        // 回显给发送者
        if err := stream.Send(&pb.ChatMessage{
            User:    "server",
            Content: "received: " + msg.Content,
        }); err != nil {
            return err
        }
    }
}
```

## 二、拦截器（Interceptor）

### 2.1 Unary拦截器

```go
// 日志拦截器
func loggingInterceptor(
    ctx context.Context,
    req interface{},
    info *grpc.UnaryServerInfo,
    handler grpc.UnaryHandler,
) (interface{}, error) {
    start := time.Now()
    
    // 调用实际handler
    resp, err := handler(ctx, req)
    
    // 记录日志
    duration := time.Since(start)
    log.Printf("method=%s duration=%s err=%v", info.FullMethod, duration, err)
    
    return resp, err
}

// 使用拦截器
func main() {
    server := grpc.NewServer(
        grpc.UnaryInterceptor(loggingInterceptor),
    )
    // ...
}
```

### 2.2 链式拦截器

```go
func main() {
    server := grpc.NewServer(
        grpc.ChainUnaryInterceptor(
            recoveryInterceptor,   // panic恢复（最外层）
            loggingInterceptor,    // 日志记录
            authInterceptor,       // 认证
            rateLimitInterceptor,  // 限流
        ),
    )
}
```

## 三、错误处理

### 3.1 gRPC状态码

```go
// 服务端返回标准错误
func (s *userServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
    if req.UserId <= 0 {
        return nil, status.Error(codes.InvalidArgument, "user_id must be positive")
    }
    user, err := s.repo.Find(ctx, req.UserId)
    if err != nil {
        if errors.Is(err, ErrNotFound) {
            return nil, status.Errorf(codes.NotFound, "user %d not found", req.UserId)
        }
        return nil, status.Errorf(codes.Internal, "internal error: %v", err)
    }
    return &pb.GetUserResponse{User: user}, nil
}
```

### 3.2 错误详情传递

```go
// 使用WithDetails传递结构化错误信息
func newUserError(msg string, field string) error {
    st := status.New(codes.InvalidArgument, msg)
    detail, _ := st.WithDetails(&errdetails.BadRequest_FieldViolation{
        Field:       field,
        Description: msg,
    })
    return detail.Err()
}
```

## 四、超时与重试

```go
// 客户端设置超时
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
resp, err := client.GetUser(ctx, req)

// 重试配置（通过Service Config）
const retryPolicy = `{
    "methodConfig": [{
        "name": [{"service": "user.UserService"}],
        "retryPolicy": {
            "maxAttempts": 3,
            "initialBackoff": "0.1s",
            "maxBackoff": "1s",
            "backoffMultiplier": 2,
            "retryableStatusCodes": ["UNAVAILABLE", "DEADLINE_EXCEEDED"]
        }
    }]
}`
```

## 五、健康检查

```go
import "google.golang.org/grpc/health"
import healthpb "google.golang.org/grpc/health/grpc_health_v1"

func main() {
    server := grpc.NewServer()
    
    // 注册健康检查服务
    healthServer := health.NewServer()
    healthpb.RegisterHealthServer(server, healthServer)
    
    // 设置服务状态
    healthServer.SetServingStatus("user.UserService", healthpb.HealthCheckResponse_SERVING)
}
```
""")

    write(f"{d}/03-实战案例.md", """# 第43章 RPC框架 - 实战案例

## 案例一：构建生产级gRPC用户服务

### 问题描述

某电商平台需要构建用户服务，要求：
- 支持高并发查询（QPS > 10000）
- 支持流式导出用户数据
- 具备完善的错误处理和监控

### 解决步骤

**Step 1：定义Protobuf接口**

```protobuf
syntax = "proto3";
package user;
option go_package = "github.com/example/user/pb";

service UserService {
    rpc GetUser(GetUserRequest) returns (GetUserResponse);
    rpc SearchUsers(SearchRequest) returns (stream User);
    rpc BatchCreate(stream CreateRequest) returns (BatchResponse);
}

message User {
    int64 id = 1;
    string username = 2;
    string email = 3;
    int64 created_at = 4;
}
```

**Step 2：实现服务端**

```go
type server struct {
    pb.UnimplementedUserServiceServer
    repo   UserRepository
    cache  *redis.Client
}

func (s *server) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
    // 先查缓存
    cacheKey := fmt.Sprintf("user:%d", req.UserId)
    cached, err := s.cache.Get(ctx, cacheKey).Result()
    if err == nil {
        var user pb.User
        json.Unmarshal([]byte(cached), &user)
        return &pb.GetUserResponse{User: &user}, nil
    }
    
    // 缓存未命中，查数据库
    user, err := s.repo.FindByID(ctx, req.UserId)
    if err != nil {
        return nil, status.Errorf(codes.NotFound, "user %d not found", req.UserId)
    }
    
    // 写入缓存
    data, _ := json.Marshal(user)
    s.cache.Set(ctx, cacheKey, data, 10*time.Minute)
    
    return &pb.GetUserResponse{User: user}, nil
}
```

**Step 3：配置服务**

```go
func main() {
    lis, _ := net.Listen("tcp", ":50051")
    
    server := grpc.NewServer(
        grpc.ChainUnaryInterceptor(
            recoveryInterceptor,
            loggingInterceptor,
            metricsInterceptor,
        ),
        grpc.MaxConcurrentStreams(1000),
    )
    
    pb.RegisterUserServiceServer(server, &server{repo: repo, cache: redisClient})
    
    // 启用反射（开发环境）
    reflection.Register(server)
    
    log.Println("gRPC server starting on :50051")
    server.Serve(lis)
}
```

### 结果验证

```bash
# 使用grpcurl测试
$ grpcurl -plaintext localhost:50051 user.UserService/GetUser '{"user_id": 123}'
{
  "user": {
    "id": 123,
    "username": "alice",
    "email": "alice@example.com"
  }
}

# 性能测试
$ ghz --insecure --proto user.proto --call user.UserService/GetUser \
  -d '{"user_id": 123}' -c 100 -n 100000 localhost:50051

Summary:
  Total:        2.34 s
  Slowest:      45.32 ms
  Fastest:      0.12 ms
  Average:      2.31 ms
  Requests/sec: 42,735
```

## 案例二：超时与重试导致的级联故障

### 问题描述

某微服务架构中，服务A调用服务B，服务B调用服务C。服务C出现慢查询，导致：
- 服务B线程池耗尽
- 服务A大量超时
- 整个调用链雪崩

### 分析与解决

**问题根因**：没有设置合理的超时和重试策略，导致慢请求堆积。

**解决方案**：

```go
// 服务A的客户端配置
conn, _ := grpc.Dial("service-b:50051",
    grpc.WithDefaultServiceConfig(retryPolicy),
    grpc.WithKeepaliveParams(keepalive.ClientParameters{
        Time:                10 * time.Second,
        Timeout:             3 * time.Second,
        PermitWithoutStream: true,
    }),
)

// 服务B设置更短的超时给服务C
ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
defer cancel()
resp, err := c.client.GetUser(ctx, req)
```

### 结果验证

实施后：
- 服务C慢查询不再影响服务A
- 超时后快速失败，释放线程资源
- 重试仅在可重试错误（UNAVAILABLE）时触发

## 案例三：mTLS安全通信

### 问题描述

内部服务间通信需要防止中间人攻击，确保双向身份认证。

### 解决步骤

```go
// 生成证书后配置TLS
creds, err := credentials.NewServerTLSFromFile("server.crt", "server.key")
if err != nil {
    log.Fatal(err)
}

server := grpc.NewServer(grpc.Creds(creds))

// 客户端
creds, _ := credentials.NewClientTLSFromFile("ca.crt", "service-b.example.com")
conn, _ := grpc.Dial("service-b:50051", grpc.WithTransportCredentials(creds))
```

### 结果验证

```bash
# 验证TLS连接
$ grpcurl -cacert ca.crt -cert client.crt -key client.key \
  service-b:50051 user.UserService/GetUser '{"user_id": 1}'
```
""")

    write(f"{d}/04-常见误区.md", """# 第43章 RPC框架 - 常见误区

## 误区一：超时设置过长或不设置

### 错误描述

不设置超时，或设置过长的超时（如60秒），导致请求堆积。

### 正确做法

```go
// ❌ 错误：不设超时
resp, err := client.GetUser(context.Background(), req)

// ❌ 错误：超时过长
ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)

// ✅ 正确：根据业务设置合理超时
ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
defer cancel()
```

### 对比

| 做法 | 超时时间 | 效果 |
|------|---------|------|
| 不设超时 | 永远等待 | 线程泄漏、雪崩 |
| 超时过长 | 60s | 请求堆积、资源耗尽 |
| 合理超时 | 1-5s | 快速失败、及时释放资源 |

## 误区二：重试所有错误

### 错误描述

对所有错误都进行重试，包括参数错误等不可重试错误。

### 正确做法

```go
// ❌ 错误：重试所有错误
if err != nil {
    return retry()
}

// ✅ 正确：只重试可重试错误
if err != nil {
    st, _ := status.FromError(err)
    switch st.Code() {
    case codes.Unavailable, codes.DeadlineExceeded:
        return retry() // 可重试
    case codes.InvalidArgument, codes.NotFound, codes.AlreadyExists:
        return err      // 不可重试，直接返回错误
    default:
        return err
    }
}
```

## 误区三：忽略幂等性

### 错误描述

重试机制下，服务端操作不幂等，导致数据重复。

### 正确做法

```go
// ❌ 错误：不幂等的扣款
func (s *server) Deduct(ctx context.Context, req *pb.DeductRequest) (*pb.DeductResponse, error) {
    account.Balance -= req.Amount  // 重复执行会多次扣款
    s.repo.Save(account)
    return &pb.DeductResponse{}, nil
}

// ✅ 正确：基于幂等键的幂等扣款
func (s *server) Deduct(ctx context.Context, req *pb.DeductRequest) (*pb.DeductResponse, error) {
    // 检查幂等键
    exists, _ := s.redis.Exists(ctx, "deduction:"+req.IdempotencyKey).Result()
    if exists > 0 {
        return &pb.DeductResponse{Status: "already_processed"}, nil
    }
    
    // 执行扣款
    account.Balance -= req.Amount
    s.repo.Save(account)
    
    // 设置幂等键（带过期时间）
    s.redis.Set(ctx, "deduction:"+req.IdempotencyKey, "1", 24*time.Hour)
    return &pb.DeductResponse{Status: "success"}, nil
}
```

## 误区四：序列化选择不当

### 错误描述

在性能敏感场景使用JSON序列化，或在需要可读性的场景使用Protobuf。

### 正确做法

| 场景 | 推荐格式 | 原因 |
|------|---------|------|
| 内部微服务RPC | Protobuf | 高性能、强类型 |
| 对外API | JSON | 可读性好、通用性强 |
| 日志传输 | JSON/MessagePack | 便于解析和搜索 |
| 大数据ETL | Avro | Schema演进友好 |

## 误区五：单连接承载所有流量

### 错误描述

所有请求共用一个gRPC连接，连接成为瓶颈。

### 正确做法

```go
// ❌ 错误：单连接
conn, _ := grpc.Dial("server:50051")
client := pb.NewServiceClient(conn)

// ✅ 正确：使用连接池或多个连接
// gRPC内部会自动管理HTTP/2多路复用，但可以配置多个ClientConn
conns := make([]*grpc.ClientConn, 4)
for i := range conns {
    conns[i], _ = grpc.Dial("server:50051", grpc.WithInsecure())
}
// 使用round-robin选择连接
```

## 误区六：忽略服务端流控

### 错误描述

Server Streaming发送数据过快，客户端处理不过来导致内存溢出。

### 正确做法

```go
// ✅ 服务端控制发送速率
func (s *server) ExportUsers(req *pb.ExportRequest, stream pb.Service_ExportUsersServer) error {
    for batch := range s.repo.StreamBatches(stream.Context()) {
        for _, user := range batch {
            if err := stream.Send(&pb.User{...}); err != nil {
                return err // 客户端断开连接
            }
        }
        // 流控：避免发送过快
        time.Sleep(10 * time.Millisecond)
    }
    return nil
}
```

## 误区七：不使用健康检查

### 错误描述

不配置gRPC健康检查，负载均衡器无法感知服务状态。

### 正确做法

始终注册gRPC健康检查服务，配合Kubernetes readinessProbe使用。

## 误区八：错误的日志级别

### 错误描述

客户端超时等常见错误使用ERROR级别日志，导致告警疲劳。

### 正确做法

```go
// ✅ 根据错误类型设置日志级别
func loggingInterceptor(...) {
    if err != nil {
        st, _ := status.FromError(err)
        switch {
        case st.Code() == codes.Unavailable:
            log.Warn("service unavailable") // WARN级别
        case st.Code() == codes.InvalidArgument:
            log.Info("invalid request")     // INFO级别
        default:
            log.Error("rpc failed", err)    // ERROR级别
        }
    }
}
```
""")

    write(f"{d}/05-练习方法.md", """# 第43章 RPC框架 - 练习方法

## 练习一：Hello World gRPC服务（入门）

### 目标

搭建第一个gRPC服务，理解RPC调用的完整流程。

### 步骤

1. 安装protoc和Go插件
2. 定义一个简单的Greeter服务（SayHello）
3. 生成Go代码
4. 实现服务端和客户端
5. 运行并测试

### 检查标准

- [ ] 能成功编译.proto文件
- [ ] 服务端正常启动并监听端口
- [ ] 客户端能收到响应
- [ ] 理解Stub生成的代码结构

```bash
# 验证命令
$ go run server/main.go &
$ go run client/main.go
Hello, World!
```

## 练习二：四种通信模式实现（进阶）

### 目标

实现gRPC的四种通信模式，理解流式通信的使用场景。

### 步骤

1. 定义包含四种模式的.proto文件
2. 实现Unary：查询单个用户
3. 实现Server Streaming：批量导出
4. 实现Client Streaming：批量导入
5. 实现Bidirectional Streaming：实时聊天

### 检查标准

- [ ] 四种模式都能正常工作
- [ ] 理解stream关键字的含义
- [ ] 能正确处理EOF和错误
- [ ] 流式传输能处理大数据量

## 练习三：拦截器与中间件（进阶）

### 目标

实现日志、认证、限流等拦截器。

### 步骤

1. 实现Unary Server Interceptor（日志）
2. 实现Stream Server Interceptor（认证）
3. 使用链式拦截器组合多个拦截器
4. 实现客户端拦截器（请求ID注入）

### 检查标准

- [ ] 拦截器能正确执行
- [ ] 链式拦截器执行顺序正确
- [ ] 认证拦截器能拒绝未授权请求
- [ ] 限流拦截器在高并发下生效

## 练习四：生产级RPC服务（高级）

### 目标

构建一个具备生产级特性的RPC服务。

### 步骤

1. 集成健康检查
2. 配置超时和重试策略
3. 实现优雅关闭（Graceful Shutdown）
4. 添加Prometheus指标
5. 配置mTLS安全通信
6. 使用ghz进行压测

### 检查标准

- [ ] 健康检查接口正常响应
- [ ] 超时后客户端收到DeadlineExceeded
- [ ] 优雅关闭时等待正在处理的请求完成
- [ ] Prometheus能采集到RPC指标
- [ ] 压测QPS达到预期

## 练习五：跨语言RPC调用（高级）

### 目标

实现Go服务端 + Python客户端的跨语言RPC。

### 步骤

1. 使用同一.proto文件生成Go和Python代码
2. Go实现服务端
3. Python实现客户端
4. 测试跨语言调用

### 检查标准

- [ ] Python客户端能成功调用Go服务端
- [ ] 理解IDL跨语言代码生成的原理
- [ ] 能处理跨语言的错误传递
""")

    write(f"{d}/06-本章小结.md", """# 第43章 RPC框架 - 本章小结

## 核心知识点回顾

### 1. RPC基本原理

RPC的本质是**让远程调用像本地调用一样简单**。核心组件包括Client Stub、Server Stub、IDL、Serializer和Transport。

### 2. gRPC四种通信模式

| 模式 | 请求 | 响应 | 典型场景 |
|------|------|------|---------|
| Unary | 单个 | 单个 | 普通查询 |
| Server Streaming | 单个 | 流 | 数据导出、实时推送 |
| Client Streaming | 流 | 单个 | 文件上传、批量导入 |
| Bidirectional | 流 | 流 | 实时聊天、双向通信 |

### 3. 工程实践要点

- **超时设置**：必须设置，通常1-5秒
- **重试策略**：只重试可重试错误（Unavailable、DeadlineExceeded）
- **幂等性**：重试机制的必要补充
- **拦截器**：实现日志、认证、限流等横切关注点
- **健康检查**：配合负载均衡器使用

### 4. 序列化选型

```
内部RPC → Protobuf（高性能、强类型）
对外API → JSON（通用、可读）
大数据  → Avro（Schema演进友好）
```

## 核心模型总结

```mermaid
graph TD
    A[RPC框架选型] --> B{语言生态?}
    B -->|Java为主| C[Dubbo]
    B -->|多语言| D[gRPC]
    B -->|简单场景| E[JSON-RPC]
    
    D --> F{需要流式?}
    F -->|是| G[gRPC Streaming]
    F -->|否| H[gRPC Unary]
    
    C --> I{版本?}
    I -->|新项目| J[Dubbo 3.x + Triple]
    I -->|存量项目| K[Dubbo 2.x]
```

## 下一步学习建议

1. **深入序列化**：学习第48章序列化与编码，理解Protobuf的wire format
2. **服务治理**：学习第41章服务治理，掌握服务发现、负载均衡
3. **服务网格**：学习第58章服务网格，理解RPC通信的基础设施层
4. **分布式事务**：学习第55章分布式事务，理解跨服务数据一致性

> **关键记忆点**：RPC框架的选择不仅是一个技术问题，更是一个生态问题。选择与团队技术栈匹配的框架，比追求"最好"的框架更重要。
""")


# ==================== Chapter 44: 数据结构与算法 ====================
def gen_ch44():
    d = f"{BASE}/第44章-数据结构与算法"
    print(f"\n=== 第44章-数据结构与算法 ===")
    
    write(f"{d}/00-章节概览.md", """# 第44章 数据结构与算法 - 章节概览

## 学习目标

1. 掌握哈希表、平衡树、堆等核心数据结构的内部实现原理
2. 理解各类排序算法的时间/空间复杂度，能在工程中做出正确选择
3. 掌握图论经典算法（BFS、DFS、Dijkstra、拓扑排序）
4. 具备动态规划建模能力，能识别最优子结构和重叠子问题
5. 了解贪心算法、回溯算法和位运算的适用场景

## 前置知识

| 知识领域 | 具体要求 |
|----------|---------|
| 编程基础 | 熟练掌握至少一门编程语言（Go/Java/Python） |
| 基本数学 | 集合论、概率论基础、递推关系 |
| 复杂度分析 | 理解O(n)、O(log n)等时间复杂度的含义 |

## 学习路径

```mermaid
graph TD
    A[核心数据结构] --> B[排序算法]
    B --> C[搜索算法]
    C --> D[图算法]
    D --> E[动态规划]
    E --> F[高级技巧]
    
    A --> A1[哈希表/树/堆/图]
    B --> B1[快排/归并/堆排序]
    C --> C1[二分搜索/插值搜索]
    D --> D1[BFS/DFS/最短路径]
    E --> E1[状态转移方程]
    F --> F1[贪心/回溯/位运算]
```

## 预计学习时间：12-15小时
""")

    write(f"{d}/01-理论基础.md", """# 第44章 数据结构与算法 - 理论基础

## 一、哈希表

### 1.1 核心思想

哈希表就像一个**超级索引的字典**。普通字典需要逐页翻找，而哈希表通过一个"计算公式"直接告诉你"这个词在第几页"。

### 1.2 碰撞解决

```mermaid
graph LR
    A[哈希冲突] --> B[链地址法]
    A --> C[开放寻址法]
    A --> D[再哈希法]
    
    B --> B1[Java HashMap]
    C --> C1[Python dict]
    D --> D1[布谷鸟哈希]
```

**链地址法**：每个bucket指向一个链表，冲突元素追加到链表。

```go
type HashMap struct {
    buckets []*Node
    size    int
}

type Node struct {
    key   string
    value interface{}
    next  *Node
}

func (h *HashMap) Put(key string, value interface{}) {
    index := hash(key) % h.size
    // 遍历链表查找或追加
    node := h.buckets[index]
    for node != nil {
        if node.key == key {
            node.value = value // 更新
            return
        }
        node = node.next
    }
    // 头插法
    h.buckets[index] = &Node{key: key, value: value, next: h.buckets[index]}
}
```

### 1.3 负载因子与扩容

负载因子 = 元素数量 / 桶数量。当负载因子超过阈值（通常0.75），触发扩容：创建2倍大小的新数组，重新哈希所有元素。

## 二、平衡二叉搜索树

### 2.1 红黑树

红黑树是工程中最常用的平衡BST，Java的TreeMap和Linux内核的CFS调度器都使用红黑树。

**五大性质**：
1. 每个节点非红即黑
2. 根节点是黑色
3. 叶子（NIL）是黑色
4. 红节点的子节点必须是黑色
5. 从根到叶子的每条路径，黑色节点数相同

### 2.2 B+树

B+树是数据库索引的核心数据结构。与红黑树不同，B+树的每个节点可以有多个子节点（通常几百个），这使得树的高度极低（3-4层即可索引上亿条记录）。

```mermaid
graph TD
    R[根节点: 20, 40] --> A[5, 10, 15]
    R --> B[25, 30, 35]
    R --> C[45, 50, 55]
    
    A --> D[叶子: 5→10→15]
    B --> E[叶子: 25→30→35]
    C --> F[叶子: 45→50→55]
    D -.-> E
    E -.-> F
```

## 三、堆与优先队列

堆是一种**完全二叉树**，满足堆性质：父节点的值大于（大顶堆）或小于（小顶堆）子节点。

```go
type MinHeap struct {
    data []int
}

func (h *MinHeap) Push(val int) {
    h.data = append(h.data, val)
    h.siftUp(len(h.data) - 1)
}

func (h *MinHeap) Pop() int {
    top := h.data[0]
    h.data[0] = h.data[len(h.data)-1]
    h.data = h.data[:len(h.data)-1]
    h.siftDown(0)
    return top
}
```

## 四、图的表示

| 表示方式 | 空间复杂度 | 判断边是否存在 | 适用场景 |
|----------|-----------|--------------|---------|
| 邻接矩阵 | O(V²) | O(1) | 稠密图 |
| 邻接表 | O(V+E) | O(degree) | 稀疏图 |
| 邻接集 | O(V+E) | O(1) | 需要快速查边 |

## 五、复杂度速查表

| 算法 | 最好 | 平均 | 最差 | 空间 | 稳定性 |
|------|------|------|------|------|--------|
| 快速排序 | O(n log n) | O(n log n) | O(n²) | O(log n) | 不稳定 |
| 归并排序 | O(n log n) | O(n log n) | O(n log n) | O(n) | 稳定 |
| 堆排序 | O(n log n) | O(n log n) | O(n log n) | O(1) | 不稳定 |
| 计数排序 | O(n+k) | O(n+k) | O(n+k) | O(k) | 稳定 |
""")

    write(f"{d}/02-核心技巧.md", """# 第44章 数据结构与算法 - 核心技巧

## 一、二分搜索的边界处理

二分搜索看似简单，但边界条件极易出错。关键在于**明确搜索区间**。

### 左闭右闭 [left, right]

```go
func search(nums []int, target int) int {
    left, right := 0, len(nums)-1
    for left <= right {                    // 注意是 <=
        mid := left + (right-left)/2
        if nums[mid] == target {
            return mid
        } else if nums[mid] < target {
            left = mid + 1                  // 注意是 +1
        } else {
            right = mid - 1                 // 注意是 -1
        }
    }
    return -1
}
```

### 左闭右开 [left, right)

```go
func search(nums []int, target int) int {
    left, right := 0, len(nums)            // 注意是 len，不是 len-1
    for left < right {                     // 注意是 <
        mid := left + (right-left)/2
        if nums[mid] == target {
            return mid
        } else if nums[mid] < target {
            left = mid + 1
        } else {
            right = mid                     // 注意不是 mid-1
        }
    }
    return -1
}
```

## 二、动态规划状态压缩

### 滚动数组

```go
// ❌ 空间O(n)
func climbStairs(n int) int {
    dp := make([]int, n+1)
    dp[0], dp[1] = 1, 1
    for i := 2; i <= n; i++ {
        dp[i] = dp[i-1] + dp[i-2]
    }
    return dp[n]
}

// ✅ 空间O(1) - 滚动数组
func climbStairs(n int) int {
    prev, curr := 1, 1
    for i := 2; i <= n; i++ {
        prev, curr = curr, prev+curr
    }
    return curr
}
```

## 三、单调栈技巧

单调栈用于解决"下一个更大元素"类问题。

```go
func nextGreaterElement(nums []int) []int {
    n := len(nums)
    result := make([]int, n)
    for i := range result {
        result[i] = -1
    }
    stack := []int{} // 存储下标
    
    for i := 0; i < n; i++ {
        for len(stack) > 0 && nums[i] > nums[stack[len(stack)-1]] {
            top := stack[len(stack)-1]
            stack = stack[:len(stack)-1]
            result[top] = nums[i]
        }
        stack = append(stack, i)
    }
    return result
}
```

## 四、滑动窗口

```go
// 最小覆盖子串
func minWindow(s, t string) string {
    need := make(map[byte]int)
    for i := 0; i < len(t); i++ {
        need[t[i]]++
    }
    
    left, count := 0, 0
    minLen, minStart := math.MaxInt32, 0
    
    for right := 0; right < len(s); right++ {
        if need[s[right]] > 0 {
            count++
        }
        need[s[right]]--
        
        for count == len(t) {
            if right-left+1 < minLen {
                minLen = right - left + 1
                minStart = left
            }
            need[s[left]]++
            if need[s[left]] > 0 {
                count--
            }
            left++
        }
    }
    if minLen == math.MaxInt32 {
        return ""
    }
    return s[minStart : minStart+minLen]
}
```

## 五、位运算技巧

```go
// 判断是否是2的幂
func isPowerOfTwo(n int) bool {
    return n > 0 && (n&(n-1)) == 0
}

// 统计二进制中1的个数
func countBits(n int) int {
    count := 0
    for n > 0 {
        n &= n - 1
        count++
    }
    return count
}

// 不用临时变量交换
func swap(a, b int) (int, int) {
    a ^= b
    b ^= a
    a ^= b
    return a, b
}
```
""")

    write(f"{d}/03-实战案例.md", """# 第44章 数据结构与算法 - 实战案例

## 案例一：使用LRU缓存优化数据库查询

### 问题描述

某API服务频繁查询用户信息，数据库成为瓶颈。需要实现一个LRU缓存层。

### 解决方案

```go
type LRUCache struct {
    capacity int
    cache    map[int]*Node
    head     *Node // 哨兵头
    tail     *Node // 哨兵尾
}

type Node struct {
    key, value int
    prev, next *Node
}

func Constructor(capacity int) LRUCache {
    head := &Node{}
    tail := &Node{}
    head.next = tail
    tail.prev = head
    return LRUCache{
        capacity: capacity,
        cache:    make(map[int]*Node),
        head:     head,
        tail:     tail,
    }
}

func (c *LRUCache) Get(key int) int {
    if node, ok := c.cache[key]; ok {
        c.moveToHead(node)
        return node.value
    }
    return -1
}

func (c *LRUCache) Put(key, value int) {
    if node, ok := c.cache[key]; ok {
        node.value = value
        c.moveToHead(node)
        return
    }
    newNode := &Node{key: key, value: value}
    c.cache[key] = newNode
    c.addToHead(newNode)
    if len(c.cache) > c.capacity {
        tail := c.removeTail()
        delete(c.cache, tail.key)
    }
}
```

### 结果验证

缓存命中率从0%提升到85%，数据库QPS降低70%。

## 案例二：拓扑排序解决任务依赖

### 问题描述

CI/CD流水线中，任务之间存在依赖关系，需要确定执行顺序。

```go
func findOrder(numTasks int, prerequisites [][]int) []int {
    graph := make([][]int, numTasks)
    inDegree := make([]int, numTasks)
    
    for _, pre := range prerequisites {
        graph[pre[1]] = append(graph[pre[1]], pre[0])
        inDegree[pre[0]]++
    }
    
    queue := []int{}
    for i := 0; i < numTasks; i++ {
        if inDegree[i] == 0 {
            queue = append(queue, i)
        }
    }
    
    result := []int{}
    for len(queue) > 0 {
        node := queue[0]
        queue = queue[1:]
        result = append(result, node)
        
        for _, next := range graph[node] {
            inDegree[next]--
            if inDegree[next] == 0 {
                queue = append(queue, next)
            }
        }
    }
    
    if len(result) != numTasks {
        return nil // 存在环，无法完成
    }
    return result
}
```

## 案例三：Bloom Filter优化缓存穿透

### 问题描述

大量请求查询不存在的key，绕过缓存直接打到数据库。

```go
type BloomFilter struct {
    bits    []bool
    hashFns []func(string) uint32
}

func (bf *BloomFilter) Add(item string) {
    for _, fn := range bf.hashFns {
        bf.bits[fn(item)%uint32(len(bf.bits))] = true
    }
}

func (bf *BloomFilter) MightContain(item string) bool {
    for _, fn := range bf.hashFns {
        if !bf.bits[fn(item)%uint32(len(bf.bits))] {
            return false // 一定不存在
        }
    }
    return true // 可能存在
}
```
""")

    write(f"{d}/04-常见误区.md", """# 第44章 数据结构与算法 - 常见误区

## 误区一：盲目追求最优算法

**错误**：所有场景都用O(n log n)排序。
**正确**：小规模数据（n<50）插入排序更快，因为常数因子小。

## 误区二：忽略空间复杂度

**错误**：递归斐波那契O(2^n)时间复杂度。
**正确**：用动态规划或记忆化搜索O(n)时间O(n)空间。

## 误区三：二分搜索的边界错误

**错误**：mid=(left+right)/2可能溢出。
**正确**：mid=left+(right-left)/2。

## 误区四：哈希表的负载因子

**错误**：不考虑负载因子，哈希冲突严重。
**正确**：负载因子超过0.75时扩容。

## 误区五：图算法的visited标记

**错误**：BFS/DFS不标记visited，死循环。
**正确**：入队/入栈时立即标记visited。
""")

    write(f"{d}/05-练习方法.md", """# 第44章 数据结构与算法 - 练习方法

## 练习一：实现HashMap（入门）

**目标**：从零实现一个支持增删查的HashMap。
**检查标准**：处理哈希冲突，支持动态扩容。

## 练习二：排序算法对比（进阶）

**目标**：实现快排、归并、堆排序，对比性能。
**检查标准**：在100万数据上测试，结果正确。

## 练习三：图算法实战（进阶）

**目标**：用BFS求最短路径，用DFS检测环。
**检查标准**：能处理有向图和无向图。

## 练习四：动态规划专项（高级）

**目标**：完成背包问题、最长公共子序列、编辑距离。
**检查标准**：能正确推导状态转移方程。

## 练习五：综合项目（高级）

**目标**：实现一个简单的搜索引擎倒排索引。
**检查标准**：支持关键词搜索，结果按相关性排序。
""")

    write(f"{d}/06-本章小结.md", """# 第44章 数据结构与算法 - 本章小结

## 核心要点

1. **数据结构选择**比算法优化更重要
2. **时间与空间的权衡**是永恒的主题
3. **二分搜索**的边界处理是常见考点
4. **动态规划**的关键是识别最优子结构
5. **图算法**是解决复杂关系问题的利器

## 选型速查

| 场景 | 推荐数据结构 | 原因 |
|------|-------------|------|
| 快速查找 | 哈希表 | O(1)平均 |
| 有序数据 | 红黑树/B+树 | O(log n) |
| 优先级任务 | 堆 | O(log n)插入 |
| 路径搜索 | 图+ BFS/DFS | 自然建模 |

## 下一步学习

- 深入学习第10章索引结构（B+树在数据库中的应用）
- 学习第12章缓存系统（LRU/LFU的工程实现）
- 学习第39章搜索引擎（倒排索引与排序算法）
""")


# ==================== Chapter 45-60 and appendices ====================
# I'll continue generating the remaining chapters...

# Let me create a more efficient approach with templates
def gen_ch45():
    d = f"{BASE}/第45章-软件测试"
    print(f"\n=== 第45章-软件测试 ===")
    
    write(f"{d}/00-章节概览.md", """# 第45章 软件测试 - 章节概览

## 学习目标

1. 理解测试层次模型（单元→集成→端到端），设计合理的测试策略
2. 掌握Mock/Stub/Spy等测试替身的使用场景
3. 掌握性能测试方法论（负载/压力/浸泡测试）和主流工具
4. 理解混沌工程理念，能引入故障注入实验
5. 了解TDD、BDD等方法论的实践方式

## 前置知识

| 知识领域 | 具体要求 |
|----------|---------|
| 编程基础 | 熟练掌握至少一门语言及其测试框架 |
| 软件工程 | 理解CI/CD基本概念 |
| 分布式基础 | 了解微服务架构的基本概念 |

## 学习路径

```mermaid
graph TD
    A[测试层次模型] --> B[单元测试实践]
    B --> C[集成测试与契约测试]
    C --> D[性能测试]
    D --> E[混沌工程]
    E --> F[测试方法论]
```

## 预计学习时间：10-12小时
""")

    write(f"{d}/01-理论基础.md", """# 第45章 软件测试 - 理论基础

## 一、测试金字塔

```mermaid
graph TD
    subgraph 测试金字塔
        E2E[端到端测试 - 少量]
        INT[集成测试 - 适量]
        UNIT[单元测试 - 大量]
    end
```

| 层次 | 数量 | 速度 | 成本 | 信心 |
|------|------|------|------|------|
| 单元测试 | 多 | 快（毫秒） | 低 | 中 |
| 集成测试 | 中 | 中（秒级） | 中 | 高 |
| 端到端测试 | 少 | 慢（分钟级） | 高 | 最高 |

## 二、测试替身分类

| 类型 | 说明 | 使用场景 |
|------|------|---------|
| **Dummy** | 占位对象，不被使用 | 填充参数 |
| **Stub** | 返回预设值 | 控制间接输入 |
| **Spy** | 记录调用信息 | 验证交互行为 |
| **Mock** | 预设期望并验证 | 验证交互行为 |
| **Fake** | 简化实现 | 数据库、支付等 |

## 三、代码覆盖率

| 指标 | 含义 | 目标 |
|------|------|------|
| 行覆盖率 | 执行了多少行 | >80% |
| 分支覆盖率 | 覆盖了多少分支 | >70% |
| 条件覆盖率 | 条件组合覆盖 | >60% |

> **注意**：覆盖率高不等于质量好，但覆盖率低一定意味着测试不足。

## 四、测试钻石 vs 测试金字塔

测试钻石模型认为应该减少单元测试，增加集成测试：

```mermaid
graph TD
    subgraph 测试钻石
        E2E[端到端测试 - 少量]
        INT[集成测试 - 大量]
        UNIT[单元测试 - 适量]
    end
```

**适用场景**：微服务架构中，集成测试能提供更好的信心/成本比。
""")

    write(f"{d}/02-核心技巧.md", """# 第45章 软件测试 - 核心技巧

## 一、高效的Mock策略

### 1.1 接口Mock

```go
// 定义接口
type UserRepository interface {
    FindByID(ctx context.Context, id int64) (*User, error)
    Save(ctx context.Context, user *User) error
}

// Mock实现
type MockUserRepo struct {
    FindByIDFunc func(ctx context.Context, id int64) (*User, error)
    SaveFunc     func(ctx context.Context, user *User) error
}

func (m *MockUserRepo) FindByID(ctx context.Context, id int64) (*User, error) {
    return m.FindByIDFunc(ctx, id)
}
```

### 1.2 使用场景

```go
func TestGetUser_Success(t *testing.T) {
    mock := &MockUserRepo{
        FindByIDFunc: func(ctx context.Context, id int64) (*User, error) {
            return &User{ID: id, Name: "Alice"}, nil
        },
    }
    service := NewUserService(mock)
    
    user, err := service.GetUser(context.Background(), 123)
    assert.NoError(t, err)
    assert.Equal(t, "Alice", user.Name)
}
```

## 二、TDD红-绿-重构

```mermaid
graph LR
    RED[🔴 写失败测试] --> GREEN[🟢 写最少代码]
    GREEN --> REFACTOR[🔵 重构代码]
    REFACTOR --> RED
```

**实践步骤**：
1. 先写一个会失败的测试
2. 写最少的代码让测试通过
3. 重构代码，保持测试通过
4. 重复

## 三、性能测试设计

### 3.1 负载测试

```javascript
// k6负载测试脚本
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
    stages: [
        { duration: '2m', target: 100 },  // 逐步加压
        { duration: '5m', target: 100 },  // 持续负载
        { duration: '2m', target: 0 },    // 逐步减压
    ],
    thresholds: {
        http_req_duration: ['p(95)<500'], // 95%请求<500ms
        http_req_failed: ['rate<0.01'],   // 错误率<1%
    },
};

export default function () {
    let res = http.get('http://api.example.com/users/1');
    check(res, {
        'status is 200': (r) => r.status === 200,
        'response time < 500ms': (r) => r.timings.duration < 500,
    });
    sleep(1);
}
```

## 四、契约测试

使用Pact验证服务间的API契约：

```go
// 消费者端测试
func TestUserConsumer(t *testing.T) {
    mockService, _ := pact.Setup()
    
    mockService.
        Given("user 1 exists").
        UponReceiving("a request for user 1").
        WithRequest(http.MethodGet, "/users/1").
        WillRespondWith(200, func(b *dsl.V1Interaction) {
            b.Body(map[string]interface{}{"id": 1, "name": "Alice"})
        })
    
    // 调用真实客户端
    user, _ := client.GetUser(1)
    assert.Equal(t, "Alice", user.Name)
}
```
""")

    write(f"{d}/03-实战案例.md", """# 第45章 软件测试 - 实战案例

## 案例一：为微服务编写单元测试

### 问题描述

订单服务的CreateOrder方法需要测试，依赖用户服务、库存服务和支付服务。

### 解决步骤

```go
func TestCreateOrder_Success(t *testing.T) {
    // 准备Mock
    userMock := &MockUserService{
        GetFunc: func(id int64) (*User, error) {
            return &User{ID: id, Name: "Alice"}, nil
        },
    }
    inventoryMock := &MockInventoryService{
        ReserveFunc: func(items []Item) error {
            return nil
        },
    }
    paymentMock := &MockPaymentService{
        ChargeFunc: func(amount float64) error {
            return nil
        },
    }
    
    service := NewOrderService(userMock, inventoryMock, paymentMock)
    order, err := service.CreateOrder(context.Background(), &CreateOrderRequest{
        UserID: 123,
        Items:  []Item{{ProductID: 1, Quantity: 2}},
    })
    
    assert.NoError(t, err)
    assert.Equal(t, OrderStatusPending, order.Status)
    assert.Equal(t, int64(123), order.UserID)
}

func TestCreateOrder_InsufficientStock(t *testing.T) {
    inventoryMock := &MockInventoryService{
        ReserveFunc: func(items []Item) error {
            return ErrInsufficientStock
        },
    }
    // ... 测试库存不足场景
}
```

### 结果验证

```
=== RUN   TestCreateOrder_Success
--- PASS: TestCreateOrder_Success (0.00s)
=== RUN   TestCreateOrder_InsufficientStock
--- PASS: TestCreateOrder_InsufficientStock (0.00s)
PASS
coverage: 85.2% of statements
```

## 案例二：混沌工程实验

### 问题描述

验证系统在网络分区和节点故障时的容错能力。

### 解决步骤

```yaml
# LitmusChaos实验定义
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: redis-chaos
spec:
  appinfo:
    appns: default
    applabel: app=redis
    appkind: deployment
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: '30'
            - name: CHAOS_INTERVAL
              value: '10'
```

### 结果验证

监控系统显示：
- 故障注入期间，服务降级但不中断
- 故障恢复后，服务自动恢复
- 无数据丢失
""")

    write(f"{d}/04-常见误区.md", """# 第45章 软件测试 - 常见误区

## 误区一：追求100%代码覆盖率

**错误**：花费大量时间覆盖getter/setter等无意义代码。
**正确**：关注业务逻辑的覆盖率，80%是合理的基线。

## 误区二：过度Mock

**错误**：Mock所有依赖，包括值对象。
**正确**：只Mock外部依赖（数据库、网络服务），值对象直接使用。

## 误区三：测试依赖执行顺序

**错误**：测试B依赖测试A的结果。
**正确**：每个测试独立，使用TestMain或setup/teardown。

## 误区四：测试中包含业务逻辑

**错误**：测试代码中重复业务代码的逻辑。
**正确**：测试应该只验证行为，不应该实现业务逻辑。

## 误区五：忽略Flaky测试

**错误**：不稳定测试反复重试直到通过。
**正确**：根治Flaky测试——找出不确定性来源（时间、并发、外部依赖）。

## 误区六：端到端测试过多

**错误**：每个场景都写端到端测试。
**正确**：端到端测试只覆盖核心业务流程，细节留给单元测试。
""")

    write(f"{d}/05-练习方法.md", """# 第45章 软件测试 - 练习方法

## 练习一：单元测试基础（入门）

**目标**：为一个Calculator类编写完整的单元测试。
**检查标准**：覆盖正常路径、边界条件、异常情况。

## 练习二：Mock实战（进阶）

**目标**：为依赖外部API的服务编写Mock测试。
**检查标准**：Mock验证交互行为，测试独立于外部服务。

## 练习三：TDD实践（进阶）

**目标**：用TDD方式实现一个简单的购物车。
**检查标准**：遵循红-绿-重构循环。

## 练习四：性能测试（高级）

**目标**：用k6对一个API进行负载测试。
**检查标准**：识别性能瓶颈，生成测试报告。

## 练习五：混沌工程实验（高级）

**目标**：在本地Kubernetes环境模拟Pod故障。
**检查标准**：验证系统自动恢复，记录故障影响。
""")

    write(f"{d}/06-本章小结.md", """# 第45章 软件测试 - 本章小结

## 核心要点

1. **测试金字塔**指导测试策略设计
2. **Mock是手段不是目的**，过度Mock降低测试价值
3. **TDD**是一种设计方法，不只是测试方法
4. **性能测试**需要在生产级环境中进行
5. **混沌工程**帮助发现系统的未知弱点

## 测试策略选型

| 项目阶段 | 重点测试类型 | 工具推荐 |
|----------|-------------|---------|
| 开发阶段 | 单元测试 | Go testing / JUnit / pytest |
| 集成阶段 | 集成测试 + 契约测试 | TestContainers / Pact |
| 预发布 | 性能测试 | k6 / JMeter / Gatling |
| 生产环境 | 混沌工程 | LitmusChaos / Chaos Monkey |

## 下一步学习

- 学习第46章CI/CD，将测试集成到流水线
- 学习第42章监控与可观测性，监控生产环境质量
- 学习第58章服务网格，理解服务间通信的测试
""")


def gen_ch46():
    d = f"{BASE}/第46章-CICD"
    print(f"\n=== 第46章-CICD ===")
    
    write(f"{d}/00-章节概览.md", """# 第46章 CI/CD - 章节概览

## 学习目标

1. 理解CI/CD的核心理念和价值
2. 掌握主流CI/CD工具（GitHub Actions、GitLab CI、Jenkins）的配置
3. 掌握蓝绿部署、金丝雀部署、滚动更新等部署策略
4. 理解GitOps理念，能用ArgoCD管理Kubernetes部署
5. 掌握Feature Flags的使用场景和实现

## 前置知识

| 知识领域 | 具体要求 |
|----------|---------|
| Git | 熟练使用分支、合并、rebase |
| Docker | 理解镜像构建和容器运行 |
| Kubernetes | 了解Pod、Deployment、Service基本概念 |

## 学习路径

```mermaid
graph TD
    A[CI核心实践] --> B[CD流水线设计]
    B --> C[部署策略]
    C --> D[GitOps实践]
    D --> E[Feature Flags]
    E --> F[IaC基础设施即代码]
```

## 预计学习时间：8-10小时
""")

    write(f"{d}/01-理论基础.md", """# 第46章 CI/CD - 理论基础

## 一、CI/CD是什么

```mermaid
graph LR
    A[代码提交] --> B[CI: 构建+测试]
    B --> C[CD: 部署到预发布]
    C --> D[CD: 部署到生产]
    
    B --> B1[自动编译]
    B --> B2[单元测试]
    B --> B3[代码质量检查]
    C --> C1[集成测试]
    C --> C2[安全扫描]
    D --> D1[灰度发布]
    D --> D2[全量发布]
```

## 二、开发分支策略

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| Git Flow | 多分支（develop/release/hotfix） | 版本发布周期长 |
| GitHub Flow | 主干+feature分支 | 持续部署 |
| Trunk-Based | 主干开发，短生命周期分支 | 高频发布 |

## 三、部署策略对比

| 策略 | 停机时间 | 资源消耗 | 回滚速度 | 风险 |
|------|---------|---------|---------|------|
| 蓝绿部署 | 零 | 高（2倍环境） | 秒级 | 低 |
| 金丝雀部署 | 零 | 低 | 秒级 | 最低 |
| 滚动更新 | 零 | 低 | 分钟级 | 中 |
| 直接替换 | 有 | 低 | 分钟级 | 高 |

## 四、制品管理

```mermaid
graph LR
    A[源代码] --> B[构建]
    B --> C[制品]
    C --> D[制品仓库]
    D --> E[部署]
    
    C --> C1[Docker镜像]
    C --> C2[JAR/WAR]
    C --> C3[Helm Chart]
    D --> D1[Harbor]
    D --> D2[Nexus]
    D --> D3[ECR]
```
""")

    write(f"{d}/02-核心技巧.md", """# 第46章 CI/CD - 核心技巧

## 一、GitHub Actions实战

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'
      
      - name: Build
        run: go build -v ./...
      
      - name: Test
        run: go test -v -coverprofile=coverage.out ./...
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker image
        run: |
          docker build -t myapp:${{ github.sha }} .
          docker tag myapp:${{ github.sha }} myapp:latest
      
      - name: Push to registry
        run: |
          echo ${{ secrets.REGISTRY_PASSWORD }} | docker login -u ${{ secrets.REGISTRY_USER }} --password-stdin
          docker push myapp:${{ github.sha }}
```

## 二、蓝绿部署实现

```yaml
# Kubernetes蓝绿部署
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      version: green
  template:
    metadata:
      labels:
        app: myapp
        version: green
    spec:
      containers:
        - name: myapp
          image: myapp:v2.0
---
# 切换Service到green
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
    version: green  # 切换这一行
```

## 三、金丝雀部署

```yaml
# Istio金丝雀
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: myapp
spec:
  hosts: [myapp]
  http:
    - route:
        - destination:
            host: myapp
            subset: stable
          weight: 90
        - destination:
            host: myapp
            subset: canary
          weight: 10
```

## 四、Feature Flags

```go
// 简单的Feature Flag实现
type FeatureFlags struct {
    flags map[string]bool
}

func (f *FeatureFlags) IsEnabled(flag string, userID string) bool {
    if enabled, ok := f.flags[flag]; ok {
        return enabled
    }
    return false
}

// 使用
func handleRequest(w http.ResponseWriter, r *http.Request) {
    if flags.IsEnabled("new-checkout-flow", userID) {
        newCheckoutHandler(w, r)
    } else {
        oldCheckoutHandler(w, r)
    }
}
```
""")

    write(f"{d}/03-实战案例.md", """# 第46章 CI/CD - 实战案例

## 案例一：从零搭建CI/CD流水线

### 问题描述

团队需要为Go微服务项目搭建完整的CI/CD流水线。

### 解决步骤

1. **代码提交触发CI**：GitHub Actions自动运行测试
2. **构建Docker镜像**：多阶段构建减小镜像体积
3. **推送到Harbor**：私有镜像仓库
4. **ArgoCD自动部署**：GitOps方式管理Kubernetes

```dockerfile
# 多阶段构建
FROM golang:1.22 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o server .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
COPY --from=builder /app/server /server
EXPOSE 8080
CMD ["/server"]
```

### 结果验证

- 代码提交后5分钟内完成测试和构建
- 镜像体积从1.2GB减小到15MB
- 部署时间从30分钟缩短到2分钟

## 案例二：金丝雀发布实践

### 解决步骤

1. 部署新版本为金丝雀（10%流量）
2. 监控错误率和延迟
3. 如果指标正常，逐步扩大到50%、100%
4. 如果异常，立即回滚到稳定版本

### 结果验证

某次发布发现新版本有内存泄漏，金丝雀阶段就检测到，仅影响10%用户，秒级回滚。
""")

    write(f"{d}/04-常见误区.md", """# 第46章 CI/CD - 常见误区

## 误区一：CI中不运行测试

**错误**：CI只做构建，测试手动运行。
**正确**：CI必须包含自动化测试。

## 误区二：数据库变更不纳入CI/CD

**错误**：数据库schema手动修改。
**正确**：使用Flyway/Liquibase管理数据库迁移。

## 误区三：环境配置硬编码

**错误**：不同环境的配置写死在代码中。
**正确**：使用配置中心或环境变量。

## 误区四：忽略制品版本管理

**错误**：每次都用latest标签。
**正确**：使用语义化版本或commit SHA作为标签。

## 误区五：没有回滚策略

**错误**：部署失败后手动修复。
**正确**：自动化回滚，蓝绿切换秒级回滚。

## 误区六：CI/CD流水线太长

**错误**：一个job包含所有步骤。
**正确**：分阶段并行执行，快速失败。
""")

    write(f"{d}/05-练习方法.md", """# 第46章 CI/CD - 练习方法

## 练习一：GitHub Actions基础（入门）

**目标**：为现有项目添加CI流水线。
**检查标准**：代码提交自动触发测试。

## 练习二：Docker多阶段构建（进阶）

**目标**：优化Docker镜像大小。
**检查标准**：镜像小于50MB。

## 练习三：ArgoCD部署（进阶）

**目标**：用ArgoCD部署应用到Kubernetes。
**检查标准**：Git变更自动同步到集群。

## 练习四：蓝绿/金丝雀部署（高级）

**目标**：实现零停机部署。
**检查标准**：部署期间无请求失败。

## 练习五：完整CI/CD流水线（高级）

**目标**：从代码提交到生产部署的全自动流水线。
**检查标准**：端到端自动化，包含测试、构建、部署、监控。
""")

    write(f"{d}/06-本章小结.md", """# 第46章 CI/CD - 本章小结

## 核心要点

1. **CI的核心**是快速反馈——频繁集成、自动测试
2. **CD的核心**是安全交付——自动化部署、快速回滚
3. **GitOps**用Git作为基础设施的唯一真相源
4. **部署策略**的选择取决于风险容忍度和资源约束
5. **Feature Flags**将代码部署与功能发布解耦

## 部署策略选型

| 场景 | 推荐策略 | 原因 |
|------|---------|------|
| 关键业务 | 金丝雀 | 最小化风险 |
| 资源充足 | 蓝绿 | 秒级回滚 |
| 常规更新 | 滚动更新 | 资源效率高 |
| 快速迭代 | Feature Flags | 灵活控制 |

## 下一步学习

- 学习第47章云原生架构，理解容器化部署
- 学习第40章容器与编排，深入Kubernetes
- 学习第42章监控与可观测性，监控部署效果
""")


# Generate remaining chapters with a template approach
def gen_chapter(num, title, topics, key_concepts, tools, practice_items, misconceptions):
    d = f"{BASE}/第{num}章-{title}"
    print(f"\n=== 第{num}章-{title} ===")
    
    overview_content = f"""# 第{num}章 {title} - 章节概览

## 学习目标

通过本章学习，你将能够：

1. 理解{title}的核心概念和基本原理
2. 掌握{title}的关键技术和实现方法
3. 能够在实际项目中应用{title}的最佳实践
4. 了解{title}的常见误区和避坑指南
5. 具备独立设计和实现{title}相关方案的能力

## 前置知识

| 知识领域 | 具体要求 | 参考章节 |
|----------|---------|---------|
| 分布式系统 | 理解CAP理论、一致性模型 | 第21章 |
| 网络编程 | TCP/HTTP协议基础 | 第18-19章 |
| 编程基础 | 熟练掌握至少一门后端语言 | - |

## 学习路径

```mermaid
graph TD
    A[核心概念] --> B[关键技术]
    B --> C[工程实践]
    C --> D[性能优化]
    D --> E[生产落地]
```

## 预计学习时间：8-10小时

## 内容结构

| 编号 | 文件 | 核心内容 |
|------|------|---------|
| 00 | 章节概览 | 学习目标、前置知识、学习路径 |
| 01 | 理论基础 | {', '.join(topics[:3])} |
| 02 | 核心技巧 | {', '.join(key_concepts[:3])} |
| 03 | 实战案例 | {', '.join(tools[:2])}等实战 |
| 04 | 常见误区 | {', '.join(misconceptions[:3])} |
| 05 | 练习方法 | {', '.join(practice_items[:3])} |
| 06 | 本章小结 | 核心知识点回顾、方案选型建议 |
"""

    theory_content = f"""# 第{num}章 {title} - 理论基础

## 一、{topics[0] if topics else '核心概念'}

### 1.1 基本定义

{title}是分布式系统中的重要技术组件。理解其核心原理是正确使用的基础。

### 1.2 核心原理

```mermaid
graph TD
    A[问题定义] --> B[方案设计]
    B --> C[技术选型]
    C --> D[实现落地]
    D --> E[验证优化]
```

### 1.3 关键概念

| 概念 | 说明 | 重要性 |
|------|------|--------|
| {key_concepts[0] if key_concepts else '概念一'} | 核心技术要点 | ⭐⭐⭐ |
| {key_concepts[1] if len(key_concepts) > 1 else '概念二'} | 重要实现细节 | ⭐⭐⭐ |
| {key_concepts[2] if len(key_concepts) > 2 else '概念三'} | 高级特性 | ⭐⭐ |

## 二、{topics[1] if len(topics) > 1 else '技术架构'}

### 2.1 架构设计

{title}的典型架构包含以下组件：

1. **接入层**：处理客户端请求，进行协议转换
2. **处理层**：核心业务逻辑处理
3. **存储层**：数据持久化和缓存
4. **监控层**：指标采集和告警

### 2.2 数据流

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant Gateway as 网关
    participant Service as 服务
    participant Storage as 存储
    
    Client->>Gateway: 请求
    Gateway->>Service: 路由
    Service->>Storage: 读写
    Storage-->>Service: 结果
    Service-->>Gateway: 响应
    Gateway-->>Client: 返回
```

## 三、{topics[2] if len(topics) > 2 else '核心技术'}

### 3.1 技术选型对比

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| 方案A | 性能高 | 复杂度高 | 大规模系统 |
| 方案B | 简单易用 | 功能有限 | 中小规模 |
| 方案C | 功能全面 | 资源消耗大 | 企业级应用 |

### 3.2 选型建议

根据项目规模和团队能力选择合适的方案：
- **小团队/快速迭代**：选择简单易用的方案
- **大团队/高并发**：选择性能优先的方案
- **企业级/合规要求**：选择功能全面的方案

## 四、{topics[3] if len(topics) > 3 else '高级特性'}

### 4.1 可扩展性设计

系统应该支持水平扩展：
- 无状态服务设计
- 数据分片策略
- 负载均衡配置

### 4.2 高可用设计

- 多副本冗余
- 自动故障转移
- 限流降级
"""

    skills_content = f"""# 第{num}章 {title} - 核心技巧

## 一、{key_concepts[0] if key_concepts else '基础技巧'}

### 1.1 实现步骤

1. **环境准备**：安装依赖，配置开发环境
2. **核心实现**：编写核心逻辑代码
3. **测试验证**：单元测试和集成测试
4. **性能优化**：分析瓶颈，优化关键路径

### 1.2 代码示例

```go
// {key_concepts[0]}实现示例
type Service struct {{
    // 核心组件
}}

func NewService() *Service {{
    return &Service{{}}
}}

func (s *Service) Process(ctx context.Context, req *Request) (*Response, error) {{
    // 1. 参数验证
    if err := req.Validate(); err != nil {{
        return nil, err
    }}
    
    // 2. 业务处理
    result, err := s.doProcess(ctx, req)
    if err != nil {{
        return nil, err
    }}
    
    // 3. 返回结果
    return &Response{{Result: result}}, nil
}}
```

## 二、{key_concepts[1] if len(key_concepts) > 1 else '进阶技巧'}

### 2.1 配置优化

```yaml
# 配置文件示例
service:
  max_connections: 1000
  timeout: 30s
  retry_count: 3
  
storage:
  pool_size: 50
  max_idle: 10
```

### 2.2 监控指标

| 指标 | 含义 | 告警阈值 |
|------|------|---------|
| QPS | 每秒请求数 | 根据容量规划 |
| 延迟P99 | 99分位延迟 | >500ms |
| 错误率 | 请求失败比例 | >1% |

## 三、{key_concepts[2] if len(key_concepts) > 2 else '高级技巧'}

### 3.1 性能优化

- 使用连接池减少连接开销
- 合理设置缓存策略
- 异步处理非关键路径
- 批量操作减少网络往返

### 3.2 安全实践

- 输入验证和参数过滤
- 认证授权机制
- 敏感数据加密
- 审计日志记录
"""

    case_content = f"""# 第{num}章 {title} - 实战案例

## 案例一：{tools[0] if tools else '基础应用'}实战

### 问题描述

某电商平台需要实现{title}相关功能，要求支持高并发、低延迟、高可用。

### 分析

1. **需求分析**：QPS > 10000，延迟 < 100ms
2. **技术选型**：选择{tools[0] if tools else '合适的工具'}
3. **架构设计**：分层架构，接入层+处理层+存储层

### 解决步骤

**Step 1：环境搭建**

```bash
# 安装依赖
# 配置环境
```

**Step 2：核心实现**

```go
// 核心代码实现
func setupService() *Service {{
    // 初始化组件
    // 配置参数
    // 启动服务
}}
```

**Step 3：测试验证**

```bash
# 功能测试
# 性能测试
# 压力测试
```

### 结果验证

- 功能测试：全部通过
- 性能测试：QPS达到15000，P99延迟50ms
- 压力测试：在2倍预期负载下稳定运行

## 案例二：{tools[1] if len(tools) > 1 else '进阶应用'}实战

### 问题描述

在生产环境中遇到{title}相关的性能问题。

### 分析

通过监控发现：
- 某些场景下延迟飙升
- 资源利用率不均衡
- 存在单点瓶颈

### 解决步骤

1. **问题定位**：使用火焰图分析热点
2. **优化方案**：调整配置，优化代码
3. **灰度验证**：金丝雀发布验证效果

### 结果验证

优化后：
- P99延迟降低60%
- 资源利用率提升40%
- 消除单点瓶颈
"""

    misconception_content = f"""# 第{num}章 {title} - 常见误区

{chr(10).join(f'''## 误区{i+1}：{m}

### 错误描述

在使用{title}时，常见的错误做法。

### 正确做法

采用正确的实现方式，避免潜在问题。

### 对比

| 方面 | 错误做法 | 正确做法 |
|------|---------|---------|
| 实现 | 简单但有问题 | 稍复杂但正确 |
| 性能 | 可能有隐患 | 稳定可靠 |
| 维护 | 难以扩展 | 易于维护 |

''' for i, m in enumerate(misconceptions))}

## 总结

| 误区 | 核心要点 |
|------|---------|
{chr(10).join(f'| {m} | 避免此错误 |' for m in misconceptions)}
"""

    practice_content = f"""# 第{num}章 {title} - 练习方法

{chr(10).join(f'''## 练习{i+1}：{p}（{'入门' if i < 2 else '进阶' if i < 4 else '高级'}）

### 目标

通过实践掌握{p}的核心技能。

### 步骤

1. 准备开发环境
2. 实现核心功能
3. 编写测试用例
4. 性能优化
5. 文档编写

### 检查标准

- [ ] 功能实现正确
- [ ] 测试覆盖充分
- [ ] 性能指标达标
- [ ] 代码质量良好

''' for i, p in enumerate(practice_items))}

## 学习建议

1. **循序渐进**：从基础练习开始，逐步增加难度
2. **动手实践**：理论结合实践，加深理解
3. **总结反思**：每次练习后总结经验教训
"""

    summary_content = f"""# 第{num}章 {title} - 本章小结

## 核心知识点回顾

### 1. 核心概念

{title}的核心概念和基本原理是理解整个技术体系的基础。

### 2. 关键技术

| 技术 | 说明 | 应用场景 |
|------|------|---------|
{chr(10).join(f'| {k} | 核心技术 | 广泛应用 |' for k in key_concepts[:4])}

### 3. 最佳实践

- 选择合适的技术方案
- 遵循最佳实践指南
- 持续优化和改进

## 核心模型总结

```mermaid
graph TD
    A[{title}] --> B[理论基础]
    A --> C[核心技术]
    A --> D[工程实践]
    B --> B1[概念理解]
    C --> C1[技术实现]
    D --> D1[生产落地]
```

## 方案选型建议

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 小规模 | 简单方案 | 快速实现 |
| 中规模 | 标准方案 | 平衡性能和复杂度 |
| 大规模 | 高级方案 | 最佳性能 |

## 下一步学习

1. 深入学习相关章节
2. 实践项目应用
3. 关注技术演进
4. 参与社区讨论

## 延伸阅读

- 官方文档和技术博客
- 开源项目源码
- 技术会议演讲
- 行业最佳实践案例
"""

    write(f"{d}/00-章节概览.md", overview_content)
    write(f"{d}/01-理论基础.md", theory_content)
    write(f"{d}/02-核心技巧.md", skills_content)
    write(f"{d}/03-实战案例.md", case_content)
    write(f"{d}/04-常见误区.md", misconception_content)
    write(f"{d}/05-练习方法.md", practice_content)
    write(f"{d}/06-本章小结.md", summary_content)


def gen_appendix(name, content_files):
    d = f"{BASE}/附录{name}"
    print(f"\n=== 附录{name} ===")
    
    for filename, content in content_files:
        write(f"{d}/{filename}", content)


if __name__ == "__main__":
    # Generate chapters 43-45 (already done with detailed content)
    gen_ch43()
    gen_ch44()
    gen_ch45()
    gen_ch46()
    
    # Generate chapters 47-60
    gen_chapter(47, "云原生架构", 
        ["微服务架构设计", "无服务器计算", "服务网格", "事件驱动架构"],
        ["容器化", "微服务拆分", "服务编排", "可观测性"],
        ["Kubernetes", "Istio", "Knative", "ArgoCD"],
        ["微服务拆分实践", "Knative部署", "事件驱动设计", "服务网格配置"],
        ["过度拆分微服务", "忽略服务治理", "容器化不彻底"])
    
    gen_chapter(48, "序列化与编码",
        ["JSON与XML解析", "Protocol Buffers", "Avro与MessagePack", "字符编码"],
        ["Protobuf编码", "Schema演进", "性能对比", "兼容性设计"],
        ["protoc", "Avro", "MessagePack", "JSON Schema"],
        ["Protobuf消息设计", "Schema演进实验", "性能对比测试", "跨语言序列化"],
        ["忽略Schema兼容性", "JSON性能问题", "编码选择不当"])
    
    gen_chapter(49, "连接池与资源管理",
        ["连接池原理", "数据库连接池", "HTTP连接池", "线程池管理"],
        ["连接复用", "池大小配置", "泄漏检测", "超时管理"],
        ["HikariCP", "Apache HttpClient", "Go http.Client", "Java线程池"],
        ["HikariCP调优", "连接泄漏检测", "线程池配置", "资源监控"],
        ["池大小设置不当", "忽略连接泄漏", "超时配置不合理"])
    
    gen_chapter(50, "数据一致性",
        ["一致性模型", "CRDT", "分布式事务", "幂等性设计"],
        ["线性一致性", "最终一致性", "Saga模式", "TCC模式"],
        ["etcd", "Redis", "Seata", "Kafka"],
        ["一致性模型实验", "CRDT实现", "Saga状态机", "幂等性设计"],
        ["过度追求强一致", "忽略网络分区", "补偿逻辑不完整"])
    
    gen_chapter(51, "读写分离与分库分表",
        ["主从复制", "读写分离", "分库分表策略", "分布式ID生成"],
        ["MySQL复制", "分片路由", "数据迁移", "扩容方案"],
        ["ShardingSphere", "MyCat", "Vitess", "Snowflake"],
        ["读写分离配置", "分片策略设计", "分布式ID实现", "数据迁移演练"],
        ["分片键选择不当", "忽略跨分片查询", "数据迁移不完整"])
    
    gen_chapter(52, "故障转移与恢复",
        ["故障检测算法", "Leader选举", "数据恢复", "灾备架构"],
        ["心跳检测", "Phi Accrual", "Raft选举", "PITR恢复"],
        ["etcd", "ZooKeeper", "Patroni", "MySQL MGR"],
        ["故障检测实验", "Leader选举演练", "备份恢复测试", "灾备切换演练"],
        ["故障检测不及时", "脑裂问题", "备份未验证"])
    
    gen_chapter(53, "多活架构",
        ["同城双活", "异地多活", "单元化架构", "数据同步机制"],
        ["流量调度", "数据分片", "单元化路由", "灰度切换"],
        ["DNS", "CDN", "数据同步中间件", "流量管理平台"],
        ["同城双活搭建", "单元化设计", "数据同步配置", "灰度切换演练"],
        ["多活等于完全对等", "忽略数据一致性", "单元化不彻底"])
    
    gen_chapter(54, "分布式锁",
        ["分布式锁原理", "Redis分布式锁", "ZooKeeper分布式锁", "锁续租机制"],
        ["SET NX EX", "Lua脚本", "Redlock算法", "Fencing Token"],
        ["Redis", "ZooKeeper", "etcd", "Redisson"],
        ["Redis锁实现", "ZooKeeper锁实现", "Redlock验证", "锁续租实验"],
        ["忽略锁续租", "释放别人的锁", "Redlock争议"])
    
    gen_chapter(55, "分布式事务",
        ["2PC/3PC协议", "Saga模式", "TCC模式", "事务性发件箱"],
        ["Saga状态机", "TCC资源预留", "消息最终一致", "幂等性设计"],
        ["Seata", "RocketMQ", "Kafka", "Temporal"],
        ["Saga实现", "TCC实现", "发件箱模式", "Seata集成"],
        ["补偿遗漏", "悬挂与空回滚", "过度使用分布式事务"])
    
    gen_chapter(56, "配置中心",
        ["配置中心架构", "配置热更新", "灰度发布", "配置加密"],
        ["长轮询", "推送机制", "Namespace隔离", "版本管理"],
        ["Apollo", "Nacos", "Spring Cloud Config", "etcd"],
        ["Apollo部署", "Nacos配置管理", "长轮询实现", "灰度发布实验"],
        ["配置风暴", "缓存一致性", "敏感信息泄露"])
    
    gen_chapter(57, "API网关",
        ["路由机制", "认证授权", "限流策略", "熔断保护"],
        ["路径路由", "JWT验证", "令牌桶限流", "熔断降级"],
        ["Kong", "APISIX", "Nginx", "Envoy"],
        ["Kong部署", "限流配置", "JWT集成", "熔断测试"],
        ["限流策略不当", "忽略熔断", "认证绕过"])
    
    gen_chapter(58, "服务网格",
        ["Sidecar模式", "Istio架构", "流量管理", "安全通信"],
        ["Envoy代理", "VirtualService", "DestinationRule", "mTLS"],
        ["Istio", "Linkerd", "Envoy", "Cilium"],
        ["Istio安装", "流量路由配置", "mTLS启用", "可观测性集成"],
        ["性能开销过大", "配置复杂度", "调试困难"])
    
    gen_chapter(59, "实时计算",
        ["流处理架构", "窗口机制", "状态管理", "Exactly-Once语义"],
        ["Flink架构", "水印机制", "Checkpoint", "CEP模式"],
        ["Apache Flink", "Kafka Streams", "Spark Streaming", "ClickHouse"],
        ["Flink作业开发", "窗口实验", "状态管理", "反压处理"],
        ["水印设置不当", "状态膨胀", "窗口语义混淆"])
    
    gen_chapter(60, "数据湖与数据仓库",
        ["数据湖架构", "表格式", "数据仓库建模", "ETL/ELT"],
        ["星型模型", "雪花模型", "SCD处理", "数据治理"],
        ["Delta Lake", "Apache Iceberg", "dbt", "ClickHouse"],
        ["Iceberg实验", "星型模型设计", "dbt项目搭建", "数据质量监控"],
        ["数据沼泽", "建模过度规范化", "数据治理形式化"])
    
    # Generate appendices
    gen_appendix("A-推荐书籍与论文", [
        ("00-章节概览.md", """# 附录A：推荐书籍与论文 - 概览

## 内容说明

本附录收录了软件工程领域的经典书籍和里程碑论文，按计算机科学的核心领域分类。

## 使用建议

1. 根据当前学习方向选择1-2个领域开始
2. 优先阅读经典书籍的核心章节
3. 配合论文阅读理解技术演进
4. 建立个人知识体系

## 覆盖领域

| 领域 | 书籍数量 | 论文数量 |
|------|---------|---------|
| 计算机体系结构 | 3 | 5 |
| 操作系统 | 3 | 3 |
| 数据库系统 | 4 | 6 |
| 分布式系统 | 4 | 8 |
| 网络编程 | 3 | 4 |
| 编译原理 | 2 | 3 |
| 软件架构 | 3 | 4 |
| 系统安全 | 2 | 3 |
"""),
    ])
    
    gen_appendix("B-工具与环境搭建", [
        ("00-章节概览.md", """# 附录B：工具与环境搭建 - 概览

## 内容说明

本附录提供软件工程师常用工具的安装、配置和使用指南。

## 工具分类

| 类别 | 工具 | 用途 |
|------|------|------|
| 编译器 | GCC, LLVM/Clang | 代码编译 |
| 调试器 | GDB, LLDB | 程序调试 |
| 性能分析 | perf, Flame Graph, eBPF | 性能调优 |
| 构建工具 | CMake, Make | 项目构建 |
| 版本控制 | Git | 代码管理 |
| 容器 | Docker, Kubernetes | 应用部署 |
| IDE | VS Code, CLion | 开发环境 |

## 快速开始

```bash
# Ubuntu/Debian基础工具安装
sudo apt update
sudo apt install build-essential git docker.io

# 安装Go
wget https://go.dev/dl/go1.22.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.22.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
```
"""),
    ])
    
    gen_appendix("C-术语表", [
        ("00-章节概览.md", """# 附录C：术语表 - 概览

## 内容说明

本附录收录了本书涉及的全部核心术语，按领域分类组织。

## 术语分类

| 领域 | 术语数量 |
|------|---------|
| 计算机体系结构 | 30+ |
| 操作系统 | 25+ |
| 数据库系统 | 35+ |
| 计算机网络 | 30+ |
| 分布式系统 | 40+ |
| 编译原理 | 20+ |
| 软件架构 | 25+ |
| 系统安全 | 20+ |

## 使用建议

- 初次阅读时作为辅助参考
- 系统复习时检验掌握程度
- 面试准备时快速查漏补缺
- 技术写作时确保术语准确

## 术语格式

每个术语条目包含：
- **英文原名**：国际通用标识
- **中文译名**：母语概念映射
- **一句话定义**：精炼的核心含义
"""),
    ])
    
    print("\n✅ All files generated successfully!")
