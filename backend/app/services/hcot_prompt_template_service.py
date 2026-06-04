"""File-based prompt template management for H-CoT / CoT pipeline.

需求：CoT/H-CoT 标注流水线提示词模板管理。
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

SYSTEM_TEMPLATE_ID = "hcot_system_default_v1"
SYSTEM_TEMPLATE_NAME = "H-CoT 系统默认模板 v1"
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Prompt layout
# ---------------------------------------------------------------------------

COMMON_PROMPTS = {
    "common.fact_card_gen": {
        "label": "1. 事实卡生成",
        "path": Path("common") / "fact_card_gen.md",
    },
    "common.sanitize": {
        "label": "2. 数值抽象",
        "path": Path("common") / "sanitize.md",
    },
    "common.quality_check": {
        "label": "最终质检",
        "path": Path("common") / "quality_check.md",
    },
}

HCOT_PROMPTS = {
    "hcot.l0_gen": {
        "label": "3. L0 总问题生成",
        "path": Path("hcot") / "l0_gen.md",
    },
    "hcot.l1_decompose": {
        "label": "4. L1 拆解",
        "path": Path("hcot") / "l1_decompose.md",
    },
    "hcot.l2_decompose": {
        "label": "5. L2 拆解",
        "path": Path("hcot") / "l2_decompose.md",
    },
    "hcot.l2_cot": {
        "label": "6. L2 CoT 生成",
        "path": Path("hcot") / "l2_cot.md",
    },
    "hcot.l1_cot": {
        "label": "7. L1 CoT 生成",
        "path": Path("hcot") / "l1_cot.md",
    },
    "hcot.l0_cot": {
        "label": "8. L0 CoT 生成",
        "path": Path("hcot") / "l0_cot.md",
    },
}

COT_PROMPTS = {
    "cot.question_gen": {
        "label": "3. 独立问题生成",
        "path": Path("cot") / "question_gen.md",
    },
    "cot.cot_gen": {
        "label": "4. 独立 CoT 生成",
        "path": Path("cot") / "cot_gen.md",
    },
}

ALL_PROMPTS = {**COMMON_PROMPTS, **HCOT_PROMPTS, **COT_PROMPTS}

VARIABLE_HINTS = {
    "common.fact_card_gen": "content：论文原文分段",
    "common.sanitize": "fact_cards：事实卡 JSON",
    "common.quality_check": "cots：CoT/H-CoT 标注结果",
    "hcot.l0_gen": "fact_cards_sanitized：去数值事实卡 JSON",
    "hcot.l1_decompose": "l0_input：L0 总问题；fact_cards_sanitized：去数值事实卡",
    "hcot.l2_decompose": "l1_input：L1 问题；fact_cards_sanitized：去数值事实卡",
    "hcot.l2_cot": "l2_input：L2 问题；fact_cards_sanitized：去数值事实卡",
    "hcot.l1_cot": "l1_input：L1 问题；l2_cots：L2 完整 CoT",
    "hcot.l0_cot": "l0_input：L0 总问题；l1_cots：L1 完整 CoT；l2_cots：L2 完整 CoT",
    "cot.question_gen": "fact_cards_sanitized：去数值事实卡 JSON",
    "cot.cot_gen": "question_input：独立问题；fact_cards_sanitized：去数值事实卡",
}

# ---------------------------------------------------------------------------
# General rule (prepended to every prompt)
# ---------------------------------------------------------------------------

GENERAL_RULE = """你现在是 CoT/H-CoT 数据标注助手。请严格遵守以下规则：

1.  只基于我提供的论文内容或 JSON 内容生成，不要编造。
2.  问题、答案和思维链中不要出现来源文献的具体实验数值、百分比、单位或数值区间。
3.  可以使用方向性表达，例如"提升""降低""改善""更均匀""更稳定""更有利于传热传质""反应更充分"。
4.  不要写"本文""本研究""该论文""证据表明""证据摘要显示""该事实卡说明"等来源提示语。
5.  不要写"L2-1-1 说明""该 L2 答案支撑 L1""综合这些 L1"等节点提示语。
6.  问题必须独立，不能依赖"上述""这种结构""该方法"等上下文。
7.  答案要完整，不能只写一句结论。
8.  思维链必须写成带步骤编号的连贯文本，每段推理以"第一步：""第二步：""第X步："开头，按因果逻辑顺序展开，不要写成项目符号列表。
9.  输出必须是 JSON，不要输出 Markdown，不要额外解释。
"""

# ---------------------------------------------------------------------------
# Default prompt contents (hardcoded)
# ---------------------------------------------------------------------------

DEFAULT_PROMPT_CONTENTS = {
    "common.fact_card_gen": GENERAL_RULE + """
