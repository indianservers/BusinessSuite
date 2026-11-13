"""Local ticket action drafts reuse native helpdesk schemas and Suite execution."""
import re
from pydantic import ConfigDict,Field,model_validator
from app.schemas.helpdesk import HelpdeskTicketStatusUpdate,HelpdeskTicketAssign,HelpdeskTicketEscalation,HelpdeskTicketReply


class Status(HelpdeskTicketStatusUpdate):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=1,strict=True)


class Assign(HelpdeskTicketAssign):
    model_config=ConfigDict(extra='forbid')
    assign_to_user_id:int=Field(gt=0,le=2147483647,strict=True)
    expected_version:int=Field(ge=1,strict=True)


class Escalate(HelpdeskTicketEscalation):
    model_config=ConfigDict(extra='forbid')
    escalated_to:int|None=Field(default=None,gt=0,le=2147483647,strict=True)
    expected_version:int=Field(ge=1,strict=True)


class Reply(HelpdeskTicketReply):
    expected_version:int=Field(ge=1,strict=True)
    is_internal:bool  # A planner must choose the visibility explicitly.

    @model_validator(mode='after')
    def text_required(self):
        if not self.message.strip():raise ValueError('Supply reply text')
        return self


INTENTS={'ticket.status','ticket.assign','ticket.escalate','ticket.reply'}
COMMAND=re.compile(r'^(?:please\s+)?(resolve|close|reopen|update|mark|assign|escalate|reply to|add internal note to)\s+(?:the\s+)?(?:helpdesk\s+)?ticket\b',re.I)


def interpret(text):
    from app.ai_operator.local_nlp import Interpretation
    text=re.sub(r'^\s*(?:HRMS|HR)\s*:\s*','',text,flags=re.I).strip();match=COMMAND.match(text)
    if not match:return None
    verb=match[1].casefold();name='ticket.'+({'assign':'assign','escalate':'escalate','reply to':'reply','add internal note to':'reply'}.get(verb,'status'))
    slots={};tail=text[match.end():].strip();ident=re.match(r'^#\s*([1-9]\d*)\b',tail)
    if ident:
        if len(ident[1])>10 or int(ident[1])>2147483647:return Interpretation('HRMS',name,1,slots,'Supply a valid ticket #ID.')
        slots['record_id']=int(ident[1]);tail=tail[ident.end():].strip()
    if verb in {'resolve','close','reopen'}:slots['status']={'resolve':'Resolved','close':'Closed','reopen':'Open'}[verb]
    if name=='ticket.reply':slots['is_internal']=verb=='add internal note to'
    if tail:
        parsed=fields(tail)
        if not parsed:return Interpretation('HRMS',name,1,slots,'Use labelled fields such as status: Pending, user id: 4, reason: Needs HR review, or message: Exact reply text.')
        slots.update(parsed)
    return Interpretation('HRMS',name,1,slots)


def fields(text):
    # A reply body is literal content, even when it contains field-like labels.
    message=re.fullmatch(r'\s*message\s*[:=]\s*(.+)',text,re.I|re.S)
    if message:
        value=message[1].strip()
        if len(value)>=2 and (value[0],value[-1]) in {('"','"'),('“','”')}:value=value[1:-1]
        return {'message':value}
    result={};labels={'status':'status','user id':'assign_to_user_id','reason':'escalation_reason','escalate to user id':'escalated_to','message':'message'}
    pattern='|'.join(re.escape(k) for k in sorted(labels,key=len,reverse=True))
    for part in re.split(r',\s*(?=(?:'+pattern+r')\s*[:=])',text,flags=re.I):
        match=re.fullmatch(r'\s*('+pattern+r')\s*[:=]\s*(.+)',part,re.I|re.S)
        if not match:return None
        key=labels[match[1].casefold()];raw=match[2].strip().strip('"“”')
        if key in result:return None
        if key.endswith('_id') or key=='escalated_to':
            if not re.fullmatch(r'[1-9]\d{0,9}',raw) or int(raw)>2147483647:return None
            result[key]=int(raw)
        else:result[key]=raw
    return result or None


def followup(current,prior,text):
    from app.ai_operator.local_nlp import Interpretation
    old=dict(prior.get('slots') or {});name=prior['intent'];reply=text.strip();plain=reply.casefold().strip(' .!?')
    if plain in {'cancel','cancel it','stop','never mind','nevermind','discard this draft'}:return Interpretation('HRMS','cancelled',1,{})
    if current.question and any(k in current.question for k in ('cannot bypass','destructive','one operation at a time')):return current
    if current.intent in INTENTS:return current
    if re.match(r'^(?:CRM|PMS|HRMS|HR|Sales|SRM)\s*:|^(?:show|list|find|create|add|delete|send|apply|request|approve|update|edit|change|assign|resolve|close|reopen|escalate|reply)\b',reply,re.I):return current
    if old.get('_awaiting')=='record_id':
        match=re.fullmatch(r'(?:ticket\s*)?(?:#\s*)?([1-9]\d{0,9})',reply,re.I)
        if not match or int(match[1])>2147483647:return Interpretation('HRMS',name,1,old,'Supply the requested ticket #ID, not an employee or task ID.')
        old['record_id']=int(match[1])
    else:
        parsed=fields(reply)
        if not parsed:return Interpretation('HRMS',name,1,old,'Supply the requested labelled ticket fields. An acknowledgement does not approve an action.')
        old.update(parsed)
    old.pop('_awaiting',None)
    return Interpretation('HRMS',name,1,old)


