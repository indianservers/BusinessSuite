"""Closed POS projection/validation of canonical native customer custom fields.

Definition reads and new-account value inserts below are fixed purposes, not
read/write grants to the generic CRM or platform custom-field directories.
"""
from dataclasses import dataclass
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
import hashlib,json
from types import SimpleNamespace
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,JsonValue,StrictInt
from sqlalchemy import inspect,select,func
from app.apps.crm.models import CRMCustomField,CRMCustomFieldValue

UNAVAILABLE='Required customer fields cannot be entered with the current native permissions or supported POS controls'
SUPPORTED=frozenset({'text','long_text','number','currency','date','datetime','dropdown','multi_select','radio','combobox','checkbox','email','phone','url'})
ALIASES={'textarea':'long_text','longtext':'long_text','select':'dropdown','boolean':'checkbox','date_time':'datetime'}
CHOICES=frozenset({'dropdown','multi_select','radio','combobox'})


def fail(message,code=422):raise HTTPException(code,message)


class CustomValueInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    field_id:StrictInt=Field(gt=0)
    value:JsonValue


@dataclass(frozen=True)
class Snapshot:
    fingerprint:str
    definitions:tuple
    eligible:tuple
    fields:tuple
    available:bool
    def output(self):
        return {'entity':'companies','schema_fingerprint':self.fingerprint,'registration_available':self.available,
            'unavailable_reason':None if self.available else UNAVAILABLE,'fields':list(self.fields)}


def _policy(db,actor):
    from app.models.user import User,Role
    from app.apps.admin_security.models import AdminProfile,AdminFieldSecurity
    u,r=User.__table__,Role.__table__;connection=db.connection()
    actual=connection.execute(select(u.c.role_id,r.c.name).select_from(u.outerjoin(r,r.c.id==u.c.role_id)).where(u.c.id==actor.id,u.c.is_active.is_(True))).first()
    if (actual is None or actual.role_id!=actor.role_id
            or (actual.role_id is not None and actual.name is None)):
        fail('Native customer field authorization changed',403)
    profile,rule=AdminProfile.__table__,AdminFieldSecurity.__table__
    inspector=inspect(connection);installed=[inspector.has_table(table.name) for table in (profile,rule)]
    if not any(installed):return actual.role_id,[]
    if not all(installed):fail('Native field permission installation is incomplete',503)
    # Native FLS has no role-named profile when the actual user has no legacy role.
    if actual.role_id is None:return None,[]
    names={actual.name,actual.name.replace('_',' ').title()}
    statement=select(rule.c.id,rule.c.module_name,rule.c.field_name,rule.c.can_view,rule.c.can_edit,rule.c.mask_value).select_from(rule.join(profile,profile.c.id==rule.c.profile_id)).where(
        profile.c.name.in_(names),profile.c.active.is_(True),rule.c.module_name.in_(('crm','srm','companies'))).order_by(rule.c.id)
    return actual.role_id,[dict(row) for row in connection.execute(statement).mappings()]


def _type(row):return ALIASES.get(str(row['field_type'] or 'text').lower(),str(row['field_type'] or 'text').lower())


def _unique(row):
    options=row['options_json'] or {}
    return bool(row['is_unique'] or (isinstance(options,dict) and any(options.get(key) for key in ('isUnique','is_unique','unique','dedupe')))
        or row['field_key'].lower() in {'tax_registration_number','tax_registration','gstin','pan','unique_id','external_id'})


def snapshot(db,actor,company,scope):
    table=CRMCustomField.__table__
    rows=[dict(row) for row in db.connection().execute(select(table).where(table.c.organization_id==company,table.c.entity=='companies',
        table.c.is_active.is_(True),table.c.deleted_at.is_(None)).order_by(table.c.position,table.c.id)).mappings()]
    role,rules=_policy(db,actor)
    allowed=[];fields=[];available=True
    from app.apps.crm.custom_field_config import option_values,PLACES
    from app.core.input_validation import clean_text
    for row in rows:
        key=row['field_key'];identifiers={key,'cf_'+key}
        if row['field_name']:identifiers.add(row['field_name'])
        matched=[rule for rule in rules if rule['field_name'] in identifiers]
        visible=row['is_visible'] is True and all(rule['can_view'] and not rule['mask_value'] for rule in matched)
        editable=visible and all(rule['can_edit'] for rule in matched)
        raw=row['options_json']
        ui=raw.get('ui',{}) if isinstance(raw,dict) else {}
        options=option_values(raw)
        places=ui.get('places',sorted(PLACES)) if isinstance(ui,dict) else None
        kind=_type(row)
        valid=(kind in SUPPORTED and isinstance(ui,dict) and isinstance(places,list) and all(isinstance(p,str) and p in PLACES for p in places)
            and 'quick_create' in places and isinstance(options,list) and len(options)<=200 and all(isinstance(value,str) and value.strip() and len(value)<=500 for value in options)
            and len(options)==len(set(options)) and (kind not in CHOICES or bool(options)))
        try:label=clean_text(row['label'],160)
        except ValueError:valid=False;label=''
        usable=visible and editable and valid
        if row['is_required'] and not usable:available=False
        if not usable:continue
        allowed.append(row)
        fields.append({'id':row['id'],'label':label,'type':kind,'required':bool(row['is_required']),'editable':True,'options':options if kind in CHOICES else [],
            'unique':_unique(row),'precision':18 if kind in ('number','currency') else None,'scale':4 if kind in ('number','currency') else None})
    payload={'company':company,'actor':actor.id,'role':role,'scope':(scope.context_id,*scope.revisions),'native_policy':getattr(actor,'_suite_policy_version',None),
        'definitions':rows,'rules':rules,'allowed_ids':[row['id'] for row in allowed]}
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
    return Snapshot(fingerprint,tuple(rows),tuple(allowed),tuple(fields),available)


