---
title: "以太网与ARP协议"
type: docs
weight: 2
---
## 以太网与ARP协议

以太网（Ethernet）和地址解析协议（ARP）是TCP/IP协议栈中最底层的两个核心组件。以太网定义了局域网中数据帧的格式和传输规则，ARP则解决了"已知IP地址、求MAC地址"的核心问题。理解这两个协议，是深入掌握网络通信的第一步。

---

### 1. 以太网（Ethernet）概述

#### 1.1 什么是以太网

以太网是当今局域网（LAN）最广泛使用的有线网络技术，由Xerox公司于1973年提出，后经Xerox、DEC和Intel联合标准化（DIX Ethernet），最终由IEEE 802.3标准正式定义。截至2020年代，以太网已从最初的10 Mbps发展到400 Gbps乃至800 Gbps，覆盖了从家庭网络到数据中心的几乎所有有线连接场景。

以太网的核心特征：

- **基带传输**：数据以数字信号直接在介质上传输，不使用调制
- **CSMA/CD**：传统半双工模式下的冲突检测机制（全双工模式已不再需要）
- **变长帧**：支持64-1518字节的标准帧（Jumbo Frame可扩展到9000字节以上）
- **广播域**：同一网段内的所有设备共享通信介质

#### 1.2 以太网的发展历程

| 代际 | 标准 | 速率 | 介质 | 典型应用 |
|------|------|------|------|----------|
| 第一代 | 10BASE5 | 10 Mbps | 粗同轴电缆 | 早期LAN |
| 第二代 | 10BASE2 | 10 Mbps | 细同轴电缆 | 办公室网络 |
| 第三代 | 10BASE-T | 10 Mbps | 双绞线（Cat3+） | 桌面接入 |
| 第四代 | 100BASE-TX | 100 Mbps | 双绞线（Cat5） | 快速以太网 |
| 第五代 | 1000BASE-T | 1 Gbps | 双绞线（Cat5e+） | 千兆以太网 |
| 第六代 | 10GBASE-T | 10 Gbps | 双绞线（Cat6a+） | 万兆接入 |
| 第七代 | 25G/40G/100G | 25-100 Gbps | 光纤/铜缆 | 数据中心 |
| 前沿 | 400G/800G | 400-800 Gbps | 光纤/高速铜缆 | 超大规模数据中心 |

#### 1.3 以太网帧结构

以太网帧（Ethernet Frame）是以太网传输的基本单位。目前主流使用的是Ethernet II帧格式（也称为DIX帧），其结构如下：

+-------------+------------+------+------------+-----+------+
| 目的MAC(6B) | 源MAC(6B)  | 类型 | 数据载荷   | FCS | 前导 |
|             |            | (2B) | (46-1500B) |(4B) | (8B) |
+-------------+------------+------+------------+-----+------+

各字段详解：

**前导码（Preamble）与帧起始定界符（SFD）**
- 前导码：7字节，交替的10101010比特模式，用于接收端时钟同步
- SFD：1字节，10101011，标记帧的正式开始
- 这8字节不计入帧长，由网卡硬件自动处理

**目的MAC地址（Destination MAC Address）**
- 6字节（48位），标识帧的目标接收方
- 单播：特定设备的唯一MAC地址
- 广播：FF:FF:FF:FF:FF:FF，同一广播域内所有设备接收
- 组播：01-00-5E开头的地址，用于一组设备

**源MAC地址（Source MAC Address）**
- 6字节（48位），标识帧的发送方
- 由网卡厂商烧录（OUI 3字节 + 序列号3字节），全球唯一

**类型/长度字段（EtherType）**
- 2字节，标识上层协议类型
- 0x0800：IPv4
- 0x86DD：IPv6
- 0x0806：ARP
- 值 ≤ 1500时表示载荷长度（IEEE 802.3原始定义）

**数据载荷（Payload）**
- 46-1500字节
- 不足46字节时需填充（Padding）至最小长度，保证帧总长至少64字节
- 超过1500字节需使用Jumbo Frame或QinQ等扩展技术

**帧校验序列（FCS）**
- 4字节，CRC-32校验
- 检测传输过程中的比特错误
- 校验失败的帧由网卡直接丢弃，不向上层报告

#### 1.4 最小帧长与冲突检测

以太网要求帧最小长度为64字节（不含前导码和SFD），这个设计与CSMA/CD机制直接相关：

