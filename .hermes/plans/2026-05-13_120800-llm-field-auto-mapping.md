# LLM 返回字段自动映射方案

## 1. 背景

### 当前问题

在 `knowledge_generate`、`answer_generate`、`question_generate` 等管线阶段中，LLM 返回的 JSON 字段通过**硬编码的白名单**（`_KNOWN_KEYS`）决定哪些字段存入数据库的独立列，其余全部塞进 `extra_fields`（JSON 列）。

**具体表现：**

- `knowledge_generate.py` 中写死了 `_KG_KNOWN_KEYS = {"knowledge", "domain", "step_count"}`
- `answer_generate.py` 中写死了 `_AG_KNOWN_KEYS = {"output", "answer", "cot", "reasoning", "step_count"}`
- `question_generate.py` 中写死了 `_QG_KNOWN_KEYS`，里面列了十几个字段名

这导致：

1. **数据错放**：数据库明明有 `difficulty` 列，但 `answer_generate` 没在白名单里写，LLM 返回的 `difficulty` 就被扔进 `extra_fields`，数据库的 `difficulty` 列永远是 NULL。
2. **扩展性差**：如果想在 Prompt 里让 LLM 返回一个新字段，必须先去白名单加字段名、改代码、重建容器。完全没法做到"加列即用"。
3. **代码重复**：5-6 个管线阶段文件各自维护自己的白名单集合，逻辑相同但散落各处。

### 期望行为

**LLM 返回什么字段，系统自动判断：**
- 字段名在 `datasets` 表里已有 → 直接存入对应列
- 字段名不在表里 → 存入 `extra_fields` JSON 列

这样只需在数据库加一列 + 在 Prompt 里提一句，就能让 LLM 返回并存储新字段，代码无需改动。

---

## 2. 当前 Dataset 模型字段清单

当前 `datasets` 表有以下列（来自 `models.py`）：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | Integer (PK) | 主键 |
| `user_id` | Integer | 用户ID |
| `domain` | Text | 领域（支持JSON数组） |
| `category` | String(32) | 类别 |
| `task_type` | String(64) | 任务类型 |
| `input` | Text | 输入（问题） |
| `output` | Text | 输出（答案） |
| `cot` | Text | 推理链 |
| `corpus_cate` | Integer | 语料分类 |
| `scene` | Text | 场景 |
| `Assessment` | String(256) | 评估 |
| `source` | String(128) | 来源 |
| `source_id` | String(128) | 来源ID |
| `source_type` | String(32) | 来源类型 |
| `originContent` | Text | 原始内容 |
| `knowledge` | Text | 知识体系 |
| `step_count` | String(32) | 步骤数 |
| `extra_fields` | JSON | 额外字段（兜底） |
| `difficulty` | String(32) | 难度 |
| `relevance` | Integer | 相关性评分 |
| `clarity` | Integer | 清晰度评分 |
| `reasoning` | Integer | 推理评分 |
| `terminology` | Integer | 术语评分 |
| `score` | Float | 总分 |
| `passed` | String(16) | 是否通过 |
| `file_id` | Integer | 文件ID |
| `current_stage` | Enum | 当前阶段 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

**需要过滤的字段**（不能从 LLM 结果自动赋值）：

| 字段名 | 原因 |
|--------|------|
| `id` | 主键，自动分配 |
| `user_id` | 由业务逻辑设置 |
| `file_id` | 由克隆逻辑设置 |
| `current_stage` | 由 clone_single_dataset 设置 |
| `created_at` | 自动时间戳 |
| `updated_at` | 自动时间戳 |
| `extra_fields` | 这是兜底列本身，不从 LLM 结果赋值 |

---

## 3. 方案设计

### 3.1 核心思路

1. **新增共享模块** `backend/app/services/field_mapper.py`
2. 从 `Dataset.__table__.columns` 动态获取所有可用列名
3. 过滤掉不可自动赋值的字段（主键、外键、时间戳等）
4. 遍历 LLM 返回的 dict：
   - key 在可用列中 → `setattr(ds, key, serialized_value)`
   - key 不在 → 放入 `extra` 字典，最后写进 `ds.extra_fields`

