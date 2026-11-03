"""Canonical business contacts and explicit links; credentials remain separate.

CRMContact is the existing canonical business identity. No HR profile data is
copied into the directory. Matching email/phone suggests duplicates, never merges
accounts. Links and their source records are guarded by the branch boundary.
"""
from sqlalchemy import Column, ForeignKey, Integer, CheckConstraint, event, inspect, select
from sqlalchemy.orm import Session, relationship
from app.db.base_class import Base


class ContactIdentityLink(Base):
    __tablename__ = "suite_contact_identity_links"
    __table_args__ = (CheckConstraint(
        "(CASE WHEN lead_id IS NOT NULL THEN 1 ELSE 0 END + "
        "CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END + "
        "CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END + "
        "CASE WHEN account_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
        name="ck_contact_identity_one_source"),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="RESTRICT"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("crm_leads.id", ondelete="RESTRICT"), unique=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="RESTRICT"), unique=True)
    person_id = Column(Integer, ForeignKey("common_people.id", ondelete="RESTRICT"), unique=True)
    account_id = Column(Integer, ForeignKey("crm_companies.id", ondelete="RESTRICT"), unique=True)
    contact = relationship("CRMContact", foreign_keys=[contact_id])
    lead = relationship("CRMLead", foreign_keys=[lead_id])
    employee = relationship("Employee", foreign_keys=[employee_id])
    person = relationship("CommonPerson", foreign_keys=[person_id])
    account = relationship("CRMCompany", foreign_keys=[account_id])


def tags(contact):
    return sorted({part.strip() for part in (contact.tags_text or "").split(",") if part.strip()}, key=str.casefold)


def add_tags(contact, *values):
    # Keep the legacy CRM text representation for existing consumers/exports.
    contact.tags_text = ", ".join(sorted(set(tags(contact)) | set(values), key=str.casefold))


def link_source(db, source, kind):
    """Explicit source identity wins. Attribute matches require human confirmation."""
    if kind not in {"lead", "account"}:
        from fastapi import HTTPException
        raise HTTPException(403, "Employee and user identities must be accessed through their authorized directories")
    from app.apps.crm.models import CRMContact
    field = f"{kind}_id"
    source_id = source.id
    link = next((x for x in db.new if isinstance(x, ContactIdentityLink) and getattr(x, kind) is source), None)
    if not link and source_id:
        link = db.query(ContactIdentityLink).filter(getattr(ContactIdentityLink, field) == source_id).first()
    if link:
        return link.contact
    # Converted leads already have a verified identity; never recreate it.
    contact = db.get(CRMContact, source.converted_contact_id) if kind == "lead" and source.converted_contact_id else None
    ctx = db.info.get("branch_context")
    company = getattr(source, "organization_id", None) or (ctx.company_id if ctx else None)
    if not company:
        return None
    if not contact:
        name = (getattr(source, "full_name", None) or getattr(source, "display_name", None)
                or getattr(source, "name", None) or " ".join(filter(None, [getattr(source, "first_name", None), getattr(source, "last_name", None)])))
        if not name:
            return None
        # These are CRM business fields; HR and login profiles are excluded.
        email = getattr(source, "email", None)
        contact = CRMContact(organization_id=company, branch_id=getattr(source, "branch_id", None) or (ctx.branch_id if ctx else None),
            full_name=name, first_name=getattr(source, "first_name", None) or name,
            last_name=getattr(source, "last_name", None), email=email,
            phone=getattr(source, "phone", None), phone_country_code=getattr(source, "phone_country_code", None),
            company_name=getattr(source, "company_name", None), owner_user_id=getattr(source, "owner_user_id", None),
            status="Active", lifecycle_stage="Customer" if kind == "account" else "Lead",
            created_by_user_id=getattr(source, "created_by_user_id", None))
        db.add(contact)
        if kind == "account":
            contact.company = source
    label = "Lead" if kind == "lead" else str(getattr(source, "account_type", None) or "Prospect").title()
    if label not in {"Lead", "Prospect", "Customer", "Vendor", "Supplier", "Partner", "Dealer", "Distributor", "Investor"}:
        label = "Other"
    if kind == "account":
        contact.lifecycle_stage = label
    add_tags(contact, label)
    if kind == "lead" and source.is_converted:
        add_tags(contact, "Customer")
    link = ContactIdentityLink(organization_id=company, contact=contact, **{kind: source})
    db.add(link)
    return contact


@event.listens_for(Session, "before_flush")
def synchronize_business_contacts(db, *_):
    # Bootstrap/schema migration sessions remain untouched. Source backfill is
    # explicit and resumable; never synthesize identities on GET requests.
    ctx = db.info.get("branch_context")
    if not ctx or not ctx.branch_id or not db.info.get("security_write_request"):
        return
    if db.info.get("contact_identity_sync"):
        return
    candidates = [x for x in db.new | db.dirty if x.__table__.name in {"crm_leads", "crm_companies"}]
    if not candidates:
        return
    # Rolling deployments can run old schema until the additive migration lands.
    if not inspect(db.connection()).has_table(ContactIdentityLink.__tablename__):
        return
    # Employees and login identities are NEVER automatically published into the
    # business directory. They require an explicit, separately authorized link.
    kinds = {"crm_leads": "lead", "crm_companies": "account"}
    db.info["contact_identity_sync"] = True
    try:
        with db.no_autoflush:
            for source in list(db.new):
                kind = kinds.get(source.__table__.name)
                if kind and not getattr(source, "deleted_at", None):
                    link_source(db, source, kind)
            for source in list(db.dirty):
                kind = kinds.get(source.__table__.name)
                if not kind:
                    continue
                link = db.query(ContactIdentityLink).filter(getattr(ContactIdentityLink, f"{kind}_id") == source.id).first()
                if not link:
                    continue
                # Copy only changed public business fields. No historical
                # transaction, employee profile or login field is mutated.
                fields = {"full_name": "full_name", "name": "full_name", "email": "email", "phone": "phone", "phone_country_code": "phone_country_code", "company_name": "company_name", "last_contacted_at": "last_contacted_at", "next_follow_up_at": "next_follow_up_at"}
                state = inspect(source)
                if kind == "account" and state.attrs.account_type.history.has_changes():
                    old = {str(x).title() for x in state.attrs.account_type.history.deleted if x}
                    label = str(source.account_type or "Prospect").title()
                    link.contact.tags_text = ",".join(sorted((set(tags(link.contact)) - old) | {label}))
                    link.contact.lifecycle_stage = label
                for original, target in fields.items():
                    if original in state.attrs and state.attrs[original].history.has_changes():
                        setattr(link.contact, target, getattr(source, original))
    finally:
        db.info.pop("contact_identity_sync", None)
