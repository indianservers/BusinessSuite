"""Reviewed native form drafts and explicit versioned publication controls."""
import json
import re
from copy import deepcopy
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field,create_model
from app.core.deps import get_db,get_current_user
from app.forms import router as native
from app.forms.settings import FormDefinition
from app.forms.models import SuiteForm
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest


class Create(FormDefinition):pass


class Edit(Create):
    form_id:int=Field(gt=0,strict=True)
    expected_revision:int=Field(ge=1,strict=True)
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class Transition(Strict):
    form_id:int=Field(gt=0,strict=True)
    expected_revision:int=Field(ge=1,strict=True)
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


MODELS={'create':Create,'edit':Edit,'publish':Transition,'close':Transition}
ACTIONS={m+'.'+action+'_form' for m in ('crm','pms','hrms') for action in MODELS}
router=APIRouter(tags=['Reviewed native forms'],dependencies=[Depends(native.no_store)])


def definition(row):return FormDefinition.model_validate(row.draft).model_dump(mode='json')


def state(row):
    return {'id':row.id,'owner_id':row.owner_id,'organization_id':row.organization_id,'module_key':row.module_key,
        'workspace_id':row.workspace_id,'legacy_entry_id':row.legacy_entry_id,'draft':definition(row),
        'published':FormDefinition.model_validate(row.published).model_dump(mode='json') if row.published else None,
        'revision':row.revision,'version':row.version,'open':row.open,'slug':row.slug}


def access(db,user,module):
    from app.shared.record_360 import module_access
    native.module(module,db,native.org(user));module_access(db,user,{'pms':'project_management'}.get(module,module))


def owned(db,user,module,ident):
    access(db,user,module);row=native.owned(db,ident,user)
    if row.module_key!=module:raise HTTPException(404,'Form not found in this module')
    return row


def read(db,user,module,ident):
    row=owned(db,user,module,ident);draft=definition(row)
    return {'id':row.id,'module':module.upper(),'definition':draft,'revision':row.revision,'source_sha256':digest(draft),
        'published_version':row.version,'open':row.open,'published':row.published is not None,
        'draft_audience':'Public link' if draft['settings']['public'] else 'Authorized legacy workspace members' if row.workspace_id and row.legacy_entry_id else 'Owner only'}


def listing(db,user,module):
    access(db,user,module)
    # Read existing owned forms only; do not trigger native legacy migration on a GET.
    rows=db.query(SuiteForm).filter_by(organization_id=native.org(user),module_key=module,owner_id=user.id).order_by(SuiteForm.id.desc()).limit(100).all()
    return {'items':[{'id':row.id,'name':row.name,'revision':row.revision,'published_version':row.version,'open':row.open} for row in rows],
        'limit':100,'note':'Owned existing forms. Read a selected form for its complete draft; no responses, uploads or public tokens are included.'}


def operation(step):return step.tool.split('.')[1].removesuffix('_form')


def checkpoint(run,step):
    value=(run.result or {}).get('form_checkpoint') or {}
    return value if value.get('step')==run.active_step and value.get('tool')==step.tool and value.get('payload_hash')==digest(step.payload) else None


def payload_definition(value):return FormDefinition.model_validate(value.model_dump(exclude={'form_id','expected_revision','source_sha256'}))


def preflight(db,user,run,step):
    module=step.tool.split('.')[0];access(db,user,module);action=operation(step);value=MODELS[action].model_validate(step.payload)
    if action=='create':
        draft=payload_definition(value);native.validate_definition(draft,db,user,module)
        if not checkpoint(run,step) and db.query(SuiteForm).filter_by(owner_id=user.id).count()>=500:raise HTTPException(422,'Limit: 500 forms per owner')
    else:
        row=owned(db,user,module,value.form_id)
        if checkpoint(run,step):return value
        if row.revision!=value.expected_revision or digest(definition(row))!=value.source_sha256:raise HTTPException(409,'Form changed; prepare a fresh review')
        draft=payload_definition(value) if action=='edit' else FormDefinition.model_validate(definition(row))
        native.validate_definition(draft,db,user,module)
        if action=='edit' and draft.model_dump(mode='json')==definition(row):raise HTTPException(422,'Choose a form value to change')
        if action=='close' and not row.open:raise HTTPException(422,'This form is already closed')
        if action=='publish':
            if row.open and row.published and FormDefinition.model_validate(row.published).model_dump(mode='json')==draft.model_dump(mode='json'):raise HTTPException(422,'This draft is already published and open')
            if draft.settings.closes_at and draft.settings.closes_at<=datetime.now(timezone.utc):raise HTTPException(422,'Choose a future form closing time before publishing')
            if draft.settings.max_responses and native.count(db,row.id)>=draft.settings.max_responses:raise HTTPException(422,'Increase the response limit before publishing')
        if run.workspace_id and row.workspace_id and row.workspace_id!=run.workspace_id:raise HTTPException(403,'Form is outside this conversation workspace')
    if draft.workflow.enabled:
        from app.apps.project_management.access import get_project_for_action
        project=get_project_for_action(db,draft.workflow.project_id,user,'manage_tasks')
        if run.workspace_id and project.workspace_id!=run.workspace_id:raise HTTPException(403,'Form workflow is outside this conversation workspace')
        selected=(run.result or {}).get('request',{}).get('project_id')
        if selected and project.id!=selected:raise HTTPException(403,'Form workflow must retain the selected project')
    return value


