"""Multi-module operator and explicit workspace credential inheritance."""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
revision = '20261024_014_suite'
down_revision = '20261024_013'
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / 'alembic_postgresql/versions/pg_20261024_014_suite_operator.py'
    spec = spec_from_file_location('suite_migration', path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.upgrade()


def downgrade():
    pass
