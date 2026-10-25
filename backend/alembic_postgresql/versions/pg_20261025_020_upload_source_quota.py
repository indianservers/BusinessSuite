"""Support upload quotas on databases provisioned before the source hash existed."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261025_020_upload_source'
down_revision='pg_20261025_019_document_tenants'
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind();table='intern_application_documents'
    if table not in sa.inspect(bind).get_table_names():return
    if 'uploader_hash' not in {column['name'] for column in sa.inspect(bind).get_columns(table)}:
        op.add_column(table,sa.Column('uploader_hash',sa.String(64),nullable=True))
    name='ix_intern_application_documents_uploader_hash'
    if name not in {index['name'] for index in sa.inspect(bind).get_indexes(table)}:
        op.create_index(name,table,['uploader_hash'])


def downgrade():
    pass  # Preserve quota history.
