"""Dataset Assessment router - Pipeline post-processing stage

Generate scoring standards (Assessment field) for short-answer QA items via LLM.
Requires prompt_id and model selection.

Key design:
- User selects a file, provides output_name, prompt, and LLM config
- Backend processes short-answer items through LLM with validation/repair
- Creates output file with Assessment field populated
"""

import asyncio
import json
import logging
import traceback
from functools import partial

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db, SessionLocal
from sqlalchemy import or_
from app.models.models import (
    File, Task, TaskLog, TaskStatusEnum, StageEnum,
    User, LLMConfig, Prompt,
)
from app.routers.auth import get_current_user
from app.services.thread_pool import (
    llm_thread_pool, register_task, unregister_task,
    get_dynamic_batch_size, iter_completed_futures, SlidingWindowExecutor,
)
from app.services.llm_service import call_llm_json_sync
from app.services.field_mapper import build_record_content
from app.services.file_service import create_output_file
from app.services.assessment_service import (
    normalize_assessment_text, get_assessment_value,
    is_qa_item, is_short_answer_item,
)
from app.services.validation_service import validate_file_fields

logger = logging.getLogger("qa_studio.dataset_assessment")

router = APIRouter()


class DatasetAssessmentStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the JSON file to assess")
    output_name: str = Field(..., description="Base name for output file")
    prompt_id: int = Field(..., description="ID of the prompt to use")
    model: str = Field(..., description="Model name to use for LLM calls")
    llm_config_id: Optional[int] = Field(None, description="ID of the LLM config to use")
    reference_fields: Optional[List[str]] = Field(None, description="参考字段列表，为空时使用 Prompt 默认值")


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    status: str
    progress_current: int
    progress_total: int
    generated_count: int = 0
    file_id: Optional[int] = None
    file_name: Optional[str] = None


def _add_task_log(db: Session, task_id: int, content: str):
    log = TaskLog(task_id=task_id, log_content=content)
    db.add(log)
    db.commit()


def _update_progress(db: Session, task_id: int, current: int):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.progress_current = current
        db.commit()


