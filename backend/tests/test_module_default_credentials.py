import pytest

from app.db.init_db import init_db
from app.models.user import User


MODULE_DEFAULT_CREDENTIALS = [
    ("hrms", "admin@aihrms.com", "Admin@123456"),
    ("hrms", "hr@aihrms.com", "HR@123456"),
    ("hrms", "manager@aihrms.com", "Manager@123456"),
    ("hrms", "employee@aihrms.com", "Employee@123456"),
    ("crm", "admin@vyaparacrm.com", "Password@123"),
    ("crm", "manager@vyaparacrm.com", "Password@123"),
    ("crm", "executive@vyaparacrm.com", "Password@123"),
    ("crm", "support@vyaparacrm.com", "Password@123"),
    ("crm", "marketing@vyaparacrm.com", "Password@123"),
    ("project_management", "admin@karyaflow.com", "Password@123"),
    ("project_management", "manager@karyaflow.com", "Password@123"),
    ("project_management", "member@karyaflow.com", "Password@123"),
    ("project_management", "client@karyaflow.com", "Password@123"),
    ("srm", "admin@srmflow.com", "Password@123"),
    ("srm", "sales.manager@srmflow.com", "Password@123"),
    ("srm", "sales.executive@srmflow.com", "Password@123"),
    ("srm", "finance@srmflow.com", "Password@123"),
    ("srm", "collections@srmflow.com", "Password@123"),
    ("fam", "admin@financeflow.com", "Password@123"),
    ("fam", "accountant@financeflow.com", "Password@123"),
    ("fam", "finance.manager@financeflow.com", "Password@123"),
    ("fam", "auditor@financeflow.com", "Password@123"),
    ("fam", "viewer@financeflow.com", "Password@123"),
]


@pytest.fixture()
def seeded_default_users(db):
    init_db(db)
    db.commit()


def test_advertised_module_default_credentials_login(client, seeded_default_users):
    failures = []
    for module, email, password in MODULE_DEFAULT_CREDENTIALS:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password, "module": module},
        )
        if response.status_code != 200:
            failures.append(f"{module}:{email} -> {response.status_code} {response.text}")
            continue
        payload = response.json()
        assert payload["email"] == email
        assert payload["access_token"]

    assert not failures, "\n".join(failures)


def test_default_credentials_are_repaired_on_seed(client, db):
    init_db(db)
    user = db.query(User).filter(User.email == "admin@vyaparacrm.com").one()
    user.hashed_password = "stale-broken-hash"
    db.commit()

    init_db(db)
    db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@vyaparacrm.com", "password": "Password@123", "module": "crm"},
    )

    assert response.status_code == 200, response.text


def test_module_default_credentials_stay_module_scoped(client, seeded_default_users):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@vyaparacrm.com", "password": "Password@123", "module": "fam"},
    )

    assert response.status_code == 403
