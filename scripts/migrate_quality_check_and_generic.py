"""Migration: 扩展 4 个 ENUM 列加入 'quality_check' 和 'generic'，并插入默认质检 Prompt。

涉及的列：
- tasks.stage
- prompts.stage
- files.source_stage
- datasets.current_stage

新增枚举值：
- quality_check
- generic

同时插入一条 stage='quality_check'、user_id=NULL、is_default=True 的默认 Prompt。

可重复执行（幂等）：
- ALTER 前会先 SHOW COLUMNS 判断是否已包含新枚举值，已包含则跳过
- 插入默认 Prompt 前会查询是否已存在 is_default=True 的同 stage Prompt，已存在则跳过

Run with: python scripts/migrate_quality_check_and_generic.py
"""

import sys
import os
from datetime import datetime

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

# StageEnum 全集（必须与 backend/app/models/models.py 保持一致）
# 顺序按 models.py 的成员顺序排，避免历史索引依赖混乱。
ALL_STAGE_VALUES = [
    "question_generate",
    "knowledge_generate",
    "question_validate",
    "answer_generate",
    "answer_validate",
    "data_evaluate",
    "quality_check",
    "cot_filter",
    "dataset_split",
    "dataset_assessment",
    "generic",
]

NEW_VALUES = {"quality_check", "generic"}

# 需要扩展的 4 个 ENUM 列：(table, column, nullable, default)
ENUM_COLUMNS = [
    ("tasks", "stage", False, None),
    ("prompts", "stage", False, None),
    ("files", "source_stage", True, None),
    ("datasets", "current_stage", True, "question_generate"),
]

# 默认质检 Prompt 内容（见需求文档子需求 2）
DEFAULT_QUALITY_CHECK_PROMPT = """你是 QA 数据质检专家。根据给定记录的问题、答案、推理过程、知识体系以及评分维度，判断该条数据是否合格。

合格标准：综合评分 ≥ 4 且各维度评分 ≥ 3，且推理逻辑无明显错误。

请返回 JSON：
{
  "validation_result": "PASS" 或 "FAIL",
  "reason": "判断理由（中文，50-150 字）"
}
"""


def _enum_contains_all(current_def: str, required_values: set) -> bool:
    """判断 SHOW COLUMNS 返回的 enum 定义字符串是否已包含所有 required_values。"""
    return all(f"'{v}'" in current_def for v in required_values)


def _build_enum_clause(values: list) -> str:
    """构造 ENUM('a','b',...) 子句。"""
    quoted = ",".join(f"'{v}'" for v in values)
    return f"ENUM({quoted})"


def migrate_enums():
    with engine.begin() as conn:
        for table, column, nullable, default in ENUM_COLUMNS:
            # 查询当前列定义
            row = conn.execute(text(
                f"SHOW COLUMNS FROM {table} WHERE Field = :col"
            ), {"col": column}).fetchone()

            if row is None:
                print(f"[WARN] 列 {table}.{column} 不存在，跳过")
                continue

            current_type = row[1]  # 形如 enum('a','b',...)

            if _enum_contains_all(current_type, NEW_VALUES):
                print(f"[SKIP] {table}.{column} 已包含 quality_check 和 generic")
                continue

            # 构造新的 ENUM 定义。沿用 ALL_STAGE_VALUES 顺序确保稳定。
            enum_clause = _build_enum_clause(ALL_STAGE_VALUES)
            null_clause = "NULL" if nullable else "NOT NULL"
            default_clause = f" DEFAULT '{default}'" if default else ""

            sql = (
                f"ALTER TABLE {table} MODIFY COLUMN {column} "
                f"{enum_clause} {null_clause}{default_clause}"
            )
            print(f"[ALTER] {sql}")
            conn.execute(text(sql))
            print(f"[OK] {table}.{column} 已扩展")


def insert_default_quality_check_prompt():
    with engine.begin() as conn:
        # 检查是否已存在默认质检 Prompt
        existing = conn.execute(text(
            "SELECT id FROM prompts "
            "WHERE stage = 'quality_check' AND is_default = 1 AND user_id IS NULL "
            "LIMIT 1"
        )).fetchone()

        if existing:
            print(f"[SKIP] 默认质检 Prompt 已存在 (id={existing[0]})")
            return

        result = conn.execute(
            text(
                "INSERT INTO prompts "
                "(user_id, stage, version, name, content, is_default, created_at) "
                "VALUES (NULL, 'quality_check', 1, :name, :content, 1, :created_at)"
            ),
            {
                "name": "默认质检 Prompt",
                "content": DEFAULT_QUALITY_CHECK_PROMPT,
                "created_at": datetime.utcnow(),
            },
        )
        print(f"[INSERT] 默认质检 Prompt 插入成功 (rowcount={result.rowcount})")


def migrate():
    print("====== 开始迁移：quality_check + generic ======")
    migrate_enums()
    insert_default_quality_check_prompt()
    print("====== 迁移完成 ======")


if __name__ == "__main__":
    migrate()
