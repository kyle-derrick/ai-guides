#!/bin/bash
# 智能章节优化脚本 - 支持多进程协作 + 自动转场
# 用法: optimize_chapters.sh <PROC_ID> <INITIAL_BOOK>
# PROC_ID: D 或 E
# INITIAL_BOOK: personal 或 communication
# 
# 转场逻辑: 当前书籍 → 帮B(搞钱) → 安全 → 软工

PROC_ID="$1"
INITIAL_BOOK="$2"
STATE_FILE="/tmp/ai-guides/.optimization_state_${PROC_ID,,}.json"
LOG_FILE="/tmp/ai-guides/.optimization_${PROC_ID,,}.log"
PROMPT_FILE="/tmp/ai-guides/.optimize_prompt.txt"
HERMES="/opt/hermes/.venv/bin/hermes"
LOCKS_DIR="/tmp/ai-guides/.chapter_locks"

# 书籍目录映射
declare -A BOOK_DIRS=(
    ["personal"]="/tmp/ai-guides/content/docs/personal/"
    ["communication"]="/tmp/ai-guides/content/docs/communication/"
    ["money"]="/tmp/ai-guides/content/docs/money/"
    ["hacker"]="/tmp/ai-guides/content/docs/hacker/"
    ["engineering"]="/tmp/ai-guides/content/docs/engineering/"
)

# 原进程映射（用于冲突检测）
declare -A ORIG_STATE=(
    ["personal"]="/tmp/ai-guides/.optimization_state_a.json"
    ["communication"]="/tmp/ai-guides/.optimization_state_c.json"
    ["money"]="/tmp/ai-guides/.optimization_state_b.json"
    ["hacker"]=""
    ["engineering"]=""
)

# 转场顺序：当帮完初始书籍后，按此顺序接手
declare -A NEXT_BOOK=(
    ["personal"]="money"
    ["communication"]="money"
    ["money"]="hacker"
    ["hacker"]="engineering"
    ["engineering"]=""
)

mkdir -p "$LOCKS_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$PROC_ID] $1" >> "$LOG_FILE"
}

cleanup() {
    log "收到终止信号，正在保存状态..."
    python3 -c "
import json, datetime, os
try:
    d = json.load(open('$STATE_FILE'))
    d['status'] = 'interrupted'
    d['interrupt_time'] = datetime.datetime.now().isoformat()
    tmp = '$STATE_FILE' + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(tmp, '$STATE_FILE')
except:
    pass
" 2>/dev/null
    log "状态已保存，退出"
    exit 0
}

trap cleanup SIGTERM SIGINT SIGHUP

# 初始化或恢复状态
init_state() {
    local book="$1"
    local book_dir="${BOOK_DIRS[$book]}"
    
    python3 -c "
import json, os, datetime

book_dir = '$book_dir'
book = '$book'

# 检查是否已有状态文件
if os.path.exists('$STATE_FILE'):
    existing = json.load(open('$STATE_FILE'))
    if existing.get('current_book') == book and existing.get('status') != 'completed':
        print('RESUME')
        exit()

# 获取原进程已处理的文件（用于冲突检测）
orig_state_path = '${ORIG_STATE[$book]}'
processed_by_orig = set()
if orig_state_path and os.path.exists(orig_state_path):
    orig = json.load(open(orig_state_path))
    orig_book_dir = orig.get('book_dirs', {}).get(list(orig.get('book_dirs', {}).keys())[0], '')
    if orig_book_dir:
        all_orig_files = []
        for root, dirs, fnames in os.walk(orig_book_dir):
            for f in sorted(fnames):
                if f.endswith('.md') and not f.startswith('_index'):
                    all_orig_files.append(os.path.join(root, f))
        all_orig_files.sort()
        orig_index = orig.get('current_file_index', 0)
        processed_by_orig = set(all_orig_files[:orig_index])

# 构建章节列表
chapters = []
for entry in sorted(os.listdir(book_dir)):
    full = os.path.join(book_dir, entry)
    if os.path.isdir(full):
        files = []
        for root, dirs, fnames in os.walk(full):
            for f in sorted(fnames):
                if f.endswith('.md') and not f.startswith('_index'):
                    fpath = os.path.join(root, f)
                    if fpath not in processed_by_orig:
                        files.append(fpath)
        files.sort()
        if files:
            chapters.append({
                'name': entry,
                'path': full,
                'files': files,
                'total': len(files),
                'processed': 0,
                'status': 'pending'
            })

state = {
    'current_book': book,
    'book_dir': book_dir,
    'chapters': chapters,
    'current_chapter': 0,
    'total_processed': 0,
    'errors': [],
    'status': 'running',
    'start_time': datetime.datetime.now().isoformat()
}
json.dump(state, open('$STATE_FILE', 'w'), indent=2, ensure_ascii=False)
print(f'INIT: {len(chapters)} chapters, {sum(c[\"total\"] for c in chapters)} files')
"
}

