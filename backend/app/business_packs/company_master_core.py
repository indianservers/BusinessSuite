"""Native canonical CRM company master, independent of operational packs."""
from types import MappingProxyType
from fastapi import HTTPException

PURPOSE='crm.company_master'
READ=frozenset({'crm_view','crm_manage','crm_admin','crm_companies_view','crm_companies_manage','crm_accounts_view','crm_accounts_manage'})
WRITE=frozenset({'crm_manage','crm_admin','crm_companies_manage','crm_accounts_manage'})


def operations(operation):
    return candidate_operations(operation)


def candidate_operations(operation):
    reads=('/api/v1/master-data/form-options','/api/v1/master-data/companies/custom-fields',
        '/api/v1/master-data/companies','/api/v1/master-data/company-directory/query','/api/v1/master-data/companies/{ident}',
        '/api/v1/master-data/contacts','/api/v1/master-data/duplicates/check')
    result={('GET',path):operation('view',tuple(sorted(READ)),purpose=PURPOSE,module='crm') for path in reads}
    result[('POST','/api/v1/master-data/companies')]=operation('create',tuple(sorted(WRITE)),purpose=PURPOSE,module='crm')
    return MappingProxyType(result)



from contextlib import contextmanager
from dataclasses import dataclass,field
from hashlib import sha256
from weakref import WeakKeyDictionary
import json
from sqlalchemy import and_,or_,event,exists,false,inspect,select,true
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import ColumnClause,TextClause

_births=WeakKeyDictionary()
_scopes=WeakKeyDictionary()
_financial_reads=WeakKeyDictionary()


def _normalized_input(data):
    # Reuse exact native pure normalizers for the few fields write_company
    # itself normalizes in-place; all other submitted values remain bound.
    value=data.model_dump(mode='json')
    from app.core.input_validation import clean_text
    value['name']=clean_text(value['name'],180)
    from app.core.business_validation import website,business_type,registration
    value['website']=website(value.get('website'))
    if value.get('businessType') and value['businessType']!='Individual':
        value['businessType']=business_type(value['businessType'])
    country=value.get('country') or 'IN'
    if country=='India':country='IN'
    if country in {'UAE','United Arab Emirates'}:country='AE'
    for item in value['taxRegistrations']:
        item['number']=registration(item.get('type','Other'),item.get('number'),item.get('country') or country)
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _input(data):
    try:return _normalized_input(data)
    except ValueError as error:raise HTTPException(422,str(error)) from None


@dataclass
class _Birth:
    actor:object
    scope:object
    payload:object
    digest:str
    root:object=None
    born:set=field(default_factory=set)
    complete:bool=False


def _active(db,actor=None):
    plan=_births.get(db)
    if plan is None:return None
    if actor is not None and plan.actor is not actor:
        raise HTTPException(403,'Native Company creation actor changed')
    if db.info.get('business_common_core_scope') is not plan.scope or _input(plan.payload)!=plan.digest:
        raise HTTPException(403,'Native Company creation payload or scope changed')
    return plan


@contextmanager
def creation(db,actor,data,source):
    scope=db.info.get('business_common_core_scope')
    if scope is None or scope.operation.purpose!=PURPOSE:
        yield None
        return
    from app.shared.master_data import CompanyInput,authorize
    from app.core.company_writer import lock_company_writer
    if (source!='crm' or type(data) is not CompanyInput or scope.method!='POST' or
            scope.route!='/api/v1/master-data/companies' or db in _births or data.version is not None):
        raise HTTPException(403,'An exact new canonical CRM Company input is required')
    authorize(actor,'crm',True,action='create')
    fresh=db.info['_company_master_fresh'];fresh()
    lock_company_writer(db,scope.company_id)
    fresh()
    plan=_Birth(actor,scope,data,_input(data));_births[db]=plan
    try:
        yield plan
        if not plan.complete:
            raise HTTPException(409,'Native Company creation did not complete')
    except BaseException:
        db.rollback()
        raise
    finally:
        _births.pop(db,None)


def finish(db,actor,plan,row):
    if plan is None:return
    if _active(db,actor) is not plan or plan.root is not row or inspect(row).session is not db or not inspect(row).persistent:
        raise HTTPException(403,'Native Company creation source differs from its actual birth')
    db.flush()
    _validate_root(plan,final=True)
    plan.complete=True


