"""Add file_id column to the datasets table.

Links each Dataset record to the File it belongs to, enabling
write_datasets_to_file() to serialize the right records back to disk.

Usage:
    cd backend
    python scripts/add_file_id.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


def add_file_id():
    """Add file_id column to datasets table if it doesn't already exist."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'datasets' "
            "AND COLUMN_NAME = 'file_id'"
        ))
        exists = result.scalar() > 0

        if exists:
            print("file_id column already exists in datasets table. Skipping.")
            return

        # Add the column with a foreign key constraint
        conn.execute(text(
            "ALTER TABLE datasets ADD COLUMN file_id INTEGER NULL,"
            " ADD INDEX ix_datasets_file_id (file_id),"
            " ADD CONSTRAINT fk_datasets_file_id"
            " FOREIGN KEY (file_id) REFERENCES files(id)"
        ))
        conn.commit()
        print("file_id column added to datasets table successfully.")


if __name__ == "__main__":
    add_file_id()