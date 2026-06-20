"""srm pos sessions and cashier closing

Revision ID: 20260620_001
Revises: 20260604_002
Create Date: 2026-06-20
"""

from alembic import op

from app.apps.srm.models import SRMPOSCashMovement, SRMPOSCashierClosing, SRMPOSSession


revision = "20260620_001"
down_revision = "20260604_002"
branch_labels = None
depends_on = None


TABLES = [
    SRMPOSSession.__table__,
    SRMPOSCashMovement.__table__,
    SRMPOSCashierClosing.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
