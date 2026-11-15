"""Native actual-time purpose is independent of private pack enrollment."""
from dataclasses import FrozenInstanceError
import pytest
from tests.test_business_pack_common_core import core_case, select_pack, core_proof_route


@pytest.mark.parametrize('selector',['absent','malformed','stale','revoked','no-grants','ambiguous'])
@pytest.mark.parametrize('admin',[False,True])
def test_native_actual_time_ignores_private_selector_and_enrollment(core_case,selector,admin):
    from app.business_packs.models import PackUserGrant,PackRecordOwnership
    n=core_case
    first=select_pack(n);select_pack(n,'salon')
    headers=dict(n.admin_headers if admin else n.headers)
    if selector=='malformed':headers['X-Suite-Pack-Context']='not-a-context'
    if selector=='stale':headers['X-Suite-Pack-Context']='999999999'
    if selector in {'revoked','no-grants'}:
        n.db.query(PackUserGrant).delete();n.db.commit()
    if selector=='revoked':headers['X-Suite-Pack-Context']=str(first.id)
    before=n.db.query(PackRecordOwnership).count()
    result=n.client.get('/api/v1/timesheets/projects',headers=headers)
    assert result.status_code==200,result.text
    assert n.assigned.id in {row['id'] for row in result.json()}
    if not admin:
        created=n.client.post('/api/v1/timesheets/',headers=headers,json={
            'project_id':n.assigned.id,'period_start':'2026-11-09','period_end':'2026-11-15'})
        assert created.status_code==201,created.text
        assert created.json()['employee_id']==n.employee.id
    assert n.db.query(PackRecordOwnership).count()==before
    if selector in {'malformed','stale','revoked','no-grants'}:
        private=n.client.get('/api/v1/srm/service-checkout/999999',headers=headers)
        assert private.status_code==403,private.text


def test_core_marker_prevents_nested_private_resolution(core_case,monkeypatch):
    from fastapi import HTTPException
    from app.business_packs.access import resolve_context
    n=core_case;n.context=select_pack(n)
    def proof(db,user):
        with pytest.raises(HTTPException) as denied:
            resolve_context(db,user,db.info['branch_context'],requested_context_id=n.context.id)
        assert denied.value.status_code==403
        return {'isolated':True}
    result=core_proof_route(n,monkeypatch,proof)
    assert result.status_code==200,result.text
    assert result.json()=={'isolated':True}


def test_binding_is_immutable_domain_epoch_not_route_epoch():
    from app.business_packs.common_binding import CoreRequestBinding,authorization_fingerprint
    a=CoreRequestBinding(1,2,'GET','/api/v1/timesheets/projects')
    b=CoreRequestBinding(1,2,'POST','/api/v1/timesheets/')
    assert authorization_fingerprint(a)==authorization_fingerprint(b)
    assert authorization_fingerprint(a)!=authorization_fingerprint(CoreRequestBinding(2,2,'GET',a.route))
    with pytest.raises(FrozenInstanceError):a.company_id=3


@pytest.mark.parametrize('change',['revoke','disable'])
def test_initial_native_branch_change_cannot_be_captured_as_valid_core_authority(core_case,monkeypatch,change):
    from sqlalchemy import delete,update
    from app.branches.models import BranchGrant,BranchPolicy
    from app.models.company import Branch
    from app.business_packs import common_core
    n=core_case
    if change=='revoke':
        n.db.add(BranchPolicy(company_id=1,user_id=n.user.id,use_home_branch=False))
        n.db.commit()
    original=common_core.resolve_request
    def raced(db,user,request,branch_ctx,binding):
        connection=db.connection()
        if change=='revoke':
            connection.execute(delete(BranchGrant).where(BranchGrant.user_id==user.id,BranchGrant.branch_id==n.branch.id))
        else:
            connection.execute(update(Branch).where(Branch.id==n.branch.id).values(is_active=False))
        return original(db,user,request,branch_ctx,binding)
    monkeypatch.setattr(common_core,'resolve_request',raced)
    result=n.client.get('/api/v1/timesheets/projects',headers=n.headers)
    assert result.status_code==403,result.text


def test_initial_branch_role_narrowing_rejects_stale_compiled_scope(core_case,monkeypatch):
    from sqlalchemy import update
    from app.branches.models import BranchGrant
    from app.business_packs import common_core
    n=core_case
    original=common_core._native_operation_access
    changed=False
    def raced(db,user,company,operation):
        nonlocal changed
        if not changed:
            changed=True
            db.connection().execute(update(BranchGrant).where(
                BranchGrant.user_id==user.id,BranchGrant.branch_id==n.branch.id).values(
                module_grants={'hrms':{'enabled':True,'permissions':['employee_view','timesheet_view'],
                    'actions':['view','create','edit'],'scope':'own'}}))
        return original(db,user,company,operation)
    monkeypatch.setattr(common_core,'_native_operation_access',raced)
    result=n.client.get('/api/v1/timesheets/projects',headers=n.headers)
    assert result.status_code==403,result.text
    assert 'branch module authority changed' in result.text
