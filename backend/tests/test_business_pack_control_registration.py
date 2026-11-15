"""Installed settings router uses native company control; no operational release."""
from fastapi.routing import iter_route_contexts
from app.main import app
from app.core.security import create_access_token
from app.models.company import Company, Branch
from app.business_packs.models import PackContext
from tests.test_business_pack_configuration import owner

ROOT = '/api/v1/access/settings/business-packs'


def headers(actor, branch='99999999'):
    return {'Authorization': 'Bearer ' + create_access_token(actor.id),
            'X-Suite-Organization': '1', 'X-Suite-Branch': str(branch)}


def test_registered_control_routes_use_genuine_company_administrator(client, db, owner):
    actor, branch, _, member = owner
    assert not actor.is_superuser and not member.is_superuser
    paths = {route.path for route in iter_route_contexts(app.router.routes)}
    assert ROOT + '/catalog' in paths
    assert '/api/v1/srm/service-checkout' not in paths
    assert '/api/v1/srm/pharma/returns' not in paths
    assert '/api/v1/srm/restaurant/tabs' not in paths
    # A stale remembered operational branch must not hide company settings.
    response = client.get(ROOT + '/catalog', headers=headers(actor))
    assert response.status_code == 200, response.text
    assert len(response.json()['items']) == 7
    denied = client.get(ROOT + '/configuration', headers={
        **headers(member, branch.id), 'X-Suite-Pack-Context': '99999999'})
    assert denied.status_code == 403, denied.text
    readiness = client.get(ROOT + '/readiness', headers=headers(actor), params={'pack_key': 'hospital'})
    assert readiness.status_code == 200, readiness.text
    assert not readiness.json()['ready'] and not readiness.json()['isolation_ready']


def test_foreign_company_branch_cannot_be_enrolled_through_registered_control(client, db, owner):
    actor, branch, _, _ = owner
    foreign_company = Company(name='Foreign protected company')
    db.add(foreign_company); db.flush()
    foreign_branch = Branch(company_id=foreign_company.id, name='Foreign protected branch')
    db.add(foreign_branch); db.commit()
    draft = client.post(ROOT + '/activations', headers=headers(actor, branch.id), json={
        'pack_key': 'hospital', 'expected_revision': 0, 'reason': 'Reviewed company draft'})
    assert draft.status_code == 201, draft.text
    before = db.query(PackContext).count()
    response = client.post(ROOT + '/contexts', headers=headers(actor, branch.id), json={
        'activation_id': draft.json()['id'], 'activation_revision': draft.json()['revision'],
        'branch_id': foreign_branch.id, 'expected_revision': 0, 'reason': 'Foreign source denied'})
    assert response.status_code in (403, 404), response.text
    assert db.query(PackContext).count() == before
