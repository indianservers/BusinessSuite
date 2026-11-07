"""Durable two-way calendar sync."""
from alembic import op
from app.apps.crm.calendar_sync_schema import upgrade as apply, downgrade as revert
revision = "20261107_072_calendar_sync"
down_revision = "20261107_071_crm_templates"
branch_labels = depends_on = None

def upgrade(): apply(op)
def downgrade(): revert(op)