def native_scope_projection(db,actor):
    """Exact current-actor CRM authorization metadata, never an HR body grant."""
    current=_scopes.get(db)
    if current is None:return None
    owner,scope=current
    from .common_binding import CoreRequestBinding,MARKER
    from .common_core import OPERATIONS,_native_authority
    state=inspect(actor,raiseerr=False)
    if (owner is not actor or state is None or not state.persistent or state.session is not db or
            db.info.get('business_common_core_scope') is not scope or db.info.get(MARKER) is not scope.binding or
            not isinstance(scope.binding,CoreRequestBinding) or scope.binding.purpose!=PURPOSE or
            OPERATIONS.get((scope.method,scope.route)) is not scope.operation or
            scope.user_id!=actor.id or scope.company_id!=actor.organization_id or
            db.info.get('business_pack_scope') is not None or db.info.get('branch_context')!=scope.branch):
        raise HTTPException(403,'A genuine Company master native authorization binding is required')
    if _native_authority(db,actor,scope.company_id)!=scope.native_authority:
        raise HTTPException(403,'Native Company authorization changed')
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.apps.crm.models import CRMOwner,CRMTeam
    from app.branches.boundary import _read_guards
    models=(Employee,CRMOwner,CRMTeam)
    selected=(scope.branch.branch_id,) if scope.branch.branch_id else tuple(sorted(scope.branch.allowed))
    guards,_=_read_guards(tuple(sorted((model.__tablename__,model) for model in models)),actor.id,
        scope.company_id,scope.branch.branch_id,selected,scope.branch.superuser,False,scope.branch.company_admin)
    connection=db.connection()
    person=connection.execute(select(Employee.branch_id,Employee.department_id).where(Employee.user_id==actor.id,
        or_(Employee.branch_id.in_(select(Branch.id).where(Branch.company_id==scope.company_id)),
            and_(Employee.branch_id.is_(None),scope.company_id==1)),guards.get(Employee,true())).limit(1)).first()
    teams=connection.scalars(select(CRMOwner.team_id).join(CRMTeam,CRMTeam.id==CRMOwner.team_id).where(
        CRMOwner.user_id==actor.id,CRMOwner.organization_id==scope.company_id,CRMTeam.organization_id==scope.company_id,
        CRMOwner.status=='Active',CRMOwner.deleted_at.is_(None),CRMTeam.status=='Active',CRMTeam.deleted_at.is_(None),
        guards.get(CRMOwner,true()),guards.get(CRMTeam,true())))
    from app.apps.crm.api.router import _crm_role_key
    return {'role':_crm_role_key(actor),'branch_id':person.branch_id if person else None,
        'department_id':person.department_id if person else None,'team_ids':sorted({value for value in teams if value})}


def _identity(row):
    state=inspect(row)
    return state.identity[0] if state.identity is not None else row.__dict__.get('id')


@contextmanager
def profile_financial_read(db,actor,row,ident):
    scope=db.info.get('business_common_core_scope')
    if scope is None or scope.operation.purpose!=PURPOSE:
        yield
        return
    from app.apps.crm.models import CRMCompany
    from app.access.catalog import permission_names
    from app.access.service import check_background_access
    from app.module_registry import is_app_enabled
    from .common_core import deny
    current=_scopes.get(db)
    if (current is None or current[0] is not actor or current[1] is not scope or
            scope.method!='GET' or scope.route!='/api/v1/master-data/companies/{ident}' or
            type(row) is not CRMCompany or inspect(row).session is not db or not inspect(row).persistent or
            row in db.dirty or row in db.deleted or type(ident) is not int or inspect(row).identity!=(ident,) or
            db in _financial_reads):
        deny('Company financial projection requires its actual native profile source')
    db.info['_company_master_fresh']()
    grant=(getattr(actor,'_suite_grants',None) or {}).get('fam',{})
    if not (actor.is_superuser or grant.get('enabled') and 'view' in grant.get('actions',()) and grant.get('scope') in {'organization','all'}):
        deny('Actual native accounting view is required')
    if not is_app_enabled('fam') or not is_app_enabled('srm'):deny('Native accounting application is unavailable')
    if not (getattr(actor,'_suite_admin_read',False) and db.info.get('admin_read_company')==scope.company_id):
        check_background_access(db,actor,'fam','view')
    # Genuine company-administrator read is independently revalidated by
    # fresh() using native membership; preserve the canonical profile's
    # administrative read rather than inventing a worker-only FAM ceiling.
    from app.shared.master_data import companies
    if companies(db,actor,'crm').with_entities(CRMCompany.id).filter(CRMCompany.id==ident).first() is None:
        deny('Native Company profile is unavailable')
    names=permission_names(actor)
    allowed={'fam_parties':frozenset({'id'}),'fam_srm_mapping':frozenset({'fam_record_id'})}
    if actor.is_superuser or names.intersection({'fam_admin','fam_purchase_view','fam_purchase_manage'}):
        allowed['fam_purchase_bills']=frozenset({'id','bill_number','bill_date','grand_total','status'})
    if actor.is_superuser or names.intersection({'fam_admin','fam_ap_view','fam_ap_manage'}):
        allowed['fam_bill_references']=frozenset({'outstanding_amount'})
    _financial_reads[db]=(actor,scope,ident,allowed)
    try:yield
    finally:_financial_reads.pop(db,None)


