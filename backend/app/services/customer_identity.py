"""Exact customer identity resolution; never infer identity from a display name."""
import re
from collections import defaultdict
from sqlalchemy import String, cast, func, and_


def phone_key(value, country_code=None, country=None):
    raw = str(value or '').strip()
    # Extensions, short numbers and alphabetic vanity numbers are not identities.
    if not raw or re.search(r'[^0-9+().\s-]', raw):
        return None
    digits = re.sub(r'\D', '', raw)
    international = raw.startswith(('+', '00'))
    if raw.startswith('00'):
        digits = digits[2:]
    code = re.sub(r'\D', '', str(country_code or ''))
    if not code and str(country or '').strip().casefold() in {'india', 'in', 'ind'}:
        code = '91'
    if not international and code:
        # A separately stored calling code means the field is a national number.
        # Indian imports also commonly contain the complete 12-digit number.
        if code == '91':
            if len(digits) == 11 and digits.startswith('0'):
                digits = digits[1:]
            if len(digits) == 10:
                digits = code + digits
            elif not (len(digits) == 12 and digits.startswith(code)):
                return None
        else:
            national = digits.lstrip('0')
            digits = code + national
    elif not international and not code:
        # Callers must explicitly mark provider numbers as international.
        return None
    return digits if re.fullmatch(r'[1-9]\d{6,14}', digits) else None


def email_key(value):
    result = str(value or '').strip().casefold()
    return result if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', result) else None


class CustomerIndex:
    """One branch-scoped CRM scan per batch, including secondary phone numbers."""
    def __init__(self, db, company, branch):
        from app.apps.crm.models import CRMContact, CRMLead
        from app.branches.models import BranchOwnership
        self.phones, self.emails = defaultdict(dict), defaultdict(dict)
        if not branch:
            return
        for kind, model in [('contact', CRMContact), ('lead', CRMLead)]:
            owner = BranchOwnership
            query = db.query(model).outerjoin(owner, and_(owner.resource_table == model.__tablename__,
                owner.resource_key == cast(model.id, String), owner.company_id == company)).filter(
                    model.organization_id == company, model.deleted_at.is_(None),
                    func.coalesce(owner.branch_id, model.branch_id) == branch)
            if kind == 'lead':
                query = query.filter(model.is_converted.is_not(True))
            for row in query.all():
                candidate = {'entityType': kind, 'entityId': row.id, 'name': row.full_name,
                    'email': row.email, 'phone': row.phone, 'branchId': branch}
                key = (kind, row.id)
                for prefix in ['', 'alternate_']:
                    phone = phone_key(getattr(row, prefix+'phone'), getattr(row, prefix+'phone_country_code'), row.country)
                    if phone:
                        self.phones[phone][key] = candidate
                email = email_key(row.email)
                if email:
                    self.emails[email][key] = candidate

    def match(self, *, phone=None, email=None):
        p = self.phones.get(phone, {}) if phone else {}
        e = self.emails.get(email_key(email), {}) if email else {}
        # If supplied identifiers disagree, a person must resolve the conflict.
        conflict = bool(p and e and not (p.keys() & e.keys()))
        matches = (p | e) if conflict else ({k:p[k] for k in p.keys() & e.keys()} if p and e else p or e)
        candidates = [dict(value, matchedBy=('phone_and_email' if key in p and key in e else 'phone' if key in p else 'email')) for key,value in matches.items()]
        return {'status': 'conflict' if conflict else 'matched' if len(candidates)==1 else 'ambiguous' if candidates else 'unmatched',
            'candidates': candidates}


def match_whatsapp(db, contact, index=None, apply=False):
    from app.services import whatsapp_workspace as wa
    if contact.entity_id:
        return {'status':'linked', 'candidates':[]}
    branch = wa.branch_ownership(db, contact)
    index = index or CustomerIndex(db, contact.organization_id, branch)
    result = index.match(phone=phone_key('+'+contact.recipient))
    if apply and result['status']=='matched':
        candidate = result['candidates'][0]
        contact.entity_type, contact.entity_id = candidate['entityType'], candidate['entityId']
    return result


def match_recipient(db, recipient, index=None, apply=False):
    from app.apps.communication.customer_models import CustomerBinding
    existing = db.query(CustomerBinding).filter_by(organization_id=recipient.organization_id,
        recipient_id=recipient.id).filter(CustomerBinding.source_type.in_(['contact','lead'])).first()
    if recipient.crm_contact_id or existing:
        return {'status':'linked','candidates':[]}
    index = index or CustomerIndex(db, recipient.organization_id, recipient.branch_id)
    result = index.match(phone=phone_key(recipient.phone), email=recipient.email)
    if apply and result['status']=='matched':
        candidate = result['candidates'][0]
        if candidate['entityType']=='contact':
            recipient.crm_contact_id = candidate['entityId']
        db.add(CustomerBinding(organization_id=recipient.organization_id, branch_id=recipient.branch_id,
            recipient_id=recipient.id, source_type=candidate['entityType'], source_id=candidate['entityId']))
    return result
