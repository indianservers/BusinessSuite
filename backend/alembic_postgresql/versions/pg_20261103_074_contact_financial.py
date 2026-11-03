"""Optional contact financial profiles and recorded payments."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261103_074_financial"
down_revision = "pg_20261103_073_master_data"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("crm_contact_financial_profiles",
        sa.Column("contact_id", sa.Integer, sa.ForeignKey("crm_contacts.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("organization_id", sa.Integer, nullable=False),
        sa.Column("gst_number", sa.String(15)),
        sa.Column("bank_accounts", sa.JSON, nullable=False),
        sa.Column("upi_ids", sa.JSON, nullable=False),
        sa.Column("version", sa.Integer, nullable=False))
    op.create_index("ix_crm_contact_financial_profiles_organization_id", "crm_contact_financial_profiles", ["organization_id"])
    op.create_table("crm_contact_financial_transactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("contact_id", sa.Integer, sa.ForeignKey("crm_contacts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("organization_id", sa.Integer, nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(120)),
        sa.Column("notes", sa.Text),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_contact_transaction_positive"))
    for column in ["contact_id", "organization_id"]:
        op.create_index(f"ix_crm_contact_financial_transactions_{column}", "crm_contact_financial_transactions", [column])


def downgrade():
    raise RuntimeError("Preserve recorded financial history; use a reviewed restore")
