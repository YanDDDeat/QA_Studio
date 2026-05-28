"""Generic Generate router - 通用生成（开放沙盒）

让用户能自由组合"任意文件 + 任意 Prompt + 任意 LLM"做一次性试跑或 Prompt 调试。
LLM 返回什么字段就保存什么字段（通过 apply_llm_fields_to_dataset 自动映射到
Dataset 标准列或 extra_fields JSON 列），不预设结构、不校验字段。

Key design (no-overwrite pattern):
- /start 不校验 prompt.stage、不校验 source_stage、不调 validate_file_fields()
- 文件选择默认 show_all=True（不限上游）
- Source Dataset records and disk files are NEVER modified
- 输出文件 source_stage=StageEnum.GENERIC
- 无评分解析逻辑
"""

import asyncio
import json
import logging
import traceback
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from sqlalchemy import or_
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
    write_datasets_to_file, ensure_datasets_for_file,
)
from app.services.field_mapper import apply_llm_fields_to_dataset, build_record_content

logger = logging.getLogger("qa_studio.generic_generate")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class GenericGenerateStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the JSON file to process")
    prompt_id: int = Field(..., description="ID of the prompt to use")
    model: str = Field(..., description="Model name to use for LLM calls")
    llm_config_id: Optional[int] = Field(None, description="ID of the LLM config to use")
    reference_fields: Optional[List[str]] = Field(None, description="参考字段列表，为空时使用 Prompt 默认值")
    output_filename: Optional[str] = Field(None, description="可选输出文件名 base，留空则按源文件派生")


class TaskStatusResponse(BaseModel):
    task_id: int
    status: str
    progress_current: int
    progress_total: int
    processed_count: int = 0
    file_id: Optional[int] = None
    filename: Optional[str] = None
    prompt_id: Optional[int] = None
    model: Optional[str] = None


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


async def _run_generic_task(
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
    """Background coroutine: 通用生成沙盒 — 对源 Dataset 调 LLM 后克隆到新输出文件，
    LLM 返回字段自动映射到 datasets 标准列或 extra_fields。

    原 file_id 下的 Dataset 与磁盘文件保持不变。
    """
    db = SessionLocal()
    register_task()
    output_file = None
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
                stage=StageEnum.GENERIC,
                output_filename=output_filename,
                username=username,
            )
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.file_id = output_file.id
                db.commit()
            _add_task_log(db, task_id, f"输出文件已创建: {output_file.filename} (file_id={output_file.id})")
        else:
            task = db.query(Task).filter(Task.id == task_id).first()
            output_file = db.query(File).filter(File.id == task.file_id).first()
            _add_task_log(db, task_id, f"恢复任务，继续写入已有输出文件: {output_file.filename}")

        processed_ok_count = 0
        loop = asyncio.get_event_loop()
        consecutive_failures = 0
        processed_count = start_index
        executor = SlidingWindowExecutor()

        # ── helper: 处理单条完成结果 ──
        def _handle_result(fut, item):
            nonlocal processed_ok_count, consecutive_failures, processed_count
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

            # 克隆 Dataset 到新输出文件，apply_llm_fields_to_dataset 自动把 LLM 字段
            # 映射到 datasets 标准列（能匹配的）或 extra_fields JSON 列（不能匹配的）
            cloned_ds = clone_single_dataset(db, dataset, output_file.id, StageEnum.GENERIC)
            extra = apply_llm_fields_to_dataset(cloned_ds, llm_result)
            cloned_ds.extra_fields = extra if extra else None
            db.commit()
            processed_ok_count += 1
            _add_task_log(db, task_id, f"记录 {batch_idx + 1}: 处理完成")
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
            record_content = build_record_content(dataset, reference_fields, "generic")
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

        if processed_ok_count == 0:
            _add_task_log(db, task_id, "本次任务无成功处理记录")
        else:
            write_datasets_to_file(db=db, file_id=output_file.id)
            _add_task_log(db, task_id, f"通用生成文件已生成: {output_file.filename}")

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            db.commit()

        logger.info(
            "Task %d completed: processed %d records, ok %d",
            task_id, total, processed_ok_count,
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
async def start_generic_generate(
    data: GenericGenerateStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a generic generate task.

    通用生成沙盒：不校验 prompt.stage、不校验 source_stage、不调 validate_file_fields。
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

    # Validate prompt exists and belongs to user (or is global)
    # 注意：不限制 prompt.stage（沙盒页面允许任意 stage 的 Prompt）
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
        stage=StageEnum.GENERIC,
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
        _run_generic_task(
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
async def get_generic_generate_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and progress of a generic generate task."""
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

    processed_count = 0
    if task.file_id:
        processed_count = (
            db.query(Dataset)
            .filter(
                Dataset.file_id == task.file_id,
                Dataset.user_id == current_user.id,
            )
            .count()
        )

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status.value,
        progress_current=task.progress_current or 0,
        progress_total=task.progress_total or 0,
        processed_count=processed_count,
        file_id=task.file_id,
        filename=db.query(File).filter(File.id == task.file_id).first().filename if task.file_id else None,
        prompt_id=task.prompt_id,
        model=task.model,
    )


@router.get("/source-files")
async def list_source_files(
    show_all: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List JSON files for generic_generate.

    默认 show_all=True（通用页面不限上游）。
    """
    query = db.query(File).filter(
        File.user_id == current_user.id,
        File.file_type == "json",
    )
    # 通用生成不限制 source_stage，默认返回全部 JSON 文件。
    # 如果未来需要按 source_stage 过滤，可扩展 show_all=False 的行为。
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
async def retry_generic_generate(
    task_id: int,
    prompt_id: Optional[int] = Body(None),
    model: Optional[str] = Body(None),
    llm_config_id: Optional[int] = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry a failed or completed generic generate task.

    Re-processes the source file from progress_current breakpoint.
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

    # Count source records (用于进度跟踪)
    remaining_count = (
        db.query(Dataset)
        .filter(
            Dataset.file_id == source_fid,
            Dataset.user_id == current_user.id,
        )
        .count()
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
        _run_generic_task(
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


def resume_generic_task(task: Task, db: Session, llm_config_id=None):
    """Resume a paused generic_generate task from progress_current."""
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
        _run_generic_task(
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
