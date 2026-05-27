from sqlalchemy.orm import Session

from app.common.services.identity import IdentitySummary, SharedIdentityService


class CrmIdentityService:
    @staticmethod
    def owner_summary(db: Session, user_id: int) -> IdentitySummary | None:
        return SharedIdentityService.contact_for_user(db, user_id)

    @staticmethod
    def search_owners(db: Session, query: str = "", limit: int = 10) -> list[IdentitySummary]:
        return SharedIdentityService.search_users(db, query=query, limit=limit)
