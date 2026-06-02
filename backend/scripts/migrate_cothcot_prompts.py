"""Add default prompts for the CoT/H-CoT pipeline.

Run with: python -m scripts.migrate_cothcot_prompts
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models.models import Prompt, StageEnum, LLMConfig

# General rule to prepend to every prompt
GENERAL_RULE = """你现在是 CoT/H-CoT 数据标注助手。请严格遵守以下规则：

1.  只基于我提供的论文内容或 JSON 内容生成，不要编造。
2.  问题、答案和思维链中不要出现来源文献的具体实验数值、百分比、单位或数值区间。
3.  可以使用方向性表达，例如“提升”“降低”“改善”“更均匀”“更稳定”“更有利于传热传质”“反应更充分”。
4.  不要写“本文”“本研究”“该论文”“证据表明”“证据摘要显示”“该事实卡说明”等来源提示语。
5.  不要写“L2-1-1 说明”“该 L2 答案支撑 L1”“综合这些 L1”等节点提示语。
6.  问题必须独立，不能依赖“上述”“这种结构”“该方法”等上下文。
7.  答案要完整，不能只写一句结论。
8.  思维链必须写成带步骤编号的连贯文本，每段推理以"第一步：""第二步：""第X步："开头，按因果逻辑顺序展开，不要写成项目符号列表。
9.  输出必须是 JSON，不要输出 Markdown，不要额外解释。
"""

# Prompts for the pipeline
DEFAULT_PROMPTS = {
    # --- Common Steps ---
    "[CoT/H-CoT] 1. 事实卡生成": GENERAL_RULE + """
请根据下面的论文内容生成事实卡。

任务要求：
1.  优先抽取机理规律、结构-性能关系、组分协同关系、界面反应关系、应用边界。
2.  不要生成“某数值是多少”这类事实卡。
3.  每张事实卡只表达一个清楚的科学规律。
4.  如果原文中有具体实验数值，可以放入 raw_numeric_mentions，但不要把具体数值写进 mechanism 和 performance_implication。
5.  不要编造论文中没有的内容。

请输出 JSON，格式如下：
{
  "fact_cards": [
    {
      "fact_id": "F-0001",
      "topic": "主题",
      "object": "研究对象",
      "mechanism": "机理规律",
      "performance_implication": "性能意义",
      "evidence_ids": ["E-0001"],
      "raw_numeric_mentions": []
    }
  ]
}

下面是论文内容：
{content}
""",
    "[CoT/H-CoT] 2. 数值抽象": GENERAL_RULE + """
请将下面的事实卡 JSON 改写为去数值版本。

要求：
1.  复制所有字段，但 mechanism 和 performance_implication 字段要改写。
2.  改写后的字段名加 `_sanitized` 后缀。
3.  改写时，将所有具体数值、比例、单位替换为方向性、规律性描述。
4.  新增 `numeric_dependency` 字段，根据情况填写 `none`, `abstractable`, `numeric_dependency_required`。

请输出 JSON，格式如下：
{
  "fact_cards_sanitized": [
    {
      "fact_id": "F-0001",
      "topic": "主题",
      "object": "研究对象",
      "mechanism_sanitized": "去数值后的机理规律",
      "performance_implication_sanitized": "去数值后的性能意义",
      "numeric_dependency": "abstractable",
      "evidence_ids": ["E-0001"]
    }
  ]
}

下面是事实卡 JSON：
{fact_cards}
""",
    # --- H-CoT Steps ---
    "[H-CoT] 3. L0 总问题生成": GENERAL_RULE + """
请根据下面的去数值事实卡，为博士论文 H-CoT 构建生成 L0 总问题候选。

L0 总问题要求：
1.  必须是独立问题，不能出现“本文”“本研究”“该论文”“上述”等表达。
2.  必须是机理分析型问题，不能是数值问答。
3.  必须能自然拆成至少 3 个 L1 子问题。
4.  不能由单一事实卡直接回答，必须综合多个事实卡。

