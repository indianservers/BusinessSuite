"""add enterprise IP access policies

Revision ID: 20260529_001
Revises: 20260512_045
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_001"
down_revision = "20260512_045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ip_access_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cidr", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ip_access_policies_id"), "ip_access_policies", ["id"], unique=False)
    op.create_index(op.f("ix_ip_access_policies_cidr"), "ip_access_policies", ["cidr"], unique=False)
    op.create_index(op.f("ix_ip_access_policies_action"), "ip_access_policies", ["action"], unique=False)
    op.create_index(op.f("ix_ip_access_policies_is_active"), "ip_access_policies", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ip_access_policies_is_active"), table_name="ip_access_policies")
    op.drop_index(op.f("ix_ip_access_policies_action"), table_name="ip_access_policies")
    op.drop_index(op.f("ix_ip_access_policies_cidr"), table_name="ip_access_policies")
    op.drop_index(op.f("ix_ip_access_policies_id"), table_name="ip_access_policies")
    op.drop_table("ip_access_policies")
