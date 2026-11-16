"""Typed private checkout follow-up provenance for native reminder dispatch.

No legacy row is adopted or retagged. Delivery authorization and derivative
birth use the reviewed common delivery lease before this module is wired.
"""
from dataclasses import dataclass
from sqlalchemy import inspect,select
from app.business_packs.models import PackRecordOwnership

class PrivateFollowupUnavailable(ValueError):
    """A private source cannot currently authorize delivery."""

@dataclass(frozen=True)
class PrivateFollowupSource:
    followup_id:int
    company_id:int
    branch_id:int
    context_id:int
    actor_id:int
    recipient_id:int
    order_id:int
    order_line_id:int


def _owner(db,table,identity):
    if identity is None:return None
    anchor=PackRecordOwnership.__table__
    return db.connection().execute(select(anchor).where(anchor.c.resource_table==table,
        anchor.c.resource_key==str(identity))).mappings().one_or_none()


def _identity(owner):
    return owner['company_id'],owner['branch_id'],owner['context_id']


def private_source(db,row):
    """None means genuinely unowned; ambiguous private ancestry fails closed.

    Read actual FK values and immutable ownership independently of a caller's
    cached ORM values. Never discover authority from notes, titles or event keys.
    """
    from app.business_packs.access import _installed
    if not _installed(db):return None
    from app.shared.follow_ups import FollowUp
    from app.apps.srm.models import SRMSalesOrder,SRMSalesOrderLine
    if type(row) is not FollowUp or inspect(row).session is not db or not inspect(row).persistent:
        raise PrivateFollowupUnavailable('Follow-up source is not persistent')
    if inspect(row).modified:
        raise PrivateFollowupUnavailable('Follow-up source has uncommitted changes')
    source=FollowUp.__table__
    actual=db.connection().execute(select(source).where(source.c.id==inspect(row).identity[0])).mappings().one_or_none()
    if actual is None:raise PrivateFollowupUnavailable('Follow-up source is unavailable')
    parent_fields={'order_id':'srm_sales_orders','order_line_id':'srm_sales_order_lines',
        'invoice_id':'srm_invoices','quotation_id':'crm_quotations','lead_id':'crm_leads',
        'contact_id':'crm_contacts','deal_id':'crm_deals'}
    owner=_owner(db,source.name,actual['id'])
    parents={field:_owner(db,table,actual[field]) for field,table in parent_fields.items()}
    if owner is None:
        if any(parents.values()):
            raise PrivateFollowupUnavailable('Unowned follow-up has a private canonical source')
        return None
    if any(actual[field] is not None for field in ('invoice_id','quotation_id','lead_id','contact_id','deal_id')):
        raise PrivateFollowupUnavailable('This private follow-up source graph is not reviewed')
    if (actual['organization_id']!=owner['company_id'] or actual['status'] not in {'Scheduled','Rescheduled'}
            or any(type(actual[field]) is not int or actual[field]<=0 for field in
                   ('id','order_id','order_line_id','created_by','assigned_user_id','customer_id','product_id'))):
        raise PrivateFollowupUnavailable('Private follow-up source identity is unavailable')
    if any(parents[field] is None or _identity(parents[field])!=_identity(owner) for field in ('order_id','order_line_id')):
        raise PrivateFollowupUnavailable('Private follow-up source crosses its exact context')
    order_table,line_table=SRMSalesOrder.__table__,SRMSalesOrderLine.__table__
    order=db.connection().execute(select(order_table).where(order_table.c.id==actual['order_id'])).mappings().one_or_none()
    line=db.connection().execute(select(line_table).where(line_table.c.id==actual['order_line_id'])).mappings().one_or_none()
    if (order is None or line is None or order['organization_id']!=owner['company_id']
            or order['customer_id']!=actual['customer_id'] or order['created_by']!=actual['created_by']
            or order['status']=='cancelled' or line['sales_order_id']!=order['id']
            or line['product_id']!=actual['product_id']):
        raise PrivateFollowupUnavailable('Private follow-up canonical source changed')
    return PrivateFollowupSource(actual['id'],*_identity(owner),actual['created_by'],
        actual['assigned_user_id'],order['id'],line['id'])


