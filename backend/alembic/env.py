import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, inspect, pool, text
from alembic import context
from alembic.operations import Operations
from alembic.script import ScriptDirectory

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _install_idempotent_operation_guards(connection) -> None:
    """Guard historical migrations against the current-model bootstrap schema.

    The first project migration creates tables from ``Base.metadata``. On a
    clean database that means later historical migrations can encounter objects
    that already exist in the current model snapshot. These guards keep a clean
    install moving while preserving normal migration behavior on older databases
    where the object is genuinely missing.
    """

    if getattr(Operations, "_business_suite_idempotent_guards", False):
        return

    original_add_column = Operations.add_column
    original_create_table = Operations.create_table
    original_create_index = Operations.create_index
    original_create_foreign_key = Operations.create_foreign_key
    original_create_unique_constraint = Operations.create_unique_constraint
    original_create_check_constraint = Operations.create_check_constraint
    original_drop_column = Operations.drop_column
    original_drop_table = Operations.drop_table
    original_drop_index = Operations.drop_index
    original_drop_constraint = Operations.drop_constraint

    def _inspector():
        return inspect(connection)

    def _table_exists(table_name, schema=None) -> bool:
        return table_name in _inspector().get_table_names(schema=schema)

    def _column_exists(table_name, column_name, schema=None) -> bool:
        if not _table_exists(table_name, schema=schema):
            return False
        return column_name in {column["name"] for column in _inspector().get_columns(table_name, schema=schema)}

    def _index_exists(table_name, index_name, schema=None) -> bool:
        if not index_name or not _table_exists(table_name, schema=schema):
            return False
        indexes = {index["name"] for index in _inspector().get_indexes(table_name, schema=schema)}
        return index_name in indexes

    def _foreign_key_exists(table_name, constraint_name, schema=None) -> bool:
        if not constraint_name or not _table_exists(table_name, schema=schema):
            return False
        foreign_keys = {fk.get("name") for fk in _inspector().get_foreign_keys(table_name, schema=schema)}
        return constraint_name in foreign_keys

    def _unique_constraint_exists(table_name, constraint_name, schema=None) -> bool:
        if not constraint_name or not _table_exists(table_name, schema=schema):
            return False
        constraints = {constraint.get("name") for constraint in _inspector().get_unique_constraints(table_name, schema=schema)}
        return constraint_name in constraints

    def _check_constraint_exists(table_name, constraint_name, schema=None) -> bool:
        if not constraint_name or not _table_exists(table_name, schema=schema):
            return False
        constraints = {constraint.get("name") for constraint in _inspector().get_check_constraints(table_name, schema=schema)}
        return constraint_name in constraints

    def guarded_add_column(self, table_name, column, *args, **kwargs):
        schema = kwargs.get("schema")
        if _column_exists(table_name, column.name, schema=schema):
            return None
        return original_add_column(self, table_name, column, *args, **kwargs)

    def guarded_create_table(self, table_name, *columns, **kwargs):
        schema = kwargs.get("schema")
        if _table_exists(table_name, schema=schema):
            return None
        return original_create_table(self, table_name, *columns, **kwargs)

    def guarded_create_index(self, index_name, table_name, columns, *args, **kwargs):
        schema = kwargs.get("schema")
        if _index_exists(table_name, index_name, schema=schema):
            return None
        return original_create_index(self, index_name, table_name, columns, *args, **kwargs)

    def guarded_create_foreign_key(self, constraint_name, source_table, referent_table, local_cols, remote_cols, *args, **kwargs):
        source_schema = kwargs.get("source_schema")
        if _foreign_key_exists(source_table, constraint_name, schema=source_schema):
            return None
        if connection.dialect.name == "sqlite" and _table_exists(source_table, schema=source_schema):
            existing_columns = {column["name"] for column in _inspector().get_columns(source_table, schema=source_schema)}
            if set(local_cols).issubset(existing_columns):
                return None
        return original_create_foreign_key(
            self,
            constraint_name,
            source_table,
            referent_table,
            local_cols,
            remote_cols,
            *args,
            **kwargs,
        )

    def guarded_create_unique_constraint(self, constraint_name, table_name, columns, *args, **kwargs):
        schema = kwargs.get("schema")
        if _unique_constraint_exists(table_name, constraint_name, schema=schema):
            return None
        if connection.dialect.name == "sqlite" and _table_exists(table_name, schema=schema):
            existing_columns = {column["name"] for column in _inspector().get_columns(table_name, schema=schema)}
            if set(columns).issubset(existing_columns):
                return None
        return original_create_unique_constraint(self, constraint_name, table_name, columns, *args, **kwargs)

    def guarded_create_check_constraint(self, constraint_name, table_name, condition, *args, **kwargs):
        schema = kwargs.get("schema")
        if _check_constraint_exists(table_name, constraint_name, schema=schema):
            return None
        if connection.dialect.name == "sqlite" and _table_exists(table_name, schema=schema):
            return None
        return original_create_check_constraint(self, constraint_name, table_name, condition, *args, **kwargs)

    def guarded_drop_column(self, table_name, column_name, *args, **kwargs):
        schema = kwargs.get("schema")
        if not _column_exists(table_name, column_name, schema=schema):
            return None
        return original_drop_column(self, table_name, column_name, *args, **kwargs)

    def guarded_drop_table(self, table_name, *args, **kwargs):
        schema = kwargs.get("schema")
        if not _table_exists(table_name, schema=schema):
            return None
        return original_drop_table(self, table_name, *args, **kwargs)

    def guarded_drop_index(self, index_name, *args, **kwargs):
        table_name = kwargs.get("table_name")
        schema = kwargs.get("schema")
        if table_name and not _index_exists(table_name, index_name, schema=schema):
            return None
        return original_drop_index(self, index_name, *args, **kwargs)

    def guarded_drop_constraint(self, constraint_name, table_name, *args, **kwargs):
        schema = kwargs.get("schema")
        if connection.dialect.name == "sqlite" and _table_exists(table_name, schema=schema):
            return None
        return original_drop_constraint(self, constraint_name, table_name, *args, **kwargs)

    Operations.add_column = guarded_add_column
    Operations.create_table = guarded_create_table
    Operations.create_index = guarded_create_index
    Operations.create_foreign_key = guarded_create_foreign_key
    Operations.create_unique_constraint = guarded_create_unique_constraint
    Operations.create_check_constraint = guarded_create_check_constraint
    Operations.drop_column = guarded_drop_column
    Operations.drop_table = guarded_drop_table
    Operations.drop_index = guarded_drop_index
    Operations.drop_constraint = guarded_drop_constraint
    Operations._business_suite_idempotent_guards = True


def _ensure_wide_alembic_version_table(connection) -> None:
    """Allow descriptive revision ids longer than Alembic's default width."""

    inspector = inspect(connection)
    table_name = "alembic_version"
    if table_name not in inspector.get_table_names():
        if connection.dialect.name == "mysql":
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(255) NOT NULL PRIMARY KEY)"))
        else:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(255) NOT NULL PRIMARY KEY)"))
        return

    columns = {column["name"]: column for column in inspector.get_columns(table_name)}
    version_column = columns.get("version_num")
    if not version_column:
        return
    length = getattr(version_column.get("type"), "length", None)
    if length and length >= 255:
        return
    if connection.dialect.name == "mysql":
        connection.execute(text("ALTER TABLE alembic_version MODIFY version_num VARCHAR(255) NOT NULL"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _install_idempotent_operation_guards(connection)
        _ensure_wide_alembic_version_table(connection)
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        head_revision = ScriptDirectory.from_config(config).get_current_head()
        if head_revision:
            connection.execute(text("UPDATE alembic_version SET version_num = :head"), {"head": head_revision})
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
