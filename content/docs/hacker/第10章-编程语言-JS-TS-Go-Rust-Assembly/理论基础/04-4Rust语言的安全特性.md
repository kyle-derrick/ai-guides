---
title: "4. Rust语言的安全特性"
type: docs
weight: 4
---

## 4. Rust语言的安全特性

Rust 是系统编程语言领域的一次范式革新——它在不依赖垃圾回收的前提下，通过编译时所有权检查消除了整类内存安全漏洞。对于安全工程师而言，Rust 的价值不仅在于"写不出 bug"，更在于它将安全保证从运行时检测（ASan、Valgrind）提升到了编译时证明，从根本上改变了攻防双方的博弈格局。

### 4.1 为什么 Rust 的安全性对安全领域至关重要

#### 4.1.1 内存安全漏洞的现实代价

Microsoft Security Response Center 在 2019 年披露，其产品中约 70% 的安全漏洞属于内存安全类别（缓冲区溢出、Use-After-Free、双重释放等）。Google 对 Chromium 项目长达 12 年的安全审计得出类似结论：约 70% 的严重安全漏洞源于内存不安全代码。Android 团队在 2024 年报告中指出，随着 Rust 在新代码中的采用，内存安全漏洞占比已从 76% 下降至 24%。

这些漏洞之所以危险，是因为它们直接打破进程隔离：

| 漏洞类型 | 攻击效果 | 经典案例 |
|----------|---------|---------|
| 缓冲区溢出 | 覆盖返回地址，劫持控制流 | Heartbleed（CVE-2014-0160）|
| Use-After-Free | 释放后重用，执行任意代码 | Chrome V8 漏洞链 |
| 双重释放 | 堆元数据损坏，任意写 | glibc malloc 利用 |
| 数据竞争 | 竞态条件绕过安全检查 | TOCTOU 类漏洞 |
| 空指针解引用 | 进程崩溃（DoS）或信息泄露 | 内核空页面映射攻击 |

Rust 的编译时检查能够从根本上消除前四类漏洞（空指针通过 `Option<T>` 类型消除），这对安全基础设施——防火墙、代理、解析器、加密库——的意义尤为深远。

#### 4.1.2 安全领域的语言选择困境

在 Rust 出现之前，安全工程师面临一个两难选择：

```text
安全语言选择的演进：

C/C++ ──────── 性能最优，但内存安全全靠人工
  │             → 大量 CVE，Heartbleed、Log4Shell 等
  │
Java/C# ────── GC 保证内存安全，但运行时开销大
  │             → 不适合内核、嵌入式、高频交易
  │
Go ─────────── 编译型 + GC，内存安全 + 高并发
  │             → GC 暂停不适合延迟敏感场景
  │
Rust ────────── 编译时所有权检查，零运行时开销
                  → 性能接近 C，内存安全由编译器证明
```

这个定位使 Rust 特别适合编写安全关键组件：TLS 库（rustls）、密码学实现（ring）、网络协议栈（smoltcp）、操作系统内核（Redox）。

### 4.2 所有权系统：Rust 安全的基石

所有权系统是 Rust 区别于所有其他主流语言的核心机制。它不是语法糖，不是库功能，而是嵌入编译器的底层约束——编译器在生成机器码之前，必须先证明你的代码满足所有权规则。

#### 4.2.1 所有权三规则

Rust 所有权系统建立在三条不可违反的规则之上：

```text
所有权三规则：

规则 1：每个值在任意时刻有且只有一个所有者（owner）
规则 2：同一时刻只能有一个所有者——赋值或传参会转移所有权（move）
规则 3：当所有者离开作用域（scope），值被自动丢弃（drop）
```

这三条规则的组合效果是：编译器在编译时就精确知道每块内存何时分配、何时释放，不需要运行时 GC，也不会出现手动管理内存的各类错误。

```rust
fn ownership_demo() {
    let s1 = String::from("hello");  // s1 是 "hello" 的所有者
    let s2 = s1;                      // 所有权从 s1 转移到 s2
    // println!("{}", s1);            // 编译错误：s1 已经无效
    println!("{}", s2);               // 正常：s2 拥有这个 String

    // s2 离开作用域时，String 的堆内存被自动释放
    // 不需要 free()，不会忘记释放，不会重复释放
}
```

