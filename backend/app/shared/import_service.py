"""Authoritative preview, duplicate resolution, atomic commit and guarded undo."""
import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import inspect, select, func
from sqlalchemy.orm import class_mapper
from app.core.deps import RequirePermission
from app.shared.import_catalog import SPECS, get_spec
from app.shared.import_models import ImportBatch


def now():
    return datetime.now(timezone.utc)


def json_value(value):
    if isinstance(value, (date, datetime, Decimal)):
        return value.isoformat() if not isinstance(value, Decimal) else str(value)
    return value


def snapshot(row):
    return {column.key: json_value(getattr(row, column.key)) for column in inspect(row).mapper.columns}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def authorize(db, user, spec, request):
    from app.module_registry import is_app_enabled
    from app.apps.srm.services.commercial import tenant
    from app.branches.service import context
    if not is_app_enabled("project_management" if spec.module == "pms" else spec.module):
        raise HTTPException(404, "Application is not enabled")
    RequirePermission(*spec.permissions)(user)
    company = tenant(user)
    ctx = context(db, user, company, request.headers.get("X-Suite-Branch"))
    if ctx.branch_id is None or ctx.branch_id not in ctx.writable:
        raise HTTPException(403, "Choose a writable branch before importing")
    return ctx


def spec_or_404(module, entity):
    spec = get_spec(module, entity)
    if not spec:
        raise HTTPException(404, "Unknown import type")
    return spec


def tenant_keys(model):
    # CRM company_id references a customer; organization_id is its tenant.
    if hasattr(model, "organization_id"):
        return ("organization_id",)
    return ("company_id",) if hasattr(model, "company_id") else ()


def owned(db, row, ctx, visited=None):
    if row is None:
        raise ValueError("Referenced record does not exist or is not accessible")
    visited = set() if visited is None else visited
    identity = (type(row), getattr(row, "id", None))
    if identity in visited:
        return
    visited.add(identity)
    for key in tenant_keys(type(row)):
        if hasattr(type(row), key) and (getattr(row, key) or 1) != ctx.company_id:
            raise ValueError("Referenced record belongs to another company")
    if getattr(row, "deleted_at", None):
        raise ValueError("Referenced record is deleted")
    branch = getattr(row, "branch_id", None)
    if branch is not None and branch != ctx.branch_id:
        raise ValueError("Referenced record is outside the selected branch")
    # Children without direct company ownership inherit it from their parent.
    if not any(hasattr(type(row), key) for key in ("organization_id", "company_id")) and type(row).__name__ != "User":
        for col in inspect(row).mapper.columns:
            for fk in col.foreign_keys:
                if fk.column.table.name in {"employees", "pms_projects", "pms_tasks", "fam_bank_statements", "crm_pipelines"}:
                    parent = model_for_table(fk.column.table.name)
                    if getattr(row, col.key) is not None:
                        owned(db, db.get(parent, getattr(row, col.key)), ctx, visited)


def model_for_table(table):
    from app.db.base_class import Base
    return next(mapper.class_ for mapper in Base.registry.mappers if mapper.local_table.name == table)


def fields_for(spec):
    return {field["key"]: field for field in spec.fields}


def convert_value(field, value, options):
    suggestions = []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped != value:
            suggestions.append("Trim surrounding spaces")
            if options.get("trim", True):
                value = stripped
    if value is None or value == "" or isinstance(value, str) and not value.strip():
        if field["required"]:
            raise ValueError("Required value is missing")
        return None, suggestions
    kind = field["type"]
    if kind == "number":
        try:
            text = str(value)
            if "," in text:
                suggestions.append("Remove thousands separators")
                if options.get("numbers", True):
                    text = text.replace(",", "")
            value = Decimal(text)
            if not value.is_finite() or value < 0:
                raise ValueError("Use a finite nonnegative number")
        except InvalidOperation:
            raise ValueError("Enter a valid number")
    elif kind == "date":
        value = date.fromisoformat(str(value))
    elif kind == "email":
        from app.core.input_validation import email_address
        email_address(str(value))
        if str(value) != str(value).lower():
            suggestions.append("Normalize email to lowercase")
            if options.get("email_case", True):
                value = str(value).lower()
    else:
        value = str(value)
        if len(value) > 10000:
            raise ValueError("Cell is too long")
    return value, suggestions


