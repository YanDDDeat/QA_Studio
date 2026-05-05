"""Assessment generation service for QA Studio.

Migrate and adapt assessment logic from QA_Gen_Studio's fill_qa_assessment.py.
For short-answer (简答) QA items, generate Assessment scoring standards via LLM,
with strict validation and repair retry mechanism.

Key design:
- Identifies short-answer items by task_type == "简答"
- Generates scoring standards using LLM (call_llm_json)
- Validates: at least 2 scoring points, total=100, each point has 满分标准/失分规则
- If validation fails, attempts repair with a retry prompt
- Uses create_output_file() for consistent naming and File registration
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.models import File, StageEnum
from app.services.file_service import create_output_file
from app.services.llm_service import call_llm_json, LLMCallError

logger = logging.getLogger("qa_studio.assessment_service")

SHORT_ANSWER_TASK_TYPE = "简答"
TOTAL_SCORE = 100
STEP_SCORE_PATTERN = re.compile(r"(?:步骤|评分点)\s*\d+\s*[（(][^）)]*?(\d+)\s*分\s*[）)]")
TOTAL_SCORE_PATTERN = re.compile(r"总分\s*[：:]\s*(\d+)\s*分")
WEAK_PHRASES_PATTERN = re.compile(r"回答完整即可得分|表述清晰即可得分|酌情给分|视情况给分")

# Default assessment prompt templates (also seeded as Prompt record)
ASSESSMENT_INITIAL_TEMPLATE = """请为下面这条简答题 QA 样本生成 `Assessment` 字段。

任务目标：
- `Assessment` 是对标准答案进行打分的评分细则，不是解析，不是评语。
- 输出必须是一个字符串，并且总分必须严格为100分。

硬性要求：
1. 只能依据【QA样本】中的 `output`、`cot` 和【源文摘录】生成评分标准，不能引入原文或标准答案中没有的数值、条件、结论、机理、公式或扩展要求。
2. 通常拆成 3-6 个评分点；若标准答案信息量明显较少，可拆成 2 个评分点，但仍必须保证每个评分点都可独立判分。
3. 每个评分点都必须写清楚：分值、满分标准、失分规则。
4. 不允许写空话或泛化表述，例如"回答完整即可得分""表述清晰即可得分""视情况给分""酌情给分"。
5. 如果标准答案包含多个并列要点，优先按并列要点拆分评分点；如果是计算/推导型简答，优先按关键计算或判断节点拆分评分点。
6. 如果出现 LaTeX 公式、数学表达式、上下标等，必须单独增加一个评分点检查公式是否正确；若没有公式，不要凭空增加。
7. 评分标准风格要具体，尽量写成可直接判分的步骤式表达。
8. 输出格式固定为单行字符串：评分点1（30分）：……；满分标准：……；失分规则：……。评分点2（40分）：……；满分标准：……；失分规则：……。评分点3（30分）：……；满分标准：……；失分规则：……。总分：100分。
9. 严格返回一个 JSON 对象，不要输出任何额外说明，格式如下：{"Assessment": "评分点1（...）......总分：100分。"}

【QA样本】
{qa_item_json}

【源文摘录】
{origin_content}"""

ASSESSMENT_REPAIR_TEMPLATE = """你上一次生成的 `Assessment` 不合规，请只做修复，不要新增原文中没有的信息。

不合规原因：{repair_reason}

上一版 Assessment：
{invalid_assessment}

请重新输出一个合规版本，并满足以下要求：
1. 必须仍然只依据【QA样本】与【源文摘录】。
2. 必须是单行字符串。
3. 必须包含至少2个评分点，每个评分点都要有分值、满分标准、失分规则。
4. 所有评分点分值之和必须严格等于100，且末尾必须写"总分：100分"。
5. 不能写空话、不能酌情给分、不能引入新知识。
6. 严格返回 JSON 对象：{"Assessment": "..."}

【QA样本】
{qa_item_json}

