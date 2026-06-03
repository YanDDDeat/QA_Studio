"""File-based professional CoT construction pipeline.

需求 26：标注流水线2专业 CoT 构建。
第一版只使用运行目录 + JSON 产物，不写 cot_nodes / datasets，不做 DB 迁移。
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.models.models import LLMConfig
from app.services.llm_service import LLMCallError, call_llm_json_sync
from app.services.thread_pool import register_task, unregister_task

logger = logging.getLogger("qa_studio.professional_cot")


def _find_project_root() -> Path:
    """Find the project root across local and container layouts."""
    marker = Path("docs") / "background" / "3类COT提示词" / "专业Cot构建.md"
    candidates = []

    env_root = os.getenv("QA_STUDIO_ROOT") or os.getenv("PROJECT_ROOT")
    if env_root:
        candidates.append(Path(env_root))

    current_file = Path(__file__).resolve()
    candidates.extend(current_file.parents)

    cwd = Path.cwd().resolve()
    candidates.append(cwd)
    candidates.extend(cwd.parents)

    candidates.extend([Path("/app"), Path("/workspace"), Path("/code")])

    seen = set()
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

    # Keep the old local layout fallback, but log the checked roots to make
    # deployment path issues diagnosable.
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
PIPELINE_NAME = "标注流水线2"
PIPELINE_TYPE = "professional_cot"

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


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def make_run_id() -> str:
    return f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


RUN_ID_PATTERN = re.compile(r"^\d{14}_[0-9a-f]{8}$")


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(str(run_id or "")):
        raise ValueError("非法 run_id")
    return run_id


def get_run_dir(run_id: str) -> Path:
    return STORAGE_ROOT / validate_run_id(run_id)


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


def manifest_path(run_id: str) -> Path:
    return get_run_dir(run_id) / "manifest.json"


def load_manifest(run_id: str) -> Dict[str, Any]:
    path = manifest_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {run_id}")
    return read_json(path)


def save_manifest(manifest: Dict[str, Any]) -> None:
    manifest["updated_at"] = utc_now_iso()
    _refresh_manifest_progress(manifest)
    atomic_write_json(get_run_dir(manifest["run_id"]) / "manifest.json", manifest)


def _refresh_manifest_progress(manifest: Dict[str, Any]) -> None:
    steps = manifest.get("steps", [])
    total = len(steps)
    done = len([s for s in steps if s.get("status") in ("completed", "skipped")])
    completed = len([s for s in steps if s.get("status") == "completed"])
    skipped = len([s for s in steps if s.get("status") == "skipped"])
    failed = len([s for s in steps if s.get("status") == "failed"])
    manifest["total_steps"] = total
    manifest["completed_steps"] = completed
    manifest["skipped_steps"] = skipped
    manifest["failed_steps"] = failed
    manifest["progress_percentage"] = int(round((done / total) * 100)) if total else 0


def _get_cot_type(target_cot_type: str) -> Dict[str, Any]:
    cot_type = normalize_cot_type(target_cot_type)
    if not cot_type:
        raise ValueError("CoT 类型不在当前支持的 10 类枚举中")
    return cot_type


def _init_steps() -> List[Dict[str, Any]]:
    """Initialize exactly 6 logical steps; Step 3 decides the target CoT type."""
    return [
        {
            "step_key": "step1_screening",
            "step": 1,
            "step_name": "筛选相关文献",
            "display_name": "Step 1：筛选相关文献",
            "status": "pending",
            "progress_current": 0,
            "progress_label": "等待执行",
            "artifact_path": "step1_screening.json",
        },
        {
            "step_key": "step2_case_card",
            "step": 2,
            "step_name": "构建文献案例卡",
            "display_name": "Step 2：构建文献案例卡",
            "status": "pending",
            "progress_current": 0,
            "progress_label": "等待执行",
            "artifact_path": "step2_case_card.json",
        },
        {
            "step_key": "step3_type_judgement",
            "step": 3,
            "step_name": "自动判定本次任务的 CoT 类型",
            "display_name": "Step 3：自动判定本次任务的 CoT 类型",
            "status": "pending",
            "progress_current": 0,
            "progress_label": "模型判定 CoT 类型：待判定",
            "artifact_path": "step3_type_judgement.json",
        },
        {
            "step_key": "step4_input",
            "step": 4,
            "step_name": "生成 input",
            "display_name": "Step 4：为 Step 3 推荐的 CoT 类型生成 input",
            "status": "pending",
            "progress_current": 0,
            "progress_label": "等待 Step 3 推荐 CoT 类型",
            "artifact_path": None,
        },
        {
            "step_key": "step5_chain",
            "step": 5,
            "step_name": "生成 chainofThought",
            "display_name": "Step 5：为 Step 3 推荐的 CoT 类型生成 chainofThought",
            "status": "pending",
            "progress_current": 0,
            "progress_label": "等待 Step 3 推荐 CoT 类型",
            "artifact_path": None,
        },
        {
            "step_key": "step6_output",
            "step": 6,
            "step_name": "生成 output",
            "display_name": "Step 6：为 Step 3 推荐的 CoT 类型生成 output",
            "status": "pending",
            "progress_current": 0,
            "progress_label": "等待 Step 3 推荐 CoT 类型",
            "artifact_path": None,
        },
    ]


def _update_step(
    manifest: Dict[str, Any],
    step_key: str,
    *,
    status: Optional[str] = None,
    progress_current: Optional[int] = None,
    progress_label: Optional[str] = None,
    error_message: Optional[str] = None,
    cot_type: Optional[str] = None,
    cot_type_key: Optional[str] = None,
    artifact_path: Optional[str] = None,
) -> None:
    for step in manifest.get("steps", []):
        if step.get("step_key") == step_key:
            if status is not None:
                step["status"] = status
            if progress_current is not None:
                step["progress_current"] = progress_current
            if progress_label is not None:
                step["progress_label"] = progress_label
            if error_message is not None:
                step["error_message"] = error_message
            if cot_type is not None:
                step["cot_type"] = cot_type
            if cot_type_key is not None:
                step["cot_type_key"] = cot_type_key
            if artifact_path is not None:
                step["artifact_path"] = artifact_path
            return


def _skip_remaining(manifest: Dict[str, Any], reason: str, from_step_index: int = 0) -> None:
    for idx, step in enumerate(manifest.get("steps", [])):
        if idx >= from_step_index and step.get("status") == "pending":
            step["status"] = "skipped"
            step["progress_current"] = 100
            step["progress_label"] = reason


def _skip_type_steps(manifest: Dict[str, Any], cot_type_key: str, reason: str) -> None:
    for step in manifest.get("steps", []):
        if step.get("cot_type_key") == cot_type_key and step.get("status") == "pending":
            step["status"] = "skipped"
            step["progress_current"] = 100
            step["progress_label"] = reason


def _normalize_text(value: str) -> str:
    text = str(value or "").lower()
    text = text.replace("cot", "")
    text = re.sub(r"[\s/／\\\-—–_（）()、，,：:]+", "", text)
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
    seen = set()
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
    """Normalize one CoT type from key / display_name / alias."""
    matches = normalize_cot_types(value)
    return matches[0] if matches else None


def _truthy_generation_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in ("true", "yes", "y", "是", "可以", "可生成", "partial"):
        return True
    return False


def _read_prompt_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_step_prompt(step_no: int) -> str:
    content = _read_prompt_file(PROMPT_ROOT / "专业Cot构建.md")
    pattern = re.compile(rf"###\s*Step\s*{step_no}[^\n]*\n(.*?)(?=\n###\s*Step\s*\d+|\Z)", re.S | re.I)
    match = pattern.search(content)
    return match.group(0).strip() if match else content


def _type_prompt(cot_type: Dict[str, Any], step_no: int) -> str:
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


def _call_json(prompt: str, llm: Dict[str, Any], username: str) -> Dict[str, Any]:
    return call_llm_json_sync(
        prompt=prompt,
        model=llm["model"],
        temperature=0.2,
        base_url_override=llm["base_url"],
        api_key_override=llm["api_key"],
        username=username,
    )


def _run_step1(paper_text: str, llm: Dict[str, Any], username: str) -> Dict[str, Any]:
    prompt = f"""
{_extract_step_prompt(1)}

