import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Financial Health Assessment API"
    env: str = os.getenv("ENV", "development")

    # For local development we default to SQLite so you can run the
    # app without having PostgreSQL installed. For production /
    # deployment, override this with a PostgreSQL URL via DATABASE_URL.
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./financial_health.db")

    secret_key: str = os.getenv("SECRET_KEY", "CHANGE_ME")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    encryption_key: str = os.getenv("ENCRYPTION_KEY", "")  # Fernet key (base64)

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


@lru_cache
def get_settings() -> Settings:
    return Settings()

