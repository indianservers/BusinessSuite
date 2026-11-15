"""Issued native invoices freeze verified pack terminology without adopting old rows."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from app.apps.srm.models import SRMInvoice, SRMInvoiceDraft
from app.apps.srm.commercial_models import InvoiceContext
from app.apps.srm.service_checkout import checkout, save_policy, save_eligibility
from app.apps.srm.service_checkout_schemas import PolicyInput, EligibilityInput
from app.apps.srm.services.commercial import invoice_business_terms, issue_snapshot
from app.business_packs.access import resolve_context
from app.business_packs.models import PackRecordOwnership
from app.shared.models import ServicePolicy
from tests.test_service_checkout import scenario, catalog, directory_identity, enable_pack, enable_audited_pack, audited_pack_writer
from tests.test_srm_native_transaction_operations import native_writer


@pytest.fixture
def issued_pack_invoice(db, scenario):
    user, branch, catalog, basket = scenario
    preference = ServicePolicy(organization_id=1, kind='business_profile',
        scope_key='business-profile:company:1', version=1, updated_by=user.id,
        values_json={'business_type': 'construction', 'terms': {'customer': ['Site buyer', 'Site buyers']}})
    db.add(preference); db.commit()
    context, grant, provider, register = enable_audited_pack(db, user, branch, catalog)
    data = basket(False); data.pos_session_id = register.id
    with audited_pack_writer(db, user, branch, context):
        scope = resolve_context(db, user, db.info['branch_context'])
        policy = save_policy(PolicyInput(service_product_id=catalog[2][1], default_duration_minutes=30,
            min_duration_minutes=5, max_duration_minutes=120), db, user)
        eligibility = save_eligibility(EligibilityInput(policy_id=policy['id'], expected_policy_revision=policy['revision'],
            provider_resource_id=provider.id, employee_id=provider.data['employee_id']), db, user)
        for line in data.lines:
            if line.booking:
                line.booking.provider_resource_id = provider.id
                line.booking.policy_id = policy['id']; line.booking.expected_policy_revision = policy['revision']
                line.booking.eligibility_id = eligibility['id']; line.booking.expected_eligibility_revision = eligibility['revision']
        result = checkout(data, db, user)
    return SimpleNamespace(user=user, branch=branch, scope=scope, context=context, grant=grant,
        invoice=db.get(SRMInvoice, result['invoice']['id']), preference=preference, result=result)


def test_native_active_hospital_checkout_freezes_patient_terms_not_company_override(db, issued_pack_invoice):
    p = issued_pack_invoice
    snapshot = db.get(InvoiceContext, p.invoice.id)
    assert snapshot.issued_at is not None
    assert snapshot.customer_snapshot['_business_terms']['customer'] == ['Patient', 'Patients']
    assert snapshot.customer_snapshot['_business_terms']['provider'] == ['Doctor', 'Doctors']
    assert p.preference.values_json['terms']['customer'] == ['Site buyer', 'Site buyers']
    with native_writer(db, p.user, p.branch):
        db.info['business_pack_scope'] = p.scope
        try:
            assert invoice_business_terms(db, p.invoice, p.user)['customer'] == ['Patient', 'Patients']
            assert invoice_business_terms(db, p.invoice)['customer'] == ['Patient', 'Patients']
        finally:
            db.info.pop('business_pack_scope', None)


def test_issued_snapshot_unchanged_when_legacy_preferences_change(db, issued_pack_invoice, monkeypatch):
    p = issued_pack_invoice
    snapshot = db.get(InvoiceContext, p.invoice.id)
    before = deepcopy(snapshot.customer_snapshot)
    p.preference.values_json = {'business_type': 'general', 'terms': {'customer': ['Counterparty', 'Counterparties']}}
    p.preference.version += 1; db.commit()
    def cannot_relabel(*args, **kwargs):
        raise AssertionError('An existing issued snapshot must not resolve new terms')
    monkeypatch.setattr('app.apps.srm.services.commercial.invoice_business_terms', cannot_relabel)
    with native_writer(db, p.user, p.branch):
        assert db.info.get('business_pack_scope') is None
        assert issue_snapshot(db, p.invoice, p.user).customer_snapshot == before
    assert snapshot.customer_snapshot == before


def test_stale_or_revoked_selected_scope_cannot_resolve_invoice_terms(db, issued_pack_invoice):
    p = issued_pack_invoice
    p.grant.active = False; db.commit()
    with native_writer(db, p.user, p.branch):
        db.info['business_pack_scope'] = p.scope
        try:
            with pytest.raises(HTTPException) as error:
                invoice_business_terms(db, p.invoice, p.user)
            assert error.value.status_code == 403
        finally:
            db.info.pop('business_pack_scope', None)


def test_unowned_old_invoice_cannot_adopt_parent_order_pack(db, issued_pack_invoice):
    p = issued_pack_invoice
    anchor = PackRecordOwnership.__table__
    db.connection().execute(delete(anchor).where(anchor.c.resource_table == 'srm_invoices', anchor.c.resource_key == str(p.invoice.id)))
    db.commit()
    with native_writer(db, p.user, p.branch):
        db.info['business_pack_scope'] = p.scope
        try:
            for issuing in (False, True):
                with pytest.raises(HTTPException) as error:
                    invoice_business_terms(db, p.invoice, p.user, issuing=issuing)
                assert error.value.status_code == 403
        finally:
            db.info.pop('business_pack_scope', None)


def test_unowned_new_draft_cannot_adopt_an_already_committed_checkout(db, issued_pack_invoice):
    p = issued_pack_invoice
    with native_writer(db, p.user, p.branch):
        draft = SRMInvoiceDraft(organization_id=1, sales_order_id=p.invoice.sales_order_id, customer_id=p.invoice.customer_id,
            source_type='sales_order', currency=p.invoice.currency, created_by=p.user.id)
        db.add(draft); db.flush()
        invoice = SRMInvoice(organization_id=1, invoice_number='UNOWNED-' + uuid4().hex, invoice_draft_id=draft.id,
            sales_order_id=p.invoice.sales_order_id, customer_id=p.invoice.customer_id, currency=p.invoice.currency, created_by=p.user.id)
        db.add(invoice); db.flush()
        db.info['business_pack_scope'] = p.scope
        try:
            with pytest.raises(HTTPException) as error:
                invoice_business_terms(db, invoice, p.user, issuing=True)
            assert error.value.status_code == 403
        finally:
            db.info.pop('business_pack_scope', None)


def test_foreign_actor_company_never_selects_invoice_presentation(db, issued_pack_invoice):
    p = issued_pack_invoice
    foreign = SimpleNamespace(id=p.user.id, organization_id=2)
    with native_writer(db, p.user, p.branch), pytest.raises(HTTPException) as error:
        invoice_business_terms(db, p.invoice, foreign)
    assert error.value.status_code == 403


def test_legacy_terms_reader_does_not_autoflush_pending_business_rows(db, scenario):
    from app.apps.srm.models import SRMInvoiceHistory
    from sqlalchemy import event
    user, branch, catalog, basket = scenario
    data = basket(False); data.lines = [data.lines[0]]
    with native_writer(db, user, branch):
        result = checkout(data, db, user)
        invoice = db.get(SRMInvoice, result['invoice']['id'])
        pending = SRMInvoiceHistory(invoice_id=invoice.id, to_status=invoice.status, actor_user_id=user.id, notes='Unflushed unrelated caller draft')
        db.add(pending)
        flushes = []
        def flushed(*args): flushes.append(True)
        event.listen(db, 'before_flush', flushed)
        try:
            assert invoice_business_terms(db, invoice, user)['customer'] == ['Customer', 'Customers']
            assert not flushes and pending in db.new and pending.id is None
        finally:
            event.remove(db, 'before_flush', flushed)
            db.expunge(pending)


def test_owned_invoice_cannot_switch_to_other_context_anchor(db, issued_pack_invoice):
    from app.business_packs.models import PackActivation, PackContext
    from sqlalchemy import update
    p = issued_pack_invoice
    activation = PackActivation(company_id=1, pack_key='restaurant', pack_version=1, state='active')
    db.add(activation); db.flush()
    other = PackContext(company_id=1, branch_id=p.branch, activation_id=activation.id, pack_key='restaurant', pack_version=1, state='active')
    db.add(other); db.flush()
    anchor = PackRecordOwnership.__table__
    db.connection().execute(update(anchor).where(anchor.c.resource_table=='srm_invoices', anchor.c.resource_key==str(p.invoice.id)).values(context_id=other.id))
    db.commit()
    with native_writer(db, p.user, p.branch):
        db.info['business_pack_scope'] = p.scope
        try:
            with pytest.raises(HTTPException) as error:
                invoice_business_terms(db, p.invoice, p.user)
            assert error.value.status_code == 403
        finally:
            db.info.pop('business_pack_scope', None)


def test_stale_invoice_identity_map_cannot_hide_changed_native_company(db, issued_pack_invoice):
    from sqlalchemy import update
    p = issued_pack_invoice
    db.connection().execute(update(SRMInvoice.__table__).where(SRMInvoice.id==p.invoice.id).values(organization_id=2))
    # Keep the mapped object deliberately stale: a trusted-connection corruption
    # must not make its cached labels an ownership proof.
    assert p.invoice.organization_id == 1
    with native_writer(db, p.user, p.branch):
        db.info['business_pack_scope'] = p.scope
        try:
            with pytest.raises(HTTPException) as error:
                invoice_business_terms(db, p.invoice, p.user)
            assert error.value.status_code == 403
        finally:
            db.info.pop('business_pack_scope', None)
    db.rollback()
