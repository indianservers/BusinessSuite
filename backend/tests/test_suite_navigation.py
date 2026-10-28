from app.access.models import AccessMembership
from app.common.models import CommonPerson
from app.models.company import Company
from app.models.notification import Notification
from app.models.user import User
from app.core.security import create_access_token


def test_access_returns_names_only_for_member_companies(client, db, superuser_headers):
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    if not db.get(Company, 1): db.add(Company(id=1, name="Primary", is_active=True))
    db.add_all([Company(id=20, name="Member company", is_active=True), Company(id=21, name="Private company", is_active=True)])
    db.add(AccessMembership(user_id=actor.id, company_id=20, active=True))
    db.commit()
    result = client.get("/api/v1/access/me", headers=superuser_headers)
    assert result.status_code == 200, result.text
    assert {org["id"] for org in result.json()["organizations"]} == {1, 20}
    assert {org["name"] for org in result.json()["organizations"]} >= {"Member company"}


def test_notification_summary_and_app_filter_are_personal_and_company_scoped(client, db, superuser_headers):
    actor = db.query(User).filter_by(email="testadmin@test.com").one()
    if not db.get(Company, 1): db.add(Company(id=1, name="Primary", is_active=True))
    db.add(Company(id=20, name="Other", is_active=True))
    other = User(email="other-nav@test.com", hashed_password="unused", is_active=True)
    db.add(other); db.flush()
    for user, company, module, url, read in [(actor.id, 1, "leave", "/leave", False), (actor.id, 1, "hrms", "/hrms/profile", False), (actor.id, 1, "crm", "/crm/contacts", False), (actor.id, 1, "hrms", "/hrms/profile", True), (actor.id, 20, "hrms", "/hrms/profile", False), (other.id, 1, "hrms", "/hrms/profile", False)]:
        db.add(Notification(user_id=user, company_id=company, module=module, action_url=url, title="Test", message="Test", priority="normal", channels=["in_app"], is_read=read))
    db.commit()
    summary = client.get("/api/v1/notifications/summary", headers=superuser_headers)
    assert summary.status_code == 200, summary.text
    assert sum(group["count"] for group in summary.json()["groups"]) == 3
    feed = client.get("/api/v1/notifications/?app=hrms&unread_only=true", headers=superuser_headers)
    assert feed.status_code == 200, feed.text
    assert feed.json()["total"] == 2
    assert {item["module"] for item in feed.json()["items"]} == {"leave", "hrms"}


def test_notification_summary_requires_authentication(client):
    assert client.get("/api/v1/notifications/summary").status_code in {401, 403}


def test_company_names_are_available_to_regular_members_across_their_workspaces(client, db):
    db.add_all([Company(id=1, name="Primary member company", is_active=True), Company(id=20, name="Second member company", is_active=True), Company(id=21, name="Inactive membership", is_active=True)])
    actor = User(email="member-nav@example.com", hashed_password="unused", is_active=True,
                 person=CommonPerson(organization_id=1, primary_email="member-nav@example.com", display_name="Member"))
    db.add(actor); db.flush()
    db.add_all([AccessMembership(user_id=actor.id, company_id=20, active=True), AccessMembership(user_id=actor.id, company_id=21, active=False)])
    db.commit()
    response = client.get("/api/v1/access/me", headers={"Authorization": f"Bearer {create_access_token(str(actor.id))}"})
    assert response.status_code == 200, response.text
    assert {org["id"] for org in response.json()["organizations"]} == {1, 20}
