# 37_需求_CoT质检提示词可配置

## 背景

当前「CoT/H-CoT 标注 -> CoT质检」使用的 system prompt 写死在 `backend/app/services/cot_quality_check_service.py` 的 `COT_QUALITY_CHECK_SYSTEM_PROMPT` 常量中。用户无法在页面上调整评估维度、评级口径或输出 JSON 字段说明，只能修改代码后重启服务，影响不同数据批次和不同领域的质检策略迭代。

项目已有通用 Prompt 表和 `/api/prompts` 接口，且 `cot_quality_check` 已作为独立阶段存在，因此 CoT 质检应复用现有提示词配置能力：默认提供内置提示词兜底，同时允许用户创建、选择、更新阶段提示词。

## 输入输出定义

### 输入

1. CoT 质检源文件：保持现有 JSON 文件选择逻辑不变。
2. LLM 配置与模型：保持现有选择逻辑不变。
3. 质检提示词：新增可选配置项，来源为 `prompts` 表中 `stage = cot_quality_check` 的用户提示词和全局提示词。

### 输出

CoT 质检仍输出三个 JSON 文件：

- `通过`：`overall_quality` 为 `合格` 的样本原记录；
- `不通过`：`overall_quality` 为 `存在缺陷`/`严重错误`/未知评级/LLM 调用失败的样本原记录；
- `评估结果`：样本原记录追加 `cot_quality_assessment` 字段。

任务记录应保存本次使用的 `prompt_id`，便于状态接口和历史任务追溯。

## 详细规则

1. 后端启动 CoT 质检时，如果请求携带 `prompt_id`，应校验该提示词属于当前用户或为全局共享提示词，且阶段为 `cot_quality_check`。
2. 如果请求未携带 `prompt_id`，应优先使用当前用户或全局共享的默认 `cot_quality_check` 提示词。
3. 如果数据库中没有可用默认提示词，应回退到现有内置 `COT_QUALITY_CHECK_SYSTEM_PROMPT`，保证旧环境无需迁移也能继续运行。
4. 前端 CoT 质检配置区新增「质检提示词」选择，展示阶段为 `cot_quality_check` 的可用提示词，并支持查看/编辑提示词内容。
5. 用户编辑提示词时应复用现有 `/api/prompts` 创建/更新能力，避免新增数据库表。
6. 启动任务时应将选择的 `prompt_id` 传给 `/api/cot-quality-check/start`。
7. LLM 配置和模型选择仍以页面选择为准；若提示词自带模型或 LLM 配置，可作为默认填充值，但不应覆盖用户在页面上显式选择的值。
8. 本需求不涉及数据库表结构变更，不编写迁移脚本。

## UI / 接口变更说明

### 后端

- 调整 `/api/cot-quality-check/start` 的提示词解析逻辑，支持阶段默认提示词和内置兜底。
- 校验 `prompt_id` 的权限与阶段，避免选择其它阶段提示词误用。
- 可新增 `/api/cot-quality-check/default-prompt` 或复用 `/api/prompts?stage=cot_quality_check`，用于前端加载默认提示词。

### 前端

- `CotQualityCheck.vue` 新增提示词选择与编辑入口。
- 进入页面时加载 `cot_quality_check` 阶段提示词，若无用户提示词则允许基于内置/默认内容创建一份。
- 启动 CoT 质检时传递 `prompt_id`。

## 验收标准

1. 页面可查看当前 CoT 质检提示词，不再只能依赖代码常量。
2. 用户修改并保存提示词后，再次启动任务会使用修改后的提示词。
3. 未选择提示词或数据库没有提示词时，CoT 质检仍可使用内置默认提示词正常运行。
4. 尝试传入其它阶段或无权限的 `prompt_id` 时，后端返回明确错误。
5. 现有通过/不通过/评估结果文件输出格式保持兼容。
