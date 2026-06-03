"""CoT Quality Check service for QA Studio.

对带思维链的 JSON 数据进行四维度深度质量评估。
逐条调用 LLM，解析返回的 overall_quality 评级，按评级分桶输出三个文件。

本模块提供：
- COT_QUALITY_CHECK_SYSTEM_PROMPT: 内嵌的 CoT 质检提示词常量
- flatten_nested_cot_items(): 将嵌套的 CoT 数据（如 l0_cot_node/l1_cot_node/l2_cot_node）展开到顶层
- _build_user_prompt(): 构造单条记录的 user prompt
- _resolve_cot_field(): 字段别名兼容（chain_of_thought / chainofThought / cot）
- _PASS_RATINGS / _FAIL_RATINGS: 评级分桶常量

实际的逐条 LLM 调用和进度管理由路由器中的后台任务负责。
"""

import json
import logging

logger = logging.getLogger("qa_studio.cot_quality_check")


# ---------------------------------------------------------------------------
# Flatten nested CoT items (e.g. l0_cot_node → top-level fields)
# ---------------------------------------------------------------------------

# 已知的嵌套包装键名（标注流水线产物的常见结构）
_NESTED_WRAPPER_KEYS = [
    "l0_cot_node", "l1_cot_node", "l2_cot_node",
    "cot_node", "hcot_node",
]


def flatten_nested_cot_items(raw_items: list) -> list:
    """将嵌套结构的 CoT 数据展开为扁平结构，使 input/output/chainofThought 等字段位于顶层。

    标注流水线产物常见格式：
        [{"l0_cot_node": {"id": "L0-1", "input": "...", "output": "...", "chainofThought": "..."}}]

    展开后变为：
        [{"id": "L0-1", "input": "...", "output": "...", "chainofThought": "...", "_wrapper_key": "l0_cot_node"}]

    如果数据已经是扁平结构则不做任何改动。

    Args:
        raw_items: 从 JSON 文件读取的原始数据列表。

    Returns:
        展开后的扁平数据列表。
    """
    flattened = []
    for item in raw_items:
        if not isinstance(item, dict):
            flattened.append(item)
            continue

        # 检查是否有已知的嵌套包装键
        wrapper_key = None
        for key in _NESTED_WRAPPER_KEYS:
            if key in item and isinstance(item[key], dict):
                wrapper_key = key
                break

        if wrapper_key is None:
            # 已经是扁平结构，或未知格式 → 不做改动
            flattened.append(item)
            continue

        # 将嵌套内容展开到顶层，保留包装键名作为追溯标记
        inner = item[wrapper_key]
        flat = dict(inner)  # 复制内部字段到顶层
        flat["_wrapper_key"] = wrapper_key  # 记录原始包装键名
        # 保留外层的其他字段（如没有嵌套到内层的元数据）
        for k, v in item.items():
            if k != wrapper_key and k not in flat:
                flat[k] = v
        flattened.append(flat)

    logger.info(
        "Flattened %d items: %d had nested wrappers, %d were already flat",
        len(raw_items),
        sum(1 for f in flattened if isinstance(f, dict) and "_wrapper_key" in f),
        sum(1 for f in flattened if isinstance(f, dict) and "_wrapper_key" not in f),
    )
    return flattened


# ---------------------------------------------------------------------------
# System prompt (embedded from CoT质检提示词.md)
# ---------------------------------------------------------------------------

