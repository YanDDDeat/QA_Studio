"""Answer Generate router - Pipeline Stage 4

Processes all Dataset records in a JSON file from the question_validate
stage (passed="是") through LLM prompts to generate answers and
reasoning chains (CoT).

Key design:
- User selects a JSON file (file_id), not individual Dataset records
- Background task queries DB for Dataset records linked to that file
  at the question_validate stage with passed="是"
- LLM prompt combines input (question) + originContent (source text)
- After completion, results are written back to the same JSON file
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
from sqlalchemy import or_
from app.models.models import (
    Dataset, File, Prompt, Task, TaskLog, TaskStatusEnum,
    StageEnum, User, LLMConfig,
)
from app.routers.auth import get_current_user
from app.services.llm_service import call_llm_json, LLMCallError
from app.services.field_mapper import apply_llm_fields_to_dataset, build_record_content
from app.services.file_service import (
    create_output_file, clone_single_dataset, write_datasets_to_file,
)
from app.services.validation_service import validate_file_fields

logger = logging.getLogger("qa_studio.answer_generate")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class AnswerGenerateStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the JSON file to process")
    prompt_id: int = Field(..., description="ID of the prompt to use")
    model: str = Field(..., description="Model name to use for LLM calls")
    llm_config_id: Optional[int] = Field(None, description="ID of the LLM config to use")
    output_filename: Optional[str] = Field(None, description="可选输出文件名 base，留空则按源文件派生")


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
# Background task runner
# ---------------------------------------------------------------------------


async def _run_answer_generate_task(
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
    """Background coroutine: 读源 question_validate(已通过) Dataset → LLM 生成 output/cot → 克隆到新输出文件。"""
    db = SessionLocal()
    try:
        source_datasets = (
            db.query(Dataset)
            .filter(
                Dataset.file_id == file_id,
                Dataset.user_id == user_id,
            )
            .order_by(Dataset.id.asc())
            .all()
        )

        total = len(source_datasets)

        task = db.query(Task).filter(Task.id == task_id).first()
        if task and start_index == 0:
            task.progress_total = total
            db.commit()

        # 提前创建输出文件，点击开始后前端立即显示输出文件名
        source_file = db.query(File).filter(File.id == file_id).first()
        output_file = create_output_file(
            db=db,
            user_id=user_id,
            source_file=source_file,
            stage=StageEnum.ANSWER_GENERATE,
            output_filename=output_filename,
            username=username,
        )
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.file_id = output_file.id
            db.commit()
        _add_task_log(db, task_id, f"输出文件已创建: {output_file.filename} (file_id={output_file.id})")

        success_count = 0
        consecutive_failures = 0

        for idx in range(start_index, total):
            dataset = source_datasets[idx]

            record_content = build_record_content(dataset, reference_fields, "answer_generate")

            if not record_content:
                logger.warning(
                    "Task %d: dataset %d has no reference content, skipping",
                    task_id, dataset.id,
                )
                _add_task_log(db, task_id, f"记录 {idx + 1}: 数据集ID {dataset.id} 无参考内容，跳过")
                _update_progress(db, task_id, idx + 1)
                continue

            llm_prompt = f"{prompt_content}\n\n---\n\n**参考内容：**\n\n{record_content}"

            # 检查任务是否被暂停
            task_check = db.query(Task).filter(Task.id == task_id).first()
            if task_check and task_check.status == TaskStatusEnum.PAUSED:
                # 暂停前将已有数据刷写到磁盘文件
                try:
                    write_datasets_to_file(db=db, file_id=output_file.id)
                    _add_task_log(db, task_id, f"任务已暂停，已将 {idx} 条数据写入文件")
                except Exception as flush_err:
                    _add_task_log(db, task_id, f"任务已暂停，刷写文件失败: {str(flush_err)[:200]}")
                return

            try:
                llm_result = await call_llm_json(
                    prompt=llm_prompt,
                    model=model,
                    temperature=0.3,
                    base_url_override=base_url_override,
                    api_key_override=api_key_override,
                    username=username,
                )
            except LLMCallError as e:
                consecutive_failures += 1
                logger.error(
                    "Task %d: LLM call failed for dataset %d: %s",
                    task_id, dataset.id, str(e),
                )
                _add_task_log(
                    db, task_id,
                    f"记录 {idx + 1}: LLM调用失败 - {str(e)[:200]}",
                )
                if consecutive_failures >= 20:
                    # 连续失败终止前将已有数据刷写到磁盘文件
                    try:
                        write_datasets_to_file(db=db, file_id=output_file.id)
                        _add_task_log(db, task_id, f"连续失败{consecutive_failures}次终止，已将已有数据写入文件")
                    except Exception as flush_err:
                        _add_task_log(db, task_id, f"连续失败{consecutive_failures}次终止，刷写文件失败: {str(flush_err)[:200]}")
                    task = db.query(Task).filter(Task.id == task_id).first()
                    if task:
                        task.status = TaskStatusEnum.FAILED
                        db.commit()
                    return
                _update_progress(db, task_id, idx + 1)
                continue

            if isinstance(llm_result, dict):
                output_text = llm_result.get("output", llm_result.get("answer", ""))
                cot_text = llm_result.get("cot", llm_result.get("reasoning", ""))
                # 立即克隆到输出文件，让前端能实时加载结果
                cloned_ds = clone_single_dataset(db, dataset, output_file.id, StageEnum.ANSWER_GENERATE)
                cloned_ds.output = output_text
                cloned_ds.cot = cot_text
                # 自动映射 LLM 返回字段到数据库列
                extra = apply_llm_fields_to_dataset(cloned_ds, llm_result)
                cloned_ds.extra_fields = extra if extra else None
                db.commit()
                success_count += 1
                consecutive_failures = 0
                _add_task_log(
                    db, task_id,
                    f"记录 {idx + 1}: 答案生成成功 (数据集ID {dataset.id})",
                )
            else:
                consecutive_failures = 0
                logger.warning(
                    "Task %d: unexpected LLM result type for dataset %d: %s",
                    task_id, dataset.id, type(llm_result).__name__,
                )
                _add_task_log(db, task_id, f"记录 {idx + 1}: LLM返回非JSON对象，跳过")

            _update_progress(db, task_id, idx + 1)

        if success_count == 0:
            _add_task_log(db, task_id, "本次任务未生成任何有效记录")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.COMPLETED
                db.commit()
            return

        write_datasets_to_file(db=db, file_id=output_file.id)
        _add_task_log(db, task_id, f"输出文件已生成: {output_file.filename} (file_id={output_file.id})")

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            task.file_id = output_file.id
            db.commit()

        logger.info(
            "Task %d completed: processed %d records, generated %d answers -> file_id=%d",
            task_id, total, success_count, output_file.id,
        )

    except Exception as e:
        logger.error(
            "Task %d unexpected error: %s\n%s",
            task_id, str(e), traceback.format_exc(),
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
async def start_answer_generate(
    data: AnswerGenerateStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start an answer generation task.

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
        file_obj.file_path, "answer_generate"
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
    if prompt_obj.stage != StageEnum.ANSWER_GENERATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提示词必须为answer_generate阶段",
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
        stage=StageEnum.ANSWER_GENERATE,
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
        _run_answer_generate_task(
            task_id=task.id,
            file_id=data.file_id,
            prompt_content=prompt_obj.content,
            model=data.model,
            user_id=current_user.id,
            username=current_user.username,
            reference_fields=prompt_obj.reference_fields,
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
async def get_answer_generate_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and progress of an answer generation task."""
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

    # 任务完成后 task.file_id 指向新输出文件；以新文件下的克隆记录数为生成数。
    generated_count = (
        db.query(Dataset)
        .filter(
            Dataset.user_id == current_user.id,
            Dataset.current_stage == StageEnum.ANSWER_GENERATE,
            Dataset.file_id == task.file_id,
        )
        .count() if task.file_id else 0
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


@router.get("/source-files")
async def list_source_files(
    show_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List JSON files for answer_generate.

    默认只返回 source_stage=question_validate 的文件；show_all=True 时返回所有 JSON。
    """
    query = db.query(File).filter(
        File.user_id == current_user.id,
        File.file_type == "json",
    )
    if not show_all:
        query = query.filter(File.source_stage == StageEnum.QUESTION_VALIDATE)
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
async def retry_answer_generate(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry a failed or completed answer generation task.

    Re-queries remaining qualifying datasets (those still at
    question_validate stage with passed="是" for the file) and
    processes them.
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
        db.query(Dataset)
        .filter(
            Dataset.file_id == task.file_id,
            Dataset.user_id == current_user.id,
            Dataset.current_stage == StageEnum.QUESTION_VALIDATE,
            Dataset.passed == "是",
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
        _run_answer_generate_task(
            task_id=task.id,
            file_id=task.file_id,
            prompt_content=prompt_obj.content,
            model=task.model,
            user_id=current_user.id,
            username=current_user.username,
            reference_fields=prompt_obj.reference_fields,
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


def resume_answer_generate_task(task: Task, db: Session):
    """Resume a paused answer_generate task from progress_current."""
    file_obj = (
        db.query(File)
        .filter(File.id == task.file_id, File.user_id == task.user_id)
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
    if prompt_obj.llm_config_id:
        llm_config_obj = db.query(LLMConfig).filter(LLMConfig.id == prompt_obj.llm_config_id).first()
        if llm_config_obj:
            base_url_override = llm_config_obj.base_url
            api_key_override = llm_config_obj.api_key

    task.status = TaskStatusEnum.RUNNING
    db.commit()

    asyncio.create_task(
        _run_answer_generate_task(
            task_id=task.id,
            file_id=file_obj.id,
            prompt_content=prompt_obj.content,
            model=task.model,
            user_id=task.user_id,
            username=username,
            reference_fields=prompt_obj.reference_fields,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            start_index=start_index,
        )
    )
