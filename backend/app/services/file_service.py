"""Shared file output service for QA Studio pipeline stages.

每个 Pipeline 阶段执行成功都会产出一个新的 File 记录 + 物理 JSON 文件，
原输入文件（File 与磁盘内容）始终保持不变。

Key design:
- write_datasets_to_file(): 把指定 file_id 下的 Dataset 列表序列化为 JSON 写入新输出文件，绝不覆盖输入文件
- create_output_file(stage=...): 通用化的新 File 工厂，所有阶段共享
- clone_datasets_to_new_file(): 把源 file_id 的 Dataset 克隆到新 file_id，方便阶段独立回溯
- create_fail_file(): 校验阶段产出的失败记录文件
- serialize_dataset_to_dict(): 把 Dataset ORM 转为可 JSON 序列化的 dict

文件按 stage 自动带中文阶段标签，统一命名规则：
    {base}_{阶段中文}_{username|user_id}_{YYYYMMDDHHmmss}{_suffix?}.json
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.models import Dataset, File, StageEnum

logger = logging.getLogger("qa_studio.file_service")

# ---------------------------------------------------------------------------
# Stage label mapping (Chinese display names)
# ---------------------------------------------------------------------------

STAGE_LABELS = {
    StageEnum.QUESTION_GENERATE: "问题生成",
    StageEnum.KNOWLEDGE_GENERATE: "知识体系",
    StageEnum.QUESTION_VALIDATE: "问题校验",
    StageEnum.ANSWER_GENERATE: "答案生成",
    StageEnum.ANSWER_VALIDATE: "答案校验",
    StageEnum.DATA_EVALUATE: "数据评估",
    StageEnum.QUALITY_CHECK: "质检",
    StageEnum.COT_FILTER: "COT过滤",
    StageEnum.DATASET_SPLIT: "数据集切分",
    StageEnum.DATASET_ASSESSMENT: "评分标准生成",
    StageEnum.GENERIC: "通用生成",
    StageEnum.COT_HCOT_PIPELINE: "CoT标注",
}


# ---------------------------------------------------------------------------
# Dataset serialization
# ---------------------------------------------------------------------------

# All Dataset columns in the order they should appear in the JSON deliverable.
# Internal columns (id, user_id, file_id, created_at, updated_at) are excluded.

_SERIALIZABLE_FIELDS = [
    "id",
    "domain",
    "category",
    "task_type",
    "input",
    "output",
    "cot",
    "step_count",
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
    "extra_fields",
]

# Dataset columns that get cloned when creating a new-stage copy of a record.
_CLONABLE_FIELDS = [
    "domain",
    "category",
    "task_type",
    "input",
    "output",
    "cot",
    "step_count",
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
    "extra_fields",
]


def ensure_datasets_for_file(db: Session, file_id: int, user_id: int) -> list:
    """Query Dataset rows for file_id. If none exist (uploaded file), create them from the JSON file on disk.

    Returns list of Dataset objects.
    """
    source_datasets = (
        db.query(Dataset)
        .filter(Dataset.file_id == file_id, Dataset.user_id == user_id)
        .order_by(Dataset.id.asc())
        .all()
    )

    if source_datasets:
        return source_datasets

    # No Dataset rows — this is a directly uploaded file. Read JSON and create rows.
    file_obj = db.query(File).filter(File.id == file_id).first()
    if not file_obj:
        return []

    try:
        with open(file_obj.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    if not isinstance(data, list):
        data = [data]

    if not data:
        return []

    # Known Dataset column names that can be mapped from JSON
    _IMPORTABLE_FIELDS = {
        "domain", "category", "task_type", "input", "output", "cot",
        "step_count", "corpus_cate", "scene", "Assessment", "source",
        "source_id", "source_type", "originContent", "knowledge",
        "difficulty", "relevance", "clarity", "reasoning", "terminology",
        "score", "passed",
    }

    # Aliases (LLM-friendly names -> canonical column names)
    _ALIASES = {
        "question": "input",
        "answer": "output",
        "reasoning": "cot",
        "content": "originContent",
        "text": "originContent",
    }

    _CASE_INSENSITIVE_IMPORT_FIELDS = {
        "relevance",
        "clarity",
        "reasoning",
        "terminology",
        "score",
    }

    def _is_number_like(value) -> bool:
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                float(value.strip())
                return True
            except ValueError:
                return False
        return False

    def _resolve_import_field(key: str, value) -> str | None:
        if str(key).lower() == "reasoning" and _is_number_like(value):
            return "reasoning"

        canonical = _ALIASES.get(key, key)
        if canonical in _IMPORTABLE_FIELDS:
            return canonical

        canonical_lower = str(canonical).lower()
        if canonical_lower in _CASE_INSENSITIVE_IMPORT_FIELDS:
            return canonical_lower

        return None

    for record in data:
        if not isinstance(record, dict):
            continue

        kwargs = {}
        extra = {}

        for key, value in record.items():
            canonical = _resolve_import_field(key, value)
            if canonical is not None:
                if isinstance(value, (list, dict)):
                    kwargs[canonical] = json.dumps(value, ensure_ascii=False)
                elif value is not None:
                    kwargs[canonical] = str(value)
            else:
                # Skip internal fields
                if key not in ("id", "user_id", "file_id", "current_stage", "created_at", "updated_at"):
                    extra[key] = value

        ds = Dataset(
            user_id=user_id,
            file_id=file_id,
            current_stage=None,  # uploaded, not from any stage
            **kwargs,
        )
        if extra:
            ds.extra_fields = extra
        db.add(ds)

    db.commit()

    # Re-query to get IDs
    return (
        db.query(Dataset)
        .filter(Dataset.file_id == file_id, Dataset.user_id == user_id)
        .order_by(Dataset.id.asc())
        .all()
    )


def clone_single_dataset(db: Session, source: Dataset, new_file_id: int, new_stage: StageEnum) -> Dataset:
    """Clone one Dataset to a new file. Flushes but does NOT commit."""
    kwargs = {field: getattr(source, field) for field in _CLONABLE_FIELDS}
    new_record = Dataset(
        user_id=source.user_id,
        file_id=new_file_id,
        current_stage=new_stage,
        **kwargs,
    )
    db.add(new_record)
    db.flush()
    return new_record


def serialize_dataset_to_dict(dataset: Dataset) -> dict:
    """Convert a Dataset ORM object to a dict suitable for JSON serialization.

    Only includes fields that have been populated (not None).
    Special handling:
    - knowledge (JSON column): serialize as-is (dict/list), never double-encoded
    - extra_fields (JSON column): serialize as-is, never double-encoded
    - score (Float): serialize as number, not string
    - current_stage (Enum): serialize as its string value
    - Assessment (default ""): included even when empty
    - corpus_cate (default 1): included even when default
    """
    result = {}
    for field in _SERIALIZABLE_FIELDS:
        value = getattr(dataset, field, None)

        if value is None:
            continue

        if field in ("knowledge", "extra_fields"):
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass
            result[field] = value

        elif field == "current_stage":
            result[field] = value.value if hasattr(value, "value") else str(value)

        elif field == "score":
            result[field] = float(value)

        else:
            result[field] = value

    return result


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------


def _build_output_filename(
    source_filename: str,
    stage: StageEnum,
    output_filename: Optional[str],
    username_or_id: str,
    name_suffix: Optional[str] = None,
) -> str:
    """构造输出文件名：{base首段}_{username}_{时间}{_suffix?}.json

    base 取源文件名按 '_' 切割后的第一段，保持文件名简短。
    """
    if output_filename:
        raw_base = os.path.splitext(output_filename)[0]
    else:
        raw_base = os.path.splitext(source_filename or "output")[0]

    base = raw_base.split("_")[0] if "_" in raw_base else raw_base

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix_part = f"_{name_suffix}" if name_suffix else ""
    return f"{base}_{username_or_id}_{timestamp}{suffix_part}.json"



def _resolve_unique_path(upload_dir: str, filename: str) -> tuple[str, str]:
    """若文件名冲突则追加 _1 / _2 … 直至可用，返回 (final_filename, final_path)。"""
    file_path = os.path.join(upload_dir, filename)
    if not os.path.exists(file_path):
        return filename, file_path

    base, ext = os.path.splitext(filename)
    counter = 1
    while True:
        candidate_filename = f"{base}_{counter}{ext}"
        candidate_path = os.path.join(upload_dir, candidate_filename)
        if not os.path.exists(candidate_path):
            return candidate_filename, candidate_path
        counter += 1


# ---------------------------------------------------------------------------
# Core write-back function
# ---------------------------------------------------------------------------


def write_datasets_to_file(db: Session, file_id: int) -> str:
    """读取 file_id 关联的 Dataset 列表，序列化为 JSON 写入对应输出文件。

    始终写入指定 file_id 对应的输出文件，绝不覆盖输入文件。

    Args:
        db: Active SQLAlchemy session.
        file_id: 要写入的输出 File 记录 ID。

    Returns:
        写入磁盘的文件路径。
    """
    file_obj = db.query(File).filter(File.id == file_id).first()
    if file_obj is None:
        raise ValueError(f"File record with id={file_id} not found")

    datasets = (
        db.query(Dataset)
        .filter(Dataset.file_id == file_id)
        .order_by(Dataset.id.asc())
        .all()
    )

    items = [serialize_dataset_to_dict(d) for d in datasets]

    file_path = file_obj.file_path
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    logger.info(
        "Written %d datasets to file %s (file_id=%d)",
        len(items), file_path, file_id,
    )

    return file_path


def repair_file_on_disk(db: Session, file_id: int) -> bool:
    """如果 File 下有 Dataset 但磁盘文件为空，自动补写。

    Returns:
        True if repair was performed, False otherwise.
    """
    file_obj = db.query(File).filter(File.id == file_id).first()
    if file_obj is None:
        return False

    # 检查磁盘文件是否存在且为空
    if not os.path.exists(file_obj.file_path):
        logger.info("repair: file_id=%d 磁盘文件不存在，无需修复", file_id)
        return False

    file_size = os.path.getsize(file_obj.file_path)
    # 只有空数组或极小文件才修复（正常文件都会有内容）
    if file_size > 5:
        return False

    datasets_count = (
        db.query(Dataset)
        .filter(Dataset.file_id == file_id)
        .count()
    )
    if datasets_count == 0:
        return False

    logger.info("repair: file_id=%d 磁盘文件为空但DB有%d条Dataset，补写文件",
                file_id, datasets_count)
    try:
        write_datasets_to_file(db, file_id)
        return True
    except Exception as e:
        logger.error("repair: file_id=%d 修复失败: %s", file_id, str(e))
        return False


# ---------------------------------------------------------------------------
# Output file creation (general purpose for all stages)
# ---------------------------------------------------------------------------


def create_output_file(
    db: Session,
    user_id: int,
    source_file: File,
    stage: Optional[StageEnum] = None,
    output_filename: Optional[str] = None,
    username: Optional[str] = None,
    name_suffix: Optional[str] = None,
    initial_content: Optional[object] = None,
    text_field: Optional[str] = None,
    stage_name: Optional[str] = None,
) -> File:
    """通用输出 File 工厂：所有阶段共享。

    新建 File 记录 + 物理空文件（默认空数组），文件名带阶段中文标签。

    Args:
        db: Active SQLAlchemy session.
        user_id: 文件归属的用户 id。
        source_file: 原始（输入）File 记录，用于命名 base 与 text_field 继承。
        stage: 当前阶段枚举（必填，决定 source_stage 与文件名标签）。
        output_filename: 用户指定的 base 名（去扩展），若空则取 source_file.filename 去扩展。
        username: 用户名，用于文件名后缀；不传则退回 user_id 字符串。
        name_suffix: 可选附加后缀（如 'train'/'test'/'cot'/'no_cot'/'assessed'）。
        initial_content: 写入磁盘的初始 JSON 内容，默认空数组 []；若调用方需要先写真实内容可传入。
        text_field: 显式覆盖 text_field，默认沿用源文件 text_field（若源 text_field 空则 'input'）。
        stage_name: 仅为兼容旧调用（已废弃）。当 stage 为空且传入 stage_name 时，回退为 QUESTION_GENERATE。

    Returns:
        新建并已 commit 的 File 记录。
    """
    if stage is None:
        if stage_name is not None:
            logger.warning("create_output_file 调用方仅传入了 stage_name，回退为 QUESTION_GENERATE")
            stage = StageEnum.QUESTION_GENERATE
        else:
            raise ValueError("create_output_file 必须传入 stage 参数")

    suffix_name = username or str(user_id)

    upload_dir = os.path.join("uploads", str(user_id))
    os.makedirs(upload_dir, exist_ok=True)

    desired_filename = _build_output_filename(
        source_filename=source_file.filename if source_file else "output",
        stage=stage,
        output_filename=output_filename,
        username_or_id=suffix_name,
        name_suffix=name_suffix,
    )
    filename, file_path = _resolve_unique_path(upload_dir, desired_filename)

    payload = initial_content if initial_content is not None else []
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    resolved_text_field = text_field
    if not resolved_text_field:
        resolved_text_field = (source_file.text_field if source_file else None) or "input"

    file_record = File(
        user_id=user_id,
        filename=filename,
        file_type="json",
        file_path=file_path,
        source_stage=stage,
        text_field=resolved_text_field,
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    logger.info(
        "Created output file %s (file_id=%d, stage=%s) from source %s",
        filename, file_record.id, stage.value,
        source_file.filename if source_file else "<none>",
    )

    return file_record


# ---------------------------------------------------------------------------
# Dataset cloning helper
# ---------------------------------------------------------------------------


def clone_datasets_to_new_file(
    db: Session,
    source_file_id: int,
    new_file_id: int,
    user_id: int,
    source_stage_filter: StageEnum,
    new_stage: StageEnum,
    passed_filter: Optional[str] = None,
    dataset_ids: Optional[Iterable[int]] = None,
) -> List[Dataset]:
    """把源 file_id 下满足条件的 Dataset 克隆到新 file_id，原记录不动。

    Args:
        db: Active SQLAlchemy session.
        source_file_id: 源 File 记录 id。
        new_file_id: 新建输出 File 记录 id（克隆目标）。
        user_id: 数据归属用户 id。
        source_stage_filter: 原 Dataset 的 current_stage 必须等于此值。
        new_stage: 新克隆 Dataset 的 current_stage 值。
        passed_filter: 可选，原 Dataset.passed == 此值（如 "是"）。
        dataset_ids: 可选 dataset.id 白名单；传则仅克隆这些 id 的记录。

    Returns:
        新建并已 commit 的 Dataset 列表（按 id 升序与源记录一致）。
    """
    query = (
        db.query(Dataset)
        .filter(
            Dataset.file_id == source_file_id,
            Dataset.user_id == user_id,
            Dataset.current_stage == source_stage_filter,
        )
    )
    if passed_filter is not None:
        query = query.filter(Dataset.passed == passed_filter)
    if dataset_ids is not None:
        ids_list = [i for i in dataset_ids]
        if not ids_list:
            return []
        query = query.filter(Dataset.id.in_(ids_list))

    source_records = query.order_by(Dataset.id.asc()).all()
    if not source_records:
        return []

    cloned: List[Dataset] = []
    for src in source_records:
        kwargs = {field: getattr(src, field) for field in _CLONABLE_FIELDS}
        new_record = Dataset(
            user_id=user_id,
            file_id=new_file_id,
            current_stage=new_stage,
            **kwargs,
        )
        db.add(new_record)
        cloned.append(new_record)

    db.commit()
    for record in cloned:
        db.refresh(record)

    logger.info(
        "Cloned %d datasets from file_id=%d to file_id=%d (new_stage=%s)",
        len(cloned), source_file_id, new_file_id, new_stage.value,
    )

    return cloned


# ---------------------------------------------------------------------------
# Fail file creation (validation stages)
# ---------------------------------------------------------------------------

# 校验阶段失败文件后缀
_FAIL_SUFFIXES = {
    StageEnum.QUESTION_VALIDATE: "问题校验失败",
    StageEnum.ANSWER_VALIDATE: "答案校验失败",
    StageEnum.QUALITY_CHECK: "质检失败",
}


def create_fail_file(
    db: Session,
    user_id: int,
    source_file: File,
    stage: StageEnum,
    fail_records: list,
) -> File:
    """为校验阶段产出汇总的失败记录 JSON 文件。

    Args:
        db: Active SQLAlchemy session.
        user_id: The user who owns the file.
        source_file: 源 JSON File 记录（用于派生命名）。
        stage: 校验阶段枚举（QUESTION_VALIDATE 或 ANSWER_VALIDATE）。
        fail_records: 失败记录 dict 列表，每条带 validation_result + reason。

    Returns:
        新建的 File 记录。
    """
    if not fail_records:
        raise ValueError("fail_records must not be empty")

    suffix = _FAIL_SUFFIXES.get(stage)
    if suffix is None:
        raise ValueError(f"Stage {stage} does not produce fail files")

    source_base = os.path.splitext(source_file.filename)[0]
    desired_filename = f"{source_base}_{suffix}.json"

    upload_dir = os.path.join("uploads", str(user_id))
    os.makedirs(upload_dir, exist_ok=True)

    filename, file_path = _resolve_unique_path(upload_dir, desired_filename)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(fail_records, f, ensure_ascii=False, indent=2)

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
