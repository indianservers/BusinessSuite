"""Deduplicated asset reminders using the suite notification and delivery queues."""
from datetime import date, timedelta
from hashlib import sha256
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_
from app.models.asset import Asset, AssetAssignment
from app.models.user import User
from app.models.notification import Notification, NotificationDeliveryLog
from app.shared.models import ServiceEvent, ServicePolicy
from app.schemas.notification import NotificationCreate
from app.services.notifications import NotificationService
from app.services import asset_lifecycle as lifecycle
from app.services.metrics.queries import business_day
from app.apps.srm.services.commercial import tenant
from app.core.masking import user_has_permission


def notify_once(db, user, recipient_id, item, kind, period, title):
    recipient = lifecycle.validate_recipient(db, user, recipient_id)
    # Do not disclose a different branch's asset in a reminder.
    from app.branches.models import BranchOwnership
    from app.branches.service import access
    ownership = db.query(BranchOwnership).filter_by(resource_table="assets", resource_key=str(item.id), company_id=tenant(user)).first()
    if ownership and ownership.branch_id not in access(db, recipient, tenant(user))[0] and not recipient.is_superuser:
        return False
    settings = lifecycle.policy(db, user)
    key = f"asset-reminder:{item.id}:{kind}:{period}:{recipient_id}"
    if db.query(ServiceEvent.id).filter_by(organization_id=tenant(user), request_key=key).first():
        return False
    if kind != "return_requested":
        recent = db.query(ServiceEvent).filter(ServiceEvent.organization_id == tenant(user), ServiceEvent.entity_id == item.id,
            ServiceEvent.entity_type == "asset", ServiceEvent.event_type == "asset."+kind,
            ServiceEvent.created_at > lifecycle.now()-timedelta(days=settings["repeat_days"])).all()
        if any((e.payload_json or {}).get("recipient_id") == recipient_id for e in recent):
            return False
    from app.shared.settings import effective
    allowed = set(effective(db, tenant(user), "hrms")["values"]["notification_channels"])
    channels = [c for c in settings["channels"] if c in allowed or c == "whatsapp"] or ["in_app"]
    from app.models.employee import Employee
    personal = db.query(AssetAssignment.id).filter(AssetAssignment.asset_id == item.id, AssetAssignment.is_active.is_(True), AssetAssignment.employee.has(Employee.user_id == recipient_id)).first() is not None
    action_url = "/hrms/ess" if personal else "/hrms/assets"
    instruction = "Open Employee Self Service and select Assets." if personal else "Review the asset lifecycle workspace."
    try:
        with db.begin_nested():
            event = ServiceEvent(organization_id=tenant(user), module_key="hrms", event_type="asset."+kind,
                entity_type="asset", entity_id=item.id, actor_id=user.id, request_key=key,
                payload_json={"recipient_id": recipient_id}, status="completed")
            db.add(event)
            db.flush()
            NotificationService.create_notification(db, NotificationCreate(company_id=tenant(user), user_id=recipient_id,
                title=title[:200], message=f"{item.name} ({item.asset_tag}) requires attention. {instruction}",
                module="hrms", event_type="asset."+kind, related_entity_type="asset", related_entity_id=item.id,
                action_url=action_url, channels=channels), commit=False)
        return True
    except IntegrityError:
        return False  # Another worker reserved this exact event.


