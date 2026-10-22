"""Frozen full-suite PostgreSQL baseline, including historical schema fields.

Schema only: no records are copied from the retired database.
"""
from pathlib import Path
import re
from alembic import op

revision = "pg_20261022_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql = (Path(__file__).resolve().parents[1] / "schema/suite_baseline.sql").read_text(encoding="utf-8")
    statements = []
    for statement in sql.split(";\n\n"):
        statement = statement.strip().rstrip(";")
        if not statement:
            continue
        statement = statement.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
        statement = re.sub(r"CREATE (UNIQUE )?INDEX ", r"CREATE \1INDEX IF NOT EXISTS ", statement, count=1)
        match = re.match(r"ALTER TABLE (\w+) ADD FOREIGN KEY\((\w+)\)", statement)
        if match:
            name = f"{match[1]}_{match[2]}_fkey"
            statement = statement.replace("ADD FOREIGN KEY", f'ADD CONSTRAINT "{name}" FOREIGN KEY', 1)
            statement = f"DO $migration$ BEGIN {statement}; EXCEPTION WHEN duplicate_object THEN NULL; END $migration$"
        statements.append(statement)
    # Neon may not expose max_locks_per_transaction. Bound DDL lock ownership,
    # and allow retries after an interrupted bootstrap without dropping records.
    # Each multi-statement batch is one implicit PostgreSQL transaction.
    with op.get_context().autocommit_block():
        for offset in range(0, len(statements), 50):
            op.get_bind().exec_driver_sql(";\n".join(statements[offset:offset + 50]) + ";")


def downgrade():
    raise RuntimeError("The initial suite schema is not destructively downgraded; restore a backup instead")
