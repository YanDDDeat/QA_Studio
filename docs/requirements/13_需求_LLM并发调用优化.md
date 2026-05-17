# 需求：LLM 并发调用优化（线程池方案）

## 背景

当前系统 6 个 Pipeline 阶段的 LLM 调用均为串行执行：`for` 循环逐条 `await call_llm_json()`。
当数据量达到上千条时，单任务处理时间过长（假设每条 5 秒，1000 条需要 83 分钟）。
需要引入并发机制提升吞吐量，同时支持多用户公平调度。

## 方案概述

采用 **全局 ThreadPoolExecutor + 分批提交 + 动态批大小** 方案。

## 详细设计

### 1. 同步版 LLM 调用

- 在 `llm_service.py` 中新增 `call_llm_sync()` 和 `call_llm_json_sync()`
- 使用 `httpx.Client`（同步）替代 `httpx.AsyncClient`
- 抽出公共逻辑（payload 构建、响应解析、thinking 标签剥离）供 async/sync 共用
- 原有 async 版本保持不变，不影响现有调用方

### 2. 全局线程池（进程级单例）

- 新建 `backend/app/services/thread_pool.py`，定义全局 `ThreadPoolExecutor`
- `max_workers` 从配置文件读取，默认 20
- 进程级单例，所有用户、所有任务共享同一个线程池
- 超过 max_workers 的任务自动在线程池内部队列排队，不会报错

### 3. 管理员前端配置线程池大小

- 管理员可在前端 LLM 配置中心设置全局线程池大小（max_workers）
- 后端提供接口读写该配置项
- 修改后需考虑：是否立即生效（重建线程池）还是下次启动生效
  - 建议：保存配置后提示"重启后端后生效"，避免运行中重建线程池的复杂性

### 4. 主控协程分批提交

- 每个 `_run_xxx_task()` 主控协程改为分批向线程池提交任务
- 使用 `loop.run_in_executor(pool, call_llm_json_sync, ...)` 桥接 async/sync
- 每批使用 `await asyncio.gather()` 等待全部完成，不阻塞事件循环
- 每批完成后：写 DB（Dataset 记录）、更新进度、检查暂停/失败

### 5. 动态批大小

- 维护全局活跃任务计数器 `active_task_count`（线程安全，使用 `threading.Lock`）
- 任务启动时 +1，结束时 -1
- 每批提交前动态计算：`batch_size = max(1, max_workers // active_task_count)`
- 效果：
  - 1 个任务时独享全部线程（batch=20）
  - 20 个任务时每人保底 1 个线程（batch=1）
  - 任务完成后，剩余任务自动获得更大批次

### 6. 进度追踪

- 改为每批完成后更新一次：`progress_current += batch_size`
- 前端进度条从"逐条涨"变成"每批跳一次"，体验差别不大
- 更新进度在主控协程中进行（单线程），无线程安全问题

### 7. 暂停处理

- 每批之间检查 `task.status == PAUSED`
- 检测到暂停后，调用 `write_datasets_to_file()` 刷盘，然后退出
- 已提交到线程池的当前批次会跑完（最多多跑 batch_size 条），可接受

### 8. 失败处理

- 废弃 `consecutive_failures` 连续失败计数
- 改为 **连续整批失败** 检测：一批中全部失败才计为一次批失败
- 连续 4 批全部失败 → 终止任务（等效于原来的连续 20 次失败）
- 终止前调用 `write_datasets_to_file()` 刷盘

### 9. DB Session 安全

- 线程内各自创建独立的 `SessionLocal()`，用完关闭
- 主控协程持有自己的 session，用于更新进度和任务状态
- 互不共享，不需要加锁
- 注意：此方案要求使用 MySQL（支持多连接并发写入）；SQLite 因文件级锁不适用

### 10. JSON 文件写入

- `write_datasets_to_file()` 仍在全部完成后由主控协程调用一次
- 暂停/失败时的刷盘也在主控协程中串行调用
- 无并发写文件问题，不需要额外处理

## 改造范围

6 个 Pipeline 阶段全部按同一模式改造：
1. `question_generate.py` — 问题生成
2. `knowledge_generate.py` — 知识体系生成
3. `question_validate.py` — 问题校验
4. `answer_generate.py` — 答案生成
5. `answer_validate.py` — 答案校验
6. `data_evaluate.py` — 数据评估

## 新增/修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/llm_service.py` | 修改 | 抽出公共逻辑，新增 sync 版本 |
| `backend/app/services/thread_pool.py` | 新建 | 全局线程池 + 活跃任务计数器 |
| `backend/app/config.py` | 修改 | 新增 `LLM_THREAD_POOL_SIZE` 配置项 |
| `backend/app/routers/llm_config.py` | 修改 | 新增线程池大小的读写接口 |
| `backend/app/routers/question_generate.py` | 修改 | 分批并发改造 |
| `backend/app/routers/knowledge_generate.py` | 修改 | 分批并发改造 |
| `backend/app/routers/question_validate.py` | 修改 | 分批并发改造 |
| `backend/app/routers/answer_generate.py` | 修改 | 分批并发改造 |
| `backend/app/routers/answer_validate.py` | 修改 | 分批并发改造 |
| `backend/app/routers/data_evaluate.py` | 修改 | 分批并发改造 |
| 前端 LLM 配置页面 | 修改 | 管理员配置线程池大小 |

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_THREAD_POOL_SIZE` | 20 | 全局线程池最大线程数 |
| `LLM_BATCH_SIZE` | 5 | 每批提交任务数（动态模式下为最大值/上限参考） |

注：动态批大小 `max(1, pool_size // active_tasks)` 会自动调整，`LLM_BATCH_SIZE` 仅作为无动态计算时的回退默认值。
