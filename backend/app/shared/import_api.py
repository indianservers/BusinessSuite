"""One import workspace for CRM, Sales, HRMS, PMS and Finance."""
import io
from uuid import uuid4
from typing import Any, Literal
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from app.core.deps import get_current_user, get_db
from app.shared.import_models import ImportBatch
from app.shared.import_catalog import SPECS
from app.shared import import_service as service
from app.shared.data_transfer import inspect_file, spreadsheet_cell

router = APIRouter(prefix="/imports", tags=["Import workspace"])


class PreviewRequest(BaseModel):
    version: int
    mapping: dict[str, str]
    duplicates: Literal["skip", "update", "error"] = "skip"
    trim: bool = True
    email_case: bool = True
    numbers: bool = True
    edits: dict[str, dict[str, str]] = Field(default_factory=dict)
    constants: dict[str, str] = Field(default_factory=dict)


class VersionRequest(BaseModel):
    version: int


def receipt(batch, detail=False):
    result = {key: getattr(batch, key) for key in ("id", "module", "entity", "filename", "source", "status", "version", "created_at", "committed_at", "revoked_at")}
    result["counts"] = (batch.preview_json or {}).get("counts", {})
    if detail:
        result.update(table=batch.table_json, mapping=batch.mapping_json or {}, options=batch.options_json or {}, preview=batch.preview_json)
    return result


def batch_for(db, module, identity, user, request, version=None):
    batch = db.query(ImportBatch).filter_by(id=identity, module=module, created_by=user.id).with_for_update().first()
    if batch is None:
        raise HTTPException(404, "Import not found")
    spec = service.spec_or_404(module, batch.entity)
    ctx = service.authorize(db, user, spec, request)
    if batch.organization_id != ctx.company_id or batch.branch_id != ctx.branch_id:
        raise HTTPException(404, "Import not found in the selected company and branch")
    if version is not None and version != batch.version:
        raise HTTPException(409, "Import changed in another window. Reload and review it again")
    return batch, spec, ctx


