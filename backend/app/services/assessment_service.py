"""Assessment generation service for QA Studio.

For short-answer (简答) QA items, generate Assessment scoring standards via LLM.
Uses the same Prompt + 参考内容 concatenation pattern as all other pipeline stages.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.models import File, StageEnum
from app.services.file_service import create_output_file
from app.services.field_mapper import build_record_content
from app.services.llm_service import call_llm_json, LLMCallError

logger = logging.getLogger("qa_studio.assessment_service")

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


async def generate_assessment(
    item: Dict[str, Any],
    prompt_content: str,
    reference_fields: Optional[List[str]],
    model: str,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
) -> Tuple[str, str]:
    """Generate assessment for a single item.

    Uses the same pattern as other stages: prompt + 参考内容 concatenation.
    Returns (assessment_text, warning_message).
    """
    record_content = build_record_content(item, reference_fields, "dataset_assessment")
    if not record_content:
        return "", "无参考内容"

    llm_prompt = f"{prompt_content}\n\n---\n\n**参考内容：**\n\n{record_content}"

    try:
        result = await call_llm_json(
            prompt=llm_prompt,
            model=model,
            temperature=0.0,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
        assessment = get_assessment_value(result)
    except (LLMCallError, Exception) as exc:
        return "", f"生成失败: {exc}"

    if not assessment:
        return "", "LLM返回的Assessment为空"

    return assessment, ""


async def run_assessment_job(
    db: Session,
    user_id: int,
    source_file: File,
    output_name: str,
    username: str,
    prompt_content: str,
    model: str,
    reference_fields: Optional[List[str]] = None,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
    task_id: int = 0,
    add_task_log=None,
    update_progress=None,
) -> dict:
    """Run assessment generation on a JSON file for short-answer items."""
    with open(source_file.file_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    if not isinstance(raw_items, list):
        raw_items = [raw_items]

    total_items = len(raw_items)
    qa_items_count = 0
    short_answer_count = sum(1 for item in raw_items if is_short_answer_item(item))
    generated_count = 0
    empty_count = 0

    if add_task_log:
        add_task_log(db, task_id, f"开始评分标准生成: 共 {total_items} 条记录, {short_answer_count} 条简答题")

    updated_items = []
    for idx, item in enumerate(raw_items):
        updated_item = dict(item)

        if is_qa_item(item):
            qa_items_count += 1
            existing = get_assessment_value(item)
            updated_item["Assessment"] = existing

            if is_short_answer_item(item) and not existing:
                assessment, warning = await generate_assessment(
                    item, prompt_content, reference_fields,
                    model, base_url_override, api_key_override,
                )
                updated_item["Assessment"] = normalize_assessment_text(assessment)
                generated_count += 1
                if not assessment:
                    empty_count += 1
                status = "OK" if assessment else "EMPTY"
                if add_task_log:
                    log_msg = f"记录 {idx + 1}: 评分标准={status}"
                    if warning:
                        log_msg += f" ({warning[:100]})"
                    add_task_log(db, task_id, log_msg)
            else:
                updated_item["Assessment"] = normalize_assessment_text(existing)

        updated_items.append(updated_item)

        if update_progress:
            update_progress(db, task_id, idx + 1)

    output_file_record = create_output_file(
        db=db,
        user_id=user_id,
        source_file=source_file,
        stage=StageEnum.DATASET_ASSESSMENT,
        output_filename=output_name,
        username=username,
        name_suffix="assessed",
        initial_content=updated_items,
        text_field="input",
    )

    if add_task_log:
        add_task_log(db, task_id, f"评分标准生成完成: 简答题 {short_answer_count} 条, 成功 {generated_count - empty_count} 条, 空 {empty_count} 条")

    logger.info(
        "Assessment job complete: qa_items=%d, short_answer=%d, generated=%d, empty=%d",
        qa_items_count, short_answer_count, generated_count, empty_count,
    )

    return {
        "qa_items": qa_items_count,
        "short_answer_items": short_answer_count,
        "generated": generated_count,
        "empty_assessment": empty_count,
        "output_file_id": output_file_record.id,
        "output_filename": output_file_record.filename,
    }
