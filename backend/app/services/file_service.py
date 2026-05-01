"""Shared file write-back service for QA Studio pipeline stages.

Every pipeline stage (except question_generate) writes its results back to the
same JSON file on disk.  question_generate is the only stage that creates a
new output file.  Validation stages also produce consolidated fail-files.

Key design:
- write_datasets_to_file(): overwrite the JSON on disk with latest DB data
- create_output_file(): make a new File record for question_generate stage
- create_fail_file(): make a consolidated fail-file for validation stages
- serialize_dataset_to_dict(): convert a Dataset ORM object to a JSON-ready dict

All functions operate on the File + Dataset models and write to the
uploads/{user_id}/ directory on disk.
"""

import json
import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Dataset, File, StageEnum

logger = logging.getLogger("qa_studio.file_service")

# ---------------------------------------------------------------------------
# Stage label mapping (Chinese display names)
# ---------------------------------------------------------------------------

STAGE_LABELS = {
    StageEnum.QUESTION_GENERATE: "问题生成",
    StageEnum.QUESTION_VALIDATE: "问题校验",
    StageEnum.ANSWER_VALIDATE: "答案校验",
}

# ---------------------------------------------------------------------------
# Dataset serialization
# ---------------------------------------------------------------------------

# All Dataset columns in the order they should appear in the JSON deliverable.
# Columns that are internal (id, user_id, file_id, created_at, updated_at)
# are excluded from the output -- the JSON file is a data deliverable, not a
# DB dump.

_SERIALIZABLE_FIELDS = [
    "domain",
    "category",
    "task_type",
    "input",
    "output",
    "cot",
    "corpus_cate",
    "scene",
    "Assessment",
    "source",
    "source_id",
    "source_type",
    "originContent",
    "knowledge",
    "difficulty",
    "relevance",
    "clarity",
    "reasoning",
    "terminology",
    "score",
    "passed",
    "current_stage",
]


def serialize_dataset_to_dict(dataset: Dataset) -> dict:
    """Convert a Dataset ORM object to a dict suitable for JSON serialization.

    Only includes fields that have been populated (not None).
    Special handling:
    - knowledge (JSON column): serialize as-is (dict/list), never double-encoded
    - score (Float): serialize as number, not string
    - current_stage (Enum): serialize as its string value
    - Assessment (default ""): included even when empty
    - corpus_cate (default 1): included even when default
    """
    result = {}
    for field in _SERIALIZABLE_FIELDS:
        value = getattr(dataset, field, None)

        # Skip fields that have never been populated (None)
        # but keep fields with explicit defaults like "" or 1
        if value is None:
            continue

        # Special handling per field type
        if field == "knowledge":
            # JSON column: if it's already a dict/list, keep it as-is.
            # If it's a string (double-encoded), parse it first.
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass  # leave as string if it can't be parsed
            result[field] = value

        elif field == "current_stage":
            # Enum column: serialize as its value string
            result[field] = value.value if hasattr(value, "value") else str(value)

        elif field == "score":
            # Float column: serialize as number, not string
            result[field] = float(value)

        else:
            result[field] = value

    return result


# ---------------------------------------------------------------------------
# Core write-back function
# ---------------------------------------------------------------------------


def write_datasets_to_file(db: Session, file_id: int) -> str:
    """Read all Dataset records linked to this file_id from the database,
    serialize them to JSON, and overwrite the file on disk.

    This is called after each pipeline stage completes to update the JSON file
    with the latest data from the database.

    Args:
        db: Active SQLAlchemy session.
        file_id: The File record ID whose linked datasets should be written.

    Returns:
        The file_path of the written file.

    Raises:
        ValueError: If the File record or its disk path cannot be resolved.
    """
    # Fetch the File record
    file_obj = db.query(File).filter(File.id == file_id).first()
    if file_obj is None:
        raise ValueError(f"File record with id={file_id} not found")

    # Fetch all Dataset records linked to this file, ordered by id
    datasets = (
        db.query(Dataset)
        .filter(Dataset.file_id == file_id)
        .order_by(Dataset.id.asc())
        .all()
    )

    # Serialize each dataset
    items = [serialize_dataset_to_dict(d) for d in datasets]

    # Write JSON to disk (overwrite the existing file)
    file_path = file_obj.file_path

    # Ensure parent directory exists (could be missing if file was created
    # in a different context)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    logger.info(
        "Written %d datasets to file %s (file_id=%d)",
        len(items), file_path, file_id,
    )

    return file_path


