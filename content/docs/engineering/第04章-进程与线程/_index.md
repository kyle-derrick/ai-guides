---
title: "第04章-进程与线程"
type: docs
weight: 4
---
# 第04章 进程与线程

## 章节概述

进程与线程是操作系统中最核心的抽象概念，也是并发编程的基石。理解进程和线程的机制，是掌握系统编程、高性能服务端开发、分布式系统设计的必要前提。本章从操作系统内核视角出发，系统性地讲解进程与线程的理论模型、调度策略、同步机制和现代并发范式。

## 为什么进程与线程如此重要

在现代计算环境中，几乎没有单线程顺序执行的程序。从浏览器的多标签页渲染，到Web服务器同时处理数万并发请求，再到手机应用在后台保持状态——这一切都依赖于操作系统对进程和线程的精细管理。进程提供了内存隔离和安全边界，线程则在同一地址空间内实现了轻量级的并发执行。二者的设计权衡，直接影响着程序的性能、可靠性和可维护性。

具体来说，进程与线程的设计决定了操作系统的四大核心能力：

- **资源隔离**：每个进程拥有独立的虚拟地址空间，一个进程的崩溃不会影响其他进程，这是现代操作系统安全性的根基
- **并发执行**：多核CPU时代，线程是利用硬件并行能力的最直接手段，合理的线程模型可以让程序性能随核心数线性增长
- **通信协作**：进程间通信（IPC）机制让独立进程能够交换数据和协同工作，是分布式系统的基石
- **性能优化**：调度策略决定了系统在响应速度（交互式任务）和吞吐量（批处理任务）之间的平衡

## 本章学习路线

本章按照"概念→机制→调度→同步→现代范式"的逻辑展开：

- **理论基础**：首先建立进程和线程的核心概念模型，包括进程控制块（PCB）、状态机、上下文切换；线程的用户态与内核态实现模型（N:1、1:1、M:N）；Linux进程管理的具体实现（task_struct、CFS调度器）；经典调度算法（FCFS、SJF、RR、MLFQ）的原理与伪代码；进程间通信（IPC）的七种主要方式；线程同步原语（互斥锁、读写锁、条件变量、自旋锁、信号量、屏障）；Futex机制的用户态-内核态协同；以及现代协程技术（Go GMP模型、Kotlin coroutine、Java Virtual Thread）。
- **核心技巧**：提炼进程与线程编程中的关键实践模式，包括进程管理技巧、线程池设计、无锁编程、协程最佳实践等。
- **实战案例**：通过真实场景展示进程与线程技术的应用，包括高性能Web服务器设计、生产者-消费者模型、分布式任务调度等。
- **常见误区**：揭示进程与线程编程中最容易犯的错误，如竞态条件、死锁、线程泄漏等。
- **练习方法**：提供系统性的学习和实践路径，帮助读者从理论走向实战。

## 本章内容导航

| 板块 | 内容 | 适合读者 |
|------|------|----------|
| [理论基础：什么是进程与线程](理论基础/01-一什么是进程与线程.md) | 进程、线程、协程的核心概念与状态模型 | 入门 |
| [理论基础：技术演进](理论基础/02-二技术演进.md) | 从单道程序到现代并发模型的技术发展脉络 | 入门 |
| 本文件（理论精讲） | PCB、CFS、调度算法、IPC、同步原语、Futex、协程 | 进阶→精通 |
| [核心技巧：基本操作](核心技巧/01-技巧一基本操作.md) | 进程创建、线程管理、协程调度的代码实战 | 实战 |
| [核心技巧：性能优化](核心技巧/02-技巧二性能优化.md) | 上下文切换优化、锁策略选择、并发性能调优 | 实战 |
| [实战案例](03-实战案例.md) | 高性能Web服务器、生产者-消费者、分布式调度 | 实战 |
| [常见误区](04-常见误区.md) | 竞态条件、死锁、线程泄漏等典型错误 | 避坑 |
| [练习方法](05-练习方法.md) | 思考题、实践项目、进阶挑战 | 自测 |
| [本章小结](06-本章小结.md) | 关键知识点回顾与速查表 | 复习 |

## 本章知识图谱

进程与线程
├── 进程
│   ├── PCB / task_struct
│   ├── 状态机模型
│   ├── 上下文切换
│   └── fork / exec / wait
├── 线程
│   ├── 用户态线程 vs 内核态线程
│   ├── N:1 / 1:1 / M:N 模型
│   └── POSIX Threads (pthread)
├── 调度
│   ├── FCFS / SJF / RR / MLFQ
│   ├── Linux CFS (vruntime)
│   └── RT / Deadline 调度
├── IPC
│   ├── 管道 / 命名管道
│   ├── 消息队列 / 共享内存
│   ├── 信号量 / Socket
│   └── Unix Domain Socket
├── 同步
│   ├── 互斥锁 / 读写锁
│   ├── 条件变量 / 自旋锁
│   ├── 信号量 / 屏障
│   ├── Futex
│   └── 内存屏障 / 原子操作
└── 协程
    ├── Go GMP 模型
    ├── Kotlin coroutine
    └── Java Virtual Thread (Loom)

## 前置知识

- 操作系统基础概念（内核态/用户态、系统调用）
- 计算机体系结构基础（CPU、寄存器、内存层次）
- C语言基础（指针、函数指针、结构体）

## 参考文献

- Abraham Silberschatz, Peter B. Galvin, Greg Gagne. *Operating System Concepts*, 10th Edition. Wiley, 2018.
- W. Richard Stevens, Stephen A. Rago. *Advanced Programming in the UNIX Environment*, 3rd Edition. Addison-Wesley, 2013.
- Robert Love. *Linux Kernel Development*, 3rd Edition. Addison-Wesley, 2010.
- Maurice J. Bach. *The Design of the UNIX Operating System*. Prentice Hall, 1986.

***


# 理论精讲

## 一、进程概念

### 1.1 进程的定义与本质

进程（Process）是操作系统对正在运行的程序的抽象。一个程序本身只是存储在磁盘上的静态二进制文件，而进程则是在内存中动态执行的实体。从操作系统的视角看，进程是资源分配的基本单位——每个进程拥有独立的地址空间、文件描述符表、信号处理表以及各种系统资源。

进程与程序的关系可以用一个类比来理解：程序是菜谱，进程是按照菜谱做菜的过程。同一个菜谱（程序）可以同时被多个厨师（进程）使用，每个厨师有自己的工作台（地址空间）和食材（数据）。

从更严格的角度定义，进程是**程序的一次执行实例**，包含：

- **代码段（Text Segment）**：存放编译后的机器指令，只读，所有进程可以共享同一份物理代码（如多个bash进程共享/bin/bash的代码段）
- **数据段（Data Segment）**：已初始化的全局变量和静态变量
- **BSS段**：未初始化的全局变量（内核自动清零）
- **堆（Heap）**：动态分配的内存，由malloc/new管理，向高地址增长
- **栈（Stack）**：局部变量、函数调用帧、返回地址，向低地址增长
- **内核空间**：每个进程的虚拟地址空间的高端部分映射到内核，但只有内核态才能访问

### 1.2 进程控制块（PCB）

进程控制块（Process Control Block）是操作系统内核中用于管理进程的核心数据结构。在Linux中，它的具体实现是 `task_struct` 结构体，定义在 `include/linux/sched.h` 中。

PCB包含以下关键信息：

task_struct 关键字段：
┌─────────────────────────────────────────┐
│ 进程标识信息                              │
│   pid, tgid, uid, gid                   │
├─────────────────────────────────────────┤
│ 调度信息                                  │
│   state, prio, policy, se (调度实体)      │
│   rt (实时调度), dl (Deadline调度)        │
├─────────────────────────────────────────┤
│ 内存管理信息                              │
│   mm (mm_struct 指针)                    │
│   -> pgd (页全局目录), mmap (VMA链表)     │
├─────────────────────────────────────────┤
│ 文件系统信息                              │
│   fs (fs_struct), files (files_struct)   │
│   -> fd (文件描述符表)                    │
├─────────────────────────────────────────┤
│ 信号处理信息                              │
│   signal, sighand, blocked, pending      │
├─────────────────────────────────────────┤
│ 进程间关系                                │
│   parent, children (子进程链表)           │
│   sibling, group_leader                  │
│   real_parent                            │
├─────────────────────────────────────────┤
│ 内核栈信息                                │
│   stack (内核栈指针)                      │
│   thread_info                            │
└─────────────────────────────────────────┘

在Linux 6.x中，`task_struct` 大约占 6-8KB（取决于内核配置）。早期版本（如Linux 2.6）将其放在内核栈底部以节省空间，现代版本则通过 `task_struct` 分配器独立分配。

### 1.3 进程状态机

进程在其生命周期中会在多个状态之间转换。Linux定义了以下进程状态：

                fork()
  ┌──────┐  ──────────►  ┌──────────┐
  │ NEW  │                │ RUNNING  │◄────────────┐
  └──────┘                │ (TASK_   │             │
                          │ RUNNING) │             │
                           └────┬─────┘             │
                                │                   │
              ┌─────────────────┼───────────────────┤
              │                 │                   │
              ▼                 ▼                   ▼
        ┌──────────┐    ┌──────────────┐    ┌────────────┐
        │ WAITING  │    │ INTERRUPTIBLE│    │ DISK/SIO   │
        │ (TASK_   │    │ SLEEP        │    │ WAIT       │
        │STOPPED)  │    │ (TASK_       │    │ (TASK_     │
        └──────────┘    │INTERRUPTIBLE)│    │UNINTERRUPT)│
                        └──────────────┘    └────────────┘
                                │                   │
                                └───────────────────┘
                                        │
                                        ▼
                                  ┌──────────┐
                                  │  ZOMBIE  │
                                  │ (EXIT_   │
                                  │ ZOMBIE)  │
                                  └──────────┘
                                        │
                                        ▼ wait()
                                  ┌──────────┐
                                  │ TERMINATED│
                                  └──────────┘

各状态的含义：

