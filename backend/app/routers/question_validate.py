"""Question Validate router - Pipeline Stage 3

Validates all Dataset records in a JSON file from the knowledge_generate
stage through LLM prompts. Each record is sent to the LLM, which returns
a PASS/FAIL verdict with a reason.

Key design:
- User selects a JSON file (file_id), not individual Dataset records
- Background task queries DB for Dataset records linked to that file
  at the knowledge_generate stage
- PASS records: set passed="是", current_stage="question_validate"
  (no validation_result/reason kept on the Dataset record)
- FAIL records: set passed="否", file_id=None (removed from main file),
  then collected for a consolidated fail file
- After all processing: write_datasets_to_file() overwrites the main
  file (only PASS + skipped records remain), create_fail_file() creates
  a consolidated fail file for all FAIL records
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
from app.services.file_service import (
    write_datasets_to_file, create_fail_file, serialize_dataset_to_dict,
)
from app.services.validation_service import validate_file_fields

logger = logging.getLogger("qa_studio.question_validate")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class QuestionValidateStartRequest(BaseModel):
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
    pass_count: int = 0
    fail_count: int = 0
    file_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


async def _run_question_validate_task(
    task_id: int,
    file_id: int,
    prompt_content: str,
    model: str,
    user_id: int,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
):
    """Background coroutine that validates each qualifying dataset record
    through the LLM.

    Queries all Dataset records linked to file_id at the knowledge_generate
    stage, calls LLM for each, and handles PASS/FAIL results.

    For FAIL records:
    - Set passed="否" and file_id=None (removes from main file)
    - Collect serialized record dict + validation_result + reason

    After all processing:
    - write_datasets_to_file() overwrites main file (only PASS + skipped)
    - create_fail_file() creates consolidated fail file for all FAILs

    Args:
        task_id: The Task record ID for progress tracking.
        file_id: The File record ID whose datasets should be validated.
        prompt_content: The prompt template to send with each record.
        model: LLM model name.
        user_id: Owner of all Dataset records.
    """
    db = SessionLocal()
    try:
        # Fetch all Dataset records linked to this file at knowledge_generate stage
        datasets = (
            db.query(Dataset)
            .filter(
                Dataset.file_id == file_id,
                Dataset.user_id == user_id,
                Dataset.current_stage == StageEnum.KNOWLEDGE_GENERATE,
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
            _add_task_log(db, task_id, "文件中没有待处理的knowledge_generate阶段记录")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.COMPLETED
                db.commit()
            return

        pass_count = 0
        fail_count = 0
        fail_records = []

        for idx in range(total):
            dataset = datasets[idx]

            # Build the prompt content with record fields
            # Include input (the question) and knowledge
            record_content = f"问题(input): {dataset.input or ''}"
            if dataset.knowledge:
                knowledge_str = (
                    json.dumps(dataset.knowledge, ensure_ascii=False)
                    if isinstance(dataset.knowledge, (dict, list))
                    else str(dataset.knowledge)
                )
                record_content += f"\n知识体系(knowledge): {knowledge_str}"

            llm_prompt = f"{prompt_content}\n\n{record_content}"

            # Call LLM with the prompt + record content
            try:
                llm_result = await call_llm_json(
                    prompt=llm_prompt,
                    model=model,
                    temperature=0.3,
                    base_url_override=base_url_override,
                    api_key_override=api_key_override,
                )
            except LLMCallError as e:
                logger.error(
                    "Task %d: LLM call failed for record %d: %s",
                    task_id, idx, str(e),
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

            # Parse LLM response: { "validation_result": "PASS/FAIL", "reason": "..." }
            validation_result = llm_result.get("validation_result", "")
            reason = llm_result.get("reason", "")

            # Normalize validation_result (handle case variations)
            validation_result_upper = str(validation_result).upper().strip()

            if validation_result_upper == "PASS":
                # PASS: update dataset, do NOT keep validation_result/reason
                dataset.passed = "是"
                dataset.current_stage = StageEnum.QUESTION_VALIDATE
                db.commit()

                pass_count += 1
                _add_task_log(
                    db, task_id,
                    f"记录 {idx + 1}: 校验通过",
                )
            else:
                # FAIL: mark as failed, remove from main file, collect for fail file
                dataset.passed = "否"
                dataset.file_id = None  # Remove from main file
                db.commit()

                fail_count += 1

                # Build the fail record dict: serialize dataset fields + validation info
                fail_dict = serialize_dataset_to_dict(dataset)
                fail_dict["validation_result"] = validation_result
                fail_dict["reason"] = reason
                fail_records.append(fail_dict)

                _add_task_log(
                    db, task_id,
                    f"记录 {idx + 1}: 校验失败 - {reason[:100]}",
                )

            _update_progress(db, task_id, idx + 1)

        # All records processed - write back to file and create fail file
        # write_datasets_to_file() will only write datasets with file_id == file_id
        # (FAIL datasets have file_id = None, so they are excluded)
        write_datasets_to_file(db=db, file_id=file_id)
        _add_task_log(db, task_id, f"通过记录已写回文件 (file_id={file_id})")

        # Create consolidated fail file if there are any FAIL records
        if fail_records:
            source_file = db.query(File).filter(File.id == file_id).first()
            if source_file:
                fail_file = create_fail_file(
                    db=db,
                    user_id=user_id,
                    source_file=source_file,
                    stage=StageEnum.QUESTION_VALIDATE,
                    fail_records=fail_records,
                )
                _add_task_log(
                    db, task_id,
                    f"失败记录文件已生成: {fail_file.filename} (共 {len(fail_records)} 条)",
                )
                logger.info(
                    "Task %d: created fail file %s with %d records",
                    task_id, fail_file.filename, len(fail_records),
                )

        # Mark task as completed
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            db.commit()

        logger.info(
            "Task %d completed: processed %d records, %d passed, %d failed",
            task_id, total, pass_count, fail_count,
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
async def start_question_validate(
    data: QuestionValidateStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a question validation task.

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
        file_obj.file_path, "question_validate"
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_msg,
        )

    # Validate file has qualifying datasets (at knowledge_generate stage)
    qualifying_count = (
        db.query(Dataset)
        .filter(
            Dataset.file_id == data.file_id,
            Dataset.user_id == current_user.id,
            Dataset.current_stage == StageEnum.KNOWLEDGE_GENERATE,
        )
        .count()
    )
    if qualifying_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该文件中没有knowledge_generate阶段的记录",
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
    if prompt_obj.stage != StageEnum.QUESTION_VALIDATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提示词必须为question_validate阶段",
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
        stage=StageEnum.QUESTION_VALIDATE,
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
        _run_question_validate_task(
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
async def get_question_validate_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and progress of a question validation task.

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
        db.query(TaskLog)
        .filter(
            TaskLog.task_id == task_id,
            TaskLog.log_content.contains("校验通过"),
        )
        .count()
    )

    fail_count = (
        db.query(TaskLog)
        .filter(
            TaskLog.task_id == task_id,
            TaskLog.log_content.contains("校验失败"),
        )
        .count()
    )

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status.value,
        progress_current=task.progress_current or 0,
        progress_total=task.progress_total or 0,
        pass_count=pass_count,
        fail_count=fail_count,
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
async def retry_question_validate(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry a failed or completed question validation task.

    Re-queries remaining qualifying datasets (those still at
    knowledge_generate stage for the file) and processes them.
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
            Dataset.current_stage == StageEnum.KNOWLEDGE_GENERATE,
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
        _run_question_validate_task(
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