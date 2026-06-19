#!/bin/bash
# 杀死所有Worker（通过PID文件 + lock文件fuser）
cd /tmp/ai-guides

PID_DIR=".worker_pids"
mkdir -p "$PID_DIR"

for w in a b c d e f g h i j k l m n o p q r s t; do
    lock=".worker_${w}.lock"
    pidfile="$PID_DIR/${w}.pid"
    
    # 方法1: PID文件
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Worker $w: 杀死 PID=$pid"
            kill "$pid" 2>/dev/null
        fi
        rm -f "$pidfile"
    fi
    
    # 方法2: lock文件fuser
    if [ -f "$lock" ]; then
        pids=$(fuser "$lock" 2>/dev/null | tr -s ' ')
        if [ -n "$pids" ]; then
            echo "Worker $w: 杀死lock持有者 $pids"
            echo "$pids" | tr ' ' '\n' | xargs -r kill 2>/dev/null
        fi
    fi
done

sleep 3

# 强杀残留
for w in a b c d e f g h i j k l m n o p q r s t; do
    lock=".worker_${w}.lock"
    if [ -f "$lock" ]; then
        pids=$(fuser "$lock" 2>/dev/null | tr -s ' ')
        if [ -n "$pids" ]; then
            echo "Worker $w: 强杀 $pids"
            echo "$pids" | tr ' ' '\n' | xargs -r kill -9 2>/dev/null
        fi
    fi
done

sleep 1

# 清理
rm -f .worker_*.lock .worker_*.heartbeat
rm -rf "$PID_DIR"

# 杀死所有hermes chat -q进程（但不杀hermes gateway）
ps -eo pid,args | grep "hermes[.]venv.*chat.*-q" | grep -v grep | awk '{print $1}' | while read pid; do
    kill "$pid" 2>/dev/null
done
sleep 2
ps -eo pid,args | grep "hermes[.]venv.*chat.*-q" | grep -v grep | awk '{print $1}' | while read pid; do
    kill -9 "$pid" 2>/dev/null
done

echo "=== 清理完成 ==="
