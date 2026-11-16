"""Retained native onboarding rows participate in cutover; no old schema adoption."""
from contextlib import contextmanager
from datetime import date
from uuid import uuid4
import pytest
from sqlalchemy import inspect,insert,select,String,ForeignKeyConstraint
from app.business_packs.first_activation import reasons,RECONCILE
from app.business_packs.legacy_cutover import _descriptors,legacy_tables
from app.models.company import Company,Branch
from app.db.base_class import Base

@contextmanager
def legacy_schema(db,fault=None):
    connection=db.connection();tables=_descriptors();inspector=inspect(connection)
    present={name for name in tables if inspector.has_table(name)}
    created=not present
    if created:
        if fault=='type':tables['onboarding_tasks'].c.category.type=String(49)
        if fault=='fk':
            from app.models.user import User
            task=tables['onboarding_tasks']
            constraint=next(key.constraint for key in task.c.template_id.foreign_keys)
            task.constraints.remove(constraint)
            task.append_constraint(ForeignKeyConstraint(['template_id'],[User.__table__.c.id],ondelete='CASCADE'))
        tables['onboarding_tasks'].create(connection)
        if fault!='partial':tables['onboarding_task_completions'].create(connection)
    elif fault=='type':connection.exec_driver_sql('ALTER TABLE onboarding_tasks ALTER COLUMN category TYPE VARCHAR(49)')
    elif fault=='fk':
        key=next(key for key in inspector.get_foreign_keys('onboarding_tasks') if key['constrained_columns']==['template_id'])
        quoted=connection.dialect.identifier_preparer.quote_identifier(key['name'])
        connection.exec_driver_sql('ALTER TABLE onboarding_tasks DROP CONSTRAINT '+quoted)
        connection.exec_driver_sql('ALTER TABLE onboarding_tasks ADD FOREIGN KEY (template_id) REFERENCES users(id) ON DELETE CASCADE')
    elif fault=='partial':tables['onboarding_task_completions'].drop(connection)
    if fault=='column':connection.exec_driver_sql('ALTER TABLE onboarding_tasks DROP COLUMN category')
    if fault=='extra':connection.exec_driver_sql('ALTER TABLE onboarding_tasks ADD COLUMN unreviewed_source VARCHAR(20)')
    try:yield tables
    finally:
        if created:
            tables['onboarding_task_completions'].drop(connection,checkfirst=True)
            tables['onboarding_tasks'].drop(connection,checkfirst=True)

@pytest.fixture
def target(db):
    if db.get(Company,1) is None:db.add(Company(id=1,name='Native cutover company'))
    branch=Branch(company_id=1,name='Empty native target',is_active=True)
    db.add(branch);db.flush();return branch


def test_exact_legacy_descriptors_never_register_models_and_empty_schema_is_allowed(db,target):
    before=set(Base.metadata.tables)
    with legacy_schema(db):
        assert set(legacy_tables(inspect(db.connection())))=={'onboarding_tasks','onboarding_task_completions'}
        assert reasons(db,1,target.id)==[]
    assert set(Base.metadata.tables)==before

@pytest.mark.parametrize('fault',['type','fk','column','extra','partial'])
def test_malformed_known_legacy_source_stays_incomplete(db,target,fault):
    with legacy_schema(db,fault):
        assert reasons(db,1,target.id)==['Native cutover source inventory is incomplete.']


def test_new_unknown_table_is_not_exempted_by_known_legacy_schema(db,target):
    with legacy_schema(db):
        db.connection().exec_driver_sql('CREATE TABLE unreviewed_native_legacy_body (id INTEGER PRIMARY KEY, branch_id INTEGER)')
        try:assert reasons(db,1,target.id)==['Native cutover source inventory is incomplete.']
        finally:db.connection().exec_driver_sql('DROP TABLE unreviewed_native_legacy_body')