COT_QUALITY_CHECK_SYSTEM_PROMPT = """**角色设定：**
你是一位精通科学方法论、逻辑学和专业领域知识（特别是物理化学、材料科学）的高级数据评估专家。你的任务是对给定的COT（思维链）数据进行严格、多维度的质量评估。

**评估对象：**
你将收到一条完整的COT数据，包含三个部分：
- **`input`**：原始提问或问题陈述。
- **`chain_of_thought`**：为解答问题而生成的思维链步骤。
- **`output`**：基于思维链生成的最终回答。

**评估框架与标准：**
请严格遵循以下四个核心维度进行评估，并在每个维度下给出具体评级（例如：优秀/良好/存在缺陷/严重错误）及详细理由。

#### 维度一：问题的科学性与逻辑自洽性
*此维度旨在识别问题本身的预设是否存在偏差，这是所有后续推理的基石。*
1.  **问题前提是否成立？** 检查问题所基于的假设、给定的数据或情境是否真实、准确、无内在矛盾。
2.  **变量设定是否合理？** 若问题要求归纳构效关系或因果关系，检查其设定的独立变量和因变量是否可被有效分离。**尤其警惕将多个共变的结构因素（如碳链长度、极性、位阻）打包处理，并要求得出与单一变量相关的结论。**
3.  **任务目标是否可达成？** 基于所给数据或信息，判断问题所要求的归纳、预测或解释在科学方法论上是否合理、可实现，还是要求了过度简化或过度外推。

#### 维度二：思维链的推理严密性
*此维度聚焦于从问题到答案的中间推理过程的质量。*
1.  **推理路径是否完整、连贯？** 思维链的步骤是否层层递进，是否存在逻辑跳跃、循环论证或关键步骤缺失？
2.  **因果推断是否可靠？** 是否正确区分了相关性（correlation）与因果性（causation）？在无法进行控制变量的对比场景中，是否承认结论的局限性，还是将相关性断定为因果性？
3.  **对潜在反例和异常值的处理：** 思维链是否考虑了与主趋势不符的数据点，并给出了合理的解释或坦诚地指出了不确定性？
4.  **边界条件的明确性：** 推理过程中是否主动、准确地识别并声明了结论所能成立的适用范围和前提假设（如特定温度、晶型、组分范围）？

#### 维度三：最终回答的知识准确性与完整性
*此维度评估最终输出的答案本身的知识价值。*
1.  **知识准确性：** 回答中涉及的核心概念、原理、定律和事实性陈述是否准确无误？
2.  **内容完整性：** 是否全面、直接地回应了提问中的所有子任务？有无关键信息遗漏？
3.  **结论的恰当性：** 给出的结论是否与推理过程的严谨程度相匹配？结论的表述是恰当的、留有余地的，还是断然、过度推广的？
4.  **知识深度与拓展价值：** 回答是否停留在现象描述，还是深入到分子机制、热力学原理等本质层面？提出的验证方案或拓展性建议是否科学、可行、富有洞察力？

#### 维度四：问题、思维链与答案的整体一致性
*此维度评估整条COT数据作为一个闭环系统的协调性。*
1.  **任务响应度：** 答案和思维链是否精准聚焦于问题，没有偏题或答非所问？
2.  **信息传递保真度：** 思维链中的正确分析是否完整、无损地传递到了最终答案中？思维链中若存在错误或偏见，是否被带入并污染了最终答案？
3.  **复杂性的匹配：** 思维链和答案的复杂度是否与问题本身的复杂度和要求相匹配？对于存在预设陷阱的问题，思维链和答案是顺应了陷阱，还是识别并绕开了陷阱？

**输出格式要求：**
请以结构化的JSON格式输出评估结果，以便于批量处理和分析。

```json
{
  "overall_quality": "优秀/良好/存在缺陷/严重错误",
  "evaluation_summary": "一句话概括本条COT数据的核心优点与致命缺陷。",
  "detailed_assessment": {
    "dimension_1_problem_soundness": {
      "rating": "评级",
      "comments": "详细评语，必须指出具体问题所在。"
    },
    "dimension_2_cot_rigor": {
      "rating": "评级",
      "comments": "详细评语，点评其逻辑链条的优劣。"
    },
    "dimension_3_answer_quality": {
      "rating": "评级",
      "comments": "详细评语，评估其知识准确与完整性。"
    },
    "dimension_4_overall_consistency": {
      "rating": "评级",
      "comments": "详细评语，评估三者间的匹配与协调度。"
    }
  },
  "critical_flaw_analysis": "如果存在严重缺陷，在此处深入剖析其根源（如：问题预设了错误前提，导致后续所有推理虽然自洽但整体无效）。若无严重缺陷，此字段可为空。"
}
```

**关键提示：**
在评估时，请时刻保持元评估的视角。**不要仅因为答案和思维链本身能自圆其说就给予高分，而是要首先审视其所回答的"问题"是否是一个成立、正确的问题。** 这是发现高级错误的唯一途径。"""


# ---------------------------------------------------------------------------
# Helper: resolve chain_of_thought field with alias support
# ---------------------------------------------------------------------------

_PASS_RATINGS = {"优秀", "良好"}
_FAIL_RATINGS = {"存在缺陷", "严重错误"}


def _resolve_cot_field(record: dict) -> str:
    """优先取 chain_of_thought，若为空依次取 chainofThought、cot。"""
    # 按优先级尝试多个可能的字段名
    for key in ("chain_of_thought", "chainofThought", "cot"):
        val = record.get(key, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _build_user_prompt(record: dict) -> str:
    """构造单条 COT 数据的 user prompt，统一使用 chain_of_thought 命名。"""
    input_text = str(record.get("input", "")).strip()
    cot_text = _resolve_cot_field(record)
    output_text = str(record.get("output", "")).strip()

    parts = []
    if input_text:
        parts.append(f"**input：**\n{input_text}")
    if cot_text:
        parts.append(f"**chain_of_thought：**\n{cot_text}")
    if output_text:
        parts.append(f"**output：**\n{output_text}")

    return "\n\n".join(parts)