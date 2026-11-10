"""Bounded conversation composition over existing, reviewed module actions.

The trained intent model still classifies clauses. This layer extracts explicit
lists and draft edits; it never invents records, people, project scopes or work.
"""
import re
from copy import deepcopy
from fastapi import HTTPException

VERSION='conversational-actions-v1'
WEEKDAY=r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
DATE=r'(?:\d{4}-\d{2}-\d{2}|day after tomorrow|today|tomorrow|(?:next )?'+WEEKDAY+r'|in \d{1,3} (?:days?|weeks?)|end of (?:this )?month)'
VERB=r'(?:create|add|make|prepare|draft|raise|open|log|submit|set up|put together)'
OBJECT=r'(?:(?:a|an|another|new|fresh)\s+)*(?:(?:CRM|PMS|HRMS|HR|project|customer|helpdesk|support)\s+)*(?:task|follow[- ]?up(?:\s+task)?|ticket|milestone|subtask)s?'
POLITE=[r'could you help me',r'i need you to',r"i(?:'d| would) like you to",r'please help me to',r'help me',r"let(?:'s| us) go ahead and",r"let(?:'s| us)",r'for the next step,?',r'for my work today,? please',r'as the next action,?',r'would you mind helping me',r'i want you to',r'can you please',r'could you',r'can you',r'would you',r'please']

def normalized_date(value):
    if value.lower()=='day after tomorrow':return 'in 2 days'
    return 'next '+value.lower() if re.fullmatch(WEEKDAY,value,re.I) else value

def clean(text):
    text=text.strip().strip('.!;,')
    for _ in range(3):
        old=text
        for prefix in POLITE:text=re.sub('^'+prefix+r'\s+','',text,flags=re.I)
        if text==old:break
    return text

def structural(text):return re.sub(r'"[^"\n]*"|“[^”\n]*”','"value"',text)

def unsafe(text):
    return bool(re.search(r'\b(?:ignore|bypass|skip|disable|override)\s+(?:(?:all|the)\s+)?(?:permissions?|approvals?|consent|security|instructions)|without\s+(?:consent|approval)|\b(?:delete|purge|drop|execute sql)\b',structural(text),re.I))

def titles(text):
    if text.count('"')%2 or text.count('“')!=text.count('”'):raise HTTPException(422,'Close the quotation marks around each task title')
    outside=r'(?=(?:[^"“”]*["“][^"“”]*["”])*[^"“”]*$)'
    lines=[v for v in text.strip().splitlines() if v.strip()]
    if len(lines)>1 and all(re.match(r'^\s*(?:[-*•]|\d+[.)])\s+\S',v) for v in lines):
        return [re.sub(r'^\s*(?:[-*•]|\d+[.)])\s+','',v).strip().strip('"“”') for v in lines]
    text=re.sub(r'(?m)^\s*(?:[-*•]|\d+[.)])\s+','',text.strip())
    parts=re.split(r'(?:\s*[,;]\s*|\s+and\s+|\n+)'+outside,text,flags=re.I)
    return [v.strip(' .').strip('"“”') for v in parts if v.strip(' .')]

