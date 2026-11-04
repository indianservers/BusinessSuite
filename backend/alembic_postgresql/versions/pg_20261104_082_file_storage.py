"""Settings file storage; preserve all existing file records."""
from alembic import op
from app.services.file_storage_schema import upgrade as apply, downgrade as revert
revision = "pg_20261104_082_file_storage"
down_revision = "pg_20261104_081_task_links"
branch_labels = depends_on = None
def upgrade(): apply(op)
def downgrade(): revert(op)
