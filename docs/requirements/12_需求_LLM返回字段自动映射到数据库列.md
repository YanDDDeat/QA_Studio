# 需求：LLM 返回字段自动映射到数据库列

## 背景

当前各 Pipeline 阶段从 LLM 返回的 JSON 中通过**硬编码白名单**（`_KNOWN_KEYS`）决定哪些字段存入数据库独立列，其余全部塞进 `extra_fields`（JSON 列）。这导致：

1. **数据错放**：数据库明明有 `difficulty` 列，但某些阶段的白名单没写，LLM 返回的 `difficulty` 被扔进 `extra_fields`
2. **扩展性差**：新增字段需要改白名单代码、重建容器，无法做到"加列即用"
3. **代码重复**：6 个管线阶段各自维护白名单，逻辑相同但散落各处

## 目标

实现**动态自动映射**：LLM 返回的字段，数据库有对应列就存入独立列，没有才进 `extra_fields`。新增字段只需 `ALTER TABLE` + 改 Prompt，代码无需改动。

---

## 输入输出定义

### 输入

- LLM 返回 JSON，包含任意字段（如 `{"domain": "混合炸药", "difficulty": "较难", "score": "0.85"}`）

### 输出

- 字段名在 `datasets` 表中有对应列 → 存入该列
- 字段名不在表中 → 存入 `extra_fields` JSON 列

---

## 详细规则

### 核心映射逻辑

1. **动态获取列名**：从 `Dataset.__table__.columns` 获取所有数据库列名
2. **过滤系统字段**：排除 `id`, `user_id`, `file_id`, `current_stage`, `created_at`, `updated_at`, `extra_fields`
3. **忽略大小写匹配**：LLM 返回 `"Relevance"` 也能匹配到数据库的 `"relevance"` 列
4. **统一序列化**：所有值转为字符串，列表转 JSON 字符串
5. **业务字段保护**：`category`, `source`, `source_id` 等由业务逻辑控制的字段不被 LLM 覆盖

### 字段处理流程

```
LLM 返回字段
    ↓
是否是业务保护字段？ → 是 → 跳过
    ↓ 否
数据库有对应列？
    ↓ 是                    ↓ 否
存入独立列              存入 extra_fields
```

### 涉及改造的管线阶段（6 个）

| # | 阶段 | 文件 | 改造内容 |
|---|------|------|---------|
| 1 | 问题生成 | `question_generate.py` | 替换 `_QG_KNOWN_KEYS` 白名单 |
| 2 | 知识生成 | `knowledge_generate.py` | 替换 `_KG_KNOWN_KEYS` 白名单 |
| 3 | 问题验证 | `question_validate.py` | 替换 `_QV_KNOWN_KEYS` 白名单 |
| 4 | 答案生成 | `answer_generate.py` | 替换 `_AG_KNOWN_KEYS` 白名单 |
| 5 | 答案验证 | `answer_validate.py` | 替换 `_AV_KNOWN_KEYS` 白名单 |
| 6 | 数据评估 | `data_evaluate.py` | 替换 `_DE_KNOWN_KEYS` 白名单 |

**无需改造的管线阶段（3 个）**：`cot_filter.py`、`dataset_assessment.py`、`dataset_split.py`（不调用 LLM）

---

## 数据库变更

无 Schema 变更。本需求是**写入逻辑**的改动，不新增/修改列。

---

## 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/field_mapper.py` | **新建** | 核心映射逻辑模块 |
| `backend/app/routers/question_generate.py` | **修改** | 替换白名单逻辑，删除 `_serialize_field` |
| `backend/app/routers/knowledge_generate.py` | **修改** | 替换白名单逻辑 |
| `backend/app/routers/question_validate.py` | **修改** | 替换白名单逻辑 |
| `backend/app/routers/answer_generate.py` | **修改** | 替换白名单逻辑 |
| `backend/app/routers/answer_validate.py` | **修改** | 替换白名单逻辑 |
| `backend/app/routers/data_evaluate.py` | **修改** | 替换白名单逻辑，简化现有复杂别名 |

---

## 核心模块设计

### `backend/app/services/field_mapper.py`

```python
"""LLM 返回字段到 Dataset 模型的自动映射器。"""

import json
from app.models.models import Dataset

# 不能从 LLM 结果自动赋值的字段
_SYSTEM_FIELDS = frozenset({
    "id", "user_id", "file_id", "current_stage",
    "created_at", "updated_at", "extra_fields",
})

# 动态获取所有可赋值的数据库列名
_DATASET_COLUMNS = frozenset(
    c.name for c in Dataset.__table__.columns
) - _SYSTEM_FIELDS


def _resolve_field_name(llm_key: str) -> str | None:
    """将 LLM 返回的字段名解析为数据库列名（支持忽略大小写）。"""
    # 1. 直接匹配
    if llm_key in _DATASET_COLUMNS:
        return llm_key
    
    # 2. 忽略大小写匹配
    llm_key_lower = llm_key.lower()
    for col in _DATASET_COLUMNS:
        if col.lower() == llm_key_lower:
            return col
    
    return None


def _serialize_value(value) -> str | None:
    """将值序列化为字符串（列表转 JSON）。"""
    if value is None:
        return None
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def apply_llm_fields_to_dataset(ds: Dataset, llm_result: dict) -> dict:
    """将 LLM 返回的字段自动映射到 Dataset 记录。
    
    Returns:
        dict: 无法映射到数据库列的字段（作为 extra_fields 存储）
    """
    extra = {}
    
    for key, value in llm_result.items():
        # 跳过业务保护字段
        if key in {"category", "source", "source_id", "source_type",
                   "corpus_cate", "originContent", "passed", "Assessment"}:
            continue
        
        # 解析字段名（支持忽略大小写）
        db_column = _resolve_field_name(key)
        
        if db_column is not None:
            setattr(ds, db_column, _serialize_value(value))
        else:
            extra[key] = value
    
    return extra
```

### 各阶段改造示例（以 `knowledge_generate.py` 为例）

**改造前：**
```python
_KG_KNOWN_KEYS = {"knowledge", "domain", "step_count"}
cloned_ds.step_count = str(llm_result.get("step_count", "")) if llm_result.get("step_count") else None
extra = {k: v for k, v in llm_result.items() if k not in _KG_KNOWN_KEYS}
cloned_ds.extra_fields = extra if extra else None
```

**改造后：**
```python
from app.services.field_mapper import apply_llm_fields_to_dataset

extra = apply_llm_fields_to_dataset(cloned_ds, llm_result)
cloned_ds.extra_fields = extra if extra else None
```

---

## 向后兼容

- **已有数据**：不受影响，历史 `extra_fields` 数据保持不变
- **新增字段**：只需 `ALTER TABLE` 加列 + Prompt 中要求返回，代码自动生效
- **列表类型**：`_serialize_value` 自动将 `list` 转 JSON 字符串，兼容之前的 `domain` 修复

---

## Prompt 要求

由于不再支持中英文别名映射，**Prompt 中应明确要求 LLM 返回与数据库列名一致的字段名**：

```markdown
请返回以下字段（字段名必须与之一致）：
- relevance: 相关性评分 (1-5)
- clarity: 清晰度评分 (1-5)  
- score: 综合评分 (0-1)
```

---

## 验证步骤

1. **单元测试**：测试 `_resolve_field_name`（精确匹配、忽略大小写、未匹配）
2. **集成测试**：LLM 返回 `{"Relevance": "5", "SCORE": "0.85"}` 验证是否映射到 `relevance` 和 `score`
3. **回归测试**：6 个管线阶段全流程正常运行
