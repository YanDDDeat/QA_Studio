"""Pre-task validation service for QA Studio.

Validates that JSON files contain the required fields for each pipeline stage
before starting a task. This prevents wasted LLM calls on files that don't
have the necessary data structure.

Each stage defines its required fields. If too few records have all required
fields, the task start is rejected with a clear error message.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("qa_studio.validation_service")

# Required fields per pipeline stage.
# question_generate uses a dynamic text_field (default "text"),
# so it's handled separately.
STAGE_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "knowledge_generate": ["input"],
    "question_validate": ["input"],
    "answer_generate": ["input"],
    "answer_validate": ["input", "output"],
    "data_evaluate": ["input", "output"],
    "cot_filter": ["cot"],
    "dataset_split": ["task_type"],
    "dataset_assessment": ["task_type", "output"],
}


def validate_file_fields(
    file_path: str,
    stage: str,
    text_field: Optional[str] = None,
) -> Tuple[bool, str, Dict]:
    """Validate that a JSON file has the required fields for a given stage.

    Args:
        file_path: Path to the JSON file on disk.
        stage: Pipeline stage name (e.g. "answer_generate").
        text_field: Custom text field name (only for question_generate stage).

    Returns:
        Tuple of (is_valid, error_message, stats_dict).
        - is_valid: True if at least some records have all required fields.
        - error_message: Human-readable description of issues (empty if valid).
        - stats_dict: { total, qualified, missing_fields: {field: count} }
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return False, f"JSON文件解析失败: {str(e)}", {}

    if not isinstance(data, list):
        data = [data]

    total = len(data)
    if total == 0:
        return False, "JSON文件没有记录", {"total": 0, "qualified": 0}

    # Determine required fields for this stage
    if stage == "question_generate":
        required = [text_field or "text"]
    else:
        required = STAGE_REQUIRED_FIELDS.get(stage, [])

    if not required:
        # No specific field requirements — accept any file
        return True, "", {"total": total, "qualified": total, "missing_fields": {}}

    # Count records missing each required field
    missing_counts: Dict[str, int] = {}
    qualified = 0

    for record in data:
        if not isinstance(record, dict):
            # Non-dict records can't have fields
            for field in required:
                missing_counts[field] = missing_counts.get(field, 0) + 1
            continue

        has_all = True
        for field in required:
            value = record.get(field, "")
            # Consider empty string, None, empty list, empty dict as "missing"
            if value is None or value == "" or value == [] or value == {}:
                missing_counts[field] = missing_counts.get(field, 0) + 1
                has_all = False

        if has_all:
            qualified += 1

    stats = {
        "total": total,
        "qualified": qualified,
        "missing_fields": missing_counts,
    }

    if qualified == 0:
        # Build error message listing which fields are missing
        parts = []
        for field, count in missing_counts.items():
            parts.append(f"'{field}' 缺失 {count}/{total} 条")
        msg = f"文件不满足 {stage} 阶段字段要求: {', '.join(parts)}. 至少需要部分记录包含所有必需字段({', '.join(required)})"
        return False, msg, stats

    # Some records qualify — log a warning if some are missing
    if qualified < total:
        parts = []
        for field, count in missing_counts.items():
            if count > 0:
                parts.append(f"'{field}' 缺失 {count} 条")
        logger.info(
            "File %s stage %s: %d/%d records qualify. Missing: %s",
            file_path, stage, qualified, total, ", ".join(parts),
        )

    return True, "", stats