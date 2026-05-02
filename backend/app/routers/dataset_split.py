"""Dataset Split router - Pipeline post-processing stage

Split QA records into train/test sets by strategy.
Pure local processing — no LLM calls, instant execution.

Key design:
- User selects a file, specifies test_count, output_name, and split_strategy
- Backend splits items and creates train/test output files
- Returns task_id for progress tracking
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
from app.services.split_service import run_dataset_split, SPLIT_STRATEGIES
from app.services.validation_service import validate_file_fields

logger = logging.getLogger("qa_studio.dataset_split")

router = APIRouter()


class DatasetSplitStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the JSON file to split")
    test_count: int = Field(..., description="Number of items for the test set", ge=5)
    output_name: str = Field(..., description="Base name for output files")
    split_strategy: str = Field("difficulty_priority", description="Split strategy: difficulty_priority or task_type_random")


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


async def _run_dataset_split_task(
    task_id: int,
    file_id: int,
    test_count: int,
    output_name: str,
    split_strategy: str,
    user_id: int,
    username: str,
):
    """Background coroutine that runs dataset split."""
    db = SessionLocal()
    try:
        _add_task_log(db, task_id, f"开始数据集切分: 策略={split_strategy}, 测试集数量={test_count}")

        source_file = db.query(File).filter(File.id == file_id, File.user_id == user_id).first()
        if not source_file:
            _add_task_log(db, task_id, "源文件不存在")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            return

        try:
            result = run_dataset_split(
                db=db,
                user_id=user_id,
                source_file=source_file,
                output_name=output_name,
                username=username,
                test_count=test_count,
                split_strategy=split_strategy,
            )
        except ValueError as e:
            _add_task_log(db, task_id, f"切分失败: {str(e)}")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            return

        _add_task_log(db, task_id, f"切分完成: 测试集 {result['test_count']} 条, 训练集 {result['train_count']} 条, 跳过非QA {result['skipped_non_qa']} 条 | 测试集题型: {result['test_task_counts']} | 训练集题型: {result['train_task_counts']}")

        # Mark task completed
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            task.progress_current = result['test_count'] + result['train_count']
            task.progress_total = result['test_count'] + result['train_count']
            db.commit()

    except Exception as e:
        logger.error("Dataset split task %d failed: %s\n%s", task_id, str(e), traceback.format_exc())
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            _add_task_log(db, task_id, f"切分失败: {str(e)[:200]}")
        except Exception:
            pass
    finally:
        db.close()


@router.post("/start")
async def start_dataset_split(
    data: DatasetSplitStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a dataset split task."""
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
        file_obj.file_path, "dataset_split"
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_msg,
        )

    # Validate split strategy
    if data.split_strategy not in SPLIT_STRATEGIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid split strategy: {data.split_strategy}. Must be one of {SPLIT_STRATEGIES}",
        )

    # Create Task record
    task = Task(
        user_id=current_user.id,
        stage=StageEnum.DATASET_SPLIT,
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
        _run_dataset_split_task(
            task_id=task.id,
            file_id=data.file_id,
            test_count=data.test_count,
            output_name=data.output_name,
            split_strategy=data.split_strategy,
            user_id=current_user.id,
            username=current_user.username,
        )
    )

    return {"task_id": task.id, "status": task.status.value}


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_dataset_split_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status of a dataset split task."""
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
    """List all JSON files available for dataset splitting."""
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