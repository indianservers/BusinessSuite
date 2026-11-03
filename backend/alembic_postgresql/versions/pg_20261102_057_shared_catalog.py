"""Shared catalog extensions; preserve all legacy catalog and project records."""
revision = "pg_20261102_057_shared_catalog"
down_revision = "pg_20261102_056_crm_task_sync"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table("shared_catalog_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("crm_products.id", ondelete="CASCADE"), unique=True),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("crm_services.id", ondelete="CASCADE"), unique=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("pms_workspaces.id", ondelete="RESTRICT")),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("custom_fields", sa.JSON(), nullable=False),
        sa.Column("pricing_options", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("(product_id IS NOT NULL AND service_id IS NULL) OR (product_id IS NULL AND service_id IS NOT NULL)", name="ck_catalog_details_item"))
    op.create_index("ix_shared_catalog_details_organization_id", "shared_catalog_details", ["organization_id"])
    op.create_index("ix_shared_catalog_details_workspace_id", "shared_catalog_details", ["workspace_id"])
    op.create_table("shared_catalog_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("crm_products.id", ondelete="RESTRICT")),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("crm_services.id", ondelete="RESTRICT")),
        sa.Column("pricing_id", sa.String(80)),
        sa.Column("quantity", sa.Numeric(14,4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14,2), nullable=False),
        sa.Column("discount", sa.Numeric(5,2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5,2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.CheckConstraint("(product_id IS NOT NULL AND service_id IS NULL) OR (product_id IS NULL AND service_id IS NOT NULL)", name="ck_catalog_link_item"))
    op.create_index("ix_catalog_link_target", "shared_catalog_links", ["organization_id", "target_type", "target_id"])


def downgrade():
    op.drop_table("shared_catalog_links")
    op.drop_table("shared_catalog_details")
