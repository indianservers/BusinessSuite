"""Typed event proposals for the existing conversational agent builder."""
import re
from datetime import datetime,timedelta,timezone
from pydantic import Field
from app.ai_operator.agent_events import EventSettings


class EventRule(EventSettings):
    expires_days:int=Field(default=30,ge=1,le=365)


SIGNAL=r'\b(?:when(?:ever)?|each time|every time|as soon as)\b|\b(?:trigger|run|start)\s+on\b|^\s*on\b|\bon(?=\s+(?:new\s+tasks?|task\s+(?:creation|updates?|assignment)|assignment\s+changes?|deal\s+stage|asset\s+handover)\b)'
WORDS={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12}
NUMBER=r'(\d+|'+'|'.join(WORDS)+')'
WEBHOOK_EVENT=r'''\bevent(?:\s+(?:named|called))?\s+(?:"([^"\n]{1,120})"|'([^'\n]{1,120})'|“([^”\n]{1,120})”|([A-Za-z0-9_.:-]{1,120}))'''


def clarification(text,event):
    signal=re.search(SIGNAL,text.casefold())
    source=text.casefold()[signal.end():] if signal else ''
    if re.search(r'\bonly if\b|\bwhere\b',source):return 'This trigger watches all matching native events. Which supported event should I use without an additional record condition?'
    if event=='pms.task_updated' and re.search(r'\b(?:priority|status|deadline|due date)\b',source):return 'This native trigger watches any task update. Should I use any task update, or would you prefer a scheduled check of that field?'
    return None


