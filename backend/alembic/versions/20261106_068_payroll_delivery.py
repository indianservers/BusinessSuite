"""Payroll delivery and verified tax document workflow."""
from alembic import op
from app.services.payroll_delivery_schema import upgrade as apply, downgrade as revert
revision = "20261106_068_payroll_delivery"
down_revision = "20261105_067_public_signup"
branch_labels = depends_on = None
def upgrade(): apply(op)
def downgrade(): revert(op)
