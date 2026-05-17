"""LLM API 并发能力测试脚本

用法：python test_llm_concurrency.py [最大并发数]

逐步增加并发数（1, 2, 5, 10, 15, 20, 30, 50），
每个级别发送该数量的并发请求，统计成功率和耗时。
"""

import sys
import time
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://10.10.15.6:30080/api/v1/chat/completions"
API_KEY = "49c90220bda747f32725be07c8cdbd90"
MODEL = "qwen3-235b"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

PAYLOAD = {
    "model": MODEL,
    "stream": False,
    "messages": [{"role": "user", "content": "请用一句话介绍你自己"}],
    "max_tokens": 50,
    "enable_thinking": False,
}


def single_request(idx: int) -> dict:
    start = time.time()
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(BASE_URL, json=PAYLOAD, headers=HEADERS)
        elapsed = time.time() - start
        if resp.status_code == 200:
            return {"idx": idx, "status": "success", "code": 200, "elapsed": elapsed}
        else:
            return {"idx": idx, "status": "failed", "code": resp.status_code, "elapsed": elapsed, "detail": resp.text[:200]}
    except Exception as e:
        elapsed = time.time() - start
        return {"idx": idx, "status": "error", "code": 0, "elapsed": elapsed, "detail": str(e)[:200]}


def test_concurrency(n: int):
    print(f"\n{'='*60}")
    print(f"  并发数: {n}")
    print(f"{'='*60}")

    start = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = {pool.submit(single_request, i): i for i in range(n)}
        for future in as_completed(futures):
            results.append(future.result())

    total_time = time.time() - start

    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]
    times = [r["elapsed"] for r in success]

    print(f"  成功: {len(success)}/{n}")
    if failed:
        print(f"  失败: {len(failed)}")
        for f in failed[:3]:
            print(f"    - code={f['code']}, {f.get('detail', '')[:100]}")
    if times:
        print(f"  耗时: 最小={min(times):.1f}s  平均={sum(times)/len(times):.1f}s  最大={max(times):.1f}s")
    print(f"  总耗时: {total_time:.1f}s")
    print(f"  吞吐: {len(success)/total_time:.2f} req/s")

    return len(success) == n


def main():
    max_level = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    levels = [n for n in [1, 2, 5, 10, 15, 20, 30, 50] if n <= max_level]

    print(f"LLM 并发测试 | {BASE_URL} | model={MODEL}")
    print(f"测试级别: {levels}")

    for n in levels:
        all_ok = test_concurrency(n)
        if not all_ok:
            print(f"\n⚠ 并发数 {n} 出现失败，建议 max_workers 设为 {levels[levels.index(n)-1] if levels.index(n) > 0 else 1}")
            break
    else:
        print(f"\n✓ 所有级别通过，并发上限至少 {levels[-1]}")


if __name__ == "__main__":
    main()
