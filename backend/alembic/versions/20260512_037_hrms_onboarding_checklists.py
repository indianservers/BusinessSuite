"""add hrms onboarding checklist system

Revision ID: 20260512_037
Revises: 20260512_036
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_037"
down_revision = "20260512_036"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    tables = _tables()

    if "onboarding_templates" not in tables:
        op.create_table(
            "onboarding_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("applicable_for", sa.String(length=30), nullable=True, server_default="all"),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_onboarding_templates_organization_id", "onboarding_templates", ["organization_id"])
        op.create_index("ix_onboarding_templates_is_active", "onboarding_templates", ["is_active"])
    else:
        _add_column_if_missing("onboarding_templates", sa.Column("organization_id", sa.Integer(), nullable=True))
        _add_column_if_missing("onboarding_templates", sa.Column("applicable_for", sa.String(length=30), nullable=True, server_default="all"))
        _add_column_if_missing("onboarding_templates", sa.Column("created_by", sa.Integer(), nullable=True))
        op.execute("UPDATE onboarding_templates SET applicable_for = 'all' WHERE applicable_for IS NULL")

    tables = _tables()
    if "onboarding_template_tasks" not in tables:
        op.create_table(
            "onboarding_template_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("template_id", sa.Integer(), sa.ForeignKey("onboarding_templates.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=50), nullable=True, server_default="other"),
            sa.Column("due_day_offset", sa.Integer(), nullable=True, server_default="1"),
            sa.Column("assigned_to_role", sa.String(length=50), nullable=True, server_default="employee"),
            sa.Column("is_mandatory", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("order_index", sa.Integer(), nullable=True, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        )
        op.create_index("ix_onboarding_template_tasks_template_id", "onboarding_template_tasks", ["template_id"])

    tables = _tables()
    if "employee_onboardings" not in tables:
        op.create_table(
            "employee_onboardings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
            sa.Column("template_id", sa.Integer(), sa.ForeignKey("onboarding_templates.id", ondelete="SET NULL"), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("target_completion_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=True, server_default="not_started"),
            sa.Column("completion_percentage", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_employee_onboardings_employee_id", "employee_onboardings", ["employee_id"])
        op.create_index("ix_employee_onboardings_status", "employee_onboardings", ["status"])
    else:
        _add_column_if_missing("employee_onboardings", sa.Column("target_completion_date", sa.Date(), nullable=True))
        _add_column_if_missing("employee_onboardings", sa.Column("completion_percentage", sa.Integer(), nullable=True, server_default="0"))
        _add_column_if_missing("employee_onboardings", sa.Column("created_by", sa.Integer(), nullable=True))
        op.execute("UPDATE employee_onboardings SET completion_percentage = 0 WHERE completion_percentage IS NULL")

    tables = _tables()
    if "employee_onboarding_tasks" not in tables:
        op.create_table(
            "employee_onboarding_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_onboarding_id", sa.Integer(), sa.ForeignKey("employee_onboardings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("template_task_id", sa.Integer(), sa.ForeignKey("onboarding_template_tasks.id", ondelete="SET NULL"), nullable=True),
            sa.Column("task_name", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=True, server_default="other"),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=True, server_default="pending"),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        )
        op.create_index("ix_employee_onboarding_tasks_employee_onboarding_id", "employee_onboarding_tasks", ["employee_onboarding_id"])
        op.create_index("ix_employee_onboarding_tasks_assigned_to_user_id", "employee_onboarding_tasks", ["assigned_to_user_id"])
        op.create_index("ix_employee_onboarding_tasks_status", "employee_onboarding_tasks", ["status"])

    if "policy_acknowledgements" not in _tables():
        op.create_table(
            "policy_acknowledgements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
            sa.Column("policy_name", sa.String(length=200), nullable=False),
            sa.Column("policy_document_url", sa.String(length=500), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ip_address", sa.String(length=50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        )


def downgrade() -> None:
    tables = _tables()
    if "employee_onboarding_tasks" in tables:
        op.drop_table("employee_onboarding_tasks")
    if "onboarding_template_tasks" in tables:
        op.drop_table("onboarding_template_tasks")
    if "employee_onboardings" in tables:
        for column_name in ("created_by", "completion_percentage", "target_completion_date"):
            if column_name in _columns("employee_onboardings"):
                op.drop_column("employee_onboardings", column_name)
    if "onboarding_templates" in tables:
        for column_name in ("created_by", "applicable_for", "organization_id"):
            if column_name in _columns("onboarding_templates"):
                op.drop_column("onboarding_templates", column_name)
