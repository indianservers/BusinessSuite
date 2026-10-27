"""Code-owned context adapters. Every access reuses canonical record authorization."""
from fastapi import HTTPException
from app.shared.contracts import RECORDS, RecordContract, register_record
from app.shared.gateway import read_record
from app.apps.project_management.access import organization_id_for

ADAPTERS = {
    ("project_management", "project"): ("/project-management/projects/{id}", "pms_view"),
    ("project_management", "task"): ("/project-management/tasks/{id}", "pms_view"),
    ("crm", "lead"): ("/crm/leads/{id}", "crm_view"),
    ("crm", "deal"): ("/crm/deals/{id}", "crm_view"),
    ("crm", "account"): ("/crm/accounts/{id}", "crm_view"),
    ("srm", "invoice"): ("/srm/invoices/{id}", "srm_view"),
    ("hrms", "employee"): ("/employees/{id}/profile-card", "employee_view"),
}


def resolve(db, user, module, entity, ident):
    key = (module, entity)
    if key not in ADAPTERS:
        raise HTTPException(422, "No approved communication context adapter for this record")
    if key not in RECORDS:
        path, permission = ADAPTERS[key]
        register_record(RecordContract(module, entity, path, permission))
    # read_record invokes the actual native API with the actor's identity and tenant.
    return read_record(db, user, organization_id_for(user), module, entity, ident)


def authorize_contexts(db, user, rid):
    from .models import ConversationContext
    for row in db.query(ConversationContext).filter_by(conversation_id=rid).limit(20):
        resolve(db, user, row.module, row.entity_type, row.entity_id)


def can_view_contexts(db, user, rid):
    try:
        authorize_contexts(db, user, rid)
        return True
    except HTTPException as exc:
        if exc.status_code in {403, 404}: return False
        raise


def denied_rooms(db, user, wid=None):
    from .models import ConversationContext
    from app.apps.project_management.chat_models import ChatMember
    member_rooms = db.query(ChatMember.conversation_id).filter_by(user_id=user.id,active=True)
    query = db.query(ConversationContext.conversation_id).filter(ConversationContext.conversation_id.in_(member_rooms)).distinct()
    if wid is not None: query = query.filter(ConversationContext.workspace_id == wid)
    allowed = [rid for rid, in query.limit(1000) if can_view_contexts(db, user, rid)]
    # Unprocessed contexts fail closed instead of leaking past the scan bound.
    return query.filter(ConversationContext.conversation_id.notin_(allowed))
