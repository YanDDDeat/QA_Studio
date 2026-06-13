
"""
Widens the width of all 'stage' related columns in the database to VARCHAR(64)
to accommodate longer stage enum values.

Run with: python -m scripts.migrate_stage_column_width
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import SessionLocal

TABLES_AND_COLUMNS = {
    "prompts": "stage",
    "datasets": "current_stage",
    "files": "source_stage",
    "tasks": "stage",
}

def widen_stage_columns():
    """Widens all stage-related columns to VARCHAR(64)."""
    db = SessionLocal()
    try:
        with db.begin():
            for table, column in TABLES_AND_COLUMNS.items():
                # This assumes a MySQL backend.
                # For other backends, the ALTER TABLE syntax might differ.
                sql = text(f"ALTER TABLE {table} MODIFY COLUMN {column} VARCHAR(64);")
                db.execute(sql)
                print(f"[migrate] Successfully widened column '{column}' in table '{table}'.")
        print("[migrate] All stage columns have been widened.")
    except Exception as e:
        print(f"[migrate] An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("[migrate] === Widening stage-related columns to VARCHAR(64) ===")
    widen_stage_columns()
    print("[migrate] === Migration complete ===")
