你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“多目标约束优化 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
多目标约束优化 CoT

生成要求：
1. output 必须直接回答 input 中提出的多目标约束优化任务，开头即给出推荐方案、推荐候选、推荐配方、推荐工艺窗口或推荐设计方向，不能用“综上”“总体来看”“可以从多个方面考虑”等泛泛开场。
2. 推荐内容必须与 input 中的设计空间一致。如果 input 要求选择候选，则给出推荐候选；如果 input 要求优化配方、工艺或结构，则给出对应的配方、工艺窗口或结构设计方向，不要答成其他任务类型。
3. output 必须紧扣“多目标约束优化”的核心：说明推荐方案如何同时处理硬约束和多个软目标，而不是只解释单一性能为什么提升。
4. 每个关键判断都必须绑定具体对象、目标指标、约束条件、冲突关系或调控变量，不能只写“综合性能更好”“实现性能平衡”“优化结构”“提升稳定性”等空泛表达。
5. 必须说明硬约束是否满足，以及哪些方案因违反硬约束、风险过高或证据不足而不应优先选择。
6. 必须说明软目标之间的主要冲突和取舍，并解释推荐方案为什么是更合理的折中解，而不是单一指标最优解。
7. 如果某个备选方案在单一指标上更优，但会损害其他目标、违反约束或增加风险，output 必须明确指出其不作为首选的原因。
8. 风险、边界和不确定性必须具体到结构、组分、工艺、性能或应用场景层面，不能只写“存在一定风险”“仍需进一步优化”“受条件限制”。
9. 验证方式必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于验证哪个目标、约束、折中判断或失效风险，以及什么结果支持推荐方案成立。
10. output 应按清晰顺序组织，建议采用“推荐结论 -> 硬约束检查 -> 软目标折中逻辑 -> 降级或排除方案 -> 验证方式 -> 适用边界”的结构，避免把结论、原因、风险和验证混在一起。
11. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“实现综合性能提升”等。若表达意义，必须落到具体目标、机制、约束或应用边界上。
12. 不要为了显得完整而强行生成多个备选方案。如果 input 和 chainofThought 只支持一个推荐方向，应集中写清楚该方向；信息不足时，在 missing_information 或 boundary_conditions 中说明缺口。
13. 不要生成完整实验方案；本步骤输出的是优化决策和验证方向，不是详细操作流程。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新候选方案或新实验条件。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该条件范围内”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“优先推荐 A 方案/窗口作为该多目标约束下的折中解。该方案首先满足 B、C 等硬约束，因此没有触及必须排除的安全、稳定性、可加工性或适用条件边界；在软目标上，它牺牲/限制了 Z1 的单项最大化，但换来了 Z2 和 Z3 的更稳定表现，因此比单独追求 Z1 的 D 方案更适合作为首选。D 方案虽然在 Z1 上更突出，但会带来 E 风险或削弱 F 目标，适合作为降级方案或暂不推荐。后续应通过 G 测试验证目标 Z1，通过 H 表征确认约束 B，通过 I 稳定性/安全性评价确认折中是否成立。该判断仅适用于 Q 条件或当前设计空间内，超出该范围需要重新验证。”

请按以下 JSON 输出：

{
  "cot_type": "多目标约束优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "recommended_solution_or_window": "推荐方案、候选、配方、工艺窗口或设计方向",
    "objective_satisfaction_summary": [
      {
        "metric": "目标指标",
        "judgement": "满足 / 部分满足 / 不满足 / 需要验证",
        "reason": "判断理由，必须绑定具体变量、目标、约束或风险"
      }
    ],
    "hard_constraints_check": [
      {
        "constraint": "硬约束",
        "status": "满足 / 不满足 / 需要验证",
        "impact_on_decision": "该约束如何影响推荐、降级或排除"
      }
    ],
    "tradeoff_rationale": "推荐方案在多个目标之间形成合理折中的原因，必须说明目标冲突和取舍逻辑",
    "rejected_or_lower_priority_options": [
      {
        "option": "被排除或降级的方案",
        "reason": "违反约束、风险过高、证据不足、单一指标好但综合不均衡等原因"
      }
    ],
    "validation_methods": [
      {
        "method": "表征、性能测试、稳定性/安全性评价、对照或计算方法",
        "validation_target": "验证哪个目标、约束、折中判断或风险",
        "success_signal": "什么结果支持推荐方案有效"
      }
    ],
    "boundary_conditions": [
      "适用条件、测试边界、设计空间边界、不确定性或需要重新验证的情况"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留体系、变量、多个目标、约束、趋势、冲突或边界；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "does_not_repeat_chain": true,
    "has_recommended_solution_or_window": true,
    "matches_input_design_space": true,
    "checks_hard_constraints": true,
    "summarizes_objective_satisfaction": true,
    "explains_tradeoff_rationale": true,
    "mentions_rejected_or_lower_priority_options": true,
    "does_not_optimize_single_metric_only": true,
    "has_specific_risks_and_boundaries": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "has_success_criteria": true,
    "keeps_boundary_conditions": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
