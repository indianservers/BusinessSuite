"""Deduplicate repeated contact transaction submissions."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261103_075_txn_requests"
down_revision = "pg_20261103_074_financial"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    table = "crm_contact_financial_transactions"
    if "request_id" not in {column["name"] for column in inspector.get_columns(table)}:
        op.add_column(table, sa.Column("request_id", sa.String(36)))
    if "uq_contact_transaction_request" not in {constraint["name"] for constraint in inspector.get_unique_constraints(table)}:
        op.create_unique_constraint("uq_contact_transaction_request", table, ["organization_id", "request_id"])


def downgrade():
    raise RuntimeError("Preserve transaction submission history; use a reviewed restore")