def proposal(intent,context):
    if intent.intent not in INTENTS:return None
    from app.ai_operator.local_dialogue import need
    from app.ai_operator.evidence import records
    if intent.question:return {'summary':'Ticket details need clarification. No action executed.','question':intent.question,'steps':[]}
    name=intent.intent;slots=intent.slots;ident=slots.get('record_id')
    if not ident:return need(intent,'record_id','Which ticket #ID should I use? I will check your current access.')
    record=next((r for p in context if p['tool']=='hrms.ticket' for r in records(p['records']) if r.get('id')==ident),None)
    if not record:return need(intent,'record_id','Select an authorized ticket #ID.')
    models={'ticket.status':Status,'ticket.assign':Assign,'ticket.escalate':Escalate,'ticket.reply':Reply}
    required={'ticket.status':('status','What status? Reply status: Open, In Progress, Pending, Resolved or Closed.'),
        'ticket.assign':('assign_to_user_id','Which active company user should own it? Reply user id: 4. Assignment also sets status to In Progress.'),
        'ticket.escalate':('escalation_reason','Why should this ticket be escalated? Reply reason: followed by your exact reason. Escalation sets priority to Critical.'),
        'ticket.reply':('message','What exact text should be posted? Reply message: followed by your text. The preview will show whether it is a requester-visible reply or an internal note.')}
    field,question=required[name]
    if not slots.get(field):return need(intent,field,question)
    model=models[name];payload={k:slots[k] for k in model.model_fields if k in slots}
    if set(slots)-set(model.model_fields)-{'record_id','_awaiting'}:
        return need(intent,field,'These fields belong to different ticket operations. Start one exact ticket action, or use a reviewed multi-step workflow.')
    payload['expected_version']=record.get('version')
    if name=='ticket.status':
        match=next((v for v in ('Open','In Progress','Pending','Resolved','Closed') if v.casefold()==str(payload.get('status')).casefold()),None)
        if match:payload['status']=match
    try:model.model_validate(payload)
    except ValueError:return need(intent,field,'Some ticket details are invalid. Supply corrected labelled fields for this action.')
    visibility=' This is an internal staff note.' if payload.get('is_internal') else ' This reply is visible to the requester.' if name=='ticket.reply' else ''
    return {'summary':'Review this exact ticket action. It has not executed.'+visibility,'steps':[
        {'tool':{'ticket.status':'hrms.status_ticket','ticket.assign':'hrms.assign_ticket','ticket.escalate':'hrms.escalate_ticket','ticket.reply':'hrms.reply_ticket'}[name],'record_id':ident,'payload':payload}]}


def projection(value):
    fields={'id','ticket_number','subject','description','status','priority','assigned_to','version','employee_id'}
    return {k:v[:4000] if isinstance(v,str) else v for k,v in value.items() if k in fields} if isinstance(value,dict) else {}


PLANNING_POLICY={'version':1,'instructions':
    'Ticket native versions are server concurrency controls, not information users should supply. Read the current version through authorized hrms.ticket context_requests after resolving its numeric record ID. A ticket number such as QA-42 is not a numeric record ID; never guess one. Ask for a ticket link or record ID when the supplied reference cannot be resolved. Ask for a full name, email, mention or known account reference when a person is ambiguous; employee record IDs are not user account IDs. Resolve supplied person names/emails through hrms.people when available in the authorized catalog. Only use authorized directory tools present in the supplied catalog. When identifiers are missing, retain the user-requested steps as a clearly proposed, non-executed outline in summary, ask one focused clarification and return steps []. Describing the user requested proposal does not require inventing business facts. Never ask a user for expected_version, claim a note is saved, or resolve a ticket until the preceding reviewed note step has a successful receipt.'}


TOOLS={'hrms.status_ticket','hrms.assign_ticket','hrms.escalate_ticket','hrms.reply_ticket'}


def preview(step,record,earlier):
    """Native versions protect a reviewed chain of changes to the same ticket."""
    from fastapi import HTTPException
    count=sum(s.tool in TOOLS and s.record_id==step.record_id for s in earlier)
    if step.payload.get('expected_version')!=record.get('version',0)+count:
        raise HTTPException(409,'Ticket version differs from this reviewed workflow')
    payload=step.payload
    proposed={'status':payload['status']} if step.tool=='hrms.status_ticket' else {'assigned_to':payload['assign_to_user_id'],'status':'In Progress'} if step.tool=='hrms.assign_ticket' else {'priority':'Critical','escalation_reason':payload['escalation_reason'],**({'escalated_to':payload['escalated_to']} if 'escalated_to' in payload else {})} if step.tool=='hrms.escalate_ticket' else {'message':payload['message'],'visibility':'Internal staff note' if payload['is_internal'] else 'Requester-visible reply'}
    return count>0,{'record_id':step.record_id,'changes':[{'field':k,'before':record.get(k),'after':v} for k,v in proposed.items()]}