def refine(draft,text):
    lower=text.casefold()
    if re.search(r'\b(?:manual only|no triggers?|remove (?:the )?(?:event )?triggers?|disable (?:the )?(?:event )?triggers?)\b',lower):
        draft.trigger=None;return False
    signal=re.search(SIGNAL,lower)
    source=lower[signal.end():] if signal else ''
    room=re.search(r'\b(?:chat )?conversation\s*#?\s*([1-9]\d*)\b',lower)
    recipient=re.search(r'\b(?:customer )?recipient\s*#?\s*([1-9]\d*)\b',lower)
    whatsapp=re.search(r'\bwhatsapp (?:contact|conversation)\s*#?\s*([1-9]\d*)\b',lower)
    hook=re.search(r'\bwebhook(?:\s+endpoint)?\s*#?\s*([1-9]\d*)\b',text,re.I)
    hook_event=re.search(WEBHOOK_EVENT,text,re.I)
    webhook_name=next((v for v in hook_event.groups() if v is not None),None) if hook_event else None
    if hook or re.search(r'\bwebhook\b',source):source=source or lower
    if room and re.fullmatch(r'\s*(?:chat )?conversation\s*#?\s*[1-9]\d*\s*[.!]?\s*',lower):source='message received'
    if recipient and re.fullmatch(r'\s*(?:customer )?recipient\s*#?\s*[1-9]\d*\s*[.!]?\s*',lower):source='customer email reply'
    if whatsapp and re.fullmatch(r'\s*whatsapp (?:contact|conversation)\s*#?\s*[1-9]\d*\s*[.!]?\s*',lower):source='whatsapp message received'
    from app.ai_operator.suite_tools import TOOLS
    modules=sorted({TOOLS[t].module for t in draft.tools if t in TOOLS})
    code=None
    if source:
        if re.search(r'\bwebhook\b',source):
            module=re.search(r'\b(CRM|PMS|HRMS|SRM|sales|FAM|finance)\s+(?:(?:signed\s+)?(?:record\s+)?)?webhook\b',text,re.I)
            name=module[1].upper() if module else modules[0] if len(modules)==1 else None
            name={'SALES':'SRM','FINANCE':'FAM'}.get(name,name)
            if not hook or not webhook_name or not name:
                draft.question='Which approved record webhook should trigger it? Reply with the module, webhook #ID and event "event.name".'
                return True
            if name not in modules:
                draft.question=f'Include {name} in the agent modules before binding its webhook.'
                return True
            code=name.lower()+'.webhook_received'
        elif re.search(r'\bwhatsapp\b',source) and re.search(r'\b(?:messages?|received|arrives?|repl(?:y|ies))\b',source):
            if not whatsapp:
                draft.question='Which WhatsApp conversation should trigger the agent? Reply with WhatsApp conversation #ID.'
                return True
            code='crm.whatsapp_message_received'
        elif re.search(r'\bemail\b',source) and re.search(r'\brepl(?:y|ies|ied)\b',source):
            if not recipient:
                draft.question='Which customer recipient ID should trigger the agent? Reply with recipient #ID.'
                return True
            code='crm.customer_email_reply'
        elif re.search(r'\bmessages?\b',source) and re.search(r'\b(?:received|arrives?|new|posted|sent)\b',source):
            if not room:
                draft.question='Which chat conversation ID should trigger the agent? Reply with conversation #ID.'
                return True
            code='pms.message_received'
        elif re.search(r'\bassets?\b',source) and re.search(r'hand(?:ed)?\s*over|handover|assign',source):code='hrms.asset_handover'
        elif re.search(r'\b(?:deals?|opportunit(?:y|ies))\b',source) and re.search(r'\b(?:stages?|pipeline)\b',source):code='crm.deal_stage'
        elif re.search(r'\b(?:assignments?|assigned|reassigned|assignees?)\b',source):code='pms.assignment_changed'
        elif re.search(r'\btasks?\b',source) and re.search(r'\b(?:created|creation|added|new)\b',source):code='pms.task_created'
        elif re.search(r'\btasks?\b',source) and re.search(r'\b(?:updated|updates|changes?|changed|modified)\b',source):code='pms.task_updated'
        else:
            draft.question='Which supported native event should trigger it: task creation, task update, task assignment change, deal stage change, asset handover, a message in conversation #ID or a verified customer email reply for recipient #ID?'
            return True
    if code:
        values=draft.trigger.model_dump() if draft.trigger else {}
        draft.trigger=EventRule(**{**values,'event':code,'chat_conversation_id':int(room[1]) if code=='pms.message_received' else None,
            'customer_recipient_id':int(recipient[1]) if code=='crm.customer_email_reply' else None,
            'whatsapp_contact_id':int(whatsapp[1]) if code=='crm.whatsapp_message_received' else None,
            'webhook_endpoint_id':int(hook[1]) if code.endswith('.webhook_received') else None,
            'webhook_event':webhook_name if code.endswith('.webhook_received') else None});draft.schedule=None
        if draft.run_prompt:
            objective=re.split(SIGNAL,draft.run_prompt,maxsplit=1,flags=re.I)[0].strip(' ,.-')
            if objective:draft.run_prompt=objective
    if not draft.trigger:return bool(code)
    values=draft.trigger.model_dump();matched=False
    settings=[('max_per_day',r'\b(?:at most|no more than|limit(?: it)? to)\s+'+NUMBER+r'(?:\s+(?:preparations?|runs?|times?))?\s+(?:per|a|each)\s+day\b'),
        ('min_interval_minutes',r'\b(?:at least|cooldown(?: of)?)\s+'+NUMBER+r'\s+minutes?(?:\s+apart)?\b'),
        ('max_event_age_minutes',r'\b(?:skip events older than|maximum event age(?: of)?)\s+'+NUMBER+r'\s+minutes?\b'),
        ('expires_days',r'\b(?:for|expires? (?:in|after))\s+'+NUMBER+r'\s+days?\b')]
    for field,pattern in settings:
        match=re.search(pattern,lower)
        if match:values[field]=int(match[1]) if match[1].isdigit() else WORDS[match[1]];matched=True
    if matched:
        try:draft.trigger=EventRule(**values)
        except ValueError:draft.question='Use 1–24 preparations per day, 1–1440 minutes for interval and event age, and 1–365 days for expiry.'
    elif re.search(r'\b(?:at most|no more than|limit(?: it)? to|at least|cooldown|skip events older than|maximum event age)\b',lower):
        draft.question='Specify the intake limit as a whole number, for example “at most 3 preparations per day” or “cooldown 10 minutes”.'
        return True
    question=clarification(re.sub(WEBHOOK_EVENT,'',text,flags=re.I) if draft.trigger.event.endswith('.webhook_received') else text,draft.trigger.event)
    if question:draft.question=question
    return bool(code or matched)


def spec(rule,prompt,zone):
    if not rule:return None
    return {**rule.model_dump(exclude={'expires_days'}),'prompt':prompt,'timezone':zone,
        'expires_at':(datetime.now(timezone.utc)+timedelta(days=rule.expires_days)).isoformat()}
