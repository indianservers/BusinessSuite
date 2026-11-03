"""Suite-wide branch access, grants, ownership and audit."""
revision = "pg_20261102_059_branch_access"
down_revision = "pg_20261102_058_pos_catalog"
branch_labels = None
depends_on = None
from alembic import op
from app.db.branch_access_upgrade import upgrade as migrate, downgrade

def upgrade():
    migrate(op)
