"""Pack switches change labels only after exact current grant verification."""
from copy import deepcopy

import pytest

from tests.test_business_pack_access import packs, denied
from app.business_packs.presentation import effective_profile
from app.business_packs.models import PackUserGrant
from app.business_packs.registry import list_packs
from app.shared.business_profile import PROFILES, effective
from app.shared.models import ServicePolicy


def test_every_pack_has_explicit_presentation_template():
    assert {pack.key for pack in list_packs()} <= PROFILES.keys()
    assert PROFILES['accounting_firm']['terms']['provider'] == ['Accountant', 'Accountants']


def test_switching_pack_changes_words_without_mutating_company_preferences(packs):
    p = packs
    policy = ServicePolicy(organization_id=1, kind='business_profile',
        scope_key='business-profile:company:1', version=1, updated_by=p.users['admin'].id,
        values_json={'business_type': 'construction', 'terms': {'customer': ['Site buyer', 'Site buyers']}})
    p.db.add(policy)
    p.db.add(PackUserGrant(company_id=1, branch_id=p.branches['a'].id,
        context_id=p.contexts['chef'].id, user_id=p.users['doctor'].id, role='chef'))
    p.db.commit()
    before = deepcopy(effective(p.db, 1))
    hospital = effective_profile(p.db, p.users['doctor'], p.ctx(), str(p.contexts['doctor'].id))
    restaurant = effective_profile(p.db, p.users['doctor'], p.ctx(), str(p.contexts['chef'].id))
    assert hospital['terms']['customer'] == ['Patient', 'Patients']
    assert hospital['packKey'] == 'hospital'
    assert restaurant['business_type'] == 'restaurant'
    assert restaurant['terms']['customer'] != hospital['terms']['customer']
    assert restaurant['packContextId'] == p.contexts['chef'].id
    assert effective(p.db, 1) == before
    assert policy.version == 1


@pytest.mark.parametrize('target', ['chef', 'builder', 'foreign'])
def test_presentation_cannot_select_foreign_pack_or_branch(packs, target):
    denied(lambda: effective_profile(packs.db, packs.users['doctor'], packs.ctx(),
                                    str(packs.contexts[target].id)))


def test_revoked_pack_never_falls_back_to_company_words(packs):
    p = packs
    assert effective_profile(p.db, p.users['doctor'], p.ctx())['packKey'] == 'hospital'
    p.grants['doctor'].active = False
    p.db.commit()
    denied(lambda: effective_profile(p.db, p.users['doctor'], p.ctx()))
    denied(lambda: effective_profile(p.db, p.users['doctor'], p.ctx(), str(p.contexts['doctor'].id)))


def test_legacy_unconfigured_branch_keeps_existing_preferences(packs):
    p = packs
    result = effective_profile(p.db, p.users['doctor'], p.ctx('unconfigured'))
    assert result['business_type'] == effective(p.db, 1, p.branches['unconfigured'].id)['business_type']
    assert 'packContextId' not in result


@pytest.mark.parametrize('selected', ['', 'invalid', '0', '-1', '１'])
def test_invalid_selector_never_returns_legacy_words(packs, selected):
    denied(lambda: effective_profile(packs.db, packs.users['doctor'], packs.ctx('unconfigured'), selected))


def test_unverified_branch_cannot_select_pack(packs):
    denied(lambda: effective_profile(packs.db, packs.users['doctor'], None, str(packs.contexts['doctor'].id)))


def test_native_effective_endpoint_verifies_raw_selected_header(client, packs):
    from app.core.security import create_access_token
    from app.branches.models import BranchGrant
    p = packs
    p.db.add(BranchGrant(company_id=1, branch_id=p.branches['a'].id,
                         user_id=p.users['doctor'].id, can_write=True))
    p.db.commit()
    headers = {'Authorization': 'Bearer ' + create_access_token(p.users['doctor'].id),
               'X-Suite-Organization': '1', 'X-Suite-Branch': str(p.branches['a'].id),
               'X-Suite-Pack-Context': str(p.contexts['doctor'].id)}
    url = '/api/v1/access/settings/business-profile/effective'
    response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['packKey'] == 'hospital'
    assert response.json()['terms']['customer'] == ['Patient', 'Patients']
    for selector in ('invalid', str(p.contexts['chef'].id)):
        denied_response = client.get(url, headers={**headers, 'X-Suite-Pack-Context': selector})
        assert denied_response.status_code == 403, denied_response.text
    p.grants['doctor'].active = False
    p.db.commit()
    assert client.get(url, headers=headers).status_code == 403
