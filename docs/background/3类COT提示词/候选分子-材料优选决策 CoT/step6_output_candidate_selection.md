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
1. output 必须直接回答 input 中提出的候选优选任务。
2. output 应明确给出推荐候选；如果证据不足以唯一推荐，应给出条件性推荐或候选排序。
3. 必须说明推荐理由，且理由应基于应用场景下的指标优先级。
4. 必须说明被推荐候选的主要优势和主要风险。
5. 必须说明其他候选为什么不是首选，避免只说“因为 A 最好”。
6. 不能只依据单一最高指标做选择，除非 input 明确该指标是唯一关键指标。
7. 必须说明如果应用场景或指标优先级变化，选择是否可能改变。
8. 必须给出后续需要补充验证的测试、表征、安全性、稳定性、成本或可制备性验证。
9. 必须保留适用边界和不确定性，不能把特定场景下的选择写成普适结论。
10. 不要引入 input 和 chainofThought 中没有出现的新候选、新指标、新数值、新风险或新结论。
11. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果。
12. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
13. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“在当前 X 应用场景下，应优先选择候选 A，因为 A 在关键指标 P 和 Q 上更符合场景需求，同时其 R 风险处于可接受范围。候选 B 虽然在 M 指标上更突出，但受 N 短板限制；候选 C 的优势是 O，但在当前优先级下不足以成为首选。如果应用场景转为更重视 M 或成本/安全性，则候选选择可能改变。后续应通过 S、T 测试进一步验证 A 的稳定性和应用可靠性。”

请按以下 JSON 输出：

{
  "cot_type": "候选分子 / 材料优选决策 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought",
  "output_elements": {
    "recommended_candidate": "推荐候选；如果无法唯一推荐，写条件性推荐或排序",
    "recommendation_type": "single_best / conditional_best / ranked_candidates / insufficient_evidence",
    "core_decision_basis": [
      "推荐候选的核心依据，需对应应用场景和指标优先级"
    ],
    "candidate_tradeoff_summary": [
      {
        "candidate": "候选名称",
        "main_advantages": ["主要优势"],
        "main_limitations": ["主要短板或风险"],
        "decision_role": "首选 / 备选 / 特定条件下更优 / 不推荐"
      }
    ],
    "unacceptable_or_manageable_risks": [
      "不可接受风险或可接受但需要验证的风险"
    ],
    "when_choice_may_change": [
      "如果应用场景、指标优先级或约束条件改变，选择可能如何变化"
    ],
    "followup_validation": [
      "需要补充的性能测试、稳定性测试、安全性验证、成本评估或可制备性验证"
    ],
    "boundary_conditions": [
      "该推荐成立的应用场景、测试条件、指标优先级或材料体系边界"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留候选名称、指标、条件、数值、单位或证据位置；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "has_recommended_candidate": true,
    "has_decision_basis": true,
    "uses_metric_priority": true,
    "compares_non_selected_candidates": true,
    "does_not_overuse_single_metric": true,
    "mentions_risks": true,
    "mentions_when_choice_changes": true,
    "includes_followup_validation": true,
    "keeps_boundary_conditions": true,
    "does_not_add_new_claims": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true
  }
}