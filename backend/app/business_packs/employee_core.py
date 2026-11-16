"""Closed canonical employment purpose. Operational pack grants confer no rights.

Routes are published only with their complete native graph. Employee360,
payroll, account administration, exports and private module aggregates are not
part of this purpose.
"""
from types import MappingProxyType
from contextlib import contextmanager
from dataclasses import dataclass,replace,field
from hashlib import sha256
import json

from fastapi import HTTPException
from sqlalchemy import and_,event,exists,false,inspect,or_,select,true
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause,TextClause
from sqlalchemy.sql.functions import count as CountFunction
from sqlalchemy.sql.selectable import Alias,Subquery,Select,FromClause,Join

PURPOSE='hrms.employee_management'
IDENTITY_FIELDS=('id','user_id','branch_id','department_id','reporting_manager_id','deleted_at')


def native_predicate(db,actor,company,model,employee_predicate):
    """Only the registered canonical employment purpose reads its definitions.

    This augments native own/team semantics for configuration and polymorphic
    employee values; native tenant/branch criteria remain independently bound.
    """
    from .common_binding import CoreRequestBinding,MARKER
    binding=db.info.get(MARKER)
    if (not isinstance(binding,CoreRequestBinding) or binding.purpose!=PURPOSE
            or binding.user_id!=actor.id or binding.company_id!=company
            or db.info.get('business_pack_scope') is not None):return None
    from .common_core import OPERATIONS,CommonCoreScope
    operation=OPERATIONS.get((binding.method,binding.route))
    if operation is None or operation.purpose!=PURPOSE:return None
    from app.models.platform import CustomFieldDefinition,CustomFieldValue
    from app.models.onboarding import OnboardingTemplate
    if model is OnboardingTemplate:
        return or_(model.organization_id==company,model.organization_id.is_(None)&(company==1))
    if model not in {CustomFieldDefinition,CustomFieldValue}:return None
    from app.models.security_boundary import SecurityResourceOwnership
    from app.models.employee import Employee
    from app.services.employee_custom_fields import role_allowed
    definitions=CustomFieldDefinition.__table__;owners=SecurityResourceOwnership.__table__
    own_definitions=select(owners.c.resource_id).where(owners.c.resource_table==definitions.name,owners.c.company_id==company)
    ids=[row.id for row in db.connection().execute(select(definitions.c.id,definitions.c.visible_to_roles).where(
        definitions.c.id.in_(own_definitions),definitions.c.module.in_(['employee','employees']),definitions.c.is_active.is_(True)))
        if role_allowed(row.visible_to_roles,actor)]
    if model is CustomFieldDefinition:return model.id.in_(ids)
    allowed_employee=employee_predicate()
    return and_(model.entity_type=='employee',model.definition_id.in_(ids),
        model.entity_id.in_(select(Employee.id).where(allowed_employee)))


def native_value_write(db,actor,company,row):
    """Prove the missing polymorphic native parent without a global exemption."""
    from .common_binding import CoreRequestBinding,MARKER
    from .common_core import OPERATIONS,CommonCoreScope
    from app.models.platform import CustomFieldValue,CustomFieldDefinition
    if not isinstance(row,CustomFieldValue):return False
    binding=db.info.get(MARKER)
    if (not isinstance(binding,CoreRequestBinding) or binding.purpose!=PURPOSE or binding.user_id!=actor.id
            or binding.company_id!=company or db.info.get('business_pack_scope') is not None):return False
    operation=OPERATIONS.get((binding.method,binding.route))
    if operation is None or operation.purpose!=PURPOSE or 'custom_field_values' not in operation.writes:return False
    scope=db.info.get('business_common_core_scope')
    if (not isinstance(scope,CommonCoreScope) or scope.binding!=binding or scope.user_id!=actor.id
            or scope.company_id!=company or scope.operation!=operation or scope.operation.purpose!=PURPOSE):return False
    from app.models.employee import Employee
    from app.services.employee_custom_fields import role_allowed
    from app.core.masking import can_view_sensitive_employee
    with db.no_autoflush:
        definition=db.query(CustomFieldDefinition).filter(CustomFieldDefinition.id==row.definition_id,
            CustomFieldDefinition.module.in_(['employee','employees']),CustomFieldDefinition.is_active.is_(True)).first()
        employee=db.query(Employee.id).filter(Employee.id==row.entity_id,Employee.deleted_at.is_(None)).first()
    if (row.entity_type!='employee' or row.updated_by!=actor.id or definition is None or employee is None
            or not role_allowed(definition.visible_to_roles,actor) or not role_allowed(definition.editable_by_roles,actor)
            or (definition.is_sensitive and not can_view_sensitive_employee(actor,row.entity_id))):
        raise HTTPException(403,'Employee custom value lacks its native definition and canonical employee authority')
    return True


def operations(operation):
    return candidate_operations(operation)


def candidate_operations(operation):
    """Complete exact inventory, exercised before publishing route capture."""
    read=operation('view','employee_view',purpose=PURPOSE)
    result={('GET',path):read for path in (
        '/api/v1/employees/','/api/v1/employees/directory','/api/v1/employees/filter-options',
        '/api/v1/employees/reporting-managers','/api/v1/employees/{employee_id}')}
    result[('GET','/api/v1/employees/work-category-options')]=operation('view',None,purpose=PURPOSE)
    result[('GET','/api/v1/employees/directory')]=operation('view',None,purpose=PURPOSE)
    result[('GET','/api/v1/employees/custom-fields/definitions')]=operation('view',('employee_view','employee_create','employee_update'),purpose=PURPOSE)
    result[('POST','/api/v1/employees/duplicate-check')]=operation('view',('employee_create','employee_update'),purpose=PURPOSE)
    result[('PUT','/api/v1/employees/{employee_id}')]=operation('edit','employee_update',
        frozenset({'employees','custom_field_values','audit_logs','field_audit_events','users','email_outbox'}),
        frozenset({'custom_field_values','audit_logs','field_audit_events','email_outbox'}),purpose=PURPOSE)
    result[('POST','/api/v1/employees/')]=operation('create','employee_create',
        frozenset({'employees','custom_field_values','employee_onboardings','employee_onboarding_tasks','users','roles','common_people','common_profiles','email_outbox'}),
        frozenset({'employees','custom_field_values','employee_onboardings','employee_onboarding_tasks','users','roles','common_people','common_profiles','email_outbox'}),purpose=PURPOSE)
    return MappingProxyType(result)


