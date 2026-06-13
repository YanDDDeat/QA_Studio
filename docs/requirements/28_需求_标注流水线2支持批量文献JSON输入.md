# 需求 28：标注流水线2支持批量文献 JSON 输入

## 背景

当前「标注流水线2」用于专业 CoT 构建时，只支持上传/选择一个 JSON 数组长度为 1 的文件进行处理，实际等价于一个任务只能处理一篇文献或一个 chunk。

随着「CoT/H-CoT 标注」分组下新增“多 MD 合并 JSON”能力，用户可以将多篇 Markdown 文献合并为如下 JSON 数组：

```json
[
  {
    "source": "paper1.md",
    "text": "paper1 的 Markdown 全文"
  },
  {
    "source": "paper2.md",
    "text": "paper2 的 Markdown 全文"
  }
]
```

因此需要优化标注流水线2，使其支持数组长度大于 1 的 JSON 输入。目标是：100 篇文献合成一个 JSON 后，只创建 1 个标注流水线2任务，由任务内部逐篇处理，而不是创建 100 个独立任务。

## 目标

- 标注流水线2支持 JSON 数组长度 `>= 1` 的输入文件。
- 一个任务可以处理多篇文献。
- 第一版采用串行处理：同一任务内按数组顺序逐篇执行原有单篇流水线逻辑。
- 单篇文献失败不影响后续文献继续处理。
- 最终输出结果中记录每篇文献的处理状态、来源和结果。
- 第一版不新增数据库表/字段，不新增数据库迁移。

## 输入定义

### 文件格式

输入文件必须是 JSON 数组：

```json
[
  {
    "source": "paper1.md",
    "text": "paper1 content"
  }
]
```

### 数组长度

- 原限制：数组长度必须等于 1。
- 新规则：数组长度必须 `>= 1`。
- 空数组不允许启动任务。

### 文本字段

- 用户仍可在页面选择文本字段。
- 默认文本字段为 `text`。
- 每个元素都必须包含所选文本字段，且字段值不能为空字符串。

### 来源字段

- `source` 字段可选。
- 若存在，用于日志、结果标识和最终输出。
- 若不存在，系统使用 `item_<序号>` 作为默认来源标识，例如 `item_1`。

## 处理规则

### 任务粒度

- 上传/选择一个多元素 JSON 后，只创建一个标注流水线2任务。
- 不为每篇文献创建独立任务。
- 任务内部按数组顺序逐篇处理文献。

### 执行方式

第一版采用串行处理：

```text
任务 A
  - 第 1 篇文献：执行完整流水线2
  - 第 2 篇文献：执行完整流水线2
  - 第 3 篇文献：执行完整流水线2
  ...
```

暂不做文献级并发，避免 LLM 并发压力、进度混乱和失败恢复复杂化。后续如需提速，可扩展“最大并发数”配置。

### 单篇处理逻辑

每篇文献应复用现有单篇/单 chunk 的流水线2逻辑。实现时建议将现有单篇处理主流程抽取为内部函数，例如：

```python
process_one_document(record, text_field, index, total)
```

批量任务主流程负责：

1. 读取输入 JSON 数组。
2. 校验数组长度和每篇文献文本字段。
3. 逐篇调用单篇处理逻辑。
4. 捕获单篇异常，记录失败并继续下一篇。
5. 汇总全部文献结果，写入最终产物。

### 失败策略

- 单篇文献失败：记录该文献失败状态、错误信息，继续处理后续文献。
- 全部文献成功：任务状态为完成。
- 部分文献失败：第一版任务整体仍可标记为完成，但最终结果中必须明确 `failed_count > 0`，并记录失败文献明细。
- 全部文献失败或任务初始化失败：任务状态为失败。

第一版不新增 `partial_failed` 任务状态，避免数据库和状态枚举变更。后续如需要更精细展示，可另行新增部分失败状态。

### 进度与日志

任务日志应记录文献级进度，例如：

```text
开始处理第 1/100 篇：paper1.md
第 1/100 篇处理完成：paper1.md
开始处理第 2/100 篇：paper2.md
第 2/100 篇处理失败：paper2.md，错误：xxx
```

