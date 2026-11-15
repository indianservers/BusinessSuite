from uuid import uuid4
from sqlalchemy import select
from app.apps.srm.models import SRMEngagement
from app.business_packs.accounting_firm.models import AccountsEngagementCommand
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity, body, revision, send
from tests.test_accounts_actual_time import delivery


def test_genuine_new_engagement_link_preserves_birth_and_exact_retry(client, db, accounts, delivery):
    response = client.post('/api/v1/srm/accounts/engagements', headers=accounts['headers'], json={
        'request_key': str(uuid4()), 'client_id': 101, 'name': 'Canonical project-linked service'})
    assert response.status_code == 201, response.text
    engagement = response.json()
    birth = db.connection().execute(select(AccountsEngagementCommand.__table__).where(
        AccountsEngagementCommand.__table__.c.engagement_id == engagement['id'])).mappings().one()
    original_digest = birth['source_sha256']
    row = send(client, accounts['headers'], '', body(accounts) | {'engagement_id': engagement['id']}, status=201)
    payload = revision(row) | {'project_id': delivery}
    result = send(client, accounts['headers'], f"/{row['id']}/project", payload)
    assert result['birth_sha256'] == original_digest
    assert send(client, accounts['headers'], f"/{row['id']}/project", payload) == result
    current = client.get('/api/v1/srm/accounts/engagements/' + str(engagement['id']), headers=accounts['headers'])
    assert current.status_code == 200, current.text
    assert db.get(SRMEngagement, engagement['id']).pms_project_id == delivery
    assert db.get(AccountsEngagementCommand, birth['id']).source_sha256 == original_digest
    assert db.get(AccountsEngagementCommand, birth['id']).source_snapshot['pms_project_id'] is None
    send(client, accounts['headers'], f"/{row['id']}/project", payload | {'request_key': str(uuid4())}, status=409)
