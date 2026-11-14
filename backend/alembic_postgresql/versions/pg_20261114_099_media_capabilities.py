"""Default-disabled media capabilities on existing provider credentials."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261114_099_media'
down_revision='pg_20261112_098_event_delivery'
branch_labels=depends_on=None


def upgrade():
    bind=op.get_bind()
    if not sa.inspect(bind).has_table('ai_operator_providers'):return
    if 'media_settings' not in {c['name'] for c in sa.inspect(bind).get_columns('ai_operator_providers')}:
        op.add_column('ai_operator_providers',sa.Column('media_settings',sa.JSON(),nullable=False,server_default='{}'))


def downgrade():
    # Preserve explicit administrator choices across a code rollback.
    pass
