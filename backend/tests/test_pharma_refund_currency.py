"""Refund currency follows the immutable issued sale, never a different drawer."""
from decimal import Decimal
from app.models.company import Company
from app.apps.srm.models import SRMPOSSession,SRMInvoice,SRMInventoryBatch,SRMInventoryMovement,SRMPOSCashMovement,SRMPOSReturn,SRMPOSReturnLine
from app.apps.fam.models import FAMVoucher,FAMLedgerEntry,FAMLedger
from app.business_packs.pharma.return_models import PharmaReturn,PharmaReturnLine,PharmaReturnLot
from tests.test_pharma_returns_http import original,lots,pharma,scenario,catalog,directory_identity,post_original,command,BASE


def test_pharma_cash_refund_rejects_genuine_different_currency_drawer_atomically(client,db,original):
    post_original(db,original[3]);case=original[0][0];checkout=original[1]
    invoice=db.get(SRMInvoice,checkout['invoice']['id']);assert invoice.currency=='INR'
    old=db.get(SRMPOSSession,original[0][2]);old.status='closed'
    # A normal company currency change and actual native register creation do
    # not rewrite the already issued/paid INR invoice or any original receipt.
    db.get(Company,1).default_currency='USD';db.commit()
    opened=client.post('/api/v1/srm/pos/sessions',headers=case[0],json={'opening_cash':'1000'})
    assert opened.status_code==201,opened.text
    register=opened.json()['session'];assert register['metadata_json']['cash_currency']=='USD'
    models=(PharmaReturn,PharmaReturnLine,PharmaReturnLot,SRMPOSReturn,SRMPOSReturnLine,SRMInventoryBatch,SRMInventoryMovement,SRMPOSCashMovement,FAMVoucher,FAMLedgerEntry)
    before={model:db.query(model).count() for model in models};balances={row.id:(row.current_balance_dr,row.current_balance_cr) for row in db.query(FAMLedger)}
    body=command(original);body['refund']['session_id']=register['id']
    response=client.post(BASE,headers=case[0],json=body)
    assert response.status_code==409,response.text
    assert 'currency differs' in response.text,response.text
    assert all(db.query(model).count()==count for model,count in before.items())
    db.expire_all();assert {row.id:(row.current_balance_dr,row.current_balance_cr) for row in db.query(FAMLedger)}==balances
    assert db.get(SRMInvoice,checkout['invoice']['id']).currency=='INR'
    assert db.get(SRMPOSSession,register['id']).metadata_json['cash_currency']=='USD'
