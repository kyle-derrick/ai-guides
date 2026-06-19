#!/usr/bin/env python3
"""指南项目全面状态报告 - Worker/进度/效率/Token"""
import sqlite3, subprocess, os, glob, time, json
from datetime import datetime, timedelta

QUEUE = "/tmp/ai-guides/work_queue.db"

def get_status():
    report = {}
    conn = sqlite3.connect(QUEUE)
    conn.row_factory = sqlite3.Row

    # ── Worker状态 ──
    # 用lock文件计数（每个Worker一个lock）
    lock_files = glob.glob("/tmp/ai-guides/.worker_*.lock")
    actual_workers = len(lock_files)

    hermes_ps = subprocess.run("ps aux | grep 'hermes chat' | grep -v grep | wc -l",
                               shell=True, capture_output=True, text=True)
    hermes_count = int(hermes_ps.stdout.strip())

    heartbeats = len(glob.glob("/tmp/ai-guides/.worker_*.heartbeat"))

    report["workers"] = {
        "running": actual_workers,
        "hermes_chat": hermes_count,
        "heartbeats": heartbeats
    }

    # ── 各书进度 ──
    books = []
    for book in ['personal', 'communication', 'money', 'hacker', 'engineering']:
        row = conn.execute("SELECT total_files, done_files, skipped_files FROM books WHERE name=?", (book,)).fetchone()
        if not row:
            continue
        total, done, skip = row
        actual_done = conn.execute("SELECT COUNT(*) FROM files WHERE book=? AND status='done'", (book,)).fetchone()[0]
        claimed = conn.execute("SELECT COUNT(*) FROM files WHERE book=? AND status='claimed'", (book,)).fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM files WHERE book=? AND status='pending'", (book,)).fetchone()[0]
        remaining = total - actual_done - skip
        books.append({
            "name": book,
            "total": total,
            "done": actual_done,
            "skipped": skip,
            "claimed": claimed,
            "pending": pending,
            "remaining": remaining,
            "progress": round((actual_done + skip) / total * 100, 1) if total > 0 else 0
        })
    report["books"] = books

    # ── 效率统计 ──
    now = datetime.now()
    one_hour_ago = (now - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    six_hours_ago = (now - timedelta(hours=6)).strftime('%Y-%m-%d %H:%M:%S')

    hourly = conn.execute("SELECT COUNT(*) FROM files WHERE status='done' AND done_at > ?", (one_hour_ago,)).fetchone()[0]
    six_hourly = conn.execute("SELECT COUNT(*) FROM files WHERE status='done' AND done_at > ?", (six_hours_ago,)).fetchone()[0]

    # 最近50个文件平均耗时
    avg = conn.execute("""
        SELECT AVG(duration_sec) FROM (
            SELECT duration_sec FROM files 
            WHERE status='done' AND duration_sec > 0 
            ORDER BY done_at DESC LIMIT 50
        )
    """).fetchone()[0] or 0

    total_done = conn.execute("SELECT COUNT(*) FROM files WHERE status='done'").fetchone()[0]
    total_remaining = sum(b["remaining"] for b in books)

    report["efficiency"] = {
        "last_1h": hourly,
        "last_6h": six_hourly,
        "avg_duration_min": round(avg / 60, 1),
        "files_per_hour": round(3600 / avg, 1) if avg > 0 else 0,
        "total_processed": total_done,
    }

    # ── Token消耗估算 ──
    # 基于progress_log的实际数据
    log_stats = conn.execute("""
        SELECT COUNT(*), AVG(duration_sec), SUM(duration_sec) 
        FROM progress_log WHERE action='done'
    """).fetchone()

    # 估算模型：mimo-v2.5-pro 处理一个文件约消耗
    #   输入: ~8K tokens (prompt + 文件内容)
    #   输出: ~6K tokens (改写后的文件)
    #   合计: ~14K tokens/文件
    tokens_per_file = 14000
    total_tokens = total_done * tokens_per_file
    remaining_tokens = total_remaining * tokens_per_file

    # 速率统计
    if hourly > 0:
        est_hours = total_remaining / hourly
    else:
        est_hours = 0

    report["tokens"] = {
        "per_file_estimate": tokens_per_file,
        "consumed": total_tokens,
        "consumed_M": round(total_tokens / 1_000_000, 2),
        "remaining_estimate": remaining_tokens,
        "remaining_M": round(remaining_tokens / 1_000_000, 2),
        "total_when_done_M": round((total_tokens + remaining_tokens) / 1_000_000, 2),
        "est_hours_remaining": round(est_hours, 1),
    }

    # ── 异常检测 ──
    issues = []
    # 检查Worker数
    if actual_workers < 15:
        issues.append(f"⚠️ Worker不足: {actual_workers}/20")
    # 检查是否有claimed但无对应worker
    orphaned = conn.execute("""
        SELECT COUNT(*) FROM files WHERE status='claimed' 
        AND claimed_by NOT IN ('a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t')
    """).fetchone()[0]
    if orphaned > 0:
        issues.append(f"⚠️ 孤儿claimed文件: {orphaned}个")
    # 检查错误文件
    errors = conn.execute("SELECT COUNT(*) FROM files WHERE status='error'").fetchone()[0]
    if errors > 0:
        issues.append(f"❌ 错误状态文件: {errors}个")
    # 检查心跳超时
    stale_heartbeats = 0
    for hb in glob.glob("/tmp/ai-guides/.worker_*.heartbeat"):
        try:
            with open(hb, 'r') as f:
                hb_time = int(f.read().strip())
            if time.time() - hb_time > 1200:  # 20分钟无心跳
                stale_heartbeats += 1
        except:
            pass
    if stale_heartbeats > 0:
        issues.append(f"⚠️ 心跳超时: {stale_heartbeats}个Worker")

    report["issues"] = issues
    report["timestamp"] = now.strftime('%Y-%m-%d %H:%M:%S')

    conn.close()
    return report

def format_report(r):
    lines = []
    lines.append(f"📊 **项目状态报告** ({r['timestamp']})")
    lines.append("")

    # Worker
    w = r["workers"]
    status_icon = "✅" if w["running"] >= 20 else "⚠️"
    lines.append(f"**Worker:** {status_icon} {w['running']}个运行中 | hermes:{w['hermes_chat']} | 心跳:{w['heartbeats']}")

    # 进度
    lines.append("")
    lines.append("**进度:**")
    for b in r["books"]:
        if b["remaining"] > 0:
            lines.append(f"  {b['name']}: {b['done']+b['skipped']}/{b['total']} ({b['progress']}%) claimed:{b['claimed']}")
        else:
            lines.append(f"  {b['name']}: ✅ {b['done']+b['skipped']}/{b['total']}")

    # 效率
    e = r["efficiency"]
    lines.append("")
    lines.append(f"**效率:** 1h:{e['last_1h']}文件 | 6h:{e['last_6h']}文件 | 均速:{e['avg_duration_min']}分钟/文件 | 吞吐:{e['files_per_hour']}文件/小时")

    # Token
    t = r["tokens"]
    lines.append("")
    lines.append(f"**Token:** 已消耗:{t['consumed_M']}M | 剩余:{t['remaining_M']}M | 总计:{t['total_when_done_M']}M | 预估剩余:{t['est_hours_remaining']}小时")

    # 异常
    if r["issues"]:
        lines.append("")
        lines.append("**异常:**")
        for i in r["issues"]:
            lines.append(f"  {i}")

    return "\n".join(lines)

if __name__ == "__main__":
    r = get_status()
    print(format_report(r))
