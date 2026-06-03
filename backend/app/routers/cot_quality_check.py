"""CoT Quality Check router - Pipeline post-processing stage

对带思维链的 JSON 数据进行四维度深度质量评估。
逐条调用 LLM，解析 overall_quality 评级，按评级分桶输出三个文件。

Key design:
- User selects a file and provides an output name
- Backend processes each record through LLM for quality assessment
- Creates three output JSON files: 通过、不通过、评估结果
- Returns task_id for progress tracking (async background task)
- Supports pause/resume, consecutive failure protection
"""

import asyncio
import json
import logging
import os
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from typing import Optional, Tuple

from app.database import get_db, SessionLocal
from sqlalchemy import or_
from app.models.models import (
    File, Task, TaskLog, TaskStatusEnum,
    StageEnum, User, LLMConfig, Prompt,
)
from app.routers.auth import get_current_user
from app.services.llm_service import call_llm_json_sync, LLMCallError
from app.services.cot_quality_check_service import (
    COT_QUALITY_CHECK_SYSTEM_PROMPT,
    flatten_nested_cot_items,
    _build_user_prompt,
    _PASS_RATINGS,
    _FAIL_RATINGS,
)
from functools import partial
from app.services.thread_pool import (
    llm_thread_pool, register_task, unregister_task, SlidingWindowExecutor,
)
from app.services.file_service import create_output_file
from app.services.validation_service import validate_file_fields

logger = logging.getLogger("qa_studio.cot_quality_check")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class CotQualityCheckStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the JSON file to process")
    output_name: str = Field(..., description="Base name for output files")
    prompt_id: Optional[int] = Field(None, description="ID of optional prompt override")
    model: Optional[str] = Field(None, description="Model name to use for LLM calls")
    llm_config_id: Optional[int] = Field(None, description="ID of the LLM config to use")


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    status: str
    progress_current: int
    progress_total: int
    pass_count: int = 0
    fail_count: int = 0
    file_id: Optional[int] = None
    filename: Optional[str] = None
    prompt_id: Optional[int] = None
    model: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

# Field aliases for cot_quality_check: chain_of_thought can be chainofThought or cot
_COT_QC_FIELD_ALIASES = {"chain_of_thought": ["chainofThought", "cot"]}


def _validate_flattened_fields(
    flat_data: list,
    stage: str,
) -> Tuple[bool, str, dict]:
    """Validate that flattened data has the required fields for a given stage.

    Works on already-flattened data in memory (not reading from disk).
    Supports field aliases (e.g. chainofThought for chain_of_thought).
    """
    required = ["input", "chain_of_thought", "output"]
    aliases = _COT_QC_FIELD_ALIASES

    total = len(flat_data)
    if total == 0:
        return False, "JSON文件没有记录", {"total": 0, "qualified": 0}

    missing_counts: dict = {}
    qualified = 0

    for record in flat_data:
        if not isinstance(record, dict):
            for field in required:
                missing_counts[field] = missing_counts.get(field, 0) + 1
            continue

        has_all = True
        for field in required:
            value = record.get(field, "")
            if value is None or value == "" or value == [] or value == {}:
                alias_list = aliases.get(field, [])
                found = False
                for alias in alias_list:
                    alt_value = record.get(alias, "")
                    if alt_value and alt_value is not None and alt_value != "" and alt_value != [] and alt_value != {}:
                        found = True
                        break
                if found:
                    continue
                missing_counts[field] = missing_counts.get(field, 0) + 1
                has_all = False

        if has_all:
            qualified += 1

    stats = {"total": total, "qualified": qualified, "missing_fields": missing_counts}

    if qualified == 0:
        parts = []
        for field, count in missing_counts.items():
            parts.append(f"'{field}' 缺失 {count}/{total} 条")
        msg = f"文件不满足 {stage} 阶段字段要求: {', '.join(parts)}. 至少需要部分记录包含所有必需字段({', '.join(required)})"
        return False, msg, stats

    if qualified < total:
        logger.info(
            "Flattened data stage %s: %d/%d records qualify. Missing: %s",
            stage, qualified, total, json.dumps(missing_counts, ensure_ascii=False),
        )

    return True, "", stats


