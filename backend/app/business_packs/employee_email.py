"""Creation-only native account/onboarding mail derived from canonical work.

This is not mailbox access. The native producer supplies the actual live
source object; no body, event key or recipient is used to discover authority.
"""
from dataclasses import dataclass
from fastapi import HTTPException
from sqlalchemy import inspect,select,and_,exists


@dataclass(frozen=True)
class _Event:
    scope:object
    source:object
    fields:tuple


FIELDS=('event_key','organization_id','module','recipient_user_id','recipient','subject','body','is_html')


def _deny():raise HTTPException(403,'Native employee email requires its exact authorized source and delivery identity')


def _scope(db):
    from .common_core import CommonCoreScope
    from .common_binding import MARKER
    from .employee_core import PURPOSE
    scope=db.info.get('business_common_core_scope')
    if scope is None:return None
    if (not isinstance(scope,CommonCoreScope) or scope.operation.purpose!=PURPOSE or scope.binding!=db.info.get(MARKER)
            or db.info.get('business_pack_scope') is not None or db.info.get('shared_actor')!=(scope.user_id,scope.company_id)):_deny()
    return scope


def _source(db,scope,source,recipient,user_id,module):
    from .employee_core import _Creation,_RoleChange
    from app.models.user import User
    from app.models.onboarding import EmployeeOnboarding,EmployeeOnboardingTask
    from app.models.employee import Employee
    from app.models.company import Branch
    state=inspect(source,raiseerr=False)
    if (state is None or not getattr(state,'persistent',False) or state.session is not db or source in db.deleted
            or len(state.identity or ())!=1 or type(state.identity[0]) is not int or state.identity[0]<=0
            or state.mapper.class_ not in {User,EmployeeOnboarding,EmployeeOnboardingTask}):_deny()
    # This minimal native identity read invokes the installed engine's current
    # principal/policy/branch fingerprint, including validated flush transitions.
    if not db.query(User.id).filter(User.id==scope.user_id).first():_deny()
    new=False
    if state.mapper.class_ is User:
        proof=db.info.get('_native_employee_role_change')
        if not isinstance(proof,_RoleChange) or proof.scope is not scope or proof.user is not source or module!='security':_deny()
        actual=db.connection().execute(select(User.__table__.c.role_id,User.__table__.c.is_active,User.__table__.c.email).where(User.__table__.c.id==state.identity[0])).first()
        if actual is None or actual.role_id!=proof.new_role_id or not actual.is_active or user_id!=state.identity[0] or recipient!=actual.email:_deny()
        employee=proof.employee
    else:
        plan=db.info.get('_native_employee_creation')
        if (not isinstance(plan,_Creation) or plan.scope is not scope or plan.actor_id!=scope.user_id or plan.company_id!=scope.company_id
                or scope.method!='POST' or scope.route!='/api/v1/employees/' or module!='hrms' or id(source) not in plan.sources):_deny()
        recorded,fields=plan.sources[id(source)]
        if recorded is not source:_deny()
        table=state.mapper.local_table
        actual=db.connection().execute(select(*(table.c[name] for name in fields)).where(table.c.id==state.identity[0])).first()
        if actual is None or tuple(actual)!=tuple(fields.values()):_deny()
        employee=plan.employee
        if employee is None:_deny()
        if isinstance(source,EmployeeOnboarding):
            if source.employee_id!=employee.id:_deny()
            if employee.user_id:
                target=db.connection().execute(select(User.__table__.c.email,User.__table__.c.is_active).where(User.__table__.c.id==employee.user_id)).first()
                if not target or not target.is_active or user_id!=employee.user_id or recipient!=target.email:_deny()
            elif user_id is not None or recipient!=(employee.work_email or employee.personal_email):_deny()
        else:
            from app.crud.crud_onboarding import assign_task_user_id
            from app.models.onboarding import OnboardingTemplateTask
            task=db.query(OnboardingTemplateTask).filter(OnboardingTemplateTask.id==source.template_task_id).first()
            if task is None or user_id!=assign_task_user_id(db,employee,task.assigned_to_role) or user_id!=source.assigned_to_user_id:_deny()
            target=db.connection().execute(select(User.__table__.c.email,User.__table__.c.is_active).where(User.__table__.c.id==user_id)).first()
            if not target or not target.is_active or recipient!=target.email:_deny()
        new=True
    # Parent company/branch is proved from the actual canonical employment row,
    # not an email address or the producer's nullable organization argument.
    employment=Employee.__table__;branches=Branch.__table__
    parent=db.connection().execute(select(employment.c.branch_id,branches.c.company_id).select_from(
        employment.outerjoin(branches,branches.c.id==employment.c.branch_id)).where(employment.c.id==employee.id)).first()
    if not parent or (parent.company_id!=scope.company_id and not (parent.branch_id is None and scope.company_id==1)):_deny()
    if parent.branch_id is not None and parent.branch_id not in scope.branch.allowed:_deny()
    if not db.query(Employee.id).filter(Employee.id==employee.id,Employee.deleted_at.is_(None)).first():_deny()
    return new


