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
from typing import List, Optional

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
    create_output_file, clone_single_dataset,
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


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


async def _run_question_validate_task(
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
    """Background coroutine: 校验源 Dataset → PASS 克隆到新输出文件 + FAIL 单独成 fail file。

    原 file_id 下的 Dataset 与磁盘文件保持不变。
    """
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
            stage=StageEnum.QUESTION_VALIDATE,
            output_filename=output_filename,
            username=username,
        )
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.file_id = output_file.id
            db.commit()

        fail_records: list[dict] = []
        pass_count = 0
        fail_count = 0
        consecutive_failures = 0

        for idx in range(start_index, total):
            dataset = source_datasets[idx]

            record_content = build_record_content(dataset, reference_fields, "question_validate")
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
                    "Task %d: LLM call failed for record %d: %s",
                    task_id, idx, str(e),
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

            validation_result = llm_result.get("validation_result", "")
            reason = llm_result.get("reason", "")
            validation_result_upper = str(validation_result).upper().strip()

            if validation_result_upper == "PASS":
                # 立即克隆到输出文件，让前端能实时加载结果
                cloned_ds = clone_single_dataset(db, dataset, output_file.id, StageEnum.QUESTION_VALIDATE)
                cloned_ds.passed = "是"
                # 自动映射 LLM 返回字段到数据库列
                extra = apply_llm_fields_to_dataset(cloned_ds, llm_result)
                cloned_ds.extra_fields = extra if extra else None
                db.commit()
                pass_count += 1
                _add_task_log(db, task_id, f"记录 {idx + 1}: 校验通过")
            else:
                fail_dict = serialize_dataset_to_dict(dataset)
                fail_dict["passed"] = "否"
                fail_dict["validation_result"] = validation_result
                fail_dict["reason"] = reason
                fail_records.append(fail_dict)
                fail_count += 1
                _add_task_log(db, task_id, f"记录 {idx + 1}: 校验失败 - {reason[:100]}")

            consecutive_failures = 0
            _update_progress(db, task_id, idx + 1)

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
                stage=StageEnum.QUESTION_VALIDATE,
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
        progress_total=0,
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
        filename=db.query(File).filter(File.id == task.file_id).first().filename if task.file_id else None,
    )


@router.get("/source-files")
async def list_source_files(
    show_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List JSON files for question_validate.

    默认只返回 source_stage=knowledge_generate 的文件；show_all=True 时返回所有 JSON。
    """
    query = db.query(File).filter(
        File.user_id == current_user.id,
        File.file_type == "json",
    )
    if not show_all:
        query = query.filter(File.source_stage == StageEnum.KNOWLEDGE_GENERATE)
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
            username=current_user.username,
            reference_fields=data.reference_fields or prompt_obj.reference_fields,
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


def resume_question_validate_task(task: Task, db: Session):
    """Resume a paused question_validate task from progress_current."""
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
        _run_question_validate_task(
            task_id=task.id,
            file_id=file_obj.id,
            prompt_content=prompt_obj.content,
            model=task.model,
            user_id=task.user_id,
            username=username,
            reference_fields=data.reference_fields or prompt_obj.reference_fields,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            start_index=start_index,
        )
    )
