# 需求：LLM 任务改进（Prompt 修复 + 默认文件名 + 任务停止恢复）

## 背景

Pipeline 的 9 个阶段虽然业务逻辑不同，但都是「选文件 → 选 Prompt → 选模型 → 调用 LLM → 写结果」的同构流程。当前在使用层面有以下问题需要统一改进：

1. 选 Prompt 下拉里能看到「V1 默认」，但点击「开始生成」会报 `Prompt not found`。
2. 输出文件名要求用户手动输入，没有合理的默认值，体验差。
3. 任务跑起来之后无法中途停止和恢复，只能等失败或完成。

本需求一并修复以上 3 项，作为分支 1 的工作内容。
分支：`feature/llm-task-improvements`

---

## 需求 1：修复 Prompt not found

### 现状
- `Prompt.user_id` 允许为 `NULL`，表示「全局共享默认 Prompt」（`is_default=True`）。
- 各阶段 `/start` 接口在校验 prompt 时使用 `Prompt.user_id == current_user.id`，遗漏了 `user_id IS NULL` 的全局 Prompt。
- 但 `/prompts/by-stage/<stage>` 列表接口包含全局 Prompt，所以下拉能看到，启动时却 404。

### 修改点
所有阶段 `/start` 接口（共 9 个 router）的 prompt 校验语句统一改为：

```python
from sqlalchemy import or_

prompt_obj = (
    db.query(Prompt)
    .filter(
        Prompt.id == data.prompt_id,
        or_(Prompt.user_id == current_user.id, Prompt.user_id.is_(None)),
    )
    .first()
)
```

### 涉及文件
- `backend/app/routers/question_generate.py`
- `backend/app/routers/knowledge_generate.py`
- `backend/app/routers/question_validate.py`
- `backend/app/routers/answer_generate.py`
- `backend/app/routers/answer_validate.py`
- `backend/app/routers/data_evaluate.py`
- `backend/app/routers/cot_filter.py`（如使用 prompt）
- `backend/app/routers/dataset_split.py`（如使用 prompt）
- `backend/app/routers/dataset_assessment.py`

> 同时检查 retry 接口是否有同样问题，若有一并修复。

### 验收
- 选「V1 默认」全局 prompt 启动任务，正常运行。
- 选用户自建 prompt 启动任务，正常运行。
- 选他人私有 prompt 启动任务，404（保持原隔离）。

---

## 需求 2：默认输出文件名

### 命名格式
```
{源文件名（去扩展名）}_{当前阶段中文名}_{username}_{YYYYMMDDHHmmss}.json
```

例：源文件 `corpus.json`，当前阶段「答案生成」，用户 `alice`，时间 `20260505143012`：
```
corpus_答案生成_alice_20260505143012.json
```

### 阶段中文名映射（补全 9 个）
| stage 枚举 | 中文名 |
|---|---|
| QUESTION_GENERATE | 问题生成 |
| KNOWLEDGE_GENERATE | 知识体系 |
| QUESTION_VALIDATE | 问题校验 |
| ANSWER_GENERATE | 答案生成 |
| ANSWER_VALIDATE | 答案校验 |
| DATA_EVALUATE | 数据评估 |
| COT_FILTER | COT过滤 |
| DATASET_SPLIT | 数据集切分 |
| DATASET_ASSESSMENT | 评分标准生成 |

补全 `backend/app/services/file_service.py` 中的 `STAGE_LABELS` 字典，作为后端唯一来源；前端通过同样映射或新增 `/api/stages/labels` 接口（推荐复用前端常量即可）。

### 后端改动
- `create_output_file()` 新增 `stage: StageEnum` 参数（必填），用于拼入文件名。
- 现有 `stage_name` 参数保留兼容但废弃，新调用一律传 stage。

### 前端改动
- 各阶段页面（`QuestionGenerate.vue` 等 9 个），新增 `output_filename` 输入框（如已存在保留），并在以下时机自动填默认值：
  1. 首次进入页面且尚未输入。
  2. 切换源文件时（输入框为空或仍为旧默认值时刷新；用户已手动改过的不覆盖）。
