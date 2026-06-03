# 需求 30：批量单COT类型展示修复

## 背景

用户反馈：在「单COT生成」任务列表中，某个批量任务已经显示 6/6 步、成功 3/3 篇、样本数 3，但「模型判定 CoT 类型」仍显示「待判定」。

现有前端列表显示逻辑依赖后端列表接口返回的 `recommended_cot_type.display_name` 或 `target_cot_type.display_name`。批量任务在逐篇处理过程中会把每篇文献的最终样本写入 `final_samples.json`，并在 `batch_summary.json` 中记录 `batch_items`，但 run 级 `recommended_cot_type` 在批量完成后可能仍为空，导致列表无法反映批量结果。

本需求做最小修复：不做数据库变更，不调整前端展示逻辑，后端在批量任务完成后或生成列表项时聚合已生成样本的 `cot_type`，返回可用于现有前端显示的 CoT 类型信息。

## 输入输出定义

### 输入

- 标注流水线2 run 的 `manifest.json`。
- 可选历史产物文件：
  - `final_samples.json`
  - `batch_summary.json`
- manifest 中已有字段：
  - `final_outputs`
  - `batch_items` 或批量汇总等价信息
  - `recommended_cot_type`
  - `target_cot_type`

### 输出

列表接口每个 run item 继续返回：

```json
{
  "recommended_cot_type": {"key": "performance_improvement", "display_name": "性能提升路径 CoT"},
  "target_cot_type": {"key": "performance_improvement", "display_name": "性能提升路径 CoT"}
}
```

当批量结果包含多个唯一 CoT 类型时，返回：

```json
{
  "recommended_cot_type": {"key": "multiple", "display_name": "多类型（性能提升路径 CoT、实验方案生成 CoT）"}
}
```

当无法从已有数据推断任何 CoT 类型时，保持 `None`，前端继续显示「待判定」。

## 详细规则

1. 优先保留 manifest 中已经存在且有效的 `recommended_cot_type` / `target_cot_type`。
2. 当 run 级类型为空时，从最终结果聚合 `final_sample.cot_type`：
   - `final_samples.json` 中的 `samples[*].cot_type`。
   - `batch_summary.json` 中 `items[*].final_sample.cot_type`。
   - manifest 中若存在 `batch_items` 或等价批量结果，也应兼容读取。
3. 聚合规则：
   - 0 个可识别类型：返回 `None`。
   - 1 个唯一类型：返回 `{key, display_name}`。
   - 多个唯一类型：返回 `{key: "multiple", display_name: "多类型（A、B、C）"}`。
4. 兼容历史已完成 run：不能只依赖新 run 完成时写入 manifest。`_manifest_to_list_item` 生成列表项时应能根据 `run_id` 安全读取 run 目录中的历史产物推断类型。
5. 读取历史文件时必须容错：文件不存在、JSON 损坏或结构不符合预期时，不影响列表接口返回。
6. 不执行数据库迁移，不新增或修改数据库表/列。

## UI / 接口变更说明

### UI

- 不修改前端组件。
- 继续使用现有展示逻辑：`row.recommended_cot_type?.display_name || row.target_cot_type?.display_name || '待判定'`。
- 修复后，批量任务若已有最终样本，列表应显示具体类型或「多类型（...）」而不是「待判定」。

### 接口

- 不新增接口。
- 不改变接口路径。
- `GET /api/professional-cot/runs` 或对应列表接口的单个 item 中，`recommended_cot_type` / `target_cot_type` 语义增强：批量 run 可由最终样本聚合得到展示类型。

## 验收标准

1. 单篇任务现有展示行为不回退。
2. 批量任务全部样本为同一 CoT 类型时，列表显示该类型。
3. 批量任务样本包含多个 CoT 类型时，列表显示「多类型（A、B、C）」。
4. 批量任务无成功样本或无法识别类型时，仍显示「待判定」。
5. 历史已完成 run 即使 manifest 未写 run 级 `recommended_cot_type`，只要 `final_samples.json` 或 `batch_summary.json` 中存在样本类型，列表也能显示。
6. Python 语法检查或相关测试通过。
