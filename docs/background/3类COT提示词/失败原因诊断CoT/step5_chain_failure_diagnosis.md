你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“失败原因诊断 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、failure_or_limitations、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
失败原因诊断 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的失败原因判断和修正建议。
3. 必须明确原始设计意图和预期正向作用。
4. 必须识别实际失败信号和失败程度。
5. 必须比较失败样品与成功样品、基准样品或对照样品之间的关键差异。
6. 必须把差异映射到可能失效环节，例如结构破坏、活性位点失效、传输受阻、界面恶化、相分离、副反应、过量添加、结晶失败、热/光/化学稳定性不足等。
7. 必须推断最可能的失败原因，并保留不确定性。
8. 必须提出修正策略，例如降低掺杂量、改变工艺窗口、调整组分比例、改善分散、避免副反应、优化后处理或增加保护措施。
9. 必须给出验证方法，例如结构表征、性能复测、稳定性测试、对照实验、原位表征、计算验证等。
10. 不能引入文献没有支撑的新变量、新机制或新实验条件。
11. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
12. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
13. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
14. 不要在 chainofThought 中用括号标注证据来源。
15. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
16. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何筛选得到，而要把证据转写为失败现象、样品差异、失效环节和专业判断。
17. 不要使用“根据已有数据”“失败实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
18. 不要生成最终 output。

推荐推理步骤结构：
1. 明确原始设计意图和目标性能。
2. 识别实际失败信号和失败程度。
3. 比较失败样品与成功/基准/对照样品的关键差异。
4. 将这些差异映射到可能失效环节。
5. 判断最可能的失败原因，并说明不确定性。
6. 提出针对性的修正策略。
7. 设计验证失败原因的实验或表征方法。
8. 说明结论边界和后续迭代方向。

请按以下 JSON 输出：

{
  "cot_type": "失败原因诊断 CoT",
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
    "每条关键推理所依赖的文献信息，保留失败信号、样品差异、表征或测试条件；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、样品范围、测试条件、失败类型或适用边界"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_design_intent": true,
    "has_failure_signal": true,
    "compares_failed_and_control_samples": true,
    "maps_differences_to_failure_link": true,
    "infers_likely_failure_reason": true,
    "keeps_uncertainty": true,
    "has_correction_strategy": true,
    "has_validation_methods": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}