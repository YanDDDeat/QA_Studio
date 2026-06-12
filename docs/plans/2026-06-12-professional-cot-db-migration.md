# 专业 CoT 管线：文件存储 → 数据库存储 迁移方案

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 将专业 CoT 管线的提示词模板、任务追踪、产出数据从纯文件存储迁移到 MySQL 数据库。

**Architecture:** 
- 复用 `tasks` 表追踪 run 生命周期（替代 `manifest.json`）
- 复用 `prompts` 表存储提示词模板（替代文件目录）
- 新建 `cot_samples` 表存储产出数据（替代 per-document JSON）
- 新建 `cot_step_logs` 表存储步骤日志（替代 manifest 内嵌 steps）
- **保留 `final_samples.json` 文件输出**（用于下载导出，不破坏现有导出流程）
- 前端 API 响应格式保持不变，只改后端数据源

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy ORM, MySQL 8.0

---

## 数据库变更总览

### StageEnum 新增

```python
PROFESSIONAL_COT = "professional_cot"  # 专业 CoT 管线
```

### prompts 表新增列

```sql
ALTER TABLE prompts ADD COLUMN template_id VARCHAR(128) NULL;
ALTER TABLE prompts ADD COLUMN prompt_key VARCHAR(128) NULL;
ALTER TABLE prompts ADD INDEX idx_template_prompt (template_id, prompt_key);
```

### tasks 表新增列

```sql
ALTER TABLE tasks ADD COLUMN input_count INT DEFAULT 1;
ALTER TABLE tasks ADD COLUMN success_count INT DEFAULT 0;
ALTER TABLE tasks ADD COLUMN failed_count INT DEFAULT 0;
ALTER TABLE tasks ADD COLUMN sample_count INT DEFAULT 0;
ALTER TABLE tasks ADD COLUMN run_extra JSON NULL COMMENT 'run 元数据：source_input, recommended_cot_type, final_outputs 等';
```

### 新建 cot_samples 表

```sql
CREATE TABLE cot_samples (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    user_id INT NOT NULL,
    source_index INT DEFAULT 0,
    source VARCHAR(512) NULL,
    source_type VARCHAR(32) DEFAULT 'unknown',
    cot_type VARCHAR(128) NULL,
    cot_type_key VARCHAR(64) NULL,
    input TEXT NULL,
    chainofThought TEXT NULL,
    output TEXT NULL,
    evidence_trace TEXT NULL,
    step_results JSON NULL COMMENT '各步骤 LLM 原始返回',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_cot_task (task_id),
    INDEX idx_cot_type (cot_type_key),
    INDEX idx_cot_user (user_id)
);
```

### 新建 cot_step_logs 表

```sql
CREATE TABLE cot_step_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    source_index INT DEFAULT 0 COMMENT '所属文献序号，-1表示run级别',
    step_key VARCHAR(64) NOT NULL COMMENT 'step1_3_integrated / step4_input / step5_chain / step6_output',
    status VARCHAR(16) DEFAULT 'pending' COMMENT 'pending / running / completed / failed / skipped',
    progress_current INT DEFAULT 0,
    progress_label VARCHAR(256) NULL,
    cot_type VARCHAR(128) NULL,
    cot_type_key VARCHAR(64) NULL,
    artifact_path VARCHAR(512) NULL,
    error_message TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    INDEX idx_step_task (task_id, source_index, step_key)
);
```

---

## 改造任务列表

### Phase 1: 基础设施（无业务影响）

---

### Task 1: 新增 StageEnum 值

**Objective:** 在 `StageEnum` 中添加 `PROFESSIONAL_COT`

**Files:**
- Modify: `backend/app/models/models.py`

**Step 1: 添加枚举值**

在 `StageEnum` 类中添加：

```python
PROFESSIONAL_COT = "professional_cot"  # 专业 CoT 管线（标注流水线2）
```

位置：紧跟 `COT_HCOT_PIPELINE` 之后。

**Step 2: 验证**