请根据下面的论文内容生成事实卡。

任务要求：
1.  优先抽取机理规律、结构-性能关系、组分协同关系、界面反应关系、应用边界。
2.  不要生成"某数值是多少"这类事实卡。
3.  每张事实卡只表达一个清楚的科学规律。
4.  如果原文中有具体实验数值，可以放入 raw_numeric_mentions，但不要把具体数值写进 mechanism、performance_implication、claim 和 implication。
5.  不要编造论文中没有的内容。
6.  object 和 performance_implication 用于博士论文 H-CoT；claim 和 implication 用于研究论文 CoT。根据内容自然填写即可。

请输出 JSON，格式如下：
{
  "fact_cards": [
    {
      "fact_id": "F-0001",
      "topic": "主题",
      "object": "研究对象",
      "claim": "核心事实或规律",
      "mechanism": "机理规律",
      "performance_implication": "性能意义",
      "implication": "意义或应用边界",
      "evidence_ids": ["E-0001"],
      "raw_numeric_mentions": []
    }
  ]
}

下面是论文内容：
{content}
""",
    "common.sanitize": GENERAL_RULE + """
请将下面的事实卡 JSON 改写为去数值版本。

要求：
1.  复制所有字段，但 mechanism、performance_implication、claim 和 implication 字段要改写。
2.  改写后的字段名加 `_sanitized` 后缀。
3.  改写时，将所有具体数值、比例、单位替换为方向性、规律性描述。
4.  新增 `numeric_dependency` 字段，根据情况填写 `none`, `abstractable`, `numeric_dependency_required`。
5.  object 和 performance_implication_sanitized 用于博士论文 H-CoT；claim_sanitized 和 implication_sanitized 用于研究论文 CoT。根据内容自然填写即可。

请输出 JSON，格式如下：
{
  "fact_cards_sanitized": [
    {
      "fact_id": "F-0001",
      "topic": "主题",
      "object": "研究对象",
      "claim": "核心事实或规律",
      "claim_sanitized": "去数值后的核心事实或规律",
      "mechanism_sanitized": "去数值后的机理规律",
      "performance_implication_sanitized": "去数值后的性能意义",
      "implication_sanitized": "去数值后的意义或应用边界",
      "numeric_dependency": "abstractable",
      "evidence_ids": ["E-0001"]
    }
  ]
}

下面是事实卡 JSON：
{fact_cards}
""",
    "hcot.l0_gen": GENERAL_RULE + """
请根据下面的去数值事实卡，为博士论文 H-CoT 构建生成 L0 总问题候选。

L0 总问题要求：
1.  必须是独立问题，不能出现"本文""本研究""该论文""上述"等表达。
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
    "hcot.l1_decompose": GENERAL_RULE + """
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
    "hcot.l2_decompose": GENERAL_RULE + """
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
    "hcot.l2_cot": GENERAL_RULE + """
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
    "hcot.l1_cot": GENERAL_RULE + """
请基于 L1 问题及其对应的 L2 完整 CoT，为每个 L1 问题生成独立的 L1 完整 CoT 训练样本。

