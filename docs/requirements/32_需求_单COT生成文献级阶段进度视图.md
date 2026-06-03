# 需求 32：单COT生成文献级阶段进度视图

## 背景

当前「单COT生成」详情页主要展示 run 级总进度和线性步骤列表。批量输入 JSON 数组时，run 内会按文献逐篇处理，并在 `documents/<序号>_<source>/` 下保存每篇文献的 Step1-3 / Step4 / Step5 / Step6 中间产物，但详情页无法直观看到每篇文献在各阶段的完成、失败、跳过或等待状态。

多COT生成详情页已有「分段级阶段进度」矩阵，能用数字块按 chunk 展示阶段状态。本需求在单COT生成详情页新增同类「文献级阶段进度矩阵」：横向对象从 chunk 改为输入 JSON 数组中的文献 item，纵向阶段对应融合后的 4 个单COT节点。

## 输入输出定义

### 输入

- 单COT生成 run 的 `manifest.json`。
- run 目录下的源输入文件：
  - 优先 `source_input.json.records`。
  - 其次 `source.json` JSON 数组。
  - 再次 `batch_summary.json.items`。
- 每篇文献目录：`documents/<source_index+1四位序号>_<sanitize(source)>/`。
- 每篇文献的阶段产物：
  - `step1_3_integrated_extraction_and_routing.json`。
  - `<cot_type_key>/step4_input.json`。
  - `<cot_type_key>/step5_chain.json`。
  - `<cot_type_key>/step6_output.json`。
- 旧 run 兼容产物（尽量识别，不做迁移）：`step1_screening.json`、`step2_case_card.json`、`step3_type_judgement.json` 或旧式 `step1.json` / `step2.json` / `step3.json`。

### 输出

详情接口 `get_run_detail_for_user` 返回的 detail 新增字段：

```json
{
  "document_stage_matrix": [
    {
      "stage_key": "step1_3_integrated",
      "stage_name": "Step 1-3 文献信息抽取与 CoT 类型路由",
      "step": "1-3",
      "items": [
        {
          "source_index": 0,
          "source": "paper1",
          "status": "completed",
          "artifact_path": "documents/0001_paper1/step1_3_integrated_extraction_and_routing.json",
          "cot_type": "性能提升路径 CoT",
          "cot_type_key": "performance_improvement",
          "error": null,
          "progress_label": "已完成"
        }
      ]
    }
  ]
}
```

## 详细规则

1. 阶段定义固定为融合后的 4 个节点：
   - 阶段1：`step1_3_integrated`，Step 1-3 文献信息抽取与 CoT 类型路由。
   - 阶段2：`step4_input`，Step 4 生成 input。
   - 阶段3：`step5_chain`，Step 5 生成 chainofThought。
   - 阶段4：`step6_output`，Step 6 生成 output。
2. 文献列表来源优先级：
   - `source_input.json.records`，使用其中 `source_index` / `source`。
   - 若缺失，则从 `source.json` 数组按顺序读取 `source`。
   - 若仍缺失，则从 `batch_summary.json.items` 读取。
3. 文献目录名必须与后端 `_document_output_dir()` / `_sanitize_dirname()` 保持一致，避免前端构造路径。
4. 产物路径规则：
   - Step1-3 新 run 使用 `documents/0001_xxx/step1_3_integrated_extraction_and_routing.json`。
   - 旧 run 若不存在融合产物，可回退识别 `step3_type_judgement.json`、`step3.json`、`step2_case_card.json`、`step2.json`、`step1_screening.json`、`step1.json`。
   - Step4/5/6 需要先推断 `cot_type_key`，再使用 `documents/0001_xxx/<cot_type_key>/step4_input.json` 等路径。
5. `cot_type_key` 推断优先级：
   - `batch_summary.items[*].final_sample.cot_type_key` 或 `cot_type`。
   - Step1-3 产物中的 `cot_type_key` / `cot_type` / `result.recommended_cot_type_key` / `result.recommended_cot_type`。
   - 文献目录下匹配 10 类 CoT key 的子目录。
6. 状态推断规则：
   - 对应阶段产物文件存在：`completed`。
   - run 当前步骤显示正在处理该文献和该阶段：`running`。
   - 文献最终 `skipped` 且该阶段及后续无产物：`skipped`。
   - 文献最终 `failed` 时，首个缺失阶段标记为 `failed`，后续缺失阶段标记为 `pending`。
   - 未处理文献：`pending`。
7. Tooltip / title 信息应包含：文献来源、阶段名、状态、CoT 类型或错误原因。
8. 有 `artifact_path` 的文献阶段数字块可点击调用现有 `previewArtifact(path, title)` 预览中间产物；无产物不可点击。
9. 不新增数据库表/字段，不新增接口，不改变现有 artifact 读取接口。

## UI / 接口变更说明

### UI

- 在 `ProfessionalCotDetail.vue` 的总进度条后、线性步骤列表前新增「文献级阶段进度」卡片。
- 当 `run.document_stage_matrix` 存在且非空时展示。
- 每行代表一个阶段，左侧显示「文献级」标签、阶段名称和阶段说明，右侧以数字块展示各文献 item。
- 数字块显示 `source_index + 1`，按状态着色：
  - `completed`：绿色。
  - `running`：蓝色 / primary，并带轻微脉冲。
  - `failed`：红色。
  - `skipped`：黄色或灰色。
  - `pending`：灰色。
- 增加图例说明颜色含义。

### 接口

- 复用现有单COT生成详情接口。
- 响应体新增 `document_stage_matrix` 字段。
- 不新增路由，不改变请求参数，不改变现有字段含义。

## 验收标准

1. 批量单COT run 详情接口返回 `document_stage_matrix`，包含 4 个阶段和每篇文献 item。
2. 新 run 中已存在阶段产物的文献 item 标为 `completed`，并带可预览的 `artifact_path`。
3. 跳过文献在 Step4/5/6 显示为 `skipped`，tooltip 能看到跳过原因。
4. 失败文献至少能将首个缺失阶段标为 `failed`，tooltip 能看到失败原因。
5. 未处理文献显示为 `pending`，不提供点击预览。
6. 前端详情页在总进度后展示「文献级阶段进度」矩阵，点击有产物的数字块可打开现有预览弹窗。
7. 旧 6 步 run 缺少新融合产物时不报错，能尽量展示已有旧产物状态。
8. 不引入数据库变更，不新增接口。
9. 后端 Python 文件通过语法检查；前端至少通过可用的轻量构建或等价验证。
