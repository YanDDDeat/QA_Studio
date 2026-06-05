你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和 chainofThought，为“实验设计配方 CoT”生成最终 output。

你只需要生成 output，不要重复完整 chainofThought。

输入：
step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input 和 input_elements>

step5_chain_result:
<粘贴 Step 5 生成的 JSON，尤其是 chainofThought、boundary_conditions 和 quality_check>

目标 CoT 类型：
实验设计配方 CoT

生成要求：
1. output 必须直接回答 input 中提出的配方设计任务，开头即说明配方目标、基础配方思路和核心筛选变量，不能用“综上”“总体来看”“可以从多个方面优化”等泛泛开场。
2. output 必须紧扣“实验设计配方”任务，不要答成普通实验方案、性能提升路径、工艺优化或泛泛配方建议。回答重点应是“配方目标 -> 组分作用 -> 单因素梯度 -> 组合优化矩阵 -> 评价与淘汰判据 -> 风险控制 -> 下一轮优化”。
3. 如果 input 或 chainofThought 没有明确配方目标、组分、可调变量、评价指标或可用范围，应将 readiness 设为 not_ready，并在 missing_information 中说明缺口，不要强行生成配方矩阵。
4. output 必须给出可执行的基础配方、变量筛选逻辑和配方矩阵，但不要写成无依据的操作规程。不得补写 input 和 chainofThought 中没有提供的称量、浓度、温度、时间、溶剂或处理条件。
5. 如果 input 或 chainofThought 中有明确数值范围、比例、浓度、单位或条件，应保持一致；如果没有明确数值范围，不能编造具体比例或浓度，只能使用低/中/高梯度、相对比例、条件性建议或“需要先确定范围”的表述。
6. 每个关键组分都必须说明作用和风险，至少说明它影响什么结构、过程、性能、稳定性、加工性、相容性或安全性，不能只写“提高性能”“改善体系”“增强稳定性”等空泛表达。
7. 每个单因素梯度必须说明筛选变量、保持不变的条件、验证目的、评价指标和进入下一阶段或淘汰的规则，不能只列出梯度名称。
8. 组合优化矩阵必须建立在单因素筛选逻辑上，说明为什么组合这些变量、预期解决什么问题，以及如何判断组合是否优于基础配方。
9. 成功判据和淘汰判据必须具体到目标性能、稳定性、加工性、相分离、副反应、可重复性、对照差异或风险信号，不能只写“性能更好”“结果稳定”“不满足要求则淘汰”。
10. 风险控制策略必须对应配方中的具体问题，例如过量添加、比例失衡、相分离、副反应、稳定性下降、加工性变差、相容性不足或安全性风险，不能只写“需要控制风险”。
11. 下一轮优化方向必须基于当前筛选结果可能出现的情况，说明缩小哪个范围、细化哪个比例、保留哪个变量或补充哪个验证，不能新增无依据组分或方向。
12. output 应按清晰顺序组织，建议采用“基础配方 -> 组分作用 -> 单因素梯度 -> 组合优化矩阵 -> 评价指标 -> 成功/淘汰判据 -> 风险控制 -> 下一轮优化 -> 适用边界”的结构，避免把组分、变量、判据和风险混在一起。
13. 禁止 AI 化套话和空泛总结，例如“具有重要意义”“为后续研究提供参考”“展现出良好应用前景”“有望推动相关领域发展”“系统优化配方性能”等。若表达方案价值，必须落到具体组分、变量、性能或风险控制上。
14. 不要为了显得完整而强行生成过多配方组或组合矩阵。如果 input 和 chainofThought 只支持有限变量，应围绕这些变量设计；证据不足时，应在 missing_information 或 boundary_conditions 中说明。
15. 不要引入 input 和 chainofThought 中没有出现的新组分、新比例、新浓度、新机制、新材料、新实验条件、新测试指标或新结论。
16. 如果 chainofThought 只支持相关性、趋势性或条件依赖判断，不要把配方设计写成确定最优方案，应保留“用于筛查”“优先验证”“可能更合适”“需要进一步确认”等限定表达。
17. output 必须去文献化，不能出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等来源表达。
18. output 应完成证据内化，不要出现“配方筛选实验表明”“根据已有数据”“结果显示”“数据说明”等证据过程表达。
19. 图号、表号、章节号、证据位置只能写入 evidence_used，不得写入 output。

