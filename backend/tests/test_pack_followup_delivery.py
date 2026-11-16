"""Actual private checkout follow-ups retain authority at worker delivery."""
from datetime import datetime,timedelta,timezone
import pytest
from app.business_packs.models import PackUserGrant,PackRecordOwnership
from app.models.notification import Notification
from app.shared.follow_ups import FollowUp,FollowUpReminder,dispatch
from tests.test_retail_return_http import retail_setup,scenario,catalog,directory_identity
from tests.test_retail_workflows import cart

@pytest.fixture
def private_followup(client,db,retail_setup):
    headers,actor,branch,context,*_=retail_setup
    data=cart(retail_setup)
    data['lines'][0]['follow_up']={'required':True,'type':'date','due_at':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat(),'reminder_minutes':5,'assigned_user_id':actor.id,'notes':'PRIVATE-PACK-DELIVERY-NOTES','purpose':'Maintenance'}
    response=client.post('/api/v1/srm/service-checkout',headers=headers,json=data)
    assert response.status_code==201,response.text
    db.expire_all()
    source=db.query(FollowUp).one()
    owner=db.query(PackRecordOwnership).filter_by(resource_table='service_follow_ups',resource_key=str(source.id)).one()
    assert owner.context_id==context
    return retail_setup,source

def notifications(db,source):
    return db.query(Notification).filter_by(related_entity_type='follow_up',related_entity_id=source.id,event_type='service_follow_up').all()

def test_private_source_delivers_once_with_exact_derivative_ownership(db,private_followup):
    setup,source=private_followup
    dispatch(db);dispatch(db)
    rows=notifications(db,source);assert len(rows)==1
    assert 'PRIVATE-PACK-DELIVERY-NOTES' in rows[0].message
    owner=db.query(PackRecordOwnership).filter_by(resource_table='notifications',resource_key=str(rows[0].id)).one()
    assert (owner.company_id,owner.branch_id,owner.context_id)==(1,setup[2],setup[3])
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).count()==1

@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef'),('construction','site_engineer')])
def test_other_assignment_never_revives_revoked_private_followup(db,private_followup,pack,role):
    from tests.test_business_pack_http_integration import grant
    setup,source=private_followup
    grant(db,setup[1],setup[2],pack,role)
    own=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one();own.active=False;db.commit()
    dispatch(db);dispatch(db)
    assert notifications(db,source)==[]
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).count()==0
    assert db.get(FollowUp,source.id) is not None

@pytest.mark.parametrize('change',['pack','role','native','identity'])
def test_worker_rechecks_current_private_authority(db,private_followup,change):
    from app.access.models import AccessPolicy
    setup,source=private_followup
    own=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one()
    if change=='pack':own.active=False
    elif change=='role':own.role='storekeeper'
    elif change=='identity':setup[1].is_active=False
    else:
        policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=setup[1].id).one()
        policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'actions':[]}}
    db.commit();dispatch(db)
    assert notifications(db,source)==[]
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).count()==0

def test_suppressed_intent_retries_once_after_exact_authority_restored(db,private_followup):
    setup,source=private_followup
    own=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one();own.active=False;db.commit()
    dispatch(db);assert notifications(db,source)==[]
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).count()==0
    own.active=True;db.commit();dispatch(db);dispatch(db)
    assert len(notifications(db,source))==1
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).count()==1
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).one().delivery_status=='delivered'

def test_private_provenance_uses_real_canonical_order_line(db,private_followup):
    from app.business_packs.followup_delivery import private_source
    setup,source=private_followup
    proof=private_source(db,source)
    assert (proof.followup_id,proof.company_id,proof.branch_id,proof.context_id,proof.actor_id,proof.recipient_id)==(source.id,1,setup[2],setup[3],setup[1].id,setup[1].id)


@pytest.fixture
def separate_recipient(client,db,retail_setup):
    from tests.test_business_pack_http_integration import native_actor,grant
    from app.business_packs.models import PackContext
    _,recipient=native_actor(db,retail_setup[2])
    from uuid import uuid4
    from app.models.employee import Employee
    from app.models.user import User
    from app.business_packs.models import PackMasterAvailability
    from tests.test_srm_native_transaction_operations import native_writer
    administrator=db.query(User).filter_by(email='testadmin@test.com').one()
    with native_writer(db,administrator,retail_setup[2]):
        employee=Employee(employee_id='PACK-RECIPIENT-'+uuid4().hex,first_name='QA',last_name='Recipient',
            user_id=recipient.id,branch_id=retail_setup[2],status='Active',date_of_joining=datetime.now(timezone.utc).date())
        db.add(employee);db.commit();employee_id=employee.id
    db.add(PackMasterAvailability(company_id=1,branch_id=retail_setup[2],context_id=retail_setup[3],
        resource_table='employees',resource_key=str(employee_id),active=True))
    db.commit();db.expire_all()
    _,assignment=grant(db,recipient,retail_setup[2],'retail','store_manager',context=db.get(PackContext,retail_setup[3]))
    return recipient,assignment

