"""Control projections stay fresh across schema installation and revocation."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.branches.service import access


def test_branch_schema_installation_and_company_admin_revocation_are_not_cached():
    engine=create_engine('sqlite://')
    with engine.connect() as connection:
        for ddl in (
            'CREATE TABLE companies(id INTEGER PRIMARY KEY,is_active BOOLEAN)',
            'CREATE TABLE branches(id INTEGER PRIMARY KEY,company_id INTEGER,is_active BOOLEAN)',
            'CREATE TABLE suite_branch_policies(id INTEGER PRIMARY KEY,company_id INTEGER,user_id INTEGER,all_branches BOOLEAN,manage_access BOOLEAN,use_home_branch BOOLEAN)',
            'CREATE TABLE suite_branch_grants(user_id INTEGER,company_id INTEGER,branch_id INTEGER,can_write BOOLEAN)',
            'INSERT INTO companies VALUES(1,1)',
            'INSERT INTO branches VALUES(11,1,1),(12,1,0)',
            'INSERT INTO suite_branch_policies VALUES(1,1,7,1,0,0)',
            'INSERT INTO suite_branch_grants VALUES(7,1,11,0)',
        ):connection.exec_driver_sql(ddl)
        with Session(bind=connection) as db:
            actor=SimpleNamespace(id=7,is_superuser=False)
            with pytest.raises(HTTPException) as error:access(db,actor,1)
            assert error.value.status_code==503
            connection.exec_driver_sql('CREATE TABLE suite_branch_lifecycle(branch_id INTEGER PRIMARY KEY,deleted_at DATETIME)')
            # Explicit all-access preserves inactive read-only definitions and
            # needs no employee-directory query to infer a redundant home.
            assert access(db,actor,1)==({11,12},{11},True,False)
            connection.exec_driver_sql('CREATE TABLE suite_access_memberships(id INTEGER PRIMARY KEY)')
            with pytest.raises(HTTPException) as error:access(db,actor,1)
            assert error.value.status_code==503
            connection.exec_driver_sql('DROP TABLE suite_access_memberships')
            connection.exec_driver_sql('CREATE TABLE suite_access_memberships(id INTEGER PRIMARY KEY,user_id INTEGER,company_id INTEGER,active BOOLEAN,is_admin BOOLEAN)')
            connection.exec_driver_sql('INSERT INTO suite_access_memberships VALUES(1,7,1,1,1)')
            connection.exec_driver_sql('UPDATE suite_branch_policies SET all_branches=0')
            assert access(db,actor,1)==({11,12},{11},True,True)
            connection.exec_driver_sql('UPDATE suite_access_memberships SET is_admin=0')
            assert access(db,actor,1)==({11},set(),False,False)
            connection.exec_driver_sql('UPDATE companies SET is_active=0')
            with pytest.raises(HTTPException) as error:access(db,actor,1)
            assert error.value.status_code==403
    engine.dispose()
