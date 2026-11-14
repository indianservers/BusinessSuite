"""Bounded, cited PMS workload intelligence over canonical workload services."""
import re
from typing import Literal
from datetime import date,timedelta,datetime
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from pydantic import Field,model_validator
from app.core.deps import get_db,get_current_user
from app.ai_operator.suite_tools import Strict


class Read(Strict):
    start:date
    scope:Literal["project","workspace"]="project"
    weeks:int=Field(default=1,ge=1,le=4,strict=True)
    after_user_id:int=Field(default=0,ge=0,le=9223372036854775807,strict=True)
    assignee_user_id:int|None=Field(default=None,gt=0,le=9223372036854775807,strict=True)

    @model_validator(mode='after')
    def valid(self):
        if self.start.weekday()!=0:raise ValueError('Choose the Monday of the workload week')
        if self.assignee_user_id is not None and self.after_user_id:raise ValueError('Choose a person or a page cursor')
        try:self.start+timedelta(weeks=self.weeks,days=-1)
        except OverflowError:raise ValueError('Choose a supported calendar range') from None
        return self


def no_store(response:Response):
    response.headers['Cache-Control']='private, no-store'


router=APIRouter(prefix='/suite/pms',tags=['Authorized workload intelligence'],dependencies=[Depends(no_store)])


def snapshot(db,user,pid,read):
    from app.apps.project_management.api.router import get_workload_heatmap
    from app.apps.project_management.access import get_project_for_action
    project=get_project_for_action(db,pid,user,'browse')
    end=read.start+timedelta(weeks=read.weeks-1)
    workspace_scope=read.scope=='workspace'
    if workspace_scope and not project.workspace_id:raise HTTPException(422,'Choose a project in the selected workspace for cross-project workload')
    native=get_workload_heatmap(projectId=None if workspace_scope else pid,workspace_id=project.workspace_id if workspace_scope else None,teamId=None,sprintId=None,from_date=read.start,to=end,basis='hours',db=db,current_user=user)
    rows=sorted(native['rows'],key=lambda row:row['user_id'])
    if read.assignee_user_id is not None:rows=[row for row in rows if row['user_id']==read.assignee_user_id]
    rows=[row for row in rows if row['user_id']>read.after_user_id]
    has_more=len(rows)>10;rows=rows[:10];people=[]
    for row in rows:
        weeks=[]
        for cell in row['cells']:
            planned=cell['planned_hours'];capacity=cell['capacity_hours']
            weeks.append({'week_start':cell['week_start'],'planned_hours':planned,'capacity_hours':capacity,
                ('scope_headroom_hours' if workspace_scope else 'project_headroom_hours'):round(capacity-planned,2),'utilization_percent':cell['utilization_percent'],
                'status':cell['status'],'task_count':cell['task_count'],
                'unestimated_task_count':sum(task['planned_hours']==0 for task in cell['tasks'])})
        totals=row['totals'];name=row['user_name'] or ''
        people.append({'user_id':row['user_id'],'name':name[:120] if '@' not in name else f'User {row["user_id"]}',
            'weeks':weeks,'planned_hours':totals['planned_hours'],'capacity_hours':totals['capacity_hours'],
            'task_week_count':totals['task_count'],('scope_headroom_hours' if workspace_scope else 'project_headroom_hours'):round(totals['capacity_hours']-totals['planned_hours'],2)})
    from app.ai_operator.workload_guard import issue
    guard=issue(pid,read.start,read.weeks,read.scope,native)
    return {'workload_guard':guard,'id':pid,'project_id':pid,'workspace_id':project.workspace_id if workspace_scope else None,'project_count':len(native['projects']),'name':(f'Workspace workload: {project.workspace_id}' if workspace_scope else f'Workload: {project.name}')[:180],
        'start':read.start.isoformat(),'end':(end+timedelta(days=6)).isoformat(),'scope':'authorized_workspace_projects' if workspace_scope else 'selected_project_only',
        'rows':people,'has_more':has_more,'next_after_user_id':rows[-1]['user_id'] if has_more else None,
        'page_size':10,'summary_scope':'returned_page',
        'over_capacity_person_weeks':sum(week['status']=='over' for person in people for week in person['weeks']),
        'basis':'Native estimated planned hours compared with working hours, dated capacity, applicable holidays and approved leave.',
        'limitations':[('Inaccessible projects, other workspaces and unassigned work are excluded; headroom does not establish that a person is free.' if workspace_scope else 'Other projects and unassigned work are excluded; headroom does not establish that a person is free.'),
            'Task windows must overlap the requested weeks; overdue or out-of-window work may add further load.',
            'Native estimates split work evenly across assignees and weeks; story points can supply a six-hour fallback.',
            'Zero-estimate tasks remain unknown effort. This is a planning snapshot, not recorded time or a capacity reservation.']}


