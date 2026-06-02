"""最终迁移：ENUM → VARCHAR + 清理旧值

把 4 个 ENUM 列改为 VARCHAR(64)，清理 cot_flow/cot_hcot → cot_hcot_pipeline。
之后再也不需要写 enum 迁移脚本了——Python 代码里加新枚举值即可。

Run with: python -m scripts.migrate_enum_to_varchar
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import engine

TABLES_COLS = [
    ("datasets", "current_stage"),  # 只剩这一个没改完
]


def migrate():
    with engine.begin() as conn:
        for table, col in TABLES_COLS:
            # 1) 先把 ENUM 列改为 VARCHAR(64) — 这样任何字符串值都能存
            conn.execute(text(
                f"ALTER TABLE {table} MODIFY COLUMN {col} VARCHAR(64)"
            ))
            print(f"[migrate] {table}.{col}: ENUM → VARCHAR(64) ✓")

            # 2) 清理旧值（VARCHAR 不限制值范围，可以自由 UPDATE）
            r1 = conn.execute(text(
                f"UPDATE {table} SET {col} = 'cot_hcot_pipeline' WHERE {col} = 'cot_flow'"
            ))
            print(f"[migrate] {table}.{col}: {r1.rowcount} rows cot_flow → cot_hcot_pipeline")

            r2 = conn.execute(text(
                f"UPDATE {table} SET {col} = 'cot_hcot_pipeline' WHERE {col} = 'cot_hcot'"
            ))
            print(f"[migrate] {table}.{col}: {r2.rowcount} rows cot_hcot → cot_hcot_pipeline")

    print("[migrate] === 全部完成。以后加新枚举值只需改 Python 代码，不再需要迁移脚本 ===")


if __name__ == "__main__":
    print("[migrate] === ENUM → VARCHAR + 清理旧值（最后一次迁移） ===")
    migrate()