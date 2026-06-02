"""Fix old enum values in the database.

- Adds 'cot_hcot_pipeline' to all 4 ENUM columns
- Migrates 'cot_flow' and 'cot_hcot' → 'cot_hcot_pipeline'

Run with: python -m scripts.migrate_enum_cot_hcot_pipeline
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import engine

NEW_ENUM = (
    "enum('question_generate','knowledge_generate','question_validate',"
    "'answer_generate','answer_validate','data_evaluate','quality_check',"
    "'cot_hcot_pipeline','cot_hcot','cot_flow','cot_filter',"
    "'dataset_split','dataset_assessment','generic')"
)

TABLES_COLS = [
    ("tasks", "stage"),
    ("files", "source_stage"),
    ("prompts", "stage"),
    ("datasets", "current_stage"),
]


def migrate():
    with engine.begin() as conn:
        for table, col in TABLES_COLS:
            # ALTER ENUM 列，加入 cot_hcot_pipeline
            conn.execute(text(f"ALTER TABLE {table} MODIFY COLUMN {col} {NEW_ENUM}"))
            print(f"[migrate] {table}.{col} ENUM updated (added cot_hcot_pipeline)")

            # cot_flow → cot_hcot_pipeline
            r1 = conn.execute(text(
                f"UPDATE {table} SET {col} = 'cot_hcot_pipeline' WHERE {col} = 'cot_flow'"
            ))
            print(f"[migrate] {table}.{col}: {r1.rowcount} rows cot_flow → cot_hcot_pipeline")

            # cot_hcot → cot_hcot_pipeline
            r2 = conn.execute(text(
                f"UPDATE {table} SET {col} = 'cot_hcot_pipeline' WHERE {col} = 'cot_hcot'"
            ))
            print(f"[migrate] {table}.{col}: {r2.rowcount} rows cot_hcot → cot_hcot_pipeline")

    print("[migrate] === All old enum values migrated to cot_hcot_pipeline ===")


if __name__ == "__main__":
    print("[migrate] === Fixing enum columns: add cot_hcot_pipeline, migrate cot_flow/cot_hcot ===")
    migrate()