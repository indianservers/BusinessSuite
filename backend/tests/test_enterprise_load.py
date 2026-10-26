"""Opt-in disposable-database scale profile, not a production capacity claim."""

import os, time, json, statistics
from pathlib import Path
import pytest
from sqlalchemy import func
from app.models.user import User
from app.models.company import Company
from app.common.models import CommonPerson
from app.apps.crm.models import CRMLead
from app.module_registry import APP_MODULES, AppModule
from app.access.catalog import MODULES
from app.core.config import settings
from tests.test_shared_services import shared_setup, access_account


@pytest.mark.skipif(
    os.getenv("RUN_ENTERPRISE_LOAD") != "1",
    reason="Opt-in isolated enterprise scale profile",
)
def test_enterprise_scale_profile(client, db, shared_setup):
    headers, user, lead = shared_setup
    accounts = int(os.getenv("ENTERPRISE_LOAD_USERS", "10000"))
    companies = int(os.getenv("ENTERPRISE_LOAD_COMPANIES", "100"))
    records = int(os.getenv("ENTERPRISE_LOAD_LEADS", "10000"))
    samples = int(os.getenv("ENTERPRISE_LOAD_SAMPLES", "20"))
    assert (
        1 <= accounts <= 100000
        and 1 <= companies <= 1000
        and 1 <= records <= 100000
        and 5 <= samples <= 100
    )
    start_company = (db.query(func.max(Company.id)).scalar() or 0) + 1
    company_ids = list(range(start_company, start_company + companies - 1))
    db.bulk_insert_mappings(
        Company,
        [
            {"id": i, "name": f"Load company {i}", "is_active": True}
            for i in company_ids
        ],
    )
    start_user = (db.query(func.max(User.id)).scalar() or 0) + 1
    users = [
        {
            "id": start_user + i,
            "email": f"load-{i}@scale.example.test",
            "hashed_password": user.hashed_password,
            "is_active": True,
            "is_superuser": False,
        }
        for i in range(max(0, accounts - db.query(User).count()))
    ]
    db.bulk_insert_mappings(User, users)
    pool = [1, *company_ids]
    db.bulk_insert_mappings(
        CommonPerson,
        [
            {
                "user_id": row["id"],
                "primary_email": row["email"],
                "organization_id": pool[index % len(pool)],
                "display_name": f"Load user {index}",
                "status": "active",
            }
            for index, row in enumerate(users)
        ],
    )
    db.bulk_insert_mappings(
        CRMLead,
        [
            {
                "organization_id": 1,
                "owner_user_id": user.id,
                "full_name": f"Load lead {i}",
                "first_name": "Load",
                "status": "New" if i % 2 else "Qualified",
            }
            for i in range(records)
        ],
    )
    db.commit()
    installed = list(settings.INSTALLED_APPS)
    added = []
    try:
        for i in range(max(0, 25 - len(APP_MODULES))):
            key = f"load_module_{i}"
            added.append(key)
            APP_MODULES[key] = AppModule(key=key, label=f"Load module {i}")
        settings.INSTALLED_APPS = installed + added
        timings = []
        for _ in range(samples):
            started = time.perf_counter()
            response = client.get(
                "/api/v1/access/enterprise/analytics",
                headers=headers,
                params={"companyId": 1, "source": "crm_leads"},
            )
            timings.append((time.perf_counter() - started) * 1000)
            assert response.status_code == 200, response.text
            assert response.json()["count"] >= records
        timings.sort()
        p = lambda fraction: round(
            timings[min(samples - 1, int((samples - 1) * fraction))], 2
        )
        report = {
            "profile": "sequential authorized analytics; synthetic account/company/module metadata and real CRM rows",
            "users": db.query(User).count(),
            "companies": db.query(Company).count(),
            "registeredModules": len(APP_MODULES),
            "leads": records,
            "requests": samples,
            "p50Ms": p(0.50),
            "p95Ms": p(0.95),
            "p99Ms": p(0.99),
            "throughputPerSecond": round(samples / (sum(timings) / 1000), 2),
            "errorRate": 0,
            "acceptanceP95Ms": 2000,
            "concurrentActivityVerified": False,
            "resourceTelemetry": "not configured",
        }
        assert report["p95Ms"] < report["acceptanceP95Ms"], report
        Path("../docs/qa/suite-access/phase3-load.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    finally:
        settings.INSTALLED_APPS = installed
        for key in added:
            APP_MODULES.pop(key, None)
            MODULES.pop(key, None)
