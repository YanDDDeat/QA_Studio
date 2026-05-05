"""Task 状态 PAUSED 迁移注记

本脚本为文档化迁移，用于将来从 SQLite → MySQL 切换时的参考。
当前 SQLite 环境下 TaskStatusEnum 使用 String 类型存储，新增的 PAUSED 值
无需显式 ALTER TABLE — SQLAlchemy 会在下次建表或访问时自动识别。

若将来切换 MySQL：
    ALTER TABLE tasks MODIFY COLUMN status ENUM('pending','running','paused','completed','failed') NOT NULL DEFAULT 'pending';

历史任务（已存在的 running/completed/failed）不受影响。
"""

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.database import SessionLocal
    from app.models.models import Task, TaskStatusEnum

    db = SessionLocal()
    try:
        running = db.query(Task).filter(Task.status == TaskStatusEnum.RUNNING).count()
        paused = db.query(Task).filter(Task.status == TaskStatusEnum.PAUSED).count()
        print(f"当前状态统计: running={running}, paused={paused}")
        print("PAUSED 枚举值已就绪，无需额外迁移。")
    finally:
        db.close()
