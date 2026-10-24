"""Dry-run by default. Apply only explicit, tenant-checked legacy ID mappings.

python scripts/reconcile_commercial_identity.py --organization 1
python scripts/reconcile_commercial_identity.py --organization 1 --actor 1 --map pms_client:12=34 --apply
Sources: pms_client, crm_account. No matching/merging by company name or domain.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func
from app.db.base import Base  # register maintained models
from app.db.session import SessionLocal
from app.apps.crm.models import CRMAccount, CRMCompany, CRMContact, CRMTeam
from app.apps.project_management.models import PMSClient, PMSProject
from app.apps.srm.commercial_models import CustomerLink, ProjectCommercial
from app.apps.srm.models import SRMInvoice, SRMEngagement, SRMSalesOrder
from app.models.user import User


def reconcile(db, organization, mappings=(), actor=None, apply=False, backfill_projects=False):
    models = {"pms_client": PMSClient, "crm_account": CRMAccount}
    report = {
        "organization_id": organization,
        "dry_run": not apply,
        "unmapped": {},
        "possible_duplicates_review_only": [],
        "proposed_mappings": [],
        "legacy_invoice_customers_requiring_review": [],
    }
    customers = (
        db.query(CRMCompany)
        .filter(
            func.coalesce(CRMCompany.organization_id, 1) == organization,
            CRMCompany.deleted_at.is_(None),
        )
        .all()
    )
    by_name = {}
    for c in customers:
        by_name.setdefault(c.name.strip().casefold(), []).append(c.id)
    report["possible_duplicates_review_only"] = [
        {"customer_ids": ids, "reason": "Similar display name; never auto-merge"}
        for ids in by_name.values()
        if len(ids) > 1
    ]
    for key, model, field in [("contacts_review_only", CRMContact, "email"), ("teams_review_only", CRMTeam, "name")]:
        groups = {}
        for record in db.query(model).filter(func.coalesce(model.organization_id, 1) == organization, model.deleted_at.is_(None)):
            value = (getattr(record, field) or "").strip().casefold()
            if value:
                groups.setdefault(value, []).append(record.id)
        report[key] = [{"ids": ids, "reason": "Repeated value; review separately, never auto-merge"} for ids in groups.values() if len(ids) > 1]
    for kind, model in models.items():
        linked = db.query(CustomerLink.source_id).filter_by(
            source_type=kind, organization_id=organization
        )
        report["unmapped"][kind] = [
            r.id
            for r in db.query(model).filter(
                func.coalesce(model.organization_id, 1) == organization,
                model.deleted_at.is_(None),
                ~model.id.in_(linked),
            )
        ]
    customer_ids = {c.id for c in customers}
    report["legacy_invoice_customers_requiring_review"] = [
        r.id
        for r in db.query(SRMInvoice).filter(
            func.coalesce(SRMInvoice.organization_id, 1) == organization
        )
        if r.customer_id not in customer_ids
    ]
    for mapping in mappings:
        source, target = mapping.split("=")
        kind, ident = source.split(":")
        if kind not in models:
            raise ValueError("Source must be pms_client or crm_account")
        old = (
            db.query(models[kind])
            .filter(
                models[kind].id == int(ident),
                func.coalesce(models[kind].organization_id, 1) == organization,
                models[kind].deleted_at.is_(None),
            )
            .first()
        )
        if not old or int(target) not in customer_ids:
            raise ValueError(
                "Every source and target must exist in the selected tenant"
            )
        existing = (
            db.query(CustomerLink).filter_by(source_type=kind, source_id=old.id).first()
        )
        if existing and existing.customer_id != int(target):
            raise ValueError(
                "Conflicting existing mapping requires separate financial review"
            )
        report["proposed_mappings"].append(
            {
                "source_type": kind,
                "source_id": old.id,
                "customer_id": int(target),
                "already_linked": bool(existing),
            }
        )
        if apply and not existing:
            if actor is None:
                raise ValueError("--actor is required to apply reviewed mappings")
            user = db.get(User, actor)
            if not user or not user.is_active or not user.is_superuser:
                raise ValueError(
                    "An active administrator must apply reviewed identity mappings"
                )
            from app.apps.srm.services.commercial import tenant

            if tenant(user) != organization:
                raise ValueError("Actor must belong to the selected tenant")
            from app.apps.srm.api.router import _audit

            db.add(
                CustomerLink(
                    organization_id=organization,
                    source_type=kind,
                    source_id=old.id,
                    customer_id=int(target),
                    actor_id=actor,
                )
            )
            _audit(
                db,
                user,
                kind,
                old.id,
                "canonical_identity_mapped",
                after={"customer_id": int(target), "source": "reviewed_reconciliation"},
            )
    report["project_links_proposed"] = []
    report["project_links_requiring_review"] = []
    from app.models.company import Company
    from app.apps.srm.services.commercial import tenant, currency_code
    from app.apps.srm.api.router import _audit
    candidates = db.query(SRMEngagement).filter(func.coalesce(SRMEngagement.organization_id, 1) == organization, SRMEngagement.pms_project_id.isnot(None), SRMEngagement.deleted_at.is_(None)).all()
    counts = {}
    for engagement in candidates:
        counts[engagement.pms_project_id] = counts.get(engagement.pms_project_id, 0) + 1
    for engagement in candidates:
        if db.get(ProjectCommercial, engagement.pms_project_id):
            continue
        project = db.get(PMSProject, engagement.pms_project_id)
        order = db.get(SRMSalesOrder, engagement.sales_order_id) if engagement.sales_order_id else None
        if not project or (project.organization_id or 1) != organization or not order or (order.organization_id or 1) != organization or not order.crm_company_id or order.crm_company_id != engagement.customer_id or order.crm_company_id not in customer_ids or counts[project.id] != 1 or not db.get(Company, organization) or (order.metadata_json or {}).get("seller_id", organization) != organization or order.currency != engagement.currency:
            report["project_links_requiring_review"].append(engagement.pms_project_id)
            continue
        try:
            currency_code(engagement.currency)
        except Exception:
            report["project_links_requiring_review"].append(project.id)
            continue
        data = {"project_id": project.id, "customer_id": order.crm_company_id, "seller_id": organization,
            "currency": engagement.currency, "opportunity_id": engagement.crm_deal_id, "sales_order_id": order.id, "engagement_id": engagement.id}
        contact = db.get(CRMContact, order.crm_contact_id) if order.crm_contact_id else None
        if contact and contact.company_id == order.crm_company_id and (contact.organization_id or 1) == organization:
            data["contact_id"] = contact.id
        report["project_links_proposed"].append(data)
        if apply and backfill_projects:
            user = db.get(User, actor) if actor else None
            if not user or not user.is_active or not user.is_superuser or tenant(user) != organization:
                raise ValueError("An active administrator in this tenant must apply project backfills")
            db.add(ProjectCommercial(**data, updated_by=user.id))
            _audit(db, user, "project", project.id, "commercial_backfilled", after=data)
    if apply:
        db.commit()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization", type=int, required=True)
    parser.add_argument("--actor", type=int)
    parser.add_argument("--map", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backfill-projects", action="store_true", help="Apply only proposed links backed by explicit CRM company/order/project IDs")
    args = parser.parse_args()
    with SessionLocal() as db:
        print(
            json.dumps(
                reconcile(db, args.organization, args.map, args.actor, args.apply, args.backfill_projects),
                indent=2,
            )
        )