请输出 JSON：
{
  "l0_candidate": {
    "input": "独立、去语境化、机理分析型总问题",
    "why_decomposable": "为什么必须拆成多个 L1 才能回答",
    "expected_l1_aspects": ["方面1", "方面2", "方面3"],
    "source_fact_ids": ["F-0001", "F-0002"]
  }
}

下面是去数值事实卡 JSON：
{fact_cards_sanitized}
""",
    "[H-CoT] 4. L1 拆解": GENERAL_RULE + """
请将下面选定的 L0 总问题拆解为 L1 子问题。

要求：
1.  每个 L1 都必须是独立问题，脱离 L0 后也能理解。
2.  每个 L1 都要支撑 L0 的一个必要方面。
3.  删除任意一个 L1 后，L0 的答案应明显不完整。
4.  L1 不能是章节概括题，也不是数值事实题。
5.  每个 L1 后续必须能继续拆成 L2 独立问题。

请输出 JSON：
{
  "l1_nodes": [
    {
      "id": "L1-1",
      "level": "L1",
      "input": "独立 L1 问题",
      "relation_to_parent": "supports",
      "necessity": "该 L1 为什么是回答 L0 的必要部分",
      "source_fact_ids": ["F-0001"]
    }
  ]
}

下面是 L0 和去数值事实卡：
L0: {l0_input}
Facts: {fact_cards_sanitized}
""",
    "[H-CoT] 5. L2 拆解": GENERAL_RULE + """
请将下面每个 L1 问题拆解为 L2 独立问题。

要求：
1.  每个 L2 脱离父问题后仍能理解。
2.  每个 L2 都是更细粒度的机理问题，不是证据核查题，也不是数值问答。
3.  每个 L2 都要支撑对应 L1 的一个必要判断。

请输出 JSON：
{
  "l2_nodes": [
    {
      "id": "L2-1-1",
      "level": "L2",
      "parent_id": "L1-1",
      "input": "独立 L2 问题",
      "relation_to_parent": "supports",
      "necessity": "该 L2 如何贡献父问题的必要判断",
      "source_fact_ids": ["F-0001"]
    }
  ]
}

下面是 L1 问题和去数值事实卡：
L1: {l1_input}
Facts: {fact_cards_sanitized}
""",
    "[H-CoT] 6. L2 CoT 生成": GENERAL_RULE + """
请为下面的每个 L2 独立问题都生成一条完整 CoT 训练样本。必须为每个 L2 问题都生成，不能遗漏。

要求：
1.  必须为每个 L2 问题都生成一条独立的样本，输出为数组。
2.  output 要完整，包含结论、原因、过程和意义。
3.  chainofThought 写成带步骤编号的连贯文本，每段推理以"第一步：""第二步：""第X步："开头，按因果逻辑顺序展开。

请输出 JSON：
{
  "l2_cot_nodes": [
    {
      "id": "L2-1-1",
      "level": "L2",
      "input": "独立问题",
      "output": "完整答案",
      "chainofThought": "带步骤编号的连贯文本思维链（第一步：…第二步：…）",
      "supports": "L1-1",
      "metadata": {
        "source_fact_ids": ["F-0001"],
        "numeric_policy": "sanitized"
      }
    },
    {
      "id": "L2-1-2",
      "level": "L2",
      "input": "独立问题",
      "output": "完整答案",
      "chainofThought": "带步骤编号的连贯文本思维链（第一步：…第二步：…）",
      "supports": "L1-1",
      "metadata": {
        "source_fact_ids": ["F-0001"],
        "numeric_policy": "sanitized"
      }
    }
  ]
}

下面是 L2 问题和去数值事实卡：
L2: {l2_input}
Facts: {fact_cards_sanitized}
""",
    "[H-CoT] 7. L1 CoT 生成": GENERAL_RULE + """