```bash
cd ~/qa_gen/backend
python3 -c "from app.models.models import StageEnum; print(StageEnum.PROFESSIONAL_COT.value)"
# 预期输出: professional_cot
```

---

### Task 2: 修改 prompts 表模型

**Objective:** 添加 `template_id` 和 `prompt_key` 字段

**Files:**
- Modify: `backend/app/models/models.py`

**Step 1: 修改 Prompt 模型**

在 `Prompt` 类中添加两个新列：

```python
template_id = Column(String(128), nullable=True)  # 提示词模板包 ID
prompt_key = Column(String(128), nullable=True)    # 模板内 prompt 标识，如 "performance_improvement.step4"
```

放在 `reference_fields` 字段之后。

**Step 2: 验证**

```bash
cd ~/qa_gen/backend
python3 -c "
from app.models.models import Prompt
print('template_id' in Prompt.__table__.columns)
print('prompt_key' in Prompt.__table__.columns)
"
# 预期: True / True
```

---

### Task 3: 修改 tasks 表模型

**Objective:** 添加 run 级别计数字段和扩展 JSON

**Files:**
- Modify: `backend/app/models/models.py`

**Step 1: 在 Task 模型末尾添加字段**

在 `prompt_template_id` 之后添加：

```python
input_count = Column(Integer, default=1)
success_count = Column(Integer, default=0)
failed_count = Column(Integer, default=0)
sample_count = Column(Integer, default=0)
run_extra = Column(JSON, nullable=True)  # 存储 source_input, recommended_cot_type, final_outputs 等
```

---

### Task 4: 新建 CotSample 和 CotStepLog 模型

**Objective:** 创建产出数据和步骤日志的 ORM 模型

**Files:**
- Modify: `backend/app/models/models.py`

**Step 1: 添加 CotSample 模型**

在 `ProfessionalCotTypeStat` 之后添加：

```python
class CotSample(Base):
    """专业 CoT 管线产出的单条训练样本"""
    __tablename__ = "cot_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source_index = Column(Integer, default=0)
    source = Column(String(512), nullable=True)
    source_type = Column(String(32), default="unknown")
    cot_type = Column(String(128), nullable=True)
    cot_type_key = Column(String(64), nullable=True, index=True)
    input = Column(Text, nullable=True)
    chainofThought = Column(Text, nullable=True)
    output = Column(Text, nullable=True)
    evidence_trace = Column(Text, nullable=True)
    step_results = Column(JSON, nullable=True)  # 各步骤 LLM 原始返回
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Step 2: 添加 CotStepLog 模型**

```python
class CotStepLog(Base):
    """专业 CoT 管线每篇文献每步骤的执行日志"""
    __tablename__ = "cot_step_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    source_index = Column(Integer, default=0, comment="文献序号，-1 表示 task 级别")
    step_key = Column(String(64), nullable=False, comment="step1_3_integrated/step4_input/step5_chain/step6_output")
    status = Column(String(16), default="pending")
    progress_current = Column(Integer, default=0)
    progress_label = Column(String(256), nullable=True)
    cot_type = Column(String(128), nullable=True)
    cot_type_key = Column(String(64), nullable=True)
    artifact_path = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

### Task 5: 写 DDL 迁移脚本 + 更新初始化 SQL

**Objective:** 创建数据库迁移脚本并更新初始化 SQL

**Files:**
- Create: `backend/scripts/migrate_professional_cot_to_db.py`
- Modify: `dev-ops/init-db/create_tables.sql`

**Step 1: 创建迁移脚本**

