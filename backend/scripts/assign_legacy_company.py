"""Review/assign unmapped legacy configuration; dry-run unless --apply is explicit."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import func
from app.db.base import Base
from app.db.session import SessionLocal
from app.models.user import User
from app.models.company import Company
from app.models.audit import AuditLog
from app.models.security_boundary import SecurityResourceOwnership
from app.core.tenant_boundary import legacy_root


def assign(db, actor, company_id, table_name, identifiers, reason, apply=False):
    if not actor or not actor.is_active or not actor.is_superuser:
        raise HTTPException(403, "Global administrator authority required")
    if (
        not identifiers
        or len(identifiers) > 200
        or any(isinstance(value, bool) or value <= 0 for value in identifiers)
    ):
        raise HTTPException(422, "Use 1 to 200 positive record IDs")
    if not 10 <= len(reason.strip()) <= 500:
        raise HTTPException(422, "A concise review reason is required")
    company = db.get(Company, company_id)
    if not company or not company.is_active:
        raise HTTPException(404, "Active company required")
    models = {
        mapper.local_table.name: mapper.class_
        for mapper in Base.registry.mappers
        if legacy_root(mapper.class_)
    }
    model = models.get(table_name)
    if model is None:
        raise HTTPException(422, "Not a supported legacy ownership table")
    identifiers = sorted(set(identifiers))
    present = {
        row[0] for row in db.query(model.id).filter(model.id.in_(identifiers)).all()
    }
    if present != set(identifiers):
        raise HTTPException(404, "One or more records do not exist")
    changes = []
    for ident in identifiers:
        existing = db.get(SecurityResourceOwnership, (table_name, ident))
        if existing and existing.company_id != company_id:
            raise HTTPException(
                409,
                "Ownership is already assigned; reassignment needs a separate review",
            )
        if not existing:
            changes.append(
                {"table": table_name, "record_id": ident, "company_id": company_id}
            )
    if apply:
        for change in changes:
            db.add(
                SecurityResourceOwnership(
                    resource_table=table_name,
                    resource_id=change["record_id"],
                    company_id=company_id,
                )
            )
            db.add(
                AuditLog(
                    user_id=actor.id,
                    organization_id=company_id,
                    method="CLI",
                    endpoint="security/legacy-ownership",
                    action="OWNERSHIP_ASSIGN",
                    entity_type=table_name,
                    entity_id=change["record_id"],
                    status_code=200,
                    actor_role="database_operator",
                    actor_authenticated=False,
                    description=reason.strip(),
                    new_values=json.dumps(change),
                )
            )
        db.flush()
    return {"dry_run": not apply, "changes": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor-email", required=True)
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--record-ids", type=int, nargs="+", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        try:
            actor = (
                db.query(User)
                .filter(func.lower(User.email) == args.actor_email.casefold())
                .one_or_none()
            )
            result = assign(
                db,
                actor,
                args.company_id,
                args.table,
                args.record_ids,
                args.reason,
                args.apply,
            )
            if args.apply:
                db.commit()
            else:
                db.rollback()
            print(json.dumps(result, indent=2))
        except Exception as exc:
            db.rollback()
            print(
                "Ownership assignment failed ("
                + type(exc).__name__
                + "). No changes committed."
            )
            raise SystemExit(1) from None


if __name__ == "__main__":
    main()