- **TASK_RUNNING（就绪/运行）**：进程正在CPU上执行，或在运行队列中等待调度。注意，"RUNNING"同时包含了"正在运行"和"就绪等待"两种情况。
- **TASK_INTERRUPTIBLE（可中断睡眠）**：进程正在等待某个事件（如I/O完成、信号量释放），可以被信号唤醒。
- **TASK_UNINTERRUPTIBLE（不可中断睡眠）**：进程正在等待硬件资源（如磁盘I/O），不会被信号中断。短暂使用通常是正常的，但如果长时间处于此状态（`D`状态），可能意味着系统出了问题。
- **__TASK_STOPPED（停止）**：进程被信号（如SIGSTOP、SIGTSTP）暂停执行。
- **EXIT_ZOMBIE（僵尸）**：进程已经终止，但其退出状态尚未被父进程通过 `wait()` 回收。僵尸进程不占用内存资源，但占用PID表项。
- **EXIT_DEAD（死亡）**：进程最终状态，内核已回收其所有资源。

在Linux 6.x中，还引入了以下扩展状态标志：
- `TASK_KILLABLE`：类似 `TASK_UNINTERRUPTIBLE`，但可以被致命信号杀死（用于解决不可中断睡眠导致的D状态问题）。
- `TASK_IDLE`：空闲任务专用状态。

### 1.4 上下文切换

上下文切换（Context Switch）是操作系统将CPU从一个进程切换到另一个进程的过程。这是理解并发性能的关键机制。

上下文切换的完整流程：

1. **触发**：时间片用完（时钟中断）、进程主动让出（yield/sleep）、更高优先级进程就绪
2. **保存当前进程状态**：
   - 通用寄存器（RAX, RBX, ... R15）
   - 程序计数器（PC / RIP）
   - 栈指针（SP / RSP）
   - 标志寄存器（FLAGS / RFLAGS）
   - 浮点寄存器（FPU/SSE/AVX状态）
   - 页表基地址寄存器（CR3）
3. **选择下一个进程**：调度器选择下一个要运行的进程
4. **恢复目标进程状态**：从目标进程的PCB中恢复所有寄存器
5. **切换地址空间**：加载新进程的页表（修改CR3寄存器），TLB可能被刷新

上下文切换的性能开销：

典型开销（x86-64 Linux）：
┌──────────────────────────────────┬──────────────┐
│ 操作                             │ 耗时         │
├──────────────────────────────────┼──────────────┤
│ 寄存器保存/恢复                   │ ~1-2 μs      │
│ TLB 刷新（无 PCID）               │ ~5-50 μs     │
│ L1/L2 缓存失效导致的 cache miss   │ ~10-100 μs   │
│ 总计（典型）                       │ ~3-15 μs     │
└──────────────────────────────────┴──────────────┘

Linux通过PCID（Process Context ID）来减少TLB刷新的开销。当PCID启用时，TLB条目可以跨上下文切换保留，避免了昂贵的全局TLB刷新。

**上下文切换的间接开销**同样不可忽视：

- **Cache污染**：新进程的数据和指令可能不在L1/L2缓存中，导致大量cache miss
- **Branch Predictor污染**：分支预测器的状态属于旧进程，新进程需要重新"训练"预测器
- **内存预取失效**：硬件预取器基于旧进程的访问模式，对新进程无效

这意味着一次上下文切换的实际开销可能远大于寄存器保存/恢复的时间——在某些工作负载下，间接开销占总切换时间的70%以上。

### 1.5 进程创建：fork的实现与COW

`fork()` 是Unix/Linux中创建新进程的系统调用。其核心设计思想是**写时复制（Copy-on-Write, COW）**。

```c
// fork() 的基本使用
pid_t pid = fork();
if (pid == 0) {
    // 子进程
    printf("Child: PID=%d\n", getpid());
    exit(0);
} else if (pid > 0) {
    // 父进程
    printf("Parent: child PID=%d\n", pid);
    wait(NULL);  // 等待子进程结束
} else {
    // fork失败
    perror("fork");
}
```

fork的COW实现原理：

1. `fork()` 被调用时，内核创建新的 `task_struct`
2. 复制父进程的页表，但**不复制实际内存页面**
3. 将父子进程的页表项都标记为**只读**
4. 当任一进程尝试写入时，触发**页错误（Page Fault）**
5. 内核在页错误处理中，复制被写的页面，更新页表为**可写**
6. 后续的写操作不再触发页错误

COW 工作原理图示：

fork() 之后：
父进程页表          子进程页表
┌───────┐           ┌───────┐
│ 页面A  │────┐ ┌───│ 页面A  │  （共享，只读）
│ 页面B  │─┐  │ │ ┌─│ 页面B  │  （共享，只读）
└───────┘ │  │ │ │ └───────┘
           │  ▼ ▼ ▼
           │ ┌───────────┐
           └►│ 物理页面A  │
             │ 物理页面B  │
             └───────────┘

子进程写入页面B后：
父进程页表          子进程页表
┌───────┐           ┌───────┐
│ 页面A  │────┐ ┌───│ 页面A  │  （共享，只读）
│ 页面B  │─┐  │ │   │ 页面B  │──► 物理页面B' （子进程副本，可写）
└───────┘ │  │ │   └───────┘
           │  ▼ ▼
           │ ┌───────────┐
           └►│ 物理页面A  │
             │ 物理页面B  │  （仍为父进程使用）
             └───────────┘

COW的优势在于：`fork()` 通常不需要复制任何物理内存，使得进程创建非常高效。随后 `exec()` 会替换进程的地址空间，之前的所有COW页面都会被丢弃，因此实际上大多数页面根本不会被复制。

### 1.6 exec 与 wait

`exec()` 系列函数（`execl`, `execv`, `execve` 等）用新的程序替换当前进程的地址空间：

```c
// 典型的 shell 执行命令的过程
pid_t pid = fork();
if (pid == 0) {
    // 子进程
    char *args[] = {"/bin/ls", "-la", NULL};
    execvp(args[0], args);  // 替换为 ls 程序
    perror("execvp");  // 如果exec成功，不会执行到这里
    exit(1);
}
```

`wait()` / `waitpid()` 用于父进程回收子进程的退出状态：

```c
int status;
pid_t pid = waitpid(child_pid, &amp;status, 0);
if (WIFEXITED(status)) {
    printf("Child exited with code %d\n", WEXITSTATUS(status));
} else if (WIFSIGNALED(status)) {
    printf("Child killed by signal %d\n", WTERMSIG(status));
}
```

**waitpid的高级用法**：

```c
// 非阻塞等待（WNOHANG）：检查子进程是否已退出，但不阻塞
pid_t pid = waitpid(child_pid, &amp;status, WNOHANG);
if (pid == 0) {
    // 子进程仍在运行
} else if (pid > 0) {
    // 子进程已退出
}

// 等待任意子进程（-1）
pid_t pid = waitpid(-1, &amp;status, 0);

// 等待同一进程组中的所有子进程
pid_t pid = waitpid(-child_pid, &amp;status, 0);
```

**僵尸进程的处理策略**：

1. **显式wait**：父进程定期调用 `waitpid()` 回收子进程
2. **SIGCHLD处理函数**：注册信号处理函数，在其中调用 `waitpid()`
3. **忽略SIGCHLD**：`signal(SIGCHLD, SIG_IGN)` 让内核自动回收（Linux特有行为）
4. **双fork技巧**：让孙子进程成为孤儿进程被init回收，父进程立即退出

```c
// SIGCHLD处理函数方式
void handle_sigchld(int sig) {
    int saved_errno = errno;
    while (waitpid(-1, NULL, WNOHANG) > 0)
        continue;
    errno = saved_errno;
}

// 注册处理函数
struct sigaction sa;
sa.sa_handler = handle_sigchld;
sigemptyset(&amp;sa.sa_mask);
sa.sa_flags = SA_RESTART | SA_NOCLDSTOP;
sigaction(SIGCHLD, &amp;sa, NULL);
```

***

## 二、线程概念

### 2.1 线程的定义

线程（Thread）是进程内的执行单元，是CPU调度的基本单位。同一进程内的所有线程共享：
- 代码段（text segment）
- 数据段（data segment、BSS）
- 堆内存
- 文件描述符表
- 信号处理函数

每个线程独立拥有：
- 程序计数器（PC）
- 寄存器组
- 栈空间
- 线程ID
- 信号掩码

进程地址空间中的线程布局：

高地址 ┌────────────────────┐
       │    内核空间         │
       ├────────────────────┤
       │   栈 (线程3)        │  ← 线程3的私有栈
       ├────────────────────┤
       │   栈 (线程2)        │  ← 线程2的私有栈
       ├────────────────────┤
       │   栈 (线程1)        │  ← 线程1的私有栈（主线程）
       │       ↓             │
       │                    │
       │   共享内存区域       │  ← mmap / 共享库
       │       ↑             │
       │   堆 (heap)         │  ← 所有线程共享
       ├────────────────────┤
       │   BSS段             │  ← 所有线程共享
       ├────────────────────┤
       │   数据段            │  ← 所有线程共享
       ├────────────────────┤
       │   代码段            │  ← 所有线程共享
低地址 └────────────────────┘

**进程 vs 线程的核心区别**：

┌──────────────────┬───────────────────┬───────────────────┐
│ 维度              │ 进程              │ 线程              │
├──────────────────┼───────────────────┼───────────────────┤
│ 地址空间          │ 独立              │ 共享              │
│ 创建开销          │ 高（需复制页表）   │ 低（共享地址空间） │
│ 通信方式          │ IPC（管道/共享内存）│ 直接读写共享变量   │
│ 切换开销          │ 高（~3-15μs）     │ 低（同进程内~1μs） │
│ 故障隔离          │ 强（一个崩溃不影响）│ 弱（一个崩溃全部） │
│ 安全边界          │ 有（独立uid/gid） │ 无（共享凭证）     │
│ 适用场景          │ 安全隔离、多实例   │ 高并发、共享数据   │
└──────────────────┴───────────────────┴───────────────────┘

### 2.2 用户态线程 vs 内核态线程

根据线程管理的层次，线程可以分为三种模型：

**用户态线程（User-Level Thread, ULT）**：
- 线程的创建、调度、同步完全在用户空间完成
- 内核不知道线程的存在，仍视进程为单一执行流
- 优点：切换开销小（无需陷入内核）、调度策略可自定义
- 缺点：一个线程阻塞会阻塞整个进程、无法利用多核CPU

**内核态线程（Kernel-Level Thread, KLT）**：
- 线程的管理由内核完成
- 内核为每个线程维护调度信息
- 优点：一个线程阻塞不影响其他线程、可以利用多核CPU
- 缺点：每次线程操作都需要系统调用，开销较大

### 2.3 线程模型：N:1、1:1、M:N