```python
#!/usr/bin/env python3
"""迁移脚本：为 professional_cot 管线创建新表、添加新列。

用法:
  cd backend
  python3 scripts/migrate_professional_cot_to_db.py
"""

import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from sqlalchemy import text

MIGRATIONS = [
    # prompts 表新列
    "ALTER TABLE prompts ADD COLUMN template_id VARCHAR(128) NULL",
    "ALTER TABLE prompts ADD COLUMN prompt_key VARCHAR(128) NULL",
    "CREATE INDEX idx_template_prompt ON prompts (template_id, prompt_key)",

    # tasks 表新列
    "ALTER TABLE tasks ADD COLUMN input_count INT DEFAULT 1",
    "ALTER TABLE tasks ADD COLUMN success_count INT DEFAULT 0",
    "ALTER TABLE tasks ADD COLUMN failed_count INT DEFAULT 0",
    "ALTER TABLE tasks ADD COLUMN sample_count INT DEFAULT 0",
    "ALTER TABLE tasks ADD COLUMN run_extra JSON NULL COMMENT 'run 元数据'",

    # cot_samples 表
    """CREATE TABLE IF NOT EXISTS cot_samples (
        id INT AUTO_INCREMENT PRIMARY KEY,
        task_id INT NOT NULL,
        user_id INT NOT NULL,
        source_index INT DEFAULT 0,
        source VARCHAR(512) NULL,
        source_type VARCHAR(32) DEFAULT 'unknown',
        cot_type VARCHAR(128) NULL,
        cot_type_key VARCHAR(64) NULL,
        input TEXT NULL,
        chainofThought TEXT NULL,
        output TEXT NULL,
        evidence_trace TEXT NULL,
        step_results JSON NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES tasks(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        INDEX idx_cot_task (task_id),
        INDEX idx_cot_type (cot_type_key),
        INDEX idx_cot_user (user_id)
    )""",

    # cot_step_logs 表
    """CREATE TABLE IF NOT EXISTS cot_step_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        task_id INT NOT NULL,
        source_index INT DEFAULT 0,
        step_key VARCHAR(64) NOT NULL,
        status VARCHAR(16) DEFAULT 'pending',
        progress_current INT DEFAULT 0,
        progress_label VARCHAR(256) NULL,
        cot_type VARCHAR(128) NULL,
        cot_type_key VARCHAR(64) NULL,
        artifact_path VARCHAR(512) NULL,
        error_message TEXT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES tasks(id),
        INDEX idx_step_task (task_id, source_index, step_key)
    )""",
]

def main():
    db = SessionLocal()
    try:
        for sql in MIGRATIONS:
            try:
                db.execute(text(sql))
                print(f"✓ {sql[:60]}...")
            except Exception as e:
                if "Duplicate column" in str(e) or "Duplicate key" in str(e) or "already exists" in str(e):
                    print(f"→ 已存在，跳过: {sql[:60]}...")
                else:
                    print(f"✗ 失败: {sql[:60]}... → {e}")
        db.commit()
        print("\n迁移完成！")
    finally:
        db.close()

if __name__ == "__main__":
    main()
```

**Step 2: 更新 create_tables.sql**

在 `dev-ops/init-db/create_tables.sql` 末尾追加 `cot_samples` 和 `cot_step_logs` 的 DDL。

**Step 3: 在容器内执行迁移**

```bash
docker exec qa-studio-backend python3 scripts/migrate_professional_cot_to_db.py
```

---

### Phase 2: 提示词模板改造

---

### Task 6: 改 `professional_cot_prompt_service.py` — 读写切换到 prompts 表

**Objective:** 把所有文件读写操作改为 `prompts` 表的 CRUD

**Files:**
- Rewrite: `backend/app/services/professional_cot_prompt_service.py`

**核心变化：**

| 函数 | 改前 | 改后 |
|------|------|------|
| `list_templates()` | glob 遍历用户模板目录 | `SELECT DISTINCT template_id FROM prompts WHERE stage='professional_cot'` |
| `get_template_detail()` | 读 manifest.json | 查 prompts 表构造相同结构的响应 |
| `get_prompt_item()` | 读 `.md` 文件 | `SELECT content FROM prompts WHERE template_id=? AND prompt_key=?` |
| `update_prompt_item()` | `atomic_write_text` | `UPDATE prompts SET content=?` |
| `duplicate_template()` | `shutil.copytree` | `INSERT INTO prompts SELECT ... template_id='new_id'` |
| `delete_template()` | `shutil.rmtree` | `DELETE FROM prompts WHERE template_id=?` |
| `create_run_prompt_snapshot()` | `shutil.copytree` 到 run 目录 | 【不再需要】改为记录 `template_id + version` |
| `read_prompt_from_snapshot()` | 读 run 目录下的文件 | `SELECT content FROM prompts WHERE template_id=? AND prompt_key=?` |

