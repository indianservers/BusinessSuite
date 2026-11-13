"""Milestone conversation slots; native PMS remains authoritative."""
import re
from fastapi import HTTPException
from app.apps.project_management.milestone_management import Edit,changes
INTENT='milestone.update'
LABEL=re.compile(r'(?:^|[,;]\s*)(name|description|status|progress|start date|due date|owner user id)\s*:\s*',re.I)


class AmbiguousFields(ValueError):
    def __init__(self,field):self.field=field


def values(text,timezone='Asia/Kolkata'):
    result={};matches=list(LABEL.finditer(unquoted(text)))
    for index,match in enumerate(matches):
        raw=text[match.end():matches[index+1].start() if index+1<len(matches) else None].strip().strip(',;').strip()
        if len(raw)>1 and raw[0]==raw[-1] and raw[0] in {'"',"'"}:raw=raw[1:-1]
        key={'progress':'progress_percent','start date':'start_date','due date':'due_date','owner user id':'owner_user_id'}.get(match[1].lower(),match[1].lower())
        if raw.lower() in {'clear','none'} and key not in {'status','name','progress_percent'}:value=None
        elif key in {'progress_percent','owner_user_id'}:value=int(raw.rstrip('%')) if raw.rstrip('%').isdigit() else raw
        elif key in {'start_date','due_date'}:
            from app.ai_operator.pms_agent import resolve_date
            try:value=resolve_date(raw,timezone)
            except HTTPException:value=raw
        else:value=raw.title() if key=='status' else raw
        if key in result and result[key]!=value:raise AmbiguousFields(key)
        result[key]=value
    return result


def unquoted(text):
    """Keep token offsets while hiding quoted literal names/descriptions."""
    masked=list(text);quote=None;escaped=False
    for index,char in enumerate(text):
        if quote:
            masked[index]=' '
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char==quote:quote=None
        elif char in {'"',"'"} and not (char=="'" and index and index+1<len(text) and text[index-1].isalnum() and text[index+1].isalnum()):
            quote=char;masked[index]=' '
    return ''.join(masked)


def bind_reference(text,ident):
    reference=f'milestone #{ident}' if ident else 'milestone'
    return re.sub(r'^(\s*(?:PMS\s*:\s*)?(?:please\s+)?(?:update|edit|set|mark|rename|reschedule|move|complete|finish|reopen|assign)\s+)(?:it|that milestone|the same milestone)\b',
                  lambda match:match[1]+reference,text,count=1,flags=re.I)


def interpret(text,timezone='Asia/Kolkata'):
    from app.ai_operator.local_nlp import Interpretation
    try:return interpret_changes(text,timezone)
    except AmbiguousFields as conflict:
        slots={'values':{}}
        ident=re.search(r'\bmilestone\s*#?\s*([1-9]\d{0,9})\b',unquoted(text),re.I)
        if ident and int(ident[1])<=2147483647:slots['record_id']=int(ident[1])
        return Interpretation('PMS',INTENT,1,slots,f"You supplied conflicting {conflict.field.replace('_',' ')} values. Which single value should I review? Nothing has changed.")


