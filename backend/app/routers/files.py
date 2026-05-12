"""Files router - CRUD with user data isolation"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import File, StageEnum, User
from app.routers.auth import get_current_user

router = APIRouter()


# ---------- API endpoints ----------


@router.get("/")
async def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all files belonging to the current user."""
    files = (
        db.query(File)
        .filter(File.user_id == current_user.id)
        .order_by(File.id.desc())
        .all()
    )
    return [
        {
            "id": f.id,
            "user_id": f.user_id,
            "filename": f.filename,
            "file_type": f.file_type,
            "file_path": f.file_path,
            "source_stage": f.source_stage,
            "created_at": f.created_at,
        }
        for f in files
    ]


@router.get("/{file_id}")
async def get_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a file by ID (must belong to current user)."""
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
    return {
        "id": file_obj.id,
        "user_id": file_obj.user_id,
        "filename": file_obj.filename,
        "file_type": file_obj.file_type,
        "file_path": file_obj.file_path,
        "source_stage": file_obj.source_stage,
        "created_at": file_obj.created_at,
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    source_stage: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a file for the current user."""
    import os
    from app.config import settings

    # Save file to disk
    upload_dir = os.path.join("uploads", str(current_user.id))
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Determine file type from extension
    ext = os.path.splitext(file.filename)[1].lower()
    file_type_map = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".doc": "doc",
        ".txt": "txt",
        ".csv": "csv",
        ".xlsx": "xlsx",
        ".json": "json",
        ".md": "markdown",
    }
    file_type = file_type_map.get(ext, ext.lstrip(".") if ext else "unknown")

    # Create DB record
    stage_enum = None
    if source_stage and source_stage in [s.value for s in StageEnum]:
        stage_enum = StageEnum(source_stage)

    file_record = File(
        user_id=current_user.id,
        filename=file.filename,
        file_type=file_type,
        file_path=file_path,
        source_stage=stage_enum,
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    return {
        "id": file_record.id,
        "filename": file_record.filename,
        "file_type": file_record.file_type,
        "file_path": file_record.file_path,
        "source_stage": file_record.source_stage,
        "created_at": file_record.created_at,
    }


@router.post("/{file_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a file (must belong to current user)."""
    import os

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

    # Remove file from disk if it exists
    if os.path.exists(file_obj.file_path):
        os.remove(file_obj.file_path)

    db.delete(file_obj)
    db.commit()