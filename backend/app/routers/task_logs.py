"""Task logs router - view task logs with pagination and task listing"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import TaskLog, Task, TaskStatusEnum, StageEnum, User
from app.routers.auth import get_current_user

router = APIRouter()


# ---------- Pydantic schemas ----------


class TaskLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    log_content: Optional[str] = None
    created_at: Optional[datetime] = None


class TaskListItem(BaseModel):
    id: int
    stage: str
    status: str
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------- API endpoints ----------


@router.get("/tasks", response_model=List[TaskListItem])
async def list_user_tasks(
    stage: Optional[str] = Query(None, description="Filter by pipeline stage"),
    task_status: Optional[str] = Query(None, alias="status", description="Filter by task status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all tasks for the current user with their latest status."""
    query = db.query(Task).filter(Task.user_id == current_user.id)

    if stage is not None:
        if stage not in [s.value for s in StageEnum]:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stage: {stage}",
            )
        query = query.filter(Task.stage == StageEnum(stage))

    if task_status is not None:
        if task_status not in [s.value for s in TaskStatusEnum]:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {task_status}",
            )
        query = query.filter(Task.status == TaskStatusEnum(task_status))

    tasks = query.order_by(Task.updated_at.desc()).all()
    return tasks


@router.get("/{task_id}", response_model=List[TaskLogResponse])
async def get_task_logs(
    task_id: int,
    limit: int = Query(200, ge=1, le=200, description="Max logs to return (max 200)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get logs for a specific task (must belong to current user).

    Returns up to 200 log entries ordered by created_at DESC (newest first).
    """
    # Verify the task belongs to the current user
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    logs = (
        db.query(TaskLog)
        .filter(TaskLog.task_id == task_id)
        .order_by(TaskLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return logs