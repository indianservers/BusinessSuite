"""Shared additive migration for both supported database migration tracks."""

import sqlalchemy as sa


def upgrade(op):
    if "power_native_deliveries" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "power_native_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column(
            "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "trigger_id",
            sa.Integer(),
            sa.ForeignKey("power_automation_triggers.id"),
            nullable=False,
        ),
        sa.Column("epoch", sa.String(36), nullable=False),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("encrypted_payload", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "trigger_id", "epoch", "message_id", name="uq_power_native_delivery"
        ),
    )
    op.create_index(
        "ix_power_native_delivery_due",
        "power_native_deliveries",
        ["trigger_id", "status", "next_at"],
    )


def downgrade(op):
    op.drop_index("ix_power_native_delivery_due", table_name="power_native_deliveries")
    op.drop_table("power_native_deliveries")
