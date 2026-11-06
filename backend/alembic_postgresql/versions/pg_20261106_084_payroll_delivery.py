"""Payroll delivery and verified tax document workflow."""
from alembic import op
from app.services.payroll_delivery_schema import upgrade as apply, downgrade as revert
revision = "pg_20261106_084_payroll_delivery"
down_revision = "pg_20261105_083_public_signup"
branch_labels = depends_on = None
def upgrade(): apply(op)
def downgrade(): revert(op)
