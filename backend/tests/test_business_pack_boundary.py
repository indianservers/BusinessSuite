"""Audited native-table primitives; this is not a claim of full graph coverage."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, ForeignKeyConstraint, Integer, String, delete, insert, literal_column, select, text, update
from sqlalchemy.orm import DeclarativeBase, aliased

from tests.test_business_pack_access import packs  # native company/branch/grant fixture
from app.business_packs.access import resolve_context
from app.business_packs.boundary import PackBoundaryPolicy, PackNativeLink, install
from app.business_packs.models import PackMasterAvailability, PackRecordOwnership, PackUserGrant
from app.apps.crm.models import CRMCompany, CRMLead
from app.apps.srm.models import SRMProduct, SRMSalesOrder, SRMSalesOrderLine
from app.models.user import Role, User
from app.branches.catalog import resource_key


POLICY = PackBoundaryPolicy(
    record_tables=frozenset({'srm_sales_orders', 'srm_sales_order_lines'}),
    master_tables=frozenset({'crm_companies', 'srm_products'}),
    native_links=(
        PackNativeLink('srm_sales_orders', 'crm_company_id', 'crm_companies'),
        PackNativeLink('srm_sales_order_lines', 'product_id', 'srm_products'),
    ),
)


def test_mixed_orm_raw_columns_and_text_cannot_escape_loader_criteria(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        raw = SRMSalesOrder.__table__.alias('raw_orders')
        forbidden(lambda: n.db.execute(select(SRMSalesOrder.id, raw.c.title)).all())
        forbidden(lambda: n.db.execute(select(SRMSalesOrder.id, text('(select title from srm_sales_orders limit 1)'))).all())
        forbidden(lambda: n.db.execute(select(SRMSalesOrder.id, literal_column('(select title from srm_sales_orders limit 1)'))).all())
    finally:
        cleanup()


def test_scope_cannot_forge_registry_capabilities_or_version(native):
    n = native
    forbidden(lambda: install(n.db, replace(n.scope, capabilities=frozenset({'hospital.all.records'})), policy=POLICY))
    forbidden(lambda: install(n.db, replace(n.scope, pack_version=99), policy=POLICY))


@pytest.fixture
def native(packs):
    p, db = packs, packs.db
    scope = resolve_context(db, p.users['doctor'], p.ctx())
    foreign_scope = resolve_context(db, p.users['chef'], p.ctx(), p.contexts['chef'].id)
    customer = CRMCompany(organization_id=1, branch_id=p.branches['a'].id, name='Explicit shared customer')
    products = {key: SRMProduct(organization_id=1, sku='PACK-' + key, item_name=key, product_type='service') for key in ('own', 'foreign', 'shared')}
    db.add_all([customer, *products.values()]); db.flush()
    orders = {key: SRMSalesOrder(organization_id=1, order_number='PACK-' + key, title=key, crm_company_id=customer.id, created_by=p.users['doctor'].id) for key in ('own', 'foreign', 'legacy')}
    db.add_all(orders.values()); db.flush()
    lines = {key: SRMSalesOrderLine(sales_order_id=orders[key].id, product_id=products['shared'].id, description=key, quantity=1) for key in ('own', 'foreign')}
    db.add_all(lines.values())
    unknown = CRMLead(organization_id=1, first_name='Unknown graph', full_name='Unknown graph secret')
    db.add(unknown); db.flush()
    for key, selected in [('own', scope), ('foreign', foreign_scope)]:
        for row in (orders[key], lines[key]):
            db.add(PackRecordOwnership(company_id=1, branch_id=selected.branch_id, context_id=selected.context_id, resource_table=row.__tablename__, resource_key=str(row.id)))
        for row in (customer, products[key], products['shared']):
            db.add(PackMasterAvailability(company_id=1, branch_id=selected.branch_id, context_id=selected.context_id, resource_table=row.__tablename__, resource_key=str(row.id)))
    db.commit()
    ids = {key: row.id for key, row in orders.items()}
    product_ids = {key: row.id for key, row in products.items()}
    return SimpleNamespace(db=db, p=p, scope=scope, foreign_scope=foreign_scope, ids=ids, product_ids=product_ids,
                           lines={key: row.id for key, row in lines.items()}, customer_id=customer.id, unknown_id=unknown.id,
                           cached_foreign=orders['foreign'], cached_foreign_user=p.users['chef'], current_user=p.users['doctor'])


def forbidden(operation):
    with pytest.raises(HTTPException) as error:
        operation()
    assert error.value.status_code == 403


def test_legacy_scope_installs_no_new_guard(native):
    n = native
    cleanup = install(n.db, None)
    assert {row.id for row in n.db.query(SRMSalesOrder)} == set(n.ids.values())
    cleanup()


def test_request_binding_then_record_boundary_preserves_outer_scope(native):
    n = native
    n.db.info['business_pack_scope'] = n.scope
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        assert {row.id for row in n.db.query(SRMSalesOrder)} == {n.ids['own']}
        nested = install(n.db, n.scope, policy=POLICY)
        nested()
        assert n.db.info['business_pack_policy'] == POLICY
        forbidden(lambda: install(n.db, n.foreign_scope, policy=POLICY))
    finally:
        cleanup()
    assert n.db.info['business_pack_scope'] == n.scope
    assert 'business_pack_policy' not in n.db.info
    assert {row.id for row in n.db.query(SRMSalesOrder)} == set(n.ids.values())


def test_bound_legacy_namespace_cannot_be_replaced_by_record_install(native):
    n = native
    n.db.info['business_pack_scope'] = None
    forbidden(lambda: install(n.db, n.scope, policy=POLICY))
    assert n.db.info['business_pack_scope'] is None
    install(n.db, None)()
    assert n.db.info['business_pack_scope'] is None


def test_bound_control_references_are_exact_and_read_only(native):
    from app.business_packs.models import PackContext, PackActivation
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        assert [row.id for row in n.db.query(PackContext)] == [n.scope.context_id]
        assert [row.id for row in n.db.query(PackActivation)] == [n.scope.activation_id]
        assert [row.id for row in n.db.query(PackUserGrant)] == [n.scope.grant_id]
        assert all(row.context_id == n.scope.context_id for row in n.db.query(PackMasterAvailability))
        assert all(row.context_id == n.scope.context_id for row in n.db.query(PackRecordOwnership))
        assert n.db.get(PackContext, n.foreign_scope.context_id) is None
        with pytest.raises(HTTPException) as error, n.db.begin_nested():
            own = n.db.get(PackUserGrant, n.scope.grant_id)
            own.active = False
            n.db.flush()
        assert error.value.status_code == 403
    finally:
        cleanup()


def test_exact_anchors_filter_query_get_column_projection_and_alias(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        assert [row.id for row in n.db.query(SRMSalesOrder)] == [n.ids['own']]
        assert n.db.get(SRMSalesOrder, n.ids['foreign']) is None
        assert n.db.get(SRMSalesOrder, n.ids['legacy']) is None
        assert n.db.execute(select(SRMSalesOrder.title)).scalars().all() == ['own']
        alias = aliased(SRMSalesOrder)
        assert n.db.execute(select(alias)).scalars().one().id == n.ids['own']
    finally:
        cleanup()


def test_native_orm_counts_are_scoped_and_raw_count_sources_remain_blocked(native):
    from sqlalchemy import func
    n = native; cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        assert n.db.query(SRMSalesOrder).count() == 1
        assert n.db.query(SRMSalesOrder).filter_by(id=n.ids['foreign']).count() == 0
        assert n.db.query(aliased(SRMSalesOrder)).count() == 1
        raw = SRMSalesOrder.__table__.alias('unscoped_orders')
        forbidden(lambda: n.db.query(SRMSalesOrder).select_from(raw).count())
        forbidden(lambda: n.db.query(func.count()).select_from(SRMSalesOrder.__table__).scalar())
        forbidden(lambda: n.db.query(literal_column('count(*)')).select_from(SRMSalesOrder).scalar())
    finally:
        cleanup()


def test_cached_foreign_record_and_identity_cannot_expose_loaded_fields(native):
    n = native
    assert n.cached_foreign.title == 'foreign'
    assert n.cached_foreign_user.email
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        forbidden(lambda: n.cached_foreign.title)
        forbidden(lambda: n.cached_foreign_user.email)
        assert n.current_user.id == n.scope.user_id
        forbidden(lambda: n.db.refresh(n.cached_foreign))
    finally:
        cleanup()


def test_native_relationship_loader_filters_child_anchors(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        own = n.db.get(SRMSalesOrder, n.ids['own'])
        assert [row.id for row in own.lines] == [n.lines['own']]
        assert n.db.get(SRMSalesOrderLine, n.lines['foreign']) is None
    finally:
        cleanup()


def test_unknown_tables_fail_closed_and_shared_customer_does_not_imply_order_ownership(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        assert n.db.get(CRMCompany, n.customer_id) is not None
        assert n.db.get(SRMSalesOrder, n.ids['legacy']) is None
        assert n.db.get(CRMLead, n.unknown_id) is None
        forbidden(lambda: n.db.query(CRMLead).all())
    finally:
        cleanup()


def test_master_availability_is_explicit_per_context(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        assert {row.id for row in n.db.query(SRMProduct)} == {n.product_ids['own'], n.product_ids['shared']}
        assert n.db.get(SRMProduct, n.product_ids['foreign']) is None
    finally:
        cleanup()


def test_new_native_aggregate_gets_individual_atomic_anchors(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        order = SRMSalesOrder(order_number='PACK-new', title='new', crm_company_id=n.customer_id, created_by=n.scope.user_id)
        order.lines.append(SRMSalesOrderLine(description='child', product_id=n.product_ids['own'], quantity=1))
        n.db.add(order); n.db.commit()
        child_id = order.lines[0].id
        assert order.organization_id == n.scope.company_id
        rows = n.db.connection().execute(select(PackRecordOwnership.__table__).where(
            PackRecordOwnership.resource_table.in_(['srm_sales_orders', 'srm_sales_order_lines']),
            PackRecordOwnership.resource_key.in_([str(order.id), str(child_id)]),
            PackRecordOwnership.context_id == n.scope.context_id,
        )).mappings().all()
        assert ('srm_sales_orders', str(order.id)) in {(row['resource_table'], row['resource_key']) for row in rows}
        assert ('srm_sales_order_lines', str(child_id)) in {(row['resource_table'], row['resource_key']) for row in rows}
    finally:
        cleanup()


def test_new_master_is_available_only_in_creator_context(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        product = SRMProduct(sku='NEW-PACK-MASTER', item_name='New master')
        n.db.add(product); n.db.commit()
        identity = product.id
        rows = n.db.connection().execute(select(PackMasterAvailability.__table__).where(
            PackMasterAvailability.resource_table == 'srm_products', PackMasterAvailability.resource_key == str(identity),
        )).mappings().all()
        assert len(rows) == 1 and rows[0]['context_id'] == n.scope.context_id
        assert n.db.connection().execute(select(PackRecordOwnership.id).where(
            PackRecordOwnership.resource_table == 'srm_products', PackRecordOwnership.resource_key == str(identity),
        )).first() is None
    finally:
        cleanup()


def test_foreign_parent_in_new_aggregate_rolls_back_source_and_anchors(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        order = SRMSalesOrder(order_number='PACK-atomic-failure', title='atomic failure', created_by=n.scope.user_id)
        order.lines.append(SRMSalesOrderLine(description='wrong product', product_id=n.product_ids['foreign'], quantity=1))
        n.db.add(order)
        forbidden(n.db.commit)
        n.db.rollback()
        assert n.db.query(SRMSalesOrder).filter_by(order_number='PACK-atomic-failure').first() is None
    finally:
        cleanup()


def test_owned_update_allowed_but_non_fk_foreign_reference_rejected(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        order = n.db.get(SRMSalesOrder, n.ids['own'])
        order.title = 'updated own'; n.db.commit()
        assert n.db.get(SRMSalesOrder, order.id).title == 'updated own'
        line = n.db.get(SRMSalesOrderLine, n.lines['own'])
        line.product_id = n.product_ids['foreign']
        forbidden(n.db.commit)
    finally:
        n.db.rollback(); cleanup()


def test_composite_parent_keys_cannot_form_a_cross_context_product(native, monkeypatch):
    from app.business_packs import boundary
    n = native
    class LocalBase(DeclarativeBase):
        pass
    class Master(LocalBase):
        __tablename__ = 'pack_boundary_test_masters'
        code = Column(String(10), primary_key=True)
        edition = Column(Integer, primary_key=True)
        company_id = Column(Integer, nullable=False)
    class Child(LocalBase):
        __tablename__ = 'pack_boundary_test_children'
        __table_args__ = (ForeignKeyConstraint(['code', 'edition'], ['pack_boundary_test_masters.code', 'pack_boundary_test_masters.edition']),)
        id = Column(Integer, primary_key=True)
        organization_id = Column(Integer)
        code = Column(String(10), nullable=False)
        edition = Column(Integer, nullable=False)
    LocalBase.metadata.create_all(n.db.connection())
    n.db.connection().execute(Master.__table__.insert(), [
        {'code': 'A', 'edition': 1, 'company_id': 1}, {'code': 'B', 'edition': 2, 'company_id': 1}, {'code': 'A', 'edition': 2, 'company_id': 1},
    ])
    for code, edition, scope in [('A', 1, n.scope), ('B', 2, n.scope), ('A', 2, n.foreign_scope)]:
        n.db.add(PackMasterAvailability(company_id=1, branch_id=scope.branch_id, context_id=scope.context_id,
            resource_table=Master.__tablename__, resource_key=resource_key(Master.__table__, {'code': code, 'edition': edition})))
    n.db.commit()
    # Test-only registry; never register synthetic tables in the app's Base.
    monkeypatch.setattr(boundary, 'Base', LocalBase)
    policy = PackBoundaryPolicy(record_tables=frozenset({Child.__tablename__}), master_tables=frozenset({Master.__tablename__}), read_only_tables=frozenset())
    cleanup = install(n.db, n.scope, policy=policy)
    try:
        n.db.add(Child(code='A', edition=2))
        forbidden(n.db.commit)
        n.db.rollback()
        n.db.add(Child(code='B', edition=2)); n.db.commit()
        assert [(row.code, row.edition) for row in n.db.query(Child)] == [('B', 2)]
    finally:
        cleanup()


def test_new_record_cannot_spoof_another_contexts_creator(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        n.db.add(SRMSalesOrder(order_number='WRONG-CREATOR', title='wrong creator', created_by=n.foreign_scope.user_id))
        forbidden(n.db.commit)
    finally:
        n.db.rollback(); cleanup()


@pytest.mark.parametrize('change', ['company', 'primary_key'])
def test_native_source_identity_cannot_be_retagged(native, change):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        row = n.db.get(SRMSalesOrder, n.ids['own'])
        if change == 'company':
            row.organization_id = 2
        else:
            row.id = 2000000000
        forbidden(n.db.commit)
    finally:
        n.db.rollback(); cleanup()


def test_owned_deletion_keeps_immutable_lineage_anchor(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        row = n.db.get(SRMSalesOrderLine, n.lines['own'])
        n.db.delete(row); n.db.commit()
        assert n.db.connection().execute(select(PackRecordOwnership.id).where(
            PackRecordOwnership.resource_table == 'srm_sales_order_lines', PackRecordOwnership.resource_key == str(n.lines['own']),
        )).first() is not None
    finally:
        cleanup()


def test_foreign_cached_record_cannot_be_deleted(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        def remove():
            n.db.delete(n.cached_foreign)
            n.db.commit()
        forbidden(remove)
    finally:
        n.db.rollback(); cleanup()


def test_unknown_table_writes_and_global_definition_writes_fail_closed(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        n.db.add(CRMLead(organization_id=1, first_name='Unknown write'))
        forbidden(n.db.commit)
        n.db.rollback()
        role = n.db.query(Role).first()
        role.name = 'cannot elevate through pack'
        forbidden(n.db.commit)
    finally:
        n.db.rollback(); cleanup()


@pytest.mark.parametrize('statement', [
    lambda: select(SRMSalesOrder.__table__),
    lambda: text('SELECT * FROM srm_sales_orders'),
    lambda: update(SRMSalesOrder).values(title='bulk mutation'),
    lambda: delete(SRMSalesOrder),
    lambda: insert(SRMSalesOrder).values(title='bulk insert', order_number='BULK'),
    lambda: select(SRMSalesOrder).union_all(select(SRMSalesOrder)),
])
def test_session_core_and_orm_bulk_cannot_bypass_native_validation(native, statement):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        forbidden(lambda: n.db.execute(statement()))
    finally:
        cleanup()


@pytest.mark.parametrize('method', ['bulk_insert_mappings', 'bulk_update_mappings', 'bulk_save_objects'])
def test_legacy_bulk_mapping_methods_cannot_bypass_pack_scope(native, method):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        forbidden(lambda: getattr(n.db, method)(SRMSalesOrder, []))
    finally:
        cleanup()


def test_readonly_scope_can_read_but_not_write(native):
    n = native
    cleanup = install(n.db, replace(n.scope, writable=False), policy=POLICY)
    try:
        row = n.db.get(SRMSalesOrder, n.ids['own'])
        assert row is not None
        row.title = 'forbidden readonly edit'
        forbidden(n.db.commit)
    finally:
        n.db.rollback(); cleanup()


def test_revoked_grant_invalidates_previously_resolved_scope(native):
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        # A trusted control-plane change is observed even by a cached scope.
        n.db.connection().execute(PackUserGrant.__table__.update().where(PackUserGrant.id == n.scope.grant_id).values(active=False, revision=2))
        forbidden(lambda: n.db.query(SRMSalesOrder).all())
        forbidden(lambda: n.db.get(SRMSalesOrder, n.ids['own']))
    finally:
        n.db.rollback(); cleanup()


def test_context_cannot_change_mid_session_and_cleanup_restores_existing_methods(native):
    n = native
    original_get = n.db.get
    cleanup = install(n.db, n.scope, policy=POLICY)
    forbidden(lambda: install(n.db, n.foreign_scope, policy=POLICY))
    forbidden(lambda: install(n.db, None))
    cleanup(); cleanup()
    assert n.db.get == original_get
    assert 'business_pack_scope' not in n.db.info
    assert n.db.get(SRMSalesOrder, n.ids['foreign']) is not None


def test_binding_rejects_pending_changes_instead_of_discarding_them(native):
    n = native
    row = n.db.get(SRMSalesOrder, n.ids['own'])
    row.title = 'unsaved before binding'
    forbidden(lambda: install(n.db, n.scope, policy=POLICY))
    assert row.title == 'unsaved before binding'


@pytest.mark.parametrize('values', [
    {'record_tables': frozenset({'srm_sales_orders'}), 'master_tables': frozenset({'srm_sales_orders'})},
    {'record_tables': frozenset({'users'}), 'master_tables': frozenset()},
    {'record_tables': frozenset(), 'master_tables': frozenset(), 'read_only_tables': frozenset({'srm_sales_orders'})},
])
def test_audited_policy_cannot_classify_private_records_as_global_or_identity_sources(values):
    with pytest.raises(ValueError):
        PackBoundaryPolicy(**values)

@pytest.mark.parametrize('shape', ['mixed', 'alias', 'count', 'join', 'nested'])
def test_late_mapper_secondary_sources_fail_closed(native, shape):
    from sqlalchemy import func, true
    from sqlalchemy.orm import registry
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    late = registry()
    class LateLead: pass
    late.map_imperatively(LateLead, CRMLead.__table__)
    try:
        alias = aliased(LateLead)
        statement = {
            'mixed': select(SRMSalesOrder, LateLead),
            'alias': select(SRMSalesOrder, alias),
            'count': select(func.count()).select_from(select(SRMSalesOrder, alias).subquery()),
            'join': select(SRMSalesOrder).join(LateLead, true()),
            'nested': select(SRMSalesOrder).where(select(LateLead.id).exists()),
        }[shape]
        forbidden(lambda: n.db.execute(statement).all())
        assert [row.id for row in n.db.query(SRMSalesOrder)] == [n.ids['own']]
    finally:
        cleanup()
        late.dispose()


def test_alternate_mapper_over_allowed_table_cannot_borrow_pack_authority(native):
    from sqlalchemy.orm import registry
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    late = registry()
    class AlternateOrder: pass
    late.map_imperatively(AlternateOrder, SRMSalesOrder.__table__)
    try:
        forbidden(lambda: n.db.execute(select(SRMSalesOrder, AlternateOrder)).all())
        forbidden(lambda: n.db.execute(select(SRMSalesOrder, aliased(AlternateOrder))).all())
    finally:
        cleanup()
        late.dispose()


def test_eager_relationship_cannot_import_unknown_native_source(native):
    from sqlalchemy.orm import joinedload
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    try:
        forbidden(lambda: n.db.execute(select(User).options(joinedload(User.employee))).all())
    finally:
        cleanup()


def test_default_eager_relationship_cannot_borrow_primary_mapper_scope(native):
    from sqlalchemy import inspect
    n = native
    cleanup = install(n.db, n.scope, policy=POLICY)
    relationship = inspect(User).relationships['employee']
    previous = relationship.lazy
    try:
        relationship.lazy = 'joined'
        forbidden(lambda: n.db.execute(select(User)).all())
    finally:
        relationship.lazy = previous
        cleanup()



def test_alternate_cached_identity_and_writes_never_borrow_table_policy(native):
    from sqlalchemy.orm import registry
    n=native;alternate=registry()
    class AlternateOrder:pass
    alternate.map_imperatively(AlternateOrder,SRMSalesOrder.__table__)
    cached=n.db.query(AlternateOrder).filter_by(id=n.ids['own']).one()
    assert cached.title=='own'
    cleanup=install(n.db,n.scope,policy=POLICY)
    try:
        forbidden(lambda:getattr(cached,'title'))
        assert n.db.get(AlternateOrder,n.ids['own']) is None
        forbidden(lambda:n.db.refresh(cached))
        with pytest.raises(HTTPException) as error,n.db.begin_nested():
            n.db.add(AlternateOrder(organization_id=1,order_number='ALTERNATE-NOT-AUTHORIZED',title='No alternate write'))
            n.db.flush()
        assert error.value.status_code==403
        assert [row.id for row in n.db.query(SRMSalesOrder)]==[n.ids['own']]
    finally:cleanup();alternate.dispose()
