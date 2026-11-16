from uuid import uuid4
from types import SimpleNamespace
from datetime import datetime,timezone
import pytest
from sqlalchemy import select,update,insert
from tests.test_business_pack_control_branch_signup import owner,draft_context,ROOT,platform_store,platform_headers

@pytest.mark.parametrize('operation',['masters','activate'])
@pytest.mark.parametrize('fault',['foreigncompany','inactive','deleted','ordinary'])
def test_addressed_control_destination_is_server_verified(client,db,owner,operation,fault):
    from app.models.company import Branch,Company
    from app.business_packs.models import PackContext
    from app.branches.models import BranchLifecycle
    from app.access.models import AccessMembership
    from app.models.user import User
    h,company,bid,a,email=owner
    created=draft_context(client,owner);assert created.status_code==201,created.text
    c=created.json()
    if fault=='foreigncompany':
        other=Company(name='Foreign control');db.add(other);db.flush()
        # The actual source ID remains immutable: caller's company header cannot adopt it.
        h={**h,'X-Suite-Organization':str(other.id)}
    elif fault=='inactive':db.connection().execute(update(Branch.__table__).where(Branch.id==bid).values(is_active=False))
    elif fault=='deleted':
        response=client.post(f'/api/v1/branches/{bid}/trash',headers=h,json={'expected_version':0,'reason':'Retire configured test branch'})
        assert response.status_code==200,response.text
    else:
        user=db.query(User).filter_by(email=email).one()
        db.query(AccessMembership).filter_by(user_id=user.id,company_id=company).one().is_admin=False
    db.commit()
    h={**h,'X-Suite-Pack-Context':'invalid-stale','X-Suite-Branch':'9999999'}
    if operation=='masters':
        result=client.put(ROOT+f"/contexts/{c['id']}/masters",headers=h,json={'kind':'products','id':1,'active':True,
            'expected_context_revision':c['revision'],'expected_revision':0,'reason':'Attempt exact branch write'})
    else:
        result=client.post(ROOT+f"/contexts/{c['id']}/activate",headers=h,json={'expected_revision':c['revision'],
            'activation_revision':a['revision'],'reason':'Attempt exact branch activation'})
    assert result.status_code==403,result.text
    from app.business_packs.models import PackMasterAvailability
    assert db.connection().scalar(select(PackMasterAvailability.id)) is None
    assert db.connection().scalar(select(PackContext.state).where(PackContext.id==c['id']))=='draft'


def test_target_resolver_matches_exact_registered_route_only():
    from app.business_packs.control_target import addressed_branch
    for method,path in [('GET','/business-packs/contexts/{context_id}/masters'),
                        ('PUT','/business-packs/contexts/{context_id}/masters/export'),
                        ('PUT','/business-packs/contexts/{context_id}/grants/{user_id}')]:
        request=SimpleNamespace(method=method,scope={'route':SimpleNamespace(path=path)})
        assert addressed_branch(None,None,request) is None


def test_oversized_control_context_id_denied_without_integer_conversion_500(client,owner):
    from app.business_packs.control_target import addressed_branch
    from fastapi import HTTPException
    h,_,_,_,_=owner
    ident='9'*5000
    result=client.put(ROOT+'/contexts/'+ident+'/masters',headers=h,json={'kind':'products','id':1,'active':True,
        'expected_context_revision':1,'expected_revision':0,'reason':'Reject oversized native context identifier'})
    assert result.status_code==422,result.text  # Native request-boundary range contract runs first.
    template='/api/v1/access/settings/business-packs/contexts/{context_id}/masters'
    request=SimpleNamespace(method='PUT',scope={'route':SimpleNamespace(path=template)},
        path_params={'context_id':ident},url=SimpleNamespace(path=template.format(context_id=ident)))
    with pytest.raises(HTTPException) as error:addressed_branch(None,None,request)
    assert error.value.status_code==403
