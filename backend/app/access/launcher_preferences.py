"""Private, company-scoped launcher favorites shared across a user's devices."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.shared.models import ServicePolicy

router = APIRouter(prefix="/launcher-preferences", tags=["Launcher preferences"])


class Favorites(BaseModel):
    model_config = ConfigDict(extra="forbid")
    favorites: list[str] = Field(max_length=100)

    @field_validator("favorites")
    @classmethod
    def validate_keys(cls, keys):
        import re
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", key) for key in keys):
            raise ValueError("Invalid application key")
        return list(dict.fromkeys(keys))


def own_preferences(db, actor):
    return db.query(ServicePolicy).filter_by(
        scope_key=f"launcher:{actor.organization_id}:{actor.id}",
        organization_id=actor.organization_id, kind="launcher_preferences",
        updated_by=actor.id,
    ).first()


@router.get("")
def get_preferences(db: Session = Depends(get_db), actor=Depends(get_current_user)):
    row = own_preferences(db, actor)
    return {"favorites": row.values_json.get("favorites", []) if row else None}


@router.put("")
def save_preferences(data: Favorites, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    row = own_preferences(db, actor)
    if row is None:
        row = ServicePolicy(scope_key=f"launcher:{actor.organization_id}:{actor.id}",
            organization_id=actor.organization_id, kind="launcher_preferences",
            module_key="*", updated_by=actor.id, values_json={})
        db.add(row)
    else:
        row.version += 1
    row.values_json = data.model_dump()
    db.commit()
    return row.values_json
