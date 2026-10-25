"""HTTP and persistence tests for the shared forms plugin."""

import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db.base_class import Base
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.forms import router as forms
from app.forms.models import FormReply, FormFile, FormChallenge, SuiteForm


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner = User(
            email="forms-owner@audit.invalid",
            hashed_password="unused",
            is_active=True,
            is_superuser=True,
        )
        other = User(
            email="forms-other@audit.invalid",
            hashed_password="unused",
            is_active=True,
            is_superuser=True,
        )
        db.add_all([owner, other])
        db.commit()
        actor = [owner]
        app = FastAPI()
        app.include_router(forms.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: actor[0]
        monkeypatch.setattr(forms, "new_code", lambda: "ABC234")
        with TestClient(app) as c:
            yield c, db, actor, owner, other
    engine.dispose()


def definition(**settings):
    return {
        "name": "Project request",
        "fields": [
            {"id": "title", "type": "text", "label": "Request title", "required": True},
            {"id": "email", "type": "email", "label": "Email"},
        ],
        "settings": {"public": True, **settings},
    }


def create(c, d=None, module="pms"):
    r = c.post("/forms", json={"module_key": module, "definition": d or definition()})
    assert r.status_code == 201, r.text
    return r.json()


def test_visual_design_persists_in_public_snapshot(setup):
    c, *_ = setup
    design = definition(columns=3, intro_enabled=True, intro_badge="Interns Hub",
                        intro_title="Build your future", intro_text="Apply today",
                        surface="gradient")
    design["fields"][0]["width"] = "full"
    form = publish(c, design)
    public = c.get(f'/forms/public/{form["slug"]}')
    assert public.status_code == 200
    saved = public.json()["definition"]
    assert saved["settings"]["columns"] == 3
    assert saved["settings"]["intro_title"] == "Build your future"
    assert saved["settings"]["surface"] == "gradient"
    assert saved["fields"][0]["width"] == "full"


@pytest.mark.parametrize("updates", [{"columns":4}, {"surface":"url(javascript:bad)"},
                                      {"intro_title":"x" * 201}])
def test_visual_design_rejects_invalid_settings(setup, updates):
    c, *_ = setup
    assert c.post("/forms", json={"module_key":"hrms", "definition":definition(**updates)}).status_code == 422


def save(c, f, **kw):
    return c.put(
        f'/forms/{f["id"]}',
        json={"revision": f["revision"], "definition": f["draft"], **kw},
    )


def publish(c, d=None, module="pms"):
    f = create(c, d, module)
    r = save(c, f, publish=True)
    assert r.status_code == 200, r.text
    return r.json()


def submit(c, f, **kw):
    challenge = c.get(f'/forms/public/{f["slug"]}/challenge')
    assert challenge.status_code == 200, challenge.text
    return c.post(
        f'/forms/public/{f["slug"]}/submit',
        json={
            "request_id": str(uuid4()),
            "version": f["version"],
            "answers": {"title": "A request"},
            "challenge_id": challenge.json()["id"],
            "captcha_answer": "ABC234",
            **kw,
        },
    )


def test_draft_snapshot_publish_close_and_conflict(setup):
    c, db, *_ = setup
    f = create(c)
    assert c.get(f'/forms/public/{f["slug"]}').status_code == 404
    f = save(c, f, publish=True).json()
    public = c.get(f'/forms/public/{f["slug"]}')
    assert public.json()["open"] and "workflow" not in public.json()["definition"]
    assert public.headers["cache-control"] == "private, no-store"
    old = dict(f)
    f["draft"]["name"] = "Private changed draft"
    f = save(c, f).json()
    assert (
        c.get(f'/forms/public/{f["slug"]}').json()["definition"]["name"]
        == "Project request"
    )
    assert save(c, old).status_code == 409
    f = save(c, f, close=True).json()
    assert not c.get(f'/forms/public/{f["slug"]}').json()["open"]
    assert c.get(f'/forms/public/{f["slug"]}/challenge').status_code == 410


def test_owner_boundary_and_tenant(setup):
    c, db, actor, owner, other = setup
    f = publish(c)
    actor[0] = other
    assert c.get("/forms?module_key=pms").json() == []
    for path in [
        f'/forms/{f["id"]}',
        f'/forms/{f["id"]}/responses',
        f'/forms/{f["id"]}/export',
    ]:
        assert c.get(path).status_code == 404
    assert save(c, f).status_code == 404
    actor[0] = owner
    owner.organization_id = 987
    assert c.get(f'/forms/{f["id"]}').status_code == 404


def test_captcha_honeypot_expiry_single_use_and_success(setup):
    c, db, *_ = setup
    f = publish(c)
    assert submit(c, f, captcha_answer="wrong").status_code == 422
    assert submit(c, f, website="bot").status_code == 422
    challenge = c.get(f'/forms/public/{f["slug"]}/challenge').json()
    ch = db.get(FormChallenge, challenge["id"])
    ch.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    payload = {
        "request_id": str(uuid4()),
        "version": f["version"],
        "answers": {"title": "Hello"},
        "challenge_id": ch.id,
        "captcha_answer": "ABC234",
    }
    assert c.post(f'/forms/public/{f["slug"]}/submit', json=payload).status_code == 422
    challenge = c.get(f'/forms/public/{f["slug"]}/challenge').json()
    payload["challenge_id"] = challenge["id"]
    assert c.post(f'/forms/public/{f["slug"]}/submit', json=payload).status_code == 201
    assert c.post(f'/forms/public/{f["slug"]}/submit', json=payload).status_code == 201
    payload["request_id"] = str(uuid4())
    assert c.post(f'/forms/public/{f["slug"]}/submit', json=payload).status_code == 422
    assert db.query(FormReply).count() == 1


def test_validation_hidden_answers_and_exports(setup):
    c, db, *_ = setup
    d = definition()
    d["fields"].append(
        {
            "id": "detail",
            "type": "text",
            "label": "Details",
            "required": True,
            "condition": {"field": "title", "operator": "equals", "value": "details"},
        }
    )
    f = publish(c, d)
    assert submit(c, f, answers={"title": "=2+2", "email": "bad"}).status_code == 422
    assert (
        submit(c, f, answers={"title": "=2+2", "detail": "hidden secret"}).status_code
        == 201
    )
    r = c.get(f'/forms/{f["id"]}/responses').json()["items"][0]
    assert "detail" not in r["answers"]
    assert "'=2+2" in c.get(f'/forms/{f["id"]}/export').text
    assert (
        c.patch(
            f'/forms/{f["id"]}/responses/{r["id"]}', json={"status": "reviewed"}
        ).json()["status"]
        == "reviewed"
    )


def test_capacity_deadline_and_version(setup):
    c, db, *_ = setup
    f = publish(c, definition(max_responses=1))
    assert submit(c, f, version=999).status_code == 409
    assert submit(c, f).status_code == 201
    assert not c.get(f'/forms/public/{f["slug"]}').json()["open"]
    f = publish(
        c,
        definition(
            closes_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        ),
    )
    assert not c.get(f'/forms/public/{f["slug"]}').json()["open"]


def test_upload_validation_privacy_and_download(setup):
    c, db, actor, owner, other = setup
    d = definition()
    d["fields"].append(
        {"id": "attachment", "type": "file", "label": "Attachment", "required": True}
    )
    f = publish(c, d)
    assert submit(c, f).status_code == 422
    assert (
        submit(
            c,
            f,
            files={
                "attachment": {
                    "filename": "bad.pdf",
                    "data": base64.b64encode(b"bad").decode(),
                }
            },
        ).status_code
        == 422
    )
    assert (
        submit(
            c,
            f,
            files={
                "attachment": {
                    "filename": "../brief.pdf",
                    "data": base64.b64encode(b"%PDF-1.7\nsynthetic").decode(),
                }
            },
        ).status_code
        == 201
    )
    file = db.query(FormFile).one()
    assert file.filename == "brief.pdf"
    assert c.get(f'/forms/{f["id"]}/files/{file.id}').content.startswith(b"%PDF-")
    actor[0] = other
    assert c.get(f'/forms/{f["id"]}/files/{file.id}').status_code == 404


def test_rate_limits_and_disabled_modules(setup, monkeypatch):
    c, db, *_ = setup
    f = publish(c)
    for _ in range(30):
        assert c.get(f'/forms/public/{f["slug"]}/challenge').status_code == 200
    assert c.get(f'/forms/public/{f["slug"]}/challenge').status_code == 429
    monkeypatch.setattr(forms, "is_app_enabled", lambda key: False)
    assert c.get("/forms?module_key=crm").status_code == 404
    assert c.get(f'/forms/public/{f["slug"]}').status_code == 404


def test_global_catalog_and_cross_module_reuse(setup):
    from app.apps.customization.models import (
        CustomizationField,
        CustomizationFieldOption,
    )

    c, db, *_ = setup
    field = CustomizationField(
        module_name="crm.contacts",
        field_api_name="interest",
        field_label="Interest",
        field_type="picklist",
        visible=True,
        editable=True,
    )
    hidden = CustomizationField(
        module_name="crm.contacts",
        field_api_name="secret",
        field_label="Secret",
        field_type="text",
        visible=False,
    )
    db.add_all([field, hidden])
    db.flush()
    db.add(
        CustomizationFieldOption(
            field_id=field.id, value="Website", label="Website", active=True
        )
    )
    db.commit()
    catalog = c.get("/forms/catalog").json()
    assert len(catalog) == 1 and catalog[0]["options"] == ["Website"]
    for module in ["pms", "crm", "srm", "fam", "hrms"]:
        f = publish(c, module=module)
        assert submit(c, f).status_code == 201
        assert len(c.get("/forms", params={"module_key": module}).json()) == 1


def test_turnstile_fail_closed(setup, monkeypatch):
    c, db, *_ = setup
    assert (
        c.post(
            "/forms",
            json={"module_key": "crm", "definition": definition(captcha="turnstile")},
        ).status_code
        == 422
    )
    monkeypatch.setattr(forms.settings, "FORMS_TURNSTILE_SITE_KEY", "test-site")
    monkeypatch.setattr(forms.settings, "FORMS_TURNSTILE_SECRET_KEY", "test-secret")
    f = publish(c, definition(captcha="turnstile"))
    monkeypatch.setattr(
        forms.httpx,
        "post",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    assert submit(c, f).status_code == 503
    assert db.query(FormReply).count() == 0


def test_legacy_import_is_idempotent_and_preserves_internal_privacy(setup):
    import json
    from app.apps.project_management.models import (
        PMSWorkspace,
        PMSWorkspaceMember,
        PMSWorkspaceEntry,
    )

    c, db, actor, owner, other = setup
    w = PMSWorkspace(name="Legacy", organization_id=1)
    db.add(w)
    db.flush()
    db.add_all(
        [
            PMSWorkspaceMember(workspace_id=w.id, user_id=owner.id, role="Owner"),
            PMSWorkspaceMember(workspace_id=w.id, user_id=other.id, role="Admin"),
        ]
    )
    d = definition()
    d.pop("settings")
    entry = PMSWorkspaceEntry(
        workspace_id=w.id,
        author_id=owner.id,
        kind="form_v2",
        body=json.dumps(
            {
                "draft": d,
                "published": d,
                "revision": 3,
                "version": 1,
                "open": True,
                "responses": 1,
            }
        ),
    )
    db.add(entry)
    db.flush()
    reply = PMSWorkspaceEntry(
        workspace_id=w.id,
        author_id=owner.id,
        kind="form_reply",
        body=json.dumps(
            {
                "key": "legacy-1",
                "form_id": entry.id,
                "version": 1,
                "answers": {"title": "Legacy reply"},
                "labels": {"title": "Request title"},
            }
        ),
    )
    db.add(reply)
    db.commit()
    actor[0] = other
    imported = c.get("/forms?module_key=pms").json()
    assert len(imported) == 1
    f = imported[0]
    assert (
        f["revision"] == 3 and f["responses"] == 1 and f["legacy_entry_id"] == entry.id
    )
    assert c.get(f'/forms/public/{f["slug"]}').status_code == 404
    assert c.get(f'/forms/{f["id"]}').status_code == 200
    assert c.get("/forms?module_key=pms").json()[0]["responses"] == 1
    db.add(
        PMSWorkspaceEntry(
            workspace_id=w.id,
            author_id=owner.id,
            kind="form_reply",
            body=json.dumps(
                {
                    "key": "legacy-2",
                    "form_id": entry.id,
                    "version": 1,
                    "answers": {"title": "Later reply"},
                    "labels": {"title": "Request title"},
                }
            ),
        )
    )
    db.commit()
    assert c.get("/forms?module_key=pms").json()[0]["responses"] == 2
    assert db.query(SuiteForm).count() == 1


def test_task_adapter_atomic_creation_and_replay(setup):
    from app.apps.project_management.models import PMSProject, PMSTask

    c, db, actor, owner, other = setup
    p = PMSProject(
        name="Intake", project_key="FORMQA", organization_id=1, manager_user_id=owner.id
    )
    db.add(p)
    db.commit()
    d = definition()
    d["workflow"] = {
        "enabled": True,
        "project_id": p.id,
        "title_field": "title",
        "priority": "High",
        "due_days": 2,
    }
    f = publish(c, d)
    rid = str(uuid4())
    assert submit(c, f, request_id=rid).status_code == 201
    assert db.query(PMSTask).count() == 1
    assert submit(c, f, request_id=rid).status_code == 201
    assert db.query(PMSTask).count() == 1
    r = c.get(f'/forms/{f["id"]}/responses').json()["items"][0]
    assert r["task_id"] is not None
    assert db.get(PMSTask, r["task_id"]).priority == "High"
    owner.is_superuser = False
    db.commit()
    # Revoking owner access must not let an anonymous response create a task.
    p.manager_user_id = other.id
    db.commit()
    assert submit(c, f).status_code in (403, 404)
    assert db.query(FormReply).count() == 1 and db.query(PMSTask).count() == 1


def test_import_validation_and_runtime_module_gate(setup):
    from app.apps.business_os.models import BOSEnabledModule

    c, db, *_ = setup
    assert (
        c.post(
            "/forms/validate", json={"name": "Malformed", "fields": [{}]}
        ).status_code
        == 422
    )
    d = definition()
    d["fields"][0]["condition"] = {"field": "missing"}
    assert c.post("/forms/validate", json=d).status_code == 422
    f = publish(c, module="crm")
    db.add(
        BOSEnabledModule(
            company_id=1,
            module_key="crm",
            display_name="CRM",
            enabled=False,
            metadata_json={},
        )
    )
    db.commit()
    assert c.get("/forms?module_key=crm").status_code == 404
    assert c.get(f'/forms/public/{f["slug"]}').status_code == 404


def test_response_search_pagination_json_and_malformed_choices(setup):
    c, db, *_ = setup
    d = definition()
    d["fields"].append(
        {
            "id": "choices",
            "type": "multiselect",
            "label": "Choices",
            "options": ["A", "B"],
        }
    )
    f = publish(c, d)
    assert submit(c, f, answers={"title": "bad", "choices": [{}]}).status_code == 422
    for title in ["Find this marker", "Other request", "Literal 100%_value"]:
        assert submit(c, f, answers={"title": title}).status_code == 201
    path = f'/forms/{f["id"]}'
    assert c.get(path + "/responses", params={"q": "marker"}).json()["total"] == 1
    assert c.get(path + "/responses", params={"q": "%_"}).json()["total"] == 1
    assert len(c.get(path + "/responses?limit=1&offset=1").json()["items"]) == 1
    exported = c.get(path + "/export?format=json")
    assert exported.status_code == 200 and len(exported.json()) == 3
    assert all("request_id" not in r for r in exported.json())


def test_internal_forms_and_legacy_member_sees_no_draft_or_responses(setup):
    import json
    from app.apps.project_management.models import (
        PMSWorkspace,
        PMSWorkspaceMember,
        PMSWorkspaceEntry,
    )

    c, db, actor, owner, member = setup
    f = publish(c, definition(public=False))
    assert c.get(f'/forms/public/{f["slug"]}').status_code == 404
    assert c.get(f'/forms/{f["id"]}/internal').status_code == 200
    payload = {
        "request_id": str(uuid4()),
        "version": f["version"],
        "answers": {"title": "Internal response"},
    }
    assert c.post(f'/forms/{f["id"]}/internal/submit', json=payload).status_code == 201
    actor[0] = member
    assert c.get(f'/forms/{f["id"]}/internal').status_code == 404
    w = PMSWorkspace(name="Shared legacy", organization_id=1)
    db.add(w)
    db.flush()
    db.add(PMSWorkspaceMember(workspace_id=w.id, user_id=member.id, role="Member"))
    d = definition(public=False)
    draft = {**d, "name": "Secret unfinished draft"}
    legacy = PMSWorkspaceEntry(
        workspace_id=w.id,
        author_id=owner.id,
        kind="form_v2",
        body=json.dumps(
            {
                "draft": draft,
                "published": d,
                "revision": 4,
                "version": 1,
                "open": True,
                "responses": 0,
            }
        ),
    )
    db.add(legacy)
    db.commit()
    listing = c.get("/forms?module_key=pms").json()
    assert len(listing) == 1
    f = listing[0]
    assert (
        f["read_only"]
        and f["draft"]["name"] == "Project request"
        and "Secret unfinished draft" not in str(listing)
    )
    assert c.get(f'/forms/{f["id"]}/internal').status_code == 200
    payload["request_id"] = str(uuid4())
    assert c.post(f'/forms/{f["id"]}/internal/submit', json=payload).status_code == 201
    assert c.get(f'/forms/{f["id"]}/responses').status_code == 404
    assert c.get(f'/forms/{f["id"]}').status_code == 404


@pytest.mark.parametrize(
    "directory,filename",
    [
        ("alembic", "20261024_013_shared_forms.py"),
        ("alembic_postgresql", "pg_20261024_013_shared_forms.py"),
    ],
)
def test_migration_creates_and_reverses_shared_tables(directory, filename):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = create_engine("sqlite://")
    forms_tables = {
        "suite_forms",
        "suite_form_replies",
        "suite_form_files",
        "suite_form_challenges",
        "suite_form_rate_buckets",
    }
    Base.metadata.create_all(
        engine,
        tables=[t for t in Base.metadata.sorted_tables if t.name not in forms_tables],
    )
    path = Path(__file__).parents[1] / directory / "versions" / filename
    spec = importlib.util.spec_from_file_location("forms_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
            assert forms_tables.issubset(inspect(connection).get_table_names())
            migration.downgrade()
            assert not forms_tables.intersection(inspect(connection).get_table_names())
    engine.dispose()


def test_numeric_conditions_keep_full_precision(setup):
    c, db, *_ = setup
    d = definition()
    d["fields"] += [
        {"id": "amount", "type": "number", "label": "Amount"},
        {
            "id": "followup",
            "type": "text",
            "label": "Follow up",
            "required": True,
            "condition": {
                "field": "amount",
                "operator": "equals",
                "value": "1.23456789",
            },
        },
    ]
    f = publish(c, d)
    assert (
        submit(c, f, answers={"title": "Precision", "amount": 1.23456789}).status_code
        == 422
    )
    assert (
        submit(
            c,
            f,
            answers={
                "title": "Precision",
                "amount": 1.23456789,
                "followup": "Required details",
            },
        ).status_code
        == 201
    )
