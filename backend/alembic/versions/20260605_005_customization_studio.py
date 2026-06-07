"""customization studio foundation

Revision ID: 20260605_005
Revises: 20260605_004
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from app.apps.customization.schema import CUSTOMIZATION_TABLE_MODELS


revision = "20260605_005"
down_revision = "20260605_004"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    for model in CUSTOMIZATION_TABLE_MODELS:
        if not _has_table(model.__tablename__):
            model.__table__.create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    for model in reversed(CUSTOMIZATION_TABLE_MODELS):
        if _has_table(model.__tablename__):
            model.__table__.drop(bind=bind)

