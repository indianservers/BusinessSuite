"""Private S3-compatible storage; local disk is staging, never cloud persistence."""
from functools import lru_cache
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs, urlencode
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import jwt
from jwt import PyJWTError as JWTError
from fastapi import HTTPException
from fastapi.responses import FileResponse as LocalFileResponse, RedirectResponse
from app.core.config import settings


def storage_key(path: str) -> str:
    root = Path(settings.UPLOAD_DIR).resolve()
    target = Path(path).resolve()
    try:
        relative = target.relative_to(root).as_posix()
    except ValueError:
        raise HTTPException(400, "File path is outside upload storage")
    if not relative or relative == ".":
        raise HTTPException(400, "A file path is required")
    return f"{settings.S3_PREFIX.strip('/')}/{relative}"


@lru_cache(maxsize=1)
def s3_client():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=settings.S3_ENDPOINT_URL,
                        region_name=settings.S3_REGION,
                        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                        config=Config(signature_version="s3v4", retries={"max_attempts": 3},
                                      connect_timeout=5, read_timeout=20))


@contextmanager
def blob_session():
    from vercel.api import session
    from vercel.blob.sync import SyncBlobServiceOptions, BlobCredentials
    token = settings.BLOB_READ_WRITE_TOKEN
    store_id = token.removeprefix("vercel_blob_rw_").split("_", 1)[0]
    with session(service_options=[SyncBlobServiceOptions(
        credentials_factory=lambda: BlobCredentials(token, store_id)
    )]):
        yield


def blob_token_path(token: str, *, verify_exp: bool = True, db=None) -> str:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                             options={"verify_exp": verify_exp,"require":["exp","path","purpose","aud"]}, audience="private-file")
        relative = payload["path"]
        if payload.get("purpose") != "blob-download" or not isinstance(relative, str):
            raise ValueError("Invalid file token")
        if verify_exp and payload.get("access_user"):
            if db is None:
                raise HTTPException(403, "Use the authorized file download endpoint")
            from app.models.user import User, UserSession
            from app.access.service import policy_for, companies_for
            user = db.get(User, int(payload["access_user"]))
            company = int(payload.get("access_company", 0))
            policy = policy_for(db, user, company) if user else None
            if not user or not user.is_active or company not in companies_for(db, user) or not policy or policy.status != "active" or policy.version != payload.get("access_policy_version"):
                raise HTTPException(403, "File access changed; open the record again")
            if payload.get("access_session"):
                session = db.get(UserSession, int(payload["access_session"]))
                if not session or session.user_id != user.id or session.status.lower() == "revoked":
                    raise HTTPException(403, "File session has been revoked")
        path = str(Path(settings.UPLOAD_DIR) / relative)
        storage_key(path)
        return path
    except (JWTError, KeyError, ValueError, TypeError):
        raise HTTPException(403, "Invalid or expired file link") from None


def persist_file(path: str) -> None:
    if settings.STORAGE_BACKEND == "local":
        return
    storage_key(path)  # Reject traversal before contacting storage.
    if settings.STORAGE_BACKEND == "vercel_blob":
        from vercel.blob.sync import put_blob
        with blob_session(), open(path, "rb") as source:
            put_blob(storage_key(path), source, content_length=Path(path).stat().st_size,
                     access="private", allow_overwrite=True,
                     content_type=mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        return
    s3_client().upload_file(str(path), settings.S3_BUCKET, storage_key(path), ExtraArgs={
        "ContentType": mimetypes.guess_type(str(path))[0] or "application/octet-stream",
        "ContentDisposition": "inline" if (mimetypes.guess_type(str(path))[0] or "").startswith("image/") else "attachment",
    })


def upload_exists(path: str) -> bool:
    if settings.STORAGE_BACKEND == "local":
        return Path(path).is_file()
    if settings.STORAGE_BACKEND == "vercel_blob":
        from vercel.blob.sync import head_blob, BlobNotFoundError
        try:
            with blob_session():
                head_blob(storage_key(path))
            return True
        except BlobNotFoundError:
            return False
    from botocore.exceptions import ClientError
    try:
        s3_client().head_object(Bucket=settings.S3_BUCKET, Key=storage_key(path))
        return True
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def materialize_file(path: str) -> str:
    """Fetch private inputs for PDF merging even on a different function instance."""
    if settings.STORAGE_BACKEND != "local":
        storage_key(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if settings.STORAGE_BACKEND == "vercel_blob":
            from vercel.blob.sync import stream_blob, BlobNotFoundError
            try:
                with blob_session(), stream_blob(storage_key(path), access="private") as download:
                    with open(path, "wb") as target:
                        for chunk in download:
                            target.write(chunk)
            except BlobNotFoundError:
                raise HTTPException(404, "File not found") from None
            return path
        s3_client().download_file(settings.S3_BUCKET, storage_key(path), str(path))
    return path


def signed_file_url(path: str) -> str:
    if settings.STORAGE_BACKEND in {"local", "vercel_blob", "s3"}:
        storage_key(path)
        relative = Path(path).resolve().relative_to(Path(settings.UPLOAD_DIR).resolve()).as_posix()
        claims = {}
        from app.core.audit_context import context
        actor = (context.get() or {}).get("actor", {})
        if actor.get("access_policy_version") is not None:
            claims = {"access_user": actor["user_id"], "access_company": actor["access_company"], "access_session": actor.get("access_session"), "access_policy_version": actor["access_policy_version"]}
        token = jwt.encode({"path": relative, "purpose": "blob-download", "aud": "private-file", **claims,
                            "exp": datetime.now(timezone.utc) + timedelta(seconds=settings.S3_SIGNED_URL_SECONDS)},
                           settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return f"{settings.BACKEND_PUBLIC_URL}/api/v1/files/blob?{urlencode({'token': token})}"
    return s3_client().generate_presigned_url("get_object", Params={
        "Bucket": settings.S3_BUCKET, "Key": storage_key(path),
    }, ExpiresIn=settings.S3_SIGNED_URL_SECONDS)


def FileResponse(path, *args, **kwargs):
    if settings.STORAGE_BACKEND == "local":
        return LocalFileResponse(path, *args, **kwargs)
    return RedirectResponse(signed_file_url(str(path)), status_code=307,
                            headers={"Cache-Control": "private, no-store"})


def sign_upload_references(value):
    # URLs originate in responses of existing permission-checked record endpoints.
    # No public endpoint accepts arbitrary object keys or grants download access.
    if isinstance(value, str) and value.startswith("/uploads/"):
        return signed_file_url(str(Path(settings.UPLOAD_DIR) / value[len("/uploads/"):]))
    if isinstance(value, list):
        return [sign_upload_references(item) for item in value]
    if isinstance(value, dict):
        return {key: sign_upload_references(item) for key, item in value.items()}
    return value


def normalize_upload_references(value):
    """Do not save expiring display links when a record is edited and resubmitted."""
    if isinstance(value, str) and settings.STORAGE_BACKEND in {"local", "vercel_blob", "s3"}:
        url = urlsplit(value)
        if url.path == "/api/v1/files/blob" and url.netloc == urlsplit(settings.BACKEND_PUBLIC_URL).netloc:
            tokens = parse_qs(url.query).get("token", [])
            if tokens:
                path = blob_token_path(tokens[0])
                relative = Path(path).resolve().relative_to(Path(settings.UPLOAD_DIR).resolve()).as_posix()
                return f"/uploads/{relative}"
    if isinstance(value, list):
        return [normalize_upload_references(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_upload_references(item) for key, item in value.items()}
    return value
