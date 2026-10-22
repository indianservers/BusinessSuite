"""Migration-critical local/remote connection and schema completeness checks."""
import json
from importlib import import_module
from pathlib import Path
import pytest
from sqlalchemy.engine import make_url
from app.core.config import Settings
from app.db.base import Base
from app.module_registry import APP_MODULES


def test_discrete_postgres_credentials_preserve_reserved_characters():
    settings = Settings(_env_file=None, DATABASE_URL=None, POSTGRES_PASSWORD="p@ss:/?#%word", POSTGRES_DB="suite_test")
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss:/?#%word"
    assert url.database == "suite_test"


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://", "postgresql+psycopg://"])
def test_remote_provider_urls_use_psycopg_and_preserve_tls(prefix):
    settings = Settings(_env_file=None, DATABASE_URL=prefix + "app:secret@remote.example:5432/suite?sslmode=verify-full")
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "verify-full"
    assert "ssl" not in settings.SQLALCHEMY_CONNECT_ARGS


def test_retired_database_driver_is_rejected():
    settings = Settings(_env_file=None, DATABASE_URL="mysql+pymysql://localhost/retired")
    with pytest.raises(ValueError, match="must use PostgreSQL"):
        _ = settings.SQLALCHEMY_DATABASE_URI


def test_baseline_covers_every_module_and_historical_schema():
    for module in APP_MODULES.values():
        for name in module.model_modules:
            import_module(name)
    root = Path(__file__).resolve().parents[1]
    coverage = json.loads((root / "alembic_postgresql/schema/coverage.json").read_text())
    assert set(Base.metadata.tables).issubset(coverage["target_tables"])
    for table in Base.metadata.tables.values():
        assert {c.name for c in table.columns}.issubset(coverage["columns"][table.name])
    assert set(coverage["source_tables"]) - {"alembic_version"} == set(coverage["target_tables"])
    assert {"onboarding_tasks", "onboarding_task_completions"}.issubset(coverage["target_tables"])
