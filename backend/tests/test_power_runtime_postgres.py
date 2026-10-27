"""Real PostgreSQL sessions/processes, with an isolated schema in the guarded test DB."""

import concurrent.futures
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import timedelta
import pytest
from sqlalchemy import create_engine, text, event, func
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.apps.power_apps.runtime import now, claim, process, lifecycle, enqueue
from app.apps.power_apps.runtime_models import (
    AutomationJob as Job,
    AutomationRun as Run,
    AutomationStep as Step,
)
from app.apps.power_apps.models import (
    PowerResource,
    PowerVersion,
    PowerExecution,
    PowerEnvironment,
)
from tests.test_power_studio import node, edge


@pytest.fixture
def durable_store(db_engine):
    url = db_engine.url
    if url.get_backend_name() != "postgresql":
        pytest.skip(
            "Real PostgreSQL is required for multi-process locking and load measurements"
        )
    if not (url.database or "").startswith(
        "business_suite_"
    ) or not url.database.endswith("_test"):
        raise RuntimeError("An isolated business_suite_*_test database is required")
    schema = "power_runtime_it_" + uuid.uuid4().hex
    with db_engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    target = url.set(
        query={**url.query, "options": f"-csearch_path={schema} -ctimezone=UTC"}
    )
    engine = create_engine(target, pool_size=12, max_overflow=4, hide_parameters=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    from app.models.company import Company
    from app.models.user import User, Role, Permission
    from app.common.models import CommonPerson
    from app.apps.power_apps.registry import PERMISSIONS

    with factory() as db:
        db.add(Company(id=101, name="Runtime isolated load company", is_active=True))
        db.flush()
        role = Role(
            name="runtime_load",
            permissions=[Permission(name=p, module="power_apps") for p in PERMISSIONS],
        )
        db.add(role)
        db.flush()
        user = User(
            email="runtime-load@example.invalid",
            hashed_password="unused",
            is_active=True,
            role=role,
            person=CommonPerson(
                organization_id=101,
                primary_email="runtime-load@example.invalid",
                display_name="Runtime load actor",
            ),
        )
        db.add(user)
        db.flush()
        db.add(PowerEnvironment(organization_id=101, key="testing", enabled=True))
        db.commit()
        user_id = user.id
    yield factory, target, user_id, engine
    engine.dispose()
    # Literal generated schema on the previously verified disposable test database only.
    with db_engine.begin() as conn:
        conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')


def prepare(factory, user_id, multi=True):
    from app.models.user import User
    from app.apps.power_apps.graph import VisualWorkflowDefinition

    with factory() as db:
        user = db.get(User, user_id)
        user.organization_id = 101
        nodes = [node("start", "manual_trigger")]
        edges = []
        if multi:
            nodes += [
                node("set", "set_variable", value=42),
                node("log", "log_event", message="Load done"),
            ]
            edges = [edge("start", "set"), edge("set", "log")]
        for i, n in enumerate(nodes):
            n["position"] = {"x": i * 300, "y": 100}
        graph = VisualWorkflowDefinition.model_validate(
            {"schema_version": 2, "nodes": nodes, "edges": edges}
        ).model_dump()
        row = PowerResource(
            organization_id=101,
            environment="testing",
            application_id="automations",
            owner_user_id=user_id,
            name="Durability / controlled load",
            description="",
            status="draft",
            version=1,
            definition=graph,
        )
        db.add(row)
        db.flush()
        db.add(
            PowerVersion(
                organization_id=101,
                resource_id=row.id,
                owner_user_id=user_id,
                version=1,
                created_by=user_id,
                snapshot={
                    "definition": graph,
                    "name": row.name,
                    "description": "",
                    "status": "draft",
                },
            )
        )
        db.flush()
        for action in ["validate", "publish", "activate"]:
            lifecycle(db, row, user, action, 1, {"concurrency": 20, "max_queued": 1000})
        db.commit()
        return row.id


def enqueue_many(factory, user_id, resource_id, count, prefix):
    from app.models.user import User

    ids = []
    for index in range(count):
        with factory() as db:
            user = db.get(User, user_id)
            user.organization_id = 101
            row = db.get(PowerResource, resource_id)
            root = enqueue(db, row, user, {}, f"{prefix}:{index:06}")
            ids.append(root.id)
            db.commit()
    return ids


def drain_worker(factory, label, results):
    deadline = time.monotonic() + 900
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("Controlled load batch exceeded 15 minutes")
        with factory() as db:
            work = claim(db, label)
            if work:
                outcome = process(db, *work)
                results.append((work[0], work[1], outcome))
                continue
            pending = (
                db.query(Job).filter(Job.status.in_(["queued", "running"])).count()
            )
            if not pending:
                return
        time.sleep(0.02)


def test_real_worker_process_crash_and_recovery(durable_store, tmp_path):
    factory, url, user_id, engine = durable_store
    resource_id = prepare(factory, user_id)
    run_id = enqueue_many(factory, user_id, resource_id, 1, "crash")[0]
    marker = tmp_path / "executor-entered.txt"
    source = """import os,time
from pathlib import Path
from app.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
SessionLocal=sessionmaker(bind=create_engine(os.environ["DATABASE_URL"]))
from app.apps.power_apps.runtime import claim,process
from app.apps.power_apps.runtime_executors import Executor
original=Executor.execute
def blocked(self,node,config,payload,previous):
    Path(os.environ['POWER_CRASH_MARKER']).write_text('entered')
    time.sleep(60)
    return original(self,node,config,payload,previous)
Executor.execute=blocked
with SessionLocal() as db:
    work=claim(db,'crash-process')
    process(db,*work)
"""
    env = dict(
        os.environ,
        DATABASE_URL=url.render_as_string(hide_password=False),
        POWER_CRASH_MARKER=str(marker),
        ENVIRONMENT="test",
    )
    backend = Path(__file__).resolve().parents[1]
    child = subprocess.Popen(
        [sys.executable, "-u", "-c", source],
        cwd=backend,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        deadline = time.monotonic() + 30
        while (
            not marker.exists() and time.monotonic() < deadline and child.poll() is None
        ):
            time.sleep(0.1)
        if not marker.exists():
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
            diagnostic = child.stderr.read().decode(errors="replace")[-4000:]
            raise AssertionError("The isolated executor did not start: " + diagnostic)
        recovery_start = time.perf_counter()
        child.kill()
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
    with factory() as db:
        assert db.get(PowerExecution, run_id).status == "running"
        assert (
            db.query(Step).filter_by(run_id=run_id, node_id="start").one().output
            is None
        )
        job = db.query(Job).filter_by(run_id=run_id, status="running").one()
        job.lease_until = now() - timedelta(seconds=1)
        db.commit()
    replacement = subprocess.run(
        [
            sys.executable,
            "-c",
            'import os,sys; from sqlalchemy import create_engine; from sqlalchemy.orm import sessionmaker; from app.apps.power_apps import worker; worker.SessionLocal=sessionmaker(bind=create_engine(os.environ["DATABASE_URL"])); sys.argv=["worker","--once"]; worker.main()',
        ],
        cwd=backend,
        env=env,
        capture_output=True,
        timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert replacement.returncode == 0, "Replacement worker failed"
    with factory() as db:
        assert (
            db.query(Step).filter_by(run_id=run_id, node_id="start").one().status
            == "completed"
        )
    results = []
    drain_worker(factory, "recovery-completion", results)
    with factory() as db:
        assert db.get(PowerExecution, run_id).status == "completed"
        steps = db.query(Step).filter_by(run_id=run_id).all()
        assert len(steps) == 3 and all(
            s.attempt == (2 if s.node_id == "start" else 1) for s in steps
        )
        assert (
            db.query(Job)
            .filter_by(run_id=run_id)
            .with_entities(func.sum(Job.claims))
            .scalar()
            == 4
        )
        target = (
            Path(__file__).resolve().parents[2] / ".tmp/power-runtime-recovery.json"
        )
        target.write_text(
            json.dumps(
                {
                    "database": "isolated local PostgreSQL",
                    "crash_during_handler": True,
                    "uncommitted_output_survived": False,
                    "recovery_seconds": time.perf_counter() - recovery_start,
                    "recovery_lease": "expired explicitly to avoid waiting 30 seconds in the test",
                    "claims": 4,
                    "attempts": {step.node_id: step.attempt for step in steps},
                    "final_status": db.get(PowerExecution, run_id).status,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def rss_bytes():
    if os.name != "nt":
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

    class Memory(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    stats = Memory()
    stats.cb = ctypes.sizeof(stats)
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(Memory),
        ctypes.c_ulong,
    ]
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        handle, ctypes.byref(stats), stats.cb
    ):
        return None
    return stats.WorkingSetSize


def test_controlled_postgres_load_and_concurrent_leases(durable_store):
    factory, url, user_id, engine = durable_store
    measurements = []
    queries = {"count": 0, "seconds": 0.0}

    @event.listens_for(engine, "before_cursor_execute")
    def before(conn, cursor, statement, parameters, context, many):
        context._power_clock = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after(conn, cursor, statement, parameters, context, many):
        queries["count"] += 1
        queries["seconds"] += time.perf_counter() - context._power_clock

    for size in [10, 50, 100, 500, 1000]:
        resource_id = prepare(factory, user_id, multi=size <= 100)
        before_queries = dict(queries)
        memory_before = rss_bytes()
        begin = time.perf_counter()
        cpu = time.process_time()
        ids = enqueue_many(factory, user_id, resource_id, size, f"load-{size}")
        enqueue_seconds = time.perf_counter() - begin
        results = []
        work_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [
                pool.submit(drain_worker, factory, f"load-worker-{i}", results)
                for i in range(8)
            ]
            for future in futures:
                future.result(timeout=900)
        processing_seconds = time.perf_counter() - work_start
        with factory() as db:
            roots = db.query(PowerExecution).filter(PowerExecution.id.in_(ids)).all()
            assert len(roots) == size and all(r.status == "completed" for r in roots)
            steps = db.query(Step).filter(Step.run_id.in_(ids)).all()
            assert len(steps) == size * (3 if size <= 100 else 1)
            assert all(s.attempt == 1 for s in steps)
            run_states = db.query(Run).filter(Run.id.in_(ids)).all()
            waits = sorted(
                (
                    r.started_at
                    - next(root.created_at for root in roots if root.id == r.id)
                ).total_seconds()
                for r in run_states
            )
            failures = sum(r.status == "failed" for r in roots)
        assert len({job for job, token, status in results}) == len(results)
        measurements.append(
            {
                "queued_runs": size,
                "workers": 8,
                "steps_per_run": 3 if size <= 100 else 1,
                "enqueue_seconds": enqueue_seconds,
                "processing_seconds": processing_seconds,
                "runs_per_second": size / processing_seconds,
                "queue_wait_mean_seconds": sum(waits) / size,
                "queue_wait_p95_seconds": waits[int((size - 1) * 0.95)],
                "query_count": queries["count"] - before_queries["count"],
                "query_wall_seconds": queries["seconds"] - before_queries["seconds"],
                "worker_cpu_seconds": time.process_time() - cpu,
                "rss_before_bytes": memory_before,
                "rss_after_bytes": rss_bytes(),
                "error_rate": failures / size,
                "retries": 0,
            }
        )
        target = Path(__file__).resolve().parents[2] / ".tmp/power-runtime-load.json"
        target.write_text(
            json.dumps(
                {
                    "database": "isolated local PostgreSQL",
                    "measurements": measurements,
                    "limits": {
                        "tenant_active_runs": 20,
                        "environment_active_runs": 10,
                        "environment_leases": 10,
                    },
                    "qualification": "Local synthetic logic measurements; not a production capacity guarantee. Worker process RSS/CPU and client query wall time are measured; database server CPU is not measured.",
                },
                indent=2,
            )
        )
