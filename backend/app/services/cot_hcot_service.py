"""CoT/H-CoT Pipeline service.

Manages the multi-step workflow for generating CoT/H-CoT training data from
research papers.  Each workflow is a parent Task (stage=COT_HCOT_PIPELINE)
with sub-tasks linked via parent_task_id.

H-CoT mode (博士论文):
  Phase 1 (per-chunk): fact_card_gen → 每个 chunk 生成事实卡
  Phase 2 (document):  merge_fact_cards → 合并所有 chunk 事实卡
                       sanitize → 数值抽象（全文事实卡）
                       l0_gen → L0 总问题数组（可能多个）
  Phase 3 (per-L0):    l1_decompose → L1 拆解（每个总问题）
                       l2_decompose → L2 拆解
                       l2_cot → L2 CoT 生成
                       l1_cot → L1 CoT 生成
                       l0_cot → L0 CoT 生成
  Phase 4 (document):  quality_check → 最终质检
                       export_jsonl → 导出训练数据（多棵 H-CoT 树）

CoT mode (研究论文):
  Phase 1 (per-chunk): fact_card_gen → 每个 chunk 生成事实卡
  Phase 2 (document):  merge_fact_cards → 合并所有 chunk 事实卡
                       sanitize → 数值抽象
                       question_gen → 独立问题生成
                       cot_gen → 独立 CoT 生成
  Phase 3 (document):  quality_check → 最终质检
                       export_jsonl → 导出训练数据
"""

import asyncio
import json
import logging
import os
import traceback
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import (
    File, LLMConfig, Prompt, Task, TaskLog, TaskStatusEnum, StageEnum, User,
)
from app.services.llm_service import call_llm_json_sync, LLMCallError
from app.services.file_service import (
    create_output_file, write_datasets_to_file, ensure_datasets_for_file,
)
from app.services.thread_pool import (
    register_task, unregister_task,
)

logger = logging.getLogger("qa_studio.cot_hcot_service")

# ---------------------------------------------------------------------------
# Step name → prompt template key mapping
# ---------------------------------------------------------------------------

def step_name_to_prompt_key(step_name: str) -> str:
    """Map pipeline step_name to H-CoT prompt template key."""
    common_steps = ("fact_card_gen", "sanitize", "quality_check")
    hcot_steps = ("l0_gen", "l1_decompose", "l2_decompose", "l2_cot", "l1_cot", "l0_cot")
    cot_steps = ("question_gen", "cot_gen")
    if step_name in common_steps:
        return f"common.{step_name}"
    if step_name in hcot_steps:
        return f"hcot.{step_name}"
    if step_name in cot_steps:
        return f"cot.{step_name}"
    raise ValueError(f"Unknown step_name: {step_name}")


def resolve_step_prompt_from_template(user_id: int, template_id: str, step_name: str) -> Optional[str]:
    """Read prompt content from an H-CoT template for a given step."""
    from app.services.hcot_prompt_template_service import (
        resolve_template_for_run, get_prompt_item,
    )
    try:
        prompt_key = step_name_to_prompt_key(step_name)
        resolved = resolve_template_for_run(user_id, template_id)
        item = get_prompt_item(resolved["template_id"], user_id, prompt_key)
        return item["content"]
    except Exception as e:
        logger.warning(f"Template prompt resolution failed for {step_name}: {e}")
        return None

# ---------------------------------------------------------------------------
# Pipeline step definitions
# ---------------------------------------------------------------------------

# Step metadata:
#   key = step_name
#   value = (display_name, prompt_name_pattern, input_sources, is_hcot_only, granularity)
#
# input_sources: dict mapping prompt placeholder → source step_name
#   e.g. {"content": None} means use source_file (no prior step)
#   e.g. {"fact_cards": "fact_card_gen"} means use fact_card_gen's output file
#   e.g. {"l1_input": "l1_decompose", "l2_cots": "l2_cot"} means combine two inputs
#
# None as source step means "use the pipeline's source_file" (the original paper)
#
# granularity: "per_chunk" → one sub-task per chunk, "document" → one sub-task for the whole doc,
#              "per_l0" → one sub-task per L0 question

PIPELINE_STEPS = {
    "fact_card_gen":      ("1. 事实卡生成",     "[CoT/H-CoT] 1. 事实卡生成",      {"content": None},                         False, "per_chunk"),
    "merge_fact_cards":   ("2. 合并事实卡",     None,                              None,                                      False, "document"),   # 纯数据合成，不调LLM，类似export_jsonl
    "sanitize":           ("3. 数值抽象",        "[CoT/H-CoT] 2. 数值抽象",        {"fact_cards": "merge_fact_cards"},        False, "document"),   # 输入改为 merge_fact_cards（合并后的全文事实卡）
    "l0_gen":             ("4. L0 总问题生成",   "[H-CoT] 3. L0 总问题生成",       {"fact_cards_sanitized": "sanitize"},      True,  "document"),
    "l1_decompose":       ("5. L1 拆解",         "[H-CoT] 4. L1 拆解",             {"l0_input": "l0_gen", "fact_cards_sanitized": "sanitize"}, True, "per_l0"),
    "l2_decompose":       ("6. L2 拆解",         "[H-CoT] 5. L2 拆解",             {"l1_input": "l1_decompose", "fact_cards_sanitized": "sanitize"}, True, "per_l0"),
    "l2_cot":             ("7. L2 CoT 生成",     "[H-CoT] 6. L2 CoT 生成",         {"l2_input": "l2_decompose", "fact_cards_sanitized": "sanitize"}, True, "per_l0"),
    "l1_cot":             ("8. L1 CoT 生成",     "[H-CoT] 7. L1 CoT 生成",         {"l1_input": "l1_decompose", "l2_cots": "l2_cot"}, True, "per_l0"),
    "l0_cot":             ("9. L0 CoT 生成",     "[H-CoT] 8. L0 CoT 生成",         {"l0_input": "l0_gen", "l1_cots": "l1_cot", "l2_cots": "l2_cot"}, True, "per_l0"),
    "question_gen":       ("4. 独立问题生成",     "[CoT] 3. 独立问题生成",           {"fact_cards_sanitized": "sanitize"},      False, "document"),
    "cot_gen":            ("5. 独立 CoT 生成",    "[CoT] 4. 独立 CoT 生成",          {"question_input": "question_gen", "fact_cards_sanitized": "sanitize"}, False, "document"),
    "quality_check":      ("最终质检",            "[CoT/H-CoT] 最终质检",            {"cots": None},                            False, "document"),
    "export_jsonl":       ("导出训练数据",        None,                              None,                                      False, "document"),
}

