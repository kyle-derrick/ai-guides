#!/bin/bash
# 自动转场监控器 - 检查进程状态，自动切换到队列模式
# 建议每5分钟运行一次

QUEUE="/tmp/ai-guides/work_queue.py"
LOG="/tmp/ai-guides/.transition_monitor.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

# 检查进程是否还在运行
is_running() {
    ps aux | grep "optimize.sh $1" | grep -v grep | grep -q "optimize.sh"
}

is_worker_running() {
    ps aux | grep "worker.sh $1" | grep -v grep | grep -q "worker.sh"
}

# 检查A是否已完成个人提升
if ! is_running "A"; then
    a_state=$(python3 -c "
import json
d = json.load(open('/tmp/ai-guides/.optimization_state_a.json'))
print(d.get('status', 'running'))
" 2>/dev/null)
    
    if [ "$a_state" = "running" ]; then
        log "A 进程已退出但状态未标记完成，可能崩溃，需要手动重启"
    else
        log "A 已完成个人提升！"
        # 启动A为队列worker
        if ! is_worker_running "A"; then
            log "启动A为队列worker (money)"
            nohup bash /tmp/ai-guides/worker.sh A money >> /tmp/ai-guides/.worker_a.log 2>&1 &
            log "A worker 已启动 (PID=$!)"
        fi
    fi
fi

# 检查C是否已完成沟通表达
if ! is_running "C"; then
    c_state=$(python3 -c "
import json
d = json.load(open('/tmp/ai-guides/.optimization_state_c.json'))
print(d.get('status', 'running'))
" 2>/dev/null)
    
    if [ "$c_state" = "running" ]; then
        log "C 进程已退出但状态未标记完成，可能崩溃，需要手动重启"
    else
        log "C 已完成沟通表达！"
        if ! is_worker_running "C"; then
            log "启动C为队列worker (money)"
            nohup bash /tmp/ai-guides/worker.sh C money >> /tmp/ai-guides/.worker_c.log 2>&1 &
            log "C worker 已启动 (PID=$!)"
        fi
    fi
fi

# 检查B是否已达到500上限并退出
if ! is_running "B"; then
    b_done=$(python3 -c "
import json
d = json.load(open('/tmp/ai-guides/.optimization_state_b.json'))
print(d.get('total_processed', 0))
" 2>/dev/null || echo "0")
    
    if [ "$b_done" -ge 500 ]; then
        log "B 已达到500文件上限！"
        if ! is_worker_running "B"; then
            log "启动B为队列worker (money)"
            nohup bash /tmp/ai-guides/worker.sh B money >> /tmp/ai-guides/.worker_b.log 2>&1 &
            log "B worker 已启动 (PID=$!)"
        fi
    fi
fi

# 释放超时任务
python3 "$QUEUE" release 2>/dev/null

# 打印状态
stats=$(python3 "$QUEUE" stats 2>/dev/null)
if [ -n "$stats" ]; then
    pending=$(echo "$stats" | python3 -c "import sys,json; s=json.load(sys.stdin); print(s['totals']['pending'])" 2>/dev/null)
    done_count=$(echo "$stats" | python3 -c "import sys,json; s=json.load(sys.stdin); print(s['totals']['done'])" 2>/dev/null)
    log "队列状态: 待处理=$pending, 完成=$done_count"
fi