def interpret_changes(text,timezone='Asia/Kolkata'):
    from app.ai_operator.local_nlp import Interpretation
    separators=list(re.finditer(r'\b(?:and|then)\s+(?=(?:please\s+)?(?:update|edit|set|mark|rename|reschedule|move|complete|finish|reopen|assign|send|delete|create|approve)\b)',unquoted(text),re.I))
    if not separators:return single(text,timezone)
    parts=[];start=0
    for match in separators:parts.append(text[start:match.start()]);start=match.end()
    parts.append(text[start:])
    first=single(parts[0],timezone)
    if first is None:return None
    slots={**first.slots,'values':dict(first.slots.get('values') or {})}
    if first.question:return first
    if not slots['values']:return Interpretation('PMS',INTENT,1,slots,'One clause is missing its proposed milestone changes. Supply that detail before reviewing the compound edit.')
    for clause in parts[1:]:
        clause=bind_reference(clause,slots.get('record_id'))
        result=single(clause,timezone)
        if not result or result.question or not result.slots.get('values') or result.slots.get('record_id')!=slots.get('record_id'):
            return Interpretation('PMS',INTENT,1,slots,'This compound request needs clarification. Keep edits on one explicitly selected milestone or prepare separate workflow steps. Nothing has run.')
        for key,value in result.slots['values'].items():
            if key in slots['values'] and slots['values'][key]!=value:
                return Interpretation('PMS',INTENT,1,slots,'Two clauses propose different values for the same milestone field. Which value should be reviewed?')
            slots['values'][key]=value
    return Interpretation('PMS',INTENT,1,slots)


def single(text,timezone='Asia/Kolkata'):
    from app.ai_operator.local_nlp import Interpretation
    text=re.sub(r'^\s*PMS\s*:\s*','',text,flags=re.I).strip()
    match=re.match(r'^(?:please\s+)?(update|edit|set|mark|rename|reschedule|move|complete|finish|reopen|assign)\s+(?:the\s+)?milestone\b',text,re.I)
    if not match:return None
    slots={'values':{}}
    ident=re.search(r'\bmilestone\s*#?\s*([1-9]\d{0,9})\b',text,re.I)
    if ident and int(ident[1])<=2147483647:slots['record_id']=int(ident[1])
    tail=text[ident.end() if ident else match.end():].lstrip(' ,;:')
    slots['values']=values(tail,timezone)
    implied='Completed' if match[1].lower() in {'complete','finish'} or match[1].lower()=='mark' and re.match(r'^(?:as\s+)?(?:complete|completed|done)\b',tail,re.I) else 'In Progress' if match[1].lower()=='reopen' else None
    if implied:
        if 'status' in slots['values'] and slots['values']['status']!=implied:raise AmbiguousFields('status')
        slots['values']['status']=implied
    if not slots['values'] and match[1].lower()=='rename':
        title=re.fullmatch(r'(?:to|as|called)\s+(.+)',tail,re.I)
        if title:slots['values']={'name':title[1][1:-1] if len(title[1])>1 and title[1][0]==title[1][-1] and title[1][0] in {'"',"'"} else title[1]}
    if not slots['values'] and match[1].lower()=='assign':
        owner=re.fullmatch(r'to\s+(?:user\s*)?#?\s*([1-9]\d{0,9})',tail,re.I)
        if owner:slots['values']={'owner_user_id':int(owner[1])}
    if not slots['values'] and match[1].lower() in {'reschedule','move'}:
        due=re.search(r'^(?:(?:to|due|until)\s+)?(.+)$',tail,re.I)
        if due:slots['values']=values('due date: '+due[1],timezone)
    if re.search(r'client\s+approval|\b(?:then|and)\s+(?:send|delete|create|approve)\b',unquoted(tail),re.I):
        return Interpretation('PMS',INTENT,1,slots,'Use one milestone edit. Client approval requires its native review workflow.')
    return Interpretation('PMS',INTENT,1,slots)


def followup(current,prior,text,timezone):
    from app.ai_operator.local_nlp import Interpretation
    try:return followup_changes(current,prior,text,timezone)
    except AmbiguousFields as conflict:
        return Interpretation('PMS',INTENT,1,dict(prior.get('slots') or {}),f"Which single {conflict.field.replace('_',' ')} value should I review? The previous draft is unchanged.")


