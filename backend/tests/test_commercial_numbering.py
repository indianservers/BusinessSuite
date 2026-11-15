"""Canonical native company number counters do not depend on visible pack rows."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select,update
from app.apps.srm.models import SRMSalesOrder,SRMReceipt,SRMInventoryMovement
from app.apps.srm.services.commercial_numbering import reserve_number,SERIES
from app.apps.srm.commercial_models import CommercialNumberSequence
from app.business_packs.legacy_boundary import install
from tests.test_business_pack_boundary import native,packs


def reserve(n,model=SRMSalesOrder,prefix='SO',column='order_number',company=1):
    return reserve_number(n.db,model,prefix,column,company,actor=n.current_user)


def test_hidden_and_legacy_null_manual_numbers_are_reconciled_even_after_bootstrap(native):
    n=native;table=SRMSalesOrder.__table__
    n.db.connection().execute(table.update().where(table.c.id==n.ids['own']).values(order_number='SO-000550'))
    n.db.add(SRMSalesOrder(organization_id=None,order_number='SO-000700',title='Historical null organization'))
    n.db.commit()
    cleanup=install(n.db,n.current_user,1)
    try:
        assert reserve(n)=='SO-000701'
        n.db.connection().execute(table.update().where(table.c.id==n.ids['foreign']).values(order_number='SO-009999'))
        assert reserve(n)=='SO-010000'
        assert reserve(n)=='SO-010001'
    finally:cleanup()


def test_reservations_before_flush_pending_manual_number_and_outer_rollback(native):
    n=native
    assert reserve(n)=='SO-000001'
    assert reserve(n)=='SO-000002'
    n.db.add(SRMSalesOrder(organization_id=1,order_number='SO-MANUAL-002000',title='Pending native manual number'))
    assert reserve(n)=='SO-002001'
    n.db.flush()
    with pytest.raises(RuntimeError):
        with n.db.begin_nested():
            assert reserve(n)=='SO-002002'
            raise RuntimeError('Outer operation rolled back')
    assert reserve(n)=='SO-002002'


def test_closed_series_rejects_arbitrary_model_column_prefix_and_foreign_actor(native):
    n=native
    for model,prefix,column,company in [(SRMSalesOrder,'RCT','order_number',1),(SRMSalesOrder,'SO','title',1),(SRMSalesOrder,'SO','order_number',2),(SRMSalesOrder,'SO','order_number',0)]:
        with pytest.raises(HTTPException) as error:reserve(n,model,prefix,column,company)
        assert error.value.status_code in (403,422)
    assert len(SERIES)==14
    with pytest.raises(TypeError):SERIES[(SRMReceipt,'receipt_number','FAKE')]=None


def test_company_scope_and_native_revocation_are_fresh(native):
    from app.models.user import User
    n=native
    n.db.connection().execute(User.__table__.update().where(User.id==n.current_user.id).values(is_active=False))
    with pytest.raises(HTTPException) as error:reserve(n)
    assert error.value.status_code==403


def test_transfer_reference_series_uses_actual_reference_storage(native):
    n=native
    # Use a pending native movement: no ledger write is needed merely to reserve
    # two transfer references before the paired INV movement rows are flushed.
    movement=SRMInventoryMovement(organization_id=1,movement_number='INV-000010',reference_number='TRF-000075')
    n.db.add(movement)
    assert reserve(n,SRMInventoryMovement,'TRF','movement_number')=='TRF-000076'
    assert reserve(n,SRMInventoryMovement,'TRF','movement_number')=='TRF-000077'
    n.db.expunge(movement)


@pytest.mark.parametrize('commit_first',[True,False])
def test_postgres_company_counter_serializes_concurrent_writers_and_rollback(db_engine,commit_first):
    if db_engine.dialect.name!='postgresql':pytest.skip('PostgreSQL transaction lock proof')
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from sqlalchemy.orm import Session
    from app.models.company import Company
    from app.models.user import User,Role
    from app.access.models import AccessMembership
    assert db_engine.url.database.startswith('business_suite_') and db_engine.url.database.endswith('_test')
    with Session(db_engine) as session:
        company=Company(name='Owned numbering concurrency');role=Role(name='number-'+uuid4().hex)
        session.add_all([company,role]);session.flush()
        user=User(email=uuid4().hex+'@example.invalid',hashed_password='not-a-login',role_id=role.id,is_active=True,is_superuser=False)
        session.add(user);session.flush();session.add(AccessMembership(user_id=user.id,company_id=company.id,active=True));session.commit()
        company_id,user_id,role_id=company.id,user.id,role.id
    acquired,release,second_entered=Event(),Event(),Event()
    def worker(first):
        with Session(db_engine) as session:
            actor=session.get(User,user_id);actor.organization_id=company_id
            if not first:second_entered.set()
            number=reserve_number(session,SRMSalesOrder,'SO','order_number',company_id,actor=actor)
            if first:
                acquired.set();assert release.wait(10)
                session.commit() if commit_first else session.rollback()
            else:session.commit()
            return number
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(worker,True);assert acquired.wait(10)
            second=pool.submit(worker,False);assert second_entered.wait(10)
            assert not second.done()
            release.set();numbers=[first.result(timeout=15),second.result(timeout=15)]
        assert numbers==['SO-000001','SO-000002' if commit_first else 'SO-000001']
    finally:
        release.set()
        with db_engine.begin() as connection:
            connection.execute(CommercialNumberSequence.__table__.delete().where(CommercialNumberSequence.series.like(f'srm_company:{company_id}:%')))
            connection.execute(AccessMembership.__table__.delete().where(AccessMembership.user_id==user_id))
            connection.execute(User.__table__.delete().where(User.id==user_id))
            connection.execute(Role.__table__.delete().where(Role.id==role_id))
            connection.execute(Company.__table__.delete().where(Company.id==company_id))


def test_number_authority_rechecks_native_branch_after_waiting_for_writer(native,monkeypatch):
    import app.core.company_writer as writers
    from app.branches.models import BranchGrant
    from app.branches.service import context
    n=native;branch=n.p.branches['a'].id
    n.db.add(BranchGrant(company_id=1,branch_id=branch,user_id=n.current_user.id,can_write=True));n.db.commit()
    n.db.info['branch_context']=context(n.db,n.current_user,1,str(branch))
    original=writers.lock_company_writer
    def revoke_after_lock(db,company):
        original(db,company)
        db.connection().execute(BranchGrant.__table__.delete().where(BranchGrant.user_id==n.current_user.id,BranchGrant.branch_id==branch))
    monkeypatch.setattr(writers,'lock_company_writer',revoke_after_lock)
    try:
        with pytest.raises(HTTPException) as error:reserve(n)
        assert error.value.status_code==403
    finally:n.db.info.pop('branch_context',None)


def test_number_authority_rechecks_native_policy_after_writer_wait(native,monkeypatch):
    import app.core.company_writer as writers
    from app.access.models import AccessPolicy
    n=native
    n.db.add(AccessPolicy(company_id=1,user_id=n.current_user.id,status='active',grants={}));n.db.commit()
    original=writers.lock_company_writer
    def revoke_after_lock(db,company):
        original(db,company)
        db.connection().execute(AccessPolicy.__table__.update().where(AccessPolicy.user_id==n.current_user.id).values(status='suspended'))
    monkeypatch.setattr(writers,'lock_company_writer',revoke_after_lock)
    with pytest.raises(HTTPException) as error:reserve(n)
    assert error.value.status_code==403


def test_native_branch_composite_parent_requires_one_complete_matching_tuple(native):
    from sqlalchemy import MetaData,Table,Column,Integer,UniqueConstraint,ForeignKeyConstraint
    from app.branches.models import BranchOwnership
    from app.branches.boundary import branch_for_row
    n=native;connection=n.db.connection();metadata=MetaData()
    parent=Table('number_test_composite_parent',metadata,Column('id',Integer,primary_key=True),Column('company_id',Integer),Column('branch_id',Integer),Column('scope_key',Integer),UniqueConstraint('id','company_id','branch_id','scope_key'))
    child=Table('number_test_composite_child',metadata,Column('id',Integer,primary_key=True),Column('parent_id',Integer),Column('company_id',Integer),Column('branch_id',Integer),Column('scope_key',Integer),ForeignKeyConstraint(['parent_id','company_id','branch_id','scope_key'],['number_test_composite_parent.id','number_test_composite_parent.company_id','number_test_composite_parent.branch_id','number_test_composite_parent.scope_key']))
    metadata.create_all(connection)
    a,b=n.p.branches['a'].id,n.p.branches['b'].id
    connection.execute(parent.insert(),[{'id':1,'company_id':1,'branch_id':a,'scope_key':0},{'id':2,'company_id':1,'branch_id':b,'scope_key':0},{'id':3,'company_id':1,'branch_id':a,'scope_key':7}])
    for ident,branch in [(1,a),(2,b),(3,a)]:connection.execute(BranchOwnership.__table__.insert().values(resource_table=parent.name,resource_key=str(ident),company_id=1,branch_id=branch,source='test-known-parent'))
    tables={parent.name:parent,child.name:child}
    try:
        assert branch_for_row(connection,child,{'id':1,'parent_id':1,'company_id':1,'branch_id':a,'scope_key':0},1,tables,a)=={a}
        assert branch_for_row(connection,child,{'id':2,'parent_id':2,'company_id':1,'branch_id':b,'scope_key':0},1,tables,b)=={b}
        # Every component exists somewhere, but this complete parent tuple does
        # not. Independent component lookups must never establish branch proof.
        with pytest.raises(HTTPException) as error:branch_for_row(connection,child,{'id':2,'parent_id':1,'company_id':1,'branch_id':b,'scope_key':0},1,tables,b)
        assert error.value.status_code==403
        with pytest.raises(HTTPException) as error:branch_for_row(connection,child,{'id':3,'parent_id':1,'company_id':1,'branch_id':a,'scope_key':7},1,tables,a)
        assert error.value.status_code==403
    finally:metadata.drop_all(connection)
