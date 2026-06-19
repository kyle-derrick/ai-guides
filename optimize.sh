#!/bin/bash
# 持续优化脚本 - 支持三进程并行 + 动态分配 + 安全重启
# 用法: optimize.sh [A|B|C]

PROC_ID="${1:-A}"
STATE_FILE="/tmp/ai-guides/.optimization_state_${PROC_ID,,}.json"
STATE_BACKUP="/tmp/ai-guides/.optimization_state_${PROC_ID,,}.json.bak"
LOG_FILE="/tmp/ai-guides/.optimization_${PROC_ID,,}.log"
PROMPT_FILE="/tmp/ai-guides/.optimize_prompt.txt"
HERMES="/opt/hermes/.venv/bin/hermes"
LOCKS_DIR="/tmp/ai-guides/.locks"

mkdir -p "$LOCKS_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$PROC_ID] $1" >> "$LOG_FILE"
}

# 安全保存状态（原子写入 + 备份 + sync）
save_state() {
    local tmp_file="${STATE_FILE}.tmp"
    # 先写入临时文件
    cp "$STATE_FILE" "$tmp_file" 2>/dev/null
    # 确保写入完成
    sync "$tmp_file" 2>/dev/null
    # 原子替换
    mv -f "$tmp_file" "$STATE_FILE" 2>/dev/null
    sync "$STATE_FILE" 2>/dev/null
    # 定期备份（每10个文件）
    local total=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('total_processed', 0))" 2>/dev/null || echo "0")
    if [ $((total % 10)) -eq 0 ] && [ "$total" -gt 0 ]; then
        cp -f "$STATE_FILE" "$STATE_BACKUP" 2>/dev/null
        sync "$STATE_BACKUP" 2>/dev/null
    fi
}

# 信号处理：收到 SIGTERM/SIGINT 时保存状态后退出
cleanup() {
    log "收到终止信号，正在保存状态..."
    # 读取当前正在处理的文件并记录
    python3 -c "
import json, datetime
try:
    d = json.load(open('$STATE_FILE'))
    d['status'] = 'interrupted'
    d['interrupt_time'] = datetime.datetime.now().isoformat()
    # 原子写入
    import tempfile, os
    tmp = '$STATE_FILE' + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(tmp, '$STATE_FILE')
    os.sync()
except:
    pass
" 2>/dev/null
    log "状态已保存，退出"
    exit 0
}

trap cleanup SIGTERM SIGINT SIGHUP

# 尝试获取一本书的锁
try_lock_book() {
    local book="$1"
    local lock_file="$LOCKS_DIR/${book}.lock"
    if [ ! -f "$lock_file" ]; then
        echo "$PROC_ID" > "$lock_file"
        return 0
    fi
    return 1
}

# 检查书是否被锁定
is_book_locked() {
    local book="$1"
    local lock_file="$LOCKS_DIR/${book}.lock"
    [ -f "$lock_file" ]
}

