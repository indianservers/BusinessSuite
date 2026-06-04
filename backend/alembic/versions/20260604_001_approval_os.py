"""approval os

Revision ID: 20260604_001
Revises: 20260603_006
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_001"
down_revision = "20260603_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_module", sa.String(length=80), nullable=False),
        sa.Column("approval_type", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requester_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_role", sa.String(length=120), nullable=True),
        sa.Column("delegated_to_user_id", sa.Integer(), nullable=True),
        sa.Column("delegated_role", sa.String(length=120), nullable=True),
        sa.Column("priority", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_user_id", sa.Integer(), nullable=True),
        sa.Column("escalation_role", sa.String(length=120), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mobile_enabled", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["delegated_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["escalation_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["id", "source_module", "approval_type", "entity_type", "entity_id", "requester_user_id", "assigned_to_user_id", "assigned_role", "priority", "status", "sla_due_at", "mobile_enabled", "created_at"]:
        op.create_index(op.f(f"ix_approval_requests_{column}"), "approval_requests", [column])

    op.create_table(
        "approval_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["request_id"], ["approval_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approval_comments_id"), "approval_comments", ["id"])
    op.create_index(op.f("ix_approval_comments_request_id"), "approval_comments", ["request_id"])

    op.create_table(
        "approval_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("before_status", sa.String(length=30), nullable=True),
        sa.Column("after_status", sa.String(length=30), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["request_id"], ["approval_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approval_history_id"), "approval_history", ["id"])
    op.create_index(op.f("ix_approval_history_request_id"), "approval_history", ["request_id"])
    op.create_index(op.f("ix_approval_history_event_type"), "approval_history", ["event_type"])
    op.create_index(op.f("ix_approval_history_created_at"), "approval_history", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_approval_history_created_at"), table_name="approval_history")
    op.drop_index(op.f("ix_approval_history_event_type"), table_name="approval_history")
    op.drop_index(op.f("ix_approval_history_request_id"), table_name="approval_history")
    op.drop_index(op.f("ix_approval_history_id"), table_name="approval_history")
    op.drop_table("approval_history")
    op.drop_index(op.f("ix_approval_comments_request_id"), table_name="approval_comments")
    op.drop_index(op.f("ix_approval_comments_id"), table_name="approval_comments")
    op.drop_table("approval_comments")
    for column in ["created_at", "mobile_enabled", "sla_due_at", "status", "priority", "assigned_role", "assigned_to_user_id", "requester_user_id", "entity_id", "entity_type", "approval_type", "source_module", "id"]:
        op.drop_index(op.f(f"ix_approval_requests_{column}"), table_name="approval_requests")
    op.drop_table("approval_requests")
