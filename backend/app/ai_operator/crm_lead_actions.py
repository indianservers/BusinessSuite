"""Typed local lead proposals. Canonical CRM owns validation and every mutation."""
import re
from typing import Literal
from decimal import Decimal
from datetime import date
from pydantic import Field, model_validator
from app.ai_operator.suite_tools import Strict


class LeadFields(Strict):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    full_name: str | None = Field(default=None, min_length=1, max_length=220)
    email: str | None = Field(default=None, max_length=150, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    phone: str | None = Field(default=None, max_length=40)
    company_name: str | None = Field(default=None, max_length=180)
    job_title: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    status: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=8000)
    owner_user_id: int | None = Field(default=None, gt=0, le=2147483647)
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    @model_validator(mode='after')
    def values_required(self):
        if not self.model_fields_set:
            raise ValueError('Choose at least one lead field')
        if any(isinstance(getattr(self, field), str) and not getattr(self, field).strip() for field in self.model_fields_set & {'first_name','full_name','status','source'}):
            raise ValueError('Required lead fields cannot be blank')
        if any(getattr(self, field) is None for field in self.model_fields_set & {'first_name','full_name','status','source'}):
            raise ValueError('Required lead fields cannot be cleared')
        if self.status and self.status.casefold() == 'converted':
            raise ValueError('Use the dedicated conversion action')
        return self


class LeadCreate(LeadFields):
    first_name: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=220)


class QualifiedStatus(Strict):
    status: Literal['Qualified']


class Qualification(Strict):
    need: str | None = Field(default=None,max_length=4000)
    budget: str | None = Field(default=None,max_length=200)
    decisionMaker: str | None = Field(default=None,max_length=200)
    timeline: str | None = Field(default=None,max_length=200)

    @model_validator(mode='after')
    def supplied(self):
        if any(getattr(self,key) is None for key in self.model_fields_set):
            raise ValueError('Qualification values must be explicit text')
        return self


class QualificationDetails(Strict):
    qualification: Qualification


class LeadQualify(Strict):
    values: QualifiedStatus
    details: QualificationDetails | None = None
    version: int | None = Field(default=None,ge=0)


class LeadConvert(Strict):
    # Explicit creation choices are required in every model-produced plan.
    createContact: bool
    createCompany: bool
    createDeal: bool
    customerType: Literal['Individual','Business'] | None = None
    existingContactId: int | None = Field(default=None, gt=0, le=2147483647)
    existingCompanyId: int | None = Field(default=None, gt=0, le=2147483647)
    contactName: str | None = Field(default=None, max_length=220)
    contactEmail: str | None = Field(default=None, max_length=150)
    contactPhone: str | None = Field(default=None, max_length=40)
    companyName: str | None = Field(default=None, max_length=180)
    companyIndustry: str | None = Field(default=None, max_length=120)
    dealName: str | None = Field(default=None, max_length=220)
    dealAmount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    pipelineId: int | None = Field(default=None, gt=0, le=2147483647)
    stageId: int | None = Field(default=None, gt=0, le=2147483647)
    expectedCloseDate: date | None = None
    ownerId: int | None = Field(default=None, gt=0, le=2147483647)
    territoryId: int | None = Field(default=None, gt=0, le=2147483647)
    description: str | None = Field(default=None, max_length=8000)

    @model_validator(mode='after')
    def conversion_target(self):
        if not any((self.createContact,self.createCompany,self.createDeal,self.existingContactId,self.existingCompanyId)):
            raise ValueError('Choose at least one conversion destination')
        return self


INTENTS = {'leads.create','leads.update','leads.qualify','leads.convert'}
CONVERSION_CHOICES = {'contact and customer':(True,True,False),'contact customer and deal':(True,True,True),'contact only':(True,False,False)}
COMMAND = re.compile(r'^(?:please\s+)?(create|add|draft|update|edit|qualify|convert)\s+(?:a\s+|an\s+|the\s+)?(?:CRM\s+)?lead\b', re.I)
FIELD_NAMES = {'name':'full_name','full name':'full_name','email':'email','phone':'phone','company':'company_name',
               'company name':'company_name','job title':'job_title','source':'source','status':'status','notes':'notes',
               'need':'need','budget':'budget','decision maker':'decisionMaker','timeline':'timeline'}