def prepare(db, spec, source, ctx, user, existing=None, check_period=True):
    values = {**spec.defaults, **source}
    model = spec.model
    if spec.module == "fam" and values.get("currency"):
        from app.apps.fam.models import FAMCompanyFinancialSettings
        settings = db.query(FAMCompanyFinancialSettings).filter_by(company_id=ctx.company_id).first()
        if str(values.pop("currency")).upper() != (settings.base_currency if settings else "INR"):
            raise ValueError("Foreign-currency opening bills require conversion in Finance first; do not mix currencies")
    if "employee_code" in values:
        from app.models.employee import Employee
        employee = db.query(Employee).filter(Employee.employee_id == values.pop("employee_code"), Employee.deleted_at.is_(None)).first()
        owned(db, employee, ctx)
        values["employee_id"] = employee.id
    for key in tenant_keys(model):
        if hasattr(model, key):
            values[key] = ctx.company_id
    if hasattr(model, "branch_id"):
        values["branch_id"] = ctx.branch_id
    for key in ("created_by", "created_by_user_id", "owner_user_id", "reporter_user_id"):
        if hasattr(model, key):
            values[key] = user.id
    if spec.key == "time_entries":
        values["user_id"] = user.id
    for phone, code in (("phone", "phone_country_code"), ("phone_number", "phone_number_country_code")):
        if values.get(phone):
            from app.core.input_validation import normalize_phone
            country = str(values.get(code) or "")
            if not country:
                raise ValueError(f"{code}: choose a calling code when a phone number is provided")
            country = "+" + country.lstrip("+")
            values[phone], _ = normalize_phone(values[phone], country)
            values[code] = country
    if spec.module == "crm" and spec.key == "leads":
        values["first_name"] = values["full_name"].split()[0]
    if spec.key == "bank_statements":
        values["line_hash"] = digest({key: str(value) for key, value in source.items()})
    for key, value in values.items():
        if key not in model.__table__.columns or value is None:
            continue
        column = model.__table__.columns[key]
        if hasattr(column.type, "precision") and column.type.precision and isinstance(value, Decimal):
            scale = column.type.scale or 0
            if value >= Decimal(10) ** (column.type.precision - scale) or value != value.quantize(Decimal(10) ** -scale):
                raise ValueError(f"{key}: value exceeds supported precision ({column.type.precision}, {scale})")
        if column.type.python_type is int:
            if Decimal(str(value)) != int(value) or not 0 <= int(value) <= 2147483647:
                raise ValueError(f"{key}: use a whole number")
            values[key] = int(value)
        if hasattr(column.type, "length") and column.type.length and len(str(value)) > column.type.length:
            raise ValueError(f"{key}: maximum length is {column.type.length}")
        for fk in column.foreign_keys:
            if fk.column.table.name != "users":
                owned(db, db.get(model_for_table(fk.column.table.name), values[key]), ctx)
    if spec.module == "pms" and values.get("project_id"):
        from app.apps.project_management.access import get_project_for_action
        get_project_for_action(db, values["project_id"], user, "log_time" if spec.key == "time_entries" else "manage_tasks")
    if spec.key == "deals":
        from app.apps.crm.models import CRMPipelineStage
        stage = db.get(CRMPipelineStage, values["stage_id"])
        if not stage.active or stage.is_won or stage.is_lost or stage.stage_type in {"won", "lost"}:
            raise ValueError("Choose an active open stage for imported deals")
        values["probability"] = stage.probability or 0
        values["expected_revenue"] = values["amount"] * Decimal(values["probability"]) / 100
        if stage.pipeline_id != values["pipeline_id"]:
            raise ValueError("Stage must belong to the selected pipeline")
    if spec.module == "pms" and values.get("task_id"):
        from app.apps.project_management.models import PMSTask
        if db.get(PMSTask, values["task_id"]).project_id != values["project_id"]:
            raise ValueError("Task must belong to the selected project")
    if spec.key == "tasks" and values.get("parent_task_id"):
        parent = db.get(model, values["parent_task_id"])
        if parent.project_id != values["project_id"] or existing and parent.id == existing.id:
            raise ValueError("Parent must be another task in the same project")
        visited = {existing.id} if existing else set()
        while parent:
            if parent.id in visited:
                raise ValueError("Parent task would create a circular hierarchy")
            visited.add(parent.id)
            parent = db.get(model, parent.parent_task_id) if parent.parent_task_id else None
    if values.get("due_date") and values.get("start_date") and values["due_date"] < values["start_date"]:
        raise ValueError("Due date must not precede start date")
    if spec.key == "products" and values.get("product_type") not in {"stock", "service"}:
        raise ValueError("Product type must be stock or service")
    if spec.key == "attendance":
        if values["status"] not in {"Present", "Absent", "Half-day", "WFH", "Holiday", "Weekend", "On Leave"} or values.get("total_hours", 0) > 24:
            raise ValueError("Choose a valid attendance status and hours from 0 to 24")
        from app.models.attendance import AttendanceMonthLock
        lock_columns = AttendanceMonthLock.__table__.columns
        locks = db.query(AttendanceMonthLock).filter(AttendanceMonthLock.status == "Locked")
        if "employee_id" in lock_columns:
            locks = locks.filter(AttendanceMonthLock.employee_id == values["employee_id"])
        if "month" in lock_columns and "year" in lock_columns:
            locks = locks.filter(AttendanceMonthLock.month == values["attendance_date"].month, AttendanceMonthLock.year == values["attendance_date"].year)
        if locks.first():
            raise ValueError("Attendance period is locked; unlock it in HRMS before importing")
    if spec.key == "salaries" and check_period:
        from app.api.v1.payroll import _ensure_not_locked_for_date
        _ensure_not_locked_for_date(db, values["effective_from"], "import salary assignment")
        overlap = db.query(model).filter(model.employee_id == values["employee_id"], model.is_active.is_(True), (model.effective_to.is_(None)) | (model.effective_to >= values["effective_from"]))
        if existing:
            overlap = overlap.filter(model.id != existing.id)
        if overlap.first():
            raise ValueError("Salary period overlaps an active assignment; close the prior assignment in payroll first")
    if spec.key == "time_entries" and not 0 < values["duration_minutes"] <= 1440:
        raise ValueError("Duration must be between 1 and 1440 minutes")
    if spec.key == "ledgers":
        values["current_balance_dr"] = values.get("opening_balance_dr", 0)
        values["current_balance_cr"] = values.get("opening_balance_cr", 0)
        from app.apps.fam.models import FAMLedgerGroup, FAMLedgerEntry
        group = db.get(FAMLedgerGroup, values["ledger_group_id"])
        if group.nature != values["nature"]:
            raise ValueError("Ledger nature must match the selected ledger group")
        if existing and (existing.system_ledger or db.query(FAMLedgerEntry).filter_by(ledger_id=existing.id).first()):
            raise ValueError("Used or system ledgers must be changed through Finance, not overwritten by an import")
        if values["nature"] not in {"asset", "liability", "income", "expense", "equity"}:
            raise ValueError("Nature must be asset, liability, income, expense or equity")
        if values.get("opening_balance_dr", 0) and values.get("opening_balance_cr", 0):
            raise ValueError("Opening balance may be debit or credit, not both")
    if spec.key == "outstanding_bills":
        from app.apps.fam.models import FAMParty
        if db.get(FAMParty, values["party_id"]).ledger_id != values["ledger_id"]:
            raise ValueError("Bill ledger must match the selected party's ledger")
        if values["due_date"] < values["bill_date"]:
            raise ValueError("Bill due date must not precede its issue date")
        if values["bill_type"] not in {"invoice", "bill", "debit_note", "credit_note", "opening", "advance"} or not 0 < values["outstanding_amount"] <= values["original_amount"]:
            raise ValueError("Choose a valid bill type and an outstanding amount no greater than the original amount")
    if spec.key == "bank_statements":
        from app.apps.fam.models import FAMBankStatement
        statement = db.get(FAMBankStatement, values["statement_id"])
        if statement.status != "imported" or (statement.statement_period_start and values["transaction_date"] < statement.statement_period_start) or (statement.statement_period_end and values["transaction_date"] > statement.statement_period_end):
            raise ValueError("Choose an open statement and a transaction date within its statement period")
    if spec.key == "bank_statements" and bool(values.get("debit_amount", 0)) == bool(values.get("credit_amount", 0)):
        raise ValueError("Exactly one of debit or credit must be positive")
    return values