# ---------------------------------------------------------------------------
# Output file creation (question_generate stage only)
# ---------------------------------------------------------------------------


def create_output_file(db: Session, user_id: int, source_file: File, stage_name: str = "问题生成", output_filename: str = None, username: str = None) -> File:
    """Create a new output File record for the question_generate stage.

    Called by question_generate to create the new JSON file.  The filename
    follows the pattern: {output_filename}_{username}_{timestamp}.json where
    timestamp is YYYYMMDDHHmmss format for uniqueness.

    Args:
        db: Active SQLAlchemy session.
        user_id: The user who owns the file.
        source_file: The original uploaded source JSON file.
        stage_name: Display suffix for the filename (default '问题生成').
        output_filename: User-specified base name for the output file (required).
        username: Username to append as suffix for uniqueness.
                  If not provided, falls back to str(user_id).

    Returns:
        A new File record with a generated filename and file_path.
    """
    # Build filename: {output_filename}_{username}_{timestamp}.json
    if output_filename:
        base = output_filename
    else:
        base = os.path.splitext(source_file.filename)[0]

    suffix_name = username or str(user_id)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{base}_{suffix_name}_{timestamp}.json"

    # Build the file_path in the user's upload directory
    upload_dir = os.path.join("uploads", str(user_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    # Create an empty JSON array as initial content (will be overwritten
    # by write_datasets_to_file once question_generate produces records)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

    # Create File DB record
    file_record = File(
        user_id=user_id,
        filename=filename,
        file_type="json",
        file_path=file_path,
        source_stage=StageEnum.QUESTION_GENERATE,
        text_field="output",
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    logger.info(
        "Created output file %s (file_id=%d) from source %s (file_id=%d)",
        filename, file_record.id, source_file.filename, source_file.id,
    )

    return file_record


# ---------------------------------------------------------------------------
# Fail file creation (validation stages)
# ---------------------------------------------------------------------------

# Stage-specific suffixes for fail filenames
_FAIL_SUFFIXES = {
    StageEnum.QUESTION_VALIDATE: "问题校验失败",
    StageEnum.ANSWER_VALIDATE: "答案校验失败",
}


def create_fail_file(
    db: Session,
    user_id: int,
    source_file: File,
    stage: StageEnum,
    fail_records: list,
) -> File:
    """Create a consolidated fail JSON file for validation stages.

    Called by question_validate and answer_validate when records fail
    validation.  The file contains all failed records together, each with
    the original record fields plus validation_result and reason.

    Args:
        db: Active SQLAlchemy session.
        user_id: The user who owns the file.
        source_file: The source JSON file being processed.
        stage: The pipeline stage that generated the failures
               (StageEnum.QUESTION_VALIDATE or StageEnum.ANSWER_VALIDATE).
        fail_records: List of dicts containing failed record data.
                      Each dict should include the original Dataset fields
                      plus 'validation_result' and 'reason'.

    Returns:
        A new File record in the file management area.
    """
    if not fail_records:
        raise ValueError("fail_records must not be empty")

    suffix = _FAIL_SUFFIXES.get(stage)
    if suffix is None:
        raise ValueError(f"Stage {stage} does not produce fail files")

    # Build filename: source_filename (without .json) + _问题校验失败 + .json
    source_base = os.path.splitext(source_file.filename)[0]
    filename = f"{source_base}_{suffix}.json"

    # Build file_path in the user's upload directory
    upload_dir = os.path.join("uploads", str(user_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    # Handle duplicate filenames by appending a counter suffix
    if os.path.exists(file_path):
        counter = 1
        candidate_path = os.path.join(upload_dir, f"{source_base}_{suffix}_{counter}.json")
        while os.path.exists(candidate_path):
            counter += 1
            candidate_path = os.path.join(upload_dir, f"{source_base}_{suffix}_{counter}.json")
        filename = f"{source_base}_{suffix}_{counter}.json"
        file_path = candidate_path

    # Write the consolidated fail file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(fail_records, f, ensure_ascii=False, indent=2)

    # Create File DB record
    file_record = File(
        user_id=user_id,
        filename=filename,
        file_type="json",
        file_path=file_path,
        source_stage=stage,
        text_field="input",
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    logger.info(
        "Created fail file %s (file_id=%d) with %d failed records from stage %s",
        filename, file_record.id, len(fail_records), stage.value,
    )

    return file_record