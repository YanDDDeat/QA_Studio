"""CoT/H-CoT Pipeline service.

Manages the multi-step workflow for generating CoT/H-CoT training data from
research papers.  Each workflow is a parent Task (stage=COT_HCOT_PIPELINE)
with sub-tasks linked via parent_task_id.

H-CoT mode (博士论文): 8 steps + 质检 + 导出
  1. fact_card_gen  → 事实卡生成          输入: 源论文文件 → {content}
  2. sanitize       → 数值抽象             输入: fact_card_gen → {fact_cards}
  3. l0_gen         → L0 总问题生成        输入: sanitize → {fact_cards_sanitized}
  4. l1_decompose   → L1 拆解              输入: l0_gen + sanitize → {l0_input} + {fact_cards_sanitized}
  5. l2_decompose   → L2 拆解              输入: l1_decompose + sanitize → {l1_input} + {fact_cards_sanitized}
  6. l2_cot         → L2 CoT 生成          输入: l2_decompose + sanitize → {l2_input} + {fact_cards_sanitized}
  7. l1_cot         → L1 CoT 生成          输入: l1_decompose + l2_cot → {l1_input} + {l2_cots}
  8. l0_cot         → L0 CoT 生成          输入: l0_gen + l1_cot → {l0_input} + {l1_cots}
  9. quality_check  → 最终质检             输入: l0_cot (或所有CoT) → {cots}
  10. export_jsonl  → 导出训练数据          输入: 所有步骤输出 (纯数据合成, 不调LLM)

CoT mode (研究论文): 4 steps + 质检 + 导出
  1. fact_card_gen  → 事实卡生成           输入: 源论文文件 → {content}
  2. sanitize       → 数值抽象              输入: fact_card_gen → {fact_cards}
  3. question_gen   → 独立问题生成          输入: sanitize → {fact_cards_sanitized}
  4. cot_gen        → 独立 CoT 生成         输入: question_gen + sanitize → {question_input} + {fact_cards_sanitized}
  5. quality_check  → 最终质检              输入: cot_gen → {cots}
  6. export_jsonl   → 导出训练数据           输入: 所有步骤输出 (纯数据合成)
"""

import asyncio
import json
import logging
import os
import traceback
from typing import Dict, List, Optional, Tuple

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
# Pipeline step definitions
# ---------------------------------------------------------------------------

# Step metadata:
#   key = step_name
#   value = (display_name, prompt_name_pattern, input_sources, is_hcot_only)
#
# input_sources: dict mapping prompt placeholder → source step_name
#   e.g. {"content": None} means use source_file (no prior step)
#   e.g. {"fact_cards": "fact_card_gen"} means use fact_card_gen's output file
#   e.g. {"l1_input": "l1_decompose", "l2_cots": "l2_cot"} means combine two inputs
#
# None as source step means "use the pipeline's source_file" (the original paper)

PIPELINE_STEPS = {
    "fact_card_gen":  ("1. 事实卡生成",     "[CoT/H-CoT] 1. 事实卡生成",      {"content": None},                    False),
    "sanitize":       ("2. 数值抽象",        "[CoT/H-CoT] 2. 数值抽象",        {"fact_cards": "fact_card_gen"},      False),
    "l0_gen":         ("3. L0 总问题生成",   "[H-CoT] 3. L0 总问题生成",       {"fact_cards_sanitized": "sanitize"}, True),
    "l1_decompose":   ("4. L1 拆解",         "[H-CoT] 4. L1 拆解",             {"l0_input": "l0_gen", "fact_cards_sanitized": "sanitize"}, True),
    "l2_decompose":   ("5. L2 拆解",         "[H-CoT] 5. L2 拆解",             {"l1_input": "l1_decompose", "fact_cards_sanitized": "sanitize"}, True),
    "l2_cot":         ("6. L2 CoT 生成",     "[H-CoT] 6. L2 CoT 生成",         {"l2_input": "l2_decompose", "fact_cards_sanitized": "sanitize"}, True),
    "l1_cot":         ("7. L1 CoT 生成",     "[H-CoT] 7. L1 CoT 生成",         {"l1_input": "l1_decompose", "l2_cots": "l2_cot"}, True),
    "l0_cot":         ("8. L0 CoT 生成",     "[H-CoT] 8. L0 CoT 生成",         {"l0_input": "l0_gen", "l1_cots": "l1_cot"}, True),
    "question_gen":   ("3. 独立问题生成",     "[CoT] 3. 独立问题生成",           {"fact_cards_sanitized": "sanitize"}, False),
    "cot_gen":        ("4. 独立 CoT 生成",    "[CoT] 4. 独立 CoT 生成",          {"question_input": "question_gen", "fact_cards_sanitized": "sanitize"}, False),
    "quality_check":  ("最终质检",            "[CoT/H-CoT] 最终质检",            {"cots": None},                        False),  # cots gathered from all CoT outputs
    "export_jsonl":   ("导出训练数据",        None,                              None,                                  False),  # no LLM prompt, pure data synthesis
}

