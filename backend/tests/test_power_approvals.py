import pytest
from app.models.user import User
from tests.test_power_runtime import db, drain
from tests.test_power_apps import actors


@pytest.fixture(autouse=True)
def approval_actor_actions(request):
    if "actors" not in request.fixturenames:
        return
    db = request.getfixturevalue("db")
    request.getfixturevalue("actors")
    from app.access.models import AccessPolicy
    import copy

    user = db.query(User).filter_by(email="power-3@example.com").one()
    row = db.query(AccessPolicy).filter_by(user_id=user.id).one()
    grants = copy.deepcopy(row.grants)
    grants["power_apps"]["actions"] += ["approve", "assign"]
    row.grants = grants
    db.commit()


ROOT = "/api/v1/power-apps/approvals"


def users(db):
    return [
        db.query(User).filter_by(email=f"power-{i}@example.com").one().id
        for i in range(5)
    ]


def policy(client, h, ids, mode="all", stages=1, **config):
    d = {
        "stages": [
            {
                "id": f"review{i}",
                "name": f"Review {i+1}",
                "mode": mode,
                "selectors": [{"kind": "user", "ids": ids}],
                **config,
            }
            for i in range(stages)
        ],
        "fields": [
            {"key": "amount", "label": "Amount", "kind": "number", "required": True}
        ],
    }
    r = client.post(
        ROOT + "/policies",
        headers=h,
        json={"name": "Isolated purchase", "definition": d},
    )
    assert r.status_code == 201, r.text
    p = r.json()
    r = client.post(
        f'{ROOT}/policies/{p["id"]}/activate', headers=h, params={"expected_version": 1}
    )
    assert r.status_code == 200, r.text
    return p


