"""Accounting background sync and explicit CRM customer links."""
from alembic import op
from app.shared.accounting_sync.background_schema import upgrade as apply, downgrade as revert
revision = "pg_20261107_086_accounting_jobs"
down_revision = "pg_20261106_085_accounting_sync"
branch_labels = depends_on = None

def upgrade(): apply(op)
def downgrade(): revert(op)
