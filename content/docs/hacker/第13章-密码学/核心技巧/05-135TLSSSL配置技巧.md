---
title: "13.5 TLS/SSL配置技巧"
type: docs
weight: 5
---

## 13.5 TLS/SSL 配置技巧

TLS（Transport Layer Security）是互联网安全通信的基石。从网上银行到即时通讯，从 API 调用到邮件传输，几乎所有涉及敏感数据的网络通信都依赖 TLS 提供机密性、完整性和身份验证。错误的 TLS 配置是导致数据泄露的最常见原因之一——不是加密算法不够强，而是配置出了问题。本节从协议原理出发，覆盖版本选择、密码套件配置、证书管理、服务器加固、性能优化和安全审计的完整链条。

### 13.5.1 TLS 协议演进与版本选择

#### 协议历史

理解 TLS 各版本的差异是做出正确配置决策的前提。

| 版本 | 发布年份 | 状态 | 核心问题 |
|------|----------|------|----------|
| SSL 2.0 | 1995 | **已废弃** | 无握手保护，多种已知攻击（DROWN） |
| SSL 3.0 | 1996 | **已废弃** | POODLE 攻击，CBC 填充预言 |
| TLS 1.0 | 1999 | **已废弃（2021 RFC 8996）** | BEAST 攻击，弱 MAC-then-Encrypt |
| TLS 1.1 | 2006 | **已废弃（2021 RFC 8996）** | 明文 IV，无 AEAD 支持 |
| TLS 1.2 | 2008 | **当前最低安全版本** | 支持 AEAD，SHA-256，可安全配置 |
| TLS 1.3 | 2018 | **推荐版本** | 1-RTT 握手，移除不安全算法，0-RTT 恢复 |

#### 为什么必须禁用旧版本

旧版本协议的漏洞不是"理论上可能被攻击"，而是"已有公开的实用攻击工具"：

- **POODLE（SSL 3.0）**：攻击者可利用 CBC 模式填充，以约 256 次请求/字节的速度解密 Cookie 等敏感数据
- **BEAST（TLS 1.0）**：利用 CBC 模式的 IV 预测问题，可窃取 HTTPS Cookie
- **DROWN（SSL 2.0）**：即使服务器仅支持 TLS，只要同一私钥曾用于 SSL 2.0，攻击者即可解密 TLS 会话
- **Raccoon（TLS 1.2 DH）**：利用 DH 密钥交换中 timing side-channel，可恢复预主密钥

#### 推荐配置策略

```nginx
# Nginx — 仅允许 TLS 1.2 和 1.3
ssl_protocols TLSv1.2 TLSv1.3;
```

```apache
# Apache — 仅允许 TLS 1.2 和 1.3
SSLProtocol -all +TLSv1.2 +TLSv1.3
```

```text
# HAProxy
ssl-default-bind-options ssl-min-ver TLSv1.2
ssl-default-bind-options no-sslv3 no-tlsv10 no-tlsv11
```

**关于 TLS 1.3 的 0-RTT 恢复**：TLS 1.3 引入了 0-RTT（Early Data）机制，允许客户端在握手第一个消息中就携带应用数据。这降低了延迟，但 0-RTT 数据没有前向保密保护，且可能遭受重放攻击。对于幂等请求（GET）风险较低，但绝不应在非幂等操作（POST、支付）中接受 0-RTT：

```nginx
# 如果安全需求高，禁用 0-RTT
ssl_early_data off;
```

### 13.5.2 密码套件选择与配置

密码套件（Cipher Suite）定义了 TLS 握手的四个关键组件：密钥交换算法、身份验证算法、批量加密算法和 MAC/哈希算法。选择不当会同时破坏安全性和性能。

#### TLS 1.3 密码套件

TLS 1.3 大幅简化了套件选择——仅保留 5 个套件，全部使用 AEAD 模式，密钥交换固定为 ECDHE 或 DHE：

```text
# TLS 1.3 完整套件列表（按推荐顺序）
TLS_AES_256_GCM_SHA384        # 256-bit AES-GCM，首选
TLS_CHACHA20_POLY1305_SHA256   # ChaCha20，适合无 AES-NI 的设备
TLS_AES_128_GCM_SHA256         # 128-bit AES-GCM，兼容性最好
TLS_AES_128_CCM_SHA256         # CCM 模式，嵌入式设备
TLS_AES_128_CCM_8_SHA256       # CCM-8 模式，8 字节 tag
```