def field_values(text):
    """Only labelled values or an explicitly quoted name; never infer record IDs."""
    result = {}
    match = re.fullmatch(r'\s*(?:named\s+)?["“]([^"”\n]+)["”]\s*', text, re.I)
    if match: return {'full_name':match[1]}
    for part in re.split(r',\s*(?=(?:full name|name|email|phone|company name|company|job title|source|status|notes|need|budget|decision maker|timeline)\s*(?:=|:|\bis\b|\bto\b))', text, flags=re.I):
        match = re.fullmatch(r'\s*(full name|name|email|phone|company name|company|job title|source|status|notes|need|budget|decision maker|timeline)\s*(?:=|:|is\b|to\b)\s*(.+?)\s*',part,re.I|re.S)
        if not match: return None
        key = FIELD_NAMES[match[1].casefold()]
        if key in result: return None
        result[key] = match[2].strip().strip('"“”')
    return result or None


def interpret(text):
    from app.ai_operator.local_nlp import Interpretation
    command = re.sub(r'^\s*CRM\s*:\s*','',text,flags=re.I).strip()
    match = COMMAND.match(command)
    if not match: return None
    verb = match[1].casefold()
    name = 'leads.' + ({'add':'create','draft':'create','edit':'update'}.get(verb,verb))
    tail = command[match.end():].strip()
    slots = {'action_verb':verb}
    ident = re.match(r'^(?:#\s*|(?:id|number)\s+)([1-9]\d*)\b',tail,re.I)
    if ident:
        if len(ident[1])>10 or int(ident[1])>2147483647:
            return Interpretation('CRM',name,1,slots,'Please use a valid lead ID.')
        slots['record_id'] = int(ident[1]);tail=tail[ident.end():].strip()
        if name=='leads.create':
            return Interpretation('CRM',name,1,slots,'Creating a lead does not take an existing lead ID. Start a new create lead request, or update the selected lead.')
    tail=re.sub(r'^(?:with|set|to)\s+','',tail,flags=re.I)
    if name in {'leads.create','leads.update','leads.qualify'} and tail:
        values = field_values(tail.lstrip(': '))
        if values: slots['values'] = values
        else: return Interpretation('CRM',name,1,slots,'Use labelled fields, for example name: "Asha Rao", email: asha@example.com. Use lead #ID to select an existing lead.')
    elif tail and not (name=='leads.convert' and re.fullmatch(r'(?:to\s+)?(?:a\s+)?customer',tail,re.I)):
        return Interpretation('CRM',name,1,slots,'Please request one lead operation with an exact lead #ID. Conversion choices will be collected separately.')
    return Interpretation('CRM',name,1,slots)


def continue_lead(current, prior, text):
    from app.ai_operator.local_nlp import Interpretation
    old = dict(prior.get('slots') or {}); name=prior['intent']; pending=old.get('_awaiting')
    reply=text.strip(); plain=reply.casefold().strip(' .!?')
    if plain in {'cancel','cancel it','never mind','nevermind','discard this draft','stop'}:
        return Interpretation('CRM','cancelled',1,{})
    if current.question and any(word in current.question for word in ('cannot bypass','destructive')): return current
    if current.question and 'one operation at a time' in current.question and not (pending=='conversion' and plain in CONVERSION_CHOICES): return current
    if name=='leads.update' and current.intent==name and not current.question:
        selected=current.slots.get('record_id');previous=old.get('record_id')
        if selected is None or selected==previous or (previous is None and pending=='record_id'):
            merged={**old,**current.slots,'values':{**old.get('values',{}),**current.slots.get('values',{})}}
            merged.pop('_awaiting',None)
            return Interpretation('CRM',name,1,merged)
    if COMMAND.match(re.sub(r'^CRM\s*:\s*','',reply,flags=re.I)): return current
    if current.intent in INTENTS: return current
    if re.match(r'^(?:CRM|PMS|HRMS|HR|Sales|SRM)\s*:',reply,re.I): return current
    if re.match(r'^(?:show|list|find|create|add|delete|send|apply|request|approve|qualify|convert|update|edit)\b',reply,re.I): return current
    if pending=='record_id':
        match=re.fullmatch(r'(?:lead\s*)?(?:#\s*|id\s*)?([1-9]\d{0,9})',reply,re.I)
        if match and int(match[1])<=2147483647: old['record_id']=int(match[1])
        else:
            fields=field_values(reply) if name in {'leads.update','leads.qualify'} else None
            if fields:
                old['values']={**old.get('values',{}),**fields}
                return Interpretation('CRM',name,1,old)
            return Interpretation('CRM',name,1,old,'Please provide the exact lead #ID; names and task IDs are not lead selections.')
    elif pending=='conversion' or name=='leads.convert' and plain in CONVERSION_CHOICES:
        if plain not in CONVERSION_CHOICES: return Interpretation('CRM',name,1,old,'Choose: contact and customer; contact customer and deal; or contact only. This does not approve execution.')
        old['conversion']=dict(zip(('createContact','createCompany','createDeal'),CONVERSION_CHOICES[plain]))
    elif pending=='qualification' and plain=='use only existing facts':
        old['qualification_existing']=True
    else:
        values=field_values(reply)
        if not values: return Interpretation('CRM',name,1,old,'Use labelled fields such as name: "Asha Rao", email: asha@example.com. Say cancel to discard. Nothing has been approved.')
        old['values']={**old.get('values',{}),**values}
    old.pop('_awaiting',None)
    return Interpretation('CRM',name,1,old)


