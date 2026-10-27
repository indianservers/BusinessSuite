"""Durable reminders run in the existing authenticated scheduler transaction."""
from datetime import datetime, timezone
from fastapi import HTTPException
from app.models.notification import Notification
from app.models.user import User
from app.apps.project_management import chat
from .models import FollowUp, Preference


def should_notify(db, rid, recipient, body):
    from app.apps.project_management.chat_models import ChatMember
    member = db.get(ChatMember,(rid,recipient.id))
    if not member or not member.active or member.muted: return False
    row = db.get(Preference, (rid,recipient.id))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row and (row.mode == "none" or (row.dnd_until and row.dnd_until > now)): return False
    if row and row.mode == "mentions": return ("@" + recipient.email).casefold() in body.casefold()
    return True


def run_reminders(db, limit=100):
    from .api import followup_data
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = db.query(FollowUp).filter(FollowUp.due_at <= now, FollowUp.reminded_at.is_(None), FollowUp.status.notin_(["Completed","Cancelled"])).order_by(FollowUp.due_at).with_for_update(skip_locked=True).limit(limit).all()
    sent=0
    for row in rows:
        recipient = db.get(User,row.assignee_id)
        if not recipient or not recipient.is_active:
            row.reminded_at=now
            continue
        try:
            chat.access(db,row.workspace_id,row.conversation_id,recipient)
            if followup_data(db,row,recipient)["status"] in {"Completed","Cancelled"}:
                row.reminded_at=now
                continue
        except HTTPException as exc:
            if exc.status_code not in {403,404}: raise
            row.reminded_at=now
            continue
        # Conditional claim makes retries harmless, including on SQLite workers.
        changed=db.query(FollowUp).filter_by(id=row.id,reminded_at=None).update({"reminded_at":now},synchronize_session=False)
        if not changed: continue
        if should_notify(db,row.conversation_id,recipient,""):
            db.add(Notification(company_id=chat.organization_id_for(recipient), user_id=recipient.id,title="Follow-up due",message="A follow-up assigned to you is due. Open its authorized conversation to review it.",module="communication",event_type="chat.followup.due",related_entity_type="communication_followup",related_entity_id=row.id,action_url=f"/pms/messages?workspace={row.workspace_id}&conversation={row.conversation_id}&message={row.message_id}"))
            sent+=1
    from datetime import timedelta
    from .models import CommunicationEvent, Presence
    db.query(CommunicationEvent).filter(CommunicationEvent.id.in_(db.query(CommunicationEvent.id).filter(CommunicationEvent.created_at < now-timedelta(days=14)).limit(1000))).delete(synchronize_session=False)
    from sqlalchemy import tuple_
    stale=db.query(Presence.conversation_id,Presence.user_id).filter(Presence.seen_at < now-timedelta(days=1)).limit(1000)
    db.query(Presence).filter(tuple_(Presence.conversation_id,Presence.user_id).in_(stale)).delete(synchronize_session=False)
    db.commit()
    return {"sent":sent}
