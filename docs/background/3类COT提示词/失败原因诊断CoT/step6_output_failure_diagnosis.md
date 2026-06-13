你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“失败原因诊断 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
失败原因诊断 CoT

生成要求：
1. output 必须直接回答 input 中提出的失败诊断任务，开头即给出最可能失败原因、优先怀疑原因或条件性诊断结论，不能用“综上”“总体来看”“可能需要从多个方面分析”等泛泛开场。
2. output 必须紧扣“失败原因诊断”任务，不要答成普通性能提升、工艺优化、实验方案或泛泛改进建议。回答重点应是“原始设计意图 -> 实际失败信号 -> 失效环节 -> 根因判断 -> 修正策略 -> 验证方式”。
3. 如果 input 或 chainofThought 没有明确失败现象、预期目标、样品差异、异常信号或可支撑的诊断依据，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行诊断。
4. 必须给出最可能失败原因；如果证据不足，应写成“优先怀疑原因”或“可能原因”，并标明置信度。不能把证据不足的判断写成确定根因。
5. 每个失败原因都必须对应具体失败信号、样品差异、性能下降、结构异常、界面问题、副反应、稳定性问题或工艺失控现象，不能只写“结构不稳定”“反应不充分”“性能下降明显”等空泛表达。
6. 必须说明失败原因与实际失败信号之间的对应关系：该原因为什么能解释观测到的异常，不能只给结论不解释诊断依据。
7. 如果存在多个可能原因，必须给出优先级或排查顺序，并说明为什么某一原因优先怀疑，其他原因属于备选或待排查。
8. 修正策略必须针对具体失效环节，说明要调整什么变量、抑制什么副作用、恢复什么结构/过程或改善什么性能通道，不能只写“优化工艺”“改善结构”“进一步调控条件”等泛泛建议。
9. 必须说明修正策略的潜在风险或边界。例如修正某个副作用时是否可能牺牲活性、稳定性、选择性、传输、加工性或安全性。
10. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于确认哪个失败原因、排除哪个备选原因、验证哪个修正策略，以及什么结果支持或否定该诊断。
11. output 应按清晰顺序组织，建议采用“诊断结论 -> 失败信号对应关系 -> 备选原因/排查顺序 -> 修正策略 -> 验证方式 -> 边界与不确定性”的结构，避免把结论、原因、修正和验证混在一起。
12. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“需要进一步系统优化”等。若表达后续意义，必须落到具体失效环节、修正变量或验证指标上。
13. 不要为了显得完整而强行生成多个失败原因。如果 input 和 chainofThought 只支持一个主要原因，应集中写清楚该原因；如果证据不足，应在 missing_information 或 remaining_uncertainties 中说明。
14. 不要生成完整实验方案；本步骤输出的是失败诊断、修正方向和验证路径，不是详细操作流程。
15. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新失败原因、新实验条件或新性能结论。
16. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“优先怀疑”“可能”“更倾向于”“需要进一步验证”等限定表达。
17. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
18. output 应完成证据内化，不要出现“失败实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
19. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该失败优先怀疑由 A 失效环节引起。A 能同时解释 B 失败信号和 C 样品差异：它会导致 D 结构/过程异常，进而削弱目标性能 Z。备选原因 E 也需要排查，但目前它只能解释部分信号，优先级低于 A。修正时应针对 A 调整 F 变量或降低 G 副作用，预期恢复 H 过程或抑制 I 失效表现；但该策略可能带来 J 风险。后续应通过 K 表征确认 A 是否存在，通过 L 性能测试判断修正后 Z 是否恢复，并通过 M 对照排除 E 原因。该诊断仅适用于 Q 条件或当前样品范围内，超出该边界需要重新验证。”

请按以下 JSON 输出：

{
  "cot_type": "失败原因诊断 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少失败现象、预期目标、样品差异、异常信号、诊断依据或验证条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "original_intent": "原始设计意图或预期目标",
    "observed_failure": "实际失败现象或异常信号",
    "likely_failure_reasons": [
      {
        "reason": "最可能失败原因或优先怀疑原因",
        "confidence": "high / medium / low",
        "linked_failure_signals": ["该原因能解释的失败信号、样品差异或异常表现"],
        "diagnostic_logic": "该原因为什么能解释这些失败信号"
      }
    ],
    "alternative_causes_or_exclusion_order": [
      {
        "cause": "备选失败原因或待排查原因",
        "priority": "高 / 中 / 低",
        "reason": "为什么需要排查，或为什么不是首要原因"
      }
    ],
    "core_diagnostic_basis": [
      "失败原因与样品差异、异常信号、性能下降或失效环节之间的核心逻辑"
    ],
    "correction_strategies": [
      {
        "strategy": "修正策略",
        "targeted_failure_link": "该策略针对哪个失效环节或失败原因",
        "expected_effect": "预期恢复或改善什么结构、过程、性能通道或失效表现",
        "potential_tradeoff_or_risk": "该修正可能带来的副作用、折中关系或边界"
      }
    ],
    "validation_methods": [
      {
        "method": "表征、测试、对照或计算方法",
        "validation_target": "用于验证哪个失败原因、排除哪个备选原因或验证哪个修正策略",
        "success_signal": "什么信号说明诊断成立、修正有效或该原因应被排除"
      }
    ],
    "remaining_uncertainties": [
      "仍需保留的不确定性、证据缺口或待排查因素"
    ],
    "boundary_conditions": [
      "该诊断成立的体系、条件、样品范围、测试边界或适用条件"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留失败信号、样品差异、表征或测试条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_failure_diagnosis_task": true,
    "has_original_intent": true,
    "has_observed_failure": true,
    "has_likely_failure_reason": true,
    "links_reason_to_failure_signal": true,
    "has_diagnostic_logic": true,
    "handles_alternative_causes_or_exclusion_order": true,
    "has_correction_strategy": true,
    "correction_strategy_targets_failure_link": true,
    "mentions_specific_tradeoffs_or_risks": true,
    "has_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "keeps_uncertainty": true,
    "keeps_boundary_conditions": true,
    "does_not_repeat_chain": true,
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
