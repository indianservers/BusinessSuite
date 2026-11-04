"""Collection eligibility shared by manual actions, scheduling and delivery."""
from datetime import datetime, timezone
from decimal import Decimal


def collection_on_hold(invoice, at=None):
    if not invoice.collection_hold:
        return False
    resume = invoice.collection_resume_at
    return resume is None or resume.replace(tzinfo=resume.tzinfo or timezone.utc) > (at or datetime.now(timezone.utc))


def reminder_block_reason(invoice, at=None):
    if invoice.deleted_at or invoice.status in {'draft', 'pending_approval', 'paid', 'cancelled', 'written_off'}:
        return 'Invoice is not an issued outstanding receivable'
    if Decimal(str(invoice.balance_amount or 0)) <= 0:
        return 'Invoice is settled'
    if collection_on_hold(invoice, at):
        return 'Invoice collections are on hold'
    return None
