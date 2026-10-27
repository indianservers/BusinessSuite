from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    **({"poolclass": NullPool} if settings.SERVERLESS else {
        "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
        "pool_size": settings.DB_POOL_SIZE, "max_overflow": settings.DB_MAX_OVERFLOW,
    }),
    connect_args=settings.SQLALCHEMY_CONNECT_ARGS,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# PostgreSQL enforces the DB deadline even if a synchronous HTTP worker is cancelled.
from sqlalchemy import event, text
from sqlalchemy.orm import Session


@event.listens_for(Session, "after_begin")
def request_statement_deadline(session, transaction, connection):
    if session.info.get("security_store_timeout") and connection.dialect.name == "postgresql":
        connection.execute(text("SELECT set_config('statement_timeout', '2000', true)"))
        connection.execute(text("SELECT set_config('lock_timeout', '1000', true)"))
    elif session.info.get("security_http_timeout") and connection.dialect.name == "postgresql":
        connection.execute(text("SELECT set_config('statement_timeout', :value, true)"), {"value": str(settings.SECURITY_REQUEST_TIMEOUT_SECONDS * 1000)})
        connection.execute(text("SELECT set_config('lock_timeout', '5000', true)"))