从安全角度看，所有权规则直接消除了以下漏洞类型：

- **Use-After-Free**：值被 move 后，原变量编译时即失效，不可能再访问已释放的内存
- **双重释放**：只有最后一个所有者离开作用域时才触发 drop，不可能出现两次 free
- **悬垂指针**：编译器保证引用不会比它指向的数据活得更久（生命周期检查）

#### 4.2.2 Move 语义 vs Copy 语义

并非所有类型都会 move。Rust 将类型分为两类：

| 行为 | 类型 | 语义 | 安全影响 |
|------|------|------|---------|
| Move | `String`, `Vec<T>`, `Box<T>` | 赋值转移所有权，原变量失效 | 防止重复释放堆内存 |
| Copy | `i32`, `f64`, `bool`, `char` | 赋值复制值，两个变量独立 | 栈上值，无资源管理问题 |

```rust
// Copy 类型：赋值不会使原变量失效
let x: i32 = 42;
let y = x;      // x 被复制到 y
println!("{} {}", x, y);  // 两个都有效

// Move 类型：赋值使原变量失效
let s1 = String::from("hello");
let s2 = s1;    // s1 的所有权转移给 s2
// println!("{}", s1);    // 编译错误！
```

这个设计的安全意义在于：只有那些管理外部资源（堆内存、文件描述符、网络连接）的类型才会 move，而这些恰恰是安全漏洞的高发区。

#### 4.2.3 RAII 与资源安全

Rust 的所有权系统本质上是 RAII（Resource Acquisition Is Initialization）模式的语言级支持。每个资源（内存、文件句柄、锁、网络连接）都绑定到一个值上，值离开作用域时资源自动释放。

```rust
use std::fs::File;
use std::io::Write;

fn write_log(message: &str) -> std::io::Result<()> {
    let mut file = File::create("app.log")?;  // 获取文件资源
    file.write_all(message.as_bytes())?;
    Ok(())
    // file 离开作用域，底层文件描述符自动关闭
    // 即使 write_all 返回错误触发 ? 提前返回，file 也会被关闭
}
```

RAII 的安全价值：

- **异常安全**：无论函数通过 `return`、`?` 还是 panic 退出，资源都会被释放
- **资源泄漏防护**：不可能"忘记关闭"文件或释放锁
- **确定性析构**：资源在作用域结束时立即释放，不像 GC 那样有不确定的延迟

### 4.3 借用检查器：编译时的数据竞争防护

借用检查器（Borrow Checker）是 Rust 编译器中验证引用合法性的核心组件。它强制执行一组约束，使得数据竞争在编译时就不可能发生。

#### 4.3.1 借用规则

```text
借用检查器的核心规则：

在任意给定时刻，对于同一块数据：
  - 要么有任意数量的不可变引用（&T）     —— "共享读"
  - 要么恰好有一个可变引用（&mut T）      —— "独占写"
  - 两者不能同时存在                       —— "读写互斥"

可变引用的额外约束：
  - 同一时刻只能有一个可变引用
  - 不可变引用和可变引用的作用域不能重叠
```

```rust
fn borrow_rules_demo() {
    let mut data = vec![1, 2, 3];

    // ✅ 多个不可变引用：允许
    let r1 = &data;
    let r2 = &data;
    println!("{:?} {:?}", r1, r2);  // r1, r2 的最后使用

    // ✅ 不可变引用使用完毕后，可变引用：允许
    let r3 = &mut data;
    r3.push(4);
    println!("{:?}", r3);

    // ❌ 不可变引用和可变引用同时存在：编译错误
    // let r4 = &data;
    // let r5 = &mut data;    // 不能同时借用
    // println!("{:?} {:?}", r4, r5);
}
```

#### 4.3.2 为什么读写互斥能防止数据竞争

数据竞争（Data Race）的定义需要三个条件同时满足：

1. 两个或多个线程并发访问同一数据
2. 至少一个线程在写入
3. 没有使用同步机制协调访问

