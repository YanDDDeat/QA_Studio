"""Add new StageEnum values for COT filter, dataset split, and assessment.

StageEnum is stored as MySQL ENUM type in 3 tables (tasks.stage,
datasets.current_stage, files.source_stage). Adding new enum values
requires ALTER TABLE on all 3 columns. This script also seeds a default
assessment Prompt.

Usage:
    cd backend
    python scripts/migrate_cot_dataset.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine, SessionLocal
from app.models.models import Prompt, StageEnum, LLMConfig


# All StageEnum values (old + new) for MySQL ENUM definition
ALL_STAGE_VALUES = [
    "question_generate",
    "knowledge_generate",
    "question_validate",
    "answer_generate",
    "answer_validate",
    "data_evaluate",
    "cot_filter",
    "dataset_split",
    "dataset_assessment",
]


def alter_enum_columns():
    """ALTER 3 MySQL ENUM columns to include the new StageEnum values."""
    enum_str = "'" + "', '".join(ALL_STAGE_VALUES) + "'"

    alter_statements = [
        # tasks.stage: NOT NULL, no default
        f"ALTER TABLE tasks MODIFY COLUMN stage ENUM({enum_str}) NOT NULL",
        # datasets.current_stage: nullable, default 'question_generate'
        f"ALTER TABLE datasets MODIFY COLUMN current_stage ENUM({enum_str}) DEFAULT 'question_generate'",
        # files.source_stage: nullable, no default
        f"ALTER TABLE files MODIFY COLUMN source_stage ENUM({enum_str})",
    ]

    with engine.connect() as conn:
        for sql in alter_statements:
            table = sql.split("ALTER TABLE ")[1].split(" ")[0]
            print(f"[migrate] {sql[:80]}...")
            conn.execute(text(sql))
            conn.commit()
            print(f"[migrate]   OK - {table}")

    print("[migrate] All ENUM columns updated with 3 new values.")


# Default assessment prompt (from QA_Gen_Studio's 简答题评分提示词.md)
ASSESSMENT_PROMPT_INITIAL = """请为下面这条简答题 QA 样本生成 `Assessment` 字段。

任务目标：
- `Assessment` 是对标准答案进行打分的评分细则，不是解析，不是评语。
- 输出必须是一个字符串，并且总分必须严格为100分。

硬性要求：
1. 只能依据【QA样本】中的 `output`、`cot` 和【源文摘录】生成评分标准，不能引入原文或标准答案中没有的数值、条件、结论、机理、公式或扩展要求。
2. 通常拆成 3-6 个评分点；若标准答案信息量明显较少，可拆成 2 个评分点，但仍必须保证每个评分点都可独立判分。
3. 每个评分点都必须写清楚：分值、满分标准、失分规则。
4. 不允许写空话或泛化表述，例如"回答完整即可得分""表述清晰即可得分""视情况给分""酌情给分"。
5. 如果标准答案包含多个并列要点，优先按并列要点拆分评分点；如果是计算/推导型简答，优先按关键计算或判断节点拆分评分点。
6. 如果出现 LaTeX 公式、数学表达式、上下标等，必须单独增加一个评分点检查公式是否正确；若没有公式，不要凭空增加。
7. 评分标准风格要具体，尽量写成可直接判分的步骤式表达。
8. 输出格式固定为单行字符串：评分点1（30分）：……；满分标准：……；失分规则：……。评分点2（40分）：……；满分标准：……；失分规则：……。评分点3（30分）：……；满分标准：……；失分规则：……。总分：100分。
9. 严格返回一个 JSON 对象，不要输出任何额外说明，格式如下：{"Assessment": "评分点1（...）......总分：100分。"}

【QA样本】
{qa_item_json}

【源文摘录】
{origin_content}"""

ASSESSMENT_PROMPT_REPAIR = """你上一次生成的 `Assessment` 不合规，请只做修复，不要新增原文中没有的信息。

不合规原因：{repair_reason}

上一版 Assessment：
{invalid_assessment}

请重新输出一个合规版本，并满足以下要求：
1. 必须仍然只依据【QA样本】与【源文摘录】。
2. 必须是单行字符串。
3. 必须包含至少2个评分点，每个评分点都要有分值、满分标准、失分规则。
4. 所有评分点分值之和必须严格等于100，且末尾必须写"总分：100分"。
5. 不能写空话、不能酌情给分、不能引入新知识。
6. 严格返回 JSON 对象：{"Assessment": "..."}

【QA样本】
{qa_item_json}

【源文摘录】
{origin_content}"""


def seed_assessment_prompt():
    """Create a default prompt for the dataset_assessment stage if one doesn't exist."""
    db = SessionLocal()
    try:
        existing = db.query(Prompt).filter(
            Prompt.stage == StageEnum.DATASET_ASSESSMENT,
            Prompt.user_id == None,
        ).first()

        if existing:
            print("[migrate] Default assessment prompt already exists. Skipping.")
            return

        # Find global dashscope config for default association
        dashscope_config = db.query(LLMConfig).filter(
            LLMConfig.user_id == None,
            LLMConfig.name == "dashscope",
        ).first()

        full_prompt = ASSESSMENT_PROMPT_INITIAL + "\n\n# 修复重写\n" + ASSESSMENT_PROMPT_REPAIR

        prompt = Prompt(
            user_id=None,
            stage=StageEnum.DATASET_ASSESSMENT,
            content=full_prompt,
            version=1,
            llm_config_id=dashscope_config.id if dashscope_config else None,
            model="qwen-plus",
        )
        db.add(prompt)
        db.commit()
        print("[migrate] Created default assessment prompt (id=%d)" % prompt.id)
    finally:
        db.close()


def main():
    print("[migrate] Starting COT/Dataset StageEnum migration...")

    # Step 1: ALTER ENUM columns to add new values
    alter_enum_columns()

    # Step 2: Seed default assessment prompt
    seed_assessment_prompt()

    print("[migrate] Migration complete.")


if __name__ == "__main__":
    main()