PIPELINE_STEP_PHASES = {
    "fact_card_gen": [
        (0, 5, "读取源文件"),
        (5, 10, "组装提示词"),
        (10, 85, "调用 LLM 生成事实卡"),
        (85, 95, "解析 LLM 输出"),
        (95, 100, "写入输出文件"),
    ],
    "merge_fact_cards": [
        (0, 30, "读取所有 chunk 事实卡"),
        (30, 70, "合并事实卡数据"),
        (70, 100, "写入合并文件"),
    ],
    "sanitize": [
        (0, 5, "读取事实卡"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 数值抽象"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "l0_gen": [
        (0, 5, "读取去数值事实卡"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 生成 L0 总问题"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "l1_decompose": [
        (0, 5, "读取 L0 和事实卡"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 拆解 L1"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "l2_decompose": [
        (0, 5, "读取 L1 和事实卡"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 拆解 L2"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "l2_cot": [
        (0, 5, "读取 L2 问题和事实卡"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 生成 L2 CoT"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "l1_cot": [
        (0, 5, "读取 L1 问题和 L2 CoT"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 生成 L1 CoT"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "l0_cot": [
        (0, 5, "读取 L0 和 L1 CoT"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 生成 L0 CoT"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "question_gen": [
        (0, 5, "读取去数值事实卡"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 生成独立问题"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "cot_gen": [
        (0, 5, "读取问题和事实卡"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 生成独立 CoT"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "quality_check": [
        (0, 5, "读取 CoT 数据"),
        (5, 10, "组装提示词"),
        (10, 80, "调用 LLM 执行质检"),
        (80, 95, "解析输出"),
        (95, 100, "写入输出文件"),
    ],
    "export_jsonl": [
        (0, 30, "读取所有中间步骤数据"),
        (30, 70, "合成层级树 + 训练样本"),
        (70, 100, "写入最终文件"),
    ],
}

# Ordered step sequences per mode
HCOT_STEP_ORDER = [
    "fact_card_gen", "merge_fact_cards", "sanitize", "l0_gen", "l1_decompose", "l2_decompose",
    "l2_cot", "l1_cot", "l0_cot", "quality_check", "export_jsonl",
]

COT_STEP_ORDER = [
    "fact_card_gen", "merge_fact_cards", "sanitize", "question_gen", "cot_gen", "quality_check", "export_jsonl",
]


def get_step_order(mode: str) -> List[str]:
    """Return ordered step list for the given pipeline mode."""
    if mode == "hcot":
        return HCOT_STEP_ORDER
    elif mode == "cot":
        return COT_STEP_ORDER
    else:
        raise ValueError(f"Unknown pipeline mode: {mode}")


def get_next_step(mode: str, completed_steps: List[str]) -> Optional[str]:
    """Return the next step name after all completed_steps, or None if done."""
    order = get_step_order(mode)
    for step in order:
        if step not in completed_steps:
            return step
    return None


# ---------------------------------------------------------------------------
# Prompt resolution
# ---------------------------------------------------------------------------

def find_prompt_for_step(db: Session, step_name: str, user_id: int, template_id: Optional[str] = None) -> Optional[Prompt]:
    """Find the default Prompt for a given pipeline step.

    If template_id is provided, try to resolve from H-CoT template first.
    Fallback to database Prompt table for backward compatibility.
    """
    if step_name not in PIPELINE_STEPS:
        return None

    _, prompt_pattern, _, _, _ = PIPELINE_STEPS[step_name]

    # export_jsonl has no prompt
    if prompt_pattern is None:
        return None

    # Try template-based resolution first
    if template_id:
        prompt_content = resolve_step_prompt_from_template(user_id, template_id, step_name)
        if prompt_content:
            # Return a synthetic Prompt object — prompt_id=None so it won't violate FK constraint
            # The actual prompt content comes from the template, not from the DB
            return Prompt(
                id=None,
                name=prompt_pattern,
                content=prompt_content,
                stage=StageEnum.COT_HCOT_PIPELINE,
                is_default=True,
                version=1,
                user_id=None,
            )

    # Fallback to database query
    from sqlalchemy import or_
    prompt = db.query(Prompt).filter(
        Prompt.stage == StageEnum.COT_HCOT_PIPELINE,
        Prompt.name == prompt_pattern,
        or_(Prompt.user_id == user_id, Prompt.user_id.is_(None)),
    ).order_by(Prompt.is_default.desc(), Prompt.version.desc()).first()

    return prompt


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _resolve_file_path(file_path: str) -> str:
    """Resolve relative file_path from DB to absolute path."""
    if os.path.isabs(file_path):
        return file_path
    return os.path.join(_BACKEND_DIR, file_path)


def _read_file_content(db: Session, file_id: int) -> Optional[str]:
    """Read the raw content of a file by its DB ID."""
    file_obj = db.query(File).filter(File.id == file_id).first()
    if not file_obj:
        return None
    try:
        abs_path = _resolve_file_path(file_obj.file_path)
        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read file_id={file_id}: {e}")
        return None


def _get_source_chunks(db: Session, source_file_id: int, user_id: int = None) -> List[Dict[str, Any]]:
    """读取源文件的分段数据，返回 chunk 列表。

    策略：优先从 Dataset 表读取。如果 Dataset 没有数据，
    调用 ensure_datasets_for_file 将 JSON 文件解析并自动写入 Dataset 行
    （该函数已内置 text_field + 别名映射机制，能处理不同字段名），
    然后再从 Dataset 读取。
    """
    from app.models.models import Dataset

    # 先尝试直接从 Dataset 表读
    query = db.query(Dataset).filter(Dataset.file_id == source_file_id)
    if user_id:
        query = query.filter(Dataset.user_id == user_id)
    datasets = query.order_by(Dataset.id.asc()).all()

    if not datasets:
        # Dataset 表没有数据——用 ensure_datasets_for_file 自动解析 JSON 并写入 Dataset
        # 它会根据 file_obj.text_field + 别名映射，自动把各种字段名映射到 Dataset 的 input/originContent
        file_obj = db.query(File).filter(File.id == source_file_id).first()
        if not file_obj:
            return []
        datasets = ensure_datasets_for_file(db, source_file_id, file_obj.user_id)
        db.flush()  # 确保新写入的 Dataset 行可以被读取

    if not datasets:
        return []

    chunks = []
    for i, ds in enumerate(datasets):
        content = ds.input or ""
        if not content:
            content = ds.originContent or ""
        if content.strip():
            chunks.append({"chunk_index": i, "content": content})

    return chunks


def _get_step_output_file_id(db: Session, parent_task_id: int, step_name: str, chunk_index: Optional[int] = None, l0_question_index: Optional[int] = None) -> Optional[int]:
    """Find the output file_id for a completed sub-task of the given step, chunk, and L0 question.

    For document-level steps (chunk_index=None, l0_question_index=None),
    must explicitly filter IS NULL to avoid matching per-chunk or per-L0 records.
    """
    query = db.query(Task).filter(
        Task.parent_task_id == parent_task_id,
        Task.step_name == step_name,
        Task.status == TaskStatusEnum.COMPLETED,
    )
    if chunk_index is not None:
        query = query.filter(Task.chunk_index == chunk_index)
    else:
        query = query.filter(Task.chunk_index.is_(None))
    if l0_question_index is not None:
        query = query.filter(Task.l0_question_index == l0_question_index)
    else:
        query = query.filter(Task.l0_question_index.is_(None))
    sub = query.first()

    if sub and sub.file_id:
        return sub.file_id
    return None


# ---------------------------------------------------------------------------
# Task helpers
# ---------------------------------------------------------------------------

def _add_task_log(db: Session, task_id: int, content: str):
    log = TaskLog(task_id=task_id, log_content=content)
    db.add(log)
    db.commit()


def _fail_task(db: Session, task_id: int, reason: str):
    """Mark a task as FAILED."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.status = TaskStatusEnum.FAILED
        db.commit()
    _add_task_log(db, task_id, reason)


def _update_progress(db: Session, task: Task, progress_pct: int, label: str):
    """更新子任务的进度百分比和阶段标签。"""
    task.progress_current = progress_pct
    task.progress_total = 100
    task.progress_label = label
    db.commit()


# ---------------------------------------------------------------------------
# L0 question helpers
# ---------------------------------------------------------------------------


def _extract_l0_question_by_index(l0_gen_content: str, l0_question_index: int) -> Optional[str]:
    """从 l0_gen 的输出 JSON 中提取指定序号的 L0 总问题文本。

    l0_gen 可能输出:
    - {"l0_candidates": [...]} → 按 index 取第 N 个，返回其 "input" 字段值
    - {"l0_candidate": {...}} → 单个总问题，index 0 返回它的 "input" 字段值
    - 也兼容旧格式：candidate 没有 "input" 字段时，返回整个对象 JSON

    返回值是总问题的文本字符串，用于填入 L1 Prompt 的 {l0_input} 占位符。
    """
    try:
        data = json.loads(l0_gen_content)
    except json.JSONDecodeError:
        return None

    candidate = None

    # 尝试从 l0_candidates 列表提取
    if "l0_candidates" in data and isinstance(data["l0_candidates"], list):
        if l0_question_index < len(data["l0_candidates"]):
            candidate = data["l0_candidates"][l0_question_index]

    # 尝试从单个 l0_candidate 提取（只有 index 0 有效）
    if candidate is None and "l0_candidate" in data and isinstance(data["l0_candidate"], dict):
        if l0_question_index == 0:
            candidate = data["l0_candidate"]

    # fallback: 如果 data 本身看起来是列表
    if candidate is None and isinstance(data, list) and l0_question_index < len(data):
        candidate = data[l0_question_index]

    if candidate is None:
        return None

    # 新格式：candidate 包含 "input" 字段 → 只提取总问题文本
    if isinstance(candidate, dict) and "input" in candidate:
        return candidate["input"]

    # fallback: candidate 没有分离的 "input" 字段 → 返回整个对象 JSON
    return json.dumps(candidate, ensure_ascii=False)


def _count_l0_questions(l0_gen_content: str) -> int:
    """从 l0_gen 输出中解析 L0 总问题数量。"""
    try:
        data = json.loads(l0_gen_content)
    except json.JSONDecodeError:
        return 1
    if "l0_candidates" in data and isinstance(data["l0_candidates"], list):
        return len(data["l0_candidates"])
    if "l0_candidate" in data:
        return 1
    if isinstance(data, list):
        return len(data)
    return 1  # fallback: assume 1 question


def _extract_fact_card_items(data: Any) -> List[Any]:
    """从单个 chunk 的事实卡输出中提取事实卡数组。

    标准 Prompt 输出为 {"fact_cards": [...]}。这里兼容直接输出数组，
    或者少数模型输出其它 list 字段的情况。
    """
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    if isinstance(data.get("fact_cards"), list):
        return data["fact_cards"]

    # 兼容可能的别名/嵌套字段
    for key in ("cards", "items", "data"):
        if isinstance(data.get(key), list):
            return data[key]

    # fallback: 找第一个元素为 dict 的列表字段
    for value in data.values():
        if isinstance(value, list) and (not value or isinstance(value[0], dict)):
            return value

    return []


def _merge_fact_card_outputs(outputs: List[Any]) -> Dict[str, List[Any]]:
    """将多个 chunk 的事实卡输出合并为统一 JSON 对象。

    输出始终是 {"fact_cards": [...]}，并在合并时重写全局唯一 fact_id：
    FC-0001、FC-0002...。每个 chunk 里的模型输出可能都从 F-0001
    开始，如果不重编号，后续 L0/L1/L2 的 source_fact_ids 会引用混乱。
    """
    merged_cards: List[Any] = []
    next_id = 1

    for output in outputs:
        chunk_index = None
        data = output
        if isinstance(output, dict) and "data" in output and "chunk_index" in output:
            chunk_index = output.get("chunk_index")
            data = output.get("data")

        for card in _extract_fact_card_items(data):
            if isinstance(card, dict):
                normalized = dict(card)
                original_fact_id = normalized.get("fact_id") or normalized.get("id")
                if original_fact_id is not None:
                    normalized["original_fact_id"] = original_fact_id
                if chunk_index is not None:
                    normalized["chunk_index"] = chunk_index
                normalized["fact_id"] = f"FC-{next_id:04d}"
                merged_cards.append(normalized)
            else:
                merged_cards.append({
                    "fact_id": f"FC-{next_id:04d}",
                    "content": card,
                    "chunk_index": chunk_index,
                })
            next_id += 1

    return {"fact_cards": merged_cards}


# ---------------------------------------------------------------------------
# Input assembly — combine outputs from prior steps into the prompt
# ---------------------------------------------------------------------------

def _assemble_step_inputs(
    db: Session,
    parent_task_id: int,
    source_file_id: int,
    step_name: str,
    chunk_content_override: Optional[str] = None,
    chunk_index: Optional[int] = None,
    l0_question_index: Optional[int] = None,

) -> Optional[Dict[str, str]]:
    """Read all required input files for a step and return placeholder→content mapping.

    Returns dict like {"content": "论文全文...", "fact_cards_sanitized": "JSON..."}
    or None if any required input is missing.

    chunk_content_override: when provided, used for {content} placeholder instead of
        reading the entire source file. Used in per-chunk fact_card_gen.
    chunk_index: when provided, used to find the correct prior-step output for
        this specific chunk. Only used for per_chunk granularity steps.
    l0_question_index: when provided, used to find the correct prior-step output for
        this specific L0 question. Only used for per_l0 granularity steps.

    General rule: for document-level steps, do NOT filter by chunk_index.
    For per-chunk steps, filter by chunk_index.
    For per-L0 steps, filter by l0_question_index.

    """
    step_meta = PIPELINE_STEPS.get(step_name)
    if not step_meta:
        return None

    _, _, input_sources, _, granularity = step_meta

    # Special handling for merge_fact_cards: combine ALL chunk fact_card_gen outputs
    if step_name == "merge_fact_cards":
        # 读取所有 chunk 的事实卡输出并合并
        all_fact_card_subs = db.query(Task).filter(
            Task.parent_task_id == parent_task_id,
            Task.step_name == "fact_card_gen",
            Task.status == TaskStatusEnum.COMPLETED,
            Task.file_id.isnot(None),
        ).all()

        if not all_fact_card_subs:
            _add_task_log(db, parent_task_id, "merge_fact_cards 需要事实卡输出，但没有已完成的 fact_card_gen 子任务")
            return None

        # 合并所有 chunk 的输出，标准化为 {"fact_cards": [...]}。
        parsed_outputs = []
        for fc_sub in all_fact_card_subs:
            content = _read_file_content(db, fc_sub.file_id)
            if not content:
                continue
            try:
                parsed_outputs.append({"chunk_index": fc_sub.chunk_index, "data": json.loads(content)})
            except json.JSONDecodeError:
                _add_task_log(db, parent_task_id, f"chunk {fc_sub.chunk_index} 的事实卡 JSON 解析失败")
                continue

        merged_data = _merge_fact_card_outputs(parsed_outputs)
        if not merged_data["fact_cards"]:
            return None

        return {"fact_cards": json.dumps(merged_data, ensure_ascii=False)}

    # Special handling for quality_check: gather ALL CoT outputs
    if step_name == "quality_check":
        mode = _get_pipeline_mode(db, parent_task_id)
        if not mode:
            return None

        # Collect all CoT-related outputs

        cot_step_names = []
        if mode == "hcot":
            cot_step_names = ["l2_cot", "l1_cot", "l0_cot"]
        else:
            cot_step_names = ["cot_gen"]

        all_cot_content = []
        for cot_step in cot_step_names:
            cot_meta = PIPELINE_STEPS.get(cot_step)
            if cot_meta and cot_meta[4] == "per_l0":
                # per-L0 steps: gather all L0 question outputs
                all_cot_subs = db.query(Task).filter(
                    Task.parent_task_id == parent_task_id,
                    Task.step_name == cot_step,
                    Task.status == TaskStatusEnum.COMPLETED,
                    Task.file_id.isnot(None),
                ).all()
                for sub in all_cot_subs:
                    content = _read_file_content(db, sub.file_id)
                    if content:
                        all_cot_content.append(content)
            else:
                # document-level steps: read single output
                file_id = _get_step_output_file_id(db, parent_task_id, cot_step)
                if file_id:
                    content = _read_file_content(db, file_id)
                    if content:
                        all_cot_content.append(content)


        if not all_cot_content:
            return None

        # Combine all CoT outputs into one block for the {cots} placeholder
        combined = "\n\n---\n\n".join(all_cot_content)
        return {"cots": combined}

    # For export_jsonl: no inputs needed (handled separately)
    if step_name == "export_jsonl":
        return {}

    # Standard steps: read each input source
    inputs = {}
    for placeholder, source_step in input_sources.items():
        if source_step is None:
            # Use the pipeline's original source file
            content = _read_file_content(db, source_file_id)
            if content is None:
                _add_task_log(db, parent_task_id, f"输入 '{placeholder}' 的源文件不存在")
                return None
            inputs[placeholder] = content
        else:
            # Determine the lookup parameters based on granularity of the source step
            source_meta = PIPELINE_STEPS.get(source_step)
            source_granularity = source_meta[4] if source_meta else "document"

            lookup_chunk = None
            lookup_l0 = None

            if source_granularity == "per_chunk":
                # Source is per-chunk: need chunk_index
                lookup_chunk = chunk_index
            elif source_granularity == "per_l0":
                # Source is per-L0: need l0_question_index
                lookup_l0 = l0_question_index
                # Special case: if placeholder is l0_input and source is l0_gen,
                # we need to extract the specific L0 question by index
                if placeholder == "l0_input" and source_step == "l0_gen":
                    l0_gen_file_id = _get_step_output_file_id(db, parent_task_id, source_step)
                    if l0_gen_file_id is None:
                        _add_task_log(db, parent_task_id, f"输入 '{placeholder}' 需要步骤 '{source_step}' 的输出，但该步骤尚未完成")
                        return None
                    l0_gen_content = _read_file_content(db, l0_gen_file_id)
                    if l0_gen_content is None:
                        _add_task_log(db, parent_task_id, f"输入 '{placeholder}' 的文件读取失败")
                        return None
                    specific_l0 = _extract_l0_question_by_index(l0_gen_content, l0_question_index or 0)
                    if specific_l0 is None:
                        _add_task_log(db, parent_task_id, f"从 l0_gen 输出中提取第 {l0_question_index} 个总问题失败")
                        return None
                    inputs[placeholder] = specific_l0
                    continue
            # document-level source: no chunk or l0 filtering needed

            file_id = _get_step_output_file_id(db, parent_task_id, source_step, chunk_index=lookup_chunk, l0_question_index=lookup_l0)

            if file_id is None:
                _add_task_log(db, parent_task_id, f"输入 '{placeholder}' 需要步骤 '{source_step}' 的输出，但该步骤尚未完成或没有输出文件")
                return None
            content = _read_file_content(db, file_id)
            if content is None:
                _add_task_log(db, parent_task_id, f"输入 '{placeholder}' 的文件读取失败 (file_id={file_id})")
                return None
            inputs[placeholder] = content

    return inputs


def _get_pipeline_mode(db: Session, parent_task_id: int) -> Optional[str]:
    """Get pipeline_mode from the parent task."""
    parent = db.query(Task).filter(Task.id == parent_task_id).first()
    if parent:
        return parent.pipeline_mode
    return None


def _build_step_prompt(prompt_template: str, inputs: Dict[str, str]) -> str:
    """Build the final LLM prompt by substituting all placeholders with their content."""
    result = prompt_template
    for placeholder, content in inputs.items():
        tag = "{" + placeholder + "}"
        result = result.replace(tag, content)
    return result


# ---------------------------------------------------------------------------
# Core step execution (sync, accepts external db session)
# ---------------------------------------------------------------------------


def _execute_llm_step(
    db: Session,
    sub_task: Task,
    step_name: str,
    prompt_content: str,
    parent_task_id: int,
    model: str,
    user_id: int,
    username: str,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
    chunk_content_override: Optional[str] = None,
    chunk_index: Optional[int] = None,
    l0_question_index: Optional[int] = None,

) -> bool:
    """Execute one LLM-based pipeline step using the given db session.

    Returns True if completed successfully, False if failed.
    Updates sub_task progress and status within the same session.
    """
    sub_task_id = sub_task.id
    phases = PIPELINE_STEP_PHASES.get(step_name, [(0, 100, "执行中")])
    _add_task_log(db, sub_task_id, f"开始执行步骤: {step_name}")

    # Phase 0: 读取输入数据
    _update_progress(db, sub_task, phases[0][0], phases[0][2])
    inputs = _assemble_step_inputs(
        db, parent_task_id, sub_task.source_file_id, step_name,
        chunk_content_override=chunk_content_override,
        chunk_index=chunk_index,
        l0_question_index=l0_question_index,

    )
    if inputs is None:
        _fail_task(db, sub_task_id, f"步骤 '{step_name}' 所需的输入数据不完整")
        return False

    # Phase 1: 组装提示词
    _update_progress(db, sub_task, phases[1][0], phases[1][2])
    llm_prompt = _build_step_prompt(prompt_content, inputs)

    # Phase 2: 调用 LLM
    _update_progress(db, sub_task, phases[2][0], phases[2][2])
    _add_task_log(db, sub_task_id, "正在调用 LLM...")
    try:
        result = call_llm_json_sync(
            prompt=llm_prompt,
            model=model,
            temperature=0.3,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            username=username,
        )
    except LLMCallError as e:
        err_msg = str(e)[:300]
        logger.error(f"Task {sub_task_id}: LLM call failed for step {step_name}: {err_msg}")
        _add_task_log(db, sub_task_id, f"LLM调用失败: {err_msg}")
        _fail_task(db, sub_task_id, f"LLM调用失败: {err_msg}")
        return False

    # LLM completed — advance progress to Phase 3 (解析输出)
    _update_progress(db, sub_task, phases[3][0], phases[3][2])

    # Phase 4: 写入输出文件
    _update_progress(db, sub_task, phases[4][0], phases[4][2])
    _add_task_log(db, sub_task_id, "正在写入输出文件...")

    sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
    source_file = db.query(File).filter(File.id == sub_task.source_file_id).first()
    step_display = PIPELINE_STEPS.get(step_name, (step_name,))[0]

    output_file = create_output_file(
        db=db,
        user_id=user_id,
        source_file=source_file,
        stage=StageEnum.COT_HCOT_PIPELINE,
        output_filename=None,
        username=username,
        name_suffix=step_name,
        initial_content=result,
        stage_name=f"CoT标注_{step_display}",
    )

    sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
    if sub_task:
        sub_task.file_id = output_file.id
        sub_task.progress_current = 100
        sub_task.progress_label = "已完成"
        sub_task.status = TaskStatusEnum.COMPLETED
        db.commit()

    if parent_task_id:
        _add_task_log(db, parent_task_id, f"步骤 '{step_display}' 完成，输出文件: {output_file.filename}")

    _add_task_log(db, sub_task_id, f"步骤完成，输出文件: {output_file.filename}")
    logger.info(f"Task {sub_task_id}: Step '{step_name}' completed, output file_id={output_file.id}")

    return True


def _execute_merge_step(
    db: Session,
    sub_task: Task,
    parent_task_id: int,
    user_id: int,
    username: str,
) -> bool:
    """Execute the merge_fact_cards step: combine all chunk fact cards into one document.

    Returns True if completed successfully, False if failed.
    """
    sub_task_id = sub_task.id
    phases = PIPELINE_STEP_PHASES.get("merge_fact_cards", [(0, 100, "执行中")])
    _add_task_log(db, sub_task_id, "开始合并事实卡")

    # Phase 0: 读取所有 chunk 事实卡
    _update_progress(db, sub_task, phases[0][0], phases[0][2])

    all_fact_card_subs = db.query(Task).filter(
        Task.parent_task_id == parent_task_id,
        Task.step_name == "fact_card_gen",
        Task.status == TaskStatusEnum.COMPLETED,
        Task.file_id.isnot(None),
    ).all()

    if not all_fact_card_subs:
        _add_task_log(db, sub_task_id, "没有已完成的事实卡生成子任务")
        _fail_task(db, sub_task_id, "合并失败：没有事实卡数据")
        return False

    # Phase 1: 合并事实卡数据
    _update_progress(db, sub_task, phases[1][0], phases[1][2])

    parsed_outputs = []
    for fc_sub in all_fact_card_subs:
        content = _read_file_content(db, fc_sub.file_id)
        if not content:
            continue
        try:
            parsed_outputs.append({"chunk_index": fc_sub.chunk_index, "data": json.loads(content)})
        except json.JSONDecodeError as e:
            _add_task_log(db, sub_task_id, f"chunk {fc_sub.chunk_index} 的事实卡 JSON 解析失败: {e}")
            continue

    merged_data = _merge_fact_card_outputs(parsed_outputs)
    if not merged_data["fact_cards"]:
        _add_task_log(db, sub_task_id, "合并后没有有效的事实卡数据")
        _fail_task(db, sub_task_id, "合并失败：没有有效数据")
        return False

    # Phase 2: 写入合并文件
    _update_progress(db, sub_task, phases[2][0], phases[2][2])

    sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
    source_file = db.query(File).filter(File.id == sub_task.source_file_id).first()

    output_file = create_output_file(
        db=db,
        user_id=user_id,
        source_file=source_file,
        stage=StageEnum.COT_HCOT_PIPELINE,
        output_filename=None,
        username=username,
        name_suffix="merge_fact_cards",
        initial_content=merged_data,
        stage_name="CoT标注_合并事实卡",
    )

    sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
    if sub_task:
        sub_task.file_id = output_file.id
        sub_task.progress_current = 100
        sub_task.progress_total = 100
        sub_task.progress_label = "已完成"
        sub_task.status = TaskStatusEnum.COMPLETED
        db.commit()

    if parent_task_id:
        _add_task_log(db, parent_task_id, f"事实卡合并完成，输出文件: {output_file.filename}")

    _add_task_log(db, sub_task_id, f"事实卡合并完成，共合并 {len(all_fact_card_subs)} 个 chunk 的事实卡")
    logger.info(f"Task {sub_task_id}: merge_fact_cards completed, file_id={output_file.id}")

    return True


def _execute_export_step(
    db: Session,
    sub_task: Task,
    parent_task_id: int,
    user_id: int,
    username: str,
) -> bool:
    """Execute the export_jsonl step using the given db session.

    Returns True if completed successfully, False if failed.
    """
    sub_task_id = sub_task.id
    parent = db.query(Task).filter(Task.id == parent_task_id).first()
    mode = parent.pipeline_mode or "hcot"
    step_order = get_step_order(mode)

    phases = PIPELINE_STEP_PHASES.get("export_jsonl", [(0, 100, "执行中")])
    _add_task_log(db, sub_task_id, "开始合成最终交付数据")

    # Phase 0: 读取所有中间步骤数据
    _update_progress(db, sub_task, phases[0][0], phases[0][2])

    all_steps_data = {}
    for step_name_iter in step_order:
        if step_name_iter == "export_jsonl":
            continue
        file_id = _get_step_output_file_id(db, parent_task_id, step_name_iter)
        if file_id:
            content = _read_file_content(db, file_id)
            if content:
                try:
                    data = json.loads(content)
                    all_steps_data[step_name_iter] = data
                except json.JSONDecodeError as e:
                    _add_task_log(db, sub_task_id, f"解析步骤 '{step_name_iter}' 输出失败: {e}")

    if not all_steps_data:
        _add_task_log(db, sub_task_id, "没有找到任何中间步骤数据")
        _fail_task(db, sub_task_id, "导出失败：没有中间步骤数据")
        return False

    # Phase 1: 合成层级树 + 训练样本
    _update_progress(db, sub_task, phases[1][0], phases[1][2])

    # Build the final deliverable structure
    final_data = {
        "source_id": parent.pipeline_name or f"pipeline_{parent.id}",
        "pipeline_mode": mode,
        "model": parent.model,
    }

    # --- Collect intermediate outputs by category ---
    if "merge_fact_cards" in all_steps_data:
        final_data["merged_fact_cards"] = all_steps_data["merge_fact_cards"]
    if "sanitize" in all_steps_data:
        final_data["fact_cards_sanitized"] = all_steps_data["sanitize"]

    if mode == "hcot":
        # Find all distinct l0_question_index values for multi-tree support
        l0_indices = set()
        l0_subs = db.query(Task).filter(
            Task.parent_task_id == parent_task_id,
            Task.l0_question_index.isnot(None),
            Task.status == TaskStatusEnum.COMPLETED,
        ).all()
        for sub in l0_subs:
            l0_indices.add(sub.l0_question_index)
        l0_indices = sorted(l0_indices)

        # If no l0_question_index found (legacy), assume single tree with index 0
        if not l0_indices:
            l0_indices = [0]

        # Build trees for each L0 question
        hcot_trees = []
        training_samples = []
        for l0_idx in l0_indices:
            # Get this L0 question's specific outputs
            l0_cot_file = _get_step_output_file_id(db, parent_task_id, "l0_cot", l0_question_index=l0_idx)
            l1_cot_file = _get_step_output_file_id(db, parent_task_id, "l1_cot", l0_question_index=l0_idx)
            l2_cot_file = _get_step_output_file_id(db, parent_task_id, "l2_cot", l0_question_index=l0_idx)
            l1_decompose_file = _get_step_output_file_id(db, parent_task_id, "l1_decompose", l0_question_index=l0_idx)
            l2_decompose_file = _get_step_output_file_id(db, parent_task_id, "l2_decompose", l0_question_index=l0_idx)
            l0_gen_file = _get_step_output_file_id(db, parent_task_id, "l0_gen")  # same for all L0 questions

            # Read and build tree for this L0 question
            tree = _build_hcot_tree_for_l0(
                l0_question_content=_read_file_content(db, l0_gen_file) or "{}",
                l1_questions_content=_read_file_content(db, l1_decompose_file) or "{}",
                l2_cots_content=_read_file_content(db, l2_cot_file) or "{}",
                l1_cots_content=_read_file_content(db, l1_cot_file) or "{}",
                l0_cot_content=_read_file_content(db, l0_cot_file) or "{}",
                l0_question_index=l0_idx,
            )
            hcot_trees.append(tree)

            # Extract training samples from this L0 question's CoT outputs
            for step_key in ["l2_cot", "l1_cot", "l0_cot"]:
                file_id = _get_step_output_file_id(db, parent_task_id, step_key, l0_question_index=l0_idx)
                if file_id:
                    content = _read_file_content(db, file_id)
                    if content:
                        try:
                            data = json.loads(content)
                            samples = _extract_training_samples(data, step_key)
                            training_samples.extend(samples)
                        except json.JSONDecodeError:
                            pass

        final_data["hcot_trees"] = hcot_trees
        final_data["training_samples"] = training_samples
        final_data["total_samples"] = len(training_samples)

    else:
        questions = all_steps_data.get("question_gen", {})
        cot_samples = all_steps_data.get("cot_gen", {})

        final_data["questions"] = questions
        final_data["cot_samples"] = cot_samples

        training_samples = []
        if "cot_gen" in all_steps_data:
            samples = _extract_training_samples(all_steps_data["cot_gen"], "cot_gen")
            training_samples.extend(samples)
        final_data["training_samples"] = training_samples
        final_data["total_samples"] = len(training_samples)

    if "quality_check" in all_steps_data:
        final_data["quality_check_result"] = all_steps_data["quality_check"]

    # Phase 2: 写入最终文件
    _update_progress(db, sub_task, phases[2][0], phases[2][2])

    source_file = db.query(File).filter(File.id == parent.source_file_id).first()

    output_file = create_output_file(
        db=db,
        user_id=user_id,
        source_file=source_file,
        stage=StageEnum.COT_HCOT_PIPELINE,
        output_filename=None,
        username=username,
        name_suffix="export_jsonl",
        initial_content=final_data,
        stage_name="CoT标注_导出训练数据",
    )

    sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
    if sub_task:
        sub_task.file_id = output_file.id
        sub_task.progress_current = 100
        sub_task.progress_total = 100
        sub_task.progress_label = "已完成"
        sub_task.status = TaskStatusEnum.COMPLETED
        db.commit()

    if parent_task_id:
        _add_task_log(db, parent_task_id, f"导出完成：{final_data.get('total_samples', 0)} 条训练样本，文件: {output_file.filename}")

    _add_task_log(db, sub_task_id, f"导出完成：包含所有中间数据和 {final_data.get('total_samples', 0)} 条训练样本")
    logger.info(f"Task {sub_task_id}: Export completed, file_id={output_file.id}")

    return True


# ---------------------------------------------------------------------------
# Background step runner (LLM steps) — standalone entry for manual trigger
# ---------------------------------------------------------------------------


async def run_pipeline_step_bg(
    sub_task_id: int,
    step_name: str,
    prompt_content: str,
    input_file_id: int,
    model: str,
    user_id: int,
    username: str,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
    parent_task_id: int = None,
):
    """Background coroutine: execute one LLM-based pipeline step (standalone entry).

    Used for manual single-step triggering. Opens its own db session and
    delegates to _execute_llm_step for the actual work.
    """
    db = SessionLocal()
    register_task()
    try:
        sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
        if not sub_task:
            logger.error(f"Task {sub_task_id}: Sub-task not found")
            return

        _execute_llm_step(
            db=db,
            sub_task=sub_task,
            step_name=step_name,
            prompt_content=prompt_content,
            parent_task_id=parent_task_id or sub_task.parent_task_id,
            model=model,
            user_id=user_id,
            username=username,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            l0_question_index=sub_task.l0_question_index,
        )

    except Exception as e:
        logger.error(f"Task {sub_task_id}: Unexpected error in step {step_name}: {e}\n{traceback.format_exc()}")
        try:
            db.rollback()
            _fail_task(db, sub_task_id, f"意外错误: {str(e)[:200]}")
        except Exception:
            pass
    finally:
        unregister_task()
        db.close()


# ---------------------------------------------------------------------------
# Background step runner (export_jsonl) — standalone entry for manual trigger
# ---------------------------------------------------------------------------


async def run_export_jsonl_bg(
    sub_task_id: int,
    step_name: str,
    input_file_id: int,
    model: str,
    user_id: int,
    username: str,
    parent_task_id: int = None,
):
    """Background coroutine: export_jsonl step (standalone entry).

    Used for manual single-step triggering. Opens its own db session and
    delegates to _execute_export_step for the actual work.
    """
    db = SessionLocal()
    register_task()
    try:
        sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
        if not sub_task:
            logger.error(f"Task {sub_task_id}: Sub-task not found")
            return

        _execute_export_step(
            db=db,
            sub_task=sub_task,
            parent_task_id=parent_task_id or sub_task.parent_task_id,
            user_id=user_id,
            username=username,
        )

    except Exception as e:
        logger.error(f"Task {sub_task_id}: Unexpected error in export: {e}\n{traceback.format_exc()}")
        try:
            db.rollback()
            _fail_task(db, sub_task_id, f"导出意外错误: {str(e)[:200]}")
        except Exception:
            pass
    finally:
        unregister_task()
        db.close()


# ---------------------------------------------------------------------------
# Helper: determine primary input file ID for a pipeline step
# ---------------------------------------------------------------------------


def _determine_primary_input_file_id(
    db: Session, parent_task_id: int, source_file_id: int, step_name: str, step_order: list
) -> int:
    """Determine the primary input file ID for a pipeline step."""
    step_meta = PIPELINE_STEPS.get(step_name)
    _, _, input_sources, _, _ = step_meta

    if not input_sources:
        return source_file_id

    first_source_step = next(iter(input_sources.values()))
    if first_source_step is None:
        return source_file_id

    file_id = _get_step_output_file_id(db, parent_task_id, first_source_step)
    if file_id:
        return file_id
    return source_file_id


# ---------------------------------------------------------------------------
# Auto-run: chain-execute all pipeline steps sequentially
# ---------------------------------------------------------------------------


def _run_llm_step_in_thread(
    sub_task_id: int,
    step_name: str,
    prompt_content: str,
    parent_task_id: int,
    model: str,
    user_id: int,
    username: str,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
    chunk_content_override: Optional[str] = None,
    chunk_index: Optional[int] = None,
    l0_question_index: Optional[int] = None,

) -> bool:
    """Thread wrapper: open fresh session, run _execute_llm_step, return success."""
    db = SessionLocal()
    try:
        sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
        if not sub_task:
            return False
        return _execute_llm_step(
            db=db, sub_task=sub_task, step_name=step_name,
            prompt_content=prompt_content, parent_task_id=parent_task_id,
            model=model, user_id=user_id, username=username,
            base_url_override=base_url_override, api_key_override=api_key_override,
            chunk_content_override=chunk_content_override, chunk_index=chunk_index,
            l0_question_index=l0_question_index,

        )
    except Exception as e:
        logger.error(f"Thread wrapper: LLM step {step_name} error: {e}")
        try:
            db.rollback()
            _fail_task(db, sub_task_id, f"意外错误: {str(e)[:200]}")
        except Exception:
            pass
        return False
    finally:
        db.close()


def _run_merge_step_in_thread(
    sub_task_id: int,
    parent_task_id: int,
    user_id: int,
    username: str,
) -> bool:
    """Thread wrapper: open fresh session, run _execute_merge_step, return success."""
    db = SessionLocal()
    try:
        sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
        if not sub_task:
            return False
        return _execute_merge_step(
            db=db, sub_task=sub_task, parent_task_id=parent_task_id,
            user_id=user_id, username=username,
        )
    except Exception as e:
        logger.error(f"Thread wrapper: merge step error: {e}")
        try:
            db.rollback()
            _fail_task(db, sub_task_id, f"合并意外错误: {str(e)[:200]}")
        except Exception:
            pass
        return False
    finally:
        db.close()


def _run_export_step_in_thread(
    sub_task_id: int,
    parent_task_id: int,
    user_id: int,
    username: str,
) -> bool:
    """Thread wrapper: open fresh session, run _execute_export_step, return success."""
    db = SessionLocal()
    try:
        sub_task = db.query(Task).filter(Task.id == sub_task_id).first()
        if not sub_task:
            return False
        return _execute_export_step(
            db=db, sub_task=sub_task, parent_task_id=parent_task_id,
            user_id=user_id, username=username,
        )
    except Exception as e:
        logger.error(f"Thread wrapper: export step error: {e}")
        try:
            db.rollback()
            _fail_task(db, sub_task_id, f"导出意外错误: {str(e)[:200]}")
        except Exception:
            pass
        return False
    finally:
        db.close()


async def run_pipeline_auto_bg(
    parent_task_id: int,
    mode: str,
    model: str,
    user_id: int,
    username: str,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
    source_file_id: int = None,
    prompt_template_id: Optional[str] = None,
):
    """三阶段式链式执行：分段→全文→推理树→质检导出。

    Phase 1 (per-chunk): 每个 chunk 生成事实卡
    Phase 2 (document):  合并事实卡 → 数值抽象 → L0 总问题生成
    Phase 3 (per-L0):    每个 L0 总问题独立构建推理树
    Phase 4 (document):  质检 → 导出

    """
    db = SessionLocal()
    register_task()
    try:
        parent = db.query(Task).filter(Task.id == parent_task_id).first()
        if not parent:
            logger.error(f"Auto-run: parent task {parent_task_id} not found")
            return

        # 读取源文件的 chunk 列表
        chunks = _get_source_chunks(db, source_file_id or parent.source_file_id, user_id=user_id)
        total_chunks = len(chunks)

        if total_chunks == 0:
            parent.status = TaskStatusEnum.FAILED
            parent.progress_label = "源文件没有可用的内容"
            db.commit()
            return

        # 更新父任务的 total_chunks
        parent.total_chunks = total_chunks
        db.commit()

        logger.info(f"Auto-run pipeline {parent_task_id}: {total_chunks} chunks to process")

        # --- Phase 1: per-chunk fact_card_gen ---
        parent = db.query(Task).filter(Task.id == parent_task_id).first()
        parent.progress_label = "阶段1: 分段事实卡生成"
        db.commit()

        for chunk_idx, chunk in enumerate(chunks):
            # 检查是否已有已完成的子任务
            existing = db.query(Task).filter(
                Task.parent_task_id == parent_task_id,
                Task.step_name == "fact_card_gen",
                Task.chunk_index == chunk_idx,
                Task.status == TaskStatusEnum.COMPLETED,
            ).first()
            if existing:
                logger.info(f"Auto-run: fact_card_gen chunk {chunk_idx} already completed, skipping")
                continue

            # 重试失败的子任务
            existing_failed = db.query(Task).filter(
                Task.parent_task_id == parent_task_id,
                Task.step_name == "fact_card_gen",
                Task.chunk_index == chunk_idx,

                Task.status == TaskStatusEnum.FAILED,
            ).first()
            if existing_failed:
                existing_failed.status = TaskStatusEnum.PAUSED
                db.commit()

            input_file_id = source_file_id or parent.source_file_id
            prompt_obj = find_prompt_for_step(db, "fact_card_gen", user_id, prompt_template_id)
            if not prompt_obj:
                parent.status = TaskStatusEnum.FAILED
                parent.progress_label = "找不到事实卡生成的提示词"
                db.commit()
                return

            sub_task = Task(
                user_id=user_id,
                stage=StageEnum.COT_HCOT_PIPELINE,
                status=TaskStatusEnum.RUNNING,
                model=model,
                source_file_id=input_file_id,
                parent_task_id=parent_task_id,
                step_name="fact_card_gen",
                chunk_index=chunk_idx,
                total_chunks=total_chunks,
                progress_current=0,
                progress_total=100,
                progress_label="准备执行...",
                prompt_id=prompt_obj.id,
            )
            db.add(sub_task)

            db.commit()
            db.refresh(sub_task)

            success = await asyncio.to_thread(
                _run_llm_step_in_thread,
                sub_task_id=sub_task.id,
                step_name="fact_card_gen",
                prompt_content=prompt_obj.content,
                parent_task_id=parent_task_id,
                model=model,
                user_id=user_id,
                username=username,
                base_url_override=base_url_override,
                api_key_override=api_key_override,
                chunk_content_override=chunk["content"],
                chunk_index=chunk_idx,
            )
            db.expire_all()

            if not success:
                parent = db.query(Task).filter(Task.id == parent_task_id).first()
                parent.status = TaskStatusEnum.FAILED
                parent.progress_label = f"chunk {chunk_idx + 1} 事实卡生成失败"
                db.commit()
                return

            parent = db.query(Task).filter(Task.id == parent_task_id).first()
            parent.progress_label = f"阶段1: chunk {chunk_idx + 1}/{total_chunks} 事实卡完成"
            db.commit()
            logger.info(f"Auto-run pipeline {parent_task_id}: fact_card_gen chunk {chunk_idx} completed")

        # --- Phase 2: document-level steps ---
        parent = db.query(Task).filter(Task.id == parent_task_id).first()
        parent.progress_label = "阶段2: 全文级处理"
        db.commit()

        # merge_fact_cards (纯数据合成，不调 LLM)
        existing = db.query(Task).filter(
            Task.parent_task_id == parent_task_id,
            Task.step_name == "merge_fact_cards",
            Task.chunk_index.is_(None),
            Task.l0_question_index.is_(None),
            Task.status == TaskStatusEnum.COMPLETED,
        ).first()
        if not existing:
            existing_failed = db.query(Task).filter(
                Task.parent_task_id == parent_task_id,
                Task.step_name == "merge_fact_cards",
                Task.chunk_index.is_(None),
                Task.l0_question_index.is_(None),
                Task.status == TaskStatusEnum.FAILED,
            ).first()
            if existing_failed:
                existing_failed.status = TaskStatusEnum.PAUSED
                db.commit()

            input_file_id = source_file_id or parent.source_file_id
            sub_task = Task(
                user_id=user_id,
                stage=StageEnum.COT_HCOT_PIPELINE,
                status=TaskStatusEnum.RUNNING,
                model=model,
                source_file_id=parent.source_file_id,
                parent_task_id=parent_task_id,
                step_name="merge_fact_cards",
                chunk_index=None,
                l0_question_index=None,
                total_chunks=total_chunks,
                progress_current=0,
                progress_total=100,
                progress_label="准备执行...",
            )
            db.add(sub_task)
            db.commit()
            db.refresh(sub_task)

            success = await asyncio.to_thread(
                _run_merge_step_in_thread,
                sub_task_id=sub_task.id,
                parent_task_id=parent_task_id,
                user_id=user_id,
                username=username,
            )
            db.expire_all()

            if not success:
                parent = db.query(Task).filter(Task.id == parent_task_id).first()
                parent.status = TaskStatusEnum.FAILED
                parent.progress_label = "事实卡合并失败"
                db.commit()
                return

            logger.info(f"Auto-run pipeline {parent_task_id}: merge_fact_cards completed")

        # sanitize (document-level)
        existing = db.query(Task).filter(
            Task.parent_task_id == parent_task_id,
            Task.step_name == "sanitize",
            Task.chunk_index.is_(None),
            Task.l0_question_index.is_(None),
            Task.status == TaskStatusEnum.COMPLETED,
        ).first()
        if not existing:
            existing_failed = db.query(Task).filter(
                Task.parent_task_id == parent_task_id,
                Task.step_name == "sanitize",
                Task.chunk_index.is_(None),
                Task.l0_question_index.is_(None),
                Task.status == TaskStatusEnum.FAILED,
            ).first()
            if existing_failed:
                existing_failed.status = TaskStatusEnum.PAUSED
                db.commit()

            input_file_id = source_file_id or parent.source_file_id
            prompt_obj = find_prompt_for_step(db, "sanitize", user_id, prompt_template_id)
            if not prompt_obj:
                parent.status = TaskStatusEnum.FAILED
                parent.progress_label = "找不到数值抽象的提示词"
                db.commit()
                return

            sub_task = Task(
                user_id=user_id,
                stage=StageEnum.COT_HCOT_PIPELINE,
                status=TaskStatusEnum.RUNNING,
                model=model,
                source_file_id=input_file_id,
                parent_task_id=parent_task_id,
                step_name="sanitize",
                chunk_index=None,
                l0_question_index=None,
                total_chunks=total_chunks,
                progress_current=0,
                progress_total=100,
                progress_label="准备执行...",
                prompt_id=prompt_obj.id,
            )
            db.add(sub_task)
            db.commit()
            db.refresh(sub_task)

            success = await asyncio.to_thread(
                _run_llm_step_in_thread,
                sub_task_id=sub_task.id,
                step_name="sanitize",
                prompt_content=prompt_obj.content,
                parent_task_id=parent_task_id,
                model=model,
                user_id=user_id,
                username=username,
                base_url_override=base_url_override,
                api_key_override=api_key_override,
                chunk_content_override=None,
                chunk_index=None,
                l0_question_index=None,
            )
            db.expire_all()

            if not success:
                parent = db.query(Task).filter(Task.id == parent_task_id).first()
                parent.status = TaskStatusEnum.FAILED
                parent.progress_label = "数值抽象失败"
                db.commit()
                return

            logger.info(f"Auto-run pipeline {parent_task_id}: sanitize completed")

        if mode == "hcot":
            # l0_gen (document-level)
            existing = db.query(Task).filter(
                Task.parent_task_id == parent_task_id,
                Task.step_name == "l0_gen",
                Task.chunk_index.is_(None),
                Task.l0_question_index.is_(None),
                Task.status == TaskStatusEnum.COMPLETED,
            ).first()
            if not existing:
                existing_failed = db.query(Task).filter(
                    Task.parent_task_id == parent_task_id,
                    Task.step_name == "l0_gen",
                    Task.chunk_index.is_(None),
                    Task.l0_question_index.is_(None),
                    Task.status == TaskStatusEnum.FAILED,
                ).first()
                if existing_failed:
                    existing_failed.status = TaskStatusEnum.PAUSED
                    db.commit()

                input_file_id = source_file_id or parent.source_file_id
                prompt_obj = find_prompt_for_step(db, "l0_gen", user_id, prompt_template_id)
                if not prompt_obj:
                    parent.status = TaskStatusEnum.FAILED
                    parent.progress_label = "找不到 L0 总问题生成的提示词"
                    db.commit()
                    return

                sub_task = Task(
                    user_id=user_id,
                    stage=StageEnum.COT_HCOT_PIPELINE,
                    status=TaskStatusEnum.RUNNING,
                    model=model,
                    source_file_id=input_file_id,
                    parent_task_id=parent_task_id,
                    step_name="l0_gen",
                    chunk_index=None,
                    l0_question_index=None,
                    total_chunks=total_chunks,
                    progress_current=0,
                    progress_total=100,
                    progress_label="准备执行...",
                    prompt_id=prompt_obj.id,
                )
                db.add(sub_task)
                db.commit()
                db.refresh(sub_task)

                success = await asyncio.to_thread(
                    _run_llm_step_in_thread,
                    sub_task_id=sub_task.id,
                    step_name="l0_gen",
                    prompt_content=prompt_obj.content,
                    parent_task_id=parent_task_id,
                    model=model,
                    user_id=user_id,
                    username=username,
                    base_url_override=base_url_override,
                    api_key_override=api_key_override,
                    chunk_content_override=None,
                    chunk_index=None,
                    l0_question_index=None,
                )
                db.expire_all()

                if not success:
                    parent = db.query(Task).filter(Task.id == parent_task_id).first()
                    parent.status = TaskStatusEnum.FAILED
                    parent.progress_label = "L0 总问题生成失败"
                    db.commit()
                    return

                logger.info(f"Auto-run pipeline {parent_task_id}: l0_gen completed")

            # 解析 l0_gen 输出，确定 L0 总问题数量
            l0_gen_file_id = _get_step_output_file_id(db, parent_task_id, "l0_gen")
            num_l0_questions = 1
            if l0_gen_file_id:
                l0_gen_content = _read_file_content(db, l0_gen_file_id)
                if l0_gen_content:
                    num_l0_questions = _count_l0_questions(l0_gen_content)

            logger.info(f"Auto-run pipeline {parent_task_id}: detected {num_l0_questions} L0 questions")

            # --- Phase 3: per-L0 推理树构建 ---
            parent = db.query(Task).filter(Task.id == parent_task_id).first()
            parent.progress_label = f"阶段3: 推理树构建 ({num_l0_questions} 个总问题)"
            db.commit()

            failed_l0_indices = []  # 记录失败的总问题序号，不阻断整体流程

            for l0_idx in range(num_l0_questions):
                l0_tree_failed = False  # 标记该总问题的推理树是否中途失败

                for step_name in ["l1_decompose", "l2_decompose", "l2_cot", "l1_cot", "l0_cot"]:
                    # 如果该总问题已有步骤失败，跳过剩余步骤（推理树是链条，缺一步后续无法衔接）
                    if l0_tree_failed:
                        logger.info(f"Auto-run: skipping step '{step_name}' for l0_idx={l0_idx} because earlier step in this tree failed")
                        continue

                    # 检查是否已有已完成的子任务
                    existing = db.query(Task).filter(
                        Task.parent_task_id == parent_task_id,
                        Task.step_name == step_name,
                        Task.chunk_index.is_(None),
                        Task.l0_question_index == l0_idx,
                        Task.status == TaskStatusEnum.COMPLETED,
                    ).first()
                    if existing:
                        logger.info(f"Auto-run: step '{step_name}' l0_idx={l0_idx} already completed, skipping")
                        continue

                    # 检查是否有之前失败的子任务（重试场景）
                    existing_failed = db.query(Task).filter(
                        Task.parent_task_id == parent_task_id,
                        Task.step_name == step_name,
                        Task.chunk_index.is_(None),
                        Task.l0_question_index == l0_idx,
                        Task.status == TaskStatusEnum.FAILED,
                    ).first()
                    if existing_failed:
                        existing_failed.status = TaskStatusEnum.PAUSED
                        db.commit()

                    prompt_obj = find_prompt_for_step(db, step_name, user_id, prompt_template_id)
                    if not prompt_obj:
                        # 提示词缺失属于严重错误，但仍然继续其他总问题
                        logger.error(f"Auto-run: 找不到步骤 '{step_name}' 的提示词，跳过总问题 {l0_idx}")
                        l0_tree_failed = True
                        failed_l0_indices.append(l0_idx)
                        continue

                    input_file_id = source_file_id or parent.source_file_id

                    sub_task = Task(
                        user_id=user_id,
                        stage=StageEnum.COT_HCOT_PIPELINE,
                        status=TaskStatusEnum.RUNNING,
                        model=model,
                        source_file_id=input_file_id,
                        parent_task_id=parent_task_id,
                        step_name=step_name,
                        chunk_index=None,
                        l0_question_index=l0_idx,
                        total_chunks=total_chunks,
                        progress_current=0,
                        progress_total=100,
                        progress_label="准备执行...",
                        prompt_id=prompt_obj.id,
                    )
                    db.add(sub_task)
                    db.commit()
                    db.refresh(sub_task)

                    success = await asyncio.to_thread(
                        _run_llm_step_in_thread,
                        sub_task_id=sub_task.id,
                        step_name=step_name,
                        prompt_content=prompt_obj.content,
                        parent_task_id=parent_task_id,
                        model=model,
                        user_id=user_id,
                        username=username,
                        base_url_override=base_url_override,
                        api_key_override=api_key_override,
                        chunk_content_override=None,
                        chunk_index=None,
                        l0_question_index=l0_idx,
                    )
                    db.expire_all()

                    if not success:
                        step_display = PIPELINE_STEPS.get(step_name, (step_name,))[0]
                        logger.warning(f"Auto-run: 总问题 {l0_idx + 1} 步骤 '{step_display}' 失败，跳过该总问题剩余步骤")
                        l0_tree_failed = True
                        failed_l0_indices.append(l0_idx)
                        # 不 return，继续下一个总问题

                if not l0_tree_failed:
                    parent = db.query(Task).filter(Task.id == parent_task_id).first()
                    parent.progress_label = f"阶段3: 总问题 {l0_idx + 1}/{num_l0_questions} 推理树完成"
                    db.commit()
                    logger.info(f"Auto-run pipeline {parent_task_id}: L0 question {l0_idx} tree completed")
                else:
                    parent = db.query(Task).filter(Task.id == parent_task_id).first()
                    parent.progress_label = f"阶段3: 总问题 {l0_idx + 1}/{num_l0_questions} 推理树失败（继续下一个）"
                    db.commit()

        else:
            # CoT mode: question_gen + cot_gen (document-level)
            parent = db.query(Task).filter(Task.id == parent_task_id).first()
            parent.progress_label = "阶段2: 独立问题与 CoT 生成"
            db.commit()

            for step_name in ["question_gen", "cot_gen"]:
                existing = db.query(Task).filter(
                    Task.parent_task_id == parent_task_id,
                    Task.step_name == step_name,
                    Task.chunk_index.is_(None),
                    Task.l0_question_index.is_(None),
                    Task.status == TaskStatusEnum.COMPLETED,
                ).first()
                if existing:
                    logger.info(f"Auto-run: step '{step_name}' already completed, skipping")
                    continue

                existing_failed = db.query(Task).filter(
                    Task.parent_task_id == parent_task_id,
                    Task.step_name == step_name,
                    Task.chunk_index.is_(None),
                    Task.l0_question_index.is_(None),
                    Task.status == TaskStatusEnum.FAILED,
                ).first()
                if existing_failed:
                    existing_failed.status = TaskStatusEnum.PAUSED
                    db.commit()

                input_file_id = source_file_id or parent.source_file_id
                prompt_obj = find_prompt_for_step(db, step_name, user_id, prompt_template_id)
                if not prompt_obj:

                    parent.status = TaskStatusEnum.FAILED
                    parent.progress_label = f"找不到步骤 '{step_name}' 的提示词"
                    db.commit()
                    return
                sub_task.prompt_id = prompt_obj.id

                sub_task = Task(
                    user_id=user_id,
                    stage=StageEnum.COT_HCOT_PIPELINE,
                    status=TaskStatusEnum.RUNNING,
                    model=model,
                    source_file_id=input_file_id,
                    parent_task_id=parent_task_id,
                    step_name=step_name,
                    chunk_index=None,
                    l0_question_index=None,
                    total_chunks=total_chunks,
                    progress_current=0,
                    progress_total=100,
                    progress_label="准备执行...",
                    prompt_id=prompt_obj.id,
                )
                db.add(sub_task)
                db.commit()
                db.refresh(sub_task)


                success = await asyncio.to_thread(
                    _run_llm_step_in_thread,
                    sub_task_id=sub_task.id,
                    step_name=step_name,
                    prompt_content=prompt_obj.content,
                    parent_task_id=parent_task_id,
                    model=model,
                    user_id=user_id,
                    username=username,
                    base_url_override=base_url_override,
                    api_key_override=api_key_override,
                    chunk_content_override=None,
                    chunk_index=None,
                    l0_question_index=None,
                )
                db.expire_all()

                if not success:
                    step_display = PIPELINE_STEPS.get(step_name, (step_name,))[0]
                    parent = db.query(Task).filter(Task.id == parent_task_id).first()
                    parent.status = TaskStatusEnum.FAILED
                    parent.progress_label = f"步骤 '{step_display}' 失败"
                    db.commit()
                    return

        # --- Phase 4: 质检 + 导出（始终执行，不因前序步骤失败而跳过） ---
        qc_failed = False
        parent = db.query(Task).filter(Task.id == parent_task_id).first()
        parent.progress_label = "阶段4: 质检与导出"
        db.commit()

        # quality_check (document-level)
        existing = db.query(Task).filter(
            Task.parent_task_id == parent_task_id,
            Task.step_name == "quality_check",
            Task.chunk_index.is_(None),
            Task.l0_question_index.is_(None),
            Task.status == TaskStatusEnum.COMPLETED,
        ).first()
        if not existing:
            existing_failed = db.query(Task).filter(
                Task.parent_task_id == parent_task_id,
                Task.step_name == "quality_check",
                Task.chunk_index.is_(None),
                Task.l0_question_index.is_(None),
                Task.status == TaskStatusEnum.FAILED,
            ).first()
            if existing_failed:
                existing_failed.status = TaskStatusEnum.PAUSED

                db.commit()
                _add_task_log(db, parent_task_id, f"链式执行终止：步骤 '{display}' 失败")
                return

            prompt_obj = find_prompt_for_step(db, "quality_check", user_id, prompt_template_id)
            if prompt_obj:
                input_file_id = source_file_id or parent.source_file_id


                sub_task = Task(
                    user_id=user_id,
                    stage=StageEnum.COT_HCOT_PIPELINE,
                    status=TaskStatusEnum.RUNNING,
                    model=model,
                    source_file_id=input_file_id,
                    parent_task_id=parent_task_id,
                    step_name="quality_check",
                    chunk_index=None,
                    l0_question_index=None,
                    total_chunks=total_chunks,
                    progress_current=0,
                    progress_total=100,
                    progress_label="准备执行...",
                    prompt_id=prompt_obj.id,
                )
                db.add(sub_task)
                db.commit()
                db.refresh(sub_task)

                success = await asyncio.to_thread(
                    _run_llm_step_in_thread,
                    sub_task_id=sub_task.id,
                    step_name="quality_check",
                    prompt_content=prompt_obj.content,
                    parent_task_id=parent_task_id,
                    model=model,
                    user_id=user_id,
                    username=username,
                    base_url_override=base_url_override,
                    api_key_override=api_key_override,
                    chunk_content_override=None,
                    chunk_index=None,
                    l0_question_index=None,
                )
                db.expire_all()

                if not success:
                    qc_failed = True
                    logger.warning(f"Auto-run pipeline {parent_task_id}: quality_check failed, proceeding to export anyway")
            else:
                qc_failed = True
                logger.warning(f"Auto-run pipeline {parent_task_id}: no quality_check prompt found, skipping QC")

        # export_jsonl (document-level, 纯数据合成)
        existing = db.query(Task).filter(
            Task.parent_task_id == parent_task_id,
            Task.step_name == "export_jsonl",
            Task.chunk_index.is_(None),
            Task.l0_question_index.is_(None),
            Task.status == TaskStatusEnum.COMPLETED,
        ).first()
        if not existing:
            existing_failed = db.query(Task).filter(
                Task.parent_task_id == parent_task_id,
                Task.step_name == "export_jsonl",
                Task.chunk_index.is_(None),
                Task.l0_question_index.is_(None),
                Task.status == TaskStatusEnum.FAILED,
            ).first()
            if existing_failed:
                existing_failed.status = TaskStatusEnum.PAUSED
                db.commit()

            sub_task = Task(
                user_id=user_id,
                stage=StageEnum.COT_HCOT_PIPELINE,
                status=TaskStatusEnum.RUNNING,
                model=model,
                source_file_id=parent.source_file_id,
                parent_task_id=parent_task_id,
                step_name="export_jsonl",
                chunk_index=None,
                l0_question_index=None,
                total_chunks=total_chunks,
                progress_current=0,
                progress_total=100,
                progress_label="准备执行...",
            )
            db.add(sub_task)
            db.commit()
            db.refresh(sub_task)

            success = await asyncio.to_thread(
                _run_export_step_in_thread,
                sub_task_id=sub_task.id,
                parent_task_id=parent_task_id,
                user_id=user_id,
                username=username,
            )
            db.expire_all()

            if not success:
                parent = db.query(Task).filter(Task.id == parent_task_id).first()
                parent.status = TaskStatusEnum.FAILED
                parent.progress_label = "导出失败"
                db.commit()
                return

        # 全部完成（可能有部分总问题失败，但整体流程走完了）
        parent = db.query(Task).filter(Task.id == parent_task_id).first()
        parent.status = TaskStatusEnum.COMPLETED
        if failed_l0_indices:
            parent.progress_label = f"流水线完成（总问题 {', '.join(str(i+1) for i in failed_l0_indices)} 推理树失败）"
        elif qc_failed:
            parent.progress_label = "流水线完成（质检失败，但导出已执行）"
        else:
            parent.progress_label = "流水线全部完成"

        parent.progress_current = 100
        parent.progress_total = 100
        db.commit()

        summary = f"三阶段式链式执行完成：{total_chunks} 个 chunk"
        if failed_l0_indices:
            summary += f"，总问题 {', '.join(str(i+1) for i in failed_l0_indices)} 推理树失败"
        _add_task_log(db, parent_task_id, summary)
        logger.info(f"Auto-run pipeline {parent_task_id}: all phases completed (failed L0s: {failed_l0_indices})")


    except Exception as e:
        logger.error(f"Auto-run pipeline {parent_task_id}: unexpected error: {e}\n{traceback.format_exc()}")
        try:
            db.rollback()
            parent = db.query(Task).filter(Task.id == parent_task_id).first()
            if parent:
                parent.status = TaskStatusEnum.FAILED
                parent.progress_label = f"链式执行意外错误"
                db.commit()
        except Exception:
            pass
    finally:
        unregister_task()
        db.close()


def _extract_training_samples(data: dict, cot_step: str) -> list:
    """Extract training-format samples from LLM output data.

    Handles various output structures from different steps:
    - l2_cot: {"l2_cot_nodes": [...]} or {"source_id": "...", "l2_cot_nodes": [...]}
    - l1_cot: {"l1_cot_nodes": [...]}
    - l0_cot: {"l0_cot_node": {...}}  (single object, not a list)
    - cot_gen: {"samples": [...]} or {"sample": {...}}  (single or list)
    """
    samples = []

    # Try known output keys
    for key in ("l2_cot_nodes", "l1_cot_nodes", "samples", "questions"):
        if key in data:
            items = data[key]
            if isinstance(items, list):
                for item in items:
                    sample = _normalize_sample(item)
                    if sample:
                        samples.append(sample)

    # l0_cot_node is a single object
    if "l0_cot_node" in data:
        sample = _normalize_sample(data["l0_cot_node"])
        if sample:
            samples.append(sample)

    # cot_gen single sample
    if "sample" in data and "samples" not in data:
        sample = _normalize_sample(data["sample"])
        if sample:
            samples.append(sample)

    # Fallback: if data itself looks like a list of samples
    if isinstance(data, list):
        for item in data:
            sample = _normalize_sample(item)
            if sample:
                samples.append(sample)

    # Fallback: if data has nested content under another key
    if not samples:
        for key, val in data.items():
            if isinstance(val, list):
                for item in val:
                    sample = _normalize_sample(item)
                    if sample:
                        samples.append(sample)
            elif isinstance(val, dict):
                sample = _normalize_sample(val)
                if sample:
                    samples.append(sample)

    return samples


def _normalize_sample(item: dict) -> Optional[dict]:
    """Normalize a sample dict to the training format: {input, output, chainofThought, level?}."""
    if not isinstance(item, dict):
        return None

    # Must have at least input and output
    if "input" not in item:
        return None

    sample = {
        "input": item.get("input", ""),
        "output": item.get("output", ""),
        "chainofThought": item.get("chainofThought", ""),
    }

    # H-CoT nodes have level field
    if "level" in item:
        sample["level"] = item["level"]

    # Preserve metadata if present
    if "metadata" in item:
        sample["metadata"] = item["metadata"]

    return sample


def _build_hcot_tree(
    l0_question: dict,
    l1_questions: dict,
    l2_cots: dict,
    l1_cots: dict,
    l0_cot: dict,
) -> dict:
    """Build the hierarchical H-CoT tree structure from intermediate outputs.

    The tree format matches the annotation spec's "最终 H-CoT 树" requirement:
    - L0 root node with its question, answer, CoT
    - L1 children with their questions, answers, CoT
    - L2 grandchildren with their questions, answers, CoT
    """
    # Extract L0 question node
    l0_node = _extract_first_node(l0_question, "l0_candidates", "l0_candidate")
    l0_cot_node = _extract_first_node(l0_cot, "l0_cot_nodes", "l0_cot_node")

    if l0_node:
        l0_node["cot"] = l0_cot_node or {}
    else:
        l0_node = l0_cot_node or {"level": "L0", "input": "", "output": "", "chainofThought": ""}

    # Extract L1 question nodes
    l1_nodes = _extract_node_list(l1_questions, "l1_nodes")

    # Extract L2 CoT nodes (grouped by parent_id for tree building)
    l2_cot_list = _extract_node_list(l2_cots, "l2_cot_nodes")
    l1_cot_list = _extract_node_list(l1_cots, "l1_cot_nodes")

    # Build tree: attach L1 nodes with their CoT and L2 children
    l1_tree = []
    for l1q in l1_nodes:
        l1_id = l1q.get("id", "")
        # Find matching L1 CoT
        l1_cot_match = next((n for n in l1_cot_list if n.get("id") == l1_id), None)
        l1q["cot"] = l1_cot_match or {}
        # Find matching L2 CoT children
        l2_children = [n for n in l2_cot_list if n.get("parent_id") == l1_id or n.get("supports") == l1_id]
        l1q["l2_children"] = l2_children
        l1_tree.append(l1q)

    # If no structured L1 questions found, build from L1 CoT directly
    if not l1_tree and l1_cot_list:
        l1_tree = []
        for l1c in l1_cot_list:
            l1_id = l1c.get("id", "")
            l2_children = [n for n in l2_cot_list if n.get("parent_id") == l1_id or n.get("supports") == l1_id]
            l1_tree.append({
                "id": l1_id,
                "level": "L1",
                "input": l1c.get("input", ""),
                "cot": l1c,
                "l2_children": l2_children,
            })

    l0_node["l1_children"] = l1_tree

    return l0_node


def _build_hcot_tree_for_l0(
    l0_question_content: str,
    l1_questions_content: str,
    l2_cots_content: str,
    l1_cots_content: str,
    l0_cot_content: str,
    l0_question_index: int,
) -> dict:
    """Build a single H-CoT tree for a specific L0 question from content strings.

    Similar to _build_hcot_tree but accepts raw JSON content strings and
    filters by l0_question_index where needed.
    """
    # Parse JSON content strings
    l0_question = {}
    l1_questions = {}
    l2_cots = {}
    l1_cots = {}
    l0_cot = {}

    # Parse each content string individually (cannot use locals() dict modification — unreliable in CPython)
    try:
        parsed = json.loads(l0_question_content)
        if l0_question_index > 0:
            specific_l0 = _extract_l0_question_by_index(l0_question_content, l0_question_index)
            if specific_l0:
                parsed = json.loads(specific_l0)
        l0_question = parsed
    except json.JSONDecodeError:
        pass

    try:
        l1_questions = json.loads(l1_questions_content)
    except json.JSONDecodeError:
        pass

    try:
        l2_cots = json.loads(l2_cots_content)
    except json.JSONDecodeError:
        pass

    try:
        l1_cots = json.loads(l1_cots_content)
    except json.JSONDecodeError:
        pass

    try:
        l0_cot = json.loads(l0_cot_content)
    except json.JSONDecodeError:
        pass

    return _build_hcot_tree(l0_question, l1_questions, l2_cots, l1_cots, l0_cot)


def _extract_first_node(data: dict, list_key: str, single_key: str) -> Optional[dict]:
    """Extract the first node from an LLM output, trying both list and single keys."""
    if not isinstance(data, dict):
        return None
    # Try list key first
    if list_key in data and isinstance(data[list_key], list) and data[list_key]:
        return data[list_key][0]
    # Try single key
    if single_key in data and isinstance(data[single_key], dict):
        return data[single_key]
    return None


def _extract_node_list(data: dict, list_key: str) -> list:
    """Extract a list of nodes from an LLM output."""
    if not isinstance(data, dict):
        return []
    if list_key in data and isinstance(data[list_key], list):
        return data[list_key]
    # Fallback: look for any list value that contains dicts with 'id' or 'input'
    for key, val in data.items():
        if isinstance(val, list):
            return val
    return []


# ---------------------------------------------------------------------------
# Workflow status aggregation
# ---------------------------------------------------------------------------


def get_workflow_status(db: Session, parent_task_id: int, user_id: int) -> Optional[dict]:
    """Get the full workflow status: parent task + all sub-tasks organized by phase.

    Returns a structure with phases:
    - Phase 1 (per-chunk): fact_card_gen per chunk
    - Phase 2 (document): merge_fact_cards, sanitize, l0_gen (or question_gen, cot_gen for CoT)
    - Phase 3 (per-L0): l1_decompose, l2_decompose, etc. per L0 question (H-CoT only)
    - Phase 4 (document): quality_check, export_jsonl
    """

    parent = db.query(Task).filter(
        Task.id == parent_task_id,
        Task.user_id == user_id,
        Task.stage == StageEnum.COT_HCOT_PIPELINE,
    ).first()
    if not parent:
        return None

    sub_tasks = db.query(Task).filter(
        Task.parent_task_id == parent_task_id,
    ).order_by(Task.id.asc()).all()

    mode = parent.pipeline_mode or "hcot"
    step_order = get_step_order(mode)

    # --- Helper: 构建 step_info ---
    def _make_step_info(step_name: str, sub: Optional[Task]) -> dict:
        display, prompt_pattern, input_sources, is_hcot_only, granularity = PIPELINE_STEPS.get(
            step_name, (step_name, "", None, False, "document")
        )
        step_info = {
            "step_name": step_name,
            "display_name": display,
            "is_hcot_only": is_hcot_only,
            "granularity": granularity,
            "needs_llm": prompt_pattern is not None,
            "status": "pending",
            "task_id": None,
            "output_file_id": None,
            "output_filename": None,
            "progress_current": 0,
            "progress_total": 100,
            "progress_label": "",
            "l0_question_index": None,
        }

        if sub:
            step_info["status"] = sub.status.value if isinstance(sub.status, TaskStatusEnum) else sub.status
            step_info["task_id"] = sub.id
            step_info["progress_current"] = sub.progress_current or 0
            step_info["progress_total"] = 100
            step_info["l0_question_index"] = sub.l0_question_index if sub.l0_question_index is not None else None
            if sub.progress_label:
                step_info["progress_label"] = sub.progress_label
            else:
                if sub.status == TaskStatusEnum.RUNNING:
                    step_info["progress_label"] = "正在执行..."
                elif sub.status == TaskStatusEnum.COMPLETED:
                    step_info["progress_label"] = "已完成"
                elif sub.status == TaskStatusEnum.FAILED:
                    step_info["progress_label"] = "失败"
            step_info["task_id"] = sub.id
            if sub.file_id:
                out_file = db.query(File).filter(File.id == sub.file_id).first()
                if out_file:
                    step_info["output_file_id"] = out_file.id
                    step_info["output_filename"] = out_file.filename

        return step_info

    # --- Phase 1: per-chunk fact_card_gen ---
    phase1_chunks = []
    all_completed_steps = []

    total_chunks = parent.total_chunks or 0

    for chunk_idx in range(total_chunks):
        chunk_steps = []
        sub = next(
            (t for t in sub_tasks if t.step_name == "fact_card_gen" and t.chunk_index == chunk_idx),
            None,
        )
        step_info = _make_step_info("fact_card_gen", sub)
        if sub and sub.status == TaskStatusEnum.COMPLETED:
            all_completed_steps.append("fact_card_gen")
        chunk_steps.append(step_info)

        phase1_chunks.append({
            "chunk_index": chunk_idx,
            "steps": chunk_steps,
        })

    # --- Phase 2: document-level steps ---
    phase2_steps = []
    doc_steps_phase2 = ["merge_fact_cards", "sanitize"]
    if mode == "hcot":
        doc_steps_phase2.append("l0_gen")
    else:
        doc_steps_phase2.extend(["question_gen", "cot_gen"])

    for step_name in doc_steps_phase2:
        sub = next(
            (t for t in sub_tasks if t.step_name == step_name and
             t.chunk_index is None and t.l0_question_index is None),
            None,
        )
        step_info = _make_step_info(step_name, sub)
        if sub and sub.status == TaskStatusEnum.COMPLETED:
            all_completed_steps.append(step_name)
        phase2_steps.append(step_info)

    # --- Phase 3: per-L0 reasoning tree (H-CoT only) ---
    phase3_l0_questions = []

    if mode == "hcot":
        # Determine number of L0 questions from l0_gen output or sub-tasks
        l0_gen_sub = next(
            (t for t in sub_tasks if t.step_name == "l0_gen" and t.status == TaskStatusEnum.COMPLETED),
            None,
        )
        num_l0_questions = 1
        if l0_gen_sub and l0_gen_sub.file_id:
            l0_gen_content = _read_file_content(db, l0_gen_sub.file_id)
            if l0_gen_content:
                num_l0_questions = _count_l0_questions(l0_gen_content)

        # Also check actual sub-task l0_question_index values
        max_l0_idx = max(
            (t.l0_question_index for t in sub_tasks if t.l0_question_index is not None),
            default=-1,
        )
        num_l0_questions = max(num_l0_questions, max_l0_idx + 1)

        l0_steps_names = ["l1_decompose", "l2_decompose", "l2_cot", "l1_cot", "l0_cot"]

        for l0_idx in range(num_l0_questions):
            l0_steps = []
            for step_name in l0_steps_names:
                sub = next(
                    (t for t in sub_tasks if t.step_name == step_name and
                     t.chunk_index is None and t.l0_question_index == l0_idx),
                    None,
                )
                step_info = _make_step_info(step_name, sub)
                if sub and sub.status == TaskStatusEnum.COMPLETED:
                    all_completed_steps.append(f"{step_name}_l0_{l0_idx}")
                l0_steps.append(step_info)

            phase3_l0_questions.append({
                "l0_question_index": l0_idx,
                "steps": l0_steps,
            })

    # --- Phase 4: document-level final steps ---
    phase4_steps = []
    final_steps = ["quality_check", "export_jsonl"]

    for step_name in final_steps:
        sub = next(
            (t for t in sub_tasks if t.step_name == step_name and
             t.chunk_index is None and t.l0_question_index is None),
            None,
        )
        step_info = _make_step_info(step_name, sub)
        if sub and sub.status == TaskStatusEnum.COMPLETED:
            all_completed_steps.append(step_name)
        phase4_steps.append(step_info)

    # --- Determine next runnable step ---
    completed_step_names = []
    for cs in all_completed_steps:
        # Extract step_name from "step_name_l0_N" or just "step_name"
        step_name = cs.split("_l0_")[0] if "_l0_" in cs else cs
        if step_name not in completed_step_names:
            completed_step_names.append(step_name)
    next_step = get_next_step(mode, completed_step_names)

    # --- Calculate overall progress ---
    all_step_infos = []
    for chunk in phase1_chunks:
        all_step_infos.extend(chunk["steps"])
    all_step_infos.extend(phase2_steps)
    for l0q in phase3_l0_questions:
        all_step_infos.extend(l0q["steps"])
    all_step_infos.extend(phase4_steps)

    completed_count = len(all_completed_steps)
    total_steps = len(all_step_infos)

    # Determine overall pipeline status
    any_running = any(s["status"] == "running" for s in all_step_infos)
    any_failed = any(s["status"] == "failed" for s in all_step_infos)
    all_completed = completed_count >= total_steps


    if any_running:
        pipeline_status = "running"
    elif any_failed:
        pipeline_status = "failed"
    elif all_completed:
        pipeline_status = "completed"
    else:
        pipeline_status = "pending"

    # Update parent task status
    if parent.status.value != pipeline_status:
        try:
            status_enum = TaskStatusEnum(pipeline_status)
            parent.status = status_enum
            db.commit()
        except ValueError:
            pass

    # Get source file info
    source_file = None
    if parent.source_file_id:
        sf = db.query(File).filter(File.id == parent.source_file_id).first()
        if sf:
            source_file = {
                "id": sf.id,
                "filename": sf.filename,
                "file_type": sf.file_type,
            }

    # Determine l0_question_count for H-CoT mode
    l0_question_count = len(phase3_l0_questions)

    return {
        "parent_task": {
            "id": parent.id,
            "pipeline_mode": parent.pipeline_mode,
            "pipeline_name": parent.pipeline_name,
            "model": parent.model,
            "status": pipeline_status,
            "created_at": parent.created_at.isoformat() if parent.created_at else None,
            "source_file": source_file,
        },
        "phases": [
            {
                "phase_name": "per_chunk",
                "label": "阶段1: 分段事实卡生成",
                "chunks": phase1_chunks,
            },
            {
                "phase_name": "document",
                "label": "阶段2: 全文级处理",
                "steps": phase2_steps,
            },
            {
                "phase_name": "per_l0",
                "label": "阶段3: 推理树构建",
                "l0_questions": phase3_l0_questions,
            },
            {
                "phase_name": "document_final",
                "label": "阶段4: 质检与导出",
                "steps": phase4_steps,
            },
        ],
        "total_chunks": total_chunks,
        "l0_question_count": l0_question_count,
        "completed_steps": completed_count,
        "total_steps": total_steps,

        "next_step": next_step,
        "total_steps": len(step_order),
    }


def list_workflows(db: Session, user_id: int) -> List[dict]:
    """List all pipeline parent tasks for the given user."""
    parents = db.query(Task).filter(
        Task.user_id == user_id,
        Task.stage == StageEnum.COT_HCOT_PIPELINE,
        Task.parent_task_id.is_(None),
    ).order_by(Task.id.desc()).all()

    result = []
    for p in parents:
        completed_count = db.query(Task).filter(
            Task.parent_task_id == p.id,
            Task.status == TaskStatusEnum.COMPLETED,
        ).count()

        total_steps = len(get_step_order(p.pipeline_mode or "hcot"))

        source_file = None
        if p.source_file_id:
            sf = db.query(File).filter(File.id == p.source_file_id).first()
            if sf:
                source_file = {"id": sf.id, "filename": sf.filename}

        result.append({
            "id": p.id,
            "pipeline_name": p.pipeline_name or f"流水线 #{p.id}",
            "pipeline_mode": p.pipeline_mode,
            "model": p.model,
            "status": p.status.value if isinstance(p.status, TaskStatusEnum) else p.status,
            "completed_steps": completed_count,
            "total_steps": total_steps,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "source_file": source_file,
        })

    return result