请基于 L1 问题及其对应的 L2 完整 CoT，为每个 L1 问题生成独立的 L1 完整 CoT 训练样本。

核心要求（非常重要）：
1.  必须为每个 L1 问题都生成一条独立的 CoT 样本，不能只生成一个。
2.  L1 的 output 绝对不能直接复制 L2 答案！必须将多个 L2 的机制重新组织、自然融合成一段完整的解释。正确做法是：先回答 L1 的核心结论，然后按因果逻辑依次展开每个 L2 的关键机制，最后总结。
3.  L1 的 chainofThought 同样不能复制 L2 的思维链文本。必须把多个 L2 的推理规律提炼后写成一段连贯的更高层次推理。
4.  L1 的 output 和 chainofThought 应该比任何一个单独的 L2 都更全面、更有深度。
5.  错误示范："L2-1-1 说明核壳结构能提高反应效率，L2-1-2 说明黏结剂参与放热，因此三组分微单元性能更好。"——这是拼接，不是融合。
6.  正确示范："核壳型三组分微单元能够提高反应效率，是因为它同时优化了界面接触、黏结剂协同和燃氧匹配。核壳结构使氧化剂与金属燃料在连续界面附近均匀接触，减少无序团聚并缩短传热传质距离；含能黏结剂在适量时参与放热并稳定结构，但过量时会阻碍反应通道；金属燃料比例也需要与氧化剂供氧能力匹配，避免反应不完全。"

请输出 JSON：
{
  "l1_cot_nodes": [
    {
      "id": "L1-1",
      "level": "L1",
      "input": "独立 L1 问题",
      "output": "融合多个 L2 机制的完整答案（不是拼接）",
      "chainofThought": "提炼并融合多个 L2 推理规律的带步骤编号思维链（第一步：…第二步：…，不是复制）",
      "depends_on": ["L2-1-1", "L2-1-2"],
      "supports": "L0-1"
    },
    {
      "id": "L1-2",
      "level": "L1",
      "input": "独立 L1 问题",
      "output": "融合对应 L2 机制的完整答案",
      "chainofThought": "提炼对应 L2 推理规律的带步骤编号思维链（第一步：…第二步：…）",
      "depends_on": ["L2-2-1", "L2-2-2"],
      "supports": "L0-1"
    }
  ]
}

下面是 L1 问题和 L2 完整 CoT：
L1: {l1_input}
L2_COTs: {l2_cots}
""",
    "[H-CoT] 8. L0 CoT 生成": GENERAL_RULE + """
请基于 L0 问题、所有 L1 完整 CoT，生成 L0 完整 CoT 训练样本。

要求：
1.  L0 的 output 不能只是短总结，必须自然包含各 L1 的关键答案内容。
2.  L0 的 chainofThought 必须用"第一步：""第二步："等编号自然纳入 L1 的推理规律。

请输出 JSON：
{
  "l0_cot_node": {
    "id": "L0-1",
    "level": "L0",
    "input": "独立 L0 总问题",
    "output": "自然包含 L1 内容的完整总答案",
    "chainofThought": "带步骤编号的思维链（第一步：…第二步：…），自然纳入 L1 推理规律"
  }
}

下面是 L0、L1 完整 CoT：
L0: {l0_input}
L1_COTs: {l1_cots}
""",
    # --- CoT Steps ---
    "[CoT] 3. 独立问题生成": GENERAL_RULE + """
请根据下面去数值事实卡生成研究论文独立 CoT 问题。

要求：
1.  每个问题都必须独立，脱离其他问题也能理解。
2.  问题以机理分析、方法作用、结构-性能关系、结果解释、应用边界为主。
3.  不要生成数值问答、图表核查题、章节概括题。

请输出 JSON：
{
  "questions": [
    {
      "question_id": "Q-0001",
      "input": "独立问题",
      "question_type": "mechanism_analysis",
      "source_fact_ids": ["F-0001"]
    }
  ]
}

