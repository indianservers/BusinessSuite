from uuid import uuid4
import pytest
from app.business_packs.delivery_source_models import PackDeliverySource
from app.business_packs.models import PackUserGrant,PackRecordOwnership
from app.models.email_outbox import EmailOutbox
from app.services.email_dispatch import _deliver
from tests.test_retail_return_http import retail_setup,scenario,catalog,directory_identity
from tests.test_retail_workflows import cart

@pytest.fixture
def queued(client,db,retail_setup):
    response=client.post('/api/v1/srm/service-checkout',headers=retail_setup[0],json=cart(retail_setup))
    assert response.status_code==201,response.text
    rows=db.query(EmailOutbox).filter_by(organization_id=1).all()
    private=[row for row in rows if db.query(PackRecordOwnership.id).filter_by(resource_table='email_outbox',resource_key=str(row.id)).first()]
    assert private
    return retail_setup,private


def test_actual_private_checkout_email_rechecks_grant_before_fake_provider(db,queued,monkeypatch):
    setup,rows=queued
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider-id')
    assert db.query(PackDeliverySource).filter(PackDeliverySource.email_outbox_id.in_([row.id for row in rows])).count()==len(rows)
    for row in rows:_deliver(db,row)
    assert len(sent)==len(rows) and all(row.status=='accepted' for row in rows)


def test_revoked_exact_private_grant_suppresses_actual_checkout_email(db,queued,monkeypatch):
    setup,rows=queued
    assignment=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one();assignment.active=False;db.commit()
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider-id')
    for row in rows:_deliver(db,row)
    assert not sent and all(row.status=='suppressed' for row in rows)

@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef'),('construction','site_engineer')])
def test_another_pack_assignment_does_not_revive_old_mail(db,queued,monkeypatch,pack,role):
    from tests.test_business_pack_http_integration import grant
    setup,rows=queued
    grant(db,setup[1],setup[2],pack,role)
    assignment=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one();assignment.active=False;db.commit()
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider-id')
    for row in rows:_deliver(db,row)
    assert not sent and all(row.status=='suppressed' for row in rows)


def test_actual_summary_keeps_common_but_hides_revoked_private_url(client,db,queued):
    from app.models.notification import Notification
    setup,rows=queued
    common=Notification(company_id=1,user_id=setup[1].id,title='Common identity update',message='Common native note',module='hrms',action_url='/hrms/me',channels=['in_app'])
    db.add(common);db.commit()
    before=client.get('/api/v1/notifications/summary',headers=setup[0]);assert before.status_code==200,before.text
    assert any(group['action_url'].startswith('/srm/invoices/') for group in before.json()['groups'])
    assignment=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one();assignment.active=False;db.commit()
    after=client.get('/api/v1/notifications/summary',headers=setup[0]);assert after.status_code==200,after.text
    assert not any(group['action_url'].startswith('/srm/invoices/') for group in after.json()['groups'])
    assert any(group['action_url']=='/hrms/me' and group['count']==1 for group in after.json()['groups'])
    # Direct handler is defense in depth, not a claim that classifier503 routes
    # have become public. Existing route policy is deliberately unchanged.
    from app.api.v1.notifications import mark_notification_read
    private=db.query(Notification).filter(Notification.action_url.like('/srm/invoices/%')).first()
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as denied:mark_notification_read(private.id,db,setup[1])
    assert denied.value.status_code==404


@pytest.mark.parametrize('change',['native_actions','native_permissions','membership','identity','branch','context','activation','role','address','origin_anchor'])
def test_private_delivery_fresh_native_ceiling_and_retained_origin(db,queued,monkeypatch,change):
    from sqlalchemy import delete,update
    from app.access.models import AccessPolicy,AccessMembership
    from app.business_packs.models import PackContext,PackActivation
    from app.models.company import Branch
    setup,rows=queued
    assignment=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one()
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=setup[1].id).one()
    if change=='native_actions':policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'actions':[]}}
    elif change=='native_permissions':policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'permissions':[]}}
    elif change=='membership':db.query(AccessMembership).filter_by(company_id=1,user_id=setup[1].id).one().active=False
    elif change=='identity':setup[1].is_active=False
    elif change=='branch':db.get(Branch,setup[2]).is_active=False
    elif change=='context':db.get(PackContext,setup[3]).state='suspended'
    elif change=='activation':db.get(PackActivation,db.get(PackContext,setup[3]).activation_id).state='suspended'
    elif change=='role':assignment.role='storekeeper'
    else:
        statement=(update(EmailOutbox.__table__).where(EmailOutbox.id.in_([row.id for row in rows])).values(recipient='tampered@example.test')
            if change=='address' else delete(PackRecordOwnership.__table__).where(PackRecordOwnership.resource_table=='email_outbox',PackRecordOwnership.resource_key.in_([str(row.id) for row in rows])))
        if db.get_bind().dialect.name=='postgresql':
            # Deployed121 adds durable SQL guards absent from bare SQLite ORM
            # fixtures: prove the corruption itself is rejected, then revoke
            # genuine authority and preserve the zero-provider assertion below.
            from sqlalchemy.exc import DBAPIError
            before=[row.recipient for row in rows]
            with pytest.raises(DBAPIError):
                with db.begin_nested():db.connection().execute(statement)
            assert [row.recipient for row in rows]==before
            assert db.query(PackRecordOwnership).filter(PackRecordOwnership.resource_table=='email_outbox',PackRecordOwnership.resource_key.in_([str(row.id) for row in rows])).count()==len(rows)
            assignment.active=False
        else:
            db.connection().execute(statement);db.expire_all()
    db.commit()
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider-id')
    for row in rows:_deliver(db,row)
    assert not sent and all(row.status=='suppressed' for row in rows)
