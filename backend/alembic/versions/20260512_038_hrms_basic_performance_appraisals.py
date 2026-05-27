"""add basic hrms performance appraisals

Revision ID: 20260512_038
Revises: 20260512_037
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_038"
down_revision = "20260512_037"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if table_name in _tables() and column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    if "appraisal_cycles" not in _tables():
        op.create_table(
            "appraisal_cycles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("cycle_type", sa.String(length=20), nullable=True),
            sa.Column("review_period_start", sa.Date(), nullable=True),
            sa.Column("review_period_end", sa.Date(), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("self_review_deadline", sa.Date(), nullable=True),
            sa.Column("manager_review_deadline", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=True, server_default="draft"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
    else:
        _add_column_if_missing("appraisal_cycles", sa.Column("organization_id", sa.Integer(), nullable=True))
        _add_column_if_missing("appraisal_cycles", sa.Column("review_period_start", sa.Date(), nullable=True))
        _add_column_if_missing("appraisal_cycles", sa.Column("review_period_end", sa.Date(), nullable=True))
        _add_column_if_missing("appraisal_cycles", sa.Column("created_by", sa.Integer(), nullable=True))
        op.execute("UPDATE appraisal_cycles SET review_period_start = start_date WHERE review_period_start IS NULL")
        op.execute("UPDATE appraisal_cycles SET review_period_end = end_date WHERE review_period_end IS NULL")

    if "performance_goals" in _tables():
        _add_column_if_missing("performance_goals", sa.Column("category", sa.String(length=30), nullable=True, server_default="individual"))
        _add_column_if_missing("performance_goals", sa.Column("target_value", sa.String(length=500), nullable=True))
        _add_column_if_missing("performance_goals", sa.Column("achieved_value", sa.String(length=500), nullable=True))
        _add_column_if_missing("performance_goals", sa.Column("set_by", sa.Integer(), nullable=True))
        op.execute("UPDATE performance_goals SET category = 'individual' WHERE category IS NULL")
    else:
        op.create_table(
            "performance_goals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
            sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=30), nullable=True, server_default="individual"),
            sa.Column("goal_type", sa.String(length=20), nullable=True, server_default="KRA"),
            sa.Column("weightage", sa.Numeric(5, 2), nullable=True, server_default="100"),
            sa.Column("target_value", sa.String(length=500), nullable=True),
            sa.Column("achieved_value", sa.String(length=500), nullable=True),
            sa.Column("target", sa.String(length=500), nullable=True),
            sa.Column("target_date", sa.Date(), nullable=True),
            sa.Column("achievement", sa.Text(), nullable=True),
            sa.Column("self_rating", sa.Numeric(3, 1), nullable=True),
            sa.Column("manager_rating", sa.Numeric(3, 1), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=True, server_default="active"),
            sa.Column("set_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "performance_reviews" not in _tables():
        op.create_table(
            "performance_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
            sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("review_type", sa.String(length=20), nullable=True),
            sa.Column("overall_rating", sa.Numeric(3, 1), nullable=True),
            sa.Column("strengths", sa.Text(), nullable=True),
            sa.Column("improvements", sa.Text(), nullable=True),
            sa.Column("comments", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=True, server_default="draft"),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "performance_rating_criteria" not in _tables():
        op.create_table(
            "performance_rating_criteria",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("review_id", sa.Integer(), sa.ForeignKey("performance_reviews.id", ondelete="CASCADE"), nullable=False),
            sa.Column("criteria_name", sa.String(length=150), nullable=False),
            sa.Column("criteria_category", sa.String(length=80), nullable=True),
            sa.Column("rating", sa.Numeric(3, 1), nullable=True),
            sa.Column("comments", sa.Text(), nullable=True),
            sa.Column("weightage", sa.Numeric(5, 2), nullable=True, server_default="0"),
        )
        op.create_index("ix_performance_rating_criteria_review_id", "performance_rating_criteria", ["review_id"])


def downgrade() -> None:
    if "performance_rating_criteria" in _tables():
        op.drop_table("performance_rating_criteria")
    for table_name, column_names in {
        "performance_goals": ("set_by", "achieved_value", "target_value", "category"),
        "appraisal_cycles": ("created_by", "review_period_end", "review_period_start", "organization_id"),
    }.items():
        if table_name in _tables():
            existing = _columns(table_name)
            for column_name in column_names:
                if column_name in existing:
                    op.drop_column(table_name, column_name)
