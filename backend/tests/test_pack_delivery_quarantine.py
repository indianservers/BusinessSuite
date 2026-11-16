"""Unknown private template cannot become unowned mail on a later retry."""
from uuid import uuid4
from app.models.email_outbox import EmailOutbox
from app.business_packs.models import PackRecordOwnership,PackUserGrant
from app.business_packs.delivery_source_models import PackDeliverySource
from app.apps.srm.models import SRMInvoice
from app.services.email_dispatch import queue_email,_deliver
from tests.test_pack_delivery_sources import queued,retail_setup,scenario,catalog,directory_identity
from tests.test_pack_followup_delivery import separate_recipient


def test_unbound_unknown_template_retains_private_origin_after_status_reset(db,queued,separate_recipient,monkeypatch):
    setup,_=queued;recipient,target=separate_recipient
    invoice=db.query(SRMInvoice).one();invoice_state=(invoice.id,invoice.status,invoice.total_amount,invoice.paid_amount,invoice.balance_amount)
    row=queue_email(db,recipient=recipient.email,subject='Unintegrated private template',body='PRIVATE-COMMAND-NOTE',
        module='srm',organization_id=1,user_id=recipient.id,event_key='unsupported-private-'+uuid4().hex,source_record=invoice)
    assert row is not None and row.status=='suppressed'
    db.commit();identity=row.id
    assert db.query(PackDeliverySource.id).filter_by(email_outbox_id=identity).first() is None
    source_grant=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one();source_grant.active=False
    db.commit();assert target.active
    # Actual retry/provider path must depend on durable origin, not Python-only
    # source attributes, previous status, or a cached issuing principal.
    from sqlalchemy.orm import Session
    fresh=Session(bind=db.connection(),join_transaction_mode='rollback_only')
    try:
        retried=fresh.get(EmailOutbox,identity);assert not hasattr(retried,'_suite_source_record')
        retried.status='queued';fresh.flush()
        sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider')
        _deliver(fresh,retried)
        assert not sent and retried.status=='suppressed'
    finally:fresh.close()
    db.expire_all();invoice=db.get(SRMInvoice,invoice_state[0])
    assert (invoice.id,invoice.status,invoice.total_amount,invoice.paid_amount,invoice.balance_amount)==invoice_state
    owner=db.query(PackRecordOwnership).filter_by(resource_table='email_outbox',resource_key=str(identity)).one()
    assert (owner.company_id,owner.branch_id,owner.context_id)==(1,setup[2],setup[3])


def test_unbound_native_notice_with_unavailable_issuer_hides_all_channels(client,db,queued,monkeypatch):
    from app.apps.srm.api.router import _notify
    from app.models.notification import Notification
    setup,_=queued;invoice=db.query(SRMInvoice).one()
    state=(invoice.id,invoice.status,invoice.total_amount,invoice.paid_amount,invoice.balance_amount)
    old_notes={row.id for row in db.query(Notification).all()};old_mail={row.id for row in db.query(EmailOutbox).all()}
    grant=db.query(PackUserGrant).filter_by(context_id=setup[3],user_id=setup[1].id).one();grant.active=False;db.commit()
    _notify(db,setup[1].id,'Invoice draft created',f'{invoice.invoice_number} is ready for review.',
        'invoice',invoice.id,f'/srm/invoices/{invoice.id}',source_record=invoice)
    db.commit()
    notice=db.query(Notification).filter(Notification.id.notin_(old_notes)).one()
    assert db.query(PackDeliverySource).filter_by(notification_id=notice.id).first() is None
    owner=db.query(PackRecordOwnership).filter_by(resource_table='notifications',resource_key=str(notice.id)).one()
    assert (owner.company_id,owner.branch_id,owner.context_id)==(1,setup[2],setup[3])
    summary=client.get('/api/v1/notifications/summary',headers=setup[0]);assert summary.status_code==200,summary.text
    assert not any(group['action_url']==f'/srm/invoices/{invoice.id}' for group in summary.json()['groups'])
    messages=db.query(EmailOutbox).filter(EmailOutbox.id.notin_(old_mail)).all();assert messages
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider')
    for row in messages:
        assert db.query(PackDeliverySource).filter_by(email_outbox_id=row.id).first() is None
        assert db.query(PackRecordOwnership).filter_by(resource_table='email_outbox',resource_key=str(row.id)).one().context_id==setup[3]
        row.status='queued'
    db.commit()
    from sqlalchemy.orm import Session
    fresh=Session(bind=db.connection(),join_transaction_mode='rollback_only')
    try:
        for original in messages:_deliver(fresh,fresh.get(EmailOutbox,original.id))
    finally:fresh.close()
    assert not sent
    db.expire_all();invoice=db.get(SRMInvoice,state[0])
    assert (invoice.id,invoice.status,invoice.total_amount,invoice.paid_amount,invoice.balance_amount)==state


