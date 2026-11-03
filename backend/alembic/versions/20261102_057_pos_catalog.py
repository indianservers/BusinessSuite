"""Reuse the POS product master for the shared catalog."""
revision = "20261102_057_pos_catalog"
down_revision = "20261102_056_shared_catalog"
branch_labels = None
depends_on = None

from alembic import op
from app.db.pos_catalog_upgrade import upgrade as migrate, downgrade


def upgrade():
    migrate(op)
