你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“多目标约束优化 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、performance_metrics、main_observed_results、mechanism_or_explanation、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
多目标约束优化 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的多目标约束优化决策。
3. 必须明确所有目标指标，并说明每个指标的优化方向和重要性。
4. 必须区分硬约束和软目标：硬约束用于筛除不可行方案，软目标用于在可行方案中排序和折中。
5. 必须先判断哪些方案、条件或设计变量水平满足硬约束，哪些应被排除或谨慎处理。
6. 必须分析目标之间的冲突关系，例如提升一个指标是否会牺牲另一个指标，以及该冲突来自结构、组成、界面、传输、稳定性、安全性、成本或工艺可行性的哪一类原因。
7. 必须识别可能的折中解、可行窗口或 Pareto 倾向方案，但不要使用证据不支持的数学优化术语或虚构权重。
8. 必须说明推荐方案或优化窗口为什么在多个目标之间更均衡，而不是只在单一指标上最好。
9. 必须说明被排除或降级方案的原因，例如违反硬约束、虽然某一性能高但副作用过大、稳定性不足、制备不可行或风险过高。
10. 必须保留不确定性；如果证据只支持相关性，不要写成确定因果。
11. 必须给出验证建议，包括关键性能复测、稳定性/安全性评价、结构表征、对照样品或边界条件验证。
12. 不要引入文献没有支撑的新变量、新机制、新数值、新候选方案或新性能结论。
13. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
14. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
15. 不要在 chainofThought 中用括号标注证据来源。
16. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
17. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据改写为目标要求、可行性判断、性能折中和专业推断。
18. 不要使用“根据已有数据”“对照实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
19. 不要生成最终 output。

推荐推理步骤结构：
1. 明确研究体系、设计空间和所有目标指标。
2. 统一各指标优化方向，区分越高越好、越低越好、阈值约束和范围约束。
3. 划分硬约束与软目标，并说明硬约束的筛选作用。
4. 筛选满足硬约束的可行方案或可行窗口。
5. 分析可行方案内部的目标冲突和折中关系。
6. 判断最均衡的推荐方案、窗口或策略，并说明优先级。
7. 说明被排除或降级方案的原因。
8. 给出验证指标、风险点和适用边界。

请按以下 JSON 输出：

{
  "cot_type": "多目标约束优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留体系、变量、多个目标、约束、趋势、冲突或边界；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、设计空间、指标阈值、测试条件、证据强度或适用边界"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_multiple_objectives": true,
    "normalizes_objective_directions": true,
    "distinguishes_hard_constraints_and_soft_goals": true,
    "screens_feasible_space": true,
    "analyzes_tradeoffs": true,
    "identifies_balanced_solution_or_window": true,
    "does_not_optimize_single_metric_only": true,
    "explains_rejected_or_downgraded_options": true,
    "mentions_risks_and_side_effects": true,
    "includes_validation_methods": true,
    "keeps_uncertainty": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}