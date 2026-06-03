"""CoT/H-CoT Pipeline router

Manages the multi-step workflow for CoT/H-CoT data generation.
Each workflow is a parent Task (stage=COT_HCOT_PIPELINE) with sub-tasks
linked via parent_task_id.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import (
    Task, TaskStatusEnum, StageEnum, User, File, Prompt, LLMConfig,
)
from app.routers.auth import get_current_user
from app.services.cot_hcot_service import (
    run_pipeline_step_bg,
    run_export_jsonl_bg,
    run_pipeline_auto_bg,
    find_prompt_for_step,
    get_workflow_status,
    list_workflows,
    get_step_order,
    get_next_step,
    PIPELINE_STEPS,
    _run_merge_step_in_thread,
)
from app.services.hcot_prompt_template_service import (
    list_templates as list_hcot_templates,
    get_template_detail as get_hcot_template_detail,
    get_prompt_item as get_hcot_prompt_item,
    update_prompt_item as update_hcot_prompt_item,
    restore_prompt_item_default as restore_hcot_prompt_default,
    duplicate_template as duplicate_hcot_template,
    rename_template as rename_hcot_template,
    set_default_template as set_hcot_default_template,
    delete_template as delete_hcot_template,
    PromptTemplateError,
)

logger = logging.getLogger("qa_studio.cothcot_pipeline")

router = APIRouter()


async def _run_merge_step_async_wrapper(
    sub_task_id: int,
    parent_task_id: int,
    user_id: int,
    username: str,
):
    """Async wrapper for _run_merge_step_in_thread to use with asyncio.create_task."""
    await asyncio.to_thread(
        _run_merge_step_in_thread,
        sub_task_id=sub_task_id,
        parent_task_id=parent_task_id,
        user_id=user_id,
        username=username,
    )


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class PipelineStartRequest(BaseModel):
    source_file_id: int = Field(..., description="ID of the source file (paper content)")
    pipeline_mode: str = Field(..., description="Mode: 'hcot' or 'cot'")
    llm_config_id: int = Field(..., description="ID of the LLM config to use")
    pipeline_name: str = Field(..., description="User-defined name for this pipeline task")
    prompt_template_id: Optional[str] = Field(None, description="ID of the H-CoT prompt template to use")


class PipelineStepRequest(BaseModel):
    parent_task_id: int = Field(..., description="ID of the main pipeline task")
    step_name: str = Field(..., description="Name of the step to run (e.g., 'sanitize', 'l0_gen')")
    prompt_id: Optional[int] = Field(None, description="Optional: override prompt ID for this step")
    l0_question_index: Optional[int] = Field(None, description="L0 总问题序号，per-L0 步骤必须传入")


class HcotTemplateNameRequest(BaseModel):
    name: str = Field(..., description="New template name")


class HcotPromptContentRequest(BaseModel):
    content: str = Field(..., description="Prompt content text")


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline(
    request: PipelineStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new CoT/H-CoT generation pipeline.

    Creates a parent task and immediately triggers the first step (fact_card_gen).
    """
    # Validate source file
    source_file = db.query(File).filter(
        File.id == request.source_file_id,
        File.user_id == current_user.id,
    ).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="源文件不存在")

    # Validate LLM config
    llm_config = db.query(LLMConfig).filter(
        LLMConfig.id == request.llm_config_id,
        or_(LLMConfig.user_id == current_user.id, LLMConfig.user_id.is_(None)),
    ).first()
    if not llm_config:
        raise HTTPException(status_code=404, detail="LLM配置不存在")

    # Validate pipeline mode
    if request.pipeline_mode not in ("hcot", "cot"):
        raise HTTPException(status_code=400, detail="pipeline_mode 必须为 'hcot' 或 'cot'")

    model = llm_config.default_model

    # Create parent task
    parent_task = Task(
        user_id=current_user.id,
        stage=StageEnum.COT_HCOT_PIPELINE,
        status=TaskStatusEnum.RUNNING,
        model=model,
        source_file_id=request.source_file_id,
        pipeline_mode=request.pipeline_mode,
        pipeline_name=request.pipeline_name,
        prompt_template_id=request.prompt_template_id,
    )
    db.add(parent_task)
    db.commit()
    db.refresh(parent_task)

    # Resolve LLM config overrides for background task
    base_url_override = llm_config.base_url
    api_key_override = llm_config.api_key

    # Find the first step's prompt
    first_step = get_step_order(request.pipeline_mode)[0]  # always "fact_card_gen"
    prompt_obj = find_prompt_for_step(db, first_step, current_user.id, request.prompt_template_id)
    if not prompt_obj:
        raise HTTPException(
            status_code=404,
            detail=f"找不到步骤 '{first_step}' 的默认提示词，请先运行迁移脚本 migrate_cothcot_prompts.py",
        )

    # Create sub-task for first step
    sub_task = Task(
        user_id=current_user.id,
        stage=StageEnum.COT_HCOT_PIPELINE,
        status=TaskStatusEnum.RUNNING,
        model=model,
        prompt_id=prompt_obj.id,
        source_file_id=request.source_file_id,
        parent_task_id=parent_task.id,
        step_name=first_step,
    )
    db.add(sub_task)
    db.commit()
    db.refresh(sub_task)

    # Launch background task for the first step
    asyncio.create_task(
        run_pipeline_step_bg(
            sub_task_id=sub_task.id,
            step_name=first_step,
            prompt_content=prompt_obj.content,
            input_file_id=request.source_file_id,
            model=model,
            user_id=current_user.id,
            username=current_user.username,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            parent_task_id=parent_task.id,
        )
    )

    logger.info(
        f"User {current_user.username} started pipeline {parent_task.id} "
        f"mode={request.pipeline_mode}, first_step_task={sub_task.id}"
    )

    return {
        "parent_task_id": parent_task.id,
        "pipeline_mode": request.pipeline_mode,
        "pipeline_name": request.pipeline_name,
        "first_step": first_step,
        "sub_task_id": sub_task.id,
        "status": "running",
    }


