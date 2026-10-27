"""Reusable company custom columns and project values."""
from alembic import op
import sqlalchemy as sa
revision = 'pg_20261027_034_custom_columns'
down_revision = 'pg_20261027_033_power_studio'
branch_labels = None
depends_on = None

def upgrade():
    # Older PMS migrations may already have created these ORM columns.
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("pms_custom_fields")}
    indexes = {index["name"] for index in inspector.get_indexes("pms_custom_fields")}
    constraints = {item["name"] for item in inspector.get_unique_constraints("pms_custom_fields")}
    with op.batch_alter_table("pms_custom_fields") as batch:
        batch.alter_column("project_id", existing_type=sa.Integer(), nullable=True)
        if "organization_id" not in columns:
            batch.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
        if "scope_key" not in columns:
            batch.add_column(sa.Column("scope_key", sa.String(80), nullable=True))
        if "entity_type" not in columns:
            batch.add_column(sa.Column("entity_type", sa.String(12), nullable=False, server_default="task"))
        if "archived" not in columns:
            batch.add_column(sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "ix_pms_custom_fields_organization_id" not in indexes:
            batch.create_index("ix_pms_custom_fields_organization_id", ["organization_id"])
        if "ix_pms_custom_fields_scope_key" not in indexes:
            batch.create_index("ix_pms_custom_fields_scope_key", ["scope_key"])
        if "uq_pms_field_scope_name" not in constraints:
            batch.create_unique_constraint("uq_pms_field_scope_name", ["scope_key", "name"])
    op.execute("UPDATE pms_custom_fields SET organization_id=COALESCE(organization_id,(SELECT organization_id FROM pms_projects WHERE pms_projects.id=pms_custom_fields.project_id)), scope_key=COALESCE(scope_key,'project:' || CAST(project_id AS VARCHAR)) WHERE project_id IS NOT NULL AND (organization_id IS NULL OR scope_key IS NULL)")
    if not inspector.has_table("pms_project_custom_field_values"):
        op.create_table("pms_project_custom_field_values",
            sa.Column("field_id", sa.Integer(), sa.ForeignKey("pms_custom_fields.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("pms_projects.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("value_json", sa.Text(), nullable=False))


def downgrade():
    raise RuntimeError("Custom columns contain company and project data; restore a backup to downgrade safely")
