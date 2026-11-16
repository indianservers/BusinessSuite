from uuid import uuid4
from types import SimpleNamespace
import pytest
from sqlalchemy import select,update
from app.models.user import User
from app.apps.srm.models import SRMProduct
from app.models.audit import AuditLog
from app.business_packs.cutover_audit import setup_predicate
from app.core.audit_context import context
from app.core.canonical_audit import arm_product_birth,take_product_birth

@pytest.fixture
def native_product(db):
    from app.models.company import Company
    if db.get(Company,1) is None:db.add(Company(id=1,name='Native source company'));db.flush()
    user=User(email=uuid4().hex+'@example.test',hashed_password='unused',is_active=True)
    db.add(user);db.flush();user.organization_id=1
    row=SRMProduct(organization_id=1,sku=uuid4().hex,item_name='Native consultation',product_type='service',created_by=user.id)
    return user,row


def request(status_path='/api/v1/srm/inventory/items',method='POST',endpoint=None):
    from app.apps.srm.api.router import create_srm_product
    return SimpleNamespace(method=method,url=SimpleNamespace(path=status_path),scope={'route':SimpleNamespace(endpoint=endpoint or create_srm_product)})


def test_pending_actual_product_birth_is_single_use_and_body_cannot_forge_it(db,native_product):
    user,row=native_product;db.add(row)
    value={'storage_session':db,'actor':{'user_id':user.id}}
    token=context.set(value)
    try:
        cleanup=arm_product_birth(db,user,row);db.flush();cleanup()
        assert take_product_birth(value,db,request(),201)==('canonical:srm_product_created',row.id)
        assert take_product_birth(value,db,request(),201) is None
        value['canonical_product_birth']={'product_id':row.id,'company_id':1,'actor_id':user.id}
        assert take_product_birth(value,db,request(),201) is None
    finally:context.reset(token)

@pytest.mark.parametrize('fault',['persistent','foreigncreator','foreigncompany','wrongsession'])
def test_product_reference_requires_actual_native_birth_source(db,native_product,fault):
    user,row=native_product;db.add(row)
    if fault=='persistent':db.flush()
    elif fault=='foreigncreator':row.created_by=user.id+100
    elif fault=='foreigncompany':row.organization_id=2
    value={'storage_session':object() if fault=='wrongsession' else db,'actor':{'user_id':user.id}}
    token=context.set(value)
    try:
        with pytest.raises(ValueError):arm_product_birth(db,user,row)
        assert 'canonical_product_birth' not in value
    finally:context.reset(token)

@pytest.mark.parametrize('fault',['rollback','status','endpoint','route','context'])
def test_birth_reference_cannot_survive_failed_or_different_native_request(db,native_product,fault):
    user,row=native_product;db.add(row)
    value={'storage_session':db,'actor':{'user_id':user.id}}
    token=context.set(value)
    try:
        cleanup=arm_product_birth(db,user,row);db.flush();cleanup()
        target=value
        if fault=='rollback':db.rollback()
        if fault=='context':target=dict(value)
        req=request(status_path='/api/v1/srm/inventory/items/clone' if fault=='route' else '/api/v1/srm/inventory/items',
                    endpoint=(lambda:None) if fault=='endpoint' else None)
        assert take_product_birth(target,db,req,409 if fault=='status' else 201) is None
    finally:context.reset(token)

