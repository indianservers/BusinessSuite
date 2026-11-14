"""Reviewed PMS view mutations using canonical native storage and Suite receipts."""
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import Field, create_model, model_validator
from sqlalchemy import or_, func
from app.core.deps import get_db, get_current_user
from app.ai_operator.suite_tools import Strict
from app.ai_operator.saved_view_actions import Create, Filters
from app.ai_operator.service import digest
from app.apps.project_management.models import PMSSavedFilter


class Update(Create):
    project_id: int = Field(gt=0, strict=True)
    view_id: int = Field(gt=0, strict=True)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class Remove(Strict):
    project_id: int = Field(gt=0, strict=True)
    view_id: int = Field(gt=0, strict=True)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class Read(Strict):
    after_id: int = Field(default=0,ge=0,le=9223372036854775807,strict=True)
    view_id: int | None = Field(default=None,gt=0,le=9223372036854775807,strict=True)
    name: str | None = Field(default=None,min_length=1,max_length=140)

    @model_validator(mode='after')
    def valid(self):
        if self.view_id is not None and (self.name is not None or self.after_id):raise ValueError('Select a view ID or a name/page cursor')
        if self.name is not None and (not self.name.strip() or re.search(r'[\x00-\x1f]',self.name)):raise ValueError('Use a plain nonempty view name')
        return self


ACTIONS = {'pms.update_saved_view', 'pms.remove_saved_view'}


def no_store(response:Response):
    response.headers['Cache-Control']='private, no-store'
    response.headers['X-Content-Type-Options']='nosniff'


router = APIRouter(prefix='/suite/pms/views', tags=['Reviewed saved views'],dependencies=[Depends(no_store)])


def state(row):
    fields = ('id','organization_id','user_id','project_id','name','view_type','entity_type',
              'query','filters_json','sort_json','columns_json','visibility','is_default','is_shared')
    return {**{key:getattr(row,key) for key in fields}, 'created_at':row.created_at.isoformat() if row.created_at else None}


def project(db,user,pid,workspace=None):
    from app.apps.project_management.access import get_project_for_action
    value=get_project_for_action(db,pid,user,'browse')
    if workspace is not None and value.workspace_id!=workspace:
        raise HTTPException(403,'Saved view project is outside this workspace')
    return value


def typed(row):
    try:
        raw=json.loads(row.filters_json or '{}')
        if 'projectId' in raw and raw.pop('projectId')!=str(row.project_id):return None
        # Keep custom native layouts intact. Only supported task-filter schemas
        # are offered for full filter replacement; opaque query data is never lost.
        query=json.loads(row.query or '{}')
        if query!={**raw,'projectId':str(row.project_id)} and query!=raw:return None
        return Filters.model_validate(raw)
    except (ValueError,TypeError,AttributeError):return None


def owned(db,user,pid,ident,workspace=None,lock=False):
    project(db,user,pid,workspace)
    query=db.query(PMSSavedFilter).filter_by(id=ident,project_id=pid,user_id=user.id,
        visibility='private',is_shared=False,entity_type='task',view_type='task_list')
    if lock:query=query.with_for_update().populate_existing()
    row=query.first()
    if not row or typed(row) is None:raise HTTPException(404,'Supported private task view not found')
    from app.ai_agents.services.advanced_security import company_id_for
    if row.organization_id not in (None,company_id_for(user)):
        raise HTTPException(404,'Supported private task view not found')
    return row