# 从可用书中获取一本
claim_available_book() {
    local available_json=$(python3 -c "
import json
d = json.load(open('$STATE_FILE'))
ab = d.get('available_books', {})
for book in ab:
    print(book)
" 2>/dev/null)
    
    for book in $available_json; do
        if try_lock_book "$book"; then
            local dir=$(python3 -c "
import json
d = json.load(open('$STATE_FILE'))
print(d['available_books']['$book'])
" 2>/dev/null)
            
            python3 -c "
import json
d = json.load(open('$STATE_FILE'))
d['book_order'].append('$book')
d['book_dirs']['$book'] = '''$dir'''
d['current_book_index'] = len(d['book_order']) - 1
d['current_file_index'] = 0
json.dump(d, open('$STATE_FILE', 'w'), indent=2, ensure_ascii=False)
"
            log "获取到新书: $book"
            return 0
        fi
    done
    return 1
}

# 恢复备份状态（如果当前状态损坏）
recover_state() {
    if [ -f "$STATE_BACKUP" ]; then
        log "从备份恢复状态..."
        cp -f "$STATE_BACKUP" "$STATE_FILE" 2>/dev/null
        sync "$STATE_FILE" 2>/dev/null
    fi
}

log "=== 进程${PROC_ID}启动 ==="

# 检查状态文件是否完好
if ! python3 -c "import json; json.load(open('$STATE_FILE'))" 2>/dev/null; then
    log "状态文件损坏，尝试恢复..."
    recover_state
fi

while true; do
    # 读取状态
    current_book_index=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('current_book_index', 0))" 2>/dev/null || echo "0")
    current_file_index=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('current_file_index', 0))" 2>/dev/null || echo "0")
    
    book_order=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(' '.join(d['book_order']))" 2>/dev/null)
    books=($book_order)
    
    # 检查是否已完成所有分配的书
    if [ "$current_book_index" -ge ${#books[@]} ]; then
        if claim_available_book; then
            current_book_index=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('current_book_index', 0))" 2>/dev/null)
            continue
        else
            log "所有书处理完毕，无可用书目"
            python3 -c "
import json, datetime
d = json.load(open('$STATE_FILE'))
d['status'] = 'completed'
d['completed_time'] = datetime.datetime.now().isoformat()
json.dump(d, open('$STATE_FILE', 'w'), indent=2, ensure_ascii=False)
"
            # 完成时主动通知
            echo "[$PROC_ID] 已完成所有任务" >> /tmp/ai-guides/.completion.log
            exit 0
        fi
    fi

    book=${books[$current_book_index]}
    dir=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d['book_dirs']['$book'])" 2>/dev/null)

    # 获取当前书的文件列表（全量，不限大小）
    mapfile -t files < <(find "$dir" -name "*.md" ! -name "_index*" 2>/dev/null | sort)

    if [ ${#files[@]} -eq 0 ]; then
        log "[$book] 没有文件，跳到下一本书"
        python3 -c "
import json
d = json.load(open('$STATE_FILE'))
d['current_book_index'] = d.get('current_book_index', 0) + 1
d['current_file_index'] = 0
json.dump(d, open('$STATE_FILE', 'w'), indent=2, ensure_ascii=False)
"
        continue
    fi

    # 检查是否当前书处理完了
    if [ "$current_file_index" -ge ${#files[@]} ]; then
        log "[$book] 处理完毕(${#files[@]}个文件)"
        # 完成一本书时记录
        echo "[$PROC_ID] 完成: $book (${#files[@]}个文件)" >> /tmp/ai-guides/.completion.log
        
        python3 -c "
import json
d = json.load(open('$STATE_FILE'))
d['current_book_index'] = d.get('current_book_index', 0) + 1
d['current_file_index'] = 0
json.dump(d, open('$STATE_FILE', 'w'), indent=2, ensure_ascii=False)
"
        continue
    fi

    # 获取当前要处理的文件
    file=${files[$current_file_index]}
    filename=$(basename "$file")
    log "[$book] 开始处理($((current_file_index+1))/${#files[@]}): $filename"

    # 构建完整 prompt
    full_prompt="文件路径：$file

$(cat "$PROMPT_FILE")"

    # 调用 hermes 优化这个文件
    result=$($HERMES chat -q "$full_prompt" -Q 2>&1)
    exit_code=$?

    # 检查执行结果
    if [ $exit_code -eq 0 ]; then
        log "[$book] 完成: $filename"
    else
        log "[$book] 失败(exit=$exit_code): $filename"
        python3 -c "
import json, datetime
d = json.load(open('$STATE_FILE'))
d.setdefault('errors', []).append({
    'file': '$file',
    'time': datetime.datetime.now().isoformat(),
    'error': 'hermes exit code $exit_code'
})
d['errors'] = d['errors'][-50:]
json.dump(d, open('$STATE_FILE', 'w'), indent=2, ensure_ascii=False)
"
    fi

    # 更新状态（原子写入 + 备份）
    python3 -c "
import json, datetime, os
d = json.load(open('$STATE_FILE'))
d['current_file_index'] = d.get('current_file_index', 0) + 1
d['last_processed_file'] = '''$file'''
d['last_processed_time'] = datetime.datetime.now().isoformat()
d['total_processed'] = d.get('total_processed', 0) + 1
d['status'] = 'running'
# 原子写入
tmp = '$STATE_FILE' + '.tmp'
with open(tmp, 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
os.replace(tmp, '$STATE_FILE')
"
    # 每10个文件备份一次
    save_state

    # B进程特殊逻辑：处理到500个文件后自动退出，切换到队列模式
    if [ "$PROC_ID" = "B" ]; then
        total_done=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('total_processed', 0))" 2>/dev/null || echo "0")
        if [ "$total_done" -ge 500 ]; then
            log "[$PROC_ID] 已处理 $total_done 个文件，达到500上限，切换到队列模式"
            echo "[$PROC_ID] 达到500文件上限，切换到队列模式" >> /tmp/ai-guides/.completion.log
            exit 0
        fi
    fi

done
