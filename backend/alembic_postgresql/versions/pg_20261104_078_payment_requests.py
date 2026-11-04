"""Shared POS, CRM and invoice payment requests."""
revision = "pg_20261104_078_payment_requests"
down_revision = "pg_20261104_077_native_events"
branch_labels = None
depends_on = None
from alembic import op
from app.shared import payment_schema

def upgrade(): payment_schema.upgrade(op)
def downgrade(): payment_schema.downgrade(op)
