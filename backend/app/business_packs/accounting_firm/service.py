"""Private client-service periods. No client books, files or financial writes."""
from hashlib import sha256
import json
from fastapi import HTTPException
from sqlalchemy import inspect,select
from sqlalchemy.exc import IntegrityError
from app.apps.srm.service_checkout import _authority, _source_scope
from app.apps.srm.services.commercial import require, lock_tenant
from app.apps.srm.access import engagement_query
from app.apps.srm.models import SRMEngagement
from app.apps.crm.models import CRMCompany
from app.models.employee import Employee
from .models import MODELS, AccountsPeriod as Period, AccountsCommand as Command


def fail(message, code=403):
    raise HTTPException(code, message)


def authority(db, actor, action='engagements.view', *, write=False):
    require(actor, *('srm_manage','srm_admin') if write else ('srm_view','srm_manage','srm_admin'))
    _, _, fresh = _authority(db, actor, order=False, write=write)
    scope = db.info.get('business_pack_scope')
    state = inspect(actor, raiseerr=False)
    if (scope is None or scope.pack_key != 'accounting_firm' or scope != fresh
        or state is None or not state.persistent or state.session is not db
        or 'accounting_firm.'+action not in scope.capabilities):
        fail('Select an authorized Accounts Company context')
    from app.business_packs.native_policy import native_srm_policy
    if db.info.get('business_pack_policy') != native_srm_policy('accounting_firm').policy:
        fail('Accounts isolation adapter is not installed',503)
    if not all(inspect(db.connection()).has_table(model.__tablename__) for model in (Period,Command)):
        fail('Install the Accounts service-period extension',503)
    return scope


def scoped(db, model, scope):
    return db.query(model).filter_by(organization_id=scope.company_id,branch_id=scope.branch_id,pack_context_id=scope.context_id)


def fields(scope,actor):
    return dict(organization_id=scope.company_id,branch_id=scope.branch_id,pack_context_id=scope.context_id,created_by=actor.id)


def source(db,actor,scope,engagement_id,client_id,*,require_open=False):
    # Native own/team/org scope and private context criteria remain installed.
    row = engagement_query(db,actor).with_entities(SRMEngagement.id,SRMEngagement.customer_id,SRMEngagement.status).filter(SRMEngagement.id==engagement_id).first()
    if row is None or row.customer_id != client_id:
        fail('Client engagement is unavailable',404)
    if require_open:
        from app.apps.srm.api.router import _require_open_engagement
        _require_open_engagement(row)
    _source_scope(db,scope,scope.company_id,scope.branch_id,SRMEngagement,engagement_id)
    client = db.query(CRMCompany.id).filter(CRMCompany.id==client_id,CRMCompany.organization_id==scope.company_id,CRMCompany.deleted_at.is_(None)).first()
    if client is None:
        fail('Client is unavailable',404)
    _source_scope(db,scope,scope.company_id,scope.branch_id,CRMCompany,client_id,master=True)
    from .engagements import validate_created_source
    validate_created_source(db,actor,scope,engagement_id)


def employee(db,scope,ident):
    row = db.query(Employee.id,Employee.user_id).filter(Employee.id==ident,Employee.branch_id==scope.branch_id,
        Employee.deleted_at.is_(None),Employee.status.in_(('Active','Probation','On Leave'))).first()
    if row is None or row.user_id is None:
        fail('Assigned employee requires an active employment and login',409)
    _source_scope(db,scope,scope.company_id,scope.branch_id,Employee,ident,master=True)
    return row.user_id


def staff(db,scope,preparer,reviewer):
    p,r=employee(db,scope,preparer),employee(db,scope,reviewer)
    if preparer==reviewer or p==r:
        fail('Preparer and reviewer must be independent employees and users',409)
    from app.business_packs.models import PackUserGrant
    from app.business_packs.registry import get_role,PackRegistryError
    from app.models.user import User
    grants=PackUserGrant.__table__
    users=User.__table__
    for user_id,capability in ((p,'work.prepare'),(r,'work.review')):
        role=db.connection().scalar(select(grants.c.role).join(users,users.c.id==grants.c.user_id).where(
            grants.c.context_id==scope.context_id,grants.c.company_id==scope.company_id,
            grants.c.branch_id==scope.branch_id,grants.c.user_id==user_id,grants.c.active.is_(True),users.c.is_active.is_(True)))
        try:
            capabilities=get_role('accounting_firm',role).capabilities if role else ()
        except PackRegistryError:
            capabilities=()
        if 'accounting_firm.'+capability not in capabilities:
            fail('Assigned staff require the corresponding active Accounts role',409)
    return p,r


def record(db,actor,scope,ident):
    row=scoped(db,Period,scope).filter_by(id=ident).first()
    if row is None:
        fail('Accounts period is unavailable',404)
    _source_scope(db,scope,scope.company_id,scope.branch_id,Period,row.id)
    source(db,actor,scope,row.engagement_id,row.client_id)
    return row


