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
1. output 必须直接回答 input 中提出的失败诊断任务。
2. 必须给出最可能失败原因；如果证据不足，应写成“可能原因”或“优先怀疑原因”。
3. 必须说明失败原因与实际失败信号之间的对应关系。
4. 必须给出针对性修正策略，而不是泛泛建议。
5. 必须给出验证失败原因的具体方法。
6. 必须保留适用边界和不确定性。
7. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制或新实验条件。
8. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果。
9. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
10. output 应完成证据内化，不要出现“失败实验表明”“根据已有数据”“结果显示”等证据过程表达。
11. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该失败优先怀疑是由 A 环节失效引起的，因为该环节能够同时解释 B 失败信号和 C 样品差异。后续应通过 D 策略修正，例如调整 E 条件或降低 F 副作用，并用 G 表征和 H 性能测试验证该判断。如果验证结果不支持 A，则需要进一步排查 I 风险。”

请按以下 JSON 输出：

{
  "cot_type": "失败原因诊断 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought",
  "output_elements": {
    "likely_failure_reasons": [
      {
        "reason": "最可能失败原因",
        "confidence": "high / medium / low",
        "linked_failure_signals": ["该原因能解释的失败信号"]
      }
    ],
    "core_diagnostic_basis": [
      "失败原因与样品差异、异常信号或性能下降之间的核心逻辑"
    ],
    "correction_strategies": [
      {
        "strategy": "修正策略",
        "targeted_failure_link": "该策略针对哪个失效环节",
        "expected_effect": "预期改善什么问题"
      }
    ],
    "validation_methods": [
      {
        "method": "表征、测试、对照或计算方法",
        "validation_target": "用于验证哪个失败原因或修正策略",
        "success_signal": "什么信号说明判断成立"
      }
    ],
    "remaining_uncertainties": [
      "仍需保留的不确定性"
    ],
    "boundary_conditions": [
      "该诊断成立的体系、条件、样品范围或适用边界"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留失败信号、样品差异、表征或测试条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "has_likely_failure_reason": true,
    "links_reason_to_failure_signal": true,
    "has_correction_strategy": true,
    "has_validation_methods": true,
    "keeps_uncertainty": true,
    "keeps_boundary_conditions": true,
    "does_not_repeat_chain": true,
    "does_not_add_new_claims": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}