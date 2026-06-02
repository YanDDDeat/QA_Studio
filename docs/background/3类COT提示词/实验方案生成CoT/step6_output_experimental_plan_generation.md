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
1. output 必须直接回答 input 中提出的实验方案设计任务。
2. output 必须是详细、可执行的实验方案，而不是只给原则性建议。
3. 必须先给出总体实验策略，说明实验如何分阶段推进。
4. 必须给出实验分组和对照设置，包括基准组、空白/暗对照、成功条件组、失败条件对照和变量筛选组。
5. 必须说明每一组实验的条件、目的、评价指标和判定规则。
6. 必须给出关键变量筛选顺序，优先采用分阶段、单因素筛选，再进行组合验证。
7. 必须说明表征方法和性能测试方法分别验证什么。
8. 必须给出判断实验成功的具体判据，以及淘汰或回退条件。
9. 必须说明如何规避或验证 input 中列出的失败条件和风险。
10. 必须保留适用边界和不确定性，不能把特定体系方案写成普适流程。
11. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制或新实验条件。
12. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果。
13. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
14. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
1. 总体策略：说明先验证基准可行条件，再分阶段筛选变量，最后进行组合优化和稳定性验证。
2. 实验分组：列出每个组的条件、目的、评价指标和判定规则。
3. 变量筛选：按变量优先级设计筛选阶段，例如溶剂、波长、功率、时间、浓度、温度、后处理条件等。
4. 表征与测试：说明每种表征和测试对应的验证目标。
5. 成功判据：给出结构确证、性能达标、无明显副反应、稳定性满足要求等判据。
6. 失败条件处理：说明如何验证、规避或淘汰失败条件。
7. 迭代优化：说明如果某阶段不达标，下一步如何调整。

请按以下 JSON 输出：

{
  "cot_type": "实验方案生成 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终实验方案，直接回答 input，不重复 chainofThought",
  "output_elements": {
    "overall_experimental_strategy": "总体实验设计策略和阶段划分",
    "experimental_groups": [
      {
        "group_name": "实验组或对照组名称",
        "group_type": "baseline / blank_control / dark_control / positive_condition / failure_control / variable_screening / combined_validation",
        "conditions": ["该组的关键实验条件"],
        "purpose": "该组用于验证什么问题",
        "evaluation_metrics": ["该组需要观察或测试的指标"],
        "decision_rule": "如何根据结果判断保留、淘汰或进入下一阶段"
      }
    ],
    "variable_screening_plan": [
      {
        "stage": "筛选阶段名称",
        "variable": "本阶段筛选的变量",
        "levels_or_conditions": ["变量水平或实验条件"],
        "fixed_conditions": ["本阶段保持不变的条件"],
        "evaluation_metrics": ["本阶段评价指标"],
        "decision_rule": "进入下一阶段或淘汰的判据"
      }
    ],
    "characterization_and_tests": [
      {
        "method": "表征、测试或计算方法",
        "validation_target": "该方法验证什么",
        "success_signal": "什么信号说明实验有效"
      }
    ],
    "success_criteria": [
      "判断实验成功的具体判据"
    ],
    "rejection_or_failure_criteria": [
      "判断实验失败、淘汰条件或需要回退优化的判据"
    ],
    "risk_control_strategy": [
      "针对已知失败条件、副作用或不稳定性的规避和验证策略"
    ],
    "iteration_plan": [
      "如果某阶段不达标，下一轮如何调整变量或补充验证"
    ],
    "boundary_conditions": [
      "该实验方案成立的体系、条件、测试范围或适用边界"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留图表、章节、变量、数值、单位或条件；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "is_detailed_experimental_plan": true,
    "has_overall_strategy": true,
    "has_experimental_groups": true,
    "has_control_groups": true,
    "has_variable_screening_plan": true,
    "matches_methods_to_validation_targets": true,
    "has_success_criteria": true,
    "has_rejection_or_failure_criteria": true,
    "has_risk_control_strategy": true,
    "has_iteration_plan": true,
    "keeps_boundary_conditions": true,
    "does_not_repeat_chain": true,
    "does_not_add_new_claims": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true
  }
}