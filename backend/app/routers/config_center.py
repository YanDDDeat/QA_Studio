"""Config Center router - 配置中心"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.models import Prompt, StageEnum, User, LLMConfig
from app.routers.auth import get_current_user

router = APIRouter()


# ---------- Pydantic schemas ----------


class PromptConfigCreate(BaseModel):
    stage: str
    content: str
    model: Optional[str] = None
    llm_config_id: Optional[int] = None


class PromptConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    stage: str
    version: int
    content: str
    model: Optional[str] = None
    llm_config_id: Optional[int] = None
    created_at: Optional[datetime] = None


class ModelConfigUpdate(BaseModel):
    stage: str
    model: str


class StageInfo(BaseModel):
    value: str
    label: str


# ---------- Stage display mapping ----------

STAGE_DISPLAY_NAMES = {
    "question_generate": "问题生成",
    "knowledge_generate": "知识体系生成",
    "question_validate": "问题校验",
    "answer_generate": "答案生成",
    "answer_validate": "答案校验",
    "data_evaluate": "数据评估",
}

# ---------- API endpoints ----------


@router.get("/stages", response_model=List[StageInfo])
async def list_stages():
    """Return the list of pipeline stages with Chinese display names."""
    return [
        StageInfo(value=s.value, label=STAGE_DISPLAY_NAMES.get(s.value, s.value))
        for s in StageEnum
    ]


@router.get("/prompts", response_model=List[PromptConfigResponse])
async def list_prompt_configs(
    stage: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List prompt configurations for the current user. Optionally filter by stage."""
    query = db.query(Prompt).filter(Prompt.user_id == current_user.id)
    if stage:
        if stage not in [s.value for s in StageEnum]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stage: {stage}",
            )
        query = query.filter(Prompt.stage == StageEnum(stage))
    prompts = query.order_by(Prompt.stage, Prompt.version.desc()).all()
    return prompts


@router.post("/prompts", response_model=PromptConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_config(
    data: PromptConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new prompt version for a stage. Auto-increment version number."""
    if data.stage not in [s.value for s in StageEnum]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage: {data.stage}",
        )

    # Find latest version for this stage+user to auto-increment
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
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_config(
    prompt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a prompt version by ID (must belong to current user)."""
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
    db.delete(prompt)
    db.commit()


@router.get("/models")
async def list_model_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return available LLM model configs visible to the current user.

    Returns configs from llm_configs table (user's own + global),
    each with their supported models. Falls back to settings if no
    configs exist.
    """
    configs = (
        db.query(LLMConfig)
        .filter(
            (LLMConfig.user_id == current_user.id) | (LLMConfig.user_id == None)
        )
        .order_by(LLMConfig.user_id.asc(), LLMConfig.id.asc())
        .all()
    )

    if not configs:
        # Fallback to settings if no llm_configs exist yet
        return {
            "configs": [
                {
                    "id": None,
                    "name": settings.LLM_PROVIDER,
                    "base_url": settings.effective_llm_base_url,
                    "models": settings.effective_llm_models,
                    "default_model": settings.effective_llm_model,
                    "is_global": True,
                }
            ],
        }

    return {
        "configs": [
            {
                "id": c.id,
                "name": c.name,
                "base_url": c.base_url,
                "models": c.models if isinstance(c.models, list) else [],
                "default_model": c.default_model,
                "is_global": c.user_id is None,
            }
            for c in configs
        ],
    }


@router.put("/models", response_model=PromptConfigResponse)
async def update_model_config(
    data: ModelConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the model for a specific stage by updating the latest prompt version's model field."""
    if data.stage not in [s.value for s in StageEnum]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage: {data.stage}",
        )
    if data.model not in settings.effective_llm_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model: {data.model}. Available models: {settings.effective_llm_models}",
        )

    # Find the latest prompt version for this stage
    latest = (
        db.query(Prompt)
        .filter(
            Prompt.user_id == current_user.id,
            Prompt.stage == StageEnum(data.stage),
        )
        .order_by(Prompt.version.desc())
        .first()
    )

    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No prompt found for stage '{data.stage}'. Please create a prompt first.",
        )

    latest.model = data.model
    db.commit()
    db.refresh(latest)
    return latest