**关键实现细节：**

```python
# 模板列表
def list_templates(user_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        # 系统模板（user_id IS NULL）+ 用户模板
        rows = db.query(Prompt.template_id, Prompt.name, Prompt.version, 
                        Prompt.user_id, Prompt.is_default)\
            .filter(Prompt.stage == StageEnum.PROFESSIONAL_COT)\
            .filter((Prompt.user_id == user_id) | (Prompt.user_id.is_(None)))\
            .distinct().all()
        # ... 构造响应
    finally:
        db.close()

# 获取单个 prompt 内容
def get_prompt_item(template_id: str, user_id: int, prompt_key: str):
    db = SessionLocal()
    try:
        prompt = db.query(Prompt).filter(
            Prompt.template_id == template_id,
            Prompt.prompt_key == prompt_key,
        ).first()
        return {"prompt_key": prompt_key, "content": prompt.content, ...}
    finally:
        db.close()

# 复制模板
def duplicate_template(template_id: str, user_id: int, name: str):
    db = SessionLocal()
    try:
        new_id = f"user_{user_id}_{uuid.uuid4().hex[:8]}"
        source_prompts = db.query(Prompt).filter(Prompt.template_id == template_id).all()
        for sp in source_prompts:
            new_prompt = Prompt(
                user_id=user_id,
                stage=StageEnum.PROFESSIONAL_COT,
                template_id=new_id,
                prompt_key=sp.prompt_key,
                name=name,
                content=sp.content,
                version=1,
            )
            db.add(new_prompt)
        db.commit()
    finally:
        db.close()

# 快照 → 改为记录引用（不再复制文件）
def create_run_prompt_snapshot(template_id: str, user_id: int, task_id: int):
    """记录任务使用的模板版本，不再复制文件"""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        task.prompt_template_id = template_id
        template = db.query(Prompt).filter(
            Prompt.template_id == template_id,
            Prompt.prompt_key == "common.step1_3"  # 取第一个 prompt 的 version
        ).first()
        # 存到 run_extra
        if task.run_extra is None:
            task.run_extra = {}
        task.run_extra["prompt_snapshot"] = {
            "template_id": template_id,
            "version": template.version if template else 1,
            "snapshot_created_at": utc_now_iso(),
        }
        db.commit()
        return task.run_extra["prompt_snapshot"]
    finally:
        db.close()

# 读 prompt（管线执行时使用）
def read_prompt_from_snapshot(template_id: str, prompt_key: str) -> str:
    """从 DB 读 prompt 内容，传入的是 run 创建时的 template_id"""
    db = SessionLocal()
    try:
        prompt = db.query(Prompt).filter(
            Prompt.template_id == template_id,
            Prompt.prompt_key == prompt_key,
        ).first()
        if not prompt:
            raise PromptTemplateError(f"提示词不存在: {template_id}.{prompt_key}")
        return prompt.content
    finally:
        db.close()
```

---

### Phase 3: 执行引擎改造（核心）

---

### Task 7: 改 `create_initial_run()` — 用 Task 记录替代 manifest.json

**Objective:** 创建 run 时写 `tasks` 表而非 `manifest.json`

**Files:**
- Modify: `backend/app/services/professional_cot_service.py`

**Step 1: 重写 `create_initial_run()`**

