from uuid import uuid4
import pytest
from sqlalchemy import select
from fastapi import HTTPException
from app.apps.project_management.models import PMSProject, PMSProjectMember
from app.branches.models import BranchOwnership
from app.business_packs.models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from app.business_packs.accounting_firm.pms_sources import project_for_action
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer

@pytest.fixture
def accounts_project(db, scenario):
    actor, branch, _, _ = scenario
    activation = PackActivation(company_id=1, pack_key='accounting_firm', pack_version=1, state='active')
    db.add(activation); db.flush()
    context = PackContext(company_id=1, branch_id=branch, activation_id=activation.id,
        pack_key='accounting_firm', pack_version=1, state='active')
    db.add(context); db.flush()
    db.add(PackUserGrant(company_id=1, branch_id=branch, context_id=context.id,
        user_id=actor.id, role='engagement_manager'))
    project = PMSProject(organization_id=1, branch_id=branch, name='Private site',
        project_key=uuid4().hex[:16], manager_user_id=actor.id)
    db.add(project); db.flush()
    db.add(PackRecordOwnership(company_id=1, branch_id=branch, context_id=context.id,
        resource_table='pms_projects', resource_key=str(project.id), source='explicit-test-enrollment'))
    native = db.query(BranchOwnership).filter_by(resource_table='pms_projects', resource_key=str(project.id)).first()
    if native is None:
        db.add(BranchOwnership(company_id=1, branch_id=branch,
            resource_table='pms_projects', resource_key=str(project.id), source='explicit-test-enrollment'))
    db.commit()
    return actor, branch, context.id, project.id


def test_native_project_resource_returns_primitives_preserves_transaction_and_pack(db, accounts_project):
    actor, branch, context_id, project_id = accounts_project
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('accounting_firm').policy)
        try:
            connection = db.connection()
            transaction = connection.get_transaction()
            result = project_for_action(db, actor, project_id, 'log_time')
            assert result.id == project_id and result.name == 'Private site' and result.currency == 'INR'
            assert db.info['business_pack_scope'] is scope
            assert transaction.is_active and connection.get_transaction() is transaction
            assert not any(type(row) is PMSProject for row in db.identity_map.values())
            # The resource grants no ordinary ORM access to the private graph.
            with pytest.raises(HTTPException):
                db.query(PMSProject).all()
        finally:
            cleanup()



def test_project_resource_requires_explicit_owner_not_matching_creator(db, accounts_project):
    actor, branch, context_id, project_id = accounts_project
    foreign = PMSProject(organization_id=1, branch_id=branch, name='Same creator is insufficient',
        project_key=uuid4().hex[:16], manager_user_id=actor.id)
    db.add(foreign); db.commit(); foreign_id = foreign.id
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('accounting_firm').policy)
        try:
            with pytest.raises(HTTPException) as exc:
                project_for_action(db, actor, foreign_id)
            assert exc.value.status_code == 404
        finally:
            cleanup()

def test_project_resource_unreviewed_action_fails_closed(db, accounts_project):
    actor, branch, context_id, project_id = accounts_project
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('accounting_firm').policy)
        try:
            with pytest.raises(HTTPException) as exc:
                project_for_action(db, actor, project_id, 'administer')
            assert exc.value.status_code == 403
        finally:
            cleanup()

def test_native_authorization_resource_rejects_other_sources_and_mutation(db, accounts_project, monkeypatch):
    from app.apps.project_management import access
    from app.models.user import User
    original = access.get_project_for_action

    def inspect_resource(native, *args):
        operations = (
            lambda: native.connection().execute(select(PMSProject.__table__)),
            lambda: native.get_bind(),
            lambda: native.bind,
            lambda: native.query(PMSProject).session.connection().execute(select(PMSProject.__table__)),
            lambda: native.query(User).first(),
            lambda: native.execute(select(PMSProject.__table__)),
            lambda: native.bulk_insert_mappings(PMSProject, []),
            lambda: native.flush(),
            lambda: native.commit(),
        )
        for operation in operations:
            with pytest.raises(HTTPException) as exc:
                operation()
            assert exc.value.status_code == 403
        return original(native, *args)

    monkeypatch.setattr(access, 'get_project_for_action', inspect_resource)
    actor, branch, context_id, project_id = accounts_project
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('accounting_firm').policy)
        try:
            assert project_for_action(db, actor, project_id).id == project_id
        finally:
            cleanup()