N:1 模型（多对一）：
  ┌─────────────────────┐
  │ 用户空间              │
  │  ULT1  ULT2  ULT3    │
  │   └─────┴─────┘      │
  │        │              │
  │    线程调度器          │
  └────────┼─────────────┘
           │
  ┌────────┼─────────────┐
  │ 内核空间 │              │
  │     KLT1              │  ← 只有一个内核线程
  └───────────────────────┘

1:1 模型（一对一）：                  ← Linux pthreads 使用此模型
  ┌─────────────────────┐
  │ 用户空间              │
  │  ULT1  ULT2  ULT3    │
  │   │      │      │     │
  └───┼──────┼──────┼─────┘
      │      │      │
  ┌───┼──────┼──────┼─────┐
  │ 内核空间                │
  │  KLT1  KLT2  KLT3     │  ← 每个用户线程对应一个内核线程
  └───────────────────────┘

M:N 模型（多对多）：                  ← Go、Erlang 使用
  ┌─────────────────────┐
  │ 用户空间              │
  │  ULT1 ULT2 ULT3 ULT4 │
  │   └────┬─────┘  └──┬─┘
  │     协程调度器     协程调度器│
  └───────┬─────────────┘
          │
  ┌───────┼──────────────┐
  │ 内核空间               │
  │  KLT1  KLT2           │  ← 少量内核线程承载多个用户线程
  └───────────────────────┘

**Linux pthreads** 使用 1:1 模型。`pthread_create()` 最终会调用 `clone()` 系统调用，在内核中创建一个新的调度实体。

### 2.4 POSIX Threads (pthread)

pthread是Unix/Linux系统上标准的线程库：

```c
#include <pthread.h>
#include <stdio.h>

void *worker(void *arg) {
    int id = *(int *)arg;
    printf("Thread %d: running\n", id);
    return NULL;
}

int main() {
    pthread_t threads[4];
    int ids[4];

    for (int i = 0; i < 4; i++) {
        ids[i] = i;
        pthread_create(&amp;threads[i], NULL, worker, &amp;ids[i]);
    }

    for (int i = 0; i < 4; i++) {
        pthread_join(threads[i], NULL);  // 等待线程结束
    }

    return 0;
}
// 编译：gcc -pthread threads.c -o threads
```

**pthread的属性控制**：

```c
pthread_attr_t attr;
pthread_attr_init(&amp;attr);

// 设置线程栈大小（默认8MB，可减小以节省内存）
pthread_attr_setstacksize(&amp;attr, 2 * 1024 * 1024);  // 2MB

// 设置线程分离属性（joinable vs detached）
pthread_attr_setdetachstate(&amp;attr, PTHREAD_CREATE_DETACHED);

// 设置线程调度策略
pthread_attr_setschedpolicy(&amp;attr, SCHED_FIFO);
struct sched_param param = { .sched_priority = 50 };
pthread_attr_setschedparam(&amp;attr, &amp;param);
pthread_attr_setinheritsched(&amp;attr, PTHREAD_EXPLICIT_SCHED);

pthread_t tid;
pthread_create(&amp;tid, &amp;attr, worker, NULL);
pthread_attr_destroy(&amp;attr);
```

***

## 三、Linux进程管理

### 3.1 task_struct 的完整结构

Linux内核中，每个进程/线程都由一个 `task_struct` 表示。线程在Linux内核中本质上就是共享了 `mm_struct`（内存空间）和 `files_struct`（文件描述符表）等资源的轻量级进程（Light-Weight Process, LWP）。

```c
// 简化的 task_struct 结构（Linux 6.x）
struct task_struct {
    // --- 调度相关 ---
    unsigned int            __state;        // 进程状态
    int                     prio;           // 动态优先级
    int                     static_prio;    // 静态优先级
    unsigned int            policy;         // 调度策略
    const struct sched_class *sched_class;  // 调度类
    struct sched_entity     se;             // CFS调度实体
    struct sched_rt_entity  rt;             // RT调度实体
    struct sched_dl_entity  dl;             // Deadline调度实体

    // --- 进程标识 ---
    pid_t                   pid;            // 线程ID
    pid_t                   tgid;           // 线程组ID（即主线程的pid）
    struct task_struct      *group_leader;  // 线程组领头进程

    // --- 内存管理 ---
    struct mm_struct        *mm;            // 用户空间内存描述符
    struct mm_struct        *active_mm;     // 当前活跃的内存描述符

    // --- 文件系统 ---
    struct fs_struct        *fs;            // 文件系统信息
    struct files_struct     *files;         // 打开文件表

    // --- 进程关系 ---
    struct task_struct      *real_parent;   // 亲生父进程
    struct task_struct      *parent;        // 养父进程（如被ptrace）
    struct list_head        children;       // 子进程链表
    struct list_head        sibling;        // 兄弟进程链表

    // --- 信号 ---
    struct signal_struct    *signal;        // 共享的信号信息
    struct sighand_struct   *sighand;       // 信号处理函数
    sigset_t                blocked;        // 被阻塞的信号
    struct sigpending       pending;        // 待处理的信号

    // --- 内核栈 ---
    void                    *stack;         // 内核栈指针

    // --- 命名空间 ---
    struct nsproxy          *nsproxy;       // 命名空间代理

    // --- cgroup ---
    struct css_set __rcu    *cgroups;       // cgroup集合

    // ... 省略约2000个其他字段
};
```

**查看task_struct**：在Linux系统上，可以通过以下方式观察进程的内部信息：

```bash
# 查看进程的完整状态（包括线程）
cat /proc/<pid>/status

# 查看进程的内存映射
cat /proc/<pid>/maps

# 查看进程的文件描述符
ls -la /proc/<pid>/fd

# 查看进程的调度策略
chrt -p <pid>

# 使用crash工具查看task_struct（需要内核调试符号）
crash> task <pid>
crash> struct task_struct.task_struct.state <task_address>
```

### 3.2 CFS调度器

完全公平调度器（Completely Fair Scheduler, CFS）是Linux默认的普通进程调度器，从Linux 2.6.23开始引入。

**核心思想**：CFS试图让所有进程获得**公平的CPU时间**。它使用**虚拟运行时间（vruntime）** 来衡量进程已经使用了多少CPU时间。

**vruntime的计算**：

vruntime += 实际运行时间 × (NICE_0_WEIGHT / 进程权重)

其中：
- `NICE_0_WEIGHT` 是nice值为0的进程的权重（1024）
- 进程权重由nice值决定（nice越低→权重越高→vruntime增长越慢→获得更多CPU时间）

nice值与权重的对应关系（部分）：
┌───────┬────────┬─────────────────────────────┐
│ nice  │ 权重    │ 相对于nice 0的CPU时间比例     │
├───────┼────────┼─────────────────────────────┤
│ -20   │ 88761  │ ≈ 88.7x                     │
│ -10   │ 11264  │ ≈ 11x                       │
│  0    │ 1024   │ 1x                          │
│  5    │ 335    │ ≈ 0.33x                     │
│  10   │ 110    │ ≈ 0.11x                     │
│  19   │ 15     │ ≈ 0.015x                    │
└───────┴────────┴─────────────────────────────┘

**CFS的红黑树**：CFS使用红黑树（按vruntime排序）来组织就绪队列。vruntime最小的进程位于红黑树最左侧，优先被调度。当进程运行时，其vruntime增加，在红黑树中向右移动；当进程休眠后被唤醒时，其vruntime可能被调整以避免获得过多的补偿时间。

```c
// CFS 选择下一个进程（简化伪代码）
static struct sched_entity *pick_next_entity(struct cfs_rq *cfs_rq) {
    // 红黑树最左节点即为vruntime最小的进程
    struct rb_node *left = rb_first_cached(&amp;cfs_rq->tasks_timeline);
    return rb_entry(left, struct sched_entity, run_node);
}

// CFS 更新vruntime（简化伪代码）
static void update_curr(struct cfs_rq *cfs_rq) {
    struct sched_entity *curr = cfs_rq->curr;
    u64 now = rq_clock_task(rq_of(cfs_rq));
    u64 delta_exec = now - curr->exec_start;  // 本次运行时长

    curr->exec_start = now;
    curr->sum_exec_runtime += delta_exec;

    // vruntime增长速率与权重成反比
    curr->vruntime += calc_delta_fair(delta_exec, curr);
}

// vruntime增量计算
static u64 calc_delta_fair(u64 delta, struct sched_entity *se) {
    if (se->load.weight != NICE_0_LOAD)
        delta = __calc_delta(delta, NICE_0_LOAD, &amp;se->load);
    return delta;
}
```

**CFS的时间片与调度周期**：

CFS不像传统调度器那样分配固定时间片。它定义了一个**调度周期（sched_latency）**，默认约6ms（`sysctl_sched_latency`），目标是在一个调度周期内让所有就绪进程都至少运行一次。每个进程获得的时间与权重成正比：

进程i的时间片 = sched_latency × (权重_i / 所有进程权重之和)

当进程数量很多时，每个进程的时间片会变得太小（小于最小粒度 `sysctl_sched_min_granularity`，默认约0.75ms），此时CFS会调整调度周期以确保最小粒度。

### 3.3 实时调度（RT）

Linux提供两种实时调度策略：

**SCHED_FIFO（先进先出）**：
- 先运行优先级最高的进程
- 同优先级的进程按FIFO顺序执行
- 一旦开始运行，除非主动让出或被更高优先级抢占，否则一直运行

**SCHED_RR（轮转）**：
- 类似SCHED_FIFO，但同优先级进程使用时间片轮转
- 时间片用完后，进程移到同优先级队列末尾

实时调度优先级范围：1-99（数值越大优先级越高），普通进程优先级为0。

**SCHED_DEADLINE（截止期限调度）**：
- 基于Earliest Deadline First（EDF）算法
- 每个任务指定三个参数：周期（period）、运行时间（runtime）、截止期限（deadline）
- 适用于有严格时序要求的实时任务

```c
// 设置实时调度策略
struct sched_param param;
param.sched_priority = 50;
sched_setscheduler(pid, SCHED_FIFO, &amp;param);

// 或使用 pthread
pthread_attr_t attr;
pthread_attr_init(&amp;attr);
pthread_attr_setschedpolicy(&amp;attr, SCHED_FIFO);
param.sched_priority = 50;
pthread_attr_setschedparam(&amp;attr, &amp;param);
pthread_attr_setinheritsched(&amp;attr, PTHREAD_EXPLICIT_SCHED);
pthread_create(&amp;thread, &amp;attr, worker, NULL);
```

***

## 四、调度算法详解

