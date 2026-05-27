"""add org structure master metadata fields

Revision ID: 20260512_036
Revises: 20260512_035
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_036"
down_revision = "20260512_035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in (
        "branches",
        "business_units",
        "cost_centers",
        "work_locations",
        "grade_bands",
        "positions",
        "departments",
        "designations",
    ):
        op.add_column(table_name, sa.Column("organization_id", sa.Integer(), nullable=True))
        op.add_column(table_name, sa.Column("created_by", sa.Integer(), nullable=True))
        op.create_index(op.f(f"ix_{table_name}_organization_id"), table_name, ["organization_id"], unique=False)

    for table_name in ("branches", "cost_centers", "work_locations", "grade_bands", "positions"):
        op.add_column(table_name, sa.Column("description", sa.Text(), nullable=True))

    for table_name in ("business_units", "cost_centers", "work_locations", "grade_bands", "positions"):
        op.add_column(table_name, sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE branches SET organization_id = company_id WHERE organization_id IS NULL")
    op.execute("UPDATE business_units SET organization_id = company_id WHERE organization_id IS NULL")
    op.execute("UPDATE cost_centers SET organization_id = company_id WHERE organization_id IS NULL")
    op.execute("UPDATE work_locations SET organization_id = company_id WHERE organization_id IS NULL")
    op.execute("UPDATE positions SET organization_id = company_id WHERE organization_id IS NULL")
    op.execute(
        """
        UPDATE departments
        SET organization_id = branches.company_id
        FROM branches
        WHERE departments.branch_id = branches.id AND departments.organization_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE designations
        SET organization_id = departments.organization_id
        FROM departments
        WHERE designations.department_id = departments.id AND designations.organization_id IS NULL
        """
    )


def downgrade() -> None:
    for table_name in ("business_units", "cost_centers", "work_locations", "grade_bands", "positions"):
        op.drop_column(table_name, "updated_at")

    for table_name in ("branches", "cost_centers", "work_locations", "grade_bands", "positions"):
        op.drop_column(table_name, "description")

    for table_name in (
        "branches",
        "business_units",
        "cost_centers",
        "work_locations",
        "grade_bands",
        "positions",
        "departments",
        "designations",
    ):
        op.drop_index(op.f(f"ix_{table_name}_organization_id"), table_name=table_name)
        op.drop_column(table_name, "created_by")
        op.drop_column(table_name, "organization_id")
