"""Text preprocess tool router.

Runs the question-generation text preprocessing as an explicit file-to-file
operation, so later question generation consumes a fixed JSON file.
"""

import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import File, StageEnum, User
from app.routers.auth import get_current_user
from app.services.file_service import create_output_file
from app.services.preprocess_service import preprocess_chunks

router = APIRouter()


class TextPreprocessRequest(BaseModel):
    file_id: int = Field(..., description="源 JSON 文件 ID")
    text_field: Optional[str] = Field(None, description="文本字段名；为空则使用文件记录的 text_field")
    min_token_threshold: int = Field(1000, ge=1, le=10000, description="短文本合并/保留阈值")
    output_filename: Optional[str] = Field(None, description="输出文件基础名")
    merge_before_classify: bool = Field(True, description="True=先合并到阈值再分类过滤；False=先分类再合并")


@router.get("/source-files")
async def list_source_files(
    show_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List JSON files available for preprocessing."""
    query = db.query(File).filter(
        File.user_id == current_user.id,
        File.file_type == "json",
    )
    if not show_all:
        query = query.filter(File.source_stage.is_(None))

    files = query.order_by(File.created_at.desc()).all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "text_field": f.text_field,
            "source_stage": f.source_stage.value if f.source_stage else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


@router.post("/run")
async def run_text_preprocess(
    data: TextPreprocessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source_file = (
        db.query(File)
        .filter(File.id == data.file_id, File.user_id == current_user.id)
        .first()
    )
    if source_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if source_file.file_type != "json":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 JSON 文件")
    if not os.path.exists(source_file.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="源文件磁盘内容不存在")

    try:
        with open(source_file.file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"读取 JSON 失败: {str(exc)[:200]}",
        )

    if not isinstance(raw_data, list):
        raw_records = [raw_data]
    else:
        raw_records = raw_data

    text_field = data.text_field or source_file.text_field or "text"
    processed_chunks, stats = preprocess_chunks(
        raw_records,
        text_field,
        min_token_threshold=data.min_token_threshold,
        merge_before_classify=data.merge_before_classify,
    )

    processed_payload = []
    for chunk in processed_chunks:
        if isinstance(chunk.original_record, dict):
            item = dict(chunk.original_record)
        else:
            item = {"source_record": chunk.original_record}

        item[text_field] = chunk.text
        if chunk.source and not item.get("source"):
            item["source"] = chunk.source
        if chunk.source_id and not item.get("source_id"):
            item["source_id"] = chunk.source_id
        if chunk.merged_from:
            item["merged_from"] = chunk.merged_from
        processed_payload.append(item)

    base_name = data.output_filename or os.path.splitext(source_file.filename)[0]
    processed_file = create_output_file(
        db=db,
        user_id=current_user.id,
        source_file=source_file,
        stage=StageEnum.GENERIC,
        output_filename=base_name,
        username=current_user.username,
        name_suffix="preprocessed",
        initial_content=processed_payload,
        text_field=text_field,
    )
    # Treat the usable preprocessed file as an input file, so question_generate
    # shows it by default without requiring "show all".
    processed_file.source_stage = None
    db.commit()
    db.refresh(processed_file)

    filtered_file = None
    if stats.skipped_records:
        filtered_payload = [
            {
                "source_id": _safe_field(raw_records[s.original_index], "source_id"),
                "source": _safe_field(raw_records[s.original_index], "source"),
                text_field: s.text,
                "skip_reason": s.skip_reason,
            }
            for s in stats.skipped_records
        ]
        filtered_file = create_output_file(
            db=db,
            user_id=current_user.id,
            source_file=source_file,
            stage=StageEnum.GENERIC,
            output_filename=base_name,
            username=current_user.username,
            name_suffix="preprocess_filtered",
            initial_content=filtered_payload,
            text_field=text_field,
        )

    return {
        "processed_file": _file_payload(processed_file),
        "filtered_file": _file_payload(filtered_file) if filtered_file else None,
        "stats": {
            "original_count": stats.original_count,
            "kept_count": stats.kept_count,
            "kept_by_merge_count": stats.kept_by_merge_count,
            "skipped_count": stats.skipped_count,
            "skip_breakdown": stats.skip_breakdown,
            "header_footer_blacklist": stats.header_footer_blacklist,
            "min_token_threshold": data.min_token_threshold,
        },
    }


def _safe_field(record, field_name: str, default: str = "") -> str:
    if isinstance(record, dict):
        val = record.get(field_name, default)
        return val if val is not None else default
    return default


def _file_payload(file_obj: Optional[File]) -> Optional[dict]:
    if file_obj is None:
        return None
    return {
        "id": file_obj.id,
        "filename": file_obj.filename,
        "text_field": file_obj.text_field,
        "source_stage": file_obj.source_stage.value if file_obj.source_stage else None,
        "created_at": file_obj.created_at.isoformat() if file_obj.created_at else None,
    }
