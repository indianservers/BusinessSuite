"""Only exact native bootstrap metadata/personal aggregates ignore pack selectors."""
import pytest
from app.business_packs.request_scope import classify_route,RouteKind
from tests.test_business_pack_common_core import core_case,select_pack


@pytest.mark.parametrize('path,kind',[
    ('/api/v1/access/enterprise/branding',RouteKind.CONTROL),
    ('/api/v1/business-os/modules',RouteKind.CONTROL),
    ('/api/v1/notifications/summary',RouteKind.PERSONAL)])
def test_only_exact_bootstrap_read_routes_are_exempt(path,kind):
    assert classify_route('GET',path) is kind
    for method in ['POST','PUT','PATCH','DELETE']:
        assert classify_route(method,path) is RouteKind.OPERATIONAL
    for neighbor in [path+'/private',path+'-export',path+'/']:
        assert classify_route('GET',neighbor) is RouteKind.OPERATIONAL


@pytest.mark.parametrize('selector',['valid','bad','999999'])
def test_bootstrap_config_reads_keep_native_membership_and_ignore_stale_selectors(core_case,selector):
    from app.shared.models import ServicePolicy
    n=core_case;ctx=select_pack(n)
    n.db.add(ServicePolicy(organization_id=1,scope_key='company:1:branding:theme',kind='branding',
        values_json={'label':'Actual company branding'},updated_by=n.admin.id));n.db.commit()
    headers={**n.headers,'X-Suite-Pack-Context':str(ctx.id) if selector=='valid' else selector}
    branding=n.client.get('/api/v1/access/enterprise/branding?companyId=1',headers=headers)
    assert branding.status_code==200,branding.text
    assert branding.json()['values']=={'label':'Actual company branding'}
    modules=n.client.get('/api/v1/business-os/modules',headers=headers)
    assert modules.status_code==200,modules.text
    assert modules.json()['company_id']==1
    assert modules.json()['modules']
    denied=n.client.get('/api/v1/access/enterprise/branding?companyId=999999',headers=headers)
    assert denied.status_code==403,denied.text
    assert n.db.info.get('business_pack_scope') is None


def test_branding_encoded_scope_does_not_override_actual_policy_company(core_case):
    from app.shared.models import ServicePolicy
    from app.models.company import Company
    n=core_case;select_pack(n)
    n.db.add(Company(id=77,name='Foreign branding company'))
    n.db.add(ServicePolicy(organization_id=77,scope_key='company:1:branding:theme',kind='branding',
        values_json={'label':'Foreign secret branding'},updated_by=n.admin.id));n.db.commit()
    response=n.client.get('/api/v1/access/enterprise/branding?companyId=1',headers={**n.headers,'X-Suite-Pack-Context':'bad'})
    assert response.status_code==200,response.text
    assert response.json()['values']=={}
    assert 'Foreign secret' not in response.text


@pytest.mark.parametrize('selector',['valid','bad','999999'])
def test_notification_summary_is_exact_personal_company_aggregate(core_case,selector):
    from app.models.notification import Notification
    from app.models.company import Company,Branch
    from app.branches.models import BranchOwnership
    n=core_case;ctx=select_pack(n)
    n.db.add(Company(id=77,name='Foreign notification company'));n.db.flush()
    foreign_branch=Branch(company_id=77,name='Foreign notification branch');n.db.add(foreign_branch);n.db.flush()
    rows=[]
    for user,company,read,title in [(n.user.id,1,False,'Own'),(n.user.id,None,False,'Global own'),
            (n.user.id,77,False,'Foreign company'),(n.admin.id,1,False,'Another user'),(n.user.id,1,True,'Already read')]:
        row=Notification(user_id=user,company_id=company,is_read=read,title=title,message='Private notification body',module='hrms',action_url='/hrms/leave');n.db.add(row);n.db.flush();rows.append(row)
        n.db.add(BranchOwnership(company_id=77 if company==77 else 1,branch_id=foreign_branch.id if company==77 else n.branch.id,
            resource_table='notifications',resource_key=str(row.id),source='verified-native-test-notification'))
    n.db.commit()
    headers={**n.headers,'X-Suite-Pack-Context':str(ctx.id) if selector=='valid' else selector}
    result=n.client.get('/api/v1/notifications/summary',headers=headers)
    assert result.status_code==200,result.text
    assert result.json()=={'groups':[{'module':'hrms','action_url':'/hrms/leave','count':2}]}
    assert 'Private notification body' not in result.text
    assert 'title' not in result.text


@pytest.mark.parametrize('method,path',[
    ('POST','/api/v1/access/enterprise/branding/logo'),('PUT','/api/v1/business-os/modules'),
    ('POST','/api/v1/notifications/summary'),('GET','/api/v1/notifications/'),
    ('GET','/api/v1/access/enterprise/branding-export')])
def test_bootstrap_classification_does_not_open_writes_or_neighbor_graphs(core_case,method,path):
    n=core_case;select_pack(n)
    result=n.client.request(method,path,headers={**n.headers,'X-Suite-Pack-Context':'bad'})
    assert result.status_code in {403,404,405,503},result.text



def test_native_nonadmin_module_configuration_mutation_remains_forbidden(core_case):
    n=core_case
    result=n.client.put('/api/v1/business-os/modules',headers=n.headers,json={'enabled_modules':['hrms']})
    assert result.status_code==403,result.text
