---
title: 技巧一Dockerfile最佳实践
type: docs
weight: 1
---
# 技巧一：Dockerfile 最佳实践

## 引言

Dockerfile 是构建 Docker 镜像的核心配置文件，它以声明式的方式定义了镜像的每一层内容。一个编写良好的 Dockerfile 不仅能显著减小镜像体积、加速构建过程，还能提升安全性和可维护性。然而，在实际工程中，许多开发者对 Dockerfile 的理解停留在"能跑就行"的层面，导致镜像臃肿、构建缓慢、存在安全隐患等问题。

本章将从 Dockerfile 指令详解出发，深入探讨镜像层优化、多阶段构建、构建缓存机制、安全最佳实践等十大核心主题，并通过真实案例对比优化前后的差异，帮助读者全面掌握 Dockerfile 的最佳实践。

---

## 1. Dockerfile 指令详解

Dockerfile 由一系列指令（Instruction）组成，每条指令都会在镜像中创建一个新的层（Layer）。理解每条指令的语义、语法和常见陷阱，是编写高质量 Dockerfile 的基础。

### 1.1 FROM —— 基础镜像

**用途**：指定基础镜像，是 Dockerfile 中必须出现的第一条有效指令。

**语法**：
```dockerfile
FROM <image>[:<tag>] [AS <name>]
FROM scratch
```

**选择基础镜像的决策树**：

| 场景 | 推荐镜像 | 理由 |
|------|----------|------|
| 需要完整系统工具 | `ubuntu:22.04` | 完整包管理器，适合调试和多工具场景 |
| Python 应用（标准） | `python:3.12-slim` | 约 150MB，平衡体积与兼容性 |
| Python 应用（极简） | `python:3.12-alpine` | 约 50MB，但 musl libc 可能导致 C 扩展兼容问题 |
| Go 静态二进制 | `scratch` 或 `distroless` | 零基础开销，仅需复制二进制和证书 |
| Node.js 应用 | `node:20-alpine` | 约 180MB，适合前端构建和轻量后端 |
| Java 应用 | `eclipse-temurin:21-jre-alpine` | 仅 JRE，比 JDK 镜像小 60%+ |
| 需要 shell 调试 | 避免 `scratch`/`distroless` | 这些镜像没有 shell，无法 `docker exec` 进入 |

**常见陷阱**：
- 使用 `FROM latest` 标签，导致构建不可复现
- 基础镜像过大，浪费存储和传输带宽
- Alpine 镜像使用 musl libc，部分 Python C 扩展（如 numpy、pandas）可能编译失败

**示例**：
```dockerfile
# 推荐：使用具体的版本标签
FROM python:3.12-slim AS builder
FROM golang:1.22-alpine AS builder
FROM ubuntu:22.04

# 使用 scratch 构建极简镜像（适用于静态编译语言）
FROM scratch

# 使用 distroless 镜像（兼顾极简与安全性）
FROM gcr.io/distroless/python3-debian12
```

### 1.2 RUN —— 执行命令

**用途**：在构建过程中执行任意命令，常用于安装软件包、编译代码等。

**语法**：
```dockerfile
RUN <command>                          # shell 形式（默认 /bin/sh -c）
RUN ["executable", "param1", "param2"] # exec 形式（不经过 shell 解释）
```

**两种形式的关键区别**：

| 特性 | shell 形式 | exec 形式 |
|------|-----------|----------|
| 是否经过 shell | 是（`/bin/sh -c`） | 否，直接执行 |
| 环境变量展开 | ✅ 自动展开 `$VAR` | ❌ 不展开 |
| 管道/重定向 | ✅ 支持 `\|`、`>`、`&&` | ❌ 不支持 |
| 信号处理 | shell 拦截 SIGTERM | 直接接收信号 |
| 适用场景 | 复杂命令组合、脚本执行 | 简单可执行文件调用 |

**常见陷阱**：
- 每条 RUN 创建一个层，过多层导致镜像臃肿
- 未清理包管理器缓存，增大镜像体积
- 在 shell 形式中 `RUN cd /app && ...` 的 `cd` 仅对当前 RUN 生效

**示例**：
```dockerfile
# 不推荐：每条 RUN 一个层，且未清理缓存
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get clean

# 推荐：合并 RUN 并在同一层清理缓存
RUN apt-get update &amp;&amp; \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates &amp;&amp; \
    apt-get clean &amp;&amp; \
    rm -rf /var/lib/apt/lists/*
```

### 1.3 COPY 与 ADD —— 复制文件

**COPY** 将本地文件或目录复制到镜像中：
```dockerfile
COPY <src>... <dest>
COPY --chown=<user>:<group> <src> <dest>
COPY --chmod=<mode> <src> <dest>  # BuildKit 新特性
COPY --link <src> <dest>          # BuildKit 新特性：独立缓存层
```

**ADD** 除了复制功能外，还支持：
- 自动解压 `.tar` 归档文件
- 从远程 URL 下载文件

```dockerfile
# ADD 会自动解压 local.tar.gz 到 /app 目录
ADD local.tar.gz /app/

# ADD 从远程 URL 下载文件（不推荐，应使用 RUN curl/wget）
ADD https://example.com/config.yaml /app/
```

**COPY vs ADD 的选择原则**：

| 特性 | COPY | ADD |
|------|------|-----|
| 复制本地文件 | ✅ | ✅ |
| 自动解压 tar | ❌ | ✅ |
| 远程 URL 下载 | ❌ | ✅ |
| 构建缓存友好 | ✅ 更可预测 | ⚠️ URL 变化难追踪 |
| 语义明确性 | ✅ 更直观 | ⚠️ 隐式行为 |

**COPY --link 的独特价值**：`COPY --link`（BuildKit 特性）创建独立的缓存层，不依赖前序层的缓存状态。当基础镜像更新时，使用 `--link` 的 COPY 指令仍然可以命中缓存，避免了连锁失效：

```dockerfile
# 无 --link：基础镜像变化 → 这里的 COPY 缓存也失效
COPY requirements.txt .

# 有 --link：基础镜像变化 → 这里的 COPY 缓存仍然命中
COPY --link requirements.txt .
```

**最佳实践**：大多数场景使用 `COPY`，仅在需要自动解压时使用 `ADD`。远程下载应使用 `RUN curl` 或 `RUN wget`，以便更好地控制缓存和错误处理。

```dockerfile
# 推荐：使用 COPY 复制本地文件
COPY requirements.txt /app/
COPY . /app/

# 仅在需要解压时使用 ADD
ADD archives.tar.gz /app/data/
```

### 1.4 WORKDIR —— 工作目录

**用途**：设置后续指令的工作目录。如果目录不存在，会自动创建（包括中间目录）。

