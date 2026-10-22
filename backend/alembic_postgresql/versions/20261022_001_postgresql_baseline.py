"""Frozen full-suite PostgreSQL baseline, including historical schema fields.

Schema only: no records are copied from the retired database.
"""
from pathlib import Path
from alembic import op

revision = "pg_20261022_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql = (Path(__file__).resolve().parents[1] / "schema/suite_baseline.sql").read_text(encoding="utf-8")
    for statement in sql.split(";\n\n"):
        if statement.strip():
            op.execute(statement.rstrip().rstrip(";"))


def downgrade():
    raise RuntimeError("The initial suite schema is not destructively downgraded; restore a backup instead")