核心要求（非常重要，违反即不合格）：
1.  必须为每个 L1 问题都生成一条独立的 CoT 样本，不能只生成一个。
2.  L1 的 output 绝对不能直接复制 L2 答案！必须将多个 L2 的机制重新组织、自然融合成一段完整的解释。正确做法是：先回答 L1 的核心结论，然后按因果逻辑依次展开每个 L2 的关键机制，最后总结。
3.  L1 的 chainofThought 同样不能复制 L2 的思维链文本。必须把多个 L2 的推理规律提炼后写成一段连贯的更高层次推理，而不是把 L2 的 chainofThought 拼接在一起。
4.  L1 的 output 和 chainofThought 应该比任何一个单独的 L2 都更全面、更有深度。
5.  错误示范："L2-1-1 说明核壳结构能提高反应效率，L2-1-2 说明黏结剂参与放热，因此三组分微单元性能更好。"——这是拼接，不是融合。另外错误示范："核壳结构可以提高反应效率，因此三组分微单元性能更好。"——这太短，没有展开机制。
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
    "hcot.l0_cot": GENERAL_RULE + """
请基于 L0 问题、所有 L1 完整 CoT 和必要 L2 推理规律，生成 L0 完整 CoT 训练样本。

要求：
1.  L0 的 output 不能只是短总结，必须自然包含各 L1 的关键答案内容，并适当吸收重要 L2 机制。
2.  L0 的 output 应体现关键 L2 机制，但不要写节点编号。
3.  L0 的 chainofThought 必须用"第一步：""第二步："等编号自然纳入 L1 的推理规律和关键 L2 机制。
4.  不要写"L1-1 说明""综合这些 L1 答案""该 L2 支撑"等节点提示语。

请输出 JSON：
{
  "l0_cot_node": {
    "id": "L0-1",
    "level": "L0",
    "input": "独立 L0 总问题",
    "output": "自然包含 L1 和关键 L2 内容的完整总答案",
    "chainofThought": "带步骤编号的思维链（第一步：…第二步：…），自然纳入 L1 推理规律和关键 L2 机制"
  }
}

下面是 L0、L1 完整 CoT 和 L2 完整 CoT：
L0: {l0_input}
L1_COTs: {l1_cots}
L2_COTs: {l2_cots}
""",
    "cot.question_gen": GENERAL_RULE + """
请根据下面去数值事实卡生成研究论文独立 CoT 问题。

要求：
1.  每个问题都必须独立，脱离其他问题也能理解。
2.  问题以机理分析、方法作用、结构-性能关系、结果解释、应用边界为主。
3.  不要生成数值问答、图表核查题、章节概括题。
4.  每个问题都要标明对应 source_fact_ids 和为什么这些事实卡足以回答该问题。

请输出 JSON：
{
  "questions": [
    {
      "question_id": "Q-0001",
      "input": "独立问题",
      "question_type": "mechanism_analysis",
      "source_fact_ids": ["F-0001"],
      "why_answerable": "为什么这些事实卡足以回答该问题"
    }
  ]
}

下面是去数值事实卡 JSON：
{fact_cards_sanitized}
""",
    "cot.cot_gen": GENERAL_RULE + """
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
    "common.quality_check": """**角色设定：**你是一位严格的数据质量评估专家，只基于我提供的论文内容或 JSON 内容进行质检。你需要基于给定的检查标准，对每条数据进行多维度的审查，并给出"合格/存在缺陷/严重错误"的综合判定。

**待检查内容：**每一个包含 `input`、`output`、`chainofThought`的完整数据。

**检查标准与三档判定依据：**

1. **input 是否是独立问题。**
  - 合格：问题语义完整，无需依赖外部上下文即可理解。
  - 存在缺陷：问题存在轻微指代不明，但结合常识仍可推断。
  - 严重错误：问题严重依赖外部上下文、缺失主语或关键信息，无法独立理解。

2. **output 是否完整回答问题，是否包含原因、过程和意义。**
  - 合格：直接回应提问，且包含必要的解释（原因）、推导（过程）和总结（意义）。
  - 存在缺陷：回答了问题，但缺失原因、过程或意义中的某一项，导致回答略显单薄。
  - 严重错误：未正面回答问题，或回答极度简略（如仅"是/否"而无任何阐述）。

3. **chainofThought是否为连贯文本。**
  - 合格：全文为流畅的自然段落,每段推理以"第一步：""第二步：""第X步："开头，按因果逻辑顺序展开。
  - 存在缺陷：局部使用了类似列表的句式，但整体仍是段落形式。
  - 严重错误：大部分或全部为列表、项目符号格式，非连贯文本。

