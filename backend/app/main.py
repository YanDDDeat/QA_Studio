"""QA Studio Backend - FastAPI Application"""

import asyncio
import bcrypt
import logging
import time
import traceback
from logging.handlers import TimedRotatingFileHandler
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Logging configuration: error/info split files (daily rotation) + console
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_log_format = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class _LevelFilter(logging.Filter):
    """Only allow log records within a level range [low, high)."""
    def __init__(self, low, high):
        super().__init__()
        self.low = low
        self.high = high

    def filter(self, record):
        return self.low <= record.levelno < self.high


# INFO file: DEBUG ~ WARNING (everything below ERROR)
_info_handler = TimedRotatingFileHandler(
    os.path.join(LOG_DIR, "info.log"),
    when="midnight",
    backupCount=90,
    encoding="utf-8",
)
_info_handler.setFormatter(_log_format)
_info_handler.setLevel(logging.DEBUG)
_info_handler.addFilter(_LevelFilter(logging.DEBUG, logging.ERROR))

# ERROR file: ERROR ~ CRITICAL only
_error_handler = TimedRotatingFileHandler(
    os.path.join(LOG_DIR, "error.log"),
    when="midnight",
    backupCount=90,
    encoding="utf-8",
)
_error_handler.setFormatter(_log_format)
_error_handler.setLevel(logging.ERROR)

# Console handler (INFO only, avoid flooding terminal)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_format)
_console_handler.setLevel(logging.INFO)

# Apply to qa_studio root logger
_root_logger = logging.getLogger("qa_studio")
_root_logger.setLevel(logging.DEBUG)
_root_logger.addHandler(_info_handler)
_root_logger.addHandler(_error_handler)
_root_logger.addHandler(_console_handler)

# Also route uvicorn logs to both files
for _uv_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    _uv_logger = logging.getLogger(_uv_name)
    _uv_logger.setLevel(logging.DEBUG)
    _uv_logger.addHandler(_info_handler)
    _uv_logger.addHandler(_error_handler)

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
    quality_check,
    generic_generate,
    text_preprocess,
    cot_hcot_pipeline,
)
from app.database import engine, Base, SessionLocal
from app.models import User, Dataset, File, Prompt, Task, TaskLog, LLMConfig
from app.models.models import TaskStatusEnum
from app.config import settings, LLM_PROVIDERS

app = FastAPI(
    title="QA Studio",
    description="QA数据生成与评估平台",
    version="0.1.0",
    redirect_slashes=False,
)


# ---------------------------------------------------------------------------
# Diagnostic logging: print every request enter/leave + traceback on exceptions
# directly to stdout (bypasses logger config so it always shows in `docker logs`).
# ---------------------------------------------------------------------------
@app.middleware("http")
async def _diag_log_requests(request: Request, call_next):
    start = time.time()
    client = request.client.host if request.client else "-"
    print(f"[REQ ] {request.method} {request.url.path} client={client}", flush=True)
    try:
        response = await call_next(request)
        elapsed_ms = (time.time() - start) * 1000
        print(
            f"[RESP] {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.0f}ms)",
            flush=True,
        )
        return response
    except Exception as exc:
        elapsed_ms = (time.time() - start) * 1000
        print(
            f"[ERR ] {request.method} {request.url.path} -> {type(exc).__name__}: {exc} ({elapsed_ms:.0f}ms)",
            flush=True,
        )
        traceback.print_exc()
        raise


@app.exception_handler(Exception)
async def _diag_unhandled_exception(request: Request, exc: Exception):
    print(
        f"[EXC ] {request.method} {request.url.path}: {type(exc).__name__}: {exc}",
        flush=True,
    )
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


@app.on_event("startup")
async def startup_event():
    """Create database tables, initialize admin account, and seed default LLM configs."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Auto-initialize admin account
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

        # Seed default LLM configs from .env provider presets
        for provider_name, preset in LLM_PROVIDERS.items():
            existing = db.query(LLMConfig).filter(LLMConfig.name == provider_name).first()
            if existing is None:
                api_key = settings.DASHSCOPE_API_KEY if provider_name == "dashscope" else settings.SWUST_API_KEY
                llm_cfg = LLMConfig(
                    user_id=None,  # global shared
                    name=provider_name,
                    base_url=preset["base_url"],
                    api_key=api_key,
                    models=preset["models"],
                    default_model=preset["default_model"],
                )
                db.add(llm_cfg)
                db.commit()
                print(f"[Startup] Default LLM config seeded: '{provider_name}'")
            else:
                print(f"[Startup] LLM config exists: '{provider_name}', skipping")
        # Clean up zombie tasks: running tasks from before restart → paused
        zombie_count = (
            db.query(Task)
            .filter(Task.status == TaskStatusEnum.RUNNING)
            .update({Task.status: TaskStatusEnum.PAUSED})
        )
        if zombie_count:
            db.commit()
            print(f"[Startup] {zombie_count} 个运行中的僵尸任务已自动改为暂停")

    except Exception as e:
        print(f"[Startup] Error initializing: {e}")
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
app.include_router(quality_check.router, prefix="/api/quality-check", tags=["质检"])
app.include_router(data_manage.router, prefix="/api/data-manage", tags=["数据管理"])
app.include_router(config_center.router, prefix="/api/config-center", tags=["配置中心"])
app.include_router(file_manage.router, prefix="/api/file-manage", tags=["文件管理"])
app.include_router(llm_config.router, prefix="/api/llm-configs", tags=["LLM配置"])
app.include_router(cot_filter.router, prefix="/api/cot-filter", tags=["COT过滤"])
app.include_router(dataset_split.router, prefix="/api/dataset-split", tags=["数据集切分"])
app.include_router(dataset_assessment.router, prefix="/api/dataset-assessment", tags=["评分标准生成"])
app.include_router(generic_generate.router, prefix="/api/generic-generate", tags=["通用生成"])
app.include_router(text_preprocess.router, prefix="/api/text-preprocess", tags=["文本预处理"])
app.include_router(cot_hcot_pipeline.router, prefix="/api/cothcot", tags=["CoT/H-CoT Pipeline"])


@app.get("/")
async def root():
    return {"message": "QA Studio API is running", "version": "0.1.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
