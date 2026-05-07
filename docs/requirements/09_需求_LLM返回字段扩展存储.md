# 需求：LLM返回字段扩展存储

## 背景
当前各 Pipeline 阶段从 LLM 返回的 JSON 中只取预定义字段存入 Dataset 表，LLM 返回的其他字段全部丢弃。需要：
1. 新增 `step_count` 字段记录 cot 推理步骤数（CHAR 类型，由 LLM 返回）
2. 新增 `extra_fields` JSON 列兜底存储所有非预定义字段，前端查看时拆开成独立行显示

## 输入输出定义

### 输入
- LLM 返回 JSON，可能包含 `step_count`、`confidence`、`suggestions` 等非预定义字段

### 输出
- Dataset 表新增 `step_count` (String) 和 `extra_fields` (JSON) 两列
- 各阶段 LLM 处理逻辑：取完预定义字段后，剩余字段整体存入 `extra_fields`
- 前端记录详情：`extra_fields` 中的每个 key-value 拆成单独一行显示（与 input/cot 同级）

## 详细规则

### step_count
- 类型：String（CHAR），存 LLM 返回的原始值
- 各阶段处理：如果 LLM 返回中包含 `step_count` 字段，取值存入 Dataset.step_count
- 空值：LLM 未返回时为 None，前端显示 `-`

### extra_fields
- 类型：JSON，存 dict
- 各阶段处理：LLM 返回的所有字段中，不属于该阶段预定义字段的，全部存入 extra_fields
- 预定义字段清单（各阶段不同）：
  - 问题生成：input, output, cot, task_type, domain, difficulty, step_count
  - 知识体系生成：knowledge, domain, step_count
  - 答案生成：output, cot, step_count
  - 问题校验：validation_result, reason, step_count
  - 答案校验：validation_result, reason, step_count
  - 数据评估：relevance, clarity, reasoning, terminology, score, step_count
- 空 LLM 返回无额外字段时 extra_fields 为 None，前端不显示

### 前端显示
- `categorizeFields` 函数需处理 extra_fields：
  - 如果 extra_fields 是 dict 且非空，将其每个 key-value 展开为独立的字段
  - 展开的字段归入 longText 或 meta（按已有阈值逻辑）
  - 展开时 key 直接用原始字段名，不做中文映射
- step_count 归入 meta（短文本描述项）

## 数据库变更
- 新增列：`step_count VARCHAR(32)`、`extra_fields JSON`
- 需迁移脚本

## 涉及文件
- `backend/app/models/models.py` — Dataset 模型加两列
- `backend/app/services/file_service.py` — serialize_dataset_to_dict 输出 extra_fields
- `backend/app/routers/question_generate.py` — 取 step_count + extra_fields
- `backend/app/routers/knowledge_generate.py` — 取 step_count + extra_fields
- `backend/app/routers/answer_generate.py` — 取 step_count + extra_fields
- `backend/app/routers/question_validate.py` — 取 step_count + extra_fields（FAIL 记录）
- `backend/app/routers/answer_validate.py` — 取 step_count + extra_fields（FAIL 记录）
- `backend/app/routers/data_evaluate.py` — 取 step_count + extra_fields
- `frontend/src/utils/fieldLabels.js` — categorizeFields 展开 extra_fields
- `scripts/migrate_step_count_extra_fields.py` — 迁移脚本