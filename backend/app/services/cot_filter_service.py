"""COT Filter service for QA Studio.

Split QA records by whether the 'cot' field is empty or not.
Pure local processing — no LLM calls, very fast.

Key design:
- Reads input JSON file from disk
- Splits into two groups: with_cot and without_cot
- Uses create_output_file() for consistent naming and File registration
- Returns statistics
"""

import json
import logging

from sqlalchemy.orm import Session

from app.models.models import File, StageEnum
from app.services.file_service import create_output_file

logger = logging.getLogger("qa_studio.cot_filter")


def run_cot_filter(
    db: Session,
    user_id: int,
    source_file: File,
    output_name: str,
    username: str,
    task_id: int,
) -> dict:
    """Run COT filter on a JSON file and create two output files.

    Args:
        db: Active SQLAlchemy session.
        user_id: The user who owns the output files.
        source_file: The source File record to filter.
        output_name: User-specified base name for output files.
        username: Username for unique filename suffix.
        task_id: Task ID for logging.

    Returns:
        Dict with statistics and output file info.
    """
    # Read source file
    with open(source_file.file_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    if not isinstance(raw_items, list):
        raw_items = [raw_items]

    if not raw_items:
        raise ValueError(f"No input items found in file {source_file.filename}")

    # Split by cot field
    with_cot = []
    without_cot = []
    for item in raw_items:
        cot_val = str(item.get("cot", "")).strip()
        if cot_val:
            with_cot.append(item)
        else:
            without_cot.append(item)

    # Create output files via shared factory
    with_cot_record = create_output_file(
        db=db,
        user_id=user_id,
        source_file=source_file,
        stage=StageEnum.COT_FILTER,
        output_filename=output_name,
        username=username,
        name_suffix="cot",
        initial_content=with_cot,
        text_field="input",
    )

    without_cot_record = create_output_file(
        db=db,
        user_id=user_id,
        source_file=source_file,
        stage=StageEnum.COT_FILTER,
        output_filename=output_name,
        username=username,
        name_suffix="no_cot",
        initial_content=without_cot,
        text_field="input",
    )

    logger.info(
        "COT filter complete: total=%d, with_cot=%d, without_cot=%d, "
        "with_cot_file=%s (id=%d), without_cot_file=%s (id=%d)",
        len(raw_items), len(with_cot), len(without_cot),
        with_cot_record.filename, with_cot_record.id,
        without_cot_record.filename, without_cot_record.id,
    )

    return {
        "total": len(raw_items),
        "with_cot_count": len(with_cot),
        "without_cot_count": len(without_cot),
        "with_cot_file_id": with_cot_record.id,
        "with_cot_filename": with_cot_record.filename,
        "without_cot_file_id": without_cot_record.id,
        "without_cot_filename": without_cot_record.filename,
        "with_cot_percent": round(len(with_cot) / len(raw_items) * 100, 1) if raw_items else 0,
        "without_cot_percent": round(len(without_cot) / len(raw_items) * 100, 1) if raw_items else 0,
    }