任务进度第一版可以按文献数粗略推进：

- `progress_total = 文献数量`
- 每完成一篇文献后 `progress_current += 1`

如果现有流水线2已经使用阶段级进度，也可以折算为：

- `progress_total = 文献数量 × 单篇阶段数`
- 每篇每阶段完成后递增。

具体采用哪种方式，以现有任务进度实现改动最小为准。

## 输出定义

### 批量结果汇总

最终输出应包含批量处理摘要和每篇文献状态：

```json
{
  "input_count": 2,
  "success_count": 1,
  "failed_count": 1,
  "items": [
    {
      "source_index": 0,
      "source": "paper1.md",
      "status": "success",
      "result": {
        "final_samples": []
      }
    },
    {
      "source_index": 1,
      "source": "paper2.md",
      "status": "failed",
      "error": "处理失败原因"
    }
  ]
}
```

### final_samples 输出

若现有流水线2会生成 `final_samples.json` / `final_samples.jsonl`，批量模式下应保持下载能力：

- `final_samples.json`：包含所有成功文献产生的样本。
- `final_samples.jsonl`：包含所有成功文献产生的样本，每行一个样本。
- 每条样本建议补充来源信息：
  - `source_index`
  - `source`

这样后续查看或质检时可以追溯样本来自哪篇文献。

### 失败文献输出

失败文献不应混入 `final_samples`，但应在批量汇总结果中记录：

- `source_index`
- `source`
- `status = failed`
- `error`

## 前端变更说明

### 标注流水线2配置页

- 取消“JSON 数组长度必须为 1”的限制。
- 允许选择数组长度大于 1 的 JSON 文件。
- 字段选择逻辑保持不变，默认文本字段仍为 `text`。
- 启动前提示当前输入文件包含的文献数量。
- 页面文案从“单 chunk JSON”调整为“单篇或多篇 JSON”。

### 任务列表/详情页

第一版保持现有任务列表结构，不新增独立文献任务。

详情页建议展示：

- 输入文献总数。
- 成功数量。
- 失败数量。
- 最终产物下载入口。
- 文献级失败明细可通过日志或汇总 JSON 查看。

如现有接口无法方便返回成功/失败数量，第一版可以先通过最终结果文件体现。

## 后端变更说明

### 接口层

- 取消数组长度等于 1 的校验。
- 保留 JSON 必须为数组、数组不能为空、文本字段必填的校验。
- 接口返回中可增加输入文献数量，便于前端提示。

### 服务层

- 将现有单篇流水线处理逻辑抽取为可复用函数。
- 批量入口按数组顺序循环调用单篇处理函数。
- 单篇异常在文献级捕获，不直接终止整个任务。
- 汇总成功、失败数量和每篇处理结果。
- 输出文件继续使用现有文件管理/下载机制。

建议服务层形成如下结构：

```text
run_professional_cot_task()
  ├─ resolve_prompt_template()
  ├─ create_prompt_snapshot()
  ├─ load_input_records()
  ├─ validate_records()
  ├─ for each record:
  │    └─ process_one_document(document_context)
  ├─ write_batch_summary()
  └─ write_final_samples()
```

`process_one_document()` 不应自行读取仓库默认提示词文件，而应从 run 级上下文中取得提示词快照或 Prompt Provider。建议上下文包含：

```json
{
  "run_id": 1,
  "text_field": "text",
  "source_index": 0,
  "source": "paper1.md",
  "prompt_snapshot_dir": "storage/professional_cot_runs/1/prompts",
  "document_output_dir": "storage/professional_cot_runs/1/documents/0001_paper1"
}
```

## 与需求 29：提示词模板管理的配合

需求 29「标注流水线2提示词模板管理」引入 run 级提示词模板包和提示词快照。本需求与其配合时遵循以下规则：

