from datetime import date, timedelta
from uuid import uuid4
from decimal import Decimal
import pytest

from tests.rich_text_test_utils import organization_context
from tests.srm_test_utils import seed_invoice_parties
from app.apps.srm.models import SRMInvoice, SRMPurchaseOrder, SRMAuditLog
from app.apps.communication.models import CommunicationEmailMessage


@pytest.fixture
def documents(client, db, superuser_headers, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'COMMUNICATION_EMAIL_PROVIDER', 'stub')
    seed_invoice_parties(db)
    headers = superuser_headers
    def create(path, payload):
        response = client.post('/api/v1/'+path, headers=headers, json=payload)
        assert response.status_code == 201, response.text
        return response.json()
    quote = create('crm/quotes', {'quote_number':'SAVED-QUOTE','company_id':101,'currency':'INR','issue_date':str(date.today()),'expiry_date':str(date.today()+timedelta(days=30))})
    create(f"crm/quotes/{quote['id']}/lines", {'name':'Retained quote line','quantity':2,'unit_price':100,'tax_rate':18})
    for action in ['submit','approve','send']:
        r=client.post(f"/api/v1/crm/quotes/{quote['id']}/{action}",headers=headers,json={})
        assert r.status_code==200,r.text
    po = create('srm/procurement/purchase-orders', {'vendor_name':'Synthetic supplier','lines':[{'description':'Retained PO line','quantity':2,'unit_price':100,'tax_amount':36}]})
    invoice = create('srm/invoices/manual', {'customer_id':101,'currency':'INR','lines':[{'description':'Retained invoice line','quantity':2,'unit_price':100,'tax_amount':36}]})
    r=client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve",headers=headers)
    assert r.status_code==200,r.text
    return {kind:record['id'] for kind,record in [('quotations',quote),('purchase-orders',po),('invoices',invoice)]}


def saved(client, headers, kind, ident):
    response=client.get(f'/api/v1/srm/documents/{kind}/{ident}',headers=headers)
    assert response.status_code==200,response.text
    return response.json()


def command(record, reason='Customer requested a corrected document', **extra):
    return {'version':record['version'],'request_id':str(uuid4()),'reason':reason,**extra}


@pytest.mark.parametrize('kind',['quotations','purchase-orders','invoices'])
def test_issued_record_revision_edit_archive_and_history(client,db,superuser_headers,documents,kind):
    ident=documents[kind];base=f'/api/v1/srm/documents/{kind}/{ident}'
    original=saved(client,superuser_headers,kind,ident)
    assert not original['editable']
    assert client.patch(base,headers=superuser_headers,json=command(original,changes={})).status_code==409
    assert client.request('DELETE',base,headers=superuser_headers,json=command(original)).status_code==409
    request=command(original)
    revision=client.post(base+'/revise',headers=superuser_headers,json=request)
    assert revision.status_code==201,revision.text
    revised=revision.json()
    assert revised['record']['id']!=ident and revised['number']!=original['number']
    assert revised['editable']
    replay=client.post(base+'/revise',headers=superuser_headers,json=request)
    assert replay.status_code==201 and replay.json()['record']['id']==revised['record']['id']
    assert saved(client,superuser_headers,kind,ident)['record']==original['record']
    target=f"/api/v1/srm/documents/{kind}/{revised['record']['id']}"
    changes={'due_date':str(date.today()+timedelta(days=40))} if kind=='invoices' else {'notes':'Corrected with a recorded reason'}
    edited=client.patch(target,headers=superuser_headers,json=command(revised,changes=changes))
    assert edited.status_code==200,edited.text
    assert edited.json()['history'][0]['reason']=='Customer requested a corrected document'
    assert client.patch(target,headers=superuser_headers,json=command(revised,changes=changes)).status_code==409
    archived=client.request('DELETE',target,headers=superuser_headers,json=command(edited.json()))
    assert archived.status_code==200,archived.text
    retained=saved(client,superuser_headers,kind,revised['record']['id'])
    assert retained['removed'] and retained['history'][0]['action']=='draft_removed'
    active=client.get(f'/api/v1/srm/documents/{kind}',headers=superuser_headers).json()['items']
    assert revised['record']['id'] not in [row['id'] for row in active]
    archive=client.get(f'/api/v1/srm/documents/{kind}?include_removed=true',headers=superuser_headers).json()['items']
    assert revised['record']['id'] in [row['id'] for row in archive]


@pytest.mark.parametrize('kind',['quotations','purchase-orders','invoices'])
def test_resend_logs_recipient_reason_and_deduplicates_browser_retry(client,db,superuser_headers,documents,kind):
    ident=documents[kind];base=f'/api/v1/srm/documents/{kind}/{ident}'
    current=saved(client,superuser_headers,kind,ident)
    payload=command(current,reason='Customer requested another copy',recipient='billing@example.com')
    before=db.query(CommunicationEmailMessage).count()
    sent=client.post(base+'/send',headers=superuser_headers,json=payload)
    assert sent.status_code==200,sent.text
    assert sent.json()['status']=='sent',sent.text
    again=client.post(base+'/send',headers=superuser_headers,json=payload)
    assert again.status_code==200,again.text
    assert db.query(CommunicationEmailMessage).count()==before+1
    current=saved(client,superuser_headers,kind,ident)
    resent=client.post(base+'/send',headers=superuser_headers,json=command(current,reason='Recipient requested a second copy',recipient='billing@example.com'))
    assert resent.status_code==200 and resent.json()['status']=='sent',resent.text
    assert db.query(CommunicationEmailMessage).count()==before+2
    history=saved(client,superuser_headers,kind,ident)['history']
    assert sum(row['action']=='document_delivery' for row in history)==2


