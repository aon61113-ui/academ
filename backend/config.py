"""Конфигурация приложения. Все настройки читаются из .env (Pydantic Settings)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "academy"
    DB_PASSWORD: str = "academy_pass"
    DB_NAME: str = "digital_academy"

    # JWT / Auth
    JWT_SECRET: str = "CHANGE_ME"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 14

    # URLs / CORS
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    COOKIE_SECURE: bool = False

    # Email
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@digital-academy.kz"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # reCAPTCHA
    RECAPTCHA_ENABLED: bool = False
    RECAPTCHA_SECRET: str = ""

    # Rate limiting
    OTP_MAX_PER_HOUR: int = 5
    LOGIN_MAX_PER_15MIN: int = 10

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