### 4.1 FCFS（先来先服务）

最简单的调度算法，按进程到达顺序执行。

伪代码：
FCFS(processes[]):
    按到达时间排序 processes
    current_time = 0
    for each p in processes:
        if current_time < p.arrival_time:
            current_time = p.arrival_time   // CPU空闲等待
        p.start_time = current_time
        p.waiting_time = current_time - p.arrival_time
        current_time += p.burst_time
        p.finish_time = current_time
        p.turnaround_time = p.finish_time - p.arrival_time

    avg_waiting = average(p.waiting_time for all p)
    avg_turnaround = average(p.turnaround_time for all p)

**特性分析**：
- 简单，无开销
- **护航效应（Convoy Effect）**：短进程被长进程阻塞，导致平均等待时间长
- 非抢占式，对交互式系统不友好

示例：
进程   到达时间   执行时间
 P1      0         24
 P2      1          3
 P3      2          3

甘特图：[P1: 0-24] [P2: 24-27] [P3: 27-30]

P1等待：0    P2等待：23    P3等待：25    平均等待：16

### 4.2 SJF（最短作业优先）

优先执行执行时间最短的进程。

伪代码（非抢占式SJF）：
SJF(processes[]):
    ready_queue = []
    current_time = 0
    completed = 0
    n = len(processes)

    while completed < n:
        // 将已到达的进程加入就绪队列
        for each p in processes:
            if p.arrival_time <= current_time and not p.added:
                ready_queue.append(p)
                p.added = true

        if ready_queue is empty:
            current_time = min(p.arrival_time for unfinished p)
            continue

        // 选择执行时间最短的进程
        shortest = min(ready_queue, key=lambda p: p.burst_time)
        ready_queue.remove(shortest)

        shortest.start_time = current_time
        shortest.waiting_time = current_time - shortest.arrival_time
        current_time += shortest.burst_time
        shortest.finish_time = current_time
        shortest.turnaround_time = shortest.finish_time - shortest.arrival_time
        completed++

    avg_waiting = average(p.waiting_time for all p)

**特性分析**：
- 最优平均等待时间（在非抢占式算法中）
- **饥饿问题**：短进程不断到来时，长进程可能永远得不到执行
- 需要预知执行时间（实际上通常用历史数据估算）

同一个例子：
甘特图：[空闲: 0-1] [P2: 1-4] [P3: 4-7] [P1: 7-31]

P1等待：7    P2等待：0    P3等待：2    平均等待：3（远优于FCFS的16）

### 4.3 RR（时间片轮转）

每个进程获得固定大小的时间片，时间片用完则被抢占。

伪代码：
RR(processes[], time_quantum):
    ready_queue = FIFO队列
    current_time = 0
    remaining = {p.burst_time for each p}  // 每个进程的剩余执行时间
    arrived = {}  // 已到达但未完成的进程集合

    while 有未完成的进程:
        // 将新到达的进程加入就绪队列
        for each p in processes:
            if p.arrival_time <= current_time and p not in arrived:
                ready_queue.enqueue(p)
                arrived.add(p)

        if ready_queue is empty:
            current_time = next_arrival_time
            continue

        current = ready_queue.dequeue()
        exec_time = min(time_quantum, remaining[current])

        current_time += exec_time
        remaining[current] -= exec_time

        // 再次检查新到达的进程（在当前进程执行期间可能有新进程到达）
        for each p in processes:
            if p.arrival_time <= current_time and p not in arrived:
                ready_queue.enqueue(p)
                arrived.add(p)

        if remaining[current] > 0:
            ready_queue.enqueue(current)  // 未完成，放回队尾
        else:
            current.finish_time = current_time
            current.turnaround_time = current.finish_time - current.arrival_time
            current.waiting_time = current.turnaround_time - current.burst_time

**时间片大小的影响**：
- **时间片太大**：退化为FCFS
- **时间片太小**：上下文切换开销过大
- **经验值**：时间片应远大于上下文切换时间（通常10-100ms），使得上下文切换开销占比小于1%

同一个例子，时间片 = 4：
甘特图：[P1: 0-4] [P2: 4-7] [P3: 7-10] [P1: 10-14] [P1: 14-18] ...
        ... [P1: 18-22] [P1: 22-26] [P1: 26-30]

P1等待：6    P2等待：3    P3等待：5    平均等待：4.67

### 4.4 MLFQ（多级反馈队列）

MLFQ是现代操作系统中最常用的调度算法框架，它结合了多种策略的优点。

MLFQ 规则：

规则1：如果A的优先级 > B的优先级，运行A
规则2：如果A的优先级 = B的优先级，按RR运行A和B
规则3：新进程进入最高优先级队列
规则4：进程用完当前层的时间片 → 降到下一级队列
规则5：经过一段时间S，将所有进程提升到最高优先级队列（防止饥饿）

优先级队列结构：
┌─────────────────────────────────────────────┐
│ Q3 (最高优先级)    时间片 = 1ms               │  ← 新进程、I/O密集型
├─────────────────────────────────────────────┤
│ Q2                时间片 = 4ms               │
├─────────────────────────────────────────────┤
│ Q1                时间片 = 8ms               │
├─────────────────────────────────────────────┤
│ Q0 (最低优先级)    时间片 = 16ms              │  ← CPU密集型
└─────────────────────────────────────────────┘

伪代码：
MLFQ(processes[], num_levels, boost_interval):
    queues[0..num_levels-1]  // 每层一个FIFO队列
    current_time = 0
    time_in_level = {}       // 每个进程在当前层已使用的时间
    last_boost = 0

    while 有未完成的进程:
        // 规则5：定时提升
        if current_time - last_boost >= boost_interval:
            for each p in 所有进程:
                将p移到最高优先级队列
                time_in_level[p] = 0
            last_boost = current_time

        // 选择最高非空队列中的进程
        selected_queue = 最高优先级的非空队列
        if selected_queue is None:
            current_time += 1
            continue

        current = selected_queue.dequeue()
        level = current的优先级
        quantum = 2^level  // 或预定义的时间片

        exec_time = min(quantum, current.remaining_time, 
                       quantum - time_in_level[current])

        current_time += exec_time
        current.remaining_time -= exec_time
        time_in_level[current] += exec_time

        if current.remaining_time <= 0:
            完成进程current
        elif time_in_level[current] >= quantum:
            // 规则4：用完时间片，降级
            if level > 0:
                将current放入queues[level-1]
            else:
                将current放入queues[0]  // 最低层重新排队
            time_in_level[current] = 0
        else:
            // 被更高优先级进程抢占，保持在当前层
            将current放回queues[level]

**MLFQ的设计哲学**：通过观察进程的行为来动态调整优先级。I/O密集型进程（交互式进程）通常只使用很短的CPU时间就进入等待，因此能保持在高优先级队列；CPU密集型进程会逐渐降到低优先级队列。这样既保证了交互式进程的响应性，又让CPU密集型进程能充分利用CPU。

### 4.5 调度算法对比总结

┌──────────┬────────┬──────────┬───────────┬───────────┬──────────┐
│ 算法      │ 类型    │ 公平性    │ 响应时间   │ 吞吐量    │ 复杂度   │
├──────────┼────────┼──────────┼───────────┼───────────┼──────────┤
│ FCFS     │ 非抢占  │ 差       │ 差        │ 中        │ O(n)     │
│ SJF      │ 非抢占  │ 差(饥饿) │ 中        │ 高        │ O(n²)    │
│ RR       │ 抢占    │ 好       │ 好(时间片)│ 中(切换)  │ O(1)     │
│ MLFQ     │ 抢占    │ 好       │ 很好      │ 高        │ O(1)     │
│ CFS      │ 抢占    │ 很好     │ 好        │ 高        │ O(log n) │
│ Deadline │ 抢占    │ N/A      │ 确定性    │ 确定性    │ O(log n) │
└──────────┴────────┴──────────┴───────────┴───────────┴──────────┘

***

## 五、进程间通信（IPC）

### 5.1 管道（Pipe）

管道是最古老的IPC机制，提供单向字节流通信。

```c
#include <unistd.h>
#include <stdio.h>
#include <string.h>

int main() {
    int pipefd[2];  // pipefd[0] = 读端, pipefd[1] = 写端
    pid_t pid;

    if (pipe(pipefd) == -1) {
        perror("pipe");
        exit(1);
    }

    pid = fork();
    if (pid == 0) {
        // 子进程：写入
        close(pipefd[0]);  // 关闭读端
        const char *msg = "Hello from child";
        write(pipefd[1], msg, strlen(msg) + 1);
        close(pipefd[1]);
        exit(0);
    } else {
        // 父进程：读取
        close(pipefd[1]);  // 关闭写端
        char buf[256];
        read(pipefd[0], buf, sizeof(buf));
        printf("Parent received: %s\n", buf);
        close(pipefd[0]);
        wait(NULL);
    }
    return 0;
}
```

**管道的实现原理**：
- 内核中分配一个环形缓冲区（默认64KB，可通过 `/proc/sys/fs/pipe-max-size` 调整到1MB）
- 写端写入数据到缓冲区，读端从缓冲区读取
- 缓冲区满时，`write()` 阻塞；缓冲区空时，`read()` 阻塞
- 所有写端关闭后，读端返回EOF（读到0字节）
- 所有读端关闭后，写端收到SIGPIPE信号

### 5.2 命名管道（FIFO）

命名管道是有文件系统路径的管道，可用于无亲缘关系的进程间通信。

```bash
# 创建命名管道
mkfifo /tmp/myfifo

# 进程1：写入
echo "Hello" > /tmp/myfifo

# 进程2：读取
cat /tmp/myfifo
```

```c
// C代码创建命名管道
#include <sys/stat.h>

mkfifo("/tmp/myfifo", 0666);

// 写进程
int fd = open("/tmp/myfifo", O_WRONLY);
write(fd, "Hello", 5);
close(fd);

// 读进程
int fd = open("/tmp/myfifo", O_RDONLY);
char buf[256];
int n = read(fd, buf, sizeof(buf));
close(fd);
```

### 5.3 消息队列（Message Queue）

消息队列是有类型标识的结构化消息传递。