@dataclass
class _Creation:
    actor_id:int
    company_id:int
    scope:object
    values:dict
    employee:object=None
    user:object=None
    role:object=None
    person:object=None
    profile:object=None
    sources:dict=field(default_factory=dict)


@dataclass(frozen=True)
class _Update:
    scope:object
    actor_id:int
    employee:object
    values:object
    role_id:int|None
    touched_at:object=None


@dataclass(frozen=True)
class _RoleFacts:
    identity:int|None
    fingerprint:str


@dataclass(frozen=True)
class _RoleChange:
    scope:object
    employee:object
    user:object
    old_role_id:int|None
    new_role_id:int
    session_id:object
    session_fingerprint:str|None
    tenant:object
    branch:object
    principal_fingerprint:str
    old_role:_RoleFacts
    new_role:_RoleFacts


def _role_facts(connection,identity):
    from app.models.user import Role,Permission,role_permissions
    table=Role.__table__
    role=connection.execute(select(table).where(table.c.id==identity)).first() if identity is not None else None
    if identity is not None and role is None:raise HTTPException(403,'Native target role is unavailable')
    permissions=[tuple(row) for row in connection.execute(select(Permission.__table__.c.id,Permission.__table__.c.name,Permission.__table__.c.module).join(
        role_permissions,role_permissions.c.permission_id==Permission.__table__.c.id).where(role_permissions.c.role_id==identity).order_by(Permission.__table__.c.id))]
    return _RoleFacts(identity,sha256(json.dumps([tuple(role) if role else None,permissions],default=str,separators=(',',':')).encode()).hexdigest())


def _principal_facts(connection,identity):
    from app.models.user import User
    table=User.__table__
    columns=[column for column in table.c if column.name not in {'role_id','updated_at'}]
    row=connection.execute(select(*columns).where(table.c.id==identity)).first()
    if row is None:raise HTTPException(403,'Native principal is unavailable')
    return sha256(json.dumps(tuple(row),default=str,separators=(',',':')).encode()).hexdigest()


def _session_facts(connection,actor):
    identity=getattr(actor,'_suite_session_id',None)
    if identity is None:return None
    from app.models.user import UserSession
    from datetime import datetime,timezone
    table=UserSession.__table__
    row=connection.execute(select(table.c.id,table.c.user_id,table.c.status,table.c.expires_at,table.c.session_token_hash).where(table.c.id==identity)).first()
    expiry=row.expires_at if row else None
    if expiry is not None and expiry.tzinfo is None:expiry=expiry.replace(tzinfo=timezone.utc)
    if row is None or row.user_id!=actor.id or (row.status or '').lower()!='active' or (expiry is not None and expiry<=datetime.now(timezone.utc)):
        raise HTTPException(403,'Native self-role session is unavailable')
    return sha256(json.dumps(tuple(row),default=str,separators=(',',':')).encode()).hexdigest()


@contextmanager
def update_plan(db,actor,employee,values,role_id):
    scope=db.info.get('business_common_core_scope')
    if scope is None or scope.operation.purpose!=PURPOSE:
        yield
        return
    if scope.method!='PUT' or scope.route!='/api/v1/employees/{employee_id}' or scope.user_id!=actor.id:
        raise HTTPException(403,'Native employee update purpose is required')
    if '_native_employee_update' in db.info:raise HTTPException(403,'Native employee update plans cannot nest')
    db.info['_native_employee_update']=_Update(scope,actor.id,employee,MappingProxyType(dict(values)),role_id)
    try:yield
    finally:
        db.info.pop('_native_employee_update',None)


def profile_touch_proof(db,actor,employee):
    scope=db.info.get('business_common_core_scope')
    if scope is None or scope.operation.purpose!=PURPOSE:return
    plan=db.info.get('_native_employee_update')
    if not isinstance(plan,_Update) or plan.scope is not scope or plan.actor_id!=actor.id or plan.employee is not employee:
        raise HTTPException(403,'Native profile touch requires its exact validated update')
    db.info['_native_employee_update']=replace(plan,touched_at=employee.updated_at)


def _native_scalar(column,value,values):
    """Match the existing HTTP ORM normalizer, not a second input contract."""
    from app.core.input_validation import PHONE_FIELDS,normalize_phone,email_address,clean_text
    name=column.name
    if name in PHONE_FIELDS and value not in (None,''):
        return normalize_phone(value,values.get(name+'_country_code'))[0]
    if (name=='email' or name.endswith('_email')) and value not in (None,''):return email_address(value)
    if (name in {'name','title','first_name','last_name','full_name','parent_name'} or name.endswith('_name')) and isinstance(value,str):
        return clean_text(value,getattr(column.type,'length',None) or 500,required=not column.nullable and name!='last_name')
    return value


