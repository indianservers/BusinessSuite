"""Suite-wide branch access, grants, ownership and audit."""
revision = "20261102_058_branch_access"
down_revision = "20261102_057_pos_catalog"
branch_labels = None
depends_on = None
from alembic import op
from app.db.branch_access_upgrade import upgrade as migrate, downgrade

def upgrade():
    migrate(op)
