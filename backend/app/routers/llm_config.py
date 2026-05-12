"""LLM Config router - LLM配置中心 CRUD + 测试连接

Provides endpoints for managing LLM endpoint configurations.
Each config stores base_url, api_key, supported models, and default_model.
Configs can be global (user_id=NULL, admin-managed) or user-owned.

Permission model:
- All users can view global configs and their own configs
- Regular users can CRUD their own configs only
- Admin (username=='admin') can CRUD global configs and all configs
"""

import time
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.models.models import LLMConfig, User
from app.routers.auth import get_current_user
from app.services.llm_service import call_llm, LLMCallError

logger = logging.getLogger("qa_studio.llm_config")

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_admin(user: User) -> bool:
    """Check if the user is admin (username == 'admin')."""
    return user.username == "admin"


def _check_permission(config: LLMConfig, user: User, require_owner_or_admin: bool = True):
    """Check if user can access/modify this config.

    Args:
        config: The LLMConfig record.
        user: The current user.
        require_owner_or_admin: If True, only owner or admin can modify/delete.
                                 If False, any authenticated user can read.

    Raises:
        HTTPException 403 if permission denied.
    """
    if not require_owner_or_admin:
        # Read access: user owns it OR it's global
        if config.user_id == user.id or config.user_id is None:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此配置",
        )

    # Write access: user owns it, OR admin can modify anything
    if config.user_id == user.id:
        return
    if _is_admin(user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="无权修改此配置",
    )


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class LLMConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="配置名称")
    base_url: str = Field(..., min_length=1, max_length=512, description="API endpoint URL")
    api_key: str = Field(..., min_length=1, max_length=512, description="API key")
    proxy: Optional[str] = Field(None, max_length=512, description="代理地址，如 http://host:port")
    models: List[str] = Field(..., min_length=1, description="支持的模型名列表")
    default_model: str = Field(..., min_length=1, max_length=128, description="默认模型名")
    is_global: bool = Field(False, description="是否创建全局配置(仅admin可用)")


class LLMConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    base_url: Optional[str] = Field(None, min_length=1, max_length=512)
    api_key: Optional[str] = Field(None, min_length=1, max_length=512)
    proxy: Optional[str] = Field(None, max_length=512)
    models: Optional[List[str]] = Field(None, min_length=1)
    default_model: Optional[str] = Field(None, min_length=1, max_length=128)


class LLMConfigResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    base_url: str
    api_key: str
    proxy: Optional[str] = None
    models: List[str]
    default_model: str
    is_global: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class LLMConfigTestResponse(BaseModel):
    ok: bool
    latency_ms: Optional[float] = None
    reply: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[LLMConfigResponse])
async def list_llm_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List LLM configs visible to the current user (own + global)."""
    configs = (
        db.query(LLMConfig)
        .filter(
            (LLMConfig.user_id == current_user.id) | (LLMConfig.user_id == None)
        )
        .order_by(LLMConfig.user_id.asc(), LLMConfig.id.asc())
        .all()
    )
    return [
        LLMConfigResponse(
            id=c.id,
            user_id=c.user_id,
            name=c.name,
            base_url=c.base_url,
            api_key=c.api_key,
            proxy=c.proxy,
            models=c.models if isinstance(c.models, list) else [],
            default_model=c.default_model,
            is_global=c.user_id is None,
            created_at=c.created_at.isoformat() if c.created_at else None,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        )
        for c in configs
    ]


@router.post("", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    data: LLMConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new LLM config.

    Regular users: auto-set user_id = current user (is_global is ignored).
    Admin users: can set is_global=true to create global config (user_id=NULL).
    """
    user_id = current_user.id

    if data.is_global:
        if not _is_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只有管理员可以创建全局配置",
            )
        user_id = None

    # Validate default_model is in models list
    if data.default_model not in data.models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"默认模型 '{data.default_model}' 不在模型列表中",
        )

    config = LLMConfig(
        user_id=user_id,
        name=data.name,
        base_url=data.base_url,
        api_key=data.api_key,
        proxy=data.proxy,
        models=data.models,
        default_model=data.default_model,
    )
    db.add(config)
    db.commit()
    db.refresh(config)

    return LLMConfigResponse(
        id=config.id,
        user_id=config.user_id,
        name=config.name,
        base_url=config.base_url,
        api_key=config.api_key,
        proxy=config.proxy,
        models=config.models if isinstance(config.models, list) else [],
        default_model=config.default_model,
        is_global=config.user_id is None,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


@router.post("/{config_id}/update", response_model=LLMConfigResponse)
async def update_llm_config(
    config_id: int,
    data: LLMConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an LLM config. Permission check: owner or admin."""
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在",
        )

    _check_permission(config, current_user, require_owner_or_admin=True)

    update_data = data.model_dump(exclude_unset=True)

    # If models is being updated, validate default_model consistency
    if "models" in update_data:
        new_models = update_data["models"]
        new_default = update_data.get("default_model", config.default_model)
        if new_default not in new_models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"默认模型 '{new_default}' 不在新的模型列表中",
            )

    if "default_model" in update_data and "models" not in update_data:
        # Check against existing models list
        if update_data["default_model"] not in (config.models if isinstance(config.models, list) else []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"默认模型 '{update_data['default_model']}' 不在模型列表中",
            )

    for field, value in update_data.items():
        if hasattr(config, field):
            setattr(config, field, value)

    db.commit()
    db.refresh(config)

    return LLMConfigResponse(
        id=config.id,
        user_id=config.user_id,
        name=config.name,
        base_url=config.base_url,
        api_key=config.api_key,
        proxy=config.proxy,
        models=config.models if isinstance(config.models, list) else [],
        default_model=config.default_model,
        is_global=config.user_id is None,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


@router.post("/{config_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an LLM config. Permission check: owner or admin."""
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在",
        )

    _check_permission(config, current_user, require_owner_or_admin=True)

    db.delete(config)
    db.commit()


@router.post("/{config_id}/test", response_model=LLMConfigTestResponse)
async def test_llm_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test an LLM config by sending a short chat/completions request.

    Uses the config's base_url, api_key, and default_model to send
    messages=[{"role":"user","content":"你好"}] and reports success/failure,
    latency, and a truncated reply.
    """
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在",
        )

    # Read access: any user who can see this config can test it
    _check_permission(config, current_user, require_owner_or_admin=False)

    start_time = time.time()
    try:
        reply = await call_llm(
            prompt="你好",
            model=config.default_model,
            api_key=config.api_key,
            base_url=config.base_url,
            proxy_override=config.proxy or None,
            temperature=0.1,
            max_tokens=64,
            timeout=30.0,
        )
        latency_ms = (time.time() - start_time) * 1000

        # Truncate reply for display
        truncated_reply = reply.strip()[:200]

        return LLMConfigTestResponse(
            ok=True,
            latency_ms=round(latency_ms, 1),
            reply=truncated_reply,
            error=None,
        )
    except LLMCallError as e:
        latency_ms = (time.time() - start_time) * 1000
        return LLMConfigTestResponse(
            ok=False,
            latency_ms=round(latency_ms, 1),
            reply=None,
            error=str(e)[:500],
        )
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        err_msg = str(e)[:500]
        return LLMConfigTestResponse(
            ok=False,
            latency_ms=round(latency_ms, 1),
            reply=None,
            error=f"Unexpected error: {err_msg}",
        )