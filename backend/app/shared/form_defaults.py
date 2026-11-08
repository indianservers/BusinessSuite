"""Validated, tenant-scoped starting values for new records. Never updates records."""
import json
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException
from sqlalchemy import select, or_
from app.models.company import Company, Branch, Department, CostCenter
from app.models.user import User
from app.shared.models import ServicePolicy

FIELDS = json.loads((Path(__file__).resolve().parents[1] / "core" / "form_defaults.json").read_text(encoding="utf-8"))
DEFINITIONS = {field["key"]: field for field in FIELDS}
MODULES = {"crm", "srm", "fam", "hrms", "project_management"}
BASE = {field["key"]: field.get("default") for field in FIELDS}


def scope_key(company_id, module=None, branch_id=None):
    if module is not None and module not in MODULES:
        raise HTTPException(422, "Select a supported module")
    return f"form-defaults:company:{company_id}" + (f":branch:{branch_id}" if branch_id else "") + (f":module:{module}" if module else "")


def check_branch(db, company_id, branch_id):
    if branch_id is not None and not db.connection().execute(select(Branch.id).where(Branch.id == branch_id, Branch.company_id == company_id, Branch.is_active.is_(True))).first():
        raise HTTPException(422, "Select an active branch in this company")


def reference_queries(db, company_id):
    from app.apps.crm.models import CRMPipeline, CRMPipelineStage, CRMPriceBook
    from app.apps.fam.models import FAMBankAccount, FAMPaymentMode, FAMCostCenter
    from app.models.attendance import Shift
    from app.models.leave import LeaveType
    from app.access.models import AccessMembership
    from app.models.employee import Employee
    from app.common.models import CommonPerson
    # Shifts and leave types are shared HR masters in the existing schema.
    return {
        "branches": (db.query(Branch).filter_by(company_id=company_id, is_active=True), "name"),
        "departments": (db.query(Department).join(Branch, Department.branch_id == Branch.id).filter(Branch.company_id == company_id, Department.is_active.is_(True)), "name"),
        "accounting_cost_centers": (db.query(FAMCostCenter).filter_by(company_id=company_id, active=True), "name"),
        "cost_centers": (db.query(CostCenter).filter_by(company_id=company_id, is_active=True), "name"),
        "pipelines": (db.query(CRMPipeline).filter_by(organization_id=company_id, active=True, deleted_at=None), "name"),
        "stages": (db.query(CRMPipelineStage).join(CRMPipeline).filter(CRMPipeline.organization_id == company_id, CRMPipeline.active.is_(True), CRMPipeline.deleted_at.is_(None), CRMPipelineStage.active.is_(True), CRMPipelineStage.deleted_at.is_(None), CRMPipelineStage.stage_type == "open"), "name"),
        "price_books": (db.query(CRMPriceBook).filter_by(organization_id=company_id, active=True, deleted_at=None), "name"),
        "bank_accounts": (db.query(FAMBankAccount).filter_by(company_id=company_id, active=True), "bank_name"),
        "payment_modes": (db.query(FAMPaymentMode).filter_by(company_id=company_id, active=True), "name"),
        "users": (db.query(User).filter(User.is_active.is_(True), User.id.notin_(select(AccessMembership.user_id).where(AccessMembership.company_id == company_id, AccessMembership.active.is_(False))), or_(User.id.in_(select(AccessMembership.user_id).where(AccessMembership.company_id == company_id, AccessMembership.active.is_(True))), User.id.in_(select(CommonPerson.user_id).where(CommonPerson.organization_id == company_id)), User.id.in_(select(Employee.user_id).join(Branch, Employee.branch_id == Branch.id).where(Branch.company_id == company_id, Employee.deleted_at.is_(None))))), "email"),
        "shifts": (db.query(Shift).filter_by(is_active=True), "name"),
        "leave_types": (db.query(LeaveType).filter_by(is_active=True), "name"),
    }


def choices(db, company_id):
    result = {}
    for key, (query, label) in reference_queries(db, company_id).items():
        result[key] = [{"value": row.id, "label": getattr(row, label), **({"pipeline_id": row.pipeline_id} if key == "stages" else {}), **({"branch_id": row.branch_id} if key == "departments" else {})} for row in query.order_by(label).all()]
    return result


