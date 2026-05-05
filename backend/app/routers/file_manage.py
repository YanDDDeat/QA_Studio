"""File Manage router - Combined file management for the workspace"""

import json
from typing import List
import os

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File as FastAPIFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import File, Task, TaskStatusEnum, StageEnum, User
from app.routers.auth import get_current_user

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