"""srm price lists

Revision ID: 20260620_006
Revises: 20260620_005
Create Date: 2026-06-20
"""

from alembic import op

from app.apps.srm.models import SRMPriceList, SRMPriceListLine


revision = "20260620_006"
down_revision = "20260620_005"
branch_labels = None
depends_on = None


TABLES = [
    SRMPriceList.__table__,
    SRMPriceListLine.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
