# 35_需求_CoT质检兼容 samples 数组

## 背景

当前 CoT 质检支持顶层为 JSON 数组，或顶层为单条对象且对象顶层直接包含 `input`、`chain_of_thought`/`chainofThought`/`cot`、`output` 字段的文件。

标注流水线2/单 COT 生成产物可能采用带元信息的包装结构：

```json
{
  "schema_version": "1.0",
  "run_id": "...",
  "pipeline_name": "单COT生成流水线",
  "sample_count": 4,
  "samples": [
    {
      "input": "...",
      "chainofThought": ["步骤 1：...", "步骤 2：..."],
      "output": "..."
    }
  ]
}
```

这种结构下，真正待质检的数据位于顶层 `samples` 数组中。当前逻辑会把整个对象当作 1 条记录，导致字段校验失败，无法生成多条质检结果。

## 输入输出定义

### 输入

CoT 质检源文件为 JSON，需兼容以下形式：

1. 顶层数组：
   ```json
   [
     {"input": "...", "chainofThought": "...", "output": "..."}
   ]
   ```

2. 顶层单条对象：
   ```json
   {"input": "...", "chainofThought": "...", "output": "..."}
   ```

3. 顶层包装对象，数据在 `samples` 数组：
   ```json
   {
     "schema_version": "1.0",
     "sample_count": 4,
     "samples": [
       {"input": "...", "chainofThought": ["步骤 1", "步骤 2"], "output": "..."}
     ]
   }
   ```

### 输出

CoT 质检仍输出三个文件：

- `通过`：`overall_quality` 为 `合格` 的样本原记录；
- `不通过`：`overall_quality` 为 `存在缺陷`/`严重错误`/未知评级/LLM 调用失败的样本原记录；
- `评估结果`：样本原记录追加 `cot_quality_assessment` 字段。

对于 `samples` 包装对象，若 `samples` 中有 4 条记录，应生成 4 条独立质检结果，进度总数也应为 4。

## 详细规则

1. CoT 质检读取源 JSON 后，应先标准化为“待质检记录数组”。
2. 若顶层是数组，沿用现有逻辑。
3. 若顶层是对象且存在 `samples` 字段，并且 `samples` 是数组，则使用 `samples` 作为待质检记录数组。
4. 若顶层是对象且不存在可识别的集合字段，则沿用现有逻辑，将该对象作为单条记录。
5. 标准化后继续执行现有嵌套 CoT 节点展开逻辑，兼容 `l0_cot_node`、`l1_cot_node`、`l2_cot_node`、`cot_node`、`hcot_node`。
6. 字段校验仍要求记录包含：
   - `input`
   - `chain_of_thought` 或 `chainofThought` 或 `cot`
   - `output`
7. `chainofThought`/`chain_of_thought`/`cot` 如果是数组，应在构造 LLM prompt 时转成换行文本，而不是 Python/JSON 数组字符串，提升质检可读性。
8. 记录中的其它字段，如 `source_type`、`source_index`、`source`、`cot_type`、`evidence_trace` 等，应在输出文件中保留。
9. 不要求本次改动递归解析任意 JSON 树结构；仅明确兼容顶层 `samples` 包装格式。

## UI / 接口变更说明

### 后端

- 修改 CoT 质检数据读取/标准化逻辑，使 `/api/cot-quality-check/start` 在字段校验和后台执行时均使用同一标准化规则。
- 优化 CoT 字段格式化逻辑，支持数组转换为换行文本。

### 前端

- 无新增 UI 控件。
- 文件预览仍显示原始 JSON 结构即可；本需求仅影响后端质检任务实际处理条数和结果。

## 验收标准

1. 使用 `C:\Users\86155\Desktop\1111111111111111ples.json` 这类顶层 `samples` 文件启动 CoT 质检时，字段校验应通过。
2. 该文件 `samples` 中有 4 条数据时，任务 `progress_total` 应为 4。
3. 完成后 `评估结果` 文件应包含 4 条记录，每条记录都带有独立的 `cot_quality_assessment`。
4. `chainofThought` 为数组时，LLM prompt 中应按换行步骤展示。
