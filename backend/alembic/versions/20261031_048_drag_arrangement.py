"""Persist quotation line order and project file folders."""
from alembic import op
import sqlalchemy as sa

revision = "20261031_048_drag_arrangement"
down_revision = "20261031_047_task_workspace"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("crm_file_folders", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.Integer(), nullable=False), sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(150), nullable=False))
    op.create_index("ix_crm_file_folders_organization_id", "crm_file_folders", ["organization_id"])
    op.add_column("crm_file_assets", sa.Column("folder_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("crm_file_assets") as batch:
        batch.create_foreign_key("fk_crm_file_assets_folder", "crm_file_folders", ["folder_id"], ["id"], ondelete="SET NULL")
    op.add_column("crm_quotation_items", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("pms_file_folders", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("project_id", sa.Integer(), sa.ForeignKey("pms_projects.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(150), nullable=False))
    op.create_index("ix_pms_file_folders_project_id", "pms_file_folders", ["project_id"])
    op.add_column("pms_file_assets", sa.Column("folder_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("pms_file_assets") as batch:
        batch.create_foreign_key("fk_pms_file_assets_folder", "pms_file_folders", ["folder_id"], ["id"], ondelete="SET NULL")


def downgrade():
    with op.batch_alter_table("crm_file_assets") as batch:
        batch.drop_constraint("fk_crm_file_assets_folder", type_="foreignkey")
        batch.drop_column("folder_id")
    op.drop_index("ix_crm_file_folders_organization_id", table_name="crm_file_folders")
    op.drop_table("crm_file_folders")
    with op.batch_alter_table("pms_file_assets") as batch:
        batch.drop_constraint("fk_pms_file_assets_folder", type_="foreignkey")
        batch.drop_column("folder_id")
    op.drop_index("ix_pms_file_folders_project_id", table_name="pms_file_folders")
    op.drop_table("pms_file_folders")
    op.drop_column("crm_quotation_items", "sort_order")
