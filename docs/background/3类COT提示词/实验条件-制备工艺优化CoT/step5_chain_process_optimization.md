你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“实验条件 / 制备工艺优化 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、cot_type_judgement、recommended_next_action>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
实验条件 / 制备工艺优化 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的工艺窗口判断。
3. 必须明确工艺优化目标和目标性能指标。
4. 必须识别核心工艺变量、变量范围或条件水平。
5. 必须说明目标性能随工艺变量变化的趋势。
6. 必须分析工艺变量如何影响结构、形貌、晶相、缺陷、界面、孔结构、光谱特征、传输行为或其他相关因素。
7. 必须把结构/过程变化与性能趋势建立联系。
8. 必须判断最优工艺窗口或最佳条件的依据。
9. 必须说明过低或过高条件可能带来的副作用。
10. 必须给出需要的表征、性能测试或稳定性验证方法。
11. 不能引入文献没有支撑的新变量、新机制或新实验条件。
12. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
13. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
14. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“图 2a”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
15. 不要在 chainofThought 中用括号标注证据来源，例如“（图 2a）”“（文献报道 8.3%）”“（见表 1）”。
16. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
17. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何筛选得到，而要把证据转写为体系事实、变量关系、条件约束和专业判断。
18. 不要使用“根据已有数据”“根据已有筛选”“筛选实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”“已有案例证明”等证据过程表达。
19. 不要生成完整实验方案，不要写 output。

推荐推理步骤结构：
1. 明确工艺优化任务和目标性能。
2. 识别核心工艺变量及其变化范围。
3. 总结性能随工艺变量变化的趋势。
4. 分析工艺变量对结构、形貌、晶相、缺陷或界面等因素的影响。
5. 解释这些结构或过程变化如何影响目标性能。
6. 判断最优工艺窗口或最佳条件的证据基础。
7. 说明过低或过高条件下的副作用。
8. 给出后续需要的表征和性能验证方法。

请按以下 JSON 输出：

{
  "cot_type": "实验条件 / 制备工艺优化 CoT",
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
    "has_process_variable": true,
    "has_performance_trend": true,
    "links_structure_or_process_to_performance": true,
    "identifies_optimal_window": true,
    "mentions_low_or_high_condition_side_effects": true,
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