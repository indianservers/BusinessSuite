"""Explicit task links to existing CRM contacts and leads."""
from alembic import op
from app.apps.project_management import task_record_link_schema
revision = '20261104_065_task_links'
down_revision = '20261104_064_imports'
branch_labels = None
depends_on = None

def upgrade():
    task_record_link_schema.upgrade(op)

def downgrade():
    task_record_link_schema.downgrade(op)
