"""Private creation provenance cannot be replaced by an object marker or master."""
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.business_packs.boundary import PackBoundaryPolicy, PackDerivedLink, install
from app.business_packs.models import PackRecordOwnership
from app.models.email_outbox import EmailOutbox
from app.apps.srm.models import SRMSalesOrder, SRMProduct
from tests.test_business_pack_boundary import native, POLICY, forbidden
from tests.test_business_pack_access import packs

FROZEN=frozenset({'event_key','module','recipient','recipient_user_id','subject','body','is_html','organization_id'})
LINK=PackDerivedLink('email_outbox',frozenset({'srm_sales_orders'}),FROZEN)
DERIVED=replace(POLICY,record_tables=POLICY.record_tables|{'email_outbox'},derived_links=(LINK,))


def email(n, source=None):
    row=EmailOutbox(event_key='derived:'+uuid4().hex,organization_id=1,module='srm',recipient='qa@example.invalid',subject='Native event',body='Private delivery body')
    if source is not None:row._suite_source_record=source
    n.db.add(row)
    return row


def anchor(n,row):
    return n.db.connection().execute(select(PackRecordOwnership.context_id).where(
        PackRecordOwnership.resource_table=='email_outbox',PackRecordOwnership.resource_key==str(row.id))).scalar()


def test_derived_adapter_is_immutable_private_code_owned_policy():
    for args in [('email_outbox',{'srm_sales_orders'},FROZEN),('email_outbox',frozenset({'email_outbox'}),FROZEN),('email_outbox',frozenset({'srm_sales_orders'}),frozenset())]:
        with pytest.raises(ValueError):PackDerivedLink(*args)
    with pytest.raises(ValueError):replace(DERIVED,derived_links=[LINK])
    with pytest.raises(ValueError):replace(DERIVED,derived_links=(LINK,LINK))
    with pytest.raises(ValueError):replace(DERIVED,derived_links=(PackDerivedLink('email_outbox',frozenset({'srm_products'}),FROZEN),))


def test_existing_private_source_creates_separate_anchor_and_history_needs_no_marker(native):
    n=native;source=n.db.get(SRMSalesOrder,n.ids['own'])
    cleanup=install(n.db,n.scope,policy=DERIVED)
    try:
        row=email(n,source);n.db.flush()
        assert anchor(n,row)==n.scope.context_id
        n.db.commit();ident=row.id
        del row._suite_source_record
        row.status='failed';row.attempts=2;row.error='Provider unavailable';n.db.commit()
        assert row.id==ident and row.status=='failed' and row.attempts==2
        assert anchor(n,row)==n.scope.context_id
    finally:cleanup()


@pytest.mark.parametrize('source_kind',['none','fake','foreign','legacy','master','new','id_spoof','deleted','other_session','self'])
def test_marker_does_not_authorize_new_delivery(native,source_kind):
    n=native
    source=n.db.get(SRMSalesOrder,n.ids['own'])
    foreign=n.db.get(SRMSalesOrder,n.ids['foreign'])
    legacy=n.db.get(SRMSalesOrder,n.ids['legacy'])
    master=n.db.get(SRMProduct,n.product_ids['own'])
    other_session=Session(bind=n.db.connection(),join_transaction_mode='rollback_only') if source_kind=='other_session' else None
    if other_session:source=other_session.get(SRMSalesOrder,n.ids['own'])
    cleanup=install(n.db,n.scope,policy=DERIVED)
    try:
        if source_kind=='none':source=None
        elif source_kind=='fake':source=SimpleNamespace(id=n.ids['own'],organization_id=1)
        elif source_kind=='foreign':source=foreign
        elif source_kind=='legacy':source=legacy
        elif source_kind=='master':source=master
        elif source_kind=='new':
            source=SRMSalesOrder(organization_id=1,order_number=uuid4().hex,title='Pending source',created_by=n.current_user.id);n.db.add(source)
        elif source_kind=='id_spoof':source.id=n.ids['foreign']
        elif source_kind=='deleted':n.db.delete(source)
        row=email(n,source)
        if source_kind=='self':row._suite_source_record=row
        forbidden(n.db.flush)
        n.db.rollback()
        assert n.db.connection().execute(select(EmailOutbox.id).where(EmailOutbox.event_key==row.event_key)).first() is None
    finally:
        cleanup()
        if other_session:other_session.close()


@pytest.mark.parametrize('field,value',[('event_key','retarget'),('module','hrms'),('recipient','other@example.invalid'),('recipient_user_id',999),('subject','Changed'),('body','Changed'),('is_html',True),('organization_id',2)])
def test_historic_delivery_identity_and_payload_cannot_be_retargeted(native,field,value):
    n=native;source=n.db.get(SRMSalesOrder,n.ids['own']);cleanup=install(n.db,n.scope,policy=DERIVED)
    try:
        row=email(n,source);n.db.commit()
        setattr(row,field,value)
        forbidden(n.db.flush);n.db.rollback()
    finally:cleanup()


def test_two_pending_deliveries_cannot_form_creation_cycle(native):
    n=native
    cyclic=replace(DERIVED,derived_links=(PackDerivedLink('email_outbox',frozenset({'srm_sales_orders','srm_sales_order_lines'}),FROZEN),))
    cleanup=install(n.db,n.scope,policy=cyclic)
    try:
        first=email(n);second=email(n)
        first._suite_source_record=second;second._suite_source_record=first
        forbidden(n.db.flush);n.db.rollback()
    finally:cleanup()


def test_adapter_columns_are_checked_against_actual_native_mapper(native):
    n=native
    bad=replace(DERIVED,derived_links=(replace(LINK,immutable_fields=FROZEN|{'not_a_native_field'}),))
    with pytest.raises(ValueError):install(n.db,n.scope,policy=bad)


def test_existing_anchor_does_not_replace_persisted_native_company_proof(native):
    n=native;source=n.db.get(SRMSalesOrder,n.ids['own'])
    source.organization_id=2;n.db.commit()
    cleanup=install(n.db,n.scope,policy=DERIVED)
    try:
        email(n,source);forbidden(n.db.flush);n.db.rollback()
    finally:cleanup()


def test_existing_anchor_does_not_replace_persisted_native_branch_proof(native):
    from app.apps.srm.industry_models import IndustryRecord
    n=native
    source=IndustryRecord(organization_id=1,branch_id=n.p.branches['b'].id,kind='appointment',title='Wrong native branch',status='booked',request_id=str(uuid4()),created_by=n.current_user.id,data={})
    n.db.add(source);n.db.flush()
    n.db.add(PackRecordOwnership(company_id=1,branch_id=n.scope.branch_id,context_id=n.scope.context_id,resource_table=source.__tablename__,resource_key=str(source.id)));n.db.commit()
    policy=replace(DERIVED,record_tables=DERIVED.record_tables|{'srm_industry_records'},derived_links=(replace(LINK,source_tables=frozenset({'srm_industry_records'})),))
    cleanup=install(n.db,n.scope,policy=policy)
    try:
        email(n,source);forbidden(n.db.flush);n.db.rollback()
    finally:cleanup()
