你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“实验方案生成 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output，也不要直接写完整实验方案。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、cot_type_judgement、recommended_next_action>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
实验方案生成 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中“完整实验方案”的形成。
3. 必须明确实验目标，例如提升转化率、提升分离产率、获得高纯度产物、验证结构或评估稳定性。
4. 必须识别当前体系短板和已知风险，例如产率低、半衰期短、逆向转化、降解、分离困难或无效条件。
5. 必须识别可调控变量，并按变量类型分层，例如溶剂、波长、功率、时间、浓度、温度、后处理和反溶剂。
6. 必须说明为什么需要设置对照组，包括原料对照、暗对照、空白/基准对照、失败条件对照和候选条件对照。
7. 必须说明变量筛选应采用分阶段、单因素优先的逻辑，避免多变量同时变化导致归因困难。
8. 必须把每类变量与评价指标对应起来，例如转化率、分离产率、半衰期、纯度、结构表征和稳定性。
9. 必须说明表征和测试方法各自验证什么，例如 UV-Vis 验证光异构化趋势，NMR 验证结构和纯度，IR/Raman 验证振动指纹，半衰期测试验证稳定性。
10. 必须形成成功判据的推理依据，例如无降解、转化率提高、分离产率提高、结构可确证、稳定性满足最低要求。
11. 必须说明风险规避逻辑，例如避光、快速后处理、避免过高功率、避免无效溶剂、验证过低功率不足等。
12. 不能引入文献没有支撑的新变量、新机制或新实验条件。
13. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
14. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
15. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“图 2a”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
16. 不要在 chainofThought 中用括号标注证据来源，例如“（图 2a）”“（文献报道 8.3%）”“（见表 1）”。
17. 可以使用 input 中已经给出的数值、条件和现象，但表达方式应改为任务事实，例如“当前分离产率较低，仅为 8.3%”，不要写“文献报道仅 8.3%”。
18. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
19. chainofThought 还必须完成“证据内化”：不要描述证据来自哪里或如何筛选得到，而要把证据转写为体系本身的事实、变量关系、条件约束和专业判断。
20. 不要使用“根据已有数据”“根据已有筛选”“筛选实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”“已有案例证明”等证据过程表达。
21. 推荐使用内化表达，例如：
    - 不写：“溶剂筛选实验表明，DMSO 是有效溶剂。”
    - 改写：“在该体系中，DMSO 更适合作为异构化反应介质，而水主要受限于后续分离，甲醇中的异构化响应较弱。”
    - 不写：“功率筛选结果显示 10 W 会破坏骨架。”
    - 改写：“过高光功率存在骨架破坏风险，过低功率则不足以维持高比例目标产物。”
22. 不要生成最终实验方案，不要写 output。

推荐推理步骤结构：
1. 明确实验方案要解决的核心目标和评价指标。
2. 识别当前体系的主要短板和必须规避的失败条件。
3. 将可调控变量分层，并确定优先筛选顺序。
4. 设计对照逻辑，说明每类对照用于排除或验证什么。
5. 规划分阶段变量筛选思路，避免多因素混杂。
6. 将表征方法和性能测试指标匹配到具体验证目标。
7. 推导成功判据和淘汰判据。
8. 说明风险规避、边界条件和下一轮迭代优化逻辑。

请按以下 JSON 输出：

{
  "cot_type": "实验方案生成 CoT",
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
    "每条关键推理所依赖的文献信息，保留变量、数值、单位、条件、图表或章节位置；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的实验条件、测试条件、材料体系或适用范围"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_experiment_goal": true,
    "has_current_shortcoming": true,
    "has_candidate_variables": true,
    "has_control_logic": true,
    "has_stagewise_screening_strategy": true,
    "matches_methods_to_validation_targets": true,
    "has_success_and_rejection_criteria": true,
    "has_risk_control_logic": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}