def result(row):
    return {name:getattr(row,name) for name in ('id','engagement_id','client_id','title','preparer_employee_id',
        'reviewer_employee_id','state','revision','work_revision','work_summary','review_reason','prepared_by_user_id',
        'submitted_work_revision','approved_work_revision')} | {
        name:getattr(row,name).isoformat() for name in ('starts_on','ends_on','due_on')}


def fingerprint(action,ident,data):
    return sha256(json.dumps({'action':action,'id':ident,'input':data.model_dump(mode='json')},sort_keys=True,separators=(',',':')).encode()).hexdigest()


def replay(db,actor,scope,action,ident,data):
    command=scoped(db,Command,scope).filter_by(request_key=str(data.request_key)).one_or_none()
    if command is None:
        return None
    _source_scope(db,scope,scope.company_id,scope.branch_id,Command,command.id)
    if command.created_by!=actor.id or command.request_sha256!=fingerprint(action,ident,data):
        fail('Request key was already used for different Accounts work',409)
    return dict(command.result)


def save(db,actor,scope,row,action,ident,data):
    dto=result(row)
    db.add(Command(**fields(scope,actor),period_id=row.id,request_key=str(data.request_key),
        request_sha256=fingerprint(action,ident,data),action=action,reason=getattr(data,'reason',''),result=dto))
    db.flush()
    return dto


def create(data,db,actor,*,commit=True):
    scope=authority(db,actor,'engagements.manage',write=True)
    lock_tenant(db,actor)
    authority(db,actor,'engagements.manage',write=True)
    source(db,actor,scope,data.engagement_id,data.client_id)
    staff(db,scope,data.preparer_employee_id,data.reviewer_employee_id)
    old=replay(db,actor,scope,'create',None,data)
    if old is not None:
        return old
    source(db,actor,scope,data.engagement_id,data.client_id,require_open=True)
    try:
        with db.begin_nested():
            row=Period(**fields(scope,actor),**data.model_dump(exclude={'request_key'}),state='draft',revision=1,work_revision=0,work_summary='')
            db.add(row)
            db.flush()
            dto=save(db,actor,scope,row,'create',None,data)
    except IntegrityError:
        fail('This engagement period already exists',409)
    if commit:
        db.commit()
    return dto


def get(ident,db,actor):
    scope=authority(db,actor)
    return result(record(db,actor,scope,ident))


def listing(db,actor,*,after=0,limit=50):
    scope=authority(db,actor)
    # SQL-filter by native engagement visibility before pagination, not in-memory.
    visible=engagement_query(db,actor).with_entities(SRMEngagement.id)
    rows=scoped(db,Period,scope).filter(Period.id>after,Period.engagement_id.in_(visible)).order_by(Period.id).limit(limit+1).all()
    items=[]
    for row in rows[:limit]:
        source(db,actor,scope,row.engagement_id,row.client_id)
        items.append(result(row))
    return {'items':items,'next':rows[limit-1].id if len(rows)>limit else None}


def capabilities(db,actor):
    scope=authority(db,actor)
    from app.access.service import check_background_access
    writable=scope.branch_id in db.info['branch_context'].writable
    try:
        require(actor,'srm_manage','srm_admin')
        check_background_access(db,actor,'srm','create',administrative_read=False,stamp=False)
    except HTTPException as exc:
        if exc.status_code!=403:
            raise
        writable=False
    employee_id=db.query(Employee.id).filter(Employee.user_id==actor.id,Employee.branch_id==scope.branch_id,
        Employee.deleted_at.is_(None),Employee.status.in_(('Active','Probation','On Leave'))).scalar()
    can_assign=writable and 'accounting_firm.engagements.manage' in scope.capabilities
    try:
        check_background_access(db,actor,'srm','assign',administrative_read=False,stamp=False)
    except HTTPException as exc:
        if exc.status_code!=403:
            raise
        can_assign=False
    return {'employee_id':employee_id,'assignments_manage':can_assign,**{name.replace('.','_'):writable and 'accounting_firm.'+name in scope.capabilities
        for name in ('engagements.manage','work.prepare','work.review','work.return')}}


