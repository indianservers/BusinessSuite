from app.core.security import get_password_hash
from app.apps.crm.models import CRMDeal, CRMPipeline, CRMPipelineStage
from app.models.user import Permission, Role, User


ALL_ANALYTICS_PERMISSIONS = [
    "analytics_view",
    "analytics_manage",
    "analytics_report_builder",
    "analytics_export",
    "analytics_schedule",
    "analytics_financial_view",
    "analytics_profitability_view",
    "analytics_admin",
]


def analytics_headers(client, db, email: str = "analytics-admin@example.com", permissions: list[str] | None = None):
    role = Role(name=f"role-{email}", description="Analytics test role", is_system=False)
    db.add(role)
    db.flush()
    for name in (ALL_ANALYTICS_PERMISSIONS if permissions is None else permissions):
        permission = db.query(Permission).filter(Permission.name == name).first()
        if not permission:
            permission = Permission(name=name, description=name, module="analytics")
            db.add(permission)
            db.flush()
        role.permissions.append(permission)
    user = User(email=email, hashed_password=get_password_hash("Password@123"), is_active=True, role_id=role.id)
    db.add(user)
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Password@123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_report(client, headers, module_name: str = "crm_deals"):
    response = client.post("/api/v1/analytics/reports", headers=headers, json={"name": "Pipeline Report", "module_name": module_name, "report_type": "table", "visibility": "public"})
    assert response.status_code == 201, response.text
    return response.json()


def create_analytics_deal(db, name: str, amount: int, probability: int = 50):
    pipeline = CRMPipeline(name=f"{name} Pipeline", is_default=True, active=True)
    db.add(pipeline)
    db.flush()
    stage = CRMPipelineStage(pipeline_id=pipeline.id, name="Open", probability=probability, stage_type="open", active=True)
    db.add(stage)
    db.flush()
    deal = CRMDeal(name=name, amount=amount, status="Open", probability=probability, pipeline_id=pipeline.id, stage_id=stage.id)
    db.add(deal)
    db.commit()
    return deal
