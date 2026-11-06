"""Read-only accounting connector mirrors and sync history."""
from alembic import op
from app.shared.accounting_sync.schema import upgrade as apply, downgrade as revert
revision = "20261106_069_accounting_sync"
down_revision = "20261106_068_payroll_delivery"
branch_labels = depends_on = None

def upgrade(): apply(op)
def downgrade(): revert(op)