@contextmanager
def creation_plan(db,actor,data):
    """Installed only by the native endpoint after its original validation.

    This records the exact native request for a one-employee operation; every
    child still requires fresh native authority and canonical source proofs.
    """
    scope=db.info.get('business_common_core_scope')
    if scope is None or scope.operation.purpose!=PURPOSE:
        yield
        return
    if scope.method!='POST' or scope.route!='/api/v1/employees/' or scope.user_id!=actor.id:
        raise HTTPException(403,'Native employee creation purpose is required')
    if '_native_employee_creation' in db.info:raise HTTPException(403,'Employee creation plans cannot nest')
    values=data.model_dump()
    # The existing native branch boundary fills an omitted/null branch on a new
    # employee from this exact verified destination before our flush guard runs.
    # Capture that deterministic native default; never reinterpret explicit IDs.
    if values.get('branch_id') is None and scope.branch.branch_id is not None:
        values['branch_id']=scope.branch.branch_id
    plan=_Creation(actor.id,scope.company_id,scope,MappingProxyType(values))
    db.info['_native_employee_creation']=plan
    try:yield
    finally:db.info.pop('_native_employee_creation',None)


def role_change_proof(db,actor,employee,role_id):
    scope=db.info.get('business_common_core_scope')
    if scope is None or scope.operation.purpose!=PURPOSE:return
    plan=db.info.get('_native_employee_update')
    if not actor.is_superuser or scope.user_id!=actor.id or scope.method!='PUT' or not isinstance(plan,_Update) or plan.scope!=scope or plan.employee is not employee or plan.role_id!=role_id:
        raise HTTPException(403,'Fresh native administrator authority is required for role changes')
    from app.models.user import User
    connection=db.connection()
    current=connection.execute(select(User.__table__.c.is_active,User.__table__.c.is_superuser,User.__table__.c.role_id).where(User.__table__.c.id==actor.id)).first()
    if not current or not current.is_active or not current.is_superuser or current.role_id!=actor.role_id:
        raise HTTPException(403,'Fresh native administrator identity is required for role changes')
    target=employee.user
    db.info['_native_employee_role_change']=_RoleChange(scope,employee,target,target.role_id,role_id,
        getattr(actor,'_suite_session_id',None),_session_facts(connection,actor),db.info.get('tenant_uuid'),db.info.get('branch_context'),_principal_facts(connection,actor.id),
        _role_facts(connection,target.role_id),_role_facts(connection,role_id))


def verify_self_role_transition(db,actor,company,proof,current_user):
    """Authenticate one native SU role command; never an initial-role fallback."""
    from .common_core import CommonCoreScope
    from .common_binding import MARKER
    scope=db.info.get('business_common_core_scope');plan=db.info.get('_native_employee_update')
    if (not isinstance(proof,_RoleChange) or db.info.get('_native_employee_role_change') is not proof
            or not isinstance(scope,CommonCoreScope) or proof.scope is not scope or scope.operation.purpose!=PURPOSE
            or scope.binding!=db.info.get(MARKER) or db.info.get('business_pack_scope') is not None
            or scope.user_id!=actor.id or scope.company_id!=company or proof.user is not actor
            or not isinstance(plan,_Update) or plan.scope is not scope or plan.employee is not proof.employee or plan.role_id!=proof.new_role_id
            or not actor.is_active or not actor.is_superuser or not current_user.is_active or not current_user.is_superuser
            or current_user.role_id not in {proof.old_role_id,proof.new_role_id} or actor.role_id not in {proof.old_role_id,proof.new_role_id}
            or getattr(actor,'_suite_session_id',None)!=proof.session_id or db.info.get('branch_context')!=proof.branch
            or db.info.get('tenant_uuid')!=proof.tenant
            or proof.employee.user_id!=actor.id):
        raise HTTPException(403,'Native self-role transition has no exact endpoint-issued authority')
    connection=db.connection()
    if (_principal_facts(connection,actor.id)!=proof.principal_fingerprint
            or _session_facts(connection,actor)!=proof.session_fingerprint
            or _role_facts(connection,proof.old_role_id)!=proof.old_role or _role_facts(connection,proof.new_role_id)!=proof.new_role):
        raise HTTPException(403,'Native principal or role facts changed outside the authorized self-role command')
    return proof.old_role_id


