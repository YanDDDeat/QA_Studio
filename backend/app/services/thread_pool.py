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
