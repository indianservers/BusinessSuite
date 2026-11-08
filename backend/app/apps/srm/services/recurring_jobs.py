"""Recurring drafts use the existing owner, company and branch authorization scope."""
import logging
from types import SimpleNamespace
from app.apps.srm.models import SRMBillingPlan
from app.models.user import User
from app.branches.models import BranchOwnership
from app.access.service import background_scope, activate_run_context, release_run_context
from app.apps.srm.access import has_any_permission
from app.shared.models import ServicePolicy

logger = logging.getLogger(__name__)


def dispatch_due(db):
    from app.apps.srm.api.router import process_due_recurring_invoices
    plans = db.query(SRMBillingPlan.id, SRMBillingPlan.created_by, SRMBillingPlan.organization_id).filter(SRMBillingPlan.status == 'active', SRMBillingPlan.recurrence_rule.isnot(None)).order_by(SRMBillingPlan.id).all()
    created = failed = 0
    for plan_id, owner_id, company_id in plans:
        profile = db.query(ServicePolicy).filter_by(scope_key=f"recurring-profile:{company_id or 1}:{plan_id}", organization_id=company_id or 1, kind="recurring_profile").first()
        owner_id = profile.updated_by if profile is not None else owner_id
        actor = db.get(User, owner_id) if owner_id else None
        if not actor or not actor.is_active:
            continue
        owner = db.query(BranchOwnership).filter_by(resource_table='srm_billing_plans', resource_key=str(plan_id), company_id=company_id or 1).first()
        if not owner:
            continue
        try:
            activate_run_context(db, actor, SimpleNamespace(scope_key=f'company:{company_id or 1}'))
            with background_scope(db, actor, 'srm', 'create', branch_id=owner.branch_id):
                from app.apps.srm.services.commercial import lock_tenant
                lock_tenant(db, actor)
                from app.apps.srm.services.recurrence import extend_ongoing_schedule, billing_today
                plan = db.query(SRMBillingPlan).filter_by(id=plan_id, status='active').with_for_update().first()
                if plan is None:
                    continue
                if has_any_permission(actor, {'srm_manage', 'srm_admin'}):
                    extend_ongoing_schedule(db, plan, billing_today(db, actor))
                if has_any_permission(actor, {'srm_invoice_create', 'srm_admin'}):
                    outcome = process_due_recurring_invoices(db=db, current_user=actor, schedule_plan_id=plan_id)
                    created += outcome['created']
                else:
                    db.commit()
        except Exception:
            db.rollback()
            failed += 1
            logger.exception('Recurring invoice plan batch failed')
        finally:
            release_run_context(db)
    return {'created': created, 'failed_owner_batches': failed}
