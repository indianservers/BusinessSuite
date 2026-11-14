"""Single-use booking capabilities delegate only the saved appointment scope."""
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import html
import secrets
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import Field
from sqlalchemy.orm import Session
from starlette.requests import Request as ScopeRequest
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.company import Company
from app.models.user import User
from app.shared.models import ServicePolicy
from app.apps.srm.models import SRMProduct
from app.apps.srm.services.commercial import customer, record, tenant
from app.apps.srm.industry_api import Strict, AppointmentInput, PROVIDER_TYPES, available, appointment_operation, context, fail, get, audit
from app.shared import business_profile

router = APIRouter(tags=['Appointment booking links'])
KIND = 'appointment_booking'


def now():
    return datetime.now(timezone.utc)


class LinkInput(Strict):
    customer_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    resource_ids: list[int] = Field(min_length=1, max_length=10)
    duration_minutes: int = Field(default=30, ge=5, le=720)
    expires_hours: int = Field(default=168, ge=1, le=168)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=64)


@router.post('/srm/industry/booking-links', status_code=201)
def create_link(data: LinkInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True, appointments=True)
    customer(db, data.customer_id, user)
    service = record(db, SRMProduct, data.service_id, user)
    if not service.active or service.product_type.lower() not in {'service', 'services'}:
        fail('Choose an active service')
    if len(set(data.resource_ids)) != len(data.resource_ids):
        fail('Select each resource once')
    resources = [get(db, user, branch, ident, 'resource') for ident in sorted(data.resource_ids)]
    if not any(row.data['resource_type'] in PROVIDER_TYPES for row in resources) or any(row.status != 'active' for row in resources):
        fail('Choose an active provider and resources')
    if data.workspace_id:
        business_profile.check_workspace(db, user, branch, 'srm', data.workspace_id)
    raw = secrets.token_urlsafe(32)
    key = hashlib.sha256(raw.encode()).hexdigest()
    expires = now() + timedelta(hours=data.expires_hours)
    from app.db.tenant import current_tenant
    route = current_tenant.get()
    locator = route.tenant_uuid if route else 'shared'
    values = {**data.model_dump(), 'resource_ids': sorted(data.resource_ids), 'branch_id': branch, 'owner_id': user.id,
              'expires_at': expires.isoformat(), 'revoked': False, 'appointment_id': None,
              'price': str(service.sales_rate), 'tax': str(service.gst_rate), 'currency': service.currency,
              'timezone': next(row.data['timezone'] for row in resources if row.data['resource_type'] in PROVIDER_TYPES),
              'locator': locator}
    policy = ServicePolicy(scope_key='appointment-booking:' + key, organization_id=tenant(user), module_key='srm', kind=KIND, values_json=values, updated_by=user.id)
    db.add(policy); db.flush()
    from app.access.service import audit as access_audit
    access_audit(db, user, tenant(user), 'appointments.booking-link.created', str(policy.id), {}, {'branch_id': branch, 'expires_at': expires.isoformat()})
    db.commit()
    path = f'/api/v1/public/appointments/{locator}/{raw}'
    return {'id': policy.id, 'url': settings.BACKEND_PUBLIC_URL.rstrip('/') + path, 'path': path, 'expires_at': expires}


@router.post('/srm/industry/booking-links/{ident}/revoke')
def revoke_link(ident: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True, appointments=True)
    row = db.query(ServicePolicy).filter_by(id=ident, organization_id=tenant(user), kind=KIND).with_for_update().first()
    if not row or row.values_json['branch_id'] != branch:
        fail('Booking link not found', 404)
    row.values_json = {**row.values_json, 'revoked': True}
    row.version += 1
    from app.access.service import audit as access_audit
    access_audit(db, user, tenant(user), 'appointments.booking-link.revoked', str(row.id), {}, {'revoked': True})
    db.commit()
    return {'revoked': True}


def throttle(db, request, token, action):
    from app.core.middleware.audit import client_addresses
    from app.core.request_limits import consume
    key = hashlib.sha256(token.encode()).hexdigest()
    ip = client_addresses(request)[0] or 'unknown'
    retry = consume(db, [(f'appointment-link:{key}:{ip}:{action}', 15 if action == 'book' else 60, 60),
                         (f'appointment-public:{ip}', 180, 60)])
    db.commit()
    if retry:
        raise HTTPException(429, 'Too many requests. Try again shortly.', headers={'Retry-After': str(retry)})


def load_link(db, locator, token):
    from app.db.tenant import current_tenant
    route = current_tenant.get()
    if locator != (route.tenant_uuid if route else 'shared') or not 32 <= len(token) <= 128:
        fail('This booking link is unavailable or has expired', 404)
    key = 'appointment-booking:' + hashlib.sha256(token.encode()).hexdigest()
    row = db.query(ServicePolicy).filter_by(scope_key=key, kind=KIND).first()
    if not row or row.values_json.get('revoked') or datetime.fromisoformat(row.values_json['expires_at']) <= now():
        fail('This booking link is unavailable or has expired', 404)
    return row


