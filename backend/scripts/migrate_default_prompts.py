"""Add is_default column to prompts table and seed default prompts for all 7 LLM stages.

Run with: D:\Anaconda\envs\myenv\python.exe scripts/migrate_default_prompts.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.database import SessionLocal
from app.models.models import Prompt, StageEnum, LLMConfig


# Default prompts for each stage
DEFAULT_PROMPTS = {
    "question_generate": """你是一个专业的QA数据生成专家。请根据给定的文本内容，生成高质量的问答对。

要求：
1. 每条文本可能生成1-3个问答对
2. 每个问答对包含以下字段，以JSON数组格式返回：
   - input: 问题文本
   - task_type: 题型（单选/多选/判断/填空/简答）
   - domain: 所属领域
   - difficulty: 难度（较难/中等/基础）
3. 问题应该考察对文本内容的深入理解，不要简单复述
4. 答案要准确、完整，基于文本内容
5. 返回格式：[{"input":"...", "task_type":"...", "domain":"...", "difficulty":"..."}]

文本内容：
{text}""",

    "knowledge_generate": """你是一个知识体系构建专家。请根据以下问题，生成其所属的知识体系路径。

要求：
1. 生成 knowledge 字段：知识体系路径，格式为 "大类-中类-小类" 的层级结构
2. 返回JSON格式：{"knowledge": "大类-中类-小类"}
3. 知识体系路径应准确反映问题所属的知识领域和层级

问题：
{input}""",

    "question_validate": """你是一个问题质量审核专家。请评估以下问题是否符合高质量QA标准。

评估维度：
1. 问题表述是否清晰、无歧义
2. 问题是否具有实际考察意义
3. 问题是否可以基于给定内容得出明确答案
4. 问题难度是否合理

请返回JSON格式：
{"validation_result": "PASS" 或 "FAIL", "reason": "通过或失败的具体原因"}

问题：{input}
原始内容：{originContent}""",

    "answer_generate": """你是一个专业答案生成专家。请根据问题和原始内容，生成高质量的答案。

要求：
1. 答案要准确、完整，基于提供的原始内容
2. 答案应包含必要的推理过程
3. 生成 output（答案文本）和 cot（思维链/推理过程）两个字段
4. 返回JSON格式：{"output": "答案内容", "cot": "推理过程"}
5. 如有公式，使用LaTeX格式表示

问题：{input}
原始内容：{originContent}""",

    "answer_validate": """你是一个答案质量审核专家。请评估以下问答对的答案质量。

评估维度：
1. 答案是否准确回答了问题
2. 答案是否完整，没有遗漏关键信息
3. 推理过程(cot)是否逻辑清晰
4. 答案中是否有明显错误

请返回JSON格式：
{"validation_result": "PASS" 或 "FAIL", "reason": "通过或失败的具体原因"}

问题：{input}
答案：{output}
推理过程：{cot}""",

    "data_evaluate": """你是一个数据质量评分专家。请对以下QA数据进行多维度评分。

评分维度（每个1-5分）：
1. relevance（相关性）：问题与领域/内容的关联程度
2. clarity（清晰度）：问题表述是否清晰易懂
3. reasoning（推理深度）：答案的推理逻辑是否深入
4. terminology（术语准确性）：专业术语使用是否正确
5. score（综合得分）：加权平均分（1-5分，保留1位小数）

返回JSON格式：
{"relevance": N, "clarity": N, "reasoning": N, "terminology": N, "score": N.N}

问题：{input}
答案：{output}
领域：{domain}
难度：{difficulty}""",

    "dataset_assessment": """请为下面这条简答题 QA 样本生成 `Assessment` 字段。

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
9. 严格返回一个 JSON 对象，不要输出任何额外说明，格式如下：{{"Assessment": "评分点1（...）......总分：100分。"}}

【QA样本】
{qa_item_json}

【源文摘录】
{origin_content}

# 修复重写

你上一次生成的 `Assessment` 不合规，请只做修复，不要新增原文中没有的信息。

不合规原因：{repair_reason}

上一版 Assessment：
{invalid_assessment}

请重新输出一个合规版本，并满足以下要求：
1. 必须仍然只依据【QA样本】与【源文摘录】。
2. 必须是单行字符串。
3. 必须包含至少2个评分点，每个评分点都要有分值、满分标准、失分规则。
4. 所有评分点分值之和必须严格等于100，且末尾必须写"总分：100分"。
5. 不能写空话、不能酌情给分、不能引入新知识。
6. 严格返回 JSON 对象：{{"Assessment": "..."}}

【QA样本】
{qa_item_json}

【源文摘录】
{origin_content}""",
}


def add_is_default_column():
    """Add is_default column to prompts table."""
    db = SessionLocal()
    try:
        # Check if column already exists
        result = db.execute(text(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'prompts' "
            "AND COLUMN_NAME = 'is_default'"
        )).fetchone()

        if result:
            print("[migrate] is_default column already exists in prompts table. Skipping.")
            return

        db.execute(text("ALTER TABLE prompts ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT FALSE"))
        db.commit()
        print("[migrate] is_default column added to prompts table successfully.")
    except Exception as e:
        print(f"[migrate] Error adding is_default column: {e}")
        db.rollback()
    finally:
        db.close()


def seed_default_prompts():
    """Create default prompts for all 7 LLM stages if they don't exist."""
    db = SessionLocal()
    try:
        # Get global dashscope LLM config for default prompts
        dashscope_config = db.query(LLMConfig).filter(
            LLMConfig.user_id == None,
            LLMConfig.name.like("%dashscope%"),
        ).first()
        default_llm_config_id = dashscope_config.id if dashscope_config else None
        default_model = dashscope_config.default_model if dashscope_config else "qwen3-max"

        for stage_value, content in DEFAULT_PROMPTS.items():
            stage_enum = StageEnum(stage_value)

            # Check if default prompt already exists for this stage
            existing = db.query(Prompt).filter(
                Prompt.stage == stage_enum,
                Prompt.is_default == True,
            ).first()

            if existing:
                print(f"[migrate] Default prompt for {stage_value} already exists (id={existing.id}). Skipping.")
                continue

            prompt = Prompt(
                user_id=None,  # Global
                stage=stage_enum,
                version=1,
                content=content,
                model=default_model,
                llm_config_id=default_llm_config_id,
                is_default=True,
            )
            db.add(prompt)
            db.commit()
            db.refresh(prompt)
            print(f"[migrate] Created default prompt for {stage_value} (id={prompt.id})")

    except Exception as e:
        print(f"[migrate] Error seeding default prompts: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    print("[migrate] === Adding is_default column and seeding default prompts ===")
    add_is_default_column()
    seed_default_prompts()
    print("[migrate] === Migration complete ===")


if __name__ == "__main__":
    main()