```python
def create_initial_run(
    *, source_data, source_filename, text_field, paper_text,
    user_id, username, llm_config, model,
    run_name=None, source_file_id=None, prompt_template_id=None,
    source_type="unknown",
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        # 创建 Task 记录
        task = Task(
            user_id=user_id,
            stage=StageEnum.PROFESSIONAL_COT,
            pipeline_mode="professional_cot",
            pipeline_name=PIPELINE_NAME,
            status=TaskStatusEnum.RUNNING,
            model=model,
            source_file_id=source_file_id,
            input_count=len(source_data),
            run_extra={
                "run_name": run_name or f"{PIPELINE_NAME}-{source_filename}",
                "username": username,
                "source_file": {"id": source_file_id, "filename": source_filename},
                "source_input": {"text_field": text_field, "text_length": len(paper_text)},
                "source_type": source_type or "unknown",
                "llm_config_name": llm_config.name,
            },
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # 保存源文件到磁盘（用于导出下载）
        run_dir = get_run_dir_by_task_id(task.id)
        run_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(run_dir / "source.json", source_data)

        # 记录提示词快照引用
        if prompt_template_id:
            snapshot_info = create_run_prompt_snapshot(prompt_template_id, user_id, task.id)

        llm_info = {
            "llm_config_id": llm_config.id,
            "llm_config_name": llm_config.name,
            "model": model,
            "base_url": llm_config.base_url,
            "api_key": llm_config.api_key,
        }

        return {"run_id": str(task.id), "task_id": task.id, "manifest": {}, "llm": llm_info, "input_count": len(source_data)}
    finally:
        db.close()
```

**设计说明：**
- `run_id` 改为 task 的整数 id（字符串化以保持 API 兼容）
- `get_run_dir_by_task_id()` 用 task id 定位文件目录
- 仍写 `source.json` 到磁盘（导出用）
- `prompt_template_id` 记录在 `task` 上

---

### Task 8: 改 `run_pipeline_sync()` — 主循环

**Objective:** 用 Task 对象替代 manifest dict 管理状态

**Files:**
- Modify: `backend/app/services/professional_cot_service.py`

**核心变化：**

```python
def run_pipeline_sync(task_id: int, llm: Dict[str, Any], username: str) -> None:
    register_task()
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return
        
        prompt_template_id = task.prompt_template_id
        run_dir = get_run_dir_by_task_id(task_id)
        
        source_data = read_json(run_dir / "source.json")
        input_count = len(source_data)
        text_field = task.run_extra.get("source_input", {}).get("text_field", "text")

        # 更新状态为 running
        task.status = TaskStatusEnum.RUNNING
        task.input_count = input_count
        task.success_count = 0
        task.failed_count = 0
        task.progress_label = f"正在处理第 1/{input_count} 篇文献"
        db.commit()

        # 恢复逻辑：从 cot_step_logs 反推已完成文档
        completed_indices = set()
        completed_logs = db.query(CotStepLog).filter(
            CotStepLog.task_id == task_id,
            CotStepLog.source_index >= 0,
            CotStepLog.status.in_(["completed", "failed", "skipped"]),
            CotStepLog.step_key == "step6_output",  # 完成标记
        ).all()
        for log in completed_logs:
            completed_indices.add(log.source_index)
        
        # 加载已有样本（用于恢复）
        all_samples = [s for s in db.query(CotSample).filter(
            CotSample.task_id == task_id
        ).order_by(CotSample.source_index).all()]

        for idx, record in enumerate(source_data):
            # 暂停检测：重新查 task.status
            db.refresh(task)
            if task.status == TaskStatusEnum.PAUSED:
                task.progress_label = f"已暂停（完成 {task.success_count}/{input_count} 篇）"
                db.commit()
                return

            # 跳过已处理
            if idx in completed_indices:
                continue

            source_label = record.get("source", f"item_{idx + 1}")
            paper_text = record.get(text_field, "")

            task.progress_label = f"正在处理第 {idx + 1}/{input_count} 篇文献：{source_label}"
            db.commit()

            doc_result = process_one_document(
                source_index=idx,
                source_label=source_label,
                paper_text=paper_text,
                text_field=text_field,
                run_dir=run_dir,
                prompt_template_id=prompt_template_id,
                task_id=task_id,
                user_id=task.user_id,
                llm=llm,
                username=username,
                source_type=task.run_extra.get("source_type"),
                input_count=input_count,
                db=db,
            )

            if doc_result["status"] == "success":
                # 写 cot_samples
                sample = CotSample(
                    task_id=task_id,
                    user_id=task.user_id,
                    source_index=idx,
                    source=source_label,
                    source_type=task.run_extra.get("source_type", "unknown"),
                    cot_type=doc_result.get("cot_type"),
                    cot_type_key=doc_result.get("cot_type_key"),
                    input=doc_result["final_sample"].get("input"),
                    chainofThought=doc_result["final_sample"].get("chainofThought"),
                    output=doc_result["final_sample"].get("output"),
                    evidence_trace=doc_result["final_sample"].get("evidence_trace"),
                    step_results=doc_result.get("step_results"),
                )
                db.add(sample)
                task.success_count += 1

            elif doc_result["status"] == "failed":
                task.failed_count += 1

            task.progress_percentage = int((idx + 1) / input_count * 100)
            db.commit()

            # 增量写 final_samples.json（保留文件兼容）
            all_cot_samples = db.query(CotSample).filter(CotSample.task_id == task_id).all()
            _write_final_samples_json(run_dir, all_cot_samples)

        # 全部完成
        task.status = TaskStatusEnum.COMPLETED
        task.progress_percentage = 100
        db.commit()
    except Exception as e:
        db.rollback()
        task.status = TaskStatusEnum.FAILED
        task.run_extra = task.run_extra or {}
        task.run_extra["error_message"] = str(e)
        db.commit()
    finally:
        db.close()
        unregister_task()
```

