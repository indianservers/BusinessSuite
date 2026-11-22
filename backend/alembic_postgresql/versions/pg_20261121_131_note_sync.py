"""Give personal notes stable identifiers across PostgreSQL installations."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261121_131_note_sync"
down_revision = "pg_20261121_130_offline_ops"
branch_labels = depends_on = None


def upgrade():
    op.add_column("pms_private_notes", sa.Column("sync_id", sa.String(36)))
    op.execute("UPDATE pms_private_notes SET sync_id = gen_random_uuid()::text")
    op.alter_column("pms_private_notes", "sync_id", nullable=False)
    op.create_unique_constraint("uq_pms_private_notes_sync_id", "pms_private_notes", ["sync_id"])


def downgrade():
    op.drop_constraint("uq_pms_private_notes_sync_id", "pms_private_notes", type_="unique")
    op.drop_column("pms_private_notes", "sync_id")
