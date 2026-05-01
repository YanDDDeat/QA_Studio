"""Dataset Split service for QA Studio.

Migrate and adapt split logic from QA_Gen_Studio's select_test_set.py.
Split QA records into train/test sets using two strategies:
- difficulty_priority: harder questions prioritized for test set
- task_type_random: proportional random sampling by task type

Key design:
- Reads input JSON file from disk
- Filters valid QA items, validates task types
- Splits into test/train based on chosen strategy
- Writes two output JSON files and registers in File table
"""

import json
import os
import logging
import re
from random import Random
from datetime import datetime
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.models import File, StageEnum

logger = logging.getLogger("qa_studio.split_service")

REQUIRED_TASK_TYPES = ["单选", "多选", "判断", "填空", "简答"]
SPLIT_STRATEGIES = ["difficulty_priority", "task_type_random"]
DIFFICULTY_PRIORITY = {"较难": 0, "中等": 1, "基础": 2}
UNKNOWN_DIFFICULTY_PRIORITY = 99


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def normalize_task_type(raw: str) -> str:
    val = normalize_space(raw)
    for t in REQUIRED_TASK_TYPES:
        if val == t:
            return t
    # Common aliases
    alias_map = {"单选题": "单选", "多选题": "多选", "判断题": "判断", "填空题": "填空", "简答题": "简答"}
    return alias_map.get(val, val)


def normalize_difficulty(raw: str) -> str:
    val = normalize_space(raw)
    if val in DIFFICULTY_PRIORITY:
        return val
    alias_map = {"难": "较难", "中": "中等", "易": "基础", "高": "较难", "低": "基础"}
    return alias_map.get(val, val)


