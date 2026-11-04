"""Compatibility projections for writes through existing module APIs."""
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from app.shared.master_data_models import ContactChannel


def mirror_primary(db, owner):
    from app.apps.crm.models import CRMContact
    from app.core.input_validation import email_address, normalize_phone
    kind = "contact" if isinstance(owner, CRMContact) else "company"
    field = "contact_id" if kind == "contact" else "account_id"
    for channel_kind, column in [("email", "email"), ("phone", "phone")]:
        value = getattr(owner, column)
        code = getattr(owner, "phone_country_code", None) if channel_kind == "phone" else None
        existing = db.query(ContactChannel).filter(getattr(ContactChannel, field) == owner.id, ContactChannel.kind == channel_kind).all()
        pending = [x for x in db.new if isinstance(x, ContactChannel) and getattr(x, field) == owner.id and x.kind == channel_kind]
        rows = [*existing, *pending]
        if not value:
            for row in rows:
                row.is_primary = False
            continue
        try:
            if channel_kind == "email": normalized = email_address(value).casefold()
            else: value, normalized = normalize_phone(value, code)
        except ValueError:
            # Preserve ambiguous legacy values in their original source; do not
            # guess a country code or create invalid normalized records.
            continue
        selected = next((x for x in rows if x.normalized_value == normalized), None)
        if not selected:
            selected = ContactChannel(organization_id=owner.organization_id, **{field: owner.id}, kind=channel_kind, value=value, normalized_value=normalized, country_code=code, label="Primary", is_primary=True, whatsapp=False, verification_status="unverified")
            db.add(selected)
        for row in rows:
            row.is_primary = row is selected
        selected.is_primary = True


@event.listens_for(Session, "before_flush")
def remember_sources(db, *_):
    from app.apps.crm.models import CRMContact, CRMCompany
    if not db.info.get("branch_context") or not db.info.get("security_write_request"):
        return
    if not inspect(db.connection()).has_table(ContactChannel.__tablename__):
        return
    pending = db.info.setdefault("master_primary_pending", [])
    for row in list(db.new | db.dirty):
        if not isinstance(row, (CRMContact, CRMCompany)):
            continue
        state = inspect(row)
        if row in db.new or any(state.attrs[key].history.has_changes() for key in ("email", "phone", "phone_country_code")):
            if row not in pending:
                pending.append(row)


@event.listens_for(Session, "after_flush_postexec")
def synchronize_sources(db, *_):
    pending = db.info.pop("master_primary_pending", [])
    with db.no_autoflush:
        for row in pending:
            if row not in db.deleted and row not in db.info.get("master_channels_managed", set()):
                mirror_primary(db, row)


@event.listens_for(Session, "after_soft_rollback")
def discard_sources(db, *_):
    db.info.pop("master_primary_pending", None)
    db.info.pop("master_channels_managed", None)


@event.listens_for(Session, "after_commit")
def clear_managed(db):
    db.info.pop("master_channels_managed", None)