@pytest.mark.parametrize('location',['target','ambiguous','other_branch','foreign_company'])
def test_real_legacy_completion_native_parent_branch_and_company_are_preserved(db,target,location):
    from app.models.employee import Employee
    from app.models.onboarding import OnboardingTemplate,EmployeeOnboarding
    from app.models.security_boundary import SecurityResourceOwnership
    from app.branches.models import BranchOwnership
    company=1
    if location=='foreign_company':
        foreign=Company(name='Other native company');db.add(foreign);db.flush();company=foreign.id
    branch=target
    if location in {'other_branch','foreign_company'}:
        branch=Branch(company_id=company,name='Existing native history branch',is_active=True);db.add(branch);db.flush()
    employee=Employee(employee_id='LEG-'+uuid4().hex,first_name='Native',last_name='Historical',status='Active',
        branch_id=None if location=='ambiguous' else branch.id,date_of_joining=date(2026,1,1))
    template=OnboardingTemplate(organization_id=company,name='Native retained template')
    db.add_all([employee,template]);db.flush()
    db.add(SecurityResourceOwnership(resource_table=employee.__tablename__,resource_id=employee.id,company_id=company))
    onboarding=EmployeeOnboarding(employee_id=employee.id,template_id=template.id,status='completed')
    db.add(onboarding);db.flush()
    if location!='ambiguous':
        for row in (template,onboarding):
            db.add(BranchOwnership(resource_table=row.__tablename__,resource_key=str(row.id),company_id=company,branch_id=branch.id,source='native-existing'))
        db.flush()
    with legacy_schema(db) as tables:
        task_id=db.connection().execute(insert(tables['onboarding_tasks']).values(template_id=template.id,title='Retained native task').returning(tables['onboarding_tasks'].c.id)).scalar_one()
        completion_id=db.connection().execute(insert(tables['onboarding_task_completions']).values(onboarding_id=onboarding.id,
            task_id=task_id,is_completed=True,remarks='Private body must not be read by cutover').returning(tables['onboarding_task_completions'].c.id)).scalar_one()
        result=reasons(db,1,target.id)
        assert result==([RECONCILE] if location in {'target','ambiguous'} else [])
        assert db.connection().scalar(select(tables['onboarding_task_completions'].c.id).where(tables['onboarding_task_completions'].c.id==completion_id))==completion_id


@pytest.mark.parametrize('location',['target','other_branch','foreign_company'])
def test_native_uuid_source_keeps_history_and_known_foreign_branch_semantics(db,target,location):
    from app.shared.accounting_sync.models import SyncConnection,SyncRecord
    from app.models.user import User
    from app.branches.models import BranchOwnership
    from sqlalchemy import event
    company=1;branch=target
    if location=='foreign_company':
        other=Company(name='Other UUID source company');db.add(other);db.flush();company=other.id
    if location!='target':
        branch=Branch(company_id=company,name='Other UUID source branch',is_active=True);db.add(branch);db.flush()
    actor=User(email=uuid4().hex+'@example.test',hashed_password='unused',is_active=True)
    db.add(actor);db.flush()
    connection=SyncConnection(id=str(uuid4()),organization_id=company,branch_id=branch.id,created_by=actor.id,
        provider='xero',account_id='Native test account',sandbox=True,enabled=True,bridge_secret='Private body is not queried')
    db.add(connection);db.flush()
    record=SyncRecord(id=str(uuid4()),connection_id=connection.id,entity='customers',external_id='native-test',
        data={'private':'not queried'},fingerprint='f'*64,present=True,seen_run_id=str(uuid4()))
    db.add(record);db.flush()
    db.add(BranchOwnership(resource_table=connection.__tablename__,resource_key=connection.id,
        company_id=company,branch_id=branch.id,source='native-existing'));db.flush()
    statements=[];engine=db.get_bind().engine
    def observe(conn,cursor,statement,*args):statements.append(statement)
    event.listen(engine,'before_cursor_execute',observe)
    try:result=reasons(db,1,target.id)
    finally:event.remove(engine,'before_cursor_execute',observe)
    assert result==([RECONCILE] if location=='target' else [])
    assert 'bridge_secret' not in '\n'.join(statements)
