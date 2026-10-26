from typing import Any, List, Optional, Union
from pydantic import AnyHttpUrl, EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import secrets
import os
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, hide_input_in_errors=True)

    PROJECT_NAME: str = "Business Suite"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    FORMS_TURNSTILE_SITE_KEY: str = ""
    FORMS_TURNSTILE_SECRET_KEY: str = ""
    RECAPTCHA_SITE_KEY: str = ""
    RECAPTCHA_SECRET_KEY: str = Field(default="", repr=False)
    ENVIRONMENT: str = "development"
    INTERN_HUB_ORGANIZATION_ID: int = Field(1, ge=1)
    INTERN_SIGNUP_FIREBASE_PROJECT_ID: str = ""
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_WEB_CONFIG: dict[str, str] = Field(default_factory=dict)
    INSTALLED_APPS: Union[List[str], str] = ["hrms", "crm", "project_management", "srm", "fam"]

    SERVERLESS: bool = bool(os.environ.get("VERCEL"))
    BUSINESSSUITE_BACKUP_SCHEDULER: bool = False
    BUSINESSSUITE_BACKUP_DIR: str = ""
    CRON_SECRET: str = ""
    REALTIME_TRANSPORT: str = "database" if os.environ.get("VERCEL") else "websocket"

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
    POSTGRES_USER: str = "business_suite"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "business_suite"
    POSTGRES_SSLMODE: str = "prefer"
    POSTGRES_SSLROOTCERT: Optional[str] = None
    DATABASE_AUTO_MIGRATE: bool = not bool(os.environ.get("VERCEL"))
    SEED_DEMO_DATA: bool = False
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 3600

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            url = make_url(self.DATABASE_URL)
            if url.get_backend_name() == "postgresql" or url.drivername == "postgres":
                return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
            if url.get_backend_name() == "sqlite":
                return self.DATABASE_URL  # Isolated unit tests only.
            raise ValueError("DATABASE_URL must use PostgreSQL (postgresql+psycopg://)")
        return URL.create("postgresql+psycopg", username=self.POSTGRES_USER,
                          password=self.POSTGRES_PASSWORD, host=self.POSTGRES_SERVER,
                          port=self.POSTGRES_PORT, database=self.POSTGRES_DB,
                          query={"sslmode": self.POSTGRES_SSLMODE}).render_as_string(hide_password=False)

    @property
    def SQLALCHEMY_CONNECT_ARGS(self) -> dict[str, Any]:
        if make_url(self.SQLALCHEMY_DATABASE_URI).get_backend_name() == "postgresql":
            args = {"connect_timeout": 10, "prepare_threshold": None}
            if not self.SERVERLESS and "-pooler." not in (make_url(self.SQLALCHEMY_DATABASE_URI).host or ""):
                args["options"] = "-c timezone=UTC"
            if self.POSTGRES_SSLROOTCERT:
                args["sslrootcert"] = self.POSTGRES_SSLROOTCERT
            return args
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
    CRM_GOOGLE_CALENDAR_REDIRECT_URI: str = ""
    CRM_OUTLOOK_CALENDAR_CLIENT_ID: str = ""
    CRM_OUTLOOK_CALENDAR_CLIENT_SECRET: str = ""
    CRM_CALENDAR_WEBHOOK_SECRET: str = ""
    CRM_WEBHOOK_BLOCK_PRIVATE_URLS: bool = True
    COMMUNICATION_EMAIL_PROVIDER: str = ""
    COMMUNICATION_EMAIL_RATE_LIMIT_PER_REQUEST: int = 50

    # File storage
    UPLOAD_DIR: str = "/tmp/business-suite-uploads" if os.environ.get("VERCEL") else "./uploads"
    STORAGE_BACKEND: str = "s3" if os.environ.get("VERCEL") else "local"
    BLOB_READ_WRITE_TOKEN: str = ""
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: Optional[str] = None
    S3_REGION: str = "auto"
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_SIGNED_URL_SECONDS: int = Field(900, ge=60, le=3600)
    S3_PREFIX: str = "business-suite"
    MAX_UPLOAD_SIZE_MB: int = 3 if os.environ.get("VERCEL") else 10
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
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5178", "http://127.0.0.1:5178", "http://localhost:4573", "http://127.0.0.1:4573", "http://localhost:3000"]
    BACKEND_PUBLIC_URL: str = "http://localhost:1534"
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
        if self.ENVIRONMENT.lower() == "production":
            if self.SEED_DEMO_DATA:
                raise ValueError('Demo seeding must be disabled in production')
            if self.DEBUG:
                raise ValueError('DEBUG must be false in production')
            if self.ALGORITHM != 'HS256':
                raise ValueError('Application sessions require HS256')
            local_markers = ("localhost", "127.0.0.1", "0.0.0.0")
            origins = [str(origin) for origin in self.BACKEND_CORS_ORIGINS]
            if "*" in origins:
                raise ValueError("BACKEND_CORS_ORIGINS must list explicit origins when ENVIRONMENT=production")
            if any(any(marker in origin for marker in local_markers) for origin in origins):
                raise ValueError("BACKEND_CORS_ORIGINS cannot contain localhost/dev origins when ENVIRONMENT=production")
            if any(not origin.startswith('https://') for origin in origins):
                raise ValueError('Production CORS origins must use HTTPS')
            for name in ('SECRET_KEY','REFRESH_SECRET_KEY'):
                value=getattr(self,name)
                if name not in self.model_fields_set or len(value)<32 or '-----BEGIN' in value:
                    raise ValueError(f'{name} must be an explicitly configured random secret of at least 32 characters')
            public_urls = {
                "BACKEND_PUBLIC_URL": self.BACKEND_PUBLIC_URL,
                "FRONTEND_PUBLIC_URL": self.FRONTEND_PUBLIC_URL,
            }
            for name, value in public_urls.items():
                if not str(value).startswith('https://'):
                    raise ValueError(f'{name} must use HTTPS in production')
                if any(marker in str(value) for marker in local_markers):
                    raise ValueError(f"{name} must be set to a production URL when ENVIRONMENT=production")
        if self.SERVERLESS:
            for name in ["SECRET_KEY", "REFRESH_SECRET_KEY"]:
                if name not in self.model_fields_set or len(getattr(self, name)) < 32:
                    raise ValueError(f"{name} must be explicitly configured with at least 32 characters for serverless")
            if not self.DATABASE_URL or make_url(self.DATABASE_URL).get_backend_name() not in {"postgresql", "postgres"}:
                raise ValueError("Serverless requires an explicit PostgreSQL DATABASE_URL")
            if make_url(self.DATABASE_URL).query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("Serverless DATABASE_URL must require TLS with sslmode=require or stronger")
            if self.REALTIME_TRANSPORT != "database":
                raise ValueError("Serverless requires REALTIME_TRANSPORT=database")
            if self.MAX_UPLOAD_SIZE_MB > 3:
                raise ValueError("Serverless multipart uploads support at most 3 MB")
            if self.DATABASE_AUTO_MIGRATE or self.SEED_DEMO_DATA:
                raise ValueError("Serverless requires DATABASE_AUTO_MIGRATE=false and SEED_DEMO_DATA=false")
            if self.STORAGE_BACKEND == "vercel_blob":
                if not self.BLOB_READ_WRITE_TOKEN:
                    raise ValueError("Vercel Blob requires BLOB_READ_WRITE_TOKEN")
            elif self.STORAGE_BACKEND != "s3" or not all([self.S3_BUCKET, self.S3_ACCESS_KEY_ID, self.S3_SECRET_ACCESS_KEY]):
                raise ValueError("Serverless requires configured private S3-compatible storage or Vercel Blob")
            if len(self.CRON_SECRET) < 32:
                raise ValueError("Serverless requires a CRON_SECRET of at least 32 characters")
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