**语法**：
```dockerfile
WORKDIR /path/to/directory
```

**常见陷阱**：
- 使用 `RUN cd /app` 试图切换目录（CD 仅对当前 RUN 生效）
- 使用 `WORKDIR .` 使路径不清晰
- 使用相对路径导致目录层级不可预测

**示例**：
```dockerfile
# 推荐：明确指定绝对路径
WORKDIR /app

# 多次 WORKDIR 会叠加：WORKDIR /app + WORKDIR src = /app/src
WORKDIR /app
WORKDIR src
# 当前目录为 /app/src

# 不推荐：使用相对路径
WORKDIR app  # 等效于 /app（首次），后续则是 /app/app

# 错误用法：RUN cd 不会影响后续指令
RUN cd /app &amp;&amp; ls  # ✅ 这个 RUN 内部有效
RUN ls              # ❌ 回到默认目录
```

### 1.5 ENV 与 ARG —— 环境变量

**ENV** 设置的环境变量在构建和运行时均生效：
```dockerfile
ENV APP_HOME=/app
ENV APP_ENV=production \
    APP_PORT=8080
```

**ARG** 仅在构建时有效，运行时不存在：
```dockerfile
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim
ARG BUILD_DATE
```

**ARG 与 FROM 的交互**：`ARG` 在 `FROM` 之前声明时，可以在 `FROM` 指令中使用，但不能在 `FROM` 之后的指令中使用。如果需要在后续指令中使用，必须在 `FROM` 之后重新声明：

```dockerfile
ARG VERSION=3.12
FROM python:${VERSION}-slim
ARG VERSION  # 重新声明，此时值为空（FROM 前的 ARG 不会传递到 FROM 后）
# 如果需要保留值，用 --build-arg 传入
```

**安全陷阱**：
```dockerfile
# ❌ 危险：ARG 中的密码会留在镜像层中！
ARG DB_PASSWORD=secretpass
ENV DB_PASSWORD=${DB_PASSWORD}
# 即使后续修改了 ENV，ARG 的值仍可通过 docker history 查看

# ✅ 安全做法：使用 --build-arg 并在运行时通过环境变量注入
# 构建时：docker build --build-arg DB_PASSWORD=xxx .
# 运行时：docker run -e DB_PASSWORD=xxx image
```

### 1.6 CMD 与 ENTRYPOINT —— 容器启动命令

这是 Dockerfile 中最常被混淆的一对指令。

**CMD** 提供容器启动时的默认命令，可被 `docker run` 的参数覆盖：
```dockerfile
# exec 形式（推荐）
CMD ["python", "app.py"]

# shell 形式
CMD python app.py

# 作为 ENTRYPOINT 的默认参数
CMD ["--port", "8080"]
```

**ENTRYPOINT** 配置容器的入口点，通常不被覆盖：
```dockerfile
# exec 形式（推荐）
ENTRYPOINT ["python", "app.py"]

# shell 形式（会经过 /bin/sh -c 包装）
ENTRYPOINT python app.py
```

**CMD vs ENTRYPOINT 组合**：

| 配置方式 | `docker run myimage` | `docker run myimage --port 9090` |
|---------|-------------------|-------------------------------|
| `CMD ["python", "app.py"]` | `python app.py` | `--port 9090`（CMD 被覆盖） |
| `ENTRYPOINT ["python", "app.py"]` | `python app.py` | `python app.py --port 9090` |
| `ENTRYPOINT ["python"]` + `CMD ["app.py"]` | `python app.py` | `python --port 9090`（CMD 被覆盖） |

**shell 形式的隐患**：当使用 shell 形式时，命令会被 `/bin/sh -c` 包装，导致应用进程变成 sh 的子进程而非 PID 1。这意味着应用无法接收 SIGTERM 信号，`docker stop` 会先发送 SIGTERM 给 sh（被忽略），等待超时后发送 SIGKILL 强制终止，造成 10 秒的优雅关闭延迟。始终推荐使用 exec 形式。

**实际应用模式**：

```dockerfile
# 模式1：直接启动（简单应用）
CMD ["python", "app.py"]

# 模式2：ENTRYPOINT 锁定程序，CMD 提供默认参数
ENTRYPOINT ["python"]
CMD ["app.py"]

# 模式3：使用 entrypoint 脚本处理初始化逻辑
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["serve"]
```

### 1.7 EXPOSE —— 声明端口

**用途**：声明容器运行时监听的端口（仅文档作用，不会自动发布端口）。

```dockerfile
EXPOSE 8080
EXPOSE 443/tcp
EXPOSE 53/udp
```

**注意**：`EXPOSE` 仅是元数据，实际发布端口需要使用 `docker run -p` 或 `docker-compose` 的 `ports` 配置。但 EXPOSE 仍有实际价值：它为 docker-compose 的 `expose` 指令提供默认值，也是容器编排系统识别服务端口的重要依据。

### 1.8 VOLUME —— 声明卷

**用途**：声明容器中的挂载点，用于持久化数据。

```dockerfile
VOLUME /data
VOLUME ["/var/log", "/var/data"]
```

**注意**：在 Dockerfile 中使用 `VOLUME` 可能导致后续对挂载点的写操作丢失。推荐在 `docker run` 或 `docker-compose.yml` 中使用挂载，而非在 Dockerfile 中。原因在于：Dockerfile 中 VOLUME 之后的指令如果试图写入该路径，写入的内容不会被保留在镜像层中，因为该路径已经被标记为匿名卷。

### 1.9 USER —— 指定运行用户

**用途**：设置后续指令和容器运行时的用户。

```dockerfile
# 创建专用用户和组
RUN groupadd -r appuser &amp;&amp; useradd -r -g appuser -d /app -s /sbin/nologin appuser

# 设置工作目录的权限
RUN chown -R appuser:appuser /app

# 切换到非 root 用户
USER appuser
```

**注意 USER 的放置位置**：USER 指令会影响后续所有 RUN 指令的执行身份。如果在安装依赖之前就切换了用户，可能导致权限不足。推荐的顺序是：先以 root 安装依赖、设置权限，最后再切换到非 root 用户。

### 1.10 HEALTHCHECK —— 健康检查

**用途**：定义容器健康检查命令，用于编排系统判断容器是否正常。

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 使用 wget 代替 curl（适用于精简镜像）
HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -qO- http://localhost:8080/health || exit 1

# 禁用健康检查
HEALTHCHECK NONE
```

**参数详解**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--interval` | 30s | 两次检查之间的间隔 |
| `--timeout` | 30s | 单次检查超时时间 |
| `--start-period` | 0s | 容器启动后的宽限期，此期间失败不计入重试次数 |
| `--start-interval` | 5s | (Docker 25+) 启动期间的检查间隔，比 `--interval` 更频繁 |
| `--retries` | 3 | 连续失败次数达到此值后标记为 unhealthy |

