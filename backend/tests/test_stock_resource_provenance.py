"""A company-less native line inherits provenance only through an audited private root."""
from dataclasses import replace
from uuid import uuid4
import pytest
from sqlalchemy import select,delete,update
from sqlalchemy.orm import Session
from app.business_packs.boundary import PackNativeLink,PackDerivedLink,install
from app.branches.models import BranchOwnership
from app.apps.srm.models import SRMSalesOrder,SRMSalesOrderLine
from app.models.email_outbox import EmailOutbox
from tests.test_business_pack_boundary import native,packs,POLICY,forbidden

FIELDS=frozenset({'organization_id','event_key','module','recipient','subject','body','is_html'})
PARENT=PackNativeLink('srm_sales_order_lines','sales_order_id','srm_sales_orders')
POLICY_LINE=replace(POLICY,record_tables=POLICY.record_tables|{'email_outbox'},native_links=(*POLICY.native_links,PARENT),
    derived_links=(PackDerivedLink('email_outbox',frozenset({'srm_sales_order_lines'}),FIELDS),))


def test_private_line_native_company_and_branch_bridge_is_explicit_and_exact(native):
    n=native;db=n.db;owner=BranchOwnership.__table__
    for table,ident in [('srm_sales_orders',n.ids['own']),('srm_sales_order_lines',n.lines['own'])]:
        db.connection().execute(owner.insert().values(resource_table=table,resource_key=str(ident),company_id=1,branch_id=n.scope.branch_id,source='known-native-source'))
    db.commit();source=db.get(SRMSalesOrderLine,n.lines['own']);cleanup=install(db,n.scope,policy=POLICY_LINE)
    try:
        row=EmailOutbox(organization_id=1,event_key=uuid4().hex,module='srm',recipient='test@example.invalid',subject='Derived private line',body='Private source')
        row._suite_source_record=source;db.add(row);db.commit()
        assert db.get(EmailOutbox,row.id) is row
    finally:cleanup()


@pytest.mark.parametrize('fault',['foreign_context_root','foreign_company_root','missing_line_owner','missing_root_owner','dirty_fk','persisted_fk_repoint','root_id_spoof','no_private_link','other_session','pending_line'])
def test_private_line_parent_bridge_cannot_use_forged_anchors_or_shared_master(native,fault):
    n=native;db=n.db;owner=BranchOwnership.__table__
    for table,ident in [('srm_sales_orders',n.ids['own']),('srm_sales_orders',n.ids['foreign']),('srm_sales_order_lines',n.lines['own'])]:
        # Missing historical metadata is seeded missing, never produced by
        # bypassing the durable private-sidecar deletion guard.
        if fault=='missing_line_owner' and table=='srm_sales_order_lines':continue
        if fault=='missing_root_owner' and table=='srm_sales_orders' and ident==n.ids['own']:continue
        db.connection().execute(owner.insert().values(resource_table=table,resource_key=str(ident),company_id=1,branch_id=n.scope.branch_id,source='known-native-source'))
    db.commit();source=db.get(SRMSalesOrderLine,n.lines['own']);root=db.get(SRMSalesOrder,n.ids['own'])
    if fault=='foreign_context_root':db.connection().execute(SRMSalesOrderLine.__table__.update().where(SRMSalesOrderLine.id==source.id).values(sales_order_id=n.ids['foreign']));db.expire(source)
    elif fault=='foreign_company_root':db.connection().execute(SRMSalesOrder.__table__.update().where(SRMSalesOrder.id==root.id).values(organization_id=2))
    policy=replace(POLICY_LINE,native_links=POLICY.native_links) if fault=='no_private_link' else POLICY_LINE
    other=Session(bind=db.connection(),join_transaction_mode='rollback_only') if fault=='other_session' else None
    if other:source=other.get(SRMSalesOrderLine,n.lines['own'])
    cleanup=install(db,n.scope,policy=policy)
    try:
        if fault=='dirty_fk':source.sales_order_id=n.ids['foreign']
        elif fault=='persisted_fk_repoint':db.connection().execute(SRMSalesOrderLine.__table__.update().where(SRMSalesOrderLine.id==n.lines['own']).values(sales_order_id=n.ids['foreign']))
        elif fault=='root_id_spoof':root.id=n.ids['foreign']
        elif fault=='pending_line':source=SRMSalesOrderLine(sales_order_id=n.ids['own'],product_id=n.product_ids['shared'],quantity=1);db.add(source)
        row=EmailOutbox(organization_id=1,event_key=uuid4().hex,module='srm',recipient='test@example.invalid',subject='Forbidden',body='Forbidden')
        row._suite_source_record=source;db.add(row)
        forbidden(db.flush);db.rollback()
    finally:
        cleanup()
        if other:other.close()