def install(db,actor,scope):
    from app.business_packs.common_core import deny,_native_authority,_native_operation_access
    from app.business_packs.common_binding import MARKER
    from app.business_packs.models import PackRecordOwnership
    from app.branches.catalog import key_expression,resource_key
    from app.branches.service import context as branch_context
    from app.db.base_class import Base
    from app.models.employee import Employee,EmployeeEducation,EmployeeExperience,EmployeeSkill,EmployeeCertification,EmployeeDocument,EmployeeLifecycleEvent
    from app.models.company import Branch,Company,Department,Designation,CostCenter,BusinessUnit,WorkLocation,GradeBand,Position
    from app.models.attendance import Shift
    from app.models.user import User,Role,Permission,PasswordPolicy,role_permissions
    from app.models.platform import CustomFieldDefinition,CustomFieldValue
    from app.models.onboarding import OnboardingTemplate,OnboardingTemplateTask,EmployeeOnboarding,EmployeeOnboardingTask
    from app.models.audit import AuditLog,FieldAuditEvent
    from app.models.email_outbox import EmailOutbox
    from app.shared.models import ServicePolicy
    from app.common.models import CommonPerson,CommonProfile
    previous=db.info.get('business_common_core_scope')
    if previous is not None:
        if previous!=scope:deny('Common Core context cannot change inside a request')
        return lambda:None
    if db.info.get('business_pack_policy') is not None:deny('Canonical employment cannot mix with private pack authority')
    if db.new or db.deleted or any(db.is_modified(row,include_collections=True) for row in db.dirty):
        deny('Finish pending changes before binding canonical employment')
    ownership=PackRecordOwnership.__table__;inspector=inspect(db.connection())
    has_ownership=inspector.has_table(ownership.name)
    if has_ownership and not {'resource_table','resource_key','company_id','branch_id','context_id'}<={column['name'] for column in inspector.get_columns(ownership.name)}:
        raise HTTPException(503,'Native Core ownership exclusion installation is incomplete')
    def unowned(table):
        return ~exists(select(1).where(ownership.c.resource_table==table.name,ownership.c.resource_key==key_expression(table))).correlate(table) if has_ownership else true()
    company_branches=select(Branch.id).where(Branch.company_id==scope.company_id)
    employee_company=or_(Employee.branch_id.in_(company_branches),Employee.branch_id.is_(None)&(scope.company_id==1))
    employees=select(Employee.id).where(employee_company,unowned(Employee.__table__))
    users=select(Employee.user_id).where(employee_company,unowned(Employee.__table__),Employee.user_id.is_not(None))
    from app.services.employee_custom_fields import role_allowed
    from app.core.masking import can_view_sensitive_employee
    # Fixed definition IDs are safe metadata snapshots; no CRM definitions or
    # values may enter via a coincidentally matching polymorphic entity ID.
    definition_table=CustomFieldDefinition.__table__
    definitions=[{column.name:getattr(row,column.name) for column in definition_table.c}
        for row in db.query(CustomFieldDefinition).filter(CustomFieldDefinition.module.in_(['employee','employees']),CustomFieldDefinition.is_active.is_(True),unowned(definition_table)).all()
        if role_allowed(row.visible_to_roles,actor)]
    permitted_definitions={row['id'] for row in definitions}
    sensitive_definitions={row['id'] for row in definitions if row['is_sensitive']}
    visible_values=and_(CustomFieldValue.entity_type=='employee',CustomFieldValue.entity_id.in_(employees),CustomFieldValue.definition_id.in_(permitted_definitions))
    # Sensitive custom data may be read only for employees native masking permits.
    if not (actor.is_superuser or getattr(actor,'_suite_admin_read',False)):
        from app.access.catalog import permission_names
        if 'employee_sensitive_view' not in permission_names(actor):
            own_ids=select(Employee.id).where(Employee.user_id==actor.id,employee_company)
            visible_values=and_(visible_values,or_(CustomFieldValue.definition_id.not_in(sensitive_definitions),CustomFieldValue.entity_id.in_(own_ids)))
    templates=or_(OnboardingTemplate.organization_id==scope.company_id,OnboardingTemplate.organization_id.is_(None)&(scope.company_id==1))
    template_ids=select(OnboardingTemplate.id).where(templates,unowned(OnboardingTemplate.__table__))
    onboardings=select(EmployeeOnboarding.id).where(EmployeeOnboarding.employee_id.in_(employees),EmployeeOnboarding.template_id.in_(template_ids))
    children={EmployeeEducation,EmployeeExperience,EmployeeSkill,EmployeeCertification,EmployeeDocument,EmployeeLifecycleEvent}
    reads={Employee,Branch,Company,Department,Designation,CostCenter,BusinessUnit,WorkLocation,GradeBand,Position,Shift,User,Role,Permission,PasswordPolicy,CommonPerson,CommonProfile,
        CustomFieldDefinition,CustomFieldValue,OnboardingTemplate,OnboardingTemplateTask,EmployeeOnboarding,EmployeeOnboardingTask,
        AuditLog,FieldAuditEvent,ServicePolicy}|children
    conditions={Employee:and_(employee_company,unowned(Employee.__table__)),Branch:Branch.company_id==scope.company_id,Company:Company.id==scope.company_id,
        Department:Department.branch_id.in_(company_branches),Designation:Designation.department_id.in_(select(Department.id).where(Department.branch_id.in_(company_branches))),
        CostCenter:CostCenter.company_id==scope.company_id,User:or_(User.id==actor.id,User.id.in_(users)),
        CustomFieldDefinition:CustomFieldDefinition.id.in_(permitted_definitions),CustomFieldValue:visible_values,
        OnboardingTemplate:templates,OnboardingTemplateTask:OnboardingTemplateTask.template_id.in_(template_ids),
        EmployeeOnboarding:and_(EmployeeOnboarding.employee_id.in_(employees),EmployeeOnboarding.template_id.in_(template_ids)),
        EmployeeOnboardingTask:EmployeeOnboardingTask.employee_onboarding_id.in_(onboardings),
        AuditLog:false(),FieldAuditEvent:false(),
        ServicePolicy:and_(ServicePolicy.organization_id==scope.company_id,ServicePolicy.kind=='form_defaults',ServicePolicy.module_key.in_(['*','hrms']))}
    conditions.update({BusinessUnit:BusinessUnit.company_id==scope.company_id,WorkLocation:WorkLocation.company_id==scope.company_id,
        Position:Position.company_id==scope.company_id,GradeBand:or_(GradeBand.organization_id==scope.company_id,GradeBand.organization_id.is_(None)&(scope.company_id==1)),
        CommonPerson:and_(CommonPerson.organization_id==scope.company_id,CommonPerson.source_module=='hrms',CommonPerson.source_record_type=='employee',CommonPerson.source_record_id.in_(employees),CommonPerson.user_id.in_(users)),
        CommonProfile:CommonProfile.person_id.in_(select(CommonPerson.id).where(CommonPerson.organization_id==scope.company_id,CommonPerson.source_module=='hrms',CommonPerson.source_record_type=='employee',CommonPerson.source_record_id.in_(employees)))})
    conditions.update({model:model.employee_id.in_(employees) for model in children})
    for model in reads:
        if model not in conditions:conditions[model]=true()
        conditions[model]=and_(conditions[model],unowned(model.__table__))
    def query_options():
        plan=db.info.get('_native_employee_creation')
        extra=None
        person_identity=inspect(plan.person).identity if isinstance(plan,_Creation) and plan.person is not None else None
        user_identity=inspect(plan.user).identity if isinstance(plan,_Creation) and plan.user is not None else None
        if isinstance(plan,_Creation) and plan.scope==scope and actor.is_superuser and person_identity and user_identity:
            extra=and_(CommonPerson.id==person_identity[0],CommonPerson.user_id==user_identity[0],CommonPerson.organization_id==scope.company_id,unowned(CommonPerson.__table__))
        return tuple(with_loader_criteria(mapper.class_,or_(conditions[CommonPerson],extra) if mapper.class_ is CommonPerson and extra is not None else conditions.get(mapper.class_,false()),include_aliases=True,propagate_to_loaders=False) for mapper in Base.registry.mappers)
    identity_table=Employee.__table__
    baseline={row[0]:tuple(row) for row in db.connection().execute(select(*(identity_table.c[name] for name in IDENTITY_FIELDS)).where(
        or_(identity_table.c.branch_id.in_(select(Branch.__table__.c.id).where(Branch.__table__.c.company_id==scope.company_id)),identity_table.c.branch_id.is_(None)&(scope.company_id==1))))}
    authority=scope.native_authority;pending={};checking=False;trusted_identity_load=False;completed_role=None
    def self_role_proof():
        proof=db.info.get('_native_employee_role_change')
        return proof if isinstance(proof,_RoleChange) and proof.user is actor and proof is not completed_role else None
    def transition_maps():
        before={};expected={}
        for row,values in pending.values():
            if row.id is None:continue
            actual=tuple(getattr(row,name) for name in IDENTITY_FIELDS)
            if actual[1:]!=values:deny('Canonical employee identity changed after native validation')
            before[row.id]=baseline.get(row.id)
            expected[row.id]=actual
        return before,expected
    def fresh():
        nonlocal checking
        if checking:return
        checking=True
        try:
            if (actor.id!=scope.user_id or actor.organization_id!=scope.company_id or db.info.get('branch_context')!=scope.branch
                    or db.info.get('business_pack_scope') is not None or db.info.get(MARKER)!=scope.binding):
                deny('Canonical employment request authority changed')
            selected=str(scope.branch.branch_id) if scope.branch.branch_id is not None else 'all' if scope.branch.all_branches else None
            if branch_context(db,actor,scope.company_id,selected)!=scope.branch:deny('Native branch authority changed during employment operation')
            before,expected=transition_maps()
            arguments={}
            if before:arguments.update(employee_before=before,employee_expected=expected)
            proof=self_role_proof()
            if proof is not None:arguments['role_transition']=proof
            candidate=_native_authority(db,actor,scope.company_id,**arguments)
            if candidate!=authority:deny('Native employment authority changed; reload before continuing')
            _native_operation_access(db,actor,scope.company_id,scope.operation)
        finally:checking=False
    def restrict(execution):
        if checking:return
        fresh()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:
            deny('Canonical employment requires validated native per-record ORM operations')
        if execution.bind_mapper is not None and execution.bind_mapper.class_ not in reads:deny('Table is outside canonical employment purpose')
        from .common_queries import assert_mapped_sources
        assert_mapped_sources(execution.statement,reads,trusted_identity=trusted_identity_load,allowed_associations=(role_permissions,))
        if execution.bind_mapper is not None and execution.bind_mapper.class_ is PasswordPolicy:
            plan=db.info.get('_native_employee_creation')
            if not actor.is_superuser or not isinstance(plan,_Creation) or not plan.values.get('create_user_account'):
                deny('Password policy metadata is only available to native employee account creation')
        if not trusted_identity_load and not execution.is_column_load and not execution.is_relationship_load:
            stars=_count_stars(execution.statement)
            for node in visitors.iterate(execution.statement):
                if isinstance(node,TextClause):deny('Canonical employment does not accept textual SQL')
                if isinstance(node,ColumnClause) and ((getattr(node,'is_literal',False) and id(node) not in stars)
                    or (getattr(node,'table',None) is not None and not (node._annotations.get('parententity') or node._annotations.get('parentmapper')))):
                    deny('Canonical employment does not accept raw SQL columns')
        inherited={id(option) for option in getattr(execution.statement,'_with_options',())}
        execution.statement=execution.statement.options(*(option for option in query_options() if id(option) not in inherited))
        execution.update_execution_options(compiled_cache=None)
    def validate(session,*args):
        fresh()
        for row in session.new|session.dirty|session.deleted:
            if row not in session.new and row not in session.deleted and not session.is_modified(row,include_collections=True):continue
            state=inspect(row);table=state.mapper.local_table
            if table.name not in scope.operation.writes or row in session.deleted or (row in session.new and table.name not in scope.operation.creates):
                deny('This canonical employee action cannot mutate that native record')
            if has_ownership and state.identity and db.connection().scalar(select(exists().where(ownership.c.resource_table==table.name,ownership.c.resource_key==resource_key(table,{key.name:getattr(row,key.name) for key in table.primary_key})))):
                deny('Private pack records cannot become canonical employment')
            if row not in session.new and any(state.attrs[key.name].history.has_changes() for key in table.primary_key):deny('Canonical employee record identity is immutable')
            if isinstance(row,Employee):
                plan=db.info.get('_native_employee_creation')
                if row in session.new:
                    if not isinstance(plan,_Creation) or plan.scope!=scope or plan.actor_id!=actor.id:deny('Native employee creation source is required')
                    if plan.employee is not None and plan.employee is not row:deny('One native request creates exactly one employee')
                    plan.employee=row
                    if row.user_id is not None and (plan.user is None or row.user_id!=plan.user.id):deny('New employee account must be its exact native created user')
                    for column in table.c:
                        if column.name in plan.values and column.name!='employee_id':
                            if getattr(row,column.name)!=_native_scalar(column,plan.values[column.name],plan.values):deny('New canonical employee differs from its validated native input')
                    if plan.values.get('employee_id') and row.employee_id!=plan.values['employee_id']:deny('Native employee code differs from its validated source')
                    provided={attribute.key for attribute in state.mapper.column_attrs if state.attrs[attribute.key].history.has_changes()}
                    if provided-(set(plan.values)&set(table.c.keys()))-{'employee_id','user_id'}:deny('Native employee creation has unvalidated scalar changes')
                else:
                    update=db.info.get('_native_employee_update')
                    if not isinstance(update,_Update) or update.scope is not scope or update.actor_id!=actor.id or update.employee is not row:
                        deny('Canonical employee changes require their exact endpoint-validated patch')
                    for attribute in state.mapper.column_attrs:
                        if not state.attrs[attribute.key].history.has_changes():continue
                        if attribute.key=='updated_at':
                            if update.touched_at is None or row.updated_at!=update.touched_at:deny('Native employee timestamp touch differs from its exact source')
                        elif attribute.key not in update.values or getattr(row,attribute.key)!=_native_scalar(table.c[attribute.key],update.values[attribute.key],update.values):
                            deny('Canonical employee scalar changed outside its validated patch')
                    from app.core.masking import SENSITIVE_EMPLOYEE_FIELDS
                    if any(state.attrs[name].history.has_changes() for name in SENSITIVE_EMPLOYEE_FIELDS if name in table.c) and not can_view_sensitive_employee(actor,row.id):
                        deny('Native sensitive employee field authority is required')
                if row not in session.new and state.attrs.user_id.history.has_changes():deny('Account linking requires its separately audited native action')
                changes={name for name in IDENTITY_FIELDS[1:] if state.attrs[name].history.has_changes()}
                native_grants=getattr(actor,'_suite_grants',None)
                native_scope=native_grants.get('hrms',{}).get('scope') if native_grants is not None else None
                native_employee=getattr(actor,'employee',None)
                old=dict(zip(IDENTITY_FIELDS,baseline.get(row.id,tuple(getattr(row,name) for name in IDENTITY_FIELDS))))
                if not actor.is_superuser:
                    changes_team=(native_scope=='team' and row.user_id is not None and native_employee is not None
                        and 'reporting_manager_id' in changes and native_employee.id in {old['reporting_manager_id'],row.reporting_manager_id})
                    changes_department=(native_scope=='department' and native_employee is not None and 'department_id' in changes
                        and (row.user_id==actor.id or native_employee.department_id in {old['department_id'],row.department_id}))
                    changes_branch=(native_scope=='branch' and native_employee is not None and 'branch_id' in changes
                        and (row.user_id==actor.id or native_employee.branch_id in {old['branch_id'],row.branch_id}))
                    if changes_team or changes_department or changes_branch:
                        deny('Employee identity changes affecting compiled native scope require a fresh separate action')
                    if row.user_id==actor.id and 'branch_id' in changes and not scope.branch.all_branches:
                        from app.branches.models import BranchGrant
                        grants=set(db.connection().scalars(select(BranchGrant.__table__.c.branch_id).where(BranchGrant.__table__.c.company_id==scope.company_id,BranchGrant.__table__.c.user_id==actor.id)))
                        if old['branch_id'] not in grants or row.branch_id not in grants:
                            deny('Employee branch changes affecting the current native realm require a fresh separate action')
                pending[id(row)]=(row,tuple(getattr(row,name) for name in IDENTITY_FIELDS[1:]))
            elif isinstance(row,(User,Role,CommonPerson,CommonProfile)):
                _validate_identity(db,actor,scope,row,session)
            elif isinstance(row,EmployeeOnboarding):
                plan=db.info.get('_native_employee_creation')
                if not isinstance(plan,_Creation) or plan.employee is None or row.employee_id!=plan.employee.id or row.created_by!=actor.id:
                    deny('Onboarding must derive from the exact native created employee')
                if row not in session.new:
                    source=plan.sources.get(id(row))
                    if source is None or source[0] is not row:deny('Employee creation cannot change historical onboarding')
                    changed={attribute.key for attribute in state.mapper.column_attrs if state.attrs[attribute.key].history.has_changes()}
                    if changed-{'status','completion_percentage'}:deny('Only native progress of this newly created onboarding may change')
                    tasks=session.query(EmployeeOnboardingTask).filter(EmployeeOnboardingTask.employee_onboarding_id==row.id).all()
                    if any(id(task) not in plan.sources for task in tasks):deny('Native new-onboarding progress has an unvalidated task source')
                    from types import SimpleNamespace
                    from app.crud.crud_onboarding import refresh_onboarding_progress
                    expected=SimpleNamespace(tasks=tasks,status=row.status,completion_percentage=row.completion_percentage)
                    refresh_onboarding_progress(expected)
                    if row.status!=expected.status or row.completion_percentage!=expected.completion_percentage:deny('Native onboarding progress differs from its actual created tasks')
                if not session.query(OnboardingTemplate.id).filter(OnboardingTemplate.id==row.template_id,OnboardingTemplate.is_active.is_(True)).first():deny('Onboarding template is not native company configuration')
                plan.sources[id(row)]=(row,{column.name:getattr(row,column.name) for column in table.c if column.name not in {'id','created_at','updated_at'}})
            elif isinstance(row,EmployeeOnboardingTask):
                plan=db.info.get('_native_employee_creation')
                parent=session.query(EmployeeOnboarding).filter(EmployeeOnboarding.id==row.employee_onboarding_id).first()
                template=session.query(OnboardingTemplateTask).filter(OnboardingTemplateTask.id==row.template_task_id).first()
                if row not in session.new or not isinstance(plan,_Creation) or plan.employee is None or parent is None or template is None or parent.employee_id!=plan.employee.id or template.template_id!=parent.template_id:
                    deny('Onboarding task requires its exact native employee and template source')
                from app.crud.crud_onboarding import assign_task_user_id
                if row.assigned_to_user_id!=assign_task_user_id(session,plan.employee,template.assigned_to_role) or row.task_name!=template.task_name or row.category!=template.category:
                    deny('Onboarding delivery identity differs from its native template')
                plan.sources[id(row)]=(row,{column.name:getattr(row,column.name) for column in table.c if column.name not in {'id','created_at','updated_at'}})
            elif isinstance(row,EmailOutbox):
                from .employee_email import validate as validate_email
                validate_email(db,row)
            elif isinstance(row,CustomFieldValue):
                if not native_value_write(db,actor,scope.company_id,row):deny('Native employee custom value source proof is required')
                if row not in session.new and any(state.attrs[name].history.has_changes() for name in ('definition_id','entity_type','entity_id')):deny('Employee custom field ownership is immutable')
            elif isinstance(row,AuditLog):
                if row not in session.new or row.user_id!=actor.id or row.entity_type!='employee' or not session.query(Employee.id).filter(Employee.id==row.entity_id).first():deny('Only native employee audit creation is permitted')
            elif isinstance(row,FieldAuditEvent):
                if row not in session.new or row.actor_user_id!=actor.id or row.module!='employee' or not session.query(Employee.id).filter(Employee.id==row.employee_id).first():deny('Only native employee field audit creation is permitted')
            with session.no_autoflush:
                for column in table.c:
                    value=getattr(row,column.name)
                    if value is None:continue
                    for fk in column.foreign_keys:
                        parent={mapper.local_table.name:mapper.class_ for mapper in Base.registry.mappers}.get(fk.column.table.name)
                        if parent not in reads:deny('Unreviewed employee native parent')
                        if isinstance(row,(User,Role,CommonPerson,CommonProfile)):
                            # Exact one-source identity validation above proves
                            # new generated parents before they become readable.
                            continue
                        if parent is User and column.name in {'updated_by','created_by','actor_user_id','user_id'} and not isinstance(row,Employee):
                            if value!=actor.id:deny('Native employee sideeffect actor differs')
                            continue
                        if parent is User and isinstance(row,Employee):
                            plan=db.info.get('_native_employee_creation')
                            if isinstance(plan,_Creation) and plan.user is not None and value==plan.user.id:continue
                        if parent is User and isinstance(row,EmployeeOnboardingTask) and column.name=='assigned_to_user_id':continue
                        attr=getattr(parent,inspect(parent).get_property_by_column(fk.column).key)
                        if not session.query(attr).filter(attr==value).first():deny('Employee parent is outside native scope')
    def advanced(session,*args):
        nonlocal authority,completed_role
        proof=self_role_proof()
        if not pending and proof is None:return
        fresh()
        for row,_ in pending.values():
            expected=tuple(getattr(row,name) for name in IDENTITY_FIELDS)
            actual=db.connection().execute(select(*(identity_table.c[name] for name in IDENTITY_FIELDS)).where(identity_table.c.id==row.id)).first()
            if actual is None or tuple(actual)!=expected:deny('Canonical employee flush did not match its exact authorized identity transition')
            baseline[row.id]=expected
        if proof is not None:
            from app.models.user import User
            actual=db.connection().execute(select(User.__table__.c.role_id,User.__table__.c.is_active,User.__table__.c.is_superuser).where(User.__table__.c.id==actor.id)).first()
            if actual is None or actual.role_id!=proof.new_role_id or not actual.is_active or not actual.is_superuser:
                deny('Native self-role flush did not match its exact authorized principal transition')
            completed_role=proof
            db.expire(actor,['role'])
        authority=_native_authority(db,actor,scope.company_id)
        pending.clear()
    fresh()
    original_get,original_refresh=db.get,db.refresh
    def visible(model,identity):
        fresh();mapper=inspect(model,raiseerr=False);model=getattr(mapper,'class_',model)
        if model not in reads:return False
        keys=inspect(model).primary_key
        values=[identity.get(key.key) for key in keys] if isinstance(identity,dict) else list(identity) if isinstance(identity,(tuple,list)) else [identity]
        if len(values)!=len(keys):return False
        attrs=[getattr(model,inspect(model).get_property_by_column(key).key) for key in keys]
        with db.no_autoflush:return db.query(*attrs).filter(*(attr==value for attr,value in zip(attrs,values))).first() is not None
    def scoped_get(model,identity,**kwargs):
        nonlocal trusted_identity_load
        if not visible(model,identity):return None
        previous=trusted_identity_load;trusted_identity_load=True
        try:return original_get(model,identity,**kwargs)
        finally:trusted_identity_load=previous
    def scoped_refresh(row,*args,**kwargs):
        nonlocal trusted_identity_load
        if not visible(type(row),inspect(row).identity):deny('Cached record is outside canonical employment authority')
        previous=trusted_identity_load;trusted_identity_load=True
        try:return original_refresh(row,*args,**kwargs)
        finally:trusted_identity_load=previous
    original_bulk={name:getattr(db,name) for name in ('bulk_insert_mappings','bulk_update_mappings','bulk_save_objects')}
    def reject_bulk(*args,**kwargs):deny('Employee bulk mutation requires a separate native adapter')
    for name in original_bulk:setattr(db,name,reject_bulk)
    for state in list(db.identity_map.all_states()):
        if state.class_ in reads-{User,Role,Permission} and state.obj() is not None:db.expire(state.obj())
    db.get,db.refresh=scoped_get,scoped_refresh
    db.info['business_common_core_scope']=scope
    event.listen(db,'do_orm_execute',restrict);event.listen(db,'before_flush',validate);event.listen(db,'after_flush_postexec',advanced)
    closed=False
    def cleanup():
        nonlocal closed
        if closed:return
        closed=True
        event.remove(db,'do_orm_execute',restrict);event.remove(db,'before_flush',validate);event.remove(db,'after_flush_postexec',advanced)
        db.get,db.refresh=original_get,original_refresh
        for name,method in original_bulk.items():setattr(db,name,method)
        db.info.pop('business_common_core_scope',None)
        db.info.pop('_native_employee_role_change',None)
    return cleanup


