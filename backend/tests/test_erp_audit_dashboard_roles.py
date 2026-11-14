import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_shared_services import shared_setup, access_account
from app.models.user import User, Role
from app.shared.models import ServicePolicy

ROOT='/api/v1/access/enterprise'


def payload(db,roles):
    owner=db.query(User).filter(User.is_superuser.is_(True)).first()
    return {'companyId':1,'kind':'dashboard','key':f'user:{owner.id}:qa-role-sharing','version':0,
        'reason':'Synthetic named role sharing','values':{'name':'Synthetic shared layout','widgets':[],'sharedRoles':roles}}


@pytest.mark.parametrize('roles',[[2147483647],[-1],[0],[True],[2**40]])
def test_dashboard_rejects_invalid_roles_without_policy(client,db,shared_setup,roles):
    headers,_,_=shared_setup
    before=db.query(ServicePolicy).filter_by(kind='dashboard').count()
    response=client.put(ROOT+'/policies',headers=headers,json=payload(db,roles))
    assert response.status_code==422,response.text
    assert db.query(ServicePolicy).filter_by(kind='dashboard').count()==before


def test_dashboard_uses_named_catalog_roles_and_preserves_failed_edit(client,db,shared_setup):
    headers,_,_=shared_setup
    catalog=client.get('/api/v1/access/catalog',headers=headers,params={'companyId':1})
    assert catalog.status_code==200,catalog.text
    role=catalog.json()['legacyRoles'][0]
    assert role['name'] and db.get(Role,role['id'])
    data=payload(db,[role['id']])
    response=client.put(ROOT+'/policies',headers=headers,json=data)
    assert response.status_code==200,response.text
    ident=response.json()['id'];version=response.json()['version']
    response=client.put(ROOT+'/policies',headers=headers,json={**data,'version':version,
        'values':{**data['values'],'name':'Invalid overwrite','sharedRoles':[2147483647]}})
    assert response.status_code==422,response.text
    db.expire_all();saved=db.get(ServicePolicy,ident)
    assert saved.version==version and saved.values_json['name']=='Synthetic shared layout'
    assert saved.values_json['sharedRoles']==[role['id']]
