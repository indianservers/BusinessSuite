"""Move master extensions without overwriting conflicting profile information."""
from fastapi import HTTPException
from app.shared.master_data_models import ContactChannel, BusinessRelationship, ContactBirthday, CompanyContactLink


def merge_contact_extensions(db, winner_id, loser_ids):
    from app.apps.project_management.task_record_links import merge_links
    from app.apps.project_management.models import PMSTaskRecordLink
    merge_links(db, 'contact', winner_id, loser_ids)
    channels = {(x.kind, x.normalized_value): x for x in db.query(ContactChannel).filter_by(contact_id=winner_id)}
    primary_kinds = {x.kind for x in channels.values() if x.is_primary}
    for row in db.query(ContactChannel).filter(ContactChannel.contact_id.in_(loser_ids)).order_by(ContactChannel.id).all():
        key = row.kind, row.normalized_value
        existing = channels.get(key)
        if existing:
            if row.notes and existing.notes and row.notes != existing.notes:
                raise HTTPException(409, "Review conflicting communication notes before merging")
            existing.notes = existing.notes or row.notes
            existing.whatsapp = existing.whatsapp or row.whatsapp
            db.delete(row)
        else:
            row.contact_id = winner_id
            row.is_primary = row.is_primary and row.kind not in primary_kinds
            if row.is_primary:
                primary_kinds.add(row.kind)
            channels[key] = row
    roles = {x.role: x for x in db.query(BusinessRelationship).filter_by(contact_id=winner_id)}
    for row in db.query(BusinessRelationship).filter(BusinessRelationship.contact_id.in_(loser_ids)).all():
        existing = roles.get(row.role)
        if existing:
            for key in ["status", "category", "payment_terms", "credit_limit", "follow_up_at", "notes"]:
                old, new = getattr(existing, key), getattr(row, key)
                if old is not None and new is not None and old != new:
                    raise HTTPException(409, "Review conflicting business relationship details before merging")
                if old is None:
                    setattr(existing, key, new)
            db.delete(row)
        else:
            row.contact_id = winner_id
            roles[row.role] = row
    birthday = db.query(ContactBirthday).filter_by(contact_id=winner_id).first()
    for row in db.query(ContactBirthday).filter(ContactBirthday.contact_id.in_(loser_ids)).all():
        if birthday:
            keys = ["birth_day", "birth_month", "birth_year", "email_opt_in", "whatsapp_opt_in", "sms_opt_in", "reminders_enabled"]
            if any(getattr(birthday, key) != getattr(row, key) for key in keys):
                raise HTTPException(409, "Review conflicting birthdays and consent before merging")
            # Retain identical source preferences and annual greeting history on
            # the archived identity instead of deleting their audit evidence.
        else:
            row.contact_id = winner_id
            birthday = row
    accounts = {x.account_id for x in db.query(CompanyContactLink).filter_by(contact_id=winner_id)}
    for row in db.query(CompanyContactLink).filter(CompanyContactLink.contact_id.in_(loser_ids)).all():
        if row.account_id in accounts:
            db.delete(row)
        else:
            row.contact_id = winner_id
            accounts.add(row.account_id)
    from app.apps.crm.financial_models import ContactFinancialProfile, ContactFinancialTransaction
    profile = db.get(ContactFinancialProfile, winner_id)
    for source in db.query(ContactFinancialProfile).filter(ContactFinancialProfile.contact_id.in_(loser_ids)).all():
        if profile:
            if (profile.gst_number, profile.bank_accounts, profile.upi_ids) != (source.gst_number, source.bank_accounts, source.upi_ids):
                raise HTTPException(409, "Review conflicting financial data before merging")
            db.delete(source)
        else:
            # contact_id is this extension's primary key. Preserve immutable
            # record identifiers by creating the survivor's extension instead.
            profile = ContactFinancialProfile(contact_id=winner_id, organization_id=source.organization_id, gst_number=source.gst_number, bank_accounts=source.bank_accounts, upi_ids=source.upi_ids, version=source.version + 1)
            db.add(profile)
            db.delete(source)
    for transaction in db.query(ContactFinancialTransaction).filter(ContactFinancialTransaction.contact_id.in_(loser_ids)).all():
        transaction.contact_id = winner_id
    return {ContactChannel, BusinessRelationship, ContactBirthday, CompanyContactLink, ContactFinancialProfile, ContactFinancialTransaction, PMSTaskRecordLink}
