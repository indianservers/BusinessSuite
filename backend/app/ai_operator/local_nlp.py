"""TensorFlow-trained local intent inference with retrieval/rule safeguards and typed slots.

No LLM, network, pickle, credential, or executable training input is used.
Intent retrieval never authorizes a read or executes a business action.
"""
import math
import re

from dataclasses import dataclass, field
from datetime import datetime

from zoneinfo import ZoneInfo
from fastapi import HTTPException

from app.ai_operator.local_corpus import VERSION, examples

ALIASES = {'SRM':'Sales','SALES':'Sales','CRM':'CRM','PMS':'PMS','HRMS':'HRMS','HR':'HRMS'}
SCOPES = {'Sales':'SRM','CRM':'CRM','PMS':'PMS','HRMS':'HRMS'}
from app.ai_operator.local_features import features,fit,head


def semantic_intent(command,module):
    """Conservative entity/filter grammar overrides ambiguous bag-of-word matches."""
    text=command.casefold()
    read=bool(re.match(r'^(?:please\s+)?(?:show|list|find|get|display|which|what|how|who|can|could|bring|look|give|check|anything)',text))
    if re.search(r'\b(?:reminders?|remind me)\b',text) and 'today' in text and read:return 'reminders.today'
    if re.search(r'\b(?:jobs|priorities|on my plate)\b|what.*(?:should|need).*do|what.*work.*today',text) and 'today' in text:return 'jobs.today'
    if module in {'CRM','PMS','HRMS'} and (re.match(r'^(?:please\s+)?remind me\b',text) or re.match(r'^(?:please\s+)?(?:create|set|schedule|add|prepare)\b',text) and 'reminder' in text):return 'reminders.create'
    if module in {'CRM','PMS'}:
        if module=='PMS' and re.search(r'\btask(?:\s+(?:record|item))?\s*#',text) and re.search(r'schedul|\bdates\b|\bstart date\b',text) and re.match(r'^(?:please\s+)?(?:schedule|plan|suggest|prepare|draft|start|set)\b',text):return 'tasks.schedule'
        if module=='CRM' and re.match(r'^(?:please\s+)?(?:add|record|write|save|prepare|attach|put)\b',text) and re.search(r'\bnote\b',text.partition(':')[0]) and re.search(r'\blead\s*#',text):return 'note.create'
        if re.match(r'^(?:please\s+)?(?:set|mark|make|change|update|raise|complete|finish)\b',text) and re.search(r'\btask(?:\s+(?:record|item))?\s*#',text) and 'reminder' not in text:
            return 'tasks.priority' if re.search(r'priority|\b(high|urgent|critical|medium|low)\b',text) else 'tasks.status'
        if re.match(r'^(?:please\s+)?(?:create|add|make|prepare|draft)\b',text) and 'reminder' not in text:
            if module=='PMS' and re.search(r'\bmilestone\b',text):return 'milestone.create'
            if re.search(r'\btask\b|\bfollow up\b',text):return 'tasks.create'
        if re.match(r'^(?:please\s+)?(?:set|mark|make|change|update|raise|complete|finish)\b',text) and re.search(r'\btask\s*#',text) and 'reminder' not in text:
            return 'tasks.priority' if re.search(r'priority|\b(high|urgent|critical|medium|low)\b',text) else 'tasks.status'
        if read:
            if re.search(r'\brisk|delivery.*block',text):return 'risk'
            if re.search(r'summary|summariz|overview|brief',text):return 'summary'
            if re.search(r'blocked|stuck|blockers',text):return 'tasks.blocked'
            if re.search(r'overdue|\blate\b|past due|missed.*deadline|deadlines?.*missed',text):return 'tasks.overdue'
            if re.search(r'unassigned|no (?:owner|assignee)|without\s+(?:an?\s+)?(?:owner|assignees?)\b|ownerless|(?:awaiting|pending|waiting for) assignment',text):return 'tasks.unassigned' if module=='PMS' else None
            if re.search(r'(?:my|\bI\b|\bme\b).*assign|assign.*(?:me|my)|tasks I own',text,re.I):return 'tasks.mine'
            if module=='PMS' and re.search(r'bandwidth|capacity|resource.*availability|team availability',text):return 'capacity'
            if module=='PMS' and re.search(r'dependenc|prerequisit|depend on',text):return 'dependencies'
    if module=='Sales':
        if 'invoice' in text or 'billing' in text:
            if re.match(r'^(?:please\s+)?(?:send|mail|email|deliver|dispatch)\b',text):return 'invoice.send'
            if re.match(r'^(?:please\s+)?(?:create|make|add|draft|prepare)\b',text) and not re.search(r'totals|amount.*report',text):return 'invoice.create'
            if read:
                if re.search(r'unpaid|outstanding|balances|pending.*payment',text):return 'invoices.unpaid'
                if re.search(r'overdue|\blate\b|past due|missed',text):return 'invoices.overdue'
                if 'today' in text:return 'invoices.today'
        if re.search(r'sales.*(?:perform|figures|dashboard|totals)',text):return 'sales.dashboard'
    if module=='HRMS' and read:
        if re.search(r'vacation|leave|time off',text):
            if re.search(r'awaiting.*(?:decision|approv)|pending.*approv|approv.*queue',text):return 'leave.pending'
            if re.search(r'reject|declin|turned down|denied',text):return 'leave.rejected'
            if re.search(r'balance|remain|entitlement|available.*days',text):return 'leave.balance'
    return None