- 在10 Mbps以太网中，最大网络直径约2500米
- 信号往返时间（RTT）约为51.2微秒
- 最小帧长 = 10 Mbps × 51.2 μs = 512位 = 64字节
- 这确保发送方在发送完帧之前，能够检测到是否发生了冲突

在全双工交换式以太网中，CSMA/CD已不再使用（每个端口独享带宽，无冲突），但最小帧长的要求仍然保留以确保向后兼容。

#### 1.5 MTU与帧大小的关系

最大传输单元（MTU）是网络层协议能够传输的最大数据大小。以太网的默认MTU为1500字节，这意味着：

- **帧大小** = 目的MAC(6) + 源MAC(6) + 类型(2) + 数据载荷(≤1500) + FCS(4) = 最大1518字节
- **Jumbo Frame**：MTU可扩展到9000字节，帧总长最大约9018字节，常用于数据中心存储（iSCSI）和高性能计算（RDMA）
- **Baby Giant / Jumbo Frame**：VLAN标签（QinQ双层标签）场景下，帧长可达1522字节，部分厂商支持

MTU不匹配是常见的网络故障原因之一。当发送方的帧大小超过接收方的MTU时，若中间路由器不支持分片（如Path MTU Discovery），数据包会被静默丢弃（ICMP不可达消息被防火墙阻止时尤为隐蔽）。

---

### 2. MAC地址详解

#### 2.1 MAC地址的结构

MAC地址（Media Access Control Address）是网络接口的硬件标识，长度为48位（6字节），通常以十六进制表示，格式为XX:XX:XX:XX:XX:XX。

|  厂商标识 OUI (3字节, 24位)  |  设备标识 (3字节, 24位)  |
|        由IEEE分配            |     由厂商自行分配        |

- **OUI（Organizationally Unique Identifier）**：由IEEE注册管理机构分配给网络设备厂商，如Cisco的OUI包含00:00:0C、00:1A等，Intel为00:03:47等
- **设备标识**：厂商在OUI基础上自行编码，保证同一OUI下每个网卡的MAC地址唯一

**特殊MAC地址**：
- 全0：00:00:00:00:00:00（无效地址，不作为源地址使用）
- 全1：FF:FF:FF:FF:FF:FF（广播地址）
- 组播位（第1字节最低位为1）：标识该地址为组播/广播用途
- 本地管理位（第1字节次低位为1）：标识该MAC为手动配置（常用于虚拟机、容器网络）

#### 2.2 MAC地址的查看与修改

在Linux系统中查看MAC地址：

```bash
# 查看所有网络接口的MAC地址
ip link show
# 或使用传统命令
ifconfig -a

# 查看指定接口的详细信息
ethtool -i eth0

# 查看ARP缓存表
ip neigh show
# 或
arp -n
```

修改MAC地址（Linux）：

```bash
# 临时修改（重启后失效）
ip link set dev eth0 down
ip link set dev eth0 address 02:00:00:00:00:01
ip link set dev eth0 up

# 通过NetworkManager永久修改（CentOS/RHEL）
nmcli connection modify "eth0" 802-3-ethernet.cloned-mac-address 02:00:00:00:00:01
nmcli connection up "eth0"
```

#### 2.3 MAC地址与网络分层

在OSI七层模型中，MAC地址工作在第二层（数据链路层）。理解MAC地址在各层之间的关系至关重要：

| 层级 | 标识 | 作用域 | 说明 |
|------|------|--------|------|
| 应用层 | URL/域名 | 全局 | 面向用户的服务标识 |
| 传输层 | 端口号 | 主机内 | 区分同一主机上的不同应用 |
| 网络层 | IP地址 | 跨网段 | 逻辑寻址，路由依据 |
| 数据链路层 | MAC地址 | 本局域网 | 物理寻址，帧转发依据 |

关键认知：**IP地址负责跨网段的端到端通信，MAC地址负责同一网段内的逐跳转发**。数据包在经过每个路由器（三层设备）时，源/目的MAC地址都会被替换，而IP地址通常保持不变。

---

### 3. 地址解析协议（ARP）

#### 3.1 ARP的必要性

在TCP/IP网络中，上层应用使用IP地址进行通信，但以太网帧的传输依赖MAC地址。当一台主机知道目标IP地址但不知道其MAC地址时，就无法构造以太网帧。ARP（Address Resolution Protocol，RFC 826）正是解决这一"IP→MAC"映射问题的协议。

