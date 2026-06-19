---
title: "Shell脚本安全编程"
type: docs
weight: 4
---

## 四、Shell脚本安全编程

Shell脚本是Linux系统管理和安全运维的核心工具，但同时也是最容易被忽视的攻击入口。一个编写不当的Shell脚本，可能导致命令注入、路径遍历、敏感信息泄露、提权攻击等严重安全问题。本章从攻击者视角和防御者视角两个维度，系统讲解Shell脚本安全编程的理论、方法和实战技巧。

### 4.1 为什么Shell脚本是高风险攻击面

Shell脚本之所以成为安全重灾区，根本原因在于它的设计哲学——**信任一切输入，直接交给解释器执行**。与编译型语言不同，Shell脚本中的变量替换、命令替换、算术展开都是在执行时动态完成的，这意味着攻击者只需控制一个字符串，就能让脚本执行任意命令。

**Shell脚本的四大攻击面**：

| 攻击面 | 风险等级 | 典型场景 | 后果 |
|---------|----------|----------|------|
| 用户输入 | 严重 | 命令行参数、read读取、环境变量 | 远程命令执行 |
| 文件内容 | 高 | 读取配置文件、日志解析 | 数据篡改、逻辑绕过 |
| 命令输出 | 中 | 捕获子命令输出做后续处理 | 命令注入 |
| 外部数据 | 中 | 网络请求、API响应 | 代码注入 |

**真实案例：配置文件注入**

某运维脚本从`/etc/app.conf`读取数据库主机名后拼接命令：

```bash
# 危险写法
DB_HOST=$(grep "^DB_HOST=" /etc/app.conf | cut -d= -f2)
ssh "$DB_HOST" "systemctl restart mysqld"
```

如果攻击者修改了配置文件为 `DB_HOST=myhost; rm -rf / #`，经过变量替换后实际执行的命令是：

```bash
ssh myhost; rm -rf / # "systemctl restart mysqld"
```

这直接导致了任意命令执行。这类漏洞在生产环境中屡见不鲜，根本原因就是脚本信任了外部数据。

### 4.2 安全脚本的基础设施：严格模式

严格模式是所有安全脚本的第一道防线。它将Shell默认的"尽量继续"策略改为"立即失败"策略，防止错误静默传播。

**标准严格模式头部**：

```bash
#!/bin/bash
# 安全脚本标准头部
set -euo pipefail
IFS=$'\n\t'
```

逐行解释每个参数的作用：

- **`set -e`**：任何命令返回非零状态码时立即退出脚本。这防止了错误被忽略后继续执行后续危险操作。例如`rm -rf /important/dir`如果目录不存在，脚本会立刻停止，而不是继续执行后续的配置修改。
- **`set -u`**：引用未定义的变量时报错退出。这防止了拼写错误导致的变量为空，进而引发意外行为。例如`rm -rf "$DIR/"`如果`DIR`未定义，不会变成`rm -rf /`。
- **`set -o pipefail`**：管道中任意命令失败时，整个管道返回失败状态码。默认情况下Shell只看管道最后一个命令的状态，这意味着`curl http://malicious.site | bash`即使curl失败，bash也会尝试执行空内容。
- **`IFS=$'\n\t'`**：将内部字段分隔符改为换行和制表符，去除空格。这防止了含空格的路径或变量被错误地拆分为多个参数。

**`set -e`的陷阱与正确使用**：

`set -e`并非万能。以下场景中，失败的命令不会触发退出：

```bash
# 场景1：if 条件中的命令
if command_that_fails; then
    echo "不会执行到这里"
fi

# 场景2：|| 后面有处理
command_that_fails || echo "已处理错误"

# 场景3：子shell中的失败
result=$(command_that_fails)  # 在某些Bash版本中不触发-e
echo "脚本继续执行"
```

正确的做法是使用 `set -e` 配合显式错误检查：

```bash
set -euo pipefail

# 用函数封装需要检查的操作
safe_command() {
    if ! "$@"; then
        echo "命令失败: $*" >&2
        return 1
    fi
}

# 或者用更明确的方式
output=$(some_command 2>&1) || {
    echo "some_command 失败: $output" >&2
    exit 1
}
```

**trap：清理陷阱**

安全脚本必须使用`trap`注册清理函数，确保异常退出时也能清理临时文件、释放锁、恢复状态：

```bash
#!/bin/bash
set -euo pipefail

# 定义清理函数
cleanup() {
    local exit_code=$?
    # 清理临时文件
    [[ -f "${TEMP_FILE:-}" ]] && rm -f "$TEMP_FILE"
    # 释放锁
    [[ -f "${LOCK_FILE:-}" ]] && rm -f "$LOCK_FILE"
    # 恢复原始设置
    [[ -n "${ORIGINAL_UMASK:-}" ]] && umask "$ORIGINAL_UMASK"
    exit "$exit_code"
}

# 注册清理函数，在脚本退出时（正常或异常）执行
trap cleanup EXIT

# 也可以针对特定信号注册
trap 'echo "收到中断信号"; exit 130' INT TERM
```

注意`trap cleanup EXIT`必须在创建临时文件或获取锁**之前**注册，否则如果脚本在创建临时文件后、注册trap之前崩溃，临时文件就不会被清理。

### 4.3 变量安全处理：引用与展开

变量处理是Shell脚本安全的核心。不当的变量引用是Shell注入漏洞的头号成因。

**黄金规则：永远用双引号包裹变量**

