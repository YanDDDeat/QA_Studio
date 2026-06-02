你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“构效关系 / 结构-性能关系 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、control_or_comparison_samples、performance_metrics、main_observed_results、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
构效关系 / 结构-性能关系 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的结构-性能规则形成。
3. 必须先确认样品是否属于同一可比系列。
4. 必须识别被系统改变的结构、组成、形貌、晶相、缺陷、孔结构、官能团、取代基或比例变量。
5. 必须归纳性能随变量变化的趋势。
6. 必须判断主导性能变化的结构因素。
7. 如果存在异常点、平台期、最优点或非线性趋势，必须解释其可能原因。
8. 必须说明该结构-性能关系的适用边界，不能写成普适规律。
9. 必须给出进一步验证该关系的表征、性能测试或计算方法。
10. 不能引入文献没有支撑的新变量、新机制或新性能结论。
11. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
12. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
13. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
14. 不要在 chainofThought 中用括号标注证据来源。
15. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
16. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据转写为系列事实、变量关系、性能趋势和专业判断。
17. 不要使用“根据已有数据”“对比实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
18. 不要生成最终 output。

推荐推理步骤结构：
1. 确认样品属于同一可比系列。
2. 找出被系统改变的结构或组成变量。
3. 比较性能随变量变化的趋势。
4. 判断主导性能变化的结构因素。
5. 解释异常点、最优点或非线性趋势。
6. 形成结构-性能关系规则。
7. 判断规则适用边界。
8. 给出进一步验证方法。

请按以下 JSON 输出：

{
  "cot_type": "构效关系 / 结构-性能关系 CoT",
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
    "每条关键推理所依赖的文献信息，保留样品系列、变量、性能指标、趋势、异常点或条件；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的样品系列、变量范围、测试条件或适用范围"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "confirms_comparable_series": true,
    "identifies_systematic_variable": true,
    "has_performance_trend": true,
    "identifies_dominant_structure_factor": true,
    "handles_anomaly_or_nonlinearity": true,
    "forms_structure_property_rule": true,
    "keeps_boundary_conditions": true,
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