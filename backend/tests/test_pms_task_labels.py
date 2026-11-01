from tests.test_pms_task_studio import studio
from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import BASE, middleware_database


def test_task_list_and_assignee_filter_use_person_names_without_employee(client, db, studio):
    owner, member, _, headers, _, _, project, _, _ = studio
    owner.person.display_name = "Delivery Manager"
    member.person.display_name = "Second Collaborator"
    db.commit()
    created = client.post(f"{BASE}/projects/{project['id']}/tasks", headers=headers,
                          json={"title": "Named collaborator", "task_key": "LABEL-1", "assignee_user_ids": [owner.id, member.id]})
    assert created.status_code == 200, created.text
    assert created.json()["reporter_user_id"] == owner.id
    response = client.get(BASE + "/tasks", headers=headers, params={"projectId": project["id"]})
    assert response.status_code == 200, response.text
    data = response.json()
    task = next(item for item in data["items"] if item["id"] == created.json()["id"])
    assert task["assignee_name"] == "Delivery Manager"
    assert {person["name"] for person in task["assignees"]} == {"Delivery Manager", "Second Collaborator"}
    assert any(person["id"] == owner.id and person["name"] == "Delivery Manager" for person in data["filters"]["assignees"])
