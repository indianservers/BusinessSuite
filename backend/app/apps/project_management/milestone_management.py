"""Native milestone edits, optimistic concurrency and project access."""
import hashlib,json
from datetime import date,datetime,timezone
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import ConfigDict,Field,model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from .models import PMSMilestone
from .schemas import PMSMilestoneResponse,PMSMilestoneUpdate
from .access import get_project_for_action
router=APIRouter()

class Edit(PMSMilestoneUpdate):
    model_config=ConfigDict(extra='forbid')
    expected_revision:str=Field(pattern=r'^[a-f0-9]{64}$')
    name:str|None=Field(default=None,min_length=1,max_length=180)
    description:str|None=Field(default=None,max_length=8000)
    status:Literal['Not Started','In Progress','On Hold','Completed','Cancelled']|None=None
    owner_user_id:int|None=Field(default=None,gt=0,le=2147483647,strict=True)
    progress_percent:int|None=Field(default=None,ge=0,le=100,strict=True)

    @model_validator(mode='after')
    def valid(self):
        if 'client_approval_status' in self.model_fields_set:raise ValueError('Use the native client approval workflow')
        if not self.model_fields_set-{'expected_revision'}:raise ValueError('Provide milestone changes')
        if 'name' in self.model_fields_set and (self.name is None or not self.name.strip()):raise ValueError('Milestone name is required')
        if 'status' in self.model_fields_set and self.status is None:raise ValueError('Status cannot be cleared')
        if 'progress_percent' in self.model_fields_set and self.progress_percent is None:raise ValueError('Progress cannot be cleared')
        return self


def selected(db,user,ident,action='browse',lock=False):
    query=db.query(PMSMilestone).filter_by(id=ident)
    row=(query.with_for_update().populate_existing() if lock else query).first()
    if not row:raise HTTPException(404,'Milestone not found')
    project=get_project_for_action(db,row.project_id,user,action)
    return row,project


def view(row):
    value=PMSMilestoneResponse.model_validate(row).model_dump(mode='json')
    return {**value,'revision':hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def changes(record,payload):
    values={key:value for key,value in payload.items() if key!='expected_revision'}
    if record.get('client_approval_status') in {'Pending','Approved'}:
        raise HTTPException(409,'A pending or approved client milestone cannot be edited through this operation')
    if values.get('status')=='Completed':
        if 'progress_percent' in values and values['progress_percent']!=100:raise HTTPException(422,'Completed milestones require 100 percent progress')
        values['progress_percent']=100
    elif 'status' in values and record.get('progress_percent')==100 and 'progress_percent' not in values:
        values['progress_percent']=0
    status=values.get('status',record.get('status'))
    progress=values.get('progress_percent',record.get('progress_percent',0))
    if (status=='Completed')!=(progress==100):raise HTTPException(422,'Completion status and progress must agree')
    start=values.get('start_date',record.get('start_date'));due=values.get('due_date',record.get('due_date'))
    start=date.fromisoformat(start) if isinstance(start,str) else start
    due=date.fromisoformat(due) if isinstance(due,str) else due
    if start and due and start>due:raise HTTPException(422,'Milestone start date must not follow its due date')
    return values


def owner_allowed(db,project,ident):
    if ident is None:return
    from .api.router import _project_user_query
    if not _project_user_query(db,project).filter(User.id==ident,User.is_active.is_(True)).first():
        raise HTTPException(422,'Choose an active eligible project owner')


@router.get('/milestones/{milestone_id}')
def get_milestone(milestone_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row,_=selected(db,user,milestone_id)
    return view(row)


@router.patch('/milestones/{milestone_id}')
def update_milestone(milestone_id:int,data:Edit,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row,project=selected(db,user,milestone_id,'manage_tasks',True)
    before=view(row)
    if data.expected_revision!=before['revision']:raise HTTPException(409,'Milestone changed; read it again before editing')
    values=changes(before,data.model_dump(exclude_unset=True))
    if 'owner_user_id' in values:owner_allowed(db,project,values['owner_user_id'])
    for key,value in values.items():setattr(row,key,value)
    if 'status' in values:row.completed_at=datetime.now(timezone.utc) if values['status']=='Completed' else None
    row.updated_at=datetime.now(timezone.utc)
    db.commit();db.refresh(row)
    return view(row)