def followup_changes(current,prior,text,timezone):
    from app.ai_operator.local_nlp import Interpretation
    old=dict(prior.get('slots') or {});plain=text.strip().casefold().strip(' .!?')
    if plain in {'cancel','cancel it','stop','never mind','discard this draft'}:return Interpretation('PMS','cancelled',1,{})
    ident=old.get('record_id')
    natural=bind_reference(text,ident)
    parsed=interpret(natural,timezone)
    if parsed:
        if parsed.question:return parsed
        target=parsed.slots.get('record_id') or ident
        if target==ident or (ident is None and old.get('_awaiting')=='record_id'):
            old['values']={**old.get('values',{}),**parsed.slots.get('values',{})}
            old.pop('_awaiting',None)
            return Interpretation('PMS',INTENT,1,{**old,**({'record_id':target} if target else {})})
        return parsed
    if current.intent==INTENT:return current
    if old.get('_awaiting')=='record_id':
        match=re.fullmatch(r'(?:milestone\s*)?#?\s*([1-9]\d{0,9})',text.strip(),re.I)
        if not match:
            fields=values(text,timezone)
            if fields:
                old['values']={**old.get('values',{}),**fields}
                return Interpretation('PMS',INTENT,1,old)
            return Interpretation('PMS',INTENT,1,old,'Supply a milestone #ID or link selection; an acknowledgement is not a record selection.')
        if int(match[1])>2147483647:return Interpretation('PMS',INTENT,1,old,'Supply an existing milestone record ID.')
        old['record_id']=int(match[1])
    else:
        fields=values(text,timezone)
        if not fields:return Interpretation('PMS',INTENT,1,old,'Supply labelled milestone fields, such as due date: tomorrow, status: In Progress, or owner user id: 12.')
        old['values']={**old.get('values',{}),**fields}
    old.pop('_awaiting',None)
    return Interpretation('PMS',INTENT,1,old)


def proposal(intent,context):
    if intent.intent!=INTENT:return None
    from app.ai_operator.local_dialogue import need
    from app.ai_operator.evidence import records
    if intent.question:return {'summary':'Milestone edit needs clarification. Nothing changed.','question':intent.question,'steps':[]}
    ident=intent.slots.get('record_id');payload=intent.slots.get('values') or {}
    if not ident:return need(intent,'record_id','Which milestone #ID should change? I will check its project and your current permissions.')
    row=next((r for p in context if p['tool']=='pms.milestone' for r in records(p['records']) if r.get('id')==ident),None)
    if not row:return need(intent,'record_id','Select an authorized milestone #ID.')
    if not payload:return need(intent,'fields','What should change? Supply name, dates, status, progress or an eligible owner user ID.')
    try:
        Edit.model_validate({**payload,'expected_revision':row['revision']})
        payload=changes(row,payload)
        Edit.model_validate({**payload,'expected_revision':row['revision']})
    except (ValueError,HTTPException):return need(intent,'fields','A milestone value or lifecycle change is invalid. Check dates, status/progress and owner ID. Pending or approved client milestones require their native approval workflow.')
    return {'summary':'Review the milestone changes. Nothing has changed yet. Client approval is separate.','steps':[{'tool':'pms.update_milestone','record_id':ident,'payload':{**payload,'expected_revision':row['revision']}}]}


def project(db,user,ident,action):
    from app.apps.project_management.milestone_management import selected
    return selected(db,user,ident,action)[1]


def preview(step,record,earlier,db=None,user=None):
    if step.payload.get('expected_revision')!=record.get('revision'):raise HTTPException(409,'Milestone changed; prepare a fresh review')
    if any(s.tool=='pms.update_milestone' and s.record_id==step.record_id for s in earlier):raise HTTPException(422,'Combine changes to the same milestone in one reviewed step')
    patch=changes(record,step.payload)
    if db is not None and 'owner_user_id' in patch:
        from app.apps.project_management.milestone_management import owner_allowed
        owner_allowed(db,project(db,user,step.record_id,'manage_tasks'),patch['owner_user_id'])
    return {'record_id':step.record_id,'record_name':record.get('name'),'project_id':record.get('project_id'),'changes':[{'field':key,'before':record.get(key),'after':value} for key,value in patch.items()]}
