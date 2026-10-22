import pytest
from app.core.config import Settings


def cloud_settings(**changes):
    values = dict(SERVERLESS=True, ENVIRONMENT="production", DEBUG=False,
        DATABASE_AUTO_MIGRATE=False, SEED_DEMO_DATA=False, MAX_UPLOAD_SIZE_MB=3,
        DATABASE_URL="postgresql://test:test@fake-pooler.neon.tech/db?sslmode=require",
        SECRET_KEY="a" * 40, REFRESH_SECRET_KEY="b" * 40, CRON_SECRET="c" * 40,
        REALTIME_TRANSPORT="database", STORAGE_BACKEND="s3", S3_BUCKET="test",
        S3_ACCESS_KEY_ID="test", S3_SECRET_ACCESS_KEY="test",
        BACKEND_PUBLIC_URL="https://api.example.com", FRONTEND_PUBLIC_URL="https://app.example.com",
        BACKEND_CORS_ORIGINS=["https://app.example.com"])
    values.update(changes)
    return Settings(_env_file=None, **values)


def test_complete_cloud_settings_accept_neon_and_private_storage():
    config = cloud_settings()
    assert "options" not in config.SQLALCHEMY_CONNECT_ARGS
    assert config.SQLALCHEMY_CONNECT_ARGS["prepare_threshold"] is None


@pytest.mark.parametrize("changes", [
    {"DATABASE_URL": "postgresql://test:test@fake.neon.tech/db?sslmode=disable"},
    {"DATABASE_AUTO_MIGRATE": True}, {"SEED_DEMO_DATA": True},
    {"REALTIME_TRANSPORT": "websocket"}, {"MAX_UPLOAD_SIZE_MB": 10},
    {"STORAGE_BACKEND": "local"}, {"CRON_SECRET": "short"},
])
def test_unsafe_cloud_settings_fail_startup(changes):
    with pytest.raises(ValueError):
        cloud_settings(**changes)