def canonical(part,module=None):
    part=clean(part);explicit=re.match(r'^(CRM|PMS|HRMS|HR)\s*:\s*',part,re.I)
    selected=explicit[1].upper() if explicit else module
    if explicit:part=part[explicit.end():]
    if selected=='HR':selected='HRMS'
    match=re.match(r'^'+VERB+r'\s+('+OBJECT+r')(?:\s+(?:called|named|titled|for)|\s*:)?\s*(.*)$',part,re.I)
    if not match:return None
    # Route from the explicit object, never from words in a supplied title.
    unquoted=match[1]
    if not explicit:
        if re.search(r'\b(?:HR|HRMS|helpdesk|support ticket)\b',unquoted,re.I):selected='HRMS'
        elif re.search(r'\b(?:PMS|project task|milestone|subtask)\b',unquoted,re.I):selected='PMS'
        elif re.search(r'\b(?:CRM|customer follow|lead follow)\b',unquoted,re.I):selected='CRM'
    obj=match[1].casefold();tail=match[2].strip()
    selected=selected or ('HRMS' if 'ticket' in obj else 'CRM')
    if 'ticket' in obj:selected='HRMS';kind='HR ticket'
    elif 'milestone' in obj:selected='PMS';kind='milestone'
    else:kind='task'
    if selected not in {'CRM','PMS','HRMS'} or selected=='HRMS' and kind!='HR ticket':return None
    extras=[];project_id=None
    for _ in range(3):
        project=re.search(r'\s+(?:in|for) project\s*#?\s*([1-9]\d*)\s*$',tail,re.I)
        if project:project_id=int(project[1]);tail=tail[:project.start()].strip();continue
        due=re.search(r'\s+(?:due|by|for)\s+('+DATE+r')\s*$',tail,re.I)
        if due:
            if kind=='HR ticket':return None
            extras.append('due '+normalized_date(due[1]));tail=tail[:due.start()].strip();continue
        priority=re.search(r'\s+(?:with\s+)?(high|medium|low|urgent|critical)\s+priority\s*$',tail,re.I)
        if priority:extras.append(priority[1]+' priority');tail=tail[:priority.start()].strip();continue
        break
    if re.search(r'\b(?:and|then|also)\s+'+VERB+r'\b',structural(tail),re.I):return None
    title=tail.strip('"“”')
    if any(char in title for char in ('"','“','”')):return None
    if len(title)>220:raise HTTPException(422,'Use titles of at most 220 characters')
    return {'text':f'{selected}: create {kind}'+(f' "{title}"' if title else '')+(' '+' '.join(extras) if extras else ''),
        'module':selected,'project_id':project_id,'original':part}

