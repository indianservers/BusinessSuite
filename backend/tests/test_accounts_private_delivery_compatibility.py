"""Actual Accounts financial workflow composes with private delivery121."""
from app.models.email_outbox import EmailOutbox
from app.business_packs.delivery_source_models import PackDeliverySource
from app.business_packs.models import PackUserGrant
from tests.test_accounts_billing import accounts,scenario,catalog,directory_identity,test_native_issue_partial_and_final_collection_use_existing_receipt_ledger as _actual_financial_workflow


def test_accounts_billing_collection_does_not_abort_or_launder_private_mail(client,db,accounts,monkeypatch):
    from app.business_packs import delivery_sources
    actual=delivery_sources.prepare_email;births=[]
    def observed(native,row,source):
        result=actual(native,row,source)
        scope=native.info.get('business_pack_scope')
        if scope is not None and scope.context_id==accounts['context']:
            births.append(row)
        return result
    monkeypatch.setattr(delivery_sources,'prepare_email',observed)
    # Reuse the unchanged real HTTP source/payment assertions, not a replacement
    # command or fabricated invoice/receipt.
    _actual_financial_workflow(client,db,accounts)
    assert births
    for row in births:
        assert db.query(PackDeliverySource.id).filter_by(email_outbox_id=row.id).first() or row.status=='suppressed'
    for grant in db.query(PackUserGrant).filter_by(context_id=accounts['context']).all():grant.active=False
    db.commit()
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider')
    from app.services.email_dispatch import _deliver
    for row in births:_deliver(db,row)
    assert not sent and all(row.status=='suppressed' for row in births)
