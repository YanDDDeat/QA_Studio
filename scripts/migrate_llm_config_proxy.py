"""Migration: add proxy column to llm_configs table.

Run with: python scripts/migrate_llm_config_proxy.py
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
    with engine.begin() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'llm_configs' "
            "AND COLUMN_NAME = 'proxy'"
        ))
        if result.scalar() == 0:
            conn.execute(text(
                "ALTER TABLE llm_configs ADD COLUMN proxy VARCHAR(512) NULL "
                "AFTER api_key"
            ))
            print("Added column: proxy")
        else:
            print("Column proxy already exists, skipping")

    print("Migration complete")


if __name__ == "__main__":
    migrate()