---

### Task 9: 改 `process_one_document()` — 步骤日志写 cot_step_logs

**Objective:** 用 `CotStepLog` 替代 `_update_manifest_step`

**Files:**
- Modify: `backend/app/services/professional_cot_service.py`

**核心变化：**

```python
def _log_step(db, task_id, source_index, step_key, **kwargs):
    """写步骤日志到 cot_step_logs"""
    existing = db.query(CotStepLog).filter(
        CotStepLog.task_id == task_id,
        CotStepLog.source_index == source_index,
        CotStepLog.step_key == step_key,
    ).first()
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
    else:
        log = CotStepLog(
            task_id=task_id,
            source_index=source_index,
            step_key=step_key,
            **kwargs,
        )
        db.add(log)

# 在 process_one_document 中：
# 改前:
# _update_manifest_step("step1_3_integrated", status="running", ...)
# 改后:
# _log_step(db, task_id, source_index, "step1_3_integrated", status="running", ...)
```

暂停检测也改为查 DB：

```python
def _check_paused(db, task_id):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task and task.status == TaskStatusEnum.PAUSED:
        raise _PipelinePausedError("流水线已被暂停")
```

---

### Task 10: 改 router — API 适配

**Objective:** 改造 `professional_cot.py` 的路由函数

**Files:**
- Modify: `backend/app/routers/professional_cot.py`

**核心变化：**

```python
# create_run — 使用 task_id 替代 run_id
@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(...):
    # ... 参数验证不变 ...
    init = create_initial_run(...)
    result = {
        "run_id": str(init["task_id"]),  # 兼容前端，字符串化
        "status": "running",
        "message": "单COT生成流水线已启动",
        "input_count": init["input_count"],
    }
    asyncio.get_running_loop().run_in_executor(
        llm_thread_pool,
        partial(run_pipeline_sync, init["task_id"], init["llm"], current_user.username),
    )
    return result

# list_runs — SQL 查询
@router.get("/runs")
async def list_runs(...):
    db = SessionLocal()
    try:
        query = db.query(Task).filter(
            Task.user_id == current_user.id,
            Task.stage == StageEnum.PROFESSIONAL_COT,
        ).order_by(Task.id.desc())
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [_task_to_list_item(t) for t in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    finally:
        db.close()

# get_run_detail — 从 DB 拼装
@router.get("/runs/{run_id}")
async def get_run_detail(run_id: str, ...):
    task_id = int(run_id)
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        
        # 构造兼容旧格式的响应
        samples = db.query(CotSample).filter(CotSample.task_id == task_id).all()
        step_logs = db.query(CotStepLog).filter(CotStepLog.task_id == task_id).all()
        
        return _build_run_detail(task, samples, step_logs)
    finally:
        db.close()

# monitor — SQL 聚合
@router.get("/monitor")
async def professional_cot_monitor(...):
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(Task.stage == StageEnum.PROFESSIONAL_COT).all()
        # ... SQL 聚合计数 ...
    finally:
        db.close()
```

