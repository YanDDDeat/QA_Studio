你是一名材料/化学领域 CoT 数据构建专家。请根据已生成的 input 和文献证据，为“机理到设计策略迁移 CoT”生成 chainofThought。

你只需要生成 chainofThought，不要生成最终 output。

输入：
step1_3_result:
<粘贴融合 Step 1-3 的输出 JSON，尤其是 key_information、mechanism_or_explanation、cot_type_judgement>

step4_input_result:
<粘贴 Step 4 生成的 JSON，尤其是 selected_input、input_elements、evidence_used>

目标 CoT 类型：
机理到设计策略迁移 CoT

生成要求：
1. chainofThought 必须围绕 selected_input 展开。
2. 每一步都必须服务于后续 output 中的设计策略形成。
3. 必须先明确已知机制 M 及其作用对象。
4. 必须识别机制 M 对应的可调控变量，例如结构、组分、缺陷、晶相、界面、孔结构、官能团、金属中心、侧链、溶剂环境等。
5. 必须分析每个变量如何影响机制 M，以及机制 M 如何影响目标性能 Z。
6. 必须从机制 M 迁移得到新的设计策略，而不是只复述原体系结论。
7. 必须判断策略适用条件和不适用场景。
8. 必须识别潜在副作用，例如稳定性下降、传输受阻、活性与选择性冲突、合成难度增加、安全性降低、成本升高等。
9. 必须给出验证策略，例如结构表征、性能测试、原位表征、动力学实验、稳定性测试或计算验证。
10. 不能引入文献没有支撑的新机制、新变量或新性能结论。
11. 如果只有相关性证据，不要写成确定因果，应使用“可能”“表明”“支持”等限定表达。
12. chainofThought 必须是去文献化的训练文本，不能出现任何文献来源痕迹。
13. 不要在 chainofThought 中出现“根据文献”“文献报道”“本文报道”“作者发现”“图 1”“表 1”“章节”“补充信息”“Figure”“Fig.”“Table”等表达。
14. 不要在 chainofThought 中用括号标注证据来源。
15. 图号、表号、章节号、文献证据位置只能写入 evidence_used，不得写入 chainofThought。
16. chainofThought 必须完成“证据内化”：不要描述证据来自哪里或如何验证得到，而要把证据转写为机制事实、变量关系、条件约束和专业判断。
17. 不要使用“根据已有数据”“机理表征表明”“实验表明”“结果显示”“数据说明”“从图中可以看出”等证据过程表达。
18. 不要生成最终 output。

推荐推理步骤结构：
1. 提取已知机制 M 及其作用对象。
2. 判断 M 对应哪些可调控设计变量。
3. 分析这些变量如何影响 M。
4. 连接 M 与目标性能 Z。
5. 从 M 迁移得到新的设计策略。
6. 判断策略适用条件和潜在副作用。
7. 给出验证策略和关键指标。
8. 说明边界条件和下一轮优化方向。

请按以下 JSON 输出：

{
  "cot_type": "机理到设计策略迁移 CoT",
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
    "每条关键推理所依赖的文献信息，保留机制、变量、性能指标、验证方法或边界；这些来源信息不得出现在 chainofThought 中"
  ],
  "boundary_conditions": [
    "推理成立所依赖的材料体系、机制适用范围、测试条件或应用场景"
  ],
  "quality_check": {
    "follows_selected_input": true,
    "has_known_mechanism": true,
    "maps_mechanism_to_variables": true,
    "links_variables_to_target_performance": true,
    "derives_new_design_strategy": true,
    "has_applicability_boundary": true,
    "identifies_potential_side_effects": true,
    "includes_validation_strategy": true,
    "avoids_unsupported_claims": true,
    "chain_is_de_literaturized": true,
    "chain_has_no_source_mentions": true,
    "chain_has_no_figure_or_table_mentions": true,
    "chain_internalizes_evidence": true,
    "chain_has_no_evidence_process_phrases": true,
    "does_not_generate_output": true
  }
}