Rust 的借用规则在编译时消除了条件 2 和条件 3 的组合可能性：如果存在可变引用（写入），就不可能同时存在其他任何引用（无同步的并发读）。这意味着数据竞争在 Rust 的 safe 代码中是**不可能**的——不是"不太可能发生"，而是"编译器保证不会发生"。

```rust
use std::thread;

fn data_race_prevention() {
    let mut data = vec![1, 2, 3];

    // ❌ 编译错误：不能将 &data 移动到另一个线程同时还在主线程使用
    // let handle = thread::spawn(|| {
    //     println!("{:?}", data);  // 不可变借用
    // });
    // data.push(4);  // 可变借用——冲突！
    // handle.join().unwrap();

    // ✅ 正确做法：move 所有权到新线程
    let handle = thread::spawn(move || {
        println!("{:?}", data);  // data 所有权已在新线程
    });
    // data 已被 move，主线程不能再使用
    handle.join().unwrap();
}
```

#### 4.3.3 NLL（Non-Lexical Lifetimes）

从 Rust 2018 版本开始，借用检查器使用 NLL 算法，引用的生命周期不是由花括号决定，而是由最后一次使用点决定。这使得许多合理的代码模式能够通过编译：

```rust
fn nll_demo() {
    let mut data = String::from("hello");

    let r1 = &data;           // 不可变借用开始
    println!("{}", r1);       // r1 的最后一次使用
    // 不可变借用在此结束（NLL）

    let r2 = &mut data;       // 可变借用开始——合法，因为 r1 已不再使用
    r2.push_str(" world");
    println!("{}", r2);       // r2 的最后一次使用
}
```

### 4.4 生命周期：消除悬垂引用

生命周期（Lifetime）是 Rust 类型系统的扩展，用于描述引用的有效范围。编译器通过生命周期分析确保所有引用在使用时都指向有效的数据。

#### 4.4.1 生命周期标注

大多数情况下，编译器可以自动推断生命周期（"生命周期省略规则"）。但在函数签名涉及多个引用时，需要显式标注：

```rust
// 'a 是一个生命周期参数，表示返回值的引用与输入参数的引用存活同样长
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}

fn lifetime_demo() {
    let string1 = String::from("long string");
    let result;
    {
        let string2 = String::from("xyz");
        result = longest(string1.as_str(), string2.as_str());
        println!("Longest: {}", result);  // ✅ 合法：string2 仍存活
    }
    // println!("{}", result);  // ❌ 编译错误：string2 已被释放
}
```

#### 4.4.2 生命周期的安全意义

生命周期系统防止的核心安全问题是**悬垂引用**（Dangling Reference）：

```rust
// ❌ 编译错误：返回的引用指向即将被释放的局部变量
fn dangling_reference() -> &String {
    let s = String::from("hello");
    &s  // s 在函数返回时被释放，引用将指向无效内存
}

// ✅ 正确做法：返回所有权
fn no_dangling() -> String {
    let s = String::from("hello");
    s   // 所有权移动给调用者
}
```

在 C 中，等价的代码返回指向栈帧的指针——函数返回后栈帧被回收，指针变成悬垂指针。攻击者可以通过精心构造的栈帧布局来利用这种漏洞（经典的 ROP 利用技术）。Rust 的生命周期检查在编译时就阻止了这种可能性。

#### 4.4.3 生命周期省略规则

编译器在以下三种情况可以自动推断生命周期，不需要显式标注：

```text
省略规则：

规则 1：每个引用参数获得独立的生命周期参数
        fn foo(x: &str) → fn foo<'a>(x: &'a str)

规则 2：如果只有一个输入生命周期参数，它被赋给所有输出引用
        fn foo(x: &str) -> &str → fn foo<'a>(x: &'a str) -> &'a str

规则 3：如果有多个输入但其中一个是 &self 或 &mut self，
        self 的生命周期被赋给所有输出引用
```

这三条规则覆盖了绝大多数函数签名，使得日常代码很少需要手写生命周期标注。

### 4.5 unsafe Rust：安全边界的精确定义

