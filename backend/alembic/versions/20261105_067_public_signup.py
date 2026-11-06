"""Public company/individual trial signup and Super Admin review queue."""
from alembic import op
from app.services.signup_schema import upgrade as apply, downgrade as revert
revision = "20261105_067_public_signup"
down_revision = "20261104_066_file_storage"
branch_labels = depends_on = None

def upgrade(): apply(op)

def downgrade(): revert(op)