def preview(db,user,run,step):
    value=preflight(db,user,run,step);action=operation(step);module=step.tool.split('.')[0]
    row=owned(db,user,module,value.form_id) if action!='create' else None
    before=definition(row) if row else None
    draft=payload_definition(value).model_dump(mode='json') if action in {'create','edit'} else FormDefinition.model_validate(row.published).model_dump(mode='json') if action=='close' and row.published else before
    changes=[]
    if action=='edit':changes=[{'field':key,'before':before[key],'after':item} for key,item in draft.items() if before[key]!=item]
    audience='Anyone with the public link' if draft['settings']['public'] else 'Authorized legacy workspace members' if row and row.workspace_id and row.legacy_entry_id else 'Owner only'
    return {'operation':action,'definition':draft,'audience':audience,'form_id':value.form_id if action!='create' else None,
        'changes':changes,'effect':{'create':'Save a closed, unpublished native draft','edit':'Save a draft revision; the published version stays unchanged',
            'publish':'Publish this exact draft and open intake for the stated audience','close':'Stop accepting new responses; existing responses remain'}[action]}


def confirmed(db,user,run,step):
    value=checkpoint(run,step)
    if not value:return None
    row=owned(db,user,step.tool.split('.')[0],value['receipt']['id'])
    if digest(state(row))!=value['state_hash']:raise HTTPException(409,'Committed form changed; reconcile its recorded receipt')
    return value['receipt']


def register(module,action,Model):
    Approved=create_model(module.title()+action.title()+'ApprovedForm',__base__=Model,suite_run_id=(int,Field(gt=0)),suite_step=(int,Field(ge=1,le=12)))
    @router.post(f'/suite/{module}/forms/{action}-approved')
    def execute(data:Approved,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
        from app.ai_operator.agent_connectors import reviewed_run
        from app.ai_agents.services.audit import AiAuditService
        run,step=reviewed_run(db,user,request,data,Model,action+'_form');value=preflight(db,user,run,step)
        existing=confirmed(db,user,run,step)
        if existing:return existing
        if action=='create':result=native.create_record(native.Create(module_key=module,definition=payload_definition(value)),db,user,commit=False)
        else:
            row=owned(db,user,module,value.form_id)
            draft=payload_definition(value) if action=='edit' else FormDefinition.model_validate(definition(row))
            result=native.save_record(value.form_id,native.Save(revision=value.expected_revision,definition=draft,publish=action=='publish',close=action=='close'),db,user,commit=False)
        row=owned(db,user,module,result['id']);url=f'/{module}/forms/{row.id}/edit'
        if action=='publish':url=f'/f/{row.slug}' if definition(row)['settings']['public'] else f'/{module}/forms/{row.id}/view'
        receipt={'id':row.id,'name':row.name,'form_revision':row.revision,'published_version':row.version,'form_open':row.open,
            'operation':action,'url':url,'form_url':url,'module':module.upper()}
        run.result={**(run.result or {}),'form_checkpoint':{'step':data.suite_step,'tool':step.tool,'payload_hash':digest(step.payload),'state_hash':digest(state(row)),'receipt':receipt}}
        AiAuditService(db).log(user=user,agent_id=None,module=module.upper(),action='suite.form.'+action,input_json={'suite_run_id':run.id,'step':data.suite_step},output_json=receipt,status='success')
        db.commit();return receipt
    if action=='create':
        @router.get(f'/suite/{module}/forms/records')
        def records(db=Depends(get_db),user=Depends(get_current_user)):return listing(db,user,module)
        @router.get(f'/suite/{module}/forms/records/{{ident}}')
        def record(ident:int,db=Depends(get_db),user=Depends(get_current_user)):return read(db,user,module,ident)


for _module in ('crm','pms','hrms'):
    for _action,_model in MODELS.items():register(_module,_action,_model)


def resume_stored(db,user,run,plan_hash):
    from app.ai_operator.suite import Plan,check_tool,finish_step
    from app.ai_operator.saved_agents import enforce
    from app.ai_agents.models import AiActionApproval
    from app.ai_agents.security import verify
    if run.status!='needs_reconciliation' or run.active_step!=len(run.receipts)+1:return False
    step=Plan.model_validate(run.plan).steps[run.active_step-1]
    if step.tool not in ACTIONS:return False
    approval=db.get(AiActionApproval,run.approval_id)
    if run.plan_hash!=plan_hash or digest(run.plan)!=plan_hash or not approval or approval.status!='approved' or approval.approved_by!=user.id:raise HTTPException(409,'Review the unchanged approved form plan')
    verify(db,user,approval.security_context,payload=approval.proposed_action_json,confirmation=True)
    enforce(db,user,run,[step]);check_tool(db,user,run.workspace_id,step,True)
    receipt=confirmed(db,user,run,step)
    if not receipt:raise HTTPException(409,'Form outcome requires reconciliation')
    index=run.active_step;finish_step(db,run,index,step.tool,receipt);run.error_code=None
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module=step.tool.split('.')[0].upper(),action='suite.form.resumed',input_json={'suite_run_id':run.id,'step':index},output_json={'form_id':receipt['id']},status='success')
    db.commit();return True


