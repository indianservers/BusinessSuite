"""Real committed PostgreSQL transactions; no SQLite locks or shared ORM session."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4
import os
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.deps import get_db
from app.apps.project_management.models import PMSProject, PMSTask, PMSWorkspaceEntry
from app.models.user import User
from app.models.workflow_engine import WorkflowInstance, WorkflowAuditEvent
from tests.rich_text_test_utils import workflow_seed_scope
from tests.test_pms_transition_approvals import setup_route, request, decide, BASE


@pytest.fixture
def live(db_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Requires independent PostgreSQL transactions")
    source = db_engine.url
    assert source.host in {"127.0.0.1", "localhost"} and source.database.endswith("_test")
    db_engine.dispose()
    name = "business_suite_workflow_races_" + uuid4().hex[:10] + "_test"
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote_identifier
        connection.exec_driver_sql(f"CREATE DATABASE {quote(name)} TEMPLATE {quote(source.database)}")
    engine = create_engine(source.set(database=name), connect_args={"options": "-c timezone=UTC -c lock_timeout=5000 -c statement_timeout=10000"})
    factory = sessionmaker(bind=engine, autoflush=False)
    previous_overrides = dict(app.dependency_overrides)
    keys = ("business_os_session_factory", "business_os_close_session", "audit_session_factory", "audit_close_session", "audit_commit")
    previous_state = {key: getattr(app.state, key, None) for key in keys}
    client = TestClient(app)
    seed = factory()
    try:
        def seed_db(): yield seed
        app.dependency_overrides[get_db] = seed_db
        app.state.business_os_session_factory = lambda: seed
        app.state.business_os_close_session = False
        app.state.audit_session_factory = lambda: seed
        app.state.audit_close_session = False
        app.state.audit_commit = False
        with workflow_seed_scope(seed):
            wid, pid, tid, owner, oh, ah, member, mh, guest, gh, scheme = setup_route(client, seed)
        reviewer = seed.query(User).filter_by(email="auto-admin@test.com").one().id
        owner_id, member_id = owner.id, member.id
        seed.commit(); seed.close()
        def sessions():
            with factory() as session:
                try: yield session
                except BaseException:
                    session.rollback()
                    raise
        app.dependency_overrides[get_db] = sessions
        app.state.business_os_session_factory = factory
        app.state.business_os_close_session = True
        app.state.audit_session_factory = factory
        app.state.audit_close_session = True
        app.state.audit_commit = True
        yield SimpleNamespace(client=client, factory=factory, engine=engine, pid=pid, tid=tid,
                              wid=wid, oh=oh, ah=ah, mh=mh, reviewer=reviewer, scheme=scheme,
                              owner_id=owner_id, member_id=member_id)
    finally:
        seed.close(); client.close()
        app.dependency_overrides.clear(); app.dependency_overrides.update(previous_overrides)
        for key, value in previous_state.items(): setattr(app.state, key, value)
        engine.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE {quote(name)} WITH (FORCE)")
        admin.dispose()


def race(*calls):
    barrier = Barrier(len(calls))
    def run(call):
        barrier.wait(timeout=10)
        return call()
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = [pool.submit(run, call) for call in calls]
        return [future.result(timeout=20) for future in futures]


def approved(case):
    approval = request(case.client, case.tid, case.mh)
    result = decide(case.client, approval["steps"][0]["id"], case.ah)
    assert result.status_code == 200, result.text
    return approval


@contextmanager
def waiting_editor(case, change):
    """Hold the project lock until the contender has actually blocked in PostgreSQL."""
    with case.factory() as editor:
        editor.query(PMSProject).filter_by(id=case.pid).with_for_update(of=PMSProject).one()
        change(editor)
        editor.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            yield pool, editor


def wait_for_lock(case):
    deadline = monotonic()+5
    while monotonic() < deadline:
        with case.engine.connect() as connection:
            waiting = connection.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'")).scalar_one()
        if waiting: return
        sleep(.02)
    pytest.fail("Contender never reached the PostgreSQL lock")


@pytest.mark.parametrize("first_publication", [False, True])
def test_same_revision_publication_has_one_winner(live, first_publication):
    path = f"{BASE}/projects/{live.pid}/workflow-scheme"
    revision = 0 if first_publication else 1
    if first_publication:
        with live.factory() as db:
            db.query(PMSWorkspaceEntry).filter_by(workspace_id=live.wid, kind=f"wf{live.pid:x}").delete()
            db.commit()
    save = lambda: live.client.put(path, headers=live.oh, json={**live.scheme, "revision": revision})
    responses = race(save, save)
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    assert live.client.get(path, headers=live.oh).json()["revision"] == revision+1
    with live.factory() as db:
        assert db.query(PMSWorkspaceEntry).filter_by(workspace_id=live.wid, kind=f"wf{live.pid:x}").count() == 1


def test_concurrent_requests_reuse_one_instance(live):
    post = lambda: live.client.post(f"{BASE}/tasks/{live.tid}/transition-approvals", headers=live.mh, json={"target": "Done"})
    responses = race(post, post)
    assert [r.status_code for r in responses] == [201, 201], [r.text for r in responses]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    with live.factory() as db:
        assert db.query(WorkflowInstance).filter_by(entity_id=live.tid, entity_type="pms_transition").count() == 1


def test_competing_decisions_record_only_one_decision(live):
    approval = request(live.client, live.tid, live.mh)
    step = approval["steps"][0]["id"]
    responses = race(lambda: decide(live.client, step, live.ah), lambda: decide(live.client, step, live.ah, "reject"))
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    with live.factory() as db:
        assert db.query(WorkflowAuditEvent).filter(WorkflowAuditEvent.instance_id == approval["id"], WorkflowAuditEvent.event_type.in_(["task_approved", "task_rejected"])).count() == 1


def test_double_application_spends_one_grant(live):
    approval = approved(live)
    patch = lambda: live.client.patch(f"{BASE}/tasks/{live.tid}", headers=live.mh, json={"status": "Done"})
    responses = race(patch, patch)
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    with live.factory() as db:
        assert db.get(PMSTask, live.tid).status == "Done"
        assert db.get(WorkflowInstance, approval["id"]).status == "Applied"
        assert db.query(WorkflowAuditEvent).filter_by(instance_id=approval["id"], event_type="transition_applied").count() == 1


def test_review_rechecks_task_after_waiting_for_an_editor(live):
    approval = request(live.client, live.tid, live.mh)
    def change(db): db.get(PMSTask, live.tid).description = "Changed during review lock wait"
    with waiting_editor(live, change) as (pool, editor):
        future = pool.submit(decide, live.client, approval["steps"][0]["id"], live.ah)
        wait_for_lock(live); editor.commit()
        response = future.result(timeout=15)
    assert response.status_code == 409, response.text


def test_bulk_rechecks_task_after_waiting_for_an_editor(live):
    approval = approved(live)
    def change(db): db.get(PMSTask, live.tid).description = "Changed during bulk lock wait"
    with waiting_editor(live, change) as (pool, editor):
        future = pool.submit(live.client.patch, BASE+"/tasks/bulk", headers=live.mh,
                             json={"task_ids": [live.tid], "status": "Done"})
        wait_for_lock(live); editor.commit()
        response = future.result(timeout=15)
    assert response.status_code == 409, response.text
    with live.factory() as db:
        assert db.get(PMSTask, live.tid).status == "To Do"
        assert db.get(WorkflowInstance, approval["id"]).status == "Approved"


def test_review_rechecks_suspension_after_lock_wait(live):
    approval = request(live.client, live.tid, live.mh)
    def change(db): db.get(User, live.reviewer).is_active = False
    with waiting_editor(live, change) as (pool, editor):
        future = pool.submit(decide, live.client, approval["steps"][0]["id"], live.ah)
        wait_for_lock(live); editor.commit()
        response = future.result(timeout=15)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("operation", ["direct", "bulk", "board", "request", "publish"])
def test_application_rechecks_requester_suspension_after_lock_wait(live, operation):
    approval = approved(live)
    actor_id = live.owner_id if operation == "publish" else live.member_id
    headers = live.oh if operation == "publish" else live.mh
    if operation == "board":
        board = live.client.get(f"{BASE}/projects/{live.pid}/board", headers=live.mh).json()
        done = next(c for c in board["columns"] if c["status_key"] == "DONE")
    def action():
        if operation == "bulk":
            return live.client.patch(BASE+"/tasks/bulk", headers=headers, json={"task_ids": [live.tid], "status": "Done"})
        if operation == "board":
            return live.client.post(f"{BASE}/projects/{live.pid}/board/reorder", headers=headers,
                                    json={"task_id": live.tid, "column_id": done["id"], "position": 0})
        if operation == "request":
            return live.client.post(f"{BASE}/tasks/{live.tid}/transition-approvals", headers=headers, json={"target": "Done"})
        if operation == "publish":
            return live.client.put(f"{BASE}/projects/{live.pid}/workflow-scheme", headers=headers, json={**live.scheme, "revision": 1})
        return live.client.patch(f"{BASE}/tasks/{live.tid}", headers=headers, json={"status": "Done"})
    def change(db): db.get(User, actor_id).is_active = False
    with waiting_editor(live, change) as (pool, editor):
        future = pool.submit(action)
        wait_for_lock(live); editor.commit()
        response = future.result(timeout=15)
    assert response.status_code == 403, response.text
    with live.factory() as db:
        assert db.get(PMSTask, live.tid).status == "To Do"
        assert db.get(WorkflowInstance, approval["id"]).status == "Approved"


def reset_policy(case):
    response = case.client.put(f"{BASE}/projects/{case.pid}/workflow-scheme", headers=case.oh,
                               json={"revision": 1, "enabled": False, "transitions": []})
    assert response.status_code == 200, response.text


@pytest.mark.skipif(os.environ.get("RUN_PMS_WORKFLOW_BROWSER") != "1", reason="Explicit PostgreSQL browser acceptance")
def test_postgresql_browser_type_overrides(live):
    from tests.workflow_browser_utils import run_browser
    reset_policy(live)
    bug = live.client.post(f"{BASE}/projects/{live.pid}/tasks", headers=live.mh,
                           json={"title": "Browser bug", "task_key": "PG-BUG", "work_type": "Bug"})
    assert bug.status_code == 200, bug.text
    with live.factory() as db:
        run_browser(live.client, db, "test-workflow-schemes.cjs", {
            "WORKFLOW_TEST_TOKEN": live.oh["Authorization"].split(" ", 1)[1],
            "WORKFLOW_TEST_PROJECT": str(live.pid), "WORKFLOW_TEST_TASK": str(live.tid),
            "WORKFLOW_TEST_ASSIGNEE": str(live.member_id), "WORKFLOW_TEST_BUG_TASK": str(bug.json()["id"])})


@pytest.mark.skipif(os.environ.get("RUN_PMS_WORKFLOW_BROWSER") != "1", reason="Explicit PostgreSQL browser acceptance")
def test_postgresql_browser_approval_route(live):
    from tests.workflow_browser_utils import run_browser
    reset_policy(live)
    actors = {"owner": {"id": live.owner_id, "token": live.oh["Authorization"].split(" ", 1)[1]},
              "requester": {"id": live.member_id, "token": live.mh["Authorization"].split(" ", 1)[1]},
              "reviewer": {"id": live.reviewer, "token": live.ah["Authorization"].split(" ", 1)[1]}}
    with live.factory() as db:
        run_browser(live.client, db, "test-transition-approvals.cjs", {"WORKFLOW_TEST_ACTORS": json.dumps(actors),
                    "WORKFLOW_TEST_PROJECT": str(live.pid), "WORKFLOW_TEST_TASK": str(live.tid)})


def test_production_mode_runtime_workflow(live, tmp_path):
    """Real production-configured process with startup enabled, on a cloned test DB."""
    import socket
    import subprocess
    import sys
    from pathlib import Path
    import httpx
    listener = socket.socket(); listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]; listener.close()
    env = {**os.environ, "DATABASE_URL": live.engine.url.render_as_string(hide_password=False),
           "PLATFORM_DATABASE_URL": "",
           "TENANT_DATABASES_ENABLED": "false", "TENANT_REGISTRY_URL": "",
           "TENANT_PROVISIONING_URL": "", "TENANT_ALLOW_REMOTE_OPERATIONS": "false",
           "ENVIRONMENT": "production", "DEBUG": "false", "SERVERLESS": "false",
           "DATABASE_AUTO_MIGRATE": "false", "SEED_DEMO_DATA": "false",
           "BACKEND_CORS_ORIGINS": '["https://workflow-acceptance.example.test"]',
           "FRONTEND_PUBLIC_URL": "https://workflow-acceptance.example.test",
           "BACKEND_PUBLIC_URL": "https://workflow-api.example.test",
           "STORAGE_BACKEND": "local", "UPLOAD_DIR": str(tmp_path / "uploads")}
    log = tmp_path / "production-runtime.log"
    with log.open("w") as output:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=Path(__file__).resolve().parents[1], env=env, stdout=output, stderr=output,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=15) as http:
                deadline = monotonic()+45
                while monotonic() < deadline:
                    if process.poll() is not None: pytest.fail("Production runtime exited: " + log.read_text())
                    try:
                        health = http.get("/health")
                        if health.status_code == 200: break
                    except httpx.TransportError: pass
                    sleep(.2)
                else: pytest.fail("Production startup timed out: " + log.read_text())
                assert health.json()["environment"] == "production" and health.json()["db"] == "ok"
                inbox = f"{BASE}/transition-approvals/inbox"
                assert http.get(inbox).status_code in [401, 403]
                approval = http.post(f"{BASE}/tasks/{live.tid}/transition-approvals", headers=live.mh, json={"target": "Done"})
                assert approval.status_code == 201, approval.text
                review_id = approval.json()["steps"][0]["id"]
                assert http.get(inbox, headers=live.ah).json()[0]["task_id"] == live.tid
                reviewed = http.put(f"/api/v1/workflow-engine/tasks/{review_id}/approve", headers=live.ah, json={"reason": "Production-mode acceptance"})
                assert reviewed.status_code == 200, reviewed.text
                applied = http.patch(f"{BASE}/tasks/{live.tid}", headers=live.mh, json={"status": "Done"})
                assert applied.status_code == 200, applied.text
                assert applied.json()["status"] == "Done"
        finally:
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=10)