# 处理一本书
process_book() {
    local book="$1"
    local book_dir="${BOOK_DIRS[$book]}"
    
    log "=== 开始处理: $book ==="
    
    # 初始化状态
    init_result=$(init_state "$book")
    log "初始化结果: $init_result"
    
    if [ "$init_result" = "RESUME" ]; then
        log "从断点恢复: $book"
    fi
    
    while true; do
        # 读取当前状态
        result=$(python3 -c "
import json, os

state = json.load(open('$STATE_FILE'))
chapters = state['chapters']
current = state.get('current_chapter', 0)

# 找到下一个待处理的章节
found = False
for i in range(current, len(chapters)):
    ch = chapters[i]
    if ch['status'] == 'pending':
        lock_file = '$LOCKS_DIR/' + ch['name'] + '_' + state.get('current_book', '') + '.lock'
        if not os.path.exists(lock_file):
            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
            state['current_chapter'] = i
            json.dump(state, open('$STATE_FILE', 'w'), indent=2, ensure_ascii=False)
            print(f'CLAIM:{i}:{ch[\"name\"]}')
            found = True
            break
        else:
            import time
            if time.time() - os.path.getmtime(lock_file) > 1800:
                os.remove(lock_file)
                with open(lock_file, 'w') as f:
                    f.write(str(os.getpid()))
                state['current_chapter'] = i
                json.dump(state, open('$STATE_FILE', 'w'), indent=2, ensure_ascii=False)
                print(f'CLAIM:{i}:{ch[\"name\"]}')
                found = True
                break

if not found:
    all_done = all(ch['status'] in ('done', 'done_by_other') for ch in chapters)
    if all_done:
        print('ALL_DONE')
    else:
        print('WAIT')
" 2>/dev/null)

        if [ "$result" = "ALL_DONE" ]; then
            log "[$book] 所有章节处理完毕！"
            return 0
        elif [ "$result" = "WAIT" ]; then
            log "[$book] 暂无可用章节，等待60秒..."
            sleep 60
            continue
        fi

        chapter_index=$(echo "$result" | cut -d: -f2)
        chapter_name=$(echo "$result" | cut -d: -f3)
        log "[$book] 开始处理章节: $chapter_name (index=$chapter_index)"

        # 获取文件列表（过滤已处理的）
        mapfile -t files < <(python3 -c "
import json, os
state = json.load(open('$STATE_FILE'))
ch = state['chapters'][$chapter_index]

# 获取原进程已处理文件
orig_state_path = '${ORIG_STATE[$book]}'
processed_by_orig = set()
if orig_state_path and os.path.exists(orig_state_path):
    orig = json.load(open(orig_state_path))
    orig_book_dir = orig.get('book_dirs', {}).get(list(orig.get('book_dirs', {}).keys())[0], '')
    if orig_book_dir:
        all_orig_files = []
        for root, dirs, fnames in os.walk(orig_book_dir):
            for f in sorted(fnames):
                if f.endswith('.md') and not f.startswith('_index'):
                    all_orig_files.append(os.path.join(root, f))
        all_orig_files.sort()
        orig_index = orig.get('current_file_index', 0)
        processed_by_orig = set(all_orig_files[:orig_index])

remaining = [f for f in ch['files'] if f not in processed_by_orig]
for f in remaining:
    print(f)
" 2>/dev/null)

        total=${#files[@]}
        if [ "$total" -eq 0 ]; then
            log "[$chapter_name] 所有文件已被原进程处理，跳过"
            python3 -c "
import json, datetime, os
d = json.load(open('$STATE_FILE'))
d['chapters'][$chapter_index]['status'] = 'done_by_other'
d['current_chapter'] = $chapter_index + 1
lock_file = '$LOCKS_DIR/${chapter_name}_${book}.lock'
if os.path.exists(lock_file):
    os.remove(lock_file)
tmp = '$STATE_FILE' + '.tmp'
with open(tmp, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
os.replace(tmp, '$STATE_FILE')
"
            continue
        fi

        processed=0
        for file in "${files[@]}"; do
            filename=$(basename "$file")
            log "[$chapter_name] 处理($((processed+1))/$total): $filename"

            full_prompt="文件路径：$file

$(cat "$PROMPT_FILE")"

            result=$($HERMES chat -q "$full_prompt" -Q 2>&1)
            exit_code=$?

            if [ $exit_code -eq 0 ]; then
                log "[$chapter_name] 完成: $filename"
            else
                log "[$chapter_name] 失败(exit=$exit_code): $filename"
                python3 -c "
import json, datetime
d = json.load(open('$STATE_FILE'))
d.setdefault('errors', []).append({
    'file': '$file',
    'chapter': '$chapter_name',
    'time': datetime.datetime.now().isoformat(),
    'error': 'hermes exit code $exit_code'
})
d['errors'] = d['errors'][-50:]
json.dump(d, open('$STATE_FILE', 'w'), indent=2, ensure_ascii=False)
"
            fi

            processed=$((processed + 1))

            python3 -c "
import json, datetime, os
d = json.load(open('$STATE_FILE'))
ch = d['chapters'][$chapter_index]
ch['processed'] = $processed
d['total_processed'] = d.get('total_processed', 0) + 1
d['last_file'] = '''$file'''
d['last_time'] = datetime.datetime.now().isoformat()
tmp = '$STATE_FILE' + '.tmp'
with open(tmp, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
os.replace(tmp, '$STATE_FILE')
"
        done

        # 标记章节完成
        python3 -c "
import json, datetime, os
d = json.load(open('$STATE_FILE'))
ch = d['chapters'][$chapter_index]
ch['status'] = 'done'
ch['done_time'] = datetime.datetime.now().isoformat()
d['current_chapter'] = $chapter_index + 1
lock_file = '$LOCKS_DIR/${chapter_name}_${book}.lock'
if os.path.exists(lock_file):
    os.remove(lock_file)
tmp = '$STATE_FILE' + '.tmp'
with open(tmp, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
os.replace(tmp, '$STATE_FILE')
"
        log "[$chapter_name] 章节完成！($total 文件)"
    done
}

# === 主流程 ===
log "=== 进程${PROC_ID}启动 ==="
log "初始任务: $INITIAL_BOOK"

current_book="$INITIAL_BOOK"

while [ -n "$current_book" ]; do
    process_book "$current_book"
    
    # 记录完成
    echo "[$PROC_ID] 完成: $current_book" >> /tmp/ai-guides/.completion.log
    
    # 转到下一本书
    next_book="${NEXT_BOOK[$current_book]}"
    if [ -n "$next_book" ]; then
        log "=== 转场: $current_book → $next_book ==="
        # 删除旧状态文件，为新书初始化
        rm -f "$STATE_FILE"
        current_book="$next_book"
    else
        log "=== 所有任务完成！==="
        exit 0
    fi
done