```bash
# 危险写法
rm -rf $DIR/
cp $FILE /backup/
ls $PATTERN

# 安全写法
rm -rf "${DIR:?变量DIR未定义}/"
cp -- "$FILE" /backup/
ls -- "$PATTERN"
```

不引用变量时，Shell会进行**单词拆分**和**文件名展开**：

```bash
# 假设 FILE="my file.txt; rm -rf /"
# 危险：未引用变量
rm $FILE
# 展开为：rm my file.txt; rm -rf /
# 三个独立命令被依次执行

# 安全：引用变量
rm -- "$FILE"
# 展开为：rm -- "my file.txt; rm -rf /"
# 一个命令，删除名为 "my file.txt; rm -rf /" 的文件
```

**变量展开的安全形式**：

```bash
# 1. 默认值：变量未定义或为空时使用默认值
echo "${VAR:-default_value}"

# 2. 强制要求变量存在：未定义时报错退出
echo "${VAR:?错误信息：VAR必须定义}"

# 3. 赋默认值：如果变量未定义则赋值
: "${VAR:=default_value}"

# 4. 字符串长度检查
if [[ ${#VAR} -eq 0 ]]; then
    echo "变量为空" >&2
    exit 1
fi

# 5. 变量值的安全替换（不使用eval）
# 危险：eval "echo \$$var_name"
# 安全：使用关联数组
declare -A config
config[host]="localhost"
config[port]="3306"
echo "${config[host]}:${config[port]}"
```

**数组与带空格的变量**：

```bash
# 文件名可能包含空格、引号、特殊字符
# 正确处理文件列表
find . -name "*.log" -print0 | while IFS= read -r -d '' file; do
    # 使用数组传递参数，避免任何字符串拼接
    rm -- "$file"
done

# 错误示例：使用for循环遍历文件名
for file in $(find . -name "*.log"); do  # 危险！
    rm -- "$file"  # 空格导致拆分
done
```

### 4.4 命令注入防御

命令注入是Shell脚本中最危险的安全漏洞类型，攻击者通过控制输入数据，让脚本执行非预期的系统命令。

**注入向量分类**：

```bash
# 1. eval注入 —— 最危险
# 危险
eval "echo $user_input"  # user_input可以是任意命令
# 修复：完全避免eval，或使用printf -v
printf -v safe_var '%s' "$user_input"

# 2. 反引号/$()注入
# 危险
result=`grep "$pattern" /etc/passwd`  # pattern可以注入命令
# 安全
grep -F -- "$pattern" /etc/passwd  # -F固定字符串匹配

# 3. 数学展开注入
# 危险
echo $(( $user_input + 1 ))  # 某些Shell版本可注入
# 安全
if [[ "$user_input" =~ ^[0-9]+$ ]]; then
    echo $(( user_input + 1 ))
else
    echo "输入不是数字" >&2
    exit 1
fi

# 4. 管道注入
# 危险
echo "$data" | sh  # data可以是任意命令
# 安全
echo "$data" > "$TEMP_FILE"
# 然后用安全方式解析文件内容
```

**`eval`的替代方案**：

很多脚本使用`eval`是因为需要动态变量名或间接引用。现代Bash提供了更安全的替代：

```bash
# 旧方法：eval实现间接引用（危险）
var_name="my_var"
eval "value=\$$var_name"  # 命令注入风险

# 新方法1：使用nameref（Bash 4.3+）
declare -n ref="$var_name"
echo "$ref"  # 安全

# 新方法2：使用关联数组（Bash 4.0+）
declare -A config
config[host]="localhost"
config[port]="3306"
key="host"
echo "${config[$key]}"  # 安全

# 旧方法：eval构建动态命令（危险）
eval "$cmd_string"

# 新方法：使用数组构建命令
declare -a cmd=(command arg1 arg2)
if [[ condition ]]; then
    cmd+=(--flag)
fi
"${cmd[@]}"  # 安全执行
```

**`read`的安全使用**：

```bash
# 危险：read默认会处理反斜杠转义
read -p "输入文件名: " filename
# 如果输入是 "file\nrm -rf /"，read会解释换行

# 安全：使用 -r 选项禁止反斜杠转义
read -r -p "输入文件名: " filename

# 完整的安全输入循环
while IFS= read -r line; do
    # 处理每行
    process_line "$line"
done < "$input_file"
```

### 4.5 输入验证与消毒

输入验证是防御注入攻击的第一道关卡。在Shell脚本中，验证必须发生在任何使用输入数据的操作之前。

**验证策略**：

```bash
# 1. 白名单验证（最安全）
validate_username() {
    local username="$1"
    if [[ ! "$username" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
        echo "用户名格式不合法: $username" >&2
        return 1
    fi
}

# 2. 数字验证
validate_port() {
    local port="$1"
    if [[ ! "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
        echo "端口号不合法: $port" >&2
        return 1
    fi
}

# 3. 路径验证（防路径遍历）
validate_path() {
    local path="$1"
    # 检查是否包含路径遍历
    if [[ "$path" == *".."* ]] || [[ "$path" == *";"* ]] || [[ "$path" == *"|"* ]]; then
        echo "路径包含危险字符: $path" >&2
        return 1
    fi
    # 更严格：只允许白名单字符
    if [[ ! "$path" =~ ^[a-zA-Z0-9/_.-]+$ ]]; then
        echo "路径包含非法字符: $path" >&2
        return 1
    fi
}

# 4. 文件存在性验证（必须在使用前）
validate_file() {
    local file="$1"
    # 检查文件是否存在
    if [[ ! -e "$file" ]]; then
        echo "文件不存在: $file" >&2
        return 1
    fi
    # 检查是否为符号链接（防链接攻击）
    if [[ -L "$file" ]]; then
        echo "不接受符号链接: $file" >&2
        return 1
    fi
    # 检查文件是否在允许的目录内
    local real_path
    real_path=$(realpath "$file")
    if [[ "$real_path" != /data/safe_dir/* ]]; then
        echo "文件不在允许的目录内: $file" >&2
        return 1
    fi
}

# 5. 综合验证函数
validate_input() {
    local input="$1"
    local type="$2"

    case "$type" in
        username) validate_username "$input" ;;
        port)     validate_port "$input" ;;
        path)     validate_path "$input" ;;
        *)
            echo "未知的验证类型: $type" >&2
            return 1
            ;;
    esac
}
```