@pytest.mark.parametrize('fault',['none','wrongcreator','deleted','wrongsource','wrongroute','operationalPOST','unowned','foreignbranch','branchunavailable'])
def test_cutover_master_telemetry_requires_actual_canonical_source(db,native_product,fault):
    user,product=native_product;db.add(product);db.flush()
    from app.branches.models import BranchOwnership
    from app.models.company import Branch
    target=Branch(company_id=1,name='Native product source branch',is_active=True)
    other=Branch(company_id=1,name='Other native source branch',is_active=True)
    db.add_all([target,other]);db.flush()
    if fault!='unowned':
        db.add(BranchOwnership(resource_table=product.__tablename__,resource_key=str(product.id),company_id=1,branch_id=other.id if fault=='foreignbranch' else target.id,source='native-source'))
        db.flush()
    values=dict(organization_id=1,user_id=user.id,actor_authenticated=True,method='POST',endpoint='/srm/inventory/items',
        module='srm',status_code=201,action='POST',entity_type='canonical:srm_product_created',entity_id=product.id)
    if fault=='branchunavailable':product.metadata_json={'catalog_branches':{'default':False,'overrides':{}}};db.flush()
    if fault=='wrongcreator':values['user_id']=None
    elif fault=='deleted':product.deleted_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc);db.flush()
    elif fault=='wrongsource':values['entity_id']=product.id+100
    elif fault=='wrongroute':values['endpoint']='/srm/inventory/items/import'
    elif fault=='operationalPOST':values.update(endpoint='/srm/industry/records',entity_type=None,entity_id=None)
    row=AuditLog(**values);db.add(row);db.flush()
    t=AuditLog.__table__
    assert bool(db.connection().scalar(select(setup_predicate(t,1,target.id)).where(t.c.id==row.id)))==(fault in {'none','unowned'})

from tests.test_business_pack_access import packs

@pytest.mark.parametrize('private_source',['product','audit'])
def test_private_master_or_private_audit_never_exempted(db,packs,private_source):
    from app.business_packs.models import PackRecordOwnership
    p=packs;actor=p.users['doctor'];ctx=p.contexts['doctor']
    product=SRMProduct(organization_id=1,sku=uuid4().hex,item_name='Private source',created_by=actor.id)
    db.add(product);db.flush()
    from app.branches.models import BranchOwnership
    db.add(BranchOwnership(resource_table=product.__tablename__,resource_key=str(product.id),company_id=1,branch_id=ctx.branch_id,source='native-source'));db.flush()
    audit=AuditLog(organization_id=1,user_id=actor.id,actor_authenticated=True,method='POST',endpoint='/srm/inventory/items',
        module='srm',status_code=201,action='POST',entity_type='canonical:srm_product_created',entity_id=product.id)
    db.add(audit);db.flush()
    source=product if private_source=='product' else audit
    db.add(PackRecordOwnership(company_id=1,branch_id=ctx.branch_id,context_id=ctx.id,
        resource_table=source.__tablename__,resource_key=str(source.id)))
    db.flush()
    t=AuditLog.__table__
    assert not db.connection().scalar(select(setup_predicate(t,1,ctx.branch_id)).where(t.c.id==audit.id))

@pytest.mark.parametrize('fault',['none','wrongcompany','wronguser','wrongrecipient','wrongkey','operationalmail','missingreceipt','private'])
def test_signup_outbox_exemption_has_exact_native_control_receipt(db,packs,fault):
    from app.apps.saas.models import TenantSubscription,TenantSubscriptionPlan
    from app.models.email_outbox import EmailOutbox
    from app.business_packs.models import PackRecordOwnership
    actor=packs.users['doctor'];ctx=packs.contexts['doctor']
    receipt={'company_id':1,'user_id':actor.id,'email':actor.email}
    if fault=='wrongcompany':receipt['company_id']=2
    if fault=='wronguser':receipt['user_id']=packs.users['chef'].id
    if fault=='missingreceipt':receipt={}
    plan=TenantSubscriptionPlan(code='platform-signup-7',name='Native public trial',config_json={'platform_provisioning':receipt})
    db.add(plan);db.flush();db.add(TenantSubscription(company_id=1,plan_id=plan.id))
    mail=EmailOutbox(organization_id=1,module='public_signup',event_key='signup-approved:7',recipient=actor.email,
        subject='Not inspected',body='Private token body must never be loaded')
    if fault=='wrongrecipient':mail.recipient=packs.users['chef'].email
    if fault=='wrongkey':mail.event_key='signup-approved:8'
    if fault=='operationalmail':mail.module='srm'
    db.add(mail);db.flush()
    if fault=='private':
        db.add(PackRecordOwnership(company_id=1,branch_id=ctx.branch_id,context_id=ctx.id,
            resource_table=mail.__tablename__,resource_key=str(mail.id)));db.flush()
    t=EmailOutbox.__table__
    assert bool(db.connection().scalar(select(setup_predicate(t,1,ctx.branch_id)).where(t.c.id==mail.id)))==(fault=='none')
