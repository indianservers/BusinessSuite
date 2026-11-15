"""Migration preserves owned masters without guessing ambiguous tenant identity."""
from pathlib import Path
import runpy
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select
from app.models.company import Company, Branch
from app.models.payroll import SalaryComponent, SalaryComponentCategory
from app.models.security_boundary import SecurityResourceOwnership
from app.branches.models import BranchOwnership


def test_salary_ownership_migration_is_additive_repeatable_and_fails_closed(db):
    connection = db.connection()
    companies = Company.__table__
    for ident in (1, 2):
        if not connection.execute(select(companies.c.id).where(companies.c.id == ident)).first():
            connection.execute(companies.insert().values(id=ident, name=f'Salary ownership company {ident}'))
    connection.execute(Branch.__table__.insert(), [
        {'id': 101, 'company_id': 1, 'name': 'First salary branch'},
        {'id': 202, 'company_id': 2, 'name': 'Second salary branch'},
    ])
    connection.execute(SalaryComponentCategory.__table__.insert().values(id=301, name='Company two category', code='MIGRATION-TWO', category_type='Earning'))
    component = SalaryComponent.__table__
    for ident in range(401, 408):
        connection.execute(component.insert().values(id=ident, name=f'Preserved component {ident}', code=f'MIGRATION-{ident}', component_type='Earning', amount=37,
                                                    category_id=301 if ident in (405, 406) else None))
    owner = SecurityResourceOwnership.__table__
    connection.execute(owner.insert(), [
        {'resource_table': 'salary_component_categories', 'resource_id': 301, 'company_id': 2},
        {'resource_table': 'salary_components', 'resource_id': 403, 'company_id': 2},
    ])
    for ident, company, branch in [(401, 1, 101), (403, 1, 101), (404, 1, 202), (405, 1, 101), (407, 2, 202)]:
        connection.execute(BranchOwnership.__table__.insert().values(resource_table='salary_components', resource_key=str(ident), company_id=company, branch_id=branch, source='verified-historical-test'))
    before = connection.execute(select(component).where(component.c.id.between(401, 407))).mappings().all()
    migration = runpy.run_path(str(Path(__file__).parents[1] / 'alembic_postgresql/versions/pg_20261114_101_salary_ownership.py'))
    with Operations.context(MigrationContext.configure(connection)):
        migration['upgrade']()
        migration['upgrade']()
        migration['downgrade']()
    claims = dict(connection.execute(select(owner.c.resource_id, owner.c.company_id).where(owner.c.resource_table == 'salary_components', owner.c.resource_id.between(401, 407))).all())
    assert claims == {401: 1, 403: 2, 406: 2, 407: 2}
    after = connection.execute(select(component).where(component.c.id.between(401, 407))).mappings().all()
    assert before == after
