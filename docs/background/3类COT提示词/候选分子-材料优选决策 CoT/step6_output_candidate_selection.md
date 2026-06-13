你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“候选分子 / 材料优选决策 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
候选分子 / 材料优选决策 CoT

生成要求：
1. output 必须直接回答 input 中提出的候选优选任务，开头即给出推荐候选、条件性推荐或候选排序，不能用“综上”“总体来看”“可以从多个方面考虑”等泛泛开场。
2. output 必须紧扣“候选分子 / 材料优选决策”任务，不要答成性能提升路径、构效关系、实验方案或泛泛材料评价。回答重点应是“应用场景 -> 指标优先级 -> 候选对比 -> 推荐结论 -> 风险与边界”。
3. 如果 input 或 chainofThought 没有明确应用场景、候选对象、评价指标或可比较依据，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行推荐。
4. 必须明确给出推荐候选；如果证据不足以唯一推荐，应给出条件性推荐或候选排序，并说明不同条件下选择如何改变。
5. 推荐理由必须基于应用场景下的指标优先级，而不是简单说“综合性能最好”。必须说明哪些指标是首要指标，哪些指标是约束、风险或次级目标。
6. 每个关键判断都必须绑定具体候选、评价指标、优势、短板或风险，不能只写“性能优异”“稳定性较好”“更适合应用”“综合表现突出”等空泛表达。
7. 不能只依据单一最高指标做选择，除非 input 明确该指标是唯一关键指标。若某候选单项指标更突出但存在关键短板，output 必须说明其为什么不作为首选。
8. 必须说明非推荐候选为什么不是首选，包括违反关键约束、关键指标不足、风险更高、适用场景不匹配或证据不足等具体原因。
9. 被推荐候选的风险和边界必须具体到性能、稳定性、安全性、成本、可制备性、相容性、加工性或应用场景层面，不能只写“存在一定风险”或“仍需优化”。
10. 后续验证必须说明验证目标和成功信号，不能只罗列测试名称。例如应说明该测试用于确认哪个关键指标、风险、稳定性、安全性、成本或可制备性问题。
11. output 应按清晰顺序组织，建议采用“推荐结论 -> 指标优先级 -> 候选对比 -> 非首选原因 -> 选择可能改变的条件 -> 后续验证 -> 适用边界”的结构，避免把结论、理由、风险和验证混在一起。
12. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“综合性能优异”等。若表达意义，必须落到具体场景、指标或约束上。
13. 不要为了显得完整而强行生成新的候选、指标或排序。如果证据只支持两个候选对比，就只比较这两个候选；如果证据不足，应在 missing_information 或 boundary_conditions 中说明。
14. 不要引入 input 和 chainofThought 中没有出现的新候选、新指标、新数值、新风险、新机制、新应用场景或新结论。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定结论，必须保留“在当前场景下”“更倾向于”“若优先级改变”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“对比实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“在当前 X 应用场景下，优先推荐候选 A。该选择的关键依据是当前场景更重视 P 和 Q 指标，而 A 在这两个核心指标上更符合要求，同时 R 风险处于可接受或可验证范围。候选 B 虽然在 M 指标上更突出，但受 N 短板限制，不宜作为首选；候选 C 的优势是 O，但在当前指标优先级下不足以抵消其 P 或 Q 方面的不足。如果应用场景转为更重视 M、成本、安全性或可制备性，候选排序可能改变。后续应通过 S 测试确认 A 的关键性能，通过 T 稳定性/安全性/成本/可制备性验证排查主要风险。该推荐仅适用于当前 X 场景和指标优先级内。”

请按以下 JSON 输出：

{
  "cot_type": "候选分子 / 材料优选决策 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少应用场景、候选对象、评价指标、优先级、风险信息或可比较证据"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "application_context": "当前应用场景或使用条件",
    "recommended_candidate": "推荐候选；如果无法唯一推荐，写条件性推荐或排序",
    "recommendation_type": "single_best / conditional_best / ranked_candidates / insufficient_evidence",
    "metric_priority": [
      {
        "metric": "评价指标或约束",
        "priority": "核心指标 / 硬约束 / 次级指标 / 风险项",
        "reason": "为什么该指标在当前场景下重要"
      }
    ],
    "core_decision_basis": [
      "推荐候选的核心依据，必须对应应用场景、指标优先级和候选差异"
    ],
    "candidate_tradeoff_summary": [
      {
        "candidate": "候选名称",
        "main_advantages": ["主要优势，必须绑定具体指标或场景"],
        "main_limitations": ["主要短板、风险或证据缺口"],
        "decision_role": "首选 / 备选 / 特定条件下更优 / 不推荐",
        "reason_for_role": "为什么承担该决策角色"
      }
    ],
    "unacceptable_or_manageable_risks": [
      "不可接受风险，或可接受但需要验证的风险"
    ],
    "when_choice_may_change": [
      "如果应用场景、指标优先级或约束条件改变，选择可能如何变化"
    ],
    "followup_validation": [
      {
        "method": "性能测试、稳定性测试、安全性验证、成本评估、可制备性验证、相容性评价或其他方法",
        "validation_target": "验证哪个关键指标、风险或选择依据",
        "success_signal": "什么结果支持该候选作为首选"
      }
    ],
    "boundary_conditions": [
      "该推荐成立的应用场景、测试条件、指标优先级、材料体系边界或不确定性"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留候选名称、指标、条件、数值、单位或证据位置；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_candidate_selection_task": true,
    "has_application_context": true,
    "has_recommended_candidate": true,
    "has_decision_basis": true,
    "uses_metric_priority": true,
    "compares_non_selected_candidates": true,
    "explains_why_others_are_not_first_choice": true,
    "does_not_overuse_single_metric": true,
    "mentions_specific_risks": true,
    "mentions_when_choice_changes": true,
    "includes_followup_validation": true,
    "validation_methods_have_targets_and_success_signals": true,
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
