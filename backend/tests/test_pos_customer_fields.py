"""Native selected-POS custom fields are typed canonical values, not graph grants."""
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from app.apps.crm.models import CRMCompany,CRMCustomField,CRMCustomFieldValue
from app.business_packs.models import PackContext
from tests.test_stock_resource import stock,scenario,catalog,directory_identity
from tests.test_business_pack_http_integration import native_actor,grant
BASE='/api/v1/srm/pos'


def definition(db,**values):
    row=CRMCustomField(**({'organization_id':1,'entity':'companies','field_key':'pos_'+uuid4().hex,'label':'POS additional field','field_type':'text','is_active':True,'is_visible':True}|values))
    db.add(row);db.commit();return row


def schema(client,headers):
    response=client.get(BASE+'/customer-schema',headers=headers)
    assert response.status_code==200,response.text
    return response.json()


def payload(token=None,values=None):
    return {'name':'Custom customer '+uuid4().hex,'address':'Supplied customer billing address','state':'Telangana','country':'IN',
        'schema_fingerprint':token,'custom_fields':values or []}


def test_required_false_zero_choices_and_phone_are_canonical_and_atomic(client,db,stock):
    defs=[]
    for kind in ['text','checkbox','number','dropdown','phone','date']:
        defs.append(definition(db,field_type=kind,is_required=True,options_json=['Gold','Standard'] if kind=='dropdown' else None))
    # Unrelated native entity definitions must never block customer creation.
    foreign=CRMCustomField(organization_id=1,entity='contacts',field_key='contact_only',label='Contact private required',is_required=True,is_active=True);db.add(foreign);db.commit()
    current=schema(client,stock.headers());assert current['registration_available'] is True
    assert {row['id'] for row in current['fields']}=={row.id for row in defs}
    assert client.get(BASE+'/customers',headers=stock.headers()).json()['features']['customers_register'] is True
    incoming=['Actual supplied answer',False,0,'Gold',{'national_number':'9876543210','country_code':'+91'},'2026-11-01']
    response=client.post(BASE+'/customers',headers=stock.headers(),json=payload(current['schema_fingerprint'],[{'field_id':field.id,'value':value} for field,value in zip(defs,incoming)]))
    assert response.status_code==201,response.text
    ident=response.json()['id'];saved={row.custom_field_id:row for row in db.query(CRMCustomFieldValue).filter_by(record_id=ident,entity='companies')}
    assert saved[defs[1].id].value_boolean is False and saved[defs[2].id].value_number==Decimal(0)
    assert saved[defs[4].id].value_json==incoming[4]
    assert all(row.organization_id==1 and row.created_by_user_id==stock.actor.id for row in saved.values())


@pytest.mark.parametrize('change',[{'is_required':True},{'options_json':{'ui':{'places':['detail']}}},{'label':'Changed field label'}])
def test_stale_schema_rejects_before_any_customer_birth(client,db,stock,change):
    field=definition(db);current=schema(client,stock.headers());before=db.query(CRMCompany).count()
    for key,value in change.items():setattr(field,key,value)
    db.commit()
    response=client.post(BASE+'/customers',headers=stock.headers(),json=payload(current['schema_fingerprint'],[{'field_id':field.id,'value':'old answer'}]))
    assert response.status_code==409,response.text
    assert db.query(CRMCompany).count()==before


@pytest.mark.parametrize('policy',['hidden','readonly','masked'])
def test_actual_native_role_field_policy_is_restrictive_and_hidden_required_safe(client,db,stock,policy):
    from app.apps.admin_security.models import AdminProfile,AdminFieldSecurity
    field=definition(db,is_required=True)
    profile=AdminProfile(name=stock.actor.role.name,active=True);db.add(profile);db.flush()
    db.add(AdminFieldSecurity(profile_id=profile.id,module_name='srm',field_name=field.field_key,can_view=policy!='hidden',can_edit=policy!='readonly',mask_value=policy=='masked'));db.commit()
    current=schema(client,stock.headers());assert current['registration_available'] is False and current['fields']==[]
    assert field.label not in str(current)
    response=client.post(BASE+'/customers',headers=stock.headers(),json=payload(current['schema_fingerprint'],[{'field_id':field.id,'value':'cannot bypass'}]))
    assert response.status_code==403,response.text
    assert field.label not in response.text


@pytest.mark.parametrize('kind',['user','owner','unsupported_type'])
def test_unaudited_reference_or_unknown_required_type_stays_explicitly_unavailable(client,db,stock,kind):
    definition(db,field_type=kind,is_required=True)
    current=schema(client,stock.headers());assert current['registration_available'] is False and current['fields']==[]
    assert client.get(BASE+'/customers',headers=stock.headers()).json()['features']['customers_register'] is False


