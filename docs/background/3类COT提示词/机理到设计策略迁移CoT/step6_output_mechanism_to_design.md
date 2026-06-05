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
1. output 必须直接回答 input 中提出的设计策略迁移任务，开头即给出推荐设计策略或策略优先级，不能用“综上”“总体来看”“可以从多个方面考虑”等泛泛开场。
2. output 必须紧扣“机理到设计策略迁移”任务，不要答成普通机理解释、性能提升路径、实验方案或泛泛优化建议。回答重点应是“已知机理 M -> 可调变量 -> 设计策略 -> 目标性能路径 -> 适用边界与验证”。
3. 如果 input 或 chainofThought 没有明确已知机理、目标性能、可调变量或可迁移设计空间，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行生成设计策略。
4. 必须给出明确的设计策略，而不是只重复机制解释。每条策略都应说明要调控什么变量、为什么该变量对应已知机理、预期通过什么路径影响目标性能。
5. 每个关键判断都必须绑定具体机理、变量、设计动作和性能结果，不能只写“优化结构”“调控界面”“增强活性”“提升稳定性”“改善传输”等空泛表达。
6. 机制迁移必须有边界。output 必须说明该策略适用于哪些结构、组分、反应条件、性能目标或应用场景，不能把特定体系中的机理直接写成普适设计规律。
7. 如果策略可能同时带来正向作用和副作用，output 必须明确说明折中关系。例如增强活性可能损害稳定性，提高传输可能影响结构完整性，增加活性位点可能引入副反应。
8. 如果存在多个策略，必须给出优先级及理由。优先级理由应基于机理对应性、变量可控性、风险大小、验证可行性或对目标性能的直接影响，不能只写“因此优先推荐”。
9. 后续验证必须说明验证目标和成功信号，不能只罗列表征、测试或计算方法。例如应说明该方法用于验证机制是否被增强、变量是否被成功调控、目标性能是否按预期变化或副作用是否可控。
10. output 应按清晰顺序组织，建议采用“设计策略结论 -> 机制依据 -> 可调变量 -> 性能路径 -> 策略优先级 -> 风险边界 -> 验证方式”的结构，避免把结论、机制、风险和验证混在一起。
11. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“可实现性能优化”等。若表达意义，必须落到具体机制、变量、性能或应用边界上。
12. 不要为了显得完整而强行生成多个策略。如果 input 和 chainofThought 只支持一个主要策略，应集中写清楚该策略；如果证据不足，应在 missing_information 或 applicability_boundary 中说明。
13. 不要生成完整实验方案；本步骤输出的是设计策略迁移结果和验证方向，不是详细操作流程。
14. 不要引入 input 和 chainofThought 中没有出现的新机制、新变量、新数值、新材料、新设计方向或新性能结论。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该机制成立的条件下”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“机理表征表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“基于机制 M，优先采用 A 设计策略。该策略的核心不是单纯提高某一指标，而是通过调控变量 C 和 D 来增强/抑制 E 过程，从而改善目标性能 Z。A 策略优先于 B 策略，是因为它与 M 的对应关系更直接，且更容易通过 R 表征和 S 性能测试验证；B 策略可作为补充，但需要关注 G 副作用。该迁移判断仅适用于具备 F 条件的体系，若结构环境、反应条件或目标性能发生变化，需要重新验证机制 M 是否仍然主导性能变化。后续应通过 H 表征确认变量 C/D 是否被调控，通过 I 测试判断 Z 是否按预期改善，并通过 J 稳定性或计算验证排查 G 风险。”

请按以下 JSON 输出：

{
  "cot_type": "机理到设计策略迁移 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少已知机理、目标性能、可调变量、迁移对象、边界条件或验证依据"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "source_mechanism": "用于迁移的已知机理 M",
    "target_performance": "希望改善或调控的目标性能 Z",
    "recommended_design_strategies": [
      {
        "strategy": "推荐设计策略",
        "target_variables": ["应调控的变量"],
        "mechanism_basis": "该策略对应的机制依据，必须说明变量如何映射到已知机理",
        "expected_performance_pathway": "变量如何通过机制通道影响目标性能",
        "potential_risks": ["潜在副作用、折中关系或限制"]
      }
    ],
    "priority_order": [
      {
        "strategy": "策略名称",
        "priority": "优先 / 辅助 / 备选",
        "reason": "优先级理由，必须绑定机理对应性、变量可控性、风险或验证可行性"
      }
    ],
    "validation_methods": [
      {
        "method": "实验、表征、测试或计算方法",
        "validation_target": "验证哪个机制、变量、性能路径或副作用",
        "success_signal": "什么结果说明策略有效或提示策略不成立"
      }
    ],
    "applicability_boundary": [
      "策略适用的体系、结构、条件、性能目标、应用边界或不确定性"
    ],
    "fallback_or_next_iteration": [
      "如果首选策略效果不足，下一步如何调整；必须基于已有机制和变量，不得新增无依据方向"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留机制、变量、性能指标、验证方法或边界；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_mechanism_to_design_task": true,
    "has_source_mechanism": true,
    "has_target_performance": true,
    "has_design_strategy": true,
    "does_not_only_repeat_mechanism": true,
    "has_mechanism_basis": true,
    "has_target_variables": true,
    "links_strategy_to_performance": true,
    "has_priority_order_when_multiple_strategies": true,
    "has_applicability_boundary": true,
    "mentions_specific_risks": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
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
