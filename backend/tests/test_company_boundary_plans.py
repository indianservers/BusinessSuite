"""Warm company plans must retain live ownership and request identity checks."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import update

from app.core.tenant_boundary import install, _company_plan
from app.apps.crm.models import CRMLead
from app.models.company import Company
from tests.test_company_security_boundary import tenants


def test_warm_plan_reuses_expressions_but_reads_current_ownership(db, tenants):
    user = tenants['users'][0]
    own, foreign = tenants['leads']
    for _ in range(2):
        cleanup = install(db, user, 1)
        try:
            assert [row.id for row in db.query(CRMLead)] == [own.id]
        finally:
            cleanup()
    warmed = _company_plan.cache_info()
    db.connection().execute(update(CRMLead.__table__).where(CRMLead.id == foreign.id).values(organization_id=1))
    cleanup = install(db, user, 1)
    try:
        assert {row.id for row in db.query(CRMLead)} == {own.id, foreign.id}
        assert _company_plan.cache_info().hits == warmed.hits + 1
    finally:
        cleanup()


def test_warm_plan_cannot_cross_company_or_skip_active_company_check(db, tenants):
    actor = SimpleNamespace(id=tenants['users'][0].id, is_superuser=True)
    for company in (1, 2, 1, 2):
        cleanup = install(db, actor, company, enforce_superuser_company=True)
        try:
            assert {row.organization_id for row in db.query(CRMLead)} == {company}
        finally:
            cleanup()
    db.connection().execute(update(Company.__table__).where(Company.id == 2).values(is_active=False))
    with pytest.raises(HTTPException) as error:
        install(db, actor, 2, enforce_superuser_company=True)
    assert error.value.status_code == 403


def test_warm_plan_does_not_cache_verified_membership(db, tenants):
    from app.access.models import AccessMembership
    actor = tenants['users'][0]
    cleanup = install(db, actor, 1)
    cleanup()
    db.add(AccessMembership(user_id=actor.id, company_id=1, active=False))
    db.flush()
    with pytest.raises(HTTPException) as error:
        install(db, actor, 1)
    assert error.value.status_code == 403
