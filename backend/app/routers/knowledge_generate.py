"""Knowledge Generate router - Pipeline Stage 2

Processes all Dataset records in a JSON file from the question_generate
stage through LLM prompts to generate knowledge and scene fields.

Key design:
- User selects a JSON file (file_id), not individual Dataset records
- Background task queries DB for Dataset records linked to that file
  at the question_generate stage
- Per-record LLM calls with structured JSON parsing
- After completion, results are written back to the same JSON file
- scene field is always set to the same value as knowledge
- Retry re-processes remaining unprocessed records
"""

import asyncio
import json
import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, SessionLocal
from app.models.models import (
    Dataset, File, Prompt, Task, TaskLog, TaskStatusEnum,
    StageEnum, User, LLMConfig,
)
from app.routers.auth import get_current_user
from app.services.llm_service import call_llm_json, LLMCallError
from app.services.file_service import write_datasets_to_file
from app.services.validation_service import validate_file_fields

logger = logging.getLogger("qa_studio.knowledge_generate")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class KnowledgeGenerateStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the JSON file to process")
    prompt_id: int = Field(..., description="ID of the prompt to use")
    model: str = Field(..., description="Model name to use for LLM calls")
    llm_config_id: Optional[int] = Field(None, description="ID of the LLM config to use")


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    status: str
    progress_current: int
    progress_total: int
    generated_count: int = 0
    file_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


