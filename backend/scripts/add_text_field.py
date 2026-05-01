"""Add text_field column to the files table.

Usage:
    cd backend
    python scripts/add_text_field.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


def add_text_field():
    """Add text_field column to files table if it doesn't already exist."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'files' "
            "AND COLUMN_NAME = 'text_field'"
        ))
        exists = result.scalar() > 0

        if exists:
            print("text_field column already exists in files table. Skipping.")
            return

        conn.execute(text(
            "ALTER TABLE files ADD COLUMN text_field VARCHAR(128) NOT NULL DEFAULT 'text'"
        ))
        conn.commit()
        print("text_field column added to files table successfully.")


if __name__ == "__main__":
    add_text_field()