def test_known_private_source_wrong_target_company_cannot_resurrect_on_retry(db,queued,monkeypatch,caplog):
    from app.models.company import Company
    from app.access.models import AccessMembership
    from tests.test_settings_hub import actor
    from sqlalchemy.orm import Session
    setup,_=queued;invoice_id=db.query(SRMInvoice.id).one()[0]
    company=Company(name='Other isolated delivery company');db.add(company);db.flush()
    _,recipient=actor(db,role='explicit-native-root-'+uuid4().hex,superuser=True)
    db.add(AccessMembership(company_id=company.id,user_id=recipient.id,active=True,is_admin=True));db.commit()
    event_key='wrong-private-'+uuid4().hex
    before_count=db.query(EmailOutbox).count()
    native=Session(bind=db.connection(),join_transaction_mode='rollback_only')
    try:
        source=native.get(SRMInvoice,invoice_id)
        financial_state=(source.status,source.total_amount,source.paid_amount,source.balance_amount)
        row=queue_email(native,recipient=recipient.email,subject='Private invoice wrong company',body='PRIVATE-CROSS-COMPANY-NOTE',
            module='srm',organization_id=company.id,user_id=recipient.id,event_key=event_key,source_record=source)
        native.commit();identity=row.id if row is not None else None
    finally:native.close()
    assert identity is None
    assert 'private_delivery_rejected_company_mismatch' in caplog.text
    if identity is None:
        assert db.query(EmailOutbox).filter_by(event_key=event_key).count()==0
        assert db.query(EmailOutbox).count()==before_count
        source=db.get(SRMInvoice,invoice_id)
        assert (source.status,source.total_amount,source.paid_amount,source.balance_amount)==financial_state
        # A legitimate unowned identity message for that same company/recipient
        # still goes through the actual queue and provider path.
        fresh=Session(bind=db.connection(),join_transaction_mode='rollback_only')
        try:
            control=queue_email(fresh,recipient=recipient.email,subject='Native identity control',body='Native identity note',
                module='auth',organization_id=company.id,user_id=recipient.id,event_key='identity-control-'+uuid4().hex)
            assert control is not None
            fresh.commit()
            sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(args[1]) or 'fake-provider')
            _deliver(fresh,control)
            assert sent==['Native identity control'] and control.status=='accepted'
        finally:fresh.close()
        return
    # No pending or stored artifact exists for a future status-reset retry.


def test_native_notify_wrong_company_rejects_only_new_notice_without_financial_rollback(db,queued,caplog):
    from app.apps.srm.api.router import _notify
    from app.models.notification import Notification
    from app.models.company import Company
    setup,_=queued;invoice=db.query(SRMInvoice).one()
    before=(db.query(Notification).count(),db.query(EmailOutbox).count())
    state=(invoice.id,invoice.status,invoice.total_amount,invoice.paid_amount,invoice.balance_amount)
    other=Company(name='Other native notice company');db.add(other);db.commit()
    result=_notify(db,setup[1].id,'Invoice draft created',f'{invoice.invoice_number} is ready for review.',
        'invoice',invoice.id,f'/srm/invoices/{invoice.id}',company_id=other.id,source_record=invoice)
    assert result is None
    db.commit()
    assert (db.query(Notification).count(),db.query(EmailOutbox).count())==before
    assert 'private_delivery_rejected_company_mismatch' in caplog.text
    db.expire_all();invoice=db.get(SRMInvoice,state[0])
    assert (invoice.id,invoice.status,invoice.total_amount,invoice.paid_amount,invoice.balance_amount)==state


def test_company_rejection_cannot_expunge_an_existing_message(db,queued):
    import pytest
    from fastapi import HTTPException
    from app.business_packs.delivery_sources import _reject_pending_target
    _,rows=queued;existing=rows[0];identity=existing.id
    with pytest.raises(HTTPException) as denied:_reject_pending_target(db,existing)
    assert denied.value.status_code==403 and db.get(EmailOutbox,identity) is existing
