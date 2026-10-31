from datetime import date, timedelta
import json
import pytest
from sqlalchemy import event
from tests.test_pms_task_studio import studio
from tests.test_pms_workspaces import account, middleware_database, BASE
from tests.rich_text_test_utils import organization_context
from app.apps.project_management.models import (
    PMSWorkspaceTeamMember,
    PMSWorkspaceMember,
    PMSWorkspaceTeam,
    PMSTask,
    PMSTaskAssignee,
)
from app.common.models import CommonProfile, CommonPerson
from app.models.user import User, Role

ROOT = BASE + "/people-workspace"


@pytest.fixture
def directory_data(db, studio):
    owner, member, outsider, headers, mh, oh, project, team, batch = studio
    team.members = [
        PMSWorkspaceTeamMember(user_id=owner.id),
        PMSWorkspaceTeamMember(user_id=member.id),
    ]
    member.person.display_name = "Anila Directory"
    outsider.person.display_name = "Unassigned Directory"
    role = Role(name="employee")
    db.add(role)
    db.flush()
    member.role_id = role.id
    member.person.profile.skills_json = ["Python", "Web Testing"]
    other, other_headers = account(db, "foreign-directory@test.com")
    other.person.organization_id = 2
    db.commit()
    return studio, other, other_headers


def test_directory_combined_filters_counts_and_private_views(
    client, db, directory_data
):
    data, other, other_headers = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    response = client.get(ROOT + "/people", headers=h, params={"page_size": 1})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 3 and len(response.json()["items"]) == 1
    assert other.id not in [
        row["id"] for row in client.get(ROOT + "/people", headers=h).json()["items"]
    ]
    for term in [
        "Anila",
        "Python",
        "Studio Batch",
        "Delivery Team",
        "Studio Department",
    ]:
        found = client.get(ROOT + "/people", headers=h, params={"q": term}).json()
        assert member.id in [row["id"] for row in found["items"]], term
    params = {
        "q": "Anila",
        "status": "active",
        "role": "employee",
        "workspace_id": project["workspace_id"],
        "team_id": team.id,
        "batch_id": batch.id,
        "kind": "interns",
        "department_id": member.employee.department_id,
        "skill": "Python",
        "membership": "member",
        "registered_from": str(date.today() - timedelta(days=2)),
        "registered_to": str(date.today() + timedelta(days=2)),
    }
    result = client.get(ROOT + "/people", headers=h, params=params)
    assert result.status_code == 200, result.text
    assert [row["id"] for row in result.json()["items"]] == [member.id]
    assert "hashed_password" not in result.text and "pan_number" not in result.text
    ref = client.get(ROOT + "/reference", headers=h)
    assert ref.status_code == 200, ref.text
    assert ref.json()["stats"] == {
        "total": 3,
        "active": 3,
        "inactive": 0,
        "teams": 1,
        "batches": 1,
    }
    created = client.post(
        ROOT + "/views",
        headers=h,
        json={"name": "Intern engineering", "filters": params},
    )
    assert created.status_code == 201, created.text
    assert len(client.get(ROOT + "/views", headers=h).json()) == 1
    assert client.get(ROOT + "/views", headers=oh).json() == []
    assert (
        client.delete(ROOT + f"/views/{created.json()['id']}", headers=oh).status_code
        == 404
    )
    assert (
        client.delete(ROOT + f"/views/{created.json()['id']}", headers=h).status_code
        == 200
    )