def validate_plan(db,user,plan):
    seen=set();creates=0
    for step in plan.steps:
        if step.tool not in ACTIONS:continue
        if operation(step)=='create':creates+=1;continue
        ident=step.payload.get('form_id')
        if type(ident) is not int:raise HTTPException(422,'Read the confirmed native form ID before preparing its next action')
        if ident in seen:raise HTTPException(422,'Read the updated form and review its next edit or publication separately')
        seen.add(ident)
    if creates and db.query(SuiteForm).filter_by(owner_id=user.id).count()+creates>500:raise HTTPException(422,'Limit: 500 forms per owner')


def fields_from_text(text,existing=()):
    import csv
    from app.forms.schema import Question
    rows=next(csv.reader([text],strict=True));fields=[];used={field['id'] for field in existing}
    for item in rows:
        match=re.fullmatch(r'\s*(.+?)\s*:\s*([a-z]+)(?:\s*\[([^]]*)\])?(?:\s+(required|optional))?\s*',item)
        if not match:raise ValueError('Use Label:type required, Category:select[Sales|Support]')
        index=1
        while 'q'+str(index) in used:index+=1
        ident='q'+str(index);used.add(ident)
        fields.append(Question(id=ident,label=match[1].strip(),type=match[2],required=match[4]=='required',options=match[3].split('|') if match[3] else []).model_dump(mode='json'))
    return fields