### 3.2 新增模块：`backend/app/services/field_mapper.py`

```python
"""LLM 返回字段到 Dataset 模型的自动映射器。

核心逻辑：根据 Dataset 表的列定义，动态决定 LLM 返回的 JSON 字段
该写入哪一列。在表列中的写独立列，不在的写入 extra_fields。
"""

import json

from app.models.models import Dataset

# 不能从 LLM 结果自动赋值的字段
# 这些由业务逻辑（clone_single_dataset、用户输入等）控制
_SYSTEM_FIELDS = frozenset({
    "id",           # 主键
    "user_id",      # 用户ID
    "file_id",      # 文件ID
    "current_stage",# 当前阶段
    "created_at",   # 自动时间戳
    "updated_at",   # 自动时间戳
    "extra_fields", # 兜底列本身
})

# 从 SQLAlchemy 模型动态获取所有可赋值的列名
_DATASET_COLUMNS = frozenset(
    c.name for c in Dataset.__table__.columns
) - _SYSTEM_FIELDS


def _resolve_field_name(llm_key: str) -> str | None:
    """将 LLM 返回的字段名解析为数据库列名（支持忽略大小写）。
    
    优先级：
    1. 直接匹配（大小写敏感）
    2. 忽略大小写匹配
    3. 返回 None 表示无法识别
    
    Args:
        llm_key: LLM 返回的字段名
        
    Returns:
        数据库列名，或 None
    """
    # 1. 直接匹配
    if llm_key in _DATASET_COLUMNS:
        return llm_key
    
    # 2. 忽略大小写匹配
    llm_key_lower = llm_key.lower()
    for col in _DATASET_COLUMNS:
        if col.lower() == llm_key_lower:
            return col
    
    # 3. 无法识别
    return None


def _serialize_value(value) -> str | None:
    """将值序列化为字符串。
    
    - 列表 → JSON 字符串（如 ["A", "B"] → '["A", "B"]'）
    - 其他 → 直接转为字符串
    - None → None
    """
    if value is None:
        return None
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def apply_llm_fields_to_dataset(ds: Dataset, llm_result: dict) -> dict:
    """将 LLM 返回的字段自动映射到 Dataset 记录。
    
    Args:
        ds: 已创建的 Dataset 实例（克隆后或新建的）
        llm_result: LLM 返回的 JSON 字典
        
    Returns:
        dict: 无法映射到数据库列的字段（将作为 extra_fields 存储）
        
    副作用:
        直接修改 ds 的对应列属性
        
    示例:
        >>> ds = clone_single_dataset(...)
        >>> extra = apply_llm_fields_to_dataset(ds, llm_result)
        >>> ds.extra_fields = extra if extra else None
        >>> db.commit()
        
    忽略大小写示例:
        LLM 返回 {"Relevance": "5", "SCORE": "0.85"}
        自动映射为 ds.relevance = "5", ds.score = "0.85"
    """
    extra = {}
    
    for key, value in llm_result.items():
        # 跳过已知的非 LLM 业务字段（如前端传的分类等）
        if key in {"category", "source", "source_id", "source_type",
                   "corpus_cate", "originContent", "passed", "Assessment"}:
            continue
        
        # 解析字段名（支持忽略大小写）
        db_column = _resolve_field_name(key)
        
        if db_column is not None:
            # 字段可以映射到数据库列
            setattr(ds, db_column, _serialize_value(value))
        else:
            # 无法识别 → 兜底存入 extra
            extra[key] = value
    
    return extra
```

### 3.3 各管线阶段改造点

#### `knowledge_generate.py`（约第 187-205 行）