下面是去数值事实卡 JSON：
{fact_cards_sanitized}
""",
    "[CoT] 4. 独立 CoT 生成": GENERAL_RULE + """
请根据下面的独立问题和去数值事实卡，生成研究论文独立 CoT 训练样本。

要求：
1.  output 要完整，包含结论、原因、过程和意义。
2.  chainofThought 必须写成带步骤编号的连贯文本，每段推理以"第一步：""第二步：""第X步："开头，按因果逻辑顺序展开。

请输出 JSON：
{
  "sample": {
    "sample_id": "RP_COT_0001",
    "input": "独立问题",
    "output": "完整答案",
    "chainofThought": "连贯文本形式的思维链"
  }
}

下面是独立问题和去数值事实卡：
Question: {question_input}
Facts: {fact_cards_sanitized}
""",
    # --- Final Check ---
    "[CoT/H-CoT] 最终质检": GENERAL_RULE + """
请检查下面的 CoT/H-CoT 标注结果是否合格。

检查标准：
1.  input 是否是独立问题。
2.  output 是否完整回答问题，是否包含原因、过程和意义。
3.  chainofThought 是否为带步骤编号（第一步、第二步、…）的连贯文本，而不是无编号的纯文本或列表。
4.  是否出现来源提示语，如“本文”“本研究”“该论文”“证据表明”。
5.  是否出现节点提示语，如“L2-1-1 说明”“该 L2 支撑 L1”。
6.  是否出现具体实验数值、百分比、单位或数值区间。
7.  如果是 H-CoT，检查父节点答案是否自然包含子节点关键内容。

请输出 JSON：
{
  "passed": true,
  "issues": [
    {
      "location": "样本或节点编号",
      "issue": "问题描述",
      "suggestion": "修改建议"
    }
  ]
}

下面是待检查内容：
{cots}
"""
}

def seed_cothcot_prompts():
    """Create or update default prompts for the CoT/H-CoT pipeline."""
    db = SessionLocal()
    try:
        # Get a global LLM config to associate with the prompts
        default_llm_config = db.query(LLMConfig).filter(LLMConfig.user_id == None).first()
        default_llm_config_id = default_llm_config.id if default_llm_config else None
        default_model = default_llm_config.default_model if default_llm_config else "qwen-max"

        stage_enum = StageEnum.COT_HCOT_PIPELINE

        for name, content in DEFAULT_PROMPTS.items():
            # Check if a default prompt with this name already exists for the stage
            existing = db.query(Prompt).filter(
                Prompt.stage == stage_enum,
                Prompt.name == name,
                Prompt.is_default == True,
            ).first()

            if existing:
                # Update the content of the existing prompt
                existing.content = content
                db.commit()
                db.refresh(existing)
                print(f"[migrate] Updated default prompt '{name}' (id={existing.id})")
                continue

            # Find the latest version for this stage to increment
            latest_version_prompt = db.query(Prompt).filter(
                Prompt.stage == stage_enum,
                Prompt.is_default == True
            ).order_by(Prompt.version.desc()).first()
            
            version = (latest_version_prompt.version + 1) if latest_version_prompt else 1

            prompt = Prompt(
                user_id=None,  # Global
                stage=stage_enum,
                version=version,
                name=name,
                content=content,
                model=default_model,
                llm_config_id=default_llm_config_id,
                is_default=True,
            )
            db.add(prompt)
            db.commit()
            db.refresh(prompt)
            print(f"[migrate] Created default prompt '{name}' for stage '{stage_enum.value}' (id={prompt.id})")

    except Exception as e:
        print(f"[migrate] Error seeding CoT/H-CoT prompts: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    print("[migrate] === Seeding CoT/H-CoT default prompts === ")
    seed_cothcot_prompts()
    print("[migrate] === Migration complete === ")

if __name__ == "__main__":
    main()
