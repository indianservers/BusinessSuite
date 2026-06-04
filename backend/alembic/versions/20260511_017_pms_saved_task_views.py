"""Add PMS saved task view fields.

Revision ID: 20260511_017
Revises: 20260511_016_pms_mentions_markdown_comments
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa


revision = "20260511_017"
down_revision = "20260511_016_pms_mentions_markdown_comments"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("pms_saved_filters")}
    new_columns = [
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(length=40), nullable=True, server_default="task"),
        sa.Column("filters_json", sa.Text(), nullable=True),
        sa.Column("sort_json", sa.Text(), nullable=True),
        sa.Column("columns_json", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=30), nullable=True, server_default="private"),
        sa.Column("is_default", sa.Boolean(), nullable=True, server_default=sa.false()),
    ]
    with op.batch_alter_table("pms_saved_filters") as batch_op:
        for column in new_columns:
            if column.name not in existing_columns:
                batch_op.add_column(column)
        batch_op.alter_column("project_id", existing_type=sa.Integer(), nullable=True)
    op.create_index("ix_pms_saved_filters_organization_id", "pms_saved_filters", ["organization_id"])
    op.create_index("ix_pms_saved_filters_entity_type", "pms_saved_filters", ["entity_type"])
    op.create_index("ix_pms_saved_filters_visibility", "pms_saved_filters", ["visibility"])
    op.create_index("ix_pms_saved_filters_is_default", "pms_saved_filters", ["is_default"])


def downgrade():
    op.drop_index("ix_pms_saved_filters_is_default", table_name="pms_saved_filters")
    op.drop_index("ix_pms_saved_filters_visibility", table_name="pms_saved_filters")
    op.drop_index("ix_pms_saved_filters_entity_type", table_name="pms_saved_filters")
    op.drop_index("ix_pms_saved_filters_organization_id", table_name="pms_saved_filters")
    with op.batch_alter_table("pms_saved_filters") as batch_op:
        batch_op.alter_column("project_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("is_default")
        batch_op.drop_column("visibility")
        batch_op.drop_column("columns_json")
        batch_op.drop_column("sort_json")
        batch_op.drop_column("filters_json")
        batch_op.drop_column("entity_type")
        batch_op.drop_column("organization_id")
