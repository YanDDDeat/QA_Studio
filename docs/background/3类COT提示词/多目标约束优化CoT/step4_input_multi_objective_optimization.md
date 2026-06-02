你是一名材料/化学领域 CoT 数据构建专家。请根据 Step 1-3 的抽取结果，为“多目标约束优化 CoT”生成训练样本 input。

你只需要生成 input，不要生成 chainofThought，不要生成 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、variables、control_or_comparison_samples、performance_metrics、main_observed_results、mechanism_or_explanation、cot_type_judgement>

目标 CoT 类型：
多目标约束优化 CoT

生成要求：
1. input 必须表现为“在多个性能目标和约束条件下，如何确定最优方案、最优窗口或合理折中”的任务。
2. input 中不要出现“根据文献”“文献报道”“本文报道”“作者发现”等来源表达。
3. 必须包含具体研究对象或材料/分子/工艺/配方/器件体系 X。
4. 必须包含至少两个目标性能或评价指标，例如活性与稳定性、容量与倍率、能量密度与安全性、产率与纯度、密度与感度、吸附容量与选择性、强度与韧性、效率与成本等。
5. 必须明确每个指标的优化方向，例如越高越好、越低越好、需控制在某范围内、需超过阈值或不能低于基线。
6. 必须包含至少一个硬约束，例如安全上限、稳定性下限、成本限制、结构保持要求、产率阈值、纯度要求、测试条件、工艺可行性或法规/应用场景约束。
7. 可以包含软目标或优先级，例如在满足安全和稳定性的前提下优先提高性能、在性能接近时优先选择低成本或易制备路线。
8. 必须包含可调控变量、候选方案或设计空间，例如组分比例、掺杂量、反应条件、配方比例、候选分子、孔结构、界面层、晶相、缺陷浓度或后处理方式。
9. 如果目标之间存在冲突或折中，应写入 input，例如提高活性可能降低稳定性、提高密度可能增加感度、增加缺陷可能提升容量但降低循环寿命。
10. input 应要求模型区分硬约束和软目标，筛除不可行方案，分析折中关系，并给出推荐方案或优化窗口。
11. 不要在 input 中直接给出最终最优方案或最终排序结论。
12. 不要把任务写成单一指标的候选优选；如果只有一个目标且没有约束，应转入“候选分子 / 材料优选决策 CoT”或“性能提升路径 CoT”。
13. 不要把任务写成完整实验步骤设计；如果核心任务是实验分组和操作流程，应转入“实验方案生成 CoT”。
14. 如果缺少多个目标、约束条件或可调控设计空间，请输出 not_ready，并说明缺少什么。

推荐 input 结构：
“X 体系需要在目标 Z1、Z2 和 Z3 之间进行优化，其中 Z1 越高越好，Z2 需要低于/高于阈值 A，Z3 作为稳定性或安全性硬约束必须满足 B。可调控变量包括 C、D 和 E，不同变量可能带来性能收益与副作用之间的折中。请区分硬约束和软目标，筛选可行方案，分析目标冲突，并给出最合理的优化窗口或推荐方案及其验证指标。”

请按以下 JSON 输出：

{
  "cot_type": "多目标约束优化 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "selected_input": "最终推荐使用的 input",
  "alternative_inputs": [
    "备选 input 1",
    "备选 input 2"
  ],
  "input_elements": {
    "research_system": "X",
    "optimization_variables_or_design_space": [
      "可调控变量、候选方案或可搜索设计空间"
    ],
    "objectives": [
      {
        "metric": "目标性能指标",
        "optimization_direction": "越高越好 / 越低越好 / 控制在范围内 / 达到阈值",
        "target_or_threshold": "目标值、阈值、范围或相对要求",
        "priority": "高 / 中 / 低 / 未明确"
      }
    ],
    "hard_constraints": [
      "必须满足的约束条件"
    ],
    "soft_preferences": [
      "满足硬约束后的偏好或次级目标"
    ],
    "tradeoff_relations": [
      "目标之间或变量与性能之间的冲突/折中关系"
    ],
    "required_task": "区分硬约束和软目标 / 筛选可行域 / 分析折中 / 给出推荐方案或优化窗口 / 给出验证指标"
  },
  "evidence_used": [
    "用于生成 input 的关键信息，保留体系、变量、多个目标、约束、趋势、冲突或边界"
  ],
  "quality_check": {
    "is_specific": true,
    "has_research_system": true,
    "has_multiple_objectives": true,
    "has_optimization_directions": true,
    "has_hard_constraints": true,
    "has_design_space_or_variables": true,
    "has_tradeoff_relations": true,
    "distinguishes_hard_constraints_and_soft_goals": true,
    "asks_for_feasible_solution": true,
    "asks_for_tradeoff_analysis": true,
    "asks_for_validation_metrics": true,
    "does_not_include_final_decision": true,
    "does_not_turn_into_single_metric_selection": true,
    "does_not_turn_into_experimental_plan": true,
    "avoids_source_mention": true
  }
}