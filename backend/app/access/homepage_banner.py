"""Company-owned launcher appearance, using existing policy and artwork storage."""
import base64
import hashlib
import ipaddress
import re
from io import BytesIO
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.access.settings_hub import context, require_option
from app.access import service
from app.shared.models import ServicePolicy

router = APIRouter(prefix="/homepage-banner", tags=["Homepage appearance"])
GALLERY = {"/images/suite-office-hero.webp", "/images/karya-login-hero.webp"}
MAX_BYTES = 5 * 1024 * 1024


class BannerAppearance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image: str = "/images/suite-office-hero.webp"
    mobile_image: str = ""
    x: float = Field(70, ge=0, le=100)
    y: float = Field(50, ge=0, le=100)
    mobile_x: float = Field(75, ge=0, le=100)
    mobile_y: float = Field(50, ge=0, le=100)
    zoom: float = Field(1, ge=1, le=3)
    overlay: str = Field("#eeedff", pattern=r"^#[0-9a-fA-F]{6}$")
    opacity: float = Field(.15, ge=0, le=1)

    @field_validator("image", "mobile_image")
    @classmethod
    def image_reference(cls, value):
        if not value or value in GALLERY or re.fullmatch(r"asset:[0-9]+-[a-f0-9]{64}", value):
            return value
        if len(value) > 2000:
            raise ValueError("Image URL is too long")
        try:
            url = urlsplit(value)
            host = (url.hostname or "").lower()
            if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
                raise ValueError("Use an HTTPS image URL without credentials or a custom port")
            if "." not in host or host.endswith((".local", ".localhost", ".internal", ".test", ".invalid")):
                raise ValueError("Use a public image host")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Use a public image host")
        except (ValueError, TypeError) as exc:
            raise ValueError("Use a public HTTPS image URL") from exc
        return value


def read_banner(db, company=None):
    keys = ["homepage-banner:default"]
    if company is not None:
        keys.insert(0, f"homepage-banner:{company}")
    for key in keys:
        row = db.query(ServicePolicy).filter_by(scope_key=key, kind="homepage-banner").first()
        if row:
            return BannerAppearance.model_validate(row.values_json).model_dump()
    return BannerAppearance().model_dump()


@router.get("")
def get_banner(db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return read_banner(db, context(db, actor)["company"])


@router.put("")
def save_banner(data: BannerAppearance, request: Request, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    _, ctx = require_option(db, actor, "appearance")
    for image in (data.image, data.mobile_image):
        if image.startswith("asset:"):
            identity, digest = image[6:].split("-", 1)
            asset = db.query(ServicePolicy).filter_by(id=int(identity),
                organization_id=ctx["company"], kind="homepage-banner-asset").first()
            if not asset or asset.values_json.get("sha256") != digest:
                raise HTTPException(422, "Select a banner uploaded to this company")
    key = f"homepage-banner:{ctx['company']}"
    row = db.query(ServicePolicy).filter_by(scope_key=key, kind="homepage-banner").first()
    before = row.values_json if row else {}
    if not row:
        row = ServicePolicy(scope_key=key, organization_id=ctx["company"], module_key="*",
                            kind="homepage-banner", updated_by=actor.id, values_json={})
        db.add(row)
    else:
        row.version += 1
    row.values_json = data.model_dump()
    row.updated_by = actor.id
    service.audit(db, actor, ctx["company"], "settings.banner.updated", "Homepage banner", before, row.values_json, request=request)
    db.commit()
    return row.values_json


@router.post("/upload", status_code=201)
async def upload_banner(file: UploadFile = File(...), db: Session = Depends(get_db), actor=Depends(get_current_user)):
    _, ctx = require_option(db, actor, "appearance")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(422, "Choose a JPEG, PNG or WebP image")
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Banner images must be at most 5 MB")
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 24_000_000:
                raise ValueError("Unsupported image or dimensions")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((2400, 1400), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, "WEBP", quality=85, method=4)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Choose a valid JPEG, PNG or WebP image under 24 megapixels")
    content = output.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    from uuid import uuid4
    asset = ServicePolicy(scope_key=f"homepage-banner-asset:{ctx['company']}:{uuid4().hex}",
        organization_id=ctx["company"], kind="homepage-banner-asset", module_key="*", updated_by=actor.id,
        values_json={"content": base64.b64encode(content).decode("ascii"), "sha256": digest})
    db.add(asset)
    db.commit()
    return {"image": f"asset:{asset.id}-{digest}"}


def published_asset(db, reference):
    # Public banner artwork is deliberately publishable. Unpublished drafts and
    # other document artwork cannot be retrieved through this endpoint.
    if not re.fullmatch(r"[0-9]+-[a-f0-9]{64}", reference):
        raise HTTPException(404, "Banner not found")
    identity, digest = reference.split("-", 1)
    asset = db.query(ServicePolicy).filter_by(id=int(identity), kind="homepage-banner-asset").first()
    if asset and asset.values_json.get("sha256") == digest:
        from app.models.company import Company
        company = db.get(Company, asset.organization_id)
        if not company or not company.is_active:
            raise HTTPException(404, "Banner not found")
        row = db.query(ServicePolicy).filter_by(scope_key=f"homepage-banner:{asset.organization_id}", kind="homepage-banner").first()
        if row and f"asset:{reference}" in (row.values_json.get("image"), row.values_json.get("mobile_image")):
            return Response(base64.b64decode(asset.values_json["content"]), media_type="image/webp", headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"})
    raise HTTPException(404, "Banner not found")