**从不可信源读取数据的安全模式**：

```bash
# 读取并验证命令行参数
process_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --host)
                [[ $# -lt 2 ]] && { echo "缺少--host参数值" >&2; exit 1; }
                HOST="$2"
                validate_host "$HOST" || exit 1
                shift 2
                ;;
            --port)
                [[ $# -lt 2 ]] && { echo "缺少--port参数值" >&2; exit 1; }
                PORT="$2"
                validate_port "$PORT" || exit 1
                shift 2
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                echo "未知参数: $1" >&2
                usage >&2
                exit 1
                ;;
        esac
    done
}

# 读取并验证配置文件（逐行解析，不用source）
load_config() {
    local config_file="$1"
    [[ ! -f "$config_file" ]] && { echo "配置文件不存在" >&2; return 1; }

    while IFS='=' read -r key value; do
        # 跳过注释和空行
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        # 去除首尾空格
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        # 验证键名格式
        [[ ! "$key" =~ ^[A-Z_]+$ ]] && continue
        # 使用关联数组存储
        config["$key"]="$value"
    done < "$config_file"
}
```

### 4.6 安全的临时文件处理

临时文件是另一个常见的安全漏洞来源。不安全的临时文件创建可能导致符号链接攻击（symlink race）和信息泄露。

**临时文件安全规范**：

```bash
# 必须使用mktemp，绝对不要自己拼接临时文件名
# 危险：可预测的文件名，攻击者可以提前创建符号链接
TEMP_FILE="/tmp/myscript.$$"  # PID可预测
TEMP_FILE="/tmp/myscript_tmp"  # 名称固定

# 安全：mktemp生成不可预测的文件名
TEMP_FILE=$(mktemp /tmp/myscript.XXXXXXXXXX)
# 或使用专用目录
TEMP_DIR=$(mktemp -d /tmp/myscript.XXXXXXXXXX)
TEMP_FILE="$TEMP_DIR/data"

# 更安全：在用户的专属目录下创建
TEMP_FILE=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/myscript.XXXXXXXXXX")

# 权限设置：只有属主可读写
chmod 600 "$TEMP_FILE"

# 原子写入：先写临时文件再移动
write_config_safely() {
    local target_file="$1"
    local content="$2"
    local temp_file
    temp_file=$(mktemp "${target_file}.tmp.XXXXXXXXXX")
    
    echo "$content" > "$temp_file"
    chmod 600 "$temp_file"
    # 原子移动：在同一个文件系统上，mv是原子操作
    mv -- "$temp_file" "$target_file"
}
```

**临时文件生命周期管理**：

```bash
#!/bin/bash
set -euo pipefail

# 创建临时目录，所有临时文件放在里面
WORK_DIR=$(mktemp -d /tmp/myscript.XXXXXXXXXX)

# 注册清理函数（必须在创建工作目录后立即注册）
trap 'rm -rf "$WORK_DIR"' EXIT INT TERM

# 在工作目录内创建临时文件
INPUT_FILE="$WORK_DIR/input.txt"
OUTPUT_FILE="$WORK_DIR/output.txt"
LOG_FILE="$WORK_DIR/processing.log"

# 脚本正常执行...
process_data > "$OUTPUT_FILE" 2> "$LOG_FILE"

# 检查处理结果
if [[ -s "$OUTPUT_FILE" ]]; then
    mv -- "$OUTPUT_FILE" "/data/results.txt"
fi

# 脚本结束时，trap自动清理WORK_DIR及其所有内容
```

**`noclobber`选项防止意外覆盖**：

```bash
# 开启noclobber：防止>意外覆盖已有文件
set -o noclobber

# 写入时使用>|强制覆盖（显式意图）
echo "data" >| "$target_file"

# 追加使用>>（不受noclobber影响）
echo "log" >> "$log_file"
```

### 4.7 凭据与密钥管理

在脚本中硬编码密码和密钥是最常见的安全反模式之一。即使脚本是私有的，版本控制系统、日志文件、进程列表都可能泄露这些信息。

**禁止的做法**：

```bash
# 绝对禁止
PASSWORD="s3cret123"
API_KEY="sk-abc123..."
sshpass -p "mypassword" ssh user@host

# 为什么危险：
# 1. ps aux 可以看到命令行参数中的密码
# 2. /proc/<pid>/cmdline 会暴露密码
# 3. .bash_history 会记录命令
# 4. 版本控制会永久保存密码
```

**安全的凭据管理方案**：

