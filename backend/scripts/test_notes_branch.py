"""Rehearse Notes migration on an explicitly identified disposable Neon branch."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config

backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend))
parser = argparse.ArgumentParser()
parser.add_argument("--url-file", required=True)
parser.add_argument("--branch-host", required=True)
args = parser.parse_args()
url = make_url(Path(args.url_file).read_text(encoding="utf-8-sig").strip())
assert url.host == args.branch_host and "-pooler" not in url.host
assert url.host.startswith("ep-") and url.host.endswith(".neon.tech")
os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
engine = create_engine(url.set(drivername="postgresql+psycopg"), hide_parameters=True)
config = Config(str(backend / "alembic.ini"))
before_revision = "pg_20261026_027_ai_security"
target_revision = "pg_20261026_028_notes_workspace"


def fingerprint(connection):
    rows = connection.execute(text("SELECT id,owner_id,title,content,project_id,task_id,tags,pinned,archived,version,created_at,updated_at,deleted_at FROM pms_private_notes ORDER BY id")).all()
    return len(rows), hashlib.sha256(json.dumps([list(row) for row in rows], default=str, sort_keys=True).encode()).hexdigest()


try:
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == before_revision
        before = fingerprint(connection)
        connection.commit()
        config.attributes["connection"] = connection
        command.upgrade(config, target_revision)
        assert fingerprint(connection) == before
        assert {"folder_id", "favorite"} <= {c["name"] for c in inspect(connection).get_columns("pms_private_notes")}
        assert connection.execute(text("SELECT count(*) FROM pms_private_notes WHERE favorite OR folder_id IS NOT NULL")).scalar() == 0
        connection.commit()
        command.downgrade(config, before_revision)
        assert fingerprint(connection) == before
        connection.commit()
        command.upgrade(config, target_revision)
        assert fingerprint(connection) == before
        connection.commit()
        print(f"PASS: production branch migration upgrade, downgrade, re-upgrade; {before[0]} legacy note(s) unchanged.")
except Exception as exc:
    diag=getattr(getattr(exc,"orig",None),"diag",None)
    print(f"FAIL: branch rehearsal ({type(exc).__name__}); SQLSTATE {getattr(getattr(exc,"orig",None),"sqlstate",None)}; {getattr(diag,"message_primary","credentials suppressed")}")
    raise SystemExit(1) from None
finally:
    engine.dispose()
