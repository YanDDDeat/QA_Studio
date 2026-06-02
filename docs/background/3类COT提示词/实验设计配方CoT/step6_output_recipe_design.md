你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“实验设计配方 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
实验设计配方 CoT

生成要求：
1. output 必须直接回答 input 中提出的配方设计任务。
2. output 必须给出可执行的基础配方、变量筛选逻辑和配方矩阵。
3. 必须说明每个关键组分的作用。
4. 必须给出单因素梯度和组合优化策略。
5. 如果 input 或 chainofThought 中有明确数值范围，应保留单位和条件。
6. 如果没有明确数值范围，不能编造具体比例或浓度；应使用低/中/高梯度、相对比例或条件性建议。
7. 必须说明每组配方要验证什么问题。
8. 必须给出评价指标、成功判据和淘汰判据。
9. 必须说明过量添加、比例失衡、相分离、副反应、稳定性下降或加工性变差等风险控制。
10. 必须给出下一轮优化方向。
11. 不要引入 input 和 chainofThought 中没有出现的新组分、新比例、新浓度、新机制或新实验条件。
12. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
13. output 应完成证据内化，不要出现“配方筛选实验表明”“根据已有数据”“结果显示”等证据过程表达。
14. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
1. 基础配方：列出固定组分和初始比例/条件。
2. 单因素梯度：逐一改变关键变量，说明每组验证目的。
3. 组合优化矩阵：在单因素筛选后组合最优区间。
4. 评价指标：说明每组配方测什么。
5. 成功与淘汰判据：说明保留、淘汰和进入下一轮的标准。
6. 风险控制：说明如何避免过量、副反应、相分离或稳定性下降。
7. 下一轮优化：根据结果继续细化比例或扩展变量。

请按以下 JSON 输出：

{
  "cot_type": "实验设计配方 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终配方设计与筛选方案，直接回答 input，不重复 chainofThought",
  "output_elements": {
    "base_recipe": {
      "description": "基础配方或基准配方",
      "fixed_components": ["固定组分及作用"],
      "initial_conditions": ["已有比例、浓度、处理条件；无明确数值时写条件性描述"]
    },
    "component_roles": [
      {
        "component": "组分名称",
        "role": "该组分的作用",
        "risk_if_too_low_or_too_high": "过低或过高的风险"
      }
    ],
    "single_factor_gradient": [
      {
        "variable": "单因素变量",
        "levels_or_range": ["具体水平、范围或低/中/高梯度"],
        "fixed_conditions": ["保持不变的配方或工艺条件"],
        "purpose": "该梯度用于验证什么",
        "evaluation_metrics": ["评价指标"],
        "decision_rule": "保留、淘汰或进入组合优化的判据"
      }
    ],
    "combination_optimization_matrix": [
      {
        "recipe_group": "组合优化组名称",
        "combined_variables": ["组合变量"],
        "design_logic": "为什么组合这些变量",
        "evaluation_metrics": ["评价指标"],
        "decision_rule": "判断是否优于基础配方的标准"
      }
    ],
    "success_criteria": [
      "判断配方成功的具体判据"
    ],
    "rejection_criteria": [
      "判断配方失败或淘汰的判据"
    ],
    "risk_control_strategy": [
      "针对过量、比例失衡、副反应、相分离、稳定性下降或加工性问题的控制策略"
    ],
    "next_iteration_plan": [
      "下一轮优化如何缩小范围、细化比例或增加验证"
    ],
    "boundary_conditions": [
      "该配方方案成立的体系、组分范围、测试条件或适用边界"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留组分、比例、浓度、单位、性能趋势或风险；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "is_actionable_recipe_design": true,
    "has_base_recipe": true,
    "has_component_roles": true,
    "has_single_factor_gradient": true,
    "has_combination_optimization_matrix": true,
    "has_success_criteria": true,
    "has_rejection_criteria": true,
    "handles_risks": true,
    "has_next_iteration_plan": true,
    "avoids_fabricated_ratios": true,
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