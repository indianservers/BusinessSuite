from app.apps.saas.models import MarketplaceApp, MarketplaceInstall
from phase10_test_utils import auth_headers


def test_internal_marketplace_listing_install_and_uninstall(client, db):
    headers = auth_headers(client, db, permissions=["marketplace_view", "marketplace_manage"])
    create = client.post("/api/v1/marketplace/apps", json={"name": "Internal Extension", "category": "internal", "description": "Internal only"}, headers=headers)
    assert create.status_code == 201, create.text
    app_id = create.json()["id"]
    assert db.query(MarketplaceApp).first().internal_only is True

    install = client.post(f"/api/v1/marketplace/apps/{app_id}/install", headers=headers)
    assert install.status_code == 201
    assert db.query(MarketplaceInstall).first().status == "installed"

    installed = client.get("/api/v1/marketplace/installed", headers=headers)
    assert installed.json()["total"] == 1
    uninstall = client.post(f"/api/v1/marketplace/apps/{app_id}/uninstall", headers=headers)
    assert uninstall.status_code == 200
