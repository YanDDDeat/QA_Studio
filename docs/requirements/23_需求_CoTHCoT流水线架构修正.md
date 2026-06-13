# 23_需求_CoTHCoT流水线架构修正：从per-chunk全流程改为document级聚合

## 背景

当前 CoT/H-CoT 流水线的自动执行逻辑是"每个 chunk 独立跑完整流水线"，导致每个 chunk 各自生成一棵独立的 L0→L1→L2→CoT 推理树。这是错误的。

**正确流程**应该是：
1. 每个 chunk → 生成事实卡 → **收集所有 chunk 的事实卡**
2. 对**所有事实卡合在一起**做数值抽象（document-level）
3. 从**所有事实卡**生成 L0 总问题数组（可能不止一个总问题）（document-level）
4. 每个 L0 总问题 → L1 → L2 → CoT（per-L0-question）

核心洞察：
- 事实卡是 per-chunk 的（论文太长，分段提取）
- 数值抽象、L0 总问题生成是 **document-level** 的（需要全文视角）
- L1→L2→CoT 是 **per-L0-question** 的（一个论文可能产生多个核心机制总问题）
- 一个论文最终可能产出**多棵** H-CoT 推理树

## 输入输出定义

### 输入
- 源论文文件（可能被切分为多个 chunk）
- 流水线模式（hcot / cot）
- LLM 配置

### 输出
- H-CoT 模式：一棵或多棵 H-CoT 推理树（每棵对应一个 L0 总问题）
- CoT 模式：一组独立的问题-CoT 对（逻辑不变，但事实卡聚合方式同上修正）

## 详细规则

### 流水线阶段划分

**H-CoT 模式（修正后）**：

| 阶段 | 粒度 | 步骤 | 说明 |
|------|------|------|------|
| 1 | per-chunk | fact_card_gen | 每个 chunk 独立调用 LLM 生成事实卡 |
| 2 | document | merge_fact_cards | 合并所有 chunk 的事实卡为一份完整事实卡 |
| 3 | document | sanitize | 对合并后的完整事实卡做数值抽象 |
| 4 | document | l0_gen | 从完整事实卡生成 L0 总问题数组（可能多个） |
| 5 | per-L0 | l1_decompose | 每个总问题拆解为 L1 子问题 |
| 6 | per-L0 | l2_decompose | 每个 L1 拆解为 L2 细粒度问题 |
| 7 | per-L0 | l2_cot | 每个 L2 生成 CoT |
| 8 | per-L0 | l1_cot | 每个 L1 综合 L2 CoT 生成 L1 CoT |
| 9 | per-L0 | l0_cot | 每个总问题综合 L1 CoT 生成 L0 CoT |
| 10 | document | quality_check | 质检所有 CoT |
| 11 | document | export_jsonl | 导出训练数据 |

**CoT 模式（修正后）**：

| 阶段 | 粒度 | 步骤 | 说明 |
|------|------|------|------|
| 1 | per-chunk | fact_card_gen | 每个 chunk 独立生成事实卡 |
| 2 | document | merge_fact_cards | 合并所有 chunk 的事实卡 |
| 3 | document | sanitize | 数值抽象 |
| 4 | document | question_gen | 独立问题生成 |
| 5 | document | cot_gen | 独立 CoT 生成 |
| 6 | document | quality_check | 质检 |
| 7 | document | export_jsonl | 导出 |

### 子任务索引字段

当前 Task 模型用 `chunk_index` 标识子任务所属 chunk。修正后需要区分：
- per-chunk 步骤：子任务用 `chunk_index` 标识
- document-level 步骤：子任务 `chunk_index = None`（不区分 chunk）
- per-L0 步骤：子任务用 `l0_question_index` 标识（新增字段）

### merge_fact_cards 步骤

这是一个纯数据合成步骤（不调 LLM），将所有 chunk 的 fact_card_gen 输出合并为一份完整的 JSON：
- 如果各 chunk 输出是 dict，合并所有 key-value
- 如果各 chunk 输出是 list，concatenate 所有 list
- 输出一份完整的事实卡 JSON 文件

### L0 总问题数组

l0_gen 的输出不再是单个总问题，而是**一个数组**（如 `l0_candidates: [...]`）。
LLM 可以根据论文的多个核心机制产出多个总问题。后续 L1/L2/CoT 步骤对每个总问题分别执行。

### 一键执行流程修正

`run_pipeline_auto_bg` 的执行逻辑从：

```
for each chunk:
    for each step:
        run(step, chunk_idx)
```

改为：

```
# 阶段1: per-chunk 事实卡（可并行）
for each chunk:
    run(fact_card_gen, chunk_idx)

# 阶段2: 文档级聚合 + 数值抽象 + L0 生成
run(merge_fact_cards)          # 合并所有事实卡
run(sanitize)                  # 数值抽象
run(l0_gen)                    # → 产出 L0 总问题数组

# 阶段3: per-L0 推理树
l0_questions = parse(l0_gen output)
for each l0_question in l0_questions:
    run(l1_decompose, l0_idx)
    run(l2_decompose, l0_idx)
    run(l2_cot, l0_idx)
    run(l1_cot, l0_idx)
    run(l0_cot, l0_idx)

# 阶段4: 质检 + 导出
run(quality_check)
run(export_jsonl)
```

### 手动单步执行

用户仍可手动触发单个步骤，但前端需要根据步骤粒度展示：
- per-chunk 步骤：展示"为 chunk X 运行"
- document 步骤：展示"运行（文档级）"
- per-L0 步骤：展示"为总问题 Y 运行"

### 导出修正

export_jsonl 需要产出多棵 H-CoT 树：
```json
{
  "hcot_trees": [
    { "l0_question_1": {..., "l1_children": [...], ... },
    { "l0_question_2": {..., "l1_children": [...], ... }
  ],
  "training_samples": [...],
  "total_samples": N
}
```

## 数据库变更

- **新增字段**：Task 表添加 `l0_question_index` (Integer, nullable)，用于标识 per-L0 步骤属于哪个总问题
- **新增步骤**：`PIPELINE_STEPS` 中添加 `merge_fact_cards`（display_name="合并事实卡", 无 LLM prompt, 纯数据合成）
- **步骤顺序更新**：HCOT_STEP_ORDER 和 COT_STEP_ORDER 需插入 `merge_fact_cards`

## 前端变更

- WorkflowDetail.vue：步骤卡片需区分粒度（per-chunk / document / per-L0），展示对应的分组标签
- 步骤列表 API：返回每个步骤的 `granularity` 字段（"per_chunk" / "document" / "per_l0"）

## 接口变更

- `POST /cothcot/run-step`：需要支持传入 `l0_question_index` 参数（用于 per-L0 步骤）
- `GET /cothcot/workflow/{task_id}`：返回结构中需包含 L0 总问题列表及对应的推理树状态

## 不涉及的范围

- Prompt 内容不变（各步骤的 Prompt 模板不变，只是输入数据的组装方式变了）
- 质检和导出的 Prompt/逻辑基本不变（只是输入来源从 per-chunk 变为 per-L0）
- CoT 模式的 question_gen 和 cot_gen 仍然是 document-level，改动较小