def listing(db,user,pid,workspace=None,*,read=None):
    read=read or Read()
    project(db,user,pid,workspace)
    from app.ai_agents.services.advanced_security import company_id_for
    query=db.query(PMSSavedFilter).filter_by(project_id=pid,user_id=user.id,
        visibility='private',is_shared=False,entity_type='task',view_type='task_list').filter(
        or_(PMSSavedFilter.organization_id.is_(None),PMSSavedFilter.organization_id==company_id_for(user)))
    if read.view_id is not None:query=query.filter(PMSSavedFilter.id==read.view_id)
    if read.name is not None:query=query.filter(or_(PMSSavedFilter.name==read.name,func.lower(PMSSavedFilter.name)==read.name.lower()))
    query=query.filter(PMSSavedFilter.id>read.after_id)
    rows=query.order_by(PMSSavedFilter.id).limit(26).all()
    has_more=len(rows)>25;page=rows[:25]
    items=[]
    for row in page:
        filters=typed(row)
        if filters is None:continue
        items.append({'id':row.id,'project_id':pid,'name':row.name,'filters':filters.model_dump(),
                      'source_sha256':digest(state(row)),'is_default':bool(row.is_default)})
    return {'items':items,'unsupported_views':len(page)-len(items),'unsupported_count_scope':'scanned_page',
            'page_size':25,'scanned_count':len(page),'has_more':has_more,'after_id':read.after_id,
            'next_after_id':page[-1].id if has_more else None}


@router.get('/records/{project_id}')
def records(project_id:int,after_id:int=Query(0,ge=0,le=9223372036854775807),
            view_id:int|None=Query(None,gt=0,le=9223372036854775807),name:str|None=Query(None,min_length=1,max_length=140),
            db=Depends(get_db),user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,None,'PMS')
    try:read=Read(after_id=after_id,view_id=view_id,name=name)
    except ValueError:raise HTTPException(422,'Choose a valid view ID or name/page cursor') from None
    return listing(db,user,project_id,read=read)


def model(step):return Update if step.tool=='pms.update_saved_view' else Remove


def checkpoint(run,step):
    value=(run.result or {}).get('saved_view_checkpoint') or {}
    return value if value.get('tool')==step.tool and value.get('step')==run.active_step and value.get('payload_hash')==digest(step.payload) else None


def preflight(db,user,run,step,index=None,lock=False):
    value=model(step).model_validate(step.payload)
    project(db,user,value.project_id,run.workspace_id)
    if checkpoint(run,step):return value
    row=owned(db,user,value.project_id,value.view_id,run.workspace_id,lock)
    if digest(state(row))!=value.source_sha256:raise HTTPException(409,'Saved view changed; read it again and review a fresh action')
    if step.tool=='pms.update_saved_view':
        if row.name==value.name and typed(row)==value.filters:raise HTTPException(422,'Choose a view value to change')
        duplicate=db.query(PMSSavedFilter.id).filter(PMSSavedFilter.project_id==value.project_id,
            PMSSavedFilter.user_id==user.id,PMSSavedFilter.name==value.name,PMSSavedFilter.id!=row.id).first()
        if duplicate:raise HTTPException(409,'A saved view with that name already exists')
    return value


def preview(db,user,run,step):
    value=preflight(db,user,run,step)
    row=owned(db,user,value.project_id,value.view_id,run.workspace_id)
    if step.tool=='pms.remove_saved_view':changes=[{'field':'saved_view','before':row.name,'after':'Removed; business records unchanged'}]
    else:
        changes=[{'field':'name','before':row.name,'after':value.name}] if row.name!=value.name else []
        changes.extend({'field':key,'before':old,'after':getattr(value.filters,key)} for key,old in typed(row).model_dump().items() if old!=getattr(value.filters,key))
    return {'record_id':row.id,'record_name':row.name,'changes':changes}


def confirmed(db,user,run,step):
    value=preflight(db,user,run,step);saved=checkpoint(run,step)
    if not saved:return None
    row=db.get(PMSSavedFilter,value.view_id)
    if step.tool=='pms.remove_saved_view':
        if row:raise HTTPException(409,'Removed view ID is present; reconcile the recorded receipt')
    else:
        row=owned(db,user,value.project_id,value.view_id,run.workspace_id)
        if digest(state(row))!=saved.get('state_hash'):raise HTTPException(409,'Committed view changed; reconcile the recorded receipt')
    return saved['receipt']


