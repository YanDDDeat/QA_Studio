"""QA Studio Backend - FastAPI Application"""

import asyncio
import bcrypt

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
)
from app.database import engine, Base, SessionLocal
from app.models import User, Dataset, File, Prompt, Task, TaskLog, LLMConfig
from app.config import settings
from app.services.llm_service import call_llm, LLMCallError

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

    # LLM connection test
    print(f"[Startup] LLM provider: {settings.LLM_PROVIDER}")
    print(f"[Startup] LLM base_url: {settings.effective_llm_base_url}")
    print(f"[Startup] LLM model: {settings.effective_llm_model}")
    print("[Startup] Testing LLM connection...")
    try:
        result = await call_llm(
            prompt="你好，请用一句话回复确认连接正常。",
            model=settings.effective_llm_model,
            api_key=settings.effective_llm_api_key,
            base_url=settings.effective_llm_base_url,
            temperature=0.1,
            max_tokens=64,
            timeout=30.0,
        )
        print(f"[Startup] LLM test OK — response: {result.strip()[:100]}")
    except LLMCallError as e:
        print(f"[Startup] LLM test FAILED: {e}")
    except Exception as e:
        print(f"[Startup] LLM test FAILED (unexpected): {e}")

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


@app.get("/")
async def root():
    return {"message": "QA Studio API is running", "version": "0.1.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}