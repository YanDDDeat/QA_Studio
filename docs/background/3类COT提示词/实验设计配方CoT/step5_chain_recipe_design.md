你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“实验设计配方 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output，也不要直接给出完整配方表。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、recipe_components、process_or_recipe_information、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
实验设计配方 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的配方矩阵和筛选方案。
3. 必须明确配方设计目标和评价指标。
4. 必须识别关键组分及其作用。
5. 必须区分配方变量和工艺变量；本类推理重点是组分比例、浓度、负载量、添加剂含量、溶剂比例、固含量等配方因素。
6. 必须说明为什么需要基础配方、单因素梯度和组合优化配方。
7. 必须根据已有证据设定安全变量范围；没有数值范围时，只能使用低/中/高梯度或条件性范围，不能编造具体数值。
8. 必须说明每个变量变化可能影响的性能、结构或工艺适配性。
9. 必须说明过量添加、比例失衡、相分离、副反应、稳定性下降或可加工性变差等风险。
10. 必须推导成功判据和淘汰判据。
11. 必须说明下一轮优化如何根据第一轮结果调整配方。
12. 不能引入文献没有支撑的新组分、新比例、新浓度、新机制或新风险。
13. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
14. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
15. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
16. 不要在 chainofThought 中用括号标注证据来源。
17. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
18. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何筛选得到，而要把证据转写为配方事实、组分作用、变量关系、条件约束和专业判断。
19. 不要使用“根据已有数据”“配方筛选实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
20. 不要生成最终配方表，不要写 output。

推荐推理步骤结构：
1. 明确配方设计目标和成功评价指标。
2. 识别基础配方、关键组分及其功能角色。
3. 区分主变量、辅助变量和固定条件。
4. 设定可接受的变量范围或低/中/高梯度。
5. 规划单因素梯度，判断每个变量要验证的问题。
6. 规划组合优化逻辑，避免变量混杂。
7. 推导成功判据、淘汰判据和风险控制逻辑。
8. 给出下一轮精细化优化方向。

请按以下 JSON 输出：

{
  "cot_type": "实验设计配方 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "chainofThought": [
    "步骤 1：...",
    "步骤 2：...",
    "步骤 3：...",
    "步骤 4：...",
    "步骤 5：...",
    "步骤 6：...",
    "步骤 7：...",
    "步骤 8：..."
  ],
  "evidence_used": [
    "每条关键推理所依赖的文献信息，保留组分、比例、浓度、单位、性能趋势或风险；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的配方体系、组分范围、工艺条件、测试条件或适用范围"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_recipe_goal": true,
    "has_key_components_and_roles": true,
    "distinguishes_recipe_variables_from_process_variables": true,
    "has_variable_ranges_or_gradients": true,
    "plans_single_factor_screening": true,
    "plans_combination_optimization": true,
    "has_success_and_rejection_criteria": true,
    "handles_overdose_or_imbalance_risks": true,
    "avoids_fabricated_ratios": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}