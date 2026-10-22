"""PostgreSQL migrations; schema setup never depends on enabled UI modules."""
from logging.config import fileConfig
from importlib import import_module
import json
from pathlib import Path
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.core.config import settings
from app.db.base import Base
from app.module_registry import APP_MODULES

for module in APP_MODULES.values():
    for name in module.model_modules:
        import_module(name)

config = context.config
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI.replace("%", "%%"))
if config.config_file_name:
    fileConfig(config.config_file_name)

coverage = json.loads((Path(__file__).parent / "schema/coverage.json").read_text())
historical_tables = {i["table"] for i in coverage["preserved_legacy_fields"] if i.get("whole_table")}
historical_columns = {(i["table"], i["column"]) for i in coverage["preserved_legacy_fields"] if "column" in i}


def include_object(obj, name, type_, reflected, compare_to):
    if reflected and compare_to is None:
        if type_ == "table" and name in historical_tables:
            return False
        if type_ == "column" and (obj.table.name, name) in historical_columns:
            return False
    return True

if context.is_offline_mode():
    context.configure(url=settings.SQLALCHEMY_DATABASE_URI, target_metadata=Base.metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"}, include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()
else:
    connectable = engine_from_config(config.get_section(config.config_ini_section),
                                    prefix="sqlalchemy.", poolclass=pool.NullPool,
                                    connect_args=settings.SQLALCHEMY_CONNECT_ARGS)
    with connectable.connect() as connection:
        if connection.dialect.name != "postgresql":
            raise RuntimeError("Suite schema migrations require PostgreSQL")
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()
