你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“实验条件 / 制备工艺优化 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
实验条件 / 制备工艺优化 CoT

生成要求：
1. output 必须直接回答 input 中提出的工艺优化任务，开头即给出推荐工艺窗口、最佳条件或优化方向，不能用“综上”“总体来看”“可以从多个方面优化”等泛泛开场。
2. output 必须紧扣“实验条件 / 制备工艺优化”任务，不要答成实验方案生成、配方设计、性能提升路径或泛泛工艺建议。回答重点应是“工艺变量 -> 结构/过程响应 -> 性能趋势 -> 推荐窗口 -> 过低/过高副作用 -> 验证方式”。
3. 如果 input 或 chainofThought 没有明确工艺变量、目标性能、性能趋势、结构/过程变化或可判断的边界条件，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行给出工艺窗口。
4. 必须给出推荐工艺窗口、最佳条件或合理优化方向。若没有明确数值范围，不能编造具体数值，只能使用低/中/高、偏低/适中/偏高、相对窗口或“需要先补充范围验证”的表述。
5. 每个关键判断都必须绑定具体工艺变量、结构/过程变化、性能指标和趋势方向，不能只写“优化工艺”“改善结构”“提高性能”“条件更合适”等空泛表达。
6. 必须说明该窗口成立的核心依据：工艺变量如何影响形貌、晶相、缺陷、孔结构、界面、传输、反应过程、稳定性或其他结构/过程因素，并进一步影响目标性能。
7. 必须分别说明过低条件和过高条件可能导致的问题。如果 input 和 chainofThought 只支持其中一侧风险，应明确写出另一侧风险证据不足，不要补写无依据副作用。
8. 如果性能趋势是先升后降、平台期、阈值效应或非线性变化，output 必须说明趋势含义和可能的结构/过程原因；如果只能判断相关性，应保留限定表达。
9. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于确认目标结构是否形成、工艺副作用是否被抑制、性能是否稳定达到窗口判断，或过低/过高条件是否被排除。
10. output 应按清晰顺序组织，建议采用“推荐窗口 -> 核心依据 -> 过低风险 -> 过高风险 -> 验证方式 -> 适用边界”的结构，避免把窗口、原因、风险和验证混在一起。
11. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“进一步优化工艺参数”等。若表达方案价值，必须落到具体工艺变量、结构响应、性能指标或风险控制上。
12. 不要为了显得完整而强行生成多个工艺变量或优化方向。如果 input 和 chainofThought 只支持一个变量，应集中写清楚该变量；证据不足时，应在 missing_information 或 boundary_conditions 中说明。
13. 不要生成完整实验方案；本步骤输出的是工艺窗口判断和验证方向，不是详细操作流程或分组方案。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新材料、新实验条件、新测试指标或新结论。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该条件范围内”“需要进一步验证”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该体系应优先将工艺变量 Y 控制在 A 条件或 A-B 窗口内。该窗口的依据是 Y 在该范围内能够促进 M 结构/过程形成，同时避免 N 副作用，使目标性能 Z 更稳定地改善。若 Y 偏低，可能导致 P 问题，例如目标结构形成不足、传输受限或反应不充分；若 Y 偏高，可能引发 Q 问题，例如结构破坏、副反应增加、稳定性下降或加工性变差。后续应通过 R 表征确认 M 是否形成，通过 S 性能测试判断 Z 是否稳定改善，并通过 T 稳定性或对照验证排除过低/过高条件带来的副作用。该判断只适用于当前体系和已给定变量范围，超出该范围需要重新筛选。”

请按以下 JSON 输出：

{
  "cot_type": "实验条件 / 制备工艺优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少工艺变量、变量范围、目标性能、性能趋势、结构/过程响应、过低/过高风险或验证条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "process_variable": "需要优化的工艺变量",
    "recommended_process_window": "推荐工艺窗口、最佳条件或优化方向；无明确数值时不得编造具体数值",
    "core_rationale": "支持该窗口的核心依据，必须说明工艺变量如何影响结构/过程并进一步影响目标性能",
    "structure_or_process_response": [
      "工艺变量变化引起的形貌、晶相、缺陷、孔结构、界面、传输、反应过程、稳定性或其他响应"
    ],
    "performance_trend": "目标性能随工艺变量变化的趋势，例如升高、降低、先升后降、平台期、阈值效应或不确定",
    "low_condition_risk": {
      "risk": "过低条件的风险或副作用；证据不足时说明缺口",
      "affected_structure_or_performance": "该风险影响的结构、过程或性能"
    },
    "high_condition_risk": {
      "risk": "过高条件的风险或副作用；证据不足时说明缺口",
      "affected_structure_or_performance": "该风险影响的结构、过程或性能"
    },
    "validation_methods": [
      {
        "method": "表征、性能测试、稳定性验证、对照或计算方法",
        "validation_target": "验证哪个工艺窗口、结构/过程响应、性能趋势或副作用",
        "success_signal": "什么结果支持该工艺窗口有效"
      }
    ],
    "boundary_conditions": [
      "适用条件、体系边界、变量范围、测试条件、不确定性或需要重新验证的情况"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留图表、章节、变量、数值、单位或条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_process_optimization_task": true,
    "does_not_repeat_chain": true,
    "has_process_variable": true,
    "has_recommended_process_window": true,
    "avoids_fabricated_conditions": true,
    "has_core_rationale": true,
    "links_process_to_structure_or_process_response": true,
    "links_response_to_performance": true,
    "has_performance_trend": true,
    "mentions_low_or_high_condition_side_effects": true,
    "low_high_risks_are_specific": true,
    "includes_validation_methods": true,
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
