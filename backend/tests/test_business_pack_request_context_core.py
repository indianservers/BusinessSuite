"""Actual native routing hints remain independent from operational pack selectors."""
import pytest
from tests.test_business_pack_leave_core import leave_case
from tests.test_business_pack_common_core import core_case,select_pack
from app.business_packs.request_context_core import PATH


@pytest.mark.parametrize('selector',[None,'bad','999999'])
@pytest.mark.parametrize('kind',['leave','expense'])
def test_native_own_routing_masks_unavailable_manager_and_ignores_pack(leave_case,selector,kind):
    n=leave_case
    select_pack(n);select_pack(n,'salon')
    headers={**n.headers}
    if selector:headers['X-Suite-Pack-Context']=selector
    response=n.client.get(PATH,headers=headers,params={'kind':kind})
    assert response.status_code==200,response.text
    body=response.json()
    assert body['employee_id']==n.employee.id
    assert body['manager_name'] is None
    assert body['approval_path']==(['Authorized HR reviewer','Finance review'] if kind=='expense' else ['Authorized HR reviewer'])
    assert set(body)=={'employee_id','employee_name','department','branch','manager_name','approval_path','routing_note','initial_status'}
    foreign=n.client.get(PATH,headers=headers,params={'employee_id':n.manager.id})
    assert foreign.status_code==404,foreign.text


@pytest.mark.parametrize('mode',['team','organization'])
def test_native_manager_routing_keeps_scope(leave_case,mode):
    from app.access.models import AccessPolicy
    n=leave_case
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.admin.id,company_id=1).one()
    policy.grants={'hrms':{**policy.grants['hrms'],'scope':mode}};n.db.commit()
    select_pack(n)
    response=n.client.get(PATH,headers=n.admin_headers,params={'employee_id':n.employee.id})
    assert response.status_code==200,response.text
    assert response.json()['manager_name']=='Leave Reviewer'


def test_native_routing_disabled_module_is_not_promoted(leave_case):
    from app.access.models import AccessPolicy
    n=leave_case;select_pack(n)
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id,company_id=1).one()
    policy.grants={'hrms':{'enabled':False,'permissions':[],'actions':[],'scope':'own'}};n.db.commit()
    response=n.client.get(PATH,headers=n.headers)
    assert response.status_code==403,response.text


def replace_call(monkeypatch,callback):
    from app.main import app
    from fastapi.routing import iter_route_contexts
    route=next(item for item in iter_route_contexts(app.router.routes) if item.path==PATH and 'GET' in (item.methods or ()))
    def injected(db,current_user,**kwargs):return callback(db,current_user)
    monkeypatch.setattr(route.dependant,'call',injected)


@pytest.mark.parametrize('attack',['branch','branch_alias','branch_scalar','salary','profile','raw','write','bulk','revoked'])
def test_routing_restricts_graph_and_rechecks_native_authority(leave_case,monkeypatch,attack):
    from sqlalchemy import select,update
    from app.models.employee import Employee
    from app.models.payroll import EmployeeSalary
    from app.models.company import Branch
    from app.common.models import CommonPerson
    from app.access.models import AccessPolicy
    n=leave_case;select_pack(n)
    def callback(db,user):
        if attack=='branch':db.query(Branch).all()
        elif attack=='branch_alias':
            from sqlalchemy.orm import aliased
            db.query(aliased(Branch)).all()
        elif attack=='branch_scalar':db.query(Branch.name).all()
        elif attack=='salary':db.query(EmployeeSalary).all()
        elif attack=='profile':db.query(CommonPerson).all()
        elif attack=='raw':db.execute(select(Employee.__table__.c.id)).all()
        elif attack=='bulk':db.bulk_update_mappings(Employee,[{'id':n.employee.id,'first_name':'forged'}])
        elif attack=='revoked':
            db.connection().execute(update(AccessPolicy).where(AccessPolicy.user_id==user.id).values(status='revoked'))
            db.query(Employee.id).all()
        else:
            row=db.query(Employee).filter_by(id=n.employee.id).one();row.first_name='forged';db.commit()
        return {}
    replace_call(monkeypatch,callback)
    response=n.client.get(PATH,headers=n.headers)
    assert response.status_code==403,response.text


def test_cached_foreign_employee_and_refresh_cannot_escape_native_scope(leave_case,monkeypatch):
    from fastapi import HTTPException
    from app.models.employee import Employee
    n=leave_case;foreign=n.manager;identity=foreign.id;own=n.employee.id;select_pack(n)
    def callback(db,user):
        assert db.get(Employee,identity) is None
        with pytest.raises(HTTPException):db.refresh(foreign)
        assert db.get(Employee,own).id==own
        return {'guarded':True}
    replace_call(monkeypatch,callback)
    response=n.client.get(PATH,headers=n.headers)
    assert response.status_code==200,response.text
    assert response.json()=={'guarded':True}
    assert n.db.info.get('business_common_core_scope') is None



def test_private_employee_cannot_be_adopted_as_native_routing_profile(leave_case):
    from app.business_packs.models import PackRecordOwnership
    n=leave_case;identity=n.employee.id;context=select_pack(n)
    n.db.add(PackRecordOwnership(company_id=1,branch_id=n.branch.id,context_id=context.id,
        resource_table='employees',resource_key=str(identity)))
    n.db.commit()
    response=n.client.get(PATH,headers=n.headers)
    assert response.status_code==400,response.text


def test_readonly_branch_preserves_routing_read_without_write_rights(leave_case):
    from app.branches.models import BranchGrant
    n=leave_case
    grant=n.db.query(BranchGrant).filter_by(user_id=n.user.id,branch_id=n.branch.id).one()
    grant.can_write=False;n.db.commit();select_pack(n)
    response=n.client.get(PATH,headers=n.headers)
    assert response.status_code==200,response.text
    assert response.json()['employee_id']==n.employee.id



def test_native_leave_apply_dialog_routing_desktop_and_mobile(leave_case,monkeypatch):
    import json
    from tests.test_control_browser import test_control_center_real_browser
    n=leave_case;context=select_pack(n)
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT','leave-routing-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH',json.dumps({'token':n.headers['Authorization'].split(' ',1)[1],
        'branch':str(n.branch.id),'context':str(context.id)}))
    test_control_center_real_browser(n.client,n.db,None,n.headers)



def test_native_org_routing_does_not_expose_foreign_company_employee(leave_case):
    from datetime import date
    from app.models.company import Company,Branch
    from app.models.employee import Employee
    from app.branches.models import BranchOwnership
    n=leave_case
    n.db.add(Company(id=77,name='Foreign private employer'))
    branch=Branch(company_id=77,name='Foreign private branch');n.db.add(branch);n.db.flush()
    row=Employee(employee_id='FOREIGN-ROUTING',first_name='Foreign',last_name='Sensitive',branch_id=branch.id,status='Active',date_of_joining=date(2020,1,1))
    n.db.add(row);n.db.flush();identity=row.id
    n.db.add(BranchOwnership(company_id=77,branch_id=branch.id,resource_table='employees',resource_key=str(identity),source='verified-test-native-source'))
    n.db.commit();select_pack(n)
    response=n.client.get(PATH,headers=n.admin_headers,params={'employee_id':identity})
    assert response.status_code==404,response.text
    assert 'Sensitive' not in response.text
