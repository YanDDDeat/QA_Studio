"""Migration: 为 tasks 表新增 chunk_index 和 total_chunks 字段。

用途：支持分 chunk 并行流水线，每个子任务可标识属于哪个 chunk。
幂等：列已存在则跳过。

Run with: python scripts/migrate_chunk_pipeline.py
"""

import sys
import os

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


def migrate():
    print("====== 开始迁移：tasks 新增 chunk_index + total_chunks ======")
    with engine.begin() as conn:
        for col_name, col_type, comment in [
            ("chunk_index", "INTEGER DEFAULT NULL", "chunk 序号（0-based）"),
            ("total_chunks", "INTEGER DEFAULT NULL", "总 chunk 数"),
        ]:
            row = conn.execute(text(
                f"SHOW COLUMNS FROM tasks WHERE Field = '{col_name}'"
            )).fetchone()
            if row:
                print(f"[SKIP] tasks.{col_name} 列已存在")
                continue
            sql = text(
                f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type} COMMENT '{comment}'"
            )
            print(f"[ALTER] ALTER TABLE tasks ADD COLUMN {col_name} ...")
            conn.execute(sql)
            print(f"[OK] tasks.{col_name} 列已添加")
    print("====== 迁移完成 ======")


if __name__ == "__main__":
    migrate()