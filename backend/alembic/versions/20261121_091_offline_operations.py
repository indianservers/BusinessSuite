"""Record committed offline writes for safe replay."""
from alembic import op
import sqlalchemy as sa

revision = '20261121_091_offline_operations'
down_revision = '20261121_090_batch_prices'
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "offline_operation_receipts",
        sa.Column("actor_id", sa.Integer(), primary_key=True),
        sa.Column("operation_id", sa.String(36), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON()),
    )


def downgrade():
    op.drop_table("offline_operation_receipts")
