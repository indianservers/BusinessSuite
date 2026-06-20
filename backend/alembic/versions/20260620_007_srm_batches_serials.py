"""srm batches and serials

Revision ID: 20260620_007
Revises: 20260620_006
Create Date: 2026-06-20
"""

from alembic import op

from app.apps.srm.models import SRMInventoryBatch, SRMSerialNumber


revision = "20260620_007"
down_revision = "20260620_006"
branch_labels = None
depends_on = None


TABLES = [
    SRMInventoryBatch.__table__,
    SRMSerialNumber.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
