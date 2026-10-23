import pytest
import os
import sys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import conv

# Unit tests default to SQLite. Set TEST_DATABASE_URL to a disposable
# PostgreSQL database (name must end in _test) for real integration coverage.
if os.environ.get("TEST_DATABASE_URL"):
    from sqlalchemy.engine import make_url
    test_url = make_url(os.environ["TEST_DATABASE_URL"])
    if test_url.get_backend_name() != "postgresql" or not (test_url.database or "").endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL must target a disposable PostgreSQL *_test database")
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

def _make_unraisablehook(default_hook):
    def _suppress_python314_gzip_teardown_warning(unraisable):
        if isinstance(unraisable.exc_value, ValueError) and "I/O operation on closed file" in str(unraisable.exc_value):
            return
        default_hook(unraisable)

    return _suppress_python314_gzip_teardown_warning


sys.unraisablehook = _make_unraisablehook(sys.unraisablehook)

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("INSTALLED_APPS", "hrms,crm,project_management,srm,fam")

from app.main import app
from app.db.base_class import Base
from app.db.base import Base as AllModels  # noqa: F401 - ensure all models imported
from app.core.deps import get_db
from app.core.security import get_password_hash, pwd_context
from app.models.user import User, Role

# Explicit CI opt-in: fixture hashes still use real bcrypt verification, with a
# cheap work factor. Production code never reads this testing-only switch.
if os.environ.get("FAST_TEST_PASSWORD_HASHES") == "1":
    pwd_context.update(bcrypt__rounds=4)

SQLALCHEMY_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    **({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
       if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {"connect_args": {"options": "-c timezone=UTC"}}),
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def db_engine():
    # Name every FK so PostgreSQL can also drop cyclic relationships at teardown.
    for table in Base.metadata.tables.values():
        for fk in table.foreign_key_constraints:
            if fk.name is None:
                element = next(iter(fk.elements))
                fk.name = conv("fk_" + table.name + "_" + element.parent.name + "_" + element.column.table.name)
    if engine.dialect.name == "postgresql":
        # Exercise the deployed migration chain, not a parallel ORM-only schema.
        from app.db.migrations import upgrade_schema
        upgrade_schema()
    else:
        Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        # Runtime startup provisions tenant 1 before module-gating middleware.
        # SQLite previously concealed this prerequisite by not enforcing FKs.
        from app.models.company import Company
        with engine.begin() as connection:
            connection.execute(Company.__table__.insert().values(id=1, name="Integration Test Company"))
            connection.exec_driver_sql("SELECT setval(pg_get_serial_sequence('companies','id'),1,true)")
    yield engine
    if engine.dialect.name == "postgresql":
        # The guarded runner recreates this dedicated DB on its next invocation.
        engine.dispose()
    else:
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
    previous_factory = getattr(app.state, "business_os_session_factory", None)
    previous_close = getattr(app.state, "business_os_close_session", None)
    # Keep middleware and handlers on the same isolated database for every dialect.
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        if previous_factory is None:
            if hasattr(app.state, "business_os_session_factory"):
                del app.state.business_os_session_factory
            if hasattr(app.state, "business_os_close_session"):
                del app.state.business_os_close_session
        else:
            app.state.business_os_session_factory = previous_factory
            app.state.business_os_close_session = previous_close


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
