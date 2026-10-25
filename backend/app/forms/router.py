"""Reusable forms plugin: private management, versioned public snapshots, guarded intake."""

import base64, csv, hashlib, hmac, io, json, secrets, time
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from typing import Literal
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import update, or_, cast, Text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw, ImageFont
from app.core.deps import get_db, get_current_user
from app.core.config import settings
from app.common.services.identity import SharedIdentityService
from app.module_registry import is_app_enabled
from .models import SuiteForm, FormReply, FormFile, FormChallenge, FormRateBucket
from .schema import Strict, clean_answers
from .settings import FormDefinition
from . import integrations


def no_store(response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"


router = APIRouter(
    prefix="/forms", tags=["Shared forms"], dependencies=[Depends(no_store)]
)
MODULES = {
    "pms": "project_management",
    "crm": "crm",
    "srm": "srm",
    "hrms": "hrms",
    "fam": "fam",
}


def org(user):
    return (
        getattr(user, "organization_id", None)
        or SharedIdentityService.organization_id_for_user(user)
        or 1
    )


def module(key, db=None, organization_id=1):
    if key not in MODULES or not is_app_enabled(MODULES[key]):
        raise HTTPException(404, "Module unavailable")
    if db is not None:
        from app.apps.business_os.models import BOSEnabledModule

        disabled = (
            db.query(BOSEnabledModule)
            .filter_by(
                company_id=organization_id, module_key=MODULES[key], enabled=False
            )
            .first()
        )
        if disabled:
            raise HTTPException(404, "Module unavailable")


def owned(db, fid, user):
    row = db.query(SuiteForm).filter_by(id=fid, organization_id=org(user)).first()
    allowed = row and row.owner_id == user.id
    if row and row.legacy_entry_id and row.workspace_id:
        from app.apps.project_management.models import PMSWorkspaceMember

        allowed = allowed or bool(
            db.query(PMSWorkspaceMember)
            .filter_by(workspace_id=row.workspace_id, user_id=user.id)
            .filter(PMSWorkspaceMember.role.in_(["Owner", "Admin"]))
            .first()
        )
    if not allowed:
        raise HTTPException(404, "Form not found")
    module(row.module_key, db, row.organization_id)
    return row


def count(db, fid):
    return db.query(FormReply).filter_by(form_id=fid).count()


def output(db, row):
    return {
        "id": row.id,
        "module_key": row.module_key,
        "legacy_entry_id": row.legacy_entry_id,
        "draft": row.draft,
        "published": row.published,
        "revision": row.revision,
        "version": row.version,
        "slug": row.slug,
        "open": row.open,
        "responses": count(db, row.id),
        "updated_at": row.updated_at,
    }


def migrate_legacy(db, user):
    # Import through source membership; drafts and responses remain restricted to administrators.
    from app.apps.project_management.models import (
        PMSWorkspaceEntry,
        PMSWorkspace,
        PMSWorkspaceMember,
    )

    entries = (
        db.query(PMSWorkspaceEntry)
        .join(PMSWorkspace, PMSWorkspace.id == PMSWorkspaceEntry.workspace_id)
        .join(PMSWorkspaceMember, PMSWorkspaceMember.workspace_id == PMSWorkspace.id)
        .filter(
            PMSWorkspaceEntry.kind == "form_v2",
            PMSWorkspaceMember.user_id == user.id,
            PMSWorkspaceMember.role != "Guest",
            or_(
                PMSWorkspace.organization_id == org(user),
                PMSWorkspace.organization_id.is_(None),
            ),
        )
        .all()
    )
    for entry in entries:
        try:
            with db.begin_nested():
                row = db.query(SuiteForm).filter_by(legacy_entry_id=entry.id).first()
                if row:
                    import_legacy_replies(db, row, entry)
                    continue
                data = json.loads(entry.body)
                draft = FormDefinition.model_validate(data["draft"]).model_dump(
                    mode="json"
                )
                published = (
                    FormDefinition.model_validate(data["published"]).model_dump(
                        mode="json"
                    )
                    if data.get("published")
                    else None
                )
                row = SuiteForm(
                    organization_id=org(user),
                    owner_id=entry.author_id,
                    module_key="pms",
                    legacy_entry_id=entry.id,
                    workspace_id=entry.workspace_id,
                    name=draft["name"],
                    draft=draft,
                    published=published,
                    revision=data.get("revision", 1),
                    version=data.get("version", 0),
                    open=data.get("open", False),
                    slug=secrets.token_urlsafe(24),
                )
                db.add(row)
                db.flush()
                import_legacy_replies(db, row, entry)
        except IntegrityError:
            # Another request imported the same immutable legacy IDs.
            db.expire_all()
    db.commit()


def import_legacy_replies(db, row, entry):
    from app.apps.project_management.models import PMSWorkspaceEntry

    for reply in db.query(PMSWorkspaceEntry).filter_by(
        workspace_id=entry.workspace_id, kind="form_reply"
    ):
        if db.query(FormReply).filter_by(legacy_entry_id=reply.id).first():
            continue
        saved = json.loads(reply.body)
        if saved.get("form_id") != entry.id:
            continue
        db.add(
            FormReply(
                form_id=row.id,
                legacy_entry_id=reply.id,
                request_id=str(saved.get("key", uuid4())),
                version=saved.get("version", 1),
                answers=saved.get("answers", {}),
                labels=saved.get("labels", {}),
                status="new",
                task_id=reply.task_id,
                submitted_at=reply.created_at,
            )
        )


class Create(Strict):
    module_key: str
    definition: FormDefinition


class Save(Strict):
    revision: int = Field(ge=1)
    definition: FormDefinition
    publish: bool = False
    close: bool = False


@router.get("")
def list_forms(
    module_key: str = "pms",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    module(module_key, db, org(user))
    if module_key == "pms":
        migrate_legacy(db, user)
    q = db.query(SuiteForm).filter_by(organization_id=org(user), module_key=module_key)
    access = SuiteForm.owner_id == user.id
    if module_key == "pms":
        from app.apps.project_management.models import PMSWorkspaceMember

        workspace_ids = db.query(PMSWorkspaceMember.workspace_id).filter(
            PMSWorkspaceMember.user_id == user.id, PMSWorkspaceMember.role != "Guest"
        )
        access = or_(access, SuiteForm.workspace_id.in_(workspace_ids))
    rows = []
    for row in q.filter(access).order_by(SuiteForm.id.desc()).limit(500):
        admin = row.owner_id == user.id
        if row.workspace_id and module_key == "pms":
            member = (
                db.query(PMSWorkspaceMember)
                .filter_by(workspace_id=row.workspace_id, user_id=user.id)
                .first()
            )
            admin = admin or bool(member and member.role in {"Owner", "Admin"})
        if admin:
            rows.append(output(db, row))
        elif row.published:
            d = FormDefinition.model_validate(row.published).model_dump(mode="json")
            d.pop("workflow", None)
            for field in d["fields"]:
                field.pop("global_field_id", None)
            rows.append(
                {
                    "id": row.id,
                    "module_key": row.module_key,
                    "draft": d,
                    "published": d,
                    "version": row.version,
                    "open": available(db, row),
                    "read_only": True,
                    "legacy_entry_id": row.legacy_entry_id,
                    "responses": 0,
                    "slug": row.slug,
                }
            )
    return rows


@router.get("/catalog")
def catalog(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.customization.models import (
        CustomizationField,
        CustomizationFieldOption,
    )

    mapping = {
        "text": "text",
        "string": "text",
        "textarea": "textarea",
        "long_text": "textarea",
        "email": "email",
        "phone": "phone",
        "url": "url",
        "number": "number",
        "integer": "number",
        "decimal": "number",
        "date": "date",
        "dropdown": "select",
        "select": "select",
        "picklist": "select",
        "multiselect": "multiselect",
        "boolean": "checkbox",
        "checkbox": "checkbox",
    }
    result = []
    for f in (
        db.query(CustomizationField)
        .filter_by(visible=True, editable=True)
        .order_by(CustomizationField.module_name, CustomizationField.field_label)
        .limit(1000)
    ):
        kind = mapping.get(f.field_type.lower())
        if not kind:
            continue
        opts = [
            o.label
            for o in db.query(CustomizationFieldOption)
            .filter_by(field_id=f.id, active=True)
            .order_by(CustomizationFieldOption.order_index)
        ]
        if kind in {"select", "multiselect"} and not opts:
            continue
        result.append(
            {
                "id": f.id,
                "module_name": f.module_name,
                "api_name": f.field_api_name,
                "label": f.field_label,
                "type": kind,
                "required": f.required,
                "help": f.help_text or "",
                "options": opts,
            }
        )
    return result


@router.get("/options")
def integration_options(
    module_key: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    module(module_key, db, org(user))
    return integrations.options(db, user, module_key)


def validate_definition(data, db, user, module_key):
    integrations.validate(db, data, user, module_key)
    if data.settings.captcha == "turnstile" and not (
        settings.FORMS_TURNSTILE_SITE_KEY and settings.FORMS_TURNSTILE_SECRET_KEY
    ):
        raise HTTPException(
            422,
            "Configure FORMS_TURNSTILE_SITE_KEY and FORMS_TURNSTILE_SECRET_KEY first",
        )


@router.post("/validate")
def validate_import(data: FormDefinition, user=Depends(get_current_user)):
    return data.model_dump(mode="json")


@router.post("", status_code=201)
def create(data: Create, db: Session = Depends(get_db), user=Depends(get_current_user)):
    module(data.module_key, db, org(user))
    validate_definition(data.definition, db, user, data.module_key)
    if db.query(SuiteForm).filter_by(owner_id=user.id).count() >= 500:
        raise HTTPException(422, "Limit: 500 forms per owner")
    row = SuiteForm(
        organization_id=org(user),
        owner_id=user.id,
        module_key=data.module_key,
        name=data.definition.name,
        draft=data.definition.model_dump(mode="json"),
        slug=secrets.token_urlsafe(24),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return output(db, row)


@router.get("/{fid:int}")
def get_form(fid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return output(db, owned(db, fid, user))


@router.put("/{fid:int}")
def save(
    fid: int, data: Save, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    row = owned(db, fid, user)
    validate_definition(data.definition, db, user, row.module_key)
    values = {
        "name": data.definition.name,
        "draft": data.definition.model_dump(mode="json"),
        "revision": data.revision + 1,
        "updated_at": datetime.now(timezone.utc),
    }
    if data.publish:
        values.update(published=values["draft"], version=row.version + 1, open=True)
    if data.close:
        values["open"] = False
    if (
        db.execute(
            update(SuiteForm)
            .where(SuiteForm.id == fid, SuiteForm.revision == data.revision)
            .values(**values)
        ).rowcount
        != 1
    ):
        db.rollback()
        raise HTTPException(
            409, "This form changed in another tab. Reload before saving."
        )
    db.commit()
    db.expire_all()
    return output(db, owned(db, fid, user))


def reply_out(r):
    return {
        "id": r.id,
        "version": r.version,
        "answers": r.answers,
        "labels": r.labels,
        "submitted_at": r.submitted_at,
        "status": r.status,
        "task_id": r.task_id,
    }


@router.get("/{fid:int}/responses")
def responses(
    fid: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    q: str = Query("", max_length=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    owned(db, fid, user)
    query = db.query(FormReply).filter_by(form_id=fid)
    if q:
        pattern = (
            json.dumps(q, ensure_ascii=True)[1:-1]
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        query = query.filter(
            cast(FormReply.answers, Text).ilike("%" + pattern + "%", escape="\\")
        )
    return {
        "total": query.count(),
        "items": [
            reply_out(r)
            for r in query.order_by(FormReply.id.desc()).offset(offset).limit(limit)
        ],
    }


class ReplyStatus(Strict):
    status: str = Field(pattern="^(new|reviewed|archived)$")


@router.patch("/{fid:int}/responses/{rid:int}")
def reply_status(
    fid: int,
    rid: int,
    data: ReplyStatus,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    owned(db, fid, user)
    r = db.query(FormReply).filter_by(id=rid, form_id=fid).first()
    if not r:
        raise HTTPException(404, "Response not found")
    r.status = data.status
    db.commit()
    return reply_out(r)


@router.get("/{fid:int}/export")
def export(
    fid: int,
    format: Literal["csv", "json"] = "csv",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    owned(db, fid, user)
    rows = db.query(FormReply).filter_by(form_id=fid).order_by(FormReply.id).all()
    if format == "json":
        return Response(
            json.dumps([reply_out(r) for r in rows], default=str, ensure_ascii=False),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="form-{fid}-responses.json"',
                "Cache-Control": "no-store",
            },
        )
    keys = list(dict.fromkeys(k for r in rows for k in r.answers))
    labels = {k: v for r in rows for k, v in r.labels.items()}

    def safe(v):
        t = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)
        return "'" + t if t.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else t

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID", "Submitted", "Status"] + [safe(labels.get(k, k)) for k in keys])
    for r in rows:
        w.writerow(
            [r.id, r.submitted_at, r.status]
            + [safe(r.answers.get(k, "")) for k in keys]
        )
    return Response(
        "\ufeff" + buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="form-{fid}-responses.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{fid:int}/files/{file_id}")
def file_download(
    fid: int,
    file_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    owned(db, fid, user)
    f = (
        db.query(FormFile)
        .join(FormReply, FormReply.id == FormFile.reply_id)
        .filter(FormFile.id == file_id, FormReply.form_id == fid)
        .first()
    )
    if not f:
        raise HTTPException(404, "File not found")
    from urllib.parse import quote

    return Response(
        f.body,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(f.filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


def public_row(db, slug):
    row = db.query(SuiteForm).filter_by(slug=slug).first()
    if (
        not row
        or not row.published
        or not row.published.get("settings", {}).get("public")
    ):
        raise HTTPException(404, "Public form not found")
    module(row.module_key, db, row.organization_id)
    return row


def available(db, row):
    d = FormDefinition.model_validate(row.published)
    if not row.open:
        return False
    if d.settings.closes_at and (
        d.settings.closes_at
        if d.settings.closes_at.tzinfo
        else d.settings.closes_at.replace(tzinfo=timezone.utc)
    ) <= datetime.now(timezone.utc):
        return False
    if d.settings.max_responses and count(db, row.id) >= d.settings.max_responses:
        return False
    return True


@router.get("/public/{slug}")
def public_form(slug: str, db: Session = Depends(get_db)):
    row = public_row(db, slug)
    d = FormDefinition.model_validate(row.published).model_dump(mode="json")
    d.pop("workflow", None)
    for f in d["fields"]:
        f.pop("global_field_id", None)
    return {
        "definition": d,
        "version": row.version,
        "open": available(db, row),
        "site_key": (
            settings.FORMS_TURNSTILE_SITE_KEY
            if d["settings"]["captcha"] == "turnstile"
            else None
        ),
    }


def digest(value):
    return hmac.new(
        settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def ip_key(request):
    return digest(request.client.host if request.client else "unknown")


def throttle(db, request, fid, kind, maximum):
    window = int(time.time() // 600)
    key = digest(f"{ip_key(request)}:{fid}:{kind}:{window}")
    # Atomic upsert for both supported databases; counters are durable across workers.
    dialect = db.bind.dialect.name
    if dialect in {"sqlite", "postgresql"}:
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert
        stmt = insert(FormRateBucket).values(key=key, window=window, attempts=1)
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=["key"], set_={"attempts": FormRateBucket.attempts + 1}
            )
        )
        db.commit()
    else:
        raise HTTPException(503, "Rate limiting unavailable")
    if db.get(FormRateBucket, key).attempts > maximum:
        raise HTTPException(429, "Too many attempts. Try again in ten minutes.")
    db.query(FormRateBucket).filter(FormRateBucket.window < window - 2).delete(
        synchronize_session=False
    )
    db.query(FormChallenge).filter(
        FormChallenge.expires_at < datetime.now(timezone.utc) - timedelta(hours=1)
    ).delete(synchronize_session=False)
    db.commit()


def new_code():
    return "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


@router.get("/public/{slug}/challenge")
def challenge(slug: str, request: Request, db: Session = Depends(get_db)):
    row = public_row(db, slug)
    if not available(db, row):
        raise HTTPException(410, "This form is closed")
    throttle(db, request, row.id, "challenge", 30)
    code = new_code()
    ident = uuid4().hex
    img = Image.new("RGB", (240, 80), (246, 244, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 32)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except OSError:
            font = ImageFont.load_default(size=30)
    for i, c in enumerate(code):
        draw.text(
            (14 + i * 36, 18 + secrets.randbelow(10)),
            c,
            font=font,
            fill=(55 + secrets.randbelow(50), 35, 130),
        )
    for _ in range(8):
        draw.line(
            (
                secrets.randbelow(240),
                secrets.randbelow(80),
                secrets.randbelow(240),
                secrets.randbelow(80),
            ),
            fill=(150, 135, 195),
            width=1,
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    db.add(
        FormChallenge(
            id=ident,
            form_id=row.id,
            answer_hash=digest(ident + code),
            ip_hash=ip_key(request),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    )
    db.commit()
    return {
        "id": ident,
        "image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
        "expires_in": 300,
    }


class Upload(Strict):
    filename: str = Field(min_length=1, max_length=200)
    data: str = Field(max_length=2800000)


class Submission(Strict):
    request_id: UUID
    version: int = Field(gt=0)
    answers: dict = Field(default_factory=dict, max_length=60)
    files: dict[str, Upload] = Field(default_factory=dict, max_length=3)
    website: str = Field(default="", max_length=200)
    challenge_id: str = Field(default="", max_length=32)
    captcha_answer: str = Field(default="", max_length=20)
    turnstile_token: str = Field(default="", max_length=2048)


@router.post("/public/{slug}/submit", status_code=201)
def submit(
    slug: str, data: Submission, request: Request, db: Session = Depends(get_db)
):
    return accept_response(public_row(db, slug), data, request, db)


def accept_response(row, data, request, db, actor=None):
    if data.website:
        raise HTTPException(422, "Submission rejected")
    throttle(db, request, row.id, "submit", 20)
    prior = (
        db.query(FormReply)
        .filter_by(form_id=row.id, request_id=str(data.request_id))
        .first()
    )
    if prior:
        return {"ok": True, "message": row.published["success_message"]}
    if not available(db, row):
        raise HTTPException(410, "This form is closed")
    if data.version != row.version:
        raise HTTPException(409, "Form changed. Reload and try again.")
    definition = FormDefinition.model_validate(row.published)
    if actor is None:
        if definition.settings.captcha == "turnstile":
            try:
                checked = httpx.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    data={
                        "secret": settings.FORMS_TURNSTILE_SECRET_KEY,
                        "response": data.turnstile_token,
                    },
                    timeout=10,
                ).json()
            except Exception:
                raise HTTPException(
                    503, "Spam verification unavailable. Try again later."
                )
            if not checked.get("success"):
                raise HTTPException(422, "Complete the spam verification")
        else:
            c = db.get(FormChallenge, data.challenge_id)
            if (
                not c
                or c.form_id != row.id
                or c.ip_hash != ip_key(request)
                or not hmac.compare_digest(
                    c.answer_hash, digest(c.id + data.captcha_answer.upper().strip())
                )
            ):
                raise HTTPException(
                    422, "Incorrect security code. Refresh the code and try again."
                )
            used = db.execute(
                update(FormChallenge)
                .where(
                    FormChallenge.id == c.id,
                    FormChallenge.used.is_(False),
                    FormChallenge.expires_at > datetime.now(timezone.utc),
                )
                .values(used=True)
                .execution_options(synchronize_session=False)
            ).rowcount
            db.commit()
            if used != 1:
                raise HTTPException(
                    422, "Security code expired or already used. Refresh it."
                )
    answers = dict(data.answers)
    pending = []
    total = 0
    fields = {f.id: f for f in definition.fields}
    for key, upload in data.files.items():
        if key not in fields or fields[key].type != "file":
            raise HTTPException(422, "Unknown upload field")
        try:
            body = base64.b64decode(upload.data, validate=True)
        except Exception:
            raise HTTPException(422, "Invalid upload")
        total += len(body)
        if not body or len(body) > 2 * 1024 * 1024 or total > 3 * 1024 * 1024:
            raise HTTPException(413, "Upload limit: 2 MB per file, 3 MB total")
        name = upload.filename.replace("\\", "/").split("/")[-1]
        ext = name.rsplit(".", 1)[-1].lower()
        valid = (
            (ext == "pdf" and body.startswith(b"%PDF-"))
            or (ext == "png" and body.startswith(b"\x89PNG\r\n\x1a\n"))
            or (ext in {"jpg", "jpeg"} and body.startswith(b"\xff\xd8\xff"))
        )
        if not valid:
            raise HTTPException(
                422, "Allowed uploads: PDF, PNG or JPEG with matching file content"
            )
        ident = uuid4().hex
        answers[key] = "file:" + ident
        pending.append((key, ident, name, body))
    clean = clean_answers(definition, answers)
    if any(
        f.type == "file" and clean.get(f.id) and f.id not in data.files
        for f in definition.fields
    ):
        raise HTTPException(422, "Attach the file with this response")
    # Reserve a revision atomically, serializing capacity/close/publish races on SQLite and PostgreSQL.
    if (
        db.execute(
            update(SuiteForm)
            .where(
                SuiteForm.id == row.id,
                SuiteForm.revision == row.revision,
                SuiteForm.version == data.version,
                SuiteForm.open.is_(True),
            )
            .values(revision=SuiteForm.revision)
        ).rowcount
        != 1
    ):
        db.rollback()
        raise HTTPException(409, "Form changed. Reload and retry.")
    db.refresh(row)
    if (
        db.query(FormReply)
        .filter_by(form_id=row.id, request_id=str(data.request_id))
        .first()
    ):
        db.rollback()
        return {"ok": True, "message": definition.success_message}
    if not available(db, row):
        db.rollback()
        raise HTTPException(410, "This form is closed")
    from app.models.user import User

    owner = db.get(User, row.owner_id)
    if not owner or not owner.is_active:
        raise HTTPException(410, "Form owner is unavailable")
    task_id = integrations.on_response(
        db, definition, clean, owner, row.module_key, data.request_id
    )
    r = FormReply(
        task_id=task_id,
        form_id=row.id,
        request_id=str(data.request_id),
        version=row.version,
        answers=clean,
        labels={f.id: f.label for f in definition.fields if f.id in clean},
        status="new",
    )
    db.add(r)
    try:
        db.flush()
        for key, ident, name, body in pending:
            if key in clean:
                db.add(
                    FormFile(
                        id=ident,
                        reply_id=r.id,
                        field_id=key,
                        filename=name,
                        media_type="application/octet-stream",
                        body=body,
                    )
                )
        db.commit()
    except IntegrityError:
        db.rollback()
        if (
            not db.query(FormReply)
            .filter_by(form_id=row.id, request_id=str(data.request_id))
            .first()
        ):
            raise
    return {"ok": True, "message": definition.success_message}


def internal_row(db, fid, user):
    row = db.query(SuiteForm).filter_by(id=fid, organization_id=org(user)).first()
    allowed = row and row.owner_id == user.id
    if row and row.workspace_id and row.legacy_entry_id:
        from app.apps.project_management.models import PMSWorkspaceMember

        allowed = allowed or bool(
            db.query(PMSWorkspaceMember)
            .filter_by(workspace_id=row.workspace_id, user_id=user.id)
            .filter(PMSWorkspaceMember.role != "Guest")
            .first()
        )
    if not allowed or not row.published:
        raise HTTPException(404, "Internal form not found")
    module(row.module_key, db, row.organization_id)
    return row


@router.get("/{fid:int}/internal")
def internal_form(
    fid: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    row = internal_row(db, fid, user)
    d = FormDefinition.model_validate(row.published).model_dump(mode="json")
    d.pop("workflow", None)
    for f in d["fields"]:
        f.pop("global_field_id", None)
    return {"definition": d, "version": row.version, "open": available(db, row)}


@router.post("/{fid:int}/internal/submit", status_code=201)
def internal_submit(
    fid: int,
    data: Submission,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return accept_response(internal_row(db, fid, user), data, request, db, actor=user)
