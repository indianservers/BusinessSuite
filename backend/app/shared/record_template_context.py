"""Allowlisted template values from the same visible records as the record UI."""
from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException
from app.apps.srm.services.commercial import tenant
from app.shared.record_360 import context, module_access


def text(value):
    if value is None: return ''
    if isinstance(value, (date, datetime)): return value.strftime('%d %B %Y')
    return str(value)


def money(value):
    return '' if value is None else f'{Decimal(str(value)):,.2f}'


def address(row):
    def value(key): return row.get(key) if isinstance(row, dict) else getattr(row, key, None)
    return ', '.join(dict.fromkeys(str(value(k)).strip() for k in ('address', 'city', 'state', 'country', 'pincode') if value(k)))


def organization_values(row):
    get = row.get if isinstance(row, dict) else lambda k: getattr(row, k, None)
    return {'organization.name': text(get('legal_name') or get('name')), 'organization.address': address(row),
            'organization.email': text(get('email')), 'organization.phone': text(get('phone')),
            'organization.tax_id': text(get('gstin'))}


def common_values(db, user):
    from app.models.company import Company
    company = db.get(Company, tenant(user))
    person = getattr(user, 'person', None)
    employee = getattr(user, 'employee', None)
    person_name = getattr(person, 'display_name', None) or getattr(person, 'full_name', None)
    employee_name = ' '.join(str(getattr(employee, k, None) or '') for k in ('first_name', 'last_name')).strip()
    designation = getattr(employee, 'designation', None)
    return {**(organization_values(company) if company else {}),
            'sender': text(person_name or employee_name or user.email), 'sender_email': text(user.email),
            'sender_title': text(getattr(designation, 'name', None)),
            'document.currency': text(getattr(company, 'default_currency', None))}


def visible_link(db, user, kind, identity, source):
    if not identity: return None
    try: return context(db, user, kind, identity, source)[0]
    except HTTPException as exc:
        if exc.status_code not in (403, 404): raise
        return None


def resolve_context(db, user, entity, identity, source='crm'):
    values = common_values(db, user)
    if entity == 'invoice': return invoice_context(db, user, identity, values)
    if source != 'crm' and entity not in ('account', 'contact'):
        raise HTTPException(422, 'Use the CRM source for leads and deals')
    kind = 'company' if entity == 'account' else entity
    row, _, company = context(db, user, kind, identity, source)
    recipient = row
    if entity == 'account': company = row
    if entity == 'deal':
        recipient = visible_link(db, user, 'contact', row.contact_id, source)
        values.update({'deal.name': row.name, 'deal.amount': money(row.amount), 'deal.currency': text(row.currency),
                       'deal.status': text(row.status), 'deal.expected_close_date': text(row.expected_close_date),
                       'document.currency': text(row.currency)})
        items = row.catalog_items or []
        if isinstance(items, list):
            names = [item.get('name') or item.get('product_name') or item.get('description') for item in items if isinstance(item, dict)]
            if any(names): values['product'] = ', '.join(str(name) for name in names if name)
    if recipient:
        name = getattr(recipient, 'full_name', None) or getattr(recipient, 'name', None)
        values.update({'name': text(name), 'first_name': text(getattr(recipient, 'first_name', None) or (name.split()[0] if name else '')),
                       'email': text(getattr(recipient, 'email', None)), 'phone': text(getattr(recipient, 'phone', None)),
                       'address': address(recipient)})
        prefix = 'contact' if entity == 'deal' else entity
        for key in ('full_name', 'first_name', 'last_name', 'email', 'phone', 'job_title', 'status', 'source', 'industry', 'website'):
            values[f'{prefix}.{key}'] = text(getattr(recipient, key, None))
    if company:
        values.update({'company': text(company.name), 'account.name': text(company.name), 'account.email': text(company.email),
                       'account.phone': text(company.phone), 'account.address': address(company), 'account.industry': text(company.industry)})
        if not values.get('address'): values['address'] = address(company)
    elif entity in ('lead', 'contact'):
        values['company'] = text(row.company_name)
    label = text(getattr(row, 'full_name', None) or getattr(row, 'name', None))
    return {'values': values, 'lines': [], 'record_name': label, 'document_status': None, 'snapshot': False}


def invoice_context(db, user, identity, values):
    from app.apps.srm.services import commercial
    from app.apps.srm.commercial_models import InvoiceContext
    from app.core.rich_text import rich_text_plain
    module_access(db, user, 'srm')
    commercial.require(user, 'srm_invoice_view', 'srm_invoice_create', 'srm_invoice_approve', 'srm_admin')
    invoice = commercial.invoice_for(db, identity, user)
    ctx = db.get(InvoiceContext, invoice.id)
    snapshot = bool(ctx and ctx.issued_at)
    buyer = (ctx.customer_snapshot or {}) if snapshot else {}
    seller = (ctx.seller_snapshot or {}) if snapshot else {}
    contact = (ctx.contact_snapshot or {}) if snapshot else {}
    if not snapshot:
        if invoice.customer_id:
            row = commercial.customer(db, invoice.customer_id, user)
            buyer = {key: getattr(row, key, None) for key in ('name', 'address', 'city', 'state', 'country', 'email', 'phone')}
        seller = commercial.seller(db, ctx.seller_id if ctx else tenant(user), user)
        if ctx and ctx.contact_id:
            # A finance user can see the billing contact only through the invoice's customer.
            from app.apps.crm.models import CRMContact
            row = commercial.record(db, CRMContact, ctx.contact_id, user)
            if row.company_id == invoice.customer_id:
                contact = {'name': row.full_name, 'email': row.email}
    name = contact.get('name') or buyer.get('name')
    values.update(organization_values(seller))
    values.update({'name': text(name), 'first_name': text(name.split()[0] if name else ''), 'company': text(buyer.get('name')),
                   'email': text(contact.get('email') or buyer.get('email')), 'phone': text(buyer.get('phone')), 'address': address(buyer),
                   'document.number': invoice.invoice_number, 'document.date': text(invoice.issue_date), 'document.due_date': text(invoice.due_date),
                   'document.currency': invoice.currency, 'document.subtotal': money(invoice.subtotal), 'document.discount': money(invoice.discount_amount),
                   'document.tax': money(invoice.tax_amount), 'document.total': money(invoice.total_amount), 'document.balance': money(invoice.balance_amount),
                   'invoice.number': invoice.invoice_number, 'invoice.status': text(invoice.status), 'invoice.paid': money(invoice.paid_amount)})
    lines = [{'description': rich_text_plain(line.description), 'quantity': format(Decimal(str(line.quantity or 0)).normalize(), 'f'),
              'rate': money(line.unit_price), 'amount': money(Decimal(str(line.quantity or 0)) * Decimal(str(line.unit_price or 0)))}
             for line in sorted(invoice.lines, key=lambda line: line.id)]
    return {'values': values, 'lines': lines, 'record_name': invoice.invoice_number, 'document_status': invoice.status, 'snapshot': snapshot}
