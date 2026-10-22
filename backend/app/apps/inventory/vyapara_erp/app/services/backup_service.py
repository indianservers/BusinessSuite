import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from flask import current_app


def backup_uploads():
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    target = Path(current_app.config["UPLOAD_FOLDER"]).parent / f"uploads-backup-{stamp}.zip"
    with ZipFile(target, "w") as zf:
        upload_root = Path(current_app.config["UPLOAD_FOLDER"])
        for file in upload_root.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(upload_root))
    return target


def backup_postgresql():
    cfg = current_app.config
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    from sqlalchemy.engine import make_url
    url = make_url(cfg["SQLALCHEMY_DATABASE_URI"])
    target = Path(current_app.instance_path) / f"{url.database}-{stamp}.dump"
    target.parent.mkdir(parents=True, exist_ok=True)
    binary = shutil.which("pg_dump")
    if not binary and os.environ.get("POSTGRES_BIN"):
        binary = str(Path(os.environ["POSTGRES_BIN"]) / "pg_dump.exe")
    if not binary:
        raise RuntimeError("Install PostgreSQL client tools or set POSTGRES_BIN")
    env = dict(os.environ, PGHOST=url.host or "127.0.0.1", PGPORT=str(url.port or 5432), PGUSER=url.username or "", PGPASSWORD=url.password or "", PGDATABASE=url.database)
    for key, value in url.query.items():
        if key in {"sslmode", "sslrootcert"}:
            env["PG" + key.upper()] = str(value)
    subprocess.run([binary, "--format=custom", "--no-owner", "--no-acl", "--file", str(target)], env=env, check=True)
    return target