def identity_fields(spec, values):
    # Lead forms often ask for a phone instead of email. Match the normalized
    # number together with its country code rather than inventing an email.
    if spec.module == 'crm' and spec.key == 'leads' and not values.get('email'):
        if not values.get('phone') or not values.get('phone_country_code'):
            raise ValueError('A lead needs an email or a phone number with its calling code')
        return ('phone', 'phone_country_code')
    return spec.identity


def candidates(db, spec, values, ctx, user):
    model = spec.model
    query = db.query(model)
    for key in tenant_keys(model):
        if hasattr(model, key):
            query = query.filter(func.coalesce(getattr(model, key), 1) == ctx.company_id)
    for key in identity_fields(spec, values):
        value = values.get(key)
        if value is None or value == "":
            raise ValueError(f"Duplicate matching requires {key}")
        column = getattr(model, key)
        query = query.filter(func.lower(column) == str(value).lower() if isinstance(value, str) else column == value)
    rows = query.limit(2).all()
    for row in rows:
        owned(db, row, ctx)
        if spec.module == "crm":
            from app.apps.crm.api.router import _get_resource, _apply_record_visibility
            visible = _apply_record_visibility(db.query(model), _get_resource(spec.key), user, db).filter(model.id == row.id).first()
            if not visible:
                raise ValueError("A matching record exists outside your editable scope")
    if len(rows) > 1:
        raise ValueError("Multiple existing matches; resolve duplicates in the module first")
    return rows[0] if rows else None