4. **chainofThought是否只写客观事实规律和因果推理。**
  - 合格：内容严格限定于客观推理，无主观评价、猜测、感慨或与任务无关的评论。
  - 存在缺陷：夹杂少量主观表达（如"我认为""显然很合理"），但主干仍是客观推理。
  - 严重错误：包含大量主观议论、个人感想、抒情或与推理无关的叙事。

5. **是否出现来源提示语，如"本文""本研究""该论文""证据表明"。**
  - 合格：无任何来源提示语。
  - 存在缺陷：出现1处来源提示语。
  - 严重错误：出现多处来源提示语，或使用来源提示语作为论据支撑。

6. **是否出现节点提示语，如"L2-1-1 说明""该 L2 支撑 L1"。**
  - 合格：无任何节点提示语。
  - 存在缺陷：出现1处节点提示语。
  - 严重错误：出现多处节点提示语，明显破坏了文本的自然连贯性。

7. **是否出现具体实验数值、百分比、单位或数值区间。**
  - 合格：未出现任何具体数值、百分比、单位。
  - 存在缺陷：出现少量数值，但不影响整体抽象推理的纯粹性。
  - 严重错误：大量使用具体数值、百分比或单位，将抽象推理转变为数据罗列。

8. **是否存在编造或超出事实卡的内容。**
  - 合格：所有信息均基于给定事实，无任何凭空编造或外推。
  - 存在缺陷：有轻微的信息延伸，但尚在合理推论范围内。
  - 严重错误：编造事实、数据、人名、文献，或做出给定信息无法支撑的断言。

9. **如果是 H-CoT，检查父节点答案是否自然包含子节点关键内容。**
  - 合格：父节点答案流畅且自然地涵盖了子节点的核心结论，无拼凑痕迹。
  - 存在缺陷：父节点包含了子节点内容，但衔接生硬或部分关键点遗漏。
  - 严重错误：父节点与子节点内容脱节、矛盾，或父节点未体现子节点的核心推理。

**综合判定标准（三档）：**
- **合格**：所有检查项均达到"合格"，无严重错误或缺陷。
- **存在缺陷**：有1项或多项被判定为"存在缺陷"，且无任何项被判定为"严重错误"。
- **严重错误**：有任意1项被判定为"严重错误"。

**输出格式要求：**请必须用JSON格式输出，包含整体评级和每一项问题的检查详情。

```json
{
  "overall_quality": "合格/存在缺陷/严重错误",
  "issues": [
    {
      "check_item": "检查项编号（1-9）",
      "severity": "存在缺陷/严重错误",
      "location": "具体问题出现的样本或节点编号",
      "description": "问题的清晰描述",
      "suggestion": "具体的修改建议"
    }
  ]
}
```

**重要提示：**
- 若所有项均合格，`issues` 数组为空。
- 请逐条核对，先给出每项的评级，再综合判定。不要遗漏任何检查项。
- 保持判断的严格性与一致性，尤其关注第1、2、8条的严重错误将直接导致整条数据不可用。

