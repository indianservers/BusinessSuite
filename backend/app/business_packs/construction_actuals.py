"""Canonical PMS actuals with immutable Construction command provenance."""
import json
from hashlib import sha256
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, exists, inspect, or_, select, update

from app.core.deps import get_current_user, get_db
from app.apps.project_management.models import (PMSProject, PMSWorkspace, PMSTask, PMSBoard,
    PMSBoardColumn, PMSWorkspaceEntry, PMSTaskExecution, PMSTaskUpdateEntry, PMSActivity,
    PMSFileAsset, PMSTaskWorkspaceState, PMSTaskWatcher, PMSChecklistItem, PMSTaskAssignee)
from app.apps.project_management.recovery_models import RecoveryChange
from app.apps.srm.industry_models import IndustryRecord
from .construction import _source, project_for_action
from .construction_planning import _owned
from .operations import require

router = APIRouter(tags=['Construction canonical actuals'])
KINDS = {'task_actual', 'cost_actual', 'cost_budget'}
_COMMANDS = WeakKeyDictionary()


def fail(message, status=409):
    raise HTTPException(status, message)


class TaskActualInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    expected_updated_at: datetime | None
    status: Literal['Backlog', 'To Do', 'In Progress', 'In Review', 'Blocked', 'Done', 'Completed', 'Closed'] | None = None
    actual_hours: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    progress: int | None = Field(None, ge=0, le=100)
    progress_revision: int | None = Field(None, ge=0)
    progress_note: str | None = Field(None, min_length=1, max_length=10000)

    @model_validator(mode='after')
    def change(self):
        if self.status is None and self.actual_hours is None and self.progress is None:
            raise ValueError('Supply a native status or actual hours')
        if self.progress is not None and (self.progress_revision is None or not (self.progress_note or '').strip()):
            raise ValueError('Manual progress needs the native revision and a supporting update')
        return self


class CostActualInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    expected_actual_cost: Decimal | None = Field(ge=0, max_digits=14, decimal_places=2)
    cumulative_actual_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    as_of: date
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def valid(self):
        self.reason = self.reason.strip()
        if not self.reason or self.as_of > date.today():
            raise ValueError('A reason and a non-future cost date are required')
        return self


class CostBudgetInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    expected_estimated_cost: Decimal | None = Field(ge=0, max_digits=14, decimal_places=2)
    estimated_cost: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def valid(self):
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError('A cost budget change needs a reason')
        return self