Rust 的安全保证有一个精确的边界：safe Rust 代码中不可能出现未定义行为（UB），但 unsafe Rust 代码可以绕过编译器的部分检查。这种设计不是缺陷，而是对系统编程现实的务实回应。

#### 4.5.1 unsafe 允许的操作

unsafe 块允许五种额外操作，每一种都对应着特定的安全需求：

| unsafe 操作 | 用途 | 安全风险 |
|-------------|------|---------|
| 解引用裸指针 | FFI 交互、自定义内存布局 | 空指针、越界、对齐错误 |
| 调用 unsafe 函数 | 底层系统调用、性能关键路径 | 函数前置条件不满足 |
| 访问/修改可变静态变量 | 全局状态 | 数据竞争、未初始化读取 |
| 实现 unsafe trait | `Send`/`Sync` 标记 | 线程安全假设错误 |
| 访问 union 字段 | C 兼容、类型双关 | 读取未初始化的变体 |

```rust
unsafe fn dangerous_raw_pointer() {
    let mut value: u32 = 42;
    let ptr = &mut value as *mut u32;

    // unsafe 块：编译器不再检查裸指针的安全性
    // 程序员必须手动保证：
    //   1. ptr 非空
    //   2. ptr 正确对齐
    //   3. ptr 指向有效内存
    //   4. 没有别名冲突
    unsafe {
        assert!(!ptr.is_null());
        assert!(ptr as usize % std::mem::align_of::<u32>() == 0);
        *ptr = 100;
    }
}
```

#### 4.5.2 unsafe 的安全契约

unsafe 的核心思想是**安全抽象**：在 unsafe 块内部可以做危险操作，但封装 unsafe 代码的 safe 函数必须保证——无论调用者传入什么合法参数，都不会导致未定义行为。

```rust
/// safe 函数：调用者不需要知道内部使用了 unsafe
pub fn split_at_mut(slice: &mut [u8], mid: usize) -> (&mut [u8], &mut [u8]) {
    let len = slice.len();
    assert!(mid <= len, "mid out of bounds");

    let ptr = slice.as_mut_ptr();
    // unsafe：裸指针操作
    // 安全保证：mid <= len 已检查，两个切片不重叠
    unsafe {
        (
            std::slice::from_raw_parts_mut(ptr, mid),
            std::slice::from_raw_parts_mut(ptr.add(mid), len - mid),
        )
    }
}
```

对于安全审计，这意味着：审计 Rust 代码时，只需要重点关注 `unsafe` 块和 `unsafe fn`——safe 代码中的内存安全问题已经被编译器消除。

#### 4.5.3 安全审计中的 unsafe 审查清单

```cpp
unsafe 代码审计要点：

1. 裸指针操作
   □ 指针是否在使用前经过非空检查？
   □ 指针是否满足目标类型的对齐要求？
   □ 指向的内存是否仍然有效（未被释放）？
   □ 是否存在别名冲突（两个可变指针指向同一地址）？

2. unsafe 函数
   □ 文档是否列出了所有前置条件（safety invariants）？
   □ 所有调用点是否满足了这些前置条件？
   □ 函数是否维护了类型的安全不变量？

3. 可变静态变量
   □ 所有访问是否都在 unsafe 块中？
   □ 是否存在并发访问（需要 Mutex/RwLock）？
   □ 变量是否在所有路径上都被正确初始化？

4. FFI（外部函数接口）
   □ C 函数的签名是否正确映射到 Rust 类型？
   □ 指针的生命周期是否正确管理？
   □ 是否处理了 C 端可能返回的错误码？

5. 内存布局
   □ #[repr(C)] 是否正确标注？
   □ 是否使用 std::mem::size_of 和 align_of 验证布局？
   □ 是否考虑了平台差异（大小端、指针宽度）？
```

### 4.6 Rust 的类型系统与安全

Rust 的类型系统不仅仅用于内存安全——它在多个层面提供编译时的安全保证。

#### 4.6.1 枚举与穷尽匹配

Rust 的枚举（enum）是代数数据类型（ADT），配合模式匹配可以实现穷尽性检查——编译器确保你处理了所有可能的变体，不可能遗漏。

