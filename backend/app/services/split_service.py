"""Dataset Split service for QA Studio.

Split QA records into train/test sets using two strategies:
- difficulty_priority: harder questions prioritized for test set
- task_type_random: proportional random sampling by task type

Key design:
- Reads input JSON file from disk
- Filters valid QA items, works with whatever task types exist in data
- Splits into test/train based on chosen strategy
- Uses create_output_file() for consistent naming and File registration
"""

import json
import logging
import re
from random import Random
from typing import Any, Dict, List, Set, Tuple

from sqlalchemy.orm import Session

from app.models.models import File, StageEnum
from app.services.file_service import create_output_file

logger = logging.getLogger("qa_studio.split_service")

KNOWN_TASK_TYPES = ["单选", "多选", "判断", "填空", "简答"]
SPLIT_STRATEGIES = ["difficulty_priority", "task_type_random"]
DIFFICULTY_PRIORITY = {"较难": 0, "中等": 1, "基础": 2}
UNKNOWN_DIFFICULTY_PRIORITY = 99


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def normalize_task_type(raw: str) -> str:
    val = normalize_space(raw)
    for t in KNOWN_TASK_TYPES:
        if val == t:
            return t
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


def discover_task_types(records: List[Dict[str, Any]]) -> List[str]:
    """Return sorted list of task types actually present in the data."""
    present: Set[str] = set()
    for record in records:
        present.add(record["task_type"])
    known = [t for t in KNOWN_TASK_TYPES if t in present]
    unknown = sorted(t for t in present if t not in KNOWN_TASK_TYPES)
    return known + unknown


def build_grouped_records(records: List[Dict[str, Any]], task_types: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        task_type: [record for record in records if record["task_type"] == task_type]
        for task_type in task_types
    }


def record_sort_key(record: Dict[str, Any]) -> Tuple[int, int]:
    return record["difficulty_rank"], record["index"]


def summarize_task_counts(items: List[Dict[str, Any]]) -> str:
    counts: Dict[str, int] = {}
    for item in items:
        tt = normalize_task_type(item.get("task_type", ""))
        counts[tt] = counts.get(tt, 0) + 1
    known = [f"{t}={counts[t]}" for t in KNOWN_TASK_TYPES if t in counts]
    unknown = [f"{t}={counts[t]}" for t in sorted(counts) if t not in KNOWN_TASK_TYPES]
    return ", ".join(known + unknown)


def validate_records(records: List[Dict[str, Any]], test_count: int) -> List[str]:
    """Validate records and return the list of present task types.
    Raises ValueError only for truly impossible conditions.
    """
    if not records:
        raise ValueError("没有有效的QA记录")

    task_types = discover_task_types(records)

    if test_count > len(records):
        raise ValueError(f"测试集数量({test_count})超过总记录数({len(records)})")

    return task_types


def select_test_records_difficulty_priority(
    records: List[Dict[str, Any]], test_count: int, task_types: List[str]
) -> List[Dict[str, Any]]:
    grouped = build_grouped_records(records, task_types)
    grouped = {
        task_type: sorted(grouped[task_type], key=record_sort_key)
        for task_type in task_types
    }

    selected: List[Dict[str, Any]] = []
    selected_counts = {task_type: 0 for task_type in task_types}

    for task_type in task_types:
        if len(selected) >= test_count:
            break
        record = grouped[task_type][0]
        selected.append(record)
        selected_counts[task_type] += 1

    remaining_candidates: List[Dict[str, Any]] = []
    for task_type in task_types:
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


