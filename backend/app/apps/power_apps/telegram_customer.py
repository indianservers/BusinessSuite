"""Fixed customer self-service reads; Telegram never chooses a tenant or customer ID."""
from sqlalchemy import or_
from fastapi import HTTPException
from app.access.service import background_scope
from app.core.deps import RequirePermission

COMMANDS = {'/account', '/orders', '/appointments', '/myrequests'}


def read(db, resource, trigger, owner, thread, linked, command):
    if command not in COMMANDS:
        return None
    if thread.interface != 'public' or not linked or not linked.verified_at or linked.revoked_at:
        return 'Link your customer identity with a one-time verification code before viewing private account information.'
    if command == '/myrequests':
        from app.apps.crm.api import router as crm
        from app.apps.crm.models import CRMTask
        with background_scope(db, owner, 'crm', 'view', branch_id=trigger.config.get('branch_id')):
            crm._assert_entity_permission('tasks', owner, 'view')
            bindings = []
            if linked.contact_id:
                crm._assert_record_visible(db, crm._get_resource('contacts'), linked.contact_id, resource.organization_id, owner)
                bindings.append(CRMTask.contact_id == linked.contact_id)
            if linked.lead_id:
                crm._assert_record_visible(db, crm._get_resource('leads'), linked.lead_id, resource.organization_id, owner)
                bindings.append(CRMTask.lead_id == linked.lead_id)
            if linked.customer_id:
                crm._assert_record_visible(db, crm._get_resource('companies'), linked.customer_id, resource.organization_id, owner)
                bindings.append(CRMTask.company_id == linked.customer_id)
            if not bindings:
                return 'No customer account is linked to this Telegram identity.'
            rows = crm._base_query(db, crm._get_resource('tasks'), resource.organization_id)
            rows = crm._apply_record_visibility(rows, crm._get_resource('tasks'), owner, db).filter(or_(*bindings)).order_by(CRMTask.id.desc()).limit(20).all()
            if not rows:
                return 'No visible requests are linked to your verified customer identity.'
            statuses = {row.id: row.status for row in rows}
            thread.context = {**(thread.context or {}), 'requests': [{**item, 'status': statuses.get(item.get('task_id'), item.get('status'))} for item in (thread.context or {}).get('requests', [])]}
            return '\n'.join(f'#{row.id} · {row.title[:120]} · {row.status}' for row in rows)[:3900]
    if not linked.customer_id:
        return 'These details require a verified customer account link. Ask the company to issue a customer-account linking code.'
    from app.apps.srm.services.commercial import customer
    with background_scope(db, owner, 'srm', 'view', branch_id=trigger.config.get('branch_id')):
        RequirePermission('srm_view', 'srm_manage', 'srm_admin', 'srm_invoice_view')(owner)
        account = customer(db, linked.customer_id, owner)
        if command == '/account':
            return f'Verified customer account: {account.name}'
        if command == '/orders':
            from app.apps.srm.models import SRMSalesOrder
            rows = db.query(SRMSalesOrder).filter(SRMSalesOrder.organization_id == resource.organization_id,
                or_(SRMSalesOrder.customer_id == account.id, SRMSalesOrder.crm_company_id == account.id)).order_by(SRMSalesOrder.id.desc()).limit(20).all()
            return '\n'.join(f'{row.order_number} · {row.status} · {row.currency} {row.total}' for row in rows) or 'No orders are available for your verified customer account.'
        from app.apps.srm.industry_api import context, query
        from app.apps.srm.industry_models import IndustryRecord
        branch = context(db, owner, appointments=True)
        rows = query(db, owner, branch).filter_by(kind='appointment', customer_id=account.id).order_by(IndustryRecord.id.desc()).limit(20).all()
        return '\n'.join(f'Appointment #{row.id} · {row.title[:100]} · {row.status} · {row.starts_at.isoformat() if row.starts_at else ""}' for row in rows) or 'No appointments are available for your verified customer account.'
