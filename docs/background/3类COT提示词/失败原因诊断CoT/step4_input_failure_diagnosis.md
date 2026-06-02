你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“失败原因诊断 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、failure_or_limitations、cot_type_judgement>

目标 CoT 类型：
失败原因诊断 CoT

生成要求：
1. input 必须表现为具体失败诊断任务，而不是泛泛讨论。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含研究对象 X。
4. 必须包含原始设计意图，例如希望通过 Y 改性、掺杂、替换、配方、工艺或结构调控提升性能 Z。
5. 必须包含实际失败信号，例如性能没有提升、反而下降、稳定性变差、选择性下降、结构坍塌、副反应增强、循环衰减、产率降低、不可重复等。
6. 如果有成功样品、失败样品、基准样品或对照样品之间的差异，应写入 input。
7. 如果有表征或测试异常，例如晶相变化、形貌破坏、阻抗升高、活性位点减少、杂相生成、孔结构塌陷、吸附过强、溶解性变差等，应写入 input。
8. input 应要求模型诊断可能失败原因，并提出修正方向和验证方法。
9. 不要在 input 中直接写出最终失败原因。
10. 如果没有明确失败现象、负例或失败信号，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“研究者原本希望通过 Y 策略改善 X 体系的 Z 性能，但实际结果显示性能没有提升或反而下降，同时出现 A、B 等异常信号；与成功样品或基准样品相比，失败样品在 M、N 方面存在差异。请诊断可能失败原因，并提出后续修正方向和验证方法。”

请按以下 JSON 输出：

{
  "cot_type": "失败原因诊断 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_object": "X",
    "original_design_intent": "原始设计意图",
    "target_performance": "Z",
    "expected_positive_effect": "预期正向作用",
    "actual_failure_signal": "实际失败表现",
    "comparison_samples": ["成功样品、失败样品、基准样品或对照样品"],
    "diagnostic_clues": ["表征、测试、结构或性能异常线索"],
    "required_task": "诊断失败原因 / 提出修正方向 / 给出验证方法"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留设计意图、失败信号、样品差异、异常表征或测试条件"
  ],
  "quality_check": {
    "is_specific": true,
    "has_design_intent": true,
    "has_failure_signal": true,
    "has_target_performance": true,
    "has_comparison_or_diagnostic_clues": true,
    "asks_for_failure_diagnosis": true,
    "asks_for_correction_strategy": true,
    "asks_for_validation_method": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}