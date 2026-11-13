"""Reviewed employee profile proposals through the native HRMS API."""
import re
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from pydantic import Field,model_validator
from app.ai_operator.suite_tools import Strict


class EmployeeProfileUpdate(Strict):
    first_name: str | None = Field(default=None,min_length=1,max_length=160)
    middle_name: str | None = Field(default=None,max_length=160)
    last_name: str | None = Field(default=None,max_length=160)
    work_email: str | None = Field(default=None,max_length=150)
    personal_email: str | None = Field(default=None,max_length=150)
    phone_number: str | None = Field(default=None,max_length=40)
    phone_number_country_code: str | None = Field(default=None,max_length=5)
    office_extension: str | None = Field(default=None,max_length=20)
    preferred_display_name: str | None = Field(default=None,max_length=220)
    work_location: str | None = Field(default=None,max_length=200)
    desk_code: str | None = Field(default=None,max_length=80)
    timezone: str | None = Field(default=None,max_length=60)
    skills_tags: str | None = Field(default=None,max_length=1000)
    bio: str | None = Field(default=None,max_length=4000)
    department_id: int | None = Field(default=None,strict=True,gt=0,le=2147483647)
    designation_id: int | None = Field(default=None,strict=True,gt=0,le=2147483647)
    reporting_manager_id: int | None = Field(default=None,strict=True,gt=0,le=2147483647)

    @model_validator(mode='after')
    def native_valid(self):
        if not self.model_fields_set:raise ValueError('Choose a profile field')
        # Reuse native text/email validation, including first-name requirements.
        from app.schemas.employee import EmployeeUpdate
        EmployeeUpdate.model_validate(self.model_dump(exclude_unset=True))
        if self.timezone:
            try:ZoneInfo(self.timezone)
            except (ZoneInfoNotFoundError,ValueError):raise ValueError('Choose an IANA timezone') from None
        return self


INTENT='employee.update'
FIELDS={'first name':'first_name','middle name':'middle_name','last name':'last_name','work email':'work_email',
    'personal email':'personal_email','phone':'phone_number','phone country code':'phone_number_country_code',
    'office extension':'office_extension','display name':'preferred_display_name','work location':'work_location',
    'desk':'desk_code','timezone':'timezone','skills':'skills_tags','bio':'bio',
    'department id':'department_id','designation id':'designation_id','manager id':'reporting_manager_id'}
LABELS='|'.join(re.escape(k) for k in sorted(FIELDS,key=len,reverse=True))
COMMAND=re.compile(r'^(?:please\s+)?(?:update|edit|change)\s+(?:the\s+)?(?:employee|staff)(?:\s+profile)?\b',re.I)


def values(text):
    result={}
    for part in re.split(r',\s*(?=(?:'+LABELS+r')\s*(?:=|:|\bto\b|\bis\b))',text,flags=re.I):
        match=re.fullmatch(r'\s*('+LABELS+r')\s*(?:=|:|is\b|to\b)\s*(.+?)\s*',part,re.I|re.S)
        if not match:return None
        key=FIELDS[match[1].casefold()]
        if key in result:return None
        raw=match[2].strip()
        if raw.casefold() in {'clear','not set','null'}:value=None
        elif key.endswith('_id'):
            if not re.fullmatch(r'[1-9]\d{0,9}',raw) or int(raw)>2147483647:return None
            value=int(raw)
        else:value=raw.strip('"“”')
        result[key]=value
    return result or None


def interpret(text):
    from app.ai_operator.local_nlp import Interpretation
    text=re.sub(r'^\s*(?:HRMS|HR)\s*:\s*','',text,flags=re.I).strip()
    match=COMMAND.match(text)
    if not match:return None
    tail=text[match.end():].strip();slots={}
    ident=re.match(r'^(?:#\s*|id\s+)([1-9]\d*)\b',tail,re.I)
    if ident:
        if len(ident[1])>10 or int(ident[1])>2147483647:
            return Interpretation('HRMS',INTENT,1,slots,'Supply a valid numeric employee record ID.')
        slots['record_id']=int(ident[1]);tail=tail[ident.end():].strip()
    tail=re.sub(r'^(?:with|set)\s+','',tail,flags=re.I).lstrip(': ')
    if tail:
        parsed=values(tail)
        if not parsed:return Interpretation('HRMS',INTENT,1,slots,'Use an exact employee #ID and labelled fields, for example office extension: 204, work location: Hyderabad. Login roles, payroll, bank data and employment status are separate native workflows.')
        slots['values']=parsed
    return Interpretation('HRMS',INTENT,1,slots)


