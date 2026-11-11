"""One bounded retrieval layer over existing private module and project stores.

    Memory is context, never permissions, business truth or execution consent.
    User memories are company-bound; module memories remain workspace-bound.
"""
from types import SimpleNamespace
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.ai_agents.security import company, verify
from app.ai_operator import suite_memory as store
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_operator.service import scope_key
from app.ai_agents.services.audit import AiAuditService

router=APIRouter(prefix='/suite/memory',tags=['Agent memory'])


class Memory(store.MemoryText):
    level: Literal['user','module','project']='module'
    module: store.Module | None = None
    workspace_id: int | None = Field(default=None,gt=0)
    project_id: int | None = Field(default=None,gt=0)
    revision: int | None = Field(default=None,ge=1)

    @model_validator(mode='after')
    def target(self):
        if self.level=='module' and not self.module:raise ValueError('Choose a module')
        if self.level=='project' and (not self.project_id or self.module not in (None,'PMS')):raise ValueError('Choose a PMS project')
        if self.level!='project' and self.project_id:raise ValueError('Project belongs only to project memory')
        if self.level=='user' and (self.module or self.workspace_id):raise ValueError('User memory applies across modules in this company')
        return self


def authorize(db,user,workspace_id=None,module=None,project_id=None):
    from app.ai_operator.suite import authorize as suite_access, memory_scope
    scope=memory_scope(db,user,workspace_id,module) if module else suite_access(db,user,workspace_id)
    if project_id:
        from app.ai_operator.workbench import access
        project,_=access(db,user,project_id)
        if project.workspace_id!=workspace_id:raise HTTPException(403,'Project must belong to the selected workspace')
    return scope


def normalized(row):
    item=store.public(row)
    return {**item,'key':f'module:{row.id}','level':'user' if item['module']=='USER' else 'module','source':'module-store'}


def collect(db,user,workspace_id=None,module=None,project_id=None,*,bounded=True):
    scope=authorize(db,user,workspace_id,module,project_id)
    result=[normalized(r) for r in store.rows(db,user,scope_key(db,user),'USER',None)[:10 if bounded else 50]]
    if module:
        result.extend(normalized(r) for r in store.rows(db,user,scope,module,workspace_id)[:10 if bounded else 50])
    if project_id:
        from app.ai_operator.workbench import _project_memory_context
        result.extend({**r,'key':f'project:{r["id"]}','level':'project','module':'PMS','project_id':project_id,
                       'workspace_id':workspace_id,'source':'project-store'} for r in _project_memory_context(db,user,project_id,20 if bounded else 250))
    # Project-specific decisions take precedence; original source and scope stay
    # visible. Contradictions at the same level require a user follow-up.
    rank={'project':0,'module':1,'user':2}
    result.sort(key=lambda r:rank[r['level']])
    if not bounded:return result
    total=0; bounded=[]
    for item in result:
        try:store.MemoryText.safe_text(item['text'])
        except ValueError:continue
        if total+len(item['text'])>12000:continue
        bounded.append(item);total+=len(item['text'])
    return bounded


@router.get('')
def listing(workspace_id:int|None=None,module:store.Module|None=None,project_id:int|None=None,
            db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return {'items':collect(db,user,workspace_id,module,project_id,bounded=False),'policy':'Project > module > user. Current explicit requests override preferences. Memory never authorizes actions.'}


@router.post('')
def create(data:Memory,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    scope=authorize(db,user,data.workspace_id,data.module,data.project_id)
    if data.level=='project':
        from app.ai_operator.workbench import ArtifactInput,create_item
        row=create_item(ArtifactInput(project_id=data.project_id,kind='memory',title=data.text[:100],
            payload=data.model_dump(mode='json',include={'text','category','expires_at'})),db,user)
        return {**row,'key':f'project:{row["id"]}','level':'project'}
    values=SimpleNamespace(module=data.module if data.level=='module' else 'USER',workspace_id=data.workspace_id,
                           text=data.text,category=data.category,expires_at=data.expires_at)
    row=store.create(db,user,scope,values)
    audit(db,user,row,'created');db.commit()
    return normalized(row)


def owned(db,user,ident):
    row=db.query(AssistantConversation).filter_by(id=ident,user_id=user.id,organization_id=company(user),deleted_at=None).with_for_update().first()
    if not row or not (row.references or {}).get('suite_memory'):raise HTTPException(404,'Memory not found')
    verify(db,user,row.security_context,history=True)
    module=row.references['module']
    scope=authorize(db,user,row.workspace_id,module if module!='USER' else None)
    if row.references['scope_key']!=scope:raise HTTPException(403,'Memory scope changed')
    return row


def audit(db,user,row,action):
    AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action=f'agent.memory.{action}',
        input_json={'memory_id':row.id},output_json={'revision':row.references.get('revision',1)},status='success')


@router.put('/{kind}/{ident}')
def edit(kind:Literal['module','project'],ident:int,data:Memory,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    authorize(db,user,data.workspace_id,data.module,data.project_id)
    if kind=='project':
        from app.ai_operator.workbench import owned as project_owned,ArtifactInput,edit_item
        old=project_owned(db,user,ident)
        if old.kind!='memory' or data.level!='project':raise HTTPException(404,'Memory not found')
        return edit_item(ident,ArtifactInput(project_id=data.project_id,kind='memory',title=data.text[:100],revision=data.revision,
            payload=data.model_dump(mode='json',include={'text','category','expires_at'})),db,user)
    row=owned(db,user,ident);r=row.references
    if data.revision!=r.get('revision',1):raise HTTPException(409,'Memory changed; reload before editing')
    if data.level!=('user' if r['module']=='USER' else 'module') or data.workspace_id!=row.workspace_id or (data.module or 'USER')!=r['module']:
        raise HTTPException(422,'Memory scope cannot change; create a separate memory')
    row.references={**r,'text':data.text,'category':data.category,'expires_at':data.expires_at.isoformat() if data.expires_at else None,'revision':r.get('revision',1)+1}
    audit(db,user,row,'updated');db.commit();return normalized(row)


@router.delete('/{kind}/{ident}')
def forget(kind:Literal['module','project'],ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if kind=='project':
        from app.ai_operator.workbench import owned as project_owned,delete_item
        if project_owned(db,user,ident).kind!='memory':raise HTTPException(404,'Memory not found')
        return delete_item(ident,db,user)
    row=owned(db,user,ident)
    audit(db,user,row,'forgotten')
    row.references={**row.references,'text':''};row.deleted_at=datetime.now(timezone.utc);db.commit()
    return {'forgotten':True}
