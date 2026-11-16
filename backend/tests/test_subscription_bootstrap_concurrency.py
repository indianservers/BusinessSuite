from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.apps.saas.api.router import _ensure_default_plans
from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
from tests.test_payroll_qa_concurrency import payroll_engine


def test_fresh_subscription_bootstrap_is_safe_for_concurrent_requests(db_engine, payroll_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL transaction lock integration test")
    primary = db_engine
    db_engine = payroll_engine
    def committed_primary_keys():
        with primary.connect() as connection:
            return {
                model.__tablename__: set(connection.execute(select(*model.__table__.primary_key.columns)).tuples())
                for model in (TenantSubscription, TenantSubscriptionPlan)
            }
    before = committed_primary_keys()
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
        # The existing UUID database fixture owns the entire committed graph.
        assert committed_primary_keys() == before
