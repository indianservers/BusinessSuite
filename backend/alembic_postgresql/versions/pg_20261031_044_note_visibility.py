"""Explicit opt-in note audiences; all existing notes remain private."""
from alembic import op
import sqlalchemy as sa
revision = "pg_20261031_044_note_visibility"
down_revision = "pg_20261031_043_pms_execution"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pms_private_notes", sa.Column("visibility_scope", sa.String(20), nullable=False, server_default="private"))


def downgrade():
    op.drop_column("pms_private_notes", "visibility_scope")
