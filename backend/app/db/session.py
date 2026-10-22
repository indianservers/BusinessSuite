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
