"""DB-based professional CoT construction pipeline.

需求 26：标注流水线2专业 CoT 构建。
使用 Task / CotSample / CotStepLog 表做运行追踪，文件只保留 source.json
和 final_samples.json/jsonl 用于导出/下载兼容。

迁移: manifest.json → MySQL (Task + CotSample + CotStepLog)
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.models.models import (
    CotSample,
    CotStepLog,
    LLMConfig,
    ProfessionalCotTypeStat,
    StageEnum,
    Task,
    TaskStatusEnum,
    User,
)
from app.database import SessionLocal
from app.services.llm_service import LLMCallError, call_llm_json_sync
from app.services.professional_cot_prompt_service import (
    create_run_prompt_snapshot,
    read_prompt_from_snapshot,
)
from app.services.thread_pool import register_task, unregister_task

logger = logging.getLogger("qa_studio.professional_cot")


def _serialize_for_db(value: Any) -> Any:
    """Convert list/dict values to JSON string for Text column storage."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


# ---------------------------------------------------------------------------
#  Constants & discovery
# ---------------------------------------------------------------------------


class _PipelinePausedError(Exception):
    """后台流水线检测到暂停请求时抛出。"""


def _find_project_root() -> Path:
    """Find the project root across local and container layouts."""
    marker = Path("docs") / "background" / "3类COT提示词" / "专业Cot构建.md"
    candidates: List[Path] = []

    env_root = os.getenv("QA_STUDIO_ROOT") or os.getenv("PROJECT_ROOT")
    if env_root:
        candidates.append(Path(env_root))

    current_file = Path(__file__).resolve()
    candidates.extend(current_file.parents)

    cwd = Path.cwd().resolve()
    candidates.append(cwd)
    candidates.extend(cwd.parents)

    candidates.extend([Path("/app"), Path("/workspace"), Path("/code")])

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / marker).exists():
            return resolved

    fallback = current_file.parents[3]
    logger.warning(
        "未找到专业 CoT 提示词目录，使用回退项目根目录: %s；已检查: %s",
        fallback,
        [str(item) for item in seen],
    )
    return fallback


PROJECT_ROOT = _find_project_root()
PROMPT_ROOT = PROJECT_ROOT / "docs" / "background" / "3类COT提示词"
STORAGE_ROOT = PROJECT_ROOT / "storage" / "professional_cot_runs"
SCHEMA_VERSION = "1.0"
PIPELINE_NAME = "单COT生成流水线"
PIPELINE_TYPE = "professional_cot"


# ---------------------------------------------------------------------------
#  Task ↔ file path helpers
# ---------------------------------------------------------------------------


def get_run_dir_by_task_id(task_id: int) -> Path:
    """Return the disk directory for a run, keyed by task_id (int)."""
    return STORAGE_ROOT / str(task_id)


def get_run_dir(run_id: str) -> Path:
    """Backward-compatible helper: resolve directory from a run_id string.

    run_id may be a legacy uuid-style string or a task_id integer-as-string.
    """
    return STORAGE_ROOT / run_id


_RUN_ID_PATTERN = re.compile(r"^\d{14}_[0-9a-f]{8}$")


def validate_run_id(run_id: str) -> str:
    """Validate legacy UUID-style run_id.  New task_id strings pass through."""
    # New-style: integer run_id (task_id as string)
    if str(run_id).isdigit():
        return str(run_id)
    # Old-style: timestamp + hex
    if _RUN_ID_PATTERN.fullmatch(str(run_id or "")):
        return str(run_id)
    raise ValueError("非法 run_id")


# ---------------------------------------------------------------------------
#  Atomic file I/O
# ---------------------------------------------------------------------------


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, path)


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
#  CoT type constants & helpers
# ---------------------------------------------------------------------------

CASE_CARD_FIELDS = [
    "source_id",
    "source_type",
    "material_or_molecule",
    "research_goal",
    "baseline",
    "modification_or_variable",
    "control_samples",
    "performance_metrics",
    "observed_results",
    "mechanism_claim",
    "process_conditions",
    "recipe_components",
    "validation_methods",
    "limitations",
    "failure_or_risk",
    "figures_or_tables",
]

COT_TYPES: List[Dict[str, Any]] = [
    {
        "key": "performance_improvement",
        "display_name": "性能提升路径 CoT",
        "prompt_dir": "性能提升路径CoT",
        "step4": "step4_input_performance_improvement.md",
        "step5": "step5_chain_performance_improvement.md",
        "step6": "step6_output_performance_improvement.md",
        "aliases": ["性能提升路径", "性能提升路径CoT"],
    },
    {
        "key": "structure_property",
        "display_name": "构效关系-结构性能关系 CoT",
        "prompt_dir": "构效关系-结构性能关系CoT",
        "step4": "step4_input_structure_property.md",
        "step5": "step5_chain_structure_property.md",
        "step6": "step6_output_structure_property.md",
        "aliases": ["构效关系", "结构性能关系", "结构-性能关系", "构效关系/结构-性能关系", "构效关系-结构性能关系"],
    },
    {
        "key": "candidate_selection",
        "display_name": "候选分子 / 材料优选决策 CoT",
        "prompt_dir": "候选分子-材料优选决策 CoT",
        "step4": "step4_input_candidate_selection.md",
        "step5": "step5_chain_candidate_selection.md",
        "step6": "step6_output_candidate_selection.md",
        "aliases": ["候选分子", "材料优选决策", "候选优选决策", "候选分子/材料优选决策", "候选分子-材料优选决策"],
    },
    {
        "key": "counterfactual_modification",
        "display_name": "反事实结构改造 CoT",
        "prompt_dir": "反事实结构改造CoT",
        "step4": "step4_input_counterfactual_modification.md",
        "step5": "step5_chain_counterfactual_modification.md",
        "step6": "step6_output_counterfactual_modification.md",
        "aliases": ["反事实结构改造", "反事实结构改造CoT"],
    },
    {
        "key": "failure_diagnosis",
        "display_name": "失败原因诊断 CoT",
        "prompt_dir": "失败原因诊断CoT",
        "step4": "step4_input_failure_diagnosis.md",
        "step5": "step5_chain_failure_diagnosis.md",
        "step6": "step6_output_failure_diagnosis.md",
        "aliases": ["失败原因诊断", "失败原因诊断CoT"],
    },
    {
        "key": "multi_objective_optimization",
        "display_name": "多目标约束优化 CoT",
        "prompt_dir": "多目标约束优化CoT",
        "step4": "step4_input_multi_objective_optimization.md",
        "step5": "step5_chain_multi_objective_optimization.md",
        "step6": "step6_output_multi_objective_optimization.md",
        "aliases": ["多目标约束优化", "多目标约束优化CoT"],
    },
    {
        "key": "mechanism_to_design",
        "display_name": "机理到设计策略迁移 CoT",
        "prompt_dir": "机理到设计策略迁移CoT",
        "step4": "step4_input_mechanism_to_design.md",
        "step5": "step5_chain_mechanism_to_design.md",
        "step6": "step6_output_mechanism_to_design.md",
        "aliases": ["机理到设计策略迁移", "机制到设计策略迁移", "机理到设计策略迁移CoT"],
    },
    {
        "key": "process_optimization",
        "display_name": "实验条件 / 制备工艺优化 CoT",
        "prompt_dir": "实验条件-制备工艺优化CoT",
        "step4": "step4_input_process_optimization.md",
        "step5": "step5_chain_process_optimization.md",
        "step6": "step6_output_process_optimization.md",
        "aliases": ["实验条件", "制备工艺优化", "实验条件/工艺优化", "实验条件/制备工艺优化", "实验条件-制备工艺优化"],
    },
    {
        "key": "experimental_plan",
        "display_name": "实验方案生成 CoT",
        "prompt_dir": "实验方案生成CoT",
        "step4": "step4_input_experimental_plan_generation.md",
        "step5": "step5_chain_experimental_plan_generation.md",
        "step6": "step6_output_experimental_plan_generation.md",
        "aliases": ["实验方案生成", "实验方案生成CoT"],
    },
    {
        "key": "recipe_design",
        "display_name": "实验设计配方 CoT",
        "prompt_dir": "实验设计配方CoT",
        "step4": "step4_input_recipe_design.md",
        "step5": "step5_chain_recipe_design.md",
        "step6": "step6_output_recipe_design.md",
        "aliases": ["实验设计配方", "实验设计配方CoT"],
    },
]

COT_TYPE_BY_KEY = {item["key"]: item for item in COT_TYPES}
COT_ENUM_TEXT = "\n".join(f"{idx + 1}. {item['display_name']}" for idx, item in enumerate(COT_TYPES))


# ---------------------------------------------------------------------------
#  CoT type normalization
# ---------------------------------------------------------------------------


def _normalize_text(value: str) -> str:
    text = str(value or "").lower()
    text = text.replace("cot", "")
    text = re.sub(r"[\s/／\\\-—–_（）()、，:：]+", "", text)
    return text