def _financial_models(db):
    from app.apps.fam.models import FAMParty,FAMSRMMapping,FAMPurchaseBill,FAMBillReference
    active=_financial_reads.get(db)
    if active is None:return set()
    return {model for model in (FAMParty,FAMSRMMapping,FAMPurchaseBill,FAMBillReference) if model.__tablename__ in active[3]}


def _financial_projection(db,statement):
    active=_financial_reads.get(db)
    if active is None:return
    from sqlalchemy.sql.selectable import Select,FromClause
    from .common_core import deny
    names={'fam_parties','fam_srm_mapping','fam_purchase_bills','fam_bill_references'}
    for query in visitors.iterate(statement):
        if not isinstance(query,Select):continue
        for selected in query._raw_columns:
            for item in visitors.iterate(selected):
                mapper=item._annotations.get('parentmapper')
                if mapper is None:continue
                table=mapper.local_table.name
                if table not in names:continue
                # Native Company profile exposes scalar summaries only, never a
                # full entity/aliased entity or unrelated financial payload.
                if isinstance(item,FromClause) or getattr(item,'name',None) not in active[3].get(table,()):
                    deny('Only the exact linked Company financial scalar projection is supported')


def _validate_root(plan,*,final=False):
    from app.shared.master_data import ROLES
    from app.core.input_validation import email_address,normalize_phone
    row=plan.root;data=plan.payload
    if row is None:raise HTTPException(403,'Canonical Company root is missing')
    if (row.organization_id,row.owner_user_id,row.created_by_user_id,row.name)!=(plan.scope.company_id,plan.actor.id,plan.actor.id,data.name):
        raise HTTPException(403,'Canonical Company identity differs from its validated input')
    target=next((role for role in ('Customer','Vendor','Supplier','Partner','Prospect') if role in data.roles),'Other')
    if set(data.roles)-ROLES:raise HTTPException(422,'Unsupported business relationship role')
    expected={'email':email_address(data.email) if data.email else None,
        'phone':normalize_phone(data.phone,data.phone_country_code)[0] if data.phone else None,
        'phone_country_code':data.phone_country_code if data.phone else None,'website':data.website,
        'industry':data.industry,'status':data.status,'notes':data.notes,'account_type':target}
    final_values=dict(expected)
    if data.communicationChannels is not None:
        from app.shared.master_data import channel_values
        channels=[channel_values(item) for item in data.communicationChannels]
        for kind in ('email','phone'):
            subset=[item for item in channels if item['kind']==kind]
            primary=next((item for item in subset if item['is_primary']),subset[0] if subset else None)
            final_values[kind]=primary['value'] if primary else None
            if kind=='phone':final_values['phone_country_code']=primary['country_code'] if primary else None
    for name,value in expected.items():
        actual=getattr(row,name)
        allowed=(final_values[name],) if final else (None,value,'Prospect') if name=='account_type' else (None,value,final_values[name])
        if actual not in allowed:raise HTTPException(403,'Company scalar differs from its canonical input')
    if row.deleted_at is not None:raise HTTPException(403,'A new Company cannot be archived during birth')


