from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.asset import Asset, AssetAssignment
from app.models.user import User
from app.models.employee import Employee
from app.models.audit import AuditLog
from app.schemas.asset import AssetHandover
from app.services.asset_lifecycle import issue_batch


def test_two_concurrent_handover_requests_have_one_winner(db_engine):
    if db_engine.dialect.name!='postgresql':pytest.skip('Real row-lock concurrency requires PostgreSQL')
    with Session(db_engine) as seed:
        user=User(email=uuid4().hex+'@asset.test',hashed_password='no-login',is_active=True,is_superuser=True)
        seed.add(user);seed.flush()
        employees=[Employee(employee_id=uuid4().hex,first_name='Concurrent',last_name=str(i),status='Active',date_of_joining=date.today()) for i in range(2)]
        item=Asset(name='Concurrent asset',asset_tag=uuid4().hex,organization_id=1,status='Available',condition='Good')
        seed.add_all([item,*employees]);seed.commit()
        uid,aid=user.id,item.id;ids=[e.id for e in employees]
    barrier=Barrier(2)
    def issue(employee):
        with Session(db_engine) as db:
            actor=db.get(User,uid);actor.organization_id=1
            barrier.wait(timeout=15)
            try:
                issue_batch(db,actor,AssetHandover(employee_id=employee,asset_ids=[aid],assigned_date=date.today(),request_key=uuid4().hex))
                db.commit();return 201
            except HTTPException as e:
                db.rollback();return e.status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(issue,ids))
        assert sorted(results)==[201,409]
        with Session(db_engine) as db:
            assert db.query(AssetAssignment).filter_by(asset_id=aid,is_active=True).count()==1
            assert db.get(Asset,aid).status=='Assigned'
    finally:
        with Session(db_engine) as db:
            from app.shared.models import ServiceEvent
            db.query(ServiceEvent).filter_by(actor_id=uid).delete()
            db.query(AssetAssignment).filter_by(asset_id=aid).delete()
            db.query(AuditLog).filter_by(entity_type='asset',entity_id=aid).delete()
            db.query(Asset).filter_by(id=aid).delete()
            db.query(Employee).filter(Employee.id.in_(ids)).delete()
            db.query(User).filter_by(id=uid).delete();db.commit()