```c
#include <sys/ipc.h>
#include <sys/msg.h>

struct msgbuf {
    long mtype;       // 消息类型（>0）
    char mtext[256];  // 消息内容
};

// 发送方
int msqid = msgget(ftok("/tmp", 'a'), IPC_CREAT | 0666);
struct msgbuf msg;
msg.mtype = 1;  // 消息类型
strcpy(msg.mtext, "Hello via message queue");
msgsnd(msqid, &amp;msg, strlen(msg.mtext) + 1, 0);

// 接收方
struct msgbuf rcv;
msgrcv(msqid, &amp;rcv, sizeof(rcv.mtext), 1, 0);  // 接收类型为1的消息
printf("Received: %s\n", rcv.mtext);

// 清理
msgctl(msqid, IPC_RMID, NULL);
```

**消息队列 vs 管道**：
- 消息队列支持有界消息（有类型标识，可按类型选择性接收）
- 消息队列是异步的（发送后即可返回）
- 管道是字节流，消息队列是消息边界

### 5.4 共享内存（Shared Memory）

共享内存是最快的IPC方式——多个进程直接访问同一块物理内存。

```c
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <semaphore.h>

// 创建共享内存
int fd = shm_open("/myshm", O_CREAT | O_RDWR, 0666);
ftruncate(fd, sizeof(int));  // 设置大小
int *shared = mmap(NULL, sizeof(int), PROT_READ | PROT_WRITE,
                   MAP_SHARED, fd, 0);

// 进程1：写入
*shared = 42;

// 进程2：读取
printf("Value: %d\n", *shared);

// 清理
munmap(shared, sizeof(int));
close(fd);
shm_unlink("/myshm");
```

**共享内存的同步问题**：共享内存本身不提供任何同步机制，必须配合信号量、互斥锁等使用。在POSIX共享内存中，通常将同步原语放在共享内存区域内。

### 5.5 信号量（Semaphore）

信号量用于进程间同步，是PV操作的实现。

```c
#include <semaphore.h>
#include <pthread.h>
#include <fcntl.h>

// POSIX命名信号量（可用于不同进程）
sem_t *sem = sem_open("/mysem", O_CREAT, 0666, 1);  // 初始值=1（互斥信号量）

// P操作（等待）
sem_wait(sem);    // 值减1，若为0则阻塞

// 临界区操作
// ...

// V操作（释放）
sem_post(sem);    // 值加1，可能唤醒等待的进程

// 清理
sem_close(sem);
sem_unlink("/mysem");
```

**System V信号量**（较老但仍然广泛使用）：

```c
#include <sys/ipc.h>
#include <sys/sem.h>

int semid = semget(IPC_PRIVATE, 1, IPC_CREAT | 0666);
semctl(semid, 0, SETVAL, 1);  // 初始化信号量值为1

struct sembuf P = {0, -1, 0};  // P操作
struct sembuf V = {0,  1, 0};  // V操作

semop(semid, &amp;P, 1);  // 等待
// 临界区
semop(semid, &amp;V, 1);  // 释放
```

### 5.6 Socket

Socket不仅可用于网络通信，也可用于本地进程间通信。

```c
// TCP Socket 示例（回环地址）
// 服务端
int server_fd = socket(AF_INET, SOCK_STREAM, 0);
struct sockaddr_in addr = {
    .sin_family = AF_INET,
    .sin_addr.s_addr = htonl(INADDR_LOOPBACK),  // 127.0.0.1
    .sin_port = htons(8080)
};
bind(server_fd, (struct sockaddr *)&amp;addr, sizeof(addr));
listen(server_fd, 5);

int client_fd = accept(server_fd, NULL, NULL);
char buf[256];
read(client_fd, buf, sizeof(buf));
write(client_fd, "ACK", 3);
close(client_fd);
close(server_fd);

// 客户端
int sock = socket(AF_INET, SOCK_STREAM, 0);
connect(sock, (struct sockaddr *)&amp;addr, sizeof(addr));
write(sock, "Hello", 5);
read(sock, buf, sizeof(buf));
close(sock);
```

### 5.7 Unix Domain Socket

Unix Domain Socket是专用于同一主机上进程间通信的Socket，比TCP Socket快得多（不需要网络协议栈处理）。

```c
#include <sys/un.h>

// 服务端
int server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
struct sockaddr_un addr;
memset(&amp;addr, 0, sizeof(addr));
addr.sun_family = AF_UNIX;
strcpy(addr.sun_path, "/tmp/mysocket");

unlink("/tmp/mysocket");
bind(server_fd, (struct sockaddr *)&amp;addr, sizeof(addr));
listen(server_fd, 5);

int client_fd = accept(server_fd, NULL, NULL);
char buf[256];
read(client_fd, buf, sizeof(buf));
printf("Received: %s\n", buf);
write(client_fd, "ACK", 3);
close(client_fd);
close(server_fd);
unlink("/tmp/mysocket");

// 客户端
int sock = socket(AF_UNIX, SOCK_STREAM, 0);
struct sockaddr_un addr;
addr.sun_family = AF_UNIX;
strcpy(addr.sun_path, "/tmp/mysocket");
connect(sock, (struct sockaddr *)&amp;addr, sizeof(addr));
write(sock, "Hello", 5);
read(sock, buf, sizeof(buf));
close(sock);
```

**Unix Domain Socket的优势**：
- 不经过网络协议栈，开销比TCP Socket小得多
- 可以传递文件描述符（通过 `SCM_RIGHTS` 辅助数据）
- 可以传递进程凭证（通过 `SCM_CREDENTIALS`）
- 支持SOCK_STREAM（流式）、SOCK_DGRAM（数据报）、SOCK_SEQPACKET（有序数据报）

**IPC方式对比**：

┌────────────────┬───────────┬──────────┬──────────┬───────────────┐
│ 方式           │ 带宽      │ 延迟     │ 复杂度   │ 适用场景       │
├────────────────┼───────────┼──────────┼──────────┼───────────────┤
│ 管道           │ 中        │ 中       │ 低       │ 父子进程单向通信│
│ 命名管道       │ 中        │ 中       │ 低       │ 任意进程单向通信│
│ 消息队列       │ 中        │ 中       │ 中       │ 异步消息传递   │
│ 共享内存       │ 极高      │ 极低     │ 高       │ 大量数据交换   │
│ 信号量         │ N/A       │ 低       │ 中       │ 同步控制       │
│ Socket         │ 低        │ 高       │ 高       │ 跨机器通信     │
│ Unix Domain    │ 高        │ 低       │ 高       │ 本机高效通信   │
└────────────────┴───────────┴──────────┴──────────┴───────────────┘

***

## 六、线程同步原语

### 6.1 互斥锁（Mutex）

互斥锁保证同一时刻只有一个线程进入临界区。

```c
#include <pthread.h>

pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
int shared_counter = 0;

void *increment(void *arg) {
    for (int i = 0; i < 100000; i++) {
        pthread_mutex_lock(&amp;mutex);
        shared_counter++;       // 临界区
        pthread_mutex_unlock(&amp;mutex);
    }
    return NULL;
}

int main() {
    pthread_t t1, t2;
    pthread_create(&amp;t1, NULL, increment, NULL);
    pthread_create(&amp;t2, NULL, increment, NULL);
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    printf("Counter: %d\n", shared_counter);  // 正确输出200000
    pthread_mutex_destroy(&amp;mutex);
    return 0;
}
```

**互斥锁的类型**：
- `PTHREAD_MUTEX_DEFAULT`：默认类型（Linux上通常等同于NORMAL）
- `PTHREAD_MUTEX_NORMAL`：不检测死锁，重复锁定导致死锁
- `PTHREAD_MUTEX_ERRORCHECK`：重复锁定返回错误
- `PTHREAD_MUTEX_RECURSIVE`：允许同一线程重复锁定（计数器机制）

**互斥锁的性能特征**：
- **无竞争时**：基于Futex快速路径，仅需一次原子操作（~20-50ns）
- **有竞争时**：需要FUTEX_WAIT系统调用挂起线程，开销~1-10μs
- **嵌套锁**：PTHREAD_MUTEX_RECURSIVE每次锁定/解锁需要额外的原子操作，比非递归锁慢约2倍

### 6.2 读写锁（Read-Write Lock）

读写锁允许多个读者同时访问，但写者独占。

```c
#include <pthread.h>

pthread_rwlock_t rwlock = PTHREAD_RWLOCK_INITIALIZER;
int shared_data = 0;

void *reader(void *arg) {
    pthread_rwlock_rdlock(&amp;rwlock);    // 获取读锁
    printf("Read: %d\n", shared_data); // 多个读者可同时执行
    pthread_rwlock_unlock(&amp;rwlock);
    return NULL;
}

void *writer(void *arg) {
    pthread_rwlock_wrlock(&amp;rwlock);    // 获取写锁（独占）
    shared_data++;                      // 写操作
    pthread_rwlock_unlock(&amp;rwlock);
    return NULL;
}
```

**适用场景**：读多写少的场景（如配置数据、缓存）。如果写操作频繁，读写锁的开销可能大于普通互斥锁。

**读写锁的陷阱——写者饥饿**：在默认的读写锁实现中，如果持续有读者获取锁，写者可能永远无法获取锁（写者饥饿）。Linux的 `pthread_rwlock` 默认使用写者优先策略来避免此问题，但不同实现可能不同。解决方法是使用 `PTHREAD_RWLOCK_PREFER_WRITER_NONRECURSIVE_NP` 属性。

### 6.3 条件变量（Condition Variable）

条件变量用于线程间的条件等待和通知。

```c
#include <pthread.h>

pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
int buffer = 0;
int has_data = 0;

void *producer(void *arg) {
    for (int i = 0; i < 10; i++) {
        pthread_mutex_lock(&amp;mutex);
        buffer = i;
        has_data = 1;
        pthread_cond_signal(&amp;cond);    // 通知消费者
        pthread_mutex_unlock(&amp;mutex);
        usleep(100000);
    }
    return NULL;
}

void *consumer(void *arg) {
    for (int i = 0; i < 10; i++) {
        pthread_mutex_lock(&amp;mutex);
        while (!has_data) {             // 必须用while，不能用if
            pthread_cond_wait(&amp;cond, &amp;mutex);  // 等待并释放锁
        }
        printf("Consumed: %d\n", buffer);
        has_data = 0;
        pthread_mutex_unlock(&amp;mutex);
    }
    return NULL;
}
```

**关键点**：
- `pthread_cond_wait()` 必须在持有锁的情况下调用
- `pthread_cond_wait()` 释放锁、进入等待、被唤醒后重新获取锁
- 检查条件必须使用 **while循环** 而非 if（防止**虚假唤醒**）
- `pthread_cond_signal()` 唤醒一个等待线程，`pthread_cond_broadcast()` 唤醒所有等待线程

