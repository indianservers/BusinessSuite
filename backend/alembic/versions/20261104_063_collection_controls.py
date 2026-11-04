"""Canonical collection holds and retry-safe allocations."""
from alembic import op
from app.apps.srm import collection_schema

revision = '20261104_063_collections'
down_revision = '20261104_062_payment_requests'
branch_labels = None
depends_on = None


def upgrade():
    collection_schema.upgrade(op)


def downgrade():
    collection_schema.downgrade(op)
