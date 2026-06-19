#!/bin/bash
# 强制杀死所有worker相关进程
# 通过ps找进程名，不依赖lock文件

# 找到所有bash worker.sh进程（排除grep自身）
ps -eo pid,args | grep "bash.*/tmp/ai-guides/worker.sh" | grep -v grep | awk '{print $1}' | while read pid; do
    echo "杀死 worker.sh PID=$pid"
    kill "$pid" 2>/dev/null
done

sleep 3

# 强杀残留
ps -eo pid,args | grep "bash.*/tmp/ai-guides/worker.sh" | grep -v grep | awk '{print $1}' | while read pid; do
    echo "强杀 worker.sh PID=$pid"
    kill -9 "$pid" 2>/dev/null
done

sleep 1

# 杀死hermes chat -q进程
ps -eo pid,args | grep "hermes.*chat.*-q" | grep -v grep | awk '{print $1}' | while read pid; do
    echo "杀死 hermes chat PID=$pid"
    kill "$pid" 2>/dev/null
done

sleep 2

# 强杀hermes残留
ps -eo pid,args | grep "hermes.*chat.*-q" | grep -v grep | awk '{print $1}' | while read pid; do
    echo "强杀 hermes chat PID=$pid"
    kill -9 "$pid" 2>/dev/null
done

sleep 1

# 清理lock/heartbeat
rm -f /tmp/ai-guides/.worker_*.lock /tmp/ai-guides/.worker_*.heartbeat

echo "=== 完成 ==="
remaining=$(ps -eo pid,args | grep "bash.*/tmp/ai-guides/worker.sh" | grep -v grep | wc -l)
hermes=$(ps -eo pid,args | grep "hermes.*chat.*-q" | grep -v grep | wc -l)
echo "残留 worker.sh: $remaining"
echo "残留 hermes chat: $hermes"
