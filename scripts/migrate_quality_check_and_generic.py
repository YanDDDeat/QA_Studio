"""Migration: extend ENUM columns for quality_check + generic stages, and seed default quality_check prompt.

Run with: python scripts/migrate_quality_check_and_generic.py
"""

import sys
import os

# Read DB config from .env file (project root)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
config = {}
if os.path.exists(dotenv_path):
    with open(dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip()

db_host = config.get("DB_HOST", "localhost")
db_port = config.get("DB_PORT", "3306")
db_user = config.get("DB_USER", "root")
db_password = config.get("DB_PASSWORD", "")
db_name = config.get("DB_NAME", "qa_gen")

db_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"

from sqlalchemy import create_engine, text

engine = create_engine(db_url, echo=False, pool_pre_ping=True, pool_recycle=3600)

# New values to add to ENUM columns
NEW_VALUES = ("quality_check", "generic")

# ENUM columns that need extension
ENUM_COLUMNS = [
    ("tasks", "stage"),
    ("prompts", "stage"),
    ("files", "source_stage"),
    ("datasets", "current_stage"),
]

# Default quality_check prompt content
QUALITY_CHECK_PROMPT_CONTENT = """你是 QA 数据质检专家。根据给定记录的问题、答案、推理过程、知识体系以及评分维度，判断该条数据是否合格。

合格标准：综合评分 >= 4 且各维度评分 >= 3，且推理逻辑无明显错误。

请返回 JSON：
{
  "validation_result": "PASS" 或 "FAIL",
  "reason": "判断理由（中文，50-150 字）"
}"""


def get_current_enum_values(conn, table: str, column: str) -> list:
    """Fetch current ENUM values for a column."""
    result = conn.execute(text(
        "SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() "
        "AND TABLE_NAME = :tbl "
        "AND COLUMN_NAME = :col"
    ), {"tbl": table, "col": column})
    row = result.fetchone()
    if not row:
        return []
    col_type = row[0]
    # Parse ENUM('val1','val2',...) from column type string
    if not col_type or "(" not in col_type:
        return []
    vals_str = col_type[col_type.index("(") + 1 : col_type.rindex(")")]
    # Split by comma, strip quotes
    values = []
    for v in vals_str.split(","):
        v = v.strip().strip("'")
        if v:
            values.append(v)
    return values


def migrate_enums():
    """Extend ENUM columns to include quality_check and generic values."""
    with engine.begin() as conn:
        for table, column in ENUM_COLUMNS:
            current = get_current_enum_values(conn, table, column)
            if not current:
                print(f"  [SKIP] {table}.{column}: cannot determine current ENUM values")
                continue

            missing = [v for v in NEW_VALUES if v not in current]
            if not missing:
                print(f"  [OK] {table}.{column}: already includes all new values")
                continue

            all_values = current + missing
            value_list = ", ".join(f"'{v}'" for v in all_values)
            # Determine if column has NOT NULL
            not_null_result = conn.execute(text(
                "SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = :tbl "
                "AND COLUMN_NAME = :col"
            ), {"tbl": table, "col": column})
            nullable_row = not_null_result.fetchone()
            is_nullable = nullable_row[0] == "YES" if nullable_row else True
            null_clause = "NOT NULL" if not is_nullable else "NULL"

            sql = f"ALTER TABLE `{table}` MODIFY COLUMN `{column}` ENUM({value_list}) {null_clause}"
            conn.execute(text(sql))
            print(f"  [DONE] {table}.{column}: added {missing} → now {all_values}")


def seed_quality_check_prompt():
    """Insert default quality_check prompt if it doesn't already exist."""
    with engine.begin() as conn:
        # Check if a default quality_check prompt with same content already exists
        result = conn.execute(text(
            "SELECT id FROM prompts "
            "WHERE stage = 'quality_check' AND is_default = 1 AND user_id IS NULL"
        ))
        if result.fetchone():
            print("  [SKIP] Default quality_check prompt already exists")
            return

        conn.execute(text(
            "INSERT INTO prompts (user_id, stage, version, name, content, is_default) "
            "VALUES (NULL, 'quality_check', 1, '质检默认Prompt', :content, 1)"
        ), {"content": QUALITY_CHECK_PROMPT_CONTENT})
        print("  [DONE] Default quality_check prompt inserted")


if __name__ == "__main__":
    print("=== Phase 1: Extending ENUM columns ===")
    migrate_enums()
    print("=== Phase 2: Seeding default prompt ===")
    seed_quality_check_prompt()
    print("=== Migration complete ===")
