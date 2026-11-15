"""Fresh exact revocations inside real typed stock/native-FAM leases."""
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.access.models import AccessPolicy,AccessMembership
from app.models.company import Branch
from app.business_packs.models import PackUserGrant
from app.apps.business_os.models import BOSEnabledModule
from app.apps.saas.models import TenantSubscription,TenantSubscriptionPlan
from app.apps.srm.models import SRMInventoryBatch,SRMInventoryMovement,SRMPOSCashMovement,SRMPOSReturn
from app.apps.fam.models import FAMVoucher,FAMLedgerEntry,FAMLedger
from app.business_packs.pharma.return_models import PharmaReturn,PharmaReturnLine,PharmaReturnLot
from tests.test_pharma_returns_http import original,lots,pharma,scenario,catalog,directory_identity,post_original,command,BASE

@pytest.mark.parametrize('point',['stock','fam'])
@pytest.mark.parametrize('change',['policy','module','branch','membership','pack','approval','subscription'])
def test_midlease_revocations_remain_fresh_and_atomic(client,db,original,monkeypatch,point,change):
    from app.business_packs.pharma import return_stock
    from app.business_packs.retail import accounting
    post_original(db,original[3]);case=original[0][0]
    if change=='subscription':
        plan=TenantSubscriptionPlan(code='REFUND-'+uuid4().hex,name='Actual refund subscription',config_json={'enforce':True,'modules':['srm','fam','crm','hrms','project_management']})
        db.add(plan);db.flush();subscription=TenantSubscription(company_id=1,plan_id=plan.id,status='active');db.add(subscription);db.commit();subscription_id=subscription.id
    models=(PharmaReturn,PharmaReturnLine,PharmaReturnLot,SRMPOSReturn,SRMInventoryBatch,SRMInventoryMovement,SRMPOSCashMovement,FAMVoucher,FAMLedgerEntry)
    before={model:db.query(model).count() for model in models};balances={row.id:(row.current_balance_dr,row.current_balance_cr) for row in db.query(FAMLedger)};fired=[]
    def revoke(session):
        if fired:return
        fired.append(True);connection=session.connection()
        if change in ('policy','approval'):
            t=AccessPolicy.__table__;row=connection.execute(select(t).where(t.c.company_id==1,t.c.user_id==case[1].id)).mappings().one()
            values={'version':t.c.version+1}
            if change=='policy':values['status']='suspended'
            else:values['grants']={**row['grants'],'fam':{**row['grants']['fam'],'actions':['view','create']}}
            connection.execute(t.update().where(t.c.id==row['id']).values(**values))
        elif change=='branch':
            t=Branch.__table__;connection.execute(t.update().where(t.c.id==case[2]).values(is_active=False))
        elif change=='membership':
            t=AccessMembership.__table__;connection.execute(t.update().where(t.c.company_id==1,t.c.user_id==case[1].id).values(active=False))
        elif change=='pack':
            t=PackUserGrant.__table__;connection.execute(t.update().where(t.c.context_id==case[3],t.c.user_id==case[1].id).values(active=False,revision=t.c.revision+1))
        elif change=='module':
            t=BOSEnabledModule.__table__;row=connection.execute(select(t.c.id).where(t.c.company_id==1,t.c.module_key=='fam')).first()
            if row:connection.execute(t.update().where(t.c.id==row.id).values(enabled=False))
            else:connection.execute(t.insert().values(company_id=1,module_key='fam',display_name='Accounting',enabled=False))
        else:
            t=TenantSubscription.__table__;connection.execute(t.update().where(t.c.id==subscription_id).values(status='suspended',version=t.c.version+1))
    if point=='stock':
        previous=return_stock.create_batch
        def create(lease,*args,**kwargs):revoke(lease.db);return previous(lease,*args,**kwargs)
        monkeypatch.setattr(return_stock,'create_batch',create)
    else:
        previous=accounting._Lease.assert_current
        def current(lease):revoke(lease.db);return previous(lease)
        monkeypatch.setattr(accounting._Lease,'assert_current',current)
    response=client.post(BASE,headers=case[0],json=command(original))
    assert fired,'Test never reached the real typed lease'
    assert response.status_code==403,response.text
    assert all(db.query(model).count()==count for model,count in before.items())
    db.expire_all();assert {row.id:(row.current_balance_dr,row.current_balance_cr) for row in db.query(FAMLedger)}==balances
    assert db not in return_stock._ACTIVE and db not in accounting._ACTIVE

@pytest.mark.parametrize('point',['stock','fam'])
def test_full_lease_entry_cannot_adopt_a_different_native_epoch(client,db,original,monkeypatch,point):
    from contextlib import contextmanager
    from app.business_packs.pharma import return_stock
    from app.business_packs.retail import accounting
    post_original(db,original[3]);case=original[0][0];fired=[]
    models=(PharmaReturn,PharmaReturnLine,PharmaReturnLot,SRMPOSReturn,SRMInventoryBatch,SRMInventoryMovement,SRMPOSCashMovement,FAMVoucher,FAMLedgerEntry)
    before={model:db.query(model).count() for model in models}
    def mutate(session):
        fired.append(True);t=AccessPolicy.__table__;connection=session.connection()
        row=connection.execute(select(t.c.id,t.c.grants).where(t.c.company_id==1,t.c.user_id==case[1].id)).mappings().one()
        # Trusted control-plane corruption test: permissions remain identical,
        # and version is deliberately unchanged. The original fingerprint must
        # still bind the command; a fresh allowed grant cannot be adopted.
        grants={**row['grants'],'srm':{**row['grants']['srm'],'audit_marker':'epoch-'+uuid4().hex}}
        connection.execute(t.update().where(t.c.id==row['id']).values(grants=grants))
    if point=='stock':
        previous=return_stock.quarantine_operation
        @contextmanager
        def enter(session,*args,**kwargs):
            mutate(session)
            with previous(session,*args,**kwargs) as lease:yield lease
        monkeypatch.setattr(return_stock,'quarantine_operation',enter)
    else:
        previous=accounting._lease
        @contextmanager
        def enter(session,*args,**kwargs):
            mutate(session)
            with previous(session,*args,**kwargs) as lease:yield lease
        monkeypatch.setattr(accounting,'_lease',enter)
    response=client.post(BASE,headers=case[0],json=command(original))
    assert fired and response.status_code==403,response.text
    assert all(db.query(model).count()==count for model,count in before.items())
    assert db not in return_stock._ACTIVE and db not in accounting._ACTIVE