def _defer(db,row,key,now,reason,proof=None):
    import logging
    from app.shared.follow_ups import FollowUpReminder
    receipt=db.query(FollowUpReminder).filter_by(follow_up_id=row.id,schedule_key=key).one_or_none()
    if receipt is not None and not inspect(receipt).modified and receipt.delivery_status!='delivered' and proof is not None:
        owner=_owner(db,FollowUpReminder.__tablename__,receipt.id)
        if owner is not None and _identity(owner)==(proof.company_id,proof.branch_id,proof.context_id):
            receipt.delivery_status='deferred'
            receipt.next_attempt_at=None
            receipt.attempt_history=[*(receipt.attempt_history or []),{'at':now.isoformat(),'status':'deferred','error':'Private source authorization unavailable'}]
    logging.getLogger(__name__).info('private_followup_deferred',extra={
        'followup_id':row.id,'delivery_state':'deferred','reason':reason})


def dispatch_private_followup(db,row,*,now,phase):
    """Handle private sources atomically; False preserves genuinely legacy work.

    Revoked first attempts create no derivative at all. Existing source-owned
    reminder intents remain recoverable after the exact authority is restored.
    The caller owns the outer transaction and its final commit.
    """
    from datetime import timedelta
    from fastapi import HTTPException
    from app.shared.follow_ups import FollowUpReminder,FollowUpPreference,utc
    from app.models.notification import Notification,NotificationDeliveryLog
    try:
        proof=private_source(db,row)
    except PrivateFollowupUnavailable:
        _defer(db,row,f'{utc(row.due_at).isoformat()}:{row.assigned_user_id}:{phase}',now,'private_source_unavailable')
        return True
    if proof is None:return False
    # The worker may have loaded this row before a concurrent native reassignment.
    # Never send cached recipient, notes or due-time values after fresh proof.
    db.refresh(row)
    try:
        proof=private_source(db,row)
        if proof is None:raise PrivateFollowupUnavailable('Private source lost its retained provenance')
    except PrivateFollowupUnavailable:
        _defer(db,row,f'{utc(row.due_at).isoformat()}:{row.assigned_user_id}:{phase}',now,'private_source_changed')
        return True
    due=utc(row.due_at)
    lead=row.configuration.get('reminder_minutes')
    if lead is None:lead=row.configuration.get('reminder_days',2)*1440
    if now<due-timedelta(minutes=lead):return True
    phase='overdue' if now>due else 'reminder'
    key=f'{due.isoformat()}:{proof.recipient_id}:{phase}'
    preference=db.query(FollowUpPreference).filter_by(organization_id=proof.company_id,user_id=proof.recipient_id).one_or_none()
    if preference and (not preference.in_app or (phase=='overdue' and not preference.overdue)):return True
    receipt=db.query(FollowUpReminder).filter_by(follow_up_id=proof.followup_id,schedule_key=key).one_or_none()
    if receipt is not None:
        if inspect(receipt).modified:
            _defer(db,row,key,now,'private_reminder_has_uncommitted_changes')
            return True
        db.refresh(receipt)
        owner=_owner(db,FollowUpReminder.__tablename__,receipt.id)
        if owner is None or _identity(owner)!=(proof.company_id,proof.branch_id,proof.context_id):
            _defer(db,row,key,now,'historical_private_reminder_uncertified',proof)
            return True
        if receipt.delivery_status=='delivered' or (receipt.next_attempt_at and utc(receipt.next_attempt_at)>now):return True
        if receipt.notification_id is not None:
            _defer(db,row,key,now,'existing_notification_requires_reconciliation',proof)
            return True
    from app.business_packs.delivery_sources import authorize_source_delivery,certify_notification,certify_followup_reminder,bind_followup_retry
    try:
        authority=authorize_source_delivery(db,row,recipient_user_id=proof.recipient_id,
            company_id=proof.company_id,branch_id=proof.branch_id)
        if authority is None:raise PrivateFollowupUnavailable('Private source lost delivery authority')
        with db.begin_nested():
            if receipt is None:
                receipt=FollowUpReminder(follow_up_id=proof.followup_id,schedule_key=key,
                    delivery_status='pending',attempt_history=[],sent_at=now)
            notification=Notification(company_id=proof.company_id,user_id=proof.recipient_id,
                title=f'Follow-up {phase}: {row.title}',message=f"Due {due.isoformat()} \u00b7 {row.configuration.get('notes','')}",
                module='crm',event_type='service_follow_up',related_entity_type='follow_up',
                related_entity_id=proof.followup_id,action_url=f'/crm/follow-ups/{proof.followup_id}',
                priority=row.priority.lower(),channels=['in_app'])
            delivery=NotificationDeliveryLog(channel='in_app',status='delivered',delivered_at=now)
            notification.delivery_logs=[delivery]
            new_reminder=inspect(receipt).transient
            db.add(notification)
            if new_reminder:db.add(receipt)
            _remember_birth(db,authority,row,proof,now,phase,notification,delivery,receipt,new_reminder)
            certify_notification(db,authority,notification,delivery_log=delivery)
            if new_reminder:
                certify_followup_reminder(db,authority,receipt)
                db.add(receipt)
            else:bind_followup_retry(db,authority,receipt)
            db.add(notification);db.flush()
            receipt.notification_id=notification.id;receipt.delivery_status='delivered'
            receipt.sent_at=now;receipt.next_attempt_at=None
            receipt.attempt_history=[*(receipt.attempt_history or []),{'at':now.isoformat(),'status':'delivered'}]
            db.flush()
    except (HTTPException,PrivateFollowupUnavailable,ValueError):
        _defer(db,row,key,now,'private_delivery_authorization_unavailable',proof)
    except Exception as failure:
        import logging
        logging.getLogger(__name__).error('private_followup_birth_failed',extra={
            'followup_id':proof.followup_id,'error_type':type(failure).__name__})
        _defer(db,row,key,now,'private_delivery_birth_failed',proof)
    return True