【源文摘录】
{origin_content}"""


def normalize_assessment_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def get_assessment_value(item: Dict[str, Any]) -> str:
    for key in ("Assessment", "assessment"):
        value = normalize_assessment_text(item.get(key, ""))
        if value:
            return value
    return ""


def validate_assessment_text(text: str) -> Tuple[bool, str]:
    """Validate that an assessment meets all requirements."""
    assessment = normalize_assessment_text(text)
    if not assessment:
        return False, "评分标准为空"

    scoring_points = [int(score) for score in STEP_SCORE_PATTERN.findall(assessment)]
    if len(scoring_points) < 2:
        return False, "评分标准必须包含至少2个评分点"
    if sum(scoring_points) != TOTAL_SCORE:
        return False, "评分点分值之和必须等于100"

    total_match = TOTAL_SCORE_PATTERN.search(assessment)
    if not total_match:
        return False, "评分标准必须包含明确的总分"
    if int(total_match.group(1)) != TOTAL_SCORE:
        return False, "总分必须为100分"

    if assessment.count("满分标准") < len(scoring_points):
        return False, "每个评分点都必须包含满分标准"
    if assessment.count("失分规则") < len(scoring_points):
        return False, "每个评分点都必须包含失分规则"
    if WEAK_PHRASES_PATTERN.search(assessment):
        return False, "评分标准包含模糊表述（酌情给分等）"

    return True, ""


def build_assessment_prompt(item: Dict[str, Any], origin_content: str, prompt_template: str) -> str:
    """Build the initial assessment generation prompt."""
    payload = {
        "id": item.get("id", ""),
        "domain": item.get("domain", ""),
        "category": item.get("category", ""),
        "task_type": item.get("task_type", ""),
        "input": item.get("input", ""),
        "output": item.get("output", ""),
        "cot": item.get("cot", ""),
        "scene": item.get("scene", ""),
        "source": item.get("source", ""),
        "source_id": item.get("source_id", ""),
        "source_type": item.get("source_type", ""),
        "knowledge": item.get("knowledge", []),
        "difficulty": item.get("difficulty", ""),
    }
    return prompt_template.format(
        qa_item_json=json.dumps(payload, ensure_ascii=False, indent=2),
        origin_content=origin_content,
    )


def build_repair_prompt(
    item: Dict[str, Any],
    origin_content: str,
    invalid_assessment: str,
    reason: str,
    repair_template: str,
) -> str:
    """Build the repair prompt for a failed assessment."""
    payload = {
        "id": item.get("id", ""),
        "domain": item.get("domain", ""),
        "category": item.get("category", ""),
        "task_type": item.get("task_type", ""),
        "input": item.get("input", ""),
        "output": item.get("output", ""),
        "cot": item.get("cot", ""),
        "scene": item.get("scene", ""),
        "source": item.get("source", ""),
        "source_id": item.get("source_id", ""),
        "source_type": item.get("source_type", ""),
        "knowledge": item.get("knowledge", []),
        "difficulty": item.get("difficulty", ""),
    }
    return repair_template.format(
        repair_reason=reason,
        invalid_assessment=invalid_assessment,
        qa_item_json=json.dumps(payload, ensure_ascii=False, indent=2),
        origin_content=origin_content,
    )


async def generate_assessment(
    item: Dict[str, Any],
    origin_content: str,
    prompt_template: str,
    repair_template: str,
    model: str,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
) -> Tuple[str, str]:
    """Generate assessment for a single item with validation and repair retry.

    Returns (assessment_text, warning_message). warning_message is empty on success.
    """
    # Initial generation
    try:
        user_prompt = build_assessment_prompt(item, origin_content, prompt_template)
        result = await call_llm_json(
            prompt=user_prompt,
            model=model,
            temperature=0.0,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
        assessment = get_assessment_value(result)
    except (LLMCallError, Exception) as exc:
        return "", f"生成失败: {exc}"

    # Validate
    valid, reason = validate_assessment_text(assessment)
    if valid:
        return assessment, ""

    # Repair attempt
    try:
        repair_prompt = build_repair_prompt(item, origin_content, assessment, reason, repair_template)
        repaired_result = await call_llm_json(
            prompt=repair_prompt,
            model=model,
            temperature=0.0,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
        repaired = get_assessment_value(repaired_result)
    except (LLMCallError, Exception) as exc:
        return "", f"修复失败 ({reason}): {exc}"

    repaired_valid, repaired_reason = validate_assessment_text(repaired)
    if repaired_valid:
        return repaired, ""

    return "", f"修复后仍不合规: {repaired_reason}"


def is_qa_item(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    return all(str(item.get(key, "")).strip() for key in ("task_type", "input", "output"))


def is_short_answer_item(item: Dict[str, Any]) -> bool:
    return is_qa_item(item) and str(item.get("task_type", "")).strip() == SHORT_ANSWER_TASK_TYPE


async def run_assessment_job(
    db: Session,
    user_id: int,
    source_file: File,
    output_name: str,
    username: str,
    prompt_content: str,
    model: str,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
    task_id: int = 0,
    add_task_log=None,
    update_progress=None,
) -> dict:
    """Run assessment generation on a JSON file for short-answer items.

    Args:
        db: Active SQLAlchemy session.
        user_id: The user who owns the output files.
        source_file: The source File record.
        output_name: User-specified base name for output file.
        username: Username for unique filename suffix.
        prompt_content: The prompt template content (from Prompt record).
        model: LLM model name.
        base_url_override: Optional LLM base_url override.
        api_key_override: Optional LLM api_key override.
        task_id: Task ID for progress logging.
        add_task_log: Optional callback for task logging.
        update_progress: Optional callback for progress updates.

    Returns:
        Dict with statistics and output file info.
    """
    # Parse prompt content into initial and repair sections
    initial_template = prompt_content
    repair_template = prompt_content
    repair_marker = "# 修复重写"
    if repair_marker in prompt_content:
        parts = prompt_content.split(repair_marker)
        initial_template = parts[0].strip()
        repair_template = repair_marker + "\n" + parts[1].strip() if len(parts) > 1 else ASSESSMENT_REPAIR_TEMPLATE

    # Read source file
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

    # Process each item
    updated_items = []
    for idx, item in enumerate(raw_items):
        updated_item = dict(item)

        if is_qa_item(item):
            qa_items_count += 1
            existing = get_assessment_value(item)
            updated_item["Assessment"] = existing

            if is_short_answer_item(item) and not existing:
                origin_content = str(item.get("originContent") or "")
                assessment, warning = await generate_assessment(
                    item, origin_content, initial_template, repair_template,
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

    # Create output file via shared factory
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
