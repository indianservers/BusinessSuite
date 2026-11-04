"""Explicit task links to existing CRM contacts and leads."""
from alembic import op
from app.apps.project_management import task_record_link_schema
revision = 'pg_20261104_081_task_links'
down_revision = 'pg_20261104_080_imports'
branch_labels = None
depends_on = None

def upgrade():
    task_record_link_schema.upgrade(op)

def downgrade():
    task_record_link_schema.downgrade(op)
