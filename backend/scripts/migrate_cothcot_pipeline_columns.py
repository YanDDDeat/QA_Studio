"""Add CoT/H-CoT pipeline columns to the tasks table.

Adds: parent_task_id, pipeline_mode, pipeline_name, step_name

Run with: python -m scripts.migrate_cothcot_pipeline_columns
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import engine


def migrate():
    """Add 4 nullable columns to the tasks table."""
    columns = [
        ("parent_task_id", "INTEGER NULL"),
        ("pipeline_mode", "VARCHAR(16) NULL"),
        ("pipeline_name", "VARCHAR(128) NULL"),
        ("step_name", "VARCHAR(64) NULL"),
    ]

    with engine.begin() as conn:
        # 检查现有列，避免重复添加
        existing_cols = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tasks'"
            ))
        }

        for col_name, col_type in columns:
            if col_name in existing_cols:
                print(f"[migrate] Column '{col_name}' already exists in tasks. Skipping.")
                continue

            alter_sql = text(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type}")
            conn.execute(alter_sql)
            print(f"[migrate] Added column '{col_name}' ({col_type}) to tasks.")

        # 为 parent_task_id 添加索引和 FK（MySQL 不支持 ALTER ADD CONSTRAINT 直接加 FK 到自引用列，
        # 使用单独语句）
        if "parent_task_id" not in existing_cols:
            try:
                conn.execute(text(
                    "CREATE INDEX ix_tasks_parent_task_id ON tasks (parent_task_id)"
                ))
                print("[migrate] Created index ix_tasks_parent_task_id.")
            except Exception as e:
                print(f"[migrate] Index creation skipped (may already exist): {e}")

            # 添加外键约束
            try:
                conn.execute(text(
                    "ALTER TABLE tasks ADD CONSTRAINT fk_tasks_parent_task "
                    "FOREIGN KEY (parent_task_id) REFERENCES tasks(id) ON DELETE SET NULL"
                ))
                print("[migrate] Added FK constraint fk_tasks_parent_task.")
            except Exception as e:
                print(f"[migrate] FK constraint skipped: {e}")

    print("[migrate] === Migration complete ===")


if __name__ == "__main__":
    print("[migrate] === Adding CoT/H-CoT pipeline columns to tasks ===")
    migrate()