### 1.11 SHELL —— 指定 Shell

**用途**：覆盖 RUN 指令中默认的 shell 解释器。

```dockerfile
# 默认使用 sh -c
SHELL ["/bin/sh", "-c"]

# 使用 bash
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# 启用 pipefail 后，管道中任意命令失败都会导致整体失败
RUN echo "test" | grep "test" &amp;&amp; echo "success"
```

**为什么 pipefail 重要**：默认的 sh 不启用 pipefail，这意味着 `RUN command1 | command2` 中即使 `command1` 失败，只要 `command2` 成功，整个 RUN 仍然返回 0。在构建过程中这会导致静默失败——你以为依赖安装成功了，实际上源列表更新失败了。启用 pipefail 是生产级 Dockerfile 的标准做法。

### 1.12 LABEL —— 元数据标签

**用途**：为镜像添加元数据，便于管理和查询。

```dockerfile
LABEL maintainer="team@example.com"
LABEL version="1.0"
LABEL org.opencontainers.image.source="https://github.com/user/repo"
LABEL org.opencontainers.image.description="My Application"
LABEL org.opencontainers.image.version="2.1.0"
LABEL org.opencontainers.image.created="2024-01-15T10:00:00Z"
```

**多行 LABEL 的正确写法**：避免为每个标签单独写一条 LABEL 指令（每条创建一个层），应合并为一条：

```dockerfile
# ❌ 不推荐：每条 LABEL 创建一个层
LABEL maintainer="team@example.com"
LABEL version="1.0"

# ✅ 推荐：合并为一条 LABEL
LABEL maintainer="team@example.com" \
      version="1.0" \
      org.opencontainers.image.source="https://github.com/user/repo"
```

### 1.13 STOPSIGNAL —— 停止信号

**用途**：定义容器停止时发送的系统信号。

```dockerfile
STOPSIGNAL SIGTERM
STOPSIGNAL SIGQUIT
```

**选择依据**：大多数应用使用默认的 `SIGTERM`（优雅关闭）。如果应用使用 `SIGQUIT` 实现优雅关闭（如 Nginx），则需要显式声明。使用 `SIGKILL` 作为 STOPSIGNAL 几乎没有意义，因为它不可被捕获或处理。

### 1.14 ONBUILD —— 延迟构建触发器

**用途**：为当前镜像定义触发器，当下游 Dockerfile 以当前镜像为基础构建时执行。

```dockerfile
# 在基础镜像 Dockerfile 中
ONBUILD COPY . /app
ONBUILD RUN pip install -r /app/requirements.txt
```

**注意**：`ONBUILD` 不会被多级构建的 `FROM` 触发，且在嵌套继承中可能导致混乱，应谨慎使用。建议在 ONBUILD 基础镜像的文档中明确说明触发行为。

---

## 2. 镜像层优化

### 2.1 Dockerfile 指令与层的关系

Docker 镜像由多个只读层（Layer）堆叠而成。每条 `FROM`、`RUN`、`COPY`、`ADD` 指令都会创建一个新的层。理解层的机制是优化镜像体积的关键。

```mermaid
graph TB
    subgraph "联合文件系统视角"
        A["Layer 5: COPY app.py (1.2KB)"] --> B["Layer 4: RUN pip install (85.2MB)"]
        B --> C["Layer 3: COPY requirements.txt (1.2KB)"]
        C --> D["Layer 2: WORKDIR /app (0B)"]
        D --> E["Layer 1: FROM python:3.12-slim (72.4MB)"]
    end
    F["最终镜像 = 72.4MB + 0B + 1.2KB + 85.2MB + 1.2KB ≈ 157.6MB"]
```

**层的不可变性原理**：Docker 使用联合文件系统（UnionFS）将多个只读层叠加，从容器视角看，所有层合并为一个统一的文件系统视图。上层文件会遮蔽下层同名文件，这就是为什么你可以在 RUN 指令中"删除"文件——实际上只是在上层创建了一个 whiteout 标记，原文件仍然存在于之前的层中，占用磁盘空间。

### 2.2 层顺序与缓存效率

Docker 构建时逐层执行，每层的缓存取决于：指令内容是否变化。一旦某层失效，其后所有层都需要重新构建。因此，**变化频率低的指令应放在前面**。

**反面示例**（缓存效率低）：
```dockerfile
# ❌ 每次代码修改都会触发依赖重新安装
FROM python:3.12-slim
WORKDIR /app
COPY . .                        # 代码频繁变化
RUN pip install -r requirements.txt  # 每次都重新安装
```

**正面示例**（缓存效率高）：
```dockerfile
# ✅ 依赖安装在代码复制之前，代码修改不会触发重新安装
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .         # 依赖文件很少变化
RUN pip install -r requirements.txt  # 缓存命中
COPY . .                        # 代码变化不影响上面的层
```

### 2.3 合并 RUN 指令减少层数

每条 `RUN` 指令创建一个独立的层，即使你在后续层中删除了文件，前一层的文件仍然存在于镜像中。

```dockerfile
# ❌ 错误做法：在后续层中删除文件并不能减小镜像
RUN apt-get update &amp;&amp; apt-get install -y gcc
RUN apt-get install -y python3-dev
RUN apt-get clean          # 清理只影响本层
RUN rm -rf /var/lib/apt/lists/*  # 又是一层

# ✅ 正确做法：在同一个 RUN 中安装和清理
RUN apt-get update &amp;&amp; \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev &amp;&amp; \
    apt-get clean &amp;&amp; \
    rm -rf /var/lib/apt/lists/*
```

### 2.4 真实的体积对比

以下是一个 Python Web 应用的 Dockerfile 优化前后对比：

**优化前**（约 980MB）：
```dockerfile
FROM python:3.12
RUN apt-get update
RUN apt-get install -y gcc python3-dev
RUN pip install flask gunicorn
COPY . /app
WORKDIR /app
CMD ["gunicorn", "app:app"]
```