def prepare(db,source,*,recipient,subject,body,module,organization_id,user_id,event_key,is_html):
    scope=_scope(db)
    if scope is None:return None
    if source is None or organization_id not in {None,scope.company_id} or not isinstance(event_key,str) or not event_key or len(event_key)>180 or is_html:_deny()
    new=_source(db,scope,source,recipient,user_id,module)
    from app.services.email_events import EVENTS
    from app.core.config import settings
    spec=EVENTS[type(source).__tablename__]
    expected_module,label,_,_,_,path=spec
    status=str(getattr(source,'status',None) or getattr(source,'execution_status',None) or getattr(source,'decision','') or '')
    expected_subject=f"{label}: {status or ('created' if new else 'updated')}"
    expected_body=f'{label} #{source.id} has an update.'
    if status:expected_body+=f'\nCurrent status: {status}.'
    expected_body+=f"\nSign in to review details: {settings.FRONTEND_PUBLIC_URL.rstrip('/')}{path}"
    if module!=expected_module or subject[:240]!=expected_subject[:240] or body!=expected_body:_deny()
    fields=(event_key,scope.company_id,module,user_id,recipient,subject[:240],body,False)
    return _Event(scope,source,fields)


def duplicate_exists(db,event):
    if not isinstance(event,_Event) or event.scope is not _scope(db):_deny()
    _verify_event(db,event)
    from app.models.email_outbox import EmailOutbox
    table=EmailOutbox.__table__
    # Fixed existence-only metadata proof. It grants no ORM/body/status access.
    filters=[table.c[name]==value for name,value in zip(FIELDS,event.fields) if name in {'event_key','organization_id','module','recipient_user_id','recipient'}]
    return bool(db.connection().scalar(select(exists().where(and_(*filters)))))


def validate(db,row):
    from app.models.email_outbox import EmailOutbox
    event=getattr(row,'_suite_employee_email',None)
    if type(row) is not EmailOutbox or row not in db.new or not isinstance(event,_Event) or event.scope is not _scope(db):_deny()
    if getattr(row,'_suite_source_record',None) is not event.source or tuple(getattr(row,name) for name in FIELDS)!=event.fields:_deny()
    if row.status!='queued' or row.provider_message_id or row.error or row.accepted_at or row.attempts not in {None,0}:_deny()
    _verify_event(db,event)
    return True


def _verify_event(db,event):
    values=dict(zip(FIELDS,event.fields))
    verified=prepare(db,event.source,recipient=values['recipient'],subject=values['subject'],body=values['body'],module=values['module'],
        organization_id=values['organization_id'],user_id=values['recipient_user_id'],event_key=values['event_key'],is_html=values['is_html'])
    if verified is None or verified.fields!=event.fields or verified.scope is not event.scope:_deny()
