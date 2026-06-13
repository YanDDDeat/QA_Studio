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
1. output 必须直接回答 input 中提出的性能提升路径任务，开头即说明该体系应优先突破的性能短板和推荐提升路径，不能用“综上”“总体来看”“可以从多个方面优化”等泛泛开场。
2. output 必须紧扣“性能提升路径”任务，不要答成实验方案、配方设计、工艺优化或泛泛机理解释。回答重点应是“性能短板 -> 主导瓶颈 -> 调控手段 -> 结构/过程变化 -> 性能收益 -> 风险与验证”。
3. 如果 input 或 chainofThought 没有明确目标性能、性能短板、可调控变量、机制依据或验证指标，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行生成提升路径。
4. output 应比单句建议更详细，必须给出可执行、可验证的分层提升路径；但不要生成完整实验分组、详细操作流程或配方矩阵。
5. 必须给出总体提升思路，说明当前性能短板应优先从哪些主导瓶颈入手突破，不能只写“通过结构优化提升性能”。
6. 必须给出至少一条优先路径；如果证据支持，可给出辅助路径或备选路径。不要为了显得完整而强行生成多条路径，证据只支持一条时应集中写清楚这一条。
7. 每条路径都必须包含：针对的瓶颈、关键调控手段、预期结构/组成/界面/传输/反应过程变化、预期性能收益、潜在副作用和验证方法。
8. 每个关键判断都必须绑定具体材料体系、性能指标、结构因素、工艺变量、组分变量或机制通道，不能只写“改善结构”“增强稳定性”“提高活性”“促进协同作用”“实现综合性能提升”等空泛表达。
9. 必须说明路径优先级及理由。优先级理由应基于主导瓶颈对应性、机制证据强弱、调控可行性、副作用大小或验证可操作性，不能只写“因此优先推荐”。
10. 如果某条路径可能提升目标性能但牺牲稳定性、安全性、选择性、传输、加工性、相容性或其他指标，必须明确说明折中关系，不能只保留有利结论。
11. 潜在副作用和适用边界必须具体到结构、组分、界面、传输、反应过程、稳定性、测试条件或应用场景层面，不能只写“存在一定风险”“仍需进一步优化”。
12. 验证方法必须说明验证目标和成功信号，不能只罗列表征或测试名称。例如应说明该方法用于验证哪个瓶颈、结构变化、机制通道、性能收益或副作用是否被抑制。
13. 必须给出成功判据或验证指标，例如目标性能变化、结构表征信号、稳定性指标、对照样品差异、失效现象是否被抑制或副作用是否处于可接受范围。
14. output 应按清晰顺序组织，建议采用“总体提升思路 -> 优先路径 -> 辅助/备选路径 -> 路径优先级理由 -> 风险与边界 -> 验证方式与成功判据”的结构，避免把结论、原因、风险和验证混在一起。
15. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“可实现综合性能提升”等。若表达意义，必须落到具体性能、机制、路径或应用边界上。
16. 不要引入 input 和 chainofThought 中没有出现的新变量、新数值、新机制、新材料、新实验条件、新测试指标或新结论。
17. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把 output 写成确定因果，必须保留“可能”“更倾向于”“在该条件范围内”“需要进一步验证”等限定表达。
18. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
19. output 应完成证据内化，不要出现“筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
20. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该体系的性能提升应优先从 B 瓶颈入手。优先路径是通过 C 调控手段改善 M 结构/过程，使目标性能 Z 得到提升；该路径优先于其他方向，是因为它直接对应当前主导瓶颈，且副作用更容易通过 R 表征和 S 性能测试验证。辅助路径可围绕 D 变量展开，用于进一步缓解 N 限制，但需要关注 P 副作用，例如稳定性下降、传输受阻或安全性变差。判断该路径有效的标准是 Z 指标出现预期改善，M 结构/过程信号得到确认，同时 P 风险没有超过可接受范围。该判断只适用于 Q 体系、条件或变量范围内，超出该边界需要重新验证。”

请按以下 JSON 输出：

{
  "cot_type": "性能提升路径 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少目标性能、性能短板、可调控变量、机制依据、风险信息或验证指标"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终答案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "target_performance": "需要提升的目标性能",
    "main_performance_bottleneck": "当前优先突破的性能短板或主导瓶颈",
    "overall_strategy": "总体性能提升思路，必须说明从哪些瓶颈入手以及为什么",
    "prioritized_improvement_paths": [
      {
        "priority": "优先 / 辅助 / 备选",
        "path_name": "路径名称，必须反映真实调控对象或机制通道",
        "target_bottleneck": "该路径针对的性能瓶颈",
        "key_adjustment": "关键调控手段，必须来自 input 或 chainofThought",
        "expected_structure_or_process_change": "预期结构、组成、界面、传输或反应过程变化",
        "expected_performance_benefit": "预期性能收益或变化方向",
        "priority_reason": "为什么该路径优先、辅助或备选，必须绑定瓶颈对应性、机制证据、风险或验证可行性",
        "potential_side_effects": [
          "潜在副作用、折中关系或风险，必须具体到结构、过程、性能或应用边界"
        ],
        "validation_methods": [
          {
            "method": "表征、测试、对照或计算方法",
            "validation_target": "验证哪个瓶颈、结构变化、机制、性能收益或副作用",
            "success_signal": "什么结果支持该路径有效"
          }
        ]
      }
    ],
    "recommended_sequence": [
      "建议优先验证和推进的路径顺序，以及排序理由"
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
    "matches_performance_improvement_task": true,
    "does_not_repeat_chain": true,
    "has_target_performance": true,
    "has_main_performance_bottleneck": true,
    "has_overall_strategy": true,
    "has_prioritized_paths": true,
    "path_names_are_specific": true,
    "each_path_has_bottleneck": true,
    "each_path_has_adjustment": true,
    "each_path_has_mechanism": true,
    "each_path_has_expected_benefit": true,
    "each_path_has_priority_reason": true,
    "mentions_specific_tradeoffs_and_side_effects": true,
    "includes_validation_methods": true,
    "validation_methods_have_targets_and_success_signals": true,
    "has_success_criteria": true,
    "keeps_boundary_conditions": true,
    "does_not_turn_into_experimental_plan": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
