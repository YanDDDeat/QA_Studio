你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“反事实结构改造 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、mechanism_or_explanation、cot_type_judgement>

目标 CoT 类型：
反事实结构改造 CoT

生成要求：
1. input 必须表现为“如果将结构因素 A 替换/改造为 B，会如何影响性能 Z”的反事实任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含具体研究对象或材料/分子体系 X。
4. 必须包含原始结构因素 A，例如官能团、金属中心、掺杂元素、晶相、缺陷浓度、侧链长度、配位环境、孔结构、界面层等。
5. 必须包含拟替换、增加、减少或改造的结构因素 B。
6. 必须包含目标性能 Z，例如活性、选择性、稳定性、容量、感度、密度、吸附能力、传输性能、能垒、溶解性等。
7. 如果有相似对照样品、系列趋势或已知副作用，应写入 input。
8. input 应要求模型预测性能变化方向，说明原因、潜在副作用和验证方法。
9. 不要在 input 中直接给出最终预测答案。
10. 如果缺少原结构因素、拟改造因素或目标性能，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“X 材料/分子原本具有结构因素 A，该因素与性能 Z 的表现有关。若将 A 替换/调控为 B，B 在电子效应、空间位阻、配位能力、界面作用或传输特性上与 A 存在差异。请预测目标性能 Z 可能如何变化，并说明原因、潜在副作用和验证方法。”

请按以下 JSON 输出：

{
  "cot_type": "反事实结构改造 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_system": "X",
    "original_structure_factor": "A",
    "counterfactual_modification": "B",
    "target_performance": "Z",
    "known_role_of_original_factor": "A 的作用",
    "expected_difference_between_A_and_B": ["电子、空间、界面、传输、吸附、稳定性等差异"],
    "possible_side_effects": ["潜在副作用或风险"],
    "required_task": "预测性能变化 / 解释原因 / 判断副作用 / 给出验证方法"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留结构因素、相似对照、性能趋势、机制或风险"
  ],
  "quality_check": {
    "is_specific": true,
    "has_original_structure_factor": true,
    "has_counterfactual_modification": true,
    "has_target_performance": true,
    "has_known_role_or_comparison_basis": true,
    "asks_for_prediction": true,
    "asks_for_side_effects": true,
    "asks_for_validation_methods": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}