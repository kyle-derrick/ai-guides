#!/usr/bin/env python3
"""
统一任务队列管理器 v3 - 全面修复版
修复:
- register_worker 不再清零统计数据
- fail_file 支持自动重试 (retry_count < 3 → pending)
- claim 原子操作 + 防重复
- release_stale 独立函数，不被worker调用
- 所有DB操作带异常保护
"""

import sqlite3
import json
import os
import sys
import shutil
from datetime import datetime

DB_PATH = "/tmp/ai-guides/work_queue.db"
BACKUP_DIR = "/tmp/ai-guides/.queue_backup"
PROGRESS_LOG = "/tmp/ai-guides/.queue_progress.log"

BOOKS = [
    ("personal", "/tmp/ai-guides/content/docs/personal/"),
    ("communication", "/tmp/ai-guides/content/docs/communication/"),
    ("money", "/tmp/ai-guides/content/docs/money/"),
    ("hacker", "/tmp/ai-guides/content/docs/hacker/"),
    ("engineering", "/tmp/ai-guides/content/docs/engineering/"),
]

MAX_RETRIES = 3
STALE_TIMEOUT_MINUTES = 25  # heartbeat超时25分钟

os.makedirs(BACKUP_DIR, exist_ok=True)

def log_progress(msg):
    try:
        with open(PROGRESS_LOG, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except:
        pass

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            book TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            claimed_by TEXT,
            claimed_at TEXT,
            done_at TEXT,
            done_by TEXT,
            error_msg TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_files_status_book ON files(book, status);
        CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
        
        CREATE TABLE IF NOT EXISTS books (
            name TEXT PRIMARY KEY,
            total_files INTEGER DEFAULT 0,
            done_files INTEGER DEFAULT 0,
            skipped_files INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            started_at TEXT,
            done_at TEXT
        );
        
        CREATE TABLE IF NOT EXISTS workers (
            worker_id TEXT PRIMARY KEY,
            current_file TEXT,
            current_book TEXT,
            total_done INTEGER DEFAULT 0,
            total_errors INTEGER DEFAULT 0,
            last_heartbeat TEXT,
            started_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS progress_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT,
            book TEXT,
            file_path TEXT,
            action TEXT,
            duration_sec REAL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            timestamp TEXT DEFAULT (datetime('now'))
        );
    """)
    # 确保retry_count列存在
    try:
        conn.execute("SELECT retry_count FROM files LIMIT 1")
    except:
        conn.execute("ALTER TABLE files ADD COLUMN retry_count INTEGER DEFAULT 0")
    conn.commit()
    return conn

def scan_book_files(book_dir):
    files = []
    for root, dirs, fnames in os.walk(book_dir):
        for f in sorted(fnames):
            if f.endswith('.md') and not f.startswith('_index'):
                files.append(os.path.join(root, f))
    files.sort()
    return files

def get_orig_processed(book):
    orig_map = {
        "personal": "/tmp/ai-guides/.optimization_state_a.json",
        "communication": "/tmp/ai-guides/.optimization_state_c.json",
        "money": "/tmp/ai-guides/.optimization_state_b.json",
    }
    orig_path = orig_map.get(book)
    if not orig_path or not os.path.exists(orig_path):
        return set()
    try:
        orig = json.load(open(orig_path))
        book_dir_key = list(orig.get('book_dirs', {}).keys())[0] if orig.get('book_dirs') else None
        if not book_dir_key:
            return set()
        all_files = scan_book_files(orig['book_dirs'][book_dir_key])
        return set(all_files[:orig.get('current_file_index', 0)])
    except:
        return set()

def populate_queue(books=None):
    conn = get_db()
    if books is None:
        books = [b[0] for b in BOOKS]
    
    for book_name, book_dir in BOOKS:
        if book_name not in books:
            continue
        
        existing = conn.execute("SELECT COUNT(*) FROM files WHERE book=?", (book_name,)).fetchone()[0]
        if existing > 0:
            print(f"  {book_name}: 已有 {existing} 个文件，跳过")
            continue
        
        all_files = scan_book_files(book_dir)
        processed = get_orig_processed(book_name)
        
        inserted = skipped = 0
        for f in all_files:
            if f in processed:
                skipped += 1
                continue
            try:
                conn.execute("INSERT INTO files (file_path, book, status) VALUES (?, ?, 'pending')", (f, book_name))
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        
        total = len(all_files)
        conn.execute("""
            INSERT OR REPLACE INTO books (name, total_files, done_files, skipped_files, status, started_at)
            VALUES (?, ?, 0, ?, 'active', datetime('now'))
        """, (book_name, total, skipped))
        conn.commit()
        print(f"  {book_name}: {inserted} 入队, {skipped} 已跳过")
    
    backup_db()
    print("队列初始化完成！")

def backup_db():
    try:
        shutil.copy2(DB_PATH, f"{BACKUP_DIR}/work_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
        for old in backups[:-5]:
            os.remove(os.path.join(BACKUP_DIR, old))
    except:
        pass

def claim_file(worker_id):
    """
    领取一个任务 - 原子操作
    使用 BEGIN IMMEDIATE 防止并发冲突
    防止同一worker领取多个文件
    """
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        
        # 检查该worker是否已有claimed文件
        existing = conn.execute("""
            SELECT COUNT(*) FROM files WHERE claimed_by=? AND status='claimed'
        """, (worker_id,)).fetchone()[0]
        if existing > 0:
            conn.rollback()
            conn.close()
            return None
        
        row = conn.execute("""
            SELECT id, file_path, book FROM files 
            WHERE status='pending'
            ORDER BY 
                CASE book
                    WHEN 'personal' THEN 1
                    WHEN 'communication' THEN 2
                    WHEN 'money' THEN 3
                    WHEN 'hacker' THEN 4
                    WHEN 'engineering' THEN 5
                END,
                id
            LIMIT 1
        """).fetchone()
        
        if not row:
            conn.rollback()
            conn.close()
            return None
        
        file_id = row['id']
        file_path = row['file_path']
        book = row['book']
        
        # 原子UPDATE，只有status='pending'才能claim
        cursor = conn.execute("""
            UPDATE files SET status='claimed', claimed_by=?, claimed_at=datetime('now')
            WHERE id=? AND status='pending'
        """, (worker_id, file_id))
        
        if cursor.rowcount == 0:
            conn.rollback()
            conn.close()
            return None

        # 更新worker状态 - 使用INSERT + 单独UPDATE，不覆盖统计数据
        conn.execute("""
            INSERT INTO workers (worker_id, current_file, current_book, last_heartbeat, started_at)
            VALUES (?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(worker_id) DO UPDATE SET
                current_file=excluded.current_file,
                current_book=excluded.current_book,
                last_heartbeat=datetime('now')
        """, (worker_id, file_path, book))
        
        conn.commit()
        conn.close()
        
        log_progress(f"CLAIM {worker_id} {book}/{os.path.basename(file_path)}")
        
        return {"id": file_id, "file_path": file_path, "book": book}
        
    except sqlite3.OperationalError as e:
        try: conn.rollback()
        except: pass
        try: conn.close()
        except: pass
        log_progress(f"CLAIM_ERROR {worker_id}: {e}")
        return None

def complete_file(file_id, worker_id, duration_sec=0.0, input_tokens=0, output_tokens=0):
    """标记完成 - 带重试"""
    import time
    for attempt in range(3):
        conn = get_db()
        try:
            conn.execute("BEGIN IMMEDIATE")
            
            cursor = conn.execute("""
                UPDATE files SET status='done', done_at=datetime('now'), done_by=?,
                    claimed_by=NULL, claimed_at=NULL
                WHERE id=? AND claimed_by=? AND status='claimed'
            """, (worker_id, file_id, worker_id))
            
            if cursor.rowcount == 0:
                conn.rollback()
                conn.close()
                log_progress(f"COMPLETE_SKIP {worker_id} file_id={file_id}: not claimed (attempt {attempt+1})")
                if attempt < 2:
                    time.sleep(1)
                    continue
                return
            
            row = conn.execute("SELECT book, file_path FROM files WHERE id=?", (file_id,)).fetchone()
            if row:
                book = row['book']
                fname = os.path.basename(row['file_path'])
                
                conn.execute("""
                    UPDATE books SET done_files = (
                        SELECT COUNT(*) FROM files WHERE book=? AND status='done'
                    ) WHERE name=?
                """, (book, book))
                
                conn.execute("""
                    INSERT INTO progress_log (worker_id, book, file_path, action, duration_sec, input_tokens, output_tokens)
                    VALUES (?, ?, ?, 'done', ?, ?, ?)
                """, (worker_id, book, row['file_path'], duration_sec, input_tokens, output_tokens))
                
                conn.execute("""
                    UPDATE workers SET 
                        total_done = total_done + 1,
                        current_file = NULL,
                        current_book = NULL,
                        last_heartbeat = datetime('now')
                    WHERE worker_id = ?
                """, (worker_id,))
                
                log_progress(f"DONE {worker_id} {book}/{fname} ({duration_sec:.0f}s)")
            
            conn.commit()
            conn.close()
            return  # success, exit retry loop
            
        except Exception as e:
            try: conn.rollback()
            except: pass
            try: conn.close()
            except: pass
            log_progress(f"COMPLETE_ERROR {worker_id} {file_id} (attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(1)
                continue

def fail_file(file_id, worker_id, error_msg="unknown"):
    """标记失败 - 带自动重试"""
    conn = get_db()
    try:
        # 获取当前retry_count
        row = conn.execute("SELECT retry_count FROM files WHERE id=? AND claimed_by=?", (file_id, worker_id)).fetchone()
        if not row:
            conn.close()
            return
        
        current_retry = (row['retry_count'] or 0)
        new_retry = current_retry + 1
        
        if new_retry < MAX_RETRIES:
            # 自动重试：重置为pending
            conn.execute("""
                UPDATE files SET status='pending', claimed_by=NULL, claimed_at=NULL, 
                    error_msg=?, retry_count=?
                WHERE id=? AND claimed_by=?
            """, (f"retry#{new_retry}: {error_msg}", new_retry, file_id, worker_id))
            log_progress(f"RETRY {worker_id} file_id={file_id} ({new_retry}/{MAX_RETRIES}): {error_msg}")
        else:
            # 超过重试次数，标记为error
            conn.execute("""
                UPDATE files SET status='error', error_msg=?, claimed_by=NULL, claimed_at=NULL,
                    retry_count=?
                WHERE id=? AND claimed_by=?
            """, (error_msg, new_retry, file_id, worker_id))
            log_progress(f"FAIL_FINAL {worker_id} file_id={file_id} ({new_retry} retries): {error_msg}")
        
        conn.execute("""
            UPDATE workers SET 
                total_errors = total_errors + 1, 
                current_file = NULL,
                current_book = NULL,
                last_heartbeat = datetime('now')
            WHERE worker_id = ?
        """, (worker_id,))
        
        conn.execute("""
            INSERT INTO progress_log (worker_id, file_path, action)
            VALUES (?, (SELECT file_path FROM files WHERE id=?), 'error')
        """, (worker_id, file_id))
        
        conn.commit()
        conn.close()
    except Exception as e:
        try: conn.rollback()
        except: pass
        try: conn.close()
        except: pass
        log_progress(f"FAIL_ERROR {worker_id} {file_id}: {e}")

def release_stale_claims(timeout_minutes=None):
    """
    释放超时任务（崩溃恢复）
    基于 worker heartbeat 判断，非 claimed_at
    只由 monitor 调用，不被 worker 调用
    """
    if timeout_minutes is None:
        timeout_minutes = STALE_TIMEOUT_MINUTES
    
    conn = get_db()
    try:
        stale = conn.execute("""
            SELECT f.id, f.file_path, f.claimed_by, w.last_heartbeat
            FROM files f
            JOIN workers w ON f.claimed_by = w.worker_id
            WHERE f.status='claimed' 
            AND datetime(w.last_heartbeat, '+{} minutes') < datetime('now')
        """.format(timeout_minutes)).fetchall()
        
        if stale:
            for s in stale:
                conn.execute("""
                    UPDATE files SET status='pending', claimed_by=NULL, claimed_at=NULL
                    WHERE id=?
                """, (s['id'],))
                log_progress(f"STALE_RELEASE {s['claimed_by']} {os.path.basename(s['file_path'])} (heartbeat={s['last_heartbeat']})")
            conn.commit()
            print(f"释放了 {len(stale)} 个超时任务（基于heartbeat {timeout_minutes}分钟）")
        conn.close()
    except Exception as e:
        try: conn.close()
        except: pass
        print(f"release_stale错误: {e}")

def reset_errors():
    """重置error文件为pending（给它们重新机会）"""
    conn = get_db()
    try:
        # 重置retry_count < MAX_RETRIES的error文件
        cursor = conn.execute("""
            UPDATE files SET status='pending', claimed_by=NULL, claimed_at=NULL
            WHERE status='error' AND retry_count < ?
        """, (MAX_RETRIES,))
        count = cursor.rowcount
        if count > 0:
            log_progress(f"RESET_ERRORS: {count} files error→pending")
            print(f"重置了 {count} 个error文件为pending")
        conn.commit()
        conn.close()
        return count
    except Exception as e:
        try: conn.close()
        except: pass
        print(f"reset_errors错误: {e}")
        return 0

def heartbeat(worker_id, current_file=None, current_book=None):
    conn = get_db()
    try:
        updates = ["last_heartbeat=datetime('now')"]
        params = []
        if current_file:
            updates.append("current_file=?")
            params.append(current_file)
        if current_book:
            updates.append("current_book=?")
            params.append(current_book)
        params.append(worker_id)
        conn.execute(f"UPDATE workers SET {', '.join(updates)} WHERE worker_id=?", params)
        conn.commit()
        conn.close()
    except:
        try: conn.close()
        except: pass

def get_stats():
    conn = get_db()
    stats = {}
    
    books = conn.execute("""
        SELECT name, total_files, done_files, skipped_files, status,
               (SELECT COUNT(*) FROM files WHERE book=books.name AND status='pending') as pending,
               (SELECT COUNT(*) FROM files WHERE book=books.name AND status='claimed') as claimed,
               (SELECT COUNT(*) FROM files WHERE book=books.name AND status='done') as done,
               (SELECT COUNT(*) FROM files WHERE book=books.name AND status='error') as errors
        FROM books ORDER BY 
            CASE name
                WHEN 'personal' THEN 1
                WHEN 'communication' THEN 2
                WHEN 'money' THEN 3
                WHEN 'hacker' THEN 4
                WHEN 'engineering' THEN 5
            END
    """).fetchall()
    stats['books'] = [dict(b) for b in books]
    
    workers = conn.execute("SELECT * FROM workers").fetchall()
    stats['workers'] = [dict(w) for w in workers]
    
    totals = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='claimed' THEN 1 ELSE 0 END) as claimed,
            SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
            SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as errors
        FROM files
    """).fetchone()
    stats['totals'] = dict(totals)
    
    # Token统计
    tokens = conn.execute("""
        SELECT 
            COALESCE(SUM(input_tokens), 0) as total_input,
            COALESCE(SUM(output_tokens), 0) as total_output,
            COUNT(*) as total_logs
        FROM progress_log WHERE action='done'
    """).fetchone()
    stats['tokens'] = dict(tokens)
    
    conn.close()
    return stats

def get_book_progress(book):
    conn = get_db()
    p = conn.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='claimed' THEN 1 ELSE 0 END) as claimed,
            SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
            SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as errors
        FROM files WHERE book=?
    """, (book,)).fetchone()
    conn.close()
    return dict(p)

def count_remaining(book=None):
    conn = get_db()
    if book:
        r = conn.execute("SELECT COUNT(*) FROM files WHERE book=? AND status='pending'", (book,)).fetchone()[0]
    else:
        r = conn.execute("SELECT COUNT(*) FROM files WHERE status='pending'").fetchone()[0]
    conn.close()
    return r

def register_worker(worker_id):
    """注册worker - 不覆盖已有数据"""
    conn = get_db()
    conn.execute("""
        INSERT INTO workers (worker_id, last_heartbeat, started_at)
        VALUES (?, datetime('now'), datetime('now'))
        ON CONFLICT(worker_id) DO UPDATE SET
            last_heartbeat=datetime('now'),
            started_at=datetime('now')
    """, (worker_id,))
    conn.commit()
    conn.close()

def get_worker_status():
    """获取所有worker状态（供monitor用）"""
    conn = get_db()
    workers = conn.execute("""
        SELECT worker_id, current_file, current_book, total_done, total_errors, 
               last_heartbeat, started_at,
               CAST((julianday('now') - julianday(last_heartbeat)) * 86400 AS INTEGER) as heartbeat_age_sec
        FROM workers
    """).fetchall()
    conn.close()
    return [dict(w) for w in workers]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: work_queue.py <cmd> [args]")
        print("  init [books]  - 初始化队列")
        print("  claim <id>    - 领取任务")
        print("  complete <fid> <id> [dur] [in_tok] [out_tok] - 完成任务")
        print("  fail <fid> <id> [msg]    - 标记失败")
        print("  stats         - 统计信息")
        print("  heartbeat <id> [file] [book] - 心跳")
        print("  release       - 释放超时任务")
        print("  reset_errors  - 重置error文件")
        print("  worker_status - worker状态")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "init":
        books = sys.argv[2].split(",") if len(sys.argv) > 2 else None
        init_db()
        populate_queue(books)
    elif cmd == "claim":
        r = claim_file(sys.argv[2])
        print(json.dumps(r) if r else "NONE")
    elif cmd == "complete":
        dur = float(sys.argv[4]) if len(sys.argv) > 4 else 0
        in_tok = int(sys.argv[5]) if len(sys.argv) > 5 else 0
        out_tok = int(sys.argv[6]) if len(sys.argv) > 6 else 0
        complete_file(int(sys.argv[2]), sys.argv[3], dur, in_tok, out_tok)
        print("OK")
    elif cmd == "fail":
        msg = sys.argv[4] if len(sys.argv) > 4 else "unknown"
        fail_file(int(sys.argv[2]), sys.argv[3], msg)
        print("OK")
    elif cmd == "stats":
        print(json.dumps(get_stats(), indent=2, ensure_ascii=False))
    elif cmd == "heartbeat":
        heartbeat(sys.argv[2], 
                  sys.argv[3] if len(sys.argv) > 3 else None,
                  sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "release":
        release_stale_claims()
    elif cmd == "remaining":
        print(count_remaining(sys.argv[2] if len(sys.argv) > 2 else None))
    elif cmd == "progress":
        print(json.dumps(get_book_progress(sys.argv[2])))
    elif cmd == "register":
        register_worker(sys.argv[2])
        print("OK")
    elif cmd == "backup":
        backup_db()
        print("OK")
    elif cmd == "reset_errors":
        reset_errors()
    elif cmd == "worker_status":
        print(json.dumps(get_worker_status(), indent=2, ensure_ascii=False))
    else:
        print(f"未知: {cmd}")
        sys.exit(1)
