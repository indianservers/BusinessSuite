"""Temporary, explicit selected-pack operation release gate.

This is additive to native authorization and native record boundaries. It does
not enable RuntimeSupport or claim that a pack/module is fully integrated.
Unselected legacy requests keep their native behavior. Selected requests to
unreviewed operational routes fail closed until their native graph is audited.
"""
from dataclasses import dataclass
from types import MappingProxyType

from fastapi import HTTPException
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy import exists, select
from starlette.routing import Match

from .access import PackScope
from .operations import capabilities, for_record_read
from .request_scope import RouteKind, classify_route


FINANCIAL_READ = ('billing.view', 'billing.prepare', 'payments.record', 'checkout.view', 'checkout.create')
PREPARE = ('billing.prepare', 'checkout.create')
SCHEDULE = ('appointments.schedule', 'reservations.schedule')
CONFIGURE = ('settings.manage', 'providers.manage')
OPTIONS = (*SCHEDULE, *PREPARE, *CONFIGURE)
TRANSITION = ('appointments.check_in', 'appointments.cancel', 'appointments.no_show',
              'visits.start', 'visits.complete', 'reservations.schedule', 'boq.approve',
              'variations.approve', 'measurements.certify', 'subcontracts.manage')
GROUP_MONEY = 'Generic financial mutations are not integrated with grouped checkout payment and line mappings; use the native checkout or appointment payment workflow'


@dataclass(frozen=True)
class RequestOperation:
    actions: tuple[str, ...] = ()
    mode: str = 'capability'
    unavailable: str | None = None
    company_admin: bool = False