@router.get("/{module}/catalog")
def catalog(module: str, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = []
    for spec in SPECS:
        if spec.module != module:
            continue
        try:
            service.authorize(db, user, spec, request)
        except HTTPException as exc:
            if exc.status_code in (403, 404):
                continue
            raise
        result.append({"key": spec.key, "label": spec.label, "fields": spec.fields, "identity": spec.identity, "note": spec.note})
    return result


@router.get("/{module}/template/{entity}")
def template(module: str, entity: str, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    spec = service.spec_or_404(module, entity)
    service.authorize(db, user, spec, request)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = spec.key[:31]
    sheet.append([field["key"] for field in spec.fields])
    sheet.append([spreadsheet_cell(field["sample"]) for field in spec.fields])
    for index, field in enumerate(spec.fields, 1):
        cell = sheet.cell(1, index)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="253858")
        sheet.column_dimensions[get_column_letter(index)].width = max(20, min(42, len(str(field["sample"])) + 3,))
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    guide = workbook.create_sheet("Instructions")
    for row in [["Import type", spec.label], ["Before importing", "Replace sample data. Map every required field, then preview before importing."], ["Linked records", "Replace example IDs with existing records in your selected company and branch."], ["Record matching", ", ".join(spec.identity)], ["Notes", spec.note], ["Revoke", "History can revoke unchanged imports. Later edits or dependencies block revoke."], ["Field", "Required", "Format"]]:
        guide.append(row)
    for field in spec.fields:
        guide.append([field["key"], "Yes" if field["required"] else "No", field["type"]])
    guide.column_dimensions["A"].width = 28
    guide.column_dimensions["B"].width = 110
    guide.column_dimensions["C"].width = 20
    output = io.BytesIO()
    workbook.save(output)
    return Response(output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{module}-{entity}-template.xlsx"', "Cache-Control": "no-store"})


@router.get("/{module}/lookups/{entity}")
def lookups(module: str, entity: str, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    spec = service.spec_or_404(module, entity)
    ctx = service.authorize(db,user,spec,request)
    result = {}
    for field in spec.fields:
        column = spec.model.__table__.columns.get(field["key"])
        if column is None or not column.foreign_keys:
            continue
        fk = next(iter(column.foreign_keys))
        if fk.column.table.name == "users":
            continue
        parent = service.model_for_table(fk.column.table.name)
        choices=[]
        for row in db.query(parent).limit(200).all():
            try:
                service.owned(db,row,ctx)
            except ValueError:
                continue
            label = next((str(getattr(row,key)) for key in ("full_name","name","legal_name","item_name","warehouse_name","group_name","ledger_name","imported_file_name") if getattr(row,key,None)), str(row.id))
            choices.append({"value":str(row.id),"label":label})
        result[field["key"]]=choices
    return result


@router.post("/{module}/upload")
async def upload(module: str, request: Request, entity: str = Form(...), sheet: str = Form(""), header_row: int = Form(1), file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    spec = service.spec_or_404(module, entity)
    ctx = service.authorize(db, user, spec, request)
    table = await inspect_file(file, sheet, header_row)
    batch = ImportBatch(id=str(uuid4()), organization_id=ctx.company_id, branch_id=ctx.branch_id, module=module, entity=entity, filename=(file.filename or "upload")[:220], source="spreadsheet", created_by=user.id, table_json=table)
    db.add(batch)
    db.commit()
    return receipt(batch, True)


@router.get("/{module}/history")
def history(module: str, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    allowed = catalog(module, request, db, user)
    if not allowed:
        raise HTTPException(403, "Import access is unavailable")
    spec = service.spec_or_404(module, allowed[0]["key"])
    ctx = service.authorize(db, user, spec, request)
    return [receipt(batch) for batch in db.query(ImportBatch).filter(ImportBatch.module == module, ImportBatch.organization_id == ctx.company_id, ImportBatch.branch_id == ctx.branch_id, ImportBatch.created_by == user.id, ImportBatch.entity.in_([item["key"] for item in allowed])).order_by(ImportBatch.created_at.desc()).limit(100)]


@router.get("/{module}/batches/{identity}")
def detail(module: str, identity: str, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return receipt(batch_for(db, module, identity, user, request)[0], True)


@router.post("/{module}/batches/{identity}/preview")
def preview(module: str, identity: str, data: PreviewRequest, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    batch, spec, ctx = batch_for(db, module, identity, user, request, data.version)
    if batch.status not in ("uploaded", "previewed"):
        raise HTTPException(409, "Revoke a completed import before correcting its mapping")
    options = data.model_dump(exclude={"version", "mapping"})
    try:
        with db.begin_nested():
            service.preview(db, batch, spec, data.mapping, options, ctx, user)
    except StaleDataError:
        raise HTTPException(409,"Import changed in another window. Reload and preview again")
    db.commit()
    return receipt(batch, True)


@router.post("/{module}/batches/{identity}/commit")
def commit(module: str, identity: str, data: VersionRequest, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    batch, spec, ctx = batch_for(db, module, identity, user, request, data.version)
    try:
        with db.begin_nested():
            service.commit(db, batch, spec, ctx, user)
    except (IntegrityError, StaleDataError):
        raise HTTPException(409,"Import conflicts with records changed since preview. No rows were imported; review a new preview")
    db.commit()
    return receipt(batch, True)


@router.post("/{module}/batches/{identity}/revoke")
def revoke(module: str, identity: str, data: VersionRequest, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    batch, spec, ctx = batch_for(db, module, identity, user, request, data.version)
    try:
        with db.begin_nested():
            service.revoke(db, batch)
    except (IntegrityError, StaleDataError):
        raise HTTPException(409,"Revoke blocked by a changed or dependent record. No records were revoked")
    db.commit()
    return receipt(batch)


@router.post("/{module}/batches/{identity}/retry")
def retry(module: str, identity: str, data: VersionRequest, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    batch, spec, ctx = batch_for(db, module, identity, user, request, data.version)
    if batch.status != "revoked":
        raise HTTPException(409, "Revoke the import before remapping and trying again")
    fresh = ImportBatch(id=str(uuid4()), organization_id=ctx.company_id, branch_id=ctx.branch_id, module=module, entity=batch.entity, filename=batch.filename, source=batch.source, created_by=user.id, table_json=batch.table_json, mapping_json=batch.mapping_json, options_json=batch.options_json)
    db.add(fresh)
    db.commit()
    return receipt(fresh, True)


class ConnectRequest(BaseModel):
    region: str = "com"


class CompleteConnection(BaseModel):
    provider: Literal["quickbooks", "zoho"]
    state: str = Field(max_length=300)
    code: str = Field(max_length=4096)
    account_id: str = Field(max_length=100)


def finance_context(db, user, request):
    for spec in SPECS:
        if spec.module != "fam":
            continue
        try:
            return service.authorize(db,user,spec,request)
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
    raise HTTPException(403,"Finance import access is required")


@router.get("/fam/connections")
def connections(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.shared.import_models import ImportConnection
    from app.shared.import_connectors import config, PROVIDERS
    ctx = finance_context(db,user,request)
    rows = db.query(ImportConnection).filter_by(organization_id=ctx.company_id, branch_id=ctx.branch_id, created_by=user.id).all()
    return {"providers": [{"key":key,"label":label,"configured":all(config(key).values())} for key,label in PROVIDERS.items()], "connections": [{"id":row.id,"provider":row.provider,"account_id":row.account_id,"region":row.region} for row in rows if row.account_id != "pending"]}


@router.post("/fam/connections/{provider}/start")
def connection_start(provider: str, data: ConnectRequest, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.shared.import_connectors import start
    ctx = finance_context(db,user,request)
    return start(db,user,ctx,provider,data.region)


@router.post("/fam/connections/complete")
def connection_complete(data: CompleteConnection, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.shared.import_connectors import complete
    ctx = finance_context(db,user,request)
    return complete(db,user,ctx,data.provider,data.state,data.code,data.account_id)


@router.delete("/fam/connections/{identity}")
def disconnect(identity: str, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.shared.import_connectors import get_connection
    ctx = finance_context(db,user,request)
    db.delete(get_connection(db,identity,user,ctx))
    db.commit()
    return {"disconnected":True}


class ConnectorFetch(BaseModel):
    entity: Literal["ledgers", "outstanding_bills"]


@router.post("/fam/connections/{identity}/fetch")
def fetch_connection(identity: str, data: ConnectorFetch, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.shared.import_connectors import get_connection, fetch_rows
    ctx = service.authorize(db,user,service.spec_or_404("fam",data.entity),request)
    connection = get_connection(db,identity,user,ctx)
    if connection.account_id == "pending":
        raise HTTPException(409,"Complete authorization first")
    table = fetch_rows(db,connection,data.entity)
    batch = ImportBatch(id=str(uuid4()), organization_id=ctx.company_id, branch_id=ctx.branch_id, module="fam", entity=data.entity, filename=f"{connection.provider}-{connection.account_id}-{data.entity}", source=connection.provider, created_by=user.id, table_json=table)
    db.add(batch)
    db.commit()
    return receipt(batch,True)
