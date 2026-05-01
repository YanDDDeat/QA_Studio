"""COT Filter service for QA Studio.

Split QA records by whether the 'cot' field is empty or not.
Pure local processing — no LLM calls, very fast.

Key design:
- Reads input JSON file from disk
- Splits into two groups: with_cot and without_cot
- Writes two new JSON output files
- Registers both output files in the File table
- Returns statistics
"""

import json
import os
import logging

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.models import Dataset, File, StageEnum
from app.services.file_service import serialize_dataset_to_dict

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

    # Build output filenames: {output_name}_{username}_{timestamp}_{suffix}.json
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix_name = username or str(user_id)
    upload_dir = os.path.join("uploads", str(user_id))
    os.makedirs(upload_dir, exist_ok=True)

    with_cot_filename = f"{output_name}_{suffix_name}_{timestamp}_cot.json"
    with_cot_path = os.path.join(upload_dir, with_cot_filename)

    without_cot_filename = f"{output_name}_{suffix_name}_{timestamp}_no_cot.json"
    without_cot_path = os.path.join(upload_dir, without_cot_filename)

    # Write output files
    with open(with_cot_path, "w", encoding="utf-8") as f:
        json.dump(with_cot, f, ensure_ascii=False, indent=2)

    with open(without_cot_path, "w", encoding="utf-8") as f:
        json.dump(without_cot, f, ensure_ascii=False, indent=2)

    # Register output files in DB
    with_cot_record = File(
        user_id=user_id,
        filename=with_cot_filename,
        file_type="json",
        file_path=with_cot_path,
        source_stage=StageEnum.COT_FILTER,
        text_field="input",
    )
    db.add(with_cot_record)

    without_cot_record = File(
        user_id=user_id,
        filename=without_cot_filename,
        file_type="json",
        file_path=without_cot_path,
        source_stage=StageEnum.COT_FILTER,
        text_field="input",
    )
    db.add(without_cot_record)
    db.commit()
    db.refresh(with_cot_record)
    db.refresh(without_cot_record)

    logger.info(
        "COT filter complete: total=%d, with_cot=%d, without_cot=%d, "
        "with_cot_file=%s (id=%d), without_cot_file=%s (id=%d)",
        len(raw_items), len(with_cot), len(without_cot),
        with_cot_filename, with_cot_record.id,
        without_cot_filename, without_cot_record.id,
    )

    return {
        "total": len(raw_items),
        "with_cot_count": len(with_cot),
        "without_cot_count": len(without_cot),
        "with_cot_file_id": with_cot_record.id,
        "with_cot_filename": with_cot_filename,
        "without_cot_file_id": without_cot_record.id,
        "without_cot_filename": without_cot_filename,
        "with_cot_percent": round(len(with_cot) / len(raw_items) * 100, 1) if raw_items else 0,
        "without_cot_percent": round(len(without_cot) / len(raw_items) * 100, 1) if raw_items else 0,
    }