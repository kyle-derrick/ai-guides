#!/bin/bash
# 统计脚本 - 完成效率 + Token消耗估算 + 进度汇报
# 输出JSON格式，供监控脚本和汇报使用

QUEUE="/tmp/ai-guides/work_queue.db"

python3 << 'EOF'
import sqlite3, json
from datetime import datetime, timedelta

conn = sqlite3.connect("/tmp/ai-guides/work_queue.db")
conn.row_factory = sqlite3.Row

stats = {
    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "workers": {},
    "books": {},
    "efficiency": {},
    "token_estimate": {}
}

# 1. Worker状态
workers_running = 0
import subprocess
ps = subprocess.run("ps aux | grep 'worker.sh' | grep -v grep | wc -l", shell=True, capture_output=True, text=True)
workers_running = int(ps.stdout.strip())

# 2. 各书进度
for book in ['personal', 'communication', 'money', 'hacker', 'engineering']:
    done = conn.execute("SELECT COUNT(*) FROM files WHERE book=? AND status='done'", (book,)).fetchone()[0]
    claimed = conn.execute("SELECT COUNT(*) FROM files WHERE book=? AND status='claimed'", (book,)).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM files WHERE book=? AND status='pending'", (book,)).fetchone()[0]
    skip = conn.execute("SELECT skipped_files FROM books WHERE name=?", (book,)).fetchone()[0]
    total = conn.execute("SELECT total_files FROM books WHERE name=?", (book,)).fetchone()[0]
    
    stats["books"][book] = {
        "done": done,
        "skipped": skip,
        "total": total,
        "claimed": claimed,
        "pending": pending,
        "progress": round((done + skip) / total * 100, 1) if total > 0 else 0
    }

# 3. 效率统计 - 最近1小时
one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
hourly_done = conn.execute("""
    SELECT COUNT(*) FROM files 
    WHERE status='done' AND done_at > ?
""", (one_hour_ago,)).fetchone()[0]

# 效率统计 - 最近10个完成文件的平均耗时
recent_durations = conn.execute("""
    SELECT 
        julianday(done_at) - julianday(claimed_at) as duration_days
    FROM files 
    WHERE status='done' AND done_at IS NOT NULL AND claimed_at IS NOT NULL
    ORDER BY done_at DESC 
    LIMIT 20
""").fetchall()

durations = [r[0] * 86400 for r in recent_durations if r[0] and r[0] > 0]  # 转换为秒
avg_duration = sum(durations) / len(durations) if durations else 0

# 4. Token消耗估算 (基于文件数和平均token使用)
# 估算：每个文件平均消耗 ~15K tokens (输入+输出)
# 每个文件平均 ~30KB 输出内容
done_today = conn.execute("""
    SELECT COUNT(*) FROM files 
    WHERE status='done' AND done_at LIKE '2026-06-25%'
""").fetchone()[0]

# 从progress_log获取更准确的统计
log_stats = conn.execute("""
    SELECT 
        COUNT(*) as total_processed,
        AVG(duration_sec) as avg_duration,
        SUM(duration_sec) as total_duration
    FROM progress_log 
    WHERE action='done'
""").fetchone()

stats["efficiency"] = {
    "last_hour": hourly_done,
    "avg_file_duration_sec": round(avg_duration, 0),
    "avg_file_duration_min": round(avg_duration / 60, 1),
    "files_per_hour": round(3600 / avg_duration, 1) if avg_duration > 0 else 0,
    "total_processed": log_stats[0] if log_stats else 0,
    "total_duration_hours": round(log_stats[2] / 3600, 1) if log_stats and log_stats[2] else 0
}

# 5. Token估算
# 基于实际数据：每个文件平均处理时间约500秒
# 假设：每秒处理约30 tokens (输入+输出)
# 每个文件：约15K tokens
tokens_per_file = 15000
total_done = sum(b["done"] for b in stats["books"].values())
total_remaining = sum(b["pending"] for b in stats["books"].values())

stats["token_estimate"] = {
    "tokens_per_file": tokens_per_file,
    "total_consumed": total_done * tokens_per_file,
    "total_consumed_million": round(total_done * tokens_per_file / 1000000, 1),
    "remaining_estimate": total_remaining * tokens_per_file,
    "remaining_estimate_million": round(total_remaining * tokens_per_file / 1000000, 1),
    "estimated_cost_usd": round(total_done * tokens_per_file / 1000000 * 0.3, 2)  # 假设$0.3/M tokens
}

stats["summary"] = {
    "workers": workers_running,
    "total_progress": f"{sum(b['done']+b['skipped'] for b in stats['books'].values())}/{sum(b['total'] for b in stats['books'].values())}",
    "total_progress_pct": round(sum(b['done']+b['skipped'] for b in stats['books'].values()) / sum(b['total'] for b in stats['books'].values()) * 100, 1),
    "hourly_rate": hourly_done,
    "est_hours_remaining": round(total_remaining / (hourly_done if hourly_done > 0 else 1), 1)
}

print(json.dumps(stats, ensure_ascii=False, indent=2))
conn.close()
EOF