class _Actual:
    """Private exact-operation extension to the finite native planning reader."""
    def __init__(self, db, actor, project_id, kind, payload, scope, workspace_id, task_ids, recipients):
        from .construction_definition import _workspace
        self.db, self.actor, self.project_id, self.kind = db, actor, project_id, kind
        self.data, self.task_id = payload['data'], payload.get('task_id')
        self.scope, self.workspace_id, self.task_ids = scope, workspace_id, task_ids
        self.recipients = recipients
        self.root, self.before = None, None
        self.expected_root, self.expected_progress = None, None
        self.recovery_ids = ()
        self.workspace_epoch = _workspace(db, actor, scope, workspace_id)
        self.config_tables = (PMSBoard, PMSBoardColumn, PMSWorkspaceEntry, PMSTaskExecution, PMSTaskUpdateEntry,
            PMSChecklistItem, PMSTaskAssignee)
        connection = db.connection()
        board = PMSBoard.__table__
        self.board_ids = tuple(connection.scalars(select(board.c.id).where(board.c.project_id == project_id)))
        self.config = self._config()
        self.other_tasks = self._other_tasks()
        if kind == 'task_actual':
            if self.task_id not in task_ids:
                fail('Select an actual task in this Construction project', 404)
            task = connection.execute(select(PMSTask.__table__).where(PMSTask.__table__.c.id == self.task_id)).one()
            if task.sprint_id is not None or task.recurrence_rule:
                fail('Recurring or sprint-linked actuals require their separately reviewed native source graph', 422)
            for model in (PMSFileAsset, PMSTaskWatcher):
                table = model.__table__
                clause = table.c.task_id == self.task_id
                if model is PMSTaskWatcher and self.data.progress is not None:
                    if connection.scalar(select(exists().where(clause))):
                        fail('Progress watcher notifications require their separately reviewed recipient graph', 422)
                elif connection.scalar(select(exists().where(clause, ~_owned(table, None, scope)))):
                    fail('Actual task attachments require explicit Construction ownership')
            history = RecoveryChange.__table__
            if connection.scalar(select(exists().where(history.c.workspace_id == workspace_id,
                    history.c.actor_id == actor.id, history.c.state == 'undone',
                    or_(history.c.task_id.notin_(task_ids), ~_owned(history, history.c.id, scope))))):
                fail('Resolve the native undo branch outside this Construction project before updating actuals')
            self.recovery_ids = tuple(connection.scalars(select(history.c.id).where(history.c.workspace_id == workspace_id,
                history.c.actor_id == actor.id, history.c.state == 'undone')))
            for row in self.config[PMSWorkspaceEntry]:
                if row.kind == 'auto_rule':
                    rule = json.loads(row.body)
                    if rule.get('enabled') and rule.get('project_id') == project_id and rule.get('trigger') == 'task.status_changed':
                        fail('Native status automation requires its separately reviewed side-effect graph', 422)
                elif row.kind == f'wf{project_id:x}':
                    scheme = json.loads(row.body)
                    routes = [*scheme.get('transitions', []), *(r for routes in scheme.get('work_type_transitions', {}).values() for r in routes)]
                    if scheme.get('enabled') and any(r.get('approval_user_ids') for r in routes):
                        fail('Native workflow approval consumption requires its separately reviewed source graph', 422)

    def _config(self):
        result = {}
        for model in self.config_tables:
            table = model.__table__
            if model is PMSBoard:
                clause = table.c.project_id == self.project_id
            elif model is PMSBoardColumn:
                clause = table.c.board_id.in_(self.board_ids)
            elif model is PMSWorkspaceEntry:
                clause = and_(table.c.workspace_id == self.workspace_id, table.c.kind.in_(['auto_rule', f'wf{self.project_id:x}']))
            else:
                clause = table.c.task_id.in_(self.task_ids)
                if model is PMSTaskUpdateEntry:
                    clause = and_(clause, table.c.kind == 'blocker')
            if self.db.connection().scalar(select(exists().where(clause, ~_owned(table, None, self.scope)))):
                fail('Every native actuals workflow, board and completion source requires explicit Construction ownership')
            result[model] = tuple(self.db.connection().execute(select(table).where(clause).order_by(*table.primary_key.columns)))
        return result

    def current(self):
        from .construction_definition import _workspace
        if (self.workspace_epoch != _workspace(self.db, self.actor, self.scope, self.workspace_id)
                or self.config != self._config() or self.other_tasks != self._other_tasks()):
            fail('Native actuals workspace or completion configuration changed')
        if self.expected_root is not None and self.expected_root != self._root_values():
            fail('Canonical native actuals changed before the command committed')
        if self.expected_progress is not None and self.expected_progress != self._progress_values():
            fail('Native progress state changed before the command committed')

    def _other_tasks(self):
        if self.kind != 'task_actual':
            return ()
        table = PMSTask.__table__
        return tuple(self.db.connection().execute(select(table.c.id, table.c.parent_task_id, table.c.status)
            .where(table.c.id.in_(self.task_ids), table.c.id != self.task_id).order_by(table.c.id)))

    def _root_values(self, *, from_root=False):
        model = PMSTask if self.kind == 'task_actual' else PMSProject
        fields = ('status', 'actual_hours', 'completed_at', 'updated_at') if self.kind == 'task_actual' else ('estimated_cost', 'actual_cost', 'updated_at')
        table = model.__table__
        values = tuple(getattr(self.root, name) for name in fields) if from_root else self.db.connection().execute(
            select(*(table.c[name] for name in fields)).where(table.c.id == (self.task_id if self.kind == 'task_actual' else self.project_id))).one()
        return tuple(value.astimezone(timezone.utc).replace(tzinfo=None) if isinstance(value, datetime) and value.tzinfo else value for value in values)

    def _progress_values(self):
        table = PMSTaskWorkspaceState.__table__
        row = self.db.connection().execute(select(table).where(table.c.task_id == self.task_id)).first()
        return tuple(row) if row else None

    def criteria(self):
        from app.common.models import CommonPerson, CommonProfile
        return {
            PMSWorkspace: and_(PMSWorkspace.id == self.workspace_id, PMSWorkspace.organization_id == self.scope.company_id),
            PMSBoard: PMSBoard.id.in_(self.board_ids),
            PMSBoardColumn: PMSBoardColumn.id.in_([r.id for r in self.config[PMSBoardColumn]]),
            PMSWorkspaceEntry: PMSWorkspaceEntry.id.in_([r.id for r in self.config[PMSWorkspaceEntry]]),
            PMSTaskExecution: PMSTaskExecution.task_id.in_(self.task_ids),
            PMSTaskUpdateEntry: PMSTaskUpdateEntry.task_id.in_(self.task_ids),
            PMSFileAsset: and_(PMSFileAsset.project_id == self.project_id, PMSFileAsset.task_id == self.task_id),
            PMSTaskWatcher: PMSTaskWatcher.task_id == self.task_id,
            CommonProfile: CommonProfile.person_id.in_(select(CommonPerson.id).where(CommonPerson.user_id == self.actor.id, CommonPerson.organization_id == self.scope.company_id)),
            RecoveryChange: and_(RecoveryChange.workspace_id == self.workspace_id, RecoveryChange.actor_id == self.actor.id,
                RecoveryChange.task_id.in_(self.task_ids)),
        }

    def bulk(self, execution):
        if not execution.is_update:
            return False
        statement = update(RecoveryChange).where(RecoveryChange.workspace_id == self.workspace_id,
            RecoveryChange.actor_id == self.actor.id, RecoveryChange.state == 'undone').values(state='discarded')
        if self.kind != 'task_actual' or str(execution.statement.compile(compile_kwargs={'literal_binds': True})) != str(statement.compile(compile_kwargs={'literal_binds': True})):
            fail('Native actuals cannot perform an unreviewed bulk update', 403)
        self.current()
        execution.statement = execution.statement.where(RecoveryChange.id.in_(self.recovery_ids))
        return True

    def validate(self, session, minted):
        from app.shared.communication.models import FollowUp, CommunicationEvent
        from app.shared.models import ServiceEvent
        from app.models.email_outbox import EmailOutbox
        from app.apps.project_management.recovery import task_state
        if session.deleted:
            fail('Actuals cannot delete native records', 403)
        for row in session.dirty:
            changed = {name for name, attr in inspect(row).attrs.items() if attr.history.has_changes()}
            if not changed:
                continue
            if type(row) is PMSTask and self.kind == 'task_actual' and row.id in self.task_ids:
                allowed = {'status', 'actual_hours', 'completed_at', 'column_id', 'position', 'updated_at'} if row.id == self.task_id else {'position'}
                if row.project_id != self.project_id or changed - allowed:
                    fail('Actuals may change only requested native status/hours and native board ordering', 403)
                if row.id == self.task_id and {row.assignee_user_id, row.reporter_user_id} - {None, *self.recipients}:
                    fail('Native actuals mail requires its separately reviewed recipient graph', 422)
                if row.id == self.task_id and any(getattr(row, k) != v for k, v in self.data.model_dump(exclude_unset=True, exclude={'request_id', 'expected_updated_at', 'progress', 'progress_revision', 'progress_note'}).items()):
                    fail('Native task actuals differ from the command', 403)
            elif type(row) is PMSProject and self.kind in {'cost_actual', 'cost_budget'} and row.id == self.project_id:
                field = 'actual_cost' if self.kind == 'cost_actual' else 'estimated_cost'
                value = self.data.cumulative_actual_cost if self.kind == 'cost_actual' else self.data.estimated_cost
                if changed - {field, 'updated_at'} or getattr(row, field) != value:
                    fail('Cost commands may update only their exact canonical PMS cost field', 403)
            elif type(row) is PMSTaskWorkspaceState and self.kind == 'task_actual' and row.task_id == self.task_id:
                if changed - {'progress', 'revision', 'updated_at'} or row.progress != self.data.progress or row.revision != self.data.progress_revision + 1:
                    fail('Manual progress must retain its native revision and command value', 403)
            else:
                fail('Native actuals attempted an unreviewed update', 403)
        for row in session.new:
            if row not in minted and getattr(row, 'id', None) is not None:
                fail('Native actual evidence requires genuinely new identities', 403)
            if type(row) is PMSActivity:
                actions = {'status.changed', 'task.updated', 'subtask.completed', 'task.update_posted'} if self.kind == 'task_actual' else {'project.updated', 'project.budget_changed'} if self.kind == 'cost_budget' else {'project.updated'}
                if row.project_id != self.project_id or row.actor_user_id != self.actor.id or row.entity_type != ('task' if self.kind == 'task_actual' else 'project') or row.entity_id != (self.task_id if self.kind == 'task_actual' else self.project_id) or row.action not in actions:
                    fail('Native activity requires the actual changed source', 403)
            elif type(row) is PMSTaskWorkspaceState:
                if self.kind != 'task_actual' or row.task_id != self.task_id or row.progress != self.data.progress or row.progress_mode != 'manual' or row.revision != 1 or self.data.progress_revision != 0:
                    fail('Manual progress requires its actual new native task state', 403)
            elif type(row) is PMSTaskUpdateEntry:
                from app.apps.project_management.task_workspace import clean_body
                if self.kind != 'task_actual' or row.task_id != self.task_id or row.author_id != self.actor.id or row.kind != 'update' or row.progress != self.data.progress or row.body != clean_body(self.data.progress_note) or row.minutes != 0 or row.file_ids or row.responsible_user_id is not None:
                    fail('Progress evidence must be its actual native update', 403)
            elif type(row) is RecoveryChange:
                if self.kind != 'task_actual' or row.workspace_id != self.workspace_id or row.actor_id != self.actor.id or row.task_id != self.task_id or row.state != 'applied' or row.before != self.before or row.after != task_state(self.root):
                    fail('Native recovery requires its actual changed task', 403)
            elif type(row) is CommunicationEvent:
                table = FollowUp.__table__
                if not self.db.connection().scalar(select(exists().where(table.c.workspace_id == self.workspace_id,
                        table.c.task_id == self.task_id, table.c.workspace_id == row.workspace_id, table.c.conversation_id == row.conversation_id))):
                    fail('Actuals cache event requires a real linked task', 403)
            elif type(row) is ServiceEvent:
                source = getattr(row, '_suite_source_record', None)
                expected_event = 'status.changed' if self.kind == 'task_actual' and self.before['status'] != self.root.status else 'record.updated'
                standard = source is self.root and inspect(source).session is session and row.event_type == expected_event and row.payload_json == {'depth': row.payload_json.get('depth'), 'data': {}}
                pipeline = (self.kind == 'task_actual' and row.event_type == 'pipeline.stage_entered'
                    and row.payload_json == {'origin': 'pipeline_workspace', 'depth': row.payload_json.get('depth'),
                        'data': {'scope': f'project:{self.project_id}', 'stage': self.data.status,
                            'previous_stage': self.before['status'], 'previous_stage_name': self.before['status'],
                            'stage_name': self.data.status, 'owner_id': self.root.assignee_user_id}})
                if row.organization_id != self.scope.company_id or row.actor_id != self.actor.id or row.module_key != 'project_management' or row.entity_type != ('task' if self.kind == 'task_actual' else 'project') or row.entity_id != (self.task_id if self.kind == 'task_actual' else self.project_id) or not (standard or pipeline):
                    fail('Native actual event requires its actual changed source', 403)
            elif type(row) is EmailOutbox:
                from .construction_planning import _task_email
                if self.kind != 'task_actual':
                    fail('Project cost updates cannot queue task mail', 403)
                _task_email(row, self.root, self.actor, self.scope, session, self.recipients)
            else:
                fail('Native actuals attempted an unreviewed insert: ' + row.__tablename__, 403)
            if row not in minted:
                minted.append(row)

    def run(self, native, principal):
        from app.apps.project_management.api import router as pms
        from app.apps.project_management.schemas import PMSTaskUpdate, PMSProjectUpdate
        from app.apps.project_management.recovery import task_state
        if self.kind == 'task_actual':
            self.root = native.get(PMSTask, self.task_id)
            self.before = task_state(self.root)
            data = PMSTaskUpdate(**self.data.model_dump(exclude={'request_id', 'progress', 'progress_revision', 'progress_note'}, exclude_unset=True))
            result = pms.update_task_operation(self.task_id, data, native, principal, commit=False)
            output = {key: getattr(result, key) for key in ('id', 'project_id', 'status', 'actual_hours', 'completed_at', 'updated_at')}
            if self.data.progress is not None:
                from app.apps.project_management.task_workspace import EntryInput, add_entry_operation
                entry = add_entry_operation(self.task_id, EntryInput(body=self.data.progress_note,
                    progress=self.data.progress, revision=self.data.progress_revision), native, principal, commit=False)
                output.update(progress=self.data.progress, progress_revision=self.data.progress_revision + 1, progress_entry_id=entry['id'])
                actual_state = native.get(PMSTaskWorkspaceState, self.task_id)
                self.expected_progress = tuple(getattr(actual_state, column.name) for column in actual_state.__table__.columns)
            self.expected_root = self._root_values(from_root=True)
            return output
        self.root = native.get(PMSProject, self.project_id)
        field = 'actual_cost' if self.kind == 'cost_actual' else 'estimated_cost'
        value = self.data.cumulative_actual_cost if self.kind == 'cost_actual' else self.data.estimated_cost
        result = pms.update_project_operation(self.project_id, PMSProjectUpdate(**{field: value}), native, principal, commit=False)
        self.expected_root = self._root_values(from_root=True)
        return {'id': result.id, field: getattr(result, field)}


