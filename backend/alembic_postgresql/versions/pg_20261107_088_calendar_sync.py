"""Durable two-way calendar sync."""
from alembic import op
from app.apps.crm.calendar_sync_schema import upgrade as apply, downgrade as revert
revision = "pg_20261107_088_calendar_sync"
down_revision = "pg_20261107_087_crm_templates"
branch_labels = depends_on = None

def upgrade(): apply(op)
def downgrade(): revert(op)
