"""Application settings loaded from .env"""

from typing import List

from pydantic_settings import BaseSettings


# LLM provider presets
LLM_PROVIDERS = {
    "dashscope": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-1744b0734d374ec7af64f5d87d8ba3e1",
        "default_model": "qwen3.6-plus",
        "models": ["qwen3.6-plus", "qwen3-max", "qwen3-turbo"],
    },
    "swust": {
        "base_url": "http://10.10.15.6:30080/api/v1",
        "api_key": "49c90220bda747f32725be07c8cdbd90",
        "default_model": "问题生成",
        "models": ["问题生成", "知识体系生成", "问题校验", "答案生成", "答案校验", "数据评估"],
    },
}


class Settings(BaseSettings):
    # Database
    DB_HOST: str = "117.72.57.125"
    DB_PORT: int = 13306
    DB_USER: str = "root"
    DB_PASSWORD: str = "swust"
    DB_NAME: str = "qa_gen"

    # LLM provider selection: "dashscope" or "swust"
    LLM_PROVIDER: str = "dashscope"

    # LLM overrides (optional, override provider preset if set)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""

    # Auth
    JWT_SECRET: str = "qa_studio_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 hours
    ADMIN_PASSWORD: str = "admin123"

    # Admin default account
    ADMIN_USERNAME: str = "admin"
    ADMIN_INIT_PASSWORD: str = "admin123"

    def _resolve_llm(self, field: str) -> str:
        """Resolve LLM config: explicit env override > provider preset."""
        explicit = getattr(self, f"_raw_{field}", None) or getattr(self, field, None)
        if explicit:
            return explicit
        preset = LLM_PROVIDERS.get(self.LLM_PROVIDER, {})
        return preset.get(field, "")

    @property
    def effective_llm_base_url(self) -> str:
        return self.LLM_BASE_URL or LLM_PROVIDERS[self.LLM_PROVIDER]["base_url"]

    @property
    def effective_llm_api_key(self) -> str:
        return self.LLM_API_KEY or LLM_PROVIDERS[self.LLM_PROVIDER]["api_key"]

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()