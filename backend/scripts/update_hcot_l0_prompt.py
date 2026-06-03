"""Update the default H-CoT L0 question generation prompt.

Run with: python -m scripts.update_hcot_l0_prompt
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models.models import Prompt, StageEnum, LLMConfig

PROMPT_NAME = "[H-CoT] 3. L0 总问题生成"

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

NEW_CONTENT = GENERAL_RULE + """
请根据下面的去数值事实卡，为博士论文 H-CoT 构建生成 L0 总问题候选数组。

你必须先识别事实卡中是否存在多条相对独立的机制主线，然后再生成 L0 总问题。
机制主线可以包括但不限于：
1. 材料/体系构建机制
2. 结构调控机制
3. 性能提升机制
4. 反应、催化、吸附、传输、降解、电化学等作用机制
5. 稳定性、失效、耐久性或适用边界机制
6. 方法、模型、工艺或参数优化机制

L0 总问题生成规则：
1. L0 是一个总问题，通常对应整篇博士论文的核心科学问题。
2. 必须是独立问题，不能出现”本文””本研究””该论文””上述”等表达。
3. 必须是机理分析型问题，不能是数值问答。
4. 必须能自然拆成至少 3 个 L1 子问题。
5. 不能由单一事实卡直接回答，必须综合多个事实卡。
6. 不要出现来源文献具体实验数值。

ID 规则（非常重要）：
1. 只能引用输入事实卡中已经存在的 fact_id。合并后的事实卡 fact_id 通常形如 FC-0001、FC-0002。
2. 不允许杜撰不存在的 fact_id。
3. source_fact_ids 必须只包含支撑该 L0 的事实卡 fact_id，且至少包含 2 个。
4. expected_l1_aspects 必须至少 3 个，且能覆盖该 L0 的必要拆解方向。

请输出 JSON，格式如下：
{
  “source_id”: “论文名称或编号”,
  “l0_candidate”: {
    “candidate_id”: “L0-001”,
    “input”: “独立、去语境化、机理分析型总问题”,
    “why_decomposable”: “为什么必须拆成多个 L1 才能回答”,
    “expected_l1_aspects”: [“方面1”, “方面2”, “方面3”],
    “source_fact_ids”: [“FC-0001”, “FC-0002”]
  }
}

注意：
- 只生成 1 个 L0 总问题，对应整篇论文的核心科学问题。
- 如果模型输出 l0_candidates 数组，只取第一个作为总问题。
- source_fact_ids 中的 FC-XXXX 编号必须与输入事实卡中的 fact_id 完全一致，不能杜撰。

下面是去数值事实卡 JSON：
{fact_cards_sanitized}
"""


def update_prompt():
    db = SessionLocal()
    try:
        prompt = db.query(Prompt).filter(
            Prompt.stage == StageEnum.COT_HCOT_PIPELINE,
            Prompt.name == PROMPT_NAME,
            Prompt.is_default == True,
        ).order_by(Prompt.version.desc()).first()

        if prompt:
            prompt.content = NEW_CONTENT
            prompt.version = (prompt.version or 1) + 1
            db.commit()
            db.refresh(prompt)
            print(f"[update] Updated default prompt '{PROMPT_NAME}' (id={prompt.id}, version={prompt.version})")
            return

        default_llm_config = db.query(LLMConfig).filter(LLMConfig.user_id == None).first()
        default_llm_config_id = default_llm_config.id if default_llm_config else None
        default_model = default_llm_config.default_model if default_llm_config else "qwen-max"

        prompt = Prompt(
            user_id=None,
            stage=StageEnum.COT_HCOT_PIPELINE,
            version=1,
            name=PROMPT_NAME,
            content=NEW_CONTENT,
            model=default_model,
            llm_config_id=default_llm_config_id,
            is_default=True,
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        print(f"[update] Created default prompt '{PROMPT_NAME}' (id={prompt.id}, version={prompt.version})")
    except Exception as exc:
        db.rollback()
        print(f"[update] Failed to update prompt: {exc}")
        raise
    finally:
        db.close()


def main():
    print("[update] === Updating H-CoT L0 prompt ===")
    update_prompt()
    print("[update] === Complete ===")


if __name__ == "__main__":
    main()
