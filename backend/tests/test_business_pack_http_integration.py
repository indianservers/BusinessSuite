"""Real authentication/request-binding HTTP proofs; no actor dependency override."""
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import pytest
from app.access.models import AccessPolicy
from app.branches.models import BranchGrant
from app.business_packs.models import PackActivation,PackContext,PackUserGrant,PackMasterAvailability
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from app.business_packs.runtime import RUNTIME_SUPPORT,activation_readiness
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMPOSSession
from app.apps.srm.service_checkout import save_policy,save_eligibility
from app.apps.srm.service_checkout_schemas import PolicyInput,EligibilityInput
from tests.test_settings_hub import actor
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_srm_native_transaction_operations import native_writer

BASE='/api/v1/srm'

def native_actor(db,branch,actions=('view','create','edit','approve'),admin=False):
    headers,user=actor(db,role='http-srm-'+uuid4().hex,permissions=['srm_admin','reports_view'],admin=admin)
    user.organization_id=1
    db.add(BranchGrant(company_id=1,branch_id=branch,user_id=user.id,can_write=True))
    db.add(AccessPolicy(company_id=1,user_id=user.id,status='active',grants={'srm':{'enabled':True,'permissions':['srm_admin'],'actions':list(actions),'scope':'organization'},'hrms':{'enabled':True,'permissions':['reports_view'],'actions':['view'],'scope':'organization'}}))
    db.commit()
    return {**headers,'X-Suite-Branch':str(branch)},user


def grant(db,user,branch,key,role,context=None):
    if context is None:
        activation=PackActivation(company_id=1,pack_key=key,pack_version=1,state='active');db.add(activation);db.flush()
        context=PackContext(company_id=1,branch_id=branch,activation_id=activation.id,pack_key=key,pack_version=1,state='active');db.add(context);db.flush()
    row=PackUserGrant(company_id=1,branch_id=branch,context_id=context.id,user_id=user.id,role=role)
    db.add(row);db.commit()
    return context,row


@pytest.fixture
def hospital_http(db,scenario):
    _,branch,catalog,_=scenario
    headers,user=native_actor(db,branch)
    provider_data=dict(db.query(IndustryRecord).filter_by(kind='resource').one().data)
    employee_id=provider_data['employee_id'];provider_data['resource_type']='doctor'
    context,role=grant(db,user,branch,'hospital','hospital_manager')
    for table,ident in [('employees',employee_id),('crm_companies',101),('srm_products',catalog[2][1])]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    # Fixture setup uses the same audited native write + record boundary. HTTP
    # operations below rely solely on the production authentication dependency.
    with native_writer(db,user,branch):
        scope=resolve_context(db,user,db.info['branch_context'],context.id)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            provider=IndustryRecord(organization_id=1,branch_id=branch,kind='resource',title='Private hospital specialist',status='active',request_id=str(uuid4()),created_by=user.id,data=provider_data)
            register=SRMPOSSession(organization_id=1,session_number='HTTP-'+uuid4().hex,status='open',cashier_user_id=user.id,created_by=user.id)
            db.add_all([provider,register]);db.commit()
            policy=save_policy(PolicyInput(service_product_id=catalog[2][1],default_duration_minutes=30,min_duration_minutes=5,max_duration_minutes=120),db,user)
            eligibility=save_eligibility(EligibilityInput(policy_id=policy['id'],expected_policy_revision=policy['revision'],provider_resource_id=provider.id,employee_id=employee_id),db,user)
            payload={'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register.id,
                'lines':[{'client_line_key':str(uuid4()),'line_kind':'booked_service','product_id':catalog[2][1],
                    'booking':{'policy_id':policy['id'],'expected_policy_revision':policy['revision'],'eligibility_id':eligibility['id'],
                    'expected_eligibility_revision':eligibility['revision'],'provider_resource_id':provider.id,'employee_id':employee_id,
                    'starts_at':(datetime.now(timezone.utc)+timedelta(days=2)).replace(hour=10,minute=0,second=0,microsecond=0).isoformat(),'duration_minutes':30}}],
                'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':'118'}]}
        finally:cleanup()
    return {**headers,'X-Suite-Pack-Context':str(context.id)},user,branch,context.id,role.id,payload


