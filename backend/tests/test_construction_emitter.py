"""Pure negative opaque-frame probes; no database or provider operation."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.business_packs import construction_emitter as emitter


def test_emitter_constructor_is_not_an_issuer():
    with pytest.raises(HTTPException) as denied:
        emitter._Frame()
    assert denied.value.status_code == 403


def test_object_new_does_not_make_an_issued_frame():
    frame = object.__new__(emitter._Frame)
    assert emitter.verify_native_emitter(object(), object(), parent=object(), frame=frame) is False


def test_forged_native_type_info_and_scope_do_not_authorize_emission():
    fake = SimpleNamespace(info={'shared_actor': (1, 1), 'business_pack_scope': object()},
        _suite_current_module='project_management', _suite_scope_active=True)
    assert emitter.verify_native_emitter(fake, object(), parent=fake, frame=fake) is False


def test_named_caller_or_supplied_guard_cannot_issue_a_frame():
    def forbidden():
        pytest.fail('A rejected issuer must never execute a caller-supplied guard')
    def fake():
        emitter.issue(object(), parent=object(), scope=object(), actor=object(), self_user=object(),
            purpose='construction.team.member', current=forbidden, epoch='0' * 64)
    fake.__name__ = '_native'
    fake.__module__ = 'app.business_packs.construction_workspace_members'
    with pytest.raises(HTTPException) as denied:
        fake()
    assert denied.value.status_code == 403


def test_unissued_frame_cannot_be_sealed_or_released():
    frame = object.__new__(emitter._Frame)
    with pytest.raises(HTTPException):
        emitter.seal(frame)
    with pytest.raises(HTTPException):
        emitter.release_native(frame, successful=True)


def test_definition_class_listener_does_not_trust_session_info_or_a_named_plan(monkeypatch):
    from app.business_packs import construction_definition as definition
    native = definition._DefinitionSession()
    native.info.update(shared_actor=(1, 1), construction_plan=SimpleNamespace(scope='construction'))
    monkeypatch.setattr(native, 'connection', lambda *args, **kwargs: pytest.fail('Unregistered session obtained authority'))
    definition._stamp_definition_births(native, object())
    assert native not in definition._BIRTH_STAMPS
    native.close()


def test_genuine_definition_anchors_precede_generic_email_preparation(client, db, definition, monkeypatch):
    from sqlalchemy import inspect, select
    from app.apps.project_management.models import PMSTask, PMSTaskAssignee
    from app.business_packs import construction_definition as module, delivery_sources as common
    from app.business_packs.models import PackRecordOwnership
    from app.branches.models import BranchOwnership
    from app.branches.catalog import resource_key
    from tests.test_construction_definition import post, project_body, task_body
    case = definition
    project = post(client, case['headers'], '/site-projects', project_body(case))
    original, prepared = common.prepare_email, []
    def observed(native, row, source):
        if type(source) in {PMSTask, PMSTaskAssignee}:
            plan = module._BIRTH_STAMPS.get(native)
            assert type(plan) is module._Birth and inspect(source).persistent
            assert source in plan.births and id(source) in plan.stamped
            for actual in [plan.root, *plan.root.assignments]:
                assert inspect(actual).persistent and actual in plan.births and id(actual) in plan.stamped
                key = resource_key(actual.__table__, {column.name: getattr(actual, column.name) for column in actual.__table__.primary_key})
                for model in (PackRecordOwnership, BranchOwnership):
                    owner = model.__table__
                    actual_owner = db.connection().execute(select(owner).where(owner.c.resource_table == actual.__tablename__,
                        owner.c.resource_key == key, owner.c.company_id == plan.scope.company_id,
                        owner.c.branch_id == plan.scope.branch_id)).one()
                    if model is PackRecordOwnership:
                        assert actual_owner.context_id == plan.scope.context_id
            prepared.append(type(source))
        return original(native, row, source)
    monkeypatch.setattr(common, 'prepare_email', observed)
    post(client, case['headers'], f'/projects/{project["id"]}/wbs-tasks', task_body(assignee_user_ids=[case['actor'].id]))
    assert set(prepared) == {PMSTask, PMSTaskAssignee}


def test_definition_stamped_native_failure_rolls_back_outbox_certificates_and_retries(client, db, definition, monkeypatch):
    from sqlalchemy import select, func
    from app.business_packs import construction_definition as module
    from app.apps.project_management.api import router as pms
    from app.apps.project_management.models import PMSTask, PMSTaskAssignee, PMSBoard, PMSBoardColumn, PMSActivity
    from app.business_packs.delivery_source_models import PackDeliverySource
    from app.models.email_outbox import EmailOutbox
    from tests.test_construction_definition import post, project_body, task_body
    case = definition
    project = post(client, case['headers'], '/site-projects', project_body(case))
    db.commit()  # Complete the prior successful request's audit transaction.
    models = (PMSTask, PMSTaskAssignee, PMSBoard, PMSBoardColumn, PMSActivity, EmailOutbox, PackDeliverySource)
    counts = {model: db.query(model).count() for model in models}
    original = pms.create_task_operation
    payload = task_body(assignee_user_ids=[case['actor'].id])
    path = f'/projects/{project["id"]}/wbs-tasks'
    def fail_after_actual_native(*args, **kwargs):
        value = original(*args, **kwargs)
        assert value.id and kwargs['commit'] is False
        assert db.connection().scalar(select(func.count()).select_from(PackDeliverySource.__table__)) > counts[PackDeliverySource]
        raise RuntimeError('Failure after actual private certificate stamping')
    with monkeypatch.context() as fault:
        fault.setattr(pms, 'create_task_operation', fail_after_actual_native)
        with pytest.raises(RuntimeError, match='Failure after actual private certificate stamping'):
            post(client, case['headers'], path, payload)
    assert {model: db.query(model).count() for model in models} == counts
    assert not module._BIRTH_STAMPS
    assert not emitter._RETAINED.get(db)
    child = post(client, case['headers'], path, payload)
    assert post(client, case['headers'], path, payload) == child
    assert db.query(PMSTask).count() == counts[PMSTask] + 1
    assert db.query(PMSTaskAssignee).count() == counts[PMSTaskAssignee] + 1
    assert db.query(EmailOutbox).count() == counts[EmailOutbox] + 2
    assert db.query(PackDeliverySource).count() == counts[PackDeliverySource] + 2
    assert not module._BIRTH_STAMPS
    assert not emitter._RETAINED.get(db)


from tests.test_construction_definition import definition
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