def preview(db, batch, spec, mapping, options, ctx, user):
    headers, source_rows = batch.table_json["headers"], batch.table_json["rows"]
    field_map = fields_for(spec)
    if any(target not in field_map or source not in headers for target, source in mapping.items()):
        raise HTTPException(422, "Choose valid source columns and destination fields")
    if len(set(mapping.values())) != len(mapping):
        raise HTTPException(422, "A spreadsheet column can only map to one destination field")
    constants = {key:value for key,value in options.get("constants", {}).items() if value != ""}
    if any(key in mapping for key in constants):
        raise HTTPException(422, "Use a mapped column or a fixed value for each field, not both")
    if any(key not in field_map for key in constants):
        raise HTTPException(422, "Unknown fixed-value field")
    edits = options.get("edits", {})
    if any(not key.isdigit() or not 0 <= int(key) < len(source_rows) or any(heading not in headers for heading in values) for key, values in edits.items()):
        raise HTTPException(422, "Invalid row correction")
    missing = [field["label"] for field in spec.fields if field["required"] and field["key"] not in mapping and not constants.get(field["key"])]
    if missing:
        raise HTTPException(422, "Map required fields: " + ", ".join(missing))
    if spec.module == 'crm' and spec.key == 'leads':
        supplied = set(mapping) | {key for key,value in constants.items() if value}
        if 'email' not in supplied and not {'phone','phone_country_code'} <= supplied:
            raise HTTPException(422, 'Map email or both phone and calling code for lead matching')
    if options.get("duplicates", "skip") not in {"skip", "update", "error"}:
        raise HTTPException(422, "Choose a duplicate policy")
    rows, seen, changes = [], set(), {}
    salary_employees, unique_values = set(), set()
    for index, source in enumerate(source_rows):
        errors, suggestions, values = [], [], {}
        row_source = dict(zip(headers, source))
        row_source.update(edits.get(str(index), {}))
        for target in [field["key"] for field in spec.fields if field["key"] in mapping or field["key"] in constants]:
            try:
                raw = constants[target] if target in constants else row_source[mapping[target]]
                value, tips = convert_value(field_map[target], raw, options)
                if value is not None:
                    values[target] = value
                suggestions.extend(f"{field_map[target]['label']}: {tip}" for tip in tips)
            except (ValueError, TypeError) as exc:
                errors.append(f"{field_map[target]['label']}: {exc}")
        row = {"row": batch.table_json["rowNumbers"][index], "values": {key: json_value(value) for key, value in values.items()}, "errors": errors, "suggestions": suggestions, "action": "create", "match_id": None}
        if not errors:
            try:
                prepared = prepare(db, spec, values, ctx, user, check_period=False)
                for key in ("phone", "phone_country_code", "phone_number", "phone_number_country_code"):
                    if key in values and values[key] != prepared.get(key):
                        row["values"][key] = prepared[key]
                        suggestions.append(f"{key}: normalize phone/calling-code format")
                match_fields = identity_fields(spec, prepared)
                identity = tuple(str(prepared.get(key, "")).lower() for key in match_fields)
                if identity in seen:
                    row["action"] = "skip"
                    suggestions.append("Duplicate within this file: later occurrence skipped")
                else:
                    seen.add(identity)
                    match = candidates(db, spec, prepared, ctx, user)
                    if match:
                        row["match_id"] = match.id
                        row["before_hash"] = digest(snapshot(match))
                        row["action"] = options.get("duplicates", "skip")
                        suggestions.append("Existing record found using " + ", ".join(match_fields))
                        if row["action"] == "error":
                            errors.append("Duplicate record found; choose skip or update")
                        if row["action"] == "update":
                            if spec.key in {"opening_stock", "sales_orders", "outstanding_bills", "bank_statements", "attendance", "salaries", "time_entries", "deals"}:
                                raise ValueError("Existing operational records cannot be overwritten here; skip, or revoke the earlier import and remap")
                            RequirePermission(*(("employee_update",) if spec.module == "hrms" else spec.permissions))(user)
                    if not match or row["action"] == "update":
                        prepare(db, spec, values, ctx, user, match)
                    if spec.key == "salaries" and row["action"] == "create":
                        if prepared["employee_id"] in salary_employees:
                            raise ValueError("Import only one open salary assignment per employee; the source contains overlapping salary periods")
                        salary_employees.add(prepared["employee_id"])
                    if row["action"] in {"create", "update"}:
                        from sqlalchemy import UniqueConstraint
                        for constraint in spec.model.__table__.constraints:
                            if not isinstance(constraint, UniqueConstraint):
                                continue
                            keys = [column.key for column in constraint.columns]
                            combination = [prepared.get(key, getattr(match, key, None)) for key in keys]
                            if any(value is None for value in combination):
                                continue
                            signature = (tuple(keys), tuple(str(value) for value in combination))
                            if signature in unique_values:
                                raise ValueError("Conflicting unique values within this file: " + ", ".join(keys))
                            query = db.query(spec.model)
                            for key, value in zip(keys, combination):
                                query = query.filter(getattr(spec.model, key) == value)
                            if match:
                                query = query.filter(spec.model.id != match.id)
                            if query.first():
                                raise ValueError("Existing record conflicts on unique fields: " + ", ".join(keys))
                            unique_values.add(signature)
            except (ValueError, TypeError, HTTPException) as exc:
                errors.append(str(getattr(exc, "detail", exc)))
        if errors:
            row["action"] = "error"
        changes[row["action"]] = changes.get(row["action"], 0) + 1
        rows.append(row)
    result = {"rows": rows, "counts": changes, "total": len(rows), "can_import": bool(rows) and not changes.get("error")}
    batch.mapping_json, batch.options_json, batch.preview_json = mapping, options, result
    batch.status = "previewed"
    batch.version += 1
    return result