def submit(client, h, p, key="approval-request-001"):
    r = client.post(
        ROOT + "/requests",
        headers=h,
        json={
            "policy_id": p["id"],
            "title": "Fixture purchase",
            "fields": {"amount": 42},
            "request_key": key,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def detail(client, h, r):
    d = client.get(f'{ROOT}/requests/{r["id"]}', headers=h)
    assert d.status_code == 200, d.text
    return d.json()


def decide(client, h, r, decision="approve", reason="", assignment=None):
    d = detail(client, h, r)
    a = assignment or next(a for a in d["assignments"] if a["can_decide"])
    return client.post(
        f'{ROOT}/requests/{r["id"]}/decisions',
        headers=h,
        json={
            "assignment_id": a["id"],
            "expected_revision": d["state"]["revision"],
            "decision": decision,
            "reason": reason,
            "request_key": f'decision-{a["id"]}-{decision}',
        },
    )


def test_simple_wait_and_resume(client, db, actors):
    ids = users(db)
    p = policy(client, actors[0], [ids[3]])
    r = submit(client, actors[0], p)
    drain(db)
    assert detail(client, actors[3], r)["assignments"][0]["can_decide"]
    response = decide(client, actors[3], r)
    assert response.status_code == 200, response.text
    drain(db)
    final = detail(client, actors[0], r)
    assert final["status"] == "Approved"
    assert final["evidence_valid"]
    assert (
        client.get(
            f'/api/v1/approval-os/requests/{r["id"]}', headers=actors[0]
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "mode,needed", [("all", 2), ("any", 1), ("majority", 2), ("quorum", 1)]
)
def test_parallel_rules(client, db, actors, mode, needed):
    ids = users(db)
    db.get(User, ids[2]).role_id = db.get(User, ids[0]).role_id
    db.commit()
    p = policy(client, actors[0], [ids[2], ids[3]], mode, quorum=1)
    r = submit(client, actors[0], p)
    drain(db)
    response = decide(client, actors[2], r)
    assert response.status_code == 200, response.text
    if needed == 2:
        assert detail(client, actors[0], r)["status"] == "Pending"
        response = decide(client, actors[3], r)
        assert response.status_code == 200, response.text
    drain(db)
    assert detail(client, actors[0], r)["status"] == "Approved"


def test_rejection_and_security(client, db, actors):
    ids = users(db)
    p = policy(client, actors[0], [ids[3]], stages=3)
    r = submit(client, actors[0], p)
    drain(db)
    assert len(detail(client, actors[0], r)["assignments"]) == 1
    assert (
        client.get(f'{ROOT}/requests/{r["id"]}', headers=actors[1]).status_code == 404
    )
    a = detail(client, actors[0], r)["assignments"][0]
    assert decide(client, actors[0], r, assignment=a).status_code == 403
    assert decide(client, actors[3], r, "reject").status_code == 422
    response = decide(client, actors[3], r, "reject", "Insufficient evidence")
    assert response.status_code == 200, response.text
    assert detail(client, actors[0], r)["status"] == "Rejected"


def test_changes_resubmit(client, db, actors):
    ids = users(db)
    p = policy(client, actors[0], [ids[3]])
    r = submit(client, actors[0], p)
    drain(db)
    response = decide(client, actors[3], r, "changes", "Add estimate")
    assert response.status_code == 200, response.text
    d = detail(client, actors[0], r)
    assert d["status"] == "Changes Requested"
    response = client.post(
        f'{ROOT}/requests/{r["id"]}/resubmit',
        headers=actors[0],
        json={
            "expected_revision": d["state"]["revision"],
            "fields": {"amount": 50},
            "reason": "Added estimate",
        },
    )
    assert response.status_code == 200, response.text
    drain(db)
    response = decide(client, actors[3], r)
    assert response.status_code == 200, response.text
    drain(db)
    d = detail(client, actors[0], r)
    assert d["status"] == "Approved"
    assert len(d["assignments"]) == 2
    assert d["evidence_valid"]


def test_three_stages_activate_only_in_order(client, db, actors):
    ids = users(db)
    p = policy(client, actors[0], [ids[3]], stages=3)
    r = submit(client, actors[0], p)
    drain(db)
    for stage in range(3):
        d = detail(client, actors[3], r)
        assert len(d["assignments"]) == stage + 1
        response = decide(client, actors[3], r)
        assert response.status_code == 200, response.text
        drain(db)
    assert detail(client, actors[0], r)["status"] == "Approved"


def test_generic_resume_cannot_bypass_approval_and_cancel_closes_wait(
    client, db, actors
):
    ids = users(db)
    p = policy(client, actors[0], [ids[3]])
    r = submit(client, actors[0], p)
    drain(db)
    d = detail(client, actors[0], r)
    response = client.post(
        f'/api/v1/power-apps/executions/{d["state"]["run_id"]}/resume',
        headers=actors[0],
        json={"event_key": f'approval:{r["id"]}'},
    )
    assert response.status_code == 404, response.text
    response = client.post(
        f'{ROOT}/requests/{r["id"]}/cancel',
        headers=actors[0],
        json={
            "expected_revision": d["state"]["revision"],
            "reason": "No longer needed",
        },
    )
    assert response.status_code == 200, response.text
    assert not any(a["can_decide"] for a in detail(client, actors[3], r)["assignments"])


def test_signed_evidence_and_completed_seats_are_immutable(client, db, actors):
    from app.models.approval_os import ApprovalHistory

    ids = users(db)
    p = policy(client, actors[0], [ids[3]])
    r = submit(client, actors[0], p)
    drain(db)
    assert decide(client, actors[3], r).status_code == 200
    drain(db)
    with pytest.raises(ValueError), db.begin_nested():
        item = db.query(ApprovalHistory).filter_by(request_id=r["id"]).first()
        item.reason = "tampered"
        db.flush()


def test_delegation_authority_and_expiry(client, db, actors):
    from datetime import timedelta
    from app.apps.power_apps.runtime import now
    from app.apps.power_apps.approvals.models import Delegation

    ids = users(db)
    db.get(User, ids[2]).role_id = db.get(User, ids[0]).role_id
    db.commit()
    response = client.post(
        ROOT + "/delegations",
        headers=actors[3],
        json={
            "alternate_user_id": ids[2],
            "starts_at": (now() - timedelta(hours=1)).isoformat(),
            "ends_at": (now() + timedelta(hours=1)).isoformat(),
            "reason": "Temporary absence",
        },
    )
    assert response.status_code == 201, response.text
    p = policy(client, actors[0], [ids[3]], allow_delegation=True)
    r = submit(client, actors[0], p)
    drain(db)
    d = detail(client, actors[2], r)
    assert d["assignments"][0]["original_user_id"] == ids[3]
    assert d["assignments"][0]["user_id"] == ids[2]
    response = decide(client, actors[2], r)
    assert response.status_code == 200, response.text


def test_conditional_stage_uses_existing_safe_rules(client, db, actors):
    ids = users(db)
    p = policy(
        client,
        actors[0],
        [ids[3]],
        when={
            "rules": [
                {
                    "left": "{{trigger.input.fields.amount}}",
                    "operator": "greater_than",
                    "right": 100,
                }
            ]
        },
    )
    r = submit(client, actors[0], p)
    drain(db)
    d = detail(client, actors[0], r)
    assert d["status"] == "Approved"
    assert d["assignments"] == []


def test_private_document_hash_and_tenant_boundary(
    client, db, actors, tmp_path, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    ids = users(db)
    p = policy(client, actors[0], [ids[3]])
    r = submit(client, actors[0], p)
    response = client.post(
        f'{ROOT}/requests/{r["id"]}/attachments',
        headers=actors[0],
        files={"file": ("estimate.txt", b"Verifiable estimate: 42", "text/plain")},
    )
    assert response.status_code == 201, response.text
    file_id = response.json()["id"]
    drain(db)
    path = f'{ROOT}/requests/{r["id"]}/attachments/{file_id}'
    response = client.get(path, headers=actors[3])
    assert response.status_code == 200
    assert response.content == b"Verifiable estimate: 42"
    assert client.get(path, headers=actors[1]).status_code == 404
    assert "storage_path" not in str(detail(client, actors[0], r))


def test_reminder_escalation_and_expiration_use_runtime_tick(
    client, db, actors, monkeypatch
):
    from datetime import timedelta
    from app.apps.power_apps.runtime import tick, now
    from app.apps.power_apps.approvals import service
    from app.models.approval_os import ApprovalHistory

    ids = users(db)
    p = policy(
        client,
        actors[0],
        [ids[3]],
        sla_seconds=60,
        remind_after_seconds=30,
        expire_after_seconds=120,
    )
    r = submit(client, actors[0], p)
    drain(db)
    initial = now()
    for seconds in [35, 65, 130]:
        with monkeypatch.context() as patch:
            patch.setattr(
                "app.apps.power_apps.runtime.now",
                lambda: initial + timedelta(seconds=seconds),
            )
            patch.setattr(service, "now", lambda: initial + timedelta(seconds=seconds))
            tick(db)
    d = detail(client, actors[0], r)
    assert d["status"] == "Expired"
    assert sum(h["event_type"] == "reminder" for h in d["history"]) == 1
    assert sum(h["event_type"] == "escalated" for h in d["history"]) == 1
    assert all(a["status"] == "closed" for a in d["assignments"])


# Real independent PostgreSQL transactions verify serialization, not just sequential mocks.
from tests.test_power_runtime_postgres import durable_store


def test_concurrent_any_one_decisions_have_one_winner(durable_store):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException
    from app.common.models import CommonPerson
    from app.apps.power_apps.approvals import api as routes, service
    from app.apps.power_apps.approvals.contracts import PolicyWrite, Submit, Decision
    from app.apps.power_apps.approvals.models import RequestState, Assignment
    from app.models.approval_os import ApprovalRequest, ApprovalHistory

    factory, target, owner_id, engine = durable_store

    def worker_process():
        import os, sys, subprocess
        from pathlib import Path

        source = """import os
from app.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.apps.power_apps.runtime import claim,process
factory=sessionmaker(bind=create_engine(os.environ['DATABASE_URL']))
while True:
    with factory() as db:
        work=claim(db,'approval-restart-process')
        if not work:break
        process(db,*work)
"""
        result = subprocess.run(
            [sys.executable, "-c", source],
            cwd=Path(__file__).resolve().parents[1],
            env={
                **os.environ,
                "DATABASE_URL": target.render_as_string(hide_password=False),
                "ENVIRONMENT": "test",
            },
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert result.returncode == 0, result.stderr[-2000:]

    with factory() as db:
        owner = db.get(User, owner_id)
        owner.organization_id = 101
        reviewers = []
        for i in range(2):
            reviewer = User(
                email=f"approver-{i}@isolated.invalid",
                hashed_password="unused",
                is_active=True,
                role_id=owner.role_id,
                person=CommonPerson(
                    organization_id=101,
                    primary_email=f"approver-{i}@isolated.invalid",
                    display_name=f"Approver {i}",
                ),
            )
            db.add(reviewer)
            db.flush()
            reviewers.append(reviewer.id)
        db.commit()
        p = routes.create_policy(
            PolicyWrite(
                name="Concurrent any-one",
                definition={
                    "stages": [
                        {
                            "id": "review",
                            "name": "Review",
                            "mode": "any",
                            "selectors": [{"kind": "user", "ids": reviewers}],
                        }
                    ]
                },
            ),
            "testing",
            db,
            owner,
        )
        routes.activate(p["id"], 1, "testing", db, owner)
        r = routes.submit(
            Submit(
                policy_id=p["id"],
                title="Concurrent request",
                request_key="concurrent-request",
            ),
            "testing",
            db,
            owner,
        )
        db.commit()
        worker_process()
        db.expire_all()
        state = db.get(RequestState, r["id"])
        revision = state.revision
        assignments = {
            a.user_id: a.id for a in db.query(Assignment).filter_by(request_id=r["id"])
        }
    barrier = Barrier(2)

    def vote(uid):
        with factory() as db:
            user = db.get(User, uid)
            user.organization_id = 101
            barrier.wait()
            try:
                with service.domain(db):
                    service.decide(
                        db,
                        user,
                        "testing",
                        r["id"],
                        Decision(
                            assignment_id=assignments[uid],
                            expected_revision=revision,
                            decision="approve",
                            request_key=f"concurrent-vote-{uid}",
                        ),
                    )
                    db.commit()
                return 200
            except HTTPException as e:
                db.rollback()
                return e.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(vote, reviewers))
    assert sorted(results) == [200, 409]
    worker_process()
    with factory() as db:
        assert db.get(ApprovalRequest, r["id"]).status == "Approved"
        assert (
            db.query(ApprovalHistory)
            .filter_by(request_id=r["id"], event_type="approve")
            .count()
            == 1
        )
        assert service.verify_history(db, db.get(RequestState, r["id"]))


def test_business_calendar_skips_weekends_and_configured_holidays():
    from datetime import datetime, timezone
    from app.apps.power_apps.approvals.calendar import deadline
    from app.apps.power_apps.approvals.contracts import BusinessCalendar

    calendar = BusinessCalendar(timezone="Asia/Dubai", holidays=["2026-11-02"])
    start = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)  # Friday 16:00 UAE
    assert deadline(start, 7200, calendar) == datetime(
        2026, 11, 3, 6, tzinfo=timezone.utc
    )
    assert deadline(start, 120, None).minute == 2


def test_analytics_are_real_and_scope_filtered(client, db, actors):
    ids = users(db)
    p = policy(client, actors[0], [ids[3]])
    r = submit(client, actors[0], p)
    drain(db)
    response = client.get(ROOT + "/analytics", headers=actors[0])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert data["counts"]["pending"] == 1
    assert data["counts"]["average_seconds"] is None
    assert decide(client, actors[3], r).status_code == 200
    drain(db)
    data = client.get(ROOT + "/analytics", headers=actors[0]).json()
    assert data["counts"]["approved"] == 1
    assert data["counts"]["average_seconds"] >= 0
    assert len(data["stage_times"]) == 1
    assert client.get(ROOT + "/analytics", headers=actors[1]).json()["total"] == 0


def test_changes_restart_earlier_approval_stages(client, db, actors):
    ids = users(db)
    p = policy(client, actors[0], [ids[3]], stages=3)
    r = submit(client, actors[0], p)
    drain(db)
    assert decide(client, actors[3], r).status_code == 200
    drain(db)
    assert (
        decide(client, actors[3], r, "changes", "Change request amount").status_code
        == 200
    )
    d = detail(client, actors[0], r)
    response = client.post(
        f'{ROOT}/requests/{r["id"]}/resubmit',
        headers=actors[0],
        json={
            "expected_revision": d["state"]["revision"],
            "fields": {"amount": 500},
            "reason": "Changed amount",
        },
    )
    assert response.status_code == 200, response.text
    drain(db)
    d = detail(client, actors[3], r)
    current = [a for a in d["assignments"] if a["can_decide"]]
    assert (
        len(current) == 1
        and current[0]["stage_name"] == "Review 1"
        and current[0]["cycle"] == 2
    )
    assert d["evidence_valid"]
    assert d["status"] == "Pending"


def test_unresolved_groups_cannot_be_reduced_to_one_seat(client, db, actors):
    ids = users(db)
    db.get(User, ids[2]).role_id = db.get(User, ids[0]).role_id
    db.commit()
    p = policy(client, actors[0], [ids[2], ids[3]])
    db.get(User, ids[2]).is_active = False
    db.commit()
    r = submit(client, actors[0], p)
    drain(db)
    d = detail(client, actors[0], r)
    assert d["status"] == "Resolution Required"
    assert d["assignments"] == []
    response = client.post(
        f'{ROOT}/requests/{r["id"]}/reassign',
        headers=actors[0],
        json={
            "expected_revision": d["state"]["revision"],
            "user_id": ids[3],
            "reason": "Restore approval",
        },
    )
    assert response.status_code == 409, response.text
    db.get(User, ids[2]).is_active = True
    db.commit()
    response = client.post(
        f'{ROOT}/requests/{r["id"]}/resolve',
        headers=actors[0],
        json={
            "expected_revision": d["state"]["revision"],
            "reason": "Approver access restored",
        },
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["assignments"]) == 2


def test_workflow_authorship_does_not_grant_decision_permission(client, db, actors):
    from app.models.user import Role

    ids = users(db)
    original = db.get(User, ids[0]).role
    role = Role(
        name="workflow_author_without_vote",
        permissions=[
            p for p in original.permissions if p.name != "power_apps_approval_decide"
        ],
    )
    db.add(role)
    db.flush()
    db.get(User, ids[0]).role_id = role.id
    db.commit()
    p = policy(client, actors[0], [ids[3]])
    r = submit(client, actors[0], p)
    drain(db)
    assignment = detail(client, actors[0], r)["assignments"][0]
    response = decide(client, actors[0], r, assignment=assignment)
    assert response.status_code == 403, response.text
    assert detail(client, actors[0], r)["status"] == "Pending"


def test_linked_execution_read_does_not_grant_generic_mutations(client, db, actors):
    ids = users(db)
    p = policy(client, actors[0], [ids[3]])
    r = submit(client, actors[0], p)
    drain(db)
    d = detail(client, actors[3], r)
    run_id = d["state"]["run_id"]
    response = client.get(f"/api/v1/power-apps/executions/{run_id}", headers=actors[3])
    assert response.status_code == 200, response.text
    response = client.post(
        f"/api/v1/power-apps/executions/{run_id}/cancel", headers=actors[3]
    )
    assert response.status_code == 404, response.text


def test_storage_tampering_is_detected_and_cannot_be_resealed_by_a_vote(
    client, db, actors
):
    from sqlalchemy import update
    from app.apps.power_apps.approvals.models import RequestState

    ids = users(db)
    p = policy(client, actors[0], [ids[3]])
    r = submit(client, actors[0], p)
    drain(db)
    # Deliberate privileged storage corruption inside the disposable test transaction.
    db.connection().execute(
        update(RequestState)
        .where(RequestState.id == r["id"])
        .values(fields={"amount": 999999})
    )
    db.expire_all()
    d = detail(client, actors[3], r)
    assert not d["evidence_valid"]
    response = decide(client, actors[3], r)
    assert response.status_code == 409, response.text
    assert not detail(client, actors[3], r)["evidence_valid"]
