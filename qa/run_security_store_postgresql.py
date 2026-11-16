"""Reproduce row-lock contention in a disposable local PostgreSQL database."""
import json
import os
from pathlib import Path
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('ENVIRONMENT', 'test')
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core import request_limits as limits
from app.models.security_boundary import SecurityRateBucket as Bucket, SecurityWorkLease as Lease
import app.db.session  # Install the same transaction deadline hooks used in production.


def main():
    source = make_url(os.environ.get('SECURITY_TEST_DATABASE_URL') or settings.SQLALCHEMY_DATABASE_URI)
    assert source.get_backend_name() == 'postgresql' and source.host in {'127.0.0.1', 'localhost'}, 'Local test PostgreSQL required'
    name = 'security_store_' + uuid4().hex[:10] + '_test'
    admin = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT')
    quote = admin.dialect.identifier_preparer.quote_identifier
    with admin.connect() as connection:
        connection.exec_driver_sql('CREATE DATABASE ' + quote(name))
    engine = create_engine(source.set(database=name), pool_size=8, max_overflow=4)
    sessions = sessionmaker(bind=engine)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(security_session_factory=sessions)), state=SimpleNamespace(request_id='isolated-postgresql-proof'))
    report = {}
    now = int(time.time()); window = now // 60
    try:
        Bucket.__table__.create(engine)
        Lease.__table__.create(engine)
        # Reversed overlapping arrays previously acquired locks in caller order.
        specs = [('proof-a', 5, 60), ('proof-b', 5, 60)]
        def reservation(index):
            return limits.security_transaction(request, lambda db: limits.consume(db, specs if index % 2 else list(reversed(specs)), now=now), cleanup=False) == 0
        with ThreadPoolExecutor(max_workers=8) as workers:
            accepted = sum(workers.map(reservation, range(12)))
        assert accepted == 5
        with sessions() as db:
            assert [row.count for row in db.query(Bucket).all()] == [5, 5]
        report['reversed_multi_key_reservations'] = {'accepted': accepted, 'attempted': 12, 'overshoot': False}

        # An expired row locked by another worker must not reject active traffic.
        with sessions.begin() as db:
            db.add(Bucket(key=limits.digest('expired-proof'), window=0, count=1, expires=now-1))
        held = sessions(); held.execute(select(Bucket).where(Bucket.key == limits.digest('expired-proof')).with_for_update()).all()
        started = time.monotonic()
        limits._next_cleanup_at = 0
        assert limits.security_transaction(request, lambda db: limits.consume(db, [('cleanup-live', 10, 60)], now=now)) == 0
        elapsed = time.monotonic() - started
        assert elapsed < 0.8, 'Cleanup waited on another transaction while accepting traffic'
        held.rollback(); held.close()
        report['locked_cleanup_does_not_block_active_budget'] = True

        def lock_temporarily(table, condition, ready):
            with sessions.begin() as db:
                db.execute(select(table).where(condition).with_for_update()).all()
                ready.set(); time.sleep(0.18)

        # Timeout on the second bucket rolls back the first bucket before retry.
        names = sorted(['retry-first', 'retry-second'], key=limits.digest)
        with sessions.begin() as db:
            for value in names:
                db.add(Bucket(key=limits.digest(value), window=window, count=1, expires=now+120))
        ready = threading.Event()
        holder = threading.Thread(target=lock_temporarily, args=(Bucket, Bucket.key == limits.digest(names[1]), ready)); holder.start(); assert ready.wait(3)
        attempts = []
        def charge(db):
            attempts.append(1); db.connection().exec_driver_sql("SET LOCAL lock_timeout = '50ms'")
            return limits.consume(db, [(value, 10, 60) for value in names], now=now)
        assert limits.security_transaction(request, charge, cleanup=False) == 0
        holder.join(3); assert not holder.is_alive()
        with sessions() as db:
            counts = [db.get(Bucket, (limits.digest(value), window)).count for value in names]
        assert counts == [2, 2] and 1 < len(attempts) <= 3
        report['partial_counter_retry'] = {'attempts': len(attempts), 'counts': counts, 'charged_once': True}

        # A rolled-back attempt cannot leak the first work lease or its token.
        work = sorted(['work-first', 'work-second'], key=limits.digest)
        with sessions.begin() as db:
            db.add(Lease(key=limits.digest(work[1]), slot=0, token='expired-token', expires=now-1))
        ready = threading.Event()
        holder = threading.Thread(target=lock_temporarily, args=(Lease, Lease.key == limits.digest(work[1]), ready)); holder.start(); assert ready.wait(3)
        attempts = []
        def work_attempt(db):
            attempts.append(1); db.connection().exec_driver_sql("SET LOCAL lock_timeout = '50ms'")
            owned = [limits.acquire(db, value, 1, 120, now=now) for value in work]
            assert all(owned)
            return owned
        owned = limits.security_transaction(request, work_attempt, cleanup=False)
        holder.join(3); assert not holder.is_alive()
        with sessions() as db:
            stored = {row.key: row.token for row in db.query(Lease).all()}
        assert len(stored) == 2 and all(stored[key] == token for key, slot, token in owned) and len(attempts) > 1
        report['work_lease_retry_has_no_leaked_token'] = True
        print(json.dumps(report))
        output = ROOT / '.local/security-store-503-20261116'
        output.mkdir(parents=True, exist_ok=True)
        (output / 'postgresql-proof.json').write_text(json.dumps(report, indent=2))
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql('DROP DATABASE ' + quote(name) + ' WITH (FORCE)')
        admin.dispose()


if __name__ == '__main__':
    if '--isolated' in sys.argv:
        import socket
        import subprocess
        folder = ROOT / '.local' / ('security-store-pg-' + uuid4().hex[:10])
        folder.mkdir(parents=True)
        binaries = ROOT / '.local/postgresql/pgsql/bin'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        subprocess.run([str(binaries/'initdb.exe'), '-D', str(folder/'data'), '-U', 'security_qa', '-A', 'trust', '--no-locale', '-E', 'UTF8'], check=True, stdout=subprocess.DEVNULL, **flags)
        started = False
        try:
            subprocess.run([str(binaries/'pg_ctl.exe'), '-D', str(folder/'data'), '-l', str(folder/'server.log'), '-o', f'-h 127.0.0.1 -p {port} -c shared_buffers=16MB', '-w', 'start'], check=True, stdout=subprocess.DEVNULL, **flags)
            started = True
            result = subprocess.run([sys.executable, str(Path(__file__).resolve())], env={**os.environ, 'SECURITY_TEST_DATABASE_URL': f'postgresql+psycopg://security_qa@127.0.0.1:{port}/postgres'}, capture_output=True, text=True, **flags)
            if result.stdout: print(result.stdout.strip())
            if result.stderr: print(result.stderr.strip(), file=sys.stderr)
        finally:
            if started:
                subprocess.run([str(binaries/'pg_ctl.exe'), '-D', str(folder/'data'), '-m', 'fast', '-w', 'stop'], check=True, stdout=subprocess.DEVNULL, **flags)
        raise SystemExit(result.returncode)
    else:
        main()
