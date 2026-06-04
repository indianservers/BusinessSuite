"""workflow automation depth

Revision ID: 20260529_002
Revises: 20260529_001
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_002"
down_revision = "20260529_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow_step_definitions", sa.Column("skip_if_condition", sa.Text(), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("reminder_hours", sa.Integer(), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("timeout_action", sa.String(length=40), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("escalation_role", sa.String(length=120), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("action_type", sa.String(length=80), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("action_config", sa.JSON(), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("delegation_type", sa.String(length=40), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("delegation_value", sa.String(length=120), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("delegation_starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("delegation_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_step_definitions", sa.Column("metadata_json", sa.JSON(), nullable=True))

    op.add_column("workflow_tasks", sa.Column("original_assigned_to_user_id", sa.Integer(), nullable=True))
    op.add_column("workflow_tasks", sa.Column("original_assigned_role", sa.String(length=120), nullable=True))
    op.add_column("workflow_tasks", sa.Column("delegated_to_user_id", sa.Integer(), nullable=True))
    op.add_column("workflow_tasks", sa.Column("delegated_role", sa.String(length=120), nullable=True))
    op.add_column("workflow_tasks", sa.Column("delegation_reason", sa.Text(), nullable=True))
    op.add_column("workflow_tasks", sa.Column("delegation_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflow_tasks", sa.Column("delegation_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(None, "workflow_tasks", "users", ["original_assigned_to_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(None, "workflow_tasks", "users", ["delegated_to_user_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "workflow_delegations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("delegator_user_id", sa.Integer(), nullable=True),
        sa.Column("delegator_role", sa.String(length=120), nullable=True),
        sa.Column("delegate_to_user_id", sa.Integer(), nullable=True),
        sa.Column("delegate_to_role", sa.String(length=120), nullable=True),
        sa.Column("module", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["delegate_to_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegator_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_delegations_id"), "workflow_delegations", ["id"])
    op.create_index(op.f("ix_workflow_delegations_is_active"), "workflow_delegations", ["is_active"])
    op.create_index(op.f("ix_workflow_delegations_module"), "workflow_delegations", ["module"])

    op.create_table(
        "workflow_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("step_definition_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("before_status", sa.String(length=30), nullable=True),
        sa.Column("after_status", sa.String(length=30), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["instance_id"], ["workflow_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_definition_id"], ["workflow_step_definitions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["workflow_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_audit_events_event_type"), "workflow_audit_events", ["event_type"])
    op.create_index(op.f("ix_workflow_audit_events_id"), "workflow_audit_events", ["id"])
    op.create_index(op.f("ix_workflow_audit_events_instance_id"), "workflow_audit_events", ["instance_id"])
    op.create_index(op.f("ix_workflow_audit_events_task_id"), "workflow_audit_events", ["task_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_workflow_audit_events_task_id"), table_name="workflow_audit_events")
    op.drop_index(op.f("ix_workflow_audit_events_instance_id"), table_name="workflow_audit_events")
    op.drop_index(op.f("ix_workflow_audit_events_id"), table_name="workflow_audit_events")
    op.drop_index(op.f("ix_workflow_audit_events_event_type"), table_name="workflow_audit_events")
    op.drop_table("workflow_audit_events")
    op.drop_index(op.f("ix_workflow_delegations_module"), table_name="workflow_delegations")
    op.drop_index(op.f("ix_workflow_delegations_is_active"), table_name="workflow_delegations")
    op.drop_index(op.f("ix_workflow_delegations_id"), table_name="workflow_delegations")
    op.drop_table("workflow_delegations")

    for column in [
        "delegation_ends_at",
        "delegation_started_at",
        "delegation_reason",
        "delegated_role",
        "delegated_to_user_id",
        "original_assigned_role",
        "original_assigned_to_user_id",
    ]:
        op.drop_column("workflow_tasks", column)

    for column in [
        "metadata_json",
        "delegation_ends_at",
        "delegation_starts_at",
        "delegation_value",
        "delegation_type",
        "action_config",
        "action_type",
        "escalation_role",
        "timeout_action",
        "reminder_hours",
        "skip_if_condition",
    ]:
        op.drop_column("workflow_step_definitions", column)