强制约束：
- 只能在以下 10 类 CoT 枚举中选择类型，输出名称必须使用枚举原文：
{COT_ENUM_TEXT}
- JSON 顶层必须是对象。
- can_generate 必须是 boolean。
- supported_cot_types 只能包含上述枚举原文；没有则为空数组。
- unsupported_types 使用数组，每项包含 cot_type 和 reason。
- 不要生成最终 CoT 样本。

请按以下 JSON 结构输出：
{{
  "can_generate": true,
  "supported_cot_types": ["性能提升路径 CoT"],
  "unsupported_types": [{{"cot_type": "...", "reason": "..."}}],
  "evidence_summary": ["..."],
  "stop_reason": null
}}

完整论文正文：
{paper_text}
""".strip()
    result = _call_json(prompt, llm, username)
    result["can_generate"] = _truthy_generation_flag(result.get("can_generate") or result.get("是否可生成") or result.get("decision"))
    result["supported_cot_types"] = [item["display_name"] for item in normalize_cot_types(result.get("supported_cot_types") or result.get("可支持的 CoT 类型") or result.get("cot_types"))]
    return result


def _run_step2(paper_text: str, llm: Dict[str, Any], username: str) -> Dict[str, Any]:
    prompt = f"""
{_extract_step_prompt(2)}