@pytest.mark.parametrize('fault',['duplicate','unknown','wrong_entity','foreign_company','inactive','hidden','readonly'])
def test_forged_field_identifiers_cannot_write_other_definitions(client,db,stock,fault):
    field=definition(db)
    if fault=='wrong_entity':field.entity='contacts'
    elif fault=='foreign_company':
        from app.models.company import Company
        if not db.get(Company,2):db.add(Company(id=2,name='Foreign definitions'))
        field.organization_id=2
    elif fault=='inactive':field.is_active=False
    elif fault=='hidden':field.is_visible=False
    elif fault=='readonly':
        from app.apps.admin_security.models import AdminProfile,AdminFieldSecurity
        profile=AdminProfile(name=stock.actor.role.name);db.add(profile);db.flush();db.add(AdminFieldSecurity(profile_id=profile.id,module_name='crm',field_name='cf_'+field.field_key,can_edit=False))
    db.commit();current=schema(client,stock.headers());values=[{'field_id':field.id if fault!='unknown' else 999999,'value':'Forged'}]
    if fault=='duplicate':values.append(values[0])
    before=db.query(CRMCompany).count();response=client.post(BASE+'/customers',headers=stock.headers(),json=payload(current['schema_fingerprint'],values))
    assert response.status_code==(403 if fault in ('hidden','readonly') else 422),response.text
    assert db.query(CRMCompany).count()==before


@pytest.mark.parametrize('kind,value',[('checkbox','false'),('number',False),('number','NaN'),('number','0.00001'),('dropdown','Unknown'),('multi_select',['Gold','Gold']),('phone',{'national_number':'9876543210','country_code':'+91','user_id':1})])
def test_strict_typed_values_reject_ambiguous_or_invalid_data(client,db,stock,kind,value):
    field=definition(db,field_type=kind,options_json=['Gold'] if kind in ('dropdown','multi_select') else None)
    current=schema(client,stock.headers());before=db.query(CRMCompany).count()
    response=client.post(BASE+'/customers',headers=stock.headers(),json=payload(current['schema_fingerprint'],[{'field_id':field.id,'value':value}]))
    assert response.status_code==422,response.text
    assert db.query(CRMCompany).count()==before


def test_unique_value_conflict_does_not_disclose_hidden_record_or_adopt_it(client,db,stock):
    field=definition(db,is_unique=True)
    existing=CRMCompany(organization_id=1,name='Hidden existing account',account_type='Customer');db.add(existing);db.flush()
    db.add(CRMCustomFieldValue(organization_id=1,custom_field_id=field.id,entity='companies',record_id=existing.id,value_text='Secret Unique Value'));db.commit()
    current=schema(client,stock.headers());before=db.query(CRMCompany).count()
    response=client.post(BASE+'/customers',headers=stock.headers(),json=payload(current['schema_fingerprint'],[{'field_id':field.id,'value':'secret unique value'}]))
    assert response.status_code==409,response.text
    assert existing.name not in response.text and 'secret' not in response.text.lower() and 'matches' not in response.text
    assert db.query(CRMCompany).count()==before


def test_value_and_account_birth_roll_back_together(client,db,stock,monkeypatch):
    from app.apps.srm.api import router as native
    from fastapi import HTTPException
    field=definition(db,is_required=True);current=schema(client,stock.headers())
    counts=(db.query(CRMCompany).count(),db.query(CRMCustomFieldValue).count())
    def denied(*args,**kwargs):raise HTTPException(409,'Late source audit conflict')
    monkeypatch.setattr(native,'_audit',denied)
    response=client.post(BASE+'/customers',headers=stock.headers(),json=payload(current['schema_fingerprint'],[{'field_id':field.id,'value':'Actual answer'}]))
    assert response.status_code==409,response.text
    assert (db.query(CRMCompany).count(),db.query(CRMCustomFieldValue).count())==counts


@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef')])
def test_schema_never_grants_specialists_customer_creation(client,db,stock,pack,role):
    s=stock;headers,actor=native_actor(db,s.branch)
    context,_=grant(db,actor,s.branch,pack,role,db.get(PackContext,s.contexts['hospital']) if pack=='hospital' else None)
    response=client.get(BASE+'/customer-schema',headers={**headers,'X-Suite-Pack-Context':str(context.id)})
    assert response.status_code==403,response.text


def test_schema_change_during_birth_rolls_back_values_and_identity(client,db,stock,monkeypatch):
    from app.apps.srm import pos_customer_fields as custom
    field=definition(db,is_required=True);current=schema(client,stock.headers())
    counts=(db.query(CRMCompany).count(),db.query(CRMCustomFieldValue).count())
    original=custom._insert_values;field_id=field.id
    def changed(*args,**kwargs):
        original(*args,**kwargs)
        db.connection().execute(CRMCustomField.__table__.update().where(CRMCustomField.id==field_id).values(label='Schema changed during birth'))
    monkeypatch.setattr(custom,'_insert_values',changed)
    response=client.post(BASE+'/customers',headers=stock.headers(),json=payload(current['schema_fingerprint'],[{'field_id':field.id,'value':'Actual answer'}]))
    assert response.status_code==409,response.text
    assert (db.query(CRMCompany).count(),db.query(CRMCustomFieldValue).count())==counts


@pytest.mark.parametrize('kind,value,column',[('number',0,'value_number'),('checkbox',False,'value_boolean')])
def test_unique_zero_and_false_are_not_treated_as_empty(client,db,stock,kind,value,column):
    field=definition(db,field_type=kind,is_unique=True,is_required=True)
    db.add(CRMCustomFieldValue(organization_id=1,custom_field_id=field.id,entity='companies',record_id=101,**{column:value}));db.commit()
    current=schema(client,stock.headers());before=db.query(CRMCompany).count()
    response=client.post(BASE+'/customers',headers=stock.headers(),json=payload(current['schema_fingerprint'],[{'field_id':field.id,'value':value}]))
    assert response.status_code==409,response.text
    assert db.query(CRMCompany).count()==before