def register(action,Model):
    Approved=create_model('PMS'+action.title()+'ApprovedView',__base__=Model,suite_run_id=(int,Field(gt=0)),suite_step=(int,Field(ge=1,le=12)))
    @router.post('/'+action+'-approved')
    def execute(data:Approved,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
        from app.ai_operator.agent_connectors import reviewed_run
        from app.apps.project_management.api.router import update_saved_view_record,delete_saved_view_record
        from app.apps.project_management.schemas import PMSSavedFilterUpdate
        from app.ai_agents.services.audit import AiAuditService
        run,step=reviewed_run(db,user,request,data,Model,action+'_saved_view')
        previous=confirmed(db,user,run,step)
        if previous:return previous
        value=preflight(db,user,run,step,lock=True)
        row=owned(db,user,value.project_id,value.view_id,run.workspace_id,lock=True);name=row.name
        if action=='update':
            filters={**value.filters.model_dump(),'projectId':str(value.project_id)}
            update_saved_view_record(row.id,PMSSavedFilterUpdate(name=value.name,filters=filters,query=json.dumps(filters)),db,user,commit=False,manage_defaults=False)
            name=value.name;state_hash=digest(state(row))
        else:
            delete_saved_view_record(row.id,db,user,commit=False);state_hash=None
        receipt={'id':value.view_id,'name':name,'project_id':value.project_id,'visibility':'private','operation':action,
                 'url':'/pms/tasks/advanced'+(f'?view={value.view_id}' if action=='update' else '')}
        run.result={**(run.result or {}),'saved_view_checkpoint':{'step':data.suite_step,'tool':step.tool,'payload_hash':digest(step.payload),'state_hash':state_hash,'receipt':receipt}}
        AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='suite.saved_view.'+action,
            input_json={'suite_run_id':run.id,'step':data.suite_step},output_json=receipt,status='success')
        db.commit();return receipt


register('update',Update)
register('remove',Remove)


