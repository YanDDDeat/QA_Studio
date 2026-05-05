"""Tasks router - CRUD + stop/resume with user data isolation"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Task, TaskStatusEnum, StageEnum, User
from app.routers.auth import get_current_user

router = APIRouter()

# ---------------------------------------------------------------------------
# Stage → resume handler dispatch table
# ---------------------------------------------------------------------------

STAGE_TO_RESUMER = {}


def _ensure_resumers_loaded():
    """Lazy-import resume handlers to avoid circular imports."""
    if STAGE_TO_RESUMER:
        return
    from app.routers.question_generate import resume_question_generate_task
    from app.routers.knowledge_generate import resume_knowledge_generate_task
    from app.routers.question_validate import resume_question_validate_task
    from app.routers.answer_generate import resume_answer_generate_task
    from app.routers.answer_validate import resume_answer_validate_task
    from app.routers.data_evaluate import resume_data_evaluate_task
    from app.routers.dataset_assessment import resume_dataset_assessment_task

    STAGE_TO_RESUMER.update({
        StageEnum.QUESTION_GENERATE: resume_question_generate_task,
        StageEnum.KNOWLEDGE_GENERATE: resume_knowledge_generate_task,
        StageEnum.QUESTION_VALIDATE: resume_question_validate_task,
        StageEnum.ANSWER_GENERATE: resume_answer_generate_task,
        StageEnum.ANSWER_VALIDATE: resume_answer_validate_task,
        StageEnum.DATA_EVALUATE: resume_data_evaluate_task,
        StageEnum.DATASET_ASSESSMENT: resume_dataset_assessment_task,
    })


# ---------- Pydantic schemas ----------


class TaskCreate(BaseModel):
    stage: str
    dataset_id: Optional[int] = None
    file_id: Optional[int] = None
    model: Optional[str] = None
    prompt_id: Optional[int] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    stage: str
    dataset_id: Optional[int] = None
    file_id: Optional[int] = None
    model: Optional[str] = None
    prompt_id: Optional[int] = None
    status: str
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------- API endpoints ----------


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    stage: Optional[str] = None,
    task_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all tasks belonging to the current user."""
    query = db.query(Task).filter(Task.user_id == current_user.id)
    if stage:
        if stage not in [s.value for s in StageEnum]:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stage: {stage}",
            )
        query = query.filter(Task.stage == StageEnum(stage))
    if task_status:
        if task_status not in [s.value for s in TaskStatusEnum]:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {task_status}",
            )
        query = query.filter(Task.status == TaskStatusEnum(task_status))
    tasks = query.order_by(Task.id.desc()).all()
    return tasks


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a task by ID (must belong to current user)."""
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
    return task


@router.post("", response_model=TaskResponse, status_code=http_status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new task for the current user."""
    if data.stage not in [s.value for s in StageEnum]:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage: {data.stage}",
        )

    task = Task(
        user_id=current_user.id,
        stage=StageEnum(data.stage),
        dataset_id=data.dataset_id,
        file_id=data.file_id,
        model=data.model,
        prompt_id=data.prompt_id,
        status=TaskStatusEnum.PENDING,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update task status/progress (must belong to current user)."""
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

    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data:
        if update_data["status"] not in [s.value for s in TaskStatusEnum]:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {update_data['status']}",
            )
        task.status = TaskStatusEnum(update_data["status"])
    if "progress_current" in update_data:
        task.progress_current = update_data["progress_current"]
    if "progress_total" in update_data:
        task.progress_total = update_data["progress_total"]
    task.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a task (must belong to current user)."""
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
    db.delete(task)
    db.commit()


# ---------- Stop / Resume endpoints ----------


@router.post("/{task_id}/stop")
async def stop_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """软停止正在运行的任务：处理完当前条后退出，已处理进度保留。"""
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="任务不存在",
        )

    if task.status != TaskStatusEnum.RUNNING:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="只能停止正在运行中的任务",
        )

    task.status = TaskStatusEnum.PAUSED
    task.updated_at = datetime.utcnow()
    db.commit()

    return {
        "task_id": task.id,
        "status": task.status.value,
        "message": "任务已标记为暂停，将在当前记录处理完成后停止",
    }


@router.post("/{task_id}/resume")
async def resume_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """恢复已暂停的任务，从 progress_current 续跑。"""
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="任务不存在",
        )

    if task.status != TaskStatusEnum.PAUSED:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="只能恢复已暂停的任务",
        )

    _ensure_resumers_loaded()
    handler = STAGE_TO_RESUMER.get(task.stage)
    if handler is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"阶段 {task.stage.value} 不支持暂停/恢复",
        )

    # 委托给对应阶段的 resume 函数（负责读取参数 + 创建后台协程）
    handler(task, db)

    return {
        "task_id": task.id,
        "status": "running",
        "message": f"任务已恢复，从第 {task.progress_current or 0} 条继续",
    }
