"""Application settings loaded from .env"""

import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings

# Resolve .env path: project root (one level up from backend/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


# LLM provider presets — API keys removed, must be set via .env
LLM_PROVIDERS = {
    "dashscope": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen3.6-plus",
        "models": ["qwen3.6-plus", "qwen3-max", "qwen3-turbo"],
    },
    "swust": {
        "base_url": "http://10.10.15.6:30080/api/v1",
        "default_model": "问题生成",
        "models": ["问题生成", "知识体系生成", "问题校验", "答案生成", "答案校验", "数据评估"],
    },
}


class Settings(BaseSettings):
    # Database — no defaults, must be set in .env
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # LLM provider selection: "dashscope" or "swust"
    LLM_PROVIDER: str = "dashscope"

    # LLM overrides — provider preset api_key removed, must set LLM_API_KEY in .env
    LLM_API_KEY: str
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""

    # Auth — must be set in .env, no hardcoded secrets
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 hours
    ADMIN_PASSWORD: str

    # Admin default account
    ADMIN_USERNAME: str = "admin"
    ADMIN_INIT_PASSWORD: str

    @property
    def effective_llm_base_url(self) -> str:
        return self.LLM_BASE_URL or LLM_PROVIDERS[self.LLM_PROVIDER]["base_url"]

    @property
    def effective_llm_api_key(self) -> str:
        return self.LLM_API_KEY

    @property
    def effective_llm_model(self) -> str:
        return self.LLM_MODEL or LLM_PROVIDERS[self.LLM_PROVIDER]["default_model"]

    @property
    def effective_llm_models(self) -> List[str]:
        return LLM_PROVIDERS[self.LLM_PROVIDER]["models"]

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


settings = Settings()