"""PostgreSQL custom-format backup without credentials on the command line."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.engine import make_url
from app.core.config import settings


def postgres_tool(name):
    root = Path(__file__).resolve().parents[2]
    configured = os.environ.get("POSTGRES_BIN")
    candidates = [Path(configured) / (name + (".exe" if os.name == "nt" else ""))] if configured else []
    candidates.append(root / ".local/postgresql/pgsql/bin" / (name + ".exe"))
    for path in candidates:
        if path.exists():
            return str(path)
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"Install PostgreSQL client tools or set POSTGRES_BIN ({name} missing)")
    return found


def postgres_environment():
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("PostgreSQL connection required")
    env = dict(os.environ, PGHOST=url.host or "127.0.0.1", PGPORT=str(url.port or 5432),
               PGDATABASE=url.database, PGUSER=url.username or "", PGPASSWORD=url.password or "")
    for key in ("sslmode", "sslrootcert"):
        value = url.query.get(key) or (settings.POSTGRES_SSLROOTCERT if key == "sslrootcert" else settings.POSTGRES_SSLMODE)
        if value:
            env["PG" + key.upper()] = str(value)
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("backups") / ("business_suite_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".dump"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([postgres_tool("pg_dump"), "--format=custom", "--no-owner", "--no-acl", "--file", str(args.output)],
                   env=postgres_environment(), check=True)
    print(f"PostgreSQL backup saved: {args.output}")


if __name__ == "__main__":
    main()
