"""Local-only due-work runner. No mail delivery or remote service calls."""
import asyncio
import logging
from sqlalchemy.engine import make_url
from app.core.config import settings

logger = logging.getLogger(__name__)


def check_once():
    from app.platform_owner.session import platform_factory
    from app.platform_owner.models import PlatformAdmin
    from app.platform_owner.api import run_due_work
    from app.db.session import SessionLocal
    with platform_factory()() as owner_db, SessionLocal() as business_db:
        owner = owner_db.query(PlatformAdmin).filter_by(role="owner", is_active=True).order_by(PlatformAdmin.id).first()
        if owner:
            run_due_work(owner_db, business_db, owner)


async def run():
    if settings.ENVIRONMENT == "test" or not settings.PLATFORM_DATABASE_URL:
        return
    cycles=0
    while True:
        await asyncio.sleep(30)
        try:
            await asyncio.to_thread(signup_cycle)
            cycles+=1
            if cycles%10==0 and settings.ENVIRONMENT=="development" and make_url(settings.PLATFORM_DATABASE_URL).host in {"127.0.0.1","localhost"}:
                await asyncio.to_thread(check_once)
        except Exception as exc:
            logger.warning("Local platform due-work check failed: %s", type(exc).__name__)


def signup_cycle():
    from app.platform_owner.session import platform_factory
    from app.db.session import LegacySessionLocal
    from app.platform_owner.signup_journey import due_work,deliver,synchronize_logins
    with platform_factory()() as owner,LegacySessionLocal() as business:
        due_work(owner)
        deliver(owner,business)
        synchronize_logins(owner,business)
