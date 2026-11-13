"""Slot-filling dialogue for local action plans; never authorizes execution."""
import re
from app.ai_operator.local_nlp import Interpretation,parse

ACTIONS={'tasks.create','tasks.priority','tasks.status','tasks.schedule','milestone.create','ticket.create',
         'note.create','leads.message','leave.create','reminders.create'}


def reference(answer,expected=None):
    value=re.sub(r'\s*#\s*',' ',answer.casefold()).strip(' .!?')
    value=re.sub(r'\s+please$','',value)
    match=re.fullmatch(r'((?:[a-z]+\s+)*)([1-9]\d*)',value)
    if not match:return None,False
    words=set(match[1].split())
    allowed={'please','use','select','choose','the','requested','existing','with','is','id','number','numbered','project','task','lead','record','leave','type','request','invoice','deal'}
    if not words<=allowed:return None,False
    kinds=words&{'project','task','lead','leave','type','invoice','deal'}
    if 'type' in kinds:kinds.discard('leave')
    if expected and kinds and kinds!={expected}:return None,True
    return int(match[2]),False


def continue_action(current,prior,text,timezone,*,instant=None,model_scope=None):
    name=prior.get('intent');old=prior.get('slots') or {};pending=old.get('_awaiting')
    if name=='milestone.update':
        from app.ai_operator.milestone_actions import followup as milestone_followup
        return milestone_followup(current,prior,text,timezone)
    from app.ai_operator.ticket_actions import INTENTS as TICKET_INTENTS,followup as ticket_followup
    if name in TICKET_INTENTS:return ticket_followup(current,prior,text)
    if name=='employee.update':
        from app.ai_operator.employee_actions import followup
        return followup(current,prior,text)
    from app.ai_operator.crm_lead_actions import INTENTS,continue_lead
    if name in INTENTS:return continue_lead(current,prior,text)
    if name not in ACTIONS and pending!='project_id':return current
    from app.ai_operator.dialogue_tensorflow import predict
    act=predict(prior['module'],name,pending,text,model_scope)
    if act:current.neural={**current.neural,'dialogue_act':act}
    answer=text.strip();plain=answer.casefold().replace('’',"'").strip(' .!?')
    control=re.sub(r'^(?:please\s+)+','',plain)
    if control in {'cancel','cancel it','stop','never mind','nevermind','start over','do not proceed','do not send it','discard this action','forget this request','cancel this request','cancel the current action','discard this draft','stop this request','cancel the proposed draft','end this operation','abandon this draft','stop the pending action'}:
        return Interpretation(prior['module'],'cancelled',1,{},None,{})
    # Permission bypasses, destructive requests and compound operations stay rejected.
    if current.question and any(word in current.question for word in ('cannot bypass','destructive')):return current
    if re.fullmatch(r'not (?:high|medium|low|urgent|critical)',plain) and (name=='tasks.priority' or name in {'tasks.create','ticket.create'}):
        revised=dict(old);revised.pop('priority',None);revised['_awaiting']='priority'
        return Interpretation(prior['module'],name,1,revised,'Which priority should replace it: High, Medium or Low?',current.neural)
    if re.fullmatch(r'not\s+(?:today|tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|\d{4}-\d{2}-\d{2})',plain):
        revised=dict(old);field=pending if pending in {'from_date','to_date'} else 'date'
        for key in ('due_date','date',field):revised.pop(key,None)
        revised['_awaiting']=field
        return Interpretation(prior['module'],name,1,revised,'What date should replace it?',current.neural)
    # An answer to a field question is not an approval or a literal question title.
    help_reply=re.fullmatch(r'(?:what does (?:that|this) mean|which options are available|what are my choices|can you explain|could you explain|explain this field|help me choose|I (?:do not|don\'t) know|I need help|not sure|what should I enter|why do you need this)',control,re.I)
    if not answer.startswith(('"','“')) and act and act['act']=='clarify' and act['score']>=.9 and act['margin']>=.25 and re.search(r'\b(?:explain|explanation|clarify|clarification|understand|question|choices|options|answer|guidance|meaning)\b',control):help_reply=True
    ambiguous=control in {'yes','okay','ok','sure','no','approve','confirm','go ahead','do it'}
    # The trained act can recognize longer acknowledgements while a field is
    # still missing. This only asks for detail; it never grants execution.
    if pending and pending!='is_half_day' and not answer.startswith(('\"','“')) and act and act['act']=='clarify' and act['score']>=.9 and act['margin']>=.25:
        if re.match(r'^(?:yes|sure|ok(?:ay)?|fine|agreed|all right|sounds (?:good|reasonable)|that (?:looks|seems|sounds) (?:fine|good|reasonable)|i (?:agree|confirm))\b',control):ambiguous=True
    if pending and (help_reply or ambiguous and pending!='is_half_day'):
        examples={'title':'a short title such as Review client response','subject':'the exact email subject','body':'the exact message text',
                  'project_id':'an existing project ID','record_id':'an existing record ID','date':'a date such as tomorrow',
                  'time':'a time such as 09:30 or 3 pm','channel':'email or in app','priority':'High, Medium or Low','status':'Done, In Progress or Blocked'}
        detail=examples.get(pending,'the requested '+pending.replace('_',' '))
        return Interpretation(prior['module'],name,1,dict(old),f'Please provide {detail}. This reply has not approved or executed anything.',current.neural)
    if current.question and 'one operation at a time' in current.question:
        if not (pending in {'title','body','subject','reason'} and act and act['act']=='provide_value' and act['score']>=.9 and act['margin']>=.3):return current
    if re.match(r'^(CRM|PMS|HRMS|HR|Sales|SRM)\s*:',answer,re.I):return current
    # An explicit new operation replaces the proposal, rather than becoming slot text.
    operation=re.match(r'^(show|list|find|create|add|delete|send|apply|request|approve)\b',answer,re.I)
    if operation and pending not in {'body','reason'}:
        # A title such as Request staffing support is a field value when no
        # supported business operation was parsed. Actual leave/ticket/action
        # requests still replace the proposal through the existing checks.
        literal_request_title=pending=='title' and operation[1].casefold()=='request' and current.intent not in ACTIONS
        if not literal_request_title:return current
    # A correction must replace the superseded value, not retain its first mention.
    revised=re.match(r'^not\s+[^,]+,\s*(.+)$',answer,re.I)
    fresh=dict(parse(revised[1],prior['module'],timezone=timezone,instant=instant,model_scope=model_scope).slots if revised else current.slots)
    correction=re.match(r'^(?:actually[, ]+)?(?:(?:change|set|update)\s+)?(?:the\s+)?(title|subject|body|reason)\s*(?:to|is|:|=)\s*(.+)$',answer,re.I)
    rename=re.match(r'^(?:actually[, ]+)?(?:rename|call|name)\s+(?:it|this|the task)\s+(?:to\s+)?(.+)$',answer,re.I)
    allowed={'title'} if name in {'tasks.create','milestone.create','ticket.create','reminders.create'} else {'subject','body'} if name=='leads.message' else {'reason'} if name=='leave.create' else set()
    corrected=None
    if correction and correction[1].casefold() in allowed:
        corrected=correction[1].casefold();fresh[corrected]=correction[2].strip().strip('"“”')
    elif rename and 'title' in allowed:corrected='title';fresh['title']=rename[1].strip().strip('"“”')
    if pending in {'title','subject','body','reason'} and corrected is None:
        value=re.sub(r'^(?:the\s+)?'+pending+r'\s*(?:is|:|=)?\s*','',answer,flags=re.I).strip().strip('"“”')
        if value and not (pending=='title' and fresh.get('due_date') and not re.search(r'["“]',answer)):fresh[pending]=value
    if pending in {'record_id','project_id','leave_type_id'}:
        expected='project' if pending=='project_id' else 'type' if pending=='leave_type_id' else 'lead' if name=='note.create' else old.get('entity') if name=='reminders.create' else 'task'
        ident,mismatch=reference(answer,expected)
        if mismatch:return Interpretation(prior['module'],name,1,dict(old),f'Please give the {expected} ID requested in this conversation.',current.neural)
        if ident:fresh[pending]=ident
        elif pending=='leave_type_id':fresh['leave_type_name']=answer
    if pending=='channel' and plain in {'email','whatsapp','sms','in app','in_app'}:fresh['channel']=plain.replace(' ','_')
    if pending in {'from_date','to_date'} and fresh.get('due_date'):fresh[pending]=fresh['due_date']
    if pending=='to_date' and plain in {'same day','the same day','one day'} and old.get('from_date'):fresh['to_date']=old['from_date']
    if name=='leave.create':
        if 'full day' in plain or plain in {'no','not half day'}:fresh['is_half_day']=False
        if 'half day' in plain or plain in {'morning','afternoon','first half','second half'}:
            fresh['is_half_day']=True
            if 'morning' in plain or plain=='first half':fresh['half_day_period']='First Half'
            if 'afternoon' in plain or plain=='second half':fresh['half_day_period']='Second Half'
    if pending=='time':
        if plain in {'noon','at noon'}:fresh['time']='12:00'
        if plain in {'midnight','at midnight'}:fresh['time']='00:00'
        match=re.fullmatch(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',plain)
        if match:
            h=int(match[1]);m=int(match[2] or 0);meridian=match[3]
            if meridian and 1<=h<=12:h=h%12+(12 if meridian=='pm' else 0)
            if 0<=h<24 and 0<=m<60:fresh['time']=f'{h:02}:{m:02}'
    if pending=='entity' and plain in {'task','lead','deal','project','leave','invoice'}:fresh['entity']=plain
    if pending=='date' and fresh.get('due_date'):fresh['date']=fresh['due_date']
    # Never lose the original mutation verb when a reply only supplies data.
    merged={**old,**fresh,'action_verb':old.get('action_verb')}
    if fresh.get('due_date'):merged.pop('invalid_date',None)
    merged.pop('_awaiting',None)
    accepted=bool(pending and pending in fresh) or bool(set(fresh)-{'action_verb','title'} & {'due_date','priority','status','channel','subject','body','record_id','is_half_day','half_day_period'})
    if corrected:accepted=True
    if pending=='is_half_day':accepted='is_half_day' in fresh
    if pending=='half_day_period':accepted='half_day_period' in fresh
    if pending=='leave_type_id' and 'leave_type_name' in fresh:accepted=True
    if name in {'tasks.create','milestone.create','ticket.create'} and fresh.get('title') and re.match(r'^(?:["“]|title\b|call it\b|rename it\b)',answer,re.I):accepted=True
    if not accepted:
        if pending:return Interpretation(prior['module'],name,1,dict(old),None,current.neural)
        return current
    return Interpretation(prior['module'],name,1,merged,None,current.neural)


def need(intent,field,question):
    intent.slots['_awaiting']=field
    return {'summary':'I am collecting details for this action. Nothing has been changed.','question':question,'steps':[]}
