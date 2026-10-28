from alembic import op
import sqlalchemy as sa

revision = "pg_20261028_042_custody"
down_revision = "pg_20261028_041_asset_org"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("asset_assignments", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("asset_assignments", sa.Column("acknowledged_by", sa.Integer(), nullable=True))
    op.add_column("asset_assignments", sa.Column("returned_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_asset_assignments_acknowledged_by", "asset_assignments", "users", ["acknowledged_by"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_asset_assignments_returned_by", "asset_assignments", "users", ["returned_by"], ["id"], ondelete="SET NULL")


def downgrade():
    op.drop_constraint("fk_asset_assignments_returned_by", "asset_assignments", type_="foreignkey")
    op.drop_constraint("fk_asset_assignments_acknowledged_by", "asset_assignments", type_="foreignkey")
    op.drop_column("asset_assignments", "returned_by")
    op.drop_column("asset_assignments", "acknowledged_by")
    op.drop_column("asset_assignments", "acknowledged_at")