@pytest.mark.parametrize('revoked',['creator','recipient'])
def test_creator_and_recipient_grants_are_independent(client,db,retail_setup,separate_recipient,revoked):
    recipient,assignment=separate_recipient
    data=cart(retail_setup)
    data['lines'][0]['follow_up']={'required':True,'type':'date','due_at':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat(),'reminder_minutes':5,'assigned_user_id':retail_setup[1].id,'notes':'SEPARATE-RECIPIENT-PRIVATE'}
    response=client.post('/api/v1/srm/service-checkout',headers=retail_setup[0],json=data)
    assert response.status_code==201,response.text
    db.expire_all();source=db.query(FollowUp).one()
    _historical_reassign(db,source,retail_setup,recipient)
    own=db.query(PackUserGrant).filter_by(context_id=retail_setup[3],user_id=retail_setup[1].id).one()
    (own if revoked=='creator' else assignment).active=False;db.commit();dispatch(db)
    assert notifications(db,source)==[]
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).count()==0


def test_cached_assignee_uses_actual_authorized_recipient(db,private_followup,separate_recipient):
    from sqlalchemy import update
    setup,source=private_followup;recipient,_=separate_recipient
    cached=source.assigned_user_id
    db.connection().execute(update(FollowUp.__table__).where(FollowUp.__table__.c.id==source.id).values(assigned_user_id=recipient.id))
    assert source.assigned_user_id==cached
    dispatch(db);dispatch(db)
    rows=notifications(db,source);assert len(rows)==1
    assert rows[0].user_id==recipient.id


@pytest.mark.parametrize('failure_point',['certify_notification','certify_followup_reminder','after_pk_certificate'])
def test_failed_private_birth_rolls_back_and_retries_once(db,private_followup,monkeypatch,failure_point):
    from app.business_packs import delivery_sources
    setup,source=private_followup
    from app.business_packs.delivery_source_models import PackDeliverySource
    from app.branches.models import BranchOwnership
    from app.models.email_outbox import EmailOutbox
    graph=(Notification,FollowUpReminder,PackRecordOwnership,BranchOwnership,PackDeliverySource,EmailOutbox)
    before={model:db.query(model).count() for model in graph}
    original=getattr(delivery_sources,'_insert_certificate' if failure_point=='after_pk_certificate' else failure_point)
    def fail(*args,**kwargs):
        if failure_point=='after_pk_certificate':
            result=original(*args,**kwargs)
            row=args[1]
            if type(row) is not Notification or row.event_type!='service_follow_up':return result
        raise ValueError('Synthetic source certification failure')
    target='_insert_certificate' if failure_point=='after_pk_certificate' else failure_point
    monkeypatch.setattr(delivery_sources,target,fail)
    dispatch(db)
    assert notifications(db,source)==[]
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).count()==0
    assert {model:db.query(model).count() for model in graph}==before
    monkeypatch.setattr(delivery_sources,target,original)
    dispatch(db);dispatch(db)
    assert len(notifications(db,source))==1
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).count()==1


def _historical_reassign(db,source,setup,recipient):
    """Trusted canonical fixture maintenance; not a released assignment API."""
    from sqlalchemy import update
    from app.models.user import User
    from tests.test_srm_native_transaction_operations import native_writer
    owner=db.query(PackRecordOwnership).filter_by(resource_table='service_follow_ups',resource_key=str(source.id)).one()
    identity=(owner.id,owner.company_id,owner.branch_id,owner.context_id)
    administrator=db.query(User).filter_by(email='testadmin@test.com').one()
    with native_writer(db,administrator,setup[2]):
        db.connection().execute(update(FollowUp.__table__).where(FollowUp.__table__.c.id==source.id,
            FollowUp.__table__.c.organization_id==1).values(assigned_user_id=recipient.id))
        db.commit()
    db.expire_all()
    retained=db.query(PackRecordOwnership).filter_by(resource_table='service_follow_ups',resource_key=str(source.id)).one()
    assert (retained.id,retained.company_id,retained.branch_id,retained.context_id)==identity
    assert source.assigned_user_id==recipient.id