def create(client,headers,payload):
    result=client.post(BASE+'/service-checkout',headers=headers,json=payload)
    assert result.status_code==201,result.text
    return result.json()


def test_real_http_hospital_checkout_native_graph_replay_and_runtime_gate(client,db,hospital_http):
    headers,_,branch,context,_,payload=hospital_http
    # Published workflows do not publish unrelated packs or weaken their gate.
    assert 'retail' not in RUNTIME_SUPPORT
    unpublished=activation_readiness(db,1,'retail',branch)
    assert not unpublished['ready'] and not unpublished['isolation_ready']
    assert 'Operational pack isolation is not enabled for this release yet.' in unpublished['reasons']
    result=create(client,headers,payload)
    assert create(client,headers,payload)==result
    assert result['invoice']['balance']=='0.00'
    capability_response=client.get(BASE+'/industry/capabilities',headers=headers)
    assert capability_response.status_code==200,capability_response.text
    assert capability_response.json()['checkout_create'] is True
    assert capability_response.json()['checkout_collect'] is True
    for path in [f"/sales-orders/{result['sales_order_id']}", f"/invoices/{result['invoice']['id']}",f"/receipts/{result['receipts'][0]['id']}",
        f"/industry/appointments/{result['lines'][0]['appointment_id']}/billing"]:
        response=client.get(BASE+path,headers=headers)
        assert response.status_code==200,response.text
    assert db.info.get('business_pack_scope') is None
    assert db.info.get('business_pack_policy') is None


def test_real_http_doctor_cannot_read_native_financial_routes(client,db,hospital_http):
    headers,_,branch,context,_,payload=hospital_http
    result=create(client,headers,payload)
    doctor_headers,doctor=native_actor(db,branch)
    grant(db,doctor,branch,'hospital','doctor',db.get(PackContext,context))
    doctor_headers['X-Suite-Pack-Context']=str(context)
    capability_response=client.get(BASE+'/industry/capabilities',headers=doctor_headers)
    assert capability_response.status_code==200,capability_response.text
    assert capability_response.json()['checkout_create'] is False
    assert capability_response.json()['checkout_collect'] is False
    for path in [f"/sales-orders/{result['sales_order_id']}", f"/invoices/{result['invoice']['id']}",f"/invoices/{result['invoice']['id']}/pdf",f"/receipts/{result['receipts'][0]['id']}"]:
        response=client.get(BASE+path,headers=doctor_headers)
        assert response.status_code==403,response.text
        assert 'Private hospital specialist' not in response.text
        assert set(response.json())=={'detail'}
        assert 'customer_id' not in response.text and 'invoice_number' not in response.text


def test_real_http_unconfigured_branch_does_not_require_another_branch_pack(client, db, hospital_http):
    from app.models.company import Branch
    from app.branches.models import BranchGrant
    headers, user, _, _, _, _ = hospital_http
    branch = Branch(company_id=1, name='Independent common workspace')
    db.add(branch); db.flush()
    db.add(BranchGrant(company_id=1, branch_id=branch.id, user_id=user.id, can_write=True))
    db.commit()
    legacy_headers = {key: value for key, value in headers.items() if key != 'X-Suite-Pack-Context'}
    legacy_headers['X-Suite-Branch'] = str(branch.id)
    response = client.get('/api/v1/access/me', headers=legacy_headers)
    assert response.status_code == 200, response.text
    discovery = response.json()['businessPacks']
    assert discovery['selectorRequired'] is False and discovery['selectionState'] == 'none'
    assert len(discovery['contexts']) == 1
    capability_response = client.get(BASE+'/industry/capabilities', headers=legacy_headers)
    assert capability_response.status_code == 200, capability_response.text
    assert capability_response.json()['checkout_create'] is True
    assert db.info.get('business_pack_scope') is None