def effective(db, company_id, module=None, branch_id=None, *, skip_scope=None):
    scope_key(company_id, module, branch_id)
    result = dict(BASE)
    org = db.get(Company, company_id)
    if org:
        from app.core.input_validation import CONTRACT
        country = next((row["iso"] for row in CONTRACT["countries"] if row["country"].lower() == (org.country or "").lower() or row["iso"] == org.country), "IN")
        country = {"UAE": "AE", "UK": "GB"}.get(org.country, country)
        phone_code = next((row["code"] for row in CONTRACT["countries"] if row["iso"] == country), "+91")
        result.update(phone_country_code=phone_code, currency=org.default_currency or "INR", payroll_currency=org.default_currency or "INR", timezone=org.default_timezone or "Asia/Kolkata", country=country, fiscal_year_start_month=org.fiscal_year_start_month or 4, working_days=list(range(1, min(org.working_days_per_week or 5, 6) + 1)) + ([0] if org.working_days_per_week == 7 else []))
    keys = [scope_key(company_id)]
    if module: keys.append(scope_key(company_id, module))
    if branch_id: keys.append(scope_key(company_id, branch_id=branch_id))
    if branch_id and module: keys.append(scope_key(company_id, module, branch_id))
    rows = {row.scope_key: row for row in db.query(ServicePolicy).filter(ServicePolicy.scope_key.in_(keys), ServicePolicy.kind == "form_defaults", ServicePolicy.organization_id == company_id).all()}
    sources = {key: "company" for key in result}
    for key in keys:
        if key != skip_scope and key in rows:
            for name, value in rows[key].values_json.items():
                if name in DEFINITIONS:
                    result[name] = value
                    sources[name] = key
    # A configured ID can be retired later. Never preselect unavailable masters.
    refs = None
    for field in FIELDS:
        if field["type"] != "reference" or not result.get(field["key"]): continue
        if refs is None: refs = reference_queries(db, company_id)
        query, _ = refs[field["reference"]]
        model = query.column_descriptions[0]["entity"]
        if field["reference"] == "branches":
            found = db.connection().execute(select(Branch.id).where(Branch.id == result[field["key"]], Branch.company_id == company_id, Branch.is_active.is_(True))).first()
        else: found = query.filter(model.id == result[field["key"]]).first()
        if not found: result[field["key"]] = None
    if result.get("stage_id"):
        from app.apps.crm.models import CRMPipelineStage
        stage = db.get(CRMPipelineStage, result["stage_id"])
        if not stage or stage.pipeline_id != result.get("pipeline_id"): result["stage_id"] = None
    if result.get("department_id") and result.get("branch_id"):
        department = db.get(Department, result["department_id"])
        if not department or department.branch_id != result["branch_id"]: result["department_id"] = None
    if result.get("payment_mode_id"):
        from app.apps.fam.models import FAMPaymentMode
        mode = db.get(FAMPaymentMode, result["payment_mode_id"])
        result["payment_mode_name"] = mode.name
        result["payment_mode_type"] = mode.type
    return {"values": result, "sources": sources}


def validate(db, company_id, values, inherited):
    if not isinstance(values, dict) or set(values) - set(DEFINITIONS):
        raise HTTPException(422, "Unknown form default")
    from app.core.business_validation import BUSINESS
    from app.core.input_validation import CONTRACT
    refs = reference_queries(db, company_id)
    for key, value in values.items():
        field = DEFINITIONS[key]
        if value is None:
            if field.get("default") is not None:
                raise HTTPException(422, f'{field["label"]} needs a value; remove the override to inherit')
            continue
        kind = field["type"]
        valid = True
        if kind == "reference":
            query, _ = refs[field["reference"]]
            model = query.column_descriptions[0]["entity"]
            if field["reference"] == "branches":
                valid = type(value) is int and bool(db.connection().execute(select(Branch.id).where(Branch.id == value, Branch.company_id == company_id, Branch.is_active.is_(True))).first())
            else:
                valid = type(value) is int and bool(query.filter(model.id == value).first())
        elif kind == "select":
            if key == "lead_source":
                from app.shared.starter_values import lead_sources
                valid = value in lead_sources(db, company_id)
            else:
                valid = any(type(value) is type(option["value"]) and value == option["value"] for option in field["options"])
        elif kind == "number":
            valid = type(value) in (int, float) and field["min"] <= value <= field["max"] and (key == "tax_rate" or type(value) is int)
        elif kind == "days":
            valid = isinstance(value, list) and 1 <= len(value) <= 7 and all(type(day) is int and 0 <= day <= 6 for day in value) and len(set(value)) == len(value)
        elif kind == "currency": valid = value in BUSINESS["currencies"]
        elif kind == "country": valid = any(row["iso"] == value for row in CONTRACT["countries"])
        elif kind == "phone": valid = any(row["code"] == value for row in CONTRACT["countries"])
        elif kind == "timezone":
            try: ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError, TypeError): valid = False
        if not valid: raise HTTPException(422, f'Select a valid {field["label"].lower()}')
    combined = {**inherited, **values}
    if combined.get("owner_mode") == "specific_user" and not combined.get("owner_id"):
        raise HTTPException(422, "Choose the specific record owner")
    if combined.get("stage_id"):
        from app.apps.crm.models import CRMPipelineStage
        stage = db.get(CRMPipelineStage, combined["stage_id"])
        if not stage or stage.pipeline_id != combined.get("pipeline_id"):
            raise HTTPException(422, "Initial stage must belong to the selected pipeline")
    if combined.get("department_id") and combined.get("branch_id"):
        department = db.get(Department, combined["department_id"])
        if not department or department.branch_id != combined["branch_id"]:
            raise HTTPException(422, "Department must belong to the selected branch")
    return values

