"""communication hub foundation

Revision ID: 20260605_006
Revises: 20260605_005
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from app.apps.communication.schema import COMMUNICATION_TABLE_MODELS


revision = "20260605_006"
down_revision = "20260605_005"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    for model in COMMUNICATION_TABLE_MODELS:
        if not _has_table(model.__tablename__):
            model.__table__.create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    for model in reversed(COMMUNICATION_TABLE_MODELS):
        if _has_table(model.__tablename__):
            model.__table__.drop(bind=bind)

