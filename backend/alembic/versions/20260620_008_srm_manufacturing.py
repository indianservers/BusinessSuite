"""srm manufacturing

Revision ID: 20260620_008
Revises: 20260620_007
Create Date: 2026-06-20
"""

from alembic import op

from app.apps.srm.models import SRMBillOfMaterial, SRMBOMComponent, SRMProductionOrder


revision = "20260620_008"
down_revision = "20260620_007"
branch_labels = None
depends_on = None


TABLES = [
    SRMBillOfMaterial.__table__,
    SRMBOMComponent.__table__,
    SRMProductionOrder.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
