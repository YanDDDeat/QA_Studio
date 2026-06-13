你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“构效关系 / 结构-性能关系 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、control_or_comparison_samples、performance_metrics、main_observed_results、cot_type_judgement>

目标 CoT 类型：
构效关系 / 结构-性能关系 CoT

生成要求：
1. input 必须表现为“归纳结构/组成变量与性能之间关系”的任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含同一可比系列样品或同一体系下的变量系列。
4. 必须包含被系统改变的结构、组成、形貌、晶相、缺陷、官能团、取代基、孔结构、掺杂比例或配方变量。
5. 必须包含目标性能指标 Z，并保留必要单位和测试条件。
6. 必须包含性能随变量变化的趋势，例如升高、降低、先升后降、存在最优点、平台期、异常点等。
7. 如果存在异常样品或非线性趋势，应写入 input，并要求解释。
8. input 应要求模型归纳结构-性能关系，说明主导因素、趋势原因和适用边界。
9. 不要在 input 中直接给出最终结构-性能规则。
10. 不要把候选优选任务混入本类 input；如果主要任务是“选哪个样品最好”，应转入候选优选 CoT。
11. 如果缺少可比系列样品、系统变量或性能趋势，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“给定 X 系列样品的对比结果，主要结构/组成变量 Y 从 A 到 B 逐步变化，目标性能 Z 呈现某种趋势，其中样品 S 可能是异常点或最优点。请归纳 Y 与 Z 之间的结构-性能关系，解释趋势形成原因，并说明该规则的适用边界。”

请按以下 JSON 输出：

{
  "cot_type": "构效关系 / 结构-性能关系 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "series_system": "同一可比系列样品或体系",
    "structure_or_composition_variable": "被系统改变的变量 Y",
    "variable_range_or_levels": "变量范围或样品水平",
    "target_performance": "性能指标 Z",
    "performance_trend": "性能随变量变化的趋势",
    "anomalies_or_optimum": ["异常点、最优点或非线性趋势"],
    "required_task": "归纳结构-性能关系 / 解释趋势 / 说明异常点 / 给出边界"
  },
  "evidence_used": [
    "用于生成 input 的关键文献信息，保留样品系列、变量、性能指标、趋势或条件"
  ],
  "quality_check": {
    "is_specific": true,
    "has_comparable_series": true,
    "has_systematic_variable": true,
    "has_performance_metric": true,
    "has_performance_trend": true,
    "asks_for_structure_property_rule": true,
    "asks_for_boundary_conditions": true,
    "does_not_turn_into_candidate_selection": true,
    "avoids_source_mention": true,
    "does_not_include_answer": true
  }
}