@contextmanager
def _owner_scope(db, link):
    from app.access.service import bind_authorization
    from app.core.tenant_boundary import install as tenant_boundary
    from app.branches.service import context as branch_context
    from app.branches.boundary import install as branch_boundary
    owner = db.get(User, link.values_json['owner_id'])
    company = db.get(Company, link.organization_id)
    if not owner or not owner.is_active or not company or not company.is_active:
        fail('This booking link is unavailable or has expired', 404)
    branch = link.values_json['branch_id']
    request = ScopeRequest({'type': 'http', 'method': 'POST', 'path': '/api/v1/srm/industry/appointments', 'query_string': b'',
                            'headers': [(b'x-suite-organization', str(link.organization_id).encode()), (b'x-suite-branch', str(branch).encode())]})
    with ExitStack() as stack:
        previous = db.info.get('security_write_request')
        db.info['security_write_request'] = True
        stack.callback(lambda: db.info.pop('security_write_request', None) if previous is None else db.info.update(security_write_request=previous))
        stack.callback(bind_authorization(db, owner, request))
        stack.callback(tenant_boundary(db, owner, link.organization_id, enforce_superuser_company=True))
        ctx = branch_context(db, owner, link.organization_id, str(branch))
        stack.callback(branch_boundary(db, owner, ctx))
        previous_branch = getattr(owner, '_suite_branch_id', None)
        owner._suite_branch_id = branch
        stack.callback(lambda: setattr(owner, '_suite_branch_id', previous_branch))
        context(db, owner, appointments=True)
        from app.apps.srm.services.commercial import require
        require(owner, 'srm_manage', 'srm_admin')
        if branch not in ctx.writable:
            fail('This booking link is unavailable or has expired', 404)
        values = link.values_json
        customer(db, values['customer_id'], owner)
        service = record(db, SRMProduct, values['service_id'], owner)
        if not values.get('appointment_id') and (not service.active or Decimal(str(service.sales_rate)) != Decimal(values['price']) or Decimal(str(service.gst_rate)) != Decimal(values['tax']) or service.currency != values['currency']):
            fail('This booking link is unavailable or has expired', 404)
        if values.get('workspace_id'):
            business_profile.check_workspace(db, owner, branch, 'srm', values['workspace_id'])
        yield owner, service


@contextmanager
def owner_scope(db, link):
    try:
        with _owner_scope(db, link) as value:
            yield value
    except HTTPException as exc:
        if exc.status_code in {403, 404}:
            fail('This booking link is unavailable or has expired', 404)
        raise


def page(title, body, status=200):
    return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                        f'<title>{html.escape(title)}</title><style>body{{font:16px system-ui;background:#f5f6f8;color:#182230;margin:0;padding:20px}}main{{max-width:520px;margin:24px auto;padding:24px;background:white;border:1px solid #ddd;border-radius:12px;overflow-wrap:anywhere}}h1{{font-size:24px}}label{{display:block;margin:18px 0}}input,select,button{{box-sizing:border-box;font:inherit;width:100%;padding:12px;margin-top:8px;border:1px solid #bbb;border-radius:6px}}button{{background:#182230;color:white}}p{{line-height:1.5}}small{{color:#555}}</style>'
                        f'<main><h1>{html.escape(title)}</h1>{body}</main></html>', status_code=status,
                        headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff',
                                 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"})


def profile_for(db, link):
    values = link.values_json
    return business_profile.effective(db, link.organization_id, values['branch_id'], workspace_module='srm' if values.get('workspace_id') else None, workspace_id=values.get('workspace_id'))


def slots(db, owner, link, day):
    values = link.values_json
    zone = ZoneInfo(values['timezone'])
    today = now().astimezone(zone).date()
    if not today <= day <= min(today + timedelta(days=30), datetime.fromisoformat(values['expires_at']).astimezone(zone).date()):
        return []
    primary = next(get(db, owner, values['branch_id'], ident, 'resource', lock=False) for ident in values['resource_ids']
                   if get(db, owner, values['branch_id'], ident, 'resource', lock=False).data['resource_type'] in PROVIDER_TYPES)
    first = datetime.combine(day, time.fromisoformat(primary.data['opens']), zone)
    end = datetime.combine(day, time.fromisoformat(primary.data['closes']), zone)
    result = []
    candidate = first
    while candidate + timedelta(minutes=values['duration_minutes']) <= end and len(result) < 96:
        start = candidate.astimezone(timezone.utc)
        if now() + timedelta(minutes=15) <= start < datetime.fromisoformat(values['expires_at']):
            try:
                available(db, owner, values['branch_id'], start, values['duration_minutes'], values['resource_ids'], lock=False)
                result.append((start.isoformat(), candidate.strftime('%H:%M')))
            except HTTPException as exc:
                if exc.status_code not in {409, 422}: raise
        candidate += timedelta(minutes=15)
    return result