PIPELINE_STEP_PHASES = {
    "fact_card_gen": [
        (0, 5, "读取源文件"),
        (5, 10, "组装提示词"),
        (10, 85, "调用 LLM 生成事实卡"),
        (85, 95, "解析 LLM 输出"),
        (95, 100, "写入输出文件"),
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
    "fact_card_gen", "sanitize", "l0_gen", "l1_decompose", "l2_decompose",
    "l2_cot", "l1_cot", "l0_cot", "quality_check", "export_jsonl",
]

COT_STEP_ORDER = [
    "fact_card_gen", "sanitize", "question_gen", "cot_gen", "quality_check", "export_jsonl",
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

def find_prompt_for_step(db: Session, step_name: str, user_id: int) -> Optional[Prompt]:
    """Find the default Prompt for a given pipeline step."""
    if step_name not in PIPELINE_STEPS:
        return None

    _, prompt_pattern, _, _ = PIPELINE_STEPS[step_name]

    # export_jsonl has no prompt
    if prompt_pattern is None:
        return None

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


def _get_step_output_file_id(db: Session, parent_task_id: int, step_name: str) -> Optional[int]:
    """Find the output file_id for a completed sub-task of the given step."""
    sub = db.query(Task).filter(
        Task.parent_task_id == parent_task_id,
        Task.step_name == step_name,
        Task.status == TaskStatusEnum.COMPLETED,
    ).first()
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
# Input assembly — combine outputs from prior steps into the prompt
# ---------------------------------------------------------------------------

def _assemble_step_inputs(
    db: Session,
    parent_task_id: int,
    source_file_id: int,
    step_name: str,
) -> Optional[Dict[str, str]]:
    """Read all required input files for a step and return placeholder→content mapping.

    Returns dict like {"content": "论文全文...", "fact_cards_sanitized": "JSON..."}
    or None if any required input is missing.
    """
    step_meta = PIPELINE_STEPS.get(step_name)
    if not step_meta:
        return None

    _, _, input_sources, _ = step_meta

    # Special handling for quality_check: gather ALL CoT outputs
    if step_name == "quality_check":
        mode = _get_pipeline_mode(db, parent_task_id)
        if not mode:
            return None
        step_order = get_step_order(mode)

        # Collect all CoT-related outputs (l2_cot, l1_cot, l0_cot for hcot; cot_gen for cot)
        cot_step_names = []
        if mode == "hcot":
            cot_step_names = ["l2_cot", "l1_cot", "l0_cot"]
        else:
            cot_step_names = ["cot_gen"]

        all_cot_content = []
        for cot_step in cot_step_names:
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
            # Use the output of a prior step
            file_id = _get_step_output_file_id(db, parent_task_id, source_step)
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
    if "fact_card_gen" in all_steps_data:
        final_data["fact_cards"] = all_steps_data["fact_card_gen"]
    if "sanitize" in all_steps_data:
        final_data["fact_cards_sanitized"] = all_steps_data["sanitize"]

    if mode == "hcot":
        l0_cot = all_steps_data.get("l0_cot", {})
        l1_cots = all_steps_data.get("l1_cot", {})
        l2_cots = all_steps_data.get("l2_cot", {})
        l0_question = all_steps_data.get("l0_gen", {})
        l1_questions = all_steps_data.get("l1_decompose", {})
        l2_questions = all_steps_data.get("l2_decompose", {})

        final_data["l0_question"] = l0_question
        final_data["l1_questions"] = l1_questions
        final_data["l2_questions"] = l2_questions
        final_data["l0_cot"] = l0_cot
        final_data["l1_cots"] = l1_cots
        final_data["l2_cots"] = l2_cots

        tree = _build_hcot_tree(l0_question, l1_questions, l2_cots, l1_cots, l0_cot)
        final_data["hcot_tree"] = tree

        training_samples = []
        for step_key in ["l2_cot", "l1_cot", "l0_cot"]:
            if step_key in all_steps_data:
                samples = _extract_training_samples(all_steps_data[step_key], step_key)
                training_samples.extend(samples)
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
    _, _, input_sources, _ = step_meta

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
):
    """一键链式执行：当前步完成→自动启动下一步，直到全部完成或某步失败。

    每步在独立线程+独立 session 中执行（不阻塞 FastAPI 事件循环），
    主协程只负责创建子任务、检查结果、推进下一步。
    前端轮询可正常获取实时进度。
    """
    db = SessionLocal()
    register_task()
    try:
        parent = db.query(Task).filter(Task.id == parent_task_id).first()
        if not parent:
            logger.error(f"Auto-run: parent task {parent_task_id} not found")
            return

        step_order = get_step_order(mode)

        for step_name in step_order:
            # 检查是否已有已完成的子任务（auto-continue 场景）
            existing_completed = db.query(Task).filter(
                Task.parent_task_id == parent_task_id,
                Task.step_name == step_name,
                Task.status == TaskStatusEnum.COMPLETED,
            ).first()
            if existing_completed:
                logger.info(f"Auto-run: step '{step_name}' already completed, skipping")
                continue

            # 检查是否有失败的子任务需要重试
            existing_failed = db.query(Task).filter(
                Task.parent_task_id == parent_task_id,
                Task.step_name == step_name,
                Task.status == TaskStatusEnum.FAILED,
            ).first()
            if existing_failed:
                existing_failed.status = TaskStatusEnum.PAUSED
                db.commit()

            step_meta = PIPELINE_STEPS.get(step_name)
            display, prompt_pattern, input_sources, is_hcot_only = step_meta

            input_file_id = _determine_primary_input_file_id(
                db, parent_task_id, source_file_id or parent.source_file_id, step_name, step_order
            )

            # 更新父任务进度标签：当前执行到哪一步
            parent.progress_label = f"正在执行: {display}"
            db.commit()

            # 创建子任务（状态=RUNNING）
            sub_task = Task(
                user_id=user_id,
                stage=StageEnum.COT_HCOT_PIPELINE,
                status=TaskStatusEnum.RUNNING,
                model=model,
                source_file_id=input_file_id,
                parent_task_id=parent_task_id,
                step_name=step_name,
                progress_current=0,
                progress_total=100,
                progress_label="准备执行...",
            )

            if step_name == "export_jsonl":
                sub_task.source_file_id = parent.source_file_id
            else:
                prompt_obj = find_prompt_for_step(db, step_name, user_id)
                if not prompt_obj:
                    logger.error(f"Auto-run: no prompt found for step '{step_name}'")
                    parent.status = TaskStatusEnum.FAILED
                    parent.progress_label = f"找不到步骤 '{step_name}' 的提示词"
                    db.commit()
                    return
                sub_task.prompt_id = prompt_obj.id

            db.add(sub_task)
            db.commit()
            db.refresh(sub_task)

            # 在独立线程中执行该步骤（不阻塞事件循环）
            if step_name == "export_jsonl":
                success = await asyncio.to_thread(
                    _run_export_step_in_thread,
                    sub_task_id=sub_task.id,
                    parent_task_id=parent_task_id,
                    user_id=user_id,
                    username=username,
                )
            else:
                prompt_obj = find_prompt_for_step(db, step_name, user_id)
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
                )

            # 刷新主 session 以读取线程写入的最新状态
            db.expire_all()

            if not success:
                parent = db.query(Task).filter(Task.id == parent_task_id).first()
                parent.status = TaskStatusEnum.FAILED
                parent.progress_label = f"步骤 '{display}' 执行失败，链式执行终止"
                db.commit()
                _add_task_log(db, parent_task_id, f"链式执行终止：步骤 '{display}' 失败")
                return

            # 步骤完成 — 更新父任务进度
            parent = db.query(Task).filter(Task.id == parent_task_id).first()
            parent.progress_label = f"已完成: {display}"
            db.commit()

            logger.info(f"Auto-run pipeline {parent_task_id}: step '{step_name}' completed, moving to next")

        # 全部完成
        parent = db.query(Task).filter(Task.id == parent_task_id).first()
        parent.status = TaskStatusEnum.COMPLETED
        parent.progress_label = "全部步骤已完成"
        parent.progress_current = 100
        parent.progress_total = 100
        db.commit()

        _add_task_log(db, parent_task_id, f"一键链式执行完成：全部 {len(step_order)} 步已成功")
        logger.info(f"Auto-run pipeline {parent_task_id}: all steps completed")

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
    """Get the full workflow status: parent task + all sub-tasks with files."""
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

    # Build step status map
    completed_steps = []
    steps_info = []
    for step_name in step_order:
        display, prompt_pattern, input_sources, is_hcot_only = PIPELINE_STEPS.get(
            step_name, (step_name, "", None, False)
        )

        sub = next((t for t in sub_tasks if t.step_name == step_name), None)

        step_info = {
            "step_name": step_name,
            "display_name": display,
            "is_hcot_only": is_hcot_only,
            "needs_llm": prompt_pattern is not None,
            "status": "pending",
            "task_id": None,
            "output_file_id": None,
            "output_filename": None,
            "progress_current": 0,
            "progress_total": 100,
            "progress_label": "",
        }

        if sub:
            step_info["status"] = sub.status.value if isinstance(sub.status, TaskStatusEnum) else sub.status
            step_info["task_id"] = sub.id
            step_info["progress_current"] = sub.progress_current or 0
            step_info["progress_total"] = 100
            # Use progress_label from DB, fallback to status-based label
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

            if sub.status == TaskStatusEnum.COMPLETED:
                completed_steps.append(step_name)

        steps_info.append(step_info)

    # Determine next runnable step
    next_step = get_next_step(mode, completed_steps)

    # Determine overall pipeline status
    any_running = any(s["status"] == "running" for s in steps_info)
    any_failed = any(s["status"] == "failed" for s in steps_info)
    all_completed = len(completed_steps) == len(step_order)

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
        "steps": steps_info,
        "completed_steps": completed_steps,
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