```bash
# 方案1：从环境变量读取（配合容器或CI/CD的密钥管理）
# 使用前必须验证变量存在
: "${DB_PASSWORD:?请设置DB_PASSWORD环境变量}"
mysql -u dbuser -p"$DB_PASSWORD" mydb

# 方案2：从文件读取密钥（权限必须600）
read_credential() {
    local cred_file="$1"
    if [[ ! -f "$cred_file" ]]; then
        echo "凭据文件不存在: $cred_file" >&2
        return 1
    fi
    # 检查文件权限
    local perms
    perms=$(stat -c '%a' "$cred_file" 2>/dev/null || stat -f '%A' "$cred_file")
    if [[ "$perms" != "600" ]]; then
        echo "凭据文件权限不安全: $perms (应为600)" >&2
        return 1
    fi
    cat "$cred_file"
}

# 方案3：从标准输入读取密码（不回显）
read_password() {
    local prompt="${1:-密码: }"
    local password
    read -r -s -p "$prompt" password
    echo  # 换行
    echo "$password"
}

# 方案4：使用keyring/secret管理工具
# gpg加密的凭据文件
read_encrypted_credential() {
    local enc_file="$1"
    gpg --quiet --batch --decrypt "$enc_file"
}

# 方案5：使用secret工具（如age、sops）
# age加密
read_age_secret() {
    local enc_file="$1"
    local key_file="$2"
    age --decrypt -i "$key_file" "$enc_file"
}
```

**进程列表中的凭据保护**：

```bash
# 危险：密码出现在ps输出中
mysql -u root -p"$PASSWORD" -e "SELECT 1"

# 安全方式1：使用配置文件
cat > ~/.my.cnf.tmp << EOF
[client]
user=root
password=${PASSWORD}
EOF
chmod 600 ~/.my.cnf.tmp
mv ~/.my.cnf.tmp ~/.my.cnf
mysql -e "SELECT 1"
rm -f ~/.my.cnf

# 安全方式2：使用环境变量（MySQL支持）
MYSQL_PWD="$PASSWORD" mysql -u root -e "SELECT 1"

# 安全方式3：使用--defaults-file
mysql --defaults-file=<(echo -e "[client]\npassword=$PASSWORD") -u root -e "SELECT 1"
```

### 4.8 文件权限与访问控制

脚本中的权限操作直接影响系统安全。错误的权限设置可能导致敏感文件被未授权访问，或脚本以过高权限运行。

**脚本文件本身的权限**：

```bash
# 脚本文件权限设置
chmod 700 /usr/local/bin/admin_script.sh    # 只有属主可执行
chmod 750 /usr/local/bin/shared_script.sh   # 属主和组可执行

# 绝对不要对安全脚本设置777权限
# 绝对不要将安全脚本放在world-writable目录
```

**运行时权限检查**：

```bash
#!/bin/bash
set -euo pipefail

# 检查是否以root运行（某些操作需要）
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "此脚本需要root权限运行" >&2
        echo "用法: sudo $0 [参数]" >&2
        exit 1
    fi
}

# 检查是否不应该以root运行（最小权限原则）
check_not_root() {
    if [[ $EUID -eq 0 ]]; then
        echo "安全警告：此脚本不应以root运行" >&2
        exit 1
    fi
}

# 安全的权限设置操作
safe_chmod() {
    local file="$1"
    local mode="$2"
    # 验证文件路径
    if [[ ! -e "$file" ]]; then
        echo "文件不存在: $file" >&2
        return 1
    fi
    # 验证权限模式格式
    if [[ ! "$mode" =~ ^[0-7]{3,4}$ ]]; then
        echo "无效的权限模式: $mode" >&2
        return 1
    fi
    chmod "$mode" "$file"
}

# 安全的所有权变更
safe_chown() {
    local target="$1"
    local owner="$2"
    # 验证所有者存在
    if ! id "$owner" &>/dev/null; then
        echo "用户不存在: $owner" >&2
        return 1
    fi
    # 使用-R时需要特别小心，防止符号链接跟随
    chown --no-dereference "$owner" "$target"
}
```

**umask设置**：

```bash
# 在脚本开始时设置安全的umask
# 077：创建的文件只有属主可读写，目录只有属主可访问
# 这是安全脚本的标准设置
ORIGINAL_UMASK=$(umask)
umask 077

# 脚本结束时恢复
trap 'umask "$ORIGINAL_UMASK"' EXIT

# 如果脚本需要创建其他用户可读的文件，临时修改umask
umask 022  # 文件644，目录755
create_public_file
umask 077  # 恢复严格模式
```

### 4.9 日志与审计

安全脚本必须有完善的日志记录。日志不仅用于调试，更是事后审计和取证的关键证据。

**结构化日志框架**：

