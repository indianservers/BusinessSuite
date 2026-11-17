"""Administrative reads can materialize reports without authorizing business writes."""
from dataclasses import replace
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.branches.boundary import install
from app.branches.service import context
from app.branches.models import BranchOwnership
from app.apps.srm.models import SRMEngagement, SRMProfitabilitySnapshot
from app.apps.crm.models import CRMCompany
from app.models.audit import AuditLog
from app.ai_agents.models import AiAuditLog
from tests.test_branch_access import setup


@pytest.mark.parametrize('case', ['allowed', 'missing_marker', 'wrong_parent', 'wrong_table', 'read_only_parent', 'foreign_company', 'write_request'])
def test_read_derivative_requires_exact_native_parent_and_writable_branch(db, case):
    user, a, b, *_ = setup(db)
    user.is_superuser = True
    engagement = SRMEngagement(organization_id=1, engagement_number='READ-DERIVED', name='Report source')
    db.add(engagement); db.flush()
    db.add(BranchOwnership(company_id=1, branch_id=a.id, resource_table='srm_engagements', resource_key=str(engagement.id), source='test-native-source'))
    db.commit()
    ctx = context(db, user, 1, 'all')
    if case == 'read_only_parent':
        ctx = replace(ctx, writable=frozenset({b.id}))
    cleanup = install(db, user, ctx)
    db.info['security_write_request'] = case == 'write_request'
    db.info['derived_read_parents'] = {} if case == 'missing_marker' else {
        'crm_companies' if case == 'wrong_table' else 'srm_profitability_snapshots':
            frozenset({engagement.id + 99 if case == 'wrong_parent' else engagement.id})}
    row = SRMProfitabilitySnapshot(organization_id=2 if case == 'foreign_company' else 1, engagement_id=engagement.id)
    try:
        db.add(row)
        if case == 'allowed':
            db.flush()
            branch = db.connection().execute(select(BranchOwnership.branch_id).where(
                BranchOwnership.resource_table == 'srm_profitability_snapshots', BranchOwnership.resource_key == str(row.id))).scalar_one()
            assert branch == a.id
        else:
            with pytest.raises(HTTPException):
                db.flush()
    finally:
        cleanup(); db.rollback()
        db.info.pop('security_write_request', None)
        db.info.pop('derived_read_parents', None)


@pytest.mark.parametrize('case', ['allowed', 'another_actor', 'foreign_company', 'write_request', 'business_record'])
@pytest.mark.parametrize('audit_kind', ['http', 'ai'])
def test_company_read_audit_exception_never_grants_transaction_authority(db, case, audit_kind):
    user, *_ = setup(db)
    user.is_superuser = True
    db.commit()
    cleanup = install(db, user, context(db, user, 1, 'all'))
    db.info['security_write_request'] = case == 'write_request'
    row = CRMCompany(organization_id=1, name='No implicit transaction') if case == 'business_record' else (AiAuditLog(
        organization_id=2 if case == 'foreign_company' else 1,
        user_id=user.id + 99 if case == 'another_actor' else user.id,
        module='CRM', action='AI_POLICY_ALLOWED', status='success') if audit_kind == 'ai' else AuditLog(
        organization_id=2 if case == 'foreign_company' else 1,
        user_id=user.id + 99 if case == 'another_actor' else user.id, method='GET', endpoint='/api/v1/report', action='EXPORT'))
    try:
        db.add(row)
        if case == 'allowed':
            db.flush()
            assert row.id is not None
        else:
            with pytest.raises(HTTPException):
                db.flush()
    finally:
        cleanup(); db.rollback()
        db.info.pop('security_write_request', None)


@pytest.mark.parametrize('case', ['allowed', 'another_actor', 'foreign_company', 'write_request', 'business_record'])
def test_ai_read_audit_on_readonly_branch_does_not_grant_business_writes(db, case):
    user, branch, *_ = setup(db)
    ctx = replace(context(db, user, 1, str(branch.id)), writable=frozenset())
    cleanup = install(db, user, ctx)
    db.info['security_write_request'] = case == 'write_request'
    row = CRMCompany(organization_id=1, name='No implicit write') if case == 'business_record' else AiAuditLog(
        organization_id=2 if case == 'foreign_company' else 1,
        user_id=user.id + 99 if case == 'another_actor' else user.id,
        module='CRM', action='AI_POLICY_ALLOWED', status='success')
    try:
        db.add(row)
        if case == 'allowed':
            db.flush()
            owned = db.connection().execute(select(BranchOwnership.branch_id).where(
                BranchOwnership.resource_table == 'ai_audit_logs', BranchOwnership.resource_key == str(row.id))).scalar_one()
            assert owned == branch.id
        else:
            with pytest.raises(HTTPException):
                db.flush()
    finally:
        cleanup(); db.rollback()
        db.info.pop('security_write_request', None)