def allocate_random_task_type_counts(
    grouped: Dict[str, List[Dict[str, Any]]], test_count: int, task_types: List[str]
) -> Dict[str, int]:
    total_records = sum(len(grouped[task_type]) for task_type in task_types)
    target_counts: Dict[str, int] = {}
    fractional_parts: List[Tuple[float, str]] = []

    for task_type in task_types:
        group_size = len(grouped[task_type])
        proportional_target = (test_count * group_size) / total_records
        capped_target = min(group_size - 1, proportional_target) if group_size > 1 else 0
        floor_target = max(0, int(capped_target))
        target_counts[task_type] = floor_target
        fractional_parts.append((capped_target - floor_target, task_type))

    remaining = test_count - sum(target_counts.values())
    while remaining > 0:
        assigned = False
        for _, task_type in sorted(fractional_parts, key=lambda item: (-item[0], task_types.index(item[1]) if item[1] in task_types else 999)):
            max_allowed = len(grouped[task_type]) - 1 if len(grouped[task_type]) > 1 else 0
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


def select_test_records_task_type_random(
    records: List[Dict[str, Any]], test_count: int, task_types: List[str]
) -> List[Dict[str, Any]]:
    grouped = build_grouped_records(records, task_types)
    selected_counts = allocate_random_task_type_counts(grouped, test_count, task_types)
    rng = Random()
    selected: List[Dict[str, Any]] = []
    for task_type in task_types:
        count = selected_counts[task_type]
        if count > 0:
            selected.extend(rng.sample(grouped[task_type], count))
    return sorted(selected, key=lambda record: record["index"])


def select_test_records(
    records: List[Dict[str, Any]], test_count: int, split_strategy: str, task_types: List[str]
) -> List[Dict[str, Any]]:
    if split_strategy == "difficulty_priority":
        return select_test_records_difficulty_priority(records, test_count, task_types)
    if split_strategy == "task_type_random":
        return select_test_records_task_type_random(records, test_count, task_types)
    raise ValueError(f"Unsupported split strategy: {split_strategy}")


def split_items(
    items: List[Dict[str, Any]],
    test_count: int,
    split_strategy: str = "difficulty_priority",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    qa_records: List[Dict[str, Any]] = []
    other_items: List[Dict[str, Any]] = []

    for index, item in enumerate(items):
        if is_qa_item(item):
            qa_records.append(build_record(index, item))
        else:
            other_items.append(item)

    if not qa_records:
        raise ValueError("输入文件中没有有效的QA记录")

    task_types = validate_records(qa_records, test_count)
    test_records = select_test_records(qa_records, test_count, split_strategy, task_types)
    test_indices = {record["index"] for record in test_records}
    train_records = [record for record in qa_records if record["index"] not in test_indices]

    test_items = [{**record["item"], "corpus_cate": 2} for record in test_records]
    train_items = [record["item"] for record in train_records]
    train_items.extend([item for item in other_items if isinstance(item, dict)])
    train_items.extend([item for item in other_items if not isinstance(item, dict)])

    return test_items, train_items, len(other_items)


def run_dataset_split(
    db: Session,
    user_id: int,
    source_file: File,
    output_name: str,
    username: str,
    test_count: int,
    split_strategy: str,
) -> dict:
    """Run dataset split on a JSON file and create train/test output files."""
    with open(source_file.file_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    if not isinstance(raw_items, list):
        raw_items = [raw_items]

    if not raw_items:
        raise ValueError(f"No input items found in file {source_file.filename}")

    test_items, train_items, skipped_non_qa = split_items(raw_items, test_count, split_strategy)

    test_file_record = create_output_file(
        db=db,
        user_id=user_id,
        source_file=source_file,
        stage=StageEnum.DATASET_SPLIT,
        output_filename=output_name,
        username=username,
        name_suffix="test",
        initial_content=test_items,
        text_field="input",
    )

    train_file_record = create_output_file(
        db=db,
        user_id=user_id,
        source_file=source_file,
        stage=StageEnum.DATASET_SPLIT,
        output_filename=output_name,
        username=username,
        name_suffix="train",
        initial_content=train_items,
        text_field="input",
    )

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
        "test_filename": test_file_record.filename,
        "train_file_id": train_file_record.id,
        "train_filename": train_file_record.filename,
        "test_task_counts": test_task_counts,
        "train_task_counts": train_task_counts,
    }
