"""Private versioned artifacts over the existing assistant storage and reviews.

Artifact content is inert text/data, never executable HTML, formulas or tools.
Writes are bound to the exact active, approved suite step. No browser storage.
"""
import csv
import io
import json
import re
from typing import Literal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import Field, model_validator,model_serializer
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.ai_agents.security import company, verify
from app.ai_agents.services.audit import AiAuditService
from app.ai_operator.assistant_models import AssistantConversation, AssistantMessage
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest
from app.ai_operator.artifact_charts import Chart
from app.ai_operator.artifact_dashboards import Panel

router=APIRouter(prefix='/suite/artifacts',tags=['Bot artifacts'])
Module=Literal['CRM','PMS','HRMS']
VERSION_TOOL='suite.artifact.version'


class Slide(Strict):
    title:str=Field(min_length=1,max_length=160)
    bullets:list[str]=Field(default_factory=list,max_length=6)

    @model_validator(mode='after')
    def bounded(self):
        if not self.title.strip() or any(not v.strip() or len(v)>240 for v in self.bullets):raise ValueError('Use a slide title and up to six nonempty points of at most 240 characters each')
        if any(re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]',v) for v in [self.title,*self.bullets]):raise ValueError('Slide contains unsupported characters')
        return self


class Body(Strict):
    title:str=Field(min_length=1,max_length=160)
    kind:Literal['document','checklist','table','presentation','dashboard']='document'
    content:str=Field(default='',max_length=20000)
    columns:list[str]=Field(default_factory=list,max_length=12)
    rows:list[list[str]]=Field(default_factory=list,max_length=100)
    slides:list[Slide]=Field(default_factory=list,max_length=20)
    chart:Chart|None=None
    panels:list[Panel]=Field(default_factory=list,max_length=6)

    @model_serializer(mode='wrap')
    def serialize(self,handler):
        value=handler(self)
        if not self.slides:value.pop('slides',None)
        if self.chart is None:value.pop('chart',None)
        if not self.panels:value.pop('panels',None)
        return value

    @model_validator(mode='after')
    def bounded(self):
        if not self.title.strip():raise ValueError('Artifact needs a title')
        if any(re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]',v) for v in [self.title,self.content,*self.columns,*[c for r in self.rows for c in r]]):raise ValueError('Artifact contains unsupported control characters')
        if self.kind=='dashboard':
            if not self.panels or self.columns or self.rows or self.slides:raise ValueError('Dashboards need 1–6 pinned source panels and no table or slide fields')
        elif self.panels:raise ValueError('Only dashboards can contain panels')
        elif self.kind=='presentation':
            if not self.slides or self.content or self.columns or self.rows:raise ValueError('Presentations need 1–20 structured slides and empty content/columns/rows')
        elif self.slides:raise ValueError('Only presentations can contain slides')
        elif self.kind=='table':
            if not self.columns or any(not c.strip() or len(c)>100 for c in self.columns):raise ValueError('Provide 1–12 named columns')
            if any(len(r)!=len(self.columns) or any(len(c)>500 for c in r) for r in self.rows):raise ValueError('Rows must match columns; cells at most 500 characters')
        elif self.columns or self.rows or not self.content.strip():raise ValueError('Documents and checklists need text and cannot contain table fields')
        if self.chart:
            if self.kind!='table':raise ValueError('Charts require an artifact table')
            from app.ai_operator.artifact_charts import analyze
            analyze({'columns':self.columns,'rows':self.rows,'chart':self.chart.model_dump()})
        if len(json.dumps(self.model_dump(),ensure_ascii=False).encode('utf-8'))>30000:raise ValueError('Artifact exceeds 30 KB; split it into smaller artifacts')
        return self


class Edit(Body):
    artifact_id:int=Field(gt=0)
    expected_revision:int=Field(ge=1)


class CreateApproved(Body):
    suite_run_id:int=Field(gt=0)
    suite_step:int=Field(ge=1,le=12)


class EditApproved(Edit):
    suite_run_id:int=Field(gt=0)
    suite_step:int=Field(ge=1,le=12)


class PanelPreview(Strict):
    module:Module
    workspace_id:int|None=Field(default=None,gt=0)
    panel:Panel


