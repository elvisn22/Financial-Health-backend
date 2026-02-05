import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Financial Health Assessment API"
    env: str = os.getenv("ENV", "development")

    # Raw database URL from the environment.
    # For local development we default to SQLite so you can run the
    # app without having PostgreSQL installed. For production /
    # deployment, override this with a PostgreSQL URL via DATABASE_URL.
    database_url_raw: str = os.getenv("DATABASE_URL", "sqlite:///./financial_health.db")

    secret_key: str = os.getenv("SECRET_KEY", "CHANGE_ME")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    encryption_key: str = os.getenv("ENCRYPTION_KEY", "")  # Fernet key (base64)

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    @property
    def database_url(self) -> str:
        """
        Normalized database URL.

        - Converts legacy `postgres://` URLs to SQLAlchemy's preferred
          `postgresql+psycopg://` form for psycopg3.
        - Converts old `postgresql+psycopg2://` URLs to `postgresql+psycopg://`
          so we don't require the psycopg2 driver on Render.
        """
        url = self.database_url_raw

        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)

        if "postgresql+psycopg2" in url:
            url = url.replace("postgresql+psycopg2", "postgresql+psycopg")

        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()