**AES-GCM vs ChaCha20-Poly1305 的选择逻辑**：

| 维度 | AES-256-GCM | ChaCha20-Poly1305 | AES-128-GCM |
|------|------------|-------------------|------------|
| 安全强度 | 256-bit | 256-bit | 128-bit |
| 硬件加速 | AES-NI | 纯软件优秀 | AES-NI |
| 无 AES-NI 性能 | 慢 3-5x | **最快** | 慢 3-5x |
| 移动设备推荐 | 服务器端 | **客户端首选** | 服务器端 |
| 认证标签长度 | 128-bit | 128-bit | 128-bit |

实操建议：服务器有 AES-NI 时优先 AES-256-GCM；面向移动客户端时将 ChaCha20 排在前面。

#### TLS 1.2 密码套件

TLS 1.2 需要更严格的筛选，因为它的套件列表包含大量不安全组合。

**推荐套件（按优先级排序）**：

```text
# 强密码套件 — TLS 1.2
ECDHE-ECDSA-AES256-GCM-SHA384
ECDHE-RSA-AES256-GCM-SHA384
ECDHE-ECDSA-CHACHA20-POLY1305
ECDHE-RSA-CHACHA20-POLY1305
ECDHE-ECDSA-AES128-GCM-SHA256
ECDHE-RSA-AES128-GCM-SHA256
```

**必须排除的算法模式**：

| 排除项 | 原因 | 攻击示例 |
|--------|------|----------|
| CBC 模式 | Padding Oracle 攻击面大 | BEAST, Lucky13, POODLE |
| RC4 | 流密码偏差，可统计恢复明文 | RC4 NOMORE |
| 3DES | Sweet32 攻击（64-bit 块大小） | Sweet32 |
| RSA 密钥交换 | 无前向保密，私钥泄露=全部会话解密 | Logjam, Heartbleed 余波 |
| NULL / EXPORT | 不加密 | — |
| MD5 / SHA-1 | 哈希碰撞 | SLOTH |

**前向保密（Forward Secrecy）是关键要求**：使用 ECDHE 或 DHE 密钥交换，确保即使服务器长期私钥泄露，历史会话仍不可解密。RSA 密钥交换（`RSA` 而非 `ECDHE-RSA`）意味着预主密钥用服务器 RSA 公钥加密——一旦私钥被窃（如 Heartbleed），攻击者可解密所有历史流量。

#### 各服务器配置示例

**Nginx**：

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
ssl_prefer_server_ciphers on;

# TLS 1.3 套件单独配置（Nginx 1.19.4+）
ssl_conf_command Ciphersuites TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256;
```

**Apache**：

```apache
SSLProtocol -all +TLSv1.2 +TLSv1.3
SSLCipherSuite ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305
SSLHonorCipherOrder on
SSLCompression off
```

**HAProxy**：

```text
ssl-default-bind-ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305
ssl-default-bind-ciphersuites TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256
ssl-default-bind-options prefer-client-ciphers ssl-min-ver TLSv1.2
```

**Go 语言应用**：

```go
tlsConfig := &tls.Config{
    MinVersion: tls.VersionTLS12,
    CurvePreferences: []tls.CurveID{
        tls.X25519,
        tls.CurveP256,
        tls.CurveP384,
    },
    CipherSuites: []uint16{
        tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
        tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
        tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
        tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
    },
    PreferServerCipherSuites: true,
}
```

### 13.5.3 椭圆曲线选择

TLS 1.3 强制使用 ECDHE，曲线选择直接影响安全性和性能。

| 曲线 | 密钥长度 | 速度 | 安全评估 | 推荐 |
|------|----------|------|----------|------|
| X25519 | 256-bit | **最快** | 高（非 NIST 曲线，无后门嫌疑） | **首选** |
| P-256 (secp256r1) | 256-bit | 快（硬件加速） | 高（NIST 标准） | 推荐 |
| P-384 (secp384r1) | 384-bit | 中 | 高 | 合规场景 |
| P-521 (secp521r1) | 521-bit | 慢 | 极高 | 高安全需求 |
| secp256k1 | 256-bit | 快 | 高（比特币曲线） | 特殊场景 |

```nginx
# Nginx 曲线配置
ssl_ecdh_curve X25519:P-256:P-384;
```

**为什么 X25519 是首选**：X25519 由 Daniel Bernstein 设计，具有常数时间实现（抗侧信道攻击）、无需随机数生成（抗 RNG 故障）、实现简洁（不易出错）等优势。其安全强度相当于 AES-128，对绝大多数场景已足够。

### 13.5.4 证书管理最佳实践

证书是 TLS 身份验证的核心。配置再好的密码套件，如果证书管理不当，整个安全体系依然形同虚设。

#### 证书链完整性

服务器必须发送完整的证书链（服务器证书 + 所有中间 CA 证书），但**不包含根 CA 证书**（根证书由客户端本地信任库提供）。

```bash
# 验证证书链完整性
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>/dev/null | \
  openssl x509 -noout -subject -issuer -dates

