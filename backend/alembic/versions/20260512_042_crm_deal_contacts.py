"""add crm deal contacts

Revision ID: 20260512_042
Revises: 20260512_041
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_042"
down_revision = "20260512_041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_deal_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("crm_deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("crm_contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True, server_default="Stakeholder"),
        sa.Column("influence_level", sa.String(length=40), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("deal_id", "contact_id", name="uq_crm_deal_contact"),
    )
    op.create_index("ix_crm_deal_contacts_organization_id", "crm_deal_contacts", ["organization_id"])
    op.create_index("ix_crm_deal_contacts_deal_id", "crm_deal_contacts", ["deal_id"])
    op.create_index("ix_crm_deal_contacts_contact_id", "crm_deal_contacts", ["contact_id"])
    op.create_index("ix_crm_deal_contacts_role", "crm_deal_contacts", ["role"])
    op.create_index("ix_crm_deal_contacts_influence_level", "crm_deal_contacts", ["influence_level"])
    op.create_index("ix_crm_deal_contacts_is_primary", "crm_deal_contacts", ["is_primary"])

    op.execute(
        """
        INSERT INTO crm_deal_contacts (
            organization_id,
            deal_id,
            contact_id,
            role,
            is_primary,
            created_by_user_id,
            updated_by_user_id,
            created_at
        )
        SELECT
            organization_id,
            id,
            contact_id,
            'Primary',
            true,
            created_by_user_id,
            updated_by_user_id,
            COALESCE(created_at, CURRENT_TIMESTAMP)
        FROM crm_deals
        WHERE contact_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_table("crm_deal_contacts")
