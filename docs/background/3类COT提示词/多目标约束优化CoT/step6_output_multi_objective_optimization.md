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
1. output 必须直接回答 input 中提出的多目标约束优化任务。
2. 必须给出推荐方案、推荐候选、推荐配方、推荐工艺窗口或推荐设计方向；具体形式应与 input 的设计空间一致。
3. 必须说明硬约束是否满足，以及哪些方案因违反硬约束或风险过高而不应优先选择。
4. 必须说明软目标之间的折中逻辑，强调推荐方案为什么是均衡解，而不是单一指标最优解。
5. 必须说明各目标之间的主要冲突和取舍。
6. 必须给出验证方法和成功判据，例如关键性能复测、稳定性/安全性测试、结构表征、对照样品或边界条件验证。
7. 必须保留适用边界和不确定性，不能把特定体系下的折中判断写成普适规律。
8. 不要生成完整实验方案；本步骤输出的是优化决策和验证方向，不是详细操作流程。
9. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新候选方案或新实验条件。
10. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果。
11. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
12. output 应完成证据内化，不要出现“筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
13. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“在该多目标约束下，优先推荐 A 方案/窗口。它首先满足 B、C 等硬约束，同时在 Z1、Z2 和 Z3 之间形成较均衡的折中：……。相比之下，D 方案虽然在 Z1 上更突出，但因 E 风险或 F 约束不满足，不宜作为首选。后续应通过 G 测试、H 表征和 I 稳定性/安全性验证确认该折中是否成立。该判断适用于 Q 条件内，超出该范围需要重新验证。”

请按以下 JSON 输出：

{
  "cot_type": "多目标约束优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought",
  "output_elements": {
    "recommended_solution_or_window": "推荐方案、候选、配方、工艺窗口或设计方向",
    "objective_satisfaction_summary": [
      {
        "metric": "目标指标",
        "judgement": "满足 / 部分满足 / 不满足 / 需要验证",
        "reason": "判断理由"
      }
    ],
    "hard_constraints_check": [
      {
        "constraint": "硬约束",
        "status": "满足 / 不满足 / 需要验证",
        "impact_on_decision": "该约束如何影响推荐或排除"
      }
    ],
    "tradeoff_rationale": "推荐方案在多个目标之间形成合理折中的原因",
    "rejected_or_lower_priority_options": [
      {
        "option": "被排除或降级的方案",
        "reason": "违反约束、风险过高、单一指标好但综合不均衡等原因"
      }
    ],
    "validation_methods": [
      {
        "method": "表征、性能测试、稳定性/安全性评价、对照或计算方法",
        "validation_target": "验证哪个目标、约束或折中判断",
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
    "checks_hard_constraints": true,
    "summarizes_objective_satisfaction": true,
    "explains_tradeoff_rationale": true,
    "mentions_rejected_or_lower_priority_options": true,
    "does_not_optimize_single_metric_only": true,
    "includes_validation_methods": true,
    "has_success_criteria": true,
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