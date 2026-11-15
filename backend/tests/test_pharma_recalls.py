"""Actual private recall command and canonical batch exclusion proofs."""
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from fastapi import HTTPException
from app.apps.srm.models import SRMInventoryBatch,SRMInventoryMovement,SRMSalesOrder,SRMInvoice,SRMReceipt
from app.business_packs.pharma.recall_models import PharmaRecall,PharmaRecallEvent,PharmaBatchControl
from app.business_packs.pharma.recall_schemas import RecallInput
from app.business_packs.pharma.recalls import create
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_pharma_fefo import lots,sale,lot_quantities
from tests.test_pharma_receipts import pharma,balance
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_srm_native_transaction_operations import native_writer

BASE='/api/v1/srm/pharma/recalls'


def request(lots,action='quarantine'):
    return {'request_key':str(uuid4()),'batch_id':lots[1][1]['batch_id'],'expected_batch_revision':0,'expected_batch_status':'available',
        'action':action,'reason':'Quality review for this batch'}


def counts(db):
    return tuple(db.connection().scalar(select(func.count()).select_from(model.__table__)) for model in (PharmaRecall,PharmaRecallEvent,PharmaBatchControl,SRMInventoryMovement,SRMSalesOrder,SRMInvoice,SRMReceipt))


def status(db,lots):
    return db.connection().scalar(select(SRMInventoryBatch.status).where(SRMInventoryBatch.id==lots[1][1]['batch_id']))


def test_quarantine_recall_close_history_replay_and_no_money_or_quantity_changes(client,db,lots):
    data=request(lots);stock=balance(db,lots[0]);quantities=lot_quantities(db,lots);before=counts(db)
    response=client.post(BASE,headers=lots[0][0],json=data);assert response.status_code==201,response.text
    first=response.json();assert first['batch_status']=='quarantined' and first['batch_revision']==1 and first['revision']==1
    assert status(db,lots)=='quarantined' and balance(db,lots[0])==stock and lot_quantities(db,lots)==quantities
    assert counts(db)[3:]==before[3:]
    recalled={'request_key':str(uuid4()),'expected_revision':1,'expected_batch_revision':1,'expected_batch_status':'quarantined','action':'recall','reason':'Recall confirmed after quality review'}
    response=client.post(f"{BASE}/{first['id']}/commands",headers=lots[0][0],json=recalled);assert response.status_code==200,response.text
    second=response.json();assert second['batch_status']=='recalled' and second['batch_revision']==2 and second['revision']==2
    closed={**recalled,'request_key':str(uuid4()),'expected_revision':2,'expected_batch_revision':2,'expected_batch_status':'recalled','action':'close','reason':'Review case closed; stock stays blocked'}
    response=client.post(f"{BASE}/{first['id']}/commands",headers=lots[0][0],json=closed);assert response.status_code==200,response.text
    third=response.json();assert third['state']=='closed' and third['revision']==3 and third['batch_revision']==2 and status(db,lots)=='recalled'
    assert client.post(BASE,headers=lots[0][0],json=data).json()==first
    assert client.post(f"{BASE}/{first['id']}/commands",headers=lots[0][0],json=recalled).json()==second
    assert client.post(f"{BASE}/{first['id']}/commands",headers=lots[0][0],json=closed).json()==third
    assert client.get(f"{BASE}/{first['id']}",headers=lots[0][0]).json()==third
    listed=client.get(BASE,headers=lots[0][0]);assert listed.status_code==200,listed.text
    assert listed.json()['items']==[third]
    assert counts(db)[:3]==(before[0]+1,before[1]+3,before[2]+1)
    assert counts(db)[3:]==before[3:] and balance(db,lots[0])==stock and lot_quantities(db,lots)==quantities
    denied=client.post('/api/v1/srm/service-checkout',headers=lots[0][0],json=sale(lots))
    assert denied.status_code==409,denied.text