推荐 output 结构：
“该配方设计应以 X 体系的 Z 性能为目标，先建立包含 A、B、C 组分的基础配方，其中 A 负责……，B 负责……，C 负责……。第一轮采用单因素梯度筛选关键变量 Y，在其他组分和处理条件保持不变的前提下比较低/中/高或已给定范围，判断 Y 对 Z、稳定性和加工性的影响；进入下一轮的条件是 P 指标改善且不出现 Q 风险。第二轮将单因素中表现较好的 Y 与 W 变量组合，形成小规模组合矩阵，用于判断二者是否存在协同或比例失衡。若出现相分离、副反应、稳定性下降或加工性变差，应淘汰该配方组或回退到较低水平。下一轮优化应围绕保留组进一步缩小比例范围，并补充 R 测试确认长期稳定性或可重复性。该方案只适用于当前组分体系和已给定变量范围，不能直接外推到其他配方体系。”

请按以下 JSON 输出：

{
  "cot_type": "实验设计配方 CoT",
  "readiness": "ready / not_ready",
  "missing_information": ["如果 not_ready，列出缺少的信息，例如缺少配方目标、基础组分、可调变量、范围信息、评价指标、风险条件或边界条件"],
  "input": "沿用 Step 4 的 selected_input",
  "output": "最终配方设计与筛选方案，直接回答 input，不重复 chainofThought；必须具体、切题、条理清晰，避免泛泛表述和 AI 化套话",
  "output_elements": {
    "recipe_goal": "配方设计要优化或验证的具体目标",
    "base_recipe": {
      "description": "基础配方或基准配方",
      "fixed_components": ["固定组分及作用"],
      "initial_conditions": ["已有比例、浓度、处理条件；无明确数值时写条件性描述，不得编造"]
    },
    "component_roles": [
      {
        "component": "组分名称",
        "role": "该组分在结构、过程、性能、稳定性、加工性、相容性或安全性中的作用",
        "risk_if_too_low_or_too_high": "过低或过高的具体风险"
      }
    ],
    "single_factor_gradient": [
      {
        "variable": "单因素变量",
        "levels_or_range": ["具体水平、范围或低/中/高梯度；不得新增无依据数值"],
        "fixed_conditions": ["保持不变的配方或工艺条件"],
        "purpose": "该梯度用于验证什么变量作用或风险",
        "evaluation_metrics": ["评价指标"],
        "decision_rule": "保留、淘汰、回退或进入组合优化的判据"
      }
    ],
    "combination_optimization_matrix": [
      {
        "recipe_group": "组合优化组名称",
        "combined_variables": ["组合变量"],
        "design_logic": "为什么组合这些变量，预期解决什么问题或验证什么协同/冲突",
        "evaluation_metrics": ["评价指标"],
        "decision_rule": "判断是否优于基础配方、是否淘汰或是否进入下一轮的标准"
      }
    ],
    "success_criteria": [
      "判断配方成功的具体判据，必须对应目标性能、稳定性、加工性、相容性、可重复性或风险抑制"
    ],
    "rejection_criteria": [
      "判断配方失败、淘汰或需要回退的具体判据"
    ],
    "risk_control_strategy": [
      "针对过量、比例失衡、副反应、相分离、稳定性下降、加工性变差、相容性不足或安全性问题的控制策略"
    ],
    "next_iteration_plan": [
      "下一轮优化如何缩小范围、细化比例、保留变量或增加验证；不得新增无依据方向"
    ],
    "boundary_conditions": [
      "该配方方案成立的体系、组分范围、测试条件、变量空间或适用边界"
    ]
  },
  "evidence_used": [
    "支持 output 的内部证据，可保留组分、比例、浓度、单位、性能趋势或风险；这些内容不得出现在 output 正文中"
  ],
  "quality_check": {
    "answers_input_directly": true,
    "matches_recipe_design_task": true,
    "is_actionable_recipe_design": true,
    "has_recipe_goal": true,
    "has_base_recipe": true,
    "has_component_roles": true,
    "component_roles_are_specific": true,
    "has_single_factor_gradient": true,
    "single_factor_gradient_has_decision_rules": true,
    "has_combination_optimization_matrix": true,
    "combination_matrix_has_design_logic": true,
    "has_success_criteria": true,
    "has_rejection_criteria": true,
    "handles_specific_risks": true,
    "has_next_iteration_plan": true,
    "avoids_fabricated_ratios": true,
    "keeps_boundary_conditions": true,
    "does_not_repeat_chain": true,
    "does_not_add_new_claims": true,
    "avoids_ai_style_generic_phrases": true,
    "output_is_de_literaturized": true,
    "output_has_no_source_mentions": true,
    "output_has_no_figure_or_table_mentions": true,
    "output_internalizes_evidence": true,
    "output_has_no_evidence_process_phrases": true
  }
}
