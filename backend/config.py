"""
ARFM Backend — Configuration
Loads and validates environment variables via Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    FRONTEND_URL: str = "http://localhost:5173"
    SECRET_KEY: str = "change-me-to-a-random-secret-key"

    # OAuth redirect URI (constructed dynamically but can be overridden)
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/auth/callback"

    # Google OAuth scopes
    GOOGLE_SCOPES: list[str] = [
        "openid",
        "email",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
