"""Quality Check router - Pipeline Stage 7

对评分阶段（data_evaluate）的输出 JSON 文件做最后一道 LLM 质检：
每条记录送给 LLM，LLM 返回 PASS / FAIL + reason。

Key design (no-overwrite pattern, 与 answer_validate 完全一致):
- User selects a JSON file (file_id), not individual Dataset records
- Background task queries DB for Dataset records linked to that file
- Source Dataset records and disk files are NEVER modified
- PASS records: cloned to a new output File with source_stage=QUALITY_CHECK
- FAIL records: collected into a separate consolidated fail file (后缀 _质检失败)
- Retry re-processes remaining unprocessed records from the original source file
"""

import asyncio
import json
import logging
import traceback

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db, SessionLocal
from sqlalchemy import func, or_
from app.models.models import (
    Dataset, File, Prompt, Task, TaskLog, TaskStatusEnum,
    StageEnum, User, LLMConfig,
)
from app.routers.auth import get_current_user
from app.services.llm_service import call_llm_json_sync, LLMCallError
from functools import partial
from app.services.thread_pool import (
    llm_thread_pool, register_task, unregister_task, get_dynamic_batch_size,
    iter_completed_futures, SlidingWindowExecutor,
)
from app.services.file_service import (
    create_output_file, clone_single_dataset,
    write_datasets_to_file, create_fail_file, serialize_dataset_to_dict,
    ensure_datasets_for_file,
)
from app.services.field_mapper import apply_llm_fields_to_dataset, build_record_content
from app.services.validation_service import validate_file_fields

logger = logging.getLogger("qa_studio.quality_check")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class QualityCheckStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the JSON file to process")
    prompt_id: int = Field(..., description="ID of the prompt to use")
    model: str = Field(..., description="Model name to use for LLM calls")
    llm_config_id: Optional[int] = Field(None, description="ID of the LLM config to use")
    reference_fields: Optional[List[str]] = Field(None, description="参考字段列表，为空时使用 Prompt 默认值")
    output_filename: Optional[str] = Field(None, description="可选输出文件名 base，留空则按源文件派生")


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
# Background task runner
# ---------------------------------------------------------------------------