@router.get('/workload/{project_id}')
def read_workload(project_id:int,start:date,weeks:int=Query(1,ge=1,le=4),
                  after_user_id:int=Query(0,ge=0,le=9223372036854775807),assignee_user_id:int|None=Query(None,gt=0),
                  scope:Literal['project','workspace']='project',db=Depends(get_db),user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,None,'PMS')
    try:read=Read(start=start,scope=scope,weeks=weeks,after_user_id=after_user_id,assignee_user_id=assignee_user_id)
    except ValueError:raise HTTPException(422,'Choose a Monday, one to four weeks, and a person or page cursor') from None
    return snapshot(db,user,project_id,read)


def prepare(data,parent):
    from app.ai_operator.suite import Plan,Step
    text=re.sub(r'(?i)^\s*PMS\s*:\s*','',data.text).strip()
    match=re.fullmatch(r'(?is)(?:show|check|review|compare)\s+(?:the\s+)?(?:team\s+|project\s+|workspace\s+|cross-project\s+)?(?:workload|capacity)(?:\s+(this week|next week))?(?:\s*:\s*(.*))?',text)
    question=re.fullmatch(r'(?i)who\s+is\s+(?:overloaded|over capacity)(?:\s+across\s+(?:all\s+)?projects)?(?:\s+(this week|next week))?[?!. ]*',text)
    workspace_requested=bool(re.search(r'(?i)\b(?:workspace|cross-project)\s+(?:workload|capacity)|\bacross\s+(?:all\s+)?projects\b',text))
    prior=(parent.result or {}).get('workload_request') if parent else None
    follow=bool(prior and (re.fullmatch(r'(?i)(?:and\s+)?(?:this week|next week)[?!. ]*',text) or re.match(r'(?i)^(?:project|start|weeks|after_user_id|user)=',text)))
    if not match and not question and not follow:return None,None
    if data.module not in (None,'PMS') and not re.match(r'(?i)^\s*PMS\s*:',data.text):return None,None
    if parent and parent.status=='awaiting_approval' and (parent.plan or {}).get('steps'):
        raise HTTPException(409,'Finish or cancel the pending action before requesting a new workload snapshot')
    data.module='PMS'
    try:today=datetime.now(ZoneInfo(data.timezone)).date()
    except (ZoneInfoNotFoundError,ValueError):raise HTTPException(422,'Choose a valid timezone') from None
    monday=today-timedelta(days=today.weekday())
    draft=dict(prior) if follow else {'project_id':data.project_id,'start':monday.isoformat(),'weeks':1}
    if not follow:draft['scope']='workspace' if workspace_requested else 'project'
    period=(match[1] if match else question[1] if question else text).lower() if (match and match[1] or question and question[1] or follow and '=' not in text) else ''
    if period:
        draft['start']=(monday+timedelta(weeks=1 if 'next' in period else 0)).isoformat();draft['weeks']=1;draft.pop('after_user_id',None)
    values=match[2] if match else text if follow and '=' in text else None
    def ask(message):return Plan(summary='Clarify the workload snapshot.',question=message,steps=[]),draft
    for part in (values or '').split(';'):
        if not part.strip():continue
        key,sep,value=part.strip().partition('=');value=value.strip()
        if not sep or key not in {'project','start','weeks','after_user_id','user'}:return ask('Use project=ID; start=YYYY-MM-DD (Monday); weeks=1..4; user=ID or after_user_id=ID.')
        key={'project':'project_id','user':'assignee_user_id'}.get(key,key)
        if key=='start':draft[key]=value
        else:
            if not re.fullmatch(r'[0-9]+',value):return ask('Use numeric project/user IDs, a Monday date, and weeks=1..4.')
            if key=='assignee_user_id':draft.pop('after_user_id',None)
            elif key=='after_user_id':draft.pop('assignee_user_id',None)
            elif key=='project_id' and draft.get('project_id')!=int(value):draft.pop('after_user_id',None)
            draft[key]=int(value)
    if not draft.get('project_id'):return ask('Which project anchors the selected workspace? Reply project=123; only authorized projects in that workspace will be included.' if draft.get('scope')=='workspace' else 'Which project should this workload snapshot cover? Reply project=123 in its workspace.')
    try:read=Read.model_validate({key:value for key,value in draft.items() if key!='project_id'})
    except ValueError:return ask('Choose a Monday start date, weeks=1..4, and either user=ID or a page cursor.')
    data.project_id=draft['project_id']
    data.context=[*data.context,Step(tool='pms.workload',record_id=draft['project_id'],payload=read.model_dump(mode='json',exclude_none=True))]
    if data.provider=='auto':data.provider='local'
    return (Plan(summary='Read the authorized workload snapshot.',steps=[]) if data.provider=='local' else None),draft


