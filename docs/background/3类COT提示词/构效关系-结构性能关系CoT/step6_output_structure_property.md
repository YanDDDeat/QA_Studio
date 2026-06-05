你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“构效关系 / 结构-性能关系 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
构效关系 / 结构-性能关系 CoT

生成要求：
1. output 必须直接回答 input 中提出的结构-性能关系归纳任务，开头即给出“结构/组成变量 Y 与性能指标 Z 的关系判断”，不能用“综上”“总体来看”“可以从多个方面分析”等泛泛开场。
2. output 必须紧扣“构效关系 / 结构-性能关系”任务，不要答成候选优选、性能提升路径、实验方案或泛泛机理解释。回答重点应是“同系列样品 -> 主变量变化 -> 性能响应趋势 -> 主导结构因素 -> 规则边界”。
3. 如果 input 或 chainofThought 没有明确样品系列、结构/组成变量、性能指标或可归纳趋势，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行总结构效规律。
4. 必须明确说明样品是否属于可比较系列，以及主要变量是什么。若变量不单一或存在多因素耦合，output 必须说明该规则只能作为趋势性判断，不能写成单变量确定因果。
5. 必须明确给出变量 Y 的变化方向和性能 Z 的响应趋势，例如升高、降低、先升后降、存在最优点、平台期、阈值效应或异常点，不能只写“二者有关”“存在影响”“表现更好”。
6. 每个关键结论都必须绑定具体结构因素、性能指标和趋势方向，不能只写“优化结构”“改善性能”“增强稳定性”“构效关系明显”等空泛表达。
7. 必须说明主导性能变化的结构因素，并解释该结构因素如何影响传输、界面、活性位点、缺陷、孔结构、晶相、稳定性、反应过程或其他与性能相关的机制通道。
8. 如果存在异常点、最优点或非线性趋势，output 必须说明可能原因；如果没有足够证据解释，应明确写“异常点原因需要进一步验证”，不要补写无依据机制。
9. 必须保留适用边界和不确定性，说明该规则适用于哪个样品系列、变量范围、测试条件或体系边界，不能把特定系列规律写成普适规律。
10. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于确认结构变量变化、验证性能趋势、解释异常点或排除其他变量干扰。
11. output 应按清晰顺序组织，建议采用“关系结论 -> 变量与性能趋势 -> 主导结构因素/机制解释 -> 异常点或最优点 -> 适用边界 -> 验证方式”的结构，避免把结论、原因、风险和验证混在一起。
12. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“说明材料具有优异性能”等。若表达意义，必须落到具体结构变量、性能指标或应用边界上。
13. 不要为了显得完整而强行生成复杂规律。如果证据只支持简单单调趋势，应集中写清楚该趋势；如果证据不足以判断趋势，应在 missing_information 或 applicability_boundary 中说明。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新性能指标或新性能结论。
15. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该系列中”“在该变量范围内”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“对比实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“在该系列样品中，结构/组成变量 Y 是影响性能 Z 的关键因素。随着 Y 从 A 向 B 变化，Z 呈现升高/降低/先升后降/平台期/最优点趋势，说明 Y 主要通过 M 结构或过程通道影响 Z。若 Y 继续偏离合适范围，可能出现 N 副作用或异常表现，使 Z 不再继续改善。因此，该结构-性能规则只适用于 Q 样品系列、变量范围或测试条件内，不能直接外推到其他体系。后续应通过 R 表征确认 Y 的结构变化，通过 S 性能测试复核 Z 的趋势，并通过 T 对照或计算排除其他变量干扰。”

请按以下 JSON 输出：

{
  "cot_type": "构效关系 / 结构-性能关系 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少样品系列、结构变量、性能指标、趋势证据或边界条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "comparability_statement": "样品是否属于可比较系列，以及是否存在多变量耦合或干扰",
    "structure_property_rule": "核心结构-性能关系规则",
    "variable_trend": "结构/组成变量的变化方向或范围",
    "performance_trend": "性能指标的变化趋势",
    "dominant_structure_factor": "主导性能变化的结构因素",
    "mechanism_to_performance_link": "结构因素如何通过具体机制通道影响性能",
    "anomaly_or_optimum_explanation": "异常点、最优点、平台期或非线性趋势解释；证据不足时说明需要进一步验证",
    "applicability_boundary": [
      "该规则适用的样品系列、变量范围、测试条件、体系边界或不确定性"
    ],
    "validation_methods": [
      {
        "method": "表征、性能测试、对照或计算方法",
        "validation_target": "验证哪个结构变量、性能趋势、机制解释、异常点或干扰因素",
        "success_signal": "什么结果支持该结构-性能关系成立"
      }
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留样品系列、变量、性能指标、趋势、异常点或条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_structure_property_task": true,
    "has_comparability_statement": true,
    "has_structure_property_rule": true,
    "has_variable_trend": true,
    "has_performance_trend": true,
    "identifies_dominant_structure_factor": true,
    "links_structure_factor_to_performance": true,
    "handles_anomaly_or_optimum": true,
    "keeps_boundary_conditions": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "does_not_turn_into_candidate_selection": true,
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
