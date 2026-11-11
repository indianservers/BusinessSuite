"""Skill testing through canonical conversations, without business execution."""
from fastapi import HTTPException
from app.ai_operator.suite_tools import TOOLS


def skill(db,user,ident,revision):
    from app.ai_operator.saved_agents import owned_skill
    from app.ai_operator.agent_library import validate_origin
    row=owned_skill(db,user,ident);validate_origin(db,user,row)
    if row.references['revision']!=revision:raise HTTPException(409,'Skill changed; start a new test of its current revision')
    return row


def context(db,user,data,parent):
    prior=(parent.result or {}).get('request',{}) if parent else {}
    if prior.get('test_skill_id'):
        if data.agent_id or data.workflow_id or data.test_skill_id and (data.test_skill_id!=prior['test_skill_id'] or data.test_skill_revision!=prior['test_skill_revision']):
            raise HTTPException(409,'Continue testing the original skill, or start a separate conversation')
        data.test_skill_id=prior['test_skill_id'];data.test_skill_revision=prior['test_skill_revision']
    elif parent and data.test_skill_id:raise HTTPException(409,'Start a separate conversation to test a skill')
    if not data.test_skill_id:return None
    from app.ai_operator.saved_agents import Config,access,public_skill
    row=skill(db,user,data.test_skill_id,data.test_skill_revision);value=row.references['config']
    if data.workspace_id!=row.workspace_id:raise HTTPException(403,'Test this skill in its configured workspace')
    modules=sorted({TOOLS[t].module for t in value['tools']})
    if data.module and data.module not in modules:raise HTTPException(403,'Module is outside this skill')
    if not data.module and len(modules)==1:data.module=modules[0]
    config=Config(name=value['name'],instructions=value['instructions'],tools=value['tools'],modules=modules,
        workspace_id=row.workspace_id,project_id=data.project_id,skill_ids=[row.id])
    access(db,user,config)
    return {**config.model_dump(exclude={'revision'}),'id':None,'revision':data.test_skill_revision,'skills':[public_skill(row)],
        'connectors':[],'mcp_tools':[],'test_only':True,'execution_policy':'Testing only. Use authorized reads and propose drafts. No business writes can be approved or executed in this conversation.'}


def enforce(db,user,run,steps):
    request=(run.result or {}).get('request',{})
    if not request.get('test_skill_id'):return False
    row=skill(db,user,request['test_skill_id'],request['test_skill_revision'])
    if row.workspace_id!=run.workspace_id:raise HTTPException(403,'Skill test workspace changed')
    if any(step.tool not in row.references['config']['tools'] for step in steps):raise HTTPException(403,'Tool is outside the tested skill')
    if run.status in ('queued','executing','waiting_pms','paused') and any(TOOLS[step.tool].method!='GET' for step in steps):
        raise HTTPException(403,'Skill tests cannot execute business writes')
    return True
