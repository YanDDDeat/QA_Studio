"""Question Generate router - Pipeline Stage 1

Processes uploaded JSON files through LLM prompts to generate
question-answer pairs. Each text record in the JSON is sent to
the LLM, which returns a list of question objects that are
stored as individual Dataset records.

Key design:
- Background task execution (asyncio.create_task)
- Frontend polls /status/{task_id} for progress
- Per-record LLM calls with structured JSON parsing
- Autoincrement IDs for Dataset records (globally unique numeric)
- User-scoped data isolation on all endpoints
- Retry from the last successfully processed record
"""

import asyncio
import json
import logging
import os
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db, SessionLocal
from sqlalchemy import or_
from app.models.models import (
    Dataset, File, Prompt, Task, TaskLog, TaskStatusEnum,
    StageEnum, SourceTypeEnum, User, LLMConfig,
)
from app.routers.auth import get_current_user
from app.services.llm_service import call_llm_json_sync, LLMCallError
from functools import partial
from app.services.thread_pool import (
    llm_thread_pool, register_task, unregister_task, get_dynamic_batch_size,
    iter_completed_futures, SlidingWindowExecutor,
)
from app.services.field_mapper import apply_llm_fields_to_dataset
from app.services.file_service import create_output_file, write_datasets_to_file
from app.services.validation_service import validate_file_fields

logger = logging.getLogger("qa_studio.question_generate")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class QuestionGenerateStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the uploaded JSON file")
    category: str = Field(..., description="Category: 知识问答 or 逻辑生成")
    source_type: str = Field(..., description="Source type: 图书, 专利, 文献, 其他")
    source: Optional[str] = Field(None, description="Source name (optional)")
    source_id: Optional[str] = Field(None, description="Source ID (optional)")
    prompt_id: int = Field(..., description="ID of the prompt to use")
    model: str = Field(..., description="Model name to use for LLM calls")
    llm_config_id: Optional[int] = Field(None, description="ID of the LLM config to use")
    reference_fields: Optional[List[str]] = Field(None, description="参考字段列表，为空时使用 Prompt 默认值")
    output_filename: str = Field(..., description="User-specified base name for the output file")


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    status: str
    progress_current: int
    progress_total: int
    generated_count: int = 0
    file_id: Optional[int] = None
    filename: Optional[str] = None


# ---------------------------------------------------------------------------
# Valid enum values
# ---------------------------------------------------------------------------

VALID_CATEGORIES = ["知识问答", "逻辑生成"]
VALID_SOURCE_TYPES = [s.value for s in SourceTypeEnum]


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


