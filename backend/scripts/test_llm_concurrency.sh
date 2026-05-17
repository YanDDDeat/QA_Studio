#!/bin/bash
# LLM API 并发能力测试脚本
# 用法: bash test_llm_concurrency.sh [最大并发数，默认50]

BASE_URL="http://10.10.15.6:30080/api/v1/chat/completions"
API_KEY="49c90220bda747f32725be07c8cdbd90"
MODEL="qwen3-235b"
MAX_LEVEL=${1:-50}
TMPDIR=$(mktemp -d)

single_request() {
    local idx=$1
    local outfile="$TMPDIR/result_$idx"
    local start=$(date +%s%N)

    http_code=$(curl -s -o "$outfile.body" -w "%{http_code}" \
        --max-time 120 \
        --location "$BASE_URL" \
        --header "Authorization: Bearer $API_KEY" \
        --header "Content-Type: application/json" \
        --data '{
            "model": "'"$MODEL"'",
            "stream": false,
            "messages": [{"role": "user", "content": "请用一句话介绍你自己"}],
            "max_tokens": 50,
            "enable_thinking": false
        }' 2>/dev/null)

    local end=$(date +%s%N)
    local elapsed=$(( (end - start) / 1000000 ))  # 毫秒

    echo "$idx $http_code $elapsed" > "$outfile"
}

test_concurrency() {
    local n=$1
    echo ""
    echo "============================================================"
    echo "  并发数: $n"
    echo "============================================================"

    # 清理上一轮
    rm -f "$TMPDIR"/result_*

    local total_start=$(date +%s%N)

    # 并发启动
    for i in $(seq 1 $n); do
        single_request $i &
    done
    wait

    local total_end=$(date +%s%N)
    local total_ms=$(( (total_end - total_start) / 1000000 ))
    local total_s=$(awk "BEGIN {printf \"%.1f\", $total_ms/1000}")

    # 统计结果
    local success=0
    local failed=0
    local min_ms=999999
    local max_ms=0
    local sum_ms=0
    local fail_details=""

    for f in "$TMPDIR"/result_*; do
        [ -f "$f" ] || continue
        read -r idx code elapsed < "$f"
        if [ "$code" = "200" ]; then
            success=$((success + 1))
            sum_ms=$((sum_ms + elapsed))
            [ "$elapsed" -lt "$min_ms" ] && min_ms=$elapsed
            [ "$elapsed" -gt "$max_ms" ] && max_ms=$elapsed
        else
            failed=$((failed + 1))
            body=""
            [ -f "$f.body" ] && body=$(head -c 100 "$f.body")
            fail_details="$fail_details\n    - code=$code, ${body}"
        fi
    done

    echo "  成功: $success/$n"
    if [ "$failed" -gt 0 ]; then
        echo "  失败: $failed"
        echo -e "$fail_details"
    fi
    if [ "$success" -gt 0 ]; then
        local avg_ms=$((sum_ms / success))
        local min_s=$(awk "BEGIN {printf \"%.1f\", $min_ms/1000}")
        local avg_s=$(awk "BEGIN {printf \"%.1f\", $avg_ms/1000}")
        local max_s=$(awk "BEGIN {printf \"%.1f\", $max_ms/1000}")
        local throughput=$(awk "BEGIN {printf \"%.2f\", $success/($total_ms/1000)}")
        echo "  耗时: 最小=${min_s}s  平均=${avg_s}s  最大=${max_s}s"
        echo "  总耗时: ${total_s}s"
        echo "  吞吐: ${throughput} req/s"
    fi

    # 返回是否全部成功
    [ "$success" -eq "$n" ]
}

# ── 主流程 ──

echo "LLM 并发测试 | $BASE_URL | model=$MODEL"

LEVELS=(1 2 5 10 15 20 30 50)
PREV=1

for n in "${LEVELS[@]}"; do
    [ "$n" -gt "$MAX_LEVEL" ] && break

    if ! test_concurrency "$n"; then
        echo ""
        echo "!! 并发数 $n 出现失败，建议 max_workers 设为 $PREV"
        rm -rf "$TMPDIR"
        exit 1
    fi
    PREV=$n
done

echo ""
echo "OK 所有级别通过，并发上限至少 $PREV"
rm -rf "$TMPDIR"
