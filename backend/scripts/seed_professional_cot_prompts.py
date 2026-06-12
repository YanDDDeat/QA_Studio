"""Seed the professional_cot system template into the prompts table.

Reads all 31 prompt .md files from docs/background/3类COT提示词/
and inserts them into the prompts table with:
  - template_id = 'system_default_v1'
  - stage = 'professional_cot'
  - user_id = NULL (global)

Usage:
    docker exec qa-studio-backend python3 scripts/seed_professional_cot_prompts.py
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.models import Prompt, StageEnum

# ---------------------------------------------------------------------------
# Constants (mirror professional_cot_prompt_service.py)
# ---------------------------------------------------------------------------

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

STEP_KEYS = ["step4", "step5", "step6"]


def _find_project_root() -> Path:
    """Find project root by locating the marker file."""
    env_root = os.getenv("QA_STUDIO_ROOT") or os.getenv("PROJECT_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / "docs" / "background" / "3类COT提示词").exists():
            return p
    # Try from current file location
    current = Path(__file__).resolve().parents[1]  # backend/.. → project root
    if (current / "docs" / "background" / "3类COT提示词").exists():
        return current
    # Fallback
    cwd = Path.cwd()
    if (cwd / "docs" / "background" / "3类COT提示词").exists():
        return cwd
    raise FileNotFoundError("无法定位项目根目录 (docs/background/3类COT提示词/ 不存在)")


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_common_prompt(step_no: int, source_md: str) -> str:
    """Extract a single step's prompt from 专业Cot构建.md."""
    pattern = re.compile(
        rf"###\s*Step\s*{step_no}[^\n]*\n(.*?)(?=\n###\s*Step\s*\d+|\Z)",
        re.S | re.I,
    )
    match = pattern.search(source_md)
    return match.group(0).strip() if match else ""


def build_prompt_records(prompt_root: Path) -> List[Dict[str, Any]]:
    """Build a list of {prompt_key, content} dicts for all 31 prompts."""
    records = []

    # --- Common prompt: step1_3 ---
    step1_3_path = prompt_root / "step1_3_integrated_extraction_and_routing.md"
    if step1_3_path.exists():
        records.append({
            "prompt_key": "common.step1_3",
            "content": read_text(step1_3_path),
        })
    else:
        print(f"  ⚠ 缺少文件: {step1_3_path}")

    # --- Legacy common prompts (step1, step2, step3) extracted from 专业Cot构建.md ---
    source_md_path = prompt_root / "专业Cot构建.md"
    source_md = read_text(source_md_path) if source_md_path.exists() else ""
    if source_md:
        for step_no in [1, 2, 3]:
            content = _extract_common_prompt(step_no, source_md)
            records.append({
                "prompt_key": f"common.step{step_no}",
                "content": content,
            })
    else:
        print(f"  ⚠ 缺少文件: {source_md_path}")

    # --- 10 CoT types × 3 steps = 30 prompts ---
    for cot in COT_PROMPT_LAYOUT:
        cot_dir = prompt_root / cot["prompt_dir"]
        for step_key in STEP_KEYS:
            filename = cot[step_key]
            filepath = cot_dir / filename
            if filepath.exists():
                records.append({
                    "prompt_key": f"{cot['key']}.{step_key}",
                    "content": read_text(filepath),
                })
            else:
                print(f"  ⚠ 缺少文件: {filepath}")

    return records


def seed():
    project_root = _find_project_root()
    prompt_root = project_root / "docs" / "background" / "3类COT提示词"

    print(f"项目根目录: {project_root}")
    print(f"提示词源目录: {prompt_root}")
    print()

    records = build_prompt_records(prompt_root)
    print(f"读取到 {len(records)} 条提示词记录")

    db = SessionLocal()
    try:
        # Check if system template already exists
        existing = db.query(Prompt).filter(
            Prompt.template_id == SYSTEM_TEMPLATE_ID,
            Prompt.stage == StageEnum.PROFESSIONAL_COT,
        ).count()

        if existing > 0:
            print(f"\n系统模板 '{SYSTEM_TEMPLATE_ID}' 已存在 ({existing} 行)。")
            answer = input("是否删除并重建？[y/N] ").strip().lower()
            if answer == "y":
                db.query(Prompt).filter(
                    Prompt.template_id == SYSTEM_TEMPLATE_ID,
                    Prompt.stage == StageEnum.PROFESSIONAL_COT,
                ).delete()
                db.commit()
                print("已删除旧记录。")
            else:
                print("跳过。")
                return

        now = datetime.utcnow()
        ref_fields = {"schema_version": SCHEMA_VERSION}

        inserted = 0
        for rec in records:
            prompt = Prompt(
                user_id=None,  # global/system
                stage=StageEnum.PROFESSIONAL_COT,
                version=1,
                name=SYSTEM_TEMPLATE_NAME,
                content=rec["content"],
                template_id=SYSTEM_TEMPLATE_ID,
                prompt_key=rec["prompt_key"],
                reference_fields=ref_fields,
                created_at=now,
                is_default=False,
            )
            db.add(prompt)
            inserted += 1

        db.commit()
        print(f"\n✅ 成功插入 {inserted} 条系统模板提示词记录。")

    except Exception as exc:
        db.rollback()
        print(f"\n❌ 错误: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
