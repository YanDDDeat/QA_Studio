你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“性能提升路径 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、performance_metrics、main_observed_results、mechanism_or_explanation、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
性能提升路径 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的“性能提升路径”生成。
3. 必须先明确目标性能 Z、当前短板和需要突破的性能边界。
4. 必须把性能 Z 拆解为若干影响通道，例如活性位点、电子结构、传质/传输、界面接触、相稳定性、孔结构、结晶质量、缺陷结构、副反应、力学稳定性、热稳定性或安全性。
5. 必须判断哪些通道更可能是主导瓶颈，并说明判断逻辑。
6. 必须把主导瓶颈映射到可调控因素，例如组成调节、结构改造、掺杂/取代、缺陷调控、形貌控制、界面工程、孔道调控、工艺窗口优化、后处理或复合策略。
7. 必须形成至少一条核心提升路径，并可根据证据强度形成辅助路径或备选路径。
8. 每条路径都必须说明“针对的瓶颈 -> 调控手段 -> 结构/过程变化 -> 性能提升方向”的因果链或条件性关联链。
9. 必须分析潜在副作用和折中关系，例如提升活性但降低稳定性、增加缺陷但引入副反应、改善传输但降低密度、提高反应性但增加安全风险等。
10. 必须给出路径优先级判断，说明优先推进哪条路径以及原因。
11. 必须给出验证建议，包括关键表征、性能测试、对照样品、稳定性测试或计算模拟。
12. 不要引入文献没有支撑的新变量、新机制、新数值或新性能结论。
13. 如果证据只支持相关性，不要写成确定因果，应使用“可能”“倾向于”“支持”等限定表达。
14. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
15. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
16. 不要在 chainofThought 中用括号标注证据来源。
17. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
18. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何比较得到，而要把证据改写为性能事实、瓶颈判断、结构/过程影响和专业推断。
19. 不要使用“根据已有数据”“对照实验表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
20. 不要生成最终 output。

推荐推理步骤结构：
1. 明确目标性能、当前短板和提升目标。
2. 拆解性能 Z 的关键决定因素。
3. 识别最可能限制性能提升的主导瓶颈。
4. 将瓶颈映射到可调控结构、组成、界面、工艺或测试因素。
5. 构建核心提升路径，并说明其作用机制。
6. 构建辅助或备选提升路径，并说明适用场景。
7. 分析路径之间的副作用、折中关系和边界条件。
8. 给出优先级排序和验证指标。

请按以下 JSON 输出：

{
  "cot_type": "性能提升路径 CoT",
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
    "每条关键推理所依赖的文献信息，保留体系、性能短板、变量、趋势、机制或约束；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、测试条件、调控范围、性能指标、证据强度或适用边界"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_target_performance": true,
    "has_performance_gap": true,
    "decomposes_performance_factors": true,
    "identifies_main_bottleneck": true,
    "maps_bottleneck_to_adjustable_factors": true,
    "proposes_core_improvement_path": true,
    "proposes_auxiliary_or_alternative_paths": true,
    "links_path_to_mechanism": true,
    "mentions_tradeoffs_and_side_effects": true,
    "prioritizes_paths": true,
    "includes_validation_metrics": true,
    "keeps_uncertainty": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}