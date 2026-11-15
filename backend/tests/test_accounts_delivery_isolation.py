from uuid import uuid4
import pytest
from app.apps.project_management.models import PMSTimeLog
from app.apps.srm.models import SRMInvoice, SRMReceipt
from app.business_packs.accounting_firm.models import AccountsCommand
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity, create, revision
from tests.test_business_pack_http_integration import grant


@pytest.mark.parametrize('pack,role', [('hospital','doctor'), ('restaurant','chef'), ('construction','site_engineer')])
def test_multi_assigned_actor_cannot_cross_pack_delivery_or_finance(client, db, accounts, pack, role):
    row = create(client, accounts)
    other, _ = grant(db, accounts['manager'], accounts['branch'], pack, role)
    headers = accounts['headers'] | {'X-Suite-Pack-Context': str(other.id)}
    root = f"/api/v1/srm/accounts/periods/{row['id']}"
    for path, payload in [
        ('/documents', revision(row) | {'title':'Foreign request','due_on':row['due_on']}),
        ('/time', revision(row) | {'log_date':'2026-01-15','duration_minutes':30,'description':'Foreign work'}),
        ('/invoice', revision(row) | {'expected_work_revision':1,'amount':'100.00'}),
        ('/payments', {'request_id':str(uuid4()),'amount':'1.00','payment_method':'cash'}),
        ('/project', revision(row) | {'project_id':1}),
    ]:
        response = client.post(root + path, headers=headers, json=payload)
        assert response.status_code == 403, (pack, path, response.text)
    assert client.get(root + '/documents', headers=headers).status_code == 403
    assert db.query(PMSTimeLog).count() == db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0
    assert db.query(AccountsCommand).count() == 1
