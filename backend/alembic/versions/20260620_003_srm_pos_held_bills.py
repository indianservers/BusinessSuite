"""srm pos held bills

Revision ID: 20260620_003
Revises: 20260620_002
Create Date: 2026-06-20
"""

from alembic import op

from app.apps.srm.models import SRMPOSHeldBill


revision = "20260620_003"
down_revision = "20260620_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SRMPOSHeldBill.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    SRMPOSHeldBill.__table__.drop(bind=bind, checkfirst=True)
