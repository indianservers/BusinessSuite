from pathlib import Path
from alembic import op

revision = 'pg_inventory_20261022'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql = (Path(__file__).resolve().parents[1] / 'schema/inventory_baseline.sql').read_text(encoding='utf-8')
    for statement in sql.split(';\n\n'):
        if statement.strip():
            op.execute(statement.rstrip().rstrip(';'))


def downgrade():
    raise RuntimeError('Restore a backup instead of destructively dropping the inventory schema')
