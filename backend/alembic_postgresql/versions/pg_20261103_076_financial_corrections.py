"""Versioned financial corrections and retained void history."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261103_076_fin_correction"
down_revision = "pg_20261103_075_txn_requests"
branch_labels = None
depends_on = None


def upgrade():
    table = "crm_contact_financial_transactions"
    op.add_column(table, sa.Column("version", sa.Integer, nullable=False, server_default="1"))
    op.add_column(table, sa.Column("status", sa.String(15), nullable=False, server_default="recorded"))
    op.add_column(table, sa.Column("void_reason", sa.String(500)))


def downgrade():
    raise RuntimeError("Preserve financial correction history; use a reviewed restore")
