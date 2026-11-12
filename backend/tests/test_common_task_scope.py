"""Shared task lists filter existing links without duplicating task identities."""
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import middleware_database
from tests.test_record_360 import seeded
from tests.test_pms_task_record_links import targets
from app.apps.project_management.models import PMSTask, PMSTaskRecordLink
from app.apps.project_management.task_record_links import link_record


@pytest.mark.parametrize("source", ["all", "pms"])
def test_project_and_all_filters_keep_original_tasks(client, db, source):
    user, headers, _, _, _, task, _ = seeded(db)
    response = client.get("/api/v1/project-management/tasks", params={"sourceModule": source}, headers=headers)
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == [task.id]
    assert db.query(PMSTask).count() == 1


def test_crm_filter_uses_multiple_links_without_duplicate_rows(client, db):
    user, headers, company, _, project, task, _ = seeded(db)
    contact, lead = targets(db, company)
    unlinked = PMSTask(project_id=project.id, task_key="R360-2", title="Unlinked project task")
    db.add(unlinked); db.commit()
    for kind, record in [("contact", contact), ("lead", lead)]:
        link_record(db, user, task.id, kind, record.id)
    response = client.get("/api/v1/project-management/tasks?sourceModule=crm", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert [row["id"] for row in response.json()["items"]] == [task.id]
    assert db.query(PMSTask).count() == 2


def test_crm_filter_excludes_cross_tenant_link(client, db):
    user, headers, company, _, _, task, _ = seeded(db)
    contact, _ = targets(db, company)
    db.add(PMSTaskRecordLink(organization_id=2, task_id=task.id, contact_id=contact.id))
    db.commit()
    response = client.get("/api/v1/project-management/tasks?sourceModule=crm", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


def test_deleted_crm_target_does_not_qualify_task(client, db):
    from datetime import datetime, timezone
    user, headers, company, _, _, task, _ = seeded(db)
    contact, lead = targets(db, company)
    link_record(db, user, task.id, "lead", lead.id)
    lead.deleted_at = datetime.now(timezone.utc); db.commit()
    response = client.get("/api/v1/project-management/tasks?sourceModule=crm", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0
    assert db.query(PMSTaskRecordLink).count() == 1
    assert db.get(PMSTask, task.id) is not None


def test_pms_membership_does_not_grant_crm_filter_access(client, db):
    from tests.test_pms_workspaces import account
    from tests.tenant_test_utils import assign_company
    from app.apps.project_management.models import PMSProjectMember
    _, _, _, _, project, _, _ = seeded(db)
    viewer, headers = account(db, "common-task-viewer@test.com")
    assign_company(db, viewer, 1)
    db.add(PMSProjectMember(project_id=project.id, user_id=viewer.id, role="Viewer"))
    db.commit()
    response = client.get("/api/v1/project-management/tasks?sourceModule=crm", headers=headers)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("source", ["hrms", "srm", "unknown", "CRM"])
def test_unsupported_task_associations_rejected(client, db, source):
    _, headers, *_ = seeded(db)
    response = client.get("/api/v1/project-management/tasks", params={"sourceModule": source}, headers=headers)
    assert response.status_code == 422