def read_followup(parent,packet,data):
    if not packet or not (parent.result or {}).get('workload_request'):return False
    if parent.status not in {'needs_clarification','answered'} or parent.receipts or parent.approval_id or (parent.plan or {}).get('steps'):return False
    prior=(parent.result or {}).get('request',{})
    if any(prior.get(key) for key in ('workflow_id','commitment_id','candidate_id')):return False
    if prior.get('project_id') not in (None,packet.get('project_id')):return False
    if prior.get('project_id') is None and parent.status!='needs_clarification':return False
    return bool(data.context) and all(step.tool=='pms.workload' and step.record_id==packet.get('project_id') for step in data.context)


def local_answer(context,sources):
    packets=[p for p in context if p['tool']=='pms.workload'];lines=[]
    for packet in packets:
        value=packet['records']
        if not isinstance(value,dict) or value.get('truncated'):continue
        coverage='authorized workspace projects only' if value.get('scope')=='authorized_workspace_projects' else 'selected project only'
        lines.append(f"{value['name']} ({value['start']} to {value['end']}), {coverage}.")
        if not value.get('rows'):lines.append('No project people were returned for these filters; this is not a company-wide availability result.')
        ranked=sorted(value.get('rows',[]),key=lambda p:(-sum(w['status']=='over' for w in p['weeks']),-max((w['utilization_percent'] for w in p['weeks']),default=0),p['user_id']))
        for person in ranked[:5]:
            over=sum(week['status']=='over' for week in person['weeks'])
            lines.append(f"{person['name']}: {person['planned_hours']:g} planned hours / {person['capacity_hours']:g} capacity hours; {over} overloaded week(s).")
        if value.get('has_more') or len(value.get('rows',[]))>5:lines.append('Additional people are not shown; narrow by user ID or request the next source page.')
    if not lines:return {'summary':'The workload snapshot could not fit the current source disclosure budget.','question':'Narrow the snapshot with user=ID and weeks=1, or use the native workload page.','steps':[],'source_ids':[]}
    lines.append('Work outside the stated scope, unassigned and out-of-window work are excluded. Low load does not prove availability; zero estimates are unknown effort. No assignments were changed.')
    return {'summary':'\n'.join(lines)[:2000],'steps':[],'source_ids':[s['id'] for s in sources if s['tool']=='pms.workload']}
