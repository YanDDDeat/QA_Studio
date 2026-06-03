"""File-based prompt template management for professional CoT pipeline.

需求 29：标注流水线2提示词模板管理。
第一版仅使用文件化存储，不接入全局 Prompt 表，不做数据库迁移。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

SYSTEM_TEMPLATE_ID = "system_default_v1"
SYSTEM_TEMPLATE_NAME = "系统默认模板 v1"
SCHEMA_VERSION = "1.0"


COT_PROMPT_LAYOUT: List[Dict[str, Any]] = [
    {
        "key": "performance_improvement",
        "display_name": "性能提升路径 CoT",
        "prompt_dir": "性能提升路径CoT",
        "step4": "step4_input_performance_improvement.md",
        "step5": "step5_chain_performance_improvement.md",
        "step6": "step6_output_performance_improvement.md",
    },
    {
        "key": "structure_property",
        "display_name": "构效关系-结构性能关系 CoT",
        "prompt_dir": "构效关系-结构性能关系CoT",
        "step4": "step4_input_structure_property.md",
        "step5": "step5_chain_structure_property.md",
        "step6": "step6_output_structure_property.md",
    },
    {
        "key": "candidate_selection",
        "display_name": "候选分子 / 材料优选决策 CoT",
        "prompt_dir": "候选分子-材料优选决策 CoT",
        "step4": "step4_input_candidate_selection.md",
        "step5": "step5_chain_candidate_selection.md",
        "step6": "step6_output_candidate_selection.md",
    },
    {
        "key": "counterfactual_modification",
        "display_name": "反事实结构改造 CoT",
        "prompt_dir": "反事实结构改造CoT",
        "step4": "step4_input_counterfactual_modification.md",
        "step5": "step5_chain_counterfactual_modification.md",
        "step6": "step6_output_counterfactual_modification.md",
    },
    {
        "key": "failure_diagnosis",
        "display_name": "失败原因诊断 CoT",
        "prompt_dir": "失败原因诊断CoT",
        "step4": "step4_input_failure_diagnosis.md",
        "step5": "step5_chain_failure_diagnosis.md",
        "step6": "step6_output_failure_diagnosis.md",
    },
    {
        "key": "multi_objective_optimization",
        "display_name": "多目标约束优化 CoT",
        "prompt_dir": "多目标约束优化CoT",
        "step4": "step4_input_multi_objective_optimization.md",
        "step5": "step5_chain_multi_objective_optimization.md",
        "step6": "step6_output_multi_objective_optimization.md",
    },
    {
        "key": "mechanism_to_design",
        "display_name": "机理到设计策略迁移 CoT",
        "prompt_dir": "机理到设计策略迁移CoT",
        "step4": "step4_input_mechanism_to_design.md",
        "step5": "step5_chain_mechanism_to_design.md",
        "step6": "step6_output_mechanism_to_design.md",
    },
    {
        "key": "process_optimization",
        "display_name": "实验条件 / 制备工艺优化 CoT",
        "prompt_dir": "实验条件-制备工艺优化CoT",
        "step4": "step4_input_process_optimization.md",
        "step5": "step5_chain_process_optimization.md",
        "step6": "step6_output_process_optimization.md",
    },
    {
        "key": "experimental_plan",
        "display_name": "实验方案生成 CoT",
        "prompt_dir": "实验方案生成CoT",
        "step4": "step4_input_experimental_plan_generation.md",
        "step5": "step5_chain_experimental_plan_generation.md",
        "step6": "step6_output_experimental_plan_generation.md",
    },
    {
        "key": "recipe_design",
        "display_name": "实验设计配方 CoT",
        "prompt_dir": "实验设计配方CoT",
        "step4": "step4_input_recipe_design.md",
        "step5": "step5_chain_recipe_design.md",
        "step6": "step6_output_recipe_design.md",
    },
]

COMMON_PROMPTS = {
    "common.step1_3": {
        "label": "Step 1-3：文献信息抽取与 CoT 类型路由",
        "path": Path("common") / "step1_3_integrated_extraction_and_routing.md",
    },
}

LEGACY_COMMON_PROMPTS = {
    "common.step1": {
        "label": "Step 1：筛选相关文献",
        "path": Path("common") / "step1_screening.md",
        "step_no": 1,
    },
    "common.step2": {
        "label": "Step 2：构建文献案例卡",
        "path": Path("common") / "step2_case_card.md",
        "step_no": 2,
    },
    "common.step3": {
        "label": "Step 3：判定 CoT 类型",
        "path": Path("common") / "step3_target_judgement.md",
        "step_no": 3,
    },
}

STEP_PROMPTS = {
    "step4": {"label": "Step 4：生成 input", "path_name": "step4_input.md"},
    "step5": {"label": "Step 5：生成 chainofThought", "path_name": "step5_chain.md"},
    "step6": {"label": "Step 6：生成 output", "path_name": "step6_output.md"},
}


class PromptTemplateError(ValueError):
    """Raised when prompt template operations are invalid."""


def _find_project_root() -> Path:
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
    return current_file.parents[3]


PROJECT_ROOT = _find_project_root()
PROMPT_SOURCE_ROOT = PROJECT_ROOT / "docs" / "background" / "3类COT提示词"
TEMPLATE_STORAGE_ROOT = PROJECT_ROOT / "storage" / "professional_cot_prompt_templates"
RUN_STORAGE_ROOT = PROJECT_ROOT / "storage" / "professional_cot_runs"


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


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


def read_text(path: Path) -> str:
    if not path.exists():
        raise PromptTemplateError(f"提示词文件不存在：{path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_common_prompt(step_no: int) -> str:
    content = read_text(PROMPT_SOURCE_ROOT / "专业Cot构建.md")
    pattern = re.compile(rf"###\s*Step\s*{step_no}[^\n]*\n(.*?)(?=\n###\s*Step\s*\d+|\Z)", re.S | re.I)
    match = pattern.search(content)
    return match.group(0).strip() if match else content


def _read_step1_3_prompt() -> str:
    return read_text(PROMPT_SOURCE_ROOT / "step1_3_integrated_extraction_and_routing.md")


def _default_common_prompt_content(prompt_key: str) -> str:
    if prompt_key == "common.step1_3":
        return _read_step1_3_prompt()
    legacy_info = LEGACY_COMMON_PROMPTS.get(prompt_key)
    if legacy_info:
        return _extract_common_prompt(legacy_info["step_no"])
    raise PromptTemplateError("非法通用 prompt_key")


def _ensure_common_prompt_files(prompts_dir: Path) -> None:
    for prompt_key, info in COMMON_PROMPTS.items():
        target = prompts_dir / info["path"]
        if not target.exists():
            atomic_write_text(target, _default_common_prompt_content(prompt_key))


def _system_template_dir() -> Path:
    return TEMPLATE_STORAGE_ROOT / "system" / "default_v1"


def _user_root(user_id: int) -> Path:
    return TEMPLATE_STORAGE_ROOT / "users" / str(user_id)


def _user_templates_root(user_id: int) -> Path:
    return _user_root(user_id) / "templates"


def _preferences_path(user_id: int) -> Path:
    return _user_root(user_id) / "preferences.json"


def _template_prompts_dir(template_dir: Path) -> Path:
    return template_dir / "prompts"


def _template_manifest_path(template_dir: Path) -> Path:
    return template_dir / "manifest.json"


def _prompt_relative_path(prompt_key: str) -> Path:
    if prompt_key in COMMON_PROMPTS:
        return COMMON_PROMPTS[prompt_key]["path"]
    if prompt_key in LEGACY_COMMON_PROMPTS:
        return LEGACY_COMMON_PROMPTS[prompt_key]["path"]

    match = re.fullmatch(r"([a-z0-9_]+)\.(step[456])", prompt_key or "")
    if not match:
        raise PromptTemplateError("非法 prompt_key")
    cot_key, step_key = match.groups()
    if cot_key not in {item["key"] for item in COT_PROMPT_LAYOUT}:
        raise PromptTemplateError("CoT 类型不在当前支持范围内")
    return Path("cot_types") / cot_key / STEP_PROMPTS[step_key]["path_name"]


def _prompt_path(template_dir: Path, prompt_key: str) -> Path:
    return _template_prompts_dir(template_dir) / _prompt_relative_path(prompt_key)


def _slugify_name(name: str) -> str:
    text = (name or "我的模板").strip().lower()
    text = re.sub(r"[^0-9a-zA-Z一-龥_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "my_template"
    return text[:48]


def _load_manifest(template_dir: Path) -> Dict[str, Any]:
    path = _template_manifest_path(template_dir)
    if not path.exists():
        raise PromptTemplateError("模板 manifest 不存在")
    return read_json(path)


def _save_manifest(template_dir: Path, manifest: Dict[str, Any]) -> None:
    manifest["updated_at"] = utc_now_iso()
    atomic_write_json(_template_manifest_path(template_dir), manifest)


def ensure_system_template() -> Dict[str, Any]:
    """Create or repair the read-only system template from docs/background."""
    template_dir = _system_template_dir()
    prompts_dir = _template_prompts_dir(template_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    for prompt_key, info in COMMON_PROMPTS.items():
        atomic_write_text(prompts_dir / info["path"], _default_common_prompt_content(prompt_key))
    for prompt_key, info in LEGACY_COMMON_PROMPTS.items():
        target = prompts_dir / info["path"]
        if not target.exists():
            atomic_write_text(target, _default_common_prompt_content(prompt_key))

    for cot in COT_PROMPT_LAYOUT:
        source_dir = PROMPT_SOURCE_ROOT / cot["prompt_dir"]
        for step_key, step_info in STEP_PROMPTS.items():
            source_name = cot[step_key]
            target = prompts_dir / "cot_types" / cot["key"] / step_info["path_name"]
            atomic_write_text(target, read_text(source_dir / source_name))

    manifest_path = _template_manifest_path(template_dir)
    now = utc_now_iso()
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        created_at = manifest.get("created_at") or now
    else:
        created_at = now
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "template_id": SYSTEM_TEMPLATE_ID,
        "name": SYSTEM_TEMPLATE_NAME,
        "owner_type": "system",
        "owner_id": None,
        "base_template_id": None,
        "version": 1,
        "status": "active",
        "is_system": True,
        "is_readonly": True,
        "created_at": created_at,
        "updated_at": now,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def _read_preferences(user_id: int) -> Dict[str, Any]:
    path = _preferences_path(user_id)
    if not path.exists():
        return {"default_template_id": None, "last_used_template_id": None}
    try:
        data = read_json(path)
    except Exception:
        return {"default_template_id": None, "last_used_template_id": None}
    return {
        "default_template_id": data.get("default_template_id"),
        "last_used_template_id": data.get("last_used_template_id"),
    }


def _write_preferences(user_id: int, data: Dict[str, Any]) -> None:
    payload = {
        "default_template_id": data.get("default_template_id"),
        "last_used_template_id": data.get("last_used_template_id"),
    }
    atomic_write_json(_preferences_path(user_id), payload)


def get_user_preferences(user_id: int) -> Dict[str, Any]:
    ensure_system_template()
    preferences = _read_preferences(user_id)
    default_id = preferences.get("default_template_id")
    if default_id and get_template_dir(default_id, user_id) is None:
        preferences["default_template_id"] = None
        _write_preferences(user_id, preferences)
    return preferences


def _iter_user_template_dirs(user_id: int) -> List[Path]:
    root = _user_templates_root(user_id)
    if not root.exists():
        return []
    return [path for path in root.iterdir() if path.is_dir() and _template_manifest_path(path).exists()]


def _count_template_usage(template_id: str) -> int:
    if not RUN_STORAGE_ROOT.exists():
        return 0
    count = 0
    for manifest_path in RUN_STORAGE_ROOT.glob("*/manifest.json"):
        try:
            manifest = read_json(manifest_path)
        except Exception:
            continue
        if manifest.get("prompt_template", {}).get("template_id") == template_id:
            count += 1
    return count


def _decorate_manifest(manifest: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    item = dict(manifest)
    item["used_count"] = _count_template_usage(item.get("template_id", ""))
    preferences = _read_preferences(user_id)
    item["is_default"] = preferences.get("default_template_id") == item.get("template_id")
    item["can_edit"] = item.get("owner_type") == "user" and item.get("owner_id") == user_id and not item.get("is_readonly")
    item["can_delete"] = item["can_edit"] and item["used_count"] == 0
    item["can_duplicate"] = True
    return item


def list_templates(user_id: int) -> Dict[str, Any]:
    ensure_system_template()
    templates = [_decorate_manifest(_load_manifest(_system_template_dir()), user_id)]
    for template_dir in _iter_user_template_dirs(user_id):
        try:
            manifest = _load_manifest(template_dir)
        except Exception:
            continue
        if manifest.get("status") != "active":
            continue
        templates.append(_decorate_manifest(manifest, user_id))
    templates.sort(key=lambda item: (item.get("owner_type") != "system", item.get("created_at") or ""))
    preferences = get_user_preferences(user_id)
    effective_default_id = preferences.get("default_template_id") or SYSTEM_TEMPLATE_ID
    return {
        "templates": templates,
        "preferences": preferences,
        "effective_default_template_id": effective_default_id,
        "system_template_id": SYSTEM_TEMPLATE_ID,
    }


def get_template_dir(template_id: str, user_id: int) -> Optional[Path]:
    ensure_system_template()
    if template_id == SYSTEM_TEMPLATE_ID:
        return _system_template_dir()
    expected_prefix = f"user_{user_id}_"
    if not str(template_id or "").startswith(expected_prefix):
        return None
    for template_dir in _iter_user_template_dirs(user_id):
        try:
            manifest = _load_manifest(template_dir)
        except Exception:
            continue
        if manifest.get("template_id") == template_id and manifest.get("owner_id") == user_id:
            return template_dir
    return None


def require_template_dir(template_id: str, user_id: int) -> Path:
    template_dir = get_template_dir(template_id, user_id)
    if template_dir is None:
        raise PromptTemplateError("模板不存在或无权访问")
    return template_dir


def build_prompt_tree() -> List[Dict[str, Any]]:
    common_children = [
        {"id": key, "label": info["label"], "prompt_key": key, "is_prompt": True}
        for key, info in COMMON_PROMPTS.items()
    ]
    cot_children = []
    for cot in COT_PROMPT_LAYOUT:
        cot_children.append({
            "id": cot["key"],
            "label": cot["display_name"],
            "is_prompt": False,
            "children": [
                {
                    "id": f"{cot['key']}.{step_key}",
                    "label": step_info["label"],
                    "prompt_key": f"{cot['key']}.{step_key}",
                    "cot_type_key": cot["key"],
                    "cot_type_name": cot["display_name"],
                    "is_prompt": True,
                }
                for step_key, step_info in STEP_PROMPTS.items()
            ],
        })
    return [
        {"id": "common", "label": "通用步骤", "is_prompt": False, "children": common_children},
        {"id": "cot_types", "label": "CoT 类型专属步骤", "is_prompt": False, "children": cot_children},
    ]


def get_template_detail(template_id: str, user_id: int) -> Dict[str, Any]:
    template_dir = require_template_dir(template_id, user_id)
    manifest = _decorate_manifest(_load_manifest(template_dir), user_id)
    return {
        "manifest": manifest,
        "tree": build_prompt_tree(),
        "prompt_count": len(COMMON_PROMPTS) + len(COT_PROMPT_LAYOUT) * len(STEP_PROMPTS),
    }


def get_prompt_item(template_id: str, user_id: int, prompt_key: str) -> Dict[str, Any]:
    template_dir = require_template_dir(template_id, user_id)
    _ensure_common_prompt_files(_template_prompts_dir(template_dir))
    manifest = _decorate_manifest(_load_manifest(template_dir), user_id)
    rel_path = _prompt_relative_path(prompt_key)
    content = read_text(_template_prompts_dir(template_dir) / rel_path)
    _ensure_common_prompt_files(_template_prompts_dir(_system_template_dir()))
    default_content = read_text(_template_prompts_dir(_system_template_dir()) / rel_path)
    return {
        "prompt_key": prompt_key,
        "content": content,
        "default_content": default_content,
        "relative_path": rel_path.as_posix(),
        "manifest": manifest,
    }


def update_prompt_item(template_id: str, user_id: int, prompt_key: str, content: str) -> Dict[str, Any]:
    if not str(content or "").strip():
        raise PromptTemplateError("Prompt 内容不能为空")
    template_dir = require_template_dir(template_id, user_id)
    manifest = _load_manifest(template_dir)
    if manifest.get("is_readonly") or manifest.get("owner_id") != user_id:
        raise PromptTemplateError("只能编辑自己的用户模板")
    target = _prompt_path(template_dir, prompt_key)
    atomic_write_text(target, content)
    _save_manifest(template_dir, manifest)
    return get_prompt_item(template_id, user_id, prompt_key)


def restore_prompt_item_default(template_id: str, user_id: int, prompt_key: str) -> Dict[str, Any]:
    template_dir = require_template_dir(template_id, user_id)
    _ensure_common_prompt_files(_template_prompts_dir(template_dir))
    manifest = _load_manifest(template_dir)
    if manifest.get("is_readonly") or manifest.get("owner_id") != user_id:
        raise PromptTemplateError("只能恢复自己的用户模板")
    rel_path = _prompt_relative_path(prompt_key)
    _ensure_common_prompt_files(_template_prompts_dir(_system_template_dir()))
    default_content = read_text(_template_prompts_dir(_system_template_dir()) / rel_path)
    atomic_write_text(_template_prompts_dir(template_dir) / rel_path, default_content)
    _save_manifest(template_dir, manifest)
    return get_prompt_item(template_id, user_id, prompt_key)


def _next_template_dir(user_id: int, name: str) -> Path:
    base_slug = _slugify_name(name)
    root = _user_templates_root(user_id)
    root.mkdir(parents=True, exist_ok=True)
    candidate = root / base_slug
    index = 2
    while candidate.exists():
        candidate = root / f"{base_slug}_{index}"
        index += 1
    return candidate


def duplicate_template(template_id: str, user_id: int, name: str) -> Dict[str, Any]:
    source_dir = require_template_dir(template_id, user_id)
    source_manifest = _load_manifest(source_dir)
    new_name = (name or "").strip()
    if not new_name:
        raise PromptTemplateError("模板名称不能为空")

    target_dir = _next_template_dir(user_id, new_name)
    shutil.copytree(_template_prompts_dir(source_dir), _template_prompts_dir(target_dir))
    now = utc_now_iso()
    existing_versions = [
        int((_load_manifest(path).get("version") or 0))
        for path in _iter_user_template_dirs(user_id)
        if path != target_dir
    ]
    version = (max(existing_versions) if existing_versions else 0) + 1
    template_id_new = f"user_{user_id}_{target_dir.name}"
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "template_id": template_id_new,
        "name": new_name,
        "owner_type": "user",
        "owner_id": user_id,
        "base_template_id": source_manifest.get("template_id"),
        "version": version,
        "status": "active",
        "is_system": False,
        "is_readonly": False,
        "created_at": now,
        "updated_at": now,
    }
    atomic_write_json(_template_manifest_path(target_dir), manifest)
    return _decorate_manifest(manifest, user_id)


def rename_template(template_id: str, user_id: int, name: str) -> Dict[str, Any]:
    new_name = (name or "").strip()
    if not new_name:
        raise PromptTemplateError("模板名称不能为空")
    template_dir = require_template_dir(template_id, user_id)
    manifest = _load_manifest(template_dir)
    if manifest.get("is_readonly") or manifest.get("owner_id") != user_id:
        raise PromptTemplateError("只能重命名自己的用户模板")
    manifest["name"] = new_name
    _save_manifest(template_dir, manifest)
    return _decorate_manifest(manifest, user_id)


def set_default_template(template_id: str, user_id: int) -> Dict[str, Any]:
    require_template_dir(template_id, user_id)
    preferences = _read_preferences(user_id)
    preferences["default_template_id"] = template_id
    preferences["last_used_template_id"] = template_id
    _write_preferences(user_id, preferences)
    return preferences


def delete_template(template_id: str, user_id: int) -> Dict[str, Any]:
    template_dir = require_template_dir(template_id, user_id)
    manifest = _load_manifest(template_dir)
    if manifest.get("is_system") or manifest.get("is_readonly"):
        raise PromptTemplateError("系统模板不可删除")
    if manifest.get("owner_id") != user_id:
        raise PromptTemplateError("只能删除自己的用户模板")
    used_count = _count_template_usage(template_id)
    if used_count > 0:
        raise PromptTemplateError("模板已被历史 run 使用，不能删除")
    shutil.rmtree(template_dir)
    preferences = _read_preferences(user_id)
    if preferences.get("default_template_id") == template_id:
        preferences["default_template_id"] = None
    if preferences.get("last_used_template_id") == template_id:
        preferences["last_used_template_id"] = None
    _write_preferences(user_id, preferences)
    return {"deleted": True, "template_id": template_id}


def resolve_template_for_run(user_id: int, template_id: Optional[str]) -> Dict[str, Any]:
    ensure_system_template()
    selected_id = (template_id or "").strip()
    if not selected_id:
        preferences = get_user_preferences(user_id)
        selected_id = preferences.get("default_template_id") or SYSTEM_TEMPLATE_ID
    template_dir = require_template_dir(selected_id, user_id)
    manifest = _decorate_manifest(_load_manifest(template_dir), user_id)
    preferences = _read_preferences(user_id)
    preferences["last_used_template_id"] = selected_id
    _write_preferences(user_id, preferences)
    return {"template_id": selected_id, "template_dir": template_dir, "manifest": manifest}


def create_run_prompt_snapshot(template_id: str, user_id: int, run_dir: Path) -> Dict[str, Any]:
    resolved = resolve_template_for_run(user_id, template_id)
    template_dir = resolved["template_dir"]
    template_manifest = resolved["manifest"]
    _ensure_common_prompt_files(_template_prompts_dir(template_dir))
    snapshot_dir = run_dir / "prompts"
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    shutil.copytree(_template_prompts_dir(template_dir), snapshot_dir)
    _ensure_common_prompt_files(snapshot_dir)
    snapshot_manifest = {
        "schema_version": SCHEMA_VERSION,
        "template_id": template_manifest.get("template_id"),
        "template_name": template_manifest.get("name"),
        "owner_type": template_manifest.get("owner_type"),
        "owner_id": template_manifest.get("owner_id"),
        "version": template_manifest.get("version"),
        "base_template_id": template_manifest.get("base_template_id"),
        "snapshot_created_at": utc_now_iso(),
        "snapshot_path": "prompts/",
        "prompt_count": len(COMMON_PROMPTS) + len(COT_PROMPT_LAYOUT) * len(STEP_PROMPTS),
    }
    atomic_write_json(snapshot_dir / "manifest.json", snapshot_manifest)
    return snapshot_manifest


def read_prompt_from_snapshot(prompt_snapshot_dir: Path, prompt_key: str) -> str:
    if not prompt_snapshot_dir.exists() or not (prompt_snapshot_dir / "manifest.json").exists():
        raise PromptTemplateError("run 提示词快照不存在")
    _ensure_common_prompt_files(prompt_snapshot_dir)
    rel_path = _prompt_relative_path(prompt_key)
    return read_text(prompt_snapshot_dir / rel_path)