async def _run_question_generate_task(
    task_id: int,
    file_path: str,
    text_field: str,
    prompt_content: str,
    model: str,
    category: str,
    source_type: str,
    source_override: Optional[str],
    source_id_override: Optional[str],
    filename: str,
    user_id: int,
    source_file_id: int,
    output_filename: str,
    username: str,
    start_index: int = 0,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
):
    """Background coroutine that processes each text record through the LLM.

    Args:
        task_id: The Task record ID for progress tracking.
        file_path: Path to the JSON file on disk.
        text_field: The JSON field that contains text content.
        prompt_content: The prompt template to send with each text.
        model: LLM model name.
        category: User-selected category (知识问答 or 逻辑生成).
        source_type: User-selected source type.
        source_override: User-provided source name (highest priority).
        source_id_override: User-provided source ID (highest priority).
        filename: Original filename (fallback for source).
        user_id: Owner of all created Dataset records.
        source_file_id: ID of the source File record (for creating output file).
        start_index: Index to resume from (for retry).
    """
    db = SessionLocal()
    register_task()
    try:
        # Read and parse the JSON file
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            data = [data]

        total = len(data)

        # Update task with total count if starting fresh
        task = db.query(Task).filter(Task.id == task_id).first()
        if task and start_index == 0:
            task.progress_total = total
            task.source_file_id = source_file_id
            db.commit()

        generated_count = 0
        loop = asyncio.get_event_loop()
        consecutive_failures = 0
        processed_count = start_index
        executor = SlidingWindowExecutor()

        if start_index == 0:
            # 提前创建输出文件，点击开始后前端立即显示输出文件名
            source_file = db.query(File).filter(File.id == source_file_id).first()
            output_file = create_output_file(
                db=db,
                user_id=user_id,
                source_file=source_file,
                stage=StageEnum.QUESTION_GENERATE,
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
            _add_task_log(db, task_id, f"恢复任务，继续写入已有输出文件: {output_file.filename}")

        # ── helper: 处理单条完成结果 ──
        def _handle_result(fut, item):
            nonlocal generated_count, consecutive_failures, processed_count
            batch_idx = item[0]
            text_content = item[2]
            effective_source = item[3]
            effective_source_id = item[4]

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

            # Parse the LLM response as a list of question objects
            questions = []
            if isinstance(llm_result, list):
                questions = llm_result
            elif isinstance(llm_result, dict):
                for key in ["questions", "data", "items", "results", "qa_pairs", "list"]:
                    if key in llm_result and isinstance(llm_result[key], list):
                        questions = llm_result[key]
                        break
                if not questions:
                    questions = [llm_result]

            if not questions:
                logger.warning(
                    "Task %d: no questions generated for record %d",
                    task_id, batch_idx,
                )
                _add_task_log(
                    db, task_id,
                    f"记录 {batch_idx + 1}: 未生成问题",
                )
                processed_count += 1
                _update_progress(db, task_id, processed_count)
                return

            for q in questions:
                if not isinstance(q, dict):
                    continue
                dataset = Dataset(
                    user_id=user_id,
                    category=category,
                    corpus_cate=1,
                    source=effective_source,
                    source_id=effective_source_id,
                    source_type=source_type,
                    originContent=text_content,
                    file_id=output_file.id,
                    Assessment="",
                    current_stage=StageEnum.QUESTION_GENERATE,
                )
                q_normalized = dict(q)
                if "question" in q_normalized and "input" not in q_normalized:
                    q_normalized["input"] = q_normalized["question"]
                if "answer" in q_normalized and "output" not in q_normalized:
                    q_normalized["output"] = q_normalized["answer"]
                if "reasoning" in q_normalized and "cot" not in q_normalized:
                    q_normalized["cot"] = q_normalized["reasoning"]
                extra = apply_llm_fields_to_dataset(dataset, q_normalized)
                dataset.extra_fields = extra if extra else None
                db.add(dataset)
                generated_count += 1

            db.commit()
            _add_task_log(
                db, task_id,
                f"记录 {batch_idx + 1}: 生成 {len(questions)} 个问题",
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
            record = data[idx]

            text_content = ""
            if isinstance(record, dict):
                text_content = record.get(text_field, "")
                if not text_content:
                    for alt in ["text", "content", "body", "paragraph"]:
                        alt_val = record.get(alt, "")
                        if alt_val:
                            text_content = alt_val
                            break
            else:
                text_content = str(record)

            if not text_content:
                logger.warning(
                    "Task %d: record %d has no text content, skipping",
                    task_id, idx,
                )
                _add_task_log(db, task_id, f"记录 {idx + 1}: 无文本内容，跳过")
                processed_count += 1
                _update_progress(db, task_id, processed_count)
                idx += 1
                continue

            effective_source = source_override
            if not effective_source and isinstance(record, dict):
                effective_source = record.get("source", "")
            if not effective_source:
                effective_source = os.path.splitext(filename)[0]

            effective_source_id = source_id_override
            if not effective_source_id and isinstance(record, dict):
                effective_source_id = record.get("source_id", "")

            llm_prompt = f"{prompt_content}\n\n---\n\n**参考内容：**\n\n{text_content}"

            # ── 获取窗口空位并提交 ──
            await executor.acquire()
            fut = loop.run_in_executor(
                llm_thread_pool,
                partial(call_llm_json_sync, prompt=llm_prompt, model=model, temperature=0.3,
                        base_url_override=base_url_override, api_key_override=api_key_override,
                        username=username),
            )
            executor.track(fut, (idx, llm_prompt, text_content, effective_source, effective_source_id))
            idx += 1

            # ── 收割已完成的结果（非阻塞） ──
            async for fut, item in executor.iter_done():
                _handle_result(fut, item)

        # ── 收割剩余 ──
        async for fut, item in executor.drain():
            _handle_result(fut, item)

        # Write all datasets for this output file to disk as JSON
        write_datasets_to_file(db=db, file_id=output_file.id)

        _add_task_log(
            db, task_id,
            f"输出文件已生成: {output_file.filename}",
        )
        logger.info(
            "Task %d: wrote output file %s (file_id=%d)",
            task_id, output_file.filename, output_file.id,
        )

        # Mark task as completed
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            task.file_id = output_file.id
            db.commit()

        logger.info(
            "Task %d completed: processed %d records, generated %d questions",
            task_id, total, generated_count,
        )

    except Exception as e:
        logger.error(
            "Task %d unexpected error | user=%s: %s\n%s",
            task_id, username, str(e), traceback.format_exc(),
        )
        # Mark task as failed
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
async def start_question_generate(
    data: QuestionGenerateStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a question generation task.

    Validates inputs, creates a Task record, and launches a background
    coroutine that processes each text record through the LLM.
    Returns the task_id immediately so the frontend can poll for progress.
    """
    # Validate category
    if data.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category: {data.category}. Must be one of {VALID_CATEGORIES}",
        )

    # Validate source_type
    if data.source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type: {data.source_type}. Must be one of {VALID_SOURCE_TYPES}",
        )

    # Validate file exists and belongs to user
    file_obj = (
        db.query(File)
        .filter(File.id == data.file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if not os.path.exists(file_obj.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk",
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
            detail="Prompt not found",
        )

    # Validate prompt stage matches
    if prompt_obj.stage != StageEnum.QUESTION_GENERATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt must be for the question_generate stage",
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
    is_valid, validation_msg, validation_stats = validate_file_fields(
        file_obj.file_path, "question_generate", text_field=file_obj.text_field
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_msg,
        )

    total_records = validation_stats.get("total", 0)

    # Create Task record
    task = Task(
        user_id=current_user.id,
        stage=StageEnum.QUESTION_GENERATE,
        file_id=data.file_id,
        model=data.model,
        prompt_id=data.prompt_id,
        status=TaskStatusEnum.RUNNING,
        progress_current=0,
        progress_total=total_records,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Launch background task
    asyncio.create_task(
        _run_question_generate_task(
            task_id=task.id,
            file_path=file_obj.file_path,
            text_field=file_obj.text_field,
            prompt_content=prompt_obj.content,
            model=data.model,
            category=data.category,
            source_type=data.source_type,
            source_override=data.source,
            source_id_override=data.source_id,
            filename=file_obj.filename,
            user_id=current_user.id,
            source_file_id=file_obj.id,
            output_filename=data.output_filename,
            username=current_user.username,
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
async def get_question_generate_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and progress of a question generation task.

    Also counts how many Dataset records were generated for this task
    by checking records created after the task started.
    """
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Count generated Dataset records for this user with question_generate stage
    # created after this task started
    generated_count = (
        db.query(Dataset)
        .filter(
            Dataset.user_id == current_user.id,
            Dataset.current_stage == StageEnum.QUESTION_GENERATE,
            Dataset.created_at >= task.created_at,
        )
        .count()
    )

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status.value,
        progress_current=task.progress_current or 0,
        progress_total=task.progress_total or 0,
        generated_count=generated_count,
        file_id=task.file_id,
        filename=db.query(File).filter(File.id == task.file_id).first().filename if task.file_id else None,
    )


@router.post("/retry/{task_id}")
async def retry_question_generate(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry a failed question generation task.

    Resumes from the last successfully processed record index.
    Resets the task status to running and restarts the background coroutine.
    """
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.status not in (TaskStatusEnum.FAILED, TaskStatusEnum.COMPLETED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed or completed tasks can be retried",
        )

    # Get the file and prompt for this task
    file_obj = (
        db.query(File)
        .filter(File.id == task.file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original file not found",
        )

    prompt_obj = (
        db.query(Prompt)
        .filter(Prompt.id == task.prompt_id, or_(Prompt.user_id == current_user.id, Prompt.user_id.is_(None)))
        .first()
    )
    if prompt_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original prompt not found",
        )

    # Determine start_index from progress_current (last processed record)
    start_index = task.progress_current or 0

    # Determine category/source info from existing Dataset records
    # created during this task's first run
    category = _get_task_field(db, task, "category", "知识问答")
    source_type = _get_task_field(db, task, "source_type", "图书")
    source_override = _get_task_field(db, task, "source", None)
    source_id_override = _get_task_field(db, task, "source_id", None)

    # Reset task status to running
    task.status = TaskStatusEnum.RUNNING
    db.commit()

    # Launch background task from where it stopped
    asyncio.create_task(
        _run_question_generate_task(
            task_id=task.id,
            file_path=file_obj.file_path,
            text_field=file_obj.text_field,
            prompt_content=prompt_obj.content,
            model=task.model,
            category=category,
            source_type=source_type,
            source_override=source_override,
            source_id_override=source_id_override,
            filename=file_obj.filename,
            user_id=current_user.id,
            source_file_id=file_obj.id,
            output_filename=os.path.splitext(file_obj.filename)[0],
            username=current_user.username,
            start_index=start_index,
        )
    )

    return {
        "task_id": task.id,
        "status": task.status.value,
        "progress_current": task.progress_current,
        "progress_total": task.progress_total,
        "message": f"Retrying from record {start_index + 1}",
    }


def _get_task_field(db: Session, task: Task, field_name: str, default_value):
    """Retrieve a field from a Dataset record created by this task."""
    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.user_id == task.user_id,
            Dataset.current_stage == StageEnum.QUESTION_GENERATE,
            Dataset.created_at >= task.created_at,
        )
        .first()
    )
    if dataset and hasattr(dataset, field_name):
        value = getattr(dataset, field_name)
        if value:
            return value
    return default_value


@router.get("/source-files")
async def list_source_files(
    show_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List JSON files available for question_generate.

    默认只返回手动上传的文件（source_stage IS NULL）；show_all=True 时返回所有 JSON。
    """
    query = db.query(File).filter(
        File.user_id == current_user.id,
        File.file_type == "json",
    )
    if not show_all:
        query = query.filter(File.source_stage.is_(None))
    files = query.order_by(File.created_at.desc()).all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "text_field": f.text_field,
            "source_stage": f.source_stage.value if f.source_stage else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


# ---------------------------------------------------------------------------
# Resume handler (called by tasks.py /resume endpoint)
# ---------------------------------------------------------------------------


def resume_question_generate_task(task: Task, db: Session):
    """Resume a paused question_generate task from progress_current."""
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
    category = _get_task_field(db, task, "category", "知识问答")
    source_type = _get_task_field(db, task, "source_type", "图书")
    source_override = _get_task_field(db, task, "source", None)
    source_id_override = _get_task_field(db, task, "source_id", None)

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
        _run_question_generate_task(
            task_id=task.id,
            file_path=file_obj.file_path,
            text_field=file_obj.text_field,
            prompt_content=prompt_obj.content,
            model=task.model,
            category=category,
            source_type=source_type,
            source_override=source_override,
            source_id_override=source_id_override,
            filename=file_obj.filename,
            user_id=task.user_id,
            source_file_id=file_obj.id,
            output_filename=os.path.splitext(file_obj.filename)[0],
            username=username,
            start_index=start_index,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
    )