```rust
enum ThreatLevel {
    Low,
    Medium,
    High,
    Critical,
}

fn response(level: ThreatLevel) -> &'static str {
    match level {
        ThreatLevel::Low => "monitor",
        ThreatLevel::Medium => "investigate",
        ThreatLevel::High => "block",
        ThreatLevel::Critical => "shutdown",
        // 如果遗漏任何一个变体，编译器会报错
    }
}
```

#### 4.6.2 Option 与空值安全

Rust 没有 null。空值通过 `Option<T>` 类型显式表示，编译器强制你在使用前处理 None 的情况：

```rust
fn find_user(id: u32) -> Option<String> {
    if id == 0 {
        None  // 用户不存在
    } else {
        Some(format!("user_{}", id))
    }
}

fn process_user(id: u32) {
    // ❌ 不能直接使用 Option<String> 作为 String
    // let name = find_user(id);
    // println!("{}", name);  // 编译错误

    // ✅ 必须显式处理 None
    match find_user(id) {
        Some(name) => println!("Found: {}", name),
        None => println!("User not found"),
    }

    // 或使用 unwrap_or 提供默认值
    let name = find_user(id).unwrap_or(String::from("anonymous"));
}
```

这消除了 Tony Hoare 所称的"十亿美元错误"——null 引用异常。在 C 中，未检查的 NULL 指针解引用是攻击者最喜欢的利用目标之一。

#### 4.6.3 Result 与错误处理

Rust 用 `Result<T, E>` 替代异常机制，编译器强制你处理错误：

```rust
use std::fs;

fn read_config(path: &str) -> Result<String, Box<dyn std::error::Error>> {
    let content = fs::read_to_string(path)?;  // ? 自动传播错误
    Ok(content)
}

fn main() {
    match read_config("/etc/app.conf") {
        Ok(config) => println!("Config loaded: {} bytes", config.len()),
        Err(e) => eprintln!("Failed to read config: {}", e),
    }
}
```

`?` 操作符是 Rust 错误处理的核心——它自动将错误类型转换（通过 `From` trait）并提前返回。这比 C 的 `errno` 检查可靠得多，也比 Go 的 `if err != nil` 简洁得多。

### 4.7 Send 与 Sync：类型级线程安全

Rust 通过两个标记 trait 将线程安全约束编码到类型系统中：

```text
Send trait：
  - 标记可以安全地在线程间转移所有权的类型
  - 几乎所有类型都自动实现 Send
  - 例外：Rc<T>（非原子引用计数）、裸指针

Sync trait：
  - 标记可以安全地在线程间共享引用的类型
  - &T: Send 当且仅当 T: Sync
  - 例外：Cell<T>、RefCell<T>（内部可变性，非线程安全）
```

```rust
use std::sync::Arc;
use std::thread;

fn thread_safety_demo() {
    let data = Arc::new(vec![1, 2, 3]);  // Arc: 原子引用计数，Send + Sync

    let handles: Vec<_> = (0..4).map(|i| {
        let data = Arc::clone(&data);
        thread::spawn(move || {
            println!("Thread {}: {:?}", i, data);
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }

    // ❌ 编译错误：Rc 不是 Send，不能跨线程
    // let data = std::rc::Rc::new(vec![1, 2, 3]);
    // thread::spawn(move || { println!("{:?}", data); });
}
```

这意味着：如果你的 Rust 程序编译通过且不使用 unsafe，它就不会有数据竞争。不需要运行时的 ThreadSanitizer 检测——类型系统在编译时就给出了证明。

### 4.8 Rust 安全特性与 C/C++ 的深度对比

#### 4.8.1 内存安全机制对比

| 安全机制 | C | C++ | Rust |
|----------|---|-----|------|
| 缓冲区溢出防护 | 无（依赖 ASan/栈保护） | 部分（std::array 带边界检查） | **编译时强制**（所有切片访问） |
| Use-After-Free 防护 | 无 | 智能指针（可绕过） | **所有权系统**（编译时） |
| 双重释放防护 | 无 | RAII（可绕过） | **所有权唯一性**（编译时） |
| 空指针防护 | 无 | 无（C++17 optional 可选） | **Option\<T\>**（编译时强制） |
| 数据竞争防护 | 无 | 无（需要手动同步） | **Send/Sync + 借用检查**（编译时） |
| 整数溢出 | 未定义行为 | 未定义行为 | debug panic + checked 方法 |
| 类型双关 | 允许（union、cast） | 允许（reinterpret_cast） | **需要 unsafe** |

