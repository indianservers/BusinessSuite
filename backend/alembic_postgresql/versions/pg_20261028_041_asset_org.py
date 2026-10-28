from alembic import op
import sqlalchemy as sa

revision = "pg_20261028_041_asset_org"
down_revision = "pg_20261027_040_email"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assets", sa.Column("organization_id", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_assets_organization_id", "assets", ["organization_id"])


def downgrade():
    op.drop_index("ix_assets_organization_id", table_name="assets")
    op.drop_column("assets", "organization_id")
