"""Module roles per branch."""
revision = "pg_20261102_061_branch_roles"
down_revision = "pg_20261102_060_branch_sharing"
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    if 'module_grants' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('suite_branch_grants')}:
        op.add_column('suite_branch_grants', sa.Column('module_grants', sa.JSON(), nullable=True))

def downgrade():
    raise RuntimeError('Restore audited branch authorization backup instead')
