"""
为 datasets 表添加复合索引 (user_id, current_stage, created_at)
解决慢查询：全表扫描 310K 行 → 走索引 <0.01s
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import text
from app.database import engine


def migrate():
    with engine.connect() as conn:
        # 检查索引是否已存在
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() "
            "AND table_name = 'datasets' "
            "AND index_name = 'idx_datasets_user_stage_created'"
        ))
        if result.scalar() > 0:
            print("索引 idx_datasets_user_stage_created 已存在，跳过")
            return

        conn.execute(text(
            "CREATE INDEX idx_datasets_user_stage_created "
            "ON datasets (user_id, current_stage, created_at)"
        ))
        conn.commit()
        print("索引 idx_datasets_user_stage_created 创建成功")


if __name__ == "__main__":
    migrate()