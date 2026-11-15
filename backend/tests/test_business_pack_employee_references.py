"""The native shift picker cannot become an attendance/profile data channel."""
from datetime import time
from types import MappingProxyType
import pytest
from tests.test_business_pack_common_core import core_case,select_pack


@pytest.fixture
def references(core_case,monkeypatch):
    from app.business_packs import common_core,employee_references
    from app.access.models import AccessPolicy
    from app.models.attendance import Shift
    from app.models.company import Company,Branch
    from app.models.security_boundary import SecurityResourceOwnership
    from app.branches.models import BranchGrant,BranchOwnership
    n=core_case
    monkeypatch.setattr(common_core,'OPERATIONS',MappingProxyType({**common_core.OPERATIONS,**employee_references.candidate_operations(common_core.CoreOperation)}))
    n.user.role.permissions=[]
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
    policy.grants={'hrms':{'enabled':True,'permissions':[],'actions':['view'],'scope':'own'}}
    other=Branch(company_id=1,name='Other native shift branch')
    n.db.add(Company(id=2,name='Foreign shift employer'));foreign=Branch(company_id=2,name='Foreign native shift branch')
    n.db.add_all([other,foreign]);n.db.flush()
    n.db.add(BranchGrant(company_id=1,user_id=n.user.id,branch_id=other.id,can_write=False))
    rows=[]
    for company,branch,name in [(1,n.branch.id,'Home shift'),(1,other.id,'Selected shift'),(2,foreign.id,'Foreign shift')]:
        shift=Shift(name=name,start_time=time(9),end_time=time(17),is_active=True);n.db.add(shift);n.db.flush()
        if n.db.get(SecurityResourceOwnership,('shifts',shift.id)) is None:n.db.add(SecurityResourceOwnership(resource_table='shifts',resource_id=shift.id,company_id=company))
        n.db.add(BranchOwnership(company_id=company,branch_id=branch,resource_table='shifts',resource_key=str(shift.id),source='native-shift-definition'))
        rows.append(shift)
    n.db.commit();n.shifts=rows;n.other_branch=other
    return n


@pytest.mark.parametrize('selector',['invalid','revoked','ambiguous'])
def test_native_shift_picker_ignores_private_selector_and_keeps_selected_branch(references,selector):
    from app.business_packs.models import PackUserGrant
    n=references
    context=select_pack(n);select_pack(n,'salon')
    if selector=='revoked':n.db.query(PackUserGrant).delete();n.db.commit()
    headers={**n.headers,'X-Suite-Branch':str(n.other_branch.id)}
    if selector!='ambiguous':headers['X-Suite-Pack-Context']='bad' if selector=='invalid' else str(context.id)
    result=n.client.get('/api/v1/attendance/shifts',headers=headers)
    assert result.status_code==200,result.text
    assert [row['id'] for row in result.json()]==[n.shifts[1].id]
    assert 'business_pack_request_binding' not in n.db.info


def test_shift_reference_native_disabled_view_is_not_promoted(references):
    from app.access.models import AccessPolicy
    n=references
    policy=n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
    policy.grants={'hrms':{'enabled':False,'permissions':[],'actions':[],'scope':'own'}};n.db.commit()
    response=n.client.get('/api/v1/attendance/shifts',headers=n.headers)
    assert response.status_code==403,response.text


def test_managed_permission_name_projections_without_ids_keep_shift_picker_scoped(references, monkeypatch):
    from types import SimpleNamespace
    from app.access import catalog
    from app.access.models import AccessPolicy
    n = references
    policy = n.db.query(AccessPolicy).filter_by(user_id=n.user.id).one()
    policy.grants = {'hrms': {'enabled': True, 'permissions': ['timesheet_view'],
        'actions': ['view'], 'scope': 'own'}}
    n.db.commit()
    original = catalog.permission_objects
    def names_only(actor):
        return [SimpleNamespace(name=item.name, module=item.module) for item in original(actor)]
    monkeypatch.setattr(catalog, 'permission_objects', names_only)
    result = n.client.get('/api/v1/attendance/shifts', headers=n.headers)
    assert result.status_code == 200, result.text
    assert [row['id'] for row in result.json()] == [n.shifts[0].id]


def replace_native_call(monkeypatch,callback):
    from app.main import app
    from fastapi.routing import iter_route_contexts
    route=next(context for context in iter_route_contexts(app.router.routes) if context.path=='/api/v1/attendance/shifts' and 'GET' in (context.methods or ()))
    def injected(db,current_user):return callback(db,current_user)
    monkeypatch.setattr(route.dependant,'call',injected)


@pytest.mark.parametrize('attack',['attendance','raw','write','bulk','scope_change'])
def test_minimal_reference_purpose_blocks_actual_data_and_mutations(references,monkeypatch,attack):
    from sqlalchemy import select,update
    from app.models.attendance import Attendance,Shift
    from app.access.models import AccessPolicy
    from app.business_packs.common_binding import CoreRequestBinding
    n=references
    def injected(db,user):
        if attack=='attendance':db.query(Attendance).all()
        elif attack=='raw':db.execute(select(Shift.__table__.c.id)).all()
        elif attack=='bulk':db.bulk_update_mappings(Shift,[{'id':n.shifts[0].id,'name':'forged'}])
        elif attack=='scope_change':
            db.info['business_pack_request_binding']=CoreRequestBinding(user.id,1,'GET','/api/v1/timesheets/projects')
            db.query(Shift).all()
        else:
            row=db.query(Shift).filter_by(id=n.shifts[0].id).one();row.name='forged';db.commit()
        return []
    replace_native_call(monkeypatch,injected)
    result=n.client.get('/api/v1/attendance/shifts',headers=n.headers)
    assert result.status_code==403,result.text
    n.db.refresh(n.shifts[0]);assert n.shifts[0].name=='Home shift'


def test_native_reference_rechecks_permission_revocation_before_query(references,monkeypatch):
    from sqlalchemy import update
    from app.access.models import AccessPolicy
    from app.models.attendance import Shift
    n=references
    def injected(db,user):
        db.connection().execute(update(AccessPolicy).where(AccessPolicy.user_id==user.id).values(status='revoked'))
        db.query(Shift).all()
        return []
    replace_native_call(monkeypatch,injected)
    response=n.client.get('/api/v1/attendance/shifts',headers=n.headers)
    assert response.status_code==403,response.text
