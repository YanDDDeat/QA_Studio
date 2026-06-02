你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“实验条件 / 制备工艺优化 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
实验条件 / 制备工艺优化 CoT

生成要求：
1. output 必须直接回答 input 中提出的工艺优化任务。
2. output 应简洁明确，但必须包含足够专业信息。
3. 必须给出推荐工艺窗口、最佳条件或合理优化方向。
4. 必须说明该窗口成立的核心依据，例如性能趋势、结构变化、过程变化、表征信号或副作用对比。
5. 必须说明过低或过高条件可能导致的问题。
6. 必须给出必要的表征、性能测试或稳定性验证方法。
7. 必须保留适用边界和不确定性，不能把特定体系结论写成普适规律。
8. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制或新实验条件。
9. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果。
10. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
11. output 应完成证据内化，不要出现“筛选实验表明”“根据已有数据”“结果显示”等证据过程表达。
12. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该体系应将工艺变量 Y 控制在 A 条件或 A-B 窗口内，因为该窗口能在促进目标结构/过程 M 的同时避免副作用 N，从而更有利于提升目标性能 Z。过低条件会导致 P 问题，过高条件会导致 Q 问题。后续应通过 R 表征和 S 性能测试验证该窗口是否稳定有效。”

请按以下 JSON 输出：

{
  "cot_type": "实验条件 / 制备工艺优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought",
  "output_elements": {
    "recommended_process_window": "推荐工艺窗口、最佳条件或优化方向",
    "core_rationale": "支持该窗口的核心依据",
    "low_condition_risk": "过低条件的风险或副作用",
    "high_condition_risk": "过高条件的风险或副作用",
    "validation_methods": ["需要的表征方法、性能测试或稳定性验证"],
    "boundary_conditions": ["适用条件、体系边界或不确定性"]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留图表、章节、变量、数值、单位或条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "does_not_repeat_chain": true,
    "has_recommended_process_window": true,
    "has_core_rationale": true,
    "mentions_low_or_high_condition_side_effects": true,
    "includes_validation_methods": true,
    "keeps_boundary_conditions": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}