def _validate_writes(db,actor,scope,session):
    from .common_core import deny
    from app.apps.crm.models import CRMCompany,CRMContact,CRMCustomFieldValue
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.shared.master_data_models import CompanyMasterDetails,BusinessRelationship,CompanyContactLink,ContactChannel
    from app.apps.crm.financial_models import ContactFinancialProfile
    from app.models.audit import AuditLog
    changes=set(session.new)|set(session.deleted)|{row for row in session.dirty if session.is_modified(row,include_collections=True)}
    if not changes:return
    plan=_active(db,actor)
    if plan is None or scope.method!='POST':deny('Company master mutations require their exact canonical creation command')
    roots=[row for row in changes if type(row) is CRMCompany]
    for row in roots:
        if plan.root is None:
            if row not in session.new or row.id is not None:deny('Existing Company adoption is not a Company birth')
            plan.root=row;plan.born.add(row)
        if row is not plan.root:deny('One Company command creates exactly one Company')
    _validate_root(plan)
    root=plan.root;root_id=root.id
    for row in changes:
        model=type(row);state=inspect(row)
        if row in session.deleted:
            if model is not ContactChannel or row not in plan.born or plan.payload.communicationChannels is None:
                deny('Company creation cannot delete pre-existing native records')
            from app.shared.master_data import channel_values
            requested={(item['kind'],item['normalized_value']) for item in map(channel_values,plan.payload.communicationChannels)}
            if row.account_id!=root_id or root_id is None or row.person_id is not None or row.contact_id is not None or (row.kind,row.normalized_value) in requested:
                deny('Only a superseded born Company compatibility channel can be removed')
            continue
        if model is CRMCompany:continue
        if row not in session.new and row not in plan.born:deny('Company birth cannot mutate an existing native record')
        if hasattr(row,'organization_id') and row.organization_id!=scope.company_id:deny('Company child source company changed')
        if model is CRMContact:
            links=[link for link in set(session.new)|plan.born if type(link) is ContactIdentityLink and link.account is root and link.contact is row]
            intrinsic=bool(links)
            primary=plan.payload.newPrimaryContact
            if not intrinsic and not (primary and row.company_id==root_id and row.full_name==primary.name):
                deny('Contact must be its exact born Company identity or submitted new primary contact')
            if row.owner_user_id!=actor.id or row.created_by_user_id!=actor.id or getattr(row,'user_id',None) is not None:
                deny('Company contact cannot acquire a foreign login identity')
            if getattr(row,'branch_id',None) not in (None,scope.branch.branch_id):deny('Company contact branch changed')
        elif model is ContactIdentityLink:
            if row.account is not root or row.contact not in set(session.new)|plan.born or row.lead_id is not None:
                deny('Company identity cannot adopt a pre-existing source')
        elif model is CompanyMasterDetails:
            if root_id is None or row.account_id!=root_id:deny('Company details parent differs')
            if row.primary_contact_id is not None and row.primary_contact_id!=plan.payload.primaryContactId:
                primary=plan.payload.newPrimaryContact
                if not primary:deny('Primary contact was not explicitly selected')
                if not any(type(item) is CRMContact and item.id==row.primary_contact_id and item.full_name==primary.name for item in plan.born):deny('New primary contact differs')
        elif model is BusinessRelationship:
            if row.account_id!=root_id or root_id is None or row.contact_id is not None or row.role not in plan.payload.roles:
                deny('Business relationship must belong to the actual born Company and submitted roles')
        elif model is CompanyContactLink:
            if row.account_id!=root_id or root_id is None:deny('Company contact link source differs')
            valid=row.contact_id==plan.payload.primaryContactId or any(type(item) is CRMContact and item.id==row.contact_id for item in plan.born)
            if not valid:deny('Company link requires the actual selected or born primary contact')
        elif model is ContactChannel:
            contacts={item.id for item in plan.born if type(item) is CRMContact and item.id is not None}
            if not ((root_id is not None and row.account_id==root_id and row.contact_id is None) or
                    (row.contact_id in contacts and row.account_id is None)) or row.person_id is not None :
                deny('Communication channel parent differs from the actual born Company graph')
            if row.verification_status not in (None,'unverified'):deny('Company birth cannot assert communication verification')
        elif model is CRMCustomFieldValue:
            contacts={item.id for item in plan.born if type(item) is CRMContact and item.id is not None}
            if not (row.entity=='companies' and row.record_id==root_id and root_id is not None or row.entity=='contacts' and row.record_id in contacts):
                deny('Custom field value cannot reference a different native record')
            from app.apps.crm.models import CRMCustomField
            field_row=db.connection().execute(select(CRMCustomField.__table__).where(CRMCustomField.id==row.custom_field_id,
                CRMCustomField.organization_id==scope.company_id,CRMCustomField.entity==row.entity,CRMCustomField.is_active.is_(True),CRMCustomField.deleted_at.is_(None))).first()
            if field_row is None:deny('Custom field definition is not active for this native Company')
        elif model is ContactFinancialProfile:
            if plan.payload.financialData is None or not any(type(item) is CRMContact and item.id==row.contact_id for item in plan.born):
                deny('Financial profile requires the actual submitted born Company contact')
        elif model is AuditLog:
            if row.user_id!=actor.id or row.organization_id not in (None,scope.company_id):deny('Native Company audit actor changed')
        else:deny('This write source is outside the canonical Company creation graph')
        if row in session.new:plan.born.add(row)
        else:
            immutable={column.name for column in state.mapper.primary_key}|{'organization_id'}
            if any(state.attrs[name].history.has_changes() for name in immutable if name in state.attrs):deny('Born Company child identity is immutable')