```bash
#!/bin/bash
set -euo pipefail

# 日志级别定义
readonly LOG_LEVEL_DEBUG=0
readonly LOG_LEVEL_INFO=1
readonly LOG_LEVEL_WARN=2
readonly LOG_LEVEL_ERROR=3

# 当前日志级别
LOG_LEVEL="${LOG_LEVEL:-$LOG_LEVEL_INFO}"
LOG_FILE="${LOG_FILE:-/var/log/security_script.log}"

# 日志函数
log() {
    local level="$1"
    local message="$2"
    local level_num
    
    case "$level" in
        DEBUG) level_num=$LOG_LEVEL_DEBUG ;;
        INFO)  level_num=$LOG_LEVEL_INFO ;;
        WARN)  level_num=$LOG_LEVEL_WARN ;;
        ERROR) level_num=$LOG_LEVEL_ERROR ;;
        *)     level_num=$LOG_LEVEL_INFO ;;
    esac
    
    # 过滤低级别日志
    (( level_num < LOG_LEVEL )) && return
    
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S %z')
    local caller_info="${BASH_SOURCE[1]:-unknown}:${BASH_LINENO[0]:-0}"
    
    local log_entry="[$timestamp] [$level] [$caller_info] $message"
    
    # 输出到stderr
    echo "$log_entry" >&2
    
    # 写入日志文件
    echo "$log_entry" >> "$LOG_FILE" 2>/dev/null || true
}

# 便捷函数
log_debug() { log "DEBUG" "$*"; }
log_info()  { log "INFO" "$*"; }
log_warn()  { log "WARN" "$*"; }
log_error() { log "ERROR" "$*"; }

# 安全事件专用日志
log_security_event() {
    local event_type="$1"
    local details="$2"
    local user="${3:-$(whoami)}"
    local source_ip="${SSH_CLIENT:-unknown}"
    
    log "WARN" "SECURITY_EVENT type=$event_type user=$user src_ip=$source_ip details=$details"
}
```

**审计跟踪**：

```bash
# 记录关键操作的审计日志
audit_log() {
    local action="$1"
    local target="$2"
    local result="$3"
    local audit_file="/var/log/audit/script_audit.log"
    
    local entry
    entry=$(printf '%s|%s|%s|%s|%s|%s' \
        "$(date -Iseconds)" \
        "$(whoami)" \
        "$action" \
        "$target" \
        "$result" \
        "$$")
    
    echo "$entry" >> "$audit_file"
}

# 使用示例
perform_action() {
    local file="$1"
    audit_log "ACCESS" "$file" "ATTEMPT"
    
    if process_file "$file"; then
        audit_log "MODIFY" "$file" "SUCCESS"
    else
        audit_log "MODIFY" "$file" "FAILURE"
    fi
}
```

### 4.10 静态分析工具：ShellCheck

ShellCheck是Shell脚本的静态分析工具，可以在不运行脚本的情况下发现潜在的安全问题和错误。它应该成为每个Shell脚本的必备检查工具。

**ShellCheck安装与使用**：

```bash
# 安装
# Debian/Ubuntu
apt install shellcheck

# macOS
brew install shellcheck

# 使用
shellcheck my_script.sh

# 集成到CI/CD
shellcheck --severity=warning --format=gcc my_script.sh

# 忽略特定警告（不推荐，但在必要时使用）
# shellcheck disable=SC2086
echo $unquoted_var

# 检查整个目录
find /path/to/scripts -name '*.sh' -exec shellcheck {} +
```

**ShellCheck常检测到的安全问题**：

| SC编号 | 严重度 | 问题描述 | 修复方法 |
|--------|--------|----------|----------|
| SC2086 | 警告 | 变量未加引号 | 使用`"$var"`包裹 |
| SC2046 | 警告 | 命令替换未引用 | 使用`"$(cmd)"`包裹 |
| SC2006 | 风格 | 使用反引号 | 改用`$(cmd)` |
| SC2012 | 信息 | 使用ls而非find | 改用`find`或`stat` |
| SC2155 | 警告 | declare和赋值分离 | `local var; var=$(cmd)` |
| SC2162 | 信息 | read缺少-r选项 | 使用`read -r` |
| SC2181 | 风格 | 检查退出码而非$? | 直接`if command` |
| SC2029 | 警告 | SSH命令中的变量扩展 | 用单引号或转义 |

**ShellCheck规则详解与示例**：

```bash
# SC2086: 双引号变量
# 错误
echo $HOME/$USER
rm $file
# 修复
echo "$HOME/$USER"
rm -- "$file"

# SC2155: declare和赋值分离
# 错误（如果cmd失败，local会隐藏退出码）
local result=$(some_command)
# 修复
local result
result=$(some_command)

# SC2012: 使用ls获取文件信息
# 错误（文件名可能包含特殊字符）
count=$(ls /dir | wc -l)
# 修复
count=$(find /dir -maxdepth 1 -type f | wc -l)
```

### 4.11 完整的安全脚本模板

以下是一个生产级安全脚本模板，整合了前述所有安全实践：

