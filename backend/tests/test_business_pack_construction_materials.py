"""Actual project stock consumption, source integrity, rollback and pack isolation."""
from decimal import Decimal
from uuid import uuid4
from types import SimpleNamespace
import pytest

from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
from app.business_packs.models import PackMasterAvailability
from app.apps.srm.models import SRMProduct, SRMInventoryMovement


def test_selected_construction_material_issue_preserves_native_stock(client, db, construction, catalog):
    actor, branch, context, project = construction
    headers, warehouse, products = catalog
    product = products[0]
    for table, ident in [('srm_products', product), ('srm_warehouses', warehouse)]:
        db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context,
            resource_table=table, resource_key=str(ident), active=True))
    db.commit()
    before = db.query(SRMInventoryMovement).count()
    body = {'request_id':str(uuid4()),'title':'Foundation material issue','project_id':project,
        'product_id':product,'warehouse_id':warehouse,'quantity':'1.250','issue_date':'2026-11-15',
        'notes':'Actual construction stock use'}
    selected = {**headers, 'X-Suite-Pack-Context':str(context)}
    response = client.post('/api/v1/srm/industry/material-issues',headers=selected,json=body)
    assert response.status_code == 201, response.text
    replay = client.post('/api/v1/srm/industry/material-issues',headers=selected,json=body)
    assert replay.status_code == 201 and replay.json() == response.json(), replay.text
    db.expire_all()
    assert db.get(SRMProduct,product).current_quantity == Decimal('3.750')
    assert db.query(SRMInventoryMovement).count() == before+1
    summary = client.get(f'/api/v1/srm/industry/projects/{project}/summary',headers=selected)
    assert summary.status_code == 200, summary.text
    assert Decimal(str(summary.json()['actual_material_cost'])) == Decimal('50.00')


@pytest.fixture
def materials(client,db,construction,catalog):
    actor,branch,context,project=construction
    headers,warehouse,products=catalog
    product=products[0]
    for table,ident in [('srm_products',product),('srm_warehouses',warehouse)]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context,
            resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    return SimpleNamespace(actor=actor,branch=branch,context=context,project=project,product=product,
        warehouse=warehouse,headers={**headers,'X-Suite-Pack-Context':str(context)},
        body={'request_id':str(uuid4()),'title':'Valued project use','project_id':project,
            'product_id':product,'warehouse_id':warehouse,'quantity':'1.250',
            'issue_date':'2026-11-15','notes':'Actual materials from canonical receipt'})


def post(client,case,body=None,expected=201):
    response=client.post('/api/v1/srm/industry/material-issues',headers=case.headers,json=body or case.body)
    assert response.status_code==expected,response.text
    return response


def test_overdraw_and_changed_retry_leave_one_native_consumption(client,db,materials):
    from app.apps.srm.industry_models import IndustryRecord
    case=materials
    original=post(client,case).json()
    post(client,case,{**case.body,'quantity':'1.251'},409)
    post(client,case,{**case.body,'request_id':str(uuid4()),'quantity':'3.751'},409)
    assert post(client,case).json()==original
    assert db.query(IndustryRecord).filter_by(kind='material_issue').count()==1
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==1
    db.expire_all()
    assert db.get(SRMProduct,case.product).current_quantity==Decimal('3.750')


@pytest.mark.parametrize('table',['srm_products','srm_warehouses'])
def test_explicit_master_availability_is_required_before_stock_write(client,db,materials,table):
    case=materials
    available=db.query(PackMasterAvailability).filter_by(context_id=case.context,resource_table=table).one()
    available.active=False;db.commit()
    post(client,case,expected=403)
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==0
    db.expire_all()
    assert db.get(SRMProduct,case.product).current_quantity==Decimal('5.000')


@pytest.mark.parametrize('pack',['hospital','salon','restaurant','retail','pharma','accounting_firm'])
def test_other_pack_business_owner_cannot_issue_construction_materials(client,db,materials,pack):
    from tests.test_business_pack_http_integration import grant
    case=materials
    other,_=grant(db,case.actor,case.branch,pack,'business_owner')
    selected={**case.headers,'X-Suite-Pack-Context':str(other.id)}
    response=client.post('/api/v1/srm/industry/material-issues',headers=selected,json=case.body)
    assert response.status_code==403,response.text
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==0
    db.expire_all()
    assert db.get(SRMProduct,case.product).current_quantity==Decimal('5.000')


