# 22. CoT/H-CoT 分 chunk 并行流水线

## 背景

当前 CoT/H-CoT 流水线把整个源文件内容一次性灌给 LLM，导致长论文（150 chunk）只生成 6 个事实卡，内容被截断，质量不足。

## 需求

### 核心改动：每个 chunk 独立走一遍完整流水线

- 读取源文件关联的 Dataset 列表（每个 chunk 的 `input` 字段为文本内容）
- 对每个 chunk，独立执行：fact_card_gen → sanitize → l0_gen → l1/l2 拆解 → CoT 生成
- 每个 chunk 生成自己的总问题（L0）和完整推理树
- 最终导出合并所有 chunk 的训练数据

### 数据库变更

| 表 | 字段 | 类型 | 说明 |
|---|---|---|---|
| Task | chunk_index | Integer, nullable | chunk 序号（0-based），标识该子任务属于哪个 chunk |
| Task | total_chunks | Integer, nullable | 该流水线的总 chunk 数 |

### 后端改动

| 文件 | 改动 |
|---|---|
| models.py | 新增 chunk_index + total_chunks 列 |
| cot_hcot_service.py | auto-run 改为 iterate over chunks；新增 chunk 解析函数；step 输入改为取单个 chunk 内容 |
| cot_hcot_pipeline.py | auto-run/auto-continue 接口不变，后端自动感知 chunk |
| migrate_chunk_pipeline.py | 迁移脚本 |

### 前端改动

| 文件 | 改动 |
|---|---|
| WorkflowDetail.vue | 步骤列表改为按 chunk 分组展示（chunk 1 的事实卡、chunk 2 的事实卡...）；总进度改为"已完成 X/Y chunk" |
| WorkflowList.vue | 无改动 |

### 关键设计细节

1. **chunk 读取**：通过 `file_id → Dataset.query.filter(file_id=source_file_id)` 获取所有 chunk
2. **每 chunk 一个子流水线**：auto-run 外层循环 chunk，内层循环步骤
3. **步骤命名**：sub-task 的 step_name 不变，通过 chunk_index 区分不同 chunk 的同一步骤
4. **输出文件**：每个 chunk 的每步输出为独立文件，最终 export 合并所有
5. **前端展示**：步骤列表从"扁平10步"变为"150×10 = 1500 子任务"，需按 chunk 分组折叠展示