```bash
#!/bin/bash
#
# 安全脚本模板
# 用途：[描述脚本功能]
# 作者：[作者名]
# 日期：[创建日期]
# 版本：1.0.0
#

# ============================================================
# 严格模式
# ============================================================
set -euo pipefail
IFS=$'\n\t'

# ============================================================
# 全局常量
# ============================================================
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly SCRIPT_VERSION="1.0.0"
readonly LOCK_FILE="/var/run/${SCRIPT_NAME}.pid"

# ============================================================
# 日志配置
# ============================================================
readonly LOG_FILE="/var/log/${SCRIPT_NAME%.*}.log"
readonly LOG_LEVEL="${LOG_LEVEL:-INFO}"

log() {
    local level="$1"; shift
    printf '[%s] [%s] [%s] %s\n' \
        "$(date '+%Y-%m-%d %H:%M:%S')" \
        "$level" \
        "$SCRIPT_NAME" \
        "$*" | tee -a "$LOG_FILE" >&2
}
log_info()  { log "INFO"  "$@"; }
log_warn()  { log "WARN"  "$@"; }
log_error() { log "ERROR" "$@"; }
log_debug() { [[ "$LOG_LEVEL" == "DEBUG" ]] && log "DEBUG" "$@"; }

# ============================================================
# 清理与信号处理
# ============================================================
cleanup() {
    local exit_code=$?
    log_debug "清理中... (退出码: $exit_code)"
    [[ -f "${LOCK_FILE}" ]] && rm -f "$LOCK_FILE"
    [[ -d "${WORK_DIR:-}" ]] && rm -rf "$WORK_DIR"
    log_info "脚本结束"
    exit "$exit_code"
}

trap cleanup EXIT
trap 'log_warn "收到INT信号"; exit 130' INT
trap 'log_warn "收到TERM信号"; exit 143' TERM

# ============================================================
# 输入验证
# ============================================================
validate_args() {
    local errors=0
    
    # 验证必要参数
    if [[ -z "${TARGET_HOST:-}" ]]; then
        log_error "缺少必要参数: --host"
        ((errors++))
    fi
    
    if [[ -n "${TARGET_PORT:-}" ]]; then
        if [[ ! "$TARGET_PORT" =~ ^[0-9]+$ ]] || (( TARGET_PORT < 1 || TARGET_PORT > 65535 )); then
            log_error "端口号无效: $TARGET_PORT"
            ((errors++))
        fi
    fi
    
    (( errors > 0 )) && return 1
    return 0
}

# ============================================================
# 进程锁
# ============================================================
acquire_lock() {
    if [[ -f "$LOCK_FILE" ]]; then
        local pid
        pid=$(cat "$LOCK_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            log_error "脚本已在运行 (PID: $pid)"
            exit 1
        fi
        log_warn "清理过时的锁文件"
        rm -f "$LOCK_FILE"
    fi
    echo $$ > "$LOCK_FILE"
}

# ============================================================
# 参数解析
# ============================================================
usage() {
    cat << EOF
用法: $SCRIPT_NAME [选项]

选项:
    --host <主机>       目标主机（必需）
    --port <端口>       目标端口（默认: 80）
    --timeout <秒>      超时时间（默认: 30）
    --dry-run           仅显示操作，不执行
    --verbose           启用详细日志
    --help              显示此帮助信息
EOF
}

TARGET_HOST=""
TARGET_PORT="80"
TIMEOUT="30"
DRY_RUN=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --host)
                [[ $# -lt 2 ]] && { log_error "--host需要参数值"; exit 1; }
                TARGET_HOST="$2"
                shift 2
                ;;
            --port)
                [[ $# -lt 2 ]] && { log_error "--port需要参数值"; exit 1; }
                TARGET_PORT="$2"
                shift 2
                ;;
            --timeout)
                [[ $# -lt 2 ]] && { log_error "--timeout需要参数值"; exit 1; }
                TIMEOUT="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                LOG_LEVEL="DEBUG"
                shift
                ;;
            --help)
                usage
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                usage >&2
                exit 1
                ;;
        esac
    done
}

# ============================================================
# 主逻辑
# ============================================================
main() {
    parse_args "$@"
    
    log_info "脚本启动 (版本: $SCRIPT_VERSION)"
    acquire_lock
    
    if ! validate_args; then
        log_error "参数验证失败"
        exit 1
    fi
    
    # 创建临时工作目录
    WORK_DIR=$(mktemp -d "/tmp/${SCRIPT_NAME}.XXXXXXXXXX")
    chmod 700 "$WORK_DIR"
    log_debug "工作目录: $WORK_DIR"
    
    # 执行业务逻辑
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] 将连接到 $TARGET_HOST:$TARGET_PORT"
    else
        log_info "连接到 $TARGET_HOST:$TARGET_PORT"
        # ... 实际业务逻辑 ...
    fi
    
    log_info "执行完成"
}

main "$@"
```

### 4.12 实战案例：系统安全检查脚本

以下是经过安全加固的系统安全检查脚本，展示了所有安全编程实践的综合应用：

