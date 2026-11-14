"""Personal recorded-time summaries over the native authorized time-log query."""
import re
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends,Response,HTTPException,Query
from pydantic import Field,model_validator
from sqlalchemy import func,case
from app.core.deps import get_db,get_current_user
from app.ai_operator.suite_tools import Strict


class Window(Strict):
    start:date
    end:date
    after_id:int=Field(default=0,ge=0,le=9223372036854775807,strict=True)

    @model_validator(mode='after')
    def bounded(self):
        if not 0<=(self.end-self.start).days<=30:raise ValueError('Choose an ordered range of at most 31 days')
        return self


router=APIRouter(prefix='/suite/pms/time-summary',tags=['Personal recorded time'])


def snapshot(db,user,pid,window):
    from app.apps.project_management.api.router import time_log_query
    from app.ai_operator.time_actions import project
    from app.apps.project_management.models import PMSTimeLog
    anchor=project(db,user,pid)
    base=time_log_query(db,user,pid,user.id).filter(PMSTimeLog.log_date>=window.start,PMSTimeLog.log_date<=window.end)
    count,minutes,billable=base.with_entities(func.count(PMSTimeLog.id),func.coalesce(func.sum(PMSTimeLog.duration_minutes),0),
        func.coalesce(func.sum(case((PMSTimeLog.is_billable.is_(True),PMSTimeLog.duration_minutes),else_=0)),0)).one()
    rows=base.filter(PMSTimeLog.id>window.after_id).order_by(PMSTimeLog.id).limit(26).all();more=len(rows)>25
    return {'id':pid,'project_id':pid,'name':f'Personal recorded time: {anchor.name}'[:180],
        'start':str(window.start),'end':str(window.end),'scope':'current_user_selected_project',
        'summary_scope':'all_matching_entries','entry_count':count,'recorded_minutes':minutes,'billable_minutes':billable,
        'nonbillable_minutes':minutes-billable,'rows_scope':'returned_page','page_size':25,
        'rows':[{'id':row.id,'log_date':str(row.log_date),'duration_minutes':row.duration_minutes,
            'is_billable':row.is_billable,'approval_status':row.approval_status} for row in rows[:25]],
        'has_more':more,'next_after_id':rows[24].id if more else None,
        'limitations':['Recorded time only; excludes running timers not yet stopped, other projects and other users.',
            'Dates use each native entry log_date; elapsed intervals are not split across midnight.',
            'Billable is an entry flag, not invoiced revenue. Recorded entries may still be Pending or Rejected.',
            'Totals cover the full date window, independent of the returned detail page. Concurrent edits can change a later read.']}


@router.get('/{project_id}')
def read(project_id:int,start:date,end:date,response:Response,after_id:int=Query(0,ge=0,le=9223372036854775807),db=Depends(get_db),user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,None,'PMS');response.headers['Cache-Control']='private, no-store'
    try:window=Window(start=start,end=end,after_id=after_id)
    except ValueError:raise HTTPException(422,'Choose an ordered range of at most 31 days') from None
    return snapshot(db,user,project_id,window)


