"""automation studio foundation

Revision ID: 20260605_004
Revises: 20260605_003
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_004"
down_revision = "20260605_003"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _create(table_name: str, *columns, **kwargs) -> None:
    if not _has_table(table_name):
        op.create_table(table_name, *columns, **kwargs)


def user_fk() -> sa.ForeignKey:
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def upgrade() -> None:
    _create(
        "automation_workflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("name", sa.String(180), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module_name", sa.String(60), nullable=False, index=True),
        sa.Column("record_type", sa.String(80), nullable=False, index=True),
        sa.Column("trigger_type", sa.String(80), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.false(), index=True),
        sa.Column("max_execution_depth", sa.Integer(), nullable=True, server_default="5"),
        sa.Column("created_by", sa.Integer(), user_fk(), nullable=True, index=True),
        sa.Column("updated_by", sa.Integer(), user_fk(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    _create(
        "automation_triggers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("automation_workflows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("trigger_type", sa.String(80), nullable=False, index=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true(), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create(
        "automation_conditions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("automation_workflows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("condition_json", sa.JSON(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create(
        "automation_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("automation_workflows.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("action_type", sa.String(80), nullable=False, index=True),
        sa.Column("action_json", sa.JSON(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create(
        "automation_execution_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("automation_workflows.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("module_name", sa.String(60), nullable=False, index=True),
        sa.Column("record_type", sa.String(80), nullable=True, index=True),
        sa.Column("record_id", sa.Integer(), nullable=True, index=True),
        sa.Column("trigger_type", sa.String(80), nullable=True, index=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="success", index=True),
        sa.Column("depth", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("request_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), user_fk(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    _create(
        "automation_blueprints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("name", sa.String(180), nullable=False, index=True),
        sa.Column("module_name", sa.String(60), nullable=False, index=True),
        sa.Column("record_type", sa.String(80), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true(), index=True),
        sa.Column("created_by", sa.Integer(), user_fk(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    _create(
        "automation_blueprint_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blueprint_id", sa.Integer(), sa.ForeignKey("automation_blueprints.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("stage_key", sa.String(80), nullable=False, index=True),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("required_fields_json", sa.JSON(), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("blueprint_id", "stage_key", name="uq_automation_blueprint_stage_key"),
    )
    _create(
        "automation_blueprint_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blueprint_id", sa.Integer(), sa.ForeignKey("automation_blueprints.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_stage_key", sa.String(80), nullable=False, index=True),
        sa.Column("to_stage_key", sa.String(80), nullable=False, index=True),
        sa.Column("required_fields_json", sa.JSON(), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("automation_workflow_id", sa.Integer(), sa.ForeignKey("automation_workflows.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("blueprint_id", "from_stage_key", "to_stage_key", name="uq_automation_blueprint_transition"),
    )
    _create(
        "automation_approval_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("name", sa.String(180), nullable=False, index=True),
        sa.Column("module_name", sa.String(60), nullable=False, index=True),
        sa.Column("record_type", sa.String(80), nullable=False, index=True),
        sa.Column("condition_json", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true(), index=True),
        sa.Column("created_by", sa.Integer(), user_fk(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    _create(
        "automation_approval_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("automation_approval_rules.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_order", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("approver_role", sa.String(80), nullable=True, index=True),
        sa.Column("approver_user_id", sa.Integer(), user_fk(), nullable=True, index=True),
        sa.Column("escalation_hours", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create(
        "automation_approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("automation_approval_rules.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("module_name", sa.String(60), nullable=False, index=True),
        sa.Column("record_type", sa.String(80), nullable=False, index=True),
        sa.Column("record_id", sa.Integer(), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=True, server_default="draft", index=True),
        sa.Column("current_step", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("submitted_by", sa.Integer(), user_fk(), nullable=True, index=True),
        sa.Column("decided_by", sa.Integer(), user_fk(), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("history_json", sa.JSON(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    _create(
        "automation_assignment_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("name", sa.String(180), nullable=False, index=True),
        sa.Column("module_name", sa.String(60), nullable=False, index=True),
        sa.Column("record_type", sa.String(80), nullable=False, index=True),
        sa.Column("condition_json", sa.JSON(), nullable=True),
        sa.Column("assignment_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true(), index=True),
        sa.Column("created_by", sa.Integer(), user_fk(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    _create(
        "automation_cadences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("name", sa.String(180), nullable=False, index=True),
        sa.Column("module_name", sa.String(60), nullable=False, index=True),
        sa.Column("target_type", sa.String(80), nullable=False, index=True),
        sa.Column("stop_rules_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(30), nullable=True, server_default="active", index=True),
        sa.Column("created_by", sa.Integer(), user_fk(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    _create(
        "automation_cadence_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cadence_id", sa.Integer(), sa.ForeignKey("automation_cadences.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("step_order", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("step_type", sa.String(40), nullable=False, index=True),
        sa.Column("delay_hours", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    _create(
        "automation_webhook_endpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("name", sa.String(180), nullable=False, index=True),
        sa.Column("target_url", sa.String(500), nullable=False),
        sa.Column("event_types_json", sa.JSON(), nullable=True),
        sa.Column("secret_ref", sa.String(180), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true(), index=True),
        sa.Column("created_by", sa.Integer(), user_fk(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    _create(
        "automation_scheduled_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True, index=True),
        sa.Column("job_type", sa.String(80), nullable=False, index=True),
        sa.Column("module_name", sa.String(60), nullable=False, index=True),
        sa.Column("record_type", sa.String(80), nullable=True, index=True),
        sa.Column("record_id", sa.Integer(), nullable=True, index=True),
        sa.Column("status", sa.String(30), nullable=True, server_default="scheduled", index=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), user_fk(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    for table_name in [
        "automation_scheduled_jobs",
        "automation_webhook_endpoints",
        "automation_cadence_steps",
        "automation_cadences",
        "automation_assignment_rules",
        "automation_approval_requests",
        "automation_approval_steps",
        "automation_approval_rules",
        "automation_blueprint_transitions",
        "automation_blueprint_stages",
        "automation_blueprints",
        "automation_execution_logs",
        "automation_actions",
        "automation_conditions",
        "automation_triggers",
        "automation_workflows",
    ]:
        if _has_table(table_name):
            op.drop_table(table_name)