强制约束：
- JSON 顶层必须是对象，必须包含 case_card。
- case_card 只能基于论文证据抽取；无证据字段写 null 或 []，不得补写。
- case_card 字段必须覆盖：{', '.join(CASE_CARD_FIELDS)}。

请按以下 JSON 结构输出：
{{
  "case_card": {{
    "source_id": null,
    "source_type": null,
    "material_or_molecule": null,
    "research_goal": null,
    "baseline": null,
    "modification_or_variable": null,
    "control_samples": [],
    "performance_metrics": [],
    "observed_results": [],
    "mechanism_claim": null,
    "process_conditions": [],
    "recipe_components": [],
    "validation_methods": [],
    "limitations": null,
    "failure_or_risk": null,
    "figures_or_tables": []
  }}
}}

完整论文正文：
{paper_text}
""".strip()
    result = _call_json(prompt, llm, username)
    case_card = result.get("case_card") if isinstance(result.get("case_card"), dict) else result
    normalized = {field: case_card.get(field) for field in CASE_CARD_FIELDS}
    return {"case_card": normalized}


def _extract_recommended_cot_type(step3: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    recommended = (
        step3.get("recommended_cot_type")
        or step3.get("推荐CoT类型")
        or step3.get("推荐类型")
        or step3.get("target_cot_type")
        or step3.get("cot_type")
        or step3.get("cot_type_key")
    )
    matched = normalize_cot_type(recommended)
    if matched:
        return matched

    constructible = step3.get("constructible_cot_types") or step3.get("可构建类型") or []
    if isinstance(constructible, list) and len(constructible) == 1:
        return normalize_cot_type(constructible[0])
    return None


def _run_step3(case_card: Dict[str, Any], llm: Dict[str, Any], username: str) -> Dict[str, Any]:
    prompt = f"""
{_extract_step_prompt(3)}

强制约束：
- Step 3 的输入仅为 Step 2 产出的 case_card；不要读取完整论文正文，不要补写 case_card 中不存在的证据。
- 必须在以下 10 类 CoT 枚举中判断可构建类型，输出名称优先使用枚举原文：
{COT_ENUM_TEXT}
- recommended_cot_type 是本次任务唯一推荐生成类型，必须来自上述 10 类枚举；若没有任何可构建类型，则写 null。
- 若多个类型可构建，必须选择证据链最完整、最适合生成单条训练样本的一类作为 recommended_cot_type。
- JSON 顶层必须是对象。
- constructible_cot_types 必须是数组，每项包含 cot_type、reason、evidence。
- not_constructible_types 必须是数组，每项包含 cot_type、reason。
- missing_information 必须是数组。

请按以下 JSON 结构输出：
{{
  "constructible_cot_types": [
    {{"cot_type": "性能提升路径 CoT", "reason": "...", "evidence": ["..."]}}
  ],
  "recommended_cot_type": "性能提升路径 CoT",
  "recommendation_reason": "...",
  "not_constructible_types": [{{"cot_type": "...", "reason": "..."}}],
  "missing_information": []
}}