async def _run_quality_check_task(
    task_id: int,
    file_id: int,
    prompt_content: str,
    model: str,
    user_id: int,
    username: str,
    reference_fields = None,
    output_filename: Optional[str] = None,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
    start_index: int = 0,
):
    """Background coroutine: 质检源 Dataset → PASS 克隆到新输出文件 + FAIL 单独成 fail file。

    原 file_id 下的 Dataset 与磁盘文件保持不变。
    """
    db = SessionLocal()
    register_task()
    output_file = None
    source_file = None
    try:
        source_datasets = ensure_datasets_for_file(db, file_id, user_id)

        total = len(source_datasets)

        task = db.query(Task).filter(Task.id == task_id).first()
        if task and start_index == 0:
            task.progress_total = total
            task.source_file_id = file_id
            db.commit()

        if start_index == 0:
            # 提前创建输出文件，点击开始后前端立即显示输出文件名
            source_file = db.query(File).filter(File.id == file_id).first()
            output_file = create_output_file(
                db=db,
                user_id=user_id,
                source_file=source_file,
                stage=StageEnum.QUALITY_CHECK,
                output_filename=output_filename,
                username=username,
            )
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.file_id = output_file.id
                db.commit()
        else:
            task = db.query(Task).filter(Task.id == task_id).first()
            output_file = db.query(File).filter(File.id == task.file_id).first()
            source_file = db.query(File).filter(File.id == file_id).first()
            _add_task_log(db, task_id, f"恢复任务，继续写入已有输出文件: {output_file.filename}")

        pass_ids: list[int] = []
        fail_records: list[dict] = []
        pass_count = 0
        fail_count = 0
        loop = asyncio.get_event_loop()
        consecutive_failures = 0
        processed_count = start_index
        executor = SlidingWindowExecutor()

        # ── helper: 处理单条完成结果 ──
        def _handle_result(fut, item):
            nonlocal pass_count, fail_count, consecutive_failures, processed_count
            batch_idx = item[0]
            dataset = item[2]
            try:
                result = fut.result()
            except Exception as e:
                err_detail = getattr(e, 'detail', None)
                err_msg = f"{e} | detail={err_detail}" if err_detail else str(e)
                logger.error(
                    "Task %d: LLM call failed for record %d | user=%s: %s",
                    task_id, batch_idx, username, err_msg,
                )
                _add_task_log(
                    db, task_id,
                    f"记录 {batch_idx + 1}: LLM调用失败 - {err_msg[:200]}",
                )
                consecutive_failures += 1
                processed_count += 1
                _update_progress(db, task_id, processed_count)
                return

            consecutive_failures = 0
            llm_result = result

            validation_result = llm_result.get("validation_result", "")
            reason = llm_result.get("reason", "")
            validation_result_upper = str(validation_result).upper().strip()

            if validation_result_upper == "PASS":
                cloned_ds = clone_single_dataset(db, dataset, output_file.id, StageEnum.QUALITY_CHECK)
                cloned_ds.passed = "是"
                extra = apply_llm_fields_to_dataset(cloned_ds, llm_result)
                cloned_ds.extra_fields = extra if extra else None
                db.commit()
                pass_count += 1
                _add_task_log(db, task_id, f"记录 {batch_idx + 1}: 质检通过")
            else:
                fail_dict = serialize_dataset_to_dict(dataset)
                fail_dict["passed"] = "否"
                fail_dict["validation_result"] = validation_result
                fail_dict["reason"] = reason
                fail_records.append(fail_dict)
                fail_count += 1
                _add_task_log(db, task_id, f"记录 {batch_idx + 1}: 质检失败 - {reason[:100]}")

            processed_count += 1
            _update_progress(db, task_id, processed_count)

        idx = start_index
        while idx < total:
            # ── 暂停检查 ──
            task_check = db.query(Task).filter(Task.id == task_id).first()
            if task_check and task_check.status == TaskStatusEnum.PAUSED:
                async for fut, item in executor.drain():
                    _handle_result(fut, item)
                try:
                    write_datasets_to_file(db=db, file_id=output_file.id)
                    _add_task_log(db, task_id, f"任务已暂停，已将 {processed_count} 条数据写入文件")
                except Exception as flush_err:
                    _add_task_log(db, task_id, f"任务已暂停，刷写文件失败: {str(flush_err)[:200]}")
                return

            # ── 连续失败检查 ──
            if consecutive_failures >= 10:
                async for fut, item in executor.drain():
                    _handle_result(fut, item)
                try:
                    write_datasets_to_file(db=db, file_id=output_file.id)
                    _add_task_log(db, task_id, f"连续{consecutive_failures}次调用失败，已将已有数据写入文件")
                except Exception as flush_err:
                    _add_task_log(db, task_id, f"连续失败终止，刷写文件失败: {str(flush_err)[:200]}")
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.status = TaskStatusEnum.FAILED
                    db.commit()
                return

            # ── 准备当前记录 ──
            dataset = source_datasets[idx]
            record_content = build_record_content(dataset, reference_fields, "quality_check")
            llm_prompt = f"{prompt_content}\n\n---\n\n**参考内容：**\n\n{record_content}"

            # ── 获取窗口空位并提交 ──
            await executor.acquire()
            fut = loop.run_in_executor(
                llm_thread_pool,
                partial(call_llm_json_sync, prompt=llm_prompt, model=model, temperature=0.3,
                        base_url_override=base_url_override, api_key_override=api_key_override,
                        username=username),
            )
            executor.track(fut, (idx, llm_prompt, dataset))
            idx += 1

            # ── 收割已完成的结果（非阻塞） ──
            async for fut, item in executor.iter_done():
                _handle_result(fut, item)

        # ── 收割剩余 ──
        async for fut, item in executor.drain():
            _handle_result(fut, item)

        if pass_count > 0:
            write_datasets_to_file(db=db, file_id=output_file.id)
            _add_task_log(db, task_id, f"通过文件已生成: {output_file.filename} (共{pass_count}条)")
        else:
            _add_task_log(db, task_id, "本次任务无通过记录，输出文件无数据")

        if fail_records and source_file:
            fail_file = create_fail_file(
                db=db,
                user_id=user_id,
                source_file=source_file,
                stage=StageEnum.QUALITY_CHECK,
                fail_records=fail_records,
            )
            _add_task_log(
                db, task_id,
                f"失败记录文件已生成: {fail_file.filename} (共 {len(fail_records)} 条)",
            )

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            task.file_id = output_file.id
            db.commit()

        logger.info(
            "Task %d completed: processed %d records, %d passed, %d failed",
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
            if output_file:
                try:
                    write_datasets_to_file(db=db, file_id=output_file.id)
                    logger.info("Task %d: flushed partial data to file on exception exit", task_id)
                except Exception:
                    pass
        except Exception:
            pass
    finally:
        unregister_task()
        db.close()


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
# API endpoints
# ---------------------------------------------------------------------------


@router.post("/start")
async def start_quality_check(
    data: QualityCheckStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a quality check task.

    Validates the file and prompt, creates a Task record, and launches
    a background coroutine that processes each qualifying Dataset record
    through the LLM. Returns the task_id for progress polling.
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
    is_valid, validation_msg, validation_stats = validate_file_fields(
        file_obj.file_path, "quality_check"
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_msg,
        )

    # Validate prompt exists and belongs to user (or is global)
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

    # Validate prompt stage matches
    if prompt_obj.stage != StageEnum.QUALITY_CHECK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提示词必须为quality_check阶段",
        )

    # Resolve LLM config overrides
    base_url_override = None
    api_key_override = None

    # Priority: explicit llm_config_id > prompt's llm_config_id > settings default
    effective_llm_config_id = data.llm_config_id or prompt_obj.llm_config_id

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
        # Check visibility: user must own it or it must be global
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
        stage=StageEnum.QUALITY_CHECK,
        file_id=data.file_id,
        model=data.model,
        prompt_id=data.prompt_id,
        status=TaskStatusEnum.RUNNING,
        progress_current=0,
        progress_total=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Launch background task
    asyncio.create_task(
        _run_quality_check_task(
            task_id=task.id,
            file_id=data.file_id,
            prompt_content=prompt_obj.content,
            model=data.model,
            user_id=current_user.id,
            username=current_user.username,
            reference_fields=data.reference_fields or prompt_obj.reference_fields,
            output_filename=data.output_filename,
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
async def get_quality_check_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and progress of a quality check task.

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

    # Count pass/fail from task logs for this specific task
    pass_count = (
        db.query(func.count(TaskLog.id))
        .filter(
            TaskLog.task_id == task_id,
            TaskLog.log_content.contains("质检通过"),
        )
        .scalar()
    )

    fail_count = (
        db.query(func.count(TaskLog.id))
        .filter(
            TaskLog.task_id == task_id,
            TaskLog.log_content.contains("质检失败"),
        )
        .scalar()
    )

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
    """List JSON files for quality_check.

    默认只返回 source_stage=data_evaluate 的文件；show_all=True 时返回所有 JSON。
    """
    query = db.query(File).filter(
        File.user_id == current_user.id,
        File.file_type == "json",
    )
    if not show_all:
        query = query.filter(File.source_stage == StageEnum.DATA_EVALUATE)
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


@router.post("/retry/{task_id}")
async def retry_quality_check(
    task_id: int,
    prompt_id: Optional[int] = Body(None),
    model: Optional[str] = Body(None),
    llm_config_id: Optional[int] = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry a failed or completed quality check task.

    Re-queries remaining qualifying datasets (those still at
    data_evaluate stage for the original source file) and processes them.
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

    if task.status not in (TaskStatusEnum.FAILED, TaskStatusEnum.COMPLETED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有失败或已完成的任务可以重试",
        )

    if prompt_id is not None:
        task.prompt_id = prompt_id
    if model is not None:
        task.model = model
    if prompt_id is not None or model is not None:
        db.commit()

    # Get the SOURCE file for this task
    source_fid = task.source_file_id or task.file_id
    file_obj = (
        db.query(File)
        .filter(File.id == source_fid, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原文件不存在",
        )

    # Get the prompt for this task
    prompt_obj = (
        db.query(Prompt)
        .filter(Prompt.id == task.prompt_id, or_(Prompt.user_id == current_user.id, Prompt.user_id.is_(None)))
        .first()
    )
    if prompt_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原提示词不存在",
        )

    # Count remaining qualifying datasets for progress tracking
    remaining_count = (
        db.query(func.count(Dataset.id))
        .filter(
            Dataset.file_id == source_fid,
            Dataset.user_id == current_user.id,
            Dataset.current_stage == StageEnum.DATA_EVALUATE,
        )
        .scalar()
    )

    # Keep progress_current for breakpoint resume
    start_index = task.progress_current or 0

    # Resolve LLM config overrides
    base_url_override = None
    api_key_override = None
    config_id = llm_config_id or prompt_obj.llm_config_id
    if config_id:
        llm_config_obj = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
        if llm_config_obj:
            base_url_override = llm_config_obj.base_url
            api_key_override = llm_config_obj.api_key

    task.status = TaskStatusEnum.RUNNING
    task.progress_total = remaining_count
    db.commit()

    # Launch background task to process remaining records
    asyncio.create_task(
        _run_quality_check_task(
            task_id=task.id,
            file_id=source_fid,
            prompt_content=prompt_obj.content,
            model=task.model,
            user_id=current_user.id,
            username=current_user.username,
            reference_fields=prompt_obj.reference_fields,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            start_index=start_index,
        )
    )

    return {
        "task_id": task.id,
        "status": task.status.value,
        "progress_current": task.progress_current,
        "progress_total": task.progress_total,
        "message": f"重试: {remaining_count} 条待处理记录",
    }

# ---------------------------------------------------------------------------
# Resume handler (called by tasks.py /resume endpoint)
# ---------------------------------------------------------------------------


def resume_quality_check_task(task: Task, db: Session, llm_config_id=None):
    """Resume a paused quality_check task from progress_current."""
    source_fid = task.source_file_id or task.file_id
    file_obj = (
        db.query(File)
        .filter(File.id == source_fid, File.user_id == task.user_id)
        .first()
    )
    if file_obj is None:
        raise ValueError("Original file not found")

    prompt_obj = (
        db.query(Prompt)
        .filter(Prompt.id == task.prompt_id, or_(Prompt.user_id == task.user_id, Prompt.user_id.is_(None)))
        .first()
    )
    if prompt_obj is None:
        raise ValueError("Original prompt not found")

    start_index = task.progress_current or 0
    user_obj = db.query(User).filter(User.id == task.user_id).first()
    username = user_obj.username if user_obj else str(task.user_id)

    base_url_override = None
    api_key_override = None
    config_id = llm_config_id or prompt_obj.llm_config_id
    if config_id:
        llm_config_obj = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
        if llm_config_obj:
            base_url_override = llm_config_obj.base_url
            api_key_override = llm_config_obj.api_key

    task.status = TaskStatusEnum.RUNNING
    db.commit()

    asyncio.create_task(
        _run_quality_check_task(
            task_id=task.id,
            file_id=file_obj.id,
            prompt_content=prompt_obj.content,
            model=task.model,
            user_id=task.user_id,
            username=username,
            reference_fields=prompt_obj.reference_fields,
            start_index=start_index,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
    )