- 默认值前端拼接：`{base}_{阶段中文}_{username}_{YYYYMMDDHHmmss}`，提交时不带 `.json`（后端补）。
- 用户可继续修改。

### 验收
- 进入「答案生成」选源文件 `corpus.json`，输入框自动出现 `corpus_答案生成_<username>_<时间>` 的默认值。
- 切源文件后默认值同步刷新（前提：用户没改过）。
- 用户手动改过后切源文件，默认值不覆盖用户输入。

---

## 需求 3：任务停止 / 恢复（软停）

### 状态机扩展
- `TaskStatusEnum` 新增 `PAUSED = "paused"`。
- 状态流转：
  - `RUNNING` → `PAUSED`（用户主动停止）
  - `PAUSED` → `RUNNING`（用户主动恢复）
  - `PAUSED` → `FAILED/COMPLETED`（恢复后正常结束）

### 软停语义
后台 task 协程在每条记录处理**前**重读一次 `task.status`：
- 若发现 `status == PAUSED`，立即 `break` 退出循环，**不**写部分结果。
- 当前正在处理的那条记录处理完整后才退出（保证不出现半条脏数据）。
- 已经写入数据库 / 文件的进度保留，`progress_current` 准确反映已处理条数。

### 接口设计
统一在 `backend/app/routers/tasks.py` 添加（已有该文件）：

```
POST /api/tasks/{task_id}/stop
  - 鉴权：task.user_id == current_user.id
  - 仅 RUNNING 任务可停止
  - 把 status 改为 PAUSED，立即返回（不等协程退出）

POST /api/tasks/{task_id}/resume
  - 仅 PAUSED 任务可恢复
  - 把 status 改回 RUNNING
  - 重新派发对应阶段的后台协程（按 stage 分发）
  - 起点 = task.progress_current
```

`resume` 内部需要按 `task.stage` 路由到对应阶段的 `_run_xxx_task()` 函数。建议方案：
- 在每个 router 模块中暴露一个 `resume_task(task: Task)` 入口函数，封装重启该阶段任务所需参数读取（file、prompt、llm config、原始 category 等）。
- `tasks.py` 维护 `STAGE_TO_RESUMER: dict[StageEnum, Callable]` 字典分发。

### 前端改动
- 所有阶段页面的「任务运行区」按钮区域：
  - `RUNNING` 状态：显示「停止」按钮（调用 `/stop`）
  - `PAUSED` 状态：显示「恢复」按钮（调用 `/resume`）+ 当前进度
  - `FAILED` / `COMPLETED`：保留现有「重试」按钮逻辑
- 进度轮询 `/status/{task_id}` 显示 `paused` 状态文案：`已暂停 (xxx/yyy)`。

### 验收
- 启动一个 10 条记录的任务，跑到 3 条左右点「停止」：
  - 状态变为 `paused`，`progress_current` 在 3~4 之间（取决于点击瞬间）。
  - 已写入的数据完整保留，正在处理的那条不出现半条脏数据。
- 点「恢复」续跑到 10，结果与不停止时完全一致。
- `paused` 状态下刷新浏览器，进度恢复正确。

---

## 不在本需求范围（属于分支 2）
- 输出文件改为新文件不覆盖（需求 4）
- File `source_stage` tag 过滤（需求 5）

## 涉及文件总览

后端：
- `backend/app/models/models.py`（TaskStatusEnum 新增 PAUSED）
- `backend/app/services/file_service.py`（STAGE_LABELS 补全 + create_output_file 加 stage 参数）
- `backend/app/routers/*.py` 9 个阶段 router（prompt 过滤修复 + resume 入口）
- `backend/app/routers/tasks.py`（stop / resume 接口）
- `scripts/migrate_task_status_paused.py`（如使用 SQLAlchemy 自动建表则可省）

前端：
- `frontend/src/views/*.vue` 9 个阶段页面（默认文件名 + 停止/恢复按钮）
- `frontend/src/api/index.js`（stop / resume API 包装）
- `frontend/src/utils/stageLabels.js`（新建，前端阶段中文名常量）
