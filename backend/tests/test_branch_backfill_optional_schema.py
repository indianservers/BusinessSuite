"""Ownership repair tolerates absent optional tables without hiding bad schemas."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import DBAPIError
from app.branches.migration import backfill
from app.branches.models import BranchOwnership
from app.models.company import Company, Branch, Department


def test_optional_table_installed_later_on_same_connection_is_backfilled():
    engine = create_engine('sqlite://')
    try:
        with engine.begin() as connection:
            for model in (Company, Branch, BranchOwnership):
                model.__table__.create(connection)
            connection.execute(Company.__table__.insert(), {'id':1,'name':'Fictional local company'})
            connection.execute(Branch.__table__.insert(), {'id':1,'company_id':1,'name':'Verified branch'})
            assert backfill(connection, 1) == {'branches':1}
            assert backfill(connection, 1, table_names={'departments'}) == {}
            Department.__table__.create(connection)
            connection.execute(Department.__table__.insert(), {'id':1,'organization_id':1,'branch_id':1,'name':'New native department'})
            assert backfill(connection, 1, table_names={'departments'}) == {'departments':1}
            assert backfill(connection, 1) == {}
            owner = connection.execute(select(BranchOwnership.__table__).where(
                BranchOwnership.resource_table=='departments', BranchOwnership.resource_key=='1')).mappings().one()
            assert (owner['company_id'],owner['branch_id'],owner['source']) == (1,1,'verified-backfill')
    finally:
        engine.dispose()


def test_partial_installed_optional_table_does_not_silently_receive_ownership():
    engine = create_engine('sqlite://')
    try:
        with engine.begin() as connection:
            for model in (Company, Branch, BranchOwnership):
                model.__table__.create(connection)
            connection.execute(Company.__table__.insert(), {'id':1,'name':'Fictional local company'})
            connection.exec_driver_sql('CREATE TABLE departments (id INTEGER PRIMARY KEY, name VARCHAR(100))')
            with pytest.raises(DBAPIError):
                backfill(connection, 1, table_names={'departments'})
            assert connection.execute(select(BranchOwnership.resource_key)).all() == []
    finally:
        engine.dispose()


def test_native_optional_table_reappearing_is_repaired_without_cached_schema(db):
    from uuid import uuid4
    if db.bind.dialect.name != 'postgresql':
        pytest.skip('Native PostgreSQL transactional schema rehearsal')
    company = Company(name='Native optional-schema rehearsal', is_active=True)
    db.add(company)
    db.flush()
    branch = Branch(company_id=company.id, name='Actual local branch')
    db.add(branch)
    db.flush()
    department = Department(organization_id=company.id, branch_id=branch.id, name='Verified native source')
    db.add(department)
    db.flush()
    quote = db.bind.dialect.identifier_preparer.quote
    temporary = 'qa_optional_departments_' + uuid4().hex
    with db.begin_nested():
        connection = db.connection()
        connection.exec_driver_sql('ALTER TABLE departments RENAME TO ' + quote(temporary))
        assert backfill(connection, company.id, table_names={'departments'}) == {}
        connection.exec_driver_sql('ALTER TABLE ' + quote(temporary) + ' RENAME TO departments')
        assert backfill(connection, company.id, table_names={'departments'}) == {'departments':1}
        row = connection.execute(select(BranchOwnership.__table__).where(
            BranchOwnership.resource_table=='departments',
            BranchOwnership.resource_key==str(department.id))).mappings().one()
        assert (row['company_id'],row['branch_id']) == (company.id,branch.id)
        assert backfill(connection, company.id, table_names={'departments'}) == {}