def capture(changes, row, before):
    from sqlalchemy.orm import object_session
    object_session(row).refresh(row)
    changes.append({"table": row.__table__.name, "id": row.id, "before": before, "after": snapshot(row)})


def commit(db, batch, spec, ctx, user):
    from sqlalchemy import event
    # Include the canonical contacts/channels created by the suite's existing
    # synchronization listeners. They belong to this import's undo receipt too.
    tracked = {}
    auxiliary = {"crm_contacts", "suite_contact_identity_links", "suite_contact_channels"}
    if spec.module == 'crm' and spec.key == 'leads':
        auxiliary.update({'crm_lead_operating_states','crm_activities','crm_tasks','crm_timeline_events','notifications'})
    def track(session, *_):
        for row in list(session.new | session.dirty):
            if row.__table__.name not in auxiliary or row in tracked:
                continue
            before = None if row in session.new else snapshot(row)
            if before is not None:
                for attribute in inspect(row).mapper.column_attrs:
                    history = inspect(row).attrs[attribute.key].history
                    if history.deleted:
                        before[attribute.key] = json_value(history.deleted[0])
            tracked[row] = before
    event.listen(db, "before_flush", track)
    try:
        counts = _commit(db, batch, spec, ctx, user)
        for _ in range(8):
            db.flush()
            if not db.new:
                break
        changes = list(batch.changes_json or [])
        for row, before in tracked.items():
            capture(changes, row, before)
        batch.changes_json = changes
        return counts
    finally:
        event.remove(db, "before_flush", track)