**改造前：**
```python
cloned_ds = clone_single_dataset(db, dataset, output_file.id, StageEnum.KNOWLEDGE_GENERATE)
# 处理 domain
domain_value = llm_result.get("domain", "")
if isinstance(domain_value, list):
    domain_value = json.dumps(domain_value, ensure_ascii=False)
cloned_ds.domain = domain_value
# 处理 knowledge/scene
if isinstance(knowledge_value, list):
    knowledge_value = json.dumps(knowledge_value, ensure_ascii=False)
cloned_ds.scene = knowledge_value
cloned_ds.knowledge = knowledge_value
# 白名单提取
_KG_KNOWN_KEYS = {"knowledge", "domain", "step_count"}
cloned_ds.step_count = str(llm_result.get("step_count", "")) if llm_result.get("step_count") else None
extra = {k: v for k, v in llm_result.items() if k not in _KG_KNOWN_KEYS}
cloned_ds.extra_fields = extra if extra else None
```

**改造后：**
```python
from app.services.field_mapper import apply_llm_fields_to_dataset

cloned_ds = clone_single_dataset(db, dataset, output_file.id, StageEnum.KNOWLEDGE_GENERATE)
extra = apply_llm_fields_to_dataset(cloned_ds, llm_result)
cloned_ds.extra_fields = extra if extra else None
```

#### `answer_generate.py`（约第 190-201 行）

**改造前：**
```python
cloned_ds = clone_single_dataset(db, dataset, output_file.id, StageEnum.ANSWER_GENERATE)
cloned_ds.output = output_text
cloned_ds.cot = cot_text
_AG_KNOWN_KEYS = {"output", "answer", "cot", "reasoning", "step_count"}
cloned_ds.step_count = str(llm_result.get("step_count", "")) if llm_result.get("step_count") else None
extra = {k: v for k, v in llm_result.items() if k not in _AG_KNOWN_KEYS}
cloned_ds.extra_fields = extra if extra else None
```

**改造后：**
```python
from app.services.field_mapper import apply_llm_fields_to_dataset

cloned_ds = clone_single_dataset(db, dataset, output_file.id, StageEnum.ANSWER_GENERATE)
extra = apply_llm_fields_to_dataset(cloned_ds, llm_result)
cloned_ds.extra_fields = extra if extra else None
```

#### `question_generate.py`（约第 280-312 行）

这个阶段比较特殊——它是**新建 Dataset** 而非克隆，且需要从 LLM 返回中提取 `input`/`output`/`cot` 等基础字段。

**改造思路：** 仍然使用 `apply_llm_fields_to_dataset`，但需要先在构造函数中填入必要的基础字段（`user_id`, `category`, `source` 等），然后将 LLM 结果中的字段自动映射。

**改造后：**
```python
from app.services.field_mapper import apply_llm_fields_to_dataset

dataset = Dataset(
    user_id=user_id,
    category=category,
    corpus_cate=1,
    source=effective_source,
    source_id=effective_source_id,
    source_type=source_type,
    originContent=text_content,
    file_id=output_file.id,
    Assessment="",
    current_stage=StageEnum.QUESTION_GENERATE,
)
extra = apply_llm_fields_to_dataset(dataset, q)
dataset.extra_fields = extra if extra else None
db.add(dataset)
```

这样 `input`、`output`、`cot`、`domain`、`difficulty` 等字段只要 LLM 返回了，且数据库有对应列，就会自动映射。

#### 其他管线阶段

同样模式应用到：
- `question_validate.py`（如有 LLM 字段处理）
- `answer_validate.py`
- `data_evaluate.py`
- `cot_filter.py`

---

## 4. 向后兼容

### 已有数据不受影响

- 这是一个**写入逻辑**的改动，不修改数据库 Schema
- 现有 `extra_fields` 中的历史数据保持不变
- 新数据按自动映射逻辑写入

### 字段语义一致性

- `apply_llm_fields_to_dataset` 内部会跳过 `category`、`source` 等业务字段，避免覆盖
- `clone_single_dataset` 已经正确复制了源记录的这些字段，不需要 LLM 重新赋值

### 列表类型序列化

- `_serialize_value` 自动将 `list` 转为 JSON 字符串，兼容之前修复的 `domain` 列表问题
- 旧代码中的 `_serialize_field` 函数可以删除（`question_generate.py`）

