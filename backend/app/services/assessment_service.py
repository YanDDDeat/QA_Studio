"""Assessment generation service utilities."""
import re
from typing import Any, Dict

SHORT_ANSWER_TASK_TYPE = "简答"


def normalize_assessment_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def get_assessment_value(item: Dict[str, Any]) -> str:
    for key in ("Assessment", "assessment"):
        value = normalize_assessment_text(item.get(key, ""))
        if value:
            return value
    return ""


def is_qa_item(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    return all(str(item.get(key, "")).strip() for key in ("task_type", "input", "output"))


def is_short_answer_item(item: Dict[str, Any]) -> bool:
    return is_qa_item(item) and str(item.get("task_type", "")).strip() == SHORT_ANSWER_TASK_TYPE
