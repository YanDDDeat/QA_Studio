"""线程池公平调度测试 — 验证 AdjustableLimiter 修复 SlidingWindowExecutor 的不公平 bug。

不依赖真实 LLM 与数据库：worker 函数用 time.sleep 模拟 LLM 调用耗时。
"""

import asyncio
import pathlib
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

# 让 `app.services.thread_pool` 可导入（项目无 pyproject.toml）
_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services import thread_pool as tp  # noqa: E402
from app.services.thread_pool import SlidingWindowExecutor  # noqa: E402


# ── fixtures ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_globals():
    """每个测试前后把 active_task_count 与 _pool_size 复位到确定状态。"""
    original_pool_size = tp._pool_size
    tp._active_task_count = 0
    tp._pool_size = 40
    yield
    tp._active_task_count = 0
    tp._pool_size = original_pool_size


@pytest.fixture
def mock_pool():
    """提供一个独立的 40-worker 线程池，避免污染全局 llm_thread_pool。"""
    pool = ThreadPoolExecutor(max_workers=40, thread_name_prefix="test-worker")
    yield pool
    pool.shutdown(wait=True)


class ConcurrencyTracker:
    """线程安全地追踪当前并发数与历史峰值。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.current = 0
        self.peak = 0
        self.completed = 0

    def worker(self, duration: float = 0.05):
        with self._lock:
            self.current += 1
            if self.current > self.peak:
                self.peak = self.current
        time.sleep(duration)
        with self._lock:
            self.current -= 1
            self.completed += 1


# ── 测试用例 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_single_task_uses_full_pool(mock_pool):
    """active=1 时单 executor 应能跑满 40 并发。"""
    tp.register_task()
    executor = SlidingWindowExecutor()
    loop = asyncio.get_running_loop()
    tracker = ConcurrencyTracker()

    for _ in range(50):
        await executor.acquire()
        fut = loop.run_in_executor(mock_pool, tracker.worker, 0.05)
        executor.track(fut, None)
        async for _f, _it in executor.iter_done():
            pass
    async for _f, _it in executor.drain():
        pass

    assert tracker.completed == 50
    assert tracker.peak == 40, f"期望峰值并发 40，实际 {tracker.peak}"
    assert executor._limiter.in_flight == 0


@pytest.mark.asyncio
async def test_window_shrinks_no_burst(mock_pool):
    """窗口缩小后，老 executor 不应"突击"提交新任务（Bug A 回归保护）。"""
    tp.register_task()  # active=1, capacity=40
    executor = SlidingWindowExecutor()
    loop = asyncio.get_running_loop()
    tracker = ConcurrencyTracker()

    # 把 in_flight 拉到 40
    for _ in range(40):
        await executor.acquire()
        fut = loop.run_in_executor(mock_pool, tracker.worker, 1.0)
        executor.track(fut, None)
    assert executor._limiter.in_flight == 40
    assert executor._limiter.capacity == 40

    # 模拟用户 B 加入：active=2，下一次 acquire 必须阻塞
    tp.register_task()

    blocked = False
    try:
        await asyncio.wait_for(executor.acquire(), timeout=0.3)
    except asyncio.TimeoutError:
        blocked = True

    assert blocked, "Bug A 回归：窗口缩小后立刻 acquire 不应成功，应等 in_flight 自然下降"
    assert executor._limiter.capacity == 20
    assert executor._limiter.in_flight == 40, (
        "in_flight 应保持 40，说明老的 release 没有偷偷给新限制器灌 permit"
    )

    async for _f, _it in executor.drain():
        pass


@pytest.mark.asyncio
async def test_window_grows_resumes(mock_pool):
    """active 从 2 降到 1 后，executor 应能从 capacity=20 恢复到 40。"""
    tp.register_task()
    tp.register_task()  # active=2
    executor = SlidingWindowExecutor()
    loop = asyncio.get_running_loop()
    tracker = ConcurrencyTracker()

    for _ in range(20):
        await executor.acquire()
        fut = loop.run_in_executor(mock_pool, tracker.worker, 1.0)
        executor.track(fut, None)
    assert executor._limiter.in_flight == 20

    # 第 21 次应阻塞
    blocked = False
    try:
        await asyncio.wait_for(executor.acquire(), timeout=0.2)
    except asyncio.TimeoutError:
        blocked = True
    assert blocked, "capacity=20 下第 21 次 acquire 应阻塞"

    # 用户 B 离开：active=1
    tp.unregister_task()

    # 现在应能再提交 20 个，到达 in_flight=40
    for _ in range(20):
        await asyncio.wait_for(executor.acquire(), timeout=1.0)
        fut = loop.run_in_executor(mock_pool, tracker.worker, 0.05)
        executor.track(fut, None)

    assert executor._limiter.capacity == 40
    assert executor._limiter.in_flight == 40

    async for _f, _it in executor.drain():
        pass


@pytest.mark.asyncio
async def test_two_users_fair_share(mock_pool):
    """主测试：A 占满 40 后 B 加入，2 秒内 A、B 完成数比例应在 [0.8, 1.25]。"""
    # A 先单独跑
    tp.register_task()  # active=1
    executor_a = SlidingWindowExecutor()
    loop = asyncio.get_running_loop()
    tracker = ConcurrencyTracker()

    stop_flag = [False]
    count_a = [0]
    count_b = [0]

    async def run_a():
        while not stop_flag[0]:
            await executor_a.acquire()
            fut = loop.run_in_executor(mock_pool, tracker.worker, 0.05)
            executor_a.track(fut, None)
            async for _f, _it in executor_a.iter_done():
                count_a[0] += 1
        async for _f, _it in executor_a.drain():
            count_a[0] += 1

    task_a = asyncio.create_task(run_a())

    # A 充分跑起来：达到 in_flight=40 的稳态
    await asyncio.sleep(0.3)

    # B 加入：active=2，A capacity 立即降到 20
    tp.register_task()
    executor_b = SlidingWindowExecutor()

    # 重置计数器，只统计 B 加入后的 throughput
    count_a[0] = 0
    count_b[0] = 0

    async def run_b():
        while not stop_flag[0]:
            await executor_b.acquire()
            fut = loop.run_in_executor(mock_pool, tracker.worker, 0.05)
            executor_b.track(fut, None)
            async for _f, _it in executor_b.iter_done():
                count_b[0] += 1
        async for _f, _it in executor_b.drain():
            count_b[0] += 1

    task_b = asyncio.create_task(run_b())

    # 测量窗口
    await asyncio.sleep(2.0)
    stop_flag[0] = True
    await asyncio.gather(task_a, task_b)

    a, b = count_a[0], count_b[0]
    assert a > 0 and b > 0, f"A={a}, B={b}（其中一方完全饥饿）"
    ratio = a / b if a > b else b / a
    assert ratio <= 1.25, (
        f"分配不公平：A={a}, B={b}, 较高/较低 ratio={ratio:.2f}（要求 ≤ 1.25）"
    )


@pytest.mark.asyncio
async def test_no_permit_leak_under_oscillation(mock_pool):
    """窗口反复缩放 100 次后，executor 实际并发不应超过线程池总容量。"""
    tp.register_task()  # active=1
    executor = SlidingWindowExecutor()
    loop = asyncio.get_running_loop()
    tracker = ConcurrencyTracker()

    async def submit_loop():
        for _ in range(300):
            await executor.acquire()
            fut = loop.run_in_executor(mock_pool, tracker.worker, 0.005)
            executor.track(fut, None)
            # 实时检查：任何时刻 in_flight 不应超过线程池上限
            assert executor._limiter.in_flight <= tp._pool_size, (
                f"in_flight={executor._limiter.in_flight} 超过 pool_size={tp._pool_size}"
            )
            assert tracker.current <= tp._pool_size, (
                f"实际并发 {tracker.current} 超过 pool_size {tp._pool_size}"
            )
            async for _f, _it in executor.iter_done():
                pass
        async for _f, _it in executor.drain():
            pass

    async def oscillator():
        for _ in range(100):
            tp.register_task()
            await asyncio.sleep(0.002)
            tp.unregister_task()
            await asyncio.sleep(0.002)

    await asyncio.gather(submit_loop(), oscillator())

    assert executor._limiter.in_flight == 0, (
        f"测试结束时 in_flight 应回到 0，实际 {executor._limiter.in_flight}（permit 泄漏）"
    )
    assert tracker.peak <= tp._pool_size, (
        f"历史峰值并发 {tracker.peak} 超过 pool_size {tp._pool_size}"
    )
