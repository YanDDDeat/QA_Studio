"""Professional CoT construction pipeline router."""

import asyncio
import json
import os
from functools import partial
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File as UploadFileParam, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.models import File as ManagedFile, LLMConfig, Task, StageEnum, TaskStatusEnum, User
from app.routers.auth import get_current_user
from app.services.thread_pool import llm_thread_pool
from app.services.professional_cot_service import (
    COT_TYPES,
    create_initial_run,
    get_export_path,
    get_export_zip_bytes,
    get_run_detail_for_user,
    get_running_monitor,
    list_runs_for_user,
    read_artifact,
    resume_paused_run,
    run_pipeline_sync,
)
from app.services.professional_cot_prompt_service import (
    PromptTemplateError,
    delete_template,
    duplicate_template,
    get_prompt_item,
    get_template_detail,
    list_templates,
    rename_template,
    restore_prompt_item_default,
    set_default_template,
    update_prompt_item,
)

router = APIRouter()


class TemplateNameRequest(BaseModel):
    name: str


class PromptContentRequest(BaseModel):
    content: str


def _prompt_error(exc: PromptTemplateError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _validate_source_json(raw: bytes, text_field: str):
    """Validate source JSON: must be a non-empty array; every element must have the chosen text_field."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="上传文件必须使用 UTF-8 编码")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"非法 JSON：{exc}")

    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="上传 JSON 顶层必须是数组")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="JSON 数组不能为空")

    missing_indices = []
    empty_indices = []
    for idx, elem in enumerate(data):
        if not isinstance(elem, dict):
            raise HTTPException(status_code=400, detail=f"JSON 数组第 {idx + 1} 个元素必须是对象")
        if text_field not in elem:
            missing_indices.append(idx + 1)
        else:
            value = elem.get(text_field)
            if not isinstance(value, str) or value.strip() == "":
                empty_indices.append(idx + 1)

    if missing_indices:
        raise HTTPException(
            status_code=400,
            detail=f"第 {', '.join(str(i) for i in missing_indices)} 个元素缺少字段 '{text_field}'",
        )
    if empty_indices:
        raise HTTPException(
            status_code=400,
            detail=f"第 {', '.join(str(i) for i in empty_indices)} 个元素字段 '{text_field}' 内容不能为空",
        )

    paper_text = "\n\n".join(elem[text_field] for elem in data)
    return data, paper_text


@router.get("/cot-types")
async def get_supported_cot_types(
    current_user: User = Depends(get_current_user),
):
    """Return the fixed 10 professional CoT types."""
    return [
        {"key": item["key"], "display_name": item["display_name"]}
        for item in COT_TYPES
    ]


@router.get("/prompts/templates")
async def list_prompt_templates(
    current_user: User = Depends(get_current_user),
):
    try:
        return list_templates(current_user.id)
    except PromptTemplateError as exc:
        raise _prompt_error(exc)


@router.get("/prompts/templates/{template_id}")
async def get_prompt_template_detail(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return get_template_detail(template_id, current_user.id)
    except PromptTemplateError as exc:
        raise _prompt_error(exc)


@router.post("/prompts/templates/{template_id}/duplicate")
async def duplicate_prompt_template(
    template_id: str,
    payload: TemplateNameRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return duplicate_template(template_id, current_user.id, payload.name)
    except PromptTemplateError as exc:
        raise _prompt_error(exc)


@router.put("/prompts/templates/{template_id}")
async def rename_prompt_template(
    template_id: str,
    payload: TemplateNameRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return rename_template(template_id, current_user.id, payload.name)
    except PromptTemplateError as exc:
        raise _prompt_error(exc)


@router.post("/prompts/templates/{template_id}/set-default")
async def set_default_prompt_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return set_default_template(template_id, current_user.id)
    except PromptTemplateError as exc:
        raise _prompt_error(exc)


@router.delete("/prompts/templates/{template_id}")
async def delete_prompt_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return delete_template(template_id, current_user.id)
    except PromptTemplateError as exc:
        raise _prompt_error(exc)


@router.get("/prompts/templates/{template_id}/items/{prompt_key}")
async def get_prompt_template_item(
    template_id: str,
    prompt_key: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return get_prompt_item(template_id, current_user.id, prompt_key)
    except PromptTemplateError as exc:
        raise _prompt_error(exc)


@router.put("/prompts/templates/{template_id}/items/{prompt_key}")
async def update_prompt_template_item(
    template_id: str,
    prompt_key: str,
    payload: PromptContentRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return update_prompt_item(template_id, current_user.id, prompt_key, payload.content)
    except PromptTemplateError as exc:
        raise _prompt_error(exc)


@router.post("/prompts/templates/{template_id}/items/{prompt_key}/restore-default")
async def restore_prompt_template_item_default(
    template_id: str,
    prompt_key: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return restore_prompt_item_default(template_id, current_user.id, prompt_key)
    except PromptTemplateError as exc:
        raise _prompt_error(exc)


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    file: Optional[UploadFile] = UploadFileParam(None),
    source_file_id: Optional[int] = Form(None),
    text_field: str = Form("text"),
    source_type: Optional[str] = Form("unknown"),
    llm_config_id: int = Form(...),
    model: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
    prompt_template_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a run from an existing managed JSON file, or fallback to an uploaded file."""
    text_field = (text_field or "text").strip()
    if not text_field:
        raise HTTPException(status_code=400, detail="正文字段名不能为空")
    source_filename = "source.json"
    source_data = None
    paper_text = ""
    selected_source_file_id = source_file_id

    if source_file_id is not None:
        query = db.query(ManagedFile).filter(ManagedFile.id == source_file_id)
        if current_user.username != "admin":
            query = query.filter(ManagedFile.user_id == current_user.id)
        file_obj = query.first()
        if file_obj is None:
            raise HTTPException(status_code=404, detail="源文件不存在或无权访问")
        if file_obj.file_type != "json":
            raise HTTPException(status_code=400, detail="源文件必须是 JSON 文件")
        if not os.path.exists(file_obj.file_path):
            raise HTTPException(status_code=404, detail="源文件磁盘内容不存在")
        with open(file_obj.file_path, "rb") as fh:
            raw = fh.read()
        if not raw:
            raise HTTPException(status_code=400, detail="源文件不能为空")
        source_data, paper_text = _validate_source_json(raw, text_field)
        source_filename = file_obj.filename
    else:
        if file is None:
            raise HTTPException(status_code=400, detail="请选择系统已有 JSON 文件或上传新文件")
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="上传文件不能为空")
        source_data, paper_text = _validate_source_json(raw, text_field)
        source_filename = file.filename or "source.json"

    llm_config = db.query(LLMConfig).filter(
        LLMConfig.id == llm_config_id,
        or_(LLMConfig.user_id == current_user.id, LLMConfig.user_id.is_(None)),
    ).first()
    if not llm_config:
        raise HTTPException(status_code=404, detail="LLM配置不存在")

    selected_model = (model or llm_config.default_model or "").strip()
    if not selected_model:
        raise HTTPException(status_code=400, detail="模型名不能为空")

    try:
        init = create_initial_run(
            source_data=source_data,
            source_filename=source_filename,
            text_field=text_field,
            paper_text=paper_text,
            user_id=current_user.id,
            username=current_user.username,
            llm_config=llm_config,
            model=selected_model,
            run_name=run_name,
            source_file_id=selected_source_file_id,
            prompt_template_id=prompt_template_id,
            source_type=source_type or "unknown",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result = {
        "run_id": init["run_id"],
        "status": "running",
        "message": "单COT生成流水线已启动，请前往详情页查看实时进度",
        "manifest": init.get("manifest", {}),
        "input_count": init["input_count"],
    }

    asyncio.get_running_loop().run_in_executor(
        llm_thread_pool,
        partial(run_pipeline_sync, init["task_id"], init["llm"], current_user.username),
    )

    return result


@router.get("/monitor")
async def professional_cot_monitor(
    current_user: User = Depends(get_current_user),
):
    """Admin-only: return running professional CoT task monitoring data."""
    if current_user.username != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可查看单COT运行监控",
        )
    return get_running_monitor()


