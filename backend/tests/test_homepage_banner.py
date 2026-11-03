from io import BytesIO
from PIL import Image
from tests.test_settings_hub import actor, BASE

BANNER = "/api/v1/access/homepage-banner"
PUBLIC = "/api/v1/auth/homepage-banner"


def test_banner_admin_required_and_company_scoped(client, db):
    employee, _ = actor(db)
    admin, _ = actor(db, role="banner-admin", admin=True)
    default = client.get(PUBLIC).json()
    assert client.put(BANNER, headers=employee, json=default).status_code == 403
    changed = {**default, "x": 10, "zoom": 1.5, "image": ""}
    assert client.put(BANNER, headers=admin, json=changed).status_code == 200
    assert client.get(BANNER, headers=employee).json()["x"] == 10
    assert client.get(PUBLIC).json() == default
    assert client.get(BANNER, headers={**employee, "X-Suite-Organization": "77"}).status_code == 403
    assert "appearance" in {o["id"] for o in client.get(BASE, headers=admin).json()["options"]}
    assert client.get(BASE+"/appearance", headers=employee).status_code == 403


def test_upload_validation_publication_and_reset(client, db):
    admin, _ = actor(db, role="banner-admin", admin=True)
    employee, _ = actor(db)
    stream = BytesIO()
    Image.new("RGB", (1200, 300), "blue").save(stream, "PNG")
    files = {"file": ("banner.png", stream.getvalue(), "image/png")}
    assert client.post(BANNER+"/upload", headers=employee, files=files).status_code == 403
    assert client.post(BANNER+"/upload", headers=admin, files={"file": ("bad.png", b"bad", "image/png")}).status_code == 422
    uploaded = client.post(BANNER+"/upload", headers=admin, files=files)
    assert uploaded.status_code == 201, uploaded.text
    reference = uploaded.json()["image"]
    image_url = PUBLIC+"/assets/"+reference[6:]
    response = client.get(image_url)
    assert response.status_code == 404, response.text
    default = client.get(PUBLIC).json()
    assert client.put(BANNER, headers=admin, json={**default, "image": reference}).status_code == 200
    assert client.get(image_url).headers["content-type"] == "image/webp"
    assert client.put(BANNER, headers=admin, json=default).status_code == 200
    response = client.get(image_url)
    assert response.status_code == 404, response.text


def test_banner_rejects_unsafe_urls_and_invalid_controls(client, db):
    admin, _ = actor(db, role="banner-admin", admin=True)
    default = client.get(PUBLIC).json()
    for image in ["http://example.com/image.jpg", "https://127.0.0.1/a.png", "https://localhost/a.png", "javascript:alert(1)", "data:image/png;base64,xx", "https://user:pass@example.com/a.png"]:
        assert client.put(BANNER, headers=admin, json={**default, "image": image}).status_code == 422
    for invalid in [{"zoom": 0}, {"x": 101}, {"opacity": 2}, {"overlay": "red"}, {"organization_id": 77}, {"image": "asset:123-"+"a"*64}]:
        assert client.put(BANNER, headers=admin, json={**default, **invalid}).status_code == 422



def test_company_banners_and_uploads_cannot_cross_organizations(client, db):
    from app.models.company import Company
    from app.access.models import AccessMembership
    admin, user = actor(db, role="banner-admin", admin=True)
    db.add(Company(id=77, name="Second company"))
    db.flush()
    db.add(AccessMembership(user_id=user.id, company_id=77, active=True, is_admin=True))
    db.commit()
    second = {**admin, "X-Suite-Organization": "77"}
    default = client.get(PUBLIC).json()
    assert client.put(BANNER, headers=admin, json={**default, "x": 11}).status_code == 200
    assert client.put(BANNER, headers=second, json={**default, "x": 88}).status_code == 200
    assert client.get(BANNER, headers=admin).json()["x"] == 11
    assert client.get(BANNER, headers=second).json()["x"] == 88
    stream = BytesIO()
    Image.new("RGB", (100, 100), "blue").save(stream, "PNG")
    image = client.post(BANNER+"/upload", headers=admin, files={"file": ("banner.png", stream.getvalue(), "image/png")}).json()["image"]
    assert client.put(BANNER, headers=second, json={**default, "image": image}).status_code == 422
