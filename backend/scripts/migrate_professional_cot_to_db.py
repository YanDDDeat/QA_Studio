#!/usr/bin/env python3
"""迁移脚本：为 professional_cot 管线创建新表、添加新列。

用法:
  cd backend
  python3 scripts/migrate_professional_cot_to_db.py

或容器内:
  docker exec qa-studio-backend python3 scripts/migrate_professional_cot_to_db.py
"""

import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from sqlalchemy import text

MIGRATIONS = [
    # prompts 表新列
    "ALTER TABLE prompts ADD COLUMN template_id VARCHAR(128) NULL",
    "ALTER TABLE prompts ADD COLUMN prompt_key VARCHAR(128) NULL",

    # tasks 表新列
    "ALTER TABLE tasks ADD COLUMN input_count INT DEFAULT 1",
    "ALTER TABLE tasks ADD COLUMN success_count INT DEFAULT 0",
    "ALTER TABLE tasks ADD COLUMN failed_count INT DEFAULT 0",
    "ALTER TABLE tasks ADD COLUMN sample_count INT DEFAULT 0",
    "ALTER TABLE tasks ADD COLUMN run_extra JSON NULL COMMENT 'run 元数据：source_input, recommended_cot_type, final_outputs 等'",

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
        step_results JSON NULL COMMENT '各步骤 LLM 原始返回',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES tasks(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        INDEX idx_cot_task (task_id),
        INDEX idx_cot_type (cot_type_key),
        INDEX idx_cot_user (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # cot_step_logs 表
    """CREATE TABLE IF NOT EXISTS cot_step_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        task_id INT NOT NULL,
        source_index INT DEFAULT 0 COMMENT '文献序号，-1表示run级别',
        step_key VARCHAR(64) NOT NULL COMMENT 'step1_3_integrated/step4_input/step5_chain/step6_output',
        status VARCHAR(16) DEFAULT 'pending' COMMENT 'pending/running/completed/failed/skipped',
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
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # prompts 表索引
    "CREATE INDEX IF NOT EXISTS idx_template_prompt ON prompts (template_id, prompt_key)",
]


def main():
    db = SessionLocal()
    try:
        for sql in MIGRATIONS:
            sql_short = sql[:80].replace('\n', ' ')
            try:
                db.execute(text(sql))
                print(f"\u2713 {sql_short}...")
            except Exception as e:
                err_msg = str(e)
                if any(kw in err_msg.lower() for kw in ('duplicate column', 'duplicate key', 'already exists', 'duplicate index')):
                    print(f"\u2192 已存在，跳过: {sql_short}...")
                else:
                    print(f"\u2717 失败: {sql_short}... \u2192 {e}")
        db.commit()
        print("\n迁移完成！")
    finally:
        db.close()


if __name__ == "__main__":
    main()
