import pytest
import os
import sys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# WARNING: Tests run against SQLite in-memory.
# MySQL-specific behaviors NOT tested here:
#   - JSON_EXTRACT / JSON column path queries
#   - CHECK constraints (e.g. accrual_frequency, payroll status)
#   - ENUM column enforcement
#   - Full-text indexes
# Run integration tests against a real MySQL instance before releasing
# any migration or CRUD change that uses these features.

def _make_unraisablehook(default_hook):
    def _suppress_python314_gzip_teardown_warning(unraisable):
        if isinstance(unraisable.exc_value, ValueError) and "I/O operation on closed file" in str(unraisable.exc_value):
            return
        default_hook(unraisable)

    return _suppress_python314_gzip_teardown_warning


sys.unraisablehook = _make_unraisablehook(sys.unraisablehook)

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MYSQL_PASSWORD", "")
os.environ.setdefault("INSTALLED_APPS", "hrms,crm,project_management,srm,fam")

from app.main import app
from app.db.base_class import Base
from app.db.base import Base as AllModels  # noqa: F401 - ensure all models imported
from app.core.deps import get_db
from app.core.security import get_password_hash
from app.models.user import User, Role

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def superuser_token(client, db):
    role = Role(name="super_admin", description="Super Admin", is_system=True)
    db.add(role)
    db.flush()

    user = User(
        email="testadmin@test.com",
        hashed_password=get_password_hash("Admin@123456"),
        is_active=True,
        is_superuser=True,
        role_id=role.id,
    )
    db.add(user)
    db.commit()

    response = client.post("/api/v1/auth/login", json={
        "email": "testadmin@test.com",
        "password": "Admin@123456"
    })
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def superuser_headers(superuser_token):
    return {"Authorization": f"Bearer {superuser_token}"}
