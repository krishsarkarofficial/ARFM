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
    ENVIRONMENT: str = "development"  # "development" or "production"

    # OAuth redirect URI (constructed dynamically but can be overridden)
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/auth/callback"

    # Google OAuth scopes
    GOOGLE_SCOPES: list[str] = [
        "openid",
        "email",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def allowed_origins(self) -> list[str]:
        """Return CORS origins — always include frontend URL, plus localhost for dev."""
        origins = [self.FRONTEND_URL]
        if not self.is_production:
            origins.extend([
                "http://localhost:5173",
                "http://localhost:3000",
                "http://127.0.0.1:5173",
            ])
        return list(set(origins))

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
