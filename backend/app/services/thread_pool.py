"""全局 LLM 线程池，供所有 Pipeline 阶段共用。"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.services.system_config import get_value

_pool_size = get_value("LLM_THREAD_POOL_SIZE", getattr(settings, "LLM_THREAD_POOL_SIZE", 40))
llm_thread_pool = ThreadPoolExecutor(
    max_workers=_pool_size,
    thread_name_prefix="llm-worker",
)

# ── 活跃任务计数 ──────────────────────────────────────────

_active_task_count = 0
_active_task_lock = threading.Lock()


def register_task():
    """任务启动时调用，计数器 +1"""
    global _active_task_count
    with _active_task_lock:
        _active_task_count += 1


def unregister_task():
    """任务结束时调用，计数器 -1"""
    global _active_task_count
    with _active_task_lock:
        _active_task_count = max(0, _active_task_count - 1)


def get_active_task_count() -> int:
    """获取当前活跃任务数"""
    return _active_task_count


# ── 动态批大小 ────────────────────────────────────────────


def get_dynamic_batch_size() -> int:
    """根据活跃任务数动态计算每批大小。

    公式：max(1, pool_size // active_count)
    """
    active = get_active_task_count()
    if active <= 0:
        return _pool_size
    return max(1, _pool_size // active)


def get_pool_size() -> int:
    """获取当前线程池大小"""
    return _pool_size


async def iter_completed_futures(fut_to_item: dict):
    """替代 asyncio.as_completed — 使用 asyncio.wait 逐条完成逐条 yield。

    asyncio.as_completed 在 Python < 3.12 中 yield 内部 _wait_for_one 协程，
    而非原始 future，导致无法用 future 查字典获取对应 item。

    本函数通过 asyncio.wait(return_when=FIRST_COMPLETED) 循环，
    yield 真正的 future 对象和对应 item。
    """
    pending = set(fut_to_item.keys())
    while pending:
        done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED
        )
        for fut in done:
            yield fut, fut_to_item[fut]


# ── 滑动窗口执行器 ──────────────────────────────────────────


class SlidingWindowExecutor:
    """滑动窗口并发控制器：始终保持 window_size 个并发，完成一个补一个。

    用法::

        executor = SlidingWindowExecutor()
        for item in items:
            await executor.acquire()          # 窗口满时阻塞
            fut = loop.run_in_executor(pool, fn, *args)
            executor.track(fut, item)
            async for f, it in executor.iter_done():  # 非阻塞收割已完成的
                process(f, it)
        async for f, it in executor.drain():  # 收割剩余
            process(f, it)
    """

    def __init__(self):
        self._sem: asyncio.Semaphore | None = None
        self._pending: dict = {}
        self._last_window_size: int = 0

    def _window_size(self) -> int:
        active = get_active_task_count()
        return max(1, _pool_size // active) if active > 0 else _pool_size

    async def acquire(self):
        """获取一个窗口空位。窗口大小随活跃任务数动态调整。"""
        ws = self._window_size()
        if self._sem is None or ws != self._last_window_size:
            self._sem = asyncio.Semaphore(ws)
            self._last_window_size = ws
        await self._sem.acquire()

    def track(self, future, item):
        """跟踪一个已提交到线程池的 future，完成时自动释放窗口空位。"""
        self._pending[future] = item
        future.add_done_callback(lambda _: self._sem.release())

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    async def iter_done(self):
        """非阻塞 yield 所有已完成的 future+item。无已完成则立即返回。"""
        if not self._pending:
            return
        done, _ = await asyncio.wait(
            self._pending.keys(), timeout=0, return_when=asyncio.FIRST_COMPLETED
        )
        for fut in done:
            item = self._pending.pop(fut)
            yield fut, item

    async def drain(self):
        """阻塞等待所有剩余 pending futures 完成，逐个 yield。"""
        while self._pending:
            done, _ = await asyncio.wait(
                self._pending.keys(), return_when=asyncio.FIRST_COMPLETED
            )
            for fut in done:
                item = self._pending.pop(fut)
                yield fut, item
