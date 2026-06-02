你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“实验方案生成 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information 和 cot_type_judgement>

目标 CoT 类型：
实验方案生成 CoT

生成要求：
1. input 必须表现为一个具体实验方案设计任务，而不是泛泛建议。
2. input 中不要出现“根据文献”“本文报道”“作者发现”等文献来源表达。
3. 必须包含研究对象 X。
4. 必须包含实验目标，例如提升性能 Z、验证机制 M、比较候选策略、优化体系短板等。
5. 必须包含当前短板或待验证问题。
6. 应包含可调控变量，例如结构变量、组分变量、工艺变量、配方变量或候选材料。
7. 应要求设计实验分组、对照组、关键变量、表征方法和性能测试。
8. 如果有已知风险、边界条件或失败信号，应写入 input，要求方案中规避或验证。
9. 不要在 input 中直接给出实验方案细节答案。
10. 如果缺少研究目标、可调变量或验证方法，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“针对 X 体系当前存在的 A 短板，希望提升或验证目标 Z。可调控变量包括 B、C、D，并需要通过 M 类表征和 P 类性能测试判断效果。请设计一套实验方案，包括实验分组、对照设置、关键变量、验证方法和成功判据。”

请按以下 JSON 输出：

{
  "cot_type": "实验方案生成 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_object": "X",
    "experiment_goal": "提升性能 / 验证机制 / 比较策略 / 优化短板",
    "current_problem_or_shortcoming": "A",
    "candidate_variables": ["B", "C", "D"],
    "suggested_controls_or_comparisons": ["空白组、对照组、变量组、最佳样品或失败样品"],
    "validation_methods": ["表征方法、性能测试或计算验证"],
    "success_metrics": ["用于判断实验是否成功的指标"],
    "risk_or_boundary": ["需要规避或验证的风险与边界"],
    "required_task": "设计实验方案 / 设置对照 / 指定验证方法 / 定义成功判据"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留图表、章节、条件或数值"
  ],
  "quality_check": {
    "is_specific": true,
    "has_experiment_goal": true,
    "has_candidate_variables": true,
    "asks_for_controls": true,
    "asks_for_validation": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}