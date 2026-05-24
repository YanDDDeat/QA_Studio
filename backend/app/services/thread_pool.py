"""全局 LLM 线程池，供所有 Pipeline 阶段共用。"""

import asyncio
import os
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor

_pool_size = int(os.environ.get("LLM_THREAD_POOL_SIZE", "40"))
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


# ── 可动态调整的并发限制器 ──────────────────────────────────


class AdjustableLimiter:
    """可动态调整容量的并发限制器，不会因容量变化产生 permit 泄漏。"""

    def __init__(self):
        self._in_flight: int = 0
        self._capacity: int = 0
        self._waiters: "deque[asyncio.Future]" = deque()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        return self._loop

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def capacity(self) -> int:
        return self._capacity

    def set_capacity(self, capacity: int) -> None:
        """更新目标容量；扩容时唤醒等待者，缩容不撤回已发出的 slot。"""
        capacity = max(0, int(capacity))
        grew = capacity > self._capacity
        self._capacity = capacity
        if grew:
            self._wake_waiters()

    def _wake_waiters(self) -> None:
        # 在容量允许范围内逐个唤醒等待者；唤醒时直接代表他们"占住"一个 slot
        while self._waiters and self._in_flight < self._capacity:
            waiter = self._waiters.popleft()
            if waiter.done():
                continue
            self._in_flight += 1
            waiter.set_result(None)

    async def acquire(self) -> None:
        """阻塞直到 in_flight < capacity，然后 in_flight += 1。"""
        loop = self._ensure_loop()
        # 快速路径：无人排队且有余量
        if not self._waiters and self._in_flight < self._capacity:
            self._in_flight += 1
            return
        waiter = loop.create_future()
        self._waiters.append(waiter)
        try:
            await waiter
        except BaseException:
            # 两种情况：
            #  1) 仍在队列里：未拿到 slot，移除即可
            #  2) 已被弹出：唤醒后才取消，slot 已记到自己头上，需要归还
            try:
                self._waiters.remove(waiter)
            except ValueError:
                if self._in_flight > 0:
                    self._in_flight -= 1
                self._wake_waiters()
            raise

    def release(self) -> None:
        """线程安全减计数；可以从任意线程（含 worker 线程）调用。"""
        loop = self._loop
        if loop is None:
            return
        if loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._release_impl)
        except RuntimeError:
            # 事件循环已结束的边缘场景：静默忽略
            pass

    def _release_impl(self) -> None:
        if self._in_flight > 0:
            self._in_flight -= 1
        self._wake_waiters()


# ── 滑动窗口执行器 ──────────────────────────────────────────


class SlidingWindowExecutor:
    """滑动窗口并发控制器：按 active_task_count 动态分配窗口，完成一个补一个。

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
        self._limiter = AdjustableLimiter()
        self._pending: dict = {}

    def _window_size(self) -> int:
        active = get_active_task_count()
        return max(1, _pool_size // active) if active > 0 else _pool_size

    async def acquire(self):
        """获取一个窗口空位。窗口大小随活跃任务数动态调整。"""
        self._limiter.set_capacity(self._window_size())
        await self._limiter.acquire()

    def track(self, future, item):
        """跟踪一个已提交到线程池的 future，完成时自动释放窗口空位。"""
        self._pending[future] = item
        limiter = self._limiter
        future.add_done_callback(lambda _: limiter.release())

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