def _add_task_log(db: Session, task_id: int, content: str):
    """Add a TaskLog entry for the given task."""
    log = TaskLog(task_id=task_id, log_content=content)
    db.add(log)
    db.commit()


def _update_progress(db: Session, task_id: int, current: int):
    """Update the progress_current field on the Task record."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.progress_current = current
        db.commit()


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


async def _run_cot_quality_check_task(
    task_id: int,
    file_id: int,
    output_name: str,
    user_id: int,
    username: str,
    model: str = None,
    prompt_content: str = None,
    base_url_override: str = None,
    api_key_override: str = None,
    start_index: int = 0,
):
    """Background coroutine: CoT质检 — 逐条 LLM 评估 + 按评级分桶。

    原 file_id 下的源文件保持不变。
    产出三个文件：通过、不通过、评估结果（原数据 + cot_quality_assessment）。
    支持从 start_index 断点恢复。
    """
    db = SessionLocal()
    register_task()

    # 三个输出 File 记录（最后统一创建或复用已有）
    pass_file = None
    fail_file = None
    assessed_file = None

    # 恢复时已有的结果列表
    pass_items = []
    fail_items = []
    assessed_items = []

    try:
        # ── 读取源文件 ──
        source_file = db.query(File).filter(File.id == file_id, File.user_id == user_id).first()
        if not source_file:
            _add_task_log(db, task_id, "源文件不存在")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            return

        with open(source_file.file_path, "r", encoding="utf-8") as f:
            raw_items = json.load(f)

        if not isinstance(raw_items, list):
            raw_items = [raw_items]

        if not raw_items:
            _add_task_log(db, task_id, "源文件没有记录")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            return

        # Flatten nested structures (e.g. l0_cot_node → top-level fields)
        raw_items = flatten_nested_cot_items(raw_items)

        total = len(raw_items)

        task = db.query(Task).filter(Task.id == task_id).first()
        if task and start_index == 0:
            task.progress_total = total
            task.source_file_id = file_id
            db.commit()

        if start_index == 0:
            _add_task_log(db, task_id, f"开始CoT质检，共 {total} 条记录")

            # ── 提前创建三个输出文件 ──
            pass_file = create_output_file(
                db=db,
                user_id=user_id,
                source_file=source_file,
                stage=StageEnum.COT_QUALITY_CHECK,
                output_filename=output_name,
                username=username,
                name_suffix="通过",
                initial_content=[],
                text_field="input",
            )

            fail_file = create_output_file(
                db=db,
                user_id=user_id,
                source_file=source_file,
                stage=StageEnum.COT_QUALITY_CHECK,
                output_filename=output_name,
                username=username,
                name_suffix="不通过",
                initial_content=[],
                text_field="input",
            )

            assessed_file = create_output_file(
                db=db,
                user_id=user_id,
                source_file=source_file,
                stage=StageEnum.COT_QUALITY_CHECK,
                output_filename=output_name,
                username=username,
                name_suffix="评估结果",
                initial_content=[],
                text_field="input",
            )

            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.file_id = assessed_file.id
                db.commit()

            _add_task_log(
                db, task_id,
                f"输出文件已创建: 通过={pass_file.filename}, "
                f"不通过={fail_file.filename}, 评估结果={assessed_file.filename}",
            )
        else:
            # ── 恢复模式：复用已有输出文件 ──
            task = db.query(Task).filter(Task.id == task_id).first()
            if task and task.file_id:
                assessed_file = db.query(File).filter(File.id == task.file_id).first()

            # 从源文件名推断通过和不通过文件
            # 查找同一 source_file_id 下 COT_QUALITY_CHECK 阶段的其他文件
            sibling_files = (
                db.query(File)
                .filter(
                    File.user_id == user_id,
                    File.source_stage == StageEnum.COT_QUALITY_CHECK,
                )
                .all()
            )
            for sf in sibling_files:
                if "通过" in sf.filename and pass_file is None:
                    pass_file = sf
                elif "不通过" in sf.filename and fail_file is None:
                    fail_file = sf

            # 从已有文件中读取之前的结果
            if pass_file and os.path.exists(pass_file.file_path):
                try:
                    with open(pass_file.file_path, "r", encoding="utf-8") as f:
                        pass_items = json.load(f)
                except Exception:
                    pass_items = []

            if fail_file and os.path.exists(fail_file.file_path):
                try:
                    with open(fail_file.file_path, "r", encoding="utf-8") as f:
                        fail_items = json.load(f)
                except Exception:
                    fail_items = []

            if assessed_file and os.path.exists(assessed_file.file_path):
                try:
                    with open(assessed_file.file_path, "r", encoding="utf-8") as f:
                        assessed_items = json.load(f)
                except Exception:
                    assessed_items = []

            _add_task_log(db, task_id, f"恢复任务，从第 {start_index + 1} 条开始继续处理")

        # ── 逐条处理 ──
        pass_count = len(pass_items)
        fail_count = len(fail_items)
        loop = asyncio.get_event_loop()
        consecutive_failures = 0
        processed_count = start_index
        executor = SlidingWindowExecutor()

        # 有效 system prompt: 用户可选覆盖，否则使用内嵌默认
        effective_system_prompt = prompt_content or COT_QUALITY_CHECK_SYSTEM_PROMPT

        # ── helper: 处理单条完成结果 ──
        def _handle_result(fut, item):
            nonlocal pass_count, fail_count, consecutive_failures, processed_count
            batch_idx = item[0]
            record = item[2]
            try:
                llm_result = fut.result()
            except Exception as e:
                err_detail = getattr(e, 'detail', None)
                err_msg = f"{e} | detail={err_detail}" if err_detail else str(e)
                logger.error(
                    "Task %d: LLM call failed for record %d | user=%s: %s",
                    task_id, batch_idx, username, err_msg,
                )
                _add_task_log(
                    db, task_id,
                    f"记录 {batch_idx + 1}: LLM调用失败，归入不通过 - {err_msg[:200]}",
                )
                # LLM调用失败 → 该条归入不通过
                fail_items.append(record)
                assessed_record = dict(record)
                assessed_record["cot_quality_assessment"] = {
                    "overall_quality": "调用失败",
                    "evaluation_summary": f"LLM调用失败: {err_msg[:100]}",
                }
                assessed_items.append(assessed_record)
                fail_count += 1
                consecutive_failures += 1
                processed_count += 1
                _update_progress(db, task_id, processed_count)
                return

            consecutive_failures = 0

            # 解析 overall_quality 评级
            overall_quality = str(llm_result.get("overall_quality", "")).strip()

            # 构造评估结果记录（原数据 + cot_quality_assessment）
            assessed_record = dict(record)
            assessed_record["cot_quality_assessment"] = llm_result

            assessed_items.append(assessed_record)

            if overall_quality in _PASS_RATINGS:
                pass_items.append(record)
                pass_count += 1
                _add_task_log(
                    db, task_id,
                    f"记录 {batch_idx + 1}: CoT质检通过 - 评级={overall_quality}",
                )
            elif overall_quality in _FAIL_RATINGS:
                fail_items.append(record)
                fail_count += 1
                _add_task_log(
                    db, task_id,
                    f"记录 {batch_idx + 1}: CoT质检不通过 - 评级={overall_quality}",
                )
            else:
                # 未知评级 → 视为不通过
                fail_items.append(record)
                fail_count += 1
                _add_task_log(
                    db, task_id,
                    f"记录 {batch_idx + 1}: CoT质检评级未知({overall_quality})，归入不通过",
                )

            processed_count += 1
            _update_progress(db, task_id, processed_count)

        idx = start_index
        while idx < total:
            # ── 暂停检查 ──
            task_check = db.query(Task).filter(Task.id == task_id).first()
            if task_check and task_check.status == TaskStatusEnum.PAUSED:
                async for fut, item in executor.drain():
                    _handle_result(fut, item)
                # 暂停时将已有数据写入磁盘
                _flush_results_to_files(
                    db, pass_file, fail_file, assessed_file,
                    pass_items, fail_items, assessed_items,
                )
                _add_task_log(db, task_id, f"任务已暂停，已将 {processed_count} 条数据写入文件")
                return

            # ── 连续失败检查 ──
            if consecutive_failures >= 10:
                async for fut, item in executor.drain():
                    _handle_result(fut, item)
                _flush_results_to_files(
                    db, pass_file, fail_file, assessed_file,
                    pass_items, fail_items, assessed_items,
                )
                _add_task_log(
                    db, task_id,
                    f"连续{consecutive_failures}次调用失败，已将已有数据写入文件",
                )
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.status = TaskStatusEnum.FAILED
                    db.commit()
                return

            # ── 准备当前记录 ──
            record = raw_items[idx]
            user_prompt = _build_user_prompt(record)

            # ── 获取窗口空位并提交 ──
            await executor.acquire()
            fut = loop.run_in_executor(
                llm_thread_pool,
                partial(
                    call_llm_json_sync,
                    prompt=user_prompt,
                    model=model,
                    system_prompt=effective_system_prompt,
                    temperature=0.3,
                    base_url_override=base_url_override,
                    api_key_override=api_key_override,
                    username=username,
                ),
            )
            executor.track(fut, (idx, user_prompt, record))
            idx += 1

            # ── 收割已完成的结果（非阻塞） ──
            async for fut, item in executor.iter_done():
                _handle_result(fut, item)

        # ── 收割剩余 ──
        async for fut, item in executor.drain():
            _handle_result(fut, item)

        # ── 最终写入三个输出文件 ──
        _flush_results_to_files(
            db, pass_file, fail_file, assessed_file,
            pass_items, fail_items, assessed_items,
        )

        _add_task_log(
            db, task_id,
            f"CoT质检完成: 总计 {total} 条, 通过 {pass_count} 条({round(pass_count/total*100, 1) if total else 0}%), "
            f"不通过 {fail_count} 条({round(fail_count/total*100, 1) if total else 0}%)",
        )

        # 更新 Task 记录
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            task.file_id = assessed_file.id  # 主输出文件指向评估结果文件
            db.commit()

        logger.info(
            "Task %d completed: total=%d, pass=%d, fail=%d",
            task_id, total, pass_count, fail_count,
        )

    except Exception as e:
        logger.error(
            "Task %d unexpected error | user=%s: %s\n%s",
            task_id, username, str(e), traceback.format_exc(),
        )
        try:
            db.rollback()
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            # 异常退出时尝试将已有数据刷写到磁盘
            if assessed_file:
                try:
                    _flush_results_to_files(
                        db, pass_file, fail_file, assessed_file,
                        pass_items, fail_items, assessed_items,
                    )
                    logger.info("Task %d: flushed partial data to files on exception exit", task_id)
                except Exception:
                    pass
        except Exception:
            pass
    finally:
        unregister_task()
        db.close()


def _flush_results_to_files(
    db: Session,
    pass_file: File,
    fail_file: File,
    assessed_file: File,
    pass_items: list,
    fail_items: list,
    assessed_items: list,
):
    """将三个分桶结果写入对应的磁盘文件。"""
    import os

    for file_obj, items in [
        (pass_file, pass_items),
        (fail_file, fail_items),
        (assessed_file, assessed_items),
    ]:
        if file_obj is None:
            continue
        file_path = file_obj.file_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        logger.info(
            "Written %d items to file %s (file_id=%d)",
            len(items), file_obj.filename, file_obj.id,
        )


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.post("/start")
async def start_cot_quality_check(
    data: CotQualityCheckStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a CoT quality check task.

    Validates the file, creates a Task record, and launches
    a background coroutine that processes each record through LLM.
    Returns the task_id for progress polling.
    """
    # Validate file exists and belongs to user
    file_obj = (
        db.query(File)
        .filter(File.id == data.file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    # Validate file has required fields for this stage
    # First flatten nested structures (e.g. l0_cot_node → top-level), then validate
    import json as _json
    try:
        with open(file_obj.file_path, "r", encoding="utf-8") as f:
            raw_data = _json.load(f)
        if not isinstance(raw_data, list):
            raw_data = [raw_data]
        flat_data = flatten_nested_cot_items(raw_data)
        # Write flattened data to a temp location for validation
        is_valid, validation_msg, validation_stats = _validate_flattened_fields(
            flat_data, "cot_quality_check"
        )
    except (_json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"JSON文件解析失败: {str(e)}",
        )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_msg,
        )

    # Resolve prompt (optional override)
    prompt_content = None
    prompt_id = None
    if data.prompt_id:
        prompt_obj = (
            db.query(Prompt)
            .filter(Prompt.id == data.prompt_id, or_(Prompt.user_id == current_user.id, Prompt.user_id.is_(None)))
            .first()
        )
        if prompt_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="提示词不存在",
            )
        prompt_content = prompt_obj.content
        prompt_id = prompt_obj.id

    # Resolve model (required for LLM calls)
    effective_model = data.model
    if not effective_model:
        # 从 prompt 的 model 或全局默认取
        if prompt_id:
            prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
            if prompt_obj and prompt_obj.model:
                effective_model = prompt_obj.model
        if not effective_model:
            from app.config import settings
            effective_model = settings.effective_llm_model

    # Resolve LLM config overrides
    base_url_override = None
    api_key_override = None
    effective_llm_config_id = data.llm_config_id

    if prompt_id and not effective_llm_config_id:
        prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
        if prompt_obj:
            effective_llm_config_id = prompt_obj.llm_config_id

    if effective_llm_config_id:
        llm_config_obj = (
            db.query(LLMConfig)
            .filter(LLMConfig.id == effective_llm_config_id)
            .first()
        )
        if llm_config_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="LLM配置不存在",
            )
        if llm_config_obj.user_id != current_user.id and llm_config_obj.user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权使用此LLM配置",
            )
        base_url_override = llm_config_obj.base_url
        api_key_override = llm_config_obj.api_key

    # Create Task record
    task = Task(
        user_id=current_user.id,
        stage=StageEnum.COT_QUALITY_CHECK,
        file_id=data.file_id,
        model=effective_model,
        prompt_id=prompt_id,
        status=TaskStatusEnum.RUNNING,
        progress_current=0,
        progress_total=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Launch background task
    asyncio.create_task(
        _run_cot_quality_check_task(
            task_id=task.id,
            file_id=data.file_id,
            output_name=data.output_name,
            user_id=current_user.id,
            username=current_user.username,
            model=effective_model,
            prompt_content=prompt_content,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
    )

    return {
        "task_id": task.id,
        "status": task.status.value,
        "progress_current": task.progress_current,
        "progress_total": task.progress_total,
    }


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_cot_quality_check_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and progress of a CoT quality check task.

    Counts pass/fail from TaskLog records for accurate per-task counts.
    """
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在",
        )

    # 统计通过/不通过数（从 TaskLog 中计数）
    pass_count = (
        db.query(TaskLog)
        .filter(
            TaskLog.task_id == task_id,
            TaskLog.log_content.contains("CoT质检通过"),
        )
        .count()
    )

    fail_count = (
        db.query(TaskLog)
        .filter(
            TaskLog.task_id == task_id,
            TaskLog.log_content.contains("CoT质检不通过"),
        )
        .count()
    )
    # 加上 LLM调用失败归入不通过的记录
    llm_fail_count = (
        db.query(TaskLog)
        .filter(
            TaskLog.task_id == task_id,
            TaskLog.log_content.contains("LLM调用失败，归入不通过"),
        )
        .count()
    )
    fail_count += llm_fail_count

    # 加上评级未知归入不通过的记录
    unknown_fail_count = (
        db.query(TaskLog)
        .filter(
            TaskLog.task_id == task_id,
            TaskLog.log_content.contains("评级未知"),
        )
        .count()
    )
    fail_count += unknown_fail_count

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status.value,
        progress_current=task.progress_current or 0,
        progress_total=task.progress_total or 0,
        pass_count=pass_count,
        fail_count=fail_count,
        file_id=task.file_id,
        filename=db.query(File).filter(File.id == task.file_id).first().filename if task.file_id else None,
        prompt_id=task.prompt_id,
        model=task.model,
    )


@router.get("/source-files")
async def list_source_files(
    show_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List JSON files for CoT quality check.

    默认只返回 source_stage=cot_hcot_pipeline 的文件；show_all=True 时返回所有 JSON。
    如果没有 cot_hcot_pipeline 的文件，也返回包含 cot 或 chain_of_thought 字段的文件。
    """
    # 先查找是否有 source_stage 为 cot_hcot_pipeline 的 StageEnum 值
    # 如果项目中还没有这个 stage，则 fallback 到 COT_FILTER
    target_stages = []

    # 检查是否存在 COT_HCOT_PIPELINE enum 值
    if hasattr(StageEnum, "COT_HCOT_PIPELINE"):
        target_stages.append(StageEnum.COT_HCOT_PIPELINE)
    target_stages.append(StageEnum.COT_FILTER)

    query = db.query(File).filter(
        File.user_id == current_user.id,
        File.file_type == "json",
    )
    if not show_all:
        query = query.filter(File.source_stage.in_(target_stages))
    files = query.order_by(File.created_at.desc()).all()

    return [
        {
            "id": f.id,
            "filename": f.filename,
            "source_stage": f.source_stage.value if f.source_stage else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


# ---------------------------------------------------------------------------
# Resume handler (called by tasks.py /resume endpoint)
# ---------------------------------------------------------------------------


def resume_cot_quality_check_task(task: Task, db: Session, llm_config_id=None):
    """Resume a paused cot_quality_check task from progress_current."""
    source_fid = task.source_file_id or task.file_id
    file_obj = (
        db.query(File)
        .filter(File.id == source_fid, File.user_id == task.user_id)
        .first()
    )
    if file_obj is None:
        raise ValueError("Original file not found")

    # Get prompt (optional)
    prompt_content = None
    if task.prompt_id:
        prompt_obj = (
            db.query(Prompt)
            .filter(Prompt.id == task.prompt_id, or_(Prompt.user_id == task.user_id, Prompt.user_id.is_(None)))
            .first()
        )
        if prompt_obj:
            prompt_content = prompt_obj.content

    user_obj = db.query(User).filter(User.id == task.user_id).first()
    username = user_obj.username if user_obj else str(task.user_id)

    base_url_override = None
    api_key_override = None
    config_id = llm_config_id
    if not config_id and task.prompt_id:
        prompt_obj = db.query(Prompt).filter(Prompt.id == task.prompt_id).first()
        if prompt_obj:
            config_id = prompt_obj.llm_config_id
    if config_id:
        llm_config_obj = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
        if llm_config_obj:
            base_url_override = llm_config_obj.base_url
            api_key_override = llm_config_obj.api_key

    start_index = task.progress_current or 0

    task.status = TaskStatusEnum.RUNNING
    db.commit()

    asyncio.create_task(
        _run_cot_quality_check_task(
            task_id=task.id,
            file_id=file_obj.id,
            output_name="",  # 恢复时不重新命名，已有文件
            user_id=task.user_id,
            username=username,
            model=task.model,
            prompt_content=prompt_content,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            start_index=start_index,
        )
    )