"""Reviewed module-private views on the existing Suite transaction and checkpoint path."""
from copy import deepcopy
import json
import re
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field,create_model
from app.core.deps import get_db,get_current_user
from app.ai_operator.service import digest
from app.ai_operator.suite_tools import Strict


class ReviewedPrivateView:
    def __init__(self,module,native,path,nouns,example):
        self.module,self.native,self.path,self.nouns,self.example=module,native,path,nouns,example
        ident=(str,Field(pattern=r'^[a-f0-9]{32}$'))
        self.Update=create_model(module+'UpdateView',__base__=native.Edit,view_id=ident,revision=(int,Field(ge=1,strict=True)))
        self.Remove=create_model(module+'RemoveView',__base__=Strict,view_id=ident,revision=(int,Field(ge=1,strict=True)))

    def action(self,step):return step.tool.split('.')[1].removesuffix('_saved_view')
    def model(self,step):return {'create':self.native.Create,'update':self.Update,'remove':self.Remove}[self.action(step)]

    def checkpoint(self,run,step):
        checkpoint=(run.result or {}).get('saved_view_checkpoint') or {}
        valid=checkpoint.get('step')==run.active_step and checkpoint.get('payload_hash')==digest(step.payload)
        valid=valid and checkpoint.get('tool',self.module.lower()+'.create_saved_view')==step.tool
        return checkpoint if valid else None

    def project(self,db,user,step,index,states):
        value=self.model(step).model_validate(step.payload);action=self.action(step)
        if self.module not in states:
            baseline=self.native.listing(db,user)
            states[self.module]={'baseline':baseline,'items':deepcopy(baseline['items']),'offset':0,'previous':None}
        state=states[self.module];baseline=state['baseline'];items=state['items'];before=None
        if action!='create':
            if value.revision!=baseline['revision']:raise HTTPException(422,'Retain the current source collection revision in every view step')
            before=next((view for view in items if view['id']==value.view_id),None)
            if before is None:raise HTTPException(422,'Select a private view that is still present at this step')
        if action!='remove':
            if any(view['name'].casefold()==value.name.casefold() and (action=='create' or view['id']!=value.view_id) for view in items):
                raise HTTPException(422,'Each projected private view must have a unique name')
            if action=='create' and len(items)+baseline['unsupported_views']>=baseline['limit']:raise HTTPException(422,'Remove an unused view before creating another')
        certificate={'tool':step.tool,'payload_hash':digest(step.payload),'base_revision':baseline['revision'],'base_hash':digest(baseline),
            'expected_revision':baseline['revision']+state['offset'],'previous_step':state['previous'],'before_hash':digest(before) if before else None}
        change=self.changes(value,before,action) if before else None
        if state['previous'] is not None and state['previous'] not in step.depends_on:step.depends_on=[*step.depends_on,state['previous']]
        if action=='remove':state['items']=[view for view in items if view['id']!=value.view_id]
        else:
            after={'id':value.view_id if action=='update' else f'created-step:{index}','name':value.name,'filters':value.filters.model_dump()}
            state['items']=[after if action=='update' and view['id']==value.view_id else view for view in items]
            if action=='create':state['items'].append(after)
        state['offset']+=1;state['previous']=index
        return certificate,change

    def certificate(self,db,run,step,index=None):
        projection=(run.snapshots or {}).get('private_views') or {}
        from app.ai_agents.models import AiActionApproval
        approval=db.get(AiActionApproval,run.approval_id) if run.approval_id else None
        sealed=((approval.proposed_action_json or {}).get('input') or {}) if approval else {}
        if not projection and not sealed.get('private_view_projection_hash'):return None
        if sealed.get('private_view_projection_hash')!=digest(projection):raise HTTPException(409,'View projection changed; prepare a fresh review')
        index=index or run.active_step
        if not index:raise HTTPException(409,'View projection step is unavailable')
        value=projection.get(str(index))
        if not value or value.get('tool')!=step.tool or value.get('payload_hash')!=digest(step.payload):raise HTTPException(409,'View projection does not match this approved step')
        return value

    def changes(self,value,before,action):
        if action=='remove':changes=[{'field':'saved_view','before':before['name'],'after':'Removed; business records unchanged'}]
        else:
            changes=[{'field':'name','before':before['name'],'after':value.name}] if before['name']!=value.name else []
            changes.extend({'field':key,'before':old,'after':value.filters.model_dump()[key]} for key,old in before['filters'].items() if old!=value.filters.model_dump()[key])
            if not changes:raise HTTPException(422,'Choose a view value to change')
        return {'record_id':before['id'],'record_name':before['name'],'changes':changes}

    def preflight(self,db,user,run,step,index=None):
        value=self.model(step).model_validate(step.payload);views=self.native.listing(db,user)
        certificate=self.certificate(db,run,step,index)
        if self.checkpoint(run,step):return value
        if certificate:
            if run.status=='awaiting_approval':
                if views['revision']!=certificate['base_revision'] or digest(views)!=certificate['base_hash']:raise HTTPException(409,'Views changed; prepare a fresh review')
                return value
            if views['revision']!=certificate['expected_revision']:raise HTTPException(409,'View collection changed outside the approved chain')
            previous=certificate['previous_step']
            if previous is not None:
                prior=(run.snapshots or {})['private_views'][str(previous)]
                receipt=next((receipt for receipt in run.receipts or [] if receipt['step']==previous and receipt.get('status')=='succeeded'),None)
                if not receipt or receipt.get('tool')!=prior['tool'] or receipt.get('view_revision')!=certificate['expected_revision']:
                    raise HTTPException(409,'The preceding view mutation has no matching native revision receipt')
            if self.action(step)!='create':
                before=next((view for view in views['items'] if view['id']==value.view_id),None)
                if digest(before)!=certificate['before_hash']:raise HTTPException(409,'View target changed outside the approved chain')
                return value.model_copy(update={'revision':certificate['expected_revision']})
            return value
        action=self.action(step)
        if action!='create':
            current=next((view for view in views['items'] if view['id']==value.view_id),None)
            if not current:raise HTTPException(404,'Private saved view not found')
            if views['revision']!=value.revision:raise HTTPException(409,'Views changed; prepare a fresh review')
            if action=='remove':return value
        existing=next((view for view in views['items'] if view['name'].casefold()==value.name.casefold()),None)
        if existing and (action=='create' or existing['id']!=value.view_id):raise HTTPException(409,f'A {self.module} view with that name exists; choose another name')
        if action=='create' and len(views['items'])+views['unsupported_views']>=views['limit']:raise HTTPException(422,'Remove an unused personal view before creating another')
        return value

    def preview(self,db,user,run,step):
        value=self.preflight(db,user,run,step)
        if self.action(step)=='create':return None
        current=next(view for view in self.native.listing(db,user)['items'] if view['id']==value.view_id)
        return self.changes(value,current,self.action(step))

    def confirmed(self,db,user,run,step):
        value=self.preflight(db,user,run,step);checkpoint=self.checkpoint(run,step)
        if not checkpoint:return None
        receipt=checkpoint['receipt'];views=self.native.listing(db,user)
        view=next((view for view in views['items'] if view['id']==receipt.get('id')),None)
        if self.action(step)=='remove':
            if view:raise HTTPException(409,'The removed view is present again; reconcile its recorded receipt')
        elif not view or view['name']!=value.name or view['filters']!=value.filters.model_dump():raise HTTPException(409,f'The committed {self.module} view changed; reconcile its recorded receipt')
        return receipt

    def router(self):
        router=APIRouter(prefix=f'/suite/{self.module.lower()}/views',tags=['Reviewed private views'])
        def register(action,Model):
            Approved=create_model(self.module+action.title()+'ApprovedView',__base__=Model,suite_run_id=(int,Field(gt=0)),suite_step=(int,Field(ge=1,le=12)))
            @router.post('/'+action+'-approved')
            def execute(data:Approved,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
                from app.ai_operator.agent_connectors import reviewed_run
                from app.ai_agents.services.audit import AiAuditService
                run,step=reviewed_run(db,user,request,data,Model,action+'_saved_view');value=self.preflight(db,user,run,step)
                previous=self.confirmed(db,user,run,step)
                if previous:return previous
                if action=='create':
                    certificate=self.certificate(db,run,step)
                    view=self.native.create_record(db,user,value,commit=False,expected_revision=certificate['expected_revision'] if certificate else None)
                else:
                    old=next(view for view in self.native.listing(db,user)['items'] if view['id']==value.view_id)
                    if action=='update':
                        self.native.store.edit_record(db,user,value.view_id,value,commit=False)
                        view={'id':value.view_id,'name':value.name}
                    else:
                        self.native.store.remove_record(db,user,value.view_id,value.revision,commit=False);view=old
                receipt={'view_revision':self.native.listing(db,user)['revision'],'id':view['id'],'name':view['name'],'visibility':'private','operation':action,'url':self.path if action=='remove' else f'{self.path}?view={view["id"]}'}
                run.result={**(run.result or {}),'saved_view_checkpoint':{'step':data.suite_step,'tool':step.tool,'payload_hash':digest(step.payload),'receipt':receipt}}
                AiAuditService(db).log(user=user,agent_id=None,module=self.module,action='suite.saved_view.'+{'create':'created','update':'updated','remove':'removed'}[action],input_json={'suite_run_id':run.id,'step':data.suite_step},output_json=receipt,status='success')
                db.commit();return receipt
        for action,Model in [('create',self.native.Create),('update',self.Update),('remove',self.Remove)]:register(action,Model)
        return router

    def prepare(self,data,parent,db=None,user=None):
        compound=self.prepare_compound(data,parent,db,user)
        if compound is not None:return compound
        change=self.prepare_change(data,parent,db,user)
        if change is not None:return change
        from app.ai_operator.suite import Plan,Step
        text=re.sub(r'(?i)^\s*'+self.module+r'\s*:\s*','',data.text).strip()
        match=re.fullmatch(r'(?is)(?:please\s+)?(?:save|create)\s+(?:a\s+)?(?:saved\s+)?(?:(?:'+self.nouns+r')\s+)?(?:view|filter)\s+called\s+([^:]+)(?::\s*(.*))?',text)
        prior=(parent.result or {}).get('saved_view_draft') if parent and parent.status in {'needs_clarification','awaiting_approval'} else None
        if prior and (prior.get('module')!=self.module or prior.get('_action') or prior.get('_view_chain')):prior=None
        if not prior and parent and parent.status=='awaiting_approval':
            steps=(parent.plan or {}).get('steps',[])
            if len(steps)==1 and steps[0]['tool']==self.module.lower()+'.create_saved_view':prior={**steps[0]['payload'],'module':self.module}
        if not match and not prior:return None,None
        data.module=self.module
        if re.fullmatch(r'(?i)(?:cancel|stop|discard)[.! ]*',text):return Plan(summary=f'{self.module} view request cancelled.',steps=[]),None
        draft={'name':match[1].strip(),'filters':{}} if match else {key:value for key,value in json.loads(json.dumps(prior)).items() if key!='module'}
        values=match[2] if match else text
        if values:
            for part in values.split(';'):
                key,sep,value=part.strip().partition('=');key=key.strip();value=value.strip()
                if not sep or key not in {'name',*self.native.Filters.model_fields}:
                    return Plan(summary=f'Clarify the {self.module} view.',question=self.example,steps=[]),{**draft,'module':self.module}
                if key=='name':draft['name']=value
                elif self.native.Filters.model_fields[key].annotation is bool:
                    if value.lower() not in {'true','false'}:return Plan(summary='Clarify the view filter.',question=f'Use {key}=true or {key}=false.',steps=[]),{**draft,'module':self.module}
                    draft['filters'][key]=value.lower()=='true'
                else:draft['filters'][key]=value
        try:value=self.native.Create.model_validate(draft)
        except ValueError:return Plan(summary=f'Clarify the {self.module} view.',question=self.example,steps=[]),{**draft,'module':self.module}
        return Plan(summary=f'Review this private {self.module} view. Native record permissions still apply. No record, sharing or default setting changes.',
            steps=[Step(tool=self.module.lower()+'.create_saved_view',payload=value.model_dump())]),{**value.model_dump(),'module':self.module}

    def prepare_change(self,data,parent,db,user,views_override=None,selected_view_id=None):
        from app.ai_operator.suite import Plan,Step
        text=re.sub(r'(?i)^\s*'+self.module+r'\s*:\s*','',data.text).strip()
        pattern=r'(?is)(update|edit|remove|delete)\s+(?:the\s+)?(?:(saved|that|this)\s+)?(?:(?:'+self.nouns+r')\s+)?(?:view|filter)(?:\s+(?:called\s+)?([^:]+))?(?::\s*(.*))?'
        match=re.fullmatch(pattern,text)
        rename=re.fullmatch(r'(?is)rename\s+(?:(that|this|saved)\s+)?view(?:\s+called\s+(.+?))?\s+to\s+(.+)',text)
        prior=(parent.result or {}).get('saved_view_draft') if parent and parent.status in {'needs_clarification','awaiting_approval'} else None
        if prior and (prior.get('module')!=self.module or not prior.get('_action')):prior=None
        if not prior and parent and parent.status=='awaiting_approval':
            steps=(parent.plan or {}).get('steps',[])
            if len(steps)==1 and steps[0]['tool'] in {self.module.lower()+'.update_saved_view',self.module.lower()+'.remove_saved_view'}:
                prior={**steps[0]['payload'],'module':self.module,'_action':steps[0]['tool'].split('.')[1].removesuffix('_saved_view')}
        if not match and not rename and not prior:return None
        if db is None or user is None:return None
        data.module=self.module
        if re.fullmatch(r'(?i)(?:cancel|stop|discard)[.! ]*',text):return Plan(summary='View change cancelled.',steps=[]),None
        action=('remove' if match and match[1].lower() in {'remove','delete'} else 'update') if match or rename else prior['_action']
        draft={'filters':{},'module':self.module,'_action':action} if match or rename else json.loads(json.dumps(prior))
        selector=rename[2] if rename else match[3] if match else None
        values=('name='+rename[3]) if rename else match[4] if match else text
        updates={}
        if values:
            for part in values.split(';'):
                key,sep,value=part.strip().partition('=');key=key.strip();value=value.strip()
                if not sep or key not in {'name','view',*self.native.Filters.model_fields} or action=='remove' and key!='view':
                    return Plan(summary='Clarify the saved view change.',question='Select view=NAME or view=ID, then supply name=value filters. Removal changes only the saved view.',steps=[]),draft
                if key=='view':selector=value
                elif key=='name':draft['name']=value;updates['name']=value
                elif self.native.Filters.model_fields[key].annotation is bool:
                    if value.lower() not in {'true','false'}:return Plan(summary='Clarify the filter.',question=f'Use {key}=true or {key}=false.',steps=[]),draft
                    draft.setdefault('filters',{})[key]=value.lower()=='true';updates.setdefault('filters',{})[key]=value.lower()=='true'
                else:draft.setdefault('filters',{})[key]=value;updates.setdefault('filters',{})[key]=value
        views=views_override if views_override is not None else self.native.listing(db,user)
        if selector:
            selector=selector.strip().strip('"').lstrip('#')
            current=next((v for v in views['items'] if v['id']==selector or v['name'].casefold()==selector.casefold()),None)
            if current and current['id']!=draft.get('view_id'):
                if draft.get('view_id'):draft={'module':self.module,'_action':action,**updates}
                draft={**draft,'view_id':current['id'],'revision':views['revision'],'name':draft.get('name',current['name']),'filters':{**current['filters'],**draft.get('filters',{})}}
            elif not current:
                return Plan(summary='Select an available private view.',question='That private view is unavailable. Supply view=NAME or view=ID from your current module.',steps=[]),draft
        if not draft.get('view_id') and not selector and selected_view_id:
            current=next((view for view in views['items'] if view['id']==selected_view_id),None)
            if current:draft={**draft,'view_id':current['id'],'revision':views['revision'],'name':draft.get('name',current['name']),'filters':{**current['filters'],**draft.get('filters',{})}}
        if not draft.get('view_id') and not selector and parent and parent.status=='succeeded':
            receipts=[r for r in parent.receipts or [] if r.get('tool') in {self.module.lower()+'.create_saved_view',self.module.lower()+'.update_saved_view'} and r.get('status')=='succeeded']
            current=next((v for v in views['items'] if receipts and v['id']==receipts[-1].get('record_id')),None)
            if current:draft={**draft,'view_id':current['id'],'revision':views['revision'],'name':draft.get('name',current['name']),'filters':{**current['filters'],**draft.get('filters',{})}}
        if not draft.get('view_id'):
            return Plan(summary='Choose a private saved view.',question='Which private view? Reply view=NAME or view=ID; your proposed changes are retained.',steps=[]),draft
        payload={key:value for key,value in draft.items() if key not in {'module','_action'}}
        if action=='remove':payload={key:value for key,value in payload.items() if key in {'view_id','revision'}}
        try:value=(self.Update if action=='update' else self.Remove).model_validate(payload)
        except ValueError:return Plan(summary='Correct the view change.',question=self.example,steps=[]),draft
        original=next((view for view in views['items'] if view['id']==value.view_id),None)
        if action=='update' and original and original['name']==value.name and original['filters']==value.filters.model_dump():
            return Plan(summary='Choose a view change.',question='Which name or filters should change? '+self.example,steps=[]),draft
        return Plan(summary=f'Review the {action} of this private {self.module} view. Business records and sharing remain unchanged.',steps=[Step(tool=self.module.lower()+'.'+action+'_saved_view',payload=value.model_dump())]),{**value.model_dump(),'module':self.module,'_action':action}

    @staticmethod
    def binding(module):
        if module=='CRM':
            from app.ai_operator.crm_saved_view_actions import service
        else:
            from app.ai_operator.hrms_saved_view_actions import service
        return service

    def prepare_compound(self,data,parent,db,user):
        from app.ai_operator.suite import Plan
        if db is None or user is None:return None
        # Split only complete view-action boundaries outside quoted names.
        text=data.text.strip();parts=[];start=0
        boundary=re.compile(r'(?i)\s+(?:and\s+then|then)\s+(?=(?:(?:CRM|HRMS)\s*:\s*)?(?:update|edit|remove|delete|rename)\s+(?:(?:the|saved|that|this|task|ticket|helpdesk)\s+)*(?:view|filter)\b)')
        for match in boundary.finditer(text):
            quoted=False;escaped=False
            for char in text[:match.start()]:
                if char=='"' and not escaped:quoted=not quoted
                escaped=char=='\\' and not escaped
            if not quoted:parts.append(text[start:match.start()]);start=match.end()
        if parts:parts.append(text[start:])
        if parts and not re.match(r'(?i)^\s*(?:(?:CRM|HRMS)\s*:\s*)?(?:update|edit|remove|delete|rename)\s+(?:(?:the|saved|that|this|task|ticket|helpdesk)\s+)*(?:view|filter)\b',parts[0]):return None
        prior=(parent.result or {}).get('saved_view_draft') if parent and parent.status in {'awaiting_approval','needs_clarification'} else None
        previous=parent.plan if parent and parent.status=='awaiting_approval' else (prior or {}).get('_chain_plan')
        if parent and parent.status=='awaiting_approval' and len((parent.plan or {}).get('steps',[]))>1 and all(step['tool'] in {m+'.'+a+'_saved_view' for m in ('crm','hrms') for a in ('update','remove')} for step in parent.plan['steps']):prior={**(prior or {}),'_view_chain':True}
        original_changes=(parent.result or {}).get('view_changes') if parent else None
        original_changes=original_changes or (prior or {}).get('_chain_changes') or {}
        if not parts and not (prior or {}).get('_view_chain'):return None
        if parts and len(parts)>12:return Plan(summary='Split this view workflow.',question='Prepare at most twelve view changes at a time.',steps=[]),None
        if not parts:
            if re.fullmatch(r'(?i)(?:cancel|stop|discard)[.! ]*',text):return Plan(summary='View workflow cancelled.',steps=[]),None
            # A complete new command deliberately starts a fresh request.
            if re.match(r'(?i)^(?:(?:CRM|HRMS)\s*:\s*)?(?:create|save|update|edit|remove|delete|rename)\b',text):return None
            packet={'module':self.module,'_view_chain':True,'_chain_plan':previous,'_chain_changes':original_changes}
            selected=re.fullmatch(r'(?is)step\s*=\s*([1-9]\d?)\s*;\s*(.+)',text)
            if not selected or not previous:return Plan(summary='Select the workflow step to change.',question='Use step=2; name=...; priority=.... Review is still required.',steps=[]),packet
            plan=Plan.model_validate(deepcopy(previous));index=int(selected[1])
            if index>len(plan.steps):return Plan(summary='Select an existing step.',question=f'Choose step=1 through step={len(plan.steps)}.',steps=[]),packet
            step=plan.steps[index-1];binding=self.binding(step.tool.split('.')[0].upper())
            if binding.action(step)!='update':return Plan(summary='This step removes a view.',question='Cancel the workflow or prepare a new complete request to change its removal target.',steps=[]),packet
            for part in selected[2].split(';'):
                key,sep,value=part.strip().partition('=');key=key.strip();value=value.strip()
                if not sep or key not in {'name',*binding.native.Filters.model_fields}:return Plan(summary='Clarify the step edit.',question=binding.example,steps=[]),packet
                if key=='name':step.payload['name']=value
                else:
                    if binding.native.Filters.model_fields[key].annotation is bool:
                        if value.lower() not in {'true','false'}:return Plan(summary='Clarify the filter.',question=f'Use {key}=true or {key}=false.',steps=[]),packet
                        value=value.lower()=='true'
                    step.payload['filters']={**step.payload['filters'],key:value}
            # Later unchanged fields follow the revised earlier state; explicit
            # later changes remain explicit. The next preflight recalculates all previews.
            states={}
            for n,current in enumerate(plan.steps,1):
                binding=self.binding(current.tool.split('.')[0].upper());module=binding.module
                if module not in states:states[module]=deepcopy(binding.native.listing(db,user)['items'])
                before=next((view for view in states[module] if view['id']==current.payload['view_id']),None)
                if before is None:return Plan(summary='Correct the workflow target.',question='A view is unavailable at this step. Prepare a fresh complete request.',steps=[]),packet
                if binding.action(current)=='update':
                    if n>index:
                        changed={c['field'] for c in original_changes.get(str(n),{}).get('changes',[])}
                        if 'name' not in changed:current.payload['name']=before['name']
                        current.payload['filters']={key:current.payload['filters'][key] if key in changed else value for key,value in before['filters'].items()}
                    after={'id':before['id'],'name':current.payload['name'],'filters':current.payload['filters']}
                    states[module]=[after if view['id']==before['id'] else view for view in states[module]]
                else:states[module]=[view for view in states[module] if view['id']!=before['id']]
            try:
                for current in plan.steps:self.binding(current.tool.split('.')[0].upper()).model(current).model_validate(current.payload)
            except ValueError:return Plan(summary='Correct the selected step.',question=binding.example,steps=[]),packet
            return plan,{'module':self.module,'_view_chain':True,'_chain_plan':plan.model_dump(mode='json')}
        states={};last={};steps=[];active_module=self.module
        for part in parts:
            explicit=re.match(r'(?i)^\s*(CRM|HRMS)\s*:',part);module=explicit[1].upper() if explicit else active_module;active_module=module;binding=self.binding(module)
            if module not in states:states[module]=deepcopy(binding.native.listing(db,user))
            child=data.model_copy(update={'text':part,'module':module})
            result=binding.prepare_change(child,parent,db,user,states[module],last.get(module))
            if result is None or result[0].question or len(result[0].steps)!=1:
                return Plan(summary='Clarify the complete view workflow.',question='Use complete named view changes joined by then. No part is approved or executed. '+(result[0].question if result and result[0].question else ''),steps=[]),None
            step=result[0].steps[0];step.depends_on=[len(steps)] if steps else [];steps.append(step)
            ident=step.payload['view_id']
            if binding.action(step)=='update':
                states[module]['items']=[{'id':ident,'name':step.payload['name'],'filters':step.payload['filters']} if view['id']==ident else view for view in states[module]['items']];last[module]=ident
            else:states[module]['items']=[view for view in states[module]['items'] if view['id']!=ident];last[module]=None
        plan=Plan(summary=f'Review these {len(steps)} dependent private view changes. Business records and sharing are unchanged.',steps=steps)
        return plan,{'module':self.module,'_view_chain':True,'_chain_plan':plan.model_dump(mode='json')}
