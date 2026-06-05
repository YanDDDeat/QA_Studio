你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“实验方案生成 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
实验方案生成 CoT

生成要求：
1. output 必须直接回答 input 中提出的实验方案设计任务，开头即说明实验目标和总体方案，不要用“综上”“总体来看”“可以从多个方面开展”等泛泛开场。
2. output 必须紧扣“实验方案生成”任务，不要答成普通机理解释、性能提升路径、候选优选或泛泛优化建议。回答重点应是“实验目标 -> 变量与对照 -> 分阶段实验 -> 表征/测试 -> 成功与淘汰判据 -> 风险与迭代”。
3. 如果 input 或 chainofThought 没有明确实验目标、研究对象、可调变量、评价指标、必要对照或验证方法，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行生成完整实验方案。
4. output 必须是可执行的实验方案，但不要写成详细操作规程。应明确分组逻辑、变量筛选顺序、评价指标和判定规则，不需要写逐步称量、仪器参数、操作时长等 input 和 chainofThought 中没有提供的细节。
5. 实验分组必须服务于 input 的目标。对照组应按任务需要设置，不能机械加入无关的空白对照、暗对照、阳性组或失败组；每个组都必须说明条件、目的、评价指标和保留/淘汰规则。
6. 每个关键实验组都必须绑定具体问题：验证哪个变量、排除哪个干扰、确认哪个机制、比较哪个性能或识别哪个失败风险，不能只写“用于对比”“用于验证效果”等空泛表述。
7. 变量筛选必须有顺序和理由。优先先筛选最影响目标性能或风险最大的变量，再做组合验证；如果变量之间存在耦合，应说明为什么不能只做单因素结论。
8. 表征方法和性能测试必须说明验证目标和成功信号，不能只罗列方法名称。例如应说明该方法验证结构是否形成、界面是否改善、目标性能是否提升、稳定性是否达标或副反应是否被抑制。
9. 成功判据、失败判据和回退条件必须具体到结构、性能、稳定性、安全性、可重复性、对照差异或风险信号，不能只写“性能较好”“结果稳定”“需要进一步优化”。
10. 风险控制策略必须对应 input 或 chainofThought 中已有的失败条件、副作用或不确定性，说明如何规避、识别或淘汰，不能新增无依据风险。
11. output 应按清晰顺序组织，建议采用“总体实验策略 -> 实验分组 -> 变量筛选计划 -> 表征与测试 -> 成功/淘汰判据 -> 风险控制 -> 迭代计划 -> 适用边界”的结构，避免把分组、目的、测试和判据混在一起。
12. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“系统开展实验验证”等。若表达方案价值，必须落到具体目标、变量、判据或风险控制上。
13. 不要为了显得完整而强行生成过多实验组或变量。如果 input 和 chainofThought 只支持有限变量，应围绕这些变量设计方案；证据不足时，应在 missing_information 或 boundary_conditions 中说明。
14. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新材料、新实验条件、新测试指标或新结论。
15. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把实验方案写成验证确定因果，应保留“用于判断”“用于筛查”“需要进一步确认”等限定表达。
16. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
17. output 应完成证据内化，不要出现“根据已有数据”“结果显示”“实验表明”“数据说明”等证据过程表达。
18. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该实验方案应围绕 X 目标展开，先建立 A 基准组确认原始体系表现，再设置 B 变量筛选组判断关键调控因素对 Z 性能的影响，最后用 C 组合验证组确认最有效策略是否稳定成立。分组中，A 组用于提供基准对照，B 组用于比较变量 Y 的不同水平或条件，C 组用于验证优选变量组合；每组都应以 P 性能、Q 结构信号和 R 稳定性/风险信号作为判据。若 B 组出现 S 失败信号，应回退调整 Y 或排除该条件；若 C 组仅提升单一指标但引入 T 副作用，则不应进入后续优化。该方案只适用于当前 X 体系和已给定变量范围，超出该设计空间需要重新设定对照和评价指标。”

请按以下 JSON 输出：

{
  "cot_type": "实验方案生成 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少实验目标、研究对象、可调变量、评价指标、对照逻辑、验证方法或风险条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终实验方案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "experimental_goal": "实验要解决的具体问题或要验证的目标性能",
    "overall_experimental_strategy": "总体实验设计策略和阶段划分",
    "experimental_groups": [
      {
        "group_name": "实验组或对照组名称",
        "group_type": "baseline / blank_control / dark_control / positive_condition / failure_control / variable_screening / combined_validation / other_relevant_control",
        "conditions": ["该组的关键实验条件，必须来自 input 或 chainofThought"],
        "purpose": "该组用于验证什么变量、排除什么干扰、比较什么性能或识别什么风险",
        "evaluation_metrics": ["该组需要观察或测试的指标"],
        "decision_rule": "如何根据结果判断保留、淘汰、回退或进入下一阶段"
      }
    ],
    "variable_screening_plan": [
      {
        "stage": "筛选阶段名称",
        "variable": "本阶段筛选的变量",
        "screening_reason": "为什么优先筛选该变量",
        "levels_or_conditions": ["变量水平或实验条件；不得新增无依据条件"],
        "fixed_conditions": ["本阶段保持不变的条件"],
        "evaluation_metrics": ["本阶段评价指标"],
        "decision_rule": "进入下一阶段、回退或淘汰的判据"
      }
    ],
    "characterization_and_tests": [
      {
        "method": "表征、测试或计算方法",
        "validation_target": "该方法验证哪个结构、机制、性能、稳定性、对照差异或风险",
        "success_signal": "什么信号说明实验有效或该条件应被保留"
      }
    ],
    "success_criteria": [
      "判断实验成功的具体判据，必须对应目标性能、结构信号、稳定性、可重复性或风险抑制"
    ],
    "rejection_or_failure_criteria": [
      "判断实验失败、淘汰条件或需要回退优化的判据"
    ],
    "risk_control_strategy": [
      "针对已知失败条件、副作用或不稳定性的规避、识别和验证策略"
    ],
    "iteration_plan": [
      "如果某阶段不达标，下一轮如何调整变量、对照或验证方式；不得新增无依据方向"
    ],
    "boundary_conditions": [
      "该实验方案成立的体系、变量范围、测试范围、适用条件或不确定性"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留图表、章节、变量、数值、单位或条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_experimental_plan_task": true,
    "is_detailed_experimental_plan": true,
    "has_experimental_goal": true,
    "has_overall_strategy": true,
    "has_experimental_groups": true,
    "groups_are_relevant_to_input": true,
    "has_control_groups_when_needed": true,
    "has_variable_screening_plan": true,
    "screening_order_has_reason": true,
    "matches_methods_to_validation_targets": true,
    "validation_methods_have_targets_and_success_signals": true,
    "has_success_criteria": true,
    "has_rejection_or_failure_criteria": true,
    "has_risk_control_strategy": true,
    "has_iteration_plan": true,
    "keeps_boundary_conditions": true,
    "does_not_repeat_chain": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