@router.post("/run-step", status_code=status.HTTP_202_ACCEPTED)
async def run_pipeline_step_endpoint(
    request: PipelineStepRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run a specific step in the pipeline.

    The step must be the next one in sequence (previous step must be completed).
    For LLM steps: creates sub-task and launches background coroutine.
    For export_jsonl: creates sub-task and launches pure data synthesis.
    """
    # Validate parent task
    parent_task = db.query(Task).filter(
        Task.id == request.parent_task_id,
        Task.user_id == current_user.id,
        Task.stage == StageEnum.COT_HCOT_PIPELINE,
    ).first()
    if not parent_task:
        raise HTTPException(status_code=404, detail="父流水线任务不存在")

    mode = parent_task.pipeline_mode or "hcot"
    step_name = request.step_name

    # Validate step name
    if step_name not in PIPELINE_STEPS:
        raise HTTPException(status_code=400, detail=f"未知步骤: {step_name}")

    step_order = get_step_order(mode)
    if step_name not in step_order:
        raise HTTPException(status_code=400, detail=f"步骤 '{step_name}' 不属于 {mode} 模式")

    # Check if this step is already running — for per-L0 steps, filter by l0_question_index
    if request.l0_question_index is not None:
        existing_sub = db.query(Task).filter(
            Task.parent_task_id == request.parent_task_id,
            Task.step_name == step_name,
            Task.l0_question_index == request.l0_question_index,
            Task.status == TaskStatusEnum.RUNNING,
        ).first()
    else:
        existing_sub = db.query(Task).filter(
            Task.parent_task_id == request.parent_task_id,
            Task.step_name == step_name,
            Task.l0_question_index.is_(None),
            Task.status == TaskStatusEnum.RUNNING,
        ).first()
    if existing_sub:
        raise HTTPException(status_code=400, detail=f"步骤 '{step_name}' 正在运行中")

    # Check if this step is already completed (allow retry by marking old sub-task as failed)
    if request.l0_question_index is not None:
        existing_completed = db.query(Task).filter(
            Task.parent_task_id == request.parent_task_id,
            Task.step_name == step_name,
            Task.l0_question_index == request.l0_question_index,
            Task.status == TaskStatusEnum.COMPLETED,
        ).first()
    else:
        existing_completed = db.query(Task).filter(
            Task.parent_task_id == request.parent_task_id,
            Task.step_name == step_name,
            Task.l0_question_index.is_(None),
            Task.status == TaskStatusEnum.COMPLETED,
        ).first()
    if existing_completed:
        existing_completed.status = TaskStatusEnum.FAILED
        db.commit()

    # For steps that need multiple inputs, validate that ALL required prior steps
    # are completed (not just the immediately previous one)
    step_meta = PIPELINE_STEPS.get(step_name)
    _, prompt_pattern, input_sources, _, granularity = step_meta

    # Per-L0 steps must have l0_question_index
    if granularity == "per_l0" and request.l0_question_index is None:
        raise HTTPException(
            status_code=400,
            detail=f"步骤 '{step_name}' 是 per-L0 步骤，必须传入 l0_question_index",
        )

    if input_sources:
        for placeholder, source_step in input_sources.items():
            if source_step is not None:
                source_sub = db.query(Task).filter(
                    Task.parent_task_id == request.parent_task_id,
                    Task.step_name == source_step,
                    Task.status == TaskStatusEnum.COMPLETED,
                ).first()
                if not source_sub:
                    raise HTTPException(
                        status_code=400,
                        detail=f"步骤 '{step_name}' 需要前置步骤 '{source_step}' 已完成（输入 '{placeholder}'）",
                    )

    # Special handling for export_jsonl (no LLM needed)
    if step_name == "export_jsonl":
        # Validate that quality_check is completed
        qc_sub = db.query(Task).filter(
            Task.parent_task_id == request.parent_task_id,
            Task.step_name == "quality_check",
            Task.status == TaskStatusEnum.COMPLETED,
        ).first()
        if not qc_sub:
            raise HTTPException(status_code=400, detail="导出训练数据需要质检步骤已完成")

        sub_task = Task(
            user_id=current_user.id,
            stage=StageEnum.COT_HCOT_PIPELINE,
            status=TaskStatusEnum.RUNNING,
            model=parent_task.model,
            source_file_id=parent_task.source_file_id,
            parent_task_id=parent_task.id,
            step_name=step_name,
        )
        db.add(sub_task)
        db.commit()
        db.refresh(sub_task)

        parent_task.status = TaskStatusEnum.RUNNING
        db.commit()

        asyncio.create_task(
            run_export_jsonl_bg(
                sub_task_id=sub_task.id,
                step_name=step_name,
                input_file_id=parent_task.source_file_id,
                model=parent_task.model,
                user_id=current_user.id,
                username=current_user.username,
                parent_task_id=parent_task.id,
            )
        )

        logger.info(
            f"User {current_user.username} triggered export_jsonl "
            f"for pipeline {request.parent_task_id}, sub_task={sub_task.id}"
        )

        return {
            "sub_task_id": sub_task.id,
            "step_name": step_name,
            "step_display": "导出训练数据",
            "input_file_id": parent_task.source_file_id,
            "status": "running",
        }

    # Special handling for merge_fact_cards (no LLM needed)
    if step_name == "merge_fact_cards":
        # Validate that all fact_card_gen sub-tasks are completed
        completed_fc_count = db.query(Task).filter(
            Task.parent_task_id == request.parent_task_id,
            Task.step_name == "fact_card_gen",
            Task.status == TaskStatusEnum.COMPLETED,
        ).count()
        total_fc = db.query(Task).filter(
            Task.parent_task_id == request.parent_task_id,
            Task.step_name == "fact_card_gen",
        ).count()
        if completed_fc_count == 0:
            raise HTTPException(status_code=400, detail="合并事实卡需要至少一个事实卡生成步骤已完成")

        sub_task = Task(
            user_id=current_user.id,
            stage=StageEnum.COT_HCOT_PIPELINE,
            status=TaskStatusEnum.RUNNING,
            model=parent_task.model,
            source_file_id=parent_task.source_file_id,
            parent_task_id=parent_task.id,
            step_name=step_name,
            l0_question_index=request.l0_question_index,
        )
        db.add(sub_task)
        db.commit()
        db.refresh(sub_task)

        parent_task.status = TaskStatusEnum.RUNNING
        db.commit()

        asyncio.create_task(
            _run_merge_step_async_wrapper(
                sub_task_id=sub_task.id,
                parent_task_id=parent_task.id,
                user_id=current_user.id,
                username=current_user.username,
            )
        )

        logger.info(
            f"User {current_user.username} triggered merge_fact_cards "
            f"for pipeline {request.parent_task_id}, sub_task={sub_task.id}"
        )

        return {
            "sub_task_id": sub_task.id,
            "step_name": step_name,
            "step_display": "2. 合并事实卡",
            "input_file_id": parent_task.source_file_id,
            "status": "running",
        }

    # --- LLM step handling ---
    # Resolve prompt
    if request.prompt_id:
        prompt_obj = db.query(Prompt).filter(
            Prompt.id == request.prompt_id,
            or_(Prompt.user_id == current_user.id, Prompt.user_id.is_(None)),
        ).first()
        if not prompt_obj:
            raise HTTPException(status_code=404, detail="指定的提示词不存在")
    else:
        prompt_obj = find_prompt_for_step(db, step_name, current_user.id)
        if not prompt_obj:
            raise HTTPException(
                status_code=404,
                detail=f"找不到步骤 '{step_name}' 的默认提示词",
            )

    # Determine the "primary" input file for the sub-task's source_file_id field
    # (the background runner will use _assemble_step_inputs to get all inputs)
    if input_sources:
        # Use the first input source's output file as the primary source_file_id
        first_source_step = next(iter(input_sources.values()))
        if first_source_step is None:
            input_file_id = parent_task.source_file_id
        else:
            # For per-L0 steps, find source output with matching l0_question_index
            source_granularity = PIPELINE_STEPS.get(first_source_step, ("", "", None, False, "document"))[4]
            if source_granularity == "per_l0" and request.l0_question_index is not None:
                source_sub = db.query(Task).filter(
                    Task.parent_task_id == request.parent_task_id,
                    Task.step_name == first_source_step,
                    Task.l0_question_index == request.l0_question_index,
                    Task.status == TaskStatusEnum.COMPLETED,
                ).first()
            else:
                source_sub = db.query(Task).filter(
                    Task.parent_task_id == request.parent_task_id,
                    Task.step_name == first_source_step,
                    Task.status == TaskStatusEnum.COMPLETED,
                ).first()
            if source_sub and source_sub.file_id:
                input_file_id = source_sub.file_id
            else:
                input_file_id = parent_task.source_file_id
    else:
        # Fallback for steps with no input_sources defined
        step_idx = step_order.index(step_name)
        if step_idx == 0:
            input_file_id = parent_task.source_file_id
        else:
            prev_step = step_order[step_idx - 1]
            if granularity == "per_l0" and request.l0_question_index is not None:
                prev_sub = db.query(Task).filter(
                    Task.parent_task_id == request.parent_task_id,
                    Task.step_name == prev_step,
                    Task.l0_question_index == request.l0_question_index,
                    Task.status == TaskStatusEnum.COMPLETED,
                ).first()
            else:
                prev_sub = db.query(Task).filter(
                    Task.parent_task_id == request.parent_task_id,
                    Task.step_name == prev_step,
                    Task.status == TaskStatusEnum.COMPLETED,
                ).first()
            input_file_id = prev_sub.file_id if prev_sub and prev_sub.file_id else parent_task.source_file_id

    # Resolve LLM config
    llm_config = None
    base_url_override = None
    api_key_override = None
    if prompt_obj.llm_config_id:
        llm_config = db.query(LLMConfig).filter(LLMConfig.id == prompt_obj.llm_config_id).first()
    if not llm_config and parent_task.model:
        llm_config = db.query(LLMConfig).filter(
            or_(LLMConfig.user_id == current_user.id, LLMConfig.user_id.is_(None)),
            LLMConfig.default_model == parent_task.model,
        ).first()

    if llm_config:
        base_url_override = llm_config.base_url
        api_key_override = llm_config.api_key

    model = parent_task.model or (llm_config.default_model if llm_config else "qwen-max")

    # Create sub-task
    sub_task = Task(
        user_id=current_user.id,
        stage=StageEnum.COT_HCOT_PIPELINE,
        status=TaskStatusEnum.RUNNING,
        model=model,
        prompt_id=prompt_obj.id,
        source_file_id=input_file_id,
        parent_task_id=parent_task.id,
        step_name=step_name,
        l0_question_index=request.l0_question_index,
    )
    db.add(sub_task)
    db.commit()
    db.refresh(sub_task)

    # Update parent status to running
    parent_task.status = TaskStatusEnum.RUNNING
    db.commit()

    # Launch background task
    asyncio.create_task(
        run_pipeline_step_bg(
            sub_task_id=sub_task.id,
            step_name=step_name,
            prompt_content=prompt_obj.content,
            input_file_id=input_file_id,
            model=model,
            user_id=current_user.id,
            username=current_user.username,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            parent_task_id=parent_task.id,
        )
    )

    step_display = PIPELINE_STEPS.get(step_name, (step_name,))[0]
    logger.info(
        f"User {current_user.username} triggered step '{step_name}' "
        f"for pipeline {request.parent_task_id}, sub_task={sub_task.id}"
    )

    return {
        "sub_task_id": sub_task.id,
        "step_name": step_name,
        "step_display": step_display,
        "input_file_id": input_file_id,
        "status": "running",
    }


@router.get("/workflows")
async def list_all_workflows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all CoT/H-CoT pipeline tasks for the current user."""
    return list_workflows(db, current_user.id)


@router.get("/workflow/{task_id}")
async def get_workflow_detail(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed status of a specific pipeline, including all sub-task steps."""
    result = get_workflow_status(db, task_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="流水线任务不存在")
    return result


@router.get("/steps/{mode}")
async def get_pipeline_steps(
    mode: str,
    current_user: User = Depends(get_current_user),
):
    """Return the ordered step list for a given pipeline mode."""
    if mode not in ("hcot", "cot"):
        raise HTTPException(status_code=400, detail="mode 必须为 'hcot' 或 'cot'")

    step_order = get_step_order(mode)
    steps = []
    for s in step_order:
        display, prompt_pattern, input_sources, is_hcot_only, granularity = PIPELINE_STEPS.get(s, (s, "", None, False, "document"))
        steps.append({
            "step_name": s,
            "display_name": display,
            "is_hcot_only": is_hcot_only,
            "granularity": granularity,
            "needs_llm": prompt_pattern is not None,
        })
    return {"mode": mode, "steps": steps}


@router.get("/source-files")
async def list_source_files(
    show_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List files that can be used as source input for a pipeline.

    默认只返回用户上传的源文件（source_stage is NULL），避免 CoT/H-CoT
    中间产物和最终导出文件混入“新建流水线”的源文件列表。
    show_all=True 时才返回全部文件，便于后续需要调试时使用。
    """
    query = db.query(File).filter(File.user_id == current_user.id)
    if not show_all:
        query = query.filter(File.source_stage.is_(None))

    files = query.order_by(File.created_at.desc()).all()

    return [
        {
            "id": f.id,
            "filename": f.filename,
            "file_type": f.file_type,
            "source_stage": f.source_stage.value if f.source_stage else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


@router.get("/prompts/{mode}")
async def get_pipeline_prompts(
    mode: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the prompts available for each step in the given pipeline mode."""
    if mode not in ("hcot", "cot"):
        raise HTTPException(status_code=400, detail="mode 必须为 'hcot' 或 'cot'")

    step_order = get_step_order(mode)
    result = []
    for step_name in step_order:
        prompt_obj = find_prompt_for_step(db, step_name, current_user.id)
        display, prompt_pattern, input_sources, is_hcot_only, granularity = PIPELINE_STEPS.get(
            step_name, (step_name, "", None, False, "document")
        )
        result.append({
            "step_name": step_name,
            "display_name": display,
            "is_hcot_only": is_hcot_only,
            "granularity": granularity,
            "prompt_id": prompt_obj.id if prompt_obj else None,
            "prompt_name": prompt_obj.name if prompt_obj else None,
            "needs_llm": prompt_pattern is not None,
            "input_sources": input_sources,
        })
    return result


# ---------------------------------------------------------------------------
# Auto-run & Auto-continue endpoints
# ---------------------------------------------------------------------------

@router.post("/auto-run", status_code=status.HTTP_202_ACCEPTED)
async def auto_run_pipeline(
    request: PipelineStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """一键创建并链式执行整个 CoT/H-CoT 流水线。

    创建父任务后，后台自动按步骤顺序链式执行全部步骤，
    无需用户手动逐步触发。
    """
    # Validate source file
    source_file = db.query(File).filter(
        File.id == request.source_file_id,
        File.user_id == current_user.id,
    ).first()
    if not source_file:
        raise HTTPException(status_code=404, detail="源文件不存在")

    # Validate LLM config
    llm_config = db.query(LLMConfig).filter(
        LLMConfig.id == request.llm_config_id,
        or_(LLMConfig.user_id == current_user.id, LLMConfig.user_id.is_(None)),
    ).first()
    if not llm_config:
        raise HTTPException(status_code=404, detail="LLM配置不存在")

    # Validate pipeline mode
    if request.pipeline_mode not in ("hcot", "cot"):
        raise HTTPException(status_code=400, detail="pipeline_mode 必须为 'hcot' 或 'cot'")

    # Validate that prompts exist for ALL steps
    step_order = get_step_order(request.pipeline_mode)
    for step_name in step_order:
        _, prompt_pattern, _, _, _ = PIPELINE_STEPS.get(step_name, (step_name, "", None, False, "document"))
        if prompt_pattern is not None and step_name != "export_jsonl":
            prompt_obj = find_prompt_for_step(db, step_name, current_user.id)
            if not prompt_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"找不到步骤 '{step_name}' 的默认提示词，无法一键运行",
                )

    model = llm_config.default_model
    base_url_override = llm_config.base_url
    api_key_override = llm_config.api_key

    # Create parent task
    parent_task = Task(
        user_id=current_user.id,
        stage=StageEnum.COT_HCOT_PIPELINE,
        status=TaskStatusEnum.RUNNING,
        model=model,
        source_file_id=request.source_file_id,
        pipeline_mode=request.pipeline_mode,
        pipeline_name=request.pipeline_name,
        progress_label="链式执行启动中...",
    )
    db.add(parent_task)
    db.commit()
    db.refresh(parent_task)

    # Launch auto-run background coroutine
    asyncio.create_task(
        run_pipeline_auto_bg(
            parent_task_id=parent_task.id,
            mode=request.pipeline_mode,
            model=model,
            user_id=current_user.id,
            username=current_user.username,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            source_file_id=request.source_file_id,
            prompt_template_id=request.prompt_template_id,
        )
    )

    logger.info(
        f"User {current_user.username} auto-started pipeline {parent_task.id} "
        f"mode={request.pipeline_mode}"
    )

    return {
        "parent_task_id": parent_task.id,
        "pipeline_mode": request.pipeline_mode,
        "pipeline_name": request.pipeline_name,
        "total_steps": len(step_order),
        "status": "running",
        "message": "一键链式执行已启动，请前往详情页查看实时进度",
    }


@router.post("/auto-continue/{task_id}", status_code=status.HTTP_202_ACCEPTED)
async def auto_continue_pipeline(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从当前进度继续一键运行剩余步骤。

    跳过已完成的步骤，从第一个未完成的步骤开始链式执行到结尾。
    适用于用户手动跑了几步后想自动跑完的场景。
    """
    # Validate parent task
    parent_task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id,
        Task.stage == StageEnum.COT_HCOT_PIPELINE,
    ).first()
    if not parent_task:
        raise HTTPException(status_code=404, detail="流水线任务不存在")

    # Check no steps currently running
    running_sub = db.query(Task).filter(
        Task.parent_task_id == task_id,
        Task.status == TaskStatusEnum.RUNNING,
    ).first()
    if running_sub:
        raise HTTPException(status_code=400, detail="有步骤正在运行中，请等待完成后再继续")

    mode = parent_task.pipeline_mode or "hcot"
    step_order = get_step_order(mode)

    # Check if already all completed
    completed_subs = db.query(Task).filter(
        Task.parent_task_id == task_id,
        Task.status == TaskStatusEnum.COMPLETED,
    ).all()
    completed_step_names = {s.step_name for s in completed_subs if s.step_name}
    if len(completed_step_names) == len(step_order):
        raise HTTPException(status_code=400, detail="所有步骤已完成，无需继续")

    # Validate that prompts exist for remaining LLM steps
    for step_name in step_order:
        if step_name in completed_step_names:
            continue
        _, prompt_pattern, _, _, _ = PIPELINE_STEPS.get(step_name, (step_name, "", None, False, "document"))
        if prompt_pattern is not None and step_name != "export_jsonl":
            prompt_obj = find_prompt_for_step(db, step_name, current_user.id)
            if not prompt_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"找不到步骤 '{step_name}' 的默认提示词，无法继续运行",
                )

    # Resolve LLM config
    llm_config = None
    base_url_override = None
    api_key_override = None
    # Find LLM config from any existing sub-task's prompt, or from a matching config
    existing_prompted = db.query(Task).filter(
        Task.parent_task_id == task_id,
        Task.prompt_id.isnot(None),
    ).first()
    if existing_prompted and existing_prompted.prompt_id:
        existing_prompt = db.query(Prompt).filter(Prompt.id == existing_prompted.prompt_id).first()
        if existing_prompt and existing_prompt.llm_config_id:
            llm_config = db.query(LLMConfig).filter(LLMConfig.id == existing_prompt.llm_config_id).first()

    if not llm_config and parent_task.model:
        llm_config = db.query(LLMConfig).filter(
            or_(LLMConfig.user_id == current_user.id, LLMConfig.user_id.is_(None)),
            LLMConfig.default_model == parent_task.model,
        ).first()

    if llm_config:
        base_url_override = llm_config.base_url
        api_key_override = llm_config.api_key

    model = parent_task.model or (llm_config.default_model if llm_config else "qwen-max")

    # Update parent task status
    parent_task.status = TaskStatusEnum.RUNNING
    parent_task.progress_label = "继续链式执行..."
    db.commit()

    # Launch auto-continue background coroutine
    asyncio.create_task(
        run_pipeline_auto_bg(
            parent_task_id=task_id,
            mode=mode,
            model=model,
            user_id=current_user.id,
            username=current_user.username,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            source_file_id=parent_task.source_file_id,
            prompt_template_id=parent_task.prompt_template_id,
        )
    )

    remaining = len(step_order) - len(completed_step_names)
    logger.info(
        f"User {current_user.username} auto-continue pipeline {task_id}, "
        f"{remaining} remaining steps"
    )

    return {
        "parent_task_id": task_id,
        "pipeline_mode": mode,
        "completed_steps": len(completed_step_names),
        "remaining_steps": remaining,
        "total_steps": len(step_order),
        "status": "running",
        "message": f"继续链式执行剩余 {remaining} 步",
    }


# ---------------------------------------------------------------------------
# H-CoT Prompt Template Management
# ---------------------------------------------------------------------------

def _hcot_prompt_error(exc: PromptTemplateError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/prompts/templates")
async def list_hcot_prompt_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all H-CoT prompt templates for the current user."""
    try:
        return list_hcot_templates(current_user.id)
    except PromptTemplateError as exc:
        raise _hcot_prompt_error(exc)


@router.get("/prompts/templates/{template_id}")
async def get_hcot_prompt_template_detail(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detail + prompt tree for a specific H-CoT template."""
    try:
        return get_hcot_template_detail(template_id, current_user.id)
    except PromptTemplateError as exc:
        raise _hcot_prompt_error(exc)


@router.post("/prompts/templates/{template_id}/duplicate")
async def duplicate_hcot_prompt_template(
    template_id: str,
    payload: HcotTemplateNameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Duplicate an H-CoT prompt template with a new name."""
    try:
        return duplicate_hcot_template(template_id, current_user.id, payload.name)
    except PromptTemplateError as exc:
        raise _hcot_prompt_error(exc)


@router.put("/prompts/templates/{template_id}")
async def rename_hcot_prompt_template(
    template_id: str,
    payload: HcotTemplateNameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rename an H-CoT prompt template."""
    try:
        return rename_hcot_template(template_id, current_user.id, payload.name)
    except PromptTemplateError as exc:
        raise _hcot_prompt_error(exc)


@router.post("/prompts/templates/{template_id}/set-default")
async def set_hcot_default_prompt_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set an H-CoT prompt template as the user's default."""
    try:
        return set_hcot_default_template(template_id, current_user.id)
    except PromptTemplateError as exc:
        raise _hcot_prompt_error(exc)


@router.delete("/prompts/templates/{template_id}")
async def delete_hcot_prompt_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an H-CoT prompt template."""
    try:
        return delete_hcot_template(template_id, current_user.id)
    except PromptTemplateError as exc:
        raise _hcot_prompt_error(exc)


@router.get("/prompts/templates/{template_id}/items/{prompt_key}")
async def get_hcot_prompt_template_item(
    template_id: str,
    prompt_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get prompt content for a specific item in an H-CoT template."""
    try:
        return get_hcot_prompt_item(template_id, current_user.id, prompt_key)
    except PromptTemplateError as exc:
        raise _hcot_prompt_error(exc)


@router.put("/prompts/templates/{template_id}/items/{prompt_key}")
async def update_hcot_prompt_template_item(
    template_id: str,
    prompt_key: str,
    payload: HcotPromptContentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update prompt content for a specific item in an H-CoT template."""
    try:
        return update_hcot_prompt_item(template_id, current_user.id, prompt_key, payload.content)
    except PromptTemplateError as exc:
        raise _hcot_prompt_error(exc)


@router.post("/prompts/templates/{template_id}/items/{prompt_key}/restore-default")
async def restore_hcot_prompt_template_item_default(
    template_id: str,
    prompt_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restore the default content for a specific prompt item in an H-CoT template."""
    try:
        return restore_hcot_prompt_default(template_id, current_user.id, prompt_key)
    except PromptTemplateError as exc:
        raise _hcot_prompt_error(exc)