下面是待检查内容：
{cots}
""",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class PromptTemplateError(ValueError):
    """Raised when prompt template operations are invalid."""


def _find_project_root() -> Path:
    marker = Path("docs") / "background" / "3类COT提示词"
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
TEMPLATE_STORAGE_ROOT = PROJECT_ROOT / "storage" / "hcot_prompt_templates"
RUN_STORAGE_ROOT = PROJECT_ROOT / "storage" / "hcot_runs"


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
    if prompt_key not in ALL_PROMPTS:
        raise PromptTemplateError(f"非法 prompt_key: {prompt_key}")
    return ALL_PROMPTS[prompt_key]["path"]


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


# ---------------------------------------------------------------------------
# System template
# ---------------------------------------------------------------------------


def ensure_system_template() -> Dict[str, Any]:
    """Create or repair the read-only system template from DEFAULT_PROMPT_CONTENTS."""
    template_dir = _system_template_dir()
    prompts_dir = _template_prompts_dir(template_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    for prompt_key, content in DEFAULT_PROMPT_CONTENTS.items():
        rel_path = ALL_PROMPTS[prompt_key]["path"]
        atomic_write_text(prompts_dir / rel_path, content)

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


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Template enumeration & decoration
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# List / detail
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Prompt tree
# ---------------------------------------------------------------------------


def build_prompt_tree() -> List[Dict[str, Any]]:
    """Return tree organized by common / hcot / cot groups."""
    common_children = [
        {
            "id": key,
            "label": info["label"],
            "prompt_key": key,
            "variable_hint": VARIABLE_HINTS.get(key, ""),
            "is_prompt": True,
        }
        for key, info in COMMON_PROMPTS.items()
    ]
    hcot_children = [
        {
            "id": key,
            "label": info["label"],
            "prompt_key": key,
            "variable_hint": VARIABLE_HINTS.get(key, ""),
            "is_prompt": True,
        }
        for key, info in HCOT_PROMPTS.items()
    ]
    cot_children = [
        {
            "id": key,
            "label": info["label"],
            "prompt_key": key,
            "variable_hint": VARIABLE_HINTS.get(key, ""),
            "is_prompt": True,
        }
        for key, info in COT_PROMPTS.items()
    ]
    return [
        {"id": "common", "label": "通用步骤 (CoT/H-CoT)", "is_prompt": False, "children": common_children},
        {"id": "hcot", "label": "H-CoT 专属步骤", "is_prompt": False, "children": hcot_children},
        {"id": "cot", "label": "CoT 专属步骤", "is_prompt": False, "children": cot_children},
    ]


def get_template_detail(template_id: str, user_id: int) -> Dict[str, Any]:
    template_dir = require_template_dir(template_id, user_id)
    manifest = _decorate_manifest(_load_manifest(template_dir), user_id)
    tree = build_prompt_tree()
    # 动态计算叶子节点数（实际提示词数量）
    actual_count = sum(
        1 for group in tree
        for child in group.get("children", [])
        if child.get("is_prompt")
    )
    return {
        "manifest": manifest,
        "tree": tree,
        "prompt_count": actual_count,
    }


# ---------------------------------------------------------------------------
# Read / write / restore individual prompts
# ---------------------------------------------------------------------------


def get_prompt_item(template_id: str, user_id: int, prompt_key: str) -> Dict[str, Any]:
    template_dir = require_template_dir(template_id, user_id)
    manifest = _decorate_manifest(_load_manifest(template_dir), user_id)
    rel_path = _prompt_relative_path(prompt_key)
    content = read_text(_template_prompts_dir(template_dir) / rel_path)
    default_content = read_text(_template_prompts_dir(_system_template_dir()) / rel_path)
    return {
        "prompt_key": prompt_key,
        "content": content,
        "default_content": default_content,
        "relative_path": rel_path.as_posix(),
        "variable_hint": VARIABLE_HINTS.get(prompt_key, ""),
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
    manifest = _load_manifest(template_dir)
    if manifest.get("is_readonly") or manifest.get("owner_id") != user_id:
        raise PromptTemplateError("只能恢复自己的用户模板")
    rel_path = _prompt_relative_path(prompt_key)
    default_content = read_text(_template_prompts_dir(_system_template_dir()) / rel_path)
    atomic_write_text(_template_prompts_dir(template_dir) / rel_path, default_content)
    _save_manifest(template_dir, manifest)
    return get_prompt_item(template_id, user_id, prompt_key)


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Run integration
# ---------------------------------------------------------------------------


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
    snapshot_dir = run_dir / "prompts"
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    shutil.copytree(_template_prompts_dir(template_dir), snapshot_dir)
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
        "prompt_count": len(ALL_PROMPTS),  # snapshot 包含全部模板文件
    }
    atomic_write_json(snapshot_dir / "manifest.json", snapshot_manifest)
    return snapshot_manifest


def read_prompt_from_snapshot(prompt_snapshot_dir: Path, prompt_key: str) -> str:
    if not prompt_snapshot_dir.exists() or not (prompt_snapshot_dir / "manifest.json").exists():
        raise PromptTemplateError("run 提示词快照不存在")
    rel_path = _prompt_relative_path(prompt_key)
    return read_text(prompt_snapshot_dir / rel_path)