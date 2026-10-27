"""Explicit tenant/environment/ownership checks in addition to suite guards."""
from fastapi import HTTPException
from app.apps.power_apps.models import PowerActivity, PowerEnvironment, PowerVersion
from app.apps.power_apps.registry import ENVIRONMENTS

def organization(user):
    value = getattr(user, "organization_id", None)
    if not value:
        raise HTTPException(403, "An authorized organization context is required")
    return int(value)

def scoped(db, model, user, environment):
    query = db.query(model).filter(model.organization_id == organization(user), model.environment == environment)
    grant = (getattr(user, "_suite_grants", None) or {}).get("power_apps", {})
    # Narrow scopes fail closed to ownership until team/assignment support exists.
    if not user.is_superuser and grant.get("scope") != "organization":
        query = query.filter(model.owner_user_id == user.id)
    return query

def validate_environment(db, user, environment):
    if environment not in ENVIRONMENTS:
        raise HTTPException(422, "Unknown Power Apps environment")
    row = db.query(PowerEnvironment).filter_by(organization_id=organization(user), key=environment).first()
    if row and row.enabled:
        return environment
    raise HTTPException(403, "Environment is not enabled for this organization")

def serialize(row):
    return {col.name: getattr(row, col.name) for col in row.__table__.columns}

def record_change(db, user, resource, action, snapshot=True):
    db.add(PowerActivity(organization_id=resource.organization_id, environment=resource.environment,
        resource_id=resource.id, owner_user_id=resource.owner_user_id, actor_user_id=user.id,
        action=action, resource_name=resource.name))
    if snapshot:
        db.add(PowerVersion(organization_id=resource.organization_id, resource_id=resource.id,
            version=resource.version, created_by=user.id, owner_user_id=resource.owner_user_id,
            snapshot={"name": resource.name, "description": resource.description, "definition": resource.definition, "status": resource.status, "archived": resource.archived_at is not None}))
