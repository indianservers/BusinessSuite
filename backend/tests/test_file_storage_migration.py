"""Storage migrations support both historical and current attachment schemas."""
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.services.file_storage_schema import upgrade


@pytest.mark.parametrize("has_locator", [False, True])
def test_storage_upgrade_preserves_existing_note_attachments(has_locator):
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            columns = [sa.Column("id", sa.Integer, primary_key=True)]
            if has_locator:
                columns.append(sa.Column("storage_path", sa.String(1000)))
            attachments = sa.Table("pms_private_note_attachments", sa.MetaData(), *columns)
            attachments.create(connection)
            row = {"id": 1}
            if has_locator:
                row["storage_path"] = "private/existing-note.pdf"
            connection.execute(attachments.insert().values(**row))

            upgrade(Operations(MigrationContext.configure(connection)))

            inspector = sa.inspect(connection)
            assert "storage_path" in {column["name"] for column in inspector.get_columns(attachments.name)}
            assert connection.exec_driver_sql("SELECT id, storage_path FROM pms_private_note_attachments").one() == (
                1, "private/existing-note.pdf" if has_locator else None
            )
            assert {"file_storage_connections", "file_storage_policies", "file_storage_oauth_states", "file_storage_objects"} <= set(inspector.get_table_names())
    finally:
        engine.dispose()
