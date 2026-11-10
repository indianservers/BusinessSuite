"""Route-wide deny checks for a signed-in account with every module disabled."""
import re
from starlette.requests import Request
from app.main import app
from app.access.catalog import request_module
from app.access.models import AccessPolicy,AccessMembership
from app.core.route_policy import dependency_names,is_public
from tests.test_authorization_audit import identity,routes


def test_disabled_modules_deny_every_registered_private_read(client,db,record_property):
    user,headers=identity(db,'no_modules_audit',[])
    company_id=1
    db.add(AccessMembership(user_id=user.id,company_id=company_id,active=True,is_admin=False))
    db.add(AccessPolicy(user_id=user.id,company_id=company_id,grants={},status='active'))
    db.commit()
    failures=[];checked=0;modules=set()
    for path,route in routes(app.router):
        if 'GET' not in route.methods or is_public(path) or 'get_current_user' not in set(dependency_names(route.dependant)):
            continue
        concrete=re.sub(r'\{[^}]+\}','1',path)
        request=Request({'type':'http','method':'GET','path':concrete,'query_string':b'','headers':[],'route':route})
        module=request_module(request)
        if not module:continue
        # Discovery of enabled modules is an authenticated account capability.
        if concrete=='/api/v1/business-os/modules' or concrete.startswith('/api/v1/branches/'):
            continue  # Account/branch discovery is independently permission-scoped, not a business-module read.
        response=client.get(concrete,headers=headers,follow_redirects=False)
        checked+=1;modules.add(module)
        if response.status_code!=403:failures.append((concrete,module,response.status_code))
    record_property('private_reads_checked',checked)
    record_property('modules',','.join(sorted(modules)))
    assert checked>1000,(checked,modules)
    assert not failures,failures[:20]