---

### Phase 4: 前端适配 + 清理

---

### Task 11: 前端 API 适配

**Objective:** 确保前端能正确解析新的 API 响应

**Files:**
- Modify: `frontend/src/api/index.js`（基本不变）
- Modify: `frontend/src/views/CotHcot/ProfessionalCotList.vue`
- Modify: `frontend/src/views/CotHcot/ProfessionalCotDetail.vue`

**关键适配：**

1. `run_id` 现在是字符串化的数字（如 `"42"`），路由参数类型需确认
2. `ProfessionalCotDetail.vue` 的字段映射（新增字段如 `source_type` 已在 task 中）
3. `ConfigCenter.vue` 的监控面板数据映射

**验证：**

```bash
# 本地构建前端并测试
cd ~/qa_gen/frontend
npm run build
```

---

### Task 12: 清理旧文件存储代码 + Docker 卷配置

**Objective:** 删除不再需要的文件操作函数，确保 volume 挂载正确

**Files:**
- Modify: `backend/app/services/professional_cot_service.py`
- Modify: `dev-ops/docker-compose.yml`

**清理：**
- 删除 `load_manifest()`、`save_manifest()`（或被降级为辅助函数）
- 删除 `_refresh_manifest_progress()`
- 保留 `atomic_write_json`、`read_json`（导出仍需要）
- 确认 `docker-compose.yml` 中 backend 有 `- backend-storage:/app/storage` 挂载

---

### Task 13: 端到端验证

**Objective:** 完整流程测试

**验证步骤：**

1. **部署更新**
```bash
cd ~/qa_gen/dev-ops
sudo docker compose down
sudo docker volume rm dev-ops_frontend-dist
sudo docker compose up -d --build
# 执行迁移
sudo docker exec qa-studio-backend python3 scripts/migrate_professional_cot_to_db.py
```

2. **创建系统默认模板**
```bash
# 需要一次性迁移系统提示词到 prompts 表
sudo docker exec qa-studio-backend python3 scripts/seed_professional_cot_prompts.py
```

3. **功能测试**
- 打开「单COT提示词」页面 → 查看系统模板、编辑保存
- 打开「单COT生成」页面 → 创建新 run
- 查看详情页 → 进度轮询正常
- run 完成后 → 导出下载正常
- 暂停/恢复 → 状态正确
- ConfigCenter 监控 → 数据正常

---

## 风险点

| 风险 | 缓解措施 |
|------|---------|
| API 兼容性 | `run_id` 统一字符串化，响应结构不变 |
| 旧 run 数据 | 保留文件存储作为历史数据只读；新 run 用 DB |
| 暂停/恢复 | `task.status` 字段 + `cot_step_logs` 取代 manifest |
| 并发安全 | `db.refresh(task)` + SQLAlchemy 行级锁 |
| Docker 数据丢失 | `backend-storage` 卷仅用于源文件和导出文件，核心数据在 MySQL |

---

## 执行顺序

```
Phase 1 (Task 1-5)  →  基础设施，无业务影响
Phase 2 (Task 6)    →  提示词模板改造
Phase 3 (Task 7-10) →  执行引擎 + API 改造
Phase 4 (Task 11-13)→  前端适配 + 验证
```

每个 Phase 内部按 Task 顺序执行。Phase 1 完成后即可合并，不影响运行中的服务。