def _flush_results(file_path: str, items: list):
    """Write current results to output file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


async def _run_assessment_task(
    task_id: int,
    file_id: int,
    output_name: str,
    prompt_content: str,
    model: str,
    user_id: int,
    username: str,
    reference_fields=None,
    base_url_override=None,
    api_key_override=None,
    start_index: int = 0,
):
    """Background coroutine: batch-threaded assessment generation."""
    db = SessionLocal()
    register_task()
    output_file = None
    try:
        source_file = db.query(File).filter(File.id == file_id, File.user_id == user_id).first()
        if not source_file:
            _add_task_log(db, task_id, "源文件不存在")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            return

        # Read source JSON
        with open(source_file.file_path, "r", encoding="utf-8") as f:
            raw_items = json.load(f)
        if not isinstance(raw_items, list):
            raw_items = [raw_items]

        total = len(raw_items)
        short_answer_count = sum(1 for item in raw_items if is_short_answer_item(item))

        task = db.query(Task).filter(Task.id == task_id).first()
        if task and start_index == 0:
            task.progress_total = total
            task.source_file_id = file_id
            db.commit()

        if start_index == 0:
            # Pre-create output file so frontend sees it immediately
            output_file = create_output_file(
                db=db, user_id=user_id, source_file=source_file,
                stage=StageEnum.DATASET_ASSESSMENT, output_filename=output_name,
                username=username, name_suffix="assessed",
            )
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.file_id = output_file.id
                db.commit()
            _add_task_log(db, task_id, f"开始评分标准生成: 共 {total} 条记录, {short_answer_count} 条简答题, 输出文件: {output_file.filename}")
        else:
            task = db.query(Task).filter(Task.id == task_id).first()
            output_file = db.query(File).filter(File.id == task.file_id).first()
            _add_task_log(db, task_id, f"恢复任务，继续写入已有输出文件: {output_file.filename}")

        # Initialize updated_items with copies of all items
        updated_items = [dict(item) for item in raw_items]

        success_count = 0
        loop = asyncio.get_event_loop()
        consecutive_failures = 0
        processed_count = start_index
        executor = SlidingWindowExecutor()
        idx = start_index

        # ── helper: 处理单条完成结果 ──
        def _handle_result(fut, item):
            nonlocal success_count, consecutive_failures, processed_count
            batch_idx = item[0]
            try:
                result = fut.result()
            except Exception as e:
                _add_task_log(db, task_id, f"记录 {batch_idx + 1}: LLM调用失败 - {str(e)[:200]}")
                consecutive_failures += 1
                processed_count += 1
                _update_progress(db, task_id, processed_count)
                return

            consecutive_failures = 0
            assessment = get_assessment_value(result) if isinstance(result, dict) else ""
            updated_items[batch_idx]["Assessment"] = normalize_assessment_text(assessment)

            status_str = "OK" if assessment else "EMPTY"
            if assessment:
                success_count += 1
            _add_task_log(db, task_id, f"记录 {batch_idx + 1}: 评分标准={status_str}")
            processed_count += 1
            _update_progress(db, task_id, processed_count)

        while idx < total:
            # ── 暂停检查 ──
            task_check = db.query(Task).filter(Task.id == task_id).first()
            if task_check and task_check.status == TaskStatusEnum.PAUSED:
                async for fut, item in executor.drain():
                    _handle_result(fut, item)
                _flush_results(output_file.file_path, updated_items)
                _add_task_log(db, task_id, f"任务已暂停，已将 {processed_count} 条数据写入文件")
                return

            # ── 连续失败检查 ──
            if consecutive_failures >= 10:
                async for fut, item in executor.drain():
                    _handle_result(fut, item)
                _flush_results(output_file.file_path, updated_items)
                _add_task_log(db, task_id, f"连续{consecutive_failures}次调用失败，已将已有数据写入文件")
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.status = TaskStatusEnum.FAILED
                    db.commit()
                return

            # ── 准备当前记录 ──
            item = raw_items[idx]
            updated_items[idx] = dict(item)

            if not is_qa_item(item):
                processed_count += 1
                _update_progress(db, task_id, processed_count)
                idx += 1
                continue

            existing = get_assessment_value(item)
            updated_items[idx]["Assessment"] = normalize_assessment_text(existing)

            if is_short_answer_item(item) and not existing:
                record_content = build_record_content(item, reference_fields, "dataset_assessment")
                if not record_content:
                    _add_task_log(db, task_id, f"记录 {idx + 1}: 无参考内容，跳过")
                    processed_count += 1
                    _update_progress(db, task_id, processed_count)
                    idx += 1
                    continue
                llm_prompt = f"{prompt_content}\n\n---\n\n**参考内容：**\n\n{record_content}"

                # ── 获取窗口空位并提交 ──
                await executor.acquire()
                fut = loop.run_in_executor(
                    llm_thread_pool,
                    partial(call_llm_json_sync, prompt=llm_prompt, model=model, temperature=0.0,
                            base_url_override=base_url_override, api_key_override=api_key_override,
                            username=username),
                )
                executor.track(fut, (idx, llm_prompt))
            else:
                processed_count += 1
                _update_progress(db, task_id, processed_count)

            idx += 1

            # ── 收割已完成的结果（非阻塞） ──
            async for fut, item in executor.iter_done():
                _handle_result(fut, item)

            # Flush after each iteration so frontend can preview partial results
            _flush_results(output_file.file_path, updated_items)

        # ── 收割剩余 ──
        async for fut, item in executor.drain():
            _handle_result(fut, item)

        # Final flush
        _flush_results(output_file.file_path, updated_items)
        _add_task_log(db, task_id, f"评分标准生成完成: 简答题 {short_answer_count} 条, 成功 {success_count} 条")

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            db.commit()

    except Exception as e:
        logger.error("Assessment task %d failed | user=%s: %s\n%s", task_id, username, str(e), traceback.format_exc())
        try:
            db.rollback()
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            _add_task_log(db, task_id, f"评分生成失败: {str(e)[:200]}")
            if output_file:
                try:
                    _flush_results(output_file.file_path, updated_items)
                except Exception:
                    pass
        except Exception:
            pass
    finally:
        unregister_task()
        db.close()


@router.post("/start")
async def start_dataset_assessment(
    data: DatasetAssessmentStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a dataset assessment task."""
    # Validate file
    file_obj = (
        db.query(File)
        .filter(File.id == data.file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # Validate file has required fields for this stage
    is_valid, validation_msg, validation_stats = validate_file_fields(
        file_obj.file_path, "dataset_assessment"
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_msg,
        )

    # Validate prompt (belongs to user or is global)
    prompt_obj = (
        db.query(Prompt)
        .filter(Prompt.id == data.prompt_id, or_(Prompt.user_id == current_user.id, Prompt.user_id.is_(None)))
        .first()
    )
    if prompt_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提示词不存在")

    # Validate prompt stage matches
    if prompt_obj.stage != StageEnum.DATASET_ASSESSMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提示词必须为dataset_assessment阶段",
        )

    # Resolve LLM config overrides
    base_url_override = None
    api_key_override = None
    effective_llm_config_id = data.llm_config_id or prompt_obj.llm_config_id

    if effective_llm_config_id:
        llm_config_obj = db.query(LLMConfig).filter(LLMConfig.id == effective_llm_config_id).first()
        if llm_config_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM配置不存在")
        if llm_config_obj.user_id != current_user.id and llm_config_obj.user_id is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权使用此LLM配置")
        base_url_override = llm_config_obj.base_url
        api_key_override = llm_config_obj.api_key

    # Create Task record
    task = Task(
        user_id=current_user.id,
        stage=StageEnum.DATASET_ASSESSMENT,
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
        _run_assessment_task(
            task_id=task.id,
            file_id=data.file_id,
            output_name=data.output_name,
            prompt_content=prompt_obj.content,
            model=data.model,
            user_id=current_user.id,
            username=current_user.username,
            reference_fields=data.reference_fields or prompt_obj.reference_fields,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            start_index=0,
        )
    )

    return {"task_id": task.id, "status": task.status.value}


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_dataset_assessment_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status of a dataset assessment task."""
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    generated_count = 0
    file_obj = db.query(File).filter(File.id == task.file_id).first()
    if file_obj:
        try:
            with open(file_obj.file_path, "r", encoding="utf-8") as f:
                items = json.load(f)
            if isinstance(items, list):
                generated_count = sum(1 for item in items if is_short_answer_item(item) and str(item.get("Assessment", "")).strip())
        except Exception:
            pass

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status.value,
        progress_current=task.progress_current or 0,
        progress_total=task.progress_total or 0,
        generated_count=generated_count,
        file_id=task.file_id,
        file_name=file_obj.filename if file_obj else None,
    )


@router.get("/source-files")
async def list_source_files(
    show_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List JSON files for assessment.

    默认只返回 source_stage=dataset_split 的文件；show_all=True 时返回所有 JSON。
    """
    query = db.query(File).filter(
        File.user_id == current_user.id,
        File.file_type == "json",
    )
    if not show_all:
        query = query.filter(File.source_stage == StageEnum.DATASET_SPLIT)
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


def resume_dataset_assessment_task(task: Task, db: Session):
    """Resume a paused dataset_assessment task from progress_current."""
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

    user_obj = db.query(User).filter(User.id == task.user_id).first()
    username = user_obj.username if user_obj else str(task.user_id)

    base_url_override = None
    api_key_override = None
    if prompt_obj.llm_config_id:
        llm_config_obj = db.query(LLMConfig).filter(LLMConfig.id == prompt_obj.llm_config_id).first()
        if llm_config_obj:
            base_url_override = llm_config_obj.base_url
            api_key_override = llm_config_obj.api_key

    task.status = TaskStatusEnum.RUNNING
    db.commit()

    asyncio.create_task(
        _run_assessment_task(
            task_id=task.id,
            file_id=file_obj.id,
            output_name=file_obj.filename,
            prompt_content=prompt_obj.content,
            model=task.model,
            user_id=task.user_id,
            username=username,
            reference_fields=prompt_obj.reference_fields,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            start_index=task.progress_current or 0,
        )
    )
