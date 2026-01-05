import secrets

from pydantic import EmailStr, MongoDsn
from pydantic_settings import BaseSettings

from shortify.app.core.enums import LogLevel


class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "Shortify"
    API_V1_STR: str = "v1"
    DEBUG: bool = True
    CORS_ORIGINS: list[str] = []
    USE_CORRELATION_ID: bool = True

    # Logging
    LOG_LEVEL: str = LogLevel.INFO

    SENTRY_DSN: str | None = None

    # MongoDB
    MONGODB_URI: MongoDsn = "mongodb://db:27017/"  # type: ignore[assignment]
    MONGODB_DB_NAME: str = "shortify"

    # Superuser
    FIRST_SUPERUSER: str
    FIRST_SUPERUSER_EMAIL: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    # Authentication
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 1  # 60 minutes * 24 hours * 1 = 1 day
    SECRET_KEY: str = secrets.token_urlsafe(32)

    # URLs
    URL_IDENT_LENGTH: int = 7

    class Config:
        env_file = ".env"
        env_prefix = "SHORTIFY_"
        case_sensitive = True
        extra = "ignore"


# Missing named arguments are filled with environment variables
settings = Settings()  # type: ignore[call-arg]
