"""Native FK validation follows nullable composites without weakening branch FKs."""
from uuid import uuid4
from contextlib import ExitStack

import pytest
from fastapi import HTTPException

from app.models.company import Branch, Company
from app.apps.srm.models import SRMProduct
from app.apps.srm.service_checkout_models import ServiceBookingPolicy
from app.business_packs.models import PackActivation, PackContext
from app.core.tenant_boundary import install as install_tenant
from sqlalchemy import Column, ForeignKeyConstraint, Integer, MetaData, Table, UniqueConstraint
from app.branches.models import BranchOwnership
from app.branches.boundary import branch_for_row
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


@pytest.mark.parametrize('case', ['legacy', 'mixed_context', 'foreign_branch'])
def test_native_optional_context_skips_null_but_checks_full_nonnull_tuple(db, scenario, case):
    user, branch, _, _ = scenario
    with native_writer(db, user, branch):
        product = SRMProduct(organization_id=1, sku=uuid4().hex, item_name='Native optional reference',
                             product_type='service', track_inventory=False)
        db.add(product); db.flush()
        product_id = product.id
    other = Branch(company_id=1, name='Different context branch')
    activation = PackActivation(company_id=1, pack_key='hospital', pack_version=1, state='draft')
    db.add_all([other, activation]); db.flush()
    context = PackContext(company_id=1, branch_id=other.id, activation_id=activation.id,
                          pack_key='hospital', pack_version=1, state='draft')
    db.add(context)
    selected_branch = branch
    if case == 'foreign_branch':
        foreign_company = Company(id=987654, name='Foreign nullable reference company')
        db.add(foreign_company); db.flush()
        foreign_branch = Branch(company_id=foreign_company.id, name='Foreign native branch')
        db.add(foreign_branch); db.flush()
        selected_branch = foreign_branch.id
    db.commit()
    with ExitStack() as stack:
        stack.callback(install_tenant(db, user, 1, enforce_superuser_company=True))
        stack.enter_context(native_writer(db, user, branch))
        policy = ServiceBookingPolicy(organization_id=1, branch_id=selected_branch,
            pack_context_id=context.id if case == 'mixed_context' else None, service_product_id=product_id,
            default_duration_minutes=30, min_duration_minutes=5, max_duration_minutes=120)
        db.add(policy)
        if case == 'legacy':
            db.flush()
            assert policy.id > 0 and policy.pack_context_id is None
        else:
            with pytest.raises(HTTPException) as error:
                db.flush()
            assert error.value.status_code == 403
            assert error.value.detail == 'Resource is outside the authorized company or writable scope'


def test_branch_reference_uses_complete_composite_tuple(db, scenario):
    _, branch_a, _, _ = scenario
    other = Branch(company_id=1, name='Second exact source branch')
    db.add(other); db.flush()
    branch_b = other.id
    metadata = MetaData()
    parent = Table('test_composite_parent_' + uuid4().hex[:12], metadata,
        Column('id', Integer, primary_key=True), Column('organization_id', Integer),
        Column('branch_id', Integer), Column('scope_context_key', Integer),
        UniqueConstraint('id', 'organization_id', 'branch_id', 'scope_context_key'))
    child = Table('test_composite_child_' + uuid4().hex[:12], metadata,
        Column('id', Integer, primary_key=True), Column('parent_id', Integer),
        Column('organization_id', Integer), Column('branch_id', Integer), Column('scope_context_key', Integer),
        ForeignKeyConstraint(['parent_id', 'organization_id', 'branch_id', 'scope_context_key'],
            [parent.c.id, parent.c.organization_id, parent.c.branch_id, parent.c.scope_context_key]))
    connection = db.connection()
    metadata.create_all(connection)
    try:
        connection.execute(parent.insert(), [
            {'id': 1, 'organization_id': 1, 'branch_id': branch_a, 'scope_context_key': 0},
            {'id': 2, 'organization_id': 1, 'branch_id': branch_b, 'scope_context_key': 0}])
        connection.execute(BranchOwnership.__table__.insert(), [
            {'resource_table': parent.name, 'resource_key': str(identity), 'company_id': 1,
             'branch_id': branch, 'source': 'composite-proof'} for identity, branch in [(1, branch_a), (2, branch_b)]])
        values = {'id': 1, 'parent_id': 2, 'organization_id': 1, 'branch_id': branch_b, 'scope_context_key': 0}
        cache = {}
        assert branch_for_row(connection, child, values, 1, metadata.tables, owner_cache=cache) == {branch_b}
        with pytest.raises(HTTPException):
            branch_for_row(connection, child, {**values, 'branch_id': branch_a}, 1, metadata.tables, owner_cache=cache)
        assert branch_for_row(connection, child, {**values, 'parent_id': None}, 1, metadata.tables, owner_cache=cache) == {branch_b}
    finally:
        metadata.drop_all(connection)
