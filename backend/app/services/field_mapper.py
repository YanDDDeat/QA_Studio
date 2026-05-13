"""LLM 返回字段到 Dataset 模型的自动映射器。

核心逻辑：根据 Dataset 表的列定义，动态决定 LLM 返回的 JSON 字段
该写入哪一列。在表列中的写独立列，不在的写入 extra_fields。
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