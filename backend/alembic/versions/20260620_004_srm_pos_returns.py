"""srm pos returns

Revision ID: 20260620_004
Revises: 20260620_003
Create Date: 2026-06-20
"""

from alembic import op

from app.apps.srm.models import SRMPOSReturn, SRMPOSReturnLine


revision = "20260620_004"
down_revision = "20260620_003"
branch_labels = None
depends_on = None


TABLES = [
    SRMPOSReturn.__table__,
    SRMPOSReturnLine.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
