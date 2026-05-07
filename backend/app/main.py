"""QA Studio Backend - FastAPI Application"""

import asyncio
import bcrypt
import logging
from logging.handlers import TimedRotatingFileHandler
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Logging configuration: file (daily, keep all) + console
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_log_format = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# File handler: daily rotation, keep 90 days, DEBUG level (save everything)
_file_handler = TimedRotatingFileHandler(
    os.path.join(LOG_DIR, "qa_studio.log"),
    when="midnight",
    backupCount=90,
    encoding="utf-8",
)
_file_handler.setFormatter(_log_format)
_file_handler.setLevel(logging.DEBUG)

# Console handler (INFO only, avoid flooding terminal)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_format)
_console_handler.setLevel(logging.INFO)

# Apply to qa_studio root logger — DEBUG so file captures everything
_root_logger = logging.getLogger("qa_studio")
_root_logger.setLevel(logging.DEBUG)
_root_logger.addHandler(_file_handler)
_root_logger.addHandler(_console_handler)

# Also route uvicorn logs to file
for _uv_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    _uv_logger = logging.getLogger(_uv_name)
    _uv_logger.setLevel(logging.DEBUG)
    _uv_logger.addHandler(_file_handler)

from app.routers import (
    auth,
    datasets,
    files,
    prompts,
    tasks,
    task_logs,
    question_generate,
    knowledge_generate,
    question_validate,
    answer_generate,
    answer_validate,
    data_evaluate,
    data_manage,
    config_center,
    file_manage,
    llm_config,
    cot_filter,
    dataset_split,
    dataset_assessment,
)
from app.database import engine, Base, SessionLocal
from app.models import User, Dataset, File, Prompt, Task, TaskLog, LLMConfig
from app.config import settings

app = FastAPI(
    title="QA Studio",
    description="QA数据生成与评估平台",
    version="0.1.0",
    redirect_slashes=False,
)


@app.on_event("startup")
async def startup_event():
    """Create database tables, initialize admin account, and test LLM connection."""
    Base.metadata.create_all(bind=engine)

    # Auto-initialize admin account
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if admin is None:
            password_hash = bcrypt.hashpw(
                settings.ADMIN_INIT_PASSWORD.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")
            admin = User(
                username=settings.ADMIN_USERNAME,
                password_hash=password_hash,
            )
            db.add(admin)
            db.commit()
            print(f"[Startup] Admin account created: username='{settings.ADMIN_USERNAME}'")
        else:
            print(f"[Startup] Admin account exists: username='{settings.ADMIN_USERNAME}'")
    except Exception as e:
        print(f"[Startup] Error initializing admin: {e}")
        db.rollback()
    finally:
        db.close()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["数据集"])
app.include_router(files.router, prefix="/api/files", tags=["文件"])
app.include_router(prompts.router, prefix="/api/prompts", tags=["Prompt"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["任务"])
app.include_router(task_logs.router, prefix="/api/task-logs", tags=["任务日志"])
app.include_router(question_generate.router, prefix="/api/question-generate", tags=["问题生成"])
app.include_router(knowledge_generate.router, prefix="/api/knowledge-generate", tags=["知识体系生成"])
app.include_router(question_validate.router, prefix="/api/question-validate", tags=["问题校验"])
app.include_router(answer_generate.router, prefix="/api/answer-generate", tags=["答案生成"])
app.include_router(answer_validate.router, prefix="/api/answer-validate", tags=["答案校验"])
app.include_router(data_evaluate.router, prefix="/api/data-evaluate", tags=["数据评估"])
app.include_router(data_manage.router, prefix="/api/data-manage", tags=["数据管理"])
app.include_router(config_center.router, prefix="/api/config-center", tags=["配置中心"])
app.include_router(file_manage.router, prefix="/api/file-manage", tags=["文件管理"])
app.include_router(llm_config.router, prefix="/api/llm-configs", tags=["LLM配置"])
app.include_router(cot_filter.router, prefix="/api/cot-filter", tags=["COT过滤"])
app.include_router(dataset_split.router, prefix="/api/dataset-split", tags=["数据集切分"])
app.include_router(dataset_assessment.router, prefix="/api/dataset-assessment", tags=["评分标准生成"])


@app.get("/")
async def root():
    return {"message": "QA Studio API is running", "version": "0.1.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}