def proposal(intent, context):
    from app.ai_operator.local_dialogue import need
    from app.ai_operator.evidence import records
    name=intent.intent;slots=intent.slots
    if name not in INTENTS: return None
    if intent.question: return {'summary':'Lead details need clarification. No changes were made.','question':intent.question,'steps':[]}
    ident=slots.get('record_id')
    if name!='leads.create':
        if not ident: return need(intent,'record_id','Which exact lead #ID should I use? I will check your current access.')
        visible=[r for p in context if p['tool'] in {'crm.lead','crm.lead_qualification'} for r in records(p['records'])]
        if not any(r.get('id')==ident for r in visible): return need(intent,'record_id','That lead is not in the authorized source. Select an accessible lead #ID.')
    values=dict(slots.get('values',{}))
    if name in {'leads.create','leads.update'}:
        if name=='leads.create' and not values.get('full_name'): return need(intent,'fields','What is the lead name? Reply name: "Asha Rao". You can also add email:, phone: and company:.')
        if not values: return need(intent,'fields','Which fields should change? For example email: asha@example.com, job title: Sales Manager.')
        if name=='leads.create':
            values['first_name']=values['full_name'].split()[0] if values['full_name'].split() else ''
        try: (LeadCreate if name=='leads.create' else LeadFields).model_validate(values)
        except ValueError: return need(intent,'fields','Some lead fields are invalid. Supply corrected labelled fields; names must be nonempty and email must be valid. Conversion uses its own reviewed action.')
        payload=values
    elif name=='leads.qualify':
        if set(values)-set(Qualification.model_fields):
            return need(intent,'qualification','For qualification supply need:, budget:, decision maker: and timeline:. Use update lead for other fields.')
        if not values and not slots.get('qualification_existing'):
            return need(intent,'qualification','What qualification facts should I record? Supply need:, budget:, decision maker: and timeline:. Use only existing facts if they are already recorded.')
        try:Qualification.model_validate(values)
        except ValueError:return need(intent,'qualification','Qualification facts exceed the supported field lengths. Supply shorter labelled facts.')
        payload={'values':{'status':'Qualified'}}
        if values:
            existing=next((r.get('qualification') for r in visible if r.get('id')==ident),None) or {}
            facts={**{k:v for k,v in existing.items() if k in Qualification.model_fields},**values}
            missing=[k for k in Qualification.model_fields if not facts.get(k)]
            if missing:
                return need(intent,'qualification','Please supply the remaining qualification facts: '+', '.join('decision maker' if k=='decisionMaker' else k for k in missing)+'. I will not invent these facts.')
            payload['details']={'qualification':facts}
        version=next((r.get('version') for r in visible if r.get('id')==ident),None)
        if isinstance(version,int):payload['version']=version
    else:
        if not slots.get('conversion'): return need(intent,'conversion','What should conversion create? Choose contact and customer; contact customer and deal; or contact only. Existing CRM qualification and duplicate rules still apply.')
        payload=slots['conversion']
    tool={'leads.create':'crm.create_lead','leads.update':'crm.update_lead','leads.qualify':'crm.qualify_lead','leads.convert':'crm.convert_lead'}[name]
    step={'tool':tool,'payload':payload}
    if name!='leads.create': step['record_id']=ident
    return {'summary':'Review this lead action and its exact fields. Nothing has been changed. CRM permissions, qualification rules and duplicate checks apply at execution.','steps':[step]}