ARP的工作场景举例：
1. 主机A（192.168.1.10）要向同一网段的主机B（192.168.1.20）发送数据
2. 主机A查ARP缓存表，未找到192.168.1.20对应的MAC地址
3. 主机A发送ARP请求（广播），询问"谁是192.168.1.20？请告诉我你的MAC地址"
4. 主机B收到后发送ARP应答（单播），告知"我是192.168.1.20，我的MAC地址是XX:XX:XX:XX:XX:XX"
5. 主机A将该映射缓存到本地ARP表，后续通信直接使用

#### 3.2 ARP报文格式

ARP报文封装在以太网帧中，EtherType为0x0806，其格式如下：

 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|         硬件类型 (Hardware Type)         |         协议类型 (Protocol Type)        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| 硬件地址长度  | 协议地址长度  |          操作码 (Opcode)          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     发送方硬件地址 (前4字节)                     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| 发送方硬件地址 |                 发送方协议地址                    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                 发送方协议地址 |              目标硬件地址           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         目标硬件地址                            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         目标协议地址                            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

各字段含义：

| 字段 | 长度 | 值/说明 |
|------|------|---------|
| 硬件类型 | 2字节 | 1 = 以太网 |
| 协议类型 | 2字节 | 0x0800 = IPv4 |
| 硬件地址长度 | 1字节 | 6（MAC地址为6字节） |
| 协议地址长度 | 1字节 | 4（IPv4地址为4字节） |
| 操作码 | 2字节 | 1 = ARP请求，2 = ARP应答，3 = RARP请求，4 = RARP应答 |
| 发送方硬件地址 | 6字节 | 发送方的MAC地址 |
| 发送方协议地址 | 4字节 | 发送方的IP地址 |
| 目标硬件地址 | 6字节 | 请求时全0，应答时填入目标MAC |
| 目标协议地址 | 4字节 | 被查询的IP地址 |

#### 3.3 ARP请求与应答流程

ARP请求是**广播帧**（目的MAC为FF:FF:FF:FF:FF:FF），同一广播域内所有设备都会收到并处理。ARP应答是**单播帧**，只发回给请求方。

完整的ARP交互时序：

主机A (192.168.1.10/AA:AA:AA:AA:AA:AA)          主机B (192.168.1.20/BB:BB:BB:BB:BB:BB)
        |                                              |
        |------- ARP Request (广播) ----------------->|
        |  "Who has 192.168.1.20? Tell 192.168.1.10"  |
        |                                              |
        |<------ ARP Reply (单播) --------------------|
        |  "192.168.1.20 is at BB:BB:BB:BB:BB:BB"     |
        |                                              |
        |======= 开始正常数据通信 ===================>|

#### 3.4 ARP缓存机制

每次ARP交互都会消耗网络带宽和CPU资源，因此操作系统维护了一个ARP缓存表（ARP Cache），将最近使用过的IP-MAC映射关系缓存起来。

**Linux系统ARP缓存管理**：

```bash
# 查看ARP缓存
ip neigh show

# 输出示例：
# 192.168.1.1 dev eth0 lladdr 00:1A:2B:3C:4D:5E REACHABLE
# 192.168.1.20 dev eth0 lladdr BB:BB:BB:BB:BB:BB STALE
# 192.168.1.254 dev eth0 lladdr CC:CC:CC:CC:CC:CC DELAY

# ARP缓存状态含义：
# REACHABLE - 最近通信确认可达
# STALE    - 超过确认时间，下次使用前需验证
# DELAY    - 等待上层协议确认
# FAILED   - 解析失败
# INCOMPLETE - 正在解析中（已发送请求，等待应答）
# PERMANENT - 静态配置的条目，不过期

# 手动添加静态ARP条目（防止ARP欺骗）
ip neigh add 192.168.1.1 lladdr 00:1A:2B:3C:4D:5E dev eth0 nud permanent

# 删除ARP缓存条目
ip neigh del 192.168.1.20 dev eth0

# 清空整个ARP缓存
ip neigh flush all
```

**ARP缓存生命周期**：
- Linux默认超时时间：30秒变为STALE，STALE状态可长期保留但不可靠
- Windows默认超时时间：2分钟（120秒）
- 静态绑定的条目永不过期，重启后需重新配置

#### 3.5 ARP在跨网段通信中的角色

当通信双方不在同一网段时，ARP只能解析本地网关（路由器接口）的MAC地址。完整的跨网段通信过程：

