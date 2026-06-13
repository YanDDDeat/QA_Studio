你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“性能提升路径 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、performance_metrics、main_observed_results、mechanism_or_explanation、cot_type_judgement>

目标 CoT 类型：
性能提升路径 CoT

生成要求：
1. input 必须表现为“针对体系 X 的性能短板，如何提出提升性能 Z 的路径”的任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. input 必须包含具体研究对象或材料/分子/催化/储能/吸附/传感体系 X。
4. input 必须包含当前性能短板、性能基线或待突破的问题，例如活性不足、选择性低、循环稳定性差、容量衰减、传输受限、能量密度不足、感度偏高、产率低、响应慢等。
5. input 必须包含目标性能指标 Z，并尽量保留必要单位、测试条件或评价场景。
6. input 必须包含至少一个限制性能提升的瓶颈线索，例如电子结构不匹配、活性位点不足、界面传输慢、孔道扩散受限、结构稳定性差、副反应多、结晶/形貌不理想、组分比例不合理等。
7. input 必须包含可调控因素，例如结构单元、取代基、掺杂元素、缺陷浓度、晶相、形貌、孔结构、界面层、负载量、组分比例、制备条件或后处理条件。
8. 如果有性能趋势、对照样品、失败条件、最优窗口或机制线索，应写入 input，但不得把最终提升路径直接写成答案。
9. input 应要求模型提出性能提升路径、说明每条路径对应的瓶颈和作用机制、判断潜在副作用，并给出验证指标。
10. 不要把任务写成“选择哪个候选最好”；如果核心任务是候选排序，应转入“候选分子 / 材料优选决策 CoT”。
11. 不要把任务写成完整实验步骤设计；如果核心任务是实验分组、操作流程和对照设置，应转入“实验方案生成 CoT”。
12. 不要把任务限定为单一反事实替换；如果核心任务是“A 替换为 B 后性能如何变化”，应转入“反事实结构改造 CoT”。
13. 如果缺少研究体系、目标性能或可调控因素，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“X 体系当前在性能 Z 上存在短板，主要表现为 A；已有信息提示该短板可能与 B 瓶颈有关，可调控因素包括 C、D 和 E。请围绕目标性能 Z 提出可行的性能提升路径，说明每条路径对应的限制因素、预期作用机制、潜在副作用、优先级和验证指标。”

请按以下 JSON 输出：

{
  "cot_type": "性能提升路径 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_system": "X",
    "current_performance_gap": "当前性能短板或性能基线",
    "target_performance": "目标性能指标 Z",
    "bottleneck_clues": [
      "限制性能提升的瓶颈线索"
    ],
    "adjustable_factors": [
      "可调控结构、组成、界面、工艺或测试因素"
    ],
    "known_trends_or_comparisons": [
      "可用于构建提升路径的趋势、对照或机制线索"
    ],
    "constraints": [
      "稳定性、安全性、成本、可制备性、测试条件或适用范围"
    ],
    "required_task": "提出性能提升路径 / 解释作用机制 / 判断副作用 / 给出优先级和验证指标"
  },
  "evidence_used": [
    "用于生成 input 的关键信息，保留体系、性能短板、可调控因素、趋势、机制或约束"
  ],
  "quality_check": {
    "is_specific": true,
    "has_research_system": true,
    "has_current_performance_gap": true,
    "has_target_performance": true,
    "has_bottleneck_clues": true,
    "has_adjustable_factors": true,
    "asks_for_improvement_paths": true,
    "asks_for_mechanism_and_side_effects": true,
    "asks_for_priority_and_validation": true,
    "does_not_turn_into_candidate_selection": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_turn_into_counterfactual_modification": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}