case_card：
{_json_block(case_card)}
""".strip()
    result = _call_json(prompt, llm, username)
    constructible = normalize_cot_types(result.get("constructible_cot_types") or result.get("可构建类型") or [])
    result["constructible_cot_types"] = [
        {
            "cot_type": item["display_name"],
            "cot_type_key": item["key"],
            "reason": next(
                (
                    raw.get("reason") or raw.get("理由") or raw.get("constructible_reason")
                    for raw in (result.get("constructible_cot_types") or [])
                    if isinstance(raw, dict) and normalize_cot_type(raw) and normalize_cot_type(raw)["key"] == item["key"]
                ),
                None,
            ),
            "evidence": next(
                (
                    raw.get("evidence") or raw.get("证据")
                    for raw in (result.get("constructible_cot_types") or [])
                    if isinstance(raw, dict) and normalize_cot_type(raw) and normalize_cot_type(raw)["key"] == item["key"]
                ),
                [],
            ),
        }
        for item in constructible
    ]
    recommended = _extract_recommended_cot_type(result)
    result["recommended_cot_type"] = recommended["display_name"] if recommended else None
    result["recommended_cot_type_key"] = recommended["key"] if recommended else None
    result.setdefault("recommendation_reason", result.get("推荐理由") or result.get("reason"))
    result.setdefault("not_constructible_types", [])
    result.setdefault("missing_information", [])
    return result


def _run_step4(cot_type: Dict[str, Any], case_card: Dict[str, Any], step1: Dict[str, Any], step3: Dict[str, Any], llm: Dict[str, Any], username: str) -> Dict[str, Any]:
    prompt = f"""
{_type_prompt(cot_type, 4)}

强制约束：
- 当前 cot_type 固定为：{cot_type['display_name']}。
- 只生成 1 个主 selected_input，alternative_inputs 可为空。
- selected_input 不得出现“根据文献”“本文报道”“作者发现”“图 1”“表 1”“Figure”“Table”等来源表达。
- JSON 顶层必须是对象。

请按以下 JSON 结构输出：
{{
  "cot_type": "{cot_type['display_name']}",
  "selected_input": "...",
  "alternative_inputs": [],
  "evidence_trace": {{}}
}}

Step 1 结果：
{_json_block(step1)}

Step 3 结果：
{_json_block(step3)}

case_card：
{_json_block(case_card)}
""".strip()
    result = _call_json(prompt, llm, username)
    selected_input = result.get("selected_input") or result.get("input")
    result["selected_input"] = _require_non_empty_string(selected_input, "Step 4 selected_input 或 input")
    return result


def _run_step5(cot_type: Dict[str, Any], case_card: Dict[str, Any], step1: Dict[str, Any], step3: Dict[str, Any], step4: Dict[str, Any], llm: Dict[str, Any], username: str) -> Dict[str, Any]:
    selected_input = step4.get("selected_input") or step4.get("input") or ""
    prompt = f"""
{_type_prompt(cot_type, 5)}

强制约束：
- 当前 cot_type 固定为：{cot_type['display_name']}。
- chainofThought 必须是数组。
- 训练文本必须去文献化，不得出现“根据文献”“本文报道”“作者发现”“图 1”“表 1”“Figure”“Table”等来源表达。
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

Step 1 结果：
{_json_block(step1)}

Step 3 结果：
{_json_block(step3)}

Step 4 结果：
{_json_block(step4)}

case_card：
{_json_block(case_card)}
""".strip()
    result = _call_json(prompt, llm, username)
    chain = result.get("chainofThought") or result.get("chain_of_thought") or result.get("chain") or []
    result["chainofThought"] = _normalize_chainofthought(chain)
    return result


def _run_step6(cot_type: Dict[str, Any], step4: Dict[str, Any], step5: Dict[str, Any], llm: Dict[str, Any], username: str) -> Dict[str, Any]:
    selected_input = step4.get("selected_input") or step4.get("input") or ""
    chain = step5.get("chainofThought") or []
    prompt = f"""
{_type_prompt(cot_type, 6)}

强制约束：
- 当前 cot_type 固定为：{cot_type['display_name']}。
- output 必须直接回答 input，不要重复完整推理过程。
- 不得出现“根据文献”“本文报道”“作者发现”“图 1”“表 1”“Figure”“Table”等来源表达。
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


def _build_final_sample(cot_type: Dict[str, Any], step4: Dict[str, Any], step5: Dict[str, Any], step6: Dict[str, Any]) -> Dict[str, Any]:
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
    return {
        "cot_type": cot_type["display_name"],
        "input": sample_input,
        "chainofThought": chain,
        "output": output,
        "evidence_trace": evidence_trace,
    }