def test_late_quantity_cache_failure_rolls_back_source_stock_and_audits(client,db,materials,monkeypatch):
    from app.apps.srm import stock_resource
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.models import SRMAuditLog
    case=materials
    before=db.query(SRMInventoryMovement).count()
    audits_before=db.query(SRMAuditLog).count()
    original=stock_resource._write_quantity_cache
    def abort(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('Material cache late failure')
    with monkeypatch.context() as patch:
        patch.setattr(stock_resource,'_write_quantity_cache',abort)
        with pytest.raises(RuntimeError,match='Material cache late failure'):
            post(client,case)
    assert db.query(IndustryRecord).filter_by(kind='material_issue').count()==0
    assert db.query(SRMInventoryMovement).count()==before
    assert db.query(SRMAuditLog).count()==audits_before
    db.expire_all()
    assert db.get(SRMProduct,case.product).current_quantity==Decimal('5.000')
    post(client,case)
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==1


def test_material_source_and_movement_are_immutable_without_balance_permission(client,db,materials):
    from datetime import date
    from fastapi import HTTPException
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.models import SRMInventoryBalance
    from tests.test_srm_native_transaction_operations import native_writer
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs.construction import project_for_action
    case=materials;result=post(client,case).json()
    with native_writer(db,case.actor,case.branch):
        scope=resolve_context(db,case.actor,db.info['branch_context'],case.context)
        cleanup=install(db,scope,policy=native_srm_policy('construction').policy)
        try:
            project_for_action(db,case.actor,case.project,'manage_tasks')
            for attack in ('kind','quantity','movement','forge'):
                with pytest.raises(HTTPException) as denied:
                    with db.begin_nested():
                        row=db.get(IndustryRecord,result['id'])
                        if attack=='kind':row.kind='appointment'
                        elif attack=='quantity':row.data={**row.data,'quantity':'4.000'}
                        elif attack=='movement':db.get(SRMInventoryMovement,result['stock_movement_id']).value=Decimal('1')
                        else:
                            forged=SRMInventoryMovement(organization_id=1,movement_number='FORGED-'+uuid4().hex,
                                movement_type='pos_sale',movement_date=date(2026,11,15),product_id=case.product,
                                warehouse_id=case.warehouse,quantity_in=0,quantity_out=1,rate=40,value=40,created_by=case.actor.id)
                            forged._suite_source_record=row;db.add(forged)
                        db.flush()
                assert denied.value.status_code==403
            with pytest.raises(HTTPException) as denied:
                db.query(SRMInventoryBalance).first()
            assert denied.value.status_code==403
        finally:cleanup()
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==1


@pytest.mark.parametrize('flag',['batch_tracking','serial_tracking','expiry_tracking'])
def test_quantity_only_project_issue_cannot_bypass_tracked_stock(client,db,materials,flag):
    case=materials
    setattr(db.get(SRMProduct,case.product),flag,True);db.commit()
    post(client,case,expected=409)
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==0
    db.expire_all()
    assert db.get(SRMProduct,case.product).current_quantity==Decimal('5.000')


def test_direct_material_command_cannot_promote_native_view_to_create(db,materials):
    from contextlib import ExitStack
    from fastapi import HTTPException
    from tests.test_business_pack_http_integration import native_actor,grant
    from app.business_packs.models import PackContext
    from app.access.service import background_scope
    from app.branches.service import context
    from app.branches.boundary import install as install_branch
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.apps.srm.industry_api import MaterialInput
    from app.business_packs.construction_materials import issue
    case=materials
    _,user=native_actor(db,case.branch,actions=('view',))
    grant(db,user,case.branch,'construction','project_manager',db.get(PackContext,case.context))
    user._suite_branch_id=case.branch
    with ExitStack() as stack:
        stack.callback(install_branch(db,user,context(db,user,1,str(case.branch))))
        stack.enter_context(background_scope(db,user,'srm','view',branch_id=case.branch))
        scope=resolve_context(db,user,db.info['branch_context'],case.context)
        stack.callback(install(db,scope,policy=native_srm_policy('construction').policy))
        with pytest.raises(HTTPException) as denied:
            issue(MaterialInput.model_validate(case.body),db,user)
        assert denied.value.status_code==403
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==0


def test_nested_material_rejection_preserves_callers_transaction(db,materials):
    from fastapi import HTTPException
    from app.models.company import Company
    from app.apps.srm.industry_api import MaterialInput
    from app.business_packs.construction_materials import issue
    with db.begin_nested() as caller:
        company=db.get(Company,1)
        company.name='Caller still owns this savepoint'
        with pytest.raises(HTTPException) as denied:
            issue(MaterialInput.model_validate(materials.body),db,materials.actor)
        assert denied.value.status_code==409
        assert caller.is_active
        assert company.name=='Caller still owns this savepoint'
        caller.rollback()
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==0


def test_mutated_internal_material_input_cannot_add_negative_stock(db,materials):
    from fastapi import HTTPException
    from app.apps.srm.industry_api import MaterialInput
    from app.business_packs.construction_materials import issue
    data=MaterialInput.model_validate(materials.body)
    data.quantity=Decimal('-1.000')
    with pytest.raises(HTTPException) as denied:
        issue(data,db,materials.actor)
    assert denied.value.status_code==422
    assert db.get(SRMProduct,materials.product).current_quantity==Decimal('5.000')
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==0


def test_recursive_material_command_rolls_back_and_same_request_can_retry(client,db,materials,monkeypatch):
    from app.apps.srm.services import commercial_numbering
    from app.apps.srm.industry_api import MaterialInput
    from app.business_packs import construction_materials
    from app.apps.srm.industry_models import IndustryRecord
    def recurse(*args,**kwargs):
        construction_materials.issue(MaterialInput.model_validate(materials.body),db,materials.actor)
    with monkeypatch.context() as patch:
        patch.setattr(commercial_numbering,'reserve_number',recurse)
        post(client,materials,expected=409)
    assert db not in construction_materials._ACTIVE
    assert db.query(IndustryRecord).filter_by(kind='material_issue').count()==0
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count()==0
    db.expire_all()
    assert db.get(SRMProduct,materials.product).current_quantity==Decimal('5.000')
    post(client,materials)
