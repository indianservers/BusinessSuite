"""Legacy native rows remain usable; immutable pack anchors cannot be declassified."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select,update,delete,text
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import ObjectDeletedError
from app.apps.srm.models import SRMSalesOrder
from app.apps.crm.models import CRMCompany
from app.business_packs.legacy_boundary import install
from tests.test_business_pack_boundary import native,packs


def denied(call):
    with pytest.raises((HTTPException,ObjectDeletedError)) as error:call()
    if isinstance(error.value,HTTPException):assert error.value.status_code==403


def test_legacy_query_alias_count_get_and_cache_exclude_only_private(native):
    n=native;db=n.db;cached=n.cached_foreign
    cleanup=install(db,n.current_user,1)
    try:
        assert db.info.get('business_pack_scope') is None
        assert {row.id for row in db.query(SRMSalesOrder)}=={n.ids['legacy']}
        assert db.query(SRMSalesOrder).count()==1
        alias=aliased(SRMSalesOrder)
        assert {row.id for row in db.query(alias)}=={n.ids['legacy']}
        assert db.get(SRMSalesOrder,n.ids['own']) is None
        denied(lambda:db.refresh(cached))
        denied(lambda:getattr(cached,'title'))
        assert db.get(CRMCompany,n.customer_id) is not None
        legacy=db.get(SRMSalesOrder,n.ids['legacy']);legacy.title='Native legacy edit';db.commit()
        assert db.get(SRMSalesOrder,n.ids['legacy']).title=='Native legacy edit'
    finally:cleanup()
    assert db.info.get('business_pack_legacy_company') is None
    assert db.get(SRMSalesOrder,n.ids['own']) is not None


@pytest.mark.parametrize('operation',['orm_update','orm_delete','bulk_update','bulk_save','core_select','text_select'])
def test_legacy_private_write_and_raw_projection_denied(native,operation):
    n=native;db=n.db;ident=n.ids['own'];cleanup=install(db,n.current_user,1)
    try:
        if operation=='orm_update':
            assert db.execute(update(SRMSalesOrder).where(SRMSalesOrder.id==ident).values(title='FORBIDDEN')).rowcount==0
        elif operation=='orm_delete':assert db.execute(delete(SRMSalesOrder).where(SRMSalesOrder.id==ident)).rowcount==0
        elif operation=='bulk_update':denied(lambda:db.bulk_update_mappings(SRMSalesOrder,[{'id':ident,'title':'FORBIDDEN'}]))
        elif operation=='bulk_save':denied(lambda:db.bulk_save_objects([SRMSalesOrder(id=ident,organization_id=1,order_number='FORBIDDEN',title='FORBIDDEN')]))
        elif operation=='core_select':denied(lambda:db.execute(select(SRMSalesOrder.__table__.c.title)).all())
        elif operation=='text_select':denied(lambda:db.execute(text('select title from srm_sales_orders')).all())
    finally:db.rollback();cleanup()


def test_legacy_unrelated_core_and_unowned_bulk_preserve_native_behavior(native):
    n=native;cleanup=install(n.db,n.current_user,1)
    try:
        assert n.db.execute(select(CRMCompany.__table__.c.id).where(CRMCompany.id==n.customer_id)).scalar()==n.customer_id
        n.db.bulk_update_mappings(SRMSalesOrder,[{'id':n.ids['legacy'],'title':'Allowed unowned'}]);n.db.commit()
        assert n.db.get(SRMSalesOrder,n.ids['legacy']).title=='Allowed unowned'
    finally:cleanup()


@pytest.mark.parametrize('kind',['move','delete','retag','metadata'])
def test_private_branch_metadata_guard_preserves_exact_identity(native,kind):
    from app.branches.models import BranchOwnership
    from app.business_packs.legacy_boundary import protect_branch_ownership
    n=native;db=n.db
    row=BranchOwnership(resource_table='srm_sales_orders',resource_key=str(n.ids['own']),company_id=1,branch_id=n.scope.branch_id,source='test')
    db.add(row);db.commit()
    cleanup=protect_branch_ownership(db,1)
    try:
        if kind=='metadata':row.source='metadata-only';db.commit();assert row.source=='metadata-only'
        elif kind=='delete':db.delete(row);denied(db.flush)
        elif kind=='retag':row.resource_key=str(n.ids['legacy']);denied(db.flush)
        else:row.branch_id=n.p.branches['b'].id;denied(db.flush)
    finally:db.rollback();cleanup()


def test_static107_repeatable_and_raw_native_branch_owner_guard(native):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    from sqlalchemy.exc import IntegrityError
    from app.branches.models import BranchOwnership
    n=native;db=n.db;table=BranchOwnership.__table__
    path=Path(__file__).resolve().parents[1]/'alembic_postgresql/versions/pg_20261115_107_pack_branch_guard.py'
    spec=importlib.util.spec_from_file_location('pack_guard107_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    connection=db.connection();module.op=SimpleNamespace(get_bind=lambda:connection)
    module.upgrade();module.upgrade()
    key=str(n.ids['own']);condition=(table.c.resource_table=='srm_sales_orders',table.c.resource_key==key)
    connection.execute(table.insert().values(resource_table='srm_sales_orders',resource_key=key,company_id=1,branch_id=n.scope.branch_id,source='correct'))
    connection.execute(table.update().where(*condition).values(source='metadata allowed'))
    for statement in [table.update().where(*condition).values(branch_id=n.p.branches['b'].id),table.delete().where(*condition),table.update().where(*condition).values(resource_key=str(n.ids['legacy']))]:
        with pytest.raises(IntegrityError):
            with connection.begin_nested():connection.execute(statement)
    legacy=str(n.ids['legacy'])
    connection.execute(table.insert().values(resource_table='srm_sales_orders',resource_key=legacy,company_id=1,branch_id=n.scope.branch_id,source='legacy'))
    connection.execute(table.update().where(table.c.resource_key==legacy).values(branch_id=n.p.branches['b'].id))
    connection.execute(table.delete().where(table.c.resource_key==legacy))
    from app.branches.models import BranchRecordShare
    share=BranchRecordShare.__table__
    with pytest.raises(IntegrityError):
        with connection.begin_nested():connection.execute(share.insert().values(company_id=1,resource_table='srm_sales_orders',resource_key=key,branch_id=n.p.branches['b'].id))
    connection.execute(share.insert().values(company_id=1,resource_table='srm_sales_orders',resource_key=key,branch_id=n.scope.branch_id))
    with pytest.raises(IntegrityError):
        with connection.begin_nested():connection.execute(share.update().where(share.c.resource_key==key).values(branch_id=n.p.branches['b'].id))
    connection.execute(share.delete().where(share.c.resource_key==key))


def test_private_share_and_sidecar_bulk_guard_without_migration(native):
    from app.branches.models import BranchOwnership,BranchRecordShare
    from app.business_packs.legacy_boundary import protect_branch_ownership
    n=native;db=n.db
    db.add(BranchOwnership(resource_table='srm_sales_orders',resource_key=str(n.ids['own']),company_id=1,branch_id=n.scope.branch_id,source='canonical'));db.commit()
    cleanup=protect_branch_ownership(db,1)
    try:
        denied(lambda:db.bulk_update_mappings(BranchOwnership,[{'resource_table':'srm_sales_orders','resource_key':str(n.ids['own']),'branch_id':n.p.branches['b'].id}]))
        denied(lambda:db.bulk_insert_mappings(BranchRecordShare,[{'resource_table':'srm_sales_orders','resource_key':str(n.ids['own']),'company_id':1,'branch_id':n.p.branches['b'].id}]))
    finally:cleanup()


def test_absent_schema_noop_partial_schema_failclosed():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from types import SimpleNamespace
    engine=create_engine('sqlite://')
    with Session(engine) as session:
        actor=SimpleNamespace(is_active=True,organization_id=1)
        original=session.get;cleanup=install(session,actor,1);assert session.get==original;cleanup()
        session.connection().exec_driver_sql('CREATE TABLE business_pack_record_ownership(id INTEGER PRIMARY KEY)')
        with pytest.raises(HTTPException) as error:install(session,actor,1)
        assert error.value.status_code==503
    engine.dispose()


def test_no_private_anchors_preserves_native_context(packs):
    original=packs.db.get
    cleanup=install(packs.db,packs.users['doctor'],1)
    assert packs.db.get==original and packs.db.info.get('business_pack_scope') is None
    cleanup()





@pytest.mark.parametrize('kind',['raw_alias','embedded_text','literal_projection','write_subquery'])
def test_legacy_embedded_private_queries_cannot_escape(native,kind):
    from sqlalchemy import literal_column
    n=native;db=n.db;cleanup=install(db,n.current_user,1)
    try:
        if kind=='raw_alias':
            alias=SRMSalesOrder.__table__.alias('hidden_native_source')
            denied(lambda:db.execute(select(SRMSalesOrder.id,alias.c.title)).all())
        elif kind=='embedded_text':denied(lambda:db.execute(select(SRMSalesOrder).from_statement(text('select * from srm_sales_orders'))).all())
        elif kind=='literal_projection':denied(lambda:db.execute(select(CRMCompany.id,literal_column('(select title from srm_sales_orders limit 1)'))).all())
        else:denied(lambda:db.execute(update(SRMSalesOrder).where(SRMSalesOrder.id==n.ids['legacy']).values(title=select(SRMSalesOrder.title).where(SRMSalesOrder.id==n.ids['own']).scalar_subquery())))
    finally:cleanup()


def test_legacy_shared_customer_cached_relationship_does_not_expose_private_contact(native):
    from app.apps.crm.models import CRMContact
    from app.business_packs.models import PackRecordOwnership
    n=native;db=n.db
    customer=db.get(CRMCompany,n.customer_id)
    contact=CRMContact(organization_id=1,company_id=customer.id,first_name='Private contact',full_name='Private contact')
    db.add(contact);db.flush()
    db.add(PackRecordOwnership(company_id=1,branch_id=n.scope.branch_id,context_id=n.scope.context_id,resource_table='crm_contacts',resource_key=str(contact.id)));db.commit()
    assert len(customer.contacts)==1
    cleanup=install(db,n.current_user,1)
    try:assert customer.contacts==[]
    finally:cleanup()


def test_legacy_cannot_create_unowned_child_for_private_native_parent(native):
    from app.apps.srm.models import SRMSalesOrderLine
    n=native;cleanup=install(n.db,n.current_user,1)
    try:
        n.db.add(SRMSalesOrderLine(sales_order_id=n.ids['own'],description='Attempted source adoption',quantity=1))
        denied(n.db.flush)
    finally:n.db.rollback();cleanup()


@pytest.mark.parametrize('reference',['literal','bind_alias','leading_zero'])
def test_legacy_orm_bulk_update_cannot_adopt_private_parent(native,reference):
    from sqlalchemy import bindparam
    from app.apps.srm.models import SRMSalesOrderLine
    n=native
    row=SRMSalesOrderLine(sales_order_id=n.ids['legacy'],description='Unowned legacy line',quantity=1)
    n.db.add(row);n.db.commit();ident=row.id
    cleanup=install(n.db,n.current_user,1)
    try:
        statement=update(SRMSalesOrderLine).where(SRMSalesOrderLine.id==ident)
        if reference=='bind_alias':
            denied(lambda:n.db.execute(statement.values(sales_order_id=bindparam('new_private_parent')),{'new_private_parent':n.ids['own']}))
        else:
            value=n.ids['own'] if reference=='literal' else '00'+str(n.ids['own'])
            denied(lambda:n.db.execute(statement.values(sales_order_id=value)))
    finally:n.db.rollback();cleanup()