def test_real_http_chef_cannot_read_other_pack_ids(client,db,hospital_http):
    headers,_,branch,_,_,payload=hospital_http
    result=create(client,headers,payload)
    chef_headers,chef=native_actor(db,branch)
    context,_=grant(db,chef,branch,'restaurant','chef')
    chef_headers['X-Suite-Pack-Context']=str(context.id)
    for path in [f"/sales-orders/{result['sales_order_id']}", f"/service-checkout/{result['id']}",f"/invoices/{result['invoice']['id']}",f"/receipts/{result['receipts'][0]['id']}",f"/industry/appointments/{result['lines'][0]['appointment_id']}/billing"]:
        response=client.get(BASE+path,headers=chef_headers)
        assert response.status_code in (403,404),response.text
        assert 'Private hospital specialist' not in response.text
        assert set(response.json())=={'detail'}
        assert 'customer_id' not in response.text and 'invoice_number' not in response.text


@pytest.mark.parametrize('other_pack', [
    'retail', 'construction', 'pharma', 'accounting_firm', 'salon', 'restaurant',
])
def test_real_http_same_native_business_owner_cannot_read_other_pack_financial_ids(
        client, db, hospital_http, other_pack):
    # Keep native actor, organization and branch identical. Neither staff role
    # denial nor a different branch may hide a missing operational pack guard.
    headers, user, branch, _, _, payload = hospital_http
    result = create(client, headers, payload)
    context, _ = grant(db, user, branch, other_pack, 'business_owner')
    other_headers = {**headers, 'X-Suite-Pack-Context': str(context.id)}
    for path in [f"/sales-orders/{result['sales_order_id']}",
                 f"/service-checkout/{result['id']}",
                 f"/invoices/{result['invoice']['id']}",
                 f"/receipts/{result['receipts'][0]['id']}",
                 f"/industry/appointments/{result['lines'][0]['appointment_id']}/billing"]:
        response = client.get(BASE + path, headers=other_headers)
        assert response.status_code == 404, (other_pack, path, response.text)
        assert set(response.json()) == {'detail'}
        assert 'Private hospital specialist' not in response.text
        assert 'customer_id' not in response.text
    # Changing the selector must never destroy the original private records.
    original = client.get(BASE + f"/service-checkout/{result['id']}", headers=headers)
    assert original.status_code == 200, original.text
    assert original.json()['id'] == result['id']


@pytest.mark.parametrize('method,path,body',[
    ('GET','/api/v1/reports/global-search?q=patient',None),
    ('POST','/api/v1/data-transfer/export/inspect',{}),
])
def test_real_http_unsupported_search_export_fail_closed(client,hospital_http,method,path,body):
    headers,*_=hospital_http
    response=client.request(method,path,headers=headers,json=body)
    assert response.status_code==503,response.text


def test_real_http_invalid_revoked_selector_and_control_repair(client,db,hospital_http):
    headers,_,branch,context,grant_id,payload=hospital_http
    invalid={**headers,'X-Suite-Pack-Context':'99999999'}
    assert client.post(BASE+'/service-checkout',headers=invalid,json=payload).status_code==403
    row=db.get(PackUserGrant,grant_id);row.active=False;db.commit()
    assert client.post(BASE+'/service-checkout',headers=headers,json=payload).status_code==403
    # A real company administrator without any pack grant must retain repair
    # controls even when the browser still sends an obsolete operational selector.
    admin_headers,admin=native_actor(db,branch,admin=True)
    admin_headers['X-Suite-Pack-Context']=str(context)
    response=client.get('/api/v1/access/settings/business-packs/configuration',headers=admin_headers)
    assert response.status_code==200,response.text


@pytest.mark.parametrize('pack_role', ['hospital_manager', 'business_owner'])
def test_real_http_pack_role_preserves_native_permission_ceiling(client,db,hospital_http,pack_role):
    headers,user,_,_,grant_id,payload=hospital_http
    grant_row=db.get(PackUserGrant,grant_id)
    grant_row.role=pack_role
    grant_row.revision+=1
    policy=db.query(AccessPolicy).filter_by(user_id=user.id,company_id=1).one()
    policy.grants={'srm':{'enabled':True,'permissions':['srm_admin'],'actions':['view'],'scope':'organization'}};db.commit()
    response=client.post(BASE+'/service-checkout',headers=headers,json=payload)
    assert response.status_code==403,response.text
