"""Accounting background sync and explicit CRM customer links."""
from alembic import op
from app.shared.accounting_sync.background_schema import upgrade as apply, downgrade as revert
revision = "20261107_070_accounting_jobs"
down_revision = "20261106_069_accounting_sync"
branch_labels = depends_on = None

def upgrade(): apply(op)
def downgrade(): revert(op)
