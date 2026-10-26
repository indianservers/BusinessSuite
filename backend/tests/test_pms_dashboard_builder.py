from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE, account
from tests.test_pms_recovery import isolated_audit
from app.apps.project_management.models import PMSWorkspace, PMSTask
from app.apps.project_management.dashboard_config import template_config, WIDGETS


def test_builder_layout_cas_history_and_source_security(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = BASE + "/dashboards"
    config = template_config("project_overview").model_dump(mode="json")
    made = client.post(
        path,
        headers=oh,
        json={
            "workspace_id": wid,
            "name": "Builder",
            "visibility": "workspace",
            "configuration": config,
        },
    )
    assert made.status_code == 201, made.text
    record = made.json()
    url = path + f"/{record['id']}"
    assert client.get(url, headers=mh).json()["can_edit"] is False
    assert (
        client.put(
            url,
            headers=mh,
            json={
                "name": "No",
                "visibility": "workspace",
                "revision": 1,
                "configuration": config,
            },
        ).status_code
        == 403
    )
    task = PMSTask(
        project_id=pid, title="Visible task", task_key="DASH-1", status="To Do"
    )
    db.add(task)
    db.commit()
    data = client.post(url + "/query", headers=mh, json=config)
    assert data.status_code == 200, data.text
    total = next(w for w in config["widgets"] if w["type"] == "total_tasks")
    assert data.json()["widgets"][total["id"]]["value"] == 1
    config["widgets"][0].update(x=6, y=30, w=6, h=4)
    saved = client.put(
        url,
        headers=oh,
        json={
            "name": "Builder saved",
            "visibility": "workspace",
            "revision": 1,
            "configuration": config,
        },
    )
    assert saved.status_code == 200, saved.text
    assert (
        client.put(
            url,
            headers=oh,
            json={
                "name": "Stale",
                "visibility": "workspace",
                "revision": 1,
                "configuration": config,
            },
        ).status_code
        == 409
    )
    assert client.get(url, headers=oh).json()["configuration"]["widgets"][0]["x"] == 6
    history = client.get(url + "/history", headers=oh).json()
    assert history and history[0]["revision"] == 1
    restored = client.post(
        url + f"/history/{history[0]['id']}/restore", headers=oh, json={"revision": 2}
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["configuration"]["widgets"][0]["x"] == 0
    assert db.get(PMSTask, task.id).status == "To Do"
    assert (
        client.post(url + "/favorite", headers=mh, json={"favorite": True}).status_code
        == 200
    )
    assert (
        next(r for r in client.get(path, headers=mh).json() if r["id"] == record["id"])[
            "favorite"
        ]
        is True
    )
    assert client.post(url + "/duplicate", headers=gh).status_code == 403
    copy = client.post(url + "/duplicate", headers=oh)
    assert copy.status_code == 201 and copy.json()["visibility"] == "private"
    invalid = {**config, "widgets": [{**config["widgets"][0], "type": "arbitrary_sql"}]}
    assert client.post(url + "/query", headers=oh, json=invalid).status_code == 422
    assert (
        client.post(
            url + "/query",
            headers=oh,
            json={**config, "filters": {"timezone": "invalid/timezone"}},
        ).status_code
        == 422
    )


def test_shared_configuration_does_not_grant_underlying_records(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    outsider, xh = account(db, "dashboard-outsider@example.invalid", True)
    from tests.tenant_test_utils import assign_company
    assign_company(db, owner, 77)
    assign_company(db, outsider, 77)
    db.get(PMSWorkspace, wid).organization_id = 77
    db.add(PMSTask(project_id=pid, title="Secret project task", task_key="DASH-SECRET"))
    db.commit()
    config = template_config("tasks").model_dump(mode="json")
    made = client.post(
        BASE + "/dashboards",
        headers=oh,
        json={
            "workspace_id": wid,
            "name": "Shared config",
            "visibility": "organization",
            "configuration": config,
        },
    )
    assert made.status_code == 201, made.text
    url = BASE + f"/dashboards/{made.json()['id']}"
    assert client.get(url, headers=xh).status_code == 200
    result = client.post(url + "/query", headers=xh, json=config)
    assert result.status_code == 200, result.text
    assert result.json()["scope"]["visible_projects"] == 0
    assert all(
        not widget.get("rows") and widget.get("value") in (None, 0)
        for widget in result.json()["widgets"].values()
    )
    assert (
        client.post(url + "/trash", headers=xh, json={"revision": 1}).status_code == 403
    )


def test_fifty_widgets_share_data_and_explicit_unavailable_states(client, db):
    wid, pid, owner, oh, *_ = setup_workspace(client, db)
    db.add_all(
        PMSTask(
            project_id=pid,
            title=f"Task {i}",
            task_key=f"DASH-{i}",
            status="Done" if i % 2 else "To Do",
        )
        for i in range(250)
    )
    db.commit()
    config = template_config("blank").model_dump(mode="json")
    config["widgets"] = [
        {
            "id": f"w{i}",
            "type": "total_tasks",
            "w": 2,
            "h": 3,
            "x": i % 6 * 2,
            "y": i // 6 * 3,
        }
        for i in range(50)
    ]
    made = client.post(
        BASE + "/dashboards",
        headers=oh,
        json={"workspace_id": wid, "name": "Large", "configuration": config},
    )
    assert made.status_code == 201, made.text
    url = BASE + f"/dashboards/{made.json()['id']}"
    result = client.post(url + "/query", headers=oh, json=config)
    assert result.status_code == 200, result.text
    assert len(result.json()["widgets"]) == 50
    assert all(w["value"] == 250 for w in result.json()["widgets"].values())
    config["widgets"][0]["type"] = "team_utilization"
    unavailable = client.post(url + "/query", headers=oh, json=config).json()[
        "widgets"
    ]["w0"]
    assert (
        unavailable["state"] == "unavailable" and "capacity" in unavailable["message"]
    )
    assert len(WIDGETS) == 100


def test_selected_editor_and_all_connected_widgets(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    config = template_config("project_overview").model_dump(mode="json")
    shares = [
        {"user_id": member.id, "role": "editor"},
        {"user_id": guest.id, "role": "viewer"},
    ]
    made = client.post(
        BASE + "/dashboards",
        headers=oh,
        json={
            "workspace_id": wid,
            "name": "Editors",
            "visibility": "selected",
            "shared_users": shares,
            "configuration": config,
        },
    )
    assert made.status_code == 201, made.text
    url = BASE + f"/dashboards/{made.json()['id']}"
    edited = client.put(
        url,
        headers=mh,
        json={
            "revision": 1,
            "name": "Updated by editor",
            "visibility": "selected",
            "shared_users": shares,
            "configuration": config,
        },
    )
    assert edited.status_code == 200, edited.text
    assert (
        client.put(
            url,
            headers=mh,
            json={"revision": 2, "name": "Reshare", "visibility": "workspace"},
        ).status_code
        == 403
    )
    assert client.get(url + "/history", headers=gh).status_code == 403
    assert (
        client.post(
            url + "/transfer", headers=mh, json={"revision": 2, "owner_id": member.id}
        ).status_code
        == 403
    )
    assert (
        client.post(url + "/trash", headers=mh, json={"revision": 2}).status_code == 403
    )
    from datetime import date, datetime, timezone
    from app.apps.project_management.models import (
        PMSTimeLog,
        PMSSprint,
        PMSMilestone,
        PMSRisk,
    )

    today = date.today()
    db.add_all(
        [
            PMSTask(
                project_id=pid,
                title="Source task",
                task_key="SOURCE-1",
                status="Done",
                estimated_hours=5,
                actual_hours=3,
                completed_at=datetime.now(timezone.utc),
                due_date=today,
            ),
            PMSTimeLog(
                project_id=pid,
                user_id=member.id,
                log_date=today,
                duration_minutes=90,
                description="Authorized time",
            ),
            PMSSprint(
                project_id=pid,
                name="Source sprint",
                start_date=today,
                end_date=today,
                committed_story_points=10,
                completed_story_points=7,
                completed_at=datetime.now(timezone.utc),
            ),
            PMSMilestone(project_id=pid, name="Source milestone", due_date=today),
            PMSRisk(project_id=pid, title="Source risk", risk_score=6),
        ]
    )
    db.commit()
    types = [s for s in WIDGETS.values() if not s["requirement"]]
    for offset in range(0, len(types), 50):
        config["widgets"] = [
            {"id": f"w{i}", "type": s["id"], "source": s["source"]}
            for i, s in enumerate(types[offset : offset + 50])
        ]
        result = client.post(url + "/query", headers=mh, json=config)
        assert result.status_code == 200, result.text
        assert all(
            v["state"] != "error" for v in result.json()["widgets"].values()
        ), result.text
    config["widgets"] = [
        {
            "id": "budget",
            "type": "bar",
            "source": "projects",
            "metric": "budget_amount",
            "aggregation": "sum",
        }
    ]
    assert (
        client.post(url + "/query", headers=mh, json=config).json()["widgets"][
            "budget"
        ]["state"]
        == "unavailable"
    )


def test_guided_and_provider_previews_never_persist_or_trust_model_ids(
    client, db, monkeypatch
):
    from app.ai_operator.models import OperatorProvider
    from app.apps.project_management.models import PMSWorkspaceEntry

    wid, pid, owner, oh, *_ = setup_workspace(client, db)
    path = BASE + "/dashboards/suggest"
    before = db.query(PMSWorkspaceEntry).count()
    guided = client.post(
        path,
        headers=oh,
        json={"prompt": "Show task priority in a donut", "workspace_id": wid},
    )
    assert guided.status_code == 200 and guided.json()["mode"] == "guided"
    assert db.query(PMSWorkspaceEntry).count() == before
    db.add(
        OperatorProvider(
            scope_key=f"workspace:{wid}",
            provider="openai",
            model="configured-model",
            encrypted_key="unused-test-key",
            enabled=True,
            data_sharing_allowed=True,
            updated_by=owner.id,
        )
    )
    db.commit()
    monkeypatch.setattr("app.ai_operator.service.require_enabled", lambda *args: None)
    outbound = []

    def fake(db, user, config, **kwargs):
        outbound.append(kwargs["prompt"])
        value = template_config("tasks").model_dump(mode="json")
        value["filters"]["project_ids"] = [999999]
        value["widgets"][0]["notes"] = "Invented model data"
        value["widgets"][0]["url"] = "https://example.invalid"
        return value

    monkeypatch.setattr("app.ai_operator.providers.generate_json", fake)
    preview = client.post(
        path,
        headers=oh,
        json={
            "prompt": "Make a dashboard about overdue tasks",
            "workspace_id": wid,
            "provider": "openai",
        },
    )
    assert preview.status_code == 200, preview.text
    value = preview.json()
    assert (
        value["mode"] == "ai" and value["configuration"]["filters"]["project_ids"] == []
    )
    assert (
        value["configuration"]["widgets"][0]["url"] == ""
        and value["configuration"]["widgets"][0]["notes"] == ""
    )
    assert "supported_widgets" in outbound[0] and "Source task" not in outbound[0]
    assert db.query(PMSWorkspaceEntry).count() == before
