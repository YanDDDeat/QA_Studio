"""COT Filter router - Pipeline post-processing stage

Split QA records by whether the 'cot' field is empty.
Pure local processing — no LLM calls, instant execution.

Key design:
- User selects a file and provides an output name
- Backend splits into with_cot and without_cot groups
- Creates two output JSON files, registered in File table
- Returns task_id for progress tracking (even though it's instant)
"""

import asyncio
import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, SessionLocal
from app.models.models import File, Task, TaskLog, TaskStatusEnum, StageEnum, User
from app.routers.auth import get_current_user
from app.services.cot_filter_service import run_cot_filter
from app.services.validation_service import validate_file_fields

logger = logging.getLogger("qa_studio.cot_filter")

router = APIRouter()


class CotFilterStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the JSON file to filter")
    output_name: str = Field(..., description="Base name for output files")


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    status: str
    progress_current: int
    progress_total: int
    result: Optional[dict] = None
    file_id: Optional[int] = None


def _add_task_log(db: Session, task_id: int, content: str):
    log = TaskLog(task_id=task_id, log_content=content)
    db.add(log)
    db.commit()


def _update_progress(db: Session, task_id: int, current: int):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.progress_current = current
        db.commit()


async def _run_cot_filter_task(
    task_id: int,
    file_id: int,
    output_name: str,
    user_id: int,
    username: str,
):
    """Background coroutine that runs COT filter."""
    db = SessionLocal()
    try:
        _add_task_log(db, task_id, "开始COT过滤")

        source_file = db.query(File).filter(File.id == file_id, File.user_id == user_id).first()
        if not source_file:
            _add_task_log(db, task_id, "源文件不存在")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            return

        result = run_cot_filter(
            db=db,
            user_id=user_id,
            source_file=source_file,
            output_name=output_name,
            username=username,
            task_id=task_id,
        )

        _add_task_log(db, task_id, f"COT过滤完成: 总计 {result['total']} 条, COT不为空 {result['with_cot_count']} 条, COT为空 {result['without_cot_count']} 条")

        # Mark task completed with result
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            task.progress_current = result['total']
            task.progress_total = result['total']
            db.commit()

    except Exception as e:
        logger.error("COT filter task %d failed: %s\n%s", task_id, str(e), traceback.format_exc())
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            _add_task_log(db, task_id, f"COT过滤失败: {str(e)[:200]}")
        except Exception:
            pass
    finally:
        db.close()


@router.post("/start")
async def start_cot_filter(
    data: CotFilterStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a COT filter task."""
    # Validate file exists and belongs to user
    file_obj = (
        db.query(File)
        .filter(File.id == data.file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # Validate file has required fields for this stage
    is_valid, validation_msg, validation_stats = validate_file_fields(
        file_obj.file_path, "cot_filter"
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_msg,
        )

    # Create Task record
    task = Task(
        user_id=current_user.id,
        stage=StageEnum.COT_FILTER,
        file_id=data.file_id,
        status=TaskStatusEnum.RUNNING,
        progress_current=0,
        progress_total=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Launch background task
    asyncio.create_task(
        _run_cot_filter_task(
            task_id=task.id,
            file_id=data.file_id,
            output_name=data.output_name,
            user_id=current_user.id,
            username=current_user.username,
        )
    )

    return {"task_id": task.id, "status": task.status.value}


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_cot_filter_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status of a COT filter task."""
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status.value,
        progress_current=task.progress_current or 0,
        progress_total=task.progress_total or 0,
        file_id=task.file_id,
    )


@router.get("/source-files")
async def list_source_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all JSON files available for COT filtering."""
    files = (
        db.query(File)
        .filter(File.user_id == current_user.id, File.file_type == "json")
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