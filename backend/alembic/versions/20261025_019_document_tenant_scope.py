"""Partition legacy document templates and company policies by tenant."""
from alembic import op
import sqlalchemy as sa
revision='20261025_019_document_tenants'
down_revision='20261025_018_shared_batches'
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind()
    for table in ('document_templates','company_policies'):
        if 'organization_id' not in {c['name'] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table,sa.Column('organization_id',sa.Integer(),nullable=False,server_default='1'))
        name='ix_'+table+'_organization_id'
        if name not in {i['name'] for i in sa.inspect(bind).get_indexes(table)}:
            op.create_index(name,table,['organization_id'])


def downgrade():
    pass  # Preserve tenant partition information; restore the reviewed backup to roll back.