def enqueue_asset_reminders(db, user, *, run_date=None, limit=100):
    if not user.is_superuser and not user_has_permission(user,"asset_manage"):
        raise HTTPException(403,"Current asset management permission is required for reminder processing")
    settings = lifecycle.policy(db, user)
    if not settings["reminders_enabled"]:
        return 0
    today = run_date or business_day(db, user)
    period = str(today.toordinal() // settings["repeat_days"])
    managers = settings["manager_user_ids"] or [user.id]
    queued = 0
    cutoff = today + timedelta(days=settings["reminder_days"])
    candidates = lifecycle.assets(db, user).filter(or_(
        Asset.assignments.any(and_(AssetAssignment.is_active.is_(True), or_(AssetAssignment.acknowledgement_signed.is_(False), AssetAssignment.expected_return_date <= cutoff))),
        Asset.assignments.any(AssetAssignment.inspection_status.in_(["Pending", "Awaiting Approval", "Rejected"])),
        and_(Asset.warranty_expiry >= today, Asset.warranty_expiry <= cutoff),
        Asset.details["insurance_expiry"].as_string() <= cutoff.isoformat(),
        Asset.details["maintenance_due"].as_string() <= cutoff.isoformat(),
        Asset.assignments.any(AssetAssignment.is_active.is_(True)),
    ))
    for item in candidates.order_by(Asset.id).yield_per(100):
        events = []
        rows = db.query(AssetAssignment).filter_by(asset_id=item.id).all()
        for row in rows:
            recipients = [row.employee.user_id] if row.employee.user_id else managers
            if row.is_active:
                if row.expected_return_date and row.expected_return_date < today:
                    events.append(("overdue", f"Overdue asset: {item.asset_tag}", recipients))
                elif row.expected_return_date and row.expected_return_date <= today + timedelta(days=settings["reminder_days"]):
                    events.append(("return_due", f"Asset return due: {item.asset_tag}", recipients))
                if not row.acknowledgement_signed:
                    events.append(("handover_pending", f"Acknowledge asset handover: {item.asset_tag}", recipients))
            elif row.inspection_status in {"Pending", "Awaiting Approval", "Rejected"}:
                events.append(("inspection_pending", f"Asset inspection pending: {item.asset_tag}", managers))
        if item.warranty_expiry and today <= item.warranty_expiry <= today + timedelta(days=settings["reminder_days"]):
            events.append(("warranty_due", f"Warranty expiring: {item.asset_tag}", managers))
        for key, kind, title in [("insurance_expiry", "insurance_due", "Insurance expiring"), ("maintenance_due", "maintenance_due", "Maintenance due")]:
            value = (item.details or {}).get(key)
            if value and date.fromisoformat(value) <= today + timedelta(days=settings["reminder_days"]):
                events.append((kind, f"{title}: {item.asset_tag}", managers))
        from app.models.exit import ExitRecord
        if any(r.is_active and db.query(ExitRecord.id).filter(ExitRecord.employee_id == r.employee_id, ExitRecord.status.in_(["Initiated", "In Progress"])).first() for r in rows):
            events.append(("exit_pending", f"Exit asset clearance awaiting action: {item.asset_tag}", managers))
        for kind, title, recipients in events:
            for recipient in set(recipients):
                if queued >= limit:
                    return queued
                if recipient:
                    queued += notify_once(db, user, recipient, item, kind, period, title)
    return queued


def enqueue_all_asset_reminders(db, limit=100):
    """Existing email worker/cron invokes this; no parallel scheduler is created."""
    from app.access.service import background_scope
    from app.branches.service import access
    queued = 0
    policies = db.query(ServicePolicy).filter_by(module_key="hrms", kind="asset_lifecycle").all()
    for saved in policies:
        actor = db.get(User, saved.updated_by)
        if not actor or not actor.is_active or not (actor.is_superuser or user_has_permission(actor,"asset_manage")) or not saved.values_json.get("reminders_enabled", True):
            continue
        previous = getattr(actor, "organization_id", None)
        actor.organization_id = saved.organization_id
        try:
            for branch in sorted(access(db, actor, saved.organization_id)[0]):
                with background_scope(db, actor, "hrms", action="edit", branch_id=branch):
                    queued += enqueue_asset_reminders(db, actor, limit=max(0, limit-queued))
                    db.commit()
                if queued >= limit:
                    return queued
        except HTTPException:
            db.rollback()  # A revoked policy owner never grants background access.
        finally:
            actor.organization_id = previous
    return queued


def dispatch_asset_whatsapp(db, limit=25):
    """Deliver through the existing consent, template and idempotency controls."""
    from app.services import whatsapp_workspace as wa
    from app.access.service import background_scope
    from app.api.v1.whatsapp_cloud import SendInput
    processed = 0
    pairs = db.query(NotificationDeliveryLog, Notification).join(Notification).filter(
        NotificationDeliveryLog.channel == "whatsapp", NotificationDeliveryLog.status == "queued",
        Notification.event_type.like("asset.%")).order_by(NotificationDeliveryLog.id).limit(limit).all()
    for delivery, notification in pairs:
        saved = db.query(ServicePolicy).filter_by(organization_id=notification.company_id, kind="asset_lifecycle").first()
        actor = db.get(User, saved.updated_by) if saved else None
        if not actor or not actor.is_active:
            delivery.status, delivery.error_message = "suppressed", "Asset reminder policy owner is unavailable"
            db.commit()
            continue
        previous = getattr(actor, "organization_id", None)
        actor.organization_id = notification.company_id
        try:
            from app.branches.models import BranchOwnership
            ownership = db.query(BranchOwnership).filter_by(resource_table="assets", resource_key=str(notification.related_entity_id), company_id=notification.company_id).first()
            with background_scope(db, actor, "hrms", action="edit", branch_id=ownership.branch_id if ownership else None):
                item = lifecycle.asset(db, actor, notification.related_entity_id)
                recipient = lifecycle.validate_recipient(db, actor, notification.user_id)
                from app.common.services.identity import SharedIdentityService
                identity = SharedIdentityService.contact_for_user(db, recipient.id)
                if not identity or not identity.phone_number:
                    raise HTTPException(422, "Recipient has no configured phone")
                message = wa.send_message(db, actor, SendInput(requestId="asset_notice_"+str(notification.id),
                    to=identity.phone_number, body=notification.title, template=saved.values_json.get("whatsapp_template")))
                delivery.status = message.status
                delivery.provider_message_id = message.provider_message_id
        except HTTPException as error:
            delivery.status, delivery.error_message = "suppressed", str(error.detail)[:250]
        finally:
            actor.organization_id = previous
        db.commit()
        processed += 1
    return processed
