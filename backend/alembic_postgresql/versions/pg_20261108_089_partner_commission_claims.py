"""Partner-owned commission claims in the active PostgreSQL migration chain."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261108_089_partner_claims"
down_revision = "pg_20261107_088_calendar_sync"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "partner_commission_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("portal_user_id", sa.Integer(), sa.ForeignKey("portal_users.id"), nullable=False),
        sa.Column("reference", sa.String(180), nullable=False),
        sa.Column("amount", sa.String(40), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_partner_commission_claims_organization_id", "partner_commission_claims", ["organization_id"])
    op.create_index("ix_partner_commission_claims_portal_user_id", "partner_commission_claims", ["portal_user_id"])


def downgrade():
    op.drop_table("partner_commission_claims")
