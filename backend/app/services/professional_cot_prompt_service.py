"""DB-based prompt template management for professional CoT pipeline.

需求 29：标注流水线2提示词模板管理。
Migrated from file-based storage to MySQL prompts table.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import SessionLocal
from app.models.models import Prompt, Task, StageEnum

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
    },
}

LEGACY_COMMON_PROMPTS = {
    "common.step1": {
        "label": "Step 1：筛选相关文献",
        "step_no": 1,
    },
    "common.step2": {
        "label": "Step 2：构建文献案例卡",
        "step_no": 2,
    },
    "common.step3": {
        "label": "Step 3：判定 CoT 类型",
        "step_no": 3,
    },
}

STEP_PROMPTS = {
    "step4": {"label": "Step 4：生成 input", "path_name": "step4_input.md"},
    "step5": {"label": "Step 5：生成 chainofThought", "path_name": "step5_chain.md"},
    "step6": {"label": "Step 6：生成 output", "path_name": "step6_output.md"},
}

# ---------------------------------------------------------------------------
# Prompt key helpers (unchanged from original — these define the structure)
# ---------------------------------------------------------------------------


def _validate_prompt_key(prompt_key: str) -> None:
    """Raise PromptTemplateError if prompt_key is not in the known schema."""
    if prompt_key in COMMON_PROMPTS:
        return
    if prompt_key in LEGACY_COMMON_PROMPTS:
        return
    match = re.fullmatch(r"([a-z0-9_]+)\.(step[456])", prompt_key or "")
    if not match:
        raise PromptTemplateError("非法 prompt_key")
    cot_key, step_key = match.groups()
    if cot_key not in {item["key"] for item in COT_PROMPT_LAYOUT}:
        raise PromptTemplateError("CoT 类型不在当前支持范围内")
    if step_key not in STEP_PROMPTS:
        raise PromptTemplateError("非法步骤 key")


def _all_prompt_keys() -> List[str]:
    """Return all 31 prompt keys for a template."""
    keys = list(COMMON_PROMPTS.keys())
    for cot in COT_PROMPT_LAYOUT:
        for step_key in STEP_PROMPTS:
            keys.append(f"{cot['key']}.{step_key}")
    return keys


# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------


class PromptTemplateError(ValueError):
    """Raised when prompt template operations are invalid."""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _slugify_name(name: str) -> str:
    text = (name or "我的模板").strip().lower()
    text = re.sub(r"[^0-9a-zA-Z一-龥_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "my_template"
    return text[:48]


# ---------------------------------------------------------------------------
# Preferences (file-based — kept as-is per task spec)
# ---------------------------------------------------------------------------

import json as _json
import os as _os
from pathlib import Path as _Path

_PREFERENCES_ROOT = _Path(__file__).resolve().parents[3] / "storage" / "professional_cot_prompt_templates"


def _preferences_path(user_id: int) -> _Path:
    return _PREFERENCES_ROOT / "users" / str(user_id) / "preferences.json"


def _read_preferences(user_id: int) -> Dict[str, Any]:
    path = _preferences_path(user_id)
    if not path.exists():
        return {"default_template_id": None, "last_used_template_id": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
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
    path = _preferences_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, ensure_ascii=False, indent=2)
    _os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_meta_row(db, template_id: str) -> Optional[Prompt]:
    """Get a representative row for template metadata (any row for this template_id)."""
    return db.query(Prompt).filter(
        Prompt.template_id == template_id,
        Prompt.stage == StageEnum.PROFESSIONAL_COT,
    ).first()


def _get_prompt_row(db, template_id: str, prompt_key: str) -> Optional[Prompt]:
    return db.query(Prompt).filter(
        Prompt.template_id == template_id,
        Prompt.prompt_key == prompt_key,
        Prompt.stage == StageEnum.PROFESSIONAL_COT,
    ).first()


def _require_prompt_row(db, template_id: str, prompt_key: str) -> Prompt:
    row = _get_prompt_row(db, template_id, prompt_key)
    if row is None:
        raise PromptTemplateError(f"提示词不存在：{template_id}/{prompt_key}")
    return row


def _build_manifest_from_row(row: Prompt) -> Dict[str, Any]:
    """Build a manifest dict from a Prompt row's metadata columns."""
    ref = row.reference_fields or {}
    is_system = (row.template_id or "").startswith("system_")
    return {
        "schema_version": ref.get("schema_version", SCHEMA_VERSION),
        "template_id": row.template_id,
        "name": row.name or "",
        "owner_type": "system" if is_system else "user",
        "owner_id": row.user_id,
        "base_template_id": ref.get("base_template_id"),
        "version": row.version or 1,
        "status": "active",
        "is_system": is_system,
        "is_readonly": is_system,
        "created_at": row.created_at.isoformat() if row.created_at else utc_now_iso(),
        "updated_at": utc_now_iso(),
    }


