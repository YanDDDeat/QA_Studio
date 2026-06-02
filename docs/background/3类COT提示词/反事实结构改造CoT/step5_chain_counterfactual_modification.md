你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“反事实结构改造 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、mechanism_or_explanation、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
反事实结构改造 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的性能变化预测。
3. 必须识别原结构因素 A 的作用。
4. 必须分析拟改造因素 B 与 A 的差异，例如电子效应、空间位阻、极性、配位能力、离子半径、界面作用、孔结构、疏水性、缺陷稳定性等。
5. 必须推断 B 替代或调控 A 后对结构、电子、界面、传输、吸附或稳定性的影响。
6. 必须连接这些影响与目标性能 Z。
7. 必须判断性能变化方向：提升、下降、存在折中或不确定。
8. 必须说明潜在副作用或风险。
9. 必须给出验证建议，例如结构表征、性能测试、对照样品、计算模拟或原位表征。
10. 不能引入文献没有支撑的新变量、新机制或新性能结论。
11. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
12. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
13. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
14. 不要在 chainofThought 中用括号标注证据来源。
15. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
16. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据转写为结构事实、变量差异、机制影响和专业判断。
17. 不要使用“根据已有数据”“对照实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
18. 不要生成最终 output。

推荐推理步骤结构：
1. 识别原结构因素 A 及其作用。
2. 分析拟改造因素 B 与 A 的关键差异。
3. 推断 B 对结构、电子、界面、传输或吸附过程的影响。
4. 连接这些影响与目标性能 Z。
5. 预测性能变化方向，并保留不确定性。
6. 判断可能的副作用或折中关系。
7. 给出验证建议。
8. 说明适用边界和后续优化方向。

请按以下 JSON 输出：

{
  "cot_type": "反事实结构改造 CoT",
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
    "每条关键推理所依赖的文献信息，保留结构因素、相似对照、性能趋势、机制或风险；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、替换范围、测试条件、结构相似性或适用边界"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_original_structure_factor": true,
    "has_counterfactual_modification": true,
    "compares_A_and_B": true,
    "links_structure_change_to_mechanism": true,
    "predicts_performance_direction": true,
    "keeps_uncertainty": true,
    "mentions_side_effects": true,
    "includes_validation_methods": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}