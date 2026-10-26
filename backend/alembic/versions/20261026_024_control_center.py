"""Add branch manager to the SQLite migration tree."""

from alembic import op
import sqlalchemy as sa

revision = "20261026_024_control"
down_revision = "20261026_023_suite_access"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("branches") as batch:
        batch.add_column(sa.Column("manager_employee_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_branch_manager_employee",
            "employees",
            ["manager_employee_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("branches") as batch:
        batch.drop_constraint("fk_branch_manager_employee", type_="foreignkey")
        batch.drop_column("manager_employee_id")
