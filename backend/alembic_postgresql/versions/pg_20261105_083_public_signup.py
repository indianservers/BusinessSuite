"""Public company/individual trial signup and Super Admin review queue."""
from alembic import op
from app.services.signup_schema import upgrade as apply, downgrade as revert
revision = "pg_20261105_083_public_signup"
down_revision = "pg_20261104_082_file_storage"
branch_labels = depends_on = None

def upgrade(): apply(op)

def downgrade(): revert(op)
