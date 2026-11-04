"""Settings file storage; preserve all existing file records."""
from alembic import op
from app.services.file_storage_schema import upgrade as apply, downgrade as revert
revision = "20261104_066_file_storage"
down_revision = "20261104_065_task_links"
branch_labels = depends_on = None
def upgrade(): apply(op)
def downgrade(): revert(op)