### 6.4 自旋锁（Spinlock）

自旋锁在获取锁失败时不会让出CPU，而是忙等待（spin）。

```c
#include <pthread.h>

pthread_spinlock_t spinlock;
pthread_spin_init(&amp;spinlock, PTHREAD_PROCESS_PRIVATE);

pthread_spin_lock(&amp;spinlock);
// 临界区（必须非常短！）
pthread_spin_unlock(&amp;spinlock);

pthread_spin_destroy(&amp;spinlock);
```

**自旋锁 vs 互斥锁**：
- 自旋锁适用于**临界区极短**（几条指令）且**持锁时间可预测**的场景
- 互斥锁适用于临界区可能较长或不确定的场景
- 在单核CPU上，自旋锁毫无意义（只会浪费CPU），应该用互斥锁
- 在用户态编程中，自旋锁很少使用（因为内核可能随时调度走持锁线程）

**内核中的自旋锁**：在内核态编程中，自旋锁更常用。内核的 `spin_lock()` 在获取失败时会禁用本地CPU的抢占（在单核上还禁用中断），然后忙等待直到锁可用。这保证了持锁线程不会被调度走，从而避免了忙等待时的无效旋转。

### 6.5 信号量（Semaphore）

信号量是一个计数器，用于控制对有限资源的并发访问。

```c
#include <semaphore.h>

sem_t sem;
sem_init(&amp;sem, 0, 3);  // 初始值=3，最多3个线程同时访问

void *worker(void *arg) {
    sem_wait(&amp;sem);      // P操作：值减1，若为0则阻塞
    // 访问资源（最多3个线程同时执行）
    printf("Thread %ld: accessing resource\n", (long)arg);
    sleep(1);
    sem_post(&amp;sem);      // V操作：值加1
    return NULL;
}
```

**信号量 vs 互斥锁**：
- 互斥锁只能被同一个线程锁定和释放（所有权语义）
- 信号量没有所有权——任何线程都可以执行 `sem_post()`，即使它没有执行过 `sem_wait()`
- 信号量的初始值 > 1 时，允许多个线程同时访问（计数信号量）

### 6.6 屏障（Barrier）

屏障使一组线程在某个点同步等待，所有线程都到达后才继续执行。

```c
#include <pthread.h>

pthread_barrier_t barrier;

int main() {
    int num_threads = 4;
    pthread_barrier_init(&amp;barrier, NULL, num_threads);

    // 创建4个工作线程
    // 每个线程执行：
    void *worker(void *arg) {
        // 第一阶段工作
        do_phase1();

        pthread_barrier_wait(&amp;barrier);  // 等待所有线程完成第一阶段

        // 第二阶段工作（所有线程同时开始）
        do_phase2();
        return NULL;
    }

    pthread_barrier_destroy(&amp;barrier);
}
```

***

## 七、Futex机制

Futex（Fast Userspace muTEX）是Linux实现高效同步原语的核心机制。它通过**用户态快速路径**和**内核态慢速路径**的结合，实现了高性能的锁。

### 7.1 Futex的工作原理

Futex 的双路径设计：

快速路径（用户态，无系统调用）：
    lock():
        atomic_cmpxchg(&futex_word, 0, 1)  // 原子操作
        if 成功:  // 锁是空闲的（值为0），获取成功
            return  // 直接返回，无需陷入内核

慢速路径（内核态，需要系统调用）：
        else:  // 锁被占用
            syscall(SYS_futex, &futex_word, FUTEX_WAIT, ...)
            // 内核将当前线程挂起，加入等待队列

    unlock():
        atomic_set(&futex_word, 0)  // 释放锁
        if 有等待者:
            syscall(SYS_futex, &futex_word, FUTEX_WAKE, ...)
            // 内核唤醒一个等待线程

### 7.2 Futex系统调用

```c
#include <linux/futex.h>
#include <sys/syscall.h>
#include <unistd.h>

int futex_wait(int *uaddr, int expected) {
    return syscall(SYS_futex, uaddr, FUTEX_WAIT, expected, NULL, NULL, 0);
}

int futex_wake(int *uaddr, int n) {
    return syscall(SYS_futex, uaddr, FUTEX_WAKE, n, NULL, NULL, 0);
}
```

### 7.3 基于Futex实现互斥锁

```c
// 简化的基于futex的互斥锁实现
typedef struct {
    int state;  // 0=空闲, 1=锁定(无等待者), 2=锁定(有等待者)
} futex_mutex_t;

void futex_lock(futex_mutex_t *m) {
    int expected = 0;
    // 快速路径：尝试从0（空闲）变为1（锁定）
    if (atomic_compare_exchange_strong(&amp;m->state, &amp;expected, 1))
        return;  // 成功获取锁

    // 慢速路径：锁已被占用
    while (1) {
        // 如果当前状态是1（锁定无等待者），设为2（锁定有等待者）
        if (expected == 1) {
            expected = 1;
            atomic_compare_exchange_strong(&amp;m->state, &amp;expected, 2);
        }
        // 让内核挂起当前线程（只有state仍为2时才真正挂起）
        futex_wait(&amp;m->state, 2);
        // 被唤醒后重新尝试获取锁
        expected = 0;
        if (atomic_compare_exchange_strong(&amp;m->state, &amp;expected, 2))
            return;  // 成功获取锁
        // 否则继续循环
    }
}

void futex_unlock(futex_mutex_t *m) {
    // 释放锁：将state设为0
    if (atomic_fetch_sub(&amp;m->state, 1) != 1) {
        // 原来state不是1（即有等待者），需要唤醒
        m->state = 0;
        futex_wake(&amp;m->state, 1);  // 唤醒一个等待线程
    }
}
```

**Futex的性能特征**：
- **无竞争情况**：只需要几个原子操作（纳秒级），不需要系统调用
- **有竞争情况**：一次 `FUTEX_WAIT` 系统调用（挂起）+ 一次 `FUTEX_WAKE` 系统调用（唤醒）
- 这使得 `pthread_mutex_lock()` 在无竞争时非常快

### 7.4 Futex的高级操作

Linux还提供了更高级的Futex操作，用于实现复杂的同步原语：

```c
// FUTEX_WAIT_BITSET：带位掩码的等待（用于条件变量）
syscall(SYS_futex, uaddr, FUTEX_WAIT_BITSET, expected, 
        timeout, NULL, FUTEX_BITSET_MATCH_MASK);

// FUTEX_WAKE_BITSET：唤醒特定掩码的等待者
syscall(SYS_futex, uaddr, FUTEX_WAKE_BITSET, n,
        NULL, NULL, FUTEX_BITSET_MATCH_MASK);

// FUTEX_LOCK_PI / FUTEX_UNLOCK_PI：优先级继承互斥锁
// 用于解决优先级反转问题
syscall(SYS_futex, uaddr, FUTEX_LOCK_PI, 0, NULL, NULL, 0);

// FUTEX_REQUEUE：将等待者从一个futex重新排队到另一个
// 用于实现条件变量的broadcast
syscall(SYS_futex, uaddr1, FUTEX_CMP_REQUEUE, 
        nwake, nrequeue, uaddr2, val3);
```

**优先级继承（Priority Inheritance）**：当低优先级线程持有锁而高优先级线程在等待时，低优先级线程临时提升为高优先级，避免**优先级反转**问题。这对实时系统至关重要。`PTHREAD_MUTEX_PRIO_INHERIT` 类型的互斥锁使用 `FUTEX_LOCK_PI` 实现。

***

## 八、协程

协程（Coroutine）是用户态的轻量级线程，由运行时（而非操作系统内核）调度。协程的切换成本远低于线程（通常只需保存/恢复几个寄存器，无需系统调用）。

### 8.1 Go Goroutine与GMP模型

Go语言的goroutine是目前最成熟的协程实现之一。其调度器基于GMP模型：

GMP 模型：
┌─────────────────────────────────────────────────┐
│  G (Goroutine)                                   │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐      │
│  │ G1  │ │ G2  │ │ G3  │ │ G4  │ │ ... │      │
│  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └─────┘      │
│     │       │       │       │                    │
│  ┌──┴───────┴───────┴───────┴──┐                 │
│  │       全局运行队列            │                 │
│  └─────────────────────────────┘                 │
│         │           │                            │
│    ┌────┴────┐ ┌────┴────┐                       │
│    │ P0      │ │ P1      │  P (Processor)        │
│    │ 本地队列 │ │ 本地队列 │                       │
│    │ [G5,G6] │ │ [G7,G8] │                       │
│    └────┬────┘ └────┬────┘                       │
│         │           │                            │
│    ┌────┴────┐ ┌────┴────┐                       │
│    │ M0      │ │ M1      │  M (Machine/OS Thread)│
│    │(OS线程) │ │(OS线程)  │                       │
│    └─────────┘ └─────────┘                       │
└─────────────────────────────────────────────────┘

**G（Goroutine）**：
- 轻量级执行单元，初始栈大小仅2KB（可动态增长到GB级别）
- 由Go运行时管理，对操作系统透明

**P（Processor）**：
- 逻辑处理器，数量默认等于CPU核心数（`GOMAXPROCS`）
- 每个P拥有一个本地goroutine队列（容量256）
- P是G和M之间的桥梁

**M（Machine）**：
- 对应一个操作系统线程
- M必须绑定一个P才能执行G
- M的数量可能超过P的数量（当有G阻塞在系统调用时）

**调度流程**：
1. 当一个G被创建时，优先放入当前P的本地队列
2. 如果本地队列满了，将本地队列的一半G移到全局队列
3. 当P的本地队列为空时，从全局队列获取G
4. 如果全局队列也为空，尝试从其他P的本地队列**偷取**（work stealing）一半G
5. 当G执行阻塞系统调用时，M和G一起阻塞，P被分离并绑定新的M（hand off）

```go
// Go goroutine使用示例
func main() {
    ch := make(chan int, 10)

    // 启动10万个goroutine
    for i := 0; i < 100000; i++ {
        go func(id int) {
            ch <- id * id
        }(i)
    }

    // 收集结果
    for i := 0; i < 100000; i++ {
        result := <-ch
        _ = result
    }
}
```

### 8.2 Kotlin Coroutines

Kotlin协程基于**结构化并发**和**挂起函数（suspend function）**的概念。

