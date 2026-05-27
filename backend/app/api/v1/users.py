from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.services.identity import SharedIdentityService
from app.core.deps import get_current_user, get_db
from app.models.user import User


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/search")
def search_users(
    q: str = Query("", max_length=100),
    limit: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = SharedIdentityService.organization_id_for_user(current_user) or 1
    users = SharedIdentityService.search_users(db, query=q, limit=limit, organization_id=company_id)
    items = [
        {
            "id": user.user_id,
            "email": user.email,
            "displayName": user.display_name,
            "role": user.role,
            "personId": user.person_id,
        }
        for user in users
    ]
    return {"items": items, "total": len(items)}
