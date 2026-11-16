"""Release gate tests against real, unpublished Pharma runtime support."""
import pytest
from app.business_packs import runtime
from app.business_packs.models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability
from tests.test_branch_access import setup


@pytest.mark.parametrize('branch_selection', ['company', 'owned', 'missing'])
def test_unpublished_pharma_readiness_denies_without_mutating_native_sources(db, branch_selection):
    _, branch, *_ = setup(db)
    models = (PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability)
    before = tuple(db.query(model).count() for model in models)
    branch_id = None if branch_selection == 'company' else branch.id if branch_selection == 'owned' else 999999
    first = runtime.activation_readiness(db, 1, 'pharma', branch_id)
    second = runtime.activation_readiness(db, 1, 'pharma', branch_id)
    assert first == second
    assert first['schema_ready'] is True
    assert first['ready'] is first['isolation_ready'] is first['workflows_ready'] is False
    assert 'Operational pack isolation is not enabled for this release yet.' in first['reasons']
    assert 'The pack workflows are still being connected and verified.' in first['reasons']
    if branch_selection == 'missing':
        assert 'An active branch belonging to this company is required.' in first['reasons']
    assert tuple(db.query(model).count() for model in models) == before