def prepare(data,parent):
    from app.ai_operator.suite import Plan,Step
    text=re.sub(r'(?i)^\s*PMS\s*:\s*','',data.text).strip()
    if data.module not in (None,'PMS') and not re.match(r'(?i)^\s*PMS\s*:',data.text):return None,None
    match=re.fullmatch(r'(?is)(?:show|review|check)\s+(?:my\s+)?(?:recorded time|time summary|time logs)(?:\s+(today|yesterday|this week|last week))?(?:\s*:\s*(.*))?[?!. ]*',text)
    question=re.fullmatch(r'(?i)how much time did I log(?:\s+(today|yesterday|this week|last week))?[?!. ]*',text)
    prior=(parent.result or {}).get('time_summary_request') if parent else None
    follow=bool(prior and (re.fullmatch(r'(?i)(?:and\s+)?(?:today|yesterday|this week|last week)[?!. ]*',text) or re.match(r'(?i)^(?:project|start|end|after_id)=',text)))
    if not match and not question and not follow:return None,None
    if parent and parent.status=='awaiting_approval':raise HTTPException(409,'Finish or cancel the pending action before reading a time summary')
    data.module='PMS'
    try:today=datetime.now(ZoneInfo(data.timezone)).date()
    except (ValueError,KeyError):raise HTTPException(422,'Choose a valid timezone') from None
    draft=dict(prior) if follow else {'project_id':data.project_id,'start':str(today),'end':str(today)}
    period=match[1] if match else question[1] if question else text if '=' not in text else None
    if period:
        period=period.lower().strip(' ?!.');start=end=today
        if 'week' in period:
            start=today-timedelta(days=today.weekday(),weeks=1 if 'last' in period else 0);end=start+timedelta(days=6)
        elif period=='yesterday':start=end=today-timedelta(days=1)
        draft.update(start=str(start),end=str(end));draft.pop('after_id',None)
    def ask(message):return Plan(summary='Clarify your personal recorded-time summary.',question=message,steps=[]),draft
    values=(match[2] if match else text if follow and '=' in text else '') or ''
    if re.search(r'(?i)(?:^|;)\s*(?:start|end)=',values) and not re.search(r'(?i)(?:^|;)\s*after_id=',values):draft.pop('after_id',None)
    for part in values.split(';'):
        if not part.strip():continue
        key,sep,value=part.strip().partition('=');key=key.lower();value=value.strip()
        if not sep or key not in {'project','start','end','after_id'}:return ask('Use project=ID; start=YYYY-MM-DD; end=YYYY-MM-DD; after_id=ID.')
        if key in {'project','after_id'}:
            if not re.fullmatch(r'[0-9]{1,18}',value):return ask('Use numeric project and cursor IDs.')
            draft['project_id' if key=='project' else key]=int(value)
        else:draft[key]=value
    if not draft.get('project_id'):return ask('Which project should your recorded-time summary cover? Reply project=123.')
    try:window=Window.model_validate({key:value for key,value in draft.items() if key!='project_id'})
    except ValueError:return ask('Choose valid start/end dates covering at most 31 days and a nonnegative cursor.')
    data.project_id=draft['project_id'];data.context=[*data.context,Step(tool='pms.time_summary',record_id=data.project_id,payload=window.model_dump(mode='json'))]
    if data.provider=='auto':data.provider='local'
    return (Plan(summary='Read your authorized recorded-time summary.',steps=[]) if data.provider=='local' else None),draft


def read_followup(parent,packet,data):
    if not packet or not (parent.result or {}).get('time_summary_request'):return False
    if parent.status not in {'needs_clarification','answered'} or parent.receipts or parent.approval_id or (parent.plan or {}).get('steps'):return False
    prior=(parent.result or {}).get('request',{})
    if any(prior.get(key) for key in ('workflow_id','commitment_id','candidate_id')):return False
    if prior.get('project_id') not in (None,packet.get('project_id')):return False
    if prior.get('project_id') is None and parent.status!='needs_clarification':return False
    return bool(data.context) and all(step.tool=='pms.time_summary' and step.record_id==packet.get('project_id') for step in data.context)


def local_answer(context,sources):
    lines=[]
    for packet in context:
        if packet['tool']!='pms.time_summary':continue
        value=packet['records']
        if not isinstance(value,dict) or value.get('truncated'):continue
        lines.append(f"{value['name']}, {value['start']} to {value['end']}: {value['recorded_minutes']} recorded minutes ({value['recorded_minutes']/60:g} hours), across {value['entry_count']} entries. Billable: {value['billable_minutes']} minutes; nonbillable: {value['nonbillable_minutes']} minutes.")
        if value.get('has_more'):lines.append('Totals cover all matching entries; only one detail page is returned. Use after_id for more detail.')
    if not lines:return {'summary':'The recorded-time source could not fit the disclosure budget.','question':'Narrow the date range or open native time tracking.','steps':[],'source_ids':[]}
    lines.append('Your selected project only. Unstopped timers are excluded; billable flags do not prove invoicing or approval. No entries changed.')
    return {'summary':'\n'.join(lines)[:2000],'steps':[],'source_ids':[source['id'] for source in sources if source['tool']=='pms.time_summary']}