@dataclass
class Interpretation:
    module: str
    intent: str
    confidence: float = 0
    slots: dict = field(default_factory=dict)
    question: str | None = None
    neural: dict = field(default_factory=dict)


def parse(text, module=None, *, timezone='Asia/Kolkata', instant=None, model_scope=None):
    text=text.strip(); command=head(text)
    unquoted=re.sub(r'"[^"\n]*"|“[^”\n]*”', ' ',command)
    explicit=re.match(r'^\s*(CRM|PMS|HRMS|HR|Sales|SRM)\s*:',text,re.I)
    selected=ALIASES.get(str(module).upper(),'CRM')
    if explicit: selected=ALIASES[explicit[1].upper()]
    elif re.search(r'\b(lead|leads|CRM|contacts|customer companies)\b',unquoted,re.I):selected='CRM'
    elif re.search(r'\b(invoice|invoices|inventory|stock|sales order|billing|sales)\b',unquoted,re.I):selected='Sales'
    elif re.search(r'\b(HRMS|HR|leave|employee|employees|payroll|attendance|helpdesk|staff|time off)\b',unquoted,re.I):selected='HRMS'
    elif re.search(r'\b(PMS|project|projects|milestone|playbook|dependencies|capacity)\b',unquoted,re.I):selected='PMS'
    from app.ai_operator.conversation_control import is_new_conversation
    if is_new_conversation(text):return Interpretation(selected,'conversation.reset',1)
    unsafe=re.search(r'\b(?:ignore|bypass|skip|disable)\s+(?:all\s+)?(?:permissions?|approvals?|consent|security|instructions)|without\s+(?:consent|approval)|system\s+prompt',unquoted,re.I)
    if unsafe:return Interpretation(selected,'unsupported',question='I cannot bypass permissions, consent or action review. Describe one permitted operation.')
    if re.search(r'\b(delete|purge|drop|destroy|execute sql)\b',unquoted.partition(':')[0],re.I):
        return Interpretation(selected,'unsupported',question='This destructive operation is not supported by local commands. Use the authorized module workflow.')
    compound=re.sub(r'\bmemory and playbooks\b','playbooks',unquoted.partition(':')[0],flags=re.I)
    if re.search(r'\band\b|\balso\b|;',compound,re.I):
        return Interpretation(selected,'unsupported',question='Please request one operation at a time so its scope and review are clear.')
    rows,idf,vectors=fit(); f=features(command)
    query={term:(1+math.log(count))*idf[term] for term,count in f.items() if term in idf}
    norm=math.sqrt(sum(v*v for v in query.values())) or 1
    scores={}
    for row,vector in zip(rows,vectors):
        if row['module']!=selected:continue
        score=sum(vector.get(term,0)*value/norm for term,value in query.items())
        scores[row['intent']]=max(score,scores.get(row['intent'],0))
    ranking=sorted(scores.items(),key=lambda p:(-p[1],p[0])); intent,confidence=ranking[0]
    from app.ai_operator.local_tensorflow import predict
    neural=predict(command,selected,model_scope) or {}
    neural_accepted=bool(neural and neural['score']>=.80 and neural['margin']>=.20 and
        (scores.get(neural['intent'],0)>=.25 or neural.get('reviewed_training') and neural.get('feature_support',0)>=.5))
    semantic=semantic_intent(unquoted,selected)
    # Exact normalized exemplars are deterministic; unseen phrases must be distinctive.
    exact={row['intent'] for row in rows if row['module']==selected and features(row['text'])==f}
    question=None
    if len(exact)==1:intent=next(iter(exact));confidence=1
    elif semantic:intent=semantic;confidence=1
    elif neural_accepted:
        intent=neural['intent'];confidence=neural['score'];neural['used']=True
    elif confidence<.36 or len(ranking)>1 and confidence-ranking[1][1]<.045:
        intent='unsupported'
        question='Please name the module and operation, for example “CRM: what are todays jobs?” or “PMS: show blocked tasks”.'
    # A retrieval match cannot turn a read into a mutation. Explicit verb grammar
    # also generalizes status updates beyond the training examples' Done value.
    if semantic!='tasks.schedule' and re.match(r'^(?:please\s+)?(?:set|mark|make|change|update|raise|complete|finish)\b',command,re.I) and re.search(r'\btask\s*#',command,re.I) and not re.search(r'\breminder\b',command,re.I) and selected in {'CRM','PMS'}:
        intent='tasks.priority' if re.search(r'\b(priority|high|urgent|critical|medium|low)\b',command,re.I) else 'tasks.status'
    clean=re.sub(r'^(?:(?:please|can you|could you|would you|i want (?:you )?to|i would like (?:you )?to)\s+)+','',command,flags=re.I)
    slots={'action_verb':clean.split(' ',1)[0].casefold()}
    for field in ('subject','body'):
        match=re.search(r'\b'+field+r'\s*[:=]?\s*"([^"\n]+)"',command,re.I)
        if match:slots[field]=match[1]
    quoted=re.search(r'["“]([^"”\n]+)["”]',command)
    if quoted:slots['title']=quoted[1]
    ident=re.search(r'\b(?:task(?:\s+(?:record|item))?|lead|invoice|request)\s*#\s*([1-9]\d*)\b',command,re.I)
    if ident:slots['record_id']=int(ident[1])
    if intent.endswith('.search'):
        searched=re.search(r'\b(?:named|matching|for|by)\s+([\w -]+?)[?.!]*$',command,re.I)
        if not searched:searched=re.search(r'\b(?:colleague|coworker|employee|lead|product|inventory|stock)\s+([\w -]+?)[?.!]*$',command,re.I)
        if not searched:searched=re.search(r'\b(?:locate|find)\s+([\w -]+?)\s+(?:leads?|stock)[?.!]*$',command,re.I)
        if searched:slots['search']=searched[1].strip()
        else:question='What exact name or search term should I look for?'
    now=instant.astimezone(ZoneInfo(timezone)) if instant else datetime.now(ZoneInfo(timezone))
    from app.ai_operator.pms_agent import resolve_date
    numbers={word:i for i,word in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen'.split())}
    date_text=re.sub(r'\bin (one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen) (days?|weeks?)\b',lambda m:f'in {numbers[m[1].lower()]} {m[2]}',unquoted,flags=re.I)
    date_text=re.sub(r'\b(?:the )?day after tomorrow\b','in 2 days',date_text,flags=re.I)
    dates=re.search(r'\b(\d{4}-\d{2}-\d{2}|today|tomorrow|next (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|in \d{1,3} (?:days?|weeks?))\b',date_text,re.I)
    if dates:
        try: slots['due_date']=resolve_date(dates[1],timezone,today=now.date())
        except HTTPException: slots['invalid_date']=True
    priority=re.search(r'\b(high|urgent|critical|medium|low)\b',unquoted,re.I)
    if priority:slots['priority']=priority[1].title()
    if re.search(r'\b(done|complete|completed|finish)\b',unquoted,re.I):slots['status']='Done'
    elif re.search(r'\bin progress\b',unquoted,re.I):slots['status']='In Progress'
    elif re.search(r'\bblocked\b',unquoted,re.I):slots['status']='Blocked'
    elif re.search(r'\bto do\b',unquoted,re.I):slots['status']='To Do'
    channel=re.search(r'\b(email|whatsapp|sms)\b',unquoted,re.I)
    if channel:slots['channel']=channel[1].lower()
    if intent=='tasks.create' and ':' in command and not quoted:
        slots['title']=command.split(':',1)[1].strip()
        slots['title']=re.sub(r'\s+(?:(?:due|for)\s+)?(?:today|tomorrow|\d{4}-\d{2}-\d{2})$','',slots['title'],flags=re.I)
    if intent=='note.create' and ':' in command:slots['body']=command.split(':',1)[1].strip()
    if intent=='reminders.create':
        entity=re.search(r'\b(task|lead|deal|project|leave|invoice)\s*#',command,re.I)
        if entity:slots['entity']=entity[1].lower()
        if slots.get('due_date'):slots['date']=slots['due_date']
        clock=re.search(r'\bat\s+(\d{1,2}):(\d{2})\b',unquoted,re.I)
        if clock and int(clock[1])<24 and int(clock[2])<60:slots['time']=f'{int(clock[1]):02}:{int(clock[2]):02}'
    if intent=='leave.create':
        if slots.get('due_date'):slots['from_date']=slots['due_date']
        values=re.findall(r'\b\d{4}-\d{2}-\d{2}\b',unquoted)
        if values:
            slots['from_date']=values[0]
            if len(values)>1:slots['to_date']=values[1]
    return Interpretation(selected,intent,round(confidence,3),slots,question,neural)


def contexts(intent, project_id=None, timezone='Asia/Kolkata'):
    name=intent.intent; module=intent.module
    if intent.question:return []
    if module=='CRM':
        tool={'leads.list':'crm.leads','leads.search':'crm.leads','leads.message':'crm.leads','contacts.list':'crm.contacts',
              'customers.list':'crm.companies','deals.list':'crm.deals','summary':'crm.tasks','risk':'crm.tasks'}.get(name)
        if name.startswith('tasks.') and name!='tasks.create':tool='crm.tasks'
    elif module=='PMS':
        tool='pms.projects' if name=='projects.list' else 'pms.tasks' if name.startswith('tasks.') and name!='tasks.create' or name in {'dependencies','summary','risk'} else None
    elif module=='Sales':
        tool={'sales.dashboard':'srm.dashboard','customers.list':'crm.companies','inventory.list':'srm.inventory','inventory.search':'srm.inventory','orders.list':'srm.sales_orders','summary':'srm.invoices','risk':'srm.invoices','jobs.today':'srm.invoices'}.get(name)
        if name.startswith('invoices.'):tool='srm.invoices'
    else:
        tool={'directory':'hrms.directory','directory.search':'hrms.directory','leave.balance':'hrms.leave_balance','leave.mine':'hrms.my_leave',
              'leave.rejected':'hrms.my_leave','leave.pending':'hrms.pending_leave','leave.team':'hrms.team_availability','policies':'hrms.policies',
              'tickets.mine':'hrms.my_tickets','leave.types':'hrms.leave_types','leave.create':'hrms.leave_types','ticket.categories':'hrms.ticket_categories','summary':'hrms.my_tickets','risk':'hrms.my_tickets'}.get(name)
    if not tool or tool=='pms.tasks' and not project_id:return []
    record_id=project_id if tool=='pms.tasks' else None
    if module=='CRM' and name in {'tasks.priority','tasks.status'} and intent.slots.get('record_id'):
        tool='crm.task';record_id=intent.slots['record_id']
    payload={}
    if intent.slots.get('search'):payload['search']=intent.slots['search']
    if tool=='crm.tasks':
        if name=='tasks.today':payload.update(task_queue='today',timezone=timezone)
        if name=='tasks.overdue':payload.update(task_queue='overdue',timezone=timezone)
        if name=='tasks.blocked':payload['status']='Blocked'
    if tool=='hrms.pending_leave':payload['status']='Pending'
    if tool=='hrms.my_leave' and name=='leave.rejected':payload['status']='Rejected'
    if tool=='hrms.team_availability':
        current=datetime.now(ZoneInfo(timezone));payload.update(year=current.year,month=current.month)
    return [{'tool':tool,'record_id':record_id,'payload':payload}]