async def _run_knowledge_generate_task(
    task_id: int,
    file_id: int,
    prompt_content: str,
    model: str,
    user_id: int,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
):
    """Background coroutine that processes each qualifying dataset record
    through the LLM to generate knowledge and scene fields.

    Queries all Dataset records linked to file_id at the question_generate
    stage, calls LLM for each, updates records, and writes results back
    to the JSON file on disk.

    Args:
        task_id: The Task record ID for progress tracking.
        file_id: The File record ID whose datasets should be processed.
        prompt_content: The prompt template to send with each record.
        model: LLM model name.
        user_id: Owner of all Dataset records (for verification).
    """
    db = SessionLocal()
    try:
        # Fetch all Dataset records linked to this file at question_generate stage
        datasets = (
            db.query(Dataset)
            .filter(
                Dataset.file_id == file_id,
                Dataset.user_id == user_id,
                Dataset.current_stage == StageEnum.QUESTION_GENERATE,
            )
            .order_by(Dataset.id.asc())
            .all()
        )

        total = len(datasets)

        # Update task with total count
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.progress_total = total
            db.commit()

        if total == 0:
            _add_task_log(db, task_id, "文件中没有待处理的question_generate阶段记录")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.COMPLETED
                db.commit()
            return

        generated_count = 0

        for idx in range(total):
            dataset = datasets[idx]

            # Get the input text from the dataset record
            input_text = dataset.input or ""
            if not input_text:
                logger.warning(
                    "Task %d: dataset record %d has no input text, skipping",
                    task_id, dataset.id,
                )
                _add_task_log(db, task_id, f"记录 {idx + 1}: 数据集ID {dataset.id} 无问题文本，跳过")
                _update_progress(db, task_id, idx + 1)
                continue

            # Call LLM with the prompt + input text
            try:
                llm_prompt = f"{prompt_content}\n\n{input_text}"
                llm_result = await call_llm_json(
                    prompt=llm_prompt,
                    model=model,
                    temperature=0.3,
                    base_url_override=base_url_override,
                    api_key_override=api_key_override,
                )
            except LLMCallError as e:
                logger.error(
                    "Task %d: LLM call failed for dataset %d: %s",
                    task_id, dataset.id, str(e),
                )
                _add_task_log(
                    db, task_id,
                    f"记录 {idx + 1}: LLM调用失败 - {str(e)[:200]}",
                )
                _update_progress(db, task_id, idx + 1)
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.status = TaskStatusEnum.FAILED
                    db.commit()
                return

            # The LLM returns a single JSON object for knowledge
            # Store it in knowledge field and set scene = knowledge
            if isinstance(llm_result, dict):
                dataset.knowledge = llm_result
                # scene = knowledge: store the same value as knowledge
                # scene is now a Text column, so we can store the full content
                knowledge_str = json.dumps(llm_result, ensure_ascii=False)
                dataset.scene = knowledge_str

                dataset.current_stage = StageEnum.KNOWLEDGE_GENERATE
                db.commit()
                generated_count += 1

                _add_task_log(
                    db, task_id,
                    f"记录 {idx + 1}: 知识体系生成成功 (数据集ID {dataset.id})",
                )
            else:
                logger.warning(
                    "Task %d: unexpected LLM result type for dataset %d: %s",
                    task_id, dataset.id, type(llm_result).__name__,
                )
                _add_task_log(
                    db, task_id,
                    f"记录 {idx + 1}: LLM返回非JSON对象，跳过",
                )

            _update_progress(db, task_id, idx + 1)

        # All records processed - write back to the JSON file on disk
        write_datasets_to_file(db=db, file_id=file_id)
        _add_task_log(db, task_id, f"结果已写回文件 (file_id={file_id})")

        # Mark task as completed
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            db.commit()

        logger.info(
            "Task %d completed: processed %d records, generated %d knowledge entries",
            task_id, total, generated_count,
        )

    except Exception as e:
        logger.error(
            "Task %d unexpected error: %s\n%s",
            task_id, str(e), traceback.format_exc(),
        )
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
        except Exception:
            pass
    finally:
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
async def start_knowledge_generate(
    data: KnowledgeGenerateStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a knowledge generation task.

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
        file_obj.file_path, "knowledge_generate"
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_msg,
        )

    # Validate file has qualifying datasets (at question_generate stage)
    qualifying_count = (
        db.query(Dataset)
        .filter(
            Dataset.file_id == data.file_id,
            Dataset.user_id == current_user.id,
            Dataset.current_stage == StageEnum.QUESTION_GENERATE,
        )
        .count()
    )
    if qualifying_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该文件中没有question_generate阶段的记录",
        )

    # Validate prompt exists and belongs to user
    prompt_obj = (
        db.query(Prompt)
        .filter(Prompt.id == data.prompt_id, Prompt.user_id == current_user.id)
        .first()
    )
    if prompt_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提示词不存在",
        )

    # Validate prompt stage matches
    if prompt_obj.stage != StageEnum.KNOWLEDGE_GENERATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提示词必须为knowledge_generate阶段",
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
        stage=StageEnum.KNOWLEDGE_GENERATE,
        file_id=data.file_id,
        model=data.model,
        prompt_id=data.prompt_id,
        status=TaskStatusEnum.RUNNING,
        progress_current=0,
        progress_total=qualifying_count,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Launch background task
    asyncio.create_task(
        _run_knowledge_generate_task(
            task_id=task.id,
            file_id=data.file_id,
            prompt_content=prompt_obj.content,
            model=data.model,
            user_id=current_user.id,
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
async def get_knowledge_generate_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and progress of a knowledge generation task."""
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

    # Count generated Dataset records at knowledge_generate stage for this file
    generated_count = (
        db.query(Dataset)
        .filter(
            Dataset.user_id == current_user.id,
            Dataset.current_stage == StageEnum.KNOWLEDGE_GENERATE,
            Dataset.file_id == task.file_id,
            Dataset.updated_at >= task.created_at,
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
    )


@router.get("/source-files")
async def list_source_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all JSON files available for the current user.

    Returns ALL JSON files belonging to the current user, regardless of
    pipeline stage. This allows users to select any file at any stage.
    Filtering happens at execution time — the background task only
    processes records at the correct previous stage.
    """
    files = (
        db.query(File)
        .filter(
            File.user_id == current_user.id,
            File.file_type == "json",
        )
        .order_by(File.created_at.desc())
        .all()
    )

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
async def retry_knowledge_generate(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry a failed or completed knowledge generation task.

    Re-queries remaining qualifying datasets (those still at
    question_generate stage for the file) and processes them.
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

    # Get the file for this task
    file_obj = (
        db.query(File)
        .filter(File.id == task.file_id, File.user_id == current_user.id)
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
        .filter(Prompt.id == task.prompt_id, Prompt.user_id == current_user.id)
        .first()
    )
    if prompt_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原提示词不存在",
        )

    # Count remaining qualifying datasets for progress tracking
    remaining_count = (
        db.query(Dataset)
        .filter(
            Dataset.file_id == task.file_id,
            Dataset.user_id == current_user.id,
            Dataset.current_stage == StageEnum.QUESTION_GENERATE,
        )
        .count()
    )

    # Reset task status and progress for retry
    task.status = TaskStatusEnum.RUNNING
    task.progress_current = 0
    task.progress_total = remaining_count
    db.commit()

    # Launch background task to process remaining records
    asyncio.create_task(
        _run_knowledge_generate_task(
            task_id=task.id,
            file_id=task.file_id,
            prompt_content=prompt_obj.content,
            model=task.model,
            user_id=current_user.id,
        )
    )

    return {
        "task_id": task.id,
        "status": task.status.value,
        "progress_current": task.progress_current,
        "progress_total": task.progress_total,
        "message": f"重试: {remaining_count} 条待处理记录",
    }