#### 4.8.2 安全检查的时机差异

```text
C/C++ 的安全检查时机：
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   编译时      │     │   测试时      │     │   运行时      │
  │  类型检查     │ ──→ │  ASan/MSan   │ ──→ │  栈保护/canary│
  │  （有限）     │     │  （覆盖有限） │     │  （有性能开销）│
  └──────────────┘     └──────────────┘     └──────────────┘
        ↑ 缺失大量安全检查        ↑ 覆盖率依赖测试质量     ↑ 可被绕过

Rust 的安全检查时机：
  ┌──────────────────────────────────┐     ┌──────────────┐
  │            编译时                 │     │   运行时      │
  │  所有权检查 + 借用检查 + 生命周期 │ ──→ │  仅业务逻辑   │
  │  + 类型检查 + 穷尽匹配 + Send/Sync│     │  （无安全检查）│
  └──────────────────────────────────┘     └──────────────┘
        ↑ 内存安全由编译器证明                ↑ 安全开销为零
```

### 4.9 Rust 在安全领域的生态与应用

#### 4.9.1 安全工具生态

Rust 已经成为安全工具开发的热门语言，多个知名工具采用 Rust 编写：

| 工具 | 类型 | Rust 安全优势 |
|------|------|--------------|
| **RustScan** | 端口扫描器 | 异步 I/O + 无内存泄漏，扫描速度极快 |
| **Ferret** | Web 模糊测试 | 处理不可信输入时无崩溃风险 |
| **rustls** | TLS 实现 | 消除了 OpenSSL 类内存漏洞（Heartbleed） |
| **trust-dns** | DNS 服务器/解析器 | DNS 协议解析涉及大量二进制数据，内存安全至关重要 |
| **nushell** | 现代 Shell | 安全处理用户输入和命令执行 |
| **starship** | 终端提示符 | 安全的子进程管理 |

#### 4.9.2 操作系统与基础设施

越来越多的安全关键基础设施开始采用 Rust：

- **Linux 内核**：从 6.1 版本开始正式支持 Rust 作为第二开发语言，用于编写驱动和安全敏感模块
- **Android**：蓝牙栈、Keystore 密钥管理、DNS over HTTPS 客户端已用 Rust 重写
- **Windows**：微软正在用 Rust 重写部分核心组件
- **Firefox**：Stylo（CSS 引擎）、WebRender（渲染引擎）已用 Rust 重写
- **Cloudflare**：Pingora 代理服务器替代了部分 Nginx 功能

#### 4.9.3 密码学实现

密码学库对内存安全的要求极高——一个字节的泄露就可能被利用。Rust 在此领域的代表项目：

- **ring**：由 BoringSSL 核心开发者创建的密码学库
- **RustCrypto**：纯 Rust 密码学算法集合（AES、ChaCha20、SHA-2/3 等）
- **dalek**：椭圆曲线密码学实现（Curve25519、Ed25519）
- **age**：现代文件加密工具，设计目标是替代 GPG

### 4.10 Rust 安全特性的局限与注意事项

Rust 不是银弹。理解其安全边界对于正确使用至关重要。

#### 4.10.1 Rust 不能防止的问题

```text
Rust 的安全边界：

safe Rust 能防止的：
  ✅ 缓冲区溢出
  ✅ Use-After-Free
  ✅ 双重释放
  ✅ 数据竞争
  ✅ 空指针解引用
  ✅ 悬垂引用

safe Rust 不能防止的：
  ❌ 逻辑错误（算法错误、业务逻辑缺陷）
  ❌ 资源耗尽（无限循环、内存膨胀）
  ❌ 信息泄露（日志打印敏感数据、侧信道）
  ❌ 未定义行为（仅在 unsafe 块中可能发生）
  ❌ 依赖供应链攻击（恶意 crate）
  ❌ 死锁（Mutex 使用不当）
  ❌ 服务拒绝（panic 导致进程崩溃）
```

