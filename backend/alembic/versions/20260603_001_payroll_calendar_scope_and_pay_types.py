"""payroll calendar scope and pay types

Revision ID: 20260603_001
Revises: 20260529_005
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260603_001"
down_revision = "20260529_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payroll_pay_groups", sa.Column("working_pattern", sa.String(length=40), nullable=True, server_default="company"))
    op.add_column("payroll_pay_groups", sa.Column("working_days_per_week", sa.Integer(), nullable=True))
    op.add_column("payroll_pay_groups", sa.Column("weekly_off_weekdays", sa.JSON(), nullable=True))

    op.add_column("employee_salaries", sa.Column("payroll_type", sa.String(length=40), nullable=True, server_default="monthly_fixed"))
    op.add_column("employee_salaries", sa.Column("wage_rate", sa.Numeric(12, 2), nullable=True, server_default="0"))
    op.add_column("employee_salaries", sa.Column("default_units", sa.Numeric(12, 2), nullable=True, server_default="0"))
    op.add_column("employee_salaries", sa.Column("unit_label", sa.String(length=40), nullable=True))
    op.add_column("employee_salaries", sa.Column("commission_rate_percent", sa.Numeric(8, 4), nullable=True, server_default="0"))
    op.add_column("employee_salaries", sa.Column("commission_base_amount", sa.Numeric(14, 2), nullable=True, server_default="0"))
    op.add_column("employee_salaries", sa.Column("invoice_amount", sa.Numeric(14, 2), nullable=True, server_default="0"))
    op.create_index("ix_employee_salaries_payroll_type", "employee_salaries", ["payroll_type"])

    op.add_column("payroll_runs", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.add_column("payroll_runs", sa.Column("department_id", sa.Integer(), nullable=True))
    op.add_column("payroll_runs", sa.Column("pay_group_id", sa.Integer(), nullable=True))
    op.add_column("payroll_runs", sa.Column("employee_category", sa.String(length=80), nullable=True))
    op.create_index("ix_payroll_runs_branch_id", "payroll_runs", ["branch_id"])
    op.create_index("ix_payroll_runs_department_id", "payroll_runs", ["department_id"])
    op.create_index("ix_payroll_runs_pay_group_id", "payroll_runs", ["pay_group_id"])
    op.create_index("ix_payroll_runs_employee_category", "payroll_runs", ["employee_category"])
    op.create_foreign_key("fk_payroll_runs_branch_id", "payroll_runs", "branches", ["branch_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_payroll_runs_department_id", "payroll_runs", "departments", ["department_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_payroll_runs_pay_group_id", "payroll_runs", "payroll_pay_groups", ["pay_group_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_payroll_runs_pay_group_id", "payroll_runs", type_="foreignkey")
    op.drop_constraint("fk_payroll_runs_department_id", "payroll_runs", type_="foreignkey")
    op.drop_constraint("fk_payroll_runs_branch_id", "payroll_runs", type_="foreignkey")
    op.drop_index("ix_payroll_runs_employee_category", table_name="payroll_runs")
    op.drop_index("ix_payroll_runs_pay_group_id", table_name="payroll_runs")
    op.drop_index("ix_payroll_runs_department_id", table_name="payroll_runs")
    op.drop_index("ix_payroll_runs_branch_id", table_name="payroll_runs")
    op.drop_column("payroll_runs", "employee_category")
    op.drop_column("payroll_runs", "pay_group_id")
    op.drop_column("payroll_runs", "department_id")
    op.drop_column("payroll_runs", "branch_id")

    op.drop_index("ix_employee_salaries_payroll_type", table_name="employee_salaries")
    op.drop_column("employee_salaries", "invoice_amount")
    op.drop_column("employee_salaries", "commission_base_amount")
    op.drop_column("employee_salaries", "commission_rate_percent")
    op.drop_column("employee_salaries", "unit_label")
    op.drop_column("employee_salaries", "default_units")
    op.drop_column("employee_salaries", "wage_rate")
    op.drop_column("employee_salaries", "payroll_type")

    op.drop_column("payroll_pay_groups", "weekly_off_weekdays")
    op.drop_column("payroll_pay_groups", "working_days_per_week")
    op.drop_column("payroll_pay_groups", "working_pattern")
