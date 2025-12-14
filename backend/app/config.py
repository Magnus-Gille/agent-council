from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    lmstudio_base_url: str = ""
    database_url: str = "sqlite+aiosqlite:///./agent_council.db"
    host: str = "127.0.0.1"
    port: int = 8000
    max_concurrency: int = 6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
