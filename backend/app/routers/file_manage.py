"""File Manage router - Combined file management for the workspace"""

import gzip
import json
from typing import List, Optional
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File as FastAPIFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Dataset, File, Task, TaskStatusEnum, StageEnum, User
from app.routers.auth import get_current_user
from app.services.file_manage_service import filter_record_fields, filter_records_fields
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
        "username": f.user.username if f.user else "",
    }


# ---------- API endpoints ----------


@router.get("")
async def list_managed_files(
    search: str = None,
    sort: str = "time_desc",
    source_stage: str = None,
    page: int = 1,
    page_size: int = 10,
    all_users: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all files for the current user, with search and sort.
    Admin users can set all_users=true to see all users' files."""
    query = db.query(File)

    # Admin can see all users' files when all_users flag is set
    if not (all_users and current_user.username == "admin"):
        query = query.filter(File.user_id == current_user.id)

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
    """Get file details by ID (must belong to current user, or admin)."""
    query = db.query(File).filter(File.id == file_id)
    if current_user.username != "admin":
        query = query.filter(File.user_id == current_user.id)
    file_obj = query.first()
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
    """Get JSON content preview for a file by ID (must belong to current user, or admin).
    Supports filtering by task_type, domain, difficulty."""
    query = db.query(File).filter(File.id == file_id)
    if current_user.username != "admin":
        query = query.filter(File.user_id == current_user.id)
    file_obj = query.first()
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


@router.get("/fields/{file_id}")
async def get_file_fields(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the field names (keys) of the first record in a JSON file."""
    query = db.query(File).filter(File.id == file_id)
    if current_user.username != "admin":
        query = query.filter(File.user_id == current_user.id)
    file_obj = query.first()
    if file_obj is None:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(file_obj.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    try:
        with open(file_obj.file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse JSON: {str(e)}")

    records = content if isinstance(content, list) else [content]
    first = records[0] if records else {}
    fields = list(first.keys()) if isinstance(first, dict) else []

    return {"file_id": file_id, "fields": fields, "total_records": len(records)}


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
    # Diagnostic: confirm the route handler was actually entered (vs being
    # rejected at the multipart-parsing layer before us). Printed via stdout so
    # it always shows up in `docker logs qa-studio-backend`.
    try:
        file_info = [(f.filename, getattr(f, "size", "?")) for f in files]
    except Exception:
        file_info = "<unreadable>"
    print(
        f"[UPLOAD] user={current_user.username} text_field={text_field!r} files={file_info}",
        flush=True,
    )
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
            parsed = json.loads(content_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append({
                "filename": file.filename,
                "error": f"Invalid JSON: {str(e)}",
            })
            continue

        # 检查 text_field 是否存在于 JSON 记录中
        text_field_warning = None
        records = parsed if isinstance(parsed, list) else [parsed]
        if records and isinstance(records[0], dict):
            sample = records[0]
            if text_field not in sample:
                available = [k for k in sample.keys() if isinstance(sample[k], str) and len(sample[k]) > 0]
                alt_fields = ["text", "content", "body", "paragraph", "input"]
                found_alt = [f for f in alt_fields if f in sample]
                hint = f"，可用字段: {', '.join(available[:8])}" if available else ""
                if found_alt:
                    text_field_warning = f"指定的text字段「{text_field}」不存在于JSON中{hint}。备选字段 {found_alt} 可用"
                else:
                    text_field_warning = f"指定的text字段「{text_field}」不存在于JSON中{hint}"

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

        result_item = _serialize_file(file_record)
        if text_field_warning:
            result_item["warning"] = text_field_warning
        results.append(result_item)

    return {"uploaded": results, "errors": errors}


@router.post("/gzip-upload-test")
async def gzip_upload_test(
    files: List[UploadFile] = FastAPIFile(...),
    text_field: str = Form("text"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """测试端点：接收 gzip 压缩文件，解压后当 JSON 处理。"""
    results = []
    errors = []

    for file in files:
        content_bytes = await file.read()

        try:
            decompressed = gzip.decompress(content_bytes)
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": f"Gzip 解压失败: {str(e)}",
            })
            continue

        try:
            parsed = json.loads(decompressed.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append({
                "filename": file.filename,
                "error": f"JSON 解析失败: {str(e)}",
            })
            continue

        records = parsed if isinstance(parsed, list) else [parsed]

        # 检查 text_field
        text_field_warning = None
        if records and isinstance(records[0], dict):
            sample = records[0]
            if text_field not in sample:
                available = [k for k in sample.keys() if isinstance(sample[k], str) and len(sample[k]) > 0]
                text_field_warning = f"text字段「{text_field}」不存在，可用字段: {', '.join(available[:8])}" if available else f"text字段「{text_field}」不存在"

        original_size = len(content_bytes)
        decompressed_size = len(decompressed)
        ratio = f"{original_size / max(decompressed_size, 1) * 100:.1f}%"

        result_item = {
            "filename": file.filename,
            "compressed_bytes": original_size,
            "decompressed_bytes": decompressed_size,
            "ratio": ratio,
            "record_count": len(records),
        }
        if text_field_warning:
            result_item["warning"] = text_field_warning
        results.append(result_item)

    return {"uploaded": results, "errors": errors}


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


@router.post("/{file_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_managed_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a file and its disk copy (must belong to current user, or admin)."""
    query = db.query(File).filter(File.id == file_id)
    if current_user.username != "admin":
        query = query.filter(File.user_id == current_user.id)
    file_obj = query.first()
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


class BatchDeleteRequest(BaseModel):
    file_ids: List[int]


@router.post("/batch-delete")
async def batch_delete_managed_files(
    body: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch delete files. Skips files with running tasks instead of blocking."""
    deleted = []
    skipped = []
    not_found = []

    for file_id in body.file_ids:
        query = db.query(File).filter(File.id == file_id)
        if current_user.username != "admin":
            query = query.filter(File.user_id == current_user.id)
        file_obj = query.first()
        if file_obj is None:
            not_found.append(file_id)
            continue

        running_count = (
            db.query(Task)
            .filter(Task.file_id == file_id, Task.status == TaskStatusEnum.RUNNING)
            .count()
        )
        if running_count > 0:
            skipped.append({"id": file_id, "reason": "有运行中的任务引用此文件"})
            continue

        db.query(Task).filter(
            Task.file_id == file_id, Task.status != TaskStatusEnum.RUNNING
        ).update({"file_id": None})
        db.query(Dataset).filter(Dataset.file_id == file_id).update({"file_id": None})
        db.commit()

        if os.path.exists(file_obj.file_path):
            os.remove(file_obj.file_path)

        db.delete(file_obj)
        db.commit()
        deleted.append(file_id)

    return {"deleted": deleted, "skipped": skipped, "not_found": not_found}


@router.get("/download/{file_id}")
async def download_managed_file(
    file_id: int,
    fields: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a file by streaming it from disk.
    If fields parameter is provided (comma-separated field names), filter JSON records
    to only include selected fields. Top-level fields are plain names; extra sub-fields
    are prefixed with 'extra.' (e.g. 'extra.options'). Without fields, returns full data."""
    query = db.query(File).filter(File.id == file_id)
    if current_user.username != "admin":
        query = query.filter(File.user_id == current_user.id)
    file_obj = query.first()
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

    # If fields filtering requested and file is JSON, apply field filtering
    if fields and file_obj.file_type == "json":
        field_list = [f.strip() for f in fields.split(",") if f.strip()]
        if field_list:
            try:
                with open(file_obj.file_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to parse JSON: {str(e)}",
                )

            if isinstance(content, list):
                filtered = filter_records_fields(content, field_list)
            elif isinstance(content, dict):
                filtered = [filter_record_fields(content, field_list)]
            else:
                filtered = content

            # Write filtered data to a temp file for streaming
            temp_dir = os.path.join("uploads", str(current_user.id))
            os.makedirs(temp_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filtered_filename = f"filtered_{file_obj.filename}_{timestamp}.json"
            filtered_path = os.path.join(temp_dir, filtered_filename)

            with open(filtered_path, "w", encoding="utf-8") as fh:
                json.dump(filtered, fh, ensure_ascii=False, indent=2)

            return FileResponse(
                path=filtered_path,
                filename=file_obj.filename,
                media_type="application/json",
            )

    # No field filtering — return original file
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


@router.post("/sync/{file_id}")
async def sync_file_to_disk(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将 DB 中该文件关联的 Dataset 数据全量同步到磁盘 JSON 文件（覆盖写入）。"""
    query = db.query(File).filter(File.id == file_id)
    if current_user.username != "admin":
        query = query.filter(File.user_id == current_user.id)
    file_obj = query.first()
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )

    if file_obj.file_type != "json":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持同步JSON文件",
        )

    datasets_count = (
        db.query(Dataset)
        .filter(Dataset.file_id == file_id)
        .count()
    )

    if datasets_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该文件下无Dataset数据可同步",
        )

    try:
        from app.services.file_service import write_datasets_to_file
        write_datasets_to_file(db=db, file_id=file_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步失败: {str(e)[:200]}",
        )

    return {
        "synced_count": datasets_count,
        "filename": file_obj.filename,
    }


class MergeDownloadRequest(BaseModel):
    file_ids: List[int]
    fields: Optional[List[str]] = None


@router.post("/merge-download")
async def merge_and_download(
    body: MergeDownloadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Merge multiple JSON files into one and return as download.
    If fields list is provided, filter records to only include selected fields."""
    file_ids = body.file_ids
    field_list = body.fields
    if len(file_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少选择2个文件进行合并",
        )

    # Validate all files (admin can access any files)
    query = db.query(File).filter(File.id.in_(file_ids))
    if current_user.username != "admin":
        query = query.filter(File.user_id == current_user.id)
    files = query.all()
    if len(files) != len(file_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="部分文件不存在或无权访问",
        )

    merged = []
    skipped = []
    # Track whether any files were successfully read
    has_content = False
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

        has_content = True
        if isinstance(content, list):
            merged.extend(content)
        elif isinstance(content, dict):
            merged.append(content)
        else:
            skipped.append(f"{f.filename} (内容不是数组或对象)")

    if not has_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有可合并的内容。请检查选择的文件是否为有效JSON数组",
        )

    # Apply field filtering if requested
    if field_list and len(field_list) > 0:
        merged = filter_records_fields(merged, field_list)

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