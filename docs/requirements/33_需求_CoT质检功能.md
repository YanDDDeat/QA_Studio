# 33 CoT质检功能

## 背景

在 COT/H-CoT 标注流水线中，生成的思维链数据需要质量评估。当前项目已有通用质检模块（`quality_check`），但该模块主要评估 `input` 和 `output` 字段，不专门针对思维链 (`chain_of_thought`) 的推理质量进行四维度深度评估。

本需求新增 **CoT质检** 功能，位于「CoT/H-CoT 标注」目录下，使用专门的 CoT 质检提示词（4 维度评估框架）对带思维链的 JSON 数据进行 LLM 评估，然后按评级分桶输出。

## 输入

- 一个 JSON 文件，每条记录包含三个核心字段：
  - `input`：原始提问或问题陈述
  - `chain_of_thought`（或 `cot`）：思维链步骤
  - `output`：基于思维链生成的最终回答

## 输出

一个输入文件产出 **三个** JSON 文件：

| 文件 | 内容 | 评级范围 |
|------|------|----------|
| 通过文件 | 评级为「良好」或「优秀」的原始数据 | 良好、优秀 |
| 不通过文件 | 评级为「存在缺陷」或「严重错误」的原始数据 | 存在缺陷、严重错误 |
| 评估结果文件 | 所有原始数据 + 每条附加 LLM 返回的完整评估结果 | 全部 |

## 详细规则

### 1. 评估维度（来自 CoT质检提示词.md）

LLM 对每条数据按四个维度评估：

- **维度一：问题的科学性与逻辑自洽性** — 问题前提、变量设定、任务目标是否合理
- **维度二：思维链的推理严密性** — 推理路径完整性、因果推断可靠性、反例处理、边界条件明确性
- **维度三：最终回答的知识准确性与完整性** — 知识准确性、内容完整性、结论恰当性、知识深度
- **维度四：问题、思维链与答案的整体一致性** — 任务响应度、信息传递保真度、复杂性匹配

### 2. 评级分桶规则

LLM 返回的 JSON 中 `overall_quality` 字段值为：

| overall_quality 值 | 分桶 | 说明 |
|---------------------|------|------|
| 优秀 | 通过 | 高质量数据 |
| 良好 | 通过 | 可接受数据 |
| 存在缺陷 | 不通过 | 有问题但可修正 |
| 严重错误 | 不通过 | 根本性错误 |

### 3. 评估结果文件格式

每条记录在原始数据基础上附加 `cot_quality_assessment` 字段，内容为 LLM 返回的完整评估 JSON：

```json
{
  "input": "...",
  "chain_of_thought": "...",
  "output": "...",
  "cot_quality_assessment": {
    "overall_quality": "良好",
    "evaluation_summary": "...",
    "detailed_assessment": {
      "dimension_1_problem_soundness": { "rating": "...", "comments": "..." },
      "dimension_2_cot_rigor": { "rating": "...", "comments": "..." },
      "dimension_3_answer_quality": { "rating": "...", "comments": "..." },
      "dimension_4_overall_consistency": { "rating": "...", "comments": "..." }
    },
    "critical_flaw_analysis": "..."
  }
}
```

### 4. 处理流程

1. 用户选择已上传的 JSON 文件 + 输入输出名称
2. 后端验证文件包含 `input`、`chain_of_thought`/`cot`、`output` 字段
3. 创建 Task（stage=cot_quality_check），启动后台异步任务
4. 对每条记录：构造 prompt → 调用 LLM → 解析 JSON 评估结果 → 按评级分桶
5. 创建三个输出 File 记录 + 物理 JSON 文件
6. 更新 Task 状态为 completed，记录统计结果到 TaskLog

### 5. LLM 调用策略

- 使用项目统一 `call_llm_json()` 服务
- System prompt = CoT质检提示词.md 内容
- User prompt = 格式化的单条 COT 数据（input + chain_of_thought + output）
- 温度 0.3（低温度，追求确定性评估）
- 逐条调用，带进度更新（progress_current/progress_total）
- 单条失败时记录错误但不中断整体流程，该条归入「不通过」文件

### 6. 字段别名兼容

输入 JSON 中的思维链字段名可能是 `chain_of_thought` 或 `cot`，需兼容两种命名：
- 优先取 `chain_of_thought`，若为空则取 `cot`
- 构造 LLM prompt 时统一使用 `chain_of_thought` 命名

## UI/接口变更

### 前端页面

新增 `CotQualityCheck.vue` 页面，位于 CoT/H-CoT 标注侧边栏子菜单下：

- **配置区**：文件选择器（FileSelector）、输出名称输入、LLM 配置选择（可选）、开始按钮
- **结果区**：统计展示（总记录数、通过数/率、不通过数/率）+ 三个下载按钮
- **进度区**：进度条 + 任务日志
- **源文件预览区**：与 CotFilter.vue 模式一致

### 侧边栏

在 `group-cot-hcot` 子菜单下新增一项：
- 路径：`/cot-quality-check`
- 名称：CoT质检
- 图标：CircleCheck

### 后端接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/cot-quality-check/start` | POST | 启动 CoT 质检任务 |
| `/api/cot-quality-check/status/{task_id}` | GET | 查询任务状态 |
| `/api/cot-quality-check/source-files` | GET | 列出可用源文件 |

## 数据库变更

无表结构变更。仅在 `StageEnum` 中新增 `COT_QUALITY_CHECK = "cot_quality_check"` 值，由于使用 VARCHAR 存储（native_enum=False），无需迁移脚本。