def prepare(data,parent,db,user):
    from app.ai_operator.suite import Plan,Step
    text=re.sub(r'(?i)^\s*PMS\s*:\s*','',data.text).strip()
    rename=re.fullmatch(r'(?is)rename\s+(?:(that|this|saved)\s+)?view(?:\s+called\s+(.+?))?\s+to\s+(.+)',text)
    if rename:
        pending=(parent.plan or {}).get('steps',[]) if parent and parent.status=='awaiting_approval' else []
        draft=(parent.result or {}).get('saved_view_draft') or {} if parent and parent.status=='needs_clarification' else {}
        selected=draft.get('module')=='PMS' and draft.get('_action')=='update' and draft.get('view_id')
        if rename[1] and rename[1].lower() in {'that','this'} and not rename[2] and (selected or len(pending)==1 and pending[0]['tool']=='pms.update_saved_view'):
            text='name='+rename[3].strip()
        else:
            target=('that ' if rename[1] and rename[1].lower() in {'that','this'} else '')+'view'+(' called '+rename[2] if rename[2] else '')
            text='update '+target+': name='+rename[3].strip()
    match=re.fullmatch(r'(?is)(update|edit|remove|delete)\s+(?:(saved|that|this)\s+)?(?:task\s+)?(?:view|filter)(?:\s+(?:called\s+)?([^:]+))?(?::\s*(.*))?',text)
    prior=(parent.result or {}).get('saved_view_draft') if parent and parent.status in {'needs_clarification','awaiting_approval'} else None
    if prior and (prior.get('module')!='PMS' or not prior.get('_action')):prior=None
    if parent and parent.status=='awaiting_approval' and len((parent.plan or {}).get('steps',[]))==1:
        step=parent.plan['steps'][0]
        if step['tool'] in ACTIONS:
            prior={**step['payload'],'module':'PMS','_action':step['tool'].split('.')[1].split('_')[0]}
    if not match and not prior:return None
    data.module='PMS'
    if re.fullmatch(r'(?i)(?:cancel|stop|discard)[.! ]*',text):return Plan(summary='PMS view request cancelled.',steps=[]),None
    action=('remove' if match[1].lower() in {'remove','delete'} else 'update') if match else prior['_action']
    draft={'module':'PMS','_action':action,'project_id':data.project_id,'_selector':match[3].strip() if match[3] else None,'_changes':{}} if match else json.loads(json.dumps(prior))
    if match and re.search(r'(?i)(?:view|filter)\s+called\s',text):draft['_selector_kind']='name'
    values=match[4] if match else text
    if prior and not match:
        natural=re.fullmatch(r'(?i)(?:make|set)\s+(?:it|this|that|the view)(?:\s+priority)?\s+(?:to\s+)?(low|medium|high|urgent|critical)[.! ]*',text)
        if natural:values='priority='+natural[1].title()
    if match and match[2] and match[2].lower() in {'that','this'} and not draft['_selector'] and parent and parent.status=='succeeded':
        receipts=[r for r in parent.receipts or [] if r.get('tool','').startswith('pms.') and r.get('tool','').endswith('_saved_view') and r.get('status')=='succeeded']
        if receipts:
            receipt=receipts[-1];draft['_selector']=str(receipt['record_id'])
            with_project=(parent.plan or {}).get('steps',[])[receipt['step']-1]['payload'].get('project_id')
            draft['project_id']=draft['project_id'] or with_project
    def ask(question):return Plan(summary='Clarify the PMS saved view.',question=question,steps=[]),draft
    for part in (values or '').split(';'):
        if not part.strip():continue
        key,sep,value=part.strip().partition('=');value=value.strip()
        if not sep or key not in {'view','project','name','status','priority','search','assignee','dueFrom','dueTo'}:
            return ask('Use view=ID or exact name; project=ID; name=...; status=...; priority=High; search=...; assignee=ID; dueFrom=YYYY-MM-DD; dueTo=YYYY-MM-DD.')
        if key=='view':
            if draft.get('view_id'):draft['_changes']={}
            draft['_selector']=value;draft['_selector_kind']='id' if value.isascii() and value.isdecimal() else 'name'
            draft.pop('view_id',None);draft.pop('source_sha256',None)
        elif key=='project':
            if not re.fullmatch(r'[1-9]\d*',value):return ask('Reply project=123 using the project ID.')
            if draft.get('project_id')!=int(value):
                draft.pop('view_id',None);draft.pop('source_sha256',None)
            draft['project_id']=int(value)
        else:
            draft.setdefault('_changes',{})['assigneeId' if key=='assignee' else key]=value
    if not draft.get('project_id'):return ask('Which project contains the view? Reply project=123.')
    selector=str(draft.get('view_id') or draft.get('_selector') or '')
    try:
        by_id=bool(draft.get('view_id')) or draft.get('_selector_kind')!='name' and selector.isascii() and selector.isdecimal()
        read=Read(view_id=int(selector)) if by_id else Read(name=selector.strip('"')) if selector else Read()
        source=listing(db,user,draft['project_id'],data.workspace_id,read=read);items=source['items']
    except ValueError:return ask('Use a valid view ID or a plain view name of at most 140 characters.')
    except HTTPException:return ask('Choose an accessible project in this conversation workspace.')
    if not draft.get('view_id'):
        if not selector or len(items)!=1 or source['has_more']:
            return ask('Which private task view should change? Reply view=ID or its exact name. Use an ID when names are ambiguous.')
        selected=items[0]
        draft.update(view_id=selected['id'],name=selected['name'],filters=dict(selected['filters']),source_sha256=selected['source_sha256'])
    changes=draft.get('_changes',{})
    if action=='remove' and changes:return ask('Removal has no editable values. Start an update request to change the view instead.')
    if 'name' in changes:draft['name']=changes['name']
    for key,value in changes.items():
        if key!='name':draft['filters'][key]=value
    if action=='update':
        current=next((item for item in items if item['id']==draft['view_id']),None)
        if current and current['name']==draft['name'] and current['filters']==draft['filters']:
            return ask('What should change? Reply name=... or a filter such as priority=High.')
    keys=('project_id','view_id','source_sha256','name','filters') if action=='update' else ('project_id','view_id','source_sha256')
    try:payload=(Update if action=='update' else Remove).model_validate({key:draft[key] for key in keys}).model_dump()
    except ValueError:return ask('Check the view name, priority, assignee ID and ISO date range; send corrected name=value fields.')
    return Plan(summary='Review the private PMS view '+action+'. Tasks, sharing and layout are unchanged.',steps=[Step(tool='pms.'+action+'_saved_view',payload=payload)]),draft