@router.get("/runs")
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """List professional CoT runs owned by the current user with pagination."""
    return list_runs_for_user(current_user.id, page=page, page_size=page_size)


@router.get("/runs/{run_id}")
async def get_run_detail(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Read one run detail from DB (Task + CotSample + CotStepLog)."""
    try:
        detail = get_run_detail_for_user(run_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if detail is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return detail


@router.get("/runs/{run_id}/artifact")
async def get_run_artifact(
    run_id: str,
    path: str,
    current_user: User = Depends(get_current_user),
):
    """Read a JSON/JSONL artifact with path traversal protection."""
    try:
        payload = read_artifact(run_id, current_user.id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if payload is None:
        raise HTTPException(status_code=404, detail="产物文件不存在")
    return payload


@router.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Resume a paused or failed run from DB."""
    # Validate ownership and status
    try:
        task_id = int(run_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="运行记录不存在")

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        if task.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权操作此任务")
        if task.status not in (TaskStatusEnum.PAUSED, TaskStatusEnum.FAILED):
            raise HTTPException(status_code=400,
                                detail=f"当前状态为 {task.status.value}, 无法恢复；只有 paused 或 failed 的 run 可以恢复")
    finally:
        db.close()

    llm_info = resume_paused_run(run_id, current_user.id)

    asyncio.get_running_loop().run_in_executor(
        llm_thread_pool,
        partial(run_pipeline_sync, task_id, llm_info, current_user.username),
    )

    return {
        "run_id": run_id,
        "status": "running",
        "message": "单COT生成流水线已恢复运行",
    }


@router.post("/runs/{run_id}/pause")
async def pause_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Pause a running run. Updates Task.status in DB."""
    try:
        task_id = int(run_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="运行记录不存在")

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        if task.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权操作此任务")
        if task.status != TaskStatusEnum.RUNNING:
            raise HTTPException(status_code=400,
                                detail=f"当前状态为 {task.status.value}, 无法暂停；只有 running 的 run 可以暂停")

        done_count = (task.success_count or 0) + (task.failed_count or 0)
        total_count = task.input_count or 1
        task.status = TaskStatusEnum.PAUSED
        task.run_extra = task.run_extra or {}
        task.run_extra["stop_reason"] = "用户手动暂停"
        task.progress_label = f"已暂停（完成 {done_count}/{total_count} 篇文献）"
        db.commit()

        return {
            "run_id": run_id,
            "status": "paused",
            "message": "单COT生成流水线已标记为暂停，后台任务将在当前文献处理完成后停止",
        }
    finally:
        db.close()


@router.get("/runs/{run_id}/export/json")
async def export_json(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download final_samples.json."""
    try:
        path = get_export_path(run_id, current_user.id, "json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if path is None:
        raise HTTPException(status_code=404, detail="final_samples.json 不存在")
    return FileResponse(
        path=str(path),
        media_type="application/json",
        filename=f"{run_id}_final_samples.json",
    )


@router.get("/runs/{run_id}/export/jsonl")
async def export_jsonl(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download final_samples.jsonl."""
    try:
        path = get_export_path(run_id, current_user.id, "jsonl")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if path is None:
        raise HTTPException(status_code=404, detail="final_samples.jsonl 不存在")
    return FileResponse(
        path=str(path),
        media_type="application/x-ndjson",
        filename=f"{run_id}_final_samples.jsonl",
    )


@router.get("/runs/{run_id}/export/zip")
async def export_zip(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download ZIP archive containing source file + final samples."""
    try:
        result = get_export_zip_bytes(run_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="无可导出的文件")
    buf, zip_filename = result
    encoded = quote(zip_filename, safe='')
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
