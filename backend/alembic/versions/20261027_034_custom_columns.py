"""Reusable company custom columns and project values."""
from alembic import op
import sqlalchemy as sa
revision = '20261027_034_custom_columns'
down_revision = '20261027_031_communication'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("pms_custom_fields") as batch:
        batch.alter_column("project_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("scope_key", sa.String(80), nullable=True))
        batch.add_column(sa.Column("entity_type", sa.String(12), nullable=False, server_default="task"))
        batch.add_column(sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_index("ix_pms_custom_fields_organization_id", ["organization_id"])
        batch.create_index("ix_pms_custom_fields_scope_key", ["scope_key"])
        batch.create_unique_constraint("uq_pms_field_scope_name", ["scope_key", "name"])
    op.execute("UPDATE pms_custom_fields SET organization_id=(SELECT organization_id FROM pms_projects WHERE pms_projects.id=pms_custom_fields.project_id), scope_key='project:' || CAST(project_id AS VARCHAR)")
    op.create_table("pms_project_custom_field_values",
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("pms_custom_fields.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("pms_projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("value_json", sa.Text(), nullable=False))

def downgrade():
    raise RuntimeError("Custom columns contain company and project data; restore a backup to downgrade safely")