def test_distinct_assignee_public_checkout_remains_unreleased(client,db,retail_setup,separate_recipient):
    from app.apps.srm.models import SRMInvoice,SRMReceipt
    recipient,_=separate_recipient
    before={model:db.query(model).count() for model in (FollowUp,SRMInvoice,SRMReceipt)}
    data=cart(retail_setup)
    data['lines'][0]['follow_up']={'required':True,'type':'date','due_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
        'reminder_days':2,'assigned_user_id':recipient.id,'notes':'UNRELEASED-PRIVATE-ASSIGNMENT'}
    response=client.post('/api/v1/srm/service-checkout',headers=retail_setup[0],json=data)
    assert response.status_code==422,response.text
    assert {model:db.query(model).count() for model in before}==before


def _historical_owned_reminder(db,setup,source,status='retry'):
    """Historical source-owned intent fixture, not a public pending-birth flow."""
    from app.branches.models import BranchOwnership
    from app.models.user import User
    from app.shared.follow_ups import utc
    from tests.test_srm_native_transaction_operations import native_writer
    instant=datetime.now(timezone.utc)-timedelta(minutes=5)
    administrator=db.query(User).filter_by(email='testadmin@test.com').one()
    key=f'{utc(source.due_at).isoformat()}:{source.assigned_user_id}:reminder'
    with native_writer(db,administrator,setup[2]):
        receipt=FollowUpReminder(follow_up_id=source.id,schedule_key=key,delivery_status=status,
            sent_at=instant,notification_id=None,attempt_history=[{'at':instant.isoformat(),'status':status}])
        db.add(receipt);db.flush()
        branch=db.get(BranchOwnership,(FollowUpReminder.__tablename__,str(receipt.id)))
        if branch is None:
            db.add(BranchOwnership(resource_table=FollowUpReminder.__tablename__,resource_key=str(receipt.id),
                company_id=1,branch_id=setup[2],source='historical-reminder-fixture'))
        else:assert (branch.company_id,branch.branch_id)==(1,setup[2])
        db.add(PackRecordOwnership(company_id=1,branch_id=setup[2],context_id=setup[3],
            resource_table=FollowUpReminder.__tablename__,resource_key=str(receipt.id),source='historical-reminder-fixture'))
        db.commit();identity=receipt.id
    db.expire_all()
    return db.get(FollowUpReminder,identity)


def _source_digest(db,source):
    import hashlib,json
    from sqlalchemy import select
    row=db.connection().execute(select(FollowUp.__table__).where(FollowUp.__table__.c.id==source.id)).mappings().one()
    return hashlib.sha256(json.dumps(dict(row),sort_keys=True,default=str).encode()).hexdigest()


def test_historical_owned_retry_reuses_same_intent_without_retag(db,private_followup):
    setup,source=private_followup;receipt=_historical_owned_reminder(db,setup,source)
    identity=receipt.id;before=_source_digest(db,source)
    owner=db.query(PackRecordOwnership).filter_by(resource_table=FollowUpReminder.__tablename__,resource_key=str(identity)).one()
    anchor=(owner.id,owner.company_id,owner.branch_id,owner.context_id,owner.source)
    dispatch(db);dispatch(db)
    assert len(notifications(db,source))==1
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).one().id==identity
    assert receipt.delivery_status=='delivered'
    db.expire_all();owner=db.get(PackRecordOwnership,anchor[0])
    assert (owner.id,owner.company_id,owner.branch_id,owner.context_id,owner.source)==anchor
    assert _source_digest(db,source)==before


def test_historical_delivered_intent_never_reemits(db,private_followup):
    setup,source=private_followup;receipt=_historical_owned_reminder(db,setup,source,'delivered')
    identity=receipt.id;dispatch(db);dispatch(db)
    assert notifications(db,source)==[]
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).one().id==identity
    assert receipt.delivery_status=='delivered'


def test_owned_retry_defers_then_restores_exact_same_intent(db,private_followup):
    setup,source=private_followup;receipt=_historical_owned_reminder(db,setup,source)
    identity=receipt.id;before=_source_digest(db,source)
    own=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one()
    own.active=False;db.commit();dispatch(db)
    assert notifications(db,source)==[]
    assert receipt.delivery_status=='deferred'
    own.active=True;db.commit();dispatch(db);dispatch(db)
    assert len(notifications(db,source))==1
    assert db.query(FollowUpReminder).filter_by(follow_up_id=source.id).one().id==identity
    assert receipt.delivery_status=='delivered'
    assert _source_digest(db,source)==before
