"""Add reversible draft archival; visual graphs live in versioned definitions."""
from alembic import op
import sqlalchemy as sa
revision = "pg_20261027_033_power_studio"
down_revision = "pg_20261027_032_power_apps"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("power_apps_resources", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_power_resources_lifecycle", "power_apps_resources", ["organization_id", "environment", "archived_at"])

def downgrade():
    op.drop_index("ix_power_resources_lifecycle", table_name="power_apps_resources")
    op.drop_column("power_apps_resources", "archived_at")
