"""Bind employee document capabilities to the current, authorized source record."""
from fastapi import HTTPException


def document_claim(value):
    if not isinstance(value, dict) or any(type(value.get(key)) is not int or value[key] <= 0
                                          for key in ("id", "employee_id")):
        return None
    if {"template_id", "is_signed", "document_name"} <= value.keys():
        table = "generated_documents"
    elif {"certificate_type", "category"} <= value.keys():
        table = "employee_certificates"
    elif {"document_type", "is_verified"} <= value.keys():
        table = "employee_documents"
    else:
        return None
    return {"table": table, "id": value["id"], "employee_id": value["employee_id"]}


def validate_document(db, user, claim, relative):
    from app.models.document import GeneratedDocument, EmployeeCertificate
    from app.models.employee import EmployeeDocument, Employee
    from app.access.catalog import permission_names

    models = {m.__tablename__: m for m in (GeneratedDocument, EmployeeCertificate, EmployeeDocument)}
    if not isinstance(claim, dict) or claim.get("table") not in models or any(
        type(claim.get(key)) is not int or claim[key] <= 0 for key in ("id", "employee_id")
    ):
        raise HTTPException(403, "Invalid document file reference")
    model = models[claim["table"]]
    # Current company, branch and record-scope guards apply to these fresh queries.
    row = db.query(model).filter(model.id == claim["id"], model.employee_id == claim["employee_id"],
                                 model.file_url == "/uploads/" + relative).populate_existing().first()
    employee = db.query(Employee).filter(Employee.id == claim["employee_id"],
                                         Employee.deleted_at.is_(None)).first()
    if row is None or employee is None:
        raise HTTPException(403, "Document access changed; open the record again")
    if user.is_superuser:
        return
    permissions = permission_names(user)
    elevated = ({"employee_update", "employee_sensitive_view"} if model is GeneratedDocument
                else {"employee_view"})
    if not elevated.intersection(permissions) and employee.user_id != user.id:
        raise HTTPException(403, "Document is outside your authorized employee scope")
