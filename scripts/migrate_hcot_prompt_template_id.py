"""Add prompt_template_id column to tasks table.

Run with: python -m scripts.migrate_hcot_prompt_template_id
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import engine


def main():
    print("[migrate] === Adding prompt_template_id to tasks table ===")

    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'tasks' AND column_name = 'prompt_template_id'"
        )
        count = result.fetchone()[0]

        if count > 0:
            print("[migrate] Column 'prompt_template_id' already exists, skipping")
        else:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN prompt_template_id VARCHAR(128) NULL "
                "COMMENT 'H-CoT prompt template ID'"
            )
            conn.commit()
            print("[migrate] Column 'prompt_template_id' added successfully")

    print("[migrate] === Migration complete ===")


if __name__ == "__main__":
    main()