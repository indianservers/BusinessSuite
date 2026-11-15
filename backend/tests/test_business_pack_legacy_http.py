"""Actual legacy branch HTTP proof after production exclusion integration."""
from sqlalchemy import select
import pytest
from tests.test_business_pack_http_integration import hospital_http,scenario,catalog,directory_identity

@pytest.mark.parametrize('native_metadata',['missing','retagged'])
def test_real_http_unconfigured_branch_cannot_read_private_sources_after_native_retag(client,db,hospital_http,scenario,native_metadata):
    from tests.test_business_pack_http_integration import create,native_actor
    from app.models.company import Branch
    from app.branches.models import BranchOwnership,BranchRecordShare
    from app.apps.srm.models import SRMInvoice,SRMAuditLog,SRMSalesOrder
    from tests.test_srm_native_transaction_operations import native_writer
    from uuid import uuid4
    headers,_,pack_branch,context_id,_,payload=hospital_http
    private=create(client,headers,payload)
    branch=Branch(company_id=1,name='Genuine legacy branch',code='LEG-'+uuid4().hex[:8]);db.add(branch);db.commit()
    legacy_headers,actor=native_actor(db,branch.id,admin=True)
    with native_writer(db,actor,branch.id):
        legacy=SRMInvoice(organization_id=1,invoice_number='LEG-'+uuid4().hex,customer_id=101,currency='INR',status='draft',subtotal=10,tax_amount=0,total_amount=10,balance_amount=10,created_by=actor.id)
        historical=SRMInvoice(organization_id=1,invoice_number='HIST-'+uuid4().hex,customer_id=101,currency='INR',status='draft',subtotal=10,tax_amount=0,total_amount=10,balance_amount=10,created_by=actor.id)
        order=SRMSalesOrder(organization_id=1,order_number='LEG-'+uuid4().hex,title='Native legacy order',customer_id=101,created_by=actor.id,status='draft')
        db.add_all([legacy,historical,order]);db.flush()
        audit=SRMAuditLog(organization_id=1,entity_type='sales_order',entity_id=order.id,action='historical',actor_user_id=actor.id,after_json={'private_note':'PRIVATE-AUDIT-PATIENT'})
        db.add(audit);db.commit();legacy_id=legacy.id;historical_id=historical.id;audit_id=audit.id
    # Historical bad metadata is seeded BEFORE immutable anchors. Even static107
    # prevents retagging an already-private source; that guarantee is separately
    # tested. Trusted fixture insertion emulates the preexisting mismatch only.
    if native_metadata=='missing':
        owner=BranchOwnership.__table__
        for table,ident in [('srm_invoices',historical_id),('srm_audit_logs',audit_id)]:
            db.connection().execute(owner.delete().where(owner.c.resource_table==table,owner.c.resource_key==str(ident)))
    from app.business_packs.models import PackRecordOwnership
    anchor=PackRecordOwnership.__table__
    for table,ident in [('srm_invoices',historical_id),('srm_audit_logs',audit_id)]:
        db.connection().execute(anchor.insert().values(company_id=1,branch_id=pack_branch,context_id=context_id,resource_table=table,resource_key=str(ident),source='historical-fixture'))
    private_audits=[audit_id]
    db.add(BranchRecordShare(company_id=1,resource_table='crm_companies',resource_key='101',branch_id=branch.id));db.commit()
    response=client.get('/api/v1/srm/invoices/'+str(historical_id),headers=legacy_headers)
    assert response.status_code==404,response.text
    response=client.get('/api/v1/srm/invoices/'+str(legacy_id),headers=legacy_headers)
    assert response.status_code==200,response.text
    response=client.get('/api/v1/srm/customer-360/101',headers=legacy_headers)
    assert response.status_code==200,response.text
    assert not any(row.get('id') in private_audits for row in response.json().get('audit_trail',[]))
    assert 'Private hospital specialist' not in response.text
    assert 'PRIVATE-AUDIT-PATIENT' not in response.text

    repair_headers={**scenario[2][0],'X-Suite-Branch':str(branch.id),'X-Suite-Pack-Context':'99999999'}
    response=client.post('/api/v1/branches/ownership/assign',headers=repair_headers,json={'table_name':'srm_invoices','resource_keys':[str(historical_id)],'branch_id':branch.id,'reason':'Attempted private source move'})
    assert response.status_code==403,response.text
    assert 'pack-private source' in response.json()['detail']
