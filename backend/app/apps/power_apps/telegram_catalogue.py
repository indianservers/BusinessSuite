"""Public, explicitly published catalogue reads; no private customer or staff fields."""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from app.access.service import background_scope
from app.apps.power_apps.runtime import now
from app.apps.power_apps.telegram_experience import configuration


_DISCOVERY = re.compile(r"\b(products?|services?|catalog(?:ue)?|prices?|cost|slots?|timings?|availability|available|appointments?|book)\b", re.I)


def requested_day(text, today):
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            raise HTTPException(422, 'Use a valid date as YYYY-MM-DD.')
    if 'day after tomorrow' in text:
        return today + timedelta(days=2)
    if 'tomorrow' in text:
        return today + timedelta(days=1)
    if 'today' in text:
        return today
    for index, weekday in enumerate(('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')):
        if re.search(r'\b' + weekday + r'\b', text):
            return today + timedelta(days=(index - today.weekday()) % 7 or 7)
    return None


def earliest_hour(text):
    match = re.search(r'\bafter\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', text)
    if not match:
        return None
    hour, minute, suffix = int(match[1]), int(match[2] or 0), match[3]
    if minute > 59 or hour > 23 or (suffix and not 1 <= hour <= 12):
        raise HTTPException(422, 'Use a valid time, for example after 4 PM.')
    if suffix:
        hour = hour % 12 + (12 if suffix == 'pm' else 0)
    return hour * 60 + minute


def answer(db, resource, trigger, owner, text):
    """Return None for non-catalogue enquiries, otherwise a safe public response."""
    settings = configuration(trigger)
    if not _DISCOVERY.search(text) and not any(service.label.casefold() in text.casefold() for service in settings.booking_services):
        return None
    from app.apps.srm.industry_api import context, get, PROVIDER_TYPES
    from app.apps.srm.models import SRMProduct
    from app.apps.srm.services.commercial import record
    from app.apps.power_apps.telegram_booking import available_slots

    query = text.casefold()
    published = settings.booking_services
    if not published and not settings.catalogue_product_ids:
        return 'The team has not published a catalogue here yet. Send Sales for an enquiry or /human for help.'
    selected = [service for service in published if service.label.casefold() in query]
    wants_slots = bool(re.search(r'\b(slots?|timings?|availability|available|appointments?|book|tomorrow|today)\b', query) or re.search(r'\d{4}-\d{2}-\d{2}', query))
    if not selected:
        selected = published
    lines = []
    try:
        with background_scope(db, owner, 'srm', 'view', branch_id=trigger.config.get('branch_id')):
            branch = context(db, owner, appointments=True)
            product_rows = [record(db, SRMProduct, ident, owner) for ident in settings.catalogue_product_ids]
            named_products = [item for item in product_rows if item.item_name.casefold() in query]
            if named_products and not any(service.label.casefold() in query for service in selected):
                selected = []
            product_rows = named_products or ([] if selected and any(service.label.casefold() in query for service in selected) else product_rows)
            for product in product_rows[:10]:
                if product.active and product.id not in {item.service_id for item in selected}:
                    lines.append(f'{product.item_name}: {product.currency} {product.sales_rate}; tax {product.gst_rate}%.')
            for service in selected[:5]:
                product = record(db, SRMProduct, service.service_id, owner)
                if not product.active or product.product_type.lower() not in {'service', 'services'}:
                    continue
                lines.append(f'{service.label}: {product.currency} {product.sales_rate}; tax {product.gst_rate}%; {service.duration_minutes} minutes.')
                if wants_slots:
                    resources = [get(db, owner, branch, ident, 'resource', lock=False) for ident in service.resource_ids]
                    primary = next((item for item in resources if item.data['resource_type'] in PROVIDER_TYPES), None)
                    if not primary:
                        lines.append('Availability is not configured; send /human for help.')
                        continue
                    day = requested_day(query, now().astimezone(ZoneInfo(primary.data['timezone'])).date())
                    if day is None:
                        lines.append('Which date? Ask, for example, "Consultation availability tomorrow after 4 PM".')
                        continue
                    slots, zone = available_slots(db, owner, branch, service, day)
                    after = earliest_hour(query)
                    slots = [value for value in slots if after is None or datetime.fromisoformat(value).hour * 60 + datetime.fromisoformat(value).minute >= after]
                    times = ', '.join(datetime.fromisoformat(value).strftime('%H:%M') for value in slots[:8])
                    lines.append(f'{day.isoformat()} ({zone}): {times or "No matching slots available"}.')
    except HTTPException as error:
        if error.status_code == 422 and error.detail in {'Use a valid date as YYYY-MM-DD.', 'Use a valid time, for example after 4 PM.', 'Choose a date within the next 30 days'}:
            return str(error.detail)
        return 'The published catalogue or availability is temporarily unavailable. Send /human for help.'
    if not lines:
        return 'No published products or services are currently available. Send Sales for an enquiry or /human for help.'
    if len(selected) > 5:
        lines.append('Showing five published services. Ask for a service by its name.')
    lines.append('Availability is checked live and may change. Send /book to choose and review a booking; no appointment has been created.')
    return '\n'.join(lines)[:3000]
