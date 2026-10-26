"""Read the existing Business OS entitlement table without seeding on reads."""

from fastapi import HTTPException
from sqlalchemy import inspect
from app.apps.business_os.models import BOSEnabledModule


def states(db, company):
    if not inspect(db.connection()).has_table("bos_enabled_modules"):
        return {}
    # Core read avoids business-record scope hooks when checking authorization itself.
    table = BOSEnabledModule.__table__
    result = {
        row.module_key: row.enabled
        for row in db.connection().execute(
            table.select().where(table.c.company_id == company)
        )
    }
    from app.models.company import Company
    from app.access.catalog import MODULES

    organization = (
        db.connection()
        .execute(Company.__table__.select().where(Company.__table__.c.id == company))
        .mappings()
        .first()
    )
    if organization and not organization["is_active"]:
        result.update({key: False for key in MODULES})
    from app.enterprise.controls import disabled_modules

    result.update({key: False for key in disabled_modules(db, company)})
    return result


def enforce(db, company, module):
    from app.models.company import Company

    table = Company.__table__
    active = (
        db.connection()
        .execute(table.select().where(table.c.id == company))
        .mappings()
        .first()
    )
    if module and active and not active["is_active"]:
        raise HTTPException(403, "Company is inactive")
    if module and states(db, company).get(module) is False:
        raise HTTPException(403, f"Module disabled for this company: {module}")


def apply(db, company, grants):
    disabled = {key for key, enabled in states(db, company).items() if not enabled}
    for key in disabled:
        if key in grants:
            grants[key]["enabled"] = False
    return grants
