"""迁移脚本：创建 professional_cot_type_stats 表并插入10行初始数据

用法：
    cd backend
    python scripts/migrate_cot_type_stats.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, SessionLocal, Base
from app.models.models import ProfessionalCotTypeStat
from app.services.professional_cot_service import COT_TYPES


def migrate():
    """建表 + 插入10行初始数据"""
    print("创建 professional_cot_type_stats 表...")
    Base.metadata.create_all(bind=engine, tables=[ProfessionalCotTypeStat.__table__])
    print("表创建成功。")

    db = SessionLocal()
    try:
        existing = db.query(ProfessionalCotTypeStat).count()
        if existing > 0:
            print(f"表已有 {existing} 行数据，跳过初始插入。")
        else:
            for item in COT_TYPES:
                row = ProfessionalCotTypeStat(
                    cot_type_key=item["key"],
                    display_name=item["display_name"],
                    count=0,
                )
                db.add(row)
            db.commit()
            print(f"已插入 {len(COT_TYPES)} 行初始数据（count=0）。")
    except Exception as e:
        print(f"插入初始数据失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    migrate()