"""Native estimated workload preconditions for reviewed atomic task plans."""
from datetime import date,timedelta
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator

KEY='__workload_guard__'


class WorkloadGuard(BaseModel):
    model_config=ConfigDict(extra='forbid')
    start:date
    weeks:int=Field(default=1,ge=1,le=4,strict=True)
    scope:Literal['project','workspace']='project'
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def bounded(self):
        if self.start.weekday()!=0:raise ValueError('Choose a Monday workload start')
        try:self.start+timedelta(weeks=self.weeks,days=-1)
        except OverflowError:raise ValueError('Choose a supported calendar range') from None
        return self


def issue(pid,start,weeks,scope,native):
    from app.ai_operator.service import digest
    body={'project_id':pid,'start':str(start),'weeks':weeks,'scope':scope,'native':native}
    return {'start':str(start),'weeks':weeks,'scope':scope,'source_sha256':digest(body)}


def current(db,user,pid,value):
    from app.apps.project_management.access import get_project_for_action
    from app.apps.project_management.api.router import get_workload_heatmap
    guard=WorkloadGuard.model_validate(value);project=get_project_for_action(db,pid,user,'browse')
    if guard.scope=='workspace' and not project.workspace_id:raise HTTPException(422,'Workspace workload requires a workspace project')
    native=get_workload_heatmap(projectId=pid if guard.scope=='project' else None,
        workspace_id=project.workspace_id if guard.scope=='workspace' else None,teamId=None,sprintId=None,
        from_date=guard.start,to=guard.start+timedelta(weeks=guard.weeks-1),basis='hours',db=db,current_user=user)
    return issue(pid,guard.start,guard.weeks,guard.scope,native)


def revalidate(db,user,pid,value):
    guard=WorkloadGuard.model_validate(value)
    fresh=current(db,user,pid,guard)
    if fresh['source_sha256']!=guard.source_sha256:raise HTTPException(409,'WORKLOAD_CHANGED')
    return fresh


def check(db,user,run,proposal):
    from app.ai_operator.service import digest
    saved=(run.snapshots or {}).get(KEY)
    sealed=(proposal or {}).get('input',{}).get('workload_guard')
    if saved is None and sealed is None:return
    if saved is None or sealed is None or digest(saved)!=digest(sealed):raise HTTPException(409,'WORKLOAD_GUARD_CHANGED')
    if run.execution_mode!='atomic':raise HTTPException(409,'Guarded workload plans must execute atomically')
    revalidate(db,user,run.project_id,saved)
