"""Start the packaged API and PostgreSQL on Windows loopback."""
import argparse
from contextlib import asynccontextmanager
import getpass
import json
import msvcrt
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time
import webbrowser

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"


def configuration(data):
    path = data / "runtime.json"
    if not path.exists():
        values = {key: secrets.token_urlsafe(48)
                  for key in ("POSTGRES_PASSWORD", "SECRET_KEY", "REFRESH_SECRET_KEY")}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(values), encoding="utf-8")
        temporary.replace(path)
    return json.loads(path.read_text(encoding="utf-8"))


def start_database(data, port, password):
    cluster = data / "postgres"
    binary = ROOT / "postgresql" / "bin"
    if not (cluster / "PG_VERSION").is_file():
        with tempfile.TemporaryDirectory(prefix="initialize-", dir=data) as temporary:
            staging = Path(temporary) / "cluster"
            password_file = Path(temporary) / "password"
            password_file.write_text(password + "\n", encoding="utf-8")
            subprocess.run([binary / "initdb.exe", "-D", staging, "-U", "business_suite",
                            "--encoding=UTF8", "--locale=C", "--auth=scram-sha-256",
                            f"--pwfile={password_file}"], check=True)
            staging.replace(cluster)

    control = [binary / "pg_ctl.exe", "-D", cluster]
    status = subprocess.run([*control, "status"], stdout=subprocess.DEVNULL).returncode
    if status == 3:
        subprocess.run([*control, "-l", data / "postgres.log", "-w", "-t", "45",
                        "-o", f"-h {HOST} -p {port} -c max_locks_per_transaction=256",
                        "start"], check=True)
    elif status != 0:
        raise RuntimeError("Could not check the local PostgreSQL cluster.")
    return control


def configure_backend(data, options, values):
    url = f"http://{HOST}:{options.port}"
    os.environ.update(values, ENVIRONMENT="development", DEBUG="false",
                      DATABASE_URL="", POSTGRES_USER="business_suite", POSTGRES_SERVER=HOST,
                      POSTGRES_PORT=str(options.postgres_port), POSTGRES_DB="business_suite",
                      POSTGRES_SSLMODE="disable", DATABASE_AUTO_MIGRATE="true",
                      SEED_DEMO_DATA="false", SERVERLESS="false", TENANT_DATABASES_ENABLED="false",
                      TENANT_ALLOW_REMOTE_OPERATIONS="false", PLATFORM_DATABASE_URL="",
                      STORAGE_BACKEND="local", UPLOAD_DIR=str(data / "uploads"),
                      BACKEND_CORS_ORIGINS=json.dumps([url]),
                      EMAIL_WORKER_ENABLED="false", ACCOUNTING_SYNC_WORKER_ENABLED="false",
                      CALENDAR_SYNC_WORKER_ENABLED="false", POWER_TELEGRAM_WORKER_ENABLED="false",
                      BUSINESSSUITE_BACKUP_SCHEDULER="false")
    backend = ROOT / "backend"
    os.chdir(backend)
    sys.path.insert(0, str(backend))
    (data / "uploads").mkdir(exist_ok=True)

    if not (data / "initialized").exists():
        from email_validator import validate_email

        email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or input("Local administrator email: ").strip()
        email = validate_email(email, check_deliverability=False).normalized
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or getpass.getpass("Local administrator password: ")
        if len(password) < 12 or len(password.encode("utf-8")) > 72:
            raise ValueError("Use at least 12 characters and at most 72 UTF-8 bytes for the password.")
        os.environ.update(BOOTSTRAP_ADMIN_EMAIL=email, BOOTSTRAP_ADMIN_PASSWORD=password)
    else:
        os.environ.update(BOOTSTRAP_ADMIN_EMAIL="", BOOTSTRAP_ADMIN_PASSWORD="")
    return url


def create_workspace(data):
    from fastapi import HTTPException, Request
    from fastapi.responses import FileResponse
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    from app.main import app
    from create_db import create_database

    create_database()
    web = ROOT / "web"
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[HOST, "localhost"])
    lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def mark_initialized(application):
        async with lifespan(application):
            membership_marker = data / "local-admin-membership-checked"
            if not membership_marker.exists():
                ensure_local_admin_membership()
                membership_marker.touch()
            (data / "initialized").touch()
            yield

    app.router.lifespan_context = mark_initialized
    # The hosted API's root is JSON. This package serves the workspace there.
    app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", None) != "/"]

    @app.get("/{path:path}", include_in_schema=False)
    async def workspace(path: str, request: Request):
        asset = (web / path).resolve()
        if (not asset.is_relative_to(web) or path.split("/", 1)[0] in {"api", "uploads"}
                or any(part.startswith(".") for part in Path(path).parts)):
            raise HTTPException(404)
        if asset.is_file() and asset != web / "index.html":
            return FileResponse(asset)
        if not path or "text/html" in request.headers.get("accept", ""):
            return FileResponse(web / "index.html", headers={"Cache-Control": "no-cache"})
        raise HTTPException(404)

    return app


def ensure_local_admin_membership():
    """Give the standalone administrator a company ownership anchor for personal records."""
    from sqlalchemy import select
    from app.access.models import AccessMembership
    from app.db.session import SessionLocal
    from app.models.company import Company
    from app.models.user import User

    with SessionLocal() as db:
        administrators = db.scalars(select(User.id).where(
            User.is_active.is_(True), User.is_superuser.is_(True)
        ).limit(2)).all()
        if len(administrators) != 1 or db.get(Company, 1) is None:
            return
        membership = db.scalar(select(AccessMembership.id).where(
            AccessMembership.user_id == administrators[0], AccessMembership.company_id == 1
        ))
        if membership is None:
            db.add(AccessMembership(user_id=administrators[0], company_id=1, active=True, is_admin=True))
            db.commit()


def open_when_ready(server, url):
    while not server.started and not server.should_exit:
        time.sleep(0.25)
    if server.started:
        webbrowser.open(url)


def run(options):
    data = options.data_dir.resolve()
    data.mkdir(parents=True, exist_ok=True)
    with (data / "runtime.lock").open("a+b") as lock, socket.socket() as listener:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError("This Windows user's local workspace is already starting or running.") from error
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((HOST, options.port))

        values = configuration(data)
        url = configure_backend(data, options, values)
        control = start_database(data, options.postgres_port, values["POSTGRES_PASSWORD"])
        try:
            import uvicorn

            app = create_workspace(data)
            server = uvicorn.Server(uvicorn.Config(
                app, host=HOST, port=options.port, proxy_headers=False, timeout_graceful_shutdown=10
            ))
            if not options.no_browser:
                Thread(target=open_when_ready, args=(server, url), daemon=True).start()
            print(f"Local Business Suite: {url}. Press Ctrl+C to stop.", flush=True)
            server.run(sockets=[listener])
            if not server.started:
                raise RuntimeError("The local API failed to start. See the errors above.")
        finally:
            subprocess.run([*control, "-m", "fast", "-w", "stop"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path,
                        default=Path(os.environ["LOCALAPPDATA"]) / "Business Suite" / "workspace")
    parser.add_argument("--port", type=int, default=15434)
    parser.add_argument("--postgres-port", type=int, default=15435)
    parser.add_argument("--no-browser", action="store_true")
    try:
        run(parser.parse_args())
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Business Suite could not start: {error}", file=sys.stderr)
        sys.exit(1)