# Exact server canonical templates, never caller paths, labels or prefixes.
_RULES = {
    ('GET', '/api/v1/srm/industry/workspaces/{workspace_id}/member-options'): RequestOperation(('settings.manage',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/workspaces/{workspace_id}/member-definitions'): RequestOperation(('settings.manage',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/workspace-definitions'): RequestOperation(('settings.manage',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/projects/{project_id}/cost-budget'): RequestOperation(('boq.prepare',), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/projects/{project_id}/commercial-source'): RequestOperation(('billing.view', 'billing.prepare'), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/projects/{project_id}/commercial-source'): RequestOperation(('billing.prepare',), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/projects/{project_id}/resource-options'): RequestOperation(('boq.prepare',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/projects/{project_id}/task-dependencies'): RequestOperation(('boq.prepare',), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/definition-workspaces'): RequestOperation(('settings.manage',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/projects/{project_id}/task-actuals/{task_id}'): RequestOperation(('diary.record',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/projects/{project_id}/cost-actuals'): RequestOperation(('billing.prepare',), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/projects/{project_id}/cost-source'): RequestOperation(('sites.view',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/measurements/{ident}/work-package'): RequestOperation(('measurements.certify',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/site-projects'): RequestOperation(('settings.manage',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/projects/{project_id}/wbs-tasks'): RequestOperation(('boq.prepare',), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/projects/{project_id}/planning-tasks'): RequestOperation(('sites.view',), mode='construction_planning'),
    ('GET', '/api/v1/project-management/projects/{project_id}/schedule-analysis'): RequestOperation(('sites.view',), mode='construction_planning'),
    ('POST', '/api/v1/project-management/projects/{project_id}/schedule-preview'): RequestOperation(('boq.prepare', 'settings.manage'), mode='construction_planning'),
    ('POST', '/api/v1/project-management/projects/{project_id}/schedule-apply'): RequestOperation(('boq.prepare', 'settings.manage'), mode='construction_planning'),
    ('POST', '/api/v1/project-management/projects/{project_id}/schedule-baselines'): RequestOperation(('boq.prepare', 'settings.manage'), mode='construction_planning'),
    ('GET', '/api/v1/project-management/projects/{project_id}/schedule-variance/export'): RequestOperation(('sites.view',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/planning-baselines'): RequestOperation(('boq.prepare',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/planning-baselines/{ident}/review'): RequestOperation(('boq.approve',), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/projects/{project_id}/planning-baselines'): RequestOperation(('sites.view',), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/projects/{project_id}/performance'): RequestOperation(('sites.view',), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/projects/{project_id}/client-report'): RequestOperation(('sites.view',), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/work-packages'): RequestOperation(('sites.view',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/work-packages'): RequestOperation(('boq.prepare',), mode='construction_planning'),
    ('PUT', '/api/v1/srm/industry/work-packages/{ident}'): RequestOperation(('boq.prepare',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/payment-certificates'): RequestOperation(('billing.prepare',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/handovers'): RequestOperation(('diary.record',), mode='construction_planning'),
    ('PUT', '/api/v1/srm/industry/handovers/{ident}'): RequestOperation(('diary.record',), mode='construction_planning'),
    ('POST', '/api/v1/srm/industry/delivery/{ident}/review'): RequestOperation(('boq.approve', 'billing.prepare'), mode='construction_planning'),
    ('GET', '/api/v1/srm/industry/delivery/{ident}/export'): RequestOperation(('sites.view',), mode='construction_planning'),
    ('GET', '/api/v1/project-management/files'): RequestOperation(('sites.view',), mode='construction_documents'),
    ('GET', '/api/v1/project-management/file-folders'): RequestOperation(('sites.view',), mode='construction_documents'),
    ('POST', '/api/v1/project-management/projects/{project_id}/files/upload'): RequestOperation(('diary.record',), mode='construction_documents'),
    ('GET', '/api/v1/project-management/attachments/{file_id}/download'): RequestOperation(('sites.view',), mode='construction_documents'),
    ('GET', '/api/v1/follow-ups/statistics'): RequestOperation(('sites.view', 'reports.view'), mode='construction_statistics'),
    ('GET', '/api/v1/srm/accounts/capabilities'): RequestOperation(mode='native_metadata'),
    ('GET', '/api/v1/srm/accounts/options'): RequestOperation(('engagements.manage',)),
    ('GET', '/api/v1/srm/accounts/periods/{ident}/project-options'): RequestOperation(('engagements.manage',)),
    ('GET', '/api/v1/srm/accounts/periods/{ident}/task-options'): RequestOperation(('documents.request',)),
    ('GET', '/api/v1/srm/accounts/periods/{ident}/delivery'): RequestOperation(('engagements.view','billing.view','billing.prepare','payments.record')),
    ('POST', '/api/v1/srm/accounts/periods/{ident}/invoice'): RequestOperation(('billing.prepare',)),
    ('POST', '/api/v1/srm/accounts/periods/{ident}/payments'): RequestOperation(('payments.record',)),
    ('POST', '/api/v1/srm/accounts/periods/{ident}/time'): RequestOperation(('time.record',)),
    ('POST', '/api/v1/srm/accounts/periods/{ident}/project'): RequestOperation(('engagements.manage',)),
    ('GET', '/api/v1/srm/accounts/periods/{ident}/documents'): RequestOperation(('documents.request','documents.view')),
    ('POST', '/api/v1/srm/accounts/periods/{ident}/documents'): RequestOperation(('documents.request',)),
    ('PUT', '/api/v1/srm/accounts/periods/{ident}/documents/{key}'): RequestOperation(('documents.request',)),
    ('POST', '/api/v1/srm/accounts/periods/{ident}/documents/{key}/upload'): RequestOperation(('documents.request',)),
    ('GET', '/api/v1/srm/accounts/periods/{ident}/documents/{key}/download'): RequestOperation(('documents.request','documents.view')),
    ('GET', '/api/v1/srm/accounts/periods/{ident}/billing'): RequestOperation(('billing.view','billing.prepare','payments.record')),
    ('GET', '/api/v1/srm/accounts/clients'): RequestOperation(('engagements.manage',)),
    ('GET', '/api/v1/srm/accounts/engagements'): RequestOperation(('engagements.view',)),
    ('POST', '/api/v1/srm/accounts/engagements'): RequestOperation(('engagements.manage',)),
    ('GET', '/api/v1/srm/accounts/engagements/{ident}'): RequestOperation(('engagements.view',)),
    ('GET', '/api/v1/srm/accounts/periods'): RequestOperation(('engagements.view','billing.view','billing.prepare','payments.record')),
    ('GET', '/api/v1/srm/accounts/periods/{ident}'): RequestOperation(('engagements.view','billing.view','billing.prepare','payments.record')),
    ('POST', '/api/v1/srm/accounts/periods'): RequestOperation(('engagements.manage',)),
    ('PUT', '/api/v1/srm/accounts/periods/{ident}/assignment'): RequestOperation(('engagements.manage',)),
    ('PUT', '/api/v1/srm/accounts/periods/{ident}/work'): RequestOperation(('work.prepare',)),
    ('POST', '/api/v1/srm/accounts/periods/{ident}/submit'): RequestOperation(('work.prepare',)),
    ('POST', '/api/v1/srm/accounts/periods/{ident}/approve'): RequestOperation(('work.review',)),
    ('POST', '/api/v1/srm/accounts/periods/{ident}/return'): RequestOperation(('work.return',)),
    ('GET', '/api/v1/srm/restaurant/capabilities'): RequestOperation(mode='native_metadata'),
    ('GET', '/api/v1/srm/restaurant/tabs/{order_id}/bills'): RequestOperation(('billing.view', 'payments.record')),
    ('POST', '/api/v1/srm/restaurant/tabs/{order_id}/bills'): RequestOperation(('billing.prepare',)),
    ('GET', '/api/v1/srm/restaurant/tabs/{order_id}/bills/{bill_id}'): RequestOperation(('billing.view', 'payments.record')),
    ('POST', '/api/v1/srm/restaurant/tabs/{order_id}/bills/{bill_id}/payments'): RequestOperation(('payments.record',)),
    ('GET', '/api/v1/srm/restaurant/daily-summary'): RequestOperation(('reports.view',)),
    ('GET', '/api/v1/srm/restaurant/reservations'): RequestOperation(('reservations.schedule',)),
    ('POST', '/api/v1/srm/restaurant/reservations'): RequestOperation(('reservations.schedule',)),
    ('PUT', '/api/v1/srm/restaurant/reservations/{ident}'): RequestOperation(('reservations.schedule',)),
    ('POST', '/api/v1/srm/restaurant/reservations/{ident}/transition'): RequestOperation(('reservations.schedule',)),
    ('POST', '/api/v1/srm/restaurant/tabs/{order_id}/remove-items'): RequestOperation(('orders.create',)),
    ('GET', '/api/v1/srm/restaurant/tables'): RequestOperation(('tables.view', 'tables.manage')),
    ('POST', '/api/v1/srm/restaurant/tables'): RequestOperation(('tables.manage',)),
    ('PUT', '/api/v1/srm/restaurant/tables/{table_id}'): RequestOperation(('tables.manage',)),
    ('POST', '/api/v1/srm/restaurant/paid-orders'): RequestOperation(('orders.create',)),
    ('GET', '/api/v1/srm/restaurant/menu'): RequestOperation(('orders.create',)),
    ('GET', '/api/v1/srm/restaurant/customers'): RequestOperation(('orders.create',)),
    ('GET', '/api/v1/srm/restaurant/registers'): RequestOperation(('billing.prepare', 'payments.record')),
    ('POST', '/api/v1/srm/restaurant/tabs'): RequestOperation(('orders.create',)),
    ('GET', '/api/v1/srm/restaurant/tabs'): RequestOperation(('orders.view', 'orders.create')),
    ('POST', '/api/v1/srm/restaurant/tabs/{order_id}/items'): RequestOperation(('orders.create',)),
    ('POST', '/api/v1/srm/restaurant/tabs/{order_id}/transfer'): RequestOperation(('tables.manage',)),
    ('POST', '/api/v1/srm/restaurant/tabs/{order_id}/customer'): RequestOperation(('orders.create',)),
    ('POST', '/api/v1/srm/restaurant/tabs/{order_id}/anonymous-settlement'): RequestOperation(('billing.prepare',)),
    ('POST', '/api/v1/srm/restaurant/tabs/{order_id}/bill'): RequestOperation(('billing.prepare',)),
    ('GET', '/api/v1/srm/restaurant/tabs/{order_id}/billing'): RequestOperation(('billing.view', 'payments.record')),
    ('POST', '/api/v1/srm/restaurant/tabs/{order_id}/payments'): RequestOperation(('payments.record',)),
    ('GET', '/api/v1/srm/restaurant/paid-orders/{checkout_id}/source'): RequestOperation(('orders.create',)),
    ('GET', '/api/v1/srm/restaurant/orders/{order_id}'): RequestOperation(('orders.view', 'orders.create')),
    ('POST', '/api/v1/srm/restaurant/orders/{order_id}/tickets'): RequestOperation(('orders.create',)),
    ('GET', '/api/v1/srm/restaurant/kitchen'): RequestOperation(('kitchen.view',)),
    ('POST', '/api/v1/srm/restaurant/tickets/{ticket_id}/prepare'): RequestOperation(('kitchen.prepare',)),
    ('POST', '/api/v1/srm/restaurant/tickets/{ticket_id}/ready'): RequestOperation(('kitchen.ready',)),
    ('POST', '/api/v1/srm/restaurant/tickets/{ticket_id}/serve'): RequestOperation(('orders.serve',)),
    ('POST', '/api/v1/srm/pharma/batch-receipts'): RequestOperation(('batches.receive',)),
    ('POST', '/api/v1/srm/pharma/returns'): RequestOperation(('returns.approve','payments.record')),
    ('GET', '/api/v1/srm/pharma/returns/{return_id}'): RequestOperation(('returns.approve',)),
    ('GET', '/api/v1/srm/pharma/returns/requests/{request_key}'): RequestOperation(('returns.approve',)),
    ('GET', '/api/v1/srm/pharma/returns/sales/{checkout_id}/lots'): RequestOperation(('returns.approve',)),
    ('GET', '/api/v1/srm/pharma/options'): RequestOperation(('batches.view',)),
    ('GET', '/api/v1/srm/pharma/batches'): RequestOperation(('batches.view',)),
    ('POST', '/api/v1/srm/pharma/recalls'): RequestOperation(('recalls.manage',)),
    ('POST', '/api/v1/srm/pharma/recalls/{recall_id}/commands'): RequestOperation(('recalls.manage',)),
    ('GET', '/api/v1/srm/pharma/recalls'): RequestOperation(('recalls.manage',)),
    ('GET', '/api/v1/srm/pharma/recalls/{recall_id}'): RequestOperation(('recalls.manage',)),
    ('GET', '/api/v1/srm/retail/stock-receipts'): RequestOperation(('stock.view',)),
    ('POST', '/api/v1/srm/retail/stock-receipts'): RequestOperation(('stock.receive',)),
    ('GET', '/api/v1/srm/retail/stock'): RequestOperation(('stock.view',)),
    ('GET', '/api/v1/srm/retail/reports/daily'): RequestOperation(('reports.view',)),
    ('POST', '/api/v1/srm/retail/returns'): RequestOperation(('returns.approve', 'payments.record')),
    ('GET', '/api/v1/srm/retail/returns/{return_id}'): RequestOperation(('returns.approve', 'payments.record')),
    ('GET', '/api/v1/srm/retail/returns/sales/{checkout_id}'): RequestOperation(('returns.approve', 'payments.record')),
    ('GET', '/api/v1/srm/retail/returns/requests/{request_key}'): RequestOperation(('returns.approve', 'payments.record')),
    ('GET', '/api/v1/catalog/items'): RequestOperation(('catalog.view',)),
    ('GET', '/api/v1/catalog/items/{kind}/{ident}'): RequestOperation(('catalog.view',)),
    ('POST', '/api/v1/catalog/items'): RequestOperation(('catalog.manage',)),
    ('PUT', '/api/v1/catalog/items/{kind}/{ident}'): RequestOperation(('catalog.manage',)),
    ('GET', '/api/v1/srm/pos/catalog'): RequestOperation(('checkout.view','checkout.create','billing.prepare')),
    ('GET', '/api/v1/srm/pos/customer-schema'): RequestOperation(('patients.register','customers.register')),
    ('GET', '/api/v1/srm/pos/customers'): RequestOperation(('checkout.view','checkout.create','billing.prepare')),
    ('GET', '/api/v1/srm/pos/customers/{customer_id}'): RequestOperation(('checkout.view','checkout.create','billing.prepare')),
    ('GET', '/api/v1/srm/pos/customers/{customer_id}/identity'): RequestOperation(('checkout.view','checkout.create','billing.prepare')),
    ('POST', '/api/v1/srm/pos/customers'): RequestOperation(('patients.register','customers.register')),
    ('POST', '/api/v1/srm/service-checkout'): RequestOperation(PREPARE),
    ('GET', '/api/v1/srm/service-checkout/{checkout_id}'): RequestOperation(FINANCIAL_READ),
    ('POST', '/api/v1/srm/service-checkout/{checkout_id}/payments'): RequestOperation(('payments.record',)),
    ('GET', '/api/v1/srm/industry/prebooking-workflows/eligibility/{service_id}/{employee_id}'): RequestOperation(CONFIGURE),
    ('POST', '/api/v1/srm/industry/prebooking-workflows/waitlist'): RequestOperation(SCHEDULE),
    ('GET', '/api/v1/srm/industry/prebooking-workflows/waitlist'): RequestOperation(SCHEDULE),
    ('POST', '/api/v1/srm/industry/prebooking-workflows/waitlist/{ident}/cancel'): RequestOperation(SCHEDULE),
    ('POST', '/api/v1/srm/industry/prebooking-workflows/series/preview'): RequestOperation(SCHEDULE),
    ('POST', '/api/v1/srm/industry/prebooking-workflows/series'): RequestOperation(SCHEDULE),
    ('GET', '/api/v1/srm/industry/prebooking-workflows/requests/{request_id}'): RequestOperation(SCHEDULE),
    ('GET', '/api/v1/srm/industry/prebooking-workflows/appointments/{ident}/summary'): RequestOperation(SCHEDULE),
    ('GET', '/api/v1/srm/industry/appointments/requests/{request_id}'): RequestOperation(SCHEDULE),
    ('GET', '/api/v1/srm/industry/appointments/customer-context/{customer_id}'): RequestOperation(SCHEDULE),
    ('GET', '/api/v1/srm/service-checkout/options'): RequestOperation(OPTIONS),
    ('GET', '/api/v1/srm/service-checkout/options/providers'): RequestOperation(OPTIONS),
    ('GET', '/api/v1/srm/service-checkout/options/availability'): RequestOperation(OPTIONS),
    ('PUT', '/api/v1/srm/service-checkout/policies'): RequestOperation(CONFIGURE),
    ('PUT', '/api/v1/srm/service-checkout/eligibility'): RequestOperation(CONFIGURE),
    ('GET', '/api/v1/srm/service-checkout/appointments/{appointment_id}/schedule'): RequestOperation(SCHEDULE),
    ('POST', '/api/v1/srm/service-checkout/appointments/{appointment_id}/schedule'): RequestOperation(SCHEDULE),
    ('GET', '/api/v1/srm/anonymous-cash/configuration'): RequestOperation((*FINANCIAL_READ, 'settings.manage')),
    ('PUT', '/api/v1/srm/anonymous-cash/configuration'): RequestOperation(CONFIGURE, company_admin=True),
    ('GET', '/api/v1/srm/sales-orders'): RequestOperation(FINANCIAL_READ),
    ('GET', '/api/v1/srm/sales-orders/{sales_order_id}'): RequestOperation(FINANCIAL_READ),
    ('GET', '/api/v1/srm/invoice-drafts'): RequestOperation(FINANCIAL_READ),
    ('GET', '/api/v1/srm/invoices'): RequestOperation(FINANCIAL_READ),
    ('GET', '/api/v1/srm/invoices/{invoice_id}'): RequestOperation(FINANCIAL_READ),
    ('GET', '/api/v1/srm/invoices/{invoice_id}/pdf'): RequestOperation(FINANCIAL_READ),
    ('GET', '/api/v1/srm/business/invoices/{invoice_id}'): RequestOperation(FINANCIAL_READ),
    ('GET', '/api/v1/srm/documents/{kind}/{ident}'): RequestOperation(FINANCIAL_READ, mode='invoice_document'),
    ('GET', '/api/v1/srm/business/collection-invoices'): RequestOperation(FINANCIAL_READ),
    ('POST', '/api/v1/srm/invoices/{invoice_id}/approve'): RequestOperation(PREPARE),
    ('POST', '/api/v1/srm/invoices/{invoice_id}/send'): RequestOperation(PREPARE),
    ('GET', '/api/v1/srm/receipts'): RequestOperation(FINANCIAL_READ),
    ('GET', '/api/v1/srm/receipts/{receipt_id}'): RequestOperation(FINANCIAL_READ),
    ('POST', '/api/v1/srm/receipts'): RequestOperation(('payments.record',), unavailable=GROUP_MONEY),
    ('POST', '/api/v1/srm/receipts/{receipt_id}/confirm'): RequestOperation(('payments.record',), unavailable=GROUP_MONEY),
    ('POST', '/api/v1/srm/receipts/{receipt_id}/allocate'): RequestOperation(('payments.record',), unavailable=GROUP_MONEY),
    ('GET', '/api/v1/srm/pos/sessions'): RequestOperation(FINANCIAL_READ),
    ('GET', '/api/v1/srm/pos/sessions/active'): RequestOperation(FINANCIAL_READ),
    ('POST', '/api/v1/srm/pos/sessions'): RequestOperation((*PREPARE, 'payments.record')),
    ('POST', '/api/v1/srm/pos/cashier-closing'): RequestOperation(('sessions.close',)),
    ('POST', '/api/v1/srm/pos/cash-movements'): RequestOperation(('sessions.close',)),
    ('GET', '/api/v1/srm/industry/capabilities'): RequestOperation(mode='native_metadata'),
    ('GET', '/api/v1/srm/industry/records'): RequestOperation(mode='industry_kind'),
    ('GET', '/api/v1/srm/industry/material-warehouse-options'): RequestOperation(('materials.request',)),
    ('GET', '/api/v1/srm/industry/project-options'): RequestOperation(('sites.view',)),
    ('GET', '/api/v1/srm/industry/staff-options'): RequestOperation((*SCHEDULE, *CONFIGURE)),
    ('GET', '/api/v1/srm/industry/employee-options'): RequestOperation((*SCHEDULE, *CONFIGURE)),
    ('POST', '/api/v1/srm/industry/resources'): RequestOperation(CONFIGURE),
    ('PUT', '/api/v1/srm/industry/resources/{ident}'): RequestOperation(CONFIGURE),
    ('POST', '/api/v1/srm/industry/appointments'): RequestOperation(SCHEDULE),
    ('PUT', '/api/v1/srm/industry/appointments/{ident}/schedule'): RequestOperation(SCHEDULE),
    ('POST', '/api/v1/srm/industry/boq'): RequestOperation(('boq.prepare', 'variations.prepare')),
    ('POST', '/api/v1/srm/industry/measurements'): RequestOperation(('measurements.prepare',)),
    ('POST', '/api/v1/srm/industry/site-diaries'): RequestOperation(('diary.record',)),
    ('POST', '/api/v1/srm/industry/subcontracts'): RequestOperation(('subcontracts.manage',)),
    ('POST', '/api/v1/srm/industry/material-issues'): RequestOperation(('materials.request',)),
    ('POST', '/api/v1/srm/industry/records/{ident}/transition'): RequestOperation(TRANSITION),
    ('POST', '/api/v1/srm/industry/records/{ident}/invoice'): RequestOperation(PREPARE),
    ('POST', '/api/v1/srm/industry/records/{ident}/payments'): RequestOperation(('payments.record',)),
    ('GET', '/api/v1/srm/industry/projects/{project_id}/summary'): RequestOperation(('sites.view',)),
    ('GET', '/api/v1/srm/industry/appointments/{ident}/billing'): RequestOperation(FINANCIAL_READ),
    ('POST', '/api/v1/srm/industry/appointments/{ident}/payments'): RequestOperation(('payments.record',)),
    ('POST', '/api/v1/srm/industry/appointments/{ident}/apply-advances'): RequestOperation(('payments.record',)),
    ('GET', '/api/v1/access/settings/business-profile/effective'): RequestOperation(mode='independent_projection'),
    ('GET', '/api/v1/access/settings/defaults/effective'): RequestOperation(mode='independent_projection'),
    ('GET', '/api/v1/employees/planned-services'): RequestOperation(mode='independent_projection'),
    ('GET', '/api/v1/employees/{employee_id}/planned-services'): RequestOperation(mode='independent_projection'),
}
# Known native mutations remain explicitly unavailable for selected scopes.
# Checking their capability first gives specialists a permission denial, rather
# than implying that enabling a missing integration would grant them access.
for _method, _path in (
    ('POST', '/api/v1/srm/sales-orders'),
    ('PATCH', '/api/v1/srm/sales-orders/{sales_order_id}'),
    ('POST', '/api/v1/srm/sales-orders/{sales_order_id}/lines'),
    ('PATCH', '/api/v1/srm/sales-orders/{sales_order_id}/lines/{line_id}'),
    ('DELETE', '/api/v1/srm/sales-orders/{sales_order_id}/lines/{line_id}'),
    ('POST', '/api/v1/srm/sales-orders/{sales_order_id}/submit'),
    ('POST', '/api/v1/srm/sales-orders/{sales_order_id}/approve'),
    ('POST', '/api/v1/srm/sales-orders/{sales_order_id}/confirm'),
    ('POST', '/api/v1/srm/sales-orders/{sales_order_id}/cancel'),
    ('POST', '/api/v1/srm/sales-orders/{sales_order_id}/close'),
    ('POST', '/api/v1/srm/invoices/draft-from-sales-order/{sales_order_id}'),
    ('POST', '/api/v1/srm/invoices/manual'),
    ('PATCH', '/api/v1/srm/invoices/{invoice_id}'),
    ('POST', '/api/v1/srm/invoices/{invoice_id}/lines'),
    ('POST', '/api/v1/srm/business/invoices/{invoice_id}/cancel'),
    ('PATCH', '/api/v1/srm/business/invoices/{invoice_id}/lines/{line_id}'),
    ('PUT', '/api/v1/srm/business/invoices/{invoice_id}/context'),
):
    _RULES[(_method, _path)] = RequestOperation(PREPARE, unavailable=GROUP_MONEY)
RULES = MappingProxyType(_RULES)
del _RULES, _method, _path


def _unavailable(method, path, reason):
    raise HTTPException(503, {'code': 'business_pack_integration_unavailable',
        'message': 'This operation is not available in the selected Business Pack integration',
        'method': method, 'route': path, 'reason': reason, 'runtime_ready': False})


def _actual_company_admin(db, actor, company_id):
    """Fresh native authority only; a pack manager is never a company admin."""
    from app.models.user import User
    from app.access.models import AccessMembership, AccessPolicy
    user = db.connection().execute(select(User.is_active, User.is_superuser).where(User.id == actor.id)).first()
    if not user or not user.is_active:
        return False
    if user.is_superuser:
        return True
    membership = exists(select(1).where(AccessMembership.user_id == actor.id,
        AccessMembership.company_id == company_id, AccessMembership.active.is_(True), AccessMembership.is_admin.is_(True)))
    suspended = exists(select(1).where(AccessPolicy.user_id == actor.id,
        AccessPolicy.company_id == company_id, AccessPolicy.status != 'active'))
    return bool(db.connection().scalar(select(membership & ~suspended)))


def authorize_request(db, actor, request, scope):
    """Authorize one matched native route without granting any native rights."""
    if scope is None:
        if db.info.get('business_pack_scope') is not None:
            raise HTTPException(403, 'Business Pack request scope cannot be discarded')
        return None
    method = request.method.upper()
    route = request.scope.get('route')
    if not isinstance(route, APIRoute) or not isinstance(route.path, str):
        _unavailable(method, None, 'A matched native canonical route is required')
    # FastAPI lazy includes keep the original child APIRoute in ASGI scope.
    # Resolve its full canonical template from the actual server registry,
    # preserving object identity and matching the framework's effective route.
    # A guessed API prefix or caller-supplied path cannot establish a rule.
    router = getattr(request.scope.get('app'), 'router', None)
    if router is None:
        _unavailable(method, None, 'The matched native route requires its server registry')
    paths = {context.path for context in iter_route_contexts(router.routes)
             if context.original_route is route and method in (context.methods or ())
             and context.matches(request.scope)[0] is Match.FULL}
    if len(paths) != 1:
        _unavailable(method, None, 'The matched native route has no unique canonical server template')
    path = paths.pop()
    if classify_route(method, request.url.path) is not RouteKind.OPERATIONAL:
        return {'method': method, 'route': path, 'adapter': 'native_control', 'runtime_ready': False}
    if not isinstance(scope, PackScope) or db.info.get('business_pack_scope') != scope:
        raise HTTPException(403, 'Business Pack request scope is not the verified bound selection')
    # Fresh actor/grant authority remains mandatory for every operational route,
    # including metadata and independently bounded projections.
    allowed = capabilities(db, actor)
    rule = RULES.get((method, path))
    if rule is None:
        _unavailable(method, path, 'No audited selected-pack operation adapter is registered for this native route')
    if rule.mode in {'construction_documents', 'construction_statistics', 'construction_planning'}:
        if scope.pack_key != 'construction' or not allowed.intersection(rule.actions):
            raise HTTPException(403, 'The selected Business Pack cannot perform this Construction operation')
    if rule.mode == 'industry_kind':
        for_record_read(db, actor, request.query_params.get('kind', ''))
    elif rule.mode in {'capability', 'invoice_document'} and not allowed.intersection(rule.actions):
        raise HTTPException(403, {'code': 'business_pack_operation_denied',
            'message': 'Assigned Business Pack role cannot perform this operation',
            'method': method, 'route': path, 'required_any': list(rule.actions)})
    if rule.mode == 'invoice_document' and request.path_params.get('kind') != 'invoices':
        _unavailable(method, path, 'Only the audited native invoice document is released for this selected workflow')
    if rule.company_admin and not _actual_company_admin(db, actor, scope.company_id):
        raise HTTPException(403, 'Actual native company administrator authority is required')
    if rule.unavailable:
        _unavailable(method, path, rule.unavailable)
    return {'method': method, 'route': path, 'adapter': rule.mode,
            'runtime_ready': False, 'native_authorization_required': True}
