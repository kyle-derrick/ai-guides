#!/bin/bash
# 动态Worker v4 - 稳定版
# 修复: 
# - 不再调用release（由monitor统一处理）
# - cleanup清理心跳子进程
# - timeout用SIGTERM+SIGKILL
# - JSON解析更健壮
# - 失败时不遗漏cleanup

WORKER_ID="${1:-A}"
QUEUE="/tmp/ai-guides/work_queue.py"
LOG_FILE="/tmp/ai-guides/.worker_${WORKER_ID,,}.log"
PROMPT_FILE="/tmp/ai-guides/.optimize_prompt.txt"
HERMES="/opt/hermes/.venv/bin/hermes"
LOCK_FILE="/tmp/ai-guides/.worker_${WORKER_ID,,}.lock"
HEARTBEAT_FILE="/tmp/ai-guides/.worker_${WORKER_ID,,}.heartbeat"
HEARTBEAT_PID=""

# 单实例锁
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "Worker $WORKER_ID 已在运行"; exit 1; }

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$WORKER_ID] $1" >> "$LOG_FILE"
}

cleanup() {
    log "收到终止信号，安全退出"
    # 停止心跳子进程
    if [ -n "$HEARTBEAT_PID" ] && kill -0 "$HEARTBEAT_PID" 2>/dev/null; then
        kill "$HEARTBEAT_PID" 2>/dev/null
        wait "$HEARTBEAT_PID" 2>/dev/null
    fi
    rm -f "$LOCK_FILE" "$HEARTBEAT_FILE"
    exit 0
}
trap cleanup SIGTERM SIGINT SIGHUP EXIT

update_heartbeat() {
    date +%s > "$HEARTBEAT_FILE"
}

# 注册worker
python3 "$QUEUE" register "$WORKER_ID" >/dev/null 2>&1
log "=== Worker $WORKER_ID 启动 (v4) ==="

while true; do
    update_heartbeat
    
    # 领取任务（不再调用release，由monitor统一处理）
    result=$(python3 "$QUEUE" claim "$WORKER_ID" 2>/dev/null)
    
    if [ "$result" = "NONE" ] || [ -z "$result" ]; then
        log "暂无任务，等待30秒..."
        sleep 30
        continue
    fi
    
    # 解析JSON（更健壮的方式）
    file_id=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['id'])" 2>/dev/null)
    file_path=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['file_path'])" 2>/dev/null)
    book=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['book'])" 2>/dev/null)
    
    if [ -z "$file_id" ] || [ -z "$file_path" ]; then
        log "任务解析失败: $result"
        sleep 5
        continue
    fi
    
    filename=$(basename "$file_path")
    log "[$book] 开始: $filename"
    
    start_time=$(date +%s)
    
    # 更新心跳到DB
    update_heartbeat
    python3 "$QUEUE" heartbeat "$WORKER_ID" "$file_path" "$book" 2>/dev/null
    
    # 检查文件是否存在
    if [ ! -f "$file_path" ]; then
        log "[$book] 文件不存在: $file_path"
        python3 "$QUEUE" fail "$file_id" "$WORKER_ID" "file_not_found" 2>>"$LOG_FILE" >/dev/null
        continue
    fi
    
    # 构建 prompt
    full_prompt="文件路径：$file_path

$(cat "$PROMPT_FILE")"

    # 启动心跳保活进程
    (
        while true; do
            sleep 60
            update_heartbeat
            python3 "$QUEUE" heartbeat "$WORKER_ID" "$file_path" "$book" >/dev/null 2>&1
        done
    ) &
    HEARTBEAT_PID=$!
    
    # 执行hermes，超时60分钟（大文件需要更长时间），先SIGTERM再SIGKILL
    timeout --signal=TERM --kill-after=60 3600 $HERMES chat -q "$full_prompt" -Q 2>&1
    exit_code=$?
    
    # 停止心跳保活
    if [ -n "$HEARTBEAT_PID" ] && kill -0 "$HEARTBEAT_PID" 2>/dev/null; then
        kill "$HEARTBEAT_PID" 2>/dev/null
        wait "$HEARTBEAT_PID" 2>/dev/null
    fi
    HEARTBEAT_PID=""
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    if [ $exit_code -eq 0 ]; then
        python3 "$QUEUE" complete "$file_id" "$WORKER_ID" "$duration" 2>>"$LOG_FILE" >/dev/null
        log "[$book] 完成: $filename (${duration}s)"
    elif [ $exit_code -eq 124 ]; then
        python3 "$QUEUE" fail "$file_id" "$WORKER_ID" "timeout_20min" 2>>"$LOG_FILE" >/dev/null
        log "[$book] 超时(20分钟): $filename"
    else
        python3 "$QUEUE" fail "$file_id" "$WORKER_ID" "exit=$exit_code" 2>>"$LOG_FILE" >/dev/null
        log "[$book] 失败(exit=$exit_code): $filename (${duration}s)"
    fi
    
    update_heartbeat
done
