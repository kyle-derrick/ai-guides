#!/usr/bin/env python3
import sqlite3, time, os

db_path = '/tmp/ai-guides/work_queue.db'
log_path = '/tmp/ai-guides/eng_progress.log'

while True:
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute('SELECT status, COUNT(*) FROM files WHERE book="engineering" GROUP BY status')
        stats = {row[0]: row[1] for row in cur.fetchall()}
        done = stats.get('done', 0)
        claimed = stats.get('claimed', 0)
        pending = stats.get('pending', 0)
        total = done + claimed + pending
        pct = (done / total * 100) if total > 0 else 0
        
        msg = f'[{time.strftime("%H:%M:%S")}] engineering: done={done}/{total} ({pct:.1f}%) claimed={claimed} pending={pending}'
        print(msg)
        
        with open(log_path, 'a') as f:
            f.write(msg + '\n')
        
        if pending == 0 and claimed == 0:
            print("✅ engineering完成!")
            break
        
        conn.close()
        time.sleep(60)  # 每分钟检查一次
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(60)