```kotlin
import kotlinx.coroutines.*

fun main() = runBlocking {
    // 启动协程
    val job = launch {
        delay(1000L)  // 挂起函数，不阻塞线程
        println("World!")
    }
    println("Hello,")
    job.join()  // 等待协程完成
}

// 并发执行
fun main() = runBlocking {
    val deferreds = (1..100_000).map { i ->
        async {
            delay(100)  // 模拟异步操作
            i * i
        }
    }
    val results = deferreds.map { it.await() }
    println("Sum: ${results.sum()}")
}
```

Kotlin协程的关键概念：
- **suspend函数**：可以暂停执行而不阻塞线程的函数
- **CoroutineScope**：协程的生命周期范围
- **Dispatcher**：决定协程在哪个线程/线程池执行
  - `Dispatchers.Default`：CPU密集型任务
  - `Dispatchers.IO`：I/O密集型任务
  - `Dispatchers.Main`：UI线程

### 8.3 Java Virtual Thread (Project Loom)

Java 21引入了虚拟线程（Virtual Thread），是JDK对协程的官方实现。

```java
// Java 21+ 虚拟线程
public class VirtualThreadDemo {
    public static void main(String[] args) throws Exception {
        // 创建虚拟线程
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<Integer>> futures = new ArrayList<>();
            for (int i = 0; i < 100_000; i++) {
                final int id = i;
                futures.add(executor.submit(() -> {
                    Thread.sleep(Duration.ofMillis(100));  // 阻塞操作不消耗平台线程
                    return id * id;
                }));
            }
            // 收集结果
            long sum = 0;
            for (var f : futures) {
                sum += f.get();
            }
            System.out.println("Sum: " + sum);
        }
    }
}

// 虚拟线程与平台线程的对比
// 平台线程：1:1 映射到OS线程
Thread platformThread = Thread.ofPlatform().start(() -> {
    System.out.println("Platform thread: " + Thread.currentThread());
});

// 虚拟线程：M:N 映射到少量carrier线程
Thread virtualThread = Thread.ofVirtual().start(() -> {
    System.out.println("Virtual thread: " + Thread.currentThread());
});
```

**Java虚拟线程的特点**：
- 由JVM管理调度，而非操作系统
- 创建成本极低（约几百字节 vs 平台线程的~1MB栈）
- 可以创建数百万个虚拟线程
- 当虚拟线程执行阻塞I/O时，JVM自动将其从载体线程（carrier thread）上卸载，释放载体线程去执行其他虚拟线程
- 与现有Java代码**完全兼容**——无需修改已有的阻塞式代码

**协程技术对比**：

┌──────────────┬──────────────┬──────────────┬──────────────┐
│              │ Go Goroutine │ Kotlin       │ Java Virtual │
│              │              │ Coroutine    │ Thread       │
├──────────────┼──────────────┼──────────────┼──────────────┤
│ 调度模型      │ M:N (GMP)    │ 用户态调度    │ M:N          │
│ 栈大小       │ 2KB起,可增长  │ 无栈(状态机) │ ~数百字节起   │
│ 阻塞处理     │ 自动处理      │ 需要suspend  │ 自动处理      │
│ 学习曲线     │ 中等          │ 较陡         │ 低(兼容旧代码)│
│ 生态成熟度   │ 高            │ 高           │ 中(较新)     │
│ 创建数量级   │ 百万级        │ 百万级       │ 百万级       │
│ 切换成本     │ ~100ns       │ ~10ns        │ ~100ns       │
└──────────────┴──────────────┴──────────────┴──────────────┘

***

## 九、fork的深入实现

### 9.1 fork的完整流程

Linux中 `fork()` 的实现经历了多次优化。现代Linux使用 `clone()` 系统调用来实现 `fork()`，`clone()` 提供了更精细的资源共享控制。

```c
// fork() 在内核中的调用链
sys_fork()
  → kernel_clone()
      → copy_process()
          ├── dup_task_struct()        // 复制task_struct和内核栈
          ├── copy_creds()             // 复制凭证
          ├── copy_mm()                // 复制内存描述符（COW）
          ├── copy_files()             // 复制文件描述符表（或共享）
          ├── copy_fs()                // 复制文件系统信息（或共享）
          ├── copy_sighand()           // 复制信号处理函数（或共享）
          ├── copy_signal()            // 复制信号信息（或共享）
          ├── copy_namespaces()        // 复制命名空间
          ├── copy_io()                // 复制IO上下文
          └── sched_fork()             // 初始化调度信息

      → wake_up_new_task()             // 将子进程加入运行队列
```

### 9.2 COW的详细机制

```c
// copy_mm() 中的COW实现（简化）
static int copy_mm(unsigned long clone_flags, struct task_struct *tsk) {
    struct mm_struct *mm;

    if (clone_flags &amp; CLONE_VM) {
        // 线程创建：共享地址空间
        mmget(current->mm);
        tsk->mm = current->mm;
        return 0;
    }

    // fork：复制地址空间（COW）
    mm = dup_mm(tsk, current->mm);
    tsk->mm = mm;
    return 0;
}

// dup_mm() 中的关键操作
static struct mm_struct *dup_mm(struct task_struct *tsk,
                                 struct mm_struct *oldmm) {
    struct mm_struct *mm = allocate_mm();
    memcpy(mm, oldmm, sizeof(*mm));

    // 复制页表，将所有页表项标记为只读
    dup_mmap(mm, oldmm);
    return mm;
}

// dup_mmap() 中对每个VMA（虚拟内存区域）的操作
static int dup_mmap(struct mm_struct *mm, struct mm_struct *oldmm) {
    for each VMA in oldmm->mmap:
        // 复制VMA结构
        new_vma = vm_area_dup(old_vma);

        // 复制页表条目，标记为只读（COW）
        copy_page_range(mm, oldmm, new_vma);

        // 将新VMA插入新进程的mm
        vma_link(mm, new_vma);
}
```

### 9.3 clone()系统调用

`clone()` 是创建线程和进程的基础系统调用，通过标志位控制资源共享：

```c
// clone() 的标志位
#define CLONE_VM      0x00000100  // 共享地址空间
#define CLONE_FS      0x00000200  // 共享文件系统信息
#define CLONE_FILES   0x00000400  // 共享文件描述符表
#define CLONE_SIGHAND 0x00000800  // 共享信号处理函数
#define CLONE_THREAD  0x00010000  // 同一线程组（线程）
#define CLONE_PARENT  0x00008000  // 与调用者共享父进程
#define CLONE_NEWPID  0x20000000  // 新的PID命名空间
#define CLONE_NEWNET  0x40000000  // 新的网络命名空间

// fork = clone() 不带任何共享标志
// vfork = clone(CLONE_VM | CLONE_VFORK)
// pthread_create = clone(CLONE_VM | CLONE_FS | CLONE_FILES | 
//                        CLONE_SIGHAND | CLONE_THREAD | ...)
```

### 9.4 vfork与posix_spawn

`vfork()` 是一个优化版本的fork，子进程直接在父进程的地址空间中运行，直到调用 `exec()` 或 `_exit()`。在这期间父进程被阻塞。

```c
// vfork的典型用法（现在已被posix_spawn替代）
pid_t pid = vfork();
if (pid == 0) {
    execl("/bin/ls", "ls", "-la", NULL);
    _exit(1);  // 必须用_exit()，不能用exit()
}
```

现代Linux中，由于COW的高效性，`vfork()` 的性能优势已经很小。`posix_spawn()` 是更推荐的创建子进程并执行新程序的方式。

***

## 十、内存屏障与原子操作

### 10.1 为什么需要内存屏障

现代CPU为了提升性能，会进行**指令重排序**（Instruction Reordering）和**乱序执行**（Out-of-Order Execution）。编译器也会进行优化级别的重排序。这意味着代码的执行顺序可能与源码顺序不同。

在单线程环境下，这种重排序对程序员是透明的（CPU保证最终一致性）。但在多线程环境下，如果一个线程的写操作在另一个线程看来顺序错乱，就会导致**数据竞争**和**不可预期的行为**。

示例：无同步时的重排序问题

线程A：                  线程B：
data = 42;              while (!ready) continue;
ready = true;           print(data);  // 可能输出0！

编译器/CPU可能将 ready = true 重排到 data = 42 之前

### 10.2 内存屏障的种类

```c
#include <stdatomic.h>

// 编译器屏障（阻止编译器重排序）
asm volatile("" ::: "memory");  // GCC/Clang
// 效果：编译器不会跨此屏障重排序内存访问

// 完整内存屏障（阻止CPU和编译器重排序）
atomic_thread_fence(memory_order_seq_cst);
// 或使用平台特定指令
__sync_synchronize();  // GCC内置
atomic_thread_fence(); // C11原子操作

// 单向屏障
atomic_thread_fence(memory_order_acquire);  // 加载屏障：后续读写不会重排到此之前
atomic_thread_fence(memory_order_release);  // 存储屏障：之前的读写不会重排到此之后
```

### 10.3 C11/C++11原子操作

```c
#include <stdatomic.h>
#include <stdio.h>
#include <pthread.h>

// 原子变量
atomic_int counter = ATOMIC_VAR_INIT(0);

void *increment(void *arg) {
    for (int i = 0; i < 1000000; i++) {
        atomic_fetch_add(&amp;counter, 1);  // 原子递增
    }
    return NULL;
}

// 原子操作的内存序
void example() {
    atomic_int flag = ATOMIC_VAR_INIT(0);
    atomic_int data = ATOMIC_VAR_INIT(0);

    // 线程A：写数据后设置标志
    atomic_store_explicit(&amp;data, 42, memory_order_relaxed);
    atomic_store_explicit(&amp;flag, 1, memory_order_release);  // 保证data的写对flag之前的线程可见

    // 线程B：检查标志后读数据
    if (atomic_load_explicit(&amp;flag, memory_order_acquire)) {  // 保证看到flag时也看到data
        int val = atomic_load_explicit(&amp;data, memory_order_relaxed);
        // val 一定是 42，不会是 0
    }
}
```

**内存序（Memory Order）的选择**：

| 内存序 | 性能 | 语义 | 适用场景 |
|--------|------|------|----------|
| `relaxed` | 最快 | 只保证原子性，不保证顺序 | 计数器、统计 |
| `consume` | 快 | 依赖关系保序 | 引用计数 |
| `acquire/release` | 中 | 单向屏障 | 锁、消息传递 |
| `seq_cst` | 慢 | 全局顺序一致 | 默认选择，最安全 |

***

## 十一、核心技巧

### 11.1 上下文切换优化

