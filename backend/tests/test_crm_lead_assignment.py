from datetime import date

from app.apps.crm.models import CRMActivity, CRMLead, CRMTimelineEvent
from app.common.models import CommonPerson
from app.core.security import get_password_hash
from app.models.employee import Employee
from app.models.notification import Notification
from app.models.user import Permission, Role, User

ROOT = "/api/v1/crm/lead-management"


def employee_account(
    db, suffix, permissions=("crm_leads_manage",), status="Active", organization=1
):
    role = Role(name=f"assignment_{suffix}", is_system=False)
    for name in permissions:
        permission = db.query(Permission).filter_by(name=name).first()
        if not permission:
            permission = Permission(name=name, module="crm", description=name)
            db.add(permission)
        role.permissions.append(permission)
    db.add(role)
    db.flush()
    user = User(
        email=f"{suffix}@example.com",
        hashed_password=get_password_hash("Sales@123456"),
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    employee = Employee(
        employee_id=f"EMP-{suffix}",
        user_id=user.id,
        first_name="Priya",
        last_name=suffix,
        date_of_joining=date(2026, 1, 1),
        status=status,
    )
    db.add(employee)
    db.add(
        CommonPerson(
            user_id=user.id,
            organization_id=organization,
            display_name=f"Priya {suffix}",
            primary_email=user.email,
            status="active",
        )
    )
    db.commit()
    return user, employee


def test_assignment_directory_uses_employee_names_codes_and_login_identifiers(
    client, db, superuser_headers
):
    # Directory identifiers must not accidentally use the independent employees.id sequence.
    db.add(
        Employee(
            id=500,
            employee_id="EMP-unlinked",
            first_name="Unlinked",
            last_name="Employee",
            date_of_joining=date(2026, 1, 1),
            status="Active",
        )
    )
    db.commit()
    user, employee = employee_account(db, "sales")
    before = db.query(User).count()
    response = client.get(ROOT + "/settings", headers=superuser_headers)
    assert response.status_code == 200, response.text
    entry = next(owner for owner in response.json()["owners"] if owner["id"] == user.id)
    assert entry["employeeId"] == employee.id and entry["id"] != employee.id
    assert entry["name"] == "Priya sales (EMP-sales)"
    unavailable = response.json()["unavailableEmployees"]
    assert any(
        item["employeeCode"] == "EMP-unlinked" and "login" in item["reason"]
        for item in unavailable
    )
    assert db.query(User).count() == before


def test_assigning_employee_routes_lead_and_notifies_their_login(
    client, db, superuser_headers
):
    user, employee = employee_account(db, "recipient")
    response = client.post(
        ROOT + "/leads",
        headers=superuser_headers,
        json={"values": {"full_name": "Assigned Prospect", "owner_user_id": user.id}},
    )
    assert response.status_code == 201, response.text
    lead = response.json()
    assert lead["owner_user_id"] == user.id
    notice = (
        db.query(Notification)
        .filter_by(event_type="lead_assignment", user_id=user.id)
        .one()
    )
    assert notice.related_entity_id == lead["id"]
    login = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "Sales@123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get(ROOT + "/leads?queue=my_day", headers=headers)
    assert any(item["id"] == lead["id"] for item in response.json()["items"])


def test_reassignment_moves_pending_followups_and_is_idempotent(
    client, db, superuser_headers
):
    first, _ = employee_account(db, "first")
    second, _ = employee_account(db, "second")
    lead = client.post(
        ROOT + "/leads",
        headers=superuser_headers,
        json={
            "values": {"full_name": "Reassigned Prospect", "owner_user_id": first.id}
        },
    ).json()
    endpoint = ROOT + f"/leads/{lead['id']}"
    client.post(
        endpoint + "/sequence",
        headers=superuser_headers,
        json={"name": "Standard follow-up"},
    )
    response = client.patch(
        endpoint,
        headers=superuser_headers,
        json={"values": {"owner_user_id": second.id}},
    )
    assert response.status_code == 200, response.text
    assert {
        a.owner_user_id
        for a in db.query(CRMActivity)
        .filter_by(lead_id=lead["id"], status="Pending")
        .all()
    } == {second.id}
    client.patch(
        endpoint,
        headers=superuser_headers,
        json={"values": {"owner_user_id": second.id}},
    )
    assert (
        db.query(Notification)
        .filter_by(event_type="lead_assignment", user_id=second.id)
        .count()
        == 1
    )
    event = (
        db.query(CRMTimelineEvent)
        .filter_by(record_id=lead["id"], event_type="assignment")
        .order_by(CRMTimelineEvent.id.desc())
        .first()
    )
    assert event.metadata_json["previousOwnerId"] == first.id


def test_ineligible_employees_cannot_be_assigned_through_workbench_or_classic_api(
    client, db, superuser_headers
):
    no_crm, _ = employee_account(db, "hr-only", permissions=("employees_view",))
    inactive, _ = employee_account(db, "terminated", status="Terminated")
    foreign, _ = employee_account(db, "foreign", organization=2)
    disabled, _ = employee_account(db, "disabled")
    disabled.is_active = False
    db.commit()
    response = client.get(ROOT + "/settings", headers=superuser_headers).json()
    eligible = {owner["id"] for owner in response["owners"]}
    assert not eligible.intersection({no_crm.id, inactive.id, foreign.id, disabled.id})
    assert all(
        item["employeeCode"] != "EMP-foreign"
        for item in response["unavailableEmployees"]
    )
    foreign.is_active = False
    db.commit()
    response = client.get(ROOT + "/settings", headers=superuser_headers).json()
    assert all(
        item["employeeCode"] != "EMP-foreign"
        for item in response["unavailableEmployees"]
    )
    for user in [no_crm, inactive, foreign, disabled]:
        response = client.post(
            ROOT + "/leads",
            headers=superuser_headers,
            json={"values": {"full_name": "Blocked", "owner_user_id": user.id}},
        )
        assert response.status_code == 422, response.text
        response = client.post(
            "/api/v1/crm/leads",
            headers=superuser_headers,
            json={"firstName": "Blocked", "fullName": "Blocked", "ownerId": user.id},
        )
        assert response.status_code == 422, response.text


def test_manual_assignment_wins_over_automatic_routing_in_both_apis(
    client, db, superuser_headers
):
    from copy import deepcopy
    from app.apps.crm.lead_management import DEFAULTS

    automatic, _ = employee_account(db, "automatic")
    manual, _ = employee_account(db, "manual")
    settings = deepcopy(DEFAULTS)
    settings["assignment"] = {
        "mode": "round_robin",
        "ownerIds": [automatic.id],
        "rules": [],
    }
    assert (
        client.put(
            ROOT + "/settings", headers=superuser_headers, json=settings
        ).status_code
        == 200
    )
    response = client.post(
        ROOT + "/leads",
        headers=superuser_headers,
        json={"values": {"full_name": "Manual Choice", "owner_user_id": manual.id}},
    )
    assert response.status_code == 201, response.text
    assert response.json()["owner_user_id"] == manual.id
    response = client.post(
        "/api/v1/crm/leads",
        headers=superuser_headers,
        json={
            "firstName": "Classic",
            "fullName": "Classic Manual Choice",
            "ownerId": manual.id,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["owner_user_id"] == manual.id


def test_crm_admin_permission_allows_assignment_even_with_custom_role_name(
    client, db, superuser_headers
):
    admin, _ = employee_account(db, "custom-admin", permissions=("crm_admin",))
    recipient, _ = employee_account(db, "admin-recipient")
    login = client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": "Sales@123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert recipient.id in {
        owner["id"]
        for owner in client.get(ROOT + "/settings", headers=headers).json()["owners"]
    }
    response = client.post(
        ROOT + "/leads",
        headers=headers,
        json={"values": {"full_name": "Admin Assigned", "owner_user_id": recipient.id}},
    )
    assert response.status_code == 201, response.text