# 检查证书链深度
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>&1 | \
  grep "depth="
```

**常见错误**：遗漏中间证书。这在部分客户端（如 Android 旧版本）上会导致握手失败，而在浏览器上可能正常——因为浏览器会尝试自动下载缺失的中间证书。应始终配置完整链。

```nginx
# Nginx — 合并证书链
# 顺序：服务器证书 → 中间CA1 → 中间CA2 → ...
cat server.crt intermediate1.crt intermediate2.crt > fullchain.crt
ssl_certificate /etc/nginx/ssl/fullchain.crt;
ssl_certificate_key /etc/nginx/ssl/server.key;
```

#### 密钥生成与保护

```bash
# 生成 ECDSA P-256 私钥（推荐，更快更小）
openssl ecparam -genkey -name prime256v1 -noout -out server.key

# 或生成 RSA 4096-bit 私钥（兼容性更好）
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out server.key

# 设置严格权限
chmod 600 server.key
chown root:root server.key
```

**RSA vs ECDSA 证书选择**：

| 维度 | RSA 4096 | ECDSA P-256 |
|------|----------|-------------|
| 签名速度 | 慢（约 10ms） | **快（约 1ms）** |
| 证书大小 | ~2KB | ~0.5KB |
| 握手性能 | 较慢 | **快 3-5 倍** |
| 客户端兼容性 | 100% | 99%+（IE6 不支持） |
| 推荐场景 | 需要兼容极旧客户端 | **绝大多数场景** |

**双证书部署**（同时配置 RSA 和 ECDSA）可兼顾性能和兼容性：

```nginx
# Nginx 双证书（1.11.0+）
ssl_certificate /path/to/ecdsa/fullchain.pem;
ssl_certificate_key /path/to/ecdsa/privkey.pem;

# 次选 RSA 证书
ssl_certificate /path/to/rsa/fullchain.pem;
ssl_certificate_key /path/to/rsa/privkey.pem;
```

Nginx 会根据客户端支持的签名算法自动选择合适的证书。

#### 证书透明度（Certificate Transparency）

CT 要求所有公开信任的 CA 将颁发的证书提交到公开的、可审计的日志中。这使得任何人都能监控某个域名的证书颁发情况，及时发现未授权证书。

- 所有主流浏览器已要求 CT 日志（Chrome 自 2018 年起）
- 使用 [crt.sh](https://crt.sh) 可查询任何域名的 CT 日志记录
- 设置 CT 监控告警，发现未预期的证书颁发立即调查

```bash
# 查询域名的 CT 日志
curl -s "https://crt.sh/?q=example.com&output=json" | jq '.[] | {issuer: .issuer_name, not_before: .not_before, not_after: .not_after}'
```

#### OCSP Stapling

OCSP（Online Certificate Status Protocol）用于检查证书是否被吊销。传统方式下，客户端需要单独向 CA 的 OCSP 服务器查询，增加了握手延迟并泄露用户浏览记录。OCSP Stapling 让服务器预先获取并缓存 OCSP 响应，在 TLS 握手时一并发送给客户端。

```nginx
# Nginx 启用 OCSP Stapling
ssl_stapling on;
ssl_stapling_verify on;
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 5s;
ssl_trusted_certificate /path/to/chain.pem;  # 包含中间CA的完整链
```

```bash
# 验证 OCSP Stapling 是否生效
openssl s_client -connect example.com:443 -servername example.com -status </dev/null 2>&1 | grep "OCSP Response Status"
# 期望输出: OCSP Response Status: successful (0x0)
```

**OCSP Stapling 的局限性**：CA 的 OCSP 服务器可能不可用或响应缓慢。Nginx 会在获取失败时使用缓存的旧响应（可配置缓存时间）。此外，隐私关注的用户可能更倾向于使用 CRLite 或类似的本地证书吊销检查方案。

#### 自动化证书管理

手动管理证书容易出期导致服务中断或安全事件。Let's Encrypt + Certbot 是最广泛使用的免费证书自动化方案：

```bash
# 安装 Certbot
apt install certbot python3-certbot-nginx  # Debian/Ubuntu
# 或
dnf install certbot python3-certbot-nginx  # RHEL/Fedora

