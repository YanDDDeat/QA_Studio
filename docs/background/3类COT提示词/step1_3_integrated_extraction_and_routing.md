你是一名材料/化学领域专业 CoT 数据构建专家。请阅读我提供的完整文献内容，先提取关键实验信息，再判断该文献适合构建 10 类 CoT 中的哪些类型。

重要要求：
1. 只基于输入文献中的证据，不凭常识补全。
2. 不要直接生成最终 CoT 样本。
3. 不要生成训练 input、chainofThought 或 output。
4. 优先依据结果与讨论、实验部分、图表、表征数据和补充信息。
5. 不要只根据摘要判断。
6. 博士论文中优先使用作者自己的实验章节，不把综述章节当作实验事实。
7. 如果证据不足以支持某类 CoT，请标记为 not_build。

输入：
source_id: <文献编号、题名、DOI、章节编号或内部编号，可为空>
source_type: <research_paper / phd_thesis / unknown>
full_literature:
<在这里粘贴完整文献内容>

请只输出以下 JSON，不要输出其他解释：

{
  "source_id": "...",
  "source_type": "research_paper / phd_thesis / unknown",
  "literature_usability": {
    "decision": "yes / partial / no",
    "reason": "简要说明该文献是否适合构建 CoT",
    "usable_parts": ["可用章节、图表、实验部分或补充信息位置"]
  },
  "key_information": {
    "research_object": "具体材料、分子、体系或研究对象",
    "research_goal": "文献想提升、解释、筛选、优化或验证的核心目标",
    "baseline_or_problem": "基准样品、原始体系、空白组或待解决短板",
    "key_variables": [
      "被改变的结构、组成、配方、工艺、条件或候选对象"
    ],
    "control_or_comparison_samples": [
      "对照样品、系列样品、候选对象、失败样品或商业对照"
    ],
    "performance_metrics": [
      "性能指标、单位和测试条件"
    ],
    "main_observed_results": [
      "主要实验结果、趋势或性能对比，只写事实"
    ],
    "mechanism_or_explanation": [
      "有表征、计算或对照证据支撑的机制解释"
    ],
    "process_or_recipe_information": [
      "关键工艺条件、配方组分、比例、浓度、温度、时间、溶剂、pH 等"
    ],
    "failure_or_limitations": [
      "失败现象、副作用、负例、条件限制或文献未解决问题"
    ],
    "evidence_locations": [
      "支撑上述信息的章节、图、表或补充信息位置"
    ]
  },
  "cot_type_judgement": [
    {
      "cot_type": "性能提升路径 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "为什么可构建或不可构建",
      "key_evidence": ["支撑该判断的关键证据"],
      "missing_or_risky_evidence": ["缺失证据或构建风险"]
    },
    {
      "cot_type": "构效关系 / 结构-性能关系 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "候选分子 / 材料优选决策 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "反事实结构改造 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "失败原因诊断 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "多目标约束优化 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "机理到设计策略迁移 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "实验条件 / 制备工艺优化 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "实验方案生成 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    },
    {
      "cot_type": "实验设计配方 CoT",
      "decision": "build / build_with_caution / not_build",
      "priority": "high / medium / low",
      "reason": "...",
      "key_evidence": ["..."],
      "missing_or_risky_evidence": ["..."]
    }
  ],
  "recommended_next_action": {
    "priority_cot_types": ["优先构建的 CoT 类型"],
    "types_to_skip": ["不建议构建的 CoT 类型"],
    "notes_for_next_step": "进入后续 input 构建时需要保留的关键边界、条件或风险"
  }
}

判定参考：
- 性能提升路径：需要有基准短板、改性变量、性能提升和机制证据。
- 构效关系：需要有同系列样品、系统变量和性能趋势。
- 候选优选：需要有多个候选对象和可比较指标。
- 反事实结构改造：需要有可替换结构变量、相似对照或趋势证据。
- 失败原因诊断：需要有失败样品、性能下降、副作用或失效证据。
- 多目标约束优化：需要有两个及以上目标，并体现冲突或折中。
- 机理到设计策略迁移：需要有已验证机制和可调控变量。
- 实验条件 / 工艺优化：需要有工艺参数变化范围、性能响应趋势和最优窗口。
- 实验方案生成：需要有明确目标、候选变量、对照逻辑和验证方法。
- 实验设计配方：需要有配方组分、比例/浓度范围、工艺条件和性能反馈。