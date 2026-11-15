"""Activation requires installed native apps and code-owned workflow support."""
from types import MappingProxyType

import pytest

from app.business_packs import runtime
from app.business_packs.registry import get_pack
from app.models.company import Company
from tests.test_branch_access import setup


def supported(monkeypatch, key='hospital'):
    manifest = get_pack(key)
    monkeypatch.setattr(runtime, 'RUNTIME_SUPPORT', MappingProxyType({key:
        runtime.PackRuntimeSupport(manifest.version, 1,
                                  frozenset(workflow.key for workflow in manifest.workflows))}))


def test_registered_pack_alone_cannot_be_activated(db):
    _, branch, *_ = setup(db)
    result = runtime.activation_readiness(db, 1, 'hospital', branch.id)
    assert result['schema_ready'] is True
    assert result['ready'] is result['isolation_ready'] is result['workflows_ready'] is False


def test_even_verified_workflows_require_installed_native_modules(db, monkeypatch):
    _, branch, *_ = setup(db)
    supported(monkeypatch)
    monkeypatch.setattr('app.module_registry.is_app_enabled', lambda key: key != 'hrms')
    result = runtime.activation_readiness(db, 1, 'hospital', branch.id)
    assert result['isolation_ready'] and result['workflows_ready']
    assert not result['ready']
    assert any('hrms' in reason for reason in result['reasons'])


@pytest.mark.parametrize('company_id, branch_id', [(999999, None), (1, 999999)])
def test_runtime_support_never_bypasses_real_company_or_branch(db, monkeypatch, company_id, branch_id):
    setup(db)
    supported(monkeypatch)
    result = runtime.activation_readiness(db, company_id, 'hospital', branch_id)
    assert not result['ready']
    assert any('active' in reason for reason in result['reasons'])


def test_retired_company_cannot_activate_even_supported_workflows(db, monkeypatch):
    _, branch, *_ = setup(db)
    supported(monkeypatch)
    db.get(Company, 1).is_active = False
    db.flush()
    assert not runtime.activation_readiness(db, 1, 'hospital', branch.id)['ready']


@pytest.mark.parametrize('pack,workflow', [('retail','returns'),('pharma','recalls')])
@pytest.mark.parametrize('unavailable_by', ['license','module','company_control'])
def test_supported_refund_workflow_never_claims_ready_without_accounting(db,monkeypatch,pack,workflow,unavailable_by):
    _, branch, *_ = setup(db)
    supported(monkeypatch,pack)
    monkeypatch.setattr('app.access.entitlements.states',lambda *args: {'fam':unavailable_by!='license'})
    monkeypatch.setattr('app.module_registry.is_app_enabled',lambda key: key!='fam' or unavailable_by!='module')
    monkeypatch.setattr('app.enterprise.controls.disabled_modules',lambda *args: {'fam'} if unavailable_by=='company_control' else set())
    result=runtime.activation_readiness(db,1,pack,branch.id)
    assert result['isolation_ready'] and result['workflows_ready']
    assert not result['ready'] and not result['workflow_modules_ready']
    assert result['missing_workflow_modules']=={workflow:['fam']}
    assert any('fam' in reason for reason in result['reasons'])


def test_workflow_prerequisite_check_does_not_enable_optional_accounting(db,monkeypatch):
    _, branch, *_ = setup(db)
    supported(monkeypatch,'retail')
    monkeypatch.setattr('app.access.entitlements.states',lambda *args: {'fam':True})
    monkeypatch.setattr('app.module_registry.is_app_enabled',lambda key: True)
    monkeypatch.setattr('app.enterprise.controls.disabled_modules',lambda *args: set())
    result=runtime.activation_readiness(db,1,'retail',branch.id)
    assert result['workflow_modules_ready']
    assert result['missing_workflow_modules']=={}
    assert result['ready']
    assert 'fam' in get_pack('retail').optional_modules
