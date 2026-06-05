你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“反事实结构改造 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
反事实结构改造 CoT

生成要求：
1. output 必须直接回答 input 中提出的反事实结构改造任务，开头即说明“将结构因素 A 替换/调控为 B 后，目标性能 Z 更可能提升、下降、出现折中或仍不确定”，不能用“综上”“总体来看”“可以从多个方面分析”等泛泛开场。
2. output 必须紧扣反事实结构改造任务，不要答成普通性能提升、实验方案生成或泛泛结构优化建议。回答重点应是“结构改造前后差异 -> 机制变化 -> 性能变化方向 -> 风险与验证”。
3. 如果 input 或 chainofThought 没有明确原结构因素 A、替换/调控因素 B、目标性能 Z 或可支撑的机制依据，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要补写无依据预测。
4. 性能变化方向必须与证据强度匹配。若证据只支持趋势或相关性，应写“可能提升/可能下降/存在折中/需要验证”，不能写成确定因果；若证据不足以判断方向，应明确输出“不确定”。
5. 每个关键判断都必须绑定具体对象、结构差异、机制通道和性能结果，不能只写“改善结构”“增强性能”“调控电子结构”“提高稳定性”等空泛表达。
6. 核心原因必须写成清楚的机制链条：B 与 A 的关键差异是什么，该差异如何影响结构、电子、界面、传输、吸附、反应过程或稳定性，进而为什么会影响目标性能 Z。
7. 如果结构替换会带来正负并存的影响，output 必须明确说明折中关系。例如某一性能可能提升，但稳定性、传输、选择性、加工性或安全性可能受到影响，不能只保留有利结论。
8. 潜在副作用或风险必须具体到结构、组分、界面、反应过程、传输路径、稳定性或应用场景层面，不能只写“存在一定风险”“可能需要进一步优化”。
9. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于确认结构替换是否发生、机制通道是否改变、目标性能是否按预测方向变化，或副作用是否出现。
10. output 应按清晰顺序组织，建议采用“预测结论 -> 结构差异 -> 机制影响 -> 性能后果 -> 副作用/边界 -> 验证方式”的结构，避免把结论、原因、风险和验证混在一起。
11. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“可实现性能优化”等。若表达意义，必须落到具体性能、机制或应用边界上。
12. 不要为了显得完整而强行生成多个改造方向。若 input 只提出一个 A 到 B 的反事实改造，应集中回答该改造；若存在多个备选改造，必须逐一说明各自依据和不确定性。
13. 不要生成完整实验方案；本步骤输出的是反事实结构改造判断和验证方向，不是详细操作流程。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新材料、新候选结构或新实验条件。
15. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
16. output 应完成证据内化，不要出现“对照实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
17. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“将结构因素 A 替换/调控为 B 后，目标性能 Z 更可能提升/下降/出现折中/仍不确定。关键原因是 B 相比 A 改变了 M 结构或过程，使 N 机制通道发生变化，从而影响 Z；但这种改造也可能带来 P 副作用，例如影响稳定性、传输、选择性、加工性或安全性。因此，该判断只适用于 Q 条件或当前设计空间内，不能直接外推到其他体系。后续应通过 R 表征确认结构替换及其作用，通过 S 性能测试判断 Z 是否按预测方向变化，并通过 T 对照或稳定性评价排查 P 风险。”

请按以下 JSON 输出：

{
  "cot_type": "反事实结构改造 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少原结构因素、替换因素、目标性能、机制依据或验证条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "counterfactual_change": {
      "original_factor": "原结构因素 A",
      "modified_factor": "替换/调控因素 B",
      "target_performance": "目标性能 Z"
    },
    "predicted_performance_change": "提升 / 下降 / 折中 / 不确定",
    "core_reason": "性能变化的核心原因，必须写清楚 A 与 B 的差异及其机制后果",
    "affected_mechanism_or_property": [
      "被影响的结构、电子、界面、传输、吸附、反应过程、稳定性或其他机制因素"
    ],
    "mechanism_to_performance_link": "结构改造如何通过具体机制通道影响目标性能",
    "potential_side_effects": [
      "可能副作用、折中关系或风险，必须具体到结构、过程、性能或应用边界"
    ],
    "validation_methods": [
      {
        "method": "表征、测试、对照或计算方法",
        "validation_target": "验证哪个结构变化、机制影响、性能趋势或副作用",
        "success_signal": "什么结果支持该预测或提示该预测不成立"
      }
    ],
    "uncertainty_and_boundary": [
      "不确定性、适用条件、设计空间边界或需要重新验证的情况"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留结构因素、相似对照、性能趋势、机制或风险；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_counterfactual_task": true,
    "has_original_and_modified_factors": true,
    "has_target_performance": true,
    "has_predicted_performance_change": true,
    "has_core_reason": true,
    "links_structure_change_to_mechanism": true,
    "links_mechanism_to_performance": true,
    "mentions_specific_side_effects": true,
    "includes_validation_methods": true,
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
