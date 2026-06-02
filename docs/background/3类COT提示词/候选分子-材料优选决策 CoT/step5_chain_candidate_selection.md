你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“候选分子 / 材料优选决策 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、cot_type_judgement、recommended_next_action>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
候选分子 / 材料优选决策 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的最终候选推荐。
3. 必须明确应用场景和选择目标，例如特定反应、器件、材料体系、配方体系或使用环境。
4. 必须识别候选对象，并确认它们是否处于同一可比任务或同一评价框架下。
5. 必须明确评价指标及其优先级，例如活性、选择性、容量、稳定性、安全性、成本、可合成性、循环寿命、感度、可加工性等。
6. 必须分别分析每个候选对象的优势、短板和风险。
7. 必须区分“关键指标优势”和“可接受短板”；不能只因某一单项指标最高就直接推荐。
8. 必须判断是否存在硬约束或不可接受风险，例如安全性不足、稳定性太差、不可合成、成本过高或应用条件不匹配。
9. 必须进行多指标权衡，并形成候选优先级或候选排序的推理依据。
10. 必须说明如果应用场景或指标优先级发生变化，候选选择是否可能改变。
11. 必须给出后续需要补充验证的性能测试、稳定性测试、成本/安全评估或可制备性验证。
12. 不能引入文献没有支撑的新候选、新指标、新数值或新风险。
13. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
14. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
15. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
16. 不要在 chainofThought 中用括号标注证据来源，例如“（图 2）”“（表 1）”“（文献报道）”。
17. 可以使用 input 中已经给出的候选名称、指标、数值和条件，但表达方式应改为任务事实，不要说明其来自文献。
18. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
19. chainofThought 还必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据转写为候选对象的性能事实、约束条件和决策依据。
20. 不要使用“对比实验表明”“根据已有数据”“结果显示”“数据说明”“从表中可以看出”“已有研究证明”等证据过程表达。
21. 推荐使用内化表达，例如：
    - 不写：“对比实验表明，候选 A 的稳定性最高。”
    - 改写：“候选 A 的主要优势在于稳定性更好，更适合稳定性优先的场景。”
    - 不写：“表中数据显示候选 B 的活性最高。”
    - 改写：“候选 B 在活性指标上更突出，但需要同时评估其稳定性和安全性是否满足场景要求。”
    - 不写：“根据数据，候选 C 是最优。”
    - 改写：“如果当前场景更重视综合平衡而非单项极值，候选 C 可能更符合整体约束。”
22. 不要生成最终 output 段落。

推荐推理步骤结构：
1. 明确应用场景和选择目标。
2. 确认可比较候选对象及其评价框架。
3. 确定评价指标优先级和硬约束。
4. 分别分析各候选的优势、短板和风险。
5. 判断候选短板是否会触发不可接受风险。
6. 进行多指标权衡，形成候选排序或优先选择依据。
7. 分析指标优先级变化时选择是否会改变。
8. 给出后续需要补充验证的指标和边界条件。

请按以下 JSON 输出：

{
  "cot_type": "候选分子 / 材料优选决策 CoT",
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
    "每条关键推理所依赖的文献信息，保留候选名称、指标、条件、数值、单位或证据位置；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的应用场景、测试条件、指标优先级、材料体系或适用范围"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_application_scenario": true,
    "has_candidate_objects": true,
    "confirms_candidate_comparability": true,
    "has_metric_priority": true,
    "compares_advantages_and_limitations": true,
    "handles_tradeoffs": true,
    "checks_unacceptable_risks": true,
    "considers_priority_change": true,
    "includes_followup_validation": true,
    "avoids_single_metric_overdecision": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}