def compose(text,module=None):
    """Return normalized explicit clauses, or abstain without making up a plan."""
    original=text;text=clean(text)
    if unsafe(text):return {'question':'I cannot bypass permissions, approvals or consent. Describe a permitted workflow.'}
    if re.search(r"\b(?:do not|don't|don’t|not yet|unless|except|only if)\b",structural(text),re.I):
        return {'question':'Please confirm the actions you want prepared. I will not infer actions from a negative or conditional request.'}
    if re.match('^'+VERB+r'\b',text,re.I) and re.search(r'\bassign(?:ed)?\s+to\b',structural(text),re.I):
        return {'question':'Assignee names need an authorized people lookup. Choose a connected provider for that request, or prepare an unassigned draft first.'}
    if re.match('^'+VERB+r'\b',text,re.I) and re.search(r'\b(?:due|by|for)\s+'+DATE+r'\s*$',structural(text),re.I) and (
        re.search(r'\b(?:HR ticket|HRMS ticket|helpdesk ticket|support ticket)\b',structural(text),re.I) or module=='HRMS' and re.search(r'\btickets?\b',structural(text),re.I)):
        return {'question':'HR tickets do not support a due date in this action. Prepare the ticket without a deadline, or create a task instead.'}
    project=re.match(r'^'+VERB+r'\s+(?:a\s+)?(?:new\s+)?project\s+(?:called|named|titled)\s+("[^"\n]+"|“[^”\n]+”|[^"“”]+?)\s+with\s+(?:the\s+)?tasks\s*:?\s*(.+)$',text,re.I)
    if project:
        name=project[1].strip('"“” ');values=titles(project[2])
        if not name or len(name)>180 or not values:return {'question':'Give the new project a name and list its task titles.'}
        clauses=[canonical('create project task called "'+title+'"','PMS') for title in values]
        if any(c is None for c in clauses):return {'question':'Give each project task a clear title.'}
        return {'new_project':{'name':name},'clauses':clauses}
    # Subtasks use the canonical parent_task_id reference, not a second project.
    parent=re.match(r'^'+VERB+r'\s+(?:a\s+)?(?:project\s+)?task\s+(?:called|named|titled)\s+("[^"\n]+"|“[^”\n]+”|[^"“”]+?)\s+with\s+(?:the\s+)?subtasks?\s*:?\s*(.+)$',text,re.I)
    if parent:
        head=canonical('create project task called '+parent[1],'PMS');children=titles(parent[2])
        if not head or not children:return {'question':'What should the parent task and each subtask be called?'}
        clauses=[head]
        for title in children:
            child=canonical('create project task called "'+title+'"','PMS')
            if not child:return {'question':'Give one clear title for each subtask.'}
            clauses.append({**child,'parent_step':1})
        return {'clauses':clauses}
    counted=re.match(r'^('+VERB+r')\s+([1-9]\d*)\s+(?=(?:(?:CRM|PMS|project|customer|HR|HRMS)\s+)?(?:tasks|tickets)\b)',text,re.I)
    declared=int(counted[2]) if counted else None
    bulk_text=counted[1]+' '+text[counted.end():] if counted else text
    bulk=re.match(r'^'+VERB+r'\s+(?:(CRM|PMS|project|customer|HR|HRMS)\s+)?(tasks|tickets)\s*(?:(?:for|called|named)\s+|:\s*)?(.+)$',bulk_text,re.I|re.S)
    if bulk:
        selected='HRMS' if bulk[2].lower()=='tickets' else 'PMS' if (bulk[1] or '').lower() in {'pms','project'} else 'CRM' if bulk[1] else module
        selected=selected or 'CRM';tail=bulk[3];suffix=''
        for _ in range(2):
            due=re.search(r'\s+(?:due|by|for)\s+('+DATE+r')\s*$',tail,re.I)
            priority=re.search(r'\s+(?:with\s+)?(high|medium|low|urgent|critical)\s+priority\s*$',tail,re.I)
            if due:
                if selected=='HRMS':return {'question':'HR tickets do not support a due date in this action. Prepare the ticket without a deadline, or create a task instead.'}
                suffix+=' due '+normalized_date(due[1]);tail=tail[:due.start()]
            elif priority:suffix+=' '+priority[1]+' priority';tail=tail[:priority.start()]
            else:break
        values=titles(tail)
        if declared is not None and declared!=len(values):return {'question':f'You requested {declared} items but supplied {len(values)} titles. Please provide the complete list or correct the count.'}
        if len(values)<2 and declared is None:return None
        obj='HR ticket' if selected=='HRMS' else 'task'
        clauses=[canonical(f'create {obj} called "{value}"'+suffix,selected) for value in values]
        if any(c is None for c in clauses):return {'question':'Choose CRM or PMS for these tasks, and give their titles.'}
        return {'clauses':clauses}
    # Only split outside quotes and before another explicit action; title text
    # such as "Research and development" is not an extra business operation.
    outside=r'(?=(?:[^"“”]*["“][^"“”]*["”])*[^"“”]*$)'
    separator=r'(?:\s+(?:and then|then|also)\s+|;\s*|\s+and\s+(?=(?:(?:CRM|PMS|HRMS|HR)\s*:\s*)?'+VERB+r'\s+'+OBJECT+r'))'+outside
    parts=re.split(separator,text,flags=re.I)
    # Preserve the old exact single-action path and its slot-filling metadata.
    extended_date=bool(re.search(r'\b(?:due|by|for)\s+(?:'+WEEKDAY+r'|day after tomorrow|end of (?:this )?month)\s*$',structural(text),re.I))
    extended_phrase=bool(re.match(r'^(?:log|submit)\b',text,re.I) or re.match(r"^(?:for the next step|let us|let's|help me|please help me)\b",original,re.I))
    if len(parts)==1 and (re.search(r'["“]',text) and not extended_date and not extended_phrase or re.fullmatch(r'(?:(?:CRM|PMS|HRMS|HR)\s*:\s*)?'+VERB+r'\s+'+OBJECT,text,re.I)):
        return None
    clauses=[canonical(part,module) for part in parts]
    if any(c is None for c in clauses):
        joined=bool(re.search(r'\b(?:and|then|also)\s+'+VERB+r'\b',structural(text),re.I))
        return {'question':'I could not identify every action. Give each task, milestone or HR ticket a clear title. Use a connected provider for broader project/document generation.'} if len(parts)>1 or joined else None
    if not clauses:return None
    if len(clauses)>8:raise HTTPException(422,'Prepare at most eight actions in one review')
    return {'clauses':clauses}

