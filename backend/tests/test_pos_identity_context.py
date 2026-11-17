from uuid import uuid4
import pytest
from app.apps.crm.models import CRMCustomFieldValue
from tests.test_pos_customer_fields import definition, schema, payload
from tests.test_stock_resource import stock, scenario, catalog, directory_identity


@pytest.mark.parametrize('field_key',['patient_id','vehicle_registration','prescription_reference'])
def test_identity_projects_only_visible_configured_identifiers(client,db,stock,field_key):
    public=definition(db,field_key=field_key,label='Configured identifier')
    hidden=definition(db,field_key='medical_record_number',label='Hidden identity',is_visible=False)
    private=definition(db,field_key='private_note',label='Private unrelated note')
    token=schema(client,stock.headers())['schema_fingerprint']
    response=client.post('/api/v1/srm/pos/customers',headers=stock.headers(),json=payload(token,[{'field_id':public.id,'value':'ID-'+uuid4().hex},{'field_id':private.id,'value':'must not appear'}]))
    assert response.status_code==201,response.text
    buyer=response.json()['id']
    db.connection().execute(CRMCustomFieldValue.__table__.insert().values(organization_id=1,entity='companies',record_id=buyer,custom_field_id=hidden.id,value_text='hidden-value'))
    db.commit()
    result=client.get(f'/api/v1/srm/pos/customers/{buyer}/identity',headers=stock.headers())
    assert result.status_code==200,result.text
    assert result.json()['customer_id']==buyer
    assert len(result.json()['fields'])==1
    assert result.json()['fields'][0]['label']=='Configured identifier'
    assert 'hidden-value' not in result.text and 'must not appear' not in result.text
    assert client.get('/api/v1/srm/pos/customers/999999/identity',headers=stock.headers()).status_code==404


@pytest.mark.parametrize('masked',[False,True])
def test_identity_respects_readonly_and_masked_native_field_policy(client,db,stock,masked):
    from app.apps.admin_security.models import AdminProfile,AdminFieldSecurity
    public=definition(db,field_key='patient_id',label='Patient ID')
    token=schema(client,stock.headers())['schema_fingerprint']
    response=client.post('/api/v1/srm/pos/customers',headers=stock.headers(),json=payload(token,[{'field_id':public.id,'value':'PATIENT-123'}]))
    assert response.status_code==201,response.text
    buyer=response.json()['id']
    profile=AdminProfile(name=stock.actor.role.name,active=True);db.add(profile);db.flush()
    db.add(AdminFieldSecurity(profile_id=profile.id,module_name='srm',field_name=public.field_key,can_view=True,can_edit=False,mask_value=masked));db.commit()
    result=client.get(f'/api/v1/srm/pos/customers/{buyer}/identity',headers=stock.headers())
    assert result.status_code==200,result.text
    assert ('PATIENT-123' in result.text) is (not masked)