主机A (192.168.1.10)                     路由器 (192.168.1.1 / 10.0.0.1)              主机C (10.0.0.20)
       |                                          |                                          |
       |-- ARP请求: 192.168.1.1的MAC? ----------->|                                          |
       |<-- ARP应答: 192.168.1.1的MAC = XX:XX ----|                                          |
       |                                          |                                          |
       |-- IP包(源:192.168.1.10, 目:10.0.0.20) -->|                                          |
       |   (以太网帧: 源MAC=AA, 目MAC=XX)         |                                          |
       |                                          |-- ARP请求: 10.0.0.20的MAC? ------------->|
       |                                          |<-- ARP应答: 10.0.0.20的MAC = YY:YY -----|
       |                                          |-- IP包(同上) --------------------------->|
       |                                          |   (以太网帧: 源MAC=ZZ, 目MAC=YY)         |

关键要点：
- 每经过一个路由器，以太网帧的源/目的MAC地址都会被重新封装
- IP包的源/目的IP地址在整个过程中通常保持不变（NAT除外）
- 路由器的每个接口都有独立的ARP缓存表

---

### 4. ARP安全与ARP欺骗

#### 4.1 ARP协议的安全缺陷

ARP协议设计于1982年，当时网络环境高度可信，因此**完全没有认证机制**。任何设备都可以发送ARP应答，即使没有收到对应的ARP请求。这导致了ARP欺骗（ARP Spoofing）攻击：

- **攻击原理**：攻击者发送伪造的ARP应答，将受害者主机的网关MAC地址映射指向攻击者的MAC地址
- **攻击后果**：中间人攻击（MITM）、流量嗅探、会话劫持、拒绝服务（DoS）
- **攻击隐蔽性**：ARP欺骗不产生明显的异常流量，受害者难以察觉

#### 4.2 ARP欺骗的典型攻击场景

正常情况:
  受害者 (PC) --- ARP: 网关IP → 网关MAC(真实) --- 路由器(网关)

ARP欺骗后:
  受害者 (PC) --- ARP: 网关IP → 攻击者MAC --- 攻击者(PC2) --- 路由器(网关)
                   ↑                           ↑
            以为在和网关通信              实际截获所有流量

攻击工具（仅用于安全研究和授权渗透测试）：
- arpspoof（dsniff套件）
- Ettercap
- Bettercap

#### 4.3 ARP防御措施

**静态ARP绑定（适用于小型网络）**：

```bash
# Linux：绑定网关MAC地址
arp -s 192.168.1.1 00:1A:2B:3C:4D:5E

# 将静态绑定加入启动脚本，确保重启后仍然有效
# CentOS/RHEL
echo "arp -s 192.168.1.1 00:1A:2B:3C:4D:5E" >> /etc/rc.local

# Windows
netsh interface ip add neighbors "以太网" 192.168.1.1 00-1A-2B-3C-4D-5E
```

**动态ARP检测（DAI，适用于企业网络）**：

DAI是交换机的安全特性，通过DHCP Snooping绑定表验证ARP报文的合法性：

```bash
# Cisco交换机配置DAI
ip arp inspection vlan 10
interface GigabitEthernet0/1
 ip arp inspection trust    # 上行口信任，不做检查
interface GigabitEthernet0/2
 no ip arp inspection trust # 下行口不信任，检查ARP
```

**ARP防护软件**：

```bash
# arptables（Linux防火墙ARP层过滤）
arptables -A INPUT --arp-ip-mac 00:1A:2B:3C:4D:5E --arp-ip-src 192.168.1.1 -j ACCEPT
arptables -A INPUT --arp-ip-src 192.168.1.1 -j DROP  # 拒绝非真实网关MAC的ARP应答
```

---

### 5. RARP、Proxy ARP与 Gratuitous ARP

#### 5.1 RARP（反向地址解析协议）

RARP解决的问题与ARP相反：已知MAC地址，求IP地址。早期无盘工作站启动时无法存储IP配置，通过RARP向服务器请求。

- 已基本被DHCP取代
- 相关RFC：RFC 903（已废弃）

#### 5.2 Proxy ARP（代理ARP）

当路由器代替目标主机回复ARP请求时，称为Proxy ARP。典型应用场景：

- **跨子网Proxy ARP**：两个子网的主机在同一物理网络但不同IP子网，路由器代理ARP使它们可以互相通信而无需配置默认网关
- **安全用途**：隐藏真实服务器的MAC地址，由防火墙代理ARP

Proxy ARP的潜在问题：
- 增加路由器负担
- 可能导致路由黑洞
- 现代网络通常使用明确的路由配置替代Proxy ARP

#### 5.3 Gratuitous ARP（免费ARP）

