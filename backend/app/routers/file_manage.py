"""File Manage router - Combined file management for the workspace"""

import json
from typing import List, Optional
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File as FastAPIFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import File, Task, TaskStatusEnum, StageEnum, User
from app.routers.auth import get_current_user
from app.services.md_parser import _split_by_section, _split_by_paragraph

router = APIRouter()


def _file_size(file_path: str) -> int:
    """Return file size in bytes, or 0 if file missing."""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


def _serialize_file(f: File) -> dict:
    """Serialize a File record to a dict including computed file_size."""
    return {
        "id": f.id,
        "filename": f.filename,
        "file_type": f.file_type,
        "file_path": f.file_path,
        "source_stage": f.source_stage,
        "text_field": f.text_field,
        "file_size": _file_size(f.file_path),
        "created_at": f.created_at,
    }


# ---------- API endpoints ----------


@router.get("")
async def list_managed_files(
    search: str = None,
    sort: str = "time_desc",
    source_stage: str = None,
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all files for the current user, with search and sort."""
    query = db.query(File).filter(File.user_id == current_user.id)

    if search:
        query = query.filter(File.filename.like(f"%{search}%"))
    if source_stage:
        if source_stage not in [s.value for s in StageEnum]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_stage: {source_stage}",
            )
        query = query.filter(File.source_stage == StageEnum(source_stage))

    # Sorting
    if sort == "time_asc":
        query = query.order_by(File.created_at.asc())
    elif sort == "name_asc":
        query = query.order_by(File.filename.asc())
    else:  # time_desc (default)
        query = query.order_by(File.id.desc())

    total = query.count()
    offset = (page - 1) * page_size
    files = query.offset(offset).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_file(f) for f in files],
    }


@router.get("/{file_id}")
async def get_managed_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get file details by ID (must belong to current user)."""
    file_obj = (
        db.query(File)
        .filter(File.id == file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    return _serialize_file(file_obj)


@router.get("/content/{file_id}")
async def get_file_content(
    file_id: int,
    task_type: str = None,
    domain: str = None,
    difficulty: str = None,
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get JSON content preview for a file by ID (must belong to current user).
    Supports filtering by task_type, domain, difficulty."""
    file_obj = (
        db.query(File)
        .filter(File.id == file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if not os.path.exists(file_obj.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk",
        )

    if file_obj.file_type != "json":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JSON files can be previewed",
        )

    try:
        with open(file_obj.file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse JSON: {str(e)}",
        )

    if isinstance(content, list):
        all_records = content
    else:
        all_records = [content]

    # Build filter options from all records (before filtering)
    filter_options = {
        "task_types": sorted(set(
            str(r.get("task_type", "")) for r in all_records
            if isinstance(r, dict) and r.get("task_type")
        )),
        "domains": sorted(set(
            str(r.get("domain", "")) for r in all_records
            if isinstance(r, dict) and r.get("domain")
        )),
        "difficulties": sorted(set(
            str(r.get("difficulty", "")) for r in all_records
            if isinstance(r, dict) and r.get("difficulty")
        )),
    }

    # Apply filters
    filtered = all_records
    if task_type:
        filtered = [r for r in filtered if isinstance(r, dict) and str(r.get("task_type", "")) == task_type]
    if domain:
        filtered = [r for r in filtered if isinstance(r, dict) and str(r.get("domain", "")) == domain]
    if difficulty:
        filtered = [r for r in filtered if isinstance(r, dict) and str(r.get("difficulty", "")) == difficulty]

    total = len(filtered)
    offset = (page - 1) * page_size
    preview = filtered[offset:offset + page_size]

    return {
        "id": file_obj.id,
        "filename": file_obj.filename,
        "text_field": file_obj.text_field,
        "total_records": total,
        "page": page,
        "page_size": page_size,
        "preview": preview,
        "filter_options": filter_options,
    }


@router.post("/upload")
async def upload_managed_files(
    files: List[UploadFile] = FastAPIFile(...),
    text_field: str = Form("text"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload one or more JSON files with a text_field parameter.

    Args:
        files: Multiple JSON files (multipart form data).
        text_field: The JSON field name that contains the text blocks (default "text").
    """
    upload_dir = os.path.join("uploads", str(current_user.id))
    os.makedirs(upload_dir, exist_ok=True)

    results = []
    errors = []

    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext != ".json":
            errors.append({
                "filename": file.filename,
                "error": "Only JSON files are accepted",
            })
            continue

        # Read and validate JSON content
        content_bytes = await file.read()
        try:
            json.loads(content_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append({
                "filename": file.filename,
                "error": f"Invalid JSON: {str(e)}",
            })
            continue

        # Save file to disk
        file_path = os.path.join(upload_dir, file.filename)
        # Handle duplicate filenames by appending a counter
        if os.path.exists(file_path):
            base, ext = os.path.splitext(file.filename)
            counter = 1
            while os.path.exists(os.path.join(upload_dir, f"{base}_{counter}{ext}")):
                counter += 1
            file_path = os.path.join(upload_dir, f"{base}_{counter}{ext}")

        with open(file_path, "wb") as f:
            f.write(content_bytes)

        # Create DB record
        file_record = File(
            user_id=current_user.id,
            filename=os.path.basename(file_path),
            file_type="json",
            file_path=file_path,
            source_stage=None,  # uploaded files have no source_stage
            text_field=text_field,
        )
        db.add(file_record)
        db.commit()
        db.refresh(file_record)

        results.append(_serialize_file(file_record))

    return {
        "uploaded": results,
        "errors": errors,
    }


SOURCE_TYPE_CHOICES = ['文献', '图书', '其他']


@router.post("/upload-md")
async def upload_md_files(
    files: List[UploadFile] = FastAPIFile(...),
    source_type: str = Form(...),
    split_mode: str = Form('full'),
    min_title_level: int = Form(1),
    max_title_level: int = Form(6),
    min_chars: int = Form(100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload MD files, convert to JSON, save only the JSON output (MD not saved).

    source_type: '文献' | '图书' | '其他'
    split_mode: 'full' (整篇不切分) | 'section' (按章节) | 'paragraph' (按段落)
    """
    if source_type not in SOURCE_TYPE_CHOICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"source_type must be one of {SOURCE_TYPE_CHOICES}",
        )
    if split_mode not in ('full', 'section', 'paragraph'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="split_mode must be one of: full, section, paragraph",
        )

    upload_dir = os.path.join("uploads", str(current_user.id))
    os.makedirs(upload_dir, exist_ok=True)

    results = []
    errors = []

    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext != ".md":
            errors.append({"filename": file.filename, "error": "Only .md files are accepted"})
            continue

        content_bytes = await file.read()
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            errors.append({"filename": file.filename, "error": f"Encoding error: {str(e)}"})
            continue

        stem = os.path.splitext(file.filename)[0]

        # Build chunks based on split_mode
        if split_mode == 'full':
            chunks = [{"text": content, "source": stem, "source_id": stem}]
        else:
            try:
                if split_mode == 'section':
                    raw_chunks = _split_by_section(
                        content, file.filename,
                        min_title_level=min_title_level,
                        max_title_level=max_title_level,
                    )
                else:  # paragraph
                    raw_chunks = _split_by_paragraph(
                        content, file.filename,
                        min_chars=min_chars,
                    )
            except Exception as e:
                errors.append({"filename": file.filename, "error": f"Parse error: {str(e)}"})
                continue

            chunks = [
                {"text": c["text"], "source": f"{stem}_{idx+1}", "source_id": f"{stem}_{idx+1}"}
                for idx, c in enumerate(raw_chunks)
            ]

        if not chunks:
            errors.append({"filename": file.filename, "error": "No content extracted"})
            continue

        # Build final JSON records
        json_records = [
            {"text": c["text"], "source": c["source"], "source_type": source_type, "source_id": c["source_id"]}
            for c in chunks
        ]

        # Save JSON file
        json_filename = f"{stem}.json"
        json_path = os.path.join(upload_dir, json_filename)
        if os.path.exists(json_path):
            base = stem
            counter = 1
            while os.path.exists(os.path.join(upload_dir, f"{base}_{counter}.json")):
                counter += 1
            json_filename = f"{base}_{counter}.json"
            json_path = os.path.join(upload_dir, json_filename)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_records, f, ensure_ascii=False, indent=2)

        # Create DB record
        file_record = File(
            user_id=current_user.id,
            filename=json_filename,
            file_type="json",
            file_path=json_path,
            source_stage=None,
            text_field="text",
        )
        db.add(file_record)
        db.commit()
        db.refresh(file_record)

        results.append(_serialize_file(file_record))

    return {"uploaded": results, "errors": errors}


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_managed_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a file and its disk copy (must belong to current user)."""
    file_obj = (
        db.query(File)
        .filter(File.id == file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Check if any RUNNING tasks reference this file — block deletion
    running_tasks = (
        db.query(Task)
        .filter(Task.file_id == file_id, Task.status == TaskStatusEnum.RUNNING)
        .count()
    )
    if running_tasks > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete file: {running_tasks} running task(s) reference this file",
        )

    # For completed/failed tasks referencing this file, set file_id to NULL
    # so they no longer reference the file being deleted
    non_running_tasks = (
        db.query(Task)
        .filter(Task.file_id == file_id, Task.status != TaskStatusEnum.RUNNING)
        .all()
    )
    for task in non_running_tasks:
        task.file_id = None
    db.commit()

    # Remove file from disk if it exists
    if os.path.exists(file_obj.file_path):
        os.remove(file_obj.file_path)

    db.delete(file_obj)
    db.commit()


@router.get("/download/{file_id}")
async def download_managed_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a file by streaming it from disk."""
    file_obj = (
        db.query(File)
        .filter(File.id == file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if not os.path.exists(file_obj.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk",
        )

    media_type_map = {
        "json": "application/json",
        "pdf": "application/pdf",
        "txt": "text/plain",
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    media_type = media_type_map.get(file_obj.file_type, "application/octet-stream")

    return FileResponse(
        path=file_obj.file_path,
        filename=file_obj.filename,
        media_type=media_type,
    )


class MergeDownloadRequest(BaseModel):
    file_ids: List[int]


@router.post("/merge-download")
async def merge_and_download(
    body: MergeDownloadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Merge multiple JSON files into one and return as download."""
    file_ids = body.file_ids
    if len(file_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少选择2个文件进行合并",
        )

    # Validate all files belong to user
    files = (
        db.query(File)
        .filter(File.id.in_(file_ids), File.user_id == current_user.id)
        .all()
    )
    if len(files) != len(file_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="部分文件不存在或无权访问",
        )

    # Merge JSON contents
    merged = []
    skipped = []
    for f in files:
        if not os.path.exists(f.file_path):
            skipped.append(f"{f.filename} (文件不存在)")
            continue
        if f.file_type != "json":
            skipped.append(f"{f.filename} (非JSON文件)")
            continue
        try:
            with open(f.file_path, "r", encoding="utf-8") as fh:
                content = json.load(fh)
        except (json.JSONDecodeError, UnicodeDecodeError):
            skipped.append(f"{f.filename} (JSON解析失败)")
            continue

        if isinstance(content, list):
            merged.extend(content)
        elif isinstance(content, dict):
            merged.append(content)
        else:
            skipped.append(f"{f.filename} (内容不是数组或对象)")

    if not merged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有可合并的内容。请检查选择的文件是否为有效JSON数组",
        )

    # Write temporary merged file
    temp_dir = os.path.join("uploads", str(current_user.id))
    os.makedirs(temp_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    merged_filename = f"merged_{len(file_ids)}files_{timestamp}.json"
    merged_path = os.path.join(temp_dir, merged_filename)

    with open(merged_path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)

    return FileResponse(
        path=merged_path,
        filename=merged_filename,
        media_type="application/json",
    )