你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“机理到设计策略迁移 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、mechanism_or_explanation、cot_type_judgement>

目标 CoT 类型：
机理到设计策略迁移 CoT

生成要求：
1. input 必须表现为“基于已知机制提出设计策略”的任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含研究对象或体系 X。
4. 必须包含已知机制 M，例如活性位点调控、界面阻抗降低、离子传输增强、载流子分离、缺陷调控、吸附能调节、疏水性增强、晶相稳定、分子构象变化等。
5. 必须包含目标性能 Z 或进一步优化目标。
6. 必须包含机制 M 对应的可调控设计变量，例如组分、缺陷、晶相、界面、孔结构、官能团、侧链、金属中心、溶剂环境、配位结构等。
7. input 应要求模型基于机制 M 推导可迁移设计策略，而不是只解释原体系为什么有效。
8. input 应要求说明策略适用条件、潜在风险和验证方法。
9. 不要在 input 中直接给出最终设计策略答案。
10. 如果缺少明确机制或机制缺少证据支撑，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“已知 X 体系的性能提升主要来自机制 M，该机制与变量 A、B、C 的调控有关。现在希望进一步提升目标性能 Z，并避免问题 R。请基于机制 M 提出可迁移的设计策略，说明应优先调控哪些变量、为什么这些变量可能有效、适用边界是什么，以及需要通过哪些实验或计算验证。”

请按以下 JSON 输出：

{
  "cot_type": "机理到设计策略迁移 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_system": "X",
    "known_mechanism": "M",
    "target_performance": "Z",
    "current_limitation_or_goal": "当前短板或进一步优化目标",
    "controllable_design_variables": ["A", "B", "C"],
    "potential_risks_or_boundaries": ["策略迁移时需要注意的风险或边界"],
    "required_task": "基于机制提出设计策略 / 判断适用条件 / 给出验证方法"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留机制、变量、性能指标、验证方法或边界条件"
  ],
  "quality_check": {
    "is_specific": true,
    "has_known_mechanism": true,
    "has_target_performance": true,
    "has_controllable_variables": true,
    "asks_for_design_strategy_transfer": true,
    "asks_for_boundary_conditions": true,
    "asks_for_validation_methods": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}