def test_teams_scope_membership_preview_and_deduplication(client, db, directory_data):
    data, foreign, fh = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    group = client.get(ROOT + "/groups", headers=h, params={"kind": "teams"})
    assert group.status_code == 200, group.text
    assert group.json()["items"][0]["members"] == 2
    assert len(group.json()["items"][0]["avatars"]) == 2
    body = {
        "user_ids": [outsider.id],
        "action": "add",
        "reason": "Add a delivery colleague",
    }
    preview = client.post(
        ROOT + f"/teams/{team.id}/members/preview", headers=h, json=body
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["missing_user_ids"] == [outsider.id]
    changed = client.post(ROOT + f"/teams/{team.id}/members", headers=h, json=body)
    assert changed.status_code == 200, changed.text
    assert (
        db.query(PMSWorkspaceTeamMember)
        .filter_by(team_id=team.id, user_id=outsider.id)
        .count()
        == 1
    )
    assert (
        client.post(ROOT + f"/teams/{team.id}/members", headers=h, json=body).json()[
            "changed"
        ]
        == 0
    )
    assert (
        client.post(
            ROOT + f"/teams/{team.id}/members", headers=mh, json=body
        ).status_code
        == 403
    )
    assert (
        client.post(
            ROOT + f"/teams/{team.id}/members",
            headers=h,
            json={**body, "user_ids": [foreign.id]},
        ).status_code
        == 422
    )
    assert client.get(ROOT + f"/groups/teams/{team.id}", headers=fh).status_code in {
        403,
        404,
    }
    details = client.get(
        ROOT + f"/groups/teams/{team.id}",
        headers=h,
        params={"section": "members", "page_size": 1},
    )
    assert details.status_code == 200, details.text
    assert details.json()["members"] == 3 and len(details.json()["items"]) == 1


def test_profiles_exports_and_assignment_context_are_scoped(client, db, directory_data):
    data, foreign, fh = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    assert client.get(ROOT + f"/people/{foreign.id}", headers=h).status_code == 404
    profile = client.get(ROOT + f"/people/{member.id}", headers=h)
    assert profile.status_code == 200, profile.text
    assert profile.json()["person"]["batches"][0]["id"] == batch.id
    context = client.get(
        ROOT + "/assignment-context",
        headers=h,
        params={"kind": "people", "ids": str(member.id)},
    )
    assert context.status_code == 200, context.text
    assert context.json()["projects"][0]["missing_user_ids"] == []
    assert (
        client.get(
            ROOT + "/assignment-context",
            headers=h,
            params={"kind": "people", "ids": str(foreign.id)},
        ).status_code
        == 422
    )
    assert (
        client.get(
            ROOT + "/assignment-context",
            headers=oh,
            params={"kind": "batches", "ids": str(batch.id)},
        ).status_code
        == 404
    )
    csv = client.get(ROOT + "/export", headers=h, params={"q": "Anila"})
    assert csv.status_code == 200, csv.text
    assert "Anila Directory" in csv.text and foreign.email not in csv.text
    assert client.get(ROOT + "/export", headers=mh).status_code == 403


def test_profile_details_and_batch_project_without_workspace_membership(client, db, directory_data):
    from app.apps.project_management.models import PMSProjectMember
    data, foreign, fh = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    team.description = "Delivery engineering"
    team.lead_user_id = owner.id
    db.query(PMSWorkspaceMember).filter_by(user_id=member.id).delete()
    db.query(PMSProjectMember).filter_by(user_id=member.id).delete()
    db.commit()
    batches = client.get(ROOT + f"/people/{member.id}", headers=h, params={"section": "batches"})
    assert batches.status_code == 200, batches.text
    assert batches.json()["is_intern"] is True
    item = batches.json()["items"][0]
    assert item["code"] == "STU" and item["project_name"] == "Studio Project"
    assert item["start_date"] == "2026-01-01" and item["mentor_name"]
    teams = client.get(ROOT + f"/people/{member.id}", headers=h, params={"section": "teams"}).json()["items"]
    assert teams[0]["description"] == "Delivery engineering"
    assert teams[0]["workspace_name"] == "Task Studio" and teams[0]["lead_name"]
    projects = client.get(ROOT + f"/people/{member.id}", headers=h, params={"section": "projects"}).json()["items"]
    assert [p["id"] for p in projects] == [project["id"]]
    assert projects[0]["project_key"] == "STU"
    overview = client.get(ROOT + f"/people/{member.id}", headers=h).json()
    assert overview["current_projects"][0]["id"] == project["id"]
    nonintern = client.get(ROOT + f"/people/{outsider.id}", headers=h, params={"section": "batches"}).json()
    assert nonintern["is_intern"] is False and nonintern["items"] == []


def test_profile_projects_include_ownership_and_task_work_without_tenant_leak(client, db, directory_data):
    from app.apps.project_management.models import PMSProject
    data, foreign, fh = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    owned = PMSProject(organization_id=1, name="Owned delivery", project_key="OWN", owner_user_id=outsider.id, status="Active")
    assigned = PMSProject(organization_id=1, name="Task delivery", project_key="ASS", status="Active")
    private = PMSProject(organization_id=2, name="Other organization", project_key="OTHER", owner_user_id=outsider.id)
    db.add_all([owned, assigned, private]); db.flush()
    db.add(PMSTask(project_id=assigned.id, title="Assigned work", task_key="ASS-1", assignee_user_id=outsider.id))
    db.commit()
    response = client.get(ROOT + f"/people/{outsider.id}", headers=h, params={"section": "projects"})
    assert response.status_code == 200, response.text
    projects = response.json()["items"]
    assert {p["id"] for p in projects} == {owned.id, assigned.id}
    assert next(p for p in projects if p["id"] == owned.id)["role"] == "Owner"
    assert "Owner" in next(p for p in projects if p["id"] == owned.id)["relationships"]
    assert "Task assignee" in next(p for p in projects if p["id"] == assigned.id)["relationships"]


def test_profile_task_filters_counts_and_directory_context(client, db, directory_data):
    data, foreign, fh = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    for title, status, due in [("Late work", "To Do", date.today()-timedelta(days=2)), ("Future work", "To Do", date.today()+timedelta(days=2)), ("Finished work", "Done", date.today()-timedelta(days=2)), ("Canceled work", "Cancelled", date.today()-timedelta(days=2))]:
        db.add(PMSTask(project_id=project["id"], title=title, task_key=title, status=status, due_date=due, assignee_user_id=member.id))
    db.commit()
    expected = {"all":4, "pending":2, "completed":1, "overdue":1}
    for task_filter, total in expected.items():
        response=client.get(ROOT+f"/people/{member.id}",headers=h,params={"section":"tasks","task_filter":task_filter})
        assert response.status_code == 200, response.text
        result=response.json()
        assert result["total"] == total
        assert result["counts"]["tasks"] == 4 and result["counts"]["teams"] == 1
        assert result["counts"]["batches"] == 1
    person=next(p for p in client.get(ROOT+"/people",headers=h).json()["items"] if p["id"]==member.id)
    assert person["employment_status"] == "Active"
    assert person["workspaces"][0]["name"] == "Task Studio"
    from app.access.models import AccessPolicy
    db.add(AccessPolicy(user_id=member.id, company_id=1, status="active", grants={"hrms":{"enabled":True}}))
    db.commit()
    profile=client.get(ROOT+f"/people/{member.id}",headers=h).json()
    assert any("does not enable PMS" in issue for issue in profile["access_issues"])
    ordered=client.get(ROOT+"/people",headers=h,params={"sort":"email_desc"})
    assert ordered.status_code == 200, ordered.text
    emails=[p["email"] for p in ordered.json()["items"]]
    assert emails == sorted(emails, reverse=True)


def test_directory_query_count_does_not_grow_with_people(client, db, directory_data):
    data, _, _ = directory_data
    h = data[3]
    for i in range(40):
        user = User(
            email=f"page-{i}@directory.test", hashed_password="unused", is_active=True
        )
        db.add(user)
        db.flush()
        db.add(
            CommonPerson(
                user_id=user.id,
                organization_id=1,
                primary_email=user.email,
                display_name=f"Paged Person {i}",
            )
        )
    db.commit()
    client.get(ROOT + "/people", headers=h)
    counts = []
    for page_size in [1, 40]:
        statements = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", listener)
        try:
            r = client.get(ROOT + "/people", headers=h, params={"page_size": page_size})
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        assert r.status_code == 200, r.text
        counts.append(len(statements))
    assert counts[1] <= counts[0] + 3, counts


def test_individual_batch_assignments_reuse_intern_distribution(
    client, db, directory_data
):
    data, _, _ = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    payload = {
        "task": {
            "title": "Independent learning check",
            "task_key": "DIR-INDEP",
            "description": "Submit evidence for reviewer approval",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        "batches": [batch.id],
        "reviewer_user_id": owner.id,
        "request_key": "directory-independent-qa",
    }
    first = client.post(
        ROOT + f"/individual-tasks/{project['id']}", headers=h, json=payload
    )
    assert first.status_code == 201, first.text
    assert first.json()["total"] == 1 and first.json()["status"] == "Completed"
    retry = client.post(
        ROOT + f"/individual-tasks/{project['id']}", headers=h, json=payload
    )
    assert retry.status_code == 201 and retry.json()["id"] == first.json()["id"]
    assert db.query(PMSTask).filter_by(id=first.json()["task_id"]).count() == 1
    row = (
        db.query(PMSTaskAssignee)
        .filter_by(task_id=first.json()["task_id"], user_id=member.id)
        .one()
    )
    assert (
        row.source_key.startswith("intern-distribution:")
        and row.reviewer_user_id == owner.id
    )
    assert client.get(
        ROOT + f"/assignment-jobs/{first.json()['id']}", headers=oh
    ).status_code in [403, 404]


def test_twenty_thousand_people_are_paginated_and_bulk_assignments_resume(
    client, db, directory_data
):
    from app.models.employee import Employee
    from app.apps.interns_hub.management_models import InternBatchMembership
    from time import perf_counter

    data, _, _ = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    started = perf_counter()
    db.bulk_insert_mappings(
        User,
        [
            {
                "email": f"scale-{i:05d}@directory.test",
                "hashed_password": "fixture-only",
                "is_active": i % 7 != 0,
            }
            for i in range(20000)
        ],
    )
    accounts = (
        db.query(User.id, User.email)
        .filter(User.email.like("scale-%@directory.test"))
        .order_by(User.id)
        .all()
    )
    db.bulk_insert_mappings(
        CommonPerson,
        [
            {
                "user_id": u.id,
                "organization_id": 1,
                "primary_email": u.email,
                "display_name": f"Scale Person {i:05d}",
                "status": "active" if i % 7 else "suspended",
            }
            for i, u in enumerate(accounts)
        ],
    )
    active = [u for i, u in enumerate(accounts) if i % 7][:600]
    db.bulk_insert_mappings(
        Employee,
        [
            {
                "employee_id": f"DIR-SCALE-{i}",
                "first_name": "Scale",
                "last_name": str(i),
                "user_id": u.id,
                "employment_type": "Intern",
                "department_id": member.employee.department_id,
                "date_of_joining": date(2026, 1, 1),
                "status": "Active",
            }
            for i, u in enumerate(active)
        ],
    )
    db.flush()
    employees = (
        db.query(Employee.id).filter(Employee.user_id.in_([u.id for u in active])).all()
    )
    db.bulk_insert_mappings(
        InternBatchMembership,
        [
            {
                "batch_id": batch.id,
                "employee_id": e.id,
                "assigned_by": owner.id,
                "status": "Active",
            }
            for e in employees
        ],
    )
    db.commit()
    response = client.get(
        ROOT + "/people", headers=h, params={"page_size": 24, "page": 200, "q": "Scale"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 20000 and len(response.json()["items"]) == 24
    assert len(response.content) < 60000
    params = {
        "q": "Scale Person 19998",
        "status": "active",
        "registered_from": "2026-01-01",
    }
    assert client.get(ROOT + "/people", headers=h, params=params).json()["total"] == 1
    payload = {
        "task": {
            "title": "Large independently tracked assignment",
            "task_key": "DIR-SCALE-JOB",
            "due_date": str(date.today() + timedelta(days=7)),
        },
        "batches": [batch.id],
        "reviewer_user_id": owner.id,
        "request_key": "directory-scale-job",
    }
    first = client.post(
        ROOT + f"/individual-tasks/{project['id']}", headers=h, json=payload
    )
    assert first.status_code == 201, first.text
    job = first.json()
    assert (
        job["processed"] == 500 and job["total"] == 601 and job["status"] == "Pending"
    )
    resumed = client.post(ROOT + f"/assignment-jobs/{job['id']}/continue", headers=h)
    assert resumed.status_code == 200, resumed.text
    assert (
        resumed.json()["processed"] == 601 and resumed.json()["status"] == "Completed"
    )
    repeated = client.post(ROOT + f"/assignment-jobs/{job['id']}/continue", headers=h)
    assert repeated.json()["processed"] == 601
    assert db.query(PMSTaskAssignee).filter_by(task_id=job["task_id"]).count() == 601
    detail = client.get(BASE + f"/task-studio/tasks/{job['task_id']}", headers=h)
    assert detail.status_code == 200, detail.text
    assert (
        detail.json()["protected_count"] == 601
        and len(detail.json()["retained_people"]) <= 100
    )
    edited = client.put(
        BASE + f"/task-studio/tasks/{job['task_id']}",
        headers=h,
        json={
            "task": {"title": "Updated large assignment"},
            "assignment": detail.json()["assignment"],
            "version": detail.json()["version"],
        },
    )
    assert edited.status_code == 200, edited.text
    assert db.query(PMSTaskAssignee).filter_by(task_id=job["task_id"]).count() == 601
    print(
        f"Disposable SQLite scale fixture: 20,000 people and 601 assignments in {perf_counter()-started:.2f}s; not production timing"
    )


def test_private_teams_and_narrow_scope_do_not_expose_unauthorized_people(
    client, db, directory_data
):
    from app.apps.project_management.people_workspace import scope, group_detail

    data, _, _ = directory_data
    owner, member, outsider, h, mh, oh, project, team, batch = data
    team.visibility = "members"
    team.members = [PMSWorkspaceTeamMember(user_id=owner.id)]
    team.member_ids_json = json.dumps([owner.id])
    db.commit()
    from app.apps.project_management.people_workspace import teams_query

    assert teams_query(db, member).all() == []
    for path, params in [
        (ROOT + "/groups", {"kind": "teams"}),
        (BASE + f"/workspaces/{project['workspace_id']}/teams", {}),
        (BASE + "/task-studio/options", {"project_id": project["id"], "compact": True}),
    ]:
        response = client.get(path, headers=mh, params=params)
        assert response.status_code in {200, 403}, response.text
        if response.status_code == 200:
            assert response.json().get("items", response.json().get("teams")) == []
    member._suite_grants = {
        "project_management": {
            "enabled": True,
            "scope": "own",
            "role": "member",
            "actions": ["view"],
        }
    }
    assert [u.id for u in scope(db, member)] == [member.id]
