"""Prompts router - CRUD with user data isolation"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Prompt, StageEnum, User
from app.routers.auth import get_current_user

router = APIRouter()


# ---------- Pydantic schemas ----------


class PromptCreate(BaseModel):
    stage: str
    content: str
    model: Optional[str] = None
    llm_config_id: Optional[int] = None
    reference_fields: Optional[List[str]] = None


class PromptUpdate(BaseModel):
    content: Optional[str] = None
    model: Optional[str] = None


class PromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    stage: str
    version: int
    content: str
    model: Optional[str] = None
    llm_config_id: Optional[int] = None
    reference_fields: Optional[List[str]] = None
    created_at: Optional[datetime] = None


# ---------- API endpoints ----------


@router.get("", response_model=List[PromptResponse])
async def list_prompts(
    stage: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all prompts belonging to the current user. Optionally filter by stage."""
    query = db.query(Prompt).filter(Prompt.user_id == current_user.id)
    if stage:
        if stage not in [s.value for s in StageEnum]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stage: {stage}",
            )
        query = query.filter(Prompt.stage == StageEnum(stage))
    prompts = query.order_by(Prompt.id.desc()).all()
    return prompts


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a prompt by ID (must belong to current user)."""
    prompt = (
        db.query(Prompt)
        .filter(Prompt.id == prompt_id, Prompt.user_id == current_user.id)
        .first()
    )
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )
    return prompt


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    data: PromptCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new prompt for the current user."""
    if data.stage not in [s.value for s in StageEnum]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage: {data.stage}",
        )

    # Determine version - find latest version for this stage+user
    latest = (
        db.query(Prompt)
        .filter(
            Prompt.user_id == current_user.id,
            Prompt.stage == StageEnum(data.stage),
        )
        .order_by(Prompt.version.desc())
        .first()
    )
    version = (latest.version + 1) if latest else 1

    prompt = Prompt(
        user_id=current_user.id,
        stage=StageEnum(data.stage),
        version=version,
        content=data.content,
        model=data.model,
        llm_config_id=data.llm_config_id,
        reference_fields=data.reference_fields,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.post("/{prompt_id}/update", response_model=PromptResponse)
async def update_prompt(
    prompt_id: int,
    data: PromptUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a prompt (must belong to current user)."""
    prompt = (
        db.query(Prompt)
        .filter(Prompt.id == prompt_id, Prompt.user_id == current_user.id)
        .first()
    )
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(prompt, field):
            setattr(prompt, field, value)

    db.commit()
    db.refresh(prompt)
    return prompt