def _write_final_outputs(run_id: str, samples: List[Dict[str, Any]]) -> Dict[str, str]:
    run_dir = get_run_dir(run_id)
    final_json = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "pipeline_name": PIPELINE_NAME,
        "sample_count": len(samples),
        "samples": samples,
    }
    atomic_write_json(run_dir / "final_samples.json", final_json)
    jsonl_content = "".join(json.dumps(sample, ensure_ascii=False) + "\n" for sample in samples)
    atomic_write_text(run_dir / "final_samples.jsonl", jsonl_content)
    return {"json": "final_samples.json", "jsonl": "final_samples.jsonl"}


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
) -> Dict[str, Any]:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = make_run_id()
    run_dir = get_run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    llm_info = {
        "llm_config_id": llm_config.id,
        "llm_config_name": llm_config.name,
        "model": model,
        "base_url": llm_config.base_url,
        "api_key": llm_config.api_key,
    }

    manifest: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "pipeline_name": PIPELINE_NAME,
        "pipeline_type": PIPELINE_TYPE,
        "run_name": run_name or f"{PIPELINE_NAME}-{source_filename}",
        "status": "running",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "user_id": user_id,
        "username": username,
        "source_file": {
            "id": source_file_id,
            "filename": source_filename,
            "artifact_path": "source.json",
        },
        "source_input": {
            "text_field": text_field,
            "artifact_path": "source_input.json",
            "text_length": len(paper_text),
        },
        "target_cot_type": None,
        "recommended_cot_type": None,
        "llm": {
            "llm_config_id": llm_config.id,
            "llm_config_name": llm_config.name,
            "model": model,
        },
        "cot_types": [
            {"key": item["key"], "display_name": item["display_name"]}
            for item in COT_TYPES
        ],
        "steps": _init_steps(),
        "final_outputs": {},
        "error_message": None,
    }
    _refresh_manifest_progress(manifest)

    atomic_write_json(run_dir / "source.json", source_data)
    atomic_write_json(run_dir / "source_input.json", {"text_field": text_field, "paper_text": paper_text})
    atomic_write_json(run_dir / "manifest.json", manifest)

    # LLM 密钥只传给后台，不写入 manifest。
    return {"run_id": run_id, "manifest": manifest, "llm": llm_info}


