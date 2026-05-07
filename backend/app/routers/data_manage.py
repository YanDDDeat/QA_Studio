"""Data Manage router - 数据管理"""

import json
from typing import List, Optional
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Dataset, File, StageEnum, User
from app.routers.auth import get_current_user

router = APIRouter()

TRUNCATE_LEN = 80

STAGE_LABELS = {
    "question_generate": "问题生成",
    "knowledge_generate": "知识体系生成",
    "question_validate": "问题校验",
    "answer_generate": "答案生成",
    "answer_validate": "答案校验",
    "data_evaluate": "数据评估",
}


def _truncate(text: Optional[str], limit: int = TRUNCATE_LEN) -> Optional[str]:
    """Truncate text with '...' if it exceeds the character limit."""
    if text is None:
        return None
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _serialize_dataset_list(d: Dataset) -> dict:
    """Serialize a Dataset for list view with truncated text fields."""
    return {
        "id": d.id,
        "domain": _truncate(d.domain, 20),
        "category": d.category,
        "task_type": _truncate(d.task_type, 20),
        "input": _truncate(d.input),
        "output": _truncate(d.output),
        "cot": _truncate(d.cot),
        "source": _truncate(d.source, 20),
        "source_type": d.source_type,
        "current_stage": d.current_stage,
        "score": d.score,
        "passed": d.passed,
        "file_id": d.file_id,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


def _serialize_dataset_detail(d: Dataset) -> dict:
    """Serialize a Dataset for detail view with full text (no truncation)."""
    return {
        "id": d.id,
        "domain": d.domain,
        "category": d.category,
        "task_type": d.task_type,
        "input": d.input,
        "output": d.output,
        "cot": d.cot,
        "corpus_cate": d.corpus_cate,
        "scene": d.scene,
        "Assessment": d.Assessment,
        "source": d.source,
        "source_id": d.source_id,
        "source_type": d.source_type,
        "originContent": d.originContent,
        "knowledge": d.knowledge,
        "difficulty": d.difficulty,
        "relevance": d.relevance,
        "clarity": d.clarity,
        "reasoning": d.reasoning,
        "terminology": d.terminology,
        "score": d.score,
        "passed": d.passed,
        "file_id": d.file_id,
        "current_stage": d.current_stage,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


# ---------- Pydantic schemas for request bodies ----------


class DatasetUpdateRequest(BaseModel):
    """Schema for updating a dataset record."""

    domain: Optional[str] = None
    category: Optional[str] = None
    task_type: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    cot: Optional[str] = None
    corpus_cate: Optional[int] = None
    scene: Optional[str] = None
    Assessment: Optional[str] = None
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


class ExportRequest(BaseModel):
    """Schema for exporting datasets."""

    dataset_ids: Optional[List[int]] = Field(None, description="Specific dataset IDs to export")
    current_stage: Optional[str] = Field(None, description="Filter by stage")
    format: str = Field("json", description="Export format (only json supported)")


# ---------- API endpoints ----------


@router.get("")
async def list_managed_data(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    current_stage: Optional[str] = Query(None, description="Filter by stage"),
    passed: Optional[str] = Query(None, description="Filter by pass status"),
    keyword: Optional[str] = Query(None, description="Search keyword"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List managed datasets (user-scoped) with pagination and filters."""
    query = db.query(Dataset).filter(Dataset.user_id == current_user.id)

    # Apply filters
    if current_stage:
        valid_stages = [s.value for s in StageEnum]
        if current_stage not in valid_stages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid current_stage: {current_stage}",
            )
        query = query.filter(Dataset.current_stage == StageEnum(current_stage))

    if passed:
        query = query.filter(Dataset.passed == passed)

    if keyword:
        keyword_filter = f"%{keyword}%"
        query = query.filter(
            (Dataset.domain.ilike(keyword_filter))
            | (Dataset.category.ilike(keyword_filter))
            | (Dataset.task_type.ilike(keyword_filter))
            | (Dataset.input.ilike(keyword_filter))
            | (Dataset.output.ilike(keyword_filter))
            | (Dataset.cot.ilike(keyword_filter))
            | (Dataset.source.ilike(keyword_filter))
        )

    total = query.count()
    offset = (page - 1) * page_size
    datasets = query.order_by(Dataset.id.desc()).offset(offset).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_dataset_list(d) for d in datasets],
    }


@router.get("/{dataset_id}")
async def get_managed_data(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full dataset details (user-scoped, no truncation)."""
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
    return _serialize_dataset_detail(dataset)


@router.put("/{dataset_id}")
async def update_managed_data(
    dataset_id: int,
    body: DatasetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a dataset record (user-scoped). Only provided fields are updated."""
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

    update_data = body.model_dump(exclude_unset=True)

    # Handle current_stage validation if present in update
    if "current_stage" in update_data:
        stage_val = update_data.pop("current_stage")
        if stage_val is not None:
            valid_stages = [s.value for s in StageEnum]
            if stage_val not in valid_stages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid current_stage: {stage_val}",
                )
            dataset.current_stage = StageEnum(stage_val)
        else:
            dataset.current_stage = None

    for key, value in update_data.items():
        if hasattr(dataset, key):
            setattr(dataset, key, value)

    dataset.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dataset)

    return _serialize_dataset_detail(dataset)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_managed_data(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a dataset record (user-scoped)."""
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


@router.post("/export")
async def export_data(
    body: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export datasets as JSON file. Saves as a File record and returns file_id."""
    query = db.query(Dataset).filter(Dataset.user_id == current_user.id)

    # Apply filters
    if body.dataset_ids:
        query = query.filter(Dataset.id.in_(body.dataset_ids))

    if body.current_stage:
        valid_stages = [s.value for s in StageEnum]
        if body.current_stage not in valid_stages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid current_stage: {body.current_stage}",
            )
        query = query.filter(Dataset.current_stage == StageEnum(body.current_stage))

    datasets = query.order_by(Dataset.id).all()

    if not datasets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No datasets found matching the criteria",
        )

    # Serialize datasets for export (full fields, no truncation)
    export_items = [_serialize_dataset_detail(d) for d in datasets]
    json_content = json.dumps(export_items, ensure_ascii=False, indent=2, default=str)

    # Save to disk as a File record
    export_dir = os.path.join("uploads", str(current_user.id))
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"data_export_{timestamp}.json"
    file_path = os.path.join(export_dir, filename)

    # Handle duplicate filenames
    if os.path.exists(file_path):
        counter = 1
        while os.path.exists(os.path.join(export_dir, f"data_export_{timestamp}_{counter}.json")):
            counter += 1
        filename = f"data_export_{timestamp}_{counter}.json"
        file_path = os.path.join(export_dir, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(json_content)

    # Create File DB record
    file_record = File(
        user_id=current_user.id,
        filename=filename,
        file_type="json",
        file_path=file_path,
        source_stage=StageEnum.DATA_EVALUATE,
        text_field="output",
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    return {
        "file_id": file_record.id,
        "filename": file_record.filename,
        "total_records": len(datasets),
    }