def _validate(row,value):
    """Native storage semantics with strict typed transport/column bounds."""
    kind=_type(row)
    if value is not None:
        if kind=='checkbox' and type(value) is not bool:fail('Customer checkbox values must be true or false')
        if kind in ('number','currency'):
            if type(value) not in (str,int,float):fail('Customer numeric values must be numbers')
            try:
                number=Decimal(str(value))
                if not number.is_finite() or abs(number)>=Decimal('100000000000000') or number!=number.quantize(Decimal('0.0001')):raise ValueError()
            except (ValueError,ArithmeticError,InvalidOperation):fail('Customer numeric value exceeds supported precision or scale')
        elif kind=='multi_select':
            if not isinstance(value,list) or len(value)>200 or any(not isinstance(v,str) or len(v)>500 for v in value) or len(value)!=len(set(value)):fail('Customer multiple-choice values must be distinct text options')
        elif kind=='phone':
            if not isinstance(value,dict) or set(value)!={'national_number','country_code'}:fail('Customer phone values need a national number and calling code')
        elif kind!='checkbox' and not isinstance(value,str):fail('Customer text, choice and date values must be text')
        if isinstance(value,str) and len(value)>8000:fail('Customer field value is too long')
    from app.apps.crm.api.router import _custom_field_storage
    definition=SimpleNamespace(**{**row,'field_type':kind})
    storage=_custom_field_storage(definition,value)
    timestamp=storage['value_datetime']
    if timestamp is not None and timestamp.tzinfo is not None:fail('Customer date/time fields use a local date and time without a timezone offset')
    return storage


def _unique_key(storage):
    for key,value in storage.items():
        if value is None:continue
        if key=='value_text':return key,value.strip().casefold()
        if key=='value_json':
            if isinstance(value,list):value=sorted(value)
            return key,json.dumps(value,sort_keys=True,separators=(',',':'))
        return key,value
    return None


def validate(db,actor,company,scope,values,fingerprint):
    current=snapshot(db,actor,company,scope)
    if not current.available:fail(UNAVAILABLE,403)
    if current.definitions and fingerprint!=current.fingerprint:fail('Customer field schema changed. Reload and review the form before saving.',409)
    if fingerprint is not None and fingerprint!=current.fingerprint:fail('Customer field schema changed. Reload and review the form before saving.',409)
    identifiers=[value.field_id for value in values]
    if len(identifiers)!=len(set(identifiers)):fail('Duplicate customer field identifiers')
    definitions={row['id']:row for row in current.definitions};eligible={row['id']:row for row in current.eligible}
    normalized=[]
    for value in values:
        if value.field_id not in definitions:fail('Unknown customer field identifier')
        if value.field_id not in eligible:fail('Customer field is not editable in this POS',403)
        storage=_validate(eligible[value.field_id],value.value)
        normalized.append((eligible[value.field_id],storage))
    for row in current.eligible:
        if row['is_required'] and row['id'] not in identifiers:fail('Complete the required customer fields')
    if len(json.dumps([value.model_dump() for value in values]))>65536:fail('Customer field payload is too large')
    # Company writer is already held by the enclosing birth command. This
    # additive check makes no claim about unmodified generic legacy writers.
    table=CRMCustomFieldValue.__table__
    for row,storage in normalized:
        key=_unique_key(storage)
        if not _unique(row) or key is None:continue
        statement=select(*(table.c[name] for name in ('value_text','value_number','value_date','value_datetime','value_boolean','value_json'))).where(
            table.c.organization_id==company,table.c.entity=='companies',table.c.custom_field_id==row['id'],table.c.deleted_at.is_(None))
        for previous in db.connection().execute(statement).mappings():
            if _unique_key(dict(previous))==key:fail('A matching customer field value already exists. Ask an authorized administrator to review it.',409)
    return normalized,current.fingerprint


def assert_current(db,actor,company,scope,expected):
    if snapshot(db,actor,company,scope).fingerprint!=expected:fail('Customer field schema changed during creation. Reload and review the form.',409)


def _insert_values(db,actor,company,branch,customer_id,normalized):
    """Only the actual ID returned by the closed new-account insert is passed."""
    from app.branches.models import BranchOwnership
    table=CRMCustomFieldValue.__table__;owner=BranchOwnership.__table__
    for definition,storage in normalized:
        ident=db.connection().execute(table.insert().values(organization_id=company,entity='companies',record_id=customer_id,custom_field_id=definition['id'],
            created_by_user_id=actor.id,updated_by_user_id=actor.id,**storage).returning(table.c.id)).scalar_one()
        db.connection().execute(owner.insert().values(company_id=company,branch_id=branch,resource_table=table.name,resource_key=str(ident),source='pos_customer_birth'))
