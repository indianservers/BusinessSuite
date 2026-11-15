"""Concurrent selected births cannot duplicate a configured unique field."""
from uuid import uuid4
from tests.test_pms_workflow_postgresql import live,race
from tests.test_stock_resource_concurrency import configured
from app.business_packs.models import PackUserGrant
from app.apps.crm.models import CRMCustomField,CRMCustomFieldValue,CRMCompany


def test_selected_customer_unique_values_serialize_on_real_native_company_writer(live):
    _,_,headers,_=configured(live)
    with live.factory() as db:
        grant=db.query(PackUserGrant).filter_by(context_id=int(headers['X-Suite-Pack-Context'])).one();grant.role='service_desk'
        field=CRMCustomField(organization_id=1,entity='companies',field_key='concurrent_reference',label='Customer reference',field_type='text',is_unique=True,is_required=True,is_visible=True,is_active=True)
        db.add(field);db.commit();ident=field.id
    response=live.client.get('/api/v1/srm/pos/customer-schema',headers=headers);assert response.status_code==200,response.text
    fingerprint=response.json()['schema_fingerprint']
    def create():
        return live.client.post('/api/v1/srm/pos/customers',headers=headers,json={'name':'Concurrent custom '+uuid4().hex,'address':'Actual supplied address','state':'Telangana','country':'IN',
            'schema_fingerprint':fingerprint,'custom_fields':[{'field_id':ident,'value':'Same supplied reference'}]})
    results=race(create,create)
    assert sorted(result.status_code for result in results)==[201,409],[result.text for result in results]
    with live.factory() as db:
        assert db.query(CRMCompany).filter(CRMCompany.name.like('Concurrent custom %')).count()==1
        assert db.query(CRMCustomFieldValue).filter_by(custom_field_id=ident).count()==1