def followup(current,prior,text):
    from app.ai_operator.local_nlp import Interpretation
    reply=text.strip();plain=reply.casefold().strip(' .!?');old=dict(prior.get('slots') or {})
    if plain in {'cancel','cancel it','stop','never mind','nevermind','discard this draft'}:
        return Interpretation('HRMS','cancelled',1,{})
    if current.question and any(k in current.question for k in ('cannot bypass','destructive','one operation at a time')):return current
    if current.intent==INTENT:
        # A partial restatement corrects the current draft; an explicit different
        # record starts a fresh selection and must not inherit old values.
        if current.question:return current
        selected=current.slots.get('record_id')
        previous=old.get('record_id')
        if selected is not None and selected!=previous and not (previous is None and old.get('_awaiting')=='record_id'):return current
        merged={**old,**current.slots,'values':{**old.get('values',{}),**current.slots.get('values',{})}}
        merged.pop('_awaiting',None)
        return Interpretation('HRMS',INTENT,1,merged)
    if re.match(r'^(?:CRM|PMS|HRMS|HR|Sales|SRM)\s*:|^(?:show|list|find|create|add|delete|send|apply|request|approve|update|edit|change)\b',reply,re.I):return current
    if old.get('_awaiting')=='record_id':
        ident=re.fullmatch(r'(?:employee\s*)?(?:#\s*|id\s*)?([1-9]\d{0,9})',reply,re.I)
        if not ident:
            parsed=values(reply)
            if parsed:
                old['values']={**old.get('values',{}),**parsed}
                return Interpretation('HRMS',INTENT,1,old)
        if not ident or int(ident[1])>2147483647:
            return Interpretation('HRMS',INTENT,1,old,'Supply the numeric employee #ID. Names, employee codes and task IDs are not record selections.')
        old['record_id']=int(ident[1])
    else:
        parsed=values(reply)
        if not parsed:return Interpretation('HRMS',INTENT,1,old,'Supply labelled profile fields, for example office extension: 204. This reply has not approved or executed anything.')
        old['values']={**old.get('values',{}),**parsed}
    old.pop('_awaiting',None)
    return Interpretation('HRMS',INTENT,1,old)


def proposal(intent,context):
    if intent.intent!=INTENT:return None
    from app.ai_operator.local_dialogue import need
    from app.ai_operator.evidence import records
    if intent.question:return {'summary':'Employee details need clarification. Nothing changed.','question':intent.question,'steps':[]}
    ident=intent.slots.get('record_id');payload=intent.slots.get('values') or {}
    if not ident:return need(intent,'record_id','Which employee record #ID should I update? I will check your HR permissions and record access.')
    visible=[r for p in context if p['tool']=='hrms.employee' for r in records(p['records'])]
    if not any(r.get('id')==ident for r in visible):return need(intent,'record_id','Select an authorized employee record #ID.')
    if not payload:return need(intent,'fields','Which profile fields should change? For example office extension: 204, work location: Hyderabad. Use clear to remove an optional value.')
    try:EmployeeProfileUpdate.model_validate(payload)
    except ValueError:return need(intent,'fields','A profile value is invalid. Supply corrected labelled fields. Email, timezone and organizational IDs must be valid; first name cannot be cleared.')
    return {'summary':'Review the exact employee profile changes. No update has executed. Native HRMS permissions, sensitive-field access, duplicate checks and organizational relationships remain mandatory.',
        'steps':[{'tool':'hrms.update_employee','record_id':ident,'payload':payload}]}


def projection(value):
    # Never forward bank, identity, medical, personal contacts or account roles.
    allowed={'id','employee_id','first_name','middle_name','last_name','preferred_display_name','work_email','office_extension',
        'work_location','desk_code','timezone','skills_tags','department_id','designation_id','reporting_manager_id'}
    return {k:v[:1000] if isinstance(v,str) else v for k,v in value.items() if k in allowed} if isinstance(value,dict) else {}