@router.post('/panel-preview')
def panel_preview(data:PanelPreview,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    access(db,user,data.workspace_id,data.module)
    from app.ai_agents.api import _require_ai_rate_limit
    from app.ai_operator.artifact_dashboards import resolve
    from app.ai_operator.artifact_charts import evidence
    _require_ai_rate_limit(db,request,user,bucket='artifact_analysis')
    value=data.panel.model_dump();source=resolve(db,user,data.workspace_id,value)
    return {'panel':value,'source':source,'citation':evidence(source),'dashboard_revision':None}


def access(db,user,workspace_id,module,project_id=None):
    from app.ai_operator.suite import memory_scope
    scope=memory_scope(db,user,workspace_id,module)
    if project_id:
        from app.ai_operator.workbench import access as project_access
        project,_=project_access(db,user,project_id)
        if project.workspace_id!=workspace_id:raise HTTPException(403,'Artifact project is outside this workspace')
    return scope


def owned(db,user,ident,lock=False):
    query=db.query(AssistantConversation).filter_by(id=ident,user_id=user.id,organization_id=company(user),deleted_at=None)
    row=(query.with_for_update() if lock else query).first()
    if not row or not (row.references or {}).get('suite_artifact'):raise HTTPException(404,'Artifact not found')
    verify(db,user,row.security_context,history=True)
    r=row.references
    if access(db,user,row.workspace_id,r['module'],r.get('project_id'))!=r['scope_key']:raise HTTPException(403,'Artifact scope changed')
    return row


def version(db,user,row,revision=None):
    revision=row.references['revision'] if revision is None else revision
    message=db.query(AssistantMessage).filter_by(conversation_id=row.id,tool=VERSION_TOOL,status='stored').filter(
        AssistantMessage.arguments['revision'].as_integer()==revision).first()
    if not message:raise HTTPException(404,'Artifact version not found')
    verify(db,user,message.security_context,history=True)
    return message


def public(db,user,row,revision=None):
    msg=version(db,user,row,revision);r=row.references
    return {'id':row.id,'module':r['module'],'workspace_id':row.workspace_id,'project_id':r.get('project_id'),
            'conversation_id':r.get('conversation_id'),'revision':msg.arguments['revision'],'current_revision':r['revision'],
            **msg.arguments['body'],'provenance':msg.arguments['provenance'],'created_at':msg.created_at.isoformat() if msg.created_at else None}


@router.get('')
def listing(module:Module,workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    scope=access(db,user,workspace_id,module)
    query=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=workspace_id,deleted_at=None).filter(
        AssistantConversation.references['suite_artifact'].as_boolean()==True,
        AssistantConversation.references['scope_key'].as_string()==scope,
        AssistantConversation.references['module'].as_string()==module).order_by(AssistantConversation.id.desc()).limit(50)
    items=[]
    for row in query:
        try:
            value=public(db,user,owned(db,user,row.id))
        except HTTPException:continue
        items.append({k:value[k] for k in ('id','title','kind','module','revision','current_revision','project_id')})
    return {'items':items,'limit':50}


@router.get('/current')
def current(artifact_id:int,module:Module,workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,artifact_id)
    if row.references['module']!=module or row.workspace_id!=workspace_id:raise HTTPException(403,'Select the artifact in its original module/workspace')
    return public(db,user,row)


@router.get('/dashboard-panel/current')
def dashboard_panel_current(request:Request,response:Response,artifact_id:int,position:int,module:Module,workspace_id:int|None=None,
    dashboard_revision:int|None=None,category_query:str='',agent_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.artifact_questions import PanelRead,read
    from app.ai_agents.api import _require_ai_rate_limit
    try:query=PanelRead(artifact_id=artifact_id,position=position,dashboard_revision=dashboard_revision,category_query=category_query)
    except ValueError:raise HTTPException(422,'Choose a valid dashboard, panel, saved version and category filter') from None
    _require_ai_rate_limit(db,request,user,bucket='artifact_analysis')
    response.headers['Cache-Control']='no-store'
    return read(db,user,module,workspace_id,query,agent_id)


@router.get('/{ident}')
def get(ident:int,revision:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return public(db,user,owned(db,user,ident),revision)


@router.get('/{ident}/versions')
def versions(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident);items=[]
    for msg in db.query(AssistantMessage).filter_by(conversation_id=row.id,tool=VERSION_TOOL,status='stored').order_by(AssistantMessage.id.desc()).limit(100):
        verify(db,user,msg.security_context,history=True)
        items.append({'revision':msg.arguments['revision'],'title':msg.arguments['body']['title'],'created_at':msg.created_at})
    return {'items':items,'current_revision':row.references['revision']}


@router.get('/{ident}/panels/{position}')
def panel(ident:int,position:int,request:Request,revision:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    item=public(db,user,owned(db,user,ident),revision)
    if item['kind']!='dashboard' or not 1<=position<=len(item['panels']):raise HTTPException(404,'Dashboard panel not found')
    from app.ai_agents.api import _require_ai_rate_limit
    from app.ai_operator.artifact_dashboards import resolve
    from app.ai_operator.artifact_charts import evidence
    _require_ai_rate_limit(db,request,user,bucket='artifact_analysis')
    value=item['panels'][position-1];source=resolve(db,user,item['workspace_id'],value)
    return {'panel':value,'source':source,'citation':evidence(source),'dashboard_revision':item['revision']}


@router.delete('/{ident}')
def archive(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True);row.deleted_at=datetime.now(timezone.utc)
    from app.ai_operator.artifact_shares import archive_source
    archive_source(db,user,ident)
    AiAuditService(db).log(user=user,agent_id=None,module=row.references['module'],action='suite.artifact.archived',
        input_json={'artifact_id':row.id},output_json={'archived':True},status='success')
    db.commit();return {'archived':True}


def validate_step(db,user,workspace_id,module,payload,project_id=None):
    """Called both before review and immediately before the canonical write."""
    access(db,user,workspace_id,module,project_id)
    from app.ai_operator.artifact_dashboards import validate
    validate(db,user,workspace_id,payload)
    if 'artifact_id' in payload:
        row=owned(db,user,payload['artifact_id'])
        if row.workspace_id!=workspace_id or row.references['module']!=module:raise HTTPException(403,'Artifact belongs to another module/workspace')
        if row.references['revision']!=payload['expected_revision']:raise HTTPException(409,'Artifact changed. Reload and prepare a new edit.')
        if row.references['kind']!=payload['kind']:raise HTTPException(422,'Artifact format cannot change during an edit')


def validation_feedback(plan,exc):
    """Field/type diagnostics only; never log provider text or validation inputs."""
    issues=[]
    for index,step in enumerate(plan.steps,1):
        model=Edit if step.tool.endswith('.edit_artifact') else Body
        errors=[]
        try:model.model_validate(step.payload)
        except ValueError as error:
            if hasattr(error,'errors'):
                errors=[{'field':'.'.join(str(p) if type(p) is int or p in model.model_fields or p in Slide.model_fields or p in Panel.model_fields or p in Chart.model_fields else 'unexpected_field' for p in e['loc'])[:120],'type':e['type']} for e in error.errors(include_input=False,include_context=False,include_url=False)[:12]]
        issues.append({'step':index,'tool':step.tool,'record_id_present':step.record_id is not None,'schema_errors':errors})
    safe={'This tool does not accept a record ID','Tool contains unsupported fields','Tool payload is incomplete or invalid','Artifact format cannot change during an edit'}
    return {'reason':exc.detail if isinstance(exc.detail,str) and exc.detail in safe else 'Artifact proposal failed validation','issues':issues,
            'instruction':'Correct only the artifact proposal schema. Artifact IDs belong in payload.artifact_id, never step.record_id. Use expected_revision from current authorized artifact_context. Keep the requested artifact/tool, its kind, unrelated content and all access boundaries. Return a question with no steps if details are missing. Do not propose business mutations or extra tools.'}


def approved(db,user,request,data,editing):
    from app.core.security import verify_access_token
    from app.ai_operator.suite import owned as run_owned
    from app.ai_agents.models import AiActionApproval
    claims=verify_access_token(request.headers.get('authorization','').partition(' ')[2]) or {}
    if not claims.get('ai_origin'):raise HTTPException(403,'Artifacts must be saved through a reviewed bot action')
    run=run_owned(db,user,data.suite_run_id,True)
    approval=db.get(AiActionApproval,run.approval_id) if run.approval_id else None
    if run.status!='executing' or run.active_step!=data.suite_step or not approval or approval.status!='approved':
        raise HTTPException(409,'Artifact action is not the active approved step')
    verify(db,user,approval.security_context,payload=approval.proposed_action_json,history=True)
    if approval.proposed_action_json.get('input',{}).get('plan_hash')!=run.plan_hash:raise HTTPException(409,'Artifact approval no longer matches this plan')
    step=run.plan['steps'][data.suite_step-1]
    module=step['tool'].split('.')[0].upper()
    if module not in ('CRM','PMS','HRMS') or step['tool']!=f'{module.lower()}.{"edit_artifact" if editing else "create_artifact"}':raise HTTPException(403,'Artifact action does not match approval')
    model=Edit if editing else Body
    expected=model.model_validate(step['payload']).model_dump(mode='json')
    actual=model.model_validate(data.model_dump(exclude={'suite_run_id','suite_step'})).model_dump(mode='json')
    if digest(expected)!=digest(actual) or digest(run.plan)!=run.plan_hash:raise HTTPException(409,'Artifact content changed since review')
    return run,module,actual


def save(db,user,request,data,editing=False):
    run,module,payload=approved(db,user,request,data,editing)
    key=digest({'run':run.id,'step':data.suite_step})
    # A repeated dispatch of this exact reviewed step returns its original receipt.
    previous=db.query(AssistantMessage).join(AssistantConversation,AssistantMessage.conversation_id==AssistantConversation.id).filter(
        AssistantConversation.user_id==user.id,AssistantConversation.organization_id==company(user),
        AssistantMessage.tool==VERSION_TOOL,AssistantMessage.request_key==key).first()
    if previous:
        row=owned(db,user,previous.conversation_id)
        verify(db,user,previous.security_context,history=True)
        return {'id':row.id,'artifact_id':row.id,'artifact_revision':previous.arguments['revision'],'artifact_kind':previous.arguments['body']['kind']}
    source=run.result['request'];project_id=source.get('project_id') if module=='PMS' else None
    from app.ai_operator.artifact_templates import enforce as enforce_template
    from app.ai_operator.suite import Step
    enforce_template(db,user,run,[Step.model_validate(run.plan['steps'][data.suite_step-1])],lock=True)
    from app.ai_operator.artifact_charts import enforce_sources
    enforce_sources(db,user,run)
    validate_step(db,user,run.workspace_id,module,payload,project_id)
    if editing:
        row=owned(db,user,payload['artifact_id'],True);old=row.references['revision'];revision=old+1
        if old!=payload['expected_revision']:raise HTTPException(409,'Artifact changed. Prepare a new reviewed edit.')
        if revision>100:raise HTTPException(422,'Version limit reached; create a separate artifact')
    else:
        scope=access(db,user,run.workspace_id,module,project_id)
        if db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=run.workspace_id,deleted_at=None).filter(AssistantConversation.references['suite_artifact'].as_boolean()==True).count()>=100:
            raise HTTPException(422,'Artifact storage limit reached')
        row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=run.workspace_id,title=payload['title'],references={
            'suite_artifact':True,'scope_key':scope,'module':module,'project_id':project_id,'conversation_id':source.get('conversation_id'),'kind':payload['kind'],'revision':1})
        db.add(row);db.flush();revision=1
    body=Body.model_validate(payload if not editing else {k:v for k,v in payload.items() if k not in ('artifact_id','expected_revision')}).model_dump(mode='json')
    citations=list(run.result.get('citations',[]))
    if editing:
        for citation in version(db,user,row,old).arguments['provenance'].get('citations',[]):
            if citation not in citations:citations.append(citation)
    provenance={'suite_run_id':run.id,'plan_hash':run.plan_hash,'base_revision':old if editing else None,'citations':citations[:50],'note':'Reviewed generated/user content. Source references reflect preparation time; facts require verification.'}
    template=(run.result or {}).get('artifact_template') or (version(db,user,row,old).arguments['provenance'].get('template') if editing else None)
    if template:provenance['template']={k:template[k] for k in ('id','revision','definition_hash')}
    msg=AssistantMessage(conversation_id=row.id,request_key=key,request_hash=digest(payload),prompt='Reviewed artifact revision',tool=VERSION_TOOL,
        arguments={'revision':revision,'body':body,'provenance':provenance},status='stored')
    db.add(msg);db.flush()
    if editing:
        changed=db.query(AssistantConversation).filter(AssistantConversation.id==row.id,AssistantConversation.references['revision'].as_integer()==old).update(
            {AssistantConversation.references:{**row.references,'revision':revision},AssistantConversation.title:body['title']},synchronize_session=False)
        if not changed:db.rollback();raise HTTPException(409,'Artifact changed. Prepare a fresh review.')
    AiAuditService(db).log(user=user,agent_id=None,module=module,action='suite.artifact.revised' if editing else 'suite.artifact.created',input_json={'artifact_id':row.id,'suite_run_id':run.id},output_json={'revision':revision},status='success')
    db.commit()
    return {'id':row.id,'artifact_id':row.id,'artifact_revision':revision,'artifact_kind':body['kind']}


@router.post('/create-approved')
def create(data:CreateApproved,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return save(db,user,request,data)


@router.post('/edit-approved')
def edit(data:EditApproved,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return save(db,user,request,data,True)


@router.get('/{ident}/download')
def download(ident:int,request:Request,format:Literal['md','csv','docx','xlsx','pdf','pptx']='md',revision:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident)
    from app.access.service import check_background_access
    from app.ai_operator.suite import MODULES
    check_background_access(db,user,MODULES[row.references['module']],'export')
    if format in ('pdf','pptx'):
        from app.ai_agents.api import _require_ai_rate_limit
        _require_ai_rate_limit(db,request,user,bucket='artifact_exports')
    item=public(db,user,row,revision)
    sources=None
    if item['kind']=='dashboard':
        from app.ai_operator.artifact_dashboards import resolve
        sources=[resolve(db,user,row.workspace_id,panel,export=True) for panel in item['panels']]
    content,mime=render_download(item,format,sources)
    AiAuditService(db).log(user=user,agent_id=None,module=item['module'],action='suite.artifact.exported',input_json={'artifact_id':ident,'revision':item['revision']},output_json={'format':format},status='success');db.commit()
    return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="artifact-{ident}-v{item["revision"]}.{format}"','X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})


def render_download(item,format,sources=None):
    """Pure export rendering shared by private and explicitly published snapshots."""
    body=io.BytesIO()
    # Spreadsheet expressions are inert strings, including formula-like input.
    def cell(value):return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value
    if format=='csv' and item['kind']!='table' or format=='xlsx' and item['kind'] not in ('table','dashboard'):raise HTTPException(422,'Choose a document download for this artifact')
    if format=='pdf':
        from app.ai_operator.artifact_exports import pdf
        if sources is not None:
            from app.ai_operator.artifact_dashboards import export_pdf
            content=export_pdf(item,sources)
        else:content=pdf(item)
        mime='application/pdf'
    elif format=='pptx':
        if item['kind']!='presentation':raise HTTPException(422,'PowerPoint export requires a presentation artifact')
        from app.ai_operator.artifact_exports import powerpoint
        content=powerpoint(item);mime='application/vnd.openxmlformats-officedocument.presentationml.presentation'
    elif format=='csv':
        stream=io.StringIO();writer=csv.writer(stream);writer.writerows([[cell(v) for v in r] for r in [item['columns'],*item['rows']]])
        content=stream.getvalue().encode('utf-8-sig');mime='text/csv'
    elif format=='xlsx' and sources is not None:
        from app.ai_operator.artifact_dashboards import export_excel
        content=export_excel(item,sources);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif format=='xlsx':
        from openpyxl import Workbook
        book=Workbook();sheet=book.active;sheet.title='Artifact'
        for values in [item['columns'],*item['rows']]:
            sheet.append(values)
            for value in sheet[sheet.max_row]:value.data_type='s'
        if item['content']:
            notes=book.create_sheet('Notes');notes.cell(1,1,item['content']).data_type='s'
        sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        if item.get('chart'):
            from app.ai_operator.artifact_chart_exports import excel
            excel(book,item)
        book.save(body);content=body.getvalue();mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif format=='docx':
        from docx import Document
        document=Document();document.add_heading(item['title'],0)
        if sources is not None:
            from app.ai_operator.artifact_dashboards import text
            for line in text(item,sources).splitlines():document.add_paragraph(line)
        elif item['kind']=='table':
            if item['content']:document.add_paragraph(item['content'])
            table=document.add_table(rows=1,cols=len(item['columns']));table.style='Table Grid'
            for c,v in zip(table.rows[0].cells,item['columns']):c.text=v
            for values in item['rows']:
                for c,v in zip(table.add_row().cells,values):c.text=v
        elif item['kind']=='presentation':
            for slide in item['slides']:
                document.add_heading(slide['title'],1)
                for point in slide['bullets']:document.add_paragraph(point,style='List Bullet')
        else:
            for line in item['content'].splitlines():document.add_paragraph(line)
        if item.get('chart'):
            from app.ai_operator.artifact_charts import summary
            document.add_heading('Computed chart statistics',1);document.add_paragraph(summary(item,item['revision']))
        document.save(body);content=body.getvalue();mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        text='# '+item['title']+'\n\n'+item['content']
        if sources is not None:
            from app.ai_operator.artifact_dashboards import text as dashboard_text
            text=dashboard_text(item,sources)
        if item['kind']=='presentation':text+='\n\n'+'\n\n'.join('## '+s['title']+'\n'+'\n'.join('- '+p for p in s['bullets']) for s in item['slides'])
        if item['kind']=='table':text+='\n\n'+ '\n'.join(' | '.join(v.replace('|','\\|').replace('\n',' ') for v in r) for r in [item['columns'],['---']*len(item['columns']),*item['rows']])
        if item.get('chart'):
            from app.ai_operator.artifact_charts import summary
            text+='\n\n'+summary(item,item['revision'])
        content=text.encode('utf-8');mime='text/markdown'
    return content,mime


def business_request(text):
    return bool(re.match(r'(?i)^\s*(?:please\s+)?(?:add|create|update|remove|edit|make|set|mark|assign|schedule|complete|close)\s+(?:(?:a|an|the|this|that|these|all|my|selected)\s+){0,3}(?:(?:CRM|PMS|HRMS)\s+)?(?:(?:high|medium|low|urgent)\s+(?:priority\s+)?)?(?:tasks?|leads?|tickets?|invoices?|leave|employees?|milestones?|projects?)\b',text))


# One grammar is shared by initial routing and clarification reconstruction.
ARTIFACT_FORMATS=r'(?:excel workbook|excel spreadsheet|excel sheet|excel|worksheet|word document|word|docx|pdf document|pdf report|document|proposal|report|brief|checklist|table|spreadsheet|presentation|slide deck|powerpoint presentation|powerpoint|pptx|pdf|bar chart|line chart|pie chart|chart|dashboard)'
ARTIFACT_CREATE=re.compile(r'(?is)^\s*(?:please\s+)?(?:create|draft|write|prepare)\s+(?:an?\s+)?('+ARTIFACT_FORMATS+r')\b\s*(.*)')


def creation_request(text):
    return bool(ARTIFACT_CREATE.match(text))


def conversation_context(db,user,data,history):
    # A record ID inside literal document/task/memory text is data, not a read.
    match=re.match(r'\s*(?:please\s+)?(?:edit|update|revise|show|read|open|rewrite|shorten|make|rename|summari[sz]e|analy[sz]e)\s+(?:the\s+)?artifact\s*#?\s*(\d+)\b',data.text,re.I)
    ident=data.artifact_id or (int(match[1]) if match else None)
    if not ident and not business_request(data.text) and re.match(r'\s*(?:please\s+)?(?:edit|revise|rewrite|append|add|remove|replace|rename|shorten|make|(?:move|refresh|update)(?=\s+(?:slide|panel)\b)|chart|(?:set|change)(?=\s+(?:the\s+)?chart\b)|analy[sz]e(?=\s+(?:(?:this|the)\s+)?(?:artifact|table|chart)\b))\b',data.text,re.I):
        for run in reversed(history):
            receipts=[r for r in run.receipts or [] if r.get('artifact_id')]
            if receipts:ident=receipts[-1]['artifact_id'];break
            # A later completed business action becomes the conversational
            # focus. Do not silently edit an older document behind it.
            if run.receipts:break
    if not ident:return None
    row=owned(db,user,ident)
    if row.workspace_id!=data.workspace_id:raise HTTPException(409,'Edit the artifact in its original workspace')
    data.module=row.references['module'];data.artifact_id=ident
    data.project_id=row.references.get('project_id')
    return public(db,user,row)


def local_plan(data,parent,context,attachments):
    """Bounded local drafting. User text stays literal; no invented company facts."""
    from copy import deepcopy
    from app.ai_operator.suite import Plan,Step
    text=data.text.strip();prefix=data.module.lower() if data.module in ('CRM','PMS','HRMS') else None
    if not prefix:return None
    if parent and parent.status=='needs_clarification' and not business_request(text) and not re.match(r'(?i)^(?:create|draft|write|prepare)\b',text):
        original=ARTIFACT_CREATE.match(parent.command)
        if original and parent.plan.get('summary')=='I need a title for the artifact.':text=f'Create {original[1]} called {text}'
        elif original and parent.plan.get('summary')=='I need the table columns.':text=f'{parent.command} with columns {text}'
        elif original and parent.plan.get('summary')=='I need valid table rows.':text=f'{parent.command.partition(":")[0]}: {text}'
        elif original and parent.plan.get('summary')=='I need dashboard sources.':text=f'{parent.command.partition(":")[0]}: {text}'
    pending=(parent.plan or {}).get('steps',[]) if parent and parent.status=='awaiting_approval' else []
    draft=deepcopy(pending[0]) if len(pending)==1 and pending[0]['tool'].endswith(('.create_artifact','.edit_artifact')) else None
    create=ARTIFACT_CREATE.match(text)
    if create:
        kind='dashboard' if create[1].lower()=='dashboard' else 'presentation' if create[1].lower() in ('presentation','slide deck','powerpoint presentation','powerpoint','pptx') else 'table' if create[1].lower() in ('table','spreadsheet','excel workbook','excel spreadsheet','excel sheet','excel','worksheet','chart','bar chart','line chart','pie chart') else 'checklist' if create[1].lower()=='checklist' else 'document'
        rest=re.sub(r'^(?:called|named|titled)\s+','',create[2],flags=re.I).strip()
        title,sep,content=rest.partition(':');title=title.strip()
        if len(title)>1 and title[0]==title[-1] and title[0] in {'"',"'"}:title=title[1:-1]
        if not title:return Plan(summary='I need a title for the artifact.',question='Give the artifact a title and any content, for example: Create document called Launch brief: goals and next steps.',steps=[])
        if kind=='dashboard':
            panels=[]
            for reference in content.split(';') if content.strip() else []:
                parsed=re.fullmatch(r'(?i)\s*(?:artifact\s*)?#?(\d+)\s+(?:v|version\s*)(\d+)(?:\s+as\s+(chart|table|summary|auto))?\s*',reference)
                if not parsed:panels=[];break
                panels.append(Panel(artifact_id=int(parsed[1]),revision=int(parsed[2]),display=parsed[3] or 'auto').model_dump())
            if not panels:return Plan(summary='I need dashboard sources.',question='Choose saved source versions: artifact #12 v1 as chart; artifact #13 v2 as summary. Open Artifacts to find IDs and versions. Sources must be in this workspace and accessible to you.',steps=[])
            body={'title':title,'kind':kind,'content':'','columns':[],'rows':[],'panels':panels}
        elif kind=='presentation':
            from app.ai_operator.artifact_slides import parse
            body={'title':title,'kind':kind,'content':'','columns':[],'rows':[],'slides':parse(content,title)}
        elif kind=='table':
            parts=re.split(r'\s+with columns\s+',title,flags=re.I,maxsplit=1)
            if len(parts)!=2:return Plan(summary='I need the table columns.',question='Include its title and columns, for example: Create table called Launch tracker with columns Task, Owner, Status.',steps=[])
            body={'title':parts[0],'kind':kind,'columns':next(csv.reader([parts[1]],skipinitialspace=True)),'rows':[],'content':''}
            if content.strip():
                try:
                    rows=list(csv.reader(io.StringIO(content.strip()),skipinitialspace=True,strict=True))
                except csv.Error:rows=None
                if rows is None or any(len(row)!=len(body['columns']) for row in rows):
                    return Plan(summary='I need valid table rows.',question='Supply CSV rows with one value per column, one row per line. Quote values containing commas. No artifact has been saved.',steps=[])
                body['rows']=rows
            if 'chart' in create[1].lower():body['chart']=Chart(kind=create[1].lower().split()[0] if ' ' in create[1] else 'bar',category_column=0,value_column=1 if len(body['columns'])>1 else None,aggregation='sum' if len(body['columns'])>1 else 'count').model_dump()
        else:
            if not content.strip() and attachments:
                content='\n\n'.join(f'Unverified uploaded source: {a["label"]}\n{a["text"]}' for a in attachments)
            if not content.strip():content=f'# {title}\n\nPurpose: {title}\n\n'+('- [ ] Define goals\n- [ ] Assign an owner\n- [ ] Review completion criteria' if kind=='checklist' else '## Goals\nTo be filled in.\n\n## Plan\nTo be filled in.\n\n## Next steps\nTo be agreed.')
            body={'title':title,'kind':kind,'content':content.strip(),'columns':[],'rows':[]}
        try:Body.model_validate(body)
        except ValueError:raise HTTPException(422,'Artifact is too large or invalid; split it or correct its table columns') from None
        return Plan(summary='Review this server artifact draft. Local drafting uses your text and placeholders; it does not invent business facts.',steps=[Step(tool=f'{prefix}.create_artifact',payload=body)])
    if not context and (not draft or business_request(text)):return None
    if context and re.match(r'(?i)^(?:show|read|open)\s+(?:the\s+)?artifact\b',text):
        return Plan(summary=f"Server artifact #{context['id']}: {context['title']} (version {context['revision']}). Open the workspace to read its full content and version history.",steps=[])
    body=deepcopy(draft['payload'] if draft else {k:context.get(k,[]) if k in ('slides','panels') else context.get(k) if k=='chart' else context[k] for k in Body.model_fields})
    operation=re.sub(r'(?is)^(?:edit|update|revise)\s+(?:artifact\s*#?\s*\d+|(?:this|the)\s+(?:artifact|document|table|checklist|presentation|deck))\s*:?\s*','',text)
    if body['kind']=='table' and re.fullmatch(r'(?i)(?:analy[sz]e (?:(?:this|the) )?(?:artifact\s*#?\s*\d+|table|chart)|show (?:the )?chart statistics)[.! ]*',operation):
        from app.ai_operator.artifact_charts import summary,evidence
        return Plan(summary=summary(body,None if draft else context['revision']),steps=[Step.model_validate(draft)] if draft else [],source_ids=[] if draft else [evidence(context)['id']])
    chart_edit=None
    if body['kind']=='dashboard':
        from app.ai_operator.artifact_dashboards import edit as edit_dashboard
        try:chart_edit=edit_dashboard(body,operation)
        except ValueError:raise HTTPException(422,'Check panel numbers, source IDs, versions and the six-panel limit') from None
    if body['kind']=='table':
        from app.ai_operator.artifact_charts import edit as edit_chart
        try:chart_edit=edit_chart(body,operation)
        except ValueError:raise HTTPException(422,'Check the chart metric, grouping and pie single-series requirements') from None
    append=re.match(r'(?is)^(?:append|add)(?:\s+(?:this|a paragraph|a line|text))?(?:\s*:\s*|\s+)(.+)',operation)
    rename=re.match(r'(?is)^(?:rename(?:\s+it)?\s+(?:to\s+)?|change (?:the )?title to\s+)(.+)',operation)
    if body['kind'] in ('presentation','dashboard') and re.match(r'(?i)^rename (?:slide|panel)\b',operation):rename=None
    replace=re.match(r'(?is)^(?:replace (?:the )?content(?:\s+with)?|set (?:the )?content(?:\s+to)?)\s*:\s*(.+)',operation)
    if chart_edit is not None:body=chart_edit
    elif body['kind']=='presentation' and not rename:
        from app.ai_operator.artifact_slides import edit as edit_slides
        revised=edit_slides(body['slides'],operation)
        if revised is None:
            return Plan(summary='I need a precise slide edit.',question='Use add slide: Title | Point, replace slide 2: Title | Point, rename slide 2 to Title, remove slide 2, move slide 2 to 1, or add point to slide 2: text. Connected intelligence supports broader rewrites.',steps=[])
        body['slides']=revised
    elif body['kind']=='table' and re.match(r'(?i)^add (?:a )?row\s*:',operation):
        body['rows'].append(next(csv.reader([operation.partition(':')[2].strip()],skipinitialspace=True)))
    elif rename:body['title']=rename[1].strip().strip('"\'')
    elif append and body['kind']!='table':body['content']+='\n\n'+append[1].strip()
    elif replace and body['kind']!='table':body['content']=replace[1].strip()
    elif body['kind']!='table' and re.fullmatch(r'(?i)(?:shorten(?: it| this| the artifact)?|make (?:it|this|the artifact) shorter)[.! ]*',operation):
        from app.ai_operator.local_writing import draft as write
        body['content']=write('shorten',body['content'])['text']
    elif re.match(r'(?i)^(?:edit|update|revise|rewrite|shorten|make|remove|replace|add|append|rename)\b',text):
        return Plan(summary='I need a precise artifact edit.',question='For local editing use append: text, replace content: text, rename to Title, make it shorter, or add row: comma-separated values. Connected intelligence supports broader rewrites.',steps=[])
    else:return None
    try:Body.model_validate({k:v for k,v in body.items() if k in Body.model_fields})
    except ValueError:raise HTTPException(422,'Artifact edit exceeds limits or its row does not match the columns') from None
    if draft:tool=draft['tool']
    else:
        tool=f'{prefix}.edit_artifact';body.update(artifact_id=context['id'],expected_revision=context['current_revision'])
    return Plan(summary='Review the complete revised artifact before saving a new server version.',steps=[Step(tool=tool,payload=body)])
