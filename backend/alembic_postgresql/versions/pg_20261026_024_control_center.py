"""Reuse organization records; add the missing branch manager link."""

from alembic import op
import sqlalchemy as sa

revision = "pg_20261026_024_control"
down_revision = "pg_20261026_023_suite_access"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "branches", sa.Column("manager_employee_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_branch_manager_employee",
        "branches",
        "employees",
        ["manager_employee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_branch_manager_employee", "branches", type_="foreignkey")
    op.drop_column("branches", "manager_employee_id")