1. **减少进程/线程数量**：使用线程池管理并发，避免频繁创建销毁
2. **CPU亲和性**：通过 `sched_setaffinity()` 将进程绑定到特定CPU核心，减少缓存迁移
3. **减少锁竞争**：使用无锁数据结构（原子操作、CAS）、减小临界区范围
4. **NUMA感知**：在NUMA架构上，确保线程访问的内存在同一NUMA节点

```c
// CPU亲和性设置示例
#include <sched.h>

cpu_set_t cpuset;
CPU_ZERO(&amp;cpuset);
CPU_SET(2, &amp;cpuset);  // 绑定到CPU核心2
sched_setaffinity(0, sizeof(cpu_set_t), &amp;cpuset);
```

### 11.2 线程池设计

```c
// 基本线程池结构
typedef struct {
    void *(*function)(void *);  // 任务函数
    void *arg;                   // 任务参数
} task_t;

typedef struct {
    pthread_t *threads;          // 线程数组
    int num_threads;             // 线程数量
    task_t *queue;               // 任务队列（环形缓冲区）
    int queue_size;              // 队列容量
    int head, tail, count;       // 队列指针
    pthread_mutex_t lock;        // 队列互斥锁
    pthread_cond_t not_empty;    // 非空条件变量
    pthread_cond_t not_full;     // 非满条件变量
    int shutdown;                // 关闭标志
} thread_pool_t;

// 提交任务
void pool_submit(thread_pool_t *pool, void *(*fn)(void *), void *arg) {
    pthread_mutex_lock(&amp;pool->lock);
    while (pool->count == pool->queue_size)
        pthread_cond_wait(&amp;pool->not_full, &amp;pool->lock);
    
    pool->queue[pool->tail].function = fn;
    pool->queue[pool->tail].arg = arg;
    pool->tail = (pool->tail + 1) % pool->queue_size;
    pool->count++;
    
    pthread_cond_signal(&amp;pool->not_empty);
    pthread_mutex_unlock(&amp;pool->lock);
}
```

**线程池设计的关键参数**：

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| I/O密集型 | CPU核心数 × 2 | I/O等待时间长，需要更多线程 |
| CPU密集型 | CPU核心数 + 1 | 避免过多上下文切换 |
| 混合型 | CPU核心数 × 1.5 | 根据实际负载调整 |
| 队列大小 | 无界队列 或 CPU核心数 × 10 | 根据内存和背压策略 |

### 11.3 IPC方式选择指南

| 场景 | 推荐方式 | 原因 |
|------|----------|------|
| 父子进程单向通信 | 管道 | 简单高效，内核自动管理生命周期 |
| 任意进程单向通信 | 命名管道 | 有文件系统路径，无需亲缘关系 |
| 异步消息传递 | 消息队列 | 有类型标识，支持选择性接收 |
| 大量数据交换 | 共享内存 | 最快的IPC方式，零拷贝 |
| 同步控制 | 信号量 | 经典PV操作，跨进程共享 |
| 跨机器通信 | TCP Socket | 网络协议栈，支持远程 |
| 本机高效通信 | Unix Domain Socket | 可传递文件描述符，比TCP快 |

***

## 十二、实战案例

### 案例1：上下文切换导致的性能问题

**场景**：某电商服务器在"秒杀"活动期间，CPU使用率高达95%，但每秒处理的请求数反而从5000下降到800。

**诊断过程**：

```bash
# 查看上下文切换频率
vmstat 1
# 关注 cs（context switches）列，正常<1000/s，异常时可能>50000/s

# 查看哪个进程上下文切换最多
pidstat -w 1
# cswch/s: 自愿上下文切换（通常是I/O等待）
# nvcswch/s: 非自愿上下文切换（时间片用完被抢占）

# 查看进程的线程数
ls /proc/<pid>/task | wc -l
```

**根因分析**：服务器为每个请求创建一个新线程，高峰期同时存在2000+个活跃线程，远超CPU核心数（8核），导致大量非自愿上下文切换。

**解决方案**：改为固定大小线程池（16个线程）+ 异步I/O模型，性能恢复到6000 QPS。

### 案例2：僵尸进程导致系统异常

**场景**：某守护进程运行数天后，系统日志出现"无法创建新进程"错误。

**诊断过程**：

```bash
# 查看系统中的僵尸进程
ps aux | awk '$8 == "Z"'
# 或
ps -eo state | grep -c Z

# 查看僵尸进程数量
cat /proc/loadavg
# 如果僵尸进程累积，/proc/sys/kernel/threads-max 可能耗尽

# 找到产生僵尸进程的父进程
ps -eo pid,ppid,stat,cmd | grep Z
```

**根因分析**：程序fork了子进程但没有调用 `wait()` 回收退出状态。SIGCHLD信号处理函数被注释掉了（为了调试临时添加的）。

**解决方案**：注册SIGCHLD处理函数，或设置 `signal(SIGCHLD, SIG_IGN)` 让内核自动回收。

### 案例3：死锁导致服务挂起

**场景**：多线程转账服务偶尔挂起，无响应且不崩溃。

**诊断方法**：

```bash
# 使用 gdb attach 到目标进程
gdb -p <pid>

# 查看所有线程
(gdb) thread apply all bt

# 使用 strace 查看线程系统调用
strace -f -p <pid> -e trace=futex
# 如果看到多个线程都在 futex(FUTEX_WAIT) 状态，可能存在死锁

# 使用 hung_task_timeout 探测内核级死锁
dmesg | grep "task hung"
```

**根因分析**：两个转账操作需要同时锁住两个账户。操作A锁住账户1后锁账户2，操作B锁住账户2后锁账户1——典型的ABBA死锁。

**解决方案**：固定加锁顺序（按账户ID排序后加锁），或使用 `trylock` + 回退重试。

***

## 十三、常见误区

### 误区1：线程总是比进程快

**真相**：取决于场景。线程创建确实更快（共享地址空间），但如果线程间存在大量锁竞争，性能可能不如进程。例如，Redis使用单线程避免锁竞争，性能反而高于多线程实现。进程在需要强隔离的场景（如Chrome浏览器的多进程架构）是更好的选择。

### 误区2：多线程一定能利用多核

**真相**：需要无锁或合理的锁设计。如果所有线程都竞争同一把锁，多线程程序的性能可能比单线程还差（因为锁竞争和上下文切换的额外开销）。正确做法：减小锁粒度、使用无锁数据结构、按CPU核心分区数据。

### 误区3：fork会复制所有内存

**真相**：现代Linux使用写时复制（COW）。fork后父子进程共享物理内存页，只有在实际写入时才会复制。但如果子进程立即调用exec()，之前的COW页表都会被丢弃——这意味着fork+exec的组合几乎没有内存复制开销。

### 误区4：协程可以完全替代线程

**真相**：协程适用于I/O密集型任务，但CPU密集型任务仍然需要操作系统线程。协程运行在用户态，无法利用多核CPU（除非与多线程结合）。Go的GMP模型就是协程（G）+ 线程（M）的组合。CPU密集型计算应使用 `runtime.GOMAXPROCS()` 设置足够的P，或直接使用线程。

### 误区5：条件变量的虚假唤醒是bug

**真相**：虚假唤醒（spurious wakeup）是POSIX标准允许的行为，不是bug。操作系统可能在没有 `pthread_cond_signal()` 的情况下唤醒等待的线程（例如，Linux的Futex实现可能因为信号或超时而唤醒）。因此必须使用 **while循环** 检查条件，而不是if。

### 误区6：信号量可以替代互斥锁

**真相**：虽然计数信号量可以实现互斥（初始值=1），但信号量没有所有权语义——任何线程都可以 `sem_post()`，这使得调试和推理变得困难。互斥锁的"谁加锁谁解锁"语义让代码更安全、更易维护。应优先使用互斥锁保护临界区，仅在需要计数或跨进程同步时使用信号量。

***

## 十四、练习方法

### 思考题

1. 进程和线程的本质区别是什么？为什么Linux把线程也实现为task_struct？
2. 为什么上下文切换会导致缓存失效？间接开销为什么可能比直接开销更大？
3. CFS调度器如何保证公平性？vruntime的设计为什么比固定时间片更好？
4. 比较管道和共享内存的性能差异，在什么场景下应该选择管道？
5. 为什么条件变量必须配合互斥锁使用？为什么必须用while而不是if检查条件？
6. Futex的双路径设计为什么比纯内核态锁（如System V信号量）更快？
7. Go的GMP模型中，work stealing机制解决了什么问题？
8. 内存屏障的 `memory_order_acquire` 和 `memory_order_release` 分别保证了什么？

### 实践项目

1. **实现线程池**：用C语言实现一个支持动态扩容的线程池，支持任务优先级
2. **生产者-消费者**：用共享内存 + 信号量实现跨进程的生产者-消费者模型
3. **死锁检测**：编写一个工具，通过分析 `strace` 输出检测潜在的死锁模式
4. **上下文切换测量**：编写程序测量进程间和线程间上下文切换的实际开销
5. **无锁队列**：用原子操作实现一个无锁的单生产者单消费者队列

### 进阶挑战

1. 阅读Linux内核源码中 `kernel/fork.c` 的 `copy_process()` 函数，理解fork的完整实现
2. 使用 `perf` 工具分析一个多线程程序的上下文切换热点
3. 实现一个基于epoll的事件驱动服务器，对比线程池模型的性能差异
4. 研究Go调度器源码中 `runtime/proc.go` 的 `schedule()` 函数

***

## 参考文献

1. Silberschatz, A., Galvin, P. B., & Gagne, G. (2018). *Operating System Concepts* (10th ed.). Wiley.
2. Love, R. (2010). *Linux Kernel Development* (3rd ed.). Addison-Wesley.
3. Bovet, D. P., & Cesati, M. (2005). *Understanding the Linux Kernel* (3rd ed.). O'Reilly.
4. McKenney, P. E. (2013). *Is Parallel Programming Hard, And, If So, What Can You Do About It?* kernel.org.
5. Vyukov, D. (2012). *Go Scheduler*. Go语言中文网.
6. Oracle. (2023). *JEP 444: Virtual Threads*. OpenJDK.
7. Butenhof, D. R. (1997). *Programming with POSIX Threads*. Addison-Wesley.
8. Kerrisk, M. (2010). *The Linux Programming Interface*. No Starch Press.
9. Drepper, U. (2007). *What Every Programmer Should Know About Memory*. Red Hat.
10. Torvalds, L. et al. Linux Kernel Source Code. kernel.org.
