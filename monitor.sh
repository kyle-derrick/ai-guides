#!/bin/bash
# Worker健康监控 v5 - 修复版
# 用PID文件检测worker状态，不用fuser/pgrep

QUEUE="/tmp/ai-guides"
WORKER_SCRIPT="$QUEUE/worker.sh"
LOG="$QUEUE/.monitor.log"
PID_DIR="$QUEUE/.worker_pids"
EXPECTED_WORKERS="a b c d e f g h i j k l m n o p q r s t"

running=0
restarted=0

for w in $EXPECTED_WORKERS; do
    pidfile="$PID_DIR/${w}.pid"
    lock="$QUEUE/.worker_${w}.lock"
    hb="$QUEUE/.worker_${w}.heartbeat"
    
    alive=false
    
    # 检查PID文件
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            alive=true
        fi
    fi
    
    if $alive; then
        # 检查heartbeat是否新鲜（5分钟）
        if [ -f "$hb" ]; then
            hb_time=$(cat "$hb" 2>/dev/null || echo "0")
            now=$(date +%s)
            age=$(( now - hb_time ))
            if [ "$age" -gt 300 ]; then
                echo "[$(date '+%H:%M:%S')] Worker $w heartbeat过期(${age}s)，重启" >> "$LOG"
                kill "$pid" 2>/dev/null
                sleep 2
                kill -9 "$pid" 2>/dev/null
                rm -f "$pidfile" "$lock" "$hb"
                alive=false
            fi
        fi
    fi
    
    if $alive; then
        running=$((running + 1))
    else
        # 清理残留
        rm -f "$lock" "$hb"
        # 杀死可能的残留进程
        if [ -f "$pidfile" ]; then
            old_pid=$(cat "$pidfile" 2>/dev/null)
            [ -n "$old_pid" ] && kill -9 "$old_pid" 2>/dev/null
            rm -f "$pidfile"
        fi
        # 启动新worker
        nohup bash "$WORKER_SCRIPT" "$w" >> "$QUEUE/.worker_${w}.log" 2>&1 &
        echo $! > "$pidfile"
        restarted=$((restarted + 1))
        echo "[$(date '+%H:%M:%S')] 重启Worker $w (PID=$!)" >> "$LOG"
        sleep 0.5
    fi
done

# 释放超时claimed任务
python3 "$QUEUE/work_queue.py" release 2>/dev/null || true

# 重置可重试的error文件
python3 "$QUEUE/work_queue.py" reset_errors 2>/dev/null || true

# 清理重复claimed文件
python3 -c "
import sqlite3
conn = sqlite3.connect('$QUEUE/work_queue.db')
rows = conn.execute('SELECT claimed_by, COUNT(*) as cnt FROM files WHERE status=\"claimed\" GROUP BY claimed_by HAVING cnt > 1').fetchall()
freed = 0
for wid, cnt in rows:
    conn.execute('UPDATE files SET status=\"pending\", claimed_by=NULL, claimed_at=NULL WHERE status=\"claimed\" AND claimed_by=? AND id NOT IN (SELECT id FROM files WHERE status=\"claimed\" AND claimed_by=? ORDER BY claimed_at DESC LIMIT 1)', (wid, wid))
    freed += cnt - 1
if freed:
    conn.commit()
    print(f'清理重复claimed: 释放{freed}个')
conn.close()
" 2>/dev/null || true

# 输出状态
total=$((running + restarted))
if [ "$restarted" -gt 0 ]; then
    echo "Worker状态: ${running}运行 + ${restarted}重启 = ${total}/20"
    echo "[$(date '+%H:%M:%S')] ${running}运行 + ${restarted}重启" >> "$LOG"
fi
