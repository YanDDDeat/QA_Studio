"""Add l0_question_index column to the tasks table.

Adds: l0_question_index (INTEGER NULL) — identifies which L0 overall question
a per-L0 sub-task belongs to (0-based index). NULL means "not applicable"
for document-level or per-chunk steps.

Run with: python -m scripts.migrate_l0_question_index
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import engine


def migrate():
    """Add nullable l0_question_index column to the tasks table."""
    with engine.begin() as conn:
        # 检查现有列，避免重复添加
        existing_cols = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tasks'"
            ))
        }

        if "l0_question_index" in existing_cols:
            print("[migrate] Column 'l0_question_index' already exists in tasks. Skipping.")
        else:
            conn.execute(text(
                "ALTER TABLE tasks ADD COLUMN l0_question_index INTEGER NULL"
            ))
            print("[migrate] Added column 'l0_question_index' (INTEGER NULL) to tasks.")

    print("[migrate] === Migration complete ===")


if __name__ == "__main__":
    print("[migrate] === Adding l0_question_index column to tasks ===")
    migrate()