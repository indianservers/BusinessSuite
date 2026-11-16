"""Retained real source issuer remains independent of an authorized target."""
import pytest
from app.business_packs.delivery_source_models import PackDeliverySource
from app.business_packs.models import PackUserGrant
from app.models.email_outbox import EmailOutbox
from app.shared.follow_ups import dispatch
from app.business_packs.delivery_sources import delivery_allowed
from tests.test_pack_followup_delivery import private_followup,separate_recipient,retail_setup,scenario,catalog,directory_identity,notifications,_historical_reassign


@pytest.mark.parametrize('fault',[None,'grant','native_permissions','role'])
def test_retained_issuer_is_rechecked_while_distinct_recipient_remains_authorized(db,private_followup,separate_recipient,monkeypatch,fault):
    setup,source=private_followup;recipient,target_grant=separate_recipient
    _historical_reassign(db,source,setup,recipient)
    dispatch(db)
    notices=notifications(db,source);assert len(notices)==1
    notice=notices[0]
    parent=db.query(PackDeliverySource).filter_by(notification_id=notice.id).one()
    assert (parent.actor_user_id,parent.recipient_user_id)==(setup[1].id,recipient.id)
    # This is the actual generic native Notification->Email producer, not a
    # direct certificate fixture or made-up email/body authority pointer.
    children=db.query(PackDeliverySource).filter_by(source_table='notifications',source_key=str(notice.id)).all()
    assert len(children)==1
    child=children[0]
    assert child.actor_user_id==parent.actor_user_id and child.recipient_user_id==recipient.id
    email=db.get(EmailOutbox,child.email_outbox_id)
    assert delivery_allowed(db,notice) and delivery_allowed(db,email)
    issuer=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one()
    if fault=='grant':issuer.active=False
    elif fault=='role':issuer.role='storekeeper'
    elif fault=='native_permissions':
        from app.access.models import AccessPolicy
        policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=setup[1].id).one()
        policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'permissions':[]}}
    db.commit()
    assert target_grant.active and target_grant.role=='store_manager' and recipient.is_active
    assert delivery_allowed(db,notice) is (fault is None)
    from app.services.metrics.queries import personal_notifications
    assert personal_notifications(db,recipient).filter_by(id=notice.id).count()==(1 if fault is None else 0)
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider')
    from app.services.email_dispatch import _deliver
    _deliver(db,email)
    assert len(sent)==(1 if fault is None else 0)
    assert email.status==('accepted' if fault is None else 'suppressed')
