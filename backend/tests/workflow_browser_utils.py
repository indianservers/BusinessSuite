"""Launch browser checks against the fixture app, never a developer database."""
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path
import uvicorn
from tempfile import TemporaryDirectory
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.deps import get_db


def run_browser(client, db, script, values, *, timeout_seconds=120):
    # Real browsers issue concurrent reads. Give each request its own session,
    # using a file-backed copy of the fixture rather than sharing its ORM session.
    temporary = TemporaryDirectory(prefix="pms-workflow-browser-")
    source_engine = db.get_bind().engine
    engine = source_engine
    if source_engine.dialect.name == "sqlite":
        path = Path(temporary.name) / "browser.db"
        # serialize includes fixture changes held in its enclosing transaction.
        db.flush()
        path.write_bytes(db.connection().connection.driver_connection.serialize())
        engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, autoflush=False)
    previous_dependency = client.app.dependency_overrides[get_db]
    names = ("business_os_session_factory", "business_os_close_session", "audit_session_factory", "audit_close_session", "audit_commit")
    previous = {name: getattr(client.app.state, name, None) for name in names}
    def sessions():
        with factory() as session:
            try:
                yield session
            except BaseException:
                session.rollback()
                raise
    client.app.dependency_overrides[get_db] = sessions
    client.app.state.business_os_session_factory = factory
    client.app.state.business_os_close_session = True
    client.app.state.audit_session_factory = factory
    client.app.state.audit_close_session = True
    client.app.state.audit_commit = True
    sock = socket.socket(); sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(client.app, lifespan="off", log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started: break
            time.sleep(0.05)
        assert server.started
        env = {**os.environ, "WORKFLOW_TEST_ORIGIN": f"http://127.0.0.1:{port}",
               "WORKFLOW_TEST_CACHE": str(Path(temporary.name) / "vite-cache"), **values}
        result = subprocess.run(["node", f"scripts/{script}"],
                                cwd=Path(__file__).resolve().parents[2] / "frontend",
                                env=env, capture_output=True, text=True, timeout=timeout_seconds)
        detail = re.sub(r"Bearer [A-Za-z0-9._-]+", "Bearer [fixture token]", result.stdout + result.stderr)
        assert result.returncode == 0, f"Browser runner exited {result.returncode}\n" + detail
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        client.app.dependency_overrides[get_db] = previous_dependency
        for name, value in previous.items():
            setattr(client.app.state, name, value)
        if engine is not source_engine:
            engine.dispose()
        temporary.cleanup()
