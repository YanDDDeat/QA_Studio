"""Migration: 为 tasks 表新增 progress_label 字段。

新增列：
- tasks.progress_label  VARCHAR(100) DEFAULT NULL

用途：存储步骤进度阶段描述（如"调用 LLM 生成事实卡..."、"组装提示词..."），
配合一键生成功能，progress_current/progress_total 改为百分比制(0-100)。

幂等：执行前先判断列是否已存在，已存在则跳过。

Run with: python scripts/migrate_auto_run_progress.py
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


def migrate():
    print("====== 开始迁移：tasks 新增 progress_label ======")
    with engine.begin() as conn:
        # 检查列是否已存在
        row = conn.execute(text(
            "SHOW COLUMNS FROM tasks WHERE Field = 'progress_label'"
        )).fetchone()

        if row:
            print("[SKIP] tasks.progress_label 列已存在，无需迁移")
            return

        # 新增列
        sql = text(
            "ALTER TABLE tasks ADD COLUMN progress_label VARCHAR(100) DEFAULT NULL "
            "COMMENT '步骤进度阶段描述'"
        )
        print("[ALTER] ALTER TABLE tasks ADD COLUMN progress_label ...")
        conn.execute(sql)
        print("[OK] tasks.progress_label 列已添加")

    print("====== 迁移完成 ======")


if __name__ == "__main__":
    migrate()