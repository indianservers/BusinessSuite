"""Shared import staging, preview receipts, history and encrypted finance connections."""
from alembic import op
from app.shared import import_schema
revision = '20261104_064_imports'
down_revision = '20261104_063_collections'
branch_labels = None
depends_on = None


def upgrade():
    import_schema.upgrade(op)


def downgrade():
    import_schema.downgrade(op)
