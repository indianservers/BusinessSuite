"""PROPOSAL ONLY: native project/task actor identity and closed source proof."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import inspect, update

from app.models.user import User
from app.models.employee import Employee
from app.apps.crm.models import CRMDeal
from app.apps.project_management.models import PMSProject, PMSTask
from app.apps.srm.industry_models import IndustryRecord
from tests.test_business_pack_construction import construction,scenario,catalog,directory_identity
from tests.test_construction_definition import definition,project_body,task_body,post


@pytest.mark.parametrize('purpose',['project','task'])
def test_native_definition_helper_receives_genuine_session_actor_and_no_unapproved_users(client,db,definition,monkeypatch,purpose):
    from app.apps.project_management.api import router as native
    from tests.test_business_pack_http_integration import native_actor
    case = definition
    _,foreign = native_actor(db,case['branch'])
    foreign_id = foreign.id
    actor_id = case['actor'].id
    assert foreign_id != actor_id and db.get(User,foreign_id) is not None
    project = post(client,case['headers'],'/site-projects',project_body(case)) if purpose == 'task' else None
    name = 'create_project_operation' if purpose == 'project' else 'create_task_operation'
    original,checked = getattr(native,name),[]
    def genuine(*args,**kwargs):
        reader,actor = args[-2],args[-1]
        assert type(actor) is User and inspect(actor).session is reader
        assert actor.id == actor_id
        assert reader.get(User,foreign_id) is None
        assert reader.query(User).filter(User.id != actor.id).count() == 0
        assert kwargs['commit'] is False
        checked.append(True)
        return original(*args,**kwargs)
    with monkeypatch.context() as fault:
        fault.setattr(native,name,genuine)
        if purpose == 'project':
            result = post(client,case['headers'],'/site-projects',project_body(case))
            assert db.get(PMSProject,result['id']).owner_user_id == case['actor'].id
        else:
            result = post(client,case['headers'],f'/projects/{project["id"]}/wbs-tasks',task_body())
            assert db.get(PMSTask,result['id']).reporter_user_id == case['actor'].id
    assert checked


@pytest.mark.parametrize('purpose',['project','task'])
def test_real_native_definition_actor_cannot_read_unregistered_employee_realm(client,db,definition,monkeypatch,purpose):
    from app.apps.project_management.api import router as native
    case = definition
    project = post(client,case['headers'],'/site-projects',project_body(case)) if purpose == 'task' else None
    db.commit()  # completed prior HTTP request/audit is durable before fault
    counts = db.query(PMSProject).count(),db.query(PMSTask).count(),db.query(IndustryRecord).count()
    name = 'create_project_operation' if purpose == 'project' else 'create_task_operation'
    original = getattr(native,name)
    def foreign_read(*args,**kwargs):
        reader,actor = args[-2],args[-1]
        assert type(actor) is User and inspect(actor).session is reader
        # Native scope may read only this actual actor's employee identity.
        assert reader.query(Employee).filter(Employee.user_id != actor.id).count() == 0
        assert reader.query(User).filter(User.id != actor.id).count() == 0
        # CRM deal records remain outside the finite definition source inventory.
        reader.query(CRMDeal).all()
        return original(*args,**kwargs)
    with monkeypatch.context() as fault:
        fault.setattr(native,name,foreign_read)
        path = '/site-projects' if purpose == 'project' else f'/projects/{project["id"]}/wbs-tasks'
        post(client,case['headers'],path,project_body(case) if purpose == 'project' else task_body(),403)
    assert (db.query(PMSProject).count(),db.query(PMSTask).count(),db.query(IndustryRecord).count()) == counts


@pytest.mark.parametrize('purpose',['project','task'])
def test_real_definition_actor_revoked_after_native_birth_rolls_back_all_business_rows(client,db,definition,monkeypatch,purpose):
    from app.apps.project_management.api import router as native
    case = definition
    project = post(client,case['headers'],'/site-projects',project_body(case)) if purpose == 'task' else None
    db.commit()
    counts = db.query(PMSProject).count(),db.query(PMSTask).count(),db.query(IndustryRecord).count()
    name = 'create_project_operation' if purpose == 'project' else 'create_task_operation'
    original,seen = getattr(native,name),[]
    def revoke(*args,**kwargs):
        reader,actor = args[-2],args[-1]
        assert type(actor) is User and inspect(actor).session is reader
        result = original(*args,**kwargs)
        seen.append(result.id)
        db.connection().execute(update(User.__table__).where(User.__table__.c.id == actor.id).values(is_active=False))
        return result
    with monkeypatch.context() as fault:
        fault.setattr(native,name,revoke)
        path = '/site-projects' if purpose == 'project' else f'/projects/{project["id"]}/wbs-tasks'
        post(client,case['headers'],path,project_body(case) if purpose == 'project' else task_body(),403)
    assert seen
    assert (db.query(PMSProject).count(),db.query(PMSTask).count(),db.query(IndustryRecord).count()) == counts
    db.expire_all()
    assert db.get(User,case['actor'].id).is_active