Gratuitous ARP是主机主动发送的ARP请求/应答，不以获取其他主机MAC为目的。用途包括：

- **IP冲突检测**：主机启动时发送Gratuitous ARP，若收到应答说明IP已被占用
- **通知MAC地址变更**：虚拟机迁移、网卡故障切换时通知网络更新ARP缓存
- **VRRP/HSRP**：高可用协议利用Gratuitous ARP更新下游设备的ARP表，实现无感知切换

```bash
# 手动发送Gratuitous ARP（Linux，需安装arping）
arping -A -c 3 -I eth0 192.168.1.10

# 检测IP冲突
arping -D -c 3 -I eth0 192.168.1.10
# 返回0表示无冲突，返回1表示IP已存在
```

---

### 6. 实战：抓包分析以太网帧与ARP

#### 6.1 使用tcpdump抓取ARP报文

```bash
# 抓取所有ARP报文
sudo tcpdump -i eth0 arp -nn

# 输出示例：
# 10:23:45.123456 ARP, Request who-has 192.168.1.20 tell 192.168.1.10, length 28
# 10:23:45.234567 ARP, Reply 192.168.1.20 is-at bb:bb:bb:bb:bb:bb, length 28

# 抓取特定主机的ARP
sudo tcpdump -i eth0 arp host 192.168.1.20 -nn

# 抓取以太网帧详情（包含MAC地址层信息）
sudo tcpdump -i eth0 -e -nn arp
# -e 参数显示以太网帧头：源MAC、目的MAC、协议类型

# 输出示例（-e格式）：
# 10:23:45.123456 aa:aa:aa:aa:aa:aa > ff:ff:ff:ff:ff:ff, ethertype ARP (0x0806), length 42:
#   Request who-has 192.168.1.20 tell 192.168.1.10, length 28
```

#### 6.2 使用Wireshark深入分析

Wireshark提供了最直观的帧分析界面。针对ARP报文的常用过滤器：

# 仅显示ARP报文
arp

# 显示ARP请求
arp.opcode == 1

# 显示ARP应答
arp.opcode == 2

# 显示特定IP的ARP
arp.dst.hw_mac == bb:bb:bb:bb:bb:bb

# 显示ARP请求（"谁有XX IP？告诉XX"格式）
arp.duplicate-address-detected

# 显示可能的ARP攻击（大量ARP应答无请求）
arp.opcode == 2 && !arp.duplicate-address-detected

#### 6.3 使用Scapy构造自定义ARP报文

Scapy是一个强大的Python网络包构造和分析库：

```python
from scapy.all import *

# 构造ARP请求
arp_request = ARP(
    op=1,                    # 1=请求, 2=应答
    pdst="192.168.1.20",     # 目标IP
    psrc="192.168.1.10",     # 源IP
    hwdst="00:00:00:00:00:00"  # 目标MAC（请求时全0）
)

# 发送ARP请求并等待应答
result = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/arp_request, timeout=3, verbose=0)

# 解析结果
for sent, received in result[0]:
    print(f"IP: {received.psrc}, MAC: {received.hwsrc}")

# 自动扫描整个子网的存活主机
def scan_subnet(subnet="192.168.1.0/24"):
    arp_request = ARP(pdst=subnet)
    broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = broadcast/arp_request
    result = srp(packet, timeout=3, verbose=0)[0]
    
    hosts = []
    for sent, received in result:
        hosts.append({"ip": received.psrc, "mac": received.hwsrc})
    return hosts

# 使用示例
alive_hosts = scan_subnet("192.168.1.0/24")
for host in alive_hosts:
    print(f"{host['ip']:>16s}  {host['mac']}")
```

---

### 7. 以太网交换与MAC地址学习

#### 7.1 交换机的工作原理

以太网交换机工作在数据链路层，通过学习源MAC地址建立**MAC地址表**（也称CAM表），实现帧的智能转发：

1. **学习**：交换机收到帧后，将源MAC地址与接收端口的映射关系存入MAC地址表
2. **转发/过滤**：查找目的MAC地址对应的端口，仅从该端口转发（单播），而非所有端口（避免广播域泛滥）
3. **泛洪**：目的MAC不在表中时，从除接收端口外的所有端口转发（未知单播泛洪）
4. **老化**：MAC地址表条目有超时机制（默认300秒），避免表无限增长

```bash
# 查看交换机MAC地址表（Cisco）
show mac address-table

# 查看Linux网桥的MAC地址表（Linux充当交换机时）
bridge fdb show

# 查看特定接口的MAC地址
bridge fdb show dev eth0
```