# 首次申请证书并自动配置 Nginx
certbot --nginx -d example.com -d www.example.com

# 自动续期（通常 cron/systemd timer 已自动配置）
certbot renew --dry-run

# 手动续期测试
certbot renew --force-renewal
```

**企业环境推荐方案**：

- **小型部署**：Certbot + Let's Encrypt（免费，90天有效期，自动续期）
- **中型部署**：ACME 协议集成（如 acme.sh，支持更多 DNS 提供商）
- **大型部署**：HashiCorp Vault PKI、Smallstep CA 或 AWS Private CA
- **内部服务**：自建 CA + 自动化分发（Smallstep、cfssl）

### 13.5.5 安全加固配置

#### HSTS（HTTP Strict Transport Security）

HSTS 告诉浏览器：在指定时间内，对该域名的所有请求都必须使用 HTTPS，即使用户手动输入 http:// 也不降级。这有效防止了 SSL 剥离攻击（如 sslstrip）。

```nginx
# Nginx HSTS 配置
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
```

**参数说明**：
- `max-age=63072000`：有效期 2 年（以秒计）。首次部署建议从短时间开始（如 300 秒），逐步增加
- `includeSubDomains`：对所有子域名生效。确认所有子域名已支持 HTTPS 后才开启
- `preload`：允许加入浏览器预加载列表。一旦加入难以撤回，请确认所有条件满足后再提交

提交到 HSTS 预加载列表：[hstspreload.org](https://hstspreload.org)。加入后，主流浏览器内置该域名的 HSTS 规则，即使是首次访问也会强制 HTTPS。

#### HTTP 公钥固定（HPKP）— 已废弃

HPKP 曾允许网站声明哪些公钥可用于未来的证书验证。由于配置错误会导致网站被"锁定"无法访问（bricking），Chrome 已于 2018 年移除支持。**不要再使用 HPKP**。替代方案是使用 `Expect-CT` 头或依赖 CT 日志监控。

#### 安全响应头

```nginx
# 组合安全头配置
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```

#### TLS 压缩禁用

TLS 压缩（Compression）存在 CRIME 攻击风险——攻击者可通过观察压缩后的数据大小推断明文内容。必须禁用：

```nginx
ssl_compression off;  # Nginx 默认已关闭
```

```apache
SSLCompression off  # Apache
```

#### 安全重协商

TLS 重协商（Renegotiation）历史上存在严重漏洞（CVE-2009-3555）。现代实现已修复，但仍应确保使用安全重协商：

```bash
# 检查是否支持安全重协商
openssl s_client -connect example.com:443 </dev/null 2>&1 | grep "Secure Renegotiation"
# 期望: Secure Renegotiation IS supported
```

#### Session 管理

TLS 会话恢复（Session Resumption）避免完整握手的开销，但实现不当会削弱安全性：

**Session Tickets**：
```nginx
# 启用 session tickets（默认开启）
ssl_session_tickets on;