```bash
#!/bin/bash
#
# 系统安全检查脚本（安全加固版）
# 所有输出格式化为结构化报告
#

set -euo pipefail
IFS=$'\n\t'

# 安全的临时目录
REPORT_DIR=$(mktemp -d /tmp/security_check.XXXXXXXXXX)
trap 'rm -rf "$REPORT_DIR"' EXIT INT TERM
umask 077

REPORT_FILE="$REPORT_DIR/report.txt"
ALERT_FILE="$REPORT_DIR/alerts.txt"

# 初始化报告
{
    echo "========================================="
    echo "  系统安全检查报告"
    echo "  生成时间: $(date '+%Y-%m-%d %H:%M:%S %z')"
    echo "  主机名: $(hostname)"
    echo "  内核版本: $(uname -r)"
    echo "========================================="
} > "$REPORT_FILE"

# 辅助函数：记录检查项
check_item() {
    local category="$1"
    local description="$2"
    shift 2
    
    {
        echo ""
        echo "--- [$category] $description ---"
        "$@" 2>/dev/null || echo "(检查失败或无数据)"
    } >> "$REPORT_FILE"
}

# 辅助函数：记录告警
alert() {
    local severity="$1"
    local message="$2"
    echo "[$severity] $message" >> "$ALERT_FILE"
    echo "[告警] $message" >&2
}

# ---- 1. 文件系统检查 ----

# SUID/SGID文件（特权文件）
check_item "文件系统" "SUID文件检查" find / -xdev -perm -4000 -type f -ls

# 可被世界写入的关键目录
check_item "文件系统" "可写关键目录检查" find /etc /usr /var -xdev -writable -type d -ls

# 空密码账户
check_item "认证" "空密码账户检查" awk -F: '($2 == "" || $2 == "!") {print $1}' /etc/shadow

# UID 0 用户（应只有root）
uid0_users=$(awk -F: '$3 == 0 && $1 != "root" {print $1}' /etc/passwd)
if [[ -n "$uid0_users" ]]; then
    alert "严重" "发现非root的UID 0用户: $uid0_users"
fi
check_item "认证" "UID 0 用户检查" awk -F: '$3 == 0 {print $1}' /etc/passwd

# ---- 2. 网络检查 ----

# 开放端口
check_item "网络" "监听端口" ss -tunlp

# 防火墙规则
check_item "网络" "iptables规则" iptables -L -n -v

# ---- 3. 进程检查 ----

# 高CPU进程
check_item "进程" "高CPU进程 (>50%)" ps aux --sort=-%cpu --no-headers -e awk '$3 > 50'

# 异常网络连接
check_item "网络" "已建立的连接" ss -tunp state established

# ---- 4. 日志检查 ----

# SSH暴力破解
if [[ -f /var/log/auth.log ]]; then
    failed_count=$(grep -c "Failed password" /var/log/auth.log 2>/dev/null || echo "0")
    if (( failed_count > 100 )); then
        alert "警告" "SSH登录失败次数: $failed_count（可能存在暴力破解）"
    fi
    check_item "日志" "SSH失败登录统计" grep "Failed password" /var/log/auth.log
fi

# ---- 5. 定时任务检查 ----

check_item "定时任务" "当前用户crontab" crontab -l
check_item "定时任务" "系统cron目录" ls -la /etc/cron.*

# ---- 生成摘要 ----

alert_count=0
[[ -f "$ALERT_FILE" ]] && alert_count=$(wc -l < "$ALERT_FILE")

{
    echo ""
    echo "========================================="
    echo "  检查摘要"
    echo "  告警数量: $alert_count"
    echo "========================================="
    
    if [[ -f "$ALERT_FILE" ]]; then
        echo ""
        echo "告警详情:"
        cat "$ALERT_FILE"
    fi
} >> "$REPORT_FILE"

# 输出报告
cat "$REPORT_FILE"
```

### 4.13 SSH暴力破解检测脚本（安全加固版）

```bash
#!/bin/bash
#
# SSH暴力破解检测与自动封禁脚本
# 功能：检测SSH暴力破解尝试，支持自动封禁和报告生成
#

set -euo pipefail
IFS=$'\n\t'

# 配置参数
readonly LOG_FILE="${LOG_FILE:-/var/log/auth.log}"
readonly THRESHOLD="${THRESHOLD:-10}"
readonly REPORT_DAYS="${REPORT_DAYS:-7}"
readonly AUTO_BAN="${AUTO_BAN:-false}"
readonly BAN_DURATION="${BAN_DURATION:-3600}"

# 检查依赖
check_dependencies() {
    local missing=()
    for cmd in awk sort uniq; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    
    if [[ "${#missing[@]}" -gt 0 ]]; then
        echo "缺少依赖: ${missing[*]}" >&2
        return 1
    fi
}

# 检查日志文件
check_log() {
    if [[ ! -f "$LOG_FILE" ]]; then
        echo "日志文件不存在: $LOG_FILE" >&2
        return 1
    fi
    if [[ ! -r "$LOG_FILE" ]]; then
        echo "无权读取日志文件: $LOG_FILE (需要sudo)" >&2
        return 1
    fi
}

# 提取暴力破解IP
extract_brute_force_ips() {
    local since_date
    since_date=$(date -d "$REPORT_DAYS days ago" '+%b %e' 2>/dev/null || date -v-"${REPORT_DAYS}"d '+%b %e')
    
    grep "Failed password" "$LOG_FILE" | \
        grep -oP '(?:from |from ip )\K[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | \
        sort | uniq -c | sort -rn
}

# 生成报告
generate_report() {
    echo "========================================="
    echo "  SSH暴力破解检测报告"
    echo "  时间范围: 最近 ${REPORT_DAYS} 天"
    echo "  告警阈值: ${THRESHOLD} 次/天"
    echo "  生成时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================="
    echo ""
    
    local total_attempts=0
    local suspicious_ips=0
    
    while read -r count ip; do
        ((total_attempts += count))
        
        if (( count >= THRESHOLD )); then
            ((suspicious_ips++))
            printf "  [!] %-18s %6d 次失败\n" "$ip" "$count"
            
            # 自动封禁
            if [[ "$AUTO_BAN" == "true" ]] && command -v iptables &>/dev/null; then
                if ! iptables -C INPUT -s "$ip" -j DROP 2>/dev/null; then
                    iptables -A INPUT -s "$ip" -j DROP
                    echo "  [封禁] 已封禁 $ip"
                    # 设置定时解封
                    (sleep "$BAN_DURATION" && iptables -D INPUT -s "$ip" -j DROP 2>/dev/null) &
                fi
            fi
        else
            printf "  [ ] %-18s %6d 次失败\n" "$ip" "$count"
        fi
    done < <(extract_brute_force_ips)
    
    echo ""
    echo "========================================="
    echo "  统计"
    echo "  总尝试次数: $total_attempts"
    echo "  可疑IP数量: $suspicious_ips"
    echo "========================================="
}

# 主函数
main() {
    check_dependencies
    check_log
    generate_report
}

main "$@"
```

