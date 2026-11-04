"""Canonical collection holds and retry-safe allocations."""
from alembic import op
from app.apps.srm import collection_schema

revision = 'pg_20261104_079_collections'
down_revision = 'pg_20261104_078_payment_requests'
branch_labels = None
depends_on = None


def upgrade():
    collection_schema.upgrade(op)


def downgrade():
    collection_schema.downgrade(op)
