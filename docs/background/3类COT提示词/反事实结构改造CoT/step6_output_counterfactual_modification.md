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
1. output 必须直接回答 input 中提出的反事实结构改造任务。
2. 必须给出性能变化方向：提升、下降、存在折中或不确定。
3. 必须说明核心原因，即 B 替代/调控 A 后如何影响结构、电子、界面、传输、吸附或稳定性。
4. 必须说明潜在副作用或风险。
5. 必须给出验证方法。
6. 必须保留不确定性和适用边界。
7. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制或新实验条件。
8. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果。
9. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
10. output 应完成证据内化，不要出现“对照实验表明”“根据已有数据”“结果显示”等证据过程表达。
11. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“将结构因素 A 替换/调控为 B 后，目标性能 Z 可能提升/下降/存在折中。主要原因是 B 会改变 M 过程，从而影响 N 性能通道；但该改造也可能带来 P 副作用。该判断适用于 Q 条件内，后续应通过 R 表征、S 性能测试和 T 对照样品验证。”

请按以下 JSON 输出：

{
  "cot_type": "反事实结构改造 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought",
  "output_elements": {
    "predicted_performance_change": "提升 / 下降 / 折中 / 不确定",
    "core_reason": "性能变化的核心原因",
    "affected_mechanism_or_property": [
      "被影响的机制、结构、电子、界面、传输、吸附或稳定性因素"
    ],
    "potential_side_effects": [
      "可能副作用或风险"
    ],
    "validation_methods": [
      {
        "method": "表征、测试、对照或计算方法",
        "validation_target": "验证哪个结构变化、机制影响或性能趋势",
        "success_signal": "什么结果支持该预测"
      }
    ],
    "uncertainty_and_boundary": [
      "不确定性、适用条件或边界"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留结构因素、相似对照、性能趋势、机制或风险；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "has_predicted_performance_change": true,
    "has_core_reason": true,
    "links_structure_change_to_mechanism": true,
    "mentions_side_effects": true,
    "includes_validation_methods": true,
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