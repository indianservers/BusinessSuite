"""Local-only checks for independently configured customer installations."""
from urllib.parse import urlsplit, parse_qs
import pytest
from fastapi import HTTPException
from tests.test_serverless_configuration import cloud_settings
from app.core import security, storage


def installation(name, **changes):
    return cloud_settings(
        BACKEND_PUBLIC_URL=f"https://app.{name}.example",
        FRONTEND_PUBLIC_URL=f"https://app.{name}.example",
        BACKEND_CORS_ORIGINS=[f"https://app.{name}.example",f"https://interns-hub.{name}.example"],
        SECRET_KEY=(name+"-access-")*8,
        REFRESH_SECRET_KEY=(name+"-refresh-")*8,
        CRON_SECRET=(name+"-cron-")*8,
        SECRET_KEY_PREVIOUS="", REFRESH_SECRET_KEY_PREVIOUS="",
        DATABASE_URL=f"postgresql://test:test@{name}-pooler.neon.tech/suite?sslmode=require",
        S3_BUCKET=f"{name}-private", **changes)


@pytest.mark.parametrize("name",["customer-a","customer-b"])
def test_independent_domains_and_databases_are_configurable(name):
    config=installation(name)
    assert config.BACKEND_PUBLIC_URL==f"https://app.{name}.example"
    assert f"https://interns-hub.{name}.example" in config.BACKEND_CORS_ORIGINS
    assert name in config.SQLALCHEMY_DATABASE_URI


def test_another_installation_cannot_use_access_or_refresh_tokens(monkeypatch):
    first,second=installation("customer-a"),installation("customer-b")
    monkeypatch.setattr(security,"settings",first)
    access=security.create_access_token(1,session_id=1)
    refresh=security.create_refresh_token(1,session_id=1)
    assert security.verify_access_token(access)
    assert security.verify_refresh_token(refresh)
    monkeypatch.setattr(security,"settings",second)
    assert security.verify_access_token(access) is None
    assert security.verify_refresh_token(refresh) is None


def test_private_file_links_use_own_domain_and_reject_other_installation(monkeypatch,tmp_path):
    first=installation("customer-a",UPLOAD_DIR=str(tmp_path))
    second=installation("customer-b",UPLOAD_DIR=str(tmp_path))
    monkeypatch.setattr(storage,"settings",first)
    link=storage.signed_file_url(str(tmp_path/"branding"/"logo.png"))
    assert urlsplit(link).netloc=="app.customer-a.example"
    token=parse_qs(urlsplit(link).query)["token"][0]
    assert storage.blob_token_path(token).endswith("logo.png")
    monkeypatch.setattr(storage,"settings",second)
    with pytest.raises(HTTPException):
        storage.blob_token_path(token)
