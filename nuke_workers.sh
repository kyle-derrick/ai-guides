#!/bin/bash
# 核武器级清理：杀死所有worker相关进程
# 通过/proc/PID/cmdline精确匹配

echo "=== 查找worker.sh进程 ==="
for pid in /proc/[0-9]*/cmdline; do
    [ -f "$pid" ] || continue
    cmd=$(tr '\0' ' ' < "$pid" 2>/dev/null)
    if echo "$cmd" | grep -q "worker.sh [a-t]"; then
        real_pid=$(echo "$pid" | grep -oP '\d+')
        echo "杀死 worker.sh PID=$real_pid: $cmd"
        kill "$real_pid" 2>/dev/null
    fi
done

sleep 3

echo "=== 查找hermes chat进程 ==="
for pid in /proc/[0-9]*/cmdline; do
    [ -f "$pid" ] || continue
    cmd=$(tr '\0' ' ' < "$pid" 2>/dev/null)
    if echo "$cmd" | grep -q "hermes.*chat.*-q"; then
        real_pid=$(echo "$pid" | grep -oP '\d+')
        echo "杀死 hermes chat PID=$real_pid"
        kill "$real_pid" 2>/dev/null
    fi
done

sleep 2

echo "=== 强杀残留worker.sh ==="
for pid in /proc/[0-9]*/cmdline; do
    [ -f "$pid" ] || continue
    cmd=$(tr '\0' ' ' < "$pid" 2>/dev/null)
    if echo "$cmd" | grep -q "worker.sh [a-t]"; then
        real_pid=$(echo "$pid" | grep -oP '\d+')
        echo "强杀 PID=$real_pid"
        kill -9 "$real_pid" 2>/dev/null
    fi
done

sleep 1

echo "=== 强杀残留hermes chat ==="
for pid in /proc/[0-9]*/cmdline; do
    [ -f "$pid" ] || continue
    cmd=$(tr '\0' ' ' < "$pid" 2>/dev/null)
    if echo "$cmd" | grep -q "hermes.*chat.*-q"; then
        real_pid=$(echo "$pid" | grep -oP '\d+')
        echo "强杀 PID=$real_pid"
        kill -9 "$real_pid" 2>/dev/null
    fi
done

sleep 1

# 清理文件
rm -f /tmp/ai-guides/.worker_*.lock /tmp/ai-guides/.worker_*.heartbeat
rm -rf /tmp/ai-guides/.worker_pids

# 释放claimed
python3 -c "
import sqlite3
conn = sqlite3.connect('/tmp/ai-guides/work_queue.db')
c = conn.execute('UPDATE files SET status=?, claimed_by=NULL, claimed_at=NULL WHERE status=?', ('pending', 'claimed'))
conn.commit()
print(f'释放claimed: {c.rowcount}个')
conn.close()
"

echo "=== 清理完成 ==="
