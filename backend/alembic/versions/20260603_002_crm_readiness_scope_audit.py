"""crm readiness scope and audit fields

Revision ID: 20260603_002
Revises: 20260512_042
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260603_002"
down_revision = "20260512_042"
branch_labels = None
depends_on = None


SCOPE_TABLES = (
    "crm_leads",
    "crm_companies",
    "crm_contacts",
    "crm_deals",
    "crm_quotations",
    "crm_activities",
    "crm_tasks",
)


def _add_scope_columns(table_name: str) -> None:
    op.add_column(table_name, sa.Column("branch_id", sa.Integer(), nullable=True))
    op.add_column(table_name, sa.Column("department_id", sa.Integer(), nullable=True))
    op.add_column(table_name, sa.Column("assigned_team_id", sa.Integer(), nullable=True))
    op.create_index(f"ix_{table_name}_branch_id", table_name, ["branch_id"])
    op.create_index(f"ix_{table_name}_department_id", table_name, ["department_id"])
    op.create_index(f"ix_{table_name}_assigned_team_id", table_name, ["assigned_team_id"])


def _drop_scope_columns(table_name: str) -> None:
    op.drop_index(f"ix_{table_name}_assigned_team_id", table_name=table_name)
    op.drop_index(f"ix_{table_name}_department_id", table_name=table_name)
    op.drop_index(f"ix_{table_name}_branch_id", table_name=table_name)
    op.drop_column(table_name, "assigned_team_id")
    op.drop_column(table_name, "department_id")
    op.drop_column(table_name, "branch_id")


def upgrade() -> None:
    for table_name in SCOPE_TABLES:
        _add_scope_columns(table_name)
    op.add_column("crm_deals", sa.Column("win_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("crm_deals", "win_reason")
    for table_name in reversed(SCOPE_TABLES):
        _drop_scope_columns(table_name)
