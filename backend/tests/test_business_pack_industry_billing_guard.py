"""Blind billing reservations do not grant native project-directory reads."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import update
from tests.test_business_pack_catalog_management import hospital_http,scenario,catalog,directory_identity,native_writer
from tests.test_business_pack_http_integration import create,grant
from app.access.service import background_scope
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from app.business_packs.industry_billing_guard import reserved_billing
from app.apps.srm.models import SRMSalesOrder
from app.apps.srm.commercial_models import ProjectCommercial
from app.apps.srm.industry_models import IndustryRecord
from app.apps.project_management.models import PMSProject
from app.business_packs.models import PackRecordOwnership


@pytest.mark.parametrize('case',['foreign_context','unrelated','other_company','not_approved','corrupt_company','corrupt_record_company'])
def test_blind_reservation_exact_source_and_company(client,db,hospital_http,case):
    headers,actor,branch,context,_,payload=hospital_http
    result=create(client,headers,payload)
    order=db.get(SRMSalesOrder,result['sales_order_id'])
    other=case in {'other_company','corrupt_company'}
    from app.models.company import Company
    if db.get(Company,2) is None:db.add(Company(id=2,name='Other native tenant'))
    db.flush()
    project=PMSProject(name='Unexposed billing project',project_key=uuid4().hex[:18],organization_id=2 if other else 1)
    db.add(project);db.flush()
    if case not in {'unrelated','other_company'}:
        db.add(ProjectCommercial(project_id=project.id,customer_id=101,seller_id=1,sales_order_id=order.id,currency='INR'))
    boq=IndustryRecord(organization_id=2 if other or case=='corrupt_record_company' else 1,branch_id=branch,project_id=project.id,kind='boq',title='Private BOQ label',status='draft' if case=='not_approved' else 'approved',created_by=actor.id,request_id=str(uuid4()),data={})
    db.add(boq);db.flush()
    if case=='foreign_context':
        foreign,_=grant(db,actor,branch,'restaurant','restaurant_manager')
        db.add(PackRecordOwnership(company_id=1,branch_id=branch,context_id=foreign.id,resource_table=boq.__tablename__,resource_key=str(boq.id)))
    db.commit()
    with native_writer(db,actor,branch),background_scope(db,actor,'srm','view',branch_id=branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            order=db.get(SRMSalesOrder,order.id)
            if case in {'corrupt_company','corrupt_record_company'}:
                with pytest.raises(HTTPException) as error:reserved_billing(db,actor,sales_order=order)
                assert error.value.status_code==409 and 'Private BOQ label' not in str(error.value.detail)
            else:assert reserved_billing(db,actor,sales_order=order) is (case=='foreign_context')
        finally:cleanup()


def test_blind_guard_rejects_unproven_source_and_cached_repoint(client,db,hospital_http):
    headers,actor,branch,context,_,payload=hospital_http
    result=create(client,headers,payload);order=db.get(SRMSalesOrder,result['sales_order_id'])
    with native_writer(db,actor,branch),background_scope(db,actor,'srm','view',branch_id=branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            for supplied in [SRMSalesOrder(id=order.id,organization_id=1),order]:
                if supplied is order:db.connection().execute(update(SRMSalesOrder.__table__).where(SRMSalesOrder.id==order.id).values(organization_id=2))
                with pytest.raises(HTTPException) as error:reserved_billing(db,actor,sales_order=supplied)
                assert error.value.status_code==403
            with pytest.raises(HTTPException) as error:reserved_billing(db,actor,project_id=1)
            assert error.value.status_code==503
        finally:cleanup();db.rollback()


def test_blind_invoice_reservations_keep_company_and_canonical_child_proof(client,db,hospital_http):
    from app.business_packs.industry_billing_guard import selected_order_source_reserved
    from app.apps.srm.models import SRMInvoice,SRMSalesOrderLine
    headers,actor,branch,context,_,payload=hospital_http
    result=create(client,headers,payload)
    order_id=result['sales_order_id'];line_id=db.query(SRMSalesOrderLine.id).filter_by(sales_order_id=order_id).scalar()
    with native_writer(db,actor,branch),background_scope(db,actor,'srm','view',branch_id=branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            assert selected_order_source_reserved(db,'sales_order',order_id) is True
            assert selected_order_source_reserved(db,'sales_order_line',line_id) is True
            with pytest.raises(HTTPException) as error:selected_order_source_reserved(db,'engagement',order_id)
            assert error.value.status_code==503
            with pytest.raises(HTTPException) as error:selected_order_source_reserved(db,'sales_order',2147483647)
            assert error.value.status_code==403
            db.connection().execute(update(SRMInvoice.__table__).where(SRMInvoice.id==result['invoice']['id']).values(organization_id=2))
            with pytest.raises(HTTPException) as error:selected_order_source_reserved(db,'sales_order',order_id)
            assert error.value.status_code==409 and 'Native invoice links require reconciliation'==error.value.detail
        finally:cleanup();db.rollback()


def test_seller_authority_metadata_is_company_read_only_and_active_ceiling_stays_native(client,db,hospital_http):
    from app.models.company import Company
    from app.apps.srm.commercial_models import SellerGrant,InvoiceContext
    from app.apps.srm.services.commercial import invoice_for
    headers,actor,branch,context,_,payload=hospital_http
    result=create(client,headers,payload)
    if db.get(Company,2) is None:db.add(Company(id=2,name='Other legal seller'))
    db.flush();db.add_all([SellerGrant(organization_id=1,seller_id=2,active=True),SellerGrant(organization_id=2,seller_id=1,active=True)])
    db.connection().execute(update(InvoiceContext.__table__).where(InvoiceContext.invoice_id==result['invoice']['id']).values(seller_id=2));db.commit()
    with native_writer(db,actor,branch),background_scope(db,actor,'srm','view',branch_id=branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            assert [(row.organization_id,row.seller_id) for row in db.query(SellerGrant)]==[(1,2)]
            assert invoice_for(db,result['invoice']['id'],actor).id==result['invoice']['id']
            db.connection().execute(update(SellerGrant.__table__).where(SellerGrant.organization_id==1).values(active=False))
            db.expire_all()
            with pytest.raises(HTTPException) as error:invoice_for(db,result['invoice']['id'],actor)
            assert error.value.status_code==404
            own=db.query(SellerGrant).one();assert own.active is False
            with pytest.raises(HTTPException) as error,db.begin_nested():
                own.active=True;db.flush()
            assert error.value.status_code==403
        finally:cleanup();db.rollback()


def test_native_own_invoice_read_keeps_creator_ceiling_without_project_graph(client,db,hospital_http):
    from app.access.models import AccessPolicy
    headers,actor,branch,context,_,payload=hospital_http
    result=create(client,headers,payload)
    policy=db.query(AccessPolicy).filter_by(user_id=actor.id,company_id=1).one()
    values=dict(policy.grants);values['srm']={**values['srm'],'scope':'own'};policy.grants=values;db.commit()
    response=client.get('/api/v1/srm/invoices/'+str(result['invoice']['id']),headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['id']==result['invoice']['id']
    assert response.json()['accounting_status']['mappings']==[]
    assert 'voucher_id' not in response.json()['accounting_status']


def test_selected_native_invoice_status_exposes_only_enum_and_linked_order_is_unsupported(client,db,hospital_http):
    from app.apps.fam.models import FAMPostingJob
    from app.apps.srm.commercial_models import InvoiceDelivery
    from app.apps.srm.models import SRMContract
    headers,actor,branch,context,_,payload=hospital_http
    result=create(client,headers,payload);invoice_id=result['invoice']['id'];order_id=result['sales_order_id']
    db.add_all([FAMPostingJob(company_id=1,source_module='srm',source_record_type='invoice',source_record_id=invoice_id,posting_type='invoice',status='failed',error_message='PRIVATE ACCOUNTING ERROR'),
        InvoiceDelivery(invoice_id=invoice_id,request_id=str(uuid4()),actor_id=actor.id,status='failed',error='PRIVATE DELIVERY ERROR')]);db.commit()
    response=client.get('/api/v1/srm/invoices/'+str(invoice_id),headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['delivery_status']=='failed' and response.json()['accounting_status']=={'status':'failed','mappings':[]}
    assert 'PRIVATE' not in response.text and 'job_id' not in response.json()['accounting_status']
    db.add(SRMContract(organization_id=1,contract_number='UNREVIEWED-'+uuid4().hex[:12],sales_order_id=order_id,title='PRIVATE CONTRACT'))
    db.commit()
    response=client.get('/api/v1/srm/sales-orders/'+str(order_id),headers=headers)
    assert response.status_code==503 and 'PRIVATE CONTRACT' not in response.text
    response=client.get('/api/v1/srm/invoices/'+str(invoice_id),headers=headers)
    assert response.status_code==503 and 'PRIVATE CONTRACT' not in response.text



def test_native_capability_scope_is_verified_implicit_and_realm_mismatch_has_no_money_effect(client,db,hospital_http):
    from app.apps.srm.models import SRMInvoice,SRMReceipt
    headers,actor,branch,context,_,payload=hospital_http
    implicit={key:value for key,value in headers.items() if key!='X-Suite-Pack-Context'}
    response=client.get('/api/v1/srm/industry/capabilities',headers=implicit)
    assert response.status_code==200,response.text
    value=response.json()['operational_scope']
    assert value['realm']=='pack' and value['context_id']==context and value['user_id']==actor.id and value['company_id']==1 and value['branch_id']==branch
    assert value['pack_key']=='hospital' and value['pack_version']==1 and all(value[key]>0 for key in ('context_revision','grant_revision','activation_revision'))
    before=tuple(db.query(model).count() for model in (SRMSalesOrder,SRMInvoice,SRMReceipt))
    result=client.post('/api/v1/srm/service-checkout',headers={**implicit,'X-Suite-Expected-Pack-Realm':'legacy'},json=payload)
    assert result.status_code==409,result.text
    assert tuple(db.query(model).count() for model in (SRMSalesOrder,SRMInvoice,SRMReceipt))==before
    assert client.get('/api/v1/srm/industry/capabilities',headers={**implicit,'X-Suite-Pack-Context':'2147483647'}).status_code==403
