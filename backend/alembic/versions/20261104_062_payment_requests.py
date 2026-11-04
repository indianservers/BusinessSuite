"""Shared POS, CRM and invoice payment requests."""
revision = "20261104_062_payment_requests"
down_revision = "20261104_061_native_events"
branch_labels = None
depends_on = None
from alembic import op
from app.shared import payment_schema

def upgrade(): payment_schema.upgrade(op)
def downgrade(): payment_schema.downgrade(op)
