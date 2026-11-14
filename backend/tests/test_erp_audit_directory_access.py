import pytest

from app.models.user import Role, User
from tests.payroll_test_utils import init_payroll_test_db


@pytest.mark.parametrize("role_name,expected", [
    ("employee", 403), ("crm_org_admin", 403), ("pms_org_admin", 200),
    ("HR Manager", 200), ("admin", 200),
])
def test_directory_api_applies_specific_directory_role_policy(client, db, role_name, expected):
    init_payroll_test_db(db)
    user = db.query(User).filter_by(email="employee@aihrms.com").one()
    role = db.query(Role).filter_by(name=role_name).first()
    if role is None:
        role = Role(name=role_name)
        db.add(role)
    user.role = role
    db.commit()
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Employee@123456"})
    assert login.status_code == 200
    response = client.get("/api/v1/users/directory", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert response.status_code == expected, response.text
    if expected == 200:
        assert any(row["email"] == user.email for row in response.json()["items"])
    else:
        assert "directory" in response.json()["detail"].lower()