@pytest.mark.parametrize('fault',['revision','status','unknown','empty_reason','foreign_batch','cashier','native_edit_revoked'])
def test_recall_denials_leave_canonical_status_and_private_history_unchanged(client,db,lots,fault):
    data=request(lots)
    if fault=='revision':data['expected_batch_revision']=1
    elif fault=='status':data['expected_batch_status']='quarantined'
    elif fault=='unknown':data['quantity']='100'
    elif fault=='empty_reason':data['reason']=' '
    elif fault=='foreign_batch':data['batch_id']=2147483647
    elif fault=='cashier':
        from app.business_packs.models import PackUserGrant
        role=db.query(PackUserGrant).filter_by(context_id=lots[0][3],user_id=lots[0][1].id).one();role.role='cashier';db.commit()
    else:
        from app.access.models import AccessPolicy
        policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=lots[0][1].id).one()
        policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'actions':['view','create','approve']}};policy.version+=1;db.commit()
    before=counts(db);stock=balance(db,lots[0]);quantities=lot_quantities(db,lots)
    response=client.post(BASE,headers=lots[0][0],json=data)
    assert response.status_code in (403,404,409,422),response.text
    assert counts(db)==before and status(db,lots)=='available' and balance(db,lots[0])==stock and lot_quantities(db,lots)==quantities


def test_changed_uuid_digest_stale_case_and_recalled_downgrade_are_denied(client,db,lots):
    data=request(lots,'recall');response=client.post(BASE,headers=lots[0][0],json=data);assert response.status_code==201,response.text
    first=response.json();before=counts(db)
    changed=client.post(BASE,headers=lots[0][0],json={**data,'reason':'Different command under same UUID'})
    assert changed.status_code==409,changed.text
    stale={'request_key':str(uuid4()),'expected_revision':2,'expected_batch_revision':1,'expected_batch_status':'recalled','action':'close','reason':'Close stale case'}
    assert client.post(f"{BASE}/{first['id']}/commands",headers=lots[0][0],json=stale).status_code==409
    downgrade=client.post(BASE,headers=lots[0][0],json={**data,'request_key':str(uuid4()),'expected_batch_revision':1,'expected_batch_status':'recalled','action':'quarantine'})
    assert downgrade.status_code==409,downgrade.text
    assert counts(db)==before and status(db,lots)=='recalled'


def test_late_event_failure_rolls_back_canonical_state_and_private_root(client,db,lots,monkeypatch):
    import app.business_packs.pharma.recalls as service
    before=counts(db)
    def conflict(*args,**kwargs):raise HTTPException(409,'Late event conflict')
    monkeypatch.setattr(service,'_event',conflict)
    response=client.post(BASE,headers=lots[0][0],json=request(lots))
    assert response.status_code==409,response.text
    assert counts(db)==before and status(db,lots)=='available'


def test_outer_rollback_restores_canonical_state_and_history(db,lots):
    case=lots[0];before=counts(db)
    with native_writer(db,case[1],case[2]):
        scope=resolve_context(db,case[1],db.info['branch_context'],case[3]);cleanup=install(db,scope,policy=native_srm_policy('pharma').policy)
        try:
            create(RecallInput.model_validate(request(lots)),db,case[1],commit=False)
            assert status(db,lots)=='quarantined'
            db.rollback();assert status(db,lots)=='available' and counts(db)==before
        finally:cleanup()


def test_other_pack_cannot_view_or_write_recall_case(client,db,lots):
    from tests.test_business_pack_http_integration import grant
    data=request(lots);response=client.post(BASE,headers=lots[0][0],json=data);assert response.status_code==201,response.text
    context,_=grant(db,lots[0][1],lots[0][2],'hospital','hospital_manager')
    headers={**lots[0][0],'X-Suite-Pack-Context':str(context.id)}
    assert client.get(f"{BASE}/{response.json()['id']}",headers=headers).status_code==403
    assert client.post(BASE,headers=headers,json={**data,'request_key':str(uuid4())}).status_code==403


def test_postgresql_raw_sql_cannot_rewrite_or_delete_recall_history(client,db,lots):
    if db.get_bind().dialect.name!='postgresql':pytest.skip('Database trigger proof requires native PostgreSQL')
    from sqlalchemy.exc import IntegrityError
    response=client.post(BASE,headers=lots[0][0],json=request(lots));assert response.status_code==201,response.text
    root=response.json();r=PharmaRecall.__table__;e=PharmaRecallEvent.__table__
    attempts=[r.update().where(r.c.id==root['id']).values(reason='Rewritten source'),
        r.update().where(r.c.id==root['id']).values(revision=99),r.delete().where(r.c.id==root['id']),
        e.update().where(e.c.id==root['event_id']).values(reason='Rewritten event'),e.delete().where(e.c.id==root['event_id'])]
    for statement in attempts:
        with pytest.raises(IntegrityError) as denied:
            with db.begin_nested():db.connection().execute(statement)
        assert denied.value.orig.sqlstate=='23514'
    assert client.get(f"{BASE}/{root['id']}",headers=lots[0][0]).json()==root
