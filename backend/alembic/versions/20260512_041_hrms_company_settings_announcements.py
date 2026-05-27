"""add company settings and announcement acknowledgements

Revision ID: 20260512_041
Revises: 20260512_040
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_041"
down_revision = "20260512_040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("cin_number", sa.String(length=30), nullable=True))
    op.add_column("companies", sa.Column("working_days_per_week", sa.Integer(), nullable=True, server_default="5"))
    op.add_column("companies", sa.Column("fiscal_year_start_month", sa.Integer(), nullable=True, server_default="4"))
    op.add_column("companies", sa.Column("default_timezone", sa.String(length=80), nullable=True, server_default="Asia/Kolkata"))
    op.add_column("companies", sa.Column("default_currency", sa.String(length=10), nullable=True, server_default="INR"))

    op.add_column("announcements", sa.Column("target_department_id", sa.Integer(), nullable=True))
    op.add_column("announcements", sa.Column("target_location_id", sa.Integer(), nullable=True))
    op.add_column("announcements", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("announcements", sa.Column("requires_acknowledgement", sa.Boolean(), nullable=True, server_default=sa.false()))
    op.create_index("ix_announcements_target_department_id", "announcements", ["target_department_id"])
    op.create_index("ix_announcements_target_location_id", "announcements", ["target_location_id"])
    op.create_foreign_key("fk_announcements_target_department", "announcements", "departments", ["target_department_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_announcements_target_location", "announcements", "work_locations", ["target_location_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "announcement_acknowledgements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("announcement_id", sa.Integer(), sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_announcement_acknowledgements_announcement_id", "announcement_acknowledgements", ["announcement_id"])
    op.create_index("ix_announcement_acknowledgements_employee_id", "announcement_acknowledgements", ["employee_id"])


def downgrade() -> None:
    op.drop_table("announcement_acknowledgements")
    op.drop_column("announcements", "requires_acknowledgement")
    op.drop_column("announcements", "expires_at")
    op.drop_column("announcements", "target_location_id")
    op.drop_column("announcements", "target_department_id")
    op.drop_column("companies", "default_currency")
    op.drop_column("companies", "default_timezone")
    op.drop_column("companies", "fiscal_year_start_month")
    op.drop_column("companies", "working_days_per_week")
    op.drop_column("companies", "cin_number")
