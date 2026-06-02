你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“性能提升路径 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
性能提升路径 CoT

生成要求：
1. output 必须直接回答 input 中提出的性能提升路径任务。
2. output 应比单句建议更详细，必须给出可执行、可验证的分层提升路径。
3. 必须给出总体提升思路，说明性能短板应从哪些主导瓶颈入手突破。
4. 必须给出至少一条优先路径；如果证据支持，应给出辅助路径或备选路径。
5. 每条路径必须包含：针对的瓶颈、关键调控手段、预期结构/过程变化、预期性能收益、潜在副作用和验证方法。
6. 必须说明路径优先级，即为什么某条路径应优先推进，其他路径适合作为补充或备选。
7. 必须给出成功判据或验证指标，例如目标性能变化、结构表征信号、稳定性指标、对照样品差异或失效现象是否被抑制。
8. 必须保留适用边界和不确定性，不能把特定体系结论写成普适规律。
9. 不要生成完整实验分组或详细操作流程；本步骤输出的是性能提升路径，不是实验方案。
10. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制或新实验条件。
11. 如果 chainofThought 只支持相关性，不要把 output 写成确定因果。
12. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
13. output 应完成证据内化，不要出现“筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
14. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该体系的性能提升应优先从 B 瓶颈入手，通过 C 调控手段改善 M 结构/过程，从而提升目标性能 Z。优先路径 1 是……；辅助路径 2 是……；备选路径 3 是……。这些路径需要关注 P 副作用，并通过 R 表征、S 性能测试和 T 稳定性评价验证。该判断适用于 Q 条件内，超出该边界需要重新验证。”

请按以下 JSON 输出：

{
  "cot_type": "性能提升路径 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought",
  "output_elements": {
    "overall_strategy": "总体性能提升思路",
    "prioritized_improvement_paths": [
      {
        "priority": "优先 / 辅助 / 备选",
        "path_name": "路径名称",
        "target_bottleneck": "该路径针对的性能瓶颈",
        "key_adjustment": "关键调控手段",
        "expected_structure_or_process_change": "预期结构、组成、界面、传输或反应过程变化",
        "expected_performance_benefit": "预期性能收益或变化方向",
        "potential_side_effects": [
          "潜在副作用、折中关系或风险"
        ],
        "validation_methods": [
          {
            "method": "表征、测试、对照或计算方法",
            "validation_target": "验证哪个瓶颈、结构变化、机制或性能提升",
            "success_signal": "什么结果支持该路径有效"
          }
        ]
      }
    ],
    "recommended_sequence": [
      "建议优先验证和推进的路径顺序"
    ],
    "success_criteria": [
      "判断性能提升路径有效的关键指标或判据"
    ],
    "boundary_conditions": [
      "适用条件、体系边界、不确定性或需要重新验证的情况"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留体系、性能短板、变量、趋势、机制或约束；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "does_not_repeat_chain": true,
    "has_overall_strategy": true,
    "has_prioritized_paths": true,
    "each_path_has_bottleneck": true,
    "each_path_has_adjustment": true,
    "each_path_has_mechanism": true,
    "each_path_has_expected_benefit": true,
    "mentions_tradeoffs_and_side_effects": true,
    "includes_validation_methods": true,
    "has_success_criteria": true,
    "keeps_boundary_conditions": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}