def _contact_id_projection(node):
    """One native financial-summary join: scoped ORM Contact.id subquery only."""
    from sqlalchemy.sql.selectable import Subquery,Alias,Select
    from app.apps.crm.models import CRMContact
    source=getattr(node,'table',None)
    if not isinstance(source,(Subquery,Alias)):return False
    inner=source.element
    while isinstance(inner,(Subquery,Alias)):inner=inner.element
    if not isinstance(inner,Select) or inner._propagate_attrs.get('compile_state_plugin')!='orm':return False
    columns=list(inner.selected_columns)
    if len(columns)!=1:return False
    mapper=columns[0]._annotations.get('parentmapper')
    if mapper is None or mapper.class_ is not CRMContact or not columns[0].shares_lineage(CRMContact.id):return False
    projected=source.corresponding_column(columns[0],require_embedded=True)
    return projected is not None and node.shares_lineage(projected)


def install(db,actor,scope):
    from .common_core import deny,_native_authority,_native_operation_access
    from .common_binding import MARKER
    from .models import PackRecordOwnership
    from app.db.base_class import Base
    from app.models.company import Company,Branch
    from app.models.employee import Employee
    from app.models.user import User,Role,Permission,role_permissions
    from app.shared.models import ServicePolicy
    from app.access.models import AccessPolicy
    from app.apps.crm.models import CRMCompany,CRMContact,CRMCustomField,CRMCustomFieldValue,CRMOwner,CRMTeam
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.shared.master_data_models import CompanyMasterDetails,BusinessRelationship,CompanyContactLink,ContactChannel
    from app.apps.crm.financial_models import ContactFinancialProfile
    from app.apps.srm.commercial_models import CustomerLink
    from app.models.audit import AuditLog
    from app.apps.crm.api import router as crm
    from app.branches.boundary import _read_guards
    from app.branches.catalog import key_expression
    from app.branches.service import context as branch_context
    if scope.binding.purpose!=PURPOSE or (scope.method,scope.route) not in candidate_operations(type(scope.operation)):
        deny('Only the exact canonical Company master purpose is supported')
    if db.info.get('business_pack_policy') is not None:deny('Native Company master cannot mix with operational pack authority')
    previous=db.info.get('business_common_core_scope')
    if previous is not None:
        if previous!=scope:deny('Company native purpose cannot change inside a request')
        return lambda:None
    if db.new or db.deleted or any(db.is_modified(row,include_collections=True) for row in db.dirty):deny('Finish pending changes before binding native Company master')
    owner=PackRecordOwnership.__table__;present=inspect(db.connection()).has_table(owner.name)
    def unowned(table):return ~exists(select(1).where(owner.c.resource_table==table.name,owner.c.resource_key==key_expression(table))).correlate(table) if present else true()
    selected=(scope.branch.branch_id,) if scope.branch.branch_id else tuple(sorted(scope.branch.allowed))
    guards,_=_read_guards(tuple(sorted((model.__tablename__,model) for model in (CRMCompany,CRMContact))),actor.id,
        scope.company_id,scope.branch.branch_id,selected,scope.branch.superuser,False,scope.branch.company_admin)
    native_scope=crm._crm_user_scope(db,actor)
    company_visibility=crm._apply_record_visibility(db.query(CRMCompany).filter(CRMCompany.organization_id==scope.company_id),crm._get_resource('companies'),actor,db).statement.whereclause
    contact_visibility=crm._apply_record_visibility(db.query(CRMContact).filter(CRMContact.organization_id==scope.company_id),crm._get_resource('contacts'),actor,db).statement.whereclause
    from app.shared.master_data import authorize
    can_contacts=True
    try:authorize(actor,'crm',entity='contacts')
    except HTTPException as error:
        if error.status_code!=403:raise
        can_contacts=False
    company_condition=and_(company_visibility,guards.get(CRMCompany,true()),unowned(CRMCompany.__table__))
    contact_condition=and_(contact_visibility,guards.get(CRMContact,true()),unowned(CRMContact.__table__))
    company_ids=select(CRMCompany.__table__.c.id).where(company_condition)
    contact_ids=select(CRMContact.__table__.c.id).where(contact_condition) if can_contacts else select(CRMContact.__table__.c.id).where(false())
    from app.access.catalog import permission_objects
    permission_names={item.name for item in permission_objects(actor)}
    permissions=list(db.connection().scalars(select(Permission.__table__.c.id).where(Permission.__table__.c.name.in_(permission_names))))
    permissions.extend(db.connection().scalars(select(role_permissions.c.permission_id).where(role_permissions.c.role_id==actor.role_id)))
    team_ids=select(CRMOwner.__table__.c.team_id).where(CRMOwner.__table__.c.organization_id==scope.company_id,CRMOwner.__table__.c.user_id==actor.id,
        CRMOwner.__table__.c.status=='Active',CRMOwner.__table__.c.deleted_at.is_(None))
    def conditions():
        plan=_active(db)
        born_contacts={_identity(row) for row in plan.born if type(row) is CRMContact and _identity(row) is not None} if plan else set()
        visible_contacts=or_(CRMContact.id.in_(contact_ids),CRMContact.id.in_(born_contacts))
        all_contacts=select(CRMContact.__table__.c.id).where(visible_contacts,CRMContact.organization_id==scope.company_id,unowned(CRMContact.__table__))
        fields=select(CRMCustomField.__table__.c.id).where(CRMCustomField.organization_id==scope.company_id,CRMCustomField.entity.in_(('companies','contacts')),
            CRMCustomField.is_active.is_(True),CRMCustomField.deleted_at.is_(None))
        result={CRMCompany:company_condition,CRMContact:visible_contacts,
            ContactIdentityLink:and_(ContactIdentityLink.organization_id==scope.company_id,ContactIdentityLink.account_id.in_(company_ids),ContactIdentityLink.lead_id.is_(None),ContactIdentityLink.employee_id.is_(None),ContactIdentityLink.person_id.is_(None),ContactIdentityLink.contact_id.in_(all_contacts)),
            CompanyMasterDetails:and_(CompanyMasterDetails.organization_id==scope.company_id,CompanyMasterDetails.account_id.in_(company_ids)),
            BusinessRelationship:and_(BusinessRelationship.organization_id==scope.company_id,or_(BusinessRelationship.account_id.in_(company_ids),BusinessRelationship.contact_id.in_(all_contacts))),
            CompanyContactLink:and_(CompanyContactLink.organization_id==scope.company_id,CompanyContactLink.account_id.in_(company_ids),CompanyContactLink.contact_id.in_(all_contacts)),
            ContactChannel:and_(ContactChannel.organization_id==scope.company_id,or_(ContactChannel.account_id.in_(company_ids),ContactChannel.contact_id.in_(all_contacts)),ContactChannel.person_id.is_(None)),
            CRMCustomField:CRMCustomField.id.in_(fields),CRMCustomFieldValue:and_(CRMCustomFieldValue.organization_id==scope.company_id,CRMCustomFieldValue.custom_field_id.in_(fields),
                or_(and_(CRMCustomFieldValue.entity=='companies',CRMCustomFieldValue.record_id.in_(company_ids)),and_(CRMCustomFieldValue.entity=='contacts',CRMCustomFieldValue.record_id.in_(all_contacts)))),
            ContactFinancialProfile:and_(ContactFinancialProfile.organization_id==scope.company_id,ContactFinancialProfile.contact_id.in_(all_contacts)),
            CustomerLink:and_(CustomerLink.organization_id==scope.company_id,CustomerLink.customer_id.in_(company_ids)),
            Company:Company.id==scope.company_id,Branch:Branch.company_id==scope.company_id,
            User:User.id==actor.id,Role:Role.id==actor.role_id,Permission:Permission.id.in_(permissions),AuditLog:false(),
            AccessPolicy:and_(AccessPolicy.company_id==scope.company_id,AccessPolicy.user_id==actor.id),
            ServicePolicy:and_(ServicePolicy.organization_id==scope.company_id,ServicePolicy.kind=='form_defaults',ServicePolicy.module_key.in_(('*','crm')))}
        financial=_financial_reads.get(db)
        if financial is not None:
            if financial[0] is not actor or financial[1] is not scope:deny('Company financial projection context changed')
            from app.apps.fam.models import FAMParty,FAMSRMMapping,FAMPurchaseBill,FAMBillReference
            ident=financial[2]
            fam_models=_financial_models(db)
            fam_guards,_=_read_guards(tuple(sorted((model.__tablename__,model) for model in fam_models)),actor.id,
                scope.company_id,scope.branch.branch_id,selected,scope.branch.superuser,False,scope.branch.company_admin)
            links=select(CustomerLink.__table__.c.source_id).where(CustomerLink.organization_id==scope.company_id,
                CustomerLink.customer_id==ident,CustomerLink.source_type=='crm_account')
            mappings=select(FAMSRMMapping.__table__.c.fam_record_id).where(FAMSRMMapping.company_id==scope.company_id,
                FAMSRMMapping.srm_record_type=='customer',FAMSRMMapping.srm_record_id==ident,
                FAMSRMMapping.fam_record_type=='party',FAMSRMMapping.mapping_status=='active')
            party_condition=and_(FAMParty.company_id==scope.company_id,or_(FAMParty.crm_account_id.in_(links),FAMParty.id.in_(mappings)),fam_guards.get(FAMParty,true()))
            parties=select(FAMParty.__table__.c.id).where(party_condition)
            result.update({model:and_(condition,fam_guards.get(model,true()),unowned(model.__table__)) for model,condition in {
                FAMParty:party_condition,FAMSRMMapping:and_(FAMSRMMapping.company_id==scope.company_id,FAMSRMMapping.srm_record_type=='customer',FAMSRMMapping.srm_record_id==ident,FAMSRMMapping.fam_record_type=='party',FAMSRMMapping.mapping_status=='active'),
                FAMPurchaseBill:and_(FAMPurchaseBill.company_id==scope.company_id,FAMPurchaseBill.vendor_id.in_(parties)),
                FAMBillReference:and_(FAMBillReference.company_id==scope.company_id,FAMBillReference.party_id.in_(parties))}.items() if model in fam_models})
        return result
    reads=set(conditions());checking=False;identity_load=False
    def fresh():
        nonlocal checking
        if checking:return
        checking=True
        try:
            if (actor.id!=scope.user_id or actor.organization_id!=scope.company_id or db.info.get(MARKER)!=scope.binding
                    or db.info.get('business_pack_scope') is not None or db.info.get('branch_context')!=scope.branch):deny('Native Company authority changed')
            branch=str(scope.branch.branch_id) if scope.branch.branch_id is not None else 'all' if scope.branch.all_branches else None
            if branch_context(db,actor,scope.company_id,branch)!=scope.branch:deny('Native Company branch access changed')
            if _native_authority(db,actor,scope.company_id)!=scope.native_authority or crm._crm_user_scope(db,actor)!=native_scope:deny('Native Company permissions or visibility changed')
            _native_operation_access(db,actor,scope.company_id,scope.operation)
            _active(db,actor)
        finally:checking=False
    def restrict(execution):
        if checking:return
        fresh()
        if not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete:deny('Company master uses canonical mapped per-record operations')
        allowed_reads=reads|_financial_models(db)
        if execution.bind_mapper is not None and execution.bind_mapper.class_ not in allowed_reads:deny('This source is outside the reviewed Company master graph')
        from .common_queries import assert_mapped_sources
        assert_mapped_sources(execution.statement,allowed_reads,trusted_identity=identity_load,allowed_associations=(role_permissions,))
        _financial_projection(db,execution.statement)
        if not identity_load and not execution.is_column_load and not execution.is_relationship_load:
            from .employee_core import _count_stars
            stars=_count_stars(execution.statement)
            for node in visitors.iterate(execution.statement):
                if isinstance(node,TextClause) or isinstance(node,ColumnClause) and ((getattr(node,'is_literal',False) and id(node) not in stars) or
                    getattr(node,'table',None) is not None and not (node._annotations.get('parententity') or node._annotations.get('parentmapper')) and not _contact_id_projection(node)):
                    deny('Company master raw SQL requires a separately reviewed native source')
        clauses=conditions()
        execution.statement=execution.statement.options(*(with_loader_criteria(mapper.class_,clauses.get(mapper.class_,false()),include_aliases=True,propagate_to_loaders=False) for mapper in Base.registry.mappers))
        execution.update_execution_options(compiled_cache=None)
    def validate(session,*args):
        fresh();_validate_writes(db,actor,scope,session)
    def before_commit(session):
        plan=_active(db,actor)
        if plan is not None and not plan.complete and not db.in_nested_transaction():
            raise HTTPException(409,'An incomplete canonical Company birth cannot commit')
        fresh()
    original_get,original_refresh=db.get,db.refresh
    def visible(model,identity):
        fresh();mapper=inspect(model,raiseerr=False);model=getattr(mapper,'class_',model)
        if model not in reads:return False
        keys=inspect(model).primary_key
        values=[identity.get(key.key) for key in keys] if isinstance(identity,dict) else list(identity) if isinstance(identity,(tuple,list)) else [identity]
        if len(keys)!=len(values):return False
        attrs=[getattr(model,inspect(model).get_property_by_column(key).key) for key in keys]
        with db.no_autoflush:return db.query(*attrs).filter(*(key==value for key,value in zip(attrs,values))).first() is not None
    def scoped_get(model,identity,**kwargs):
        nonlocal identity_load
        if not visible(model,identity):return None
        old=identity_load;identity_load=True
        try:return original_get(model,identity,**kwargs)
        finally:identity_load=old
    def scoped_refresh(row,*args,**kwargs):
        nonlocal identity_load
        if not visible(type(row),inspect(row).identity):deny('Cached Company source is outside current native scope')
        old=identity_load;identity_load=True
        try:return original_refresh(row,*args,**kwargs)
        finally:identity_load=old
    bulk={name:getattr(db,name) for name in ('bulk_insert_mappings','bulk_update_mappings','bulk_save_objects')}
    def reject(*args,**kwargs):deny('Company master bulk writes require their own reviewed command')
    fresh()
    for name in bulk:setattr(db,name,reject)
    for state in list(db.identity_map.all_states()):
        if state.class_ in reads and state.obj() is not None:db.expire(state.obj())
    db.get,db.refresh=scoped_get,scoped_refresh
    db.info['business_common_core_scope']=scope;db.info['_company_master_fresh']=fresh
    _scopes[db]=(actor,scope)
    event.listen(db,'do_orm_execute',restrict);event.listen(db,'before_flush',validate);event.listen(db,'before_commit',before_commit)
    closed=False
    def cleanup():
        nonlocal closed
        if closed:return
        closed=True
        event.remove(db,'do_orm_execute',restrict);event.remove(db,'before_flush',validate);event.remove(db,'before_commit',before_commit)
        db.get,db.refresh=original_get,original_refresh
        for name,method in bulk.items():setattr(db,name,method)
        db.info.pop('business_common_core_scope',None);db.info.pop('_company_master_fresh',None);_scopes.pop(db,None)
    return cleanup
