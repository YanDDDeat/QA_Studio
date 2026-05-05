import os, sys
os.chdir(r'D:\Code\QA_Studio\backend')
sys.path.insert(0, '.')
from app.config import settings
import pymysql

NEW_ENUM = "ENUM('question_generate','knowledge_generate','question_validate','answer_generate','answer_validate','data_evaluate','cot_filter','dataset_split','dataset_assessment')"

conn = pymysql.connect(
    host=settings.DB_HOST,
    port=int(settings.DB_PORT),
    user=settings.DB_USER,
    password=settings.DB_PASSWORD,
    database=settings.DB_NAME,
    charset='utf8mb4'
)
try:
    with conn.cursor() as cur:
        # datasets.current_stage
        sql = f"ALTER TABLE datasets MODIFY COLUMN current_stage {NEW_ENUM} DEFAULT 'question_generate'"
        cur.execute(sql)
        conn.commit()
        print('datasets.current_stage OK')

        # prompts.stage
        sql = f"ALTER TABLE prompts MODIFY COLUMN stage {NEW_ENUM} NOT NULL"
        cur.execute(sql)
        conn.commit()
        print('prompts.stage OK')

        # tasks.stage
        sql = f"ALTER TABLE tasks MODIFY COLUMN stage {NEW_ENUM} NOT NULL"
        cur.execute(sql)
        conn.commit()
        print('tasks.stage OK')

    print('All done')
finally:
    conn.close()
