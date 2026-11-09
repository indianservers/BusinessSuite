from tests.test_settings_hub import actor
from app.models.company import Company
from app.access.models import AccessMembership

URL = "/api/v1/access/launcher-preferences"


def test_favorites_persist_order_clear_and_isolate_users(client, db):
    first, _ = actor(db, role="favorite-first")
    second, _ = actor(db, role="favorite-second")
    assert client.get(URL, headers=first).json() == {"favorites": None}
    result = client.put(URL, headers=first, json={"favorites": ["crm", "hrms", "crm"]})
    assert result.status_code == 200, result.text
    assert result.json() == {"favorites": ["crm", "hrms"]}
    assert client.get(URL, headers=first).json() == result.json()
    assert client.get(URL, headers=second).json() == {"favorites": None}
    assert client.put(URL, headers=first, json={"favorites": ["hrms", "crm"]}).status_code == 200
    assert client.get(URL, headers=first).json()["favorites"] == ["hrms", "crm"]
    assert client.put(URL, headers=first, json={"favorites": []}).status_code == 200
    assert client.get(URL, headers=first).json()["favorites"] == []


def test_favorites_company_boundary_and_validation(client, db):
    headers, user = actor(db, role="favorite-company")
    db.add(Company(id=77, name="Other favorites company")); db.flush()
    db.add(AccessMembership(user_id=user.id, company_id=77, active=True, is_admin=False)); db.commit()
    second = {**headers, "X-Suite-Organization": "77"}
    assert client.put(URL, headers=headers, json={"favorites": ["crm"]}).status_code == 200
    assert client.get(URL, headers=second).json() == {"favorites": None}
    assert client.put(URL, headers=second, json={"favorites": ["pms"]}).status_code == 200
    assert client.get(URL, headers=headers).json()["favorites"] == ["crm"]
    for payload in [{"favorites": ["../bad"]}, {"favorites": ["crm"] * 101}, {"favorites": [], "user_id": 2}]:
        assert client.put(URL, headers=headers, json=payload).status_code == 422
    assert client.get(URL).status_code in (401, 403)

