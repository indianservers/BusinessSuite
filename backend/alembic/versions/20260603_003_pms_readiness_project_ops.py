"""pms readiness project operations

Revision ID: 20260603_003
Revises: 20260603_002
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260603_003"
down_revision = "20260603_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pms_projects", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.add_column("pms_projects", sa.Column("department_id", sa.Integer(), nullable=True))
    op.add_column("pms_projects", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.add_column("pms_projects", sa.Column("category", sa.String(length=80), nullable=True))
    op.add_column("pms_projects", sa.Column("planned_start_date", sa.Date(), nullable=True))
    op.add_column("pms_projects", sa.Column("planned_end_date", sa.Date(), nullable=True))
    op.add_column("pms_projects", sa.Column("actual_start_date", sa.Date(), nullable=True))
    op.add_column("pms_projects", sa.Column("actual_end_date", sa.Date(), nullable=True))
    op.add_column("pms_projects", sa.Column("estimated_hours", sa.Numeric(10, 2), nullable=True))
    op.add_column("pms_projects", sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=True))
    op.add_column("pms_projects", sa.Column("billing_status", sa.String(length=40), nullable=True, server_default="Unbilled"))
    op.add_column("pms_projects", sa.Column("is_template", sa.Boolean(), nullable=True, server_default=sa.false()))
    op.add_column("pms_project_members", sa.Column("allocation_percent", sa.Numeric(5, 2), nullable=True, server_default="100"))
    op.add_column("pms_tasks", sa.Column("recurrence_rule", sa.String(length=40), nullable=True))
    op.add_column("pms_tasks", sa.Column("recurrence_interval", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("pms_tasks", sa.Column("recurrence_until", sa.Date(), nullable=True))
    op.create_index("ix_pms_projects_owner_user_id", "pms_projects", ["owner_user_id"])
    op.create_index("ix_pms_projects_department_id", "pms_projects", ["department_id"])
    op.create_index("ix_pms_projects_branch_id", "pms_projects", ["branch_id"])
    op.create_index("ix_pms_projects_category", "pms_projects", ["category"])
    op.create_index("ix_pms_projects_billing_status", "pms_projects", ["billing_status"])
    op.create_index("ix_pms_projects_is_template", "pms_projects", ["is_template"])
    op.create_index("ix_pms_tasks_recurrence_rule", "pms_tasks", ["recurrence_rule"])


def downgrade() -> None:
    op.drop_index("ix_pms_tasks_recurrence_rule", table_name="pms_tasks")
    op.drop_index("ix_pms_projects_is_template", table_name="pms_projects")
    op.drop_index("ix_pms_projects_billing_status", table_name="pms_projects")
    op.drop_index("ix_pms_projects_category", table_name="pms_projects")
    op.drop_index("ix_pms_projects_branch_id", table_name="pms_projects")
    op.drop_index("ix_pms_projects_department_id", table_name="pms_projects")
    op.drop_index("ix_pms_projects_owner_user_id", table_name="pms_projects")
    op.drop_column("pms_tasks", "recurrence_until")
    op.drop_column("pms_tasks", "recurrence_interval")
    op.drop_column("pms_tasks", "recurrence_rule")
    op.drop_column("pms_project_members", "allocation_percent")
    op.drop_column("pms_projects", "is_template")
    op.drop_column("pms_projects", "billing_status")
    op.drop_column("pms_projects", "estimated_cost")
    op.drop_column("pms_projects", "estimated_hours")
    op.drop_column("pms_projects", "actual_end_date")
    op.drop_column("pms_projects", "actual_start_date")
    op.drop_column("pms_projects", "planned_end_date")
    op.drop_column("pms_projects", "planned_start_date")
    op.drop_column("pms_projects", "category")
    op.drop_column("pms_projects", "branch_id")
    op.drop_column("pms_projects", "department_id")
    op.drop_column("pms_projects", "owner_user_id")
