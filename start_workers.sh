#!/bin/bash
# 启动所有20个Worker（安全版：PID文件 + 先检查再启动）
cd /tmp/ai-guides

PID_DIR=".worker_pids"
mkdir -p "$PID_DIR"

for w in a b c d e f g h i j k l m n o p q r s t; do
    lock=".worker_${w}.lock"
    pidfile="$PID_DIR/${w}.pid"
    
    # 方法1: 检查PID文件
    if [ -f "$pidfile" ]; then
        old_pid=$(cat "$pidfile")
        if kill -0 "$old_pid" 2>/dev/null; then
            echo "Worker $w: 已在运行 (PID=$old_pid)，跳过"
            continue
        fi
        rm -f "$pidfile"
    fi
    
    # 方法2: 检查lock文件
    if [ -f "$lock" ]; then
        if fuser "$lock" >/dev/null 2>&1; then
            echo "Worker $w: lock被占用，跳过"
            continue
        fi
        rm -f "$lock"
    fi
    
    rm -f ".worker_${w}.heartbeat"
    nohup bash worker.sh "$w" >> ".worker_${w}.log" 2>&1 &
    echo $! > "$pidfile"
    echo "Worker $w: PID=$! 已启动"
    sleep 0.3
done

echo "=== 启动完成 ==="
