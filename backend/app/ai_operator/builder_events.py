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
    code=None
    if source:
        if re.search(r'\bassets?\b',source) and re.search(r'hand(?:ed)?\s*over|handover|assign',source):code='hrms.asset_handover'
        elif re.search(r'\b(?:deals?|opportunit(?:y|ies))\b',source) and re.search(r'\b(?:stages?|pipeline)\b',source):code='crm.deal_stage'
        elif re.search(r'\b(?:assignments?|assigned|reassigned|assignees?)\b',source):code='pms.assignment_changed'
        elif re.search(r'\btasks?\b',source) and re.search(r'\b(?:created|creation|added|new)\b',source):code='pms.task_created'
        elif re.search(r'\btasks?\b',source) and re.search(r'\b(?:updated|updates|changes?|changed|modified)\b',source):code='pms.task_updated'
        else:
            draft.question='Which supported native event should trigger it: task creation, task update, task assignment change, deal stage change or asset handover?'
            return True
    if code:
        values=draft.trigger.model_dump() if draft.trigger else {}
        draft.trigger=EventRule(**{**values,'event':code});draft.schedule=None
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
    question=clarification(text,draft.trigger.event)
    if question:draft.question=question
    return bool(code or matched)


def spec(rule,prompt,zone):
    if not rule:return None
    return {**rule.model_dump(exclude={'expires_days'}),'prompt':prompt,'timezone':zone,
        'expires_at':(datetime.now(timezone.utc)+timedelta(days=rule.expires_days)).isoformat()}