### 4.14 常见安全误区与纠正

**误区1：认为`-f`检查足够安全**

```bash
# 误区：-f检查防止了文件不存在的错误
if [[ -f "$file" ]]; then
    rm "$file"  # 看起来安全？
fi

# 问题：TOCTOU竞态条件
# 在-f检查和rm执行之间，文件可能被替换为符号链接

# 纠正：使用原子操作或跟随安全模式
# 方案1：直接操作，处理错误
rm -- "$file" 2>/dev/null || true

# 方案2：使用--no-dereference
rm --one-file-system -- "$file"
```

**误区2：用`which`检查命令是否存在**

```bash
# 误区
if which python3 &>/dev/null; then
    python3 script.py
fi

# 问题：which不是POSIX标准，某些系统可能返回错误路径

# 纠正：使用command -v
if command -v python3 &>/dev/null; then
    python3 script.py
fi
```

**误区3：忽略命令替换的退出码**

```bash
# 误区
output=$(cmd_that_might_fail)
echo "$output"  # cmd失败时output为空，但脚本继续

# 纠正：分离声明和赋值，检查退出码
output=$(cmd_that_might_fail) || {
    echo "命令失败" >&2
    exit 1
}
```

**误区4：用`echo`输出数据到文件**

```bash
# 误区：echo处理转义字符的行为不可预测
echo "$data" > "$file"

# 纠正：使用printf
printf '%s\n' "$data" > "$file"

# 或者处理特殊字符
printf '%q\n' "$data" > "$file"  # 自动转义
```

**误区5：在函数中声明local变量时赋值**

```bash
# 误区：如果some_command失败，local会隐藏退出码
my_function() {
    local result=$(some_command)
    # set -e 不会在这里退出，因为local总是返回0
}

# 纠正：声明和赋值分开
my_function() {
    local result
    result=$(some_command)  # 如果失败，set -e会生效
}
```

**误区6：不处理信号导致孤儿进程**

```bash
# 误区：脚本收到信号后退出，但子进程继续运行
some_background_process &
# 如果脚本被kill，子进程成为孤儿

# 纠正：追踪并清理子进程
PIDS=()

start_worker() {
    some_background_process &
    PIDS+=($!)
}

cleanup_workers() {
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
}

trap cleanup_workers EXIT
```

**误区7：用`source`加载配置文件**

```bash
# 误区：source会执行配置文件中的任意代码
source /etc/app/config  # 如果config被篡改，任意代码执行

# 纠正：逐行解析配置文件
while IFS='=' read -r key value; do
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$key" ]] && continue
    # 验证key格式
    [[ ! "$key" =~ ^[A-Z_]+$ ]] && continue
    # 只接受简单的值
    [[ "$value" =~ [\$\`\;] ]] && continue
    config["$key"]="$value"
done < /etc/app/config
```

### 4.15 进阶话题：Shell脚本的安全测试

**单元测试框架（使用shunit2）**：

```bash
#!/bin/bash
# 测试安全函数

# 加载被测函数
source ./security_functions.sh

# 加载测试框架
source /usr/local/lib/shunit2

test_validate_username_valid() {
    validate_username "admin"
    assertEquals "有效用户名应通过" 0 $?
}

test_validate_username_invalid() {
    validate_username "admin; rm -rf /"
    assertNotEquals "注入尝试应失败" 0 $?
}

test_validate_port_in_range() {
    validate_port "8080"
    assertEquals "有效端口应通过" 0 $?
}

test_validate_port_out_of_range() {
    validate_port "99999"
    assertNotEquals "超范围端口应失败" 0 $?
}
```

**Fuzz测试**：

```bash
#!/bin/bash
# 简单的fuzz测试：用随机输入测试脚本的健壮性

FUZZ_ITERATIONS=1000
SCRIPT_UNDER_TEST="./target_script.sh"

for ((i=0; i<FUZZ_ITERATIONS; i++)); do
    # 生成随机输入
    random_input=$(head -c 100 /dev/urandom | base64 | tr -d '\n')
    
    # 运行脚本，捕获退出码
    timeout 5 "$SCRIPT_UNDER_TEST" "$random_input" &>/dev/null
    exit_code=$?
    
    # 检查是否有段错误或异常退出
    if [[ $exit_code -eq 139 ]]; then
        echo "迭代 $i: 段错误！输入: $random_input"
    elif [[ $exit_code -eq 137 ]]; then
        echo "迭代 $i: 超时或OOM"
    fi
done
```

### 4.16 Shell脚本安全检查清单

在发布任何Shell脚本之前，使用以下清单进行最终检查：

```text
[ ] 是否使用 #!/bin/bash（而非#!/bin/sh，除非需要POSIX兼容）
[ ] 是否设置了 set -euo pipefail
[ ] 是否设置了 IFS=$'\n\t'
[ ] 是否使用 trap 注册了清理函数
[ ] 所有变量是否使用双引号引用
[ ] 是否避免了 eval、source 不可信文件
[ ] 是否使用 mktemp 创建临时文件
[ ] 是否设置了安全的 umask
[ ] 是否有输入验证（白名单优于黑名单）
[ ] 凭据是否从安全存储读取（不硬编码）
[ ] 是否使用 ShellCheck 通过无警告
[ ] 是否有适当的日志记录
[ ] 脚本文件权限是否为 700 或 750
[ ] 是否处理了符号链接和路径遍历
[ ] 是否有进程锁防止并发执行
```
