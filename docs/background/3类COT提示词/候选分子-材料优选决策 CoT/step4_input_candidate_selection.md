你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“候选分子 / 材料优选决策 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output，也不要提前给出最终推荐候选。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、cot_type_judgement、recommended_next_action>

目标 CoT 类型：
候选分子 / 材料优选决策 CoT

生成要求：
1. input 必须表现为一个具体候选优选任务，而不是泛泛比较。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含明确应用场景或选择目标，例如电池电极、催化反应、吸附分离、含能材料、药物分子、涂层、聚合物体系等。
4. 必须包含至少 2 个候选对象，优先包含 3 个或以上候选对象。
5. 候选对象必须是具体分子、材料、样品、配方、结构或工艺路线，不要只写宽泛类别。
6. 必须包含可比较指标，例如活性、选择性、稳定性、容量、能量密度、安全性、感度、成本、合成难度、环境适应性、循环寿命、可加工性等。
7. 必须说明指标优先级或应用约束。如果文献中没有显式优先级，应根据应用场景给出“当前场景下更应优先考虑的指标”，并标注为场景约束，而不是绝对规律。
8. input 应呈现候选之间的优缺点差异，但不要直接写“最佳候选是 A”。
9. input 应要求模型做出选择，并说明理由、风险和条件变化下选择是否会改变。
10. 最终 input 中不要使用“候选 A / 候选 B / 候选 C”这类占位符，除非原始样品名称本身就是 A、B、C。
11. 不要写成“候选A（化合物3）”“候选B（样品 S2）”这类占位符-真实名称混合表达；应直接使用真实名称，例如“化合物 3”“样品 S2”“Ni-Fe-LDH-2”。
12. 如果需要提高可读性，可以写“化合物 3、化合物 5 和化合物 7 三个候选物”，不要额外引入 A/B/C 映射。
13. “实测密度”“理论密度”“计算能量”等术语只有在它们本身是评价指标时才保留；不要写成“文献实测”“报道实测”等来源化表达。
14. 如果候选数量不足、缺少可比较指标、没有应用场景或无法判断优先级，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“针对 X 应用场景，需要在化合物 3、化合物 5 和化合物 7 中选择更合适的材料/分子。已知化合物 3 在指标 P 上表现较好但存在 Q 风险，化合物 5 在稳定性或安全性上更优但关键性能较弱，化合物 7 在综合性能上较均衡。当前场景更重视 P 和 R，同时要求 Q 风险可控。请判断应优先选择哪个候选，并说明理由、潜在风险以及在指标优先级变化时选择是否会改变。”

请按以下 JSON 输出：

{
  "cot_type": "候选分子 / 材料优选决策 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "application_scenario": "具体应用场景或选择目标",
    "decision_goal": "需要做出的选择，例如选择最适合的材料/分子/样品/配方/路线",
    "candidate_objects": [
      {
        "candidate_name": "真实候选名称，例如化合物 3、样品 S2 或 Ni-Fe-LDH-2",
        "known_advantages": ["可写入 input 的优势"],
        "known_limitations": ["可写入 input 的短板或风险"],
        "key_metrics": ["该候选涉及的关键指标"]
      }
    ],
    "evaluation_metrics": [
      {
        "metric": "评价指标",
        "priority": "high / medium / low / scenario_dependent",
        "preferred_direction": "higher_is_better / lower_is_better / balanced / condition_dependent",
        "condition_or_unit": "单位、测试条件或应用约束"
      }
    ],
    "application_constraints": [
      "成本、安全性、稳定性、可合成性、环境条件、工艺兼容性、法规或使用场景限制"
    ],
    "required_task": "选择候选 / 说明理由 / 判断风险 / 讨论优先级变化时选择是否改变"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留候选名称、指标、条件、数值或对比关系"
  ],
  "quality_check": {
    "is_specific": true,
    "has_application_scenario": true,
    "has_at_least_two_candidates": true,
    "uses_real_candidate_names": true,
    "does_not_use_placeholder_candidate_labels": true,
    "does_not_mix_placeholder_and_real_names": true,
    "has_comparable_metrics": true,
    "has_metric_priority_or_constraints": true,
    "shows_candidate_tradeoffs": true,
    "does_not_reveal_final_choice": true,
    "asks_for_reasoned_selection": true,
    "asks_for_risk_or_boundary": true,
    "avoids_source_mention": true
  }
}