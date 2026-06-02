你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“实验设计配方 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、recipe_components、process_or_recipe_information、cot_type_judgement>

目标 CoT 类型：
实验设计配方 CoT

生成要求：
1. input 必须表现为具体配方设计任务，而不是泛泛实验建议。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含研究体系 X，例如电解液、浆料、涂层、催化剂、聚合物、复合材料、凝胶、前驱体体系、药物分子配方等。
4. 必须包含配方设计目标 Z，例如提升容量、稳定性、选择性、安全性、机械强度、溶解度、成膜性、能量密度、分散性或可加工性。
5. 必须包含关键组分及其作用，例如活性组分、溶剂、添加剂、粘结剂、前驱体、交联剂、载体、盐、填料、助剂等。
6. 必须包含可调配方变量，例如质量比、摩尔比、浓度、添加剂含量、负载量、溶剂比例、固含量或组分梯度。
7. 如果文献信息中有明确比例、浓度或范围，应保留单位和条件。
8. 如果没有明确比例或浓度，不能编造数值；可以要求设计低/中/高梯度或在已有安全范围内筛选。
9. 必须包含评价指标和成功判据，例如目标性能、稳定性、重复性、纯度、分散性、黏度、成膜质量、安全性等。
10. 如果存在过量添加、副反应、相分离、稳定性下降、黏度过高、性能下降等风险，应写入 input。
11. input 应要求模型给出基础配方、变量矩阵、筛选逻辑、淘汰准则和下一轮优化方向。
12. 不要在 input 中直接给出最终配方答案。
13. 如果缺少配方组分、可调比例/浓度或性能反馈，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“需要为 X 体系设计一组实验配方，以优化目标性能 Z。已知关键组分包括 A、B、C，其中 A 主要负责 P，B 影响 Q，C 可能改善 R，但过量 C 会带来 S 风险。可调因素包括 A:B 比例、C 含量、溶剂比例和处理条件。请给出合理的基础配方、单因素梯度、组合优化配方、成功判据和淘汰准则。”

请按以下 JSON 输出：

{
  "cot_type": "实验设计配方 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "recipe_system": "X",
    "recipe_design_goal": "Z",
    "base_recipe_or_reference": "已有基础配方、基准配方或参考体系",
    "key_components": [
      {
        "component": "组分名称",
        "role": "该组分在配方中的作用"
      }
    ],
    "adjustable_recipe_variables": [
      "可调比例、浓度、负载量、添加剂含量、溶剂比例、固含量等"
    ],
    "known_ranges_or_levels": [
      "已知比例、浓度、单位或低/中/高梯度"
    ],
    "performance_metrics": [
      "用于评价配方效果的指标"
    ],
    "risks_or_side_effects": [
      "过量、缺失、比例不当或工艺不兼容带来的风险"
    ],
    "required_task": "设计基础配方 / 单因素梯度 / 组合优化矩阵 / 成功判据 / 淘汰准则"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留组分、比例、浓度、单位、性能趋势或风险"
  ],
  "quality_check": {
    "is_specific": true,
    "has_recipe_system": true,
    "has_recipe_design_goal": true,
    "has_key_components": true,
    "has_adjustable_recipe_variables": true,
    "has_performance_metrics": true,
    "mentions_ranges_or_says_no_fabrication": true,
    "asks_for_recipe_matrix": true,
    "asks_for_success_and_rejection_criteria": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}