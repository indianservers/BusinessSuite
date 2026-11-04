"""Archive generated PDF/spreadsheet responses, including endpoints that never wrote a file."""
import re
from email.message import Message
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.audit_context import context
from app.core.config import settings
from app.services.file_storage import retain_generated, module_for


def should_archive(request, response):
    evidence = context.get() or {}
    if evidence.get("file_response_path") or response.status_code != 200:
        return False
    if not evidence.get("actor", {}).get("access_company"):
        return False
    if request.url.path.startswith(("/api/v1/files/", "/api/v1/files-storage/")):
        return False
    kind = response.headers.get("content-type", "").split(";")[0]
    return (kind == "application/pdf" or "export" in request.url.path.lower()) and bool(response.headers.get("content-disposition"))


def archive(body, content_disposition):
    evidence = context.get() or {}
    original = evidence.get("storage_session")
    if original is None or not body: return
    header = Message()
    header["content-disposition"] = content_disposition
    name = header.get_filename() or "document.pdf"
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r"[\r\n\x00]", "", name)[:180] or "document"
    # Independent metadata transaction: never commit the endpoint's business work.
    with Session(bind=original.get_bind()) as db:
        module = module_for(str(settings.UPLOAD_DIR) + "/exports/" + name, evidence.get("actor", {}))
        retain_generated(db, module, name, body)
