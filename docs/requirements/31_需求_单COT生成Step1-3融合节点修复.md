# 需求 31：单COT生成 Step1-3 融合节点修复

## 背景

当前「单COT生成」流程在 `professional_cot_service.py` 中依次执行 `_run_step1`、`_run_step2`、`_run_step3`，分别从 `专业Cot构建.md` 提取 Step 1/2/3 提示词并进行 3 次 LLM 调用：文献可用性筛选、案例卡抽取、CoT 类型判定。

但现有类型专属 Step 4/5 提示词已经以 `step1_3_result` 作为上游输入，真实业务理解应为：使用融合提示词 `docs/background/3类COT提示词/step1_3_integrated_extraction_and_routing.md`，在一个节点、一次 LLM 调用中完成文献可用性判断、关键信息抽取和 CoT 类型路由。

本需求修复单COT生成流程的节点定义与执行逻辑，使 Step 1-3 作为一个融合节点展示和落盘，同时保持 Step 4/5/6 类型专属生成逻辑不变。

## 输入输出定义

### 输入

- 单COT生成任务的源 JSON 数组记录。
- 用户选择的文本字段，例如 `text`。
- 单篇文献完整正文 `paper_text`。
- 可选来源标识：
  - `source_label`：记录中的 `source` 或默认 `item_N`。
  - `source_id`：记录中可用的来源编号；没有时可使用 `source_label`。
- 任务启动时保存的提示词快照目录 `prompts/`。
- LLM 配置与模型信息。

### 输出

每篇文献新增融合节点产物：

```json
{
  "step": "1-3",
  "step_name": "文献信息抽取与 CoT 类型路由",
  "status": "completed",
  "cot_type": "性能提升路径 CoT",
  "cot_type_key": "performance_improvement",
  "result": {
    "source_id": "...",
    "source_type": "research_paper",
    "literature_usability": {
      "decision": "yes",
      "reason": "...",
      "usable_parts": []
    },
    "key_information": {},
    "cot_type_judgement": [],
    "recommended_next_action": {
      "priority_cot_types": ["性能提升路径 CoT"],
      "types_to_skip": [],
      "notes_for_next_step": "..."
    },
    "recommended_cot_type": "性能提升路径 CoT",
    "recommended_cot_type_key": "performance_improvement"
  }
}
```

manifest 步骤从 6 个逻辑节点调整为 4 个展示节点：

1. Step 1-3：文献信息抽取与 CoT 类型路由
2. Step 4：生成 input
3. Step 5：生成 chainofThought
4. Step 6：生成 output

融合节点推荐产物文件名：`step1_3_integrated_extraction_and_routing.json`。

## 详细规则

1. 提示词读取规则：
   - 若存在任务提示词快照目录，优先读取快照中的 `common.step1_3`。
   - 无快照时读取系统默认文件 `docs/background/3类COT提示词/step1_3_integrated_extraction_and_routing.md`。
   - 用户旧模板缺少融合提示词文件时，应在模板 ensure / 读取 / 快照创建时自动补默认文件，避免任务创建失败。
2. LLM 调用规则：
   - Step 1-3 融合节点只能调用一次 LLM。
   - 强制 JSON 顶层对象。
   - 强制只在当前支持的 10 类 CoT 枚举中输出和推荐类型。
   - 不得在融合节点生成最终训练样本、input、chainofThought 或 output。
3. 融合结果规范化规则：
   - `literature_usability.decision` 规范为 `yes` / `partial` / `no`。
   - `cot_type_judgement[*].cot_type` 尽量规范为 10 类枚举 display_name，并补充 `cot_type_key`。
   - `cot_type_judgement[*].decision` 规范为 `build` / `build_with_caution` / `not_build`。
   - `cot_type_judgement[*].priority` 规范为 `high` / `medium` / `low`。
   - `recommended_next_action.priority_cot_types` 规范为 10 类枚举 display_name 列表。
   - 补充 `recommended_cot_type` 与 `recommended_cot_type_key`：优先取 `priority_cot_types` 第一项；若为空，则从 `cot_type_judgement` 中 `decision` 为 `build` 或 `build_with_caution` 且优先级较高的类型回退选择。
4. 跳过规则：
   - 若 `literature_usability.decision` 为 `no`，则跳过 Step 4/5/6，并在 manifest 和文档结果中记录跳过原因。
   - 若无法得到 `recommended_cot_type`，则跳过 Step 4/5/6，并记录证据缺口或推荐缺失原因。
5. 后续步骤输入规则：
   - Step 4 和 Step 5 的 prompt 注入 `step1_3_result`，不再分散注入 `step1`、`case_card`、`step3`。
   - Step 6 可继续使用 Step 4/5 结果。
6. 兼容规则：
   - 单文档 legacy artifact 复制逻辑需兼容新的 `step1_3_integrated_extraction_and_routing.json`。
   - 旧 run 的展示与历史产物不要求迁移。
   - 保留批量单COT类型展示修复中 run 级 CoT 类型汇总推断逻辑。

## UI / 接口变更说明

### UI

- 单COT生成任务详情中的步骤列表由后端 manifest 驱动，展示为 4 个节点。
- 提示词模板管理页面通用步骤变量提示从旧 `common.step1` / `common.step2` / `common.step3` 调整为 `common.step1_3`。
- 不新增前端页面，不改变列表页 CoT 类型展示规则。

### 接口

- 不新增接口。
- 不改变接口路径。
- 提示词模板接口返回的通用步骤树中，新模板应展示 `common.step1_3` 融合节点；旧 `common.step1/2/3` 可保留读取兼容，但不作为新树的通用节点展示。
- run manifest 的 `steps` 结构减少为 4 个展示节点，`total_steps` 应随 manifest 自动刷新为 4。

## 验收标准

1. 新建单COT任务时，manifest 初始步骤为 4 个节点，第一项为 `step1_3_integrated`。
2. 单篇文献处理 Step 1-3 只进行一次 LLM 调用，并写入 `step1_3_integrated_extraction_and_routing.json`。
3. 当融合结果 `literature_usability.decision = no` 时，任务跳过 Step 4/5/6，并记录跳过原因。
4. 当融合结果没有可识别推荐类型时，任务跳过 Step 4/5/6，并记录证据缺口或推荐缺失原因。
5. 当融合结果推荐有效 CoT 类型时，Step 4/5/6 继续生成最终样本，且 Step 4/5 prompt 使用 `step1_3_result`。
6. 提示词模板系统默认模板和用户旧模板缺少 `common.step1_3` 时可自动补默认文件，任务创建不失败。
7. 单文档 legacy artifact 复制后，run 根目录可读取新融合节点 JSON。
8. 需求30批量 CoT 类型汇总展示逻辑不被破坏。
9. 改动 Python 文件通过语法检查；如存在相关测试，应通过最小相关测试。
