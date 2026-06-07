"""crm phase 1 core foundation

Revision ID: 20260605_001
Revises: 20260604_002
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_001"
down_revision = "20260604_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("account_number", sa.String(length=60), nullable=True),
        sa.Column("account_name", sa.String(length=180), nullable=False),
        sa.Column("legal_name", sa.String(length=180), nullable=True),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("website", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("billing_address", sa.Text(), nullable=True),
        sa.Column("shipping_address", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True, server_default="India"),
        sa.Column("tax_registration_number", sa.String(length=80), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("account_status", sa.String(length=40), nullable=True, server_default="Active"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "account_number", name="uq_crm_account_org_number"),
    )
    for column in [
        "organization_id",
        "account_number",
        "account_name",
        "industry",
        "country",
        "tax_registration_number",
        "owner_id",
        "account_status",
    ]:
        op.create_index(f"ix_crm_accounts_{column}", "crm_accounts", [column])

    op.create_table(
        "crm_timeline_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("record_type", sa.String(length=40), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    for column in ["organization_id", "record_type", "record_id", "event_type", "actor_user_id", "occurred_at"]:
        op.create_index(f"ix_crm_timeline_events_{column}", "crm_timeline_events", [column])

    op.create_table(
        "crm_lead_conversion_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("converted_account_id", sa.Integer(), sa.ForeignKey("crm_companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("converted_contact_id", sa.Integer(), sa.ForeignKey("crm_contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("converted_deal_id", sa.Integer(), sa.ForeignKey("crm_deals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("converted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversion_status", sa.String(length=40), nullable=True, server_default="completed"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    for column in [
        "organization_id",
        "lead_id",
        "converted_account_id",
        "converted_contact_id",
        "converted_deal_id",
        "converted_by_user_id",
        "conversion_status",
        "converted_at",
    ]:
        op.create_index(f"ix_crm_lead_conversion_logs_{column}", "crm_lead_conversion_logs", [column])


def downgrade() -> None:
    op.drop_table("crm_lead_conversion_logs")
    op.drop_table("crm_timeline_events")
    op.drop_table("crm_accounts")