def run_pipeline_sync(run_id: str, llm: Dict[str, Any], username: str) -> None:
    register_task()
    try:
        manifest = load_manifest(run_id)
        run_dir = get_run_dir(run_id)
        paper_text = read_json(run_dir / "source_input.json")["paper_text"]
        samples: List[Dict[str, Any]] = []

        try:
            manifest["status"] = "running"
            manifest["progress_label"] = "正在执行 Step 1：筛选相关文献"
            _update_step(manifest, "step1_screening", status="running", progress_current=10, progress_label="调用 LLM 判断可生成性")
            save_manifest(manifest)
            step1 = _run_step1(paper_text, llm, username)
            atomic_write_json(run_dir / "step1_screening.json", {"step": 1, "step_name": "筛选相关文献", "status": "completed", "result": step1})
            _update_step(manifest, "step1_screening", status="completed", progress_current=100, progress_label="已完成")
            manifest["step1_summary"] = step1
            save_manifest(manifest)

            if not step1.get("can_generate"):
                stop_reason = step1.get("stop_reason") or "Step 1 判断该论文不适合构建当前支持的专业 CoT"
                _skip_remaining(manifest, stop_reason, from_step_index=1)
                manifest["status"] = "completed"
                manifest["stop_reason"] = stop_reason
                manifest["progress_label"] = stop_reason
                manifest["final_outputs"] = _write_final_outputs(run_id, samples)
                save_manifest(manifest)
                return

            manifest["progress_label"] = "正在执行 Step 2：构建文献案例卡"
            _update_step(manifest, "step2_case_card", status="running", progress_current=10, progress_label="调用 LLM 抽取案例卡")
            save_manifest(manifest)
            step2 = _run_step2(paper_text, llm, username)
            case_card = step2["case_card"]
            atomic_write_json(run_dir / "step2_case_card.json", {"step": 2, "step_name": "构建文献案例卡", "status": "completed", "result": step2})
            _update_step(manifest, "step2_case_card", status="completed", progress_current=100, progress_label="已完成")
            save_manifest(manifest)

            manifest["progress_label"] = "正在执行 Step 3：自动判定本次任务的 CoT 类型"
            _update_step(manifest, "step3_type_judgement", status="running", progress_current=10, progress_label="模型正在判定 CoT 类型")
            save_manifest(manifest)
            step3 = _run_step3(case_card, llm, username)
            target = _extract_recommended_cot_type(step3)
            if target and not step3.get("constructible_cot_types"):
                target = None
            step3_payload = {
                "step": 3,
                "step_name": "自动判定本次任务的 CoT 类型",
                "status": "completed",
                "result": step3,
            }
            if target:
                step3_payload["cot_type"] = target["display_name"]
                step3_payload["cot_type_key"] = target["key"]
                manifest["target_cot_type"] = {"key": target["key"], "display_name": target["display_name"]}
                manifest["recommended_cot_type"] = {"key": target["key"], "display_name": target["display_name"]}
                _update_step(
                    manifest,
                    "step3_type_judgement",
                    status="completed",
                    progress_current=100,
                    progress_label=f"模型判定 CoT 类型：{target['display_name']}",
                    cot_type=target["display_name"],
                    cot_type_key=target["key"],
                )
                for step_key, artifact_name in (
                    ("step4_input", "step4_input.json"),
                    ("step5_chain", "step5_chain.json"),
                    ("step6_output", "step6_output.json"),
                ):
                    _update_step(
                        manifest,
                        step_key,
                        progress_label=f"等待执行 {target['display_name']}",
                        cot_type=target["display_name"],
                        cot_type_key=target["key"],
                        artifact_path=f"{target['key']}/{artifact_name}",
                    )
            else:
                _update_step(
                    manifest,
                    "step3_type_judgement",
                    status="completed",
                    progress_current=100,
                    progress_label="模型判定 CoT 类型：无可构建类型",
                )
            atomic_write_json(run_dir / "step3_type_judgement.json", step3_payload)
            manifest["step3_type_judgement"] = step3
            save_manifest(manifest)

            if not target:
                missing = step3.get("missing_information") or []
                reason = step3.get("recommendation_reason") or "Step 3 未推荐可构建的 CoT 类型"
                if isinstance(missing, list) and missing:
                    reason = f"{reason}；证据缺口：{'；'.join(str(item) for item in missing[:5])}"
                _skip_remaining(manifest, reason, from_step_index=3)
                manifest["status"] = "completed"
                manifest["stop_reason"] = reason
                manifest["progress_label"] = reason
                manifest["final_outputs"] = _write_final_outputs(run_id, samples)
                manifest["sample_count"] = 0
                save_manifest(manifest)
                return

            type_dir = run_dir / target["key"]
            type_dir.mkdir(parents=True, exist_ok=True)

            manifest["progress_label"] = f"正在执行 {target['display_name']} Step 4"
            _update_step(manifest, "step4_input", status="running", progress_current=15, progress_label="生成主 input")
            save_manifest(manifest)
            step4 = _run_step4(target, case_card, step1, step3, llm, username)
            atomic_write_json(type_dir / "step4_input.json", {"step": 4, "step_name": "生成 input", "status": "completed", "cot_type": target["display_name"], "cot_type_key": target["key"], "result": step4})
            _update_step(manifest, "step4_input", status="completed", progress_current=100, progress_label="已完成")
            save_manifest(manifest)

            manifest["progress_label"] = f"正在执行 {target['display_name']} Step 5"
            _update_step(manifest, "step5_chain", status="running", progress_current=15, progress_label="生成 chainofThought")
            save_manifest(manifest)
            step5 = _run_step5(target, case_card, step1, step3, step4, llm, username)
            atomic_write_json(type_dir / "step5_chain.json", {"step": 5, "step_name": "生成 chainofThought", "status": "completed", "cot_type": target["display_name"], "cot_type_key": target["key"], "result": step5})
            _update_step(manifest, "step5_chain", status="completed", progress_current=100, progress_label="已完成")
            save_manifest(manifest)

            manifest["progress_label"] = f"正在执行 {target['display_name']} Step 6"
            _update_step(manifest, "step6_output", status="running", progress_current=15, progress_label="生成 output")
            save_manifest(manifest)
            step6 = _run_step6(target, step4, step5, llm, username)
            sample = _build_final_sample(target, step4, step5, step6)
            step6_payload = {"step": 6, "step_name": "生成 output", "status": "completed", "cot_type": target["display_name"], "cot_type_key": target["key"], "result": step6, "final_sample": sample}
            atomic_write_json(type_dir / "step6_output.json", step6_payload)
            samples.append(sample)
            _update_step(manifest, "step6_output", status="completed", progress_current=100, progress_label="已完成")
            manifest["sample_count"] = len(samples)
            save_manifest(manifest)

            manifest["final_outputs"] = _write_final_outputs(run_id, samples)
            manifest["sample_count"] = len(samples)
            manifest["status"] = "completed"
            manifest["progress_label"] = f"全部完成，生成 {len(samples)} 条样本"
            save_manifest(manifest)

        except (LLMCallError, FileNotFoundError, ValueError) as exc:
            logger.error("professional cot run %s failed: %s", run_id, exc)
            _mark_run_failed(manifest, str(exc))
        except Exception as exc:  # noqa: BLE001 - 后台任务必须兜底写入 manifest
            logger.exception("professional cot run %s unexpected failure", run_id)
            _mark_run_failed(manifest, str(exc))
    finally:
        unregister_task()