@dataclass(frozen=True)
class _BirthPlan:
    authority:object
    source:object
    proof:PrivateFollowupSource
    instant:object
    phase:str
    notification:object
    delivery:object
    reminder:object
    new_reminder:bool
    retry_snapshot:object


def _remember_birth(db,authority,source,proof,instant,phase,notification,delivery,reminder,new_reminder):
    plans=db.info.setdefault('_private_followup_delivery_births',{})
    from copy import deepcopy
    snapshot=None if new_reminder else deepcopy((reminder.delivery_status,reminder.sent_at,reminder.next_attempt_at,reminder.notification_id,list(reminder.attempt_history or [])))
    plan=_BirthPlan(authority,source,proof,instant,phase,notification,delivery,reminder,new_reminder,snapshot)
    plans[id(authority)]=plan
    return plan


def _birth(db,authority):
    plan=db.info.get('_private_followup_delivery_births',{}).get(id(authority))
    if plan is None or plan.authority is not authority:return None
    try:current=private_source(db,plan.source)
    except PrivateFollowupUnavailable:return None
    return plan if current==plan.proof else None


def validate_notification(db,authority,notification,delivery_log=None):
    """Exact fixed native payload; only this worker's actual new instances."""
    from app.models.notification import Notification,NotificationDeliveryLog
    from app.shared.follow_ups import FollowUp,utc
    plan=_birth(db,authority)
    if (plan is None or notification is not plan.notification or delivery_log is not plan.delivery
            or type(notification) is not Notification or type(delivery_log) is not NotificationDeliveryLog):return False
    table=FollowUp.__table__
    row=db.connection().execute(select(table).where(table.c.id==plan.proof.followup_id)).mappings().one_or_none()
    if row is None:return False
    due=utc(row['due_at']);phase='overdue' if plan.instant>due else 'reminder'
    if phase!=plan.phase:return False
    expected={'company_id':plan.proof.company_id,'user_id':plan.proof.recipient_id,
        'title':f"Follow-up {phase}: {row['title']}",
        'message':f"Due {due.isoformat()} \u00b7 {row['configuration'].get('notes','')}",
        'module':'crm','event_type':'service_follow_up','related_entity_type':'follow_up',
        'related_entity_id':plan.proof.followup_id,'action_url':f'/crm/follow-ups/{plan.proof.followup_id}',
        'priority':row['priority'].lower(),'channels':['in_app']}
    if any(getattr(notification,key)!=value for key,value in expected.items()):return False
    if (delivery_log not in notification.delivery_logs or delivery_log.notification is not notification
            or delivery_log.channel!='in_app' or delivery_log.status!='delivered'
            or delivery_log.recipient is not None or delivery_log.provider_message_id is not None
            or delivery_log.error_message is not None or utc(delivery_log.delivered_at)!=plan.instant):return False
    return True