def is_qa_item(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    return all(normalize_space(item.get(key, "")) for key in ("task_type", "input", "output"))


def build_record(index: int, item: Dict[str, Any]) -> Dict[str, Any]:
    task_type = normalize_task_type(item.get("task_type", ""))
    difficulty = normalize_difficulty(item.get("difficulty", ""))
    return {
        "index": index,
        "item": item,
        "task_type": task_type,
        "difficulty": difficulty,
        "difficulty_rank": DIFFICULTY_PRIORITY.get(difficulty, UNKNOWN_DIFFICULTY_PRIORITY),
    }


def build_grouped_records(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        task_type: [record for record in records if record["task_type"] == task_type]
        for task_type in REQUIRED_TASK_TYPES
    }


def record_sort_key(record: Dict[str, Any]) -> Tuple[int, int]:
    return record["difficulty_rank"], record["index"]


def summarize_task_counts(items: List[Dict[str, Any]]) -> str:
    parts = []
    for task_type in REQUIRED_TASK_TYPES:
        count = sum(1 for item in items if normalize_task_type(item.get("task_type", "")) == task_type)
        parts.append(f"{task_type}={count}")
    return ", ".join(parts)


def validate_records(records: List[Dict[str, Any]], test_count: int) -> None:
    if test_count < len(REQUIRED_TASK_TYPES):
        raise ValueError(f"测试集数量必须 >= {len(REQUIRED_TASK_TYPES)} 以覆盖所有题型")

    unsupported = [record for record in records if record["task_type"] not in REQUIRED_TASK_TYPES]
    if unsupported:
        raise ValueError(f"存在不支持的任务类型: {unsupported[0]['task_type']}")

    task_counts = {task_type: 0 for task_type in REQUIRED_TASK_TYPES}
    for record in records:
        task_counts[record["task_type"]] += 1

    missing = [task_type for task_type, count in task_counts.items() if count == 0]
    if missing:
        raise ValueError(f"缺少以下题型: {', '.join(missing)}")

    insufficient = [f"{task_type}={count}" for task_type, count in task_counts.items() if count < 2]
    if insufficient:
        raise ValueError(f"每种题型至少需要2条记录: {', '.join(insufficient)}")

    max_test_count = sum(count - 1 for count in task_counts.values())
    if test_count > max_test_count:
        raise ValueError(f"测试集数量过大，最多可选 {max_test_count} 条")


def select_test_records_difficulty_priority(records: List[Dict[str, Any]], test_count: int) -> List[Dict[str, Any]]:
    grouped = build_grouped_records(records)
    grouped = {
        task_type: sorted(grouped[task_type], key=record_sort_key)
        for task_type in REQUIRED_TASK_TYPES
    }

    selected: List[Dict[str, Any]] = []
    selected_counts = {task_type: 0 for task_type in REQUIRED_TASK_TYPES}

    # Guarantee at least one per task type
    for task_type in REQUIRED_TASK_TYPES:
        record = grouped[task_type][0]
        selected.append(record)
        selected_counts[task_type] += 1

    # Fill remaining by difficulty priority
    remaining_candidates: List[Dict[str, Any]] = []
    for task_type in REQUIRED_TASK_TYPES:
        remaining_candidates.extend(grouped[task_type][1:])

    for record in sorted(remaining_candidates, key=record_sort_key):
        if len(selected) >= test_count:
            break
        task_type = record["task_type"]
        total_in_group = len(grouped[task_type])
        if selected_counts[task_type] >= total_in_group - 1:
            continue
        selected.append(record)
        selected_counts[task_type] += 1

    if len(selected) != test_count:
        raise ValueError("无法满足测试集数量要求，同时保持各题型约束")
    return sorted(selected, key=lambda record: record["index"])


def allocate_random_task_type_counts(grouped: Dict[str, List[Dict[str, Any]]], test_count: int) -> Dict[str, int]:
    total_records = sum(len(grouped[task_type]) for task_type in REQUIRED_TASK_TYPES)
    target_counts = {task_type: 1 for task_type in REQUIRED_TASK_TYPES}
    fractional_parts: List[Tuple[float, str]] = []

    for task_type in REQUIRED_TASK_TYPES:
        group_size = len(grouped[task_type])
        proportional_target = (test_count * group_size) / total_records
        capped_target = min(group_size - 1, proportional_target)
        floor_target = max(1, int(capped_target))
        target_counts[task_type] = floor_target
        fractional_parts.append((capped_target - floor_target, task_type))

    remaining = test_count - sum(target_counts.values())
    while remaining > 0:
        assigned = False
        for _, task_type in sorted(
            fractional_parts,
            key=lambda item: (-item[0], REQUIRED_TASK_TYPES.index(item[1])),
        ):
            max_allowed = len(grouped[task_type]) - 1
            if target_counts[task_type] >= max_allowed:
                continue
            target_counts[task_type] += 1
            remaining -= 1
            assigned = True
            if remaining == 0:
                break
        if not assigned:
            raise ValueError("无法分配剩余的随机切分名额")

    return target_counts


def select_test_records_task_type_random(records: List[Dict[str, Any]], test_count: int) -> List[Dict[str, Any]]:
    grouped = build_grouped_records(records)
    selected_counts = allocate_random_task_type_counts(grouped, test_count)
    rng = Random()
    selected: List[Dict[str, Any]] = []
    for task_type in REQUIRED_TASK_TYPES:
        selected.extend(rng.sample(grouped[task_type], selected_counts[task_type]))
    return sorted(selected, key=lambda record: record["index"])


def select_test_records(records: List[Dict[str, Any]], test_count: int, split_strategy: str = "difficulty_priority") -> List[Dict[str, Any]]:
    if split_strategy == "difficulty_priority":
        return select_test_records_difficulty_priority(records, test_count)
    if split_strategy == "task_type_random":
        return select_test_records_task_type_random(records, test_count)
    raise ValueError(f"Unsupported split strategy: {split_strategy}")


def split_items(
    items: List[Dict[str, Any]],
    test_count: int,
    split_strategy: str = "difficulty_priority",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    qa_records: List[Dict[str, Any]] = []
    skipped_non_qa = 0

    for index, item in enumerate(items):
        if is_qa_item(item):
            qa_records.append(build_record(index, item))
        else:
            skipped_non_qa += 1

    if not qa_records:
        raise ValueError("输入文件中没有有效的QA记录")

    validate_records(qa_records, test_count)
    test_records = select_test_records(qa_records, test_count, split_strategy)
    test_indices = {record["index"] for record in test_records}
    train_records = [record for record in qa_records if record["index"] not in test_indices]

    test_items = [{**record["item"], "corpus_cate": 2} for record in test_records]
    train_items = [{**record["item"], "corpus_cate": 0} for record in train_records]
    return test_items, train_items, skipped_non_qa


def run_dataset_split(
    db: Session,
    user_id: int,
    source_file: File,
    output_name: str,
    username: str,
    test_count: int,
    split_strategy: str,
) -> dict:
    """Run dataset split on a JSON file and create train/test output files.

    Args:
        db: Active SQLAlchemy session.
        user_id: The user who owns the output files.
        source_file: The source File record to split.
        output_name: User-specified base name for output files.
        username: Username for unique filename suffix.
        test_count: Number of items to place in the test set.
        split_strategy: 'difficulty_priority' or 'task_type_random'.

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

    # Split
    test_items, train_items, skipped_non_qa = split_items(raw_items, test_count, split_strategy)

    # Build output filenames
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix_name = username or str(user_id)
    upload_dir = os.path.join("uploads", str(user_id))
    os.makedirs(upload_dir, exist_ok=True)

    test_filename = f"{output_name}_{suffix_name}_{timestamp}_test.json"
    test_path = os.path.join(upload_dir, test_filename)

    train_filename = f"{output_name}_{suffix_name}_{timestamp}_train.json"
    train_path = os.path.join(upload_dir, train_filename)

    # Write output files
    with open(test_path, "w", encoding="utf-8") as f:
        json.dump(test_items, f, ensure_ascii=False, indent=2)

    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(train_items, f, ensure_ascii=False, indent=2)

    # Register output files in DB
    test_file_record = File(
        user_id=user_id,
        filename=test_filename,
        file_type="json",
        file_path=test_path,
        source_stage=StageEnum.DATASET_SPLIT,
        text_field="input",
    )
    db.add(test_file_record)

    train_file_record = File(
        user_id=user_id,
        filename=train_filename,
        file_type="json",
        file_path=train_path,
        source_stage=StageEnum.DATASET_SPLIT,
        text_field="input",
    )
    db.add(train_file_record)
    db.commit()
    db.refresh(test_file_record)
    db.refresh(train_file_record)

    test_task_counts = summarize_task_counts(test_items)
    train_task_counts = summarize_task_counts(train_items)

    logger.info(
        "Dataset split complete: strategy=%s, test=%d, train=%d, skipped=%d",
        split_strategy, len(test_items), len(train_items), skipped_non_qa,
    )

    return {
        "test_count": len(test_items),
        "train_count": len(train_items),
        "skipped_non_qa": skipped_non_qa,
        "split_strategy": split_strategy,
        "test_file_id": test_file_record.id,
        "test_filename": test_filename,
        "train_file_id": train_file_record.id,
        "train_filename": train_filename,
        "test_task_counts": test_task_counts,
        "train_task_counts": train_task_counts,
    }