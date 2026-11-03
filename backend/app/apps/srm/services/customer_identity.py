"""Explicit legacy identity adapters. Never match customers by name/domain."""

from sqlalchemy.orm import object_session, Session
from sqlalchemy import event
from app.apps.crm.models import CRMCompany, CRMAccount
from app.apps.project_management.models import PMSClient
from app.apps.srm.commercial_models import CustomerLink
from app.apps.srm.services.commercial import tenant

ACCOUNT_FIELDS = {
    "account_name": "name",
    "billing_address": "address",
    "website": "website",
    "phone": "phone",
    "phone_country_code": "phone_country_code",
    "country": "country",
}
CLIENT_FIELDS = {
    "name": "name",
    "company_name": "name",
    "email": "email",
    "phone": "phone",
    "phone_country_code": "phone_country_code",
    "website": "website",
}


def linked_customer(db, source_type, ident):
    link = (
        db.query(CustomerLink)
        .filter_by(source_type=source_type, source_id=ident)
        .first()
    )
    return db.get(CRMCompany, link.customer_id) if link else None


def account_write(db, account, user, changes=None):
    """New account -> explicit customer identity; existing unmapped accounts need review."""
    buyer = linked_customer(db, "crm_account", account.id)
    if buyer is None:
        buyer = CRMCompany(
            organization_id=tenant(user),
            name=account.account_name,
            owner_user_id=account.owner_id or user.id,
            created_by_user_id=user.id,
            account_type="Customer",
        )
        db.add(buyer)
        db.flush()
        db.add(
            CustomerLink(
                organization_id=tenant(user),
                source_type="crm_account",
                source_id=account.id,
                customer_id=buyer.id,
                actor_id=user.id,
            )
        )
    for old, new in ACCOUNT_FIELDS.items():
        if changes is None or old in changes:
            setattr(buyer, new, getattr(account, old))
    return buyer


def overlay(value, payload):
    db = object_session(value)
    kind, fields = (
        ("crm_account", ACCOUNT_FIELDS)
        if isinstance(value, CRMAccount)
        else ("pms_client", CLIENT_FIELDS)
    )
    if not db:
        return payload
    buyer = linked_customer(db, kind, value.id)
    if buyer:
        payload.update({old: getattr(buyer, new) for old, new in fields.items()})
        payload["shared_customer_id"] = buyer.id
    return payload


def client_write(db, client, user, changes, shared_customer_id=None, confirmed=False, reason=None):
    """Explicit PMS adapter; never infer a match from a name or email."""
    from fastapi import HTTPException
    from app.shared.master_data import CompanyInput, owner, write_company, version
    buyer = linked_customer(db, "pms_client", client.id)
    if shared_customer_id is not None:
        selected = owner(db, user, "company", shared_customer_id, "project_management")
        if buyer and buyer.id != selected.id:
            raise HTTPException(409, "This client already has a shared identity. Review its business links before relinking")
        buyer = selected
    if buyer is None:
        buyer = write_company(db, user, "project_management", CompanyInput(
            name=client.company_name or client.name, email=client.email,
            phone=client.phone, phone_country_code=client.phone_country_code,
            website=client.website, roles=["Customer"], confirmShared=confirmed, sharedReason=reason))
    elif shared_customer_id is None:
        # Preserve master extensions and independent roles while editing legacy fields.
        from app.shared.master_data import company_output
        current = company_output(db, buyer)
        values = {key: current.get(key) for key in CompanyInput.model_fields if key in current}
        for old, new in CLIENT_FIELDS.items():
            if old in changes:
                values[new] = changes[old]
        if not values.get("name"):
            raise HTTPException(422, "Company name cannot be empty")
        values.update(version=version(buyer), confirmShared=confirmed, sharedReason=reason)
        write_company(db, user, "project_management", CompanyInput(**values), buyer)
    link = db.query(CustomerLink).filter_by(source_type="pms_client", source_id=client.id).first()
    if not link:
        db.add(CustomerLink(organization_id=tenant(user), source_type="pms_client", source_id=client.id, customer_id=buyer.id, actor_id=user.id))
    for old, new in CLIENT_FIELDS.items():
        setattr(client, old, getattr(buyer, new))
    return buyer


@event.listens_for(Session, "before_flush")
def refresh_legacy_projections(db, flush_context, instances):
    """Canonical profile edits refresh compatibility columns in the same transaction.

    Invoice snapshots are deliberately excluded. There is no reverse event loop:
    edits through an extension API must call the canonical adapter explicitly.
    """
    for buyer in list(db.dirty):
        if not isinstance(buyer, CRMCompany) or not db.is_modified(
            buyer, include_collections=False
        ):
            continue
        links = db.query(CustomerLink).filter_by(customer_id=buyer.id).all()
        for kind, model, fields in [
            ("crm_account", CRMAccount, ACCOUNT_FIELDS),
            ("pms_client", PMSClient, CLIENT_FIELDS),
        ]:
            ids = [link.source_id for link in links if link.source_type == kind]
            if ids:
                # ORM writes enforce branch/tenant ownership and run validation;
                # bulk UPDATE bypasses that unit of work and is intentionally denied.
                for extension in db.query(model).filter(model.id.in_(ids)).all():
                    for old, new in fields.items():
                        setattr(extension, old, getattr(buyer, new))