def amend(state,text,timezone,module=None):
    """Edit only an unexecuted draft; approval stays a separate operation."""
    from app.ai_operator.pms_agent import resolve_date
    state=deepcopy(state);text=clean(text);intents=state['intents']
    if unsafe(text):return state,'I cannot bypass review, consent or permissions.'
    if re.fullmatch(r'(?:cancel|cancel it|cancel (?:this|the) (?:workflow|plan|draft)|forget (?:this|the) (?:workflow|plan|draft)|never mind|stop)',text,re.I):return {'cancelled':True},None
    possessive=re.fullmatch(r'(set|change|update)\s+(.+?)[\x27’]s\s+(priority|title|due date|deadline)\s+to\s+(.+)',text,re.I)
    if possessive:text=possessive[1]+' the '+possessive[3]+' of '+possessive[2]+' to '+possessive[4]
    field_change=re.fullmatch(r'(?:set|change|update)\s+(?:the\s+)?(priority|due date|deadline|title)\s+of\s+(.+?)\s+to\s+(.+)',text,re.I)
    if field_change:text=('rename ' if field_change[1].lower()=='title' else 'set ')+field_change[2]+' to '+field_change[3]+(' priority' if field_change[1].lower()=='priority' else '')
    text=re.sub(r'^(?:change|set|update) its priority to (.+)$',r'make it \1 priority',text,flags=re.I)
    text=re.sub(r'^(?:change|set|update) its title to (.+)$',r'rename it to \1',text,flags=re.I)
    text=re.sub(r'^clear (?:the )?due date of (.+)$',r'clear \1 due date',text,flags=re.I)
    text=re.sub(r'^remove (?:the )?due date from (.+)$',r'clear \1 due date',text,flags=re.I)
    text=re.sub(r'^clear its due date$',r'clear it due date',text,flags=re.I)
    earlier=re.fullmatch(r'(?:bring\s+(.+?)\s+forward|move\s+(.+?)\s+earlier)\s+by\s+(.+)',text,re.I)
    if earlier:text='push '+(earlier[1] or earlier[2])+' ahead by '+earlier[3]
    if re.match(r'^push\b',text,re.I):
        numbers={'one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7'}
        text=re.sub(r'\b(back|ahead) by (one|two|three|four|five|six|seven)\b',lambda m:m[1]+' by '+numbers[m[2].lower()],text,flags=re.I)
    marked=re.fullmatch(r'mark\s+(.+?)\s+(?:as\s+)?(high|medium|low|urgent|critical)(?:\s+priority)?',text,re.I)
    if marked:text='set '+marked[1]+' to '+marked[2]+' priority'
    # Resolve names only inside this server-owned, unexecuted draft. Quoted
    # names are never interpreted as live record IDs or a fuzzy search.
    named=re.match(r'^(rename|call|remove|move|schedule|set|make|change|clear|push)\s+(?:"([^"\n]+)"|“([^”\n]+)”)(?=\s|$)',text,re.I)
    if named:
        title=(named[2] or named[3]).strip().casefold()
        offset=int(bool(state.get('new_project')))
        choices=[(i+1+offset,str(item['slots'].get('title') or '').strip().casefold()) for i,item in enumerate(intents)]
        if offset:choices.insert(0,(1,str(state['new_project'].get('name') or '').strip().casefold()))
        matches=[index for index,value in choices if value==title]
        if len(matches)!=1:return state,'I cannot identify one draft item with that exact title. Use its item number; duplicate and missing names are ambiguous.'
        text=named[1]+' item '+str(matches[0])+text[named.end():]
    # Normalize only the leading reference; a new quoted title containing
    # "item 2" is user content and must remain byte-for-byte unchanged.
    numbered=re.match(r'^(rename|call|remove|move|schedule|set|make|change|clear|push)\s+(?:the\s+)?(?:item|task|ticket|action)\s+#?([1-9]\d*)(?=\s|$)',text,re.I)
    names=('first','second','third','fourth','fifth','sixth','seventh','eighth')
    if numbered:
        index=int(numbered[2])
        if index>len(intents)+int(bool(state.get('new_project'))):return state,'That item number is not in this draft.'
        text=numbered[1]+' the '+names[index-1]+' one'+text[numbered.end():]
    target=r'(?:it|both|this (?:task|ticket|item)|them(?: all)?|all(?: the)? (?:tasks|tickets|items|actions)|everything)'
    priority=re.fullmatch(r'(?:make|set|change)\s+('+target+r')(?:\s+to)?\s+(high|medium|low|urgent|critical)(?:\s+priority)?',text,re.I)
    due=re.fullmatch(r'(?:move|schedule|set)\s+('+target+r')\s+(?:to|for)\s+('+DATE+')',text,re.I)
    ordinals={'first':0,'second':1,'third':2,'fourth':3,'fifth':4,'sixth':5,'seventh':6,'eighth':7,'last':len(intents)-1}
    rename=re.fullmatch(r'(?:rename|call)\s+(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|last|it)(?:\s+(?:one|task|ticket|item|action))?\s+(?:(?:to|as)\s+)?(.+)',text,re.I)
    remove=re.fullmatch(r'(?:remove|drop)\s+(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|last)(?:\s+(?:one|task|ticket|item|action))?',text,re.I)
    ordinal_priority=re.fullmatch(r'(?:make|set|change)\s+(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|last)(?:\s+(?:one|task|ticket|item|action))?(?:\s+to)?\s+(high|medium|low|urgent|critical)(?:\s+priority)?',text,re.I)
    ordinal_due=re.fullmatch(r'(?:move|schedule|set)\s+(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|last)(?:\s+(?:one|task|ticket|item|action))?\s+(?:to|for)\s+('+DATE+')',text,re.I)
    reference=r'(?:the\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|last|it)(?:\s+(?:one|task|ticket|item|action))?'
    clear_due=re.fullmatch(r'clear\s+'+reference+r'\s+due date',text,re.I)
    shift_due=re.fullmatch(r'push\s+'+reference+r'\s+(back|ahead) by\s+([1-9]\d{0,2})\s+(days?|weeks?)',text,re.I)
    if (priority or due) and (priority or due)[1].lower() in {'it','this task','this ticket','this item'} and len(intents)+int(bool(state.get('new_project')))!=1:
        return state,'Which item should I change? Specify its number, or say all tasks.'
    if (priority or due) and (priority or due)[1].lower()=='both' and len(intents)+int(bool(state.get('new_project')))!=2:
        return state,'Which two items do you mean? This draft does not contain exactly two items.'
    if ordinal_priority or ordinal_due or clear_due or shift_due:
        selected=ordinal_priority or ordinal_due or clear_due or shift_due
        if selected[1].lower()=='it' and len(intents)+int(bool(state.get('new_project')))!=1:return state,'Which item should I change? Specify its number.'
        index=0 if selected[1].lower()=='it' else ordinals[selected[1].lower()]
        field='priority' if ordinal_priority else 'due_date'
        slots=None
        if state.get('new_project'):
            if selected[1].lower()=='last':index=len(intents)
            if index==0:slots=state['new_project']
            index-=1
        if slots is None:
            if index>=len(intents):return state,'That item number is not in this draft.'
            if not ordinal_priority and intents[index]['intent'] not in {'tasks.create','milestone.create'}:return state,'This item does not support a due date. Choose a task or milestone instead.'
            slots=intents[index]['slots']
        if clear_due:slots.pop('due_date',None)
        elif shift_due:
            if not slots.get('due_date'):return state,'This item has no deadline to shift. Set an explicit due date first.'
            from datetime import date,timedelta
            try:
                value=(date.fromisoformat(slots['due_date'])+timedelta(days=int(shift_due[3])*(7 if shift_due[4].lower().startswith('week') else 1)*(-1 if shift_due[2].lower()=='ahead' else 1))).isoformat()
            except (ValueError,OverflowError):return state,'The shifted deadline is outside the supported date range. Choose an explicit valid date.'
            slots['due_date']=value
        else:slots[field]=selected[2].title() if ordinal_priority else resolve_date(normalized_date(selected[2]),timezone)
    elif priority:
        for intent in intents:intent['slots']['priority']=priority[2].title()
        if state.get('new_project'):state['new_project']['priority']=priority[2].title()
    elif due:
        if any(i['intent'] not in {'tasks.create','milestone.create'} for i in intents):return state,'Not every item supports a due date. Specify the task or milestone to change.'
        value=resolve_date(normalized_date(due[2]),timezone)
        for intent in intents:intent['slots']['due_date']=value
        if state.get('new_project'):state['new_project']['due_date']=value
    elif rename or remove:
        match=rename or remove
        if match[1].lower()=='it' and len(intents)+int(bool(state.get('new_project')))!=1:return state,'Which item should I rename? Specify its number.'
        index=0 if match[1].lower()=='it' else ordinals[match[1].lower()]
        if state.get('new_project'):
            if match[1].lower()=='last':index=len(intents)
            if index==0:
                if remove:return state,'The new project is required by these tasks. Cancel the draft to remove the whole workflow.'
                title=rename[2].strip('"“” ')
                if not title or len(title)>180:return state,'Use a project name of at most 180 characters.'
                state['new_project']['name']=title
                return state,None
            index-=1
        if index>=len(intents):return state,'That item number is not in this draft.'
        if rename:
            title=rename[2].strip('"“” ')
            if not title or len(title)>220:return state,'Use a nonempty title of at most 220 characters.'
            intents[index]['slots']['title']=title
        else:
            if any(i['slots'].get('_parent_step')==index+1 for i in intents):return state,'That task has subtasks in this draft. Remove its subtasks first.'
            intents.pop(index)
            for intent in intents:
                if intent['slots'].get('_parent_step',0)>index+1:intent['slots']['_parent_step']-=1
            if not intents:return {'cancelled':True},None
    elif re.match(r'^(?:also\s+)?'+VERB+r'\b',text,re.I):
        from app.ai_operator.local_nlp import parse
        proposal=compose(re.sub(r'^also\s+','',text,flags=re.I),module)
        if not proposal:
            single=canonical(re.sub(r'^also\s+','',text,flags=re.I),module)
            if single:proposal={'clauses':[single]}
        if not proposal or not proposal.get('clauses'):return state,'Describe the additional task or HR ticket with a title.'
        if proposal.get('new_project') or any(c.get('parent_step') for c in proposal['clauses']):return state,'Start a new conversation for a new project or parent/subtask structure; I will not flatten its dependencies into this draft.'
        if len(intents)+len(proposal['clauses'])+int(bool(state.get('new_project')))>8:raise HTTPException(422,'Prepare at most eight actions in one review')
        if any(c.get('project_id') and c['project_id']!=state.get('project_id') for c in proposal['clauses']):return state,'The added task belongs to a different project. Start a separate conversation for that project.'
        for clause in proposal['clauses']:
            intent=parse(clause['text'],clause['module'],timezone=timezone)
            intents.append({'module':intent.module,'intent':intent.intent,'slots':dict(intent.slots),'question':intent.question})
    else:return state,'Specify a change such as “make them all high priority”, “rename the second one to Review”, or “add another task called QA”.'
    return state,None

async def project_choice(data,parent,request):
    """Resolve exact project names only through the caller's canonical API."""
    if not parent or parent.status!='needs_clarification':return None
    state=(parent.result or {}).get('workflow') or {};pending=state.get('pending')
    if type(pending) is not int or pending>=len(state.get('intents',[])):return None
    if state['intents'][pending]['slots'].get('_awaiting')!='project_id':return None
    name=re.sub(r'^(?:(?:use|choose|select)\s+)?(?:the\s+)?project\s+','',data.text.strip(),flags=re.I).strip('"“” .')
    if not name or len(name)>180 or '#' in name or name.isdecimal() or unsafe(name) or re.match(r'^(?:show|list|create|cancel|what|why|help|explain)\b',name,re.I):return None
    from app.ai_operator.suite import api_call
    from app.ai_operator.evidence import records
    value=await api_call(request.app,request.headers.get('authorization',''),'GET','/project-management/projects')
    matches=[row for row in records(value) if row.get('workspace_id')==data.workspace_id and str(row.get('name','')).casefold()==name.casefold()]
    return matches[0]['id'] if len(matches)==1 else None
