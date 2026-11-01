"""Add service currency after the already-deployed deal workspace revision.

The earlier workspace revision has already run in production. A fresh revision
is required even when that earlier script also handles currency on fresh installs.
"""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261101_055_service_currency"
down_revision = "pg_20261101_054_deal_workspace"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("crm_services") and "currency" not in {
        column["name"] for column in inspector.get_columns("crm_services")
    }:
        op.add_column("crm_services", sa.Column("currency", sa.String(10), server_default="INR"))


def downgrade():
    # Retain commercial data and compatibility with deployments that added this
    # column in the prior revision; reverting application code does not need a drop.
    pass