# 设置 ticket 密钥轮换（关键！长期不轮换 ticket key 会削弱前向保密）
# Nginx 不原生支持自动轮换，需要外部脚本定期更新
# 建议使用 OpenSSL 的自动 ticket key 名称功能
ssl_session_ticket_key /path/to/current.key;
ssl_session_ticket_key /path/to/previous.key;
```

**Session Cache**：
```nginx
ssl_session_cache shared:SSL:50m;  # 50MB 共享缓存，约 200K 会话
ssl_session_timeout 1d;             # 会话有效期 1 天
```

**安全考量**：Session Tickets 使用服务器端密钥加密会话状态。如果该密钥不轮换，拥有该密钥的攻击者可解密所有使用该 ticket 的会话，破坏前向保密。建议每 1-24 小时轮换一次 ticket key。

### 13.5.6 性能优化

TLS 握手是性能瓶颈之一，优化得当可显著降低延迟和 CPU 开销。

#### TLS 1.3 的性能优势

TLS 1.3 将握手从 2-RTT 减少到 1-RTT：

```text
TLS 1.2 握手（2-RTT）:
  Client → Server:  ClientHello
  Client ← Server:  ServerHello, Certificate, ServerKeyExchange, ServerHelloDone
  Client → Server:  ClientKeyExchange, ChangeCipherSpec, Finished
  Client ← Server:  ChangeCipherSpec, Finished
  --- 握手完成，开始传输数据 ---

TLS 1.3 握手（1-RTT）:
  Client → Server:  ClientHello, KeyShare
  Client ← Server:  ServerHello, KeyShare, EncryptedExtensions, Certificate, CertificateVerify, Finished
  --- 握手完成，开始传输数据 ---
```

#### Session 复用

合理配置 Session Cache 和 Session Tickets 可将恢复握手降至 0-RTT（TLS 1.3）或 1-RTT（TLS 1.2）。

#### 硬件加速

```bash
# 检查 CPU 是否支持 AES-NI
grep -o aes /proc/cpuinfo | head -1
# 输出 "aes" 表示支持

# 检查 OpenSSL 是否使用了硬件加速
openssl speed -elapsed aes-256-gcm 2>&1 | head -5
```

- **AES-NI**：Intel/AMD 处理器的 AES 指令集，AES-GCM 性能提升 3-10 倍
- **无 AES-NI 时**：优先使用 ChaCha20-Poly1305（纯软件实现更快）
- **SSL 卸载**：高流量场景可使用专用硬件（如 F5、A10）或云服务商的 SSL 卸载服务

#### OCSP Stapling 性能影响

不使用 OCSP Stapling 时，浏览器需要单独连接 CA 的 OCSP 服务器验证证书状态，额外增加 300-1000ms 延迟。启用 Stapling 后，验证数据随握手一起返回，零额外延迟。

### 13.5.7 安全审计与监控

#### 在线测试工具

| 工具 | 地址 | 用途 |
|------|------|------|
| SSL Labs | ssllabs.com/ssltest | 综合评分 A+ 到 F |
| testssl.sh | github.com/drwetter/testssl.sh | 命令行全面检测 |
| Hardenize | hardenize.com | 含邮件、DNS 在内的综合评估 |
| Observatory | observatory.mozilla.org | HTTP 安全头 + TLS 综合检查 |

#### testssl.sh 实战

```bash
# 安装
git clone --depth 1 https://github.com/drwetter/testssl.sh.git
cd testssl.sh

# 快速检测
./testssl.sh example.com

# 仅检测密码套件
./testssl.sh --cipher-per-proto example.com

# 检测特定端口
./testssl.sh --sni example.com:8443

# 输出 JSON 报告
./testssl.sh --jsonfile report.json example.com
```

#### OpenSSL 手动检测

```bash
# 测试特定 TLS 版本
openssl s_client -connect example.com:443 -tls1_2 </dev/null
openssl s_client -connect example.com:443 -tls1_3 </dev/null

# 列出服务器支持的密码套件（需要 nmap）
nmap --script ssl-enum-ciphers -p 443 example.com

# 检查证书详细信息
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | openssl x509 -noout -text