def test_invoice_revision_cannot_issue_until_original_cancelled(client,db,superuser_headers,documents):
    ident=documents['invoices'];current=saved(client,superuser_headers,'invoices',ident)
    revision=client.post(f'/api/v1/srm/documents/invoices/{ident}/revise',headers=superuser_headers,json=command(current))
    assert revision.status_code==201,revision.text
    new_id=revision.json()['record']['id']
    blocked=client.post(f'/api/v1/srm/invoices/{new_id}/approve',headers=superuser_headers)
    assert blocked.status_code==409,blocked.text
    current=saved(client,superuser_headers,'invoices',ident)
    cancelled=client.post(f'/api/v1/srm/documents/invoices/{ident}/cancel',headers=superuser_headers,json=command(current,reason='Superseded by the corrected draft'))
    assert cancelled.status_code==200,cancelled.text
    issued=client.post(f'/api/v1/srm/invoices/{new_id}/approve',headers=superuser_headers)
    assert issued.status_code==200,issued.text
    assert db.get(SRMInvoice,ident).status=='cancelled'
    assert db.get(SRMInvoice,new_id).total_amount==Decimal('236')


def test_reason_validation_and_issued_quote_cannot_be_overwritten(client,superuser_headers,documents):
    ident=documents['quotations'];row=saved(client,superuser_headers,'quotations',ident)
    assert client.post(f'/api/v1/srm/documents/quotations/{ident}/revise',headers=superuser_headers,json=command(row,reason='     ')).status_code==422
    assert client.patch(f'/api/v1/crm/quotations/{ident}',headers=superuser_headers,json={'notes':'Silent overwrite'}).status_code==409
    assert client.delete(f'/api/v1/crm/quotations/{ident}',headers=superuser_headers).status_code==409
    assert client.post(f'/api/v1/crm/quotes/{ident}/new-version',headers=superuser_headers,json={}).status_code==409
    assert client.get(f'/api/v1/srm/documents/quotations/{ident}/pdf',headers=superuser_headers).content.startswith(b'%PDF')


def test_issued_quote_pdf_is_retained_after_customer_changes(client,db,superuser_headers,documents):
    from app.apps.crm.models import CRMCompany
    ident=documents['quotations']
    path=f'/api/v1/srm/documents/quotations/{ident}/pdf'
    original=client.get(path,headers=superuser_headers).content
    customer=db.get(CRMCompany,101);customer.name='Changed customer master after quote issue';db.commit()
    assert client.get(path,headers=superuser_headers).content==original
    row=saved(client,superuser_headers,'quotations',ident)
    line=row['record']['lines'][0]
    assert client.patch(f"/api/v1/crm/quotation-items/{line['id']}",headers=superuser_headers,json={'unit_price':1}).status_code==409
    assert client.post('/api/v1/crm/quotation-items',headers=superuser_headers,json={'quotation_id':ident,'name':'Unapproved extra line','unit_price':1}).status_code==409


@pytest.mark.parametrize('activity', [None, 'project', 'active_plan', 'ready_milestone', 'invoice', 'stock'])
def test_order_cancel_retains_unused_scaffolding_but_blocks_started_work(client, db, superuser_headers, documents, activity):
    from app.apps.srm.models import SRMSalesOrder, SRMEngagement, SRMBillingPlan, SRMBillingMilestone
    headers = superuser_headers
    created = client.post('/api/v1/srm/sales-orders', headers=headers, json={
        'title': 'Unused service order', 'customer_id': 101,
        'lines': [{'description': 'Service only', 'quantity': 1, 'unit_price': 100}],
    })
    assert created.status_code == 201, created.text
    ident = created.json()['id']
    for action in ['submit', 'confirm']:
        response = client.post(f'/api/v1/srm/sales-orders/{ident}/{action}', headers=headers)
        assert response.status_code == 200, response.text
    order = db.get(SRMSalesOrder, ident)
    engagement = db.query(SRMEngagement).filter_by(sales_order_id=ident).one()
    plan = db.query(SRMBillingPlan).filter_by(engagement_id=engagement.id).one()
    milestone = db.query(SRMBillingMilestone).filter_by(billing_plan_id=plan.id).one()
    if activity == 'project': engagement.pms_project_id = 98765
    if activity == 'active_plan': plan.status = 'active'
    if activity == 'ready_milestone': milestone.status = 'ready'
    if activity == 'invoice': db.add(SRMInvoice(organization_id=order.organization_id, invoice_number='CANCEL-GUARD', sales_order_id=ident, customer_id=101, status='draft'))
    if activity == 'stock': order.metadata_json = {'inventory_issued_at': '2026-01-01T00:00:00Z'}
    db.commit()
    original = saved(client, headers, 'sales-orders', ident)
    payload = command(original, reason='Customer cancelled before service delivery')
    response = client.post(f'/api/v1/srm/documents/sales-orders/{ident}/cancel', headers=headers, json=payload)
    assert response.status_code == (409 if activity else 200), response.text
    db.refresh(order); db.refresh(engagement); db.refresh(plan); db.refresh(milestone)
    if activity:
        assert order.status == 'confirmed' and engagement.status == 'project_pending'
        assert plan.status == ('active' if activity == 'active_plan' else 'draft')
    else:
        assert order.status == engagement.status == plan.status == milestone.status == 'cancelled'
        assert response.json()['history'][0]['reason'] == payload['reason']
        child_logs = db.query(SRMAuditLog).filter_by(action='cancelled_with_order').all()
        assert len(child_logs) == 3
        assert all(log.after_json['reason'] == payload['reason'] for log in child_logs)
        replay = client.post(f'/api/v1/srm/documents/sales-orders/{ident}/cancel', headers=headers, json=payload)
        assert replay.status_code == 200
        assert db.query(SRMAuditLog).filter_by(action='cancelled_with_order').count() == 3