1. 一个批量 run 只选择一个完整提示词模板包版本。
2. 不支持在同一个批量 run 内为不同文献选择不同模板。
3. run 创建时先确定 `prompt_template_id`，并在处理第一篇文献前生成完整提示词快照。
4. 批量 run 内所有文献都从同一个 run 快照读取 Prompt。
5. 用户在任务运行中修改模板，不影响当前 run 正在处理或尚未处理的文献。
6. 若需求 29 尚未实现，当前版本可使用系统默认提示词作为临时 Prompt Provider，但单篇处理逻辑仍应通过 Provider/快照接口读取 Prompt，避免后续重复重构。
7. 新建任务接口若已接入需求 29，应接收 `prompt_template_id`；若未传入，则按需求 29 的默认模板规则解析。
8. 批量汇总结果应记录本次使用的模板信息引用，例如 `prompt_template_id`、`prompt_template_name`、`prompt_snapshot_path`。

批量 run 的创建顺序应为：

```text
创建 run
  ↓
确定 prompt_template_id
  ↓
生成 prompts/ 快照
  ↓
读取并校验输入 JSON 数组
  ↓
逐篇处理 documents[0..n]
  ↓
写入 batch_summary.json 和聚合 final_samples
```

## 批量产物目录结构

批量模式下，不能继续让每篇文献写入相同的 `step1.json`、`step2.json` 等固定文件名，否则后处理的文献会覆盖前面文献的阶段产物。

建议 run 目录结构如下：

```text
storage/professional_cot_runs/<run_id>/
├─ manifest.json
├─ prompts/
│  ├─ manifest.json
│  ├─ common/
│  └─ cot_types/
├─ documents/
│  ├─ 0001_paper1/
│  │  ├─ input.json
│  │  ├─ step1.json
│  │  ├─ step2.json
│  │  ├─ step3.json
│  │  ├─ step4.json
│  │  ├─ step5.json
│  │  ├─ step6.json
│  │  └─ final_samples.json
│  ├─ 0002_paper2/
│  │  └─ ...
│  └─ ...
├─ batch_summary.json
├─ final_samples.json
└─ final_samples.jsonl
```

规则：

- `prompts/` 保存本次 run 的提示词快照，对应需求 29。
- `documents/<序号>_<source>/` 保存单篇文献的输入、阶段产物和单篇最终样本。
- 根目录 `batch_summary.json` 保存批量摘要、每篇状态、失败明细和模板信息引用。
- 根目录 `final_samples.json` / `final_samples.jsonl` 保存所有成功文献样本的聚合结果。
- 目录名中的 `source` 应做安全化处理，避免特殊字符影响路径；若 source 缺失，则使用 `item_<序号>`。

### 数据库

第一版不新增数据库表/字段，不新增迁移脚本。

所有文献级状态和错误明细写入任务日志和最终输出 JSON。

## 非目标

本需求第一版不做以下内容：

- 不做文献级并发处理。
- 不新增每篇文献的独立子任务。
- 不新增数据库表/字段。
- 不新增 `partial_failed` 任务状态。
- 不做单篇文献失败后的单独重试。
- 不支持同一批量 run 内不同文献使用不同提示词模板。
- 不为每篇文献重复创建提示词快照。
- 不对 MD 内容进行切分、清洗、标题识别或 token 过滤。
- 不改变“多 MD 合并 JSON”的输出格式。

## 验收标准

1. 标注流水线2可选择/上传 JSON 数组长度大于 1 的文件并启动任务。
2. JSON 数组为空时，前端或后端明确提示不允许启动。
3. 每个元素缺少所选文本字段或文本为空时，任务启动前应提示具体问题。
4. 一个多文献 JSON 只创建一个标注流水线2任务。
5. 任务内部按数组顺序逐篇处理文献。
6. 单篇文献失败后，后续文献仍会继续处理。
7. 最终输出包含 `input_count`、`success_count`、`failed_count` 和每篇文献状态。
8. 成功文献产生的最终样本仍可通过 `final_samples.json` / `final_samples.jsonl` 下载。
9. 批量输出中的样本可追溯到原始文献，至少包含 `source_index`，有 `source` 时也应保留。
10. 批量模式下每篇文献的阶段产物写入独立 `documents/<序号>_<source>/` 目录，不互相覆盖。
11. 若接入需求 29，批量 run 内所有文献共用同一个提示词模板快照，且运行中修改模板不影响当前 run。
12. 第一版不产生数据库迁移。
