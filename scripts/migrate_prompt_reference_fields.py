"""迁移：prompts 表新增 reference_fields JSON 列

存储用户选择的附加参考字段列表，如 ["input", "output", "domain"]。
为空/NULL 时使用各阶段的默认字段。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    db.execute(text(
        "ALTER TABLE prompts ADD COLUMN reference_fields JSON NULL "
        "COMMENT '附加参考字段列表'"
    ))
    db.commit()
    print("✅ prompts.reference_fields 列添加成功")
except Exception as e:
    db.rollback()
    if "Duplicate column" in str(e):
        print("⚠️ 列已存在，跳过")
    else:
        print(f"❌ 迁移失败: {e}")
finally:
    db.close()