def _validate_identity(db,actor,scope,row,session):
    """Narrow native SU/account side effects; never general account authority."""
    from app.business_packs.common_core import deny
    from app.models.user import User,Role
    from app.common.models import CommonPerson,CommonProfile
    from app.core.security import verify_password
    current=db.connection().execute(select(User.__table__.c.is_active,User.__table__.c.is_superuser).where(User.__table__.c.id==actor.id)).first()
    if not actor.is_superuser or not current or not current.is_active or not current.is_superuser:deny('Employee account side effects require fresh native superuser authority')
    state=inspect(row)
    changed={attribute.key for attribute in state.attrs if attribute.history.has_changes()}
    proof=db.info.get('_native_employee_role_change')
    if isinstance(row,User) and row not in session.new:
        plan=db.info.get('_native_employee_creation')
        if isinstance(plan,_Creation) and row is plan.user and changed<={'employee','person'} and (not row.employee or row.employee is plan.employee) and row.person is plan.person:return
        if not isinstance(proof,_RoleChange) or proof.scope is not scope or proof.user is not row or row.role_id!=proof.new_role_id or not changed<={'role_id','role'}:deny('Only the native authorized employee account role may change')
        return
    plan=db.info.get('_native_employee_creation')
    if not isinstance(plan,_Creation) or plan.scope!=scope or plan.actor_id!=actor.id or not plan.values.get('create_user_account'):
        deny('Native employee account creation source is required')
    if row not in session.new and not (isinstance(row,CommonPerson) and row is plan.person):
        deny('Employee creation cannot retarget an existing canonical identity')
    role_name='intern' if plan.values['employment_type'].strip().lower()=='intern' else 'employee'
    if isinstance(row,Role):
        if plan.role is not None and plan.role is not row:deny('One employee creation cannot create multiple login roles')
        if row.name!=role_name or not row.is_system or row.permissions or not changed<={'name','description','is_system'}:deny('Only the native unprivileged default employee role may be created')
        plan.role=row
    elif isinstance(row,User):
        if plan.user is not None and plan.user is not row:deny('One employee creation cannot create multiple users')
        role=session.query(Role).filter(Role.id==row.role_id,Role.name==role_name).first()
        if role is None:deny('Native employee default role is unavailable')
        if row.email!=plan.values.get('user_email') or not row.is_active or row.is_superuser:deny('Native created employee account identity differs from the validated request')
        if not verify_password(plan.values.get('user_password') or '',row.hashed_password):deny('Native employee password does not match its validated source')
        if not changed<={'email','hashed_password','is_active','role_id','person'}:deny('Unreviewed fields on native employee account')
        if 'person' in changed and (row.person is None or row.person not in session.new or row.person.user is not row or row.person.organization_id!=scope.company_id or row.person.primary_email!=row.email):
            deny('Native account automatic person must belong to the exact new user')
        plan.user=row
    elif isinstance(row,CommonPerson):
        if plan.person is not None and plan.person is not row:deny('One employee creation cannot create multiple shared people')
        employee=plan.employee
        if plan.user is None or row.organization_id!=scope.company_id or row.primary_email!=plan.user.email:
            deny('Shared identity must derive from the exact native employee account')
        if employee is None:
            if row not in session.new or row.user is not plan.user or row.source_module or row.source_record_type or row.source_record_id or row.display_name!=plan.user.email:
                deny('Provisional native identity must come from automatic new-account binding')
        elif row.user_id!=plan.user.id or row.source_module!='hrms' or row.source_record_type!='employee' or row.source_record_id!=employee.id:
            deny('Shared identity source must be the exact canonical employee')
        elif row.display_name!=' '.join(part for part in (employee.first_name,employee.last_name) if part).strip():
            deny('Shared identity name must match its canonical employee')
        if not changed<={'user','user_id','organization_id','primary_email','display_name','phone_number','phone_number_country_code','source_module','source_record_type','source_record_id','profile'}:
            deny('Unreviewed native shared identity fields')
        plan.person=row
    elif isinstance(row,CommonProfile):
        if plan.profile is not None and plan.profile is not row:deny('One employee creation cannot create multiple shared profiles')
        if plan.person is None or row.person_id!=plan.person.id or row.profile_data_json or row.skills_json:deny('Shared profile must derive from its exact new native person')
        if plan.employee is None or any(getattr(row,name)!=getattr(plan.employee,name) for name in ('preferred_display_name','profile_photo_url','bio','timezone','directory_visibility')):
            deny('Shared profile defaults must match the exact canonical source employee')
        if not changed<={'person_id','preferred_display_name','profile_photo_url','bio','timezone','directory_visibility','person'}:deny('Unreviewed native shared profile fields')
        plan.profile=row


def _count_stars(statement):
    """Only scoped ORM Query.count() structural wrappers admit count(*)."""
    columns,sources=getattr(statement,'_raw_columns',()),getattr(statement,'_from_obj',())
    if not (len(columns)==len(sources)==1 and isinstance(columns[0],CountFunction) and not statement._where_criteria):return set()
    arguments=list(columns[0].clauses);inner=sources[0]
    while isinstance(inner,(Alias,Subquery)):inner=inner.element
    if not (len(arguments)==1 and isinstance(arguments[0],ColumnClause) and arguments[0].is_literal and arguments[0].name=='*' and isinstance(inner,Select)):return set()
    nodes=tuple(visitors.iterate(inner));mapped=[node._deannotate() for node in nodes if isinstance(node,FromClause) and (node._annotations.get('parententity') or node._annotations.get('parentmapper'))]
    # assert_mapped_sources has already checked every SELECT independently,
    # including typed ID subqueries; their inferred FROM may be a plain Table.
    return {id(arguments[0])} if mapped and inner._propagate_attrs.get('compile_state_plugin')=='orm' else set()