### 数值型字段类型转换

- `_serialize_value` 自动将 `list` 转为 JSON 字符串，兼容之前修复的 `domain` 列表问题
- 旧代码中的 `_serialize_field` 函数可以删除（`question_generate.py`）

### data_evaluate.py 特殊处理

原 `data_evaluate.py` 的白名单支持中文/英文/简写等多种别名：

```python
_DE_KNOWN_KEYS = {
    "relevance", "relevant", "相关性", "Relevance",
    "clarity", "clear", "清晰度", "Clarity",
    ...
}
```

使用新的 `field_mapper.py` 后，这些复杂的别名逻辑被**自动处理**，代码从 15 行简化到 1 行。

**注意：** 本方案只支持忽略大小写的字段名映射（如 `Relevance` → `relevance`），不支持中英文别名。Prompt 中应明确要求 LLM 返回与数据库列名一致的字段名。

---

## 5. 涉及文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/field_mapper.py` | **新建** | 核心映射逻辑（含别名映射） |
| `backend/app/routers/question_generate.py` | **修改** | 替换白名单逻辑为自动映射，删除 `_serialize_field` |
| `backend/app/routers/knowledge_generate.py` | **修改** | 替换白名单逻辑为自动映射 |
| `backend/app/routers/question_validate.py` | **修改** | 替换白名单逻辑为自动映射 |
| `backend/app/routers/answer_generate.py` | **修改** | 替换白名单逻辑为自动映射 |
| `backend/app/routers/answer_validate.py` | **修改** | 替换白名单逻辑为自动映射 |
| `backend/app/routers/data_evaluate.py` | **修改** | 替换白名单逻辑为自动映射（含别名逻辑，简化现有代码） |
| `.hermes/skills/qa-studio-dev/SKILL.md` | **修改** | 更新开发模式文档 |

**无需改造的文件（不调用 LLM）：**
- `cot_filter.py` - 纯规则过滤
- `dataset_assessment.py` - 静态报告生成
- `dataset_split.py` - 数据切分

---

## 6. 验证步骤

1. **单元测试**：为 `field_mapper.py` 编写测试
   - 普通字符串字段映射
   - 列表类型字段映射（转 JSON）
   - 未知字段兜底到 `extra_fields`
   - 系统字段过滤（不会被覆盖）

2. **集成测试**：
   - 创建一个包含 `difficulty`、`score` 等字段的 Prompt
   - 让 LLM 返回这些字段
   - 验证数据库 `difficulty`、`score` 列有值，而不是在 `extra_fields` 中

3. **回归测试**：
   - 现有管线（question_generate → knowledge_generate → answer_generate）正常运行
   - 已有数据查询正常

4. **Docker 重建**：
   ```bash
   cd /home/yandddeat/qa_gen/dev-ops
   docker compose up -d --build backend
   ```

---

## 7. 风险与注意事项

| 风险 | 应对 |
|------|------|
| LLM 返回的字段名与数据库列名不匹配（如 `input_text` vs `input`） | Prompt 中明确指定返回字段名与数据库列名一致 |
| LLM 返回类型与列类型不兼容（如返回字符串给 Integer 列） | `_serialize_value` 统一转字符串，SQLAlchemy/MySQL 会尝试隐式转换；极端情况可在映射器中加类型检查 |
| 新增列后忘记更新 Prompt | 这不是代码问题，是 Prompt 设计问题。但映射器本身会自动发现新列，只需在 Prompt 中加上即可 |

---

## 8. 收益

1. **零代码扩展**：加新字段只需 `ALTER TABLE` + 改 Prompt，不用改 Python 代码
2. **代码精简**：删除 4-5 处白名单集合（每处 5-15 行）+ 重复的序列化逻辑
3. **数据准确性**：不会再出现"数据库有列但永远是 NULL"的情况
4. **统一机制**：所有管线阶段共享同一套映射逻辑，维护成本大幅降低
