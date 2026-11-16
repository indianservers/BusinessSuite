"""Actual queue/dispatch on owned SQLite schema states; no provider/network."""
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from app.db.base_class import Base
from app.business_packs.delivery_source_models import PackDeliverySource
from app.business_packs.models import PackRecordOwnership,PackActivation,PackContext
from app.models.company import Company,Branch
from app.models.email_outbox import EmailOutbox
from app.services.email_dispatch import queue_email,_deliver

@pytest.mark.parametrize('module',['auth','security','hrms'])
@pytest.mark.parametrize('schema',['100','102','121'])
def test_genuine_unowned_default_mail_uses_actual_dispatch_without_missing_table_queries(monkeypatch,module,schema):
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    with engine.begin() as connection:
        if schema in {'100','102'}:PackDeliverySource.__table__.drop(connection)
        if schema=='100':PackRecordOwnership.__table__.drop(connection)
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider-id')
    try:
        with Session(engine) as db:
            row=queue_email(db,recipient='legacy@example.test',subject='Native account update',body='Common identity notice',module=module,event_key=uuid4().hex)
            db.commit();_deliver(db,row)
            assert row.status=='accepted' and sent==[1]
    finally:engine.dispose()

@pytest.mark.parametrize('schema',['102','121','partial'])
def test_known_private_or_partial_origin_never_falls_back_to_unowned_provider(monkeypatch,schema):
    engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
    with engine.begin() as connection:
        if schema in {'102','partial'}:PackDeliverySource.__table__.drop(connection)
        if schema=='partial':connection.exec_driver_sql('CREATE TABLE business_pack_delivery_sources (id INTEGER PRIMARY KEY,email_outbox_id INTEGER)')
    sent=[];monkeypatch.setattr('app.core.email.send_email',lambda *args:sent.append(1) or 'fake-provider-id')
    try:
        with Session(engine) as db:
            company=Company(name='Owned compatibility fixture');db.add(company);db.flush()
            branch=Branch(company_id=company.id,name='Compatibility source');db.add(branch);db.flush()
            activation=PackActivation(company_id=company.id,pack_key='retail',pack_version=1,state='active');db.add(activation);db.flush()
            context=PackContext(company_id=company.id,branch_id=branch.id,activation_id=activation.id,pack_key='retail',pack_version=1,state='active');db.add(context);db.flush()
            row=queue_email(db,recipient='private@example.test',subject='Historical private source',body='Private native update',module='srm',organization_id=company.id,event_key=uuid4().hex)
            db.flush();db.add(PackRecordOwnership(company_id=company.id,branch_id=branch.id,context_id=context.id,resource_table='email_outbox',resource_key=str(row.id)));db.commit()
            _deliver(db,row)
            assert row.status=='suppressed' and not sent
    finally:engine.dispose()
