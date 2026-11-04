from tests.rich_text_test_utils import organization_context
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.apps.crm.models import CRMContact, CRMLead
from app.apps.project_management.models import PMSTask, PMSTaskRecordLink, PMSProjectMember, PMSActivity
from app.apps.project_management.task_record_links import link_record, read_links, unlink_record
from app.shared.record_360 import record_work
from tests.test_record_360 import seeded
from tests.test_pms_workspaces import middleware_database, account
from tests.tenant_test_utils import assign_company
from test_identity_utils import own_workflow_records


def targets(db, company):
    contact=CRMContact(organization_id=1,first_name='Linked',full_name='Linked contact',company_id=company.id)
    lead=CRMLead(organization_id=1,first_name='Prospect',full_name='Unconverted prospect')
    db.add_all([contact,lead]);own_workflow_records(db,contact,lead);db.commit()
    return contact,lead


def test_links_reuse_contact_and_unconverted_lead_in_focus(db):
    actor,_,company,other,project,task,entry=seeded(db)
    contact,lead=targets(db,company)
    a=link_record(db,actor,task.id,'contact',contact.id)
    b=link_record(db,actor,task.id,'lead',lead.id)
    assert [item['name'] for item in read_links(db,actor,task.id)['items']]==[contact.full_name,lead.full_name]
    for kind,ident in [('contact',contact.id),('lead',lead.id)]:
        work=record_work(kind,ident,'crm',1,25,db,actor)
        assert {i['source'] for i in work['items']}=={'pms_task','pms_followup'}
    assert getattr(lead,'company_id',None) is None
    assert db.query(PMSTask).count()==1


def test_link_is_idempotent_and_unlink_retains_original_records(db):
    actor,_,company,_,project,task,_=seeded(db);contact,_=targets(db,company)
    first=link_record(db,actor,task.id,'contact',contact.id)
    assert link_record(db,actor,task.id,'contact',contact.id)['id']==first['id']
    assert db.query(PMSActivity).filter_by(action='task.crm_linked').count()==1
    unlink_record(db,actor,task.id,first['id'])
    assert read_links(db,actor,task.id)['items']==[]
    assert db.get(CRMContact,contact.id) and db.get(PMSTask,task.id)
    assert db.query(PMSActivity).filter_by(action='task.crm_unlinked').count()==1


def test_customer_and_tenant_mismatch_are_rejected(db):
    actor,_,company,other,_,task,_=seeded(db);contact,_=targets(db,other)
    with pytest.raises(HTTPException) as exc: link_record(db,actor,task.id,'contact',contact.id)
    assert exc.value.status_code==422
    contact.organization_id=2;db.commit()
    with pytest.raises(HTTPException): link_record(db,actor,task.id,'contact',contact.id)
    assert db.query(PMSTaskRecordLink).count()==0


def test_viewer_cannot_link_and_revoked_target_is_not_exposed(db):
    actor,_,company,_,project,task,_=seeded(db);contact,lead=targets(db,company)
    link=link_record(db,actor,task.id,'lead',lead.id)
    viewer,_=account(db,'task-link-viewer@test.com');assign_company(db,viewer,1)
    db.add(PMSProjectMember(project_id=project.id,user_id=viewer.id,role='Viewer'));db.commit()
    assert read_links(db,viewer,task.id)=={'items':[],'can_manage':False}
    with pytest.raises(HTTPException):link_record(db,viewer,task.id,'contact',contact.id)
    with pytest.raises(HTTPException):unlink_record(db,viewer,task.id,link['id'])
    lead.deleted_at=datetime.now(timezone.utc);db.commit()
    assert read_links(db,actor,task.id)['items']==[]
    assert db.query(PMSTaskRecordLink).count()==1


def test_http_links_options_and_unlink(client,db):
    actor,headers,company,_,_,task,_=seeded(db);contact,lead=targets(db,company)
    base=f'/api/v1/project-management/task-workspace/tasks/{task.id}'
    response=client.post(base+'/crm-links',json={'kind':'contact','record_id':contact.id},headers=headers)
    assert response.status_code==200,response.text
    options=client.get(base+'/crm-link-options',params={'kind':'lead','search':'Unconverted'},headers=headers)
    assert options.status_code==200,options.text
    assert options.json()['items']==[{'id':lead.id,'name':lead.full_name}]
    assert client.get(base+'/crm-links',headers=headers).json()['items'][0]['record_id']==contact.id
    assert client.delete(base+f'/crm-links/{response.json()["id"]}',headers=headers).status_code==200


def test_additive_link_migration_and_indexes():
    from app.apps.project_management import task_record_link_schema as schema
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        for name in ('pms_tasks','crm_contacts','crm_leads','users'):
            connection.exec_driver_sql(f'CREATE TABLE {name} (id INTEGER PRIMARY KEY)')
        op=Operations(MigrationContext.configure(connection))
        schema.upgrade(op)
        assert {i['name'] for i in inspect(connection).get_indexes('pms_task_record_links')}=={'ix_pms_task_record_links_task_id','ix_pms_task_contact_scope','ix_pms_task_lead_scope'}
        schema.downgrade(op)
        assert 'pms_task_record_links' not in inspect(connection).get_table_names()


def test_postgresql_migration_compiles_and_chains_to_current_heads():
    from io import StringIO
    from pathlib import Path
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.apps.project_management import task_record_link_schema
    output=StringIO()
    context=MigrationContext.configure(dialect_name='postgresql',opts={'as_sql':True,'output_buffer':output})
    task_record_link_schema.upgrade(Operations(context))
    sql=output.getvalue()
    assert 'pms_task_record_links' in sql and 'FOREIGN KEY(task_id)' in sql
    root=Path(__file__).resolve().parents[1]
    scripts=ScriptDirectory.from_config(Config(str(root/'alembic.ini')))
    assert scripts.get_revision('pg_20261104_081_task_links').down_revision=='pg_20261104_080_imports'


@pytest.mark.parametrize('kind',['contact','lead'])
def test_existing_crm_merge_repoints_and_deduplicates_task_links(db,kind):
    from app.apps.crm.api.router import _merge_related_records
    actor,_,company,_,project,task,entry=seeded(db)
    contact,lead=targets(db,company)
    winner=contact if kind=='contact' else lead
    model=CRMContact if kind=='contact' else CRMLead
    loser=model(organization_id=1,first_name='Duplicate',full_name='Duplicate identity')
    if kind=='contact':loser.company_id=company.id
    db.add(loser);db.flush()
    link_record(db,actor,task.id,kind,winner.id)
    link_record(db,actor,task.id,kind,loser.id)
    _merge_related_records(db,1,'contacts' if kind=='contact' else 'leads',winner.id,[loser.id],actor.id)
    db.commit()
    rows=db.query(PMSTaskRecordLink).filter_by(task_id=task.id).all()
    assert len(rows)==1 and getattr(rows[0],kind+'_id')==winner.id