def options(db,actor,*,engagement_after=0,preparer_after=0,reviewer_after=0,limit=100):
    if (any(type(value) is not int or value < 0 for value in (engagement_after,preparer_after,reviewer_after))
            or type(limit) is not int or not 1 <= limit <= 100):
        fail('Choose valid Accounts option cursors and a limit from 1 to 100',422)
    scope=authority(db,actor,'engagements.manage')
    from app.business_packs.models import PackUserGrant
    from app.business_packs.registry import get_role,PackRegistryError
    from app.models.user import User
    engagements=engagement_query(db,actor).join(CRMCompany,CRMCompany.id==SRMEngagement.customer_id).with_entities(
        SRMEngagement.id,SRMEngagement.name,SRMEngagement.customer_id,CRMCompany.name.label('client_name')).filter(
        CRMCompany.organization_id==scope.company_id,CRMCompany.deleted_at.is_(None),
        SRMEngagement.id>engagement_after).order_by(SRMEngagement.id).limit(limit+1).all()
    employees=db.query(Employee.id,Employee.first_name,Employee.last_name,Employee.user_id).filter(
        Employee.branch_id==scope.branch_id,Employee.deleted_at.is_(None),Employee.status.in_(('Active','Probation','On Leave')),
        Employee.user_id.is_not(None))
    grants=PackUserGrant.__table__
    users=User.__table__
    role_by_user=dict(db.connection().execute(select(grants.c.user_id,grants.c.role).join(users,users.c.id==grants.c.user_id).where(grants.c.context_id==scope.context_id,
        grants.c.company_id==scope.company_id,grants.c.branch_id==scope.branch_id,grants.c.active.is_(True),users.c.is_active.is_(True))).all())
    eligible={'preparers':set(),'reviewers':set()}
    for user_id,role in role_by_user.items():
        try:
            caps=get_role('accounting_firm',role).capabilities if role else ()
        except PackRegistryError:
            caps=()
        for key,cap in (('preparers','work.prepare'),('reviewers','work.review')):
            if 'accounting_firm.'+cap in caps:
                eligible[key].add(user_id)
    people={}
    next_cursor={'engagements':engagements[limit-1].id if len(engagements)>limit else None}
    for key,after in (('preparers',preparer_after),('reviewers',reviewer_after)):
        # Filter eligibility before limiting: unrelated staff must not hide an
        # eligible preparer/reviewer beyond the first page of employees.
        rows=employees.filter(Employee.user_id.in_(eligible[key]),Employee.id>after).order_by(Employee.id).limit(limit+1).all()
        people[key]=[{'id':row.id,'name':f'{row.first_name} {row.last_name}'.strip()} for row in rows[:limit]]
        next_cursor[key]=rows[limit-1].id if len(rows)>limit else None
    return {'engagements':[{'id':row.id,'name':row.name,'client_id':row.customer_id,'client_name':row.client_name} for row in engagements[:limit]],
        **people,'limit':limit,'next':next_cursor,
        'has_more':{key:value is not None for key,value in next_cursor.items()}}


def change(ident,action,data,db,actor,*,commit=True):
    capability={'assign':'engagements.manage','work':'work.prepare','submit':'work.prepare','approve':'work.review','return':'work.return'}[action]
    scope=authority(db,actor,capability,write=True)
    from app.access.service import check_background_access
    if action=='assign':
        check_background_access(db,actor,'srm','assign')
    lock_tenant(db,actor)
    authority(db,actor,capability,write=True)
    if action=='assign':
        check_background_access(db,actor,'srm','assign')
    row=record(db,actor,scope,ident)
    p,r=staff(db,scope,row.preparer_employee_id,row.reviewer_employee_id)
    if action in {'work','submit'} and actor.id!=p:
        fail('Only the assigned preparer can prepare or submit work')
    if action in {'approve','return'} and (actor.id!=r or actor.id==p or actor.id==row.prepared_by_user_id):
        fail('Only the independent assigned reviewer can review this work')
    old=replay(db,actor,scope,action,ident,data)
    if old is not None:
        return old
    source(db,actor,scope,row.engagement_id,row.client_id,require_open=True)
    if row.revision!=data.expected_revision:
        fail('Period changed; reload its current revision',409)
    with db.begin_nested():
        if action=='assign':
            staff(db,scope,data.preparer_employee_id,data.reviewer_employee_id)
            row.preparer_employee_id=data.preparer_employee_id
            row.reviewer_employee_id=data.reviewer_employee_id
            row.state='draft'
            row.review_reason=''
            row.submitted_work_revision=row.approved_work_revision=None
        elif action=='work':
            row.work_summary=data.summary
            row.work_revision+=1
            row.prepared_by_user_id=actor.id
            row.state='draft'
            row.review_reason=''
            row.submitted_work_revision=row.approved_work_revision=None
        elif action=='submit':
            if row.state not in {'draft','returned'} or row.work_revision<1 or row.prepared_by_user_id!=actor.id:
                fail('Prepare the current work before submitting',409)
            row.state='submitted'
            row.submitted_work_revision=row.work_revision
        else:
            if row.state!='submitted' or row.work_revision!=data.expected_work_revision or row.submitted_work_revision!=row.work_revision:
                fail('Only the current submitted work revision can be reviewed',409)
            if action=='return' and not data.reason.strip():
                fail('A return reason is required',422)
            row.state='approved' if action=='approve' else 'returned'
            row.review_reason=data.reason.strip()
            row.approved_work_revision=row.work_revision if action=='approve' else None
        row.revision+=1
        db.flush()
        dto=save(db,actor,scope,row,action,ident,data)
    if commit:
        db.commit()
    return dto