def creation_values(db, actor, entity, payload, module="crm"):
    """Fill omitted create fields only. Explicit input, including null, always wins."""
    from datetime import date, timedelta
    branch = getattr(actor, "_suite_branch_id", None)
    values = effective(db, actor.organization_id, module, branch if isinstance(branch, int) else None)["values"]
    data = dict(payload)
    groups = {
        "leads": {"source": "lead_source"},
        "deals": {"currency": "currency", "pipeline_id": "pipeline_id", "stage_id": "stage_id", "priority": "task_priority"},
        "quotes": {"currency": "currency"}, "quotations": {"currency": "currency"},
        "tasks": {"priority": "task_priority"},
        "price-books": {"currency": "currency"},
        "price-book-items": {"price_book_id": "price_book_id"},
    }
    aliases = {"pipeline_id": "pipelineId", "stage_id": "stageId", "price_book_id": "priceBookId"}
    for name, key in groups.get(entity, {}).items():
        if name not in data and aliases.get(name) not in data and values.get(key) is not None:
            data[name] = values[key]
    if entity in {"leads", "contacts", "companies", "deals", "quotes", "quotations", "tasks"}:
        if not {"ownerId", "owner_id", "owner_user_id"}.intersection(data):
            if values["owner_mode"] == "specific_user" and values.get("owner_id"):
                data["owner_user_id"] = values["owner_id"]
            elif values["owner_mode"] == "current_user":
                data["owner_user_id"] = actor.id
    if entity == "deals":
        supplied_pipeline = data.get("pipeline_id", data.get("pipelineId"))
        if supplied_pipeline != values.get("pipeline_id") and not {"stage_id", "stageId"}.intersection(payload):
            data.pop("stage_id", None)
    if entity in {"quotes", "quotations"}:
        if not {"expiry_date", "valid_until", "expiryDate", "validUntil"}.intersection(data):
            data["expiry_date"] = (date.today() + timedelta(days=values["quote_validity_days"])).isoformat()
        if not {"terms", "terms_and_conditions"}.intersection(data):
            days = values["payment_terms_days"]
            data["terms"] = f"Payment terms: Net {days}" if days else "Payment due on receipt"
    return data


def capture_document_defaults(db, company_id, module, entity, record_id, actor):
    branch = getattr(actor, "_suite_branch_id", None)
    values = effective(db, company_id, module, branch if isinstance(branch, int) else None)["values"]
    # Freeze presentation/payment defaults at creation so later settings do not alter old documents.
    keys = {"date_format", "time_format", "number_format", "language", "timezone", "invoice_template", "quote_template", "bank_account_id", "payment_mode_id", "payment_terms_days"}
    snapshot = {key: values[key] for key in keys}
    if values.get("bank_account_id"):
        from app.apps.fam.models import FAMBankAccount
        bank = db.query(FAMBankAccount).filter_by(id=values["bank_account_id"], company_id=company_id, active=True).first()
        if bank: snapshot["bank_details"] = {key: getattr(bank, key) for key in ("bank_name", "branch_name", "account_number_masked", "ifsc")}
    if values.get("payment_mode_id"):
        from app.apps.fam.models import FAMPaymentMode
        mode = db.query(FAMPaymentMode).filter_by(id=values["payment_mode_id"], company_id=company_id, active=True).first()
        if mode: snapshot["payment_method"] = mode.name
    key=f"form-snapshot:{company_id}:{module}:{entity}:{record_id}"
    # Called only when creating a document. SQLite can reuse a hard-deleted
    # document ID; replace its orphaned presentation slot in this transaction.
    policy=db.query(ServicePolicy).filter_by(scope_key=key,organization_id=company_id,kind="form_snapshot").first()
    if policy:
        policy.values_json=snapshot
        policy.updated_by=actor.id
        policy.version+=1
    else:
        db.add(ServicePolicy(scope_key=key, organization_id=company_id, module_key=module, kind="form_snapshot", values_json=snapshot, version=1, updated_by=actor.id))
    return snapshot


def document_defaults(db, company_id, module, entity, record_id):
    row = db.query(ServicePolicy).filter_by(scope_key=f"form-snapshot:{company_id}:{module}:{entity}:{record_id}", organization_id=company_id, kind="form_snapshot").first()
    return row.values_json if row else {**BASE, "date_format": "YYYY-MM-DD", "bank_account_id": None, "payment_mode_id": None}


def document_date(value, defaults):
    if value is None: return ""
    pattern = {"DD/MM/YYYY": "%d/%m/%Y", "MM/DD/YYYY": "%m/%d/%Y", "YYYY-MM-DD": "%Y-%m-%d"}[defaults.get("date_format", "YYYY-MM-DD")]
    return value.strftime(pattern)

def document_money(value, currency, defaults):
    from decimal import Decimal
    amount = f"{Decimal(str(value or 0)):.2f}"
    whole, fraction = amount.split(".")
    negative = whole.startswith("-")
    whole = whole.lstrip("-")
    if defaults.get("number_format") == "en-IN" and len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while head:
            parts.insert(0, head[-2:]); head = head[:-2]
        whole = ",".join(parts + [tail])
    else: whole = f"{int(whole):,}"
    return f"{currency} {'-' if negative else ''}{whole}.{fraction}"
