from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy.orm import Session
from app.apps.saas.api.router import _ensure_default_plans
from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan


def test_fresh_subscription_bootstrap_is_safe_for_concurrent_requests(db_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL transaction lock integration test")
    barrier = Barrier(2)

    def bootstrap():
        with Session(db_engine) as session:
            barrier.wait(timeout=10)
            _ensure_default_plans(session)
            session.commit()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: bootstrap(), range(2)))
        with Session(db_engine) as session:
            assert session.query(TenantSubscriptionPlan).count() == 4
            assert session.query(TenantSubscription).count() == 1
    finally:
        with Session(db_engine) as session:
            session.query(TenantSubscription).delete()
            session.query(TenantSubscriptionPlan).delete()
            session.commit()