def _count_template_usage(template_id: str) -> int:
    """Count how many tasks reference this template via prompt_template_id."""
    db = SessionLocal()
    try:
        return db.query(Task).filter(Task.prompt_template_id == template_id).count()
    finally:
        db.close()


def _decorate_manifest(manifest: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    item = dict(manifest)
    item["used_count"] = _count_template_usage(item.get("template_id", ""))
    preferences = _read_preferences(user_id)
    item["is_default"] = preferences.get("default_template_id") == item.get("template_id")
    item["can_edit"] = item.get("owner_type") == "user" and item.get("owner_id") == user_id and not item.get("is_readonly")
    item["can_delete"] = item["can_edit"] and item["used_count"] == 0
    item["can_duplicate"] = True
    return item


def _template_exists(db, template_id: str) -> bool:
    return db.query(Prompt).filter(
        Prompt.template_id == template_id,
        Prompt.stage == StageEnum.PROFESSIONAL_COT,
    ).first() is not None


def _require_template(db, template_id: str, user_id: int) -> Prompt:
    """Require that the template exists and user has access, return a metadata row."""
    row = _get_meta_row(db, template_id)
    if row is None:
        raise PromptTemplateError("模板不存在或无权访问")
    is_system = (template_id or "").startswith("system_")
    if not is_system:
        expected_prefix = f"user_{user_id}_"
        if not str(template_id or "").startswith(expected_prefix):
            raise PromptTemplateError("模板不存在或无权访问")
    return row


# ---------------------------------------------------------------------------
# Public API — list / detail
# ---------------------------------------------------------------------------


def list_templates(user_id: int) -> Dict[str, Any]:
    """Return all templates (system + user) with decorated manifests."""
    db = SessionLocal()
    try:
        # Get distinct template_ids for professional_cot stage
        rows = db.query(Prompt.template_id, Prompt.user_id).filter(
            Prompt.stage == StageEnum.PROFESSIONAL_COT,
        ).distinct().all()

        template_ids_seen = set()
        templates = []
        for template_id, owner_id in rows:
            if template_id in template_ids_seen:
                continue
            template_ids_seen.add(template_id)
            is_system = (template_id or "").startswith("system_")
            # For user templates, only show those belonging to this user
            if not is_system and owner_id != user_id:
                continue
            meta_row = _get_meta_row(db, template_id)
            if meta_row is None:
                continue
            manifest = _build_manifest_from_row(meta_row)
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
    finally:
        db.close()


def get_user_preferences(user_id: int) -> Dict[str, Any]:
    preferences = _read_preferences(user_id)
    default_id = preferences.get("default_template_id")
    if default_id:
        db = SessionLocal()
        try:
            if not _template_exists(db, default_id):
                preferences["default_template_id"] = None
                _write_preferences(user_id, preferences)
        finally:
            db.close()
    return preferences


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
    db = SessionLocal()
    try:
        row = _require_template(db, template_id, user_id)
        manifest = _decorate_manifest(_build_manifest_from_row(row), user_id)
        return {
            "manifest": manifest,
            "tree": build_prompt_tree(),
            "prompt_count": len(COMMON_PROMPTS) + len(COT_PROMPT_LAYOUT) * len(STEP_PROMPTS),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Public API — prompt item CRUD
# ---------------------------------------------------------------------------


def get_prompt_item(template_id: str, user_id: int, prompt_key: str) -> Dict[str, Any]:
    _validate_prompt_key(prompt_key)
    db = SessionLocal()
    try:
        row = _require_template(db, template_id, user_id)
        manifest = _decorate_manifest(_build_manifest_from_row(row), user_id)

        prompt_row = _require_prompt_row(db, template_id, prompt_key)
        content = prompt_row.content or ""

        # Get default content from system template
        sys_row = _get_prompt_row(db, SYSTEM_TEMPLATE_ID, prompt_key)
        default_content = sys_row.content if sys_row else ""

        return {
            "prompt_key": prompt_key,
            "content": content,
            "default_content": default_content,
            "relative_path": prompt_key,  # keep compatibility — frontend may use this
            "manifest": manifest,
        }
    finally:
        db.close()


def update_prompt_item(template_id: str, user_id: int, prompt_key: str, content: str) -> Dict[str, Any]:
    if not str(content or "").strip():
        raise PromptTemplateError("Prompt 内容不能为空")
    _validate_prompt_key(prompt_key)
    db = SessionLocal()
    try:
        row = _require_template(db, template_id, user_id)
        manifest = _build_manifest_from_row(row)
        if manifest.get("is_readonly") or manifest.get("owner_id") != user_id:
            raise PromptTemplateError("只能编辑自己的用户模板")

        prompt_row = _require_prompt_row(db, template_id, prompt_key)
        prompt_row.content = content
        db.commit()
    finally:
        db.close()
    return get_prompt_item(template_id, user_id, prompt_key)


def restore_prompt_item_default(template_id: str, user_id: int, prompt_key: str) -> Dict[str, Any]:
    _validate_prompt_key(prompt_key)
    db = SessionLocal()
    try:
        row = _require_template(db, template_id, user_id)
        manifest = _build_manifest_from_row(row)
        if manifest.get("is_readonly") or manifest.get("owner_id") != user_id:
            raise PromptTemplateError("只能恢复自己的用户模板")

        sys_row = _require_prompt_row(db, SYSTEM_TEMPLATE_ID, prompt_key)
        default_content = sys_row.content or ""

        prompt_row = _require_prompt_row(db, template_id, prompt_key)
        prompt_row.content = default_content
        db.commit()
    finally:
        db.close()
    return get_prompt_item(template_id, user_id, prompt_key)


# ---------------------------------------------------------------------------
# Public API — template lifecycle
# ---------------------------------------------------------------------------


def duplicate_template(template_id: str, user_id: int, name: str) -> Dict[str, Any]:
    new_name = (name or "").strip()
    if not new_name:
        raise PromptTemplateError("模板名称不能为空")

    db = SessionLocal()
    try:
        source_row = _require_template(db, template_id, user_id)
        source_manifest = _build_manifest_from_row(source_row)

        # Generate new template_id
        slug = _slugify_name(new_name)
        new_template_id = f"user_{user_id}_{slug}"

        # Ensure uniqueness
        existing = _get_meta_row(db, new_template_id)
        counter = 2
        while existing is not None:
            new_template_id = f"user_{user_id}_{slug}_{counter}"
            existing = _get_meta_row(db, new_template_id)
            counter += 1

        # Compute next version
        max_version = db.query(Prompt.version).filter(
            Prompt.stage == StageEnum.PROFESSIONAL_COT,
            Prompt.user_id == user_id,
        ).order_by(Prompt.version.desc()).first()
        version = (max_version[0] + 1) if max_version and max_version[0] else 1

        now = datetime.utcnow()
        ref_fields = {
            "schema_version": SCHEMA_VERSION,
            "base_template_id": source_manifest.get("template_id"),
        }

        # Copy all prompt rows from source
        source_rows = db.query(Prompt).filter(
            Prompt.template_id == template_id,
            Prompt.stage == StageEnum.PROFESSIONAL_COT,
        ).all()

        for src in source_rows:
            new_row = Prompt(
                user_id=user_id,
                stage=StageEnum.PROFESSIONAL_COT,
                version=version,
                name=new_name,
                content=src.content,
                template_id=new_template_id,
                prompt_key=src.prompt_key,
                reference_fields=ref_fields,
                created_at=now,
                is_default=False,
            )
            db.add(new_row)

        db.commit()

        # Return manifest for the new template
        new_meta = _get_meta_row(db, new_template_id)
        manifest = _build_manifest_from_row(new_meta) if new_meta else {
            "schema_version": SCHEMA_VERSION,
            "template_id": new_template_id,
            "name": new_name,
            "owner_type": "user",
            "owner_id": user_id,
            "base_template_id": source_manifest.get("template_id"),
            "version": version,
            "status": "active",
            "is_system": False,
            "is_readonly": False,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        return _decorate_manifest(manifest, user_id)
    finally:
        db.close()


def rename_template(template_id: str, user_id: int, name: str) -> Dict[str, Any]:
    new_name = (name or "").strip()
    if not new_name:
        raise PromptTemplateError("模板名称不能为空")

    db = SessionLocal()
    try:
        row = _require_template(db, template_id, user_id)
        manifest = _build_manifest_from_row(row)
        if manifest.get("is_readonly") or manifest.get("owner_id") != user_id:
            raise PromptTemplateError("只能重命名自己的用户模板")

        # Update name on all rows of this template
        db.query(Prompt).filter(
            Prompt.template_id == template_id,
            Prompt.stage == StageEnum.PROFESSIONAL_COT,
        ).update({"name": new_name})
        db.commit()

        # Re-fetch for updated manifest
        row = _get_meta_row(db, template_id)
        return _decorate_manifest(_build_manifest_from_row(row), user_id)
    finally:
        db.close()


def set_default_template(template_id: str, user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        _require_template(db, template_id, user_id)
    finally:
        db.close()
    preferences = _read_preferences(user_id)
    preferences["default_template_id"] = template_id
    preferences["last_used_template_id"] = template_id
    _write_preferences(user_id, preferences)
    return preferences


def delete_template(template_id: str, user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        row = _require_template(db, template_id, user_id)
        manifest = _build_manifest_from_row(row)
        if manifest.get("is_system") or manifest.get("is_readonly"):
            raise PromptTemplateError("系统模板不可删除")
        if manifest.get("owner_id") != user_id:
            raise PromptTemplateError("只能删除自己的用户模板")

        used_count = _count_template_usage(template_id)
        if used_count > 0:
            raise PromptTemplateError("模板已被历史 run 使用，不能删除")

        # Delete all prompt rows for this template
        db.query(Prompt).filter(
            Prompt.template_id == template_id,
            Prompt.stage == StageEnum.PROFESSIONAL_COT,
        ).delete()
        db.commit()
    finally:
        db.close()

    preferences = _read_preferences(user_id)
    if preferences.get("default_template_id") == template_id:
        preferences["default_template_id"] = None
    if preferences.get("last_used_template_id") == template_id:
        preferences["last_used_template_id"] = None
    _write_preferences(user_id, preferences)
    return {"deleted": True, "template_id": template_id}


# ---------------------------------------------------------------------------
# Public API — run-time snapshot / resolution
# ---------------------------------------------------------------------------


def resolve_template_for_run(user_id: int, template_id: Optional[str]) -> Dict[str, Any]:
    """Resolve which template to use for a pipeline run."""
    selected_id = (template_id or "").strip()
    if not selected_id:
        preferences = get_user_preferences(user_id)
        selected_id = preferences.get("default_template_id") or SYSTEM_TEMPLATE_ID

    db = SessionLocal()
    try:
        row = _require_template(db, selected_id, user_id)
        manifest = _decorate_manifest(_build_manifest_from_row(row), user_id)

        preferences = _read_preferences(user_id)
        preferences["last_used_template_id"] = selected_id
        _write_preferences(user_id, preferences)

        return {"template_id": selected_id, "manifest": manifest}
    finally:
        db.close()


def create_run_prompt_snapshot(template_id: str, user_id: int, task_id: int) -> Dict[str, Any]:
    """Record the template snapshot info on the Task row.

    Takes task_id (int) instead of run_dir (Path).
    Writes snapshot metadata to Task.run_extra['prompt_snapshot'].
    """
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task is None:
            raise PromptTemplateError(f"任务不存在：{task_id}")

        resolved = resolve_template_for_run(user_id, template_id)
        template_manifest = resolved["manifest"]

        snapshot_manifest = {
            "schema_version": SCHEMA_VERSION,
            "template_id": template_manifest.get("template_id"),
            "template_name": template_manifest.get("name"),
            "owner_type": template_manifest.get("owner_type"),
            "owner_id": template_manifest.get("owner_id"),
            "version": template_manifest.get("version"),
            "base_template_id": template_manifest.get("base_template_id"),
            "snapshot_created_at": utc_now_iso(),
            "snapshot_path": "prompts/",  # keep compatibility
            "prompt_count": len(COMMON_PROMPTS) + len(COT_PROMPT_LAYOUT) * len(STEP_PROMPTS),
        }

        # Write to Task.run_extra
        run_extra = task.run_extra or {}
        run_extra["prompt_snapshot"] = snapshot_manifest
        task.run_extra = run_extra
        task.prompt_template_id = template_manifest.get("template_id")
        db.commit()

        return snapshot_manifest
    finally:
        db.close()


def read_prompt_from_snapshot(template_id: str, prompt_key: str) -> str:
    """Read a prompt from the DB by template_id + prompt_key.

    Called during pipeline execution to fetch the prompt content
    that was snapshotted for this run.
    """
    _validate_prompt_key(prompt_key)
    db = SessionLocal()
    try:
        row = _require_prompt_row(db, template_id, prompt_key)
        return row.content or ""
    finally:
        db.close()
