"""Least-privilege model discovery; execution still rechecks native permissions."""
from fastapi import HTTPException


def available(db,user,workspace_id,*,module=None,agent_tools=None):
    from app.ai_operator.suite_tools import catalog
    from app.ai_operator.suite import check_tool_access
    allowed=None if agent_tools is None else set(agent_tools)
    result=[]
    for entry in catalog():
        if module and entry['module']!=module:continue
        if allowed is not None and entry['name'] not in allowed:continue
        try:check_tool_access(db,user,workspace_id,entry['name'])
        except HTTPException as exc:
            if exc.status_code not in {403,404,422}:raise
            continue
        result.append(entry)
    return result


def enforce(plan,offered):
    """A provider cannot discover hidden capabilities by proposing their names."""
    allowed={entry['name'] for entry in offered}
    for step in [*plan.steps,*plan.context_requests]:
        if step.tool not in allowed:
            raise HTTPException(422,'Provider selected a tool outside the offered capability catalog')