def normalize_cot_types(values: Any) -> List[Dict[str, Any]]:
    if values is None:
        return []

    raw_items: List[Any] = []
    if isinstance(values, list):
        raw_items = values
    elif isinstance(values, dict):
        known_keys = {"cot_type", "recommended_cot_type", "display_name", "cot_type_key", "key", "type", "name", "cot_type_name"}
        raw_items = [values] if any(key in values for key in known_keys) else list(values.keys())
    elif isinstance(values, str):
        raw_items = [item for item in re.split(r"[\n,，、;；]+", values) if item.strip()]
    else:
        raw_items = [values]

    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_items:
        if isinstance(raw, dict):
            candidate = (
                raw.get("cot_type")
                or raw.get("recommended_cot_type")
                or raw.get("display_name")
                or raw.get("cot_type_key")
                or raw.get("key")
                or raw.get("type")
                or raw.get("name")
                or raw.get("cot_type_name")
                or ""
            )
        else:
            candidate = str(raw)
        normalized = _normalize_text(candidate)
        if not normalized:
            continue

        matched = None
        for cot_type in COT_TYPES:
            aliases = [cot_type["key"], cot_type["display_name"], *cot_type.get("aliases", [])]
            for alias in aliases:
                alias_norm = _normalize_text(alias)
                if normalized == alias_norm or alias_norm in normalized or normalized in alias_norm:
                    matched = cot_type
                    break
            if matched:
                break

        if matched and matched["key"] not in seen:
            seen.add(matched["key"])
            result.append(matched)
    return result


def normalize_cot_type(value: Any) -> Optional[Dict[str, Any]]:
    matches = normalize_cot_types(value)
    return matches[0] if matches else None


def _coerce_cot_type_summary(value: Any) -> Optional[Dict[str, str]]:
    if not value:
        return None

    if isinstance(value, dict):
        key = value.get("key") or value.get("cot_type_key")
        display_name = value.get("display_name") or value.get("cot_type") or value.get("name")
        if key == "multiple" and display_name:
            return {"key": "multiple", "display_name": str(display_name)}

    matched = normalize_cot_type(value)
    if matched:
        return {"key": matched["key"], "display_name": matched["display_name"]}
    return None