**优化后**（约 150MB）：
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update &amp;&amp; \
    apt-get install -y --no-install-recommends gcc python3-dev &amp;&amp; \
    pip install --no-cache-dir -r requirements.txt &amp;&amp; \
    apt-get purge -y --auto-remove gcc &amp;&amp; \
    rm -rf /var/lib/apt/lists/*
COPY . .
CMD ["gunicorn", "app:app"]
```

**体积缩减约 85%**，关键优化点：
1. 基础镜像从 `python:3.12`（约 900MB）切换到 `python:3.12-slim`（约 150MB）
2. 使用 `--no-cache-dir` 避免 pip 缓存
3. 使用 `--no-install-recommends` 减少不必要的依赖
4. 安装和清理在同一个 RUN 层中完成
5. 在同一层中 `apt-get purge gcc` 移除编译工具（gcc 安装后约 100MB，编译完成后不再需要）

---

## 3. 多阶段构建 (Multi-stage Build)

### 3.1 为什么需要多阶段构建

在构建过程中，编译器、构建工具、头文件等开发依赖通常体积庞大，但运行时并不需要。多阶段构建允许我们在一个阶段中编译代码，在另一个阶段中只复制编译产物，从而大幅减小最终镜像体积。

```mermaid
graph LR
    A[构建阶段 Build Stage] -->|COPY --from| B[运行阶段 Runtime Stage]
    A -->|包含: 编译器, 依赖源码, 构建工具| C[临时镜像 - 不发布]
    B -->|包含: 二进制文件, 运行时依赖| D[最终镜像 - 发布]
```

**多阶段构建的三层价值**：
1. **体积缩减**：移除编译工具和构建依赖
2. **安全加固**：源代码、密钥、构建脚本不进入运行时镜像
3. **缓存优化**：不同阶段独立缓存，互不干扰

### 3.2 Go 微服务多阶段构建

Go 语言编译产生静态二进制文件，非常适合多阶段构建。

**优化前**（约 800MB）：
```dockerfile
FROM golang:1.22
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o server .
CMD ["./server"]
```

**优化后**（约 12MB）：
```dockerfile
# ============ 构建阶段 ============
FROM golang:1.22-alpine AS builder

WORKDIR /app

# 先复制依赖文件，利用缓存
COPY go.mod go.sum ./
RUN go mod download

# 复制源代码并编译
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o server .

# ============ 运行阶段 ============
FROM scratch

# 从构建阶段复制编译产物
COPY --from=builder /app/server /server
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

EXPOSE 8080
ENTRYPOINT ["/server"]
```

**关键点**：
- 构建阶段使用 `golang:1.22-alpine`，包含完整 Go 工具链
- 运行阶段使用 `scratch`，仅包含静态二进制文件
- 使用 `-ldflags="-s -w"` 去除调试信息，进一步缩小体积
- 需要手动复制 CA 证书（scratch 镜像中没有）
- `CGO_ENABLED=0` 确保纯静态编译，不依赖任何动态链接库

### 3.3 Python Web 应用多阶段构建

```dockerfile
# ============ 构建阶段 ============
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装编译依赖
RUN apt-get update &amp;&amp; \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libpq-dev &amp;&amp; \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖到虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============ 运行阶段 ============
FROM python:3.12-slim

WORKDIR /app

# 只安装运行时系统依赖
RUN apt-get update &amp;&amp; \
    apt-get install -y --no-install-recommends libpq5 &amp;&amp; \
    rm -rf /var/lib/apt/lists/*

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
```

**虚拟环境的关键作用**：Python 多阶段构建中使用 venv 而非直接 `pip install --target`，是因为 venv 保留了完整的 Python 包元数据和入口点脚本，确保运行阶段可以正确解析包依赖关系。

### 3.4 命名构建阶段与跨阶段复制

使用 `AS` 关键字命名构建阶段，然后通过 `COPY --from=<name>` 引用：

```dockerfile
# 阶段1：安装依赖
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production

# 阶段2：构建前端资源
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/ .
RUN npm ci &amp;&amp; npm run build

# 阶段3：最终运行镜像
FROM node:20-alpine

WORKDIR /app

# 从阶段1复制生产依赖
COPY --from=deps /app/node_modules ./node_modules

# 从阶段2复制构建产物
COPY --from=frontend /frontend/dist ./public

COPY backend/ .
RUN useradd --create-home appuser
USER appuser

EXPOSE 3000
CMD ["node", "server.js"]
```

### 3.5 使用 --target 构建特定阶段

```bash
# 仅构建构建阶段（用于调试）
docker build --target builder -t myapp:debug .

# 构建完整镜像（默认最后一层）
docker build -t myapp:latest .

# CI/CD 中可能需要构建测试阶段
docker build --target test -t myapp:test .
```

### 3.6 多阶段构建中的 ARG 作用域

每个阶段的 `ARG` 是独立的，不会跨阶段传递。如果需要在多个阶段使用同一个构建参数，必须在每个阶段都声明：

```dockerfile
ARG NODE_VERSION=20

# 阶段1
FROM node:${NODE_VERSION}-alpine AS builder
ARG NODE_VERSION  # 不需要重新赋值，FROM 之前的 ARG 已经被使用

# 阶段2
FROM node:${NODE_VERSION}-alpine  # ARG 在 FROM 中自动可用
```

---

## 4. 构建缓存机制

### 4.1 缓存工作原理

Docker 构建时逐层检查缓存。对于每一条指令，Docker 会判断该层是否可以复用缓存：

1. **基础镜像**：直接使用缓存的镜像层
2. **RUN 指令**：检查指令字符串是否完全相同（包括换行符）
3. **COPY/ADD 指令**：检查文件内容的校验和（checksum）是否变化
4. **其他指令**：检查指令参数是否变化

### 4.2 缓存失效规则

一旦某一层缓存失效，该层之后的所有层都将重新构建：

```dockerfile
FROM node:20-alpine          # 层1: 缓存 ✅
WORKDIR /app                 # 层2: 缓存 ✅
COPY package.json ./         # 层3: 缓存 ✅ (文件未变)
RUN npm install              # 层4: 缓存 ✅
COPY . .                     # 层5: 缓存 ❌ (代码变了!)
RUN npm run build            # 层6: 必须重新构建 ❌
```

### 4.3 优化缓存的实战策略

**策略1：先复制依赖描述文件，再安装依赖**

```dockerfile
# ✅ 优化后的 Dockerfile
FROM python:3.12-slim
WORKDIR /app

# 第1步：只复制依赖清单（很少变化）
COPY requirements.txt .

# 第2步：安装依赖（依赖未变时使用缓存）
RUN pip install --no-cache-dir -r requirements.txt

# 第3步：复制应用代码（频繁变化，但不会触发上面的重新安装）
COPY . .
```

**策略2：使用 BuildKit 的缓存挂载**

```dockerfile
# Dockerfile (需要启用 BuildKit)
# syntax=docker/dockerfile:1

FROM python:3.12-slim
WORKDIR /app

# --mount=type=cache 持久化 pip 缓存
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 持久化 apt 缓存
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update &amp;&amp; apt-get install -y --no-install-recommends gcc
```

**策略3：使用 .dockerignore 排除无关文件**

如果 `COPY . .` 没有 `.dockerignore`，任何文件变化（包括 `.git`、`node_modules`、日志等）都会导致缓存失效。

---

## 5. .dockerignore 最佳实践

### 5.1 什么是 .dockerignore

`.dockerignore` 文件类似于 `.gitignore`，用于排除不需要发送到 Docker 构建上下文（Build Context）的文件和目录。构建上下文是 `docker build` 命令后指定路径下的所有文件。

### 5.2 为什么重要

1. **减小构建上下文体积**：未排除的文件会通过 Docker 守护进程传输，增大网络开销
2. **避免缓存失效**：`COPY . .` 会将所有文件的内容哈希作为缓存键，无关文件变化会导致缓存失效
3. **安全**：避免将 `.env`、密钥文件等敏感信息复制到镜像中
4. **减少攻击面**：测试文件、CI 配置、文档等不应进入运行时镜像

### 5.3 推荐的 .dockerignore 模板

```dockerignore
# 版本控制
.git
.gitignore
.svn
.github

# Docker 相关
Dockerfile*
docker-compose*.yml
.dockerignore

# 依赖目录（避免覆盖镜像中的依赖）
node_modules
venv
.venv
__pycache__
*.pyc
target

# IDE 和编辑器
.idea
.vscode
*.swp
*.swo
*~

# 操作系统文件
.DS_Store
Thumbs.db

# 环境和敏感文件
.env
.env.*
*.pem
*.key
credentials.json
secrets/

# 文档和测试
*.md
LICENSE
docs/
tests/
.github/
```

### 5.4 对构建性能的影响

一个未配置 `.dockerignore` 的 Node.js 项目，构建上下文可能包含：
- `node_modules/`（200MB+）
- `.git/`（50MB+）
- 各种日志和临时文件

配置合理的 `.dockerignore` 后，构建上下文可以缩小到仅几百 KB，构建速度显著提升。在 CI/CD 环境中，构建上下文的传输速度直接影响流水线耗时——一个 300MB 的构建上下文通过 Docker socket 传输可能需要 30 秒，而优化后仅需 2 秒。

### 5.5 选择性包含模式

有时项目中大部分文件需要排除，但少数文件需要包含。使用 `!` 取反模式可以实现白名单策略：

```dockerignore
# 排除所有文件
*

# 只包含必要的文件
!src/
!requirements.txt
!pyproject.toml
!setup.cfg
```

---

## 6. 安全最佳实践

### 6.1 不以 root 身份运行

默认情况下，容器以 root 用户运行，这会带来严重的安全风险。如果攻击者利用应用漏洞获得容器内的 shell，以 root 运行意味着直接拥有容器内的最高权限，在某些配置下甚至可以逃逸到宿主机。

```dockerfile
# ✅ 创建专用用户并切换
RUN groupadd -r appuser &amp;&amp; \
    useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app
COPY --chown=appuser:appuser . .

USER appuser
```

**运行时验证**：
```bash
docker run --rm myimage whoami
# 输出: appuser（而非 root）
```

**注意**：`USER` 指令会改变后续 RUN 指令的执行身份。如果在安装依赖之前就切换到非 root 用户，可能导致权限不足。推荐的顺序是：先以 root 安装依赖、设置文件权限，最后再切换到非 root 用户。

### 6.2 使用具体的基础镜像标签

```dockerfile
# ❌ 不可复现，可能引入意外更新或安全漏洞
FROM python:latest
FROM node:20

# ✅ 使用具体的版本和变体
FROM python:3.12.4-slim
FROM node:20.11.1-alpine3.19
```

**更进一步：使用镜像摘要（digest）锁定版本**：
```dockerfile
# 使用 SHA256 摘要确保完全一致的基础镜像
FROM python:3.12.4-slim@sha256:abc123...
```

### 6.3 镜像安全扫描

```bash
# 使用 Trivy 扫描镜像漏洞
trivy image myapp:latest

# 使用 Grype 扫描
grype myapp:latest

# 在 CI/CD 中设置漏洞阈值
trivy image --severity HIGH,CRITICAL --exit-code 1 myapp:latest

# 输出为 SARIF 格式（可集成到 GitHub Security 面板）
trivy image --format sarif --output result.sarif myapp:latest
```

### 6.4 使用最小基础镜像

| 基础镜像 | 大小 | 特点 | 适用场景 |
|---------|------|------|----------|
| `ubuntu:22.04` | ~77MB | 完整 Debian 系统 | 需要完整包管理器的场景 |
| `python:3.12` | ~900MB | 含完整 Python 运行时和工具 | 开发/调试 |
| `python:3.12-slim` | ~150MB | 精简版 Python | 大多数 Python 生产应用 |
| `python:3.12-alpine` | ~50MB | Alpine Linux + Python | 极简场景，注意 musl 兼容性 |
| `gcr.io/distroless/python3` | ~50MB | 无 shell、无包管理器 | 最大安全性要求 |
| `scratch` | 0MB | 完全空白，仅适用静态二进制 | Go/Rust 静态编译 |

### 6.5 不要在镜像中存储密钥

```dockerfile
# ❌ 危险：密钥会永久存在于镜像层中
ARG DATABASE_URL=postgres://user:***@db:5432/mydb
ENV API_KEY=sk-123...cdef

# ✅ 使用 Docker secrets 或运行时环境变量注入
# docker run -e DATABASE_URL=xxx image
# docker service create --secret db_url image
```

**即使在多阶段构建中也要注意**：如果在构建阶段使用了密钥（如 `pip install --extra-index-url https://token:xxx@...`），密钥可能残留在 pip 缓存或构建日志中。使用 BuildKit 的 `--secret` 挂载可以在构建完成后安全清除：

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf \
    pip install -r requirements.txt
# secret 不会保留在镜像层中
```

### 6.6 只读文件系统与权限最小化

```bash
# 运行时使用只读文件系统
docker run --read-only --tmpfs /tmp myimage

# 丢弃所有 Linux 能力
docker run --cap-drop ALL --cap-add NET_BIND_SERVICE myimage
```

### 6.7 多阶段构建减少攻击面

多阶段构建不仅减小镜像体积，更重要的是：编译工具、源代码、开发依赖不会出现在最终镜像中，大幅减小攻击面。

---

## 7. 性能优化技巧

### 7.1 启用 BuildKit

BuildKit 是 Docker 新一代构建引擎，支持并行构建、更好的缓存管理和更详细的构建日志。

```bash
# 方式1：设置环境变量
export DOCKER_BUILDKIT=1
docker build .

# 方式2：使用 docker buildx
docker buildx build .

# 方式3：在 Docker 配置中全局启用
# /etc/docker/daemon.json
{
  "features": {
    "buildkit": true
  }
}
```

**BuildKit 相比传统构建引擎的优势**：
- 并行构建互不依赖的阶段
- 缓存挂载（`--mount=type=cache`）跨构建复用
- `COPY --link` 创建独立缓存层
- 秘密挂载（`--mount=type=secret`）安全传递构建密钥
- 更精细的构建日志（`--progress=plain`）

### 7.2 使用 BuildKit 缓存挂载

```dockerfile
# syntax=docker/dockerfile:1

FROM python:3.12-slim

# pip 缓存挂载（跨构建复用）
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# apt 缓存挂载
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update &amp;&amp; apt-get install -y gcc
```

**缓存挂载的工作原理**：`--mount=type=cache` 将指定路径挂载为持久化缓存目录。即使构建失败或基础镜像更新，缓存目录的内容仍然保留。下次构建时，包管理器可以复用已下载的包，避免重复下载。注意缓存挂载的目录不会进入镜像层。

### 7.3 COPY --link 实现独立缓存

`COPY --link`（需要 BuildKit）创建独立的层，不依赖前序层的缓存状态：

```dockerfile
# syntax=docker/dockerfile:1

# 基础层
FROM python:3.12-slim

# --link 使复制操作独立于前序层
COPY --link requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 即使基础层变化，这里的复制仍然可以使用缓存
COPY --link . /app
```

### 7.4 优化 apt 安装

```dockerfile
# ❌ 安装不必要的推荐包
RUN apt-get update &amp;&amp; apt-get install -y curl

# ✅ 仅安装必要依赖
RUN apt-get update &amp;&amp; \
    apt-get install -y --no-install-recommends curl &amp;&amp; \
    rm -rf /var/lib/apt/lists/*
```

**`--no-install-recommends` 的效果**：以 `curl` 为例，不加此标志会额外安装约 15 个推荐包（共约 30MB），加上后仅安装 curl 本身及其硬依赖（约 5MB）。

### 7.5 并行构建多个阶段

BuildKit 会自动并行构建互不依赖的阶段：

```dockerfile
# 这两个阶段可以并行构建
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/ .
RUN npm ci &amp;&amp; npm run build

FROM python:3.12-slim AS backend-build
WORKDIR /backend
COPY backend/ .
RUN pip install -r requirements.txt

# 最终阶段依赖前两个阶段的输出
FROM python:3.12-slim
COPY --from=frontend-build /frontend/dist /app/public
COPY --from=backend-build /backend /app
```

### 7.6 利用 BuildKit 的构建秘密挂载

当构建过程中需要认证信息（如私有包仓库的 token），不要使用 ARG 或 ENV（会残留在镜像层中），而是使用 BuildKit 的 secret 挂载：

```dockerfile
# syntax=docker/dockerfile:1

# 从 --secret 挂载 pip 配置（含认证 token）
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf \
    pip install -r requirements.txt

# 从 --secret 挂载 SSH key（用于拉取私有 Git 仓库）
RUN --mount=type=ssh \
    git clone git@github.com:private/repo.git
```

构建时使用 `--ssh default` 或 `--secret id=pip_conf,src=./pip.conf` 传递密钥，密钥不会保留在最终镜像中。

---

## 8. 常见反模式与纠正

| 反模式 | 问题 | 正确做法 |
|--------|------|----------|
| `FROM ubuntu`（无版本号） | 构建不可复现，安全风险 | `FROM ubuntu:22.04` |
| 多条 `RUN apt-get update` 分开 | 每层独立缓存，包列表可能过期 | 合并为一条 `RUN` 并立即清理 |
| `COPY . .` 放在最前面 | 任何文件变化都导致后续缓存失效 | 先复制依赖文件，再安装，最后复制代码 |
| 在 Dockerfile 中 `ENV PASSWORD=xxx` | 密钥永久存在于镜像层 | 运行时通过 `-e` 或 secrets 注入 |
| 以 root 运行应用 | 容器逃逸可获得宿主机 root 权限 | 使用 `USER` 指令切换到非 root 用户 |
| 使用 `ADD` 复制普通文件 | ADD 的隐式行为（自动解压）造成混淆 | 大多数场景使用 `COPY` |
| 未使用 `.dockerignore` | 构建上下文臃肿，缓存频繁失效 | 配置完整的 `.dockerignore` 文件 |
| 每条指令创建一个 RUN 层 | 镜像体积膨胀，删除操作无效 | 合并相关 RUN 指令为一条 |
| 使用 `latest` 标签 | 基础镜像不确定，构建不可复现 | 使用具体的版本标签如 `3.12.4-slim` |
| 不设置 HEALTHCHECK | 编排系统无法判断容器健康状态 | 添加 HEALTHCHECK 指令 |
| `RUN apt-get install` 不加 `--no-install-recommends` | 安装大量不必要的推荐包 | 添加 `--no-install-recommends` |
| 在 `RUN cd /app && ...` 后期望目录持久 | `RUN` 内的 cd 不影响后续指令 | 使用 `WORKDIR` 设置工作目录 |
| 在 shell 形式中使用 ENTRYPOINT | 应用进程不是 PID 1，无法接收信号 | 使用 exec 形式 `ENTRYPOINT ["cmd"]` |

---

## 9. 实战案例

### 9.1 Python Web 应用 (Flask)

**优化前**（体积约 980MB，构建慢）：
```dockerfile
FROM python:3.12
RUN apt-get update
RUN apt-get install -y gcc python3-dev
RUN pip install flask gunicorn psycopg2-binary
RUN pip install -r requirements.txt
COPY . /app
WORKDIR /app
EXPOSE 8000
CMD python -m gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

**优化后**（体积约 130MB，构建快）：
```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装编译依赖
RUN apt-get update &amp;&amp; \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libpq-dev &amp;&amp; \
    rm -rf /var/lib/apt/lists/*

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# ========== 运行阶段 ==========
FROM python:3.12-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update &amp;&amp; \
    apt-get install -y --no-install-recommends libpq5 &amp;&amp; \
    rm -rf /var/lib/apt/lists/*

# 复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制应用代码
COPY . .

# 非 root 运行
RUN useradd --create-home appuser &amp;&amp; \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
```

### 9.2 Node.js 应用

**优化前**（体积约 1.1GB）：
```dockerfile
FROM node:20
WORKDIR /app
COPY . .
RUN npm install
RUN npm run build
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

**优化后**（体积约 180MB）：
```dockerfile
# syntax=docker/dockerfile:1

# ========== 依赖安装阶段 ==========
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production &amp;&amp; \
    npm cache clean --force

# ========== 构建阶段 ==========
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ========== 运行阶段 ==========
FROM node:20-alpine

RUN apk add --no-cache tini
WORKDIR /app

# 设置 Node.js 为生产模式
ENV NODE_ENV=production

# 从构建阶段复制生产依赖和构建产物
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./

# 非 root 运行
RUN addgroup -S appgroup &amp;&amp; \
    adduser -S appuser -G appgroup
USER appuser

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -qO- http://localhost:3000/health || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "dist/server.js"]
```

**关键优化点**：
- 使用 Alpine 基础镜像（约 50MB vs 标准 Node 镜像约 900MB）
- 多阶段构建分离依赖安装和代码构建
- 使用 `npm ci` 替代 `npm install`（更快、更确定，严格按 lock 文件安装）
- 使用 `tini` 作为 PID 1 处理信号转发和僵尸进程回收
- 设置 `NODE_ENV=production` 禁用开发模式的调试功能

### 9.3 Go 微服务

**优化前**（体积约 800MB）：
```dockerfile
FROM golang:1.22
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o server .
CMD ["./server"]
```

**优化后**（体积约 12MB）：
```dockerfile
# syntax=docker/dockerfile:1

# ========== 构建阶段 ==========
FROM golang:1.22-alpine AS builder

RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /app

# 利用缓存：先复制依赖文件
COPY go.mod go.sum ./
RUN go mod download

# 复制源代码
COPY . .

# 交叉编译静态二进制
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build \
    -ldflags="-s -w -X main.version=$(cat VERSION)" \
    -o /server .

# ========== 运行阶段 ==========
FROM scratch

# 从构建阶段复制必要文件
COPY --from=builder /server /server
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo

# 复制配置文件（如果有）
COPY --from=builder /app/configs/ /configs/

EXPOSE 8080

ENTRYPOINT ["/server"]
```

**关键优化点**：
- 最终镜像基于 `scratch`（0MB），仅包含静态二进制文件和必要证书
- 使用 `-ldflags="-s -w"` 去除调试符号和 DWARF 信息
- `CGO_ENABLED=0` 确保纯静态编译
- 复制 CA 证书（HTTPS 调用需要）和时区数据（时间处理需要）到 scratch 镜像中
- `-X main.version=$(cat VERSION)` 在编译时注入版本号

---

## 10. 诊断与调试

### 10.1 docker history —— 查看镜像层

```bash
# 查看镜像的所有层及其大小
docker history myapp:latest

# 输出示例：
# IMAGE          CREATED       CREATED BY                                      SIZE      COMMENT
# a1b2c3d4e5f6   2 min ago     CMD ["gunicorn" "-w" "4" ...]                 0B        buildkit
# <missing>      2 min ago     USER appuser                                   0B        buildkit
# <missing>      2 min ago     COPY . .                                       15.3kB    buildkit
# <missing>      5 min ago     RUN |1 PIP_NO_CACHE_DIR=1 pip install -r ...  85.2MB    buildkit
# <missing>      5 min ago     COPY requirements.txt .                       1.2kB     buildkit
# <missing>      10 min ago    WORKDIR /app                                   0B        buildkit
# <missing>      2 weeks ago   /bin/sh -c #(nop)  FROM python:3.12-slim     72.4MB
```

### 10.2 构建过程详细日志

```bash
# 使用 BuildKit 查看完整的构建命令输出
DOCKER_BUILDKIT=1 docker build --progress=plain -t myapp .

# 仅查看失败步骤的输出
docker build --progress=plain --no-cache .
```

### 10.3 hadolint —— Dockerfile 静态分析

```bash
# 安装 hadolint
# macOS
brew install hadolint

# Linux
wget -O /usr/local/bin/hadolint \
    https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64
chmod +x /usr/local/bin/hadolint

# 检查 Dockerfile
hadolint Dockerfile

# 输出示例：
# Dockerfile:3 DL3008 Pin versions in apt get install
# Dockerfile:5 DL3009 Delete the apt-get lists after installing
# Dockerfile:7 DL3059 Multiple consecutive `RUN` instructions
# Dockerfile:10 DL3003 Use WORKDIR to switch to a directory
```

**常用 hadolint 规则速查**：

| 规则 | 严重度 | 说明 |
|------|--------|------|
| DL3006 | warning | 始终为 COPY --from 指定阶段名或索引 |
| DL3008 | warning | apt-get install 中固定版本号 |
| DL3009 | info | 安装后删除 apt-get lists |
| DL3003 | warning | 使用 WORKDIR 而非 RUN cd |
| DL3006 | warning | 始终为 COPY --from 指定阶段名或索引 |
| DL3015 | info | 使用 --no-install-recommends |
| DL3025 | warning | 使用 JSON 格式的 CMD/ENTRYPOINT |
| DL3059 | info | 多个连续 RUN 指令可合并 |

在 CI/CD 中集成：
```yaml
# .github/workflows/lint.yml
- name: Lint Dockerfile
  uses: hadolint/hadolint-action@v3.1.0
  with:
    dockerfile: Dockerfile
    failure-threshold: warning
```

### 10.4 dive —— 镜像层可视化分析

```bash
# 安装 dive
brew install dive  # macOS
# 或
wget https://github.com/wagoodman/dive/releases/download/v0.12.0/dive_0.12.0_linux_amd64.deb
sudo dpkg -i dive_0.12.0_linux_amd64.deb

# 分析镜像
dive myapp:latest

# CI 模式：自动检测浪费的空间
CI=true dive myapp:latest --highestImageEfficiency=0.95
```

dive 提供交互式界面，可以逐层查看每个层添加的文件，并计算镜像空间利用率。当发现某一层添加了大量无用文件时，可以直接定位到 Dockerfile 中对应的指令进行优化。

### 10.5 docker diff —— 查看容器文件系统变更

```bash
# 查看容器运行后相对于基础镜像的变化
docker diff mycontainer

# 输出说明：
# A /tmp/test.log        (Added - 新增的文件)
# C /app/config.yaml     (Changed - 修改的文件)
# D /app/old_cache.dat   (Deleted - 删除的文件)
```

### 10.6 调试技巧合集

```bash
# 1. 进入构建中间层进行调试
docker build --target builder -t myapp:debug .
docker run -it myapp:debug /bin/bash

# 2. 使用 BuildKit 的调试挂载
# syntax=docker/dockerfile:1
RUN --mount=type=cache,target=/app/cache \
    --mount=type=bind,source=./,target=/src \
    echo "Debug: files in /src" &amp;&amp; ls /src

# 3. 检查镜像元数据
docker inspect myapp:latest

# 4. 导出镜像文件系统进行检查
docker save myapp:latest | tar -tf - | head -50

# 5. 使用 docker run 的 --entrypoint 覆盖启动命令
docker run -it --entrypoint /bin/sh myapp:latest
```

---

## 11. 信号处理与优雅关闭

容器化应用的优雅关闭是生产部署中的关键问题。理解 Linux 信号机制和容器的 PID 1 问题，可以避免数据丢失和服务中断。

### 11.1 容器中的信号传递机制

当执行 `docker stop` 时，Docker 引擎首先向容器的 PID 1 进程发送 SIGTERM 信号，等待一段宽限期（默认 10 秒），如果进程仍未退出，则发送 SIGKILL 强制终止。

**PID 1 的特殊性**：在 Linux 中，PID 1 进程对未显式注册处理函数的信号有特殊行为——SIGTERM 默认被忽略。这意味着如果你的应用以 exec 形式作为 PID 1 运行但未注册 SIGTERM 处理，`docker stop` 会等待 10 秒后被 SIGKILL 强制终止。

### 11.2 tini 的使用

```dockerfile
RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "app.py"]]
```

tini 作为轻量级 init 进程解决了两个问题：
1. 正确转发信号给子进程
2. 回收僵尸进程（应用 fork 子进程后未正确 wait 的情况）

### 11.3 应用层面的最佳实践

```python
# Python 示例：优雅关闭
import signal
import sys

def graceful_shutdown(signum, frame):
    print("Received SIGTERM, shutting down gracefully...")
    server.shutdown()  # 停止接受新连接
    server.close_all()  # 关闭现有连接
    sys.exit(0)

signal.signal(signal.SIGTERM, graceful_shutdown)
```

**关键原则**：应用必须在收到 SIGTERM 后主动关闭资源（数据库连接、文件句柄、消息队列消费者），而不是依赖 SIGKILL。

---

## 12. 企业级 Dockerfile 规范

在大型团队中维护一致的 Dockerfile 规范至关重要。以下是经过生产验证的企业级规范：

**规范一：强制多阶段构建**。所有生产环境镜像必须使用多阶段构建，将构建环境与运行环境彻底分离。

**规范二：固定所有外部依赖版本**。包括基础镜像的精确版本号、系统包的精确版本、以及应用依赖的锁定文件。禁止使用浮动标签（如 `latest`、`stable`），在 CI 中使用镜像哈希引用基础镜像。

**规范三：标准化元数据标签**。遵循 OCI 标准标签规范，为所有镜像添加标准化的元数据标签，包括维护者信息、版本号、构建时间、源代码仓库地址、许可证信息等。

**规范四：强制安全扫描**。在 CI/CD 流水线中集成 Trivy 或 Grype，对每次构建的镜像进行漏洞扫描。高危和严重漏洞必须在合并到主分支前修复。

**规范五：最小权限原则**。所有生产容器必须以非 root 用户运行。对于需要绑定特权端口（小于 1024）的应用，优先考虑端口映射或 setcap 而非以 root 运行。

**规范六：健康检查必须配置**。每个面向生产的服务镜像都必须包含 HEALTHCHECK 指令，健康检查端点应该轻量快速。

**规范七：日志与监控友好**。确保应用将日志输出到 stdout 和 stderr 而非文件，确保应用响应 SIGTERM 信号。

**规范八：CI/CD 集成**。Dockerfile 的 lint（hadolint）、安全扫描（trivy）、镜像体积检查（dive）必须集成到 CI 流水线中，作为合并门禁的一部分。

---

## 13. 常见语言栈速查

以下速查表汇总了主流编程语言的推荐 Dockerfile 模式：

**Python Web 应用**：使用 `python:X.Y-slim` 作为基础镜像，多阶段构建中在构建阶段使用完整的编译工具链安装 C 扩展依赖，在运行阶段仅复制虚拟环境。使用 `--no-cache-dir` 避免 pip 缓存占用空间。

**Node.js 应用**：使用 `node:X.Y-alpine` 作为基础镜像，分别使用 `npm ci --only=production` 安装生产依赖和 `npm ci` 安装全部依赖，通过多阶段构建将两者分离。使用 `tini` 作为 init 进程处理信号转发。

**Go 微服务**：使用 `golang:X.Y-alpine` 作为构建阶段基础镜像，`scratch` 或 `gcr.io/distroless/static` 作为运行阶段基础镜像。编译时使用 `CGO_ENABLED=0` 确保静态编译，使用 `-ldflags="-s -w"` 去除调试信息。需要手动复制 CA 证书和时区数据。

**Java 应用**：使用 `eclipse-temurin:X.Y-jre-alpine` 作为运行时基础镜像，使用 `eclipse-temurin:X.Y-jdk-alpine` 作为构建阶段。通过分层 JAR（Spring Boot 3.2+）或 Maven/Gradle 依赖缓存优化构建速度。Java 应用的内存设置需要考虑容器的内存限制，使用 `-XX:+UseContainerSupport` 确保 JVM 正确感知容器资源。

**Rust 应用**：使用 `rust:X.Y-slim` 作为构建阶段，`debian:bookworm-slim` 或 `scratch` 作为运行阶段。利用 Rust 的 `--release` 标志进行优化编译。注意 Rust 编译过程需要大量内存和时间，可以使用 `cargo-chef` 工具缓存依赖编译结果，显著加速后续构建。

**静态二进制（C/C++）**：使用 `gcc:X.Y` 或 `musl` 工具链作为构建阶段，`scratch` 作为运行阶段。通过静态链接（`-static`）确保二进制文件不依赖动态链接库，使得最终镜像可以使用完全空白的 scratch 基础镜像，达到最小的镜像体积。

---

## 总结

编写高质量的 Dockerfile 需要综合考虑构建效率、镜像体积、安全性和可维护性。本章总结的核心原则包括：

1. **精简指令**：合并 RUN 指令，在同一层完成安装和清理
2. **利用缓存**：将变化频率低的操作放在前面，先复制依赖文件再安装
3. **多阶段构建**：分离构建环境和运行环境，只保留运行时必需的文件
4. **安全优先**：使用具体版本标签、非 root 用户运行、最小基础镜像、不存储密钥
5. **持续诊断**：使用 hadolint、dive 等工具持续监控镜像质量
6. **信号感知**：使用 exec 形式 ENTRYPOINT、tini init 进程，确保优雅关闭
7. **团队规范**：建立并执行企业级 Dockerfile 规范，集成到 CI/CD 流水线

掌握这些最佳实践，将帮助你构建出更小、更快、更安全的 Docker 镜像，为容器化应用的生产部署打下坚实的基础。

---

*本章通过系统性的讲解和丰富的实战案例，全面覆盖了 Dockerfile 编写的核心知识点和最佳实践。掌握这些内容将帮助开发者构建出高效、安全、可维护的容器镜像，为容器化应用的生产部署奠定坚实的基础。建议读者在实际项目中逐步应用这些实践，并结合团队需求制定适合自身的 Dockerfile 编写规范。*
