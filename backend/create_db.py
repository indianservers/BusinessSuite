"""Provision PostgreSQL and migrate all suite tables without importing data."""
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.migrations import upgrade_schema


def create_database():
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("Database provisioning requires PostgreSQL")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT",
                          connect_args=settings.SQLALCHEMY_CONNECT_ARGS)
    try:
        with admin.connect() as connection:
            exists = connection.execute(text("SELECT 1 FROM pg_database WHERE datname=:name"),
                                        {"name": url.database}).scalar()
            if not exists:
                name = admin.dialect.identifier_preparer.quote_identifier(url.database)
                connection.exec_driver_sql(f"CREATE DATABASE {name} ENCODING 'UTF8'")
    finally:
        admin.dispose()


if __name__ == "__main__":
    create_database()
    upgrade_schema()
    print("PostgreSQL database and all suite tables ready; no source data copied.")