def confirmation(db, owner, link):
    row = get(db, owner, link.values_json['branch_id'], link.values_json['appointment_id'], 'appointment', lock=False)
    label = profile_for(db, link)['terms']['appointment'][0]
    when = datetime.fromisoformat(row.data['starts_at']).astimezone(ZoneInfo(link.values_json['timezone'])).strftime('%d %b %Y, %H:%M')
    return page(f'{label} confirmed', f'<p>Your booking is confirmed for {html.escape(when)} ({html.escape(link.values_json["timezone"])}).</p><p>Reference: #{row.id}</p><p>Payment is handled by the business. No online charge has been made.</p>')


@router.get('/public/appointments/{locator}/{token}')
def booking_page(locator: str, token: str, request: Request, day: date | None = None, db: Session = Depends(get_db)):
    throttle(db, request, token, 'view')
    link = load_link(db, locator, token)
    with owner_scope(db, link) as (owner, service):
        if link.values_json.get('appointment_id'):
            return confirmation(db, owner, link)
        values = link.values_json
        zone = ZoneInfo(values['timezone'])
        today = now().astimezone(zone).date()
        selected = day or today
        options = slots(db, owner, link, selected)
        terms = profile_for(db, link)['terms']
        label = terms['appointment'][0]
        providers = [get(db, owner, values['branch_id'], ident, 'resource', lock=False) for ident in values['resource_ids']]
        provider_names = ', '.join(row.title for row in providers if row.data['resource_type'] in PROVIDER_TYPES)
        fee = (Decimal(values['price']) * (1 + Decimal(values['tax']) / 100)).quantize(Decimal('0.01'))
        date_form = f'<form method="get"><label>Date<input type="date" name="day" value="{selected.isoformat()}" min="{today.isoformat()}" max="{datetime.fromisoformat(values["expires_at"]).astimezone(zone).date().isoformat()}" required></label><button>Show available times</button></form>'
        body = f'<p>{html.escape(service.item_name)} · {values["duration_minutes"]} minutes</p><p>{html.escape(terms["provider"][1])}: {html.escape(provider_names)}</p><p>Charge: {html.escape(values["currency"])} {fee}. Payment is handled by the business.</p><p>Time zone: {html.escape(values["timezone"])}</p>' + date_form
        if options:
            choices = ''.join(f'<option value="{html.escape(value)}">{html.escape(text)}</option>' for value, text in options)
            body += f'<form method="post" action="{html.escape(request.url.path)}/book"><label>Available time<select name="slot" required>{choices}</select></label><button>Confirm {html.escape(label.lower())}</button></form>'
        else:
            body += '<p>No available times on this date. Choose another date or contact the business.</p>'
        body += '<small>This private link is single-use. Availability is checked again when you confirm.</small>'
        return page(f'Book {label.lower()}', body)


@router.post('/public/appointments/{locator}/{token}/book')
def book(locator: str, token: str, request: Request, slot: str = Form(max_length=50), db: Session = Depends(get_db)):
    throttle(db, request, token, 'book')
    link = load_link(db, locator, token)
    with owner_scope(db, link) as (owner, service):
        context(db, owner, True, appointments=True)  # Same company writer lock/order as reception bookings.
        link = db.query(ServicePolicy).filter_by(id=link.id, organization_id=link.organization_id, kind=KIND).with_for_update().populate_existing().first()
        if link.values_json.get('revoked') or datetime.fromisoformat(link.values_json['expires_at']) <= now():
            fail('This booking link is unavailable or has expired', 404)
        if link.values_json.get('appointment_id'):
            return confirmation(db, owner, link)
        try:
            start = datetime.fromisoformat(slot)
            if start.utcoffset() is None: raise ValueError()
            start = start.astimezone(timezone.utc)
        except ValueError:
            fail('Choose an available time', 422)
        values = link.values_json
        chosen_day = start.astimezone(ZoneInfo(values['timezone'])).date()
        if start.isoformat() not in {value for value, _ in slots(db, owner, link, chosen_day)}:
            return page('Choose another time', '<p>This time is unavailable. Return to the booking page and choose another time.</p>', 409)
        request_id = uuid5(NAMESPACE_URL, link.scope_key)
        result = appointment_operation(AppointmentInput(request_id=request_id, title=service.item_name,
                        customer_id=values['customer_id'], service_id=values['service_id'], resource_ids=values['resource_ids'],
                        duration_minutes=values['duration_minutes'], starts_at=start), db, owner, commit=False)
        link.values_json = {**values, 'appointment_id': result['id']}
        link.version += 1
        db.commit()
        return confirmation(db, owner, link)
