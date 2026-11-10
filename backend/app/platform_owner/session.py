from functools import lru_cache
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


@lru_cache(maxsize=1)
def platform_factory():
    if not settings.PLATFORM_DATABASE_URL or len(settings.PLATFORM_SECRET_KEY) < 32:
        raise HTTPException(503, "Platform owner database is not configured")
    url = make_url(settings.PLATFORM_DATABASE_URL)
    business = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if (url.host, url.port, url.database) == (business.host, business.port, business.database):
        raise RuntimeError("Platform and customer databases must be different")
    if url.get_backend_name() not in {"postgresql", "postgres"}:
        raise RuntimeError("Platform owner storage requires PostgreSQL")
    engine = create_engine(url.set(drivername="postgresql+psycopg"), pool_pre_ping=True,
                           pool_size=3, max_overflow=3, connect_args={"connect_timeout": 10})
    return sessionmaker(bind=engine, autoflush=False)


def get_platform_db(request: Request):
    from app.core.route_policy import is_public
    if not is_public(request.url.path):
        from app.platform_owner.auth import validate_platform_bearer
        scheme, _, raw = request.headers.get("authorization", "").partition(" ")
        validate_platform_bearer(raw if scheme.lower() == "bearer" else "")
    with platform_factory()() as db:
        try:
            yield db
        except BaseException:
            db.rollback()
            raise