def _mark_run_failed(manifest: Dict[str, Any], message: str) -> None:
    manifest["status"] = "failed"
    manifest["error_message"] = message[:1000]
    manifest["progress_label"] = "流水线执行失败"
    for step in manifest.get("steps", []):
        if step.get("status") == "running":
            step["status"] = "failed"
            step["progress_label"] = "执行失败"
            step["error_message"] = message[:500]
            break
    save_manifest(manifest)


def list_runs_for_user(user_id: int, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    if not STORAGE_ROOT.exists():
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    runs: List[Dict[str, Any]] = []
    for path in STORAGE_ROOT.glob("*/manifest.json"):
        try:
            manifest = read_json(path)
        except Exception:
            continue
        if manifest.get("user_id") != user_id:
            continue
        runs.append(_manifest_to_list_item(manifest))
    runs.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    total = len(runs)
    offset = (page - 1) * page_size
    return {
        "items": runs[offset:offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _manifest_to_list_item(manifest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_id": manifest.get("run_id"),
        "run_name": manifest.get("run_name"),
        "pipeline_name": manifest.get("pipeline_name"),
        "pipeline_type": manifest.get("pipeline_type"),
        "status": manifest.get("status"),
        "progress_percentage": manifest.get("progress_percentage", 0),
        "completed_steps": manifest.get("completed_steps", 0),
        "skipped_steps": manifest.get("skipped_steps", 0),
        "failed_steps": manifest.get("failed_steps", 0),
        "total_steps": manifest.get("total_steps", 0),
        "sample_count": manifest.get("sample_count", 0),
        "source_filename": manifest.get("source_file", {}).get("filename"),
        "text_field": manifest.get("source_input", {}).get("text_field"),
        "target_cot_type": manifest.get("target_cot_type"),
        "recommended_cot_type": manifest.get("recommended_cot_type"),
        "model": manifest.get("llm", {}).get("model"),
        "created_at": manifest.get("created_at"),
        "updated_at": manifest.get("updated_at"),
        "progress_label": manifest.get("progress_label"),
        "error_message": manifest.get("error_message"),
    }


def get_run_detail_for_user(run_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    try:
        manifest = load_manifest(run_id)
    except FileNotFoundError:
        return None
    if manifest.get("user_id") != user_id:
        return None

    detail = dict(manifest)
    final_path = get_run_dir(run_id) / "final_samples.json"
    if final_path.exists():
        try:
            final_data = read_json(final_path)
            detail["final_samples_preview"] = final_data.get("samples", [])[:5]
        except Exception:
            detail["final_samples_preview"] = []
    return detail


def resolve_artifact_path(run_id: str, user_id: int, rel_path: str) -> Optional[Path]:
    manifest = get_run_detail_for_user(run_id, user_id)
    if manifest is None:
        return None
    if not rel_path or os.path.isabs(rel_path):
        raise ValueError("非法 artifact 路径")
    run_dir = get_run_dir(run_id).resolve()
    target = (run_dir / rel_path).resolve()
    if target != run_dir and run_dir not in target.parents:
        raise ValueError("非法 artifact 路径")
    if not target.exists() or not target.is_file():
        return None
    return target


def read_artifact(run_id: str, user_id: int, rel_path: str) -> Any:
    target = resolve_artifact_path(run_id, user_id, rel_path)
    if target is None:
        return None
    if target.suffix.lower() == ".jsonl":
        with open(target, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return read_json(target)


def get_export_path(run_id: str, user_id: int, export_type: str) -> Optional[Path]:
    filename = "final_samples.jsonl" if export_type == "jsonl" else "final_samples.json"
    return resolve_artifact_path(run_id, user_id, filename)
