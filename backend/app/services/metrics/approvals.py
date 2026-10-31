"""Aggregate the complete authorized approval inbox before applying page limits."""
from datetime import datetime,timezone
from sqlalchemy import func,case,literal
from app.models.approval_os import ApprovalRequest
from app.models.workflow_engine import WorkflowTask,WorkflowInstance,WorkflowStepDefinition
from app.schemas.approval_os import ApprovalSummary,ApprovalInboxResponse


def inbox(db,user,scope="mine",status=None,module=None,page=1,per_page=300,include_items=True):
    from app.api.v1.approval_os import _request_query,_workflow_query,_native_item,_workflow_item
    native=_request_query(db,user,scope)
    workflows=_workflow_query(db,user,scope)
    first=native.with_entities(literal("approval").label("source"),ApprovalRequest.id.label("id"),ApprovalRequest.source_module.label("module"),ApprovalRequest.approval_type.label("kind"),ApprovalRequest.status.label("status"),ApprovalRequest.priority.label("priority"),ApprovalRequest.sla_due_at.label("due"),ApprovalRequest.escalated_at.label("escalated"),ApprovalRequest.created_at.label("created"))
    second=workflows.with_entities(literal("workflow").label("source"),WorkflowTask.id.label("id"),func.coalesce(WorkflowInstance.module,"workflow").label("module"),func.coalesce(WorkflowStepDefinition.step_type,"Approval").label("kind"),WorkflowTask.status.label("status"),func.coalesce(WorkflowInstance.context_json["priority"].as_string(),"Normal").label("priority"),WorkflowTask.due_at.label("due"),WorkflowTask.escalated_at.label("escalated"),WorkflowTask.created_at.label("created"))
    rows=first.union_all(second).subquery();visible=db.query(rows)
    if status:visible=visible.filter(func.lower(rows.c.status)==status.lower())
    if module:visible=visible.filter(func.lower(rows.c.module)==module.lower())
    now=datetime.now(timezone.utc);pending=func.lower(rows.c.status)=="pending"
    total,pending_count,overdue,escalated,high=visible.with_entities(func.count(),func.sum(case((pending,1),else_=0)),func.sum(case((pending & (rows.c.due<now),1),else_=0)),func.sum(case((rows.c.escalated.isnot(None),1),else_=0)),func.sum(case((func.lower(rows.c.priority).in_(["high","urgent","critical"]),1),else_=0))).one()
    modules=dict(visible.with_entities(rows.c.module,func.count()).group_by(rows.c.module).all())
    kinds=dict(visible.with_entities(rows.c.kind,func.count()).group_by(rows.c.kind).all())
    summary=ApprovalSummary(total=total,pending=int(pending_count or 0),overdue=int(overdue or 0),escalated=int(escalated or 0),high_priority=int(high or 0),by_module=modules,by_type=kinds)
    items=[]
    if include_items:
        chosen=visible.order_by(func.coalesce(rows.c.due,rows.c.created),rows.c.source,rows.c.id).offset((page-1)*per_page).limit(per_page).all()
        native_ids=[r.id for r in chosen if r.source=="approval"];workflow_ids=[r.id for r in chosen if r.source=="workflow"]
        native_items={r.id:_native_item(r,user) for r in native.filter(ApprovalRequest.id.in_(native_ids)).all()} if native_ids else {}
        workflow_items={task.id:_workflow_item(task,instance,step,user) for task,instance,step in workflows.filter(WorkflowTask.id.in_(workflow_ids)).all()} if workflow_ids else {}
        items=[native_items[r.id] if r.source=="approval" else workflow_items[r.id] for r in chosen]
    return ApprovalInboxResponse(summary=summary,items=items,total=total,page=page,per_page=per_page,pages=(total+per_page-1)//per_page)
