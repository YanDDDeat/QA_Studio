"""LLM 返回字段到 Dataset 模型的自动映射器。

核心逻辑：根据 Dataset 表的列定义，动态决定 LLM 返回的 JSON 字段
该写入哪一列。在表列中的写独立列，不在的写入 extra_fields。

同时提供 Prompt 输入字段的动态拼接：根据 prompt.reference_fields
自动从 Dataset 抽取对应字段的值，拼接为 LLM 输入参考内容。
"""

import json

from app.models.models import Dataset

# 不能从 LLM 结果自动赋值的字段
_SYSTEM_FIELDS = frozenset({
    "id",
    "user_id",
    "file_id",
    "current_stage",
    "created_at",
    "updated_at",
    "extra_fields",
})

# 从 SQLAlchemy 模型动态获取所有可赋值的列名
_DATASET_COLUMNS = frozenset(
    c.name for c in Dataset.__table__.columns
) - _SYSTEM_FIELDS

# -----------------------------------------------------------------
# 各阶段默认参考字段（reference_fields 为空时使用）
# -----------------------------------------------------------------
_STAGE_DEFAULT_FIELDS = {
    "question_generate": [],       # 特殊：读上传 JSON 的 text_content
    "knowledge_generate": ["input", "task_type", "domain"],
    "question_validate": ["input", "knowledge"],
    "answer_generate": ["input", "task_type", "originContent"],
    "answer_validate": ["input", "output", "cot", "knowledge"],
    "data_evaluate": ["input", "output", "cot", "knowledge", "task_type", "domain", "difficulty", "originContent"],
    "quality_check": ["input", "output", "cot", "knowledge", "score", "relevance", "clarity", "reasoning", "terminology"],
    "dataset_assessment": ["input", "output", "cot", "task_type", "domain", "difficulty", "originContent"],
    "generic": [],
}

# 字段名 → 中文标签（用于 Prompt 中显示）
_FIELD_LABELS = {
    "input": "问题",
    "output": "答案",
    "cot": "推理过程",
    "knowledge": "知识体系",
    "domain": "领域",
    "difficulty": "难度",
    "task_type": "任务类型",
    "originContent": "原文",
    "scene": "场景",
    "source": "来源",
    "source_type": "来源类型",
    "step_count": "步骤数",
    "relevance": "相关性",
    "clarity": "清晰度",
    "reasoning": "推理评分",
    "terminology": "术语评分",
    "score": "综合评分",
}


def _resolve_field_name(llm_key: str) -> str | None:
    """将 LLM 返回的字段名解析为数据库列名（支持忽略大小写）。

    优先级：
    1. 直接匹配（大小写敏感）
    2. 忽略大小写匹配
    3. 返回 None 表示无法识别
    """
    if llm_key in _DATASET_COLUMNS:
        return llm_key

    llm_key_lower = llm_key.lower()
    for col in _DATASET_COLUMNS:
        if col.lower() == llm_key_lower:
            return col

    return None


def _serialize_value(value) -> str | None:
    """将值序列化为字符串。

    - 列表 → JSON 字符串
    - 其他 → 直接转为字符串
    - None → None
    """
    if value is None:
        return None
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def apply_llm_fields_to_dataset(ds, llm_result: dict) -> dict:
    """将 LLM 返回的字段自动映射到 Dataset 记录。

    Returns:
        dict: 无法映射到数据库列的字段（作为 extra_fields 存储）
    """
    extra = {}

    for key, value in llm_result.items():
        if key in {"category", "source", "source_id", "source_type",
                   "corpus_cate", "originContent", "passed", "Assessment"}:
            continue

        db_column = _resolve_field_name(key)

        if db_column is not None:
            setattr(ds, db_column, _serialize_value(value))
        else:
            extra[key] = value

    return extra


def build_record_content(ds, reference_fields, stage: str) -> str:
    """根据 reference_fields 从 Dataset 或 dict 抽取字段，拼接为 LLM 参考内容。

    Args:
        ds: Dataset 实例或 dict
        reference_fields: 用户选择的字段列表（如 ["input","output","domain"]），
                         为空时使用 stage 默认字段
        stage: 阶段名（如 "data_evaluate"）

    Returns:
        拼接后的参考内容字符串，格式：
            问题(input): xxx
            答案(output): xxx
            领域(domain): xxx
    """
    fields = reference_fields if reference_fields else _STAGE_DEFAULT_FIELDS.get(stage, [])

    is_dict = isinstance(ds, dict)
    parts = []
    for field in fields:
        value = ds.get(field) if is_dict else getattr(ds, field, None)
        if value is not None and str(value).strip():
            label = _FIELD_LABELS.get(field, field)
            display_value = str(value)
            parts.append(f"{label}({field}): {display_value}")

    return "\n".join(parts)