# 验证私钥与证书匹配
openssl x509 -noout -modulus -in cert.pem | openssl md5
openssl rsa -noout -modulus -in key.pem | openssl md5
# 两个 MD5 值应相同
```

#### 持续监控

```bash
# 证书过期监控脚本
#!/bin/bash
DOMAIN="example.com"
EXPIRY=$(echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null | \
         openssl x509 -noout -enddate | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

if [ "$DAYS_LEFT" -lt 30 ]; then
    echo "WARNING: Certificate for $DOMAIN expires in $DAYS_LEFT days!"
    # 发送告警（邮件/Slack/钉钉等）
fi
```

### 13.5.8 常见配置错误与排查

#### 错误一：证书链不完整

**症状**：部分客户端（Android、Java、curl）报 `unable to verify the first certificate`，浏览器正常。

**诊断**：
```bash
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>&1 | grep "verify return"
# 如果看到 "Verify return code: 21 (unable to verify the first certificate)"
```

**修复**：将所有中间证书合并到服务器证书文件中。

#### 错误二：私钥与证书不匹配

**症状**：服务器启动时报错或握手失败。

**诊断**：
```bash
# 对比 modulus 的 MD5
openssl x509 -noout -modulus -in cert.pem | openssl md5
openssl rsa -noout -modulus -in key.pem | openssl md5
```

#### 错误三：SNI 配置遗漏

**症状**：多域名服务器上，客户端未发送 SNI 时返回错误证书。

**修复**：确保每个 `server` 块都有正确的 `ssl_certificate` 配置，并设置默认服务器块。

#### 错误四：混合内容（Mixed Content）

**症状**：浏览器显示"不安全"警告，但证书本身有效。

**原因**：HTTPS 页面中加载了 HTTP 资源（JS、CSS、图片）。浏览器会阻止或警告。

**诊断**：Chrome DevTools → Security 面板 → 查看 Mixed Content 列表。

**修复**：
```nginx
# 自动将 HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name example.com;
    return 301 https://$server_name$request_uri;
}

# 或使用 Content-Security-Policy 头升级混合内容
add_header Content-Security-Policy "upgrade-insecure-requests" always;
```

#### 错误五：过期的中间证书

**症状**：Let's Encrypt 的 DST Root CA X3 过期后（2021年9月），使用旧 `ISRG Root X1` 交叉签名的证书在 Android 7.1 以下设备上失效。

**修复**：使用 Certbot 的 `--preferred-chain` 参数选择兼容性更好的证书链，或更新客户端根证书库。

### 13.5.9 合规要求参考

不同行业和标准对 TLS 配置有特定要求：

| 标准 | 最低 TLS 版本 | 其他要求 |
|------|--------------|----------|
| PCI DSS 4.0 | TLS 1.2 | 2025年3月起强制，禁用所有 SSL 和 TLS 1.0/1.1 |
| NIST SP 800-52 Rev. 2 | TLS 1.2 | 推荐 TLS 1.3，禁用 CBC 套件 |
| HIPAA | 无明确要求 | 传输加密为"地址able"要求，TLS 1.2+ 是行业实践 |
| GDPR | 无明确要求 | 加密是数据保护的技术措施之一 |
| 等保 2.0（中国） | TLS 1.2 | 三级以上系统要求加密传输 |
| FIPS 140-3 | TLS 1.2 | 仅允许 FIPS 批准的算法 |

### 13.5.10 配置模板速查

以下是经过 SSL Labs A+ 评级验证的 Nginx 完整 TLS 配置模板：

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    # 证书
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # 协议和密码套件
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_prefer_server_ciphers on;

    # 曲线
    ssl_ecdh_curve X25519:P-256:P-384;

    # Session 管理
    ssl_session_cache shared:SSL:50m;
    ssl_session_timeout 1d;
    ssl_session_tickets on;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;
    ssl_trusted_certificate /etc/letsencrypt/live/example.com/chain.pem;

    # 安全头
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    # 应用配置...
}

# HTTP 强制跳转 HTTPS
server {
    listen 80;
    server_name example.com;
    return 301 https://$server_name$request_uri;
}
```

**部署后验证清单**：

```text
□ SSL Labs 评分达到 A 或 A+
□ testssl.sh 无 HIGH/CRITICAL 级别问题
□ 证书链完整且顺序正确
□ OCSP Stapling 正常工作
□ HSTS 头正确设置
□ 所有 HTTP 请求被重定向到 HTTPS
□ 无混合内容警告
□ 证书有效期 > 30 天
□ 自动续期机制已测试
```