def _commit(db, batch, spec, ctx, user):
    expected = batch.preview_json
    if batch.status != "previewed" or not expected or not expected["can_import"]:
        raise HTTPException(409, "Map columns and preview without errors before importing")
    # Revalidation catches records changed/created between preview and commit.
    current = preview(db, batch, spec, batch.mapping_json, batch.options_json, ctx, user)
    if digest(current) != digest(expected):
        raise HTTPException(409, "Data changed since preview. Review a fresh preview before importing")
    changes = []
    for row in current["rows"]:
        if row["action"] == "skip":
            continue
        fields = fields_for(spec)
        source = {key: convert_value(fields[key], value, batch.options_json)[0] for key, value in row["values"].items()}
        model = spec.model
        existing = db.query(model).filter(model.id == row["match_id"]).with_for_update().first() if row["match_id"] else None
        if existing and digest(snapshot(existing)) != row["before_hash"]:
            raise HTTPException(409, "A matching record changed; preview again")
        values = prepare(db, spec, source, ctx, user, existing)
        before = snapshot(existing) if existing else None
        if spec.key == "opening_stock":
            from app.apps.srm.models import SRMProduct, SRMInventoryBalance
            from app.apps.srm.api.router import _post_stock_movement
            product = db.query(SRMProduct).filter(SRMProduct.id == values["product_id"]).with_for_update().one()
            balance = db.query(SRMInventoryBalance).filter(SRMInventoryBalance.organization_id == ctx.company_id, SRMInventoryBalance.product_id == product.id, SRMInventoryBalance.warehouse_id == values["warehouse_id"]).with_for_update().first()
            product_before, balance_before = snapshot(product), snapshot(balance) if balance else None
            movement = _post_stock_movement(db, ctx.company_id, product, values["warehouse_id"], "opening_stock", values["quantity_in"], Decimal(0), values["rate"], values["movement_date"], values["movement_number"], "Spreadsheet import", user)
            movement.movement_number = values["movement_number"]
            db.flush()
            balance = db.query(SRMInventoryBalance).filter(SRMInventoryBalance.organization_id == ctx.company_id, SRMInventoryBalance.product_id == product.id, SRMInventoryBalance.warehouse_id == values["warehouse_id"]).one()
            capture(changes, product, product_before)
            capture(changes, balance, balance_before)
            capture(changes, movement, None)
        else:
            if existing:
                # Never overwrite ownership, lifecycle or default values on an update.
                update_fields = set(source) & set(model.__table__.columns.keys())
                if spec.key == "ledgers":
                    update_fields.update(key.replace("opening_", "current_") for key in source if key in {"opening_balance_dr", "opening_balance_cr"})
                for key in update_fields:
                    if key in values:
                        setattr(existing, key, values[key])
                record = existing
            else:
                record = model(**values)
                db.add(record)
            db.flush()
            if spec.module == 'crm' and spec.key == 'leads' and existing is None:
                from app.apps.crm.lead_management import after_existing_api, state
                state(db, record)
                after_existing_api(db, user, record, owner_was_provided=False)
                db.flush()
            capture(changes, record, before)
    batch.changes_json = changes
    batch.status, batch.committed_at = "imported", now()
    batch.version += 1
    return current["counts"]


