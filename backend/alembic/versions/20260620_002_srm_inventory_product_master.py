"""srm inventory product master

Revision ID: 20260620_002
Revises: 20260620_001
Create Date: 2026-06-20
"""

from alembic import op

from app.apps.srm.models import (
    SRMInventoryBalance,
    SRMInventoryMovement,
    SRMProduct,
    SRMProductCategory,
    SRMWarehouse,
)


revision = "20260620_002"
down_revision = "20260620_001"
branch_labels = None
depends_on = None


TABLES = [
    SRMProductCategory.__table__,
    SRMWarehouse.__table__,
    SRMProduct.__table__,
    SRMInventoryBalance.__table__,
    SRMInventoryMovement.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
