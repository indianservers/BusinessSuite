"""Read-only, permission-aware customer plan presentation."""
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy import case, and_
from app.shared import plan_engine as engine


def state_expression():
    from app.shared.plan_models import CustomerPlan as P
    return case(
        (P.status == 'cancelled', 'cancelled'),
        (P.end_date <= date.today(), 'expired'),
        (and_(P.status == 'pending', P.configuration['activation'].as_string() == 'first_use'), 'awaiting_first_use'),
        (P.status == 'pending', 'pending_approval'),
        (and_(P.status == 'active', P.start_date > date.today()), 'scheduled'),
        else_=P.status)


def state(plan):
    if plan.status == 'cancelled': return 'cancelled'
    if plan.end_date and plan.end_date <= date.today(): return 'expired'
    if plan.status == 'pending': return 'awaiting_first_use' if plan.configuration.get('activation') == 'first_use' else 'pending_approval'
    if plan.status == 'active' and plan.start_date > date.today(): return 'scheduled'
    return plan.status


def summary(plan, offering, benefits):
    current = state(plan)
    descriptions = {
        'active':'Access is active, subject to eligibility and remaining benefits.',
        'scheduled':'Access starts on the scheduled start date.',
        'awaiting_first_use':'Waiting for the first eligible use; validity is recalculated when that use is recorded.',
        'pending_approval':'Approval is required. The validity clock continues while approval is pending.',
        'paused':'Access is stopped. The validity clock continues; expiry is unchanged.',
        'suspended':'Access is blocked by an administrative suspension. The validity clock continues.',
        'expired':'The validity period has ended. Renew before using benefits.',
        'cancelled':'Access is cancelled. Remaining balances are retained for history and cannot be used.',
    }
    return {'name':plan.price_snapshot.get('name') or offering.item_name,
        'tier':plan.configuration.get('tier') or '', 'display_status':current,
        'status_description':descriptions.get(current, current),
        'benefit_summary':[{'id':b.id, **b.definition, 'remaining':b.remaining} for b in benefits]}


def actions(plan, can_manage):
    result = {}
    for action in ['activate','pause','resume','suspend','renew','extend','cancel']:
        reason = None
        if not can_manage: reason = 'You have read-only access to this plan.'
        elif state(plan) == 'expired' and action in {'activate','pause','resume','suspend'}: reason = 'Validity has ended. Renew the plan before changing access.'
        elif action in {'renew','extend'} and plan.end_date is None: reason = 'Lifetime plans have no expiry to renew or extend.'
        elif action == 'pause' and not plan.configuration.get('allow_pause', True): reason = 'Pausing is disabled for this plan.'
        elif plan.status == 'cancelled': reason = 'This plan is cancelled. Its history and balances are retained.'
        elif action == 'activate' and plan.status != 'pending': reason = 'Only pending plans need activation.'
        elif action == 'pause' and plan.status != 'active': reason = 'Only active plans can be paused.'
        elif action == 'resume' and plan.status not in {'paused','suspended'}: reason = 'Only paused or suspended plans can resume.'
        elif action == 'suspend' and plan.status != 'active': reason = 'Only active plans can be suspended.'
        else:
            try:
                until = max(plan.end_date or date.today(), date.today()) + timedelta(days=1) if action in {'renew','extend'} else None
                engine.transition_changes(plan, action, until)
            except HTTPException as exc: reason = str(exc.detail)
            except OverflowError: reason = 'No later date is available in the supported calendar.'
        result[action] = {'available':reason is None, 'reason':reason}
    result['change'] = {'available':False, 'reason':'Changing a purchased plan, upgrades, downgrades and proration are not supported. Existing purchase terms are retained.'}
    return result


def history_text(event):
    before, after = event.before or {}, event.after or {}
    if event.action in {'renew','extend'}:
        verb = 'Renewed' if event.action == 'renew' else 'Extended'
        return f"{verb} plan: expiry {before.get('end_date') or 'no expiry'} → {after.get('end_date') or 'no expiry'}"
    return {'issue':'Assigned plan','pause':'Paused access; validity continues','resume':'Resumed access',
        'suspend':'Suspended access; validity continues','cancel':'Cancelled access; history retained',
        'activate':'Activated plan','expire':'Marked plan expired','transfer':'Transferred plan to another customer'}.get(event.action,event.action.replace('_',' ').capitalize())
