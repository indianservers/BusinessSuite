"""add pms project intake

Revision ID: 20260512_035
Revises: 20260512_034
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_035"
down_revision = "20260512_034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pms_project_intakes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requester_user_id", sa.Integer(), nullable=True),
        sa.Column("requester_name", sa.String(length=180), nullable=True),
        sa.Column("requester_email", sa.String(length=150), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("client_name", sa.String(length=180), nullable=True),
        sa.Column("priority", sa.String(length=30), nullable=True),
        sa.Column("desired_start_date", sa.Date(), nullable=True),
        sa.Column("desired_due_date", sa.Date(), nullable=True),
        sa.Column("budget_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_project_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["pms_clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_project_id"], ["pms_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pms_project_intakes_client_id"), "pms_project_intakes", ["client_id"], unique=False)
    op.create_index(op.f("ix_pms_project_intakes_created_project_id"), "pms_project_intakes", ["created_project_id"], unique=False)
    op.create_index(op.f("ix_pms_project_intakes_id"), "pms_project_intakes", ["id"], unique=False)
    op.create_index(op.f("ix_pms_project_intakes_organization_id"), "pms_project_intakes", ["organization_id"], unique=False)
    op.create_index(op.f("ix_pms_project_intakes_requester_email"), "pms_project_intakes", ["requester_email"], unique=False)
    op.create_index(op.f("ix_pms_project_intakes_requester_user_id"), "pms_project_intakes", ["requester_user_id"], unique=False)
    op.create_index(op.f("ix_pms_project_intakes_status"), "pms_project_intakes", ["status"], unique=False)
    op.create_index(op.f("ix_pms_project_intakes_title"), "pms_project_intakes", ["title"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pms_project_intakes_title"), table_name="pms_project_intakes")
    op.drop_index(op.f("ix_pms_project_intakes_status"), table_name="pms_project_intakes")
    op.drop_index(op.f("ix_pms_project_intakes_requester_user_id"), table_name="pms_project_intakes")
    op.drop_index(op.f("ix_pms_project_intakes_requester_email"), table_name="pms_project_intakes")
    op.drop_index(op.f("ix_pms_project_intakes_organization_id"), table_name="pms_project_intakes")
    op.drop_index(op.f("ix_pms_project_intakes_id"), table_name="pms_project_intakes")
    op.drop_index(op.f("ix_pms_project_intakes_created_project_id"), table_name="pms_project_intakes")
    op.drop_index(op.f("ix_pms_project_intakes_client_id"), table_name="pms_project_intakes")
    op.drop_table("pms_project_intakes")
