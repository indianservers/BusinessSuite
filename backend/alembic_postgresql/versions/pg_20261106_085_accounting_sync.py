"""Read-only accounting connector mirrors and sync history."""
from alembic import op
from app.shared.accounting_sync.schema import upgrade as apply, downgrade as revert
revision = "pg_20261106_085_accounting_sync"
down_revision = "pg_20261106_084_payroll_delivery"
branch_labels = depends_on = None

def upgrade(): apply(op)
def downgrade(): revert(op)
