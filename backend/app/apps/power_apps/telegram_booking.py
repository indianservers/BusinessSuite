"""Telegram booking delegates to native appointment rules and resource locks."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from app.access.service import background_scope
from app.apps.power_apps.runtime import now
from app.apps.power_apps.telegram_experience import configuration
from app.apps.power_apps import telegram_operations as operations


def actor_for(db, resource, owner, thread, linked):
    if not linked or not linked.verified_at or linked.revoked_at:
        raise HTTPException(403, 'Verify your identity before booking or changing an appointment')
    if thread.interface == 'company':
        return operations.staff_member(db, linked, resource.organization_id)
    if not linked.customer_id:
        raise HTTPException(403, 'A verified customer-account link is required for appointment booking')
    return owner


def available_slots(db, actor, branch, service, day, ignore=None):
    from app.apps.srm.industry_api import get, available, PROVIDER_TYPES
    resources = [get(db, actor, branch, ident, 'resource', lock=False) for ident in service.resource_ids]
    primary = next((item for item in resources if item.data['resource_type'] in PROVIDER_TYPES), None)
    if not primary:
        raise HTTPException(422, 'This service has no active provider')
    zone = ZoneInfo(primary.data['timezone'])
    if not now().astimezone(zone).date() <= day <= now().astimezone(zone).date() + timedelta(days=30):
        raise HTTPException(422, 'Choose a date within the next 30 days')
    candidate = datetime.combine(day, time.fromisoformat(primary.data['opens']), zone)
    end = datetime.combine(day, time.fromisoformat(primary.data['closes']), zone)
    slots = []
    while candidate + timedelta(minutes=service.duration_minutes) <= end and len(slots) < 24:
        if candidate > now():
            try:
                available(db, actor, branch, candidate, service.duration_minutes, service.resource_ids, ignore=ignore, lock=False)
                slots.append(candidate.isoformat())
            except HTTPException as error:
                if error.status_code != 409:
                    raise
        candidate += timedelta(minutes=15)
    return slots, primary.data['timezone']


def handle(db, resource, trigger, owner, thread, linked, text, state):
    handled = text == '/book' or text.startswith(('/book ', '/reschedule ', '/cancelbooking ', '/bookcustomer ', '/slot ')) or state.get('stage') in {'booking_customer', 'booking_date', 'booking_slot', 'booking_cancel_reason'}
    if not handled:
        return False, state, None, None
    actor = actor_for(db, resource, owner, thread, linked)
    from app.apps.srm.industry_api import context, get
    from app.apps.srm.models import SRMProduct
    from app.apps.srm.services.commercial import customer, record
    settings = configuration(trigger)
    keyboard = None
    with background_scope(db, actor, 'srm', 'view', branch_id=trigger.config.get('branch_id')):
        branch = context(db, actor, appointments=True)
        if text == '/book':
            if thread.interface == 'company':
                from app.apps.crm.models import CRMCompany
                choices = []
                for buyer in db.query(CRMCompany).order_by(CRMCompany.name).limit(30).all():
                    try:
                        customer(db, buyer.id, actor)
                        choices.append([{'text': buyer.name[:100], 'callback_data': f'customer:{buyer.id}'}])
                    except HTTPException:
                        continue
                return True, {'stage': 'booking_customer', 'interface': thread.interface}, 'Choose the customer account for this appointment.', {'inline_keyboard': choices}
            state = {'interface': thread.interface, 'customer_id': linked.customer_id}
            text = '/bookcustomer ' + str(linked.customer_id)
        if text.startswith('/bookcustomer '):
            try:
                customer_id = int(text.split()[1])
            except (IndexError, ValueError):
                raise HTTPException(422, 'Choose a customer account')
            if thread.interface == 'public' and customer_id != linked.customer_id:
                raise HTTPException(403, 'This customer account is not linked to your identity')
            customer(db, customer_id, actor)
            choices = [[{'text': service.label, 'callback_data': f'book:{service.service_id}'}] for service in settings.booking_services]
            return True, {'stage': 'booking_service', 'interface': thread.interface, 'customer_id': customer_id}, 'Choose an appointment service.', {'inline_keyboard': choices}
        if text.startswith('/book '):
            try:
                service_id = int(text.split()[1])
            except (IndexError, ValueError):
                raise HTTPException(422, 'Choose an appointment service')
            service = next((item for item in settings.booking_services if item.service_id == service_id), None)
            if not service:
                raise HTTPException(404, 'This service is not available through the bot')
            customer_id = state.get('customer_id') if thread.interface == 'company' else linked.customer_id
            if not customer_id:
                raise HTTPException(422, 'Choose the customer account first using /book')
            customer(db, customer_id, actor)
            return True, {'stage': 'booking_date', 'interface': thread.interface, 'customer_id': customer_id, 'service_id': service_id, 'experience_revision': settings.revision}, 'Which date? Enter YYYY-MM-DD.', {'remove_keyboard': True}
        if text.startswith(('/reschedule ', '/cancelbooking ')):
            try:
                appointment_id = int(text.split()[1])
            except (IndexError, ValueError):
                raise HTTPException(422, 'Provide an appointment number')
            appointment = get(db, actor, branch, appointment_id, 'appointment', lock=False)
            if thread.interface == 'public' and appointment.customer_id != linked.customer_id:
                raise HTTPException(404, 'Appointment is not available for your verified account')
            customer(db, appointment.customer_id, actor)
            service_id = appointment.data['service_id']
            if not any(item.service_id == service_id for item in settings.booking_services):
                raise HTTPException(409, 'Manage this service through the company’s appointment team')
            next_state = {'stage': 'booking_date' if text.startswith('/reschedule') else 'booking_cancel_reason', 'interface': thread.interface,
                'appointment_id': appointment.id, 'appointment_revision': appointment.revision, 'service_id': service_id,
                'customer_id': appointment.customer_id, 'experience_revision': settings.revision}
            return True, next_state, 'Which date? Enter YYYY-MM-DD.' if text.startswith('/reschedule') else 'Why do you want to cancel this appointment?', {'remove_keyboard': True}
        if state.get('experience_revision') != settings.revision:
            raise HTTPException(409, 'Booking configuration changed. Start again with /book.')
        service = next((item for item in settings.booking_services if item.service_id == state.get('service_id')), None)
        if not service:
            raise HTTPException(409, 'This service is no longer available')
        if state.get('stage') == 'booking_date':
            try:
                day = date.fromisoformat(text)
            except ValueError:
                return True, state, 'Enter the date as YYYY-MM-DD.', None
            slots, zone = available_slots(db, actor, branch, service, day, state.get('appointment_id'))
            if not slots:
                return True, state, 'No slots are available on that date. Choose another date as YYYY-MM-DD.', None
            keyboard = {'inline_keyboard': [[{'text': datetime.fromisoformat(slot).strftime('%H:%M') + ' ' + zone, 'callback_data': f'slot:{index}'}] for index, slot in enumerate(slots)]}
            return True, {**state, 'stage': 'booking_slot', 'slots': slots, 'timezone': zone}, 'Choose an available appointment time.', keyboard
        if state.get('stage') == 'booking_slot':
            try:
                index = int(text.split()[1]) if text.startswith('/slot ') else -1
                starts = state['slots'][index] if 0 <= index < len(state['slots']) else None
            except (ValueError, IndexError, KeyError):
                starts = None
            if not starts:
                return True, state, 'Choose a time using the displayed buttons.', None
            product = record(db, SRMProduct, service.service_id, actor)
            resources = [get(db, actor, branch, ident, 'resource', lock=False) for ident in service.resource_ids]
            operation = {'action': 'reschedule' if state.get('appointment_id') else 'create', 'customer_id': state['customer_id'], 'service_id': service.service_id,
                'resource_ids': service.resource_ids, 'starts_at': starts, 'duration_minutes': service.duration_minutes, 'experience_revision': settings.revision,
                'appointment_id': state.get('appointment_id'), 'appointment_revision': state.get('appointment_revision'),
                'price': str(product.sales_rate), 'tax': str(product.gst_rate), 'currency': product.currency, 'title': service.label}
            if state.get('appointment_id'):
                existing = get(db, actor, branch, state['appointment_id'], 'appointment', lock=False)
                operation.update(price=str(existing.data['unit_price']), tax=str(existing.data['tax_rate']), currency=existing.data['currency'])
            preview = f"{'Reschedule' if state.get('appointment_id') else 'Book'} appointment\nCustomer: {customer(db, state['customer_id'], actor).name}\nService: {service.label}\nTime: {starts}\nDuration: {service.duration_minutes} minutes\nResources: {', '.join(item.title for item in resources)}\nPrice: {operation['currency']} {operation['price']}; tax rate: {operation['tax']}%"
            if state.get('appointment_id'):
                preview += '\nExisting appointment pricing remains unchanged. No payment is collected.'
        elif state.get('stage') == 'booking_cancel_reason':
            if not text.strip() or len(text) > 1800:
                return True, state, 'Provide a cancellation reason of 1–1800 characters.', None
            operation = {'action': 'cancel', 'appointment_id': state['appointment_id'], 'appointment_revision': state['appointment_revision'],
                'customer_id': state['customer_id'], 'experience_revision': settings.revision, 'reason': text}
            preview = f"Cancel appointment #{state['appointment_id']}\nReason: {text}"
        else:
            return True, state, 'Start appointment booking with /book.', None
    from app.apps.power_apps.telegram_approvals import issue
    approval, message, keyboard = issue(db, resource, thread, linked, 'booking', operation, preview)
    return True, {'stage': 'booking_review', 'interface': thread.interface, 'approval_id': approval.id}, message, keyboard


def execute_approval(db, resource, trigger, owner, thread, linked, approval):
    if approval.kind != 'booking':
        raise HTTPException(422, 'Unsupported action review')
    if approval.status == 'reject_requested':
        return {'execution_status': 'rejected'}
    actor = actor_for(db, resource, owner, thread, linked)
    operation = approval.operation
    if thread.interface == 'public' and operation['customer_id'] != linked.customer_id:
        raise HTTPException(403, 'Customer authorization changed')
    settings = configuration(trigger)
    if settings.revision != operation['experience_revision']:
        raise HTTPException(409, 'Booking configuration changed; review again')
    from app.apps.srm import industry_api as native
    from app.apps.srm.models import SRMProduct
    from app.apps.srm.services.commercial import customer, record
    with background_scope(db, actor, 'srm', 'create', branch_id=trigger.config.get('branch_id')):
        branch = native.context(db, actor, True, appointments=True)
        customer(db, operation['customer_id'], actor)
        if operation['action'] in {'create', 'reschedule'} and datetime.fromisoformat(operation['starts_at']) <= now():
            raise HTTPException(409, 'This appointment time has passed. Choose a new slot.')
        if operation['action'] == 'create':
            product = record(db, SRMProduct, operation['service_id'], actor)
            if (Decimal(str(product.sales_rate)), Decimal(str(product.gst_rate)), product.currency) != (Decimal(operation['price']), Decimal(operation['tax']), operation['currency']):
                raise HTTPException(409, 'Service pricing changed; review again')
            result = native.appointment_operation(native.AppointmentInput(request_id=uuid5(NAMESPACE_URL, f'telegram-booking:{resource.id}:{approval.id}'),
                title=operation['title'], customer_id=operation['customer_id'], service_id=operation['service_id'],
                resource_ids=operation['resource_ids'], starts_at=operation['starts_at'], duration_minutes=operation['duration_minutes']), db, actor, commit=False)
        else:
            appointment = native.get(db, actor, branch, operation['appointment_id'], 'appointment')
            if appointment.customer_id != operation['customer_id']:
                raise HTTPException(403, 'Appointment customer changed')
            if operation['action'] == 'reschedule':
                result = native.reschedule_operation(appointment.id, native.Reschedule(expected_revision=operation['appointment_revision'], starts_at=operation['starts_at'],
                    duration_minutes=operation['duration_minutes'], resource_ids=operation['resource_ids']), db, actor, commit=False)
            else:
                result = native.transition_operation(appointment.id, native.Transition(expected_revision=operation['appointment_revision'], status='cancelled', reason=operation['reason']), db, actor, commit=False)
    return {'execution_status': result['status'], 'appointment_id': result['id'], 'revision': result['revision']}
