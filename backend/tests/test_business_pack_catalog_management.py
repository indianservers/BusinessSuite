"""Real native HTTP commands over one explicitly available canonical master."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from tests.test_business_pack_http_integration import hospital_http, native_actor, grant
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer
from app.apps.srm.models import SRMProduct
from app.shared.catalog_models import CatalogDetails
from app.business_packs.models import PackMasterAvailability, PackContext, PackUserGrant

BASE = '/api/v1/catalog/items'


def body(**extra):
    return {'kind':'service','name':'Canonical appointment service','code':'SERVICE-'+uuid4().hex,'price':99.99,
        'tax':18,'currency':'INR','unit':'visit','status':'Active',**extra}


def create(client, headers, **extra):
    response=client.post(BASE+'?source=srm',headers=headers,json=body(**extra))
    assert response.status_code==201,response.text
    return response.json()


def test_native_selected_create_read_update_one_id_in_pos(client,db,hospital_http):
    headers,actor,branch,context,_,_=hospital_http
    item=create(client,headers)
    product=db.get(SRMProduct,item['id'])
    assert product.product_type=='service' and product.track_inventory is False
    assert db.query(PackMasterAvailability).filter_by(resource_table='srm_products',resource_key=str(item['id'])).count()==1
    detail=db.query(CatalogDetails).filter_by(service_id=item['id']).one()
    assert detail.product_id is None and detail.organization_id==1
    listing=client.get(BASE+'?source=srm',headers=headers)
    assert listing.status_code==200,listing.text
    assert listing.json()['permissions']['service'] is True
    assert next(row for row in listing.json()['items'] if row['id']==item['id'])['can_edit'] is True
    read=client.get(f"{BASE}/service/{item['id']}?source=srm",headers=headers)
    assert read.status_code==200,read.text
    changed={**read.json(),'name':'Updated same canonical service','price':125}
    changed.pop('id');changed.pop('features',None);changed.pop('can_edit',None)
    saved=client.put(f"{BASE}/service/{item['id']}?source=srm",headers=headers,json=changed)
    assert saved.status_code==200,saved.text
    assert saved.json()['id']==item['id'] and saved.json()['version']==item['version']+1
    pos=client.get('/api/v1/srm/pos/catalog',headers=headers)
    assert pos.status_code==200,pos.text
    assert any(row['id']==item['id'] and row['item_name']=='Updated same canonical service' for row in pos.json()['items'])


def test_other_context_not_adopted_and_version_required(client,db,hospital_http):
    headers,actor,branch,context,_,_=hospital_http
    item=create(client,headers)
    other,_=grant(db,actor,branch,'restaurant','restaurant_manager')
    foreign={**headers,'X-Suite-Pack-Context':str(other.id)}
    response=client.get(f"{BASE}/service/{item['id']}?source=srm",headers=foreign)
    assert response.status_code==404,response.text
    payload={key:value for key,value in item.items() if key not in {'id','version','features','can_edit'}}
    assert client.put(f"{BASE}/service/{item['id']}?source=srm",headers=headers,json=payload).status_code==422
    payload['version']=0
    assert client.put(f"{BASE}/service/{item['id']}?source=srm",headers=headers,json=payload).status_code==409
    assert db.query(PackMasterAvailability).filter_by(context_id=other.id,resource_key=str(item['id']),resource_table='srm_products').count()==0


@pytest.mark.parametrize('role',['doctor','cashier','receptionist'])
def test_native_srm_admin_cannot_replace_catalog_pack_action(client,db,hospital_http,role):
    headers,_,branch,context,_,_=hospital_http
    target_headers,target=native_actor(db,branch)
    grant(db,target,branch,'hospital',role,db.get(PackContext,context))
    target_headers={**target_headers,'X-Suite-Pack-Context':str(context)}
    assert client.get(BASE+'?source=srm',headers=target_headers).status_code==403
    assert client.post(BASE+'?source=srm',headers=target_headers,json=body()).status_code==403


def test_hospital_receptionist_can_read_only_the_sales_service_catalog(client, db, hospital_http):
    _, _, branch, context_id, _, payload = hospital_http
    headers, receptionist = native_actor(db, branch)
    grant(db, receptionist, branch, 'hospital', 'receptionist', db.get(PackContext, context_id))
    headers['X-Suite-Pack-Context'] = str(context_id)
    service = payload['lines'][0]['product_id']
    listed = client.get(BASE, headers=headers, params={'source': 'srm', 'kind': 'service', 'include_facets': True})
    assert listed.status_code == 200, listed.text
    assert [item['id'] for item in listed.json()['items']] == [service]
    assert client.get(f'{BASE}/service/{service}?source=srm', headers=headers).status_code == 200
    assert client.get(BASE + '?source=srm&kind=product', headers=headers).status_code == 403
    assert client.get(BASE + '?source=crm&kind=service', headers=headers).status_code == 403


def test_catalog_pack_manager_native_action_ceiling(client,db,hospital_http):
    _,_,branch,context,_,_=hospital_http
    headers,user=native_actor(db,branch,actions=('view',))
    grant(db,user,branch,'hospital','hospital_manager',db.get(PackContext,context))
    headers={**headers,'X-Suite-Pack-Context':str(context)}
    read=client.get(BASE+'?source=srm',headers=headers)
    assert read.status_code==200,read.text
    assert read.json()['permissions']=={kind:False for kind in ('product','service','membership','subscription','bundle')}
    assert client.post(BASE+'?source=srm',headers=headers,json=body()).status_code==403


def test_optional_graphs_and_arbitrary_fields_remain_closed(client,db,hospital_http):
    headers,_,_,_,_,_=hospital_http
    for extra in [{'workspace_id':1},{'branch_availability':{'scope':'all'}},{'follow_up':{'required':True,'reference':'purchase','interval_days':7}}]:
        result=client.post(BASE+'?source=srm',headers=headers,json=body(**extra))
        assert result.status_code==503,result.text
    result=client.post(BASE+'?source=srm',headers=headers,json=body(current_quantity=999))
    assert result.status_code==422,result.text


def test_generic_orm_master_update_stays_denied(db,hospital_http):
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    _,actor,branch,context,_,payload=hospital_http
    with native_writer(db,actor,branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            row=db.query(SRMProduct).filter_by(id=payload['lines'][0]['product_id']).one()
            row.item_name='Generic forbidden mutation'
            with pytest.raises(HTTPException):db.flush()
            db.rollback()
        finally:cleanup()


def test_revoked_availability_and_wrong_metadata_parent_fail_closed(client,db,hospital_http):
    headers,_,_,context,_,_=hospital_http
    item=create(client,headers)
    availability=db.query(PackMasterAvailability).filter_by(context_id=context,resource_table='srm_products',resource_key=str(item['id'])).one()
    availability.active=False;db.commit()
    assert client.get(f"{BASE}/service/{item['id']}?source=srm",headers=headers).status_code==404


@pytest.mark.parametrize('source,permission,module',[('crm','crm_products_manage','crm'),('pms','pms_manage_projects','project_management')])
def test_each_native_source_creates_and_edits_same_canonical_master(client,db,hospital_http,source,permission,module):
    from tests.test_settings_hub import actor as settings_actor
    from app.access.models import AccessPolicy
    from app.branches.models import BranchGrant
    _,_,branch,context,_,_=hospital_http
    grants={module:{'enabled':True,'permissions':[permission],'actions':['view','create','edit'],'scope':'organization'},
        'srm':{'enabled':True,'permissions':['srm_admin'],'actions':['view'],'scope':'organization'}}
    headers,user=settings_actor(db,role='catalog-'+uuid4().hex,permissions=[permission,'srm_admin'],grants=grants)
    db.add(BranchGrant(company_id=1,user_id=user.id,branch_id=branch,can_write=True));db.commit()
    grant(db,user,branch,'hospital','hospital_manager',db.get(PackContext,context))
    headers={**headers,'X-Suite-Branch':str(branch),'X-Suite-Pack-Context':str(context)}
    result=client.post(BASE+'?source='+source,headers=headers,json=body())
    assert result.status_code==201,result.text
    item=result.json()
    read=client.get(f"{BASE}/service/{item['id']}?source={source}",headers=headers)
    assert read.status_code==200,read.text
    payload={key:value for key,value in read.json().items() if key not in {'id','features','can_edit'}}
    payload['name']='Native '+source+' change'
    changed=client.put(f"{BASE}/service/{item['id']}?source={source}",headers=headers,json=payload)
    assert changed.status_code==200,changed.text
    assert changed.json()['id']==item['id'] and changed.json()['version']==2
    # Supplying a different source never launders its missing native action.
    payload['version']=changed.json()['version']
    assert client.put(f"{BASE}/service/{item['id']}?source=srm",headers=headers,json=payload).status_code==403


def test_post_lock_native_policy_revocation_rolls_back_birth(client,db,hospital_http,monkeypatch):
    from app.access.models import AccessPolicy
    from app.apps.srm.services import commercial
    headers,actor,_,_,_,_=hospital_http
    actual=commercial.lock_tenant
    def revoke(session,user):
        actual(session,user)
        table=AccessPolicy.__table__
        session.connection().execute(table.update().where(table.c.user_id==actor.id,table.c.company_id==1).values(status='suspended'))
    monkeypatch.setattr(commercial,'lock_tenant',revoke)
    code='NO-BIRTH-'+uuid4().hex
    result=client.post(BASE+'?source=srm',headers=headers,json=body(code=code))
    assert result.status_code==403,result.text
    assert db.connection().execute(select(SRMProduct.id).where(SRMProduct.sku==code)).first() is None


def test_post_lock_master_unshare_prevents_update(client,db,hospital_http,monkeypatch):
    from app.apps.srm.services import commercial
    headers,_,_,context,_,_=hospital_http
    item=create(client,headers)
    actual=commercial.lock_tenant
    def unshare(session,user):
        actual(session,user)
        table=PackMasterAvailability.__table__
        session.connection().execute(table.update().where(table.c.context_id==context,
            table.c.resource_table=='srm_products',table.c.resource_key==str(item['id'])).values(active=False))
    monkeypatch.setattr(commercial,'lock_tenant',unshare)
    payload={key:value for key,value in item.items() if key not in {'id','features','can_edit'}}
    payload['name']='Must never save after unshare'
    result=client.put(f"{BASE}/service/{item['id']}?source=srm",headers=headers,json=payload)
    assert result.status_code in {403,404},result.text
    assert db.connection().scalar(select(SRMProduct.item_name).where(SRMProduct.id==item['id']))==item['name']


@pytest.mark.parametrize('extra',[{'X-Suite-Organization':'999'},{'X-Suite-Branch':'999'}, {'X-Suite-Pack-Context':'invalid'}])
def test_explicit_foreign_or_invalid_selectors_never_fallback(client,db,hospital_http,extra):
    headers,_,_,_,_,_=hospital_http
    code='NO-SELECTOR-'+uuid4().hex
    result=client.post(BASE+'?source=srm',headers={**headers,**extra},json=body(code=code))
    assert result.status_code==403,result.text
    assert db.connection().execute(select(SRMProduct.id).where(SRMProduct.sku==code)).first() is None


def test_canonical_metadata_corruption_and_followup_preservation(client,db,hospital_http):
    headers,_,_,_,_,_=hospital_http
    item=create(client,headers)
    product=SRMProduct.__table__
    stored={'required':True,'reference':'purchase','interval_days':7}
    row=db.get(SRMProduct,item['id'])
    db.connection().execute(product.update().where(product.c.id==item['id']).values(metadata_json={**row.metadata_json,'follow_up':stored}));db.commit()
    payload={key:value for key,value in item.items() if key not in {'id','features','can_edit'}}
    payload['name']='Keep stored follow-up'
    saved=client.put(f"{BASE}/service/{item['id']}?source=srm",headers=headers,json=payload)
    assert saved.status_code==200,saved.text
    assert db.connection().scalar(select(product.c.metadata_json).where(product.c.id==item['id']))['follow_up']==stored
    detail=CatalogDetails.__table__
    db.connection().execute(detail.update().where(detail.c.service_id==item['id']).values(organization_id=999));db.commit()
    corrupt=client.get(f"{BASE}/service/{item['id']}?source=srm",headers=headers)
    assert corrupt.status_code==503,corrupt.text


@pytest.mark.parametrize('native_scope',['own','team','organization'])
def test_crm_native_record_scope_is_not_laundered_by_pack_manager(client,db,hospital_http,native_scope):
    from datetime import date
    from tests.test_settings_hub import actor as settings_actor
    from app.branches.models import BranchGrant
    from app.models.employee import Employee
    headers,other,branch,context,_,_=hospital_http
    other_item=create(client,headers)
    permissions=['crm_products_manage','srm_admin']
    grants={'crm':{'enabled':True,'permissions':['crm_products_manage'],'actions':['view','create','edit'],'scope':native_scope},
        'srm':{'enabled':True,'permissions':['srm_admin'],'actions':['view'],'scope':'organization'}}
    own_headers,user=settings_actor(db,role='catalog-record-'+uuid4().hex,permissions=permissions,grants=grants)
    db.add(BranchGrant(company_id=1,user_id=user.id,branch_id=branch,can_write=True));db.commit()
    grant(db,user,branch,'hospital','hospital_manager',db.get(PackContext,context))
    if native_scope=='team':
        manager=Employee(employee_id='MAN-'+uuid4().hex,first_name='Native',last_name='Manager',user_id=user.id,branch_id=branch,date_of_joining=date.today())
        db.add(manager);db.flush()
        report=Employee(employee_id='REP-'+uuid4().hex,first_name='Native',last_name='Report',user_id=other.id,branch_id=branch,reporting_manager_id=manager.id,date_of_joining=date.today())
        db.add(report);db.commit()
    own_headers={**own_headers,'X-Suite-Branch':str(branch),'X-Suite-Pack-Context':str(context)}
    created=client.post(BASE+'?source=crm',headers=own_headers,json=body())
    assert created.status_code==201,created.text
    mine=created.json()['id']
    listed=client.get(BASE+'?source=crm',headers=own_headers)
    assert listed.status_code==200,listed.text
    ids={row['id'] for row in listed.json()['items']}
    assert mine in ids
    assert (other_item['id'] in ids)==(native_scope in {'team','organization'})
    target=client.get(f"{BASE}/service/{other_item['id']}?source=crm",headers=own_headers)
    assert target.status_code==(200 if native_scope in {'team','organization'} else 404),target.text


def test_large_catalog_database_paging_loads_only_page_and_keeps_hidden_rows_out(client,db,hospital_http):
    from sqlalchemy import event
    headers,actor,branch,context,_,_=hospital_http
    other,_=grant(db,actor,branch,'restaurant','restaurant_manager')
    table=SRMProduct.__table__
    rows=[{'id':30000+i,'organization_id':1,'created_by':actor.id,'sku':f'BULK-{i:05}',
        'item_name':f'Bulk service {i:05}','product_type':'service','sales_rate':i,'active':True,
        'category_name':'Bulk category','metadata_json':{'catalog_tags':['bulk','even' if i%2==0 else 'odd']}} for i in range(1500)]
    db.connection().execute(table.insert(),rows)
    availability=PackMasterAvailability.__table__
    db.connection().execute(availability.insert(),[{'company_id':1,'branch_id':branch,
        'context_id':context if i<1200 else other.id,'resource_table':'srm_products','resource_key':str(30000+i),
        'active':True,'revision':1} for i in range(1500)])
    db.commit()
    loaded=[];sql=[]
    def on_load(session,obj):
        if isinstance(obj,SRMProduct):loaded.append(obj.id)
    def on_sql(connection,cursor,statement,parameters,execution,many):
        if statement.lstrip().upper().startswith('SELECT') and 'FROM srm_products' in statement:sql.append(statement)
    event.listen(db,'loaded_as_persistent',on_load)
    connection=db.connection();event.listen(connection,'before_cursor_execute',on_sql)
    try:
        response=client.get(BASE+'?source=srm&search=Bulk&sort=name&page=101&per_page=7&include_facets=true',headers=headers)
    finally:
        event.remove(db,'loaded_as_persistent',on_load);event.remove(connection,'before_cursor_execute',on_sql)
    assert response.status_code==200,response.text
    value=response.json()
    assert value['total']==1200 and value['pages']==172
    assert [row['id'] for row in value['items']]==list(range(30700,30707))
    assert len(loaded)<=7 and all(ident<31200 for ident in loaded)
    assert len(sql)<=8,sql
    assert any('LIMIT' in statement.upper() and 'OFFSET' in statement.upper() for statement in sql)
    assert value['facets']['categories']==['Bulk category'] and value['facets']['tags']==['bulk','even','odd']
    ordered=client.get(BASE+'?source=srm&item_keys=service:31199,service:30001,service:31200&key_order=true&per_page=2',headers=headers)
    assert ordered.status_code==200,ordered.text
    assert ordered.json()['total']==2 and [row['id'] for row in ordered.json()['items']]==[31199,30001]
    filtered=client.get(BASE+'?source=srm&search=Bulk&tag=even&sort=price&direction=desc&per_page=3',headers=headers)
    assert filtered.status_code==200,filtered.text
    assert filtered.json()['total']==600 and [row['id'] for row in filtered.json()['items']]==[31198,31196,31194]


def test_initial_unmanaged_cached_native_permission_revocation_denies_command(db,hospital_http):
    from app.access.models import AccessPolicy
    from app.models.user import role_permissions
    from app.business_packs.access import resolve_context
    from app.business_packs.catalog_management import save_item
    from app.shared.catalog import ItemInput
    _,actor,branch,context,_,_=hospital_http
    with native_writer(db,actor,branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        cached=list(actor.role.permissions)
        db.connection().execute(AccessPolicy.__table__.delete().where(AccessPolicy.user_id==actor.id))
        for name in ('_suite_policy_version','_suite_grants'):
            if hasattr(actor,name):delattr(actor,name)
        actor._suite_permission_objects=cached
        db.connection().execute(role_permissions.delete().where(role_permissions.c.role_id==actor.role_id))
        db.info['business_pack_scope']=scope
        code='REVOKED-BEFORE-HASH-'+uuid4().hex
        try:
            with pytest.raises(HTTPException) as error:
                save_item(db,actor,'srm',ItemInput.model_validate(body(code=code)))
            assert error.value.status_code==403
            assert db.connection().execute(select(SRMProduct.id).where(SRMProduct.sku==code)).first() is None
        finally:db.info.pop('business_pack_scope',None)


def test_unchanged_echoed_native_shared_branch_policy_requires_all_branch_writes(client,db,hospital_http):
    from app.models.company import Branch
    from app.branches.models import BranchGrant
    headers,actor,branch,_,_,_=hospital_http
    item=create(client,headers)
    other=Branch(company_id=1,name='Read only catalog destination',code='CAT-READ',is_active=True)
    db.add(other);db.flush()
    db.add(BranchGrant(company_id=1,user_id=actor.id,branch_id=other.id,can_write=False))
    metadata=db.connection().scalar(select(SRMProduct.metadata_json).where(SRMProduct.id==item['id']))
    metadata['catalog_branches']={'default':False,'overrides':{str(branch):True,str(other.id):True}}
    db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id==item['id']).values(metadata_json=metadata));db.commit()
    read=client.get(f"{BASE}/service/{item['id']}?source=srm",headers=headers)
    assert read.status_code==200,read.text
    payload={key:value for key,value in read.json().items() if key not in {'id','features','can_edit'}}
    assert payload['branch_availability']=={'scope':'selected','branch_ids':sorted([branch,other.id])}
    payload['price']=999
    denied=client.put(f"{BASE}/service/{item['id']}?source=srm",headers=headers,json=payload)
    assert denied.status_code==403,denied.text
    from decimal import Decimal
    assert db.connection().scalar(select(SRMProduct.sales_rate).where(SRMProduct.id==item['id']))==Decimal(str(item['price']))
    assert db.connection().scalar(select(CatalogDetails.version).where(CatalogDetails.service_id==item['id']))==item['version']
    # Omission retains native historical semantics, rather than inventing a
    # stronger global write rule for a command that did not edit branch policy.
    payload.pop('branch_availability')
    allowed=client.put(f"{BASE}/service/{item['id']}?source=srm",headers=headers,json=payload)
    assert allowed.status_code==200,allowed.text


def test_private_workspace_offering_never_enters_counts_facets_or_pages(client,db,hospital_http):
    from app.apps.project_management.models import PMSWorkspace
    headers,actor,_,_,_,_=hospital_http
    item=create(client,headers,name='PRIVATE-WORKSPACE-SERVICE',category='PRIVATE-WORKSPACE-CATEGORY',tags=['private-workspace-tag'])
    workspace=PMSWorkspace(name='Private unreviewed workspace',organization_id=1)
    db.add(workspace);db.flush()
    db.connection().execute(CatalogDetails.__table__.update().where(CatalogDetails.service_id==item['id']).values(workspace_id=workspace.id));db.commit()
    listed=client.get(BASE+'?source=srm&include_facets=true&per_page=100',headers=headers)
    assert listed.status_code==200,listed.text
    assert item['id'] not in {row['id'] for row in listed.json()['items']}
    assert 'PRIVATE-WORKSPACE' not in listed.text and 'private-workspace-tag' not in listed.text
    targeted=client.get(BASE+'?source=srm&search=PRIVATE-WORKSPACE',headers=headers)
    assert targeted.status_code==200 and targeted.json()['total']==0,targeted.text
    direct=client.get(f"{BASE}/service/{item['id']}?source=srm",headers=headers)
    assert direct.status_code==503,direct.text


@pytest.mark.parametrize('srm_create,admin',[(True,False),(False,False),(False,True),(True,True)])
def test_fresh_dual_module_configuration_features_and_actual_write(client,db,hospital_http,srm_create,admin):
    from tests.test_settings_hub import actor as settings_actor
    from app.branches.models import BranchGrant
    _,_,branch,context,_,_=hospital_http
    permissions=['crm_products_manage']+(['srm_admin'] if srm_create else [])
    grants={'crm':{'enabled':True,'permissions':['crm_products_manage'],'actions':['view','create','edit'],'scope':'organization'}}
    if srm_create:grants['srm']={'enabled':True,'permissions':['srm_admin'],'actions':['view','create','edit'],'scope':'organization'}
    headers,user=settings_actor(db,role='catalog-features-'+uuid4().hex,permissions=permissions,grants=grants,admin=admin)
    db.add(BranchGrant(company_id=1,user_id=user.id,branch_id=branch,can_write=True));db.commit()
    grant(db,user,branch,'hospital','hospital_manager',db.get(PackContext,context))
    headers={**headers,'X-Suite-Branch':str(branch),'X-Suite-Pack-Context':str(context)}
    created=client.post(BASE+'?source=crm',headers=headers,json=body())
    assert created.status_code==201,created.text
    value=client.get(f"{BASE}/service/{created.json()['id']}?source=crm",headers=headers)
    assert value.status_code==200,value.text
    assert value.json()['features']['scheduling_configure'] is srm_create
    assert value.json()['features']['workspaces'] is False
    policy=client.put('/api/v1/srm/service-checkout/policies',headers=headers,json={'service_product_id':created.json()['id'],
        'default_duration_minutes':45,'min_duration_minutes':15,'max_duration_minutes':90})
    assert policy.status_code==(200 if srm_create else 403),policy.text


def test_feature_probe_preserves_all_actor_authorization_attributes(db,hospital_http):
    from app.business_packs.catalog_management import features,authority
    from app.business_packs.access import resolve_context
    _,actor,branch,context,_,_=hospital_http
    with native_writer(db,actor,branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        db.info['business_pack_scope']=scope
        # Match the real endpoint: native catalogue authority is established
        # before its advisory projection, including normal relationship reads.
        authority(db,actor,'srm','service')
        # Probe while pretending to render a different foreground module.
        # Its real native grants and named permissions remain unchanged.
        actor._suite_current_module='crm'
        actor._suite_branch_roles_fingerprint='unchanged-foreground-fingerprint'
        before={key:value for key,value in vars(actor).items() if key!='_sa_instance_state'}
        try:
            assert features(db,actor,scope)['scheduling_configure'] is True
            after={key:value for key,value in vars(actor).items() if key!='_sa_instance_state'}
            assert after==before
        finally:db.info.pop('business_pack_scope',None)


def test_read_only_branch_never_advertises_configuration(client,db,hospital_http):
    from app.branches.models import BranchGrant
    headers,actor,branch,_,_,_=hospital_http
    native=db.query(BranchGrant).filter_by(user_id=actor.id,branch_id=branch,company_id=1).one()
    native.can_write=False;db.commit()
    response=client.get(BASE+'?source=srm',headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['features']['scheduling_configure'] is False


@pytest.mark.parametrize('attack',['clone','company','correlation','projection','plain_alias','outside_purpose','wrong_scope'])
def test_certified_metadata_predicate_does_not_exempt_raw_columns_or_changed_ast(db,hospital_http,attack):
    from dataclasses import replace
    from sqlalchemy.sql import visitors
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs.catalog_predicate import _projection,_workspace_predicate
    _,actor,branch,context,_,_=hospital_http
    with native_writer(db,actor,branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            with _projection(db,actor,scope,'srm',('service',)):
                certified=_workspace_predicate(db,scope)
                query=db.query(SRMProduct.id).filter(~certified)
                if attack=='clone':query=db.query(SRMProduct.id).filter(~certified._clone())
                elif attack=='company':
                    binding=next(node for node in visitors.iterate(certified) if getattr(node,'value',None)==scope.company_id)
                    binding.value=999
                elif attack=='correlation':certified.element.element._correlate=()
                elif attack=='projection':
                    raw=next(node for node in visitors.iterate(certified) if getattr(node,'name',None)=='workspace_id')
                    query=query.add_columns(raw)  # Same raw object outside approved subtree.
                elif attack=='plain_alias':
                    alias=CatalogDetails.__table__.alias('unregistered_metadata')
                    query=query.add_columns(alias.c.workspace_id)
                elif attack=='wrong_scope':db.info['business_pack_scope']=replace(scope,context_revision=scope.context_revision+1)
                if attack!='outside_purpose':
                    with pytest.raises(HTTPException) as error:query.all()
                    assert error.value.status_code==403
            if attack=='outside_purpose':
                with pytest.raises(HTTPException) as error:query.all()
                assert error.value.status_code==403
        finally:
            db.info['business_pack_scope']=scope
            cleanup()


@pytest.mark.parametrize('native_scope',['own','team','department','branch','organization','assigned'])
@pytest.mark.parametrize('source,module,permission',[('crm','crm','crm_products_manage'),('pms','project_management','pms_manage_projects')])
def test_admin_inspection_cannot_promote_native_product_write_scope(client,db,hospital_http,native_scope,source,module,permission):
    from datetime import date
    from tests.test_settings_hub import actor as settings_actor
    from app.models.employee import Employee
    from app.models.company import Branch,Department
    _,_,branch,context,_,_=hospital_http
    grants={module:{'enabled':True,'permissions':[permission],'actions':['view','create','edit'],'scope':native_scope},
        'srm':{'enabled':True,'permissions':['srm_admin'],'actions':['view'],'scope':'organization'}}
    headers,user=settings_actor(db,role='catalog-scope-'+uuid4().hex,permissions=[permission,'srm_admin'],grants=grants,admin=True)
    grant(db,user,branch,'hospital','hospital_manager',db.get(PackContext,context))
    _,peer=settings_actor(db,role='catalog-peer-'+uuid4().hex)
    _,outside=settings_actor(db,role='catalog-outside-'+uuid4().hex)
    other_branch=Branch(company_id=1,name='Other native employment branch',code='CAT-EMP-OTHER',is_active=True)
    db.add(other_branch);db.flush()
    department=Department(branch_id=branch,name='Native owning department')
    other_department=Department(branch_id=other_branch.id,name='Other owning department')
    db.add_all([department,other_department]);db.flush()
    manager=Employee(employee_id='CAT-M-'+uuid4().hex,first_name='Native',last_name='Manager',user_id=user.id,
        branch_id=branch,department_id=department.id,date_of_joining=date.today())
    db.add(manager);db.flush()
    db.add_all([Employee(employee_id='CAT-P-'+uuid4().hex,first_name='Native',last_name='Peer',user_id=peer.id,
        branch_id=branch,department_id=department.id,reporting_manager_id=manager.id,date_of_joining=date.today()),
        Employee(employee_id='CAT-O-'+uuid4().hex,first_name='Native',last_name='Outside',user_id=outside.id,
        branch_id=other_branch.id,department_id=other_department.id,date_of_joining=date.today())])
    db.flush()
    for ident,creator in [(50001,user),(50002,peer),(50003,outside)]:
        db.connection().execute(SRMProduct.__table__.insert().values(id=ident,organization_id=1,created_by=creator.id,
            sku=f'SCOPE-{ident}',item_name=f'Scope service {ident}',product_type='service',active=True,sales_rate=10,
            metadata_json={'catalog_branches':{'default':False,'overrides':{str(branch):True}}}))
        db.connection().execute(CatalogDetails.__table__.insert().values(organization_id=1,service_id=ident,version=1,unit='visit',images=[],custom_fields={},pricing_options=[]))
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context,resource_table='srm_products',resource_key=str(ident)))
    db.commit()
    headers={**headers,'X-Suite-Branch':str(branch),'X-Suite-Pack-Context':str(context)}
    listed=client.get(BASE+f'?source={source}&search=Scope%20service',headers=headers)
    assert listed.status_code==200,listed.text
    rows={row['id']:row for row in listed.json()['items']}
    assert {50001,50002,50003}<=rows.keys()  # Existing companyadmin inspection is broad read only.
    expected={50001:native_scope!='assigned',50002:native_scope in {'team','department','branch','organization'},50003:native_scope=='organization'}
    for ident,editable in expected.items():
        assert rows[ident]['can_edit'] is editable,(native_scope,ident,rows[ident])
        payload={key:value for key,value in rows[ident].items() if key not in {'id','features','can_edit'}}
        payload['price']=11
        saved=client.put(f'{BASE}/service/{ident}?source={source}',headers=headers,json=payload)
        assert (saved.status_code==200) is editable,(native_scope,ident,saved.text)
        if not editable:assert saved.status_code in {403,404},saved.text


@pytest.mark.parametrize('admin',[False,True])
def test_branch_module_read_role_never_promotes_configuration_feature(client,db,hospital_http,admin):
    from tests.test_settings_hub import actor as settings_actor
    from app.branches.models import BranchGrant
    _,_,branch,context,_,existing=hospital_http
    crm={'enabled':True,'permissions':['crm_products_manage'],'actions':['view','create','edit'],'scope':'organization'}
    srm={'enabled':True,'permissions':['srm_admin'],'actions':['view','create','edit'],'scope':'organization'}
    headers,user=settings_actor(db,role='cat-branch-'+uuid4().hex,permissions=['crm_products_manage','srm_admin'],grants={'crm':crm,'srm':srm},admin=admin)
    db.add(BranchGrant(company_id=1,user_id=user.id,branch_id=branch,can_write=True,module_grants={'crm':crm,'srm':{**srm,'actions':['view']}}));db.commit()
    grant(db,user,branch,'hospital','hospital_manager',db.get(PackContext,context))
    headers={**headers,'X-Suite-Branch':str(branch),'X-Suite-Pack-Context':str(context)}
    listed=client.get(BASE+'?source=crm',headers=headers)
    assert listed.status_code==200,listed.text
    assert listed.json()['permissions']['service'] is True
    assert listed.json()['features']['scheduling_configure'] is False
    denied=client.put('/api/v1/srm/service-checkout/policies',headers=headers,json={'service_product_id':existing['lines'][0]['product_id'],
        'default_duration_minutes':45,'min_duration_minutes':15,'max_duration_minutes':90})
    assert denied.status_code==403,denied.text


def test_selected_pos_excludes_workspace_master_and_direct_checkout_has_no_effects(client,db,hospital_http):
    from app.apps.project_management.models import PMSWorkspace
    from app.apps.srm.models import SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement
    headers,actor,branch,context,_,payload=hospital_http
    product_id=payload['lines'][0]['product_id']
    workspace=PMSWorkspace(name='Private selected POS workspace',organization_id=1)
    db.add(workspace);db.flush()
    db.add(CatalogDetails(organization_id=1,service_id=product_id,workspace_id=workspace.id,version=1));db.commit()
    listing=client.get('/api/v1/srm/pos/catalog',headers=headers)
    assert listing.status_code==200,listing.text
    assert all(row['id']!=product_id for row in listing.json()['items'])
    models=(SRMSalesOrder,SRMInvoice,SRMReceipt,SRMInventoryMovement)
    before=tuple(db.query(model).count() for model in models)
    result=client.post('/api/v1/srm/service-checkout',headers=headers,json=payload)
    assert result.status_code==503,result.text
    assert tuple(db.query(model).count() for model in models)==before


def test_selected_linked_product_requires_closed_pos_purpose(db,hospital_http):
    from app.shared.follow_ups import linked_product
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    headers,actor,branch,context,_,payload=hospital_http
    with native_writer(db,actor,branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            with pytest.raises(HTTPException) as error:linked_product(db,actor,payload['lines'][0]['product_id'])
            assert error.value.status_code==503
        finally:cleanup()



def test_checkout_selector_preserves_exact_existing_verified_binding(db,hospital_http):
    from app.apps.srm.service_checkout_api import pack_selection
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    headers,actor,branch,context,_,payload=hospital_http
    with native_writer(db,actor,branch):
        scope=resolve_context(db,actor,db.info['branch_context'],context)
        cleanup=install(db,scope,policy=native_srm_policy('hospital').policy)
        try:
            dependency=pack_selection(str(context),db,actor)
            assert next(dependency) is scope
            assert db.info['business_pack_scope'] is scope
            with pytest.raises(StopIteration):next(dependency)
            assert db.info['business_pack_scope'] is scope
        finally:cleanup()
