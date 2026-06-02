你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“机理到设计策略迁移 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
机理到设计策略迁移 CoT

生成要求：
1. output 必须直接回答 input 中提出的设计策略迁移任务。
2. 必须给出明确的设计策略，而不是只重复机制解释。
3. 必须说明该策略对应的机制依据。
4. 必须说明应优先调控哪些变量。
5. 必须说明这些变量如何影响目标性能。
6. 必须说明策略适用条件和潜在风险。
7. 必须给出验证方法，例如结构表征、性能测试、稳定性测试、动力学实验、原位表征或计算验证。
8. 不要引入 input 和 chainofThought 中没有出现的新机制、新变量、新数值或新性能结论。
9. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果。
10. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
11. output 应完成证据内化，不要出现“机理表征表明”“根据已有数据”“结果显示”等证据过程表达。
12. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“基于机制 M，应优先采用 A 和 B 设计策略，通过调控变量 C、D 来增强过程 E，从而改善目标性能 Z。该策略适用于具备 F 条件的体系，但需要注意 G 副作用。后续应通过 H 表征、I 性能测试和 J 稳定性/计算验证确认该策略是否真正增强了机制 M。”

请按以下 JSON 输出：

{
  "cot_type": "机理到设计策略迁移 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought",
  "output_elements": {
    "recommended_design_strategies": [
      {
        "strategy": "推荐设计策略",
        "target_variables": ["应调控的变量"],
        "mechanism_basis": "该策略对应的机制依据",
        "expected_performance_pathway": "变量如何通过机制影响目标性能",
        "potential_risks": ["潜在副作用或限制"]
      }
    ],
    "priority_order": [
      "如果有多个策略，给出优先级"
    ],
    "validation_methods": [
      {
        "method": "实验、表征、测试或计算方法",
        "validation_target": "验证哪个机制、变量或性能路径",
        "success_signal": "什么结果说明策略有效"
      }
    ],
    "applicability_boundary": [
      "策略适用的体系、结构、条件或应用边界"
    ],
    "fallback_or_next_iteration": [
      "如果首选策略效果不足，下一步如何调整"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留机制、变量、性能指标、验证方法或边界；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "has_design_strategy": true,
    "has_mechanism_basis": true,
    "has_target_variables": true,
    "links_strategy_to_performance": true,
    "has_applicability_boundary": true,
    "mentions_potential_risks": true,
    "includes_validation_methods": true,
    "does_not_repeat_chain": true,
    "does_not_add_new_claims": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}