def validate_reminder(db,authority,reminder):
    from app.shared.follow_ups import FollowUpReminder,utc
    plan=_birth(db,authority)
    if plan is None or not plan.new_reminder or type(reminder) is not FollowUpReminder or reminder is not plan.reminder:return False
    key=f'{utc(plan.source.due_at).isoformat()}:{plan.proof.recipient_id}:{plan.phase}'
    if (reminder.follow_up_id!=plan.proof.followup_id or reminder.schedule_key!=key
            or reminder.sent_at is None or utc(reminder.sent_at)!=plan.instant
            or reminder.next_attempt_at is not None):return False
    if reminder.notification_id is None:
        return reminder.delivery_status=='pending' and reminder.attempt_history==[]
    return (plan.notification.id is not None and reminder.notification_id==plan.notification.id
        and reminder.delivery_status=='delivered'
        and reminder.attempt_history==[{'at':plan.instant.isoformat(),'status':'delivered'}])



def validate_retry_reminder(db,authority,reminder):
    from app.shared.follow_ups import FollowUpReminder,utc
    plan=_birth(db,authority)
    if (plan is None or plan.new_reminder or type(reminder) is not FollowUpReminder
            or reminder is not plan.reminder or inspect(reminder).session is not db
            or not inspect(reminder).persistent):return False
    owner=_owner(db,FollowUpReminder.__tablename__,reminder.id)
    if owner is None or _identity(owner)!=(plan.proof.company_id,plan.proof.branch_id,plan.proof.context_id):return False
    key=f'{utc(plan.source.due_at).isoformat()}:{plan.proof.recipient_id}:{plan.phase}'
    if reminder.follow_up_id!=plan.proof.followup_id or reminder.schedule_key!=key:return False
    state=(reminder.delivery_status,reminder.sent_at,reminder.next_attempt_at,reminder.notification_id,list(reminder.attempt_history or []))
    if reminder.notification_id is None:
        return state==plan.retry_snapshot and reminder.delivery_status in {'pending','retry','deferred','blocked'}
    expected_history=[*plan.retry_snapshot[4],{'at':plan.instant.isoformat(),'status':'delivered'}]
    return (plan.notification.id is not None and reminder.notification_id==plan.notification.id
        and reminder.delivery_status=='delivered' and utc(reminder.sent_at)==plan.instant
        and reminder.next_attempt_at is None and reminder.attempt_history==expected_history)


from sqlalchemy import event
from sqlalchemy.orm import Session

@event.listens_for(Session,'after_commit')
def _clear_committed_births(db):
    if not db.in_nested_transaction():db.info.pop('_private_followup_delivery_births',None)

@event.listens_for(Session,'after_soft_rollback')
def _clear_rolled_back_births(db,transaction):
    plans=db.info.get('_private_followup_delivery_births',{})
    for key,plan in list(plans.items()):
        if inspect(plan.notification).session is not db:plans.pop(key,None)
    if not transaction.parent:db.info.pop('_private_followup_delivery_births',None)


def source_allowed(db,certificate,recipient,scope):
    """Fresh canonical source/creator/assigned-recipient check for certificate121."""
    from app.shared.follow_ups import FollowUp
    from app.business_packs.request_operations import FINANCIAL_READ
    if (certificate.source_table!=FollowUp.__tablename__ or not isinstance(certificate.source_key,str)
            or not certificate.source_key.isascii() or not certificate.source_key.isdigit()):return False
    source=db.get(FollowUp,int(certificate.source_key))
    if source is None:return False
    try:proof=private_source(db,source)
    except PrivateFollowupUnavailable:return False
    if (proof is None or (proof.company_id,proof.branch_id,proof.context_id)!=
            (scope.company_id,scope.branch_id,scope.context_id)
            or proof.recipient_id!=certificate.recipient_user_id
            or recipient.id not in {proof.actor_id,proof.recipient_id}):return False
    allowed={value.removeprefix(scope.pack_key+'.') for value in scope.capabilities}
    if not allowed.intersection(FINANCIAL_READ):return False
    # Current native visibility is guaranteed by the actual persisted creator
    # and assigned-user predicates, without a stale cached source or team union.
    from fastapi import HTTPException
    from app.shared.follow_ups import access
    try:access(recipient,db=db)
    except HTTPException:return False
    return True