def _collect_cot_types_from_samples(samples: Iterable[Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        candidates = [
            sample.get("cot_type"),
            sample.get("cot_type_key"),
            sample.get("recommended_cot_type"),
            sample.get("target_cot_type"),
        ]
        final_sample = sample.get("final_sample")
        if isinstance(final_sample, dict):
            candidates.extend([
                final_sample.get("cot_type"),
                final_sample.get("cot_type_key"),
                final_sample.get("recommended_cot_type"),
                final_sample.get("target_cot_type"),
            ])
        for candidate in candidates:
            matched = normalize_cot_type(candidate)
            if matched and matched["key"] not in seen:
                seen.add(matched["key"])
                result.append(matched)
                break
    return result


def _build_cot_type_summary(cot_types: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    if not cot_types:
        return None
    if len(cot_types) == 1:
        cot_type = cot_types[0]
        return {"key": cot_type["key"], "display_name": cot_type["display_name"]}
    display_names = "、".join(item["display_name"] for item in cot_types)
    return {"key": "multiple", "display_name": f"多类型（{display_names}）"}


def _infer_cot_type_summary_from_samples(samples: Iterable[Any]) -> Optional[Dict[str, str]]:
    return _build_cot_type_summary(_collect_cot_types_from_samples(samples))


# ---------------------------------------------------------------------------
#  全局COT类型优先队列均衡分配
# ---------------------------------------------------------------------------


def allocate_cot_type_from_pool(candidate_keys: List[str]) -> Optional[Dict[str, Any]]:
    """从候选池中选全局计数最小的COT类型，分配后计数+1。"""
    if not candidate_keys:
        return None

    valid_keys = [k for k in candidate_keys if k in COT_TYPE_BY_KEY]
    if not valid_keys:
        return None

    db = SessionLocal()
    try:
        rows = db.query(ProfessionalCotTypeStat).filter(
            ProfessionalCotTypeStat.cot_type_key.in_(valid_keys)
        ).all()

        count_map: Dict[str, int] = {}
        for row in rows:
            count_map[row.cot_type_key] = row.count
        for k in valid_keys:
            if k not in count_map:
                count_map[k] = 0

        min_key = min(valid_keys, key=lambda k: count_map[k])
        min_count = count_map[min_key]
        target = COT_TYPE_BY_KEY[min_key]

        stat_row = db.query(ProfessionalCotTypeStat).filter(
            ProfessionalCotTypeStat.cot_type_key == min_key
        ).first()
        if stat_row:
            stat_row.count = min_count + 1
        else:
            stat_row = ProfessionalCotTypeStat(
                cot_type_key=min_key,
                display_name=target["display_name"],
                count=1,
            )
            db.add(stat_row)
        db.commit()

        logger.info(
            "优先队列分配: 文献候选池 %s → 选择 %s (全局计数 %d→%d)",
            valid_keys, target["display_name"], min_count, min_count + 1,
        )
        return target
    except Exception as exc:
        db.rollback()
        logger.warning("优先队列分配失败，回退到LLM推荐: %s", exc)
        return None
    finally:
        db.close()


def get_cot_type_distribution() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(ProfessionalCotTypeStat).all()
        row_map = {row.cot_type_key: row.count for row in rows}
        return [
            {
                "key": item["key"],
                "display_name": item["display_name"],
                "count": row_map.get(item["key"], 0),
            }
            for item in COT_TYPES
        ]
    except Exception:
        return [
            {"key": item["key"], "display_name": item["display_name"], "count": 0}
            for item in COT_TYPES
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
#  Step log helper (DB)
# ---------------------------------------------------------------------------


def _log_step(
    db: Any,
    task_id: int,
    source_index: int,
    step_key: str,
    **kwargs: Any,
) -> None:
    """Upsert a CotStepLog row for a given task/source_index/step_key."""
    existing = db.query(CotStepLog).filter(
        CotStepLog.task_id == task_id,
        CotStepLog.source_index == source_index,
        CotStepLog.step_key == step_key,
    ).first()
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
    else:
        log = CotStepLog(task_id=task_id, source_index=source_index, step_key=step_key, **kwargs)
        db.add(log)
    db.commit()


_STEP_ORDER = ["step1_3_integrated", "step4_input", "step5_chain", "step6_output"]


def _mark_failed_step(db: Any, task_id: int, source_index: int, error: str) -> None:
    """When a document fails mid-pipeline, mark the running step as failed
    and subsequent steps as skipped, so the UI shows the correct culprit."""
    existing = db.query(CotStepLog).filter(
        CotStepLog.task_id == task_id,
        CotStepLog.source_index == source_index,
    ).all()
    status_map = {log.step_key: log.status for log in existing}

    failed_marked = False
    for step_key in _STEP_ORDER:
        current = status_map.get(step_key)
        if current == "running":
            _log_step(db, task_id, source_index, step_key,
                      status="failed", error_message=error)
            failed_marked = True
        elif current is None and failed_marked:
            _log_step(db, task_id, source_index, step_key,
                      status="skipped", error_message=error)
        elif current is None:
            # step not yet created → also mark as skipped (prevent "pending" ghost)
            _log_step(db, task_id, source_index, step_key,
                      status="skipped", error_message=error)


# ---------------------------------------------------------------------------
#  Per-document artifact file helpers
# ---------------------------------------------------------------------------


def _sanitize_dirname(name: str) -> str:
    text = str(name or "").strip()
    text = re.sub(r"[/\\:<>|?*\x00-\x1f\"]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "unnamed"
    return text[:64]


def _document_output_dir(run_dir: Path, source_index: int, source_label: str) -> Path:
    seq = str(source_index + 1).zfill(4)
    sanitized = _sanitize_dirname(source_label)
    return run_dir / "documents" / f"{seq}_{sanitized}"


# ---------------------------------------------------------------------------
#  create_initial_run (DB Task row)
# ---------------------------------------------------------------------------


def create_initial_run(
    *,
    source_data: List[Dict[str, Any]],
    source_filename: str,
    text_field: str,
    paper_text: str,
    user_id: int,
    username: str,
    llm_config: LLMConfig,
    model: str,
    run_name: Optional[str] = None,
    source_file_id: Optional[int] = None,
    prompt_template_id: Optional[str] = None,
    source_type: Optional[str] = "unknown",
) -> Dict[str, Any]:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    llm_info = {
        "llm_config_id": llm_config.id,
        "llm_config_name": llm_config.name,
        "model": model,
        "base_url": llm_config.base_url,
        "api_key": llm_config.api_key,
    }

    input_count = len(source_data)

    db = SessionLocal()
    try:
        task = Task(
            user_id=user_id,
            stage=StageEnum.PROFESSIONAL_COT,
            pipeline_mode="professional_cot",
            pipeline_name=PIPELINE_NAME,
            status=TaskStatusEnum.RUNNING,
            model=model,
            source_file_id=source_file_id,
            input_count=input_count,
            success_count=0,
            failed_count=0,
            progress_current=0,
            progress_total=input_count,
            progress_label="初始化中…",
            prompt_template_id=prompt_template_id,
            run_extra={
                "run_name": run_name or f"{PIPELINE_NAME}-{source_filename}",
                "username": username,
                "source_file": {"id": source_file_id, "filename": source_filename},
                "source_input": {"text_field": text_field, "text_length": len(paper_text), "input_count": input_count},
                "source_type": source_type or "unknown",
                "llm_config_id": llm_config.id,
                "llm_config_name": llm_config.name,
                "cot_types": [{"key": item["key"], "display_name": item["display_name"]} for item in COT_TYPES],
            },
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
    finally:
        db.close()

    # Disk artifacts for export compatibility
    run_dir = get_run_dir_by_task_id(task_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(run_dir / "source.json", source_data)

    source_input_payload = {
        "text_field": text_field,
        "input_count": input_count,
        "paper_text": paper_text,
        "records": [
            {
                "source_index": idx,
                "source": record.get("source", f"item_{idx + 1}"),
                "text_length": len(record.get(text_field, "")),
            }
            for idx, record in enumerate(source_data)
        ],
    }
    atomic_write_json(run_dir / "source_input.json", source_input_payload)

    # Record prompt template snapshot
    prompt_snapshot = create_run_prompt_snapshot(prompt_template_id, user_id, task_id)

    return {
        "task_id": task_id,
        "run_id": str(task_id),
        "llm": llm_info,
        "input_count": input_count,
        "manifest": prompt_snapshot,  # backward compat for frontend
    }


# ---------------------------------------------------------------------------
#  _write_final_samples_json_for_export
# ---------------------------------------------------------------------------


def _write_final_samples_json_for_export(run_dir: Path, cot_samples: List[CotSample]) -> None:
    """Write final_samples.json and .jsonl from CotSample DB rows (for export)."""
    ordered_samples = []
    for idx, s in enumerate(cot_samples, start=1):
        ordered = {
            "id": idx,
            "source_type": s.source_type or "unknown",
            "source_index": s.source_index,
            "source": s.source,
            "cot_type": s.cot_type,
            "cot_type_key": s.cot_type_key,
            "input": s.input,
            "chainofThought": s.chainofThought,
            "output": s.output,
            "evidence_trace": s.evidence_trace,
        }
        ordered_samples.append(ordered)

    final_json = {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(run_dir.name),
        "pipeline_name": PIPELINE_NAME,
        "sample_count": len(ordered_samples),
        "samples": ordered_samples,
    }
    atomic_write_json(run_dir / "final_samples.json", final_json)
    jsonl_content = "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in ordered_samples)
    atomic_write_text(run_dir / "final_samples.jsonl", jsonl_content)


# ---------------------------------------------------------------------------
#  process_one_document (DB-based step logging)
# ---------------------------------------------------------------------------


def process_one_document(
    *,
    source_index: int,
    source_label: str,
    paper_text: str,
    text_field: str,
    run_dir: Path,
    prompt_template_id: Optional[str],
    task_id: int,
    user_id: int,
    llm: Dict[str, Any],
    username: str,
    source_id: Optional[str] = None,
    source_type: Optional[str] = None,
    input_count: int = 1,
    db: Any,
) -> Dict[str, Any]:
    """Execute the integrated 4-node professional CoT pipeline for one document.

    Uses CotStepLog for step tracking instead of manifest.json.
    """
    doc_dir = _document_output_dir(run_dir, source_index, source_label)
    doc_dir.mkdir(parents=True, exist_ok=True)

    doc_rel_prefix = f"documents/{str(source_index + 1).zfill(4)}_{_sanitize_dirname(source_label)}/"

    # Write per-document input.json
    atomic_write_json(doc_dir / "input.json", {
        "source_index": source_index,
        "source": source_label,
        "text_field": text_field,
        "text_length": len(paper_text),
    })

    def _pause_check() -> None:
        """Re-query Task status from DB to detect pause requests."""
        current_task = db.query(Task).filter(Task.id == task_id).first()
        if current_task:
            db.refresh(current_task)
            if current_task.status == TaskStatusEnum.PAUSED:
                logger.info("检测到暂停请求，停止处理文献 task_id=%d", task_id)
                raise _PipelinePausedError("流水线已被暂停")

    try:
        # Integrated Step 1-3: extraction and CoT routing
        _pause_check()
        _log_step(db, task_id, source_index, "step1_3_integrated",
                  status="running", progress_current=10,
                  progress_label=f"文献 {source_index + 1}/{input_count}：抽取信息并判定 CoT 类型")
        step1_3 = _run_step1_3_integrated(
            paper_text,
            source_label=source_label,
            source_id=source_id or source_label,
            source_type=source_type,
            llm=llm,
            username=username,
            prompt_template_id=prompt_template_id,
        )
        candidate_keys = [
            item.get("cot_type_key")
            for item in (step1_3.get("cot_type_judgement") or [])
            if isinstance(item, dict) and item.get("decision") in ("build", "build_with_caution")
        ]
        target = allocate_cot_type_from_pool(candidate_keys)
        if target is None:
            target = normalize_cot_type(step1_3.get("recommended_cot_type_key") or step1_3.get("recommended_cot_type"))
        step1_3_payload = {
            "step": "1-3",
            "step_name": "文献信息抽取与 CoT 类型路由",
            "status": "completed",
            "result": step1_3,
        }
        if target:
            step1_3_payload["cot_type"] = target["display_name"]
            step1_3_payload["cot_type_key"] = target["key"]
        atomic_write_json(doc_dir / "step1_3_integrated_extraction_and_routing.json", step1_3_payload)

        usability = step1_3.get("literature_usability") if isinstance(step1_3.get("literature_usability"), dict) else {}
        usability_decision = usability.get("decision")
        if target and usability_decision != "no":
            _log_step(db, task_id, source_index, "step1_3_integrated",
                      status="completed", progress_current=100,
                      progress_label=f"文献 {source_index + 1}/{input_count}：推荐 {target['display_name']}",
                      cot_type=target["display_name"], cot_type_key=target["key"],
                      artifact_path=f"{doc_rel_prefix}step1_3_integrated_extraction_and_routing.json")

            for step_key, artifact_name in (
                ("step4_input", "step4_input.json"),
                ("step5_chain", "step5_chain.json"),
                ("step6_output", "step6_output.json"),
            ):
                _log_step(db, task_id, source_index, step_key,
                          status="pending", progress_current=0,
                          progress_label=f"文献 {source_index + 1}/{input_count}：等待执行 {target['display_name']}",
                          cot_type=target["display_name"], cot_type_key=target["key"],
                          artifact_path=f"{doc_rel_prefix}{target['key']}/{artifact_name}")
        else:
            if usability_decision == "no":
                reason = usability.get("reason") or "融合节点判断该文献不适合构建当前支持的专业 CoT"
            else:
                next_action = step1_3.get("recommended_next_action") if isinstance(step1_3.get("recommended_next_action"), dict) else {}
                reason = next_action.get("notes_for_next_step") or "融合节点未推荐可构建的 CoT 类型"
                missing_items: List[str] = []
                for item in step1_3.get("cot_type_judgement") or []:
                    if isinstance(item, dict) and item.get("missing_or_risky_evidence"):
                        missing = item.get("missing_or_risky_evidence")
                        if isinstance(missing, list):
                            missing_items.extend(str(value) for value in missing[:2])
                if missing_items:
                    reason = f"{reason}；证据缺口：{'；'.join(missing_items[:5])}"
            _log_step(db, task_id, source_index, "step1_3_integrated",
                      status="completed", progress_current=100, progress_label=reason,
                      artifact_path=f"{doc_rel_prefix}step1_3_integrated_extraction_and_routing.json")
            _log_step(db, task_id, source_index, "step4_input",
                      status="skipped", progress_current=100, progress_label=reason)
            _log_step(db, task_id, source_index, "step5_chain",
                      status="skipped", progress_current=100, progress_label=reason)
            _log_step(db, task_id, source_index, "step6_output",
                      status="skipped", progress_current=100, progress_label=reason)
            return {
                "source_index": source_index,
                "source": source_label,
                "status": "skipped",
                "error": reason,
            }

        # Per-CoT type directory
        type_dir = doc_dir / target["key"]
        type_dir.mkdir(parents=True, exist_ok=True)

        # Step 4
        _pause_check()
        _log_step(db, task_id, source_index, "step4_input",
                  status="running", progress_current=15,
                  progress_label=f"文献 {source_index + 1}/{input_count}：生成 {target['display_name']} input")
        step4 = _run_step4(target, step1_3, llm, username, prompt_template_id)
        atomic_write_json(type_dir / "step4_input.json", {
            "step": 4, "step_name": "生成 input", "status": "completed",
            "cot_type": target["display_name"], "cot_type_key": target["key"],
            "result": step4,
        })
        _log_step(db, task_id, source_index, "step4_input",
                  status="completed", progress_current=100,
                  progress_label=f"文献 {source_index + 1}/{input_count}：input 完成",
                  artifact_path=f"{doc_rel_prefix}{target['key']}/step4_input.json")

        # Step 5
        _pause_check()
        _log_step(db, task_id, source_index, "step5_chain",
                  status="running", progress_current=15,
                  progress_label=f"文献 {source_index + 1}/{input_count}：生成 {target['display_name']} chainofThought")
        step5 = _run_step5(target, step1_3, step4, llm, username, prompt_template_id)
        atomic_write_json(type_dir / "step5_chain.json", {
            "step": 5, "step_name": "生成 chainofThought", "status": "completed",
            "cot_type": target["display_name"], "cot_type_key": target["key"],
            "result": step5,
        })
        _log_step(db, task_id, source_index, "step5_chain",
                  status="completed", progress_current=100,
                  progress_label=f"文献 {source_index + 1}/{input_count}：chainofThought 完成",
                  artifact_path=f"{doc_rel_prefix}{target['key']}/step5_chain.json")

        # Step 6
        _pause_check()
        _log_step(db, task_id, source_index, "step6_output",
                  status="running", progress_current=15,
                  progress_label=f"文献 {source_index + 1}/{input_count}：生成 {target['display_name']} output")
        step6 = _run_step6(target, step4, step5, llm, username, prompt_template_id)
        sample = _build_final_sample(target, step4, step5, step6, source_type=source_type)
        step6_payload = {
            "step": 6, "step_name": "生成 output", "status": "completed",
            "cot_type": target["display_name"], "cot_type_key": target["key"],
            "result": step6, "final_sample": sample,
        }
        atomic_write_json(type_dir / "step6_output.json", step6_payload)
        _log_step(db, task_id, source_index, "step6_output",
                  status="completed", progress_current=100,
                  progress_label=f"文献 {source_index + 1}/{input_count}：output 完成",
                  artifact_path=f"{doc_rel_prefix}{target['key']}/step6_output.json")

        # Enrich sample with source info
        sample["source_index"] = source_index
        sample["source"] = source_label

        # Write per-document final_samples.json
        ordered_sample = {
            "id": 1,
            "source_type": sample.get("source_type", "unknown"),
            "source_index": source_index,
            "source": source_label,
            "cot_type": sample.get("cot_type"),
            "input": sample.get("input"),
            "chainofThought": sample.get("chainofThought"),
            "output": sample.get("output"),
            "evidence_trace": sample.get("evidence_trace"),
        }
        for key in sample:
            if key not in ordered_sample:
                ordered_sample[key] = sample[key]
        atomic_write_json(doc_dir / "final_samples.json", {
            "schema_version": SCHEMA_VERSION,
            "source_index": source_index,
            "source": source_label,
            "sample_count": 1,
            "samples": [ordered_sample],
        })

        return {
            "source_index": source_index,
            "source": source_label,
            "status": "success",
            "final_sample": sample,
            "sample_count": 1,
            "cot_type": target["display_name"],
            "cot_type_key": target["key"],
            "step_results": {
                "step1_3": step1_3,
                "step4": step4,
                "step5": step5,
                "step6": step6,
            },
        }

    except _PipelinePausedError:
        logger.info("文献 %s (#%d) 因暂停请求而中断", source_label, source_index + 1)
        return {
            "source_index": source_index,
            "source": source_label,
            "status": "paused",
            "error": "因暂停请求中断",
        }
    except (LLMCallError, FileNotFoundError, ValueError) as exc:
        logger.error("文献 %s (#%d) 处理失败: %s", source_label, source_index + 1, exc)
        _mark_failed_step(db, task_id, source_index, str(exc)[:500])
        return {
            "source_index": source_index,
            "source": source_label,
            "status": "failed",
            "error": str(exc)[:1000],
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("文献 %s (#%d) 处理意外失败", source_label, source_index + 1)
        _mark_failed_step(db, task_id, source_index, str(exc)[:500])
        return {
            "source_index": source_index,
            "source": source_label,
            "status": "failed",
            "error": str(exc)[:1000],
        }


# ---------------------------------------------------------------------------
#  run_pipeline_sync (DB-based main loop)
# ---------------------------------------------------------------------------


def run_pipeline_sync(task_id: int, llm: Dict[str, Any], username: str) -> None:
    """Run the professional CoT pipeline for all documents in a task.

    Uses Task / CotSample / CotStepLog for all tracking.
    Keeps file artifacts for export compatibility.
    """
    register_task()
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        run_dir = get_run_dir_by_task_id(task_id)
        source_data = read_json(run_dir / "source.json")
        input_count = len(source_data)

        text_field = (task.run_extra or {}).get("source_input", {}).get("text_field", "text")
        prompt_template_id = task.prompt_template_id

        # Reset run state
        task.status = TaskStatusEnum.RUNNING
        task.progress_label = f"正在处理第 1/{input_count} 篇文献"
        task.success_count = 0
        task.failed_count = 0
        db.commit()

        # Resume: find completed documents from CotStepLog
        completed_indices: set[int] = set()
        completed_logs = db.query(CotStepLog).filter(
            CotStepLog.task_id == task_id,
            CotStepLog.source_index >= 0,
            CotStepLog.status.in_(["completed", "failed", "skipped"]),
            CotStepLog.step_key == "step6_output",
        ).all()
        for log in completed_logs:
            completed_indices.add(log.source_index)

        # Load existing samples from cot_samples table
        existing_samples = db.query(CotSample).filter(
            CotSample.task_id == task_id
        ).order_by(CotSample.source_index).all()
        task.success_count = len(existing_samples)
        db.commit()

        for idx, record in enumerate(source_data):
            # Pause detection: re-query task status
            db.refresh(task)
            if task.status == TaskStatusEnum.PAUSED:
                logger.info("检测到暂停请求，停止处理 task %d 于文献 %d/%d", task_id, idx + 1, input_count)
                task.progress_label = f"已暂停（完成 {task.success_count} 篇，于第 {idx + 1}/{input_count} 篇中断）"
                db.commit()
                return

            if idx in completed_indices:
                logger.info("跳过已处理的文献 %d/%d", idx + 1, input_count)
                continue

            source_label = record.get("source", f"item_{idx + 1}")
            paper_text = record.get(text_field, "")

            task.progress_label = f"正在处理第 {idx + 1}/{input_count} 篇文献：{source_label}"
            db.commit()

            doc_result = process_one_document(
                source_index=idx,
                source_label=source_label,
                paper_text=paper_text,
                text_field=text_field,
                run_dir=run_dir,
                prompt_template_id=prompt_template_id,
                task_id=task_id,
                user_id=task.user_id,
                llm=llm,
                username=username,
                source_id=record.get("source_id") or record.get("id") or record.get("doi") or source_label,
                source_type=(task.run_extra or {}).get("source_type", "unknown"),
                input_count=input_count,
                db=db,
            )

            if doc_result.get("status") == "paused":
                logger.info("文献 %d 因暂停中断，退出 run_pipeline_sync", idx + 1)
                return

            if doc_result["status"] == "success":
                sample = CotSample(
                    task_id=task_id,
                    user_id=task.user_id,
                    source_index=idx,
                    source=source_label,
                    source_type=(task.run_extra or {}).get("source_type", "unknown"),
                    cot_type=doc_result.get("cot_type"),
                    cot_type_key=doc_result.get("cot_type_key"),
                    input=_serialize_for_db(doc_result["final_sample"].get("input")),
                    chainofThought=_serialize_for_db(doc_result["final_sample"].get("chainofThought")),
                    output=_serialize_for_db(doc_result["final_sample"].get("output")),
                    evidence_trace=_serialize_for_db(doc_result["final_sample"].get("evidence_trace")),
                    step_results=doc_result.get("step_results"),
                )
                db.add(sample)
                task.success_count += 1
                logger.info("第 %d/%d 篇文献处理完成: %s", idx + 1, input_count, source_label)
            elif doc_result["status"] in ("failed", "skipped"):
                task.failed_count += 1
                logger.warning(
                    "第 %d/%d 篇文献处理失败: %s, 错误: %s",
                    idx + 1, input_count, source_label, doc_result.get("error", ""),
                )

            # Progress update
            task.progress_total = input_count
            task.progress_current = idx + 1
            db.commit()

            # Write final_samples.json to disk (for export)
            all_samples = db.query(CotSample).filter(CotSample.task_id == task_id).all()
            _write_final_samples_json_for_export(run_dir, all_samples)

        # Finished
        if task.success_count > 0:
            task.status = TaskStatusEnum.COMPLETED
            if task.failed_count > 0:
                task.progress_label = f"完成：{task.success_count} 篇成功，{task.failed_count} 篇失败"
            else:
                task.progress_label = f"全部完成，生成 {task.success_count} 条样本"
        elif task.failed_count > 0:
            task.status = TaskStatusEnum.FAILED
            task.progress_label = f"全部 {input_count} 篇文献处理失败"
        else:
            task.status = TaskStatusEnum.PAUSED

        task.sample_count = db.query(CotSample).filter(CotSample.task_id == task_id).count()
        db.commit()

    except Exception as e:
        db.rollback()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                task.run_extra = task.run_extra or {}
                task.run_extra["error_message"] = str(e)
                db.commit()
                logger.exception("professional cot task %d unexpected failure", task_id)
        except Exception:
            pass
    finally:
        db.close()
        unregister_task()


# ---------------------------------------------------------------------------
#  LLM call steps (unchanged from original)
# ---------------------------------------------------------------------------


def _call_json(prompt: str, llm: Dict[str, Any], username: str) -> Dict[str, Any]:
    return call_llm_json_sync(
        prompt=prompt,
        model=llm["model"],
        temperature=0.2,
        base_url_override=llm["base_url"],
        api_key_override=llm["api_key"],
        username=username,
    )


def _read_prompt_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_step_prompt(step_no: int, prompt_template_id: Optional[str] = None) -> str:
    if prompt_template_id is not None:
        return read_prompt_from_snapshot(prompt_template_id, f"common.step{step_no}")
    content = _read_prompt_file(PROMPT_ROOT / "专业Cot构建.md")
    pattern = re.compile(rf"###\s*Step\s*{step_no}[^\n]*\n(.*?)(?=\n###\s*Step\s*\d+|\Z)", re.S | re.I)
    match = pattern.search(content)
    return match.group(0).strip() if match else content


def _extract_step1_3_integrated_prompt(prompt_template_id: Optional[str] = None) -> str:
    if prompt_template_id is not None:
        return read_prompt_from_snapshot(prompt_template_id, "common.step1_3")
    return _read_prompt_file(PROMPT_ROOT / "step1_3_integrated_extraction_and_routing.md")


def _type_prompt(cot_type: Dict[str, Any], step_no: int, prompt_template_id: Optional[str] = None) -> str:
    if prompt_template_id is not None:
        return read_prompt_from_snapshot(prompt_template_id, f"{cot_type['key']}.step{step_no}")
    filename = cot_type[f"step{step_no}"]
    return _read_prompt_file(PROMPT_ROOT / cot_type["prompt_dir"] / filename)


def _json_block(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _require_non_empty_string(value: Any, field_label: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise ValueError(f"{field_label} 必须是非空字符串")
    return text


def _normalize_chainofthought(value: Any) -> List[Any]:
    if isinstance(value, str):
        chain = [line.strip() for line in value.split("\n") if line.strip()]
    elif isinstance(value, list):
        chain = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    chain.append(text)
            elif item not in (None, [], {}):
                chain.append(item)
    else:
        chain = []

    if not chain:
        raise ValueError("chainofThought 必须是非空数组")
    return chain


def _truthy_generation_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in ("true", "yes", "y", "是", "可以", "可生成", "partial"):
        return True
    return False


def _normalize_usability_decision(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in ("yes", "true", "y", "是", "可以", "可用", "适合", "可生成", "build"):
        return "yes"
    if text in ("partial", "partially", "部分", "部分可用", "谨慎", "build_with_caution"):
        return "partial"
    return "no" if text in ("no", "false", "n", "否", "不可用", "不适合", "不可生成", "not_build") else "partial"


def _normalize_cot_judgement_decision(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in ("build", "yes", "true", "可构建", "适合"):
        return "build"
    if text in ("build_with_caution", "caution", "partial", "谨慎构建", "部分可构建"):
        return "build_with_caution"
    return "not_build"


def _normalize_priority(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in ("high", "高", "最高", "优先"):
        return "high"
    if text in ("medium", "mid", "中", "中等"):
        return "medium"
    return "low"


def _select_recommended_from_judgements(judgements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    decision_rank = {"build": 0, "build_with_caution": 1}
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    candidates: List[tuple] = []
    for index, item in enumerate(judgements):
        matched = normalize_cot_type(item.get("cot_type_key") or item.get("cot_type"))
        decision = item.get("decision")
        if matched and decision in decision_rank:
            candidates.append((decision_rank[decision], priority_rank.get(item.get("priority"), 9), index, matched))
    candidates.sort(key=lambda row: (row[0], row[1], row[2]))
    return candidates[0][3] if candidates else None


def _run_step1_3_integrated(
    paper_text: str,
    *,
    source_label: str,
    source_id: Optional[str],
    source_type: Optional[str] = None,
    llm: Dict[str, Any],
    username: str,
    prompt_template_id: Optional[str] = None,
) -> Dict[str, Any]:
    prompt = f"""
{_extract_step1_3_integrated_prompt(prompt_template_id)}

强制约束：
- 本节点只允许完成文献可用性判断、关键信息抽取、CoT 类型路由。
- 不要生成最终 CoT 样本，不要生成训练 input、chainofThought 或 output。
- JSON 顶层必须是对象。
- literature_usability.decision 只能是 yes / partial / no。
- cot_type_judgement[*].decision 只能是 build / build_with_caution / not_build。
- cot_type_judgement[*].priority 只能是 high / medium / low。
- cot_type_judgement[*].cot_type、recommended_next_action.priority_cot_types、types_to_skip 只能使用以下 10 类 CoT 枚举原文：
{COT_ENUM_TEXT}

请按融合提示词中的 JSON 结构输出；如果输入 source_id/source_type 为空，请据实写 null 或 unknown。

source_id: {source_id or source_label or ""}
source_label: {source_label or ""}
source_type: {source_type or "unknown"}
full_literature:
{paper_text}
""".strip()
    result = _call_json(prompt, llm, username)

    usability = result.get("literature_usability") if isinstance(result.get("literature_usability"), dict) else {}
    usability["decision"] = _normalize_usability_decision(
        usability.get("decision") or result.get("decision") or result.get("can_generate")
    )
    usability.setdefault("reason", result.get("reason") or result.get("stop_reason"))
    usability.setdefault("usable_parts", [])
    result["literature_usability"] = usability

    raw_judgements = result.get("cot_type_judgement") or result.get("cot_type_judgments") or result.get("type_judgement") or []
    if isinstance(raw_judgements, dict):
        raw_judgements = list(raw_judgements.values())
    if not isinstance(raw_judgements, list):
        raw_judgements = []

    normalized_judgements: List[Dict[str, Any]] = []
    for raw in raw_judgements:
        if not isinstance(raw, dict):
            continue
        matched = normalize_cot_type(raw.get("cot_type") or raw.get("cot_type_key") or raw.get("type") or raw.get("name"))
        item = dict(raw)
        if matched:
            item["cot_type"] = matched["display_name"]
            item["cot_type_key"] = matched["key"]
        item["decision"] = _normalize_cot_judgement_decision(raw.get("decision") or raw.get("can_build") or raw.get("status"))
        item["priority"] = _normalize_priority(raw.get("priority"))
        item.setdefault("key_evidence", raw.get("evidence") or [])
        item.setdefault("missing_or_risky_evidence", raw.get("missing_information") or [])
        normalized_judgements.append(item)
    result["cot_type_judgement"] = normalized_judgements

    next_action = result.get("recommended_next_action") if isinstance(result.get("recommended_next_action"), dict) else {}
    priority_types = normalize_cot_types(
        next_action.get("priority_cot_types")
        or result.get("priority_cot_types")
        or result.get("recommended_cot_type")
        or result.get("target_cot_type")
    )
    next_action["priority_cot_types"] = [item["display_name"] for item in priority_types]
    next_action["types_to_skip"] = [item["display_name"] for item in normalize_cot_types(next_action.get("types_to_skip") or [])]
    next_action.setdefault("notes_for_next_step", result.get("notes_for_next_step") or result.get("recommendation_reason") or "")
    result["recommended_next_action"] = next_action

    recommended = priority_types[0] if priority_types else _select_recommended_from_judgements(normalized_judgements)
    result["recommended_cot_type"] = recommended["display_name"] if recommended else None
    result["recommended_cot_type_key"] = recommended["key"] if recommended else None
    result["source_id"] = result.get("source_id") or source_id or source_label
    result.setdefault("source_type", "unknown")
    result.setdefault("key_information", {})
    return result


def _run_step4(cot_type: Dict[str, Any], step1_3_result: Dict[str, Any], llm: Dict[str, Any], username: str, prompt_template_id: Optional[str] = None) -> Dict[str, Any]:
    prompt = f"""
{_type_prompt(cot_type, 4, prompt_template_id)}

强制约束：
- 当前 cot_type 固定为：{cot_type['display_name']}。
- 只生成 1 个主 selected_input，alternative_inputs 可为空。
- selected_input 不得出现"根据文献""本文报道""作者发现""图 1""表 1""Figure""Table"等来源表达。
- JSON 顶层必须是对象。

请按以下 JSON 结构输出：
{{
  "cot_type": "{cot_type['display_name']}",
  "selected_input": "...",
  "alternative_inputs": [],
  "evidence_trace": {{}}
}}

step1_3_result：
{_json_block(step1_3_result)}
""".strip()
    result = _call_json(prompt, llm, username)
    selected_input = result.get("selected_input") or result.get("input")
    result["selected_input"] = _require_non_empty_string(selected_input, "Step 4 selected_input 或 input")
    return result


def _run_step5(cot_type: Dict[str, Any], step1_3_result: Dict[str, Any], step4: Dict[str, Any], llm: Dict[str, Any], username: str, prompt_template_id: Optional[str] = None) -> Dict[str, Any]:
    selected_input = step4.get("selected_input") or step4.get("input") or ""
    prompt = f"""
{_type_prompt(cot_type, 5, prompt_template_id)}

强制约束：
- 当前 cot_type 固定为：{cot_type['display_name']}。
- chainofThought 必须是数组。
- 训练文本必须去文献化，不得出现"根据文献""本文报道""作者发现""图 1""表 1""Figure""Table"等来源表达。
- 证据来源只能放入 evidence_used 或 evidence_trace。
- JSON 顶层必须是对象。

请按以下 JSON 结构输出：
{{
  "cot_type": "{cot_type['display_name']}",
  "chainofThought": ["步骤 1：..."],
  "evidence_used": {{}}
}}

input：
{selected_input}

step1_3_result：
{_json_block(step1_3_result)}

Step 4 结果：
{_json_block(step4)}
""".strip()
    result = _call_json(prompt, llm, username)
    chain = result.get("chainofThought") or result.get("chain_of_thought") or result.get("chain") or []
    result["chainofThought"] = _normalize_chainofthought(chain)
    return result


def _run_step6(cot_type: Dict[str, Any], step4: Dict[str, Any], step5: Dict[str, Any], llm: Dict[str, Any], username: str, prompt_template_id: Optional[str] = None) -> Dict[str, Any]:
    selected_input = step4.get("selected_input") or step4.get("input") or ""
    chain = step5.get("chainofThought") or []
    prompt = f"""
{_type_prompt(cot_type, 6, prompt_template_id)}

强制约束：
- 当前 cot_type 固定为：{cot_type['display_name']}。
- output 必须直接回答 input，不要重复完整推理过程。
- 不得出现"根据文献""本文报道""作者发现""图 1""表 1""Figure""Table"等来源表达。
- JSON 顶层必须是对象。

请按以下 JSON 结构输出：
{{
  "cot_type": "{cot_type['display_name']}",
  "output": "...",
  "evidence_trace": {{}},
  "final_sample": {{
    "cot_type": "{cot_type['display_name']}",
    "input": "...",
    "chainofThought": ["步骤 1：..."],
    "output": "...",
    "evidence_trace": {{}}
  }}
}}

input：
{selected_input}

chainofThought：
{_json_block(chain)}

Step 4 结果：
{_json_block(step4)}

Step 5 结果：
{_json_block(step5)}
""".strip()
    result = _call_json(prompt, llm, username)
    final_sample = result.get("final_sample") if isinstance(result.get("final_sample"), dict) else {}
    output = result.get("output") or final_sample.get("output")
    result["output"] = _require_non_empty_string(output, "Step 6 output 或 final_sample.output")
    return result


def _build_final_sample(cot_type: Dict[str, Any], step4: Dict[str, Any], step5: Dict[str, Any], step6: Dict[str, Any], source_type: Optional[str] = None) -> Dict[str, Any]:
    final_sample = step6.get("final_sample") if isinstance(step6.get("final_sample"), dict) else {}
    evidence_trace = (
        final_sample.get("evidence_trace")
        or step6.get("evidence_trace")
        or step5.get("evidence_trace")
        or step5.get("evidence_used")
        or step4.get("evidence_trace")
        or {}
    )
    sample_input = _require_non_empty_string(
        final_sample.get("input") or step4.get("selected_input") or step4.get("input"),
        "final_sample.input",
    )
    chain = _normalize_chainofthought(final_sample.get("chainofThought") or step5.get("chainofThought"))
    output = _require_non_empty_string(
        final_sample.get("output") or step6.get("output"),
        "final_sample.output",
    )
    sample = {
        "cot_type": cot_type["display_name"],
        "input": sample_input,
        "chainofThought": chain,
        "output": output,
        "evidence_trace": evidence_trace,
        "source_type": source_type or "unknown",
    }
    return sample


# ---------------------------------------------------------------------------
#  Recover zombie runs (DB-based)
# ---------------------------------------------------------------------------


def recover_zombie_runs() -> int:
    """Scan Task table for stuck 'running' tasks and mark them as 'paused'."""
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(
            Task.stage == StageEnum.PROFESSIONAL_COT,
            Task.status == TaskStatusEnum.RUNNING,
        ).all()
        count = 0
        for task in tasks:
            task.status = TaskStatusEnum.PAUSED
            task.progress_label = "服务重启后自动暂停，可手动恢复"
            count += 1
            logger.info("恢复僵尸task %d: running → paused", task.id)
        if count:
            db.commit()
            logger.info("共恢复 %d 个僵尸单COT生成流水线task", count)
        return count
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
#  Resume paused run (DB-based)
# ---------------------------------------------------------------------------


def resume_paused_run(run_id: str, user_id: int) -> Dict[str, Any]:
    """Resume a paused or failed run. Updates Task status, returns llm info."""
    try:
        task_id = int(run_id)
    except (ValueError, TypeError):
        raise ValueError("无效的 run_id")

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("任务不存在")
        if task.user_id != user_id:
            raise ValueError("无权操作此任务")

        task.status = TaskStatusEnum.RUNNING
        task.run_extra = task.run_extra or {}
        task.run_extra["error_message"] = None
        task.progress_label = "正在恢复运行..."
        db.commit()

        # Build llm_info from run_extra + LLMConfig
        run_extra = task.run_extra or {}
        llm_config_id = run_extra.get("llm_config_id")
        llm_config_name = run_extra.get("llm_config_name") or ""
        model = task.model or ""
        base_url = ""
        api_key = ""

        if llm_config_id:
            cfg = db.query(LLMConfig).filter(LLMConfig.id == llm_config_id).first()
            if cfg:
                base_url = cfg.base_url or ""
                api_key = cfg.api_key or ""
                model = model or cfg.default_model or ""
        elif llm_config_name:
            # Fallback: lookup by name for tasks created before llm_config_id was saved
            cfg = db.query(LLMConfig).filter(LLMConfig.name == llm_config_name).first()
            if cfg:
                llm_config_id = cfg.id
                base_url = cfg.base_url or ""
                api_key = cfg.api_key or ""
                model = model or cfg.default_model or ""

        llm_info = {
            "llm_config_id": llm_config_id,
            "llm_config_name": llm_config_name,
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
        }

        logger.info("恢复运行 task %d", task_id)
        return llm_info
    finally:
        db.close()


# ---------------------------------------------------------------------------
#  get_running_monitor (SQL aggregation)
# ---------------------------------------------------------------------------


def _task_to_monitor_item(task: Task) -> Dict[str, Any]:
    run_extra = task.run_extra or {}
    return {
        "run_id": str(task.id),
        "run_name": run_extra.get("run_name") or task.pipeline_name,
        "pipeline_name": task.pipeline_name,
        "pipeline_type": PIPELINE_TYPE,
        "status": task.status.value if hasattr(task.status, "value") else str(task.status),
        "progress_percentage": int(task.progress_current / task.progress_total * 100) if task.progress_total else 0,
        "completed_steps": task.success_count or 0,
        "skipped_steps": task.failed_count or 0,
        "failed_steps": 0,
        "total_steps": task.input_count or 0,
        "sample_count": task.sample_count or 0,
        "input_count": task.input_count or 1,
        "success_count": task.success_count or 0,
        "failed_count": task.failed_count or 0,
        "source_filename": (run_extra.get("source_file") or {}).get("filename"),
        "text_field": (run_extra.get("source_input") or {}).get("text_field"),
        "model": task.model,
        "llm_config_name": run_extra.get("llm_config_name", ""),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "progress_label": task.progress_label,
        "error_message": run_extra.get("error_message"),
        "username": run_extra.get("username", "未知"),
        "user_id": task.user_id,
    }


def get_running_monitor() -> Dict[str, Any]:
    """Return monitoring data for admin dashboard via SQL aggregation."""
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(
            Task.stage == StageEnum.PROFESSIONAL_COT,
        ).order_by(Task.id.desc()).all()

        status_counts = {"running": 0, "paused": 0, "completed": 0, "failed": 0}
        user_ids: set[int] = set()
        total_input = 0
        total_success = 0
        total_failed = 0
        all_runs: List[Dict[str, Any]] = []

        for task in tasks:
            item = _task_to_monitor_item(task)
            all_runs.append(item)

            status_value = item["status"]
            status_counts[status_value] = status_counts.get(status_value, 0) + 1

            if task.user_id is not None:
                user_ids.add(task.user_id)
            total_input += task.input_count or 0
            total_success += task.success_count or 0
            total_failed += task.failed_count or 0

        return {
            "running_count": status_counts.get("running", 0),
            "paused_count": status_counts.get("paused", 0),
            "completed_count": status_counts.get("completed", 0),
            "failed_count": status_counts.get("failed", 0),
            "total_count": len(all_runs),
            "active_user_count": len(user_ids),
            "total_input_count": total_input,
            "total_success_count": total_success,
            "total_failed_count": total_failed,
            "runs": all_runs,
            "cot_type_distribution": get_cot_type_distribution(),
        }
    except Exception:
        return {
            "running_count": 0,
            "paused_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "total_count": 0,
            "active_user_count": 0,
            "total_input_count": 0,
            "total_success_count": 0,
            "total_failed_count": 0,
            "runs": [],
            "cot_type_distribution": get_cot_type_distribution(),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
#  list_runs_for_user (DB-based)
# ---------------------------------------------------------------------------


def list_runs_for_user(user_id: int, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """List professional CoT runs owned by user, paginated from Task table."""
    db = SessionLocal()
    try:
        query = db.query(Task).filter(
            Task.user_id == user_id,
            Task.stage == StageEnum.PROFESSIONAL_COT,
        ).order_by(Task.id.desc())

        total = query.count()
        tasks = query.offset((page - 1) * page_size).limit(page_size).all()

        items = []
        for task in tasks:
            items.append(_task_to_monitor_item(task))

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
#  get_run_detail_for_user (DB + file artifacts)
# ---------------------------------------------------------------------------


def _read_run_json_safely(run_dir: Path, rel_path: str) -> Optional[Any]:
    """Read a JSON artifact under run_dir without allowing path traversal."""
    if not rel_path or os.path.isabs(rel_path):
        return None
    try:
        base = run_dir.resolve()
        target = (base / rel_path).resolve()
        if target != base and base not in target.parents:
            return None
        if not target.exists() or not target.is_file():
            return None
        return read_json(target)
    except Exception:
        return None


def _existing_rel_path(run_dir: Path, rel_path: str) -> Optional[str]:
    if not rel_path or os.path.isabs(rel_path):
        return None
    try:
        base = run_dir.resolve()
        target = (base / rel_path).resolve()
        if target != base and base not in target.parents:
            return None
        if target.exists() and target.is_file():
            return target.relative_to(base).as_posix()
    except Exception:
        return None
    return None


DOCUMENT_STAGE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "stage_key": "step1_3_integrated",
        "stage_name": "Step 1-3 文献信息抽取与 CoT 类型路由",
        "step": "1-3",
    },
    {
        "stage_key": "step4_input",
        "stage_name": "Step 4 生成 input",
        "step": 4,
        "artifact_name": "step4_input.json",
    },
    {
        "stage_key": "step5_chain",
        "stage_name": "Step 5 生成 chainofThought",
        "step": 5,
        "artifact_name": "step5_chain.json",
    },
    {
        "stage_key": "step6_output",
        "stage_name": "Step 6 生成 output",
        "step": 6,
        "artifact_name": "step6_output.json",
    },
]


def _extract_document_sources(run_dir: Path) -> List[Dict[str, Any]]:
    source_input = _read_run_json_safely(run_dir, "source_input.json")
    records = source_input.get("records") if isinstance(source_input, dict) else None
    if isinstance(records, list) and records:
        result = []
        for idx, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            source_index = record.get("source_index")
            if not isinstance(source_index, int):
                source_index = idx
            result.append({
                "source_index": source_index,
                "source": record.get("source") or f"item_{source_index + 1}",
            })
        if result:
            return result

    source_data = _read_run_json_safely(run_dir, "source.json")
    if isinstance(source_data, list) and source_data:
        result = []
        for idx, record in enumerate(source_data):
            source = record.get("source") if isinstance(record, dict) else None
            result.append({"source_index": idx, "source": source or f"item_{idx + 1}"})
        return result

    return []


def _find_step1_3_artifact(run_dir: Path, doc_rel_prefix: str) -> Optional[str]:
    for filename in (
        "step1_3_integrated_extraction_and_routing.json",
        "step3_type_judgement.json", "step3.json",
        "step2_case_card.json", "step2.json",
        "step1_screening.json", "step1.json",
    ):
        rel_path = _existing_rel_path(run_dir, f"{doc_rel_prefix}{filename}")
        if rel_path:
            return rel_path
    return None


def _find_typed_step_artifact(
    run_dir: Path, doc_rel_prefix: str, doc_dir: Path,
    cot_type_key: Optional[str], artifact_name: str,
) -> Optional[str]:
    if cot_type_key:
        rel_path = _existing_rel_path(run_dir, f"{doc_rel_prefix}{cot_type_key}/{artifact_name}")
        if rel_path:
            return rel_path

    try:
        if doc_dir.exists():
            known_keys = {item["key"] for item in COT_TYPES}
            for child in doc_dir.iterdir():
                if child.is_dir() and child.name in known_keys:
                    rel_path = _existing_rel_path(run_dir, f"{doc_rel_prefix}{child.name}/{artifact_name}")
                    if rel_path:
                        return rel_path
    except Exception:
        return None
    return None


def _infer_document_cot_type(
    *,
    doc_dir: Path,
    step1_3_data: Optional[Any],
    cot_sample: Optional[CotSample],
) -> Optional[Dict[str, str]]:
    if cot_sample and cot_sample.cot_type:
        matched = normalize_cot_type(cot_sample.cot_type_key or cot_sample.cot_type)
        if matched:
            return {"key": matched["key"], "display_name": matched["display_name"]}

    candidates: List[Any] = []
    if isinstance(step1_3_data, dict):
        candidates.extend([step1_3_data.get("cot_type_key"), step1_3_data.get("cot_type")])
        result = step1_3_data.get("result")
        if isinstance(result, dict):
            candidates.extend([
                result.get("recommended_cot_type_key"),
                result.get("recommended_cot_type"),
            ])
    for value in candidates:
        matched = normalize_cot_type(value)
        if matched:
            return {"key": matched["key"], "display_name": matched["display_name"]}

    try:
        if doc_dir.exists():
            known_keys = {item["key"] for item in COT_TYPES}
            for child in doc_dir.iterdir():
                if child.is_dir() and child.name in known_keys:
                    matched = normalize_cot_type(child.name)
                    if matched:
                        return {"key": matched["key"], "display_name": matched["display_name"]}
    except Exception:
        return None
    return None


def _build_document_stage_matrix(task: Task, run_dir: Path, step_logs: List[CotStepLog], cot_samples: List[CotSample]) -> List[Dict[str, Any]]:
    """Build per-document progress data from DB and file artifacts."""
    documents = _extract_document_sources(run_dir)
    if not documents:
        return []

    # Build lookup maps
    step_log_map: Dict[tuple, CotStepLog] = {}
    for sl in step_logs:
        if sl.source_index >= 0:
            step_log_map[(sl.source_index, sl.step_key)] = sl

    sample_map: Dict[int, CotSample] = {}
    for s in cot_samples:
        if s.source_index >= 0:
            sample_map[s.source_index] = s

    running_source_index = None
    running_step_key = None
    running_label = None
    if task.status == TaskStatusEnum.RUNNING:
        progress_label = task.progress_label or ""
        match = re.search(r"文献\s*(\d+)\s*/", progress_label)
        if not match:
            match = re.search(r"第\s*(\d+)\s*/", progress_label)
        if match:
            running_source_index = max(0, int(match.group(1)) - 1)
        for sl in step_logs:
            if sl.status == "running" and sl.source_index >= 0:
                running_step_key = sl.step_key
                running_label = sl.progress_label or progress_label
                break

    result: List[Dict[str, Any]] = []
    for doc in documents:
        source_index = doc["source_index"]
        source = str(doc.get("source") or f"item_{source_index + 1}")
        doc_dir = _document_output_dir(run_dir, source_index, source)
        doc_rel_prefix = f"documents/{str(source_index + 1).zfill(4)}_{_sanitize_dirname(source)}/"

        step1_3_artifact = _find_step1_3_artifact(run_dir, doc_rel_prefix)
        step1_3_data = _read_run_json_safely(run_dir, step1_3_artifact) if step1_3_artifact else None
        cot_sample = sample_map.get(source_index)
        cot_type = _infer_document_cot_type(doc_dir=doc_dir, step1_3_data=step1_3_data, cot_sample=cot_sample)
        cot_type_key = cot_type.get("key") if cot_type else None
        cot_type_name = cot_type.get("display_name") if cot_type else None

        artifacts: Dict[str, Optional[str]] = {
            "step1_3_integrated": step1_3_artifact,
            "step4_input": _find_typed_step_artifact(run_dir, doc_rel_prefix, doc_dir, cot_type_key, "step4_input.json"),
            "step5_chain": _find_typed_step_artifact(run_dir, doc_rel_prefix, doc_dir, cot_type_key, "step5_chain.json"),
            "step6_output": _find_typed_step_artifact(run_dir, doc_rel_prefix, doc_dir, cot_type_key, "step6_output.json"),
        }

        steps: List[Dict[str, Any]] = []
        for stage_index, stage in enumerate(DOCUMENT_STAGE_DEFINITIONS):
            stage_key = stage["stage_key"]
            artifact_path = artifacts.get(stage_key)
            status = "pending"
            progress_label = "等待处理"
            error = None

            if artifact_path:
                # Check if artifact corresponds to a completed step log
                sl = step_log_map.get((source_index, stage_key))
                if sl and sl.status == "completed":
                    status = "completed"
                    progress_label = "已完成"
                elif sl and sl.status == "failed":
                    status = "failed"
                    progress_label = "处理失败"
                    error = sl.error_message
                else:
                    status = "completed"  # artifact exists, assume completed
                    progress_label = "已完成"
            elif source_index == running_source_index and stage_key == running_step_key:
                status = "running"
                progress_label = running_label or "正在执行"
            elif cot_sample:
                # Sample exists in DB, so all steps should be complete
                status = "completed"
                progress_label = "已完成"
            else:
                # Check step log status
                sl = step_log_map.get((source_index, stage_key))
                if sl:
                    status = sl.status or "pending"
                    progress_label = sl.progress_label or "等待处理"
                    if sl.status in ("failed", "skipped"):
                        error = sl.error_message

            steps.append({
                "step_key": stage_key,
                "display_name": stage["stage_name"],
                "step": stage["step"],
                "status": status,
                "artifact_path": artifact_path,
                "progress_label": progress_label,
                "error": error if status in ("failed", "skipped") else None,
            })

        overall_status = "pending"
        if steps:
            has_running = any(s["status"] == "running" for s in steps)
            has_failed = any(s["status"] == "failed" for s in steps)
            all_completed_or_skipped = all(s["status"] in ("completed", "skipped") for s in steps)
            all_skipped = all(s["status"] == "skipped" for s in steps)

            if all_completed_or_skipped and not all_skipped:
                overall_status = "completed"
            elif all_skipped:
                overall_status = "skipped"
            elif has_running:
                overall_status = "running"
            elif has_failed:
                overall_status = "failed"

        result.append({
            "source_index": source_index,
            "source": source,
            "status": overall_status,
            "cot_type": cot_type_name,
            "cot_type_key": cot_type_key,
            "error": None,
            "steps": steps,
        })

    return result


def get_run_detail_for_user(run_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    """Build run detail response from Task + CotSample + CotStepLog + file artifacts."""
    try:
        task_id = int(run_id)
    except (ValueError, TypeError):
        return None

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task or task.user_id != user_id:
            return None

        run_dir = get_run_dir_by_task_id(task_id)
        run_extra = task.run_extra or {}

        # Build detail dict matching old manifest format
        detail: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "run_id": str(task_id),
            "pipeline_name": PIPELINE_NAME,
            "pipeline_type": PIPELINE_TYPE,
            "run_name": run_extra.get("run_name") or task.pipeline_name or PIPELINE_NAME,
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "user_id": task.user_id,
            "username": run_extra.get("username", ""),
            "source_file": run_extra.get("source_file", {}),
            "source_input": run_extra.get("source_input", {}),
            "source_type": run_extra.get("source_type", "unknown"),
            "input_count": task.input_count or 0,
            "success_count": task.success_count or 0,
            "failed_count": task.failed_count or 0,
            "sample_count": task.sample_count or 0,
            "progress_percentage": int(task.progress_current / task.progress_total * 100) if task.progress_total else 0,
            "progress_label": task.progress_label,
            "error_message": run_extra.get("error_message"),
            "llm": {
                "llm_config_id": run_extra.get("llm_config_id"),
                "llm_config_name": run_extra.get("llm_config_name", ""),
                "model": task.model,
            },
            "cot_types": run_extra.get("cot_types", []),
            "prompt_template": {},  # Will be populated from prompts table if needed
            "steps": [],  # Computed below from step_logs
            "final_outputs": {},  # Computed below
            "target_cot_type": None,
            "recommended_cot_type": None,
            "document_stage_matrix": [],
            "final_samples_preview": [],
            "batch_summary": None,
        }

        # Load samples and step logs
        cot_samples = db.query(CotSample).filter(CotSample.task_id == task_id).order_by(CotSample.source_index).all()
        step_logs = db.query(CotStepLog).filter(CotStepLog.task_id == task_id).all()

        # Legacy step counts for backward compat
        completed_step_logs = len([sl for sl in step_logs if sl.status == "completed"])
        failed_step_logs = len([sl for sl in step_logs if sl.status == "failed"])
        skipped_step_logs = len([sl for sl in step_logs if sl.status == "skipped"])
        total_step_logs = len(step_logs)
        detail["total_steps"] = max(total_step_logs, (task.input_count or 0) * 4)
        detail["completed_steps"] = completed_step_logs
        detail["failed_steps"] = failed_step_logs
        detail["skipped_steps"] = skipped_step_logs

        # Build legacy step array from step_logs
        legacy_steps = []
        seen_keys: set[str] = set()
        for sl in sorted(step_logs, key=lambda x: (x.source_index, x.step_key)):
            if sl.step_key in seen_keys:
                continue
            seen_keys.add(sl.step_key)
            legacy_steps.append({
                "step_key": sl.step_key,
                "step_name": sl.step_key.replace("_", " ").title(),
                "status": sl.status or "pending",
                "progress_current": sl.progress_current or 0,
                "progress_label": sl.progress_label or "",
                "cot_type": sl.cot_type,
                "cot_type_key": sl.cot_type_key,
                "artifact_path": sl.artifact_path,
                "error_message": sl.error_message,
            })
        detail["steps"] = legacy_steps

        # Final outputs (for export)
        detail["final_outputs"] = {"json": "final_samples.json", "jsonl": "final_samples.jsonl"}

        # Inferred CoT type
        cot_type_summary = _infer_cot_type_summary_from_samples(cot_samples)
        detail["recommended_cot_type"] = cot_type_summary
        detail["target_cot_type"] = cot_type_summary

        # Final samples preview
        detail["final_samples_preview"] = []
        for s in cot_samples[:5]:
            detail["final_samples_preview"].append({
                "cot_type": s.cot_type,
                "cot_type_key": s.cot_type_key,
                "source": s.source,
                "source_index": s.source_index,
                "input": s.input,
                "chainofThought": s.chainofThought,
                "output": s.output,
                "evidence_trace": s.evidence_trace,
            })

        # Document stage matrix
        detail["document_stage_matrix"] = _build_document_stage_matrix(task, run_dir, step_logs, cot_samples)

        return detail
    finally:
        db.close()


# ---------------------------------------------------------------------------
#  Export helpers (file-based, unchanged)
# ---------------------------------------------------------------------------


def read_artifact(run_id: str, user_id: int, rel_path: str) -> Any:
    manifest = get_run_detail_for_user(run_id, user_id)
    if manifest is None:
        return None

    if not rel_path or os.path.isabs(rel_path):
        raise ValueError("非法 artifact 路径")

    try:
        run_dir = get_run_dir(run_id).resolve()
    except ValueError:
        return None

    target = (run_dir / rel_path).resolve()
    if target != run_dir and run_dir not in target.parents:
        raise ValueError("非法 artifact 路径")
    if not target.exists() or not target.is_file():
        return None

    if target.suffix.lower() == ".jsonl":
        with open(target, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return read_json(target)


def get_export_path(run_id: str, user_id: int, export_type: str) -> Optional[Path]:
    filename = "final_samples.jsonl" if export_type == "jsonl" else "final_samples.json"
    try:
        run_dir = get_run_dir(run_id).resolve()
    except ValueError:
        return None

    # Security: check ownership
    detail = get_run_detail_for_user(run_id, user_id)
    if detail is None:
        return None

    target = run_dir / filename
    if target.exists() and target.is_file():
        return target
    return None


def get_export_zip_bytes(run_id: str, user_id: int) -> Optional[tuple]:
    import io
    import zipfile

    detail = get_run_detail_for_user(run_id, user_id)
    if detail is None:
        return None

    try:
        run_dir = get_run_dir(run_id).resolve()
    except ValueError:
        return None

    source_filename = detail.get("source_file", {}).get("filename", "source.json")

    files_to_pack = []

    source_path = run_dir / "source.json"
    if source_path.exists() and source_path.is_file():
        files_to_pack.append((source_path, "source_file.json"))

    final_json = run_dir / "final_samples.json"
    if final_json.exists() and final_json.is_file():
        files_to_pack.append((final_json, "final_samples.json"))

    if not files_to_pack:
        return None

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for disk_path, zip_name in files_to_pack:
            zf.write(disk_path, zip_name)
    buf.seek(0)

    stem = Path(source_filename).stem if source_filename else run_id
    zip_filename = f"{stem}_export.zip"

    return buf, zip_filename


# ---------------------------------------------------------------------------
#  Legacy compatibility functions (stubs for imports)
# ---------------------------------------------------------------------------

def load_manifest(run_id: str) -> Dict[str, Any]:
    """Legacy stub: read manifest from Task DB row or disk fallback.

    Returns a dict mimicking the old manifest.json format.
    """
    try:
        task_id = int(run_id)
    except (ValueError, TypeError):
        raise FileNotFoundError(f"manifest not found: {run_id}")

    detail = get_run_detail_for_user(run_id, 0)  # user_id=0 bypasses check
    if detail is None:
        # Fallback: try old file-based manifest
        try:
            from app.database import SessionLocal as _db
            db2 = _db()
            task = db2.query(Task).filter(Task.id == task_id).first()
            db2.close()
            if task:
                return get_run_detail_for_user(run_id, task.user_id) or {}
        except Exception:
            pass
        raise FileNotFoundError(f"manifest not found: {run_id}")
    return detail


def save_manifest(manifest: Dict[str, Any]) -> None:
    """Legacy stub: no-op for DB-based storage. Logged for debugging."""
    logger.debug("save_manifest called but DB storage is now primary; manifest: %s",
                 manifest.get("run_id", "unknown"))


def _refresh_manifest_progress(manifest: Dict[str, Any]) -> None:
    """Legacy stub: no-op."""


def _update_step(manifest: Dict[str, Any], step_key: str, **kwargs: Any) -> None:
    """Legacy stub: no-op."""


def _mark_run_failed(manifest: Dict[str, Any], message: str) -> None:
    """Legacy stub — updates Task status in DB."""
    run_id = manifest.get("run_id") if isinstance(manifest, dict) else None
    if not run_id:
        return
    try:
        task_id = int(run_id)
    except (ValueError, TypeError):
        return
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.FAILED
            task.run_extra = task.run_extra or {}
            task.run_extra["error_message"] = message[:1000]
            task.progress_label = "流水线执行失败"
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _mark_all_steps_failed(manifest: Dict[str, Any], message: str) -> None:
    """Legacy stub: no-op."""


def _skip_remaining(manifest: Dict[str, Any], reason: str, from_step_index: int = 0) -> None:
    """Legacy stub: no-op."""


def _skip_type_steps(manifest: Dict[str, Any], cot_type_key: str, reason: str) -> None:
    """Legacy stub: no-op."""


def _write_batch_summary(run_dir: Path, run_id: str, input_count: int, batch_items: List[Dict[str, Any]], manifest: Dict[str, Any]) -> None:
    """Legacy stub: batch_summary.json is no longer written incrementally."""
    pass
