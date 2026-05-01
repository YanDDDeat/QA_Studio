"""QA Studio Backend - FastAPI Application

启动方式：
    从 backend 目录运行: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

    或者直接运行此文件: python run.py
"""

from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)