def validate_record(db, scope, row):
    if type(row) is not IndustryRecord or row.kind not in KINDS:
        return
    if not inspect(row).persistent:
        if _COMMANDS.get(db) is not row or row.created_by != scope.user_id or row.status != 'recorded':
            fail('Actuals provenance requires its actual canonical command', 403)
    elif db.is_modified(row, include_collections=True):
        fail('Native actuals provenance is immutable', 403)


def _command(db, actor, project_id, kind, data, task_id=None):
    from app.apps.srm.industry_api import context, audit
    from .construction_planning import _run, _graph, _start_checks, _final_checks, _drop_checks
    from .common_core import _native_authority
    from .construction import _project_epoch
    scope, _ = _source(db, actor, project_id)
    require(db, actor, 'diary.record' if kind == 'task_actual' else 'boq.prepare' if kind == 'cost_budget' else 'billing.prepare')
    authority = _native_authority(db, actor, scope.company_id)
    from .catalog_management import _module_grant
    from app.access.service import check_background_access
    sales = _module_grant(db, actor, scope, 'srm')
    native_permissions = {'srm_invoice_create', 'srm_admin'} if kind == 'cost_actual' else {'srm_manage', 'srm_admin'}
    if not actor.is_superuser and (not sales.get('enabled') or 'create' not in sales.get('actions', ())
            or not native_permissions.intersection(sales.get('permissions', ()))):
        fail('Fresh native Sales write permission is required for Construction actuals', 403)
    check_background_access(db, actor, 'srm', 'create', administrative_read=False, stamp=False)
    context(db, actor, True, finance=kind == 'cost_actual')
    if authority != _native_authority(db, actor, scope.company_id):
        fail('Native actuals authority changed while waiting', 403)
    _graph(db, actor, project_id, True, kind)
    project = project_for_action(db, actor, project_id, 'manage_tasks' if kind == 'task_actual' else 'edit_project')
    authority = _native_authority(db, actor, scope.company_id)
    epoch = _project_epoch(db, scope, project_id)
    # UUID comparison includes task identity so replay cannot migrate evidence.
    token = data.model_dump(mode='json') | {'task_id': task_id}
    token_hash = sha256(json.dumps(token, sort_keys=True).encode()).hexdigest()
    reserved = db.connection().execute(select(IndustryRecord.__table__.c.id).where(
        IndustryRecord.__table__.c.organization_id == scope.company_id,
        IndustryRecord.__table__.c.branch_id == scope.branch_id, IndustryRecord.__table__.c.request_id == str(data.request_id))).first()
    if reserved:
        row = db.query(IndustryRecord).filter_by(id=reserved.id, project_id=project_id, kind=kind).first()
        if row is None or row.data.get('_request_digest') != token_hash:
            fail('Actuals request identity is already reserved with different details')
        return row.data['native_result']
    before = None
    if kind in {'cost_actual', 'cost_budget'}:
        raw = db.connection().execute(select(PMSProject.__table__).where(PMSProject.__table__.c.id == project_id).with_for_update()).one()
        field = 'actual_cost' if kind == 'cost_actual' else 'estimated_cost'
        before = Decimal(str(getattr(raw, field))) if getattr(raw, field) is not None else None
        expected = data.expected_actual_cost if kind == 'cost_actual' else data.expected_estimated_cost
        if before != expected:
            fail('Canonical project cost changed; reload before retrying')
    if kind == 'cost_actual':
        if project.currency != data.currency:
            fail('Cost actual currency must match the canonical project currency')
        history = db.query(IndustryRecord).filter_by(project_id=project_id, kind='cost_actual').all()
        if any(row.data.get('currency') != data.currency or date.fromisoformat(row.data['as_of']) >= data.as_of for row in history):
            fail('Cost dates must follow retained history and preserve its currency')
    _start_checks(db)
    try:
        with db.begin_nested():
            result = jsonable_encoder(_run(db, actor, project_id, kind, {'data': data, 'task_id': task_id}))
            payload = {'_request_digest': token_hash, 'native_result': result, 'task_id': task_id}
            if kind == 'cost_actual':
                payload.update(as_of=data.as_of.isoformat(), currency=data.currency, cumulative_actual_cost=str(data.cumulative_actual_cost),
                    source_project_id=project_id, source_before=str(before) if before is not None else None, source_after=str(data.cumulative_actual_cost), reason=data.reason)
            elif kind == 'cost_budget':
                payload.update(currency=project.currency, source_project_id=project_id, source_before=str(before) if before is not None else None,
                    source_after=str(data.estimated_cost), reason=data.reason)
            row = IndustryRecord(organization_id=scope.company_id, branch_id=scope.branch_id, project_id=project_id,
                kind=kind, title='Canonical project cost budget' if kind == 'cost_budget' else 'Canonical project cost actual' if kind == 'cost_actual' else f'Canonical task {task_id} actual',
                request_id=str(data.request_id), status='recorded', revision=1, created_by=actor.id, data=payload)
            _COMMANDS[db] = row
            try:
                db.add(row); db.flush(); audit(db, actor, row, kind + '_recorded')
            finally:
                _COMMANDS.pop(db, None)
        _final_checks(db)
        latest = project_for_action(db, actor, project_id, 'manage_tasks' if kind == 'task_actual' else 'edit_project')
        if kind == 'cost_actual' and latest.currency != data.currency:
            fail('Canonical project currency changed before cost evidence committed')
        if kind == 'cost_budget' and latest.currency != project.currency:
            fail('Canonical project currency changed before cost budget evidence committed')
        _graph(db, actor, project_id, True, kind)
        if authority != _native_authority(db, actor, scope.company_id) or epoch != _project_epoch(db, scope, project_id):
            fail('Native actuals authority changed before the command committed', 403)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        _drop_checks(db)


@router.post('/projects/{project_id}/task-actuals/{task_id}')
def task_actual(project_id: int, task_id: int, data: TaskActualInput, db=Depends(get_db), actor=Depends(get_current_user)):
    return _command(db, actor, project_id, 'task_actual', data, task_id)


@router.post('/projects/{project_id}/cost-actuals')
def cost_actual(project_id: int, data: CostActualInput, db=Depends(get_db), actor=Depends(get_current_user)):
    return _command(db, actor, project_id, 'cost_actual', data)


@router.post('/projects/{project_id}/cost-budget')
def cost_budget(project_id: int, data: CostBudgetInput, db=Depends(get_db), actor=Depends(get_current_user)):
    return _command(db, actor, project_id, 'cost_budget', data)
