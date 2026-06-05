from typing import Any, List, Optional, Union
from pydantic import AnyHttpUrl, EmailStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import secrets
from urllib.parse import quote_plus


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)

    PROJECT_NAME: str = "Business Suite"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    INSTALLED_APPS: Union[List[str], str] = ["hrms", "crm", "project_management", "srm"]

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(48)
    SECRET_KEY_PREVIOUS: Optional[str] = None
    REFRESH_SECRET_KEY: str = secrets.token_urlsafe(48)
    REFRESH_SECRET_KEY_PREVIOUS: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: Optional[str] = None
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_SERVER: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "ai_hrms"
    MYSQL_SSL_CA: Optional[str] = None
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 3600

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        user = quote_plus(self.MYSQL_USER)
        password = quote_plus(self.MYSQL_PASSWORD)
        database = quote_plus(self.MYSQL_DB)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.MYSQL_SERVER}:{self.MYSQL_PORT}/{database}"
            f"?charset=utf8mb4"
        )

    @property
    def SQLALCHEMY_CONNECT_ARGS(self) -> dict[str, Any]:
        if self.MYSQL_SSL_CA:
            return {"ssl": {"ca": self.MYSQL_SSL_CA}}
        return {}

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_TIMEZONE: str = "Asia/Kolkata"

    # Email
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@aihrms.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    # CRM messaging
    CRM_MESSAGE_PROVIDER: str = "mock"
    CRM_SMS_PROVIDER: str = "mock"
    CRM_WHATSAPP_PROVIDER: str = "mock"
    CRM_SMS_API_KEY: str = ""
    CRM_SMS_API_SECRET: str = ""
    CRM_SMS_SENDER_ID: str = ""
    CRM_WHATSAPP_ACCESS_TOKEN: str = ""
    CRM_WHATSAPP_PHONE_NUMBER_ID: str = ""
    CRM_WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    CRM_GOOGLE_CALENDAR_CLIENT_ID: str = ""
    CRM_GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    CRM_OUTLOOK_CALENDAR_CLIENT_ID: str = ""
    CRM_OUTLOOK_CALENDAR_CLIENT_SECRET: str = ""
    CRM_CALENDAR_WEBHOOK_SECRET: str = ""
    CRM_WEBHOOK_BLOCK_PRIVATE_URLS: bool = True

    # File storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: str = "pdf,doc,docx,jpg,jpeg,png"

    # AI
    OPENAI_API_KEY: str = ""
    # Intentional GPT-4.1 family default. Keep this aligned with the models enabled on the deployed OpenAI account.
    OPENAI_MODEL: str = "gpt-4.1-mini"
    AI_AGENT_DEFAULT_TEMPERATURE: float = 0.2
    AI_AGENT_MAX_TOOL_CALLS: int = 8
    AI_AGENT_ENABLE_STREAMING: bool = False
    AI_AGENT_AUDIT_LOGGING: bool = True
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4573", "http://127.0.0.1:4573", "http://localhost:3000"]
    BACKEND_PUBLIC_URL: str = "http://localhost:8001"
    FRONTEND_PUBLIC_URL: str = "http://localhost:5173"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [i.strip() for i in v.split(",")]
        return v

    @field_validator("INSTALLED_APPS", mode="before")
    @classmethod
    def assemble_installed_apps(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_cors(self):
        if self.ENVIRONMENT.lower() == "production" and "*" in self.BACKEND_CORS_ORIGINS:
            raise ValueError("BACKEND_CORS_ORIGINS must list explicit origins when ENVIRONMENT=production")
        return self

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on", "debug", "development", "dev"}
        return bool(v)

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]


settings = Settings()