#### 7.2 VLAN与以太网

虚拟局域网（VLAN，IEEE 802.1Q）在以太网帧中插入4字节的VLAN标签，将物理网络逻辑划分为多个广播域：

+-------+-------+------+--------+------+---------+------+
|目的MAC|源MAC  |TPID  |TCI     | 类型 | 数据载荷 | FCS  |
| (6B)  | (6B)  |(2B)  |(2B)    | (2B) |          |(4B)  |
|       |       |0x8100|VLAN ID |      |          |      |
+-------+-------+------+--------+------+---------+------+

VLAN标签的TCI字段包含：
- 3位优先级（Priority Code Point）：QoS标记
- 1位CFI（Canonical Format Indicator）：标识MAC地址格式
- 12位VLAN ID：支持4094个VLAN（0和4095保留）

---

### 8. 常见问题与故障排查

#### 8.1 ARP相关故障

**故障一：ARP缓存毒化导致网络中断**

```bash
# 症状：突然无法访问网关
# 排查步骤：
1. 查看ARP缓存
   ip neigh show
   # 如果网关IP对应的MAC地址频繁变化，可能遭受ARP攻击

2. 对比真实网关MAC
   # 从网关设备上确认真实MAC地址
   # 或联系网络管理员获取

3. 临时修复：手动绑定静态ARP
   ip neigh add 192.168.1.1 lladdr <真实MAC> nud permanent
```

**故障二：ARP请求无应答**

```bash
# 可能原因：
# 1. 目标主机不在线
ping -c 3 192.168.1.20

# 2. 目标主机防火墙阻止ARP
#    Linux: arptables -L 查看规则
#    Windows: 检查Windows防火墙高级设置

# 3. VLAN隔离，主机虽在同一IP子网但不同VLAN
#    检查交换机VLAN配置
show vlan brief

# 4. 交换机端口安全限制了MAC地址
#    检查端口安全配置
show port-security interface eth0
```

**故障三：MTU不匹配导致部分网站无法访问**

```bash
# 症状：大部分网站正常，部分网站（尤其HTTPS大页面）加载失败
# 排查方法：
ping -M do -s 1472 192.168.1.20
# -M do: 设置Don't Fragment标志
# -s 1472: 数据大小（1472 + 28字节IP/ICMP头 = 1500字节）

# 逐步降低-s值直到ping通
ping -M do -s 1400 192.168.1.20

# 如果1472不通但1400通，说明路径中存在MTU限制
# 解决方案：在主机上设置合适的MTU
ip link set dev eth0 mtu 1400
```

#### 8.2 以太网相关故障

**常见以太网问题排查清单**：

| 问题 | 排查命令 | 可能原因 |
|------|----------|----------|
| 链路不UP | `ip link show eth0` | 网线松动/损坏、端口关闭 |
| 速率不匹配 | `ethtool eth0` | 双端自协商失败、强制速率不一致 |
| 频繁丢包 | `ethtool -S eth0` | 线缆质量差、电磁干扰、CRC错误增多 |
| 网络环路 | `bridge link show` | 交换机间形成环路、STP失效 |
| Jumbo Frame失败 | `ping -M do -s 8972 <IP>` | 路径中某设备不支持巨型帧 |

```bash
# 详细查看网卡状态和统计
ethtool eth0
# 关注：Speed/Duplex/Link detected/Auto-negotiation

# 查看网卡错误统计
ethtool -S eth0 | grep -i error
# 关注：rx_crc_errors（CRC校验错误）、rx_fifo_errors（FIFO溢出）

# 强制设置速率和双工模式（排除自协商问题）
ethtool -s eth0 speed 1000 duplex full autoneg off
```

---

### 9. 本节小结

以太网和ARP是理解网络通信的基石：

- **以太网**定义了局域网中数据帧的格式、传输规则和介质访问控制。从10 Mbps到800 Gbps，以太网始终是局域网的事实标准。
- **ARP**通过广播请求/单播应答的机制，实现了IP地址到MAC地址的动态映射，使得三层（IP）和二层（以太网）能够协同工作。
- **ARP安全**是网络管理的重要课题，静态绑定、DAI、端口安全等措施可以有效防御ARP欺骗攻击。
- **实操技能**：使用tcpdump/Wireshark抓包分析以太网帧和ARP报文，使用Scapy构造自定义报文，是网络工程师必备的诊断能力。
