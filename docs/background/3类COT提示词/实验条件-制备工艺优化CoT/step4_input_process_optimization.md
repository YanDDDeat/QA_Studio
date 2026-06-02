你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“实验条件 / 制备工艺优化 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information 和 cot_type_judgement>

目标 CoT 类型：
实验条件 / 制备工艺优化 CoT

生成要求：
1. input 必须表现为具体工艺优化问题，而不是完整实验方案设计任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含具体研究对象 X。
4. 必须包含明确工艺变量 Y，例如温度、时间、溶剂、pH、气氛、前驱体比例、煅烧条件、结晶条件、光照波长、光照功率等。
5. 必须包含变量范围、变量水平或至少两个可比较条件。
6. 必须包含目标性能 Z 或评价指标，例如容量、效率、选择性、稳定性、转化率、产率、过电位、半衰期等。
7. 如果存在“先升后降”“过低不足”“过高副作用”“某一窗口最优”等趋势，应写入 input。
8. 如果存在结构、形貌、晶相、缺陷、界面、孔结构、光谱特征或传输行为等线索，可作为背景写入 input。
9. input 应要求模型解释性能趋势、判断工艺窗口、说明副作用和提出验证方法。
10. 不要在 input 中直接给出最终原因、完整答案或完整实验方案。
11. 不要要求“设计实验分组、对照设置、完整实验方案”；这属于实验方案生成 CoT。
12. 如果缺少明确工艺变量、变量范围或性能趋势，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“X 材料/体系在工艺条件 Y 从 A 到 B 变化时，目标性能 Z 呈现某种趋势；相关表征显示结构因素 M、N 也随 Y 发生变化。请解释该性能趋势，判断合理的工艺优化窗口，并说明过低或过高条件的副作用以及需要的验证方法。”

请按以下 JSON 输出：

{
  "cot_type": "实验条件 / 制备工艺优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_object": "X",
    "process_variable": "Y",
    "variable_range_or_levels": "A 到 B，或具体条件列表",
    "target_performance": "Z",
    "observed_trend": "性能变化趋势",
    "structure_or_process_clues": ["可用于后续推理的结构、表征、机制或过程线索"],
    "low_or_high_condition_risks": ["过低或过高条件下的风险"],
    "required_task": "解释趋势 / 判断工艺窗口 / 说明副作用 / 给出验证方法"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留变量、数值、单位、条件或对比关系"
  ],
  "quality_check": {
    "is_specific": true,
    "has_process_variable": true,
    "has_variable_range_or_levels": true,
    "has_performance_metric": true,
    "has_trend_or_comparison": true,
    "asks_for_process_window": true,
    "asks_for_side_effects": true,
    "asks_for_validation": true,
    "does_not_turn_into_experimental_plan": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}