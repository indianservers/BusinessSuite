"""One login's Doctor/Stylist, Chef and Construction grants stay contextual."""
from app.business_packs.models import PackActivation, PackContext, PackUserGrant
from tests.test_industry_assignment import assigned


def test_multiple_pack_grants_never_union_service_or_financial_permissions(assigned):
    p = assigned
    user = p.users['a']
    branch = p.employees['a'].branch_id
    activation = PackActivation(company_id=1, pack_key='construction', pack_version=1, state='active')
    p.db.add(activation); p.db.flush()
    construction = PackContext(company_id=1, branch_id=branch, activation_id=activation.id,
        pack_key='construction', pack_version=1, state='active')
    p.db.add(construction); p.db.flush()
    for context, role in [(p.contexts['restaurant'], 'chef'), (construction, 'business_owner')]:
        p.db.add(PackUserGrant(company_id=1, branch_id=branch, context_id=context.id, user_id=user.id, role=role))
    p.db.commit()
    original = dict(p.headers['a'])
    ident = p.appts['a'].id
    for context in [p.contexts['restaurant'], construction]:
        headers = {**original, 'X-Suite-Pack-Context': str(context.id)}
        response = p.client.post(f'/api/v1/srm/industry/records/{ident}/transition', headers=headers,
            json={'status': 'in_service', 'expected_revision': 1})
        assert response.status_code in (403, 404), response.text
        assert 'A assigned' not in response.text
    # Other grants do not lend billing/configuration capabilities to a clinician.
    response = p.client.get(f'/api/v1/srm/industry/appointments/{ident}/billing', headers=original)
    assert response.status_code == 403, response.text
    response = p.client.get('/api/v1/srm/service-checkout/options/providers', headers=original)
    assert response.status_code == 403, response.text
    own = p.client.get('/api/v1/srm/industry/records', params={'kind': 'appointment'}, headers=original)
    assert own.status_code == 200, own.text
    assert [row['id'] for row in own.json()['items']] == [ident]
    for status, revision in [('in_service', 1), ('completed', 2)]:
        response = p.client.post(f'/api/v1/srm/industry/records/{ident}/transition', headers=original,
            json={'status': status, 'expected_revision': revision})
        assert response.status_code == 200, response.text
        assert 'unit_price' not in response.json()['data']
