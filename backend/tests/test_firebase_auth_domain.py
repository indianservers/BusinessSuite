import json
from pathlib import Path


def test_google_auth_domain_is_opt_in_and_preserves_other_provider_config(monkeypatch):
    from app.core.config import settings
    from app.api.v1.auth import firebase_login_config
    import app.module_registry
    monkeypatch.setattr(app.module_registry, "is_app_enabled", lambda _: True)
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "fixture-project")
    monkeypatch.setattr(settings, "FIREBASE_WEB_CONFIG", {
        "projectId": "fixture-project", "apiKey": "fixture-public-key",
        "appId": "fixture-app", "authDomain": "fixture-project.firebaseapp.com",
    })
    monkeypatch.setattr(settings, "FIREBASE_GOOGLE_AUTH_DOMAIN", "")
    assert "googleAuthDomain" not in firebase_login_config()["firebase_config"]
    monkeypatch.setattr(settings, "FIREBASE_GOOGLE_AUTH_DOMAIN", "app.fixture.example")
    config = firebase_login_config()["firebase_config"]
    assert config["googleAuthDomain"] == "app.fixture.example"
    assert config["authDomain"] == "fixture-project.firebaseapp.com"
    assert "googleAuthDomain" not in settings.FIREBASE_WEB_CONFIG


def test_auth_helper_proxy_precedes_spa_and_uses_the_configured_firebase_project():
    config = json.loads((Path(__file__).resolve().parents[2] / "vercel.json").read_text())
    routes = config["rewrites"]
    auth = next(r for r in routes if r["source"] == "/__/auth/:path*")
    assert auth["destination"] == "https://mlvisualizationsaimersweb.firebaseapp.com/__/auth/:path*"
    assert routes.index(auth) < next(i for i,r in enumerate(routes) if r["source"] == "/(.*)")
