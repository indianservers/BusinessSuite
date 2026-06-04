"""field audit privacy processors

Revision ID: 20260529_003
Revises: 20260529_002
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_003"
down_revision = "20260529_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "field_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=True),
        sa.Column("old_value_masked", sa.String(length=500), nullable=True),
        sa.Column("new_value_masked", sa.String(length=500), nullable=True),
        sa.Column("old_value_hash", sa.String(length=128), nullable=True),
        sa.Column("new_value_hash", sa.String(length=128), nullable=True),
        sa.Column("old_value_plaintext", sa.Text(), nullable=True),
        sa.Column("new_value_plaintext", sa.Text(), nullable=True),
        sa.Column("is_sensitive", sa.Boolean(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_field_audit_events_action"), "field_audit_events", ["action"])
    op.create_index(op.f("ix_field_audit_events_actor_user_id"), "field_audit_events", ["actor_user_id"])
    op.create_index(op.f("ix_field_audit_events_created_at"), "field_audit_events", ["created_at"])
    op.create_index(op.f("ix_field_audit_events_employee_id"), "field_audit_events", ["employee_id"])
    op.create_index(op.f("ix_field_audit_events_entity_id"), "field_audit_events", ["entity_id"])
    op.create_index(op.f("ix_field_audit_events_entity_type"), "field_audit_events", ["entity_type"])
    op.create_index(op.f("ix_field_audit_events_field_name"), "field_audit_events", ["field_name"])
    op.create_index(op.f("ix_field_audit_events_id"), "field_audit_events", ["id"])
    op.create_index(op.f("ix_field_audit_events_is_sensitive"), "field_audit_events", ["is_sensitive"])
    op.create_index(op.f("ix_field_audit_events_module"), "field_audit_events", ["module"])
    op.create_index(op.f("ix_field_audit_events_new_value_hash"), "field_audit_events", ["new_value_hash"])
    op.create_index(op.f("ix_field_audit_events_old_value_hash"), "field_audit_events", ["old_value_hash"])
    op.create_index("idx_field_audit_employee_field", "field_audit_events", ["employee_id", "field_name", "created_at"])
    op.create_index("idx_field_audit_hash", "field_audit_events", ["new_value_hash"])
    op.create_index("idx_field_audit_module_actor", "field_audit_events", ["module", "actor_user_id", "created_at"])

    op.add_column("data_privacy_requests", sa.Column("processing_result_json", sa.JSON(), nullable=True))
    op.add_column("data_privacy_requests", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("data_retention_policies", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("data_retention_policies", sa.Column("last_run_summary_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("data_retention_policies", "last_run_summary_json")
    op.drop_column("data_retention_policies", "last_run_at")
    op.drop_column("data_privacy_requests", "processed_at")
    op.drop_column("data_privacy_requests", "processing_result_json")
    op.drop_index("idx_field_audit_module_actor", table_name="field_audit_events")
    op.drop_index("idx_field_audit_hash", table_name="field_audit_events")
    op.drop_index("idx_field_audit_employee_field", table_name="field_audit_events")
    op.drop_table("field_audit_events")
