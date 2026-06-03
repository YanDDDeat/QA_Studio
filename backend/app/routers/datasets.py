"""Datasets router - CRUD with user data isolation"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Dataset, StageEnum, User
from app.routers.auth import get_current_user

router = APIRouter()


# ---------- Pydantic schemas ----------


class DatasetCreate(BaseModel):
    domain: Optional[str] = None
    category: Optional[str] = None
    task_type: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    cot: Optional[str] = None
    corpus_cate: int = 1
    scene: Optional[str] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = "图书"
    originContent: Optional[str] = None


class DatasetUpdate(BaseModel):
    domain: Optional[str] = None
    category: Optional[str] = None
    task_type: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    cot: Optional[str] = None
    corpus_cate: Optional[int] = None
    scene: Optional[str] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    originContent: Optional[str] = None
    knowledge: Optional[str] = None
    difficulty: Optional[str] = None
    relevance: Optional[int] = None
    clarity: Optional[int] = None
    reasoning: Optional[int] = None
    terminology: Optional[int] = None
    score: Optional[float] = None
    passed: Optional[str] = None
    current_stage: Optional[str] = None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    domain: Optional[str] = None
    category: Optional[str] = None
    task_type: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    cot: Optional[str] = None
    corpus_cate: int
    scene: Optional[str] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    originContent: Optional[str] = None
    knowledge: Optional[str] = None
    difficulty: Optional[str] = None
    relevance: Optional[int] = None
    clarity: Optional[int] = None
    reasoning: Optional[int] = None
    terminology: Optional[int] = None
    score: Optional[float] = None
    passed: Optional[str] = None
    file_id: Optional[int] = None
    current_stage: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaginatedDatasetResponse(BaseModel):
    items: List[DatasetResponse]
    total: int
    page: int
    page_size: int


# ---------- API endpoints ----------


@router.get("", response_model=PaginatedDatasetResponse)
async def list_datasets(
    current_stage: Optional[str] = None,
    file_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List datasets belonging to the current user, with optional filters and pagination."""
    filters = [Dataset.user_id == current_user.id]
    if current_stage:
        if current_stage not in [s.value for s in StageEnum]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stage: {current_stage}",
            )
        filters.append(Dataset.current_stage == StageEnum(current_stage))
    if file_id is not None:
        filters.append(Dataset.file_id == file_id)
    total = db.query(func.count(Dataset.id)).filter(*filters).scalar()
    items = db.query(Dataset).filter(*filters).order_by(Dataset.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedDatasetResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a dataset by ID (must belong to current user)."""
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    return dataset


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    data: DatasetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new dataset for the current user."""
    dataset = Dataset(**data.model_dump(), user_id=current_user.id)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.post("/{dataset_id}/update", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: int,
    data: DatasetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a dataset (must belong to current user)."""
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(dataset, field):
            setattr(dataset, field, value)
    dataset.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(dataset)
    return dataset


@router.post("/{dataset_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a dataset (must belong to current user)."""
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    db.delete(dataset)
    db.commit()