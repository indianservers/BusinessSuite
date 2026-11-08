import pytest
from tests.fam_test_utils import fam_admin_headers,create_party,ledger_by_nature


def source_profile(client,db,kind='bill'):
    headers=fam_admin_headers(client,db)
    expense=ledger_by_nature(client,headers,'expense')
    vendor=create_party(client,headers,'vendor','REC-VENDOR','Recurring supplier')
    line={'expense_ledger_id':expense['id'],'description':'Monthly services','taxable_value':500,'gst_amount':25}
    if kind=='bill':
        endpoint='purchase-bills';body={'vendor_id':vendor['id'],'bill_number':'REC-SOURCE','bill_date':'2026-06-06','lines':[line]}
    else:
        endpoint='expenses';body={'claim_number':'REC-SOURCE','claim_date':'2026-06-06','payable_ledger_id':vendor['ledger_id'],'lines':[line]}
    source=client.post('/api/v1/fam/'+endpoint,headers=headers,json=body)
    assert source.status_code==201,source.text
    body={'kind':kind,'source_id':source.json()['id'],'name':'Monthly supplier services','start_date':'2020-01-31','rule':'monthly','occurrences':2,'payment_terms_days':14}
    profile=client.post('/api/v1/fam/recurring-purchases',headers=headers,json=body)
    assert profile.status_code==201,profile.text
    return headers,source.json(),profile.json(),body,endpoint


@pytest.mark.parametrize('kind',['bill','expense'])
def test_native_recurring_purchase_drafts_are_anchored_and_idempotent(client,db,kind):
    from app.apps.fam.recurring_purchases import dispatch_due
    headers,source,profile,body,endpoint=source_profile(client,db,kind)
    assert client.post('/api/v1/fam/recurring-purchases',headers=headers,json=body).status_code==409
    assert dispatch_due(db)=={'created':2,'failed_profiles':0}
    assert dispatch_due(db)=={'created':0,'failed_profiles':0}
    profiles=client.get('/api/v1/fam/recurring-purchases',headers=headers).json()
    current=next(r for r in profiles if r['id']==profile['id'])
    assert current['status']=='completed'
    assert [r['date'] for r in current['history']]==['2020-01-31','2020-02-29']
    assert 'template' not in current
    records=client.get('/api/v1/fam/'+endpoint,headers=headers).json()['items']
    generated=[r for r in records if r['id']!=source['id']]
    assert len(generated)==2
    assert all(r['status']=='draft' and r['grand_total']==525 for r in generated)
    if kind=='bill':
        assert sorted(r['due_date'] for r in generated)==['2020-02-14','2020-03-14']


def test_schedule_pause_resume_uses_versions(client,db):
    from app.apps.fam.recurring_purchases import dispatch_due
    headers,_,profile,_,_=source_profile(client,db)
    path=f'/api/v1/fam/recurring-purchases/{profile["id"]}/status'
    paused=client.put(path,headers=headers,json={'status':'paused','expected_version':profile['version']})
    assert paused.status_code==200,paused.text
    assert dispatch_due(db)['created']==0
    stale=client.put(path,headers=headers,json={'status':'active','expected_version':profile['version']})
    assert stale.status_code==409
    resumed=client.put(path,headers=headers,json={'status':'active','expected_version':paused.json()['version']})
    assert resumed.status_code==200,resumed.text
    assert dispatch_due(db)['created']==2


def test_failure_rolls_back_draft_and_schedule_cursor_together(client,db,monkeypatch):
    from app.apps.fam.recurring_purchases import dispatch_due
    from app.apps.fam.api import router
    headers,_,profile,_,endpoint=source_profile(client,db,'expense')
    original=router.create_expense
    def fail_after_flush(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('Simulated worker interruption before atomic commit')
    monkeypatch.setattr(router,'create_expense',fail_after_flush)
    assert dispatch_due(db)=={'created':0,'failed_profiles':1}
    assert 'fam_recurring_transaction' not in db.info
    assert len(client.get('/api/v1/fam/'+endpoint,headers=headers).json()['items'])==1
    current=client.get('/api/v1/fam/recurring-purchases',headers=headers).json()[0]
    assert current['next_index']==0 and not current['history']
    monkeypatch.setattr(router,'create_expense',original)
    assert dispatch_due(db)=={'created':2,'failed_profiles':0}