def prepare(db,user,data,parent):
    from app.ai_operator.suite import Plan,Step
    explicit=re.match(r'(?i)^\s*(CRM|PMS|HRMS)\s*:\s*',data.text)
    prior_module=(parent.result or {}).get('request',{}).get('module') if parent else None
    target=(explicit[1] if explicit else data.module or prior_module or 'CRM').lower()
    if target not in {'crm','pms','hrms'}:return None,None
    text=data.text[explicit.end():].strip() if explicit else data.text.strip()
    create=re.fullmatch(r'(?is)(?:please\s+)?(?:create|draft|build)\s+(?:an?\s+)?(?:intake\s+)?form(?:\s+called\s+(.+?))?(?:\s+with\s+(?:fields|questions)\s+(.+))?',text)
    change=re.fullmatch(r'(?is)(edit|update|publish|close)\s+(?:the\s+)?(?:(that|this|saved)\s+)?form(?:\s+(?:called\s+)?([^:]+))?(?::\s*(.*))?',text)
    prior=(parent.result or {}).get('form_draft') if parent and parent.status in {'needs_clarification','awaiting_approval'} else None
    if prior and prior.get('module')!=target:prior=None
    if parent and parent.status=='awaiting_approval':
        steps=(parent.plan or {}).get('steps',[])
        if len(steps)==1 and steps[0]['tool'] in ACTIONS and steps[0]['tool'].startswith(target+'.'):
            prior={'module':target,'action':steps[0]['tool'].split('.')[1].removesuffix('_form'),'payload':deepcopy(steps[0]['payload'])}
    if not create and not change and not prior:return None,None
    pending_selector=change[3].strip().strip('"').lstrip('#') if change and change[3] else None
    pending_target=prior and (not pending_selector or pending_selector==str(prior['payload'].get('form_id')) or pending_selector.casefold()==str(prior['payload'].get('name','')).casefold())
    if change and change[1].lower()=='publish' and prior and prior['action'] in {'create','edit'} and pending_target:
        try:pending=MODELS[prior['action']].model_validate(prior['payload'])
        except ValueError:return Plan(summary='Complete the pending form draft first.',question='Finish the draft questions and review its save before requesting publication.',steps=[]),prior
        return Plan(summary='Review and save the pending form draft first. Publication requires a fresh, separate review of the saved form.',steps=[Step(tool=target+'.'+prior['action']+'_form',payload=pending.model_dump(mode='json'))]),prior
    data.module=target.upper();access(db,user,target)
    if re.fullmatch(r'(?i)(?:cancel|stop|discard)[.! ]*',text):return Plan(summary='Form request cancelled.',steps=[]),None
    packet={'module':target,'action':'create','payload':{'name':create[1].strip() if create and create[1] else '', 'fields':[]}} if create else deepcopy(prior) if not change and prior else {'module':target,'action':'edit' if change[1].lower() in {'edit','update'} else change[1].lower(),'payload':{}}
    payload=packet['payload'];action=packet['action'];values=create[2] if create else change[4] if change else text
    if prior and not create and not change and action in {'create','edit'}:
        if re.fullmatch(r'(?i)(?:review|show review|continue)[.! ]*',text):values=None
        rename=re.fullmatch(r'(?is)rename\s+(?:the\s+)?form\s+to\s+(.+)',text)
        public=re.fullmatch(r'(?i)make\s+(?:the\s+)?(?:form|it)\s+(public|private)',text)
        required=re.fullmatch(r'(?is)make\s+(.+?)\s+(required|optional)',text)
        add=re.fullmatch(r'(?is)add\s+(?:an?\s+)?(?:(required|optional)\s+)?(text|email|phone|url|number|date|textarea|checkbox|rating|file)\s+(?:field|question)\s+(?:called\s+|named\s+)?(.+)',text)
        label=re.fullmatch(r'(?is)rename\s+(?:the\s+)?(?:field|question)\s+(.+?)\s+to\s+(.+)',text)
        if rename:values='name='+rename[1]
        elif public:values='public='+str(public[1].lower()=='public').lower()
        elif add:
            import csv,io
            buffer=io.StringIO();csv.writer(buffer).writerow([add[3]+':'+add[2].lower()+(' required' if add[1] and add[1].lower()=='required' else '')])
            values='add='+buffer.getvalue().strip()
        elif required or label:
            selector=(required[1] if required else label[1]).strip().strip('"')
            exact=[field for field in payload.get('fields',[]) if field['id']==selector]
            matches=exact or [field for field in payload.get('fields',[]) if field['label'].casefold()==selector.casefold()]
            if len(matches)!=1:return Plan(summary='Choose one question.',question='That question is missing or ambiguous. Use its preview ID: required=q1:true or label=q1:Full name.',steps=[]),packet
            values=('required='+matches[0]['id']+':'+str(required[2].lower()=='required').lower()) if required else 'label='+matches[0]['id']+':'+label[2]
        elif action=='create' and not payload.get('fields') and '=' not in text and re.search(r':[a-z]+',text):values='fields='+text
    try:
        if create and values:payload['fields']=fields_from_text(values);values=None
        if action!='create':
            selector=change[3].strip().strip('"') if change and change[3] else None
            selector_is_name=bool(change and re.search(r'(?i)\bform\s+called\s+',text))
            if selector and not selector_is_name:selector=selector.lstrip('#')
            parts=[]
            for part in (values or '').split(';'):
                key,sep,item=part.strip().partition('=')
                if sep and key.strip()=='form':
                    selector_is_name=item.strip().startswith('"') and item.strip().endswith('"')
                    selector=item.strip().strip('"')
                    if not selector_is_name:selector=selector.lstrip('#')
                elif part.strip():parts.append(part)
            values=';'.join(parts) or None
            if change or selector or not payload.get('form_id'):
                ident=int(selector) if selector and not selector_is_name and re.fullmatch(r'[1-9]\d{0,9}',selector) else None
                if selector and ident is None:
                    matches=[row for row in listing(db,user,target)['items'] if row['name'].casefold()==selector.casefold()]
                    if len(matches)==1:ident=matches[0]['id']
                if ident is None and not selector and parent and parent.status=='succeeded':
                    receipts=[receipt for receipt in parent.receipts or [] if receipt.get('status')=='succeeded' and receipt.get('tool') in ACTIONS and receipt['tool'].startswith(target+'.')]
                    if receipts:ident=receipts[-1]['record_id']
                if ident is None:
                    packet['pending_fields']=values or packet.get('pending_fields','')
                    return Plan(summary='Choose an authorized form.',question='Which form? Reply form=ID. Duplicate names require an ID; proposed field changes are retained.',steps=[]),packet
                try:source=read(db,user,target,ident)
                except HTTPException as exc:
                    if exc.status_code!=404:raise
                    packet['pending_fields']=values or packet.get('pending_fields','')
                    return Plan(summary='Choose an available form.',question='That form is unavailable in your current module and company. Reply form=ID.',steps=[]),packet
                # Selecting a different existing target starts from its own complete
                # definition, never from the previous form's unapproved fields.
                pending=packet.pop('pending_fields','') if not payload.get('form_id') else ''
                values=';'.join(part for part in (pending,values) if part) or None
                packet['payload']={'form_id':ident,'expected_revision':source['revision'],'source_sha256':source['source_sha256']}
                if action=='edit':packet['payload']={**source['definition'],**packet['payload']}
                payload=packet['payload']
                if action=='close' and not source['open']:return Plan(summary='This form is already closed. No form was changed.',steps=[]),None
        if values:
            if action in {'publish','close'}:
                if not re.fullmatch(r'(?i)(?:review|show review)[.! ]*',values):return Plan(summary='Review the exact saved draft.',question='Use the action review to approve publication or closure. To change fields or audience, edit the draft first, then request publication again.',steps=[]),packet
            else:
                for part in values.split(';'):
                    key,sep,value=part.strip().partition('=');key=key.strip();value=value.strip()
                    if not sep:raise ValueError('Use name=...; description=...; fields=Name:text required, Email:email; add=Phone:phone; label=q1:Full name; required=q1:true; public=true.')
                    if key in {'name','description','submit_label','success_message','accent'}:payload[key]=value
                    elif key=='fields':payload['fields']=fields_from_text(value)
                    elif key=='add':payload['fields']=[*payload.get('fields',[]),*fields_from_text(value,payload.get('fields',[]))]
                    elif key in {'label','required','options','remove'}:
                        ident,_,answer=value.partition(':');field=next((field for field in payload.get('fields',[]) if field['id']==ident),None)
                        if not field:raise ValueError('Choose an existing question ID from the preview')
                        if key=='remove':payload['fields']=[field for field in payload['fields'] if field['id']!=ident]
                        elif key=='required':
                            if answer.lower() not in {'true','false'}:raise ValueError('Use required=q1:true or required=q1:false')
                            field['required']=answer.lower()=='true'
                        elif key=='options':field['options']=answer.split('|')
                        else:field['label']=answer
                    elif key in {'public','workflow'}:
                        if value.lower() not in {'true','false'}:raise ValueError('Use true or false')
                        payload.setdefault('settings' if key=='public' else 'workflow',{})['public' if key=='public' else 'enabled']=value.lower()=='true'
                    elif key in {'project','assignee','due_days','task_title','task_priority'}:
                        field={'project':'project_id','assignee':'assignee_id','due_days':'due_days','task_title':'title_field','task_priority':'priority'}[key]
                        if key in {'project','assignee','due_days'}:
                            if not re.fullmatch(r'\d{1,10}',value):raise ValueError('Use a numeric project, assignee or due-days value')
                            value=int(value)
                        payload.setdefault('workflow',{})[field]=value
                    else:raise ValueError('Unsupported form field. Use the native question editor for conditions, layout and appearance.')
        if not payload.get('name') and action=='create':raise ValueError('What should the form be called? Reply name=...; fields=Name:text required, Email:email.')
        if not payload.get('fields') and action=='create':raise ValueError('Which questions should this form contain? Reply fields=Name:text required, Email:email.')
        validated=MODELS[action].model_validate(payload)
        if action=='edit' and payload_definition(validated).model_dump(mode='json')==read(db,user,target,validated.form_id)['definition']:
            raise ValueError('What should change? Use name=...; add=Phone:phone; label=q1:Full name; required=q1:true; public=true.')
    except (ValueError,StopIteration) as exc:
        message=str(exc) if not hasattr(exc,'errors') else 'Check the question types, choices, unique IDs, required fields and workflow settings; then supply corrected name=value fields.'
        return Plan(summary='Clarify the form draft.',question=message[:700],steps=[]),packet
    return Plan(summary={'create':'Review this closed, unpublished form draft.','edit':'Review this draft revision. Publication stays separate.','publish':'Review publication of this exact form and its intake audience.','close':'Review closure of form intake. Existing responses remain.'}[action],steps=[Step(tool=target+'.'+action+'_form',payload=validated.model_dump(mode='json'))]),{'module':target,'action':action,'payload':validated.model_dump(mode='json')}