#### 4.10.2 panic 与安全

Rust 的 `panic!` 会展开栈并终止当前线程。虽然这不会导致未定义行为，但在安全场景中需要注意：

```rust
fn security_concern_with_panic() {
    // unwrap() 在 None 时 panic
    // 如果攻击者能触发 None，就能 DoS 整个服务
    let value: Option<i32> = None;
    // value.unwrap();  // 进程崩溃

    // 安全做法：使用 expect（带消息）或 match 处理
    match value {
        Some(v) => println!("{}", v),
        None => eprintln!("Warning: missing value, using default"),
    }
}
```

在安全关键路径上，应设置 `panic = "abort"` 以避免展开过程中的竞态条件：

```toml
[profile.release]
panic = "abort"  # panic 时直接终止进程，不展开栈
```

#### 4.10.3 依赖安全

Rust 的 crate 生态系统（crates.io）虽然方便，但也引入了供应链风险：

```text
依赖安全检查清单：

1. 使用 cargo-audit 检查已知漏洞
   $ cargo install cargo-audit
   $ cargo audit

2. 使用 cargo-deny 审查依赖许可证和重复
   $ cargo install cargo-deny
   $ cargo deny check

3. 审查 unsafe 使用情况
   $ cargo install cargo-geiger
   $ cargo geiger

4. 锁定依赖版本
   → 始终提交 Cargo.lock 到版本控制

5. 定期更新依赖
   $ cargo update
   → 更新后运行完整测试套件
```

### 4.11 Rust 安全特性的形式化验证

Rust 社区正在推进安全特性的形式化验证，增强对编译器正确性的信心：

- **RustBelt**：用 Coq 证明了 Rust 核心类型系统（包括生命周期和借用检查）的 soundness
- **Oxide**：Rust 的形式化语义模型，用于验证编译器优化的正确性
- **Miri**：Rust 的实验性解释器，能在运行时检测未定义行为（包括 unsafe 代码中的问题）
- **Prusti**：基于 Viper 的 Rust 程序验证工具，可以验证程序满足形式化规约

```bash
# 使用 Miri 检测 unsafe 代码中的未定义行为
rustup component add miri
cargo miri test
cargo miri run
```

### 4.12 本节小结

```text
Rust 安全特性体系：

┌─────────────────────────────────────────────────┐
│                编译时安全保证                      │
│  ┌───────────┐ ┌───────────┐ ┌───────────────┐  │
│  │  所有权    │ │ 借用检查  │ │  生命周期      │  │
│  │  唯一所有者│ │ 读写互斥  │ │ 引用有效性     │  │
│  │  move语义 │ │ 共享或独占│ │ 悬垂引用防护   │  │
│  └─────┬─────┘ └─────┬─────┘ └──────┬────────┘  │
│        │             │              │            │
│        ▼             ▼              ▼            │
│  ┌──────────────────────────────────────────┐    │
│  │     类型系统（Option/Result/enum）         │    │
│  │     穷尽匹配 + 空值安全 + 错误强制处理    │    │
│  └──────────────────────────────────────────┘    │
│        │             │              │            │
│        ▼             ▼              ▼            │
│  ┌──────────────────────────────────────────┐    │
│  │     线程安全（Send/Sync trait）            │    │
│  │     编译时证明无数据竞争                   │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│          unsafe 边界（人工审查区域）               │
│  → 仅 unsafe 块/函数中可能出现未定义行为           │
│  → safe 封装必须保证调用者安全                    │
│  → 审计时只需关注 unsafe 代码                    │
└─────────────────────────────────────────────────┘
```

Rust 的安全特性不是单一机制，而是一个层层递进的体系：所有权系统消除资源管理错误，借用检查器消除数据竞争，生命周期消除悬垂引用，类型系统消除空值和遗漏处理，Send/Sync trait 消除线程安全错误。每一层都在编译时验证，运行时零开销。对于安全工程师来说，这意味着编写安全基础设施时，Rust 将整类漏洞从"需要靠人小心"变成了"编译器不允许犯错"。
