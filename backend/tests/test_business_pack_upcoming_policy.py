"""Narrowed release labels and activation hold; no production publication."""
import pytest
from app.business_packs.registry import get_pack
from app.business_packs.service import manifest_output
from app.business_packs.release_policy import UPCOMING_REASON

@pytest.mark.parametrize('key',['retail','pharma','restaurant'])
def test_upcoming_catalog(key):
    output=manifest_output(get_pack(key))
    assert output['label']==get_pack(key).label+' (Upcoming)'
    assert output['release_status']=='upcoming' and output['activation_ready'] is False

@pytest.mark.parametrize('key',['hospital','salon','accounting_firm','construction'])
def test_selected_four_have_no_false_readiness(key):
    output=manifest_output(get_pack(key))
    assert output['label']==get_pack(key).label
    assert output['release_status']=='review_required' and output['activation_ready'] is False

@pytest.mark.parametrize('key',['retail','pharma','restaurant'])
def test_policy_overrides_hypothetical_future_support(db,monkeypatch,key):
    from app.models.company import Company
    from app.business_packs import runtime
    from app.access import entitlements
    from app.enterprise import controls
    from app import module_registry
    from app.business_packs.restaurant import schema_readiness
    if db.get(Company,1) is None:db.add(Company(id=1,name='Upcoming policy test',is_active=True));db.commit()
    monkeypatch.setattr(runtime,'schema_ready',lambda db:True)
    monkeypatch.setattr(entitlements,'states',lambda db,company:{m:True for m in ('hrms','crm','project_management','srm','fam')})
    monkeypatch.setattr(controls,'disabled_modules',lambda db,company:set())
    monkeypatch.setattr(module_registry,'is_app_enabled',lambda module:True)
    monkeypatch.setattr(schema_readiness,'installation_reasons',lambda connection:[])
    manifest=get_pack(key)
    monkeypatch.setattr(runtime,'RUNTIME_SUPPORT',{key:runtime.PackRuntimeSupport(1,1,frozenset(w.key for w in manifest.workflows))})
    output=runtime.activation_readiness(db,1,key)
    assert output['isolation_ready'] is True and output['workflows_ready'] is True
    assert output['ready'] is False and UPCOMING_REASON in output['reasons']
