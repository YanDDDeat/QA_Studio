"""Professional CoT construction pipeline router."""

import asyncio
import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, File as UploadFileParam, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import File as ManagedFile, LLMConfig, User
from app.routers.auth import get_current_user
from app.services.professional_cot_service import (
    COT_TYPES,
    create_initial_run,
    get_export_path,
    get_run_detail_for_user,
    list_runs_for_user,
    read_artifact,
    run_pipeline_sync,
)

router = APIRouter()


def _validate_source_json(raw: bytes, text_field: str):
    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="上传文件必须使用 UTF-8 编码")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"非法 JSON：{exc}")

    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="上传 JSON 顶层必须是数组")
    if len(data) != 1:
        raise HTTPException(status_code=400, detail="上传 JSON 数组长度必须等于 1")
    if not isinstance(data[0], dict):
        raise HTTPException(status_code=400, detail="上传 JSON 第一个元素必须是对象")
    if text_field not in data[0]:
        raise HTTPException(status_code=400, detail=f"字段 '{text_field}' 不存在")
    value = data[0].get(text_field)
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"字段 '{text_field}' 必须是字符串")
    if value.strip() == "":
        raise HTTPException(status_code=400, detail=f"字段 '{text_field}' 内容不能为空")
    return data, value


@router.get("/cot-types")
async def get_supported_cot_types(
    current_user: User = Depends(get_current_user),
):
    """Return the fixed 10 professional CoT types."""
    return [
        {"key": item["key"], "display_name": item["display_name"]}
        for item in COT_TYPES
    ]


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    file: Optional[UploadFile] = UploadFileParam(None),
    source_file_id: Optional[int] = Form(None),
    text_field: str = Form("text"),
    llm_config_id: int = Form(...),
    model: Optional[str] = Form(None),
    run_name: Optional[str] = Form(None),
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
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    asyncio.create_task(
        asyncio.to_thread(
            run_pipeline_sync,
            init["run_id"],
            init["llm"],
            current_user.username,
        )
    )

    return {
        "run_id": init["run_id"],
        "status": "running",
        "message": "标注流水线2已启动，请前往详情页查看实时进度",
        "manifest": init["manifest"],
    }


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
    """Read one run detail from manifest and final preview."""
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