def restore_value(column, value):
    if value is None:
        return None
    kind = column.type.python_type
    if kind in (date, datetime):
        return kind.fromisoformat(value)
    if kind is Decimal:
        return Decimal(value)
    return value


def revoke(db, batch):
    from app.db.base_class import Base
    if batch.status != "imported":
        raise HTTPException(409, "Only a completed import can be revoked")
    # Collapse repeated edits (e.g. several stock rows updating one product).
    consolidated = {}
    for change in batch.changes_json or []:
        key = (change["table"], change["id"])
        if key in consolidated:
            consolidated[key]["after"] = change["after"]
        else:
            consolidated[key] = dict(change)
    for (table, identity), change in consolidated.items():
        row = db.query(model_for_table(table)).filter_by(id=identity).with_for_update().first()
        if row is None or digest(snapshot(row)) != digest(change["after"]):
            raise HTTPException(409, "Revoke blocked: an imported record was changed or removed. No records were revoked")
        if table in {"employee_salaries", "attendances"}:
            from app.models.payroll import PayrollRecord, PayrollRun
            effective = row.effective_from if table == "employee_salaries" else row.attendance_date
            query = db.query(PayrollRecord).join(PayrollRun,PayrollRecord.payroll_run_id == PayrollRun.id).filter(PayrollRecord.employee_id == row.employee_id, PayrollRun.deleted_at.is_(None))
            month = PayrollRun.year * 12 + PayrollRun.month
            query = query.filter(month >= effective.year * 12 + effective.month) if table == "employee_salaries" else query.filter(month == effective.year * 12 + effective.month)
            if query.first():
                raise HTTPException(409,"Revoke blocked: payroll records use this employee's salary or attendance period. Review payroll dependencies first. No records were revoked")
    for (table, identity), change in reversed(list(consolidated.items())):
        model = model_for_table(table)
        row = db.get(model, identity)
        if change["before"] is None:
            for child in Base.metadata.tables.values():
                for column in child.columns:
                    for fk in column.foreign_keys:
                        if fk.column.table.name == table and fk.column.name == "id":
                            child_model = model_for_table(child.name)
                            if db.query(child_model).filter(getattr(child_model, column.key) == identity).first():
                                raise HTTPException(409, "Revoke blocked: imported records are used by other records. Remove those dependencies first. No records were revoked")
            db.delete(row)
        else:
            for column in model.__table__.columns:
                setattr(row, column.key, restore_value(column, change["before"][column.key]))
        db.flush()
    batch.status, batch.revoked_at = "revoked", now()
    batch.version += 1
