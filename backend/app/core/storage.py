"""Private S3-compatible storage; local disk is staging, never cloud persistence."""
from functools import lru_cache
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit, unquote
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


def persist_file(path: str) -> None:
    if settings.STORAGE_BACKEND == "local":
        return
    storage_key(path)  # Reject traversal before contacting storage.
    s3_client().upload_file(str(path), settings.S3_BUCKET, storage_key(path), ExtraArgs={
        "ContentType": mimetypes.guess_type(str(path))[0] or "application/octet-stream",
        "ContentDisposition": "inline" if (mimetypes.guess_type(str(path))[0] or "").startswith("image/") else "attachment",
    })


def upload_exists(path: str) -> bool:
    if settings.STORAGE_BACKEND == "local":
        return Path(path).is_file()
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
        s3_client().download_file(settings.S3_BUCKET, storage_key(path), str(path))
    return path


def signed_file_url(path: str) -> str:
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
    if isinstance(value, str) and "X-Amz-Signature=" in value:
        url = urlsplit(value)
        service_host = urlsplit(s3_client().meta.endpoint_url).hostname
        if url.hostname in {service_host, f"{settings.S3_BUCKET}.{service_host}"}:
            path = unquote(url.path)
            prefixes = [f"/{settings.S3_PREFIX.strip('/')}/", f"/{settings.S3_BUCKET}/{settings.S3_PREFIX.strip('/')}/"]
            for prefix in prefixes:
                if path.startswith(prefix):
                    relative = path[len(prefix):]
                    storage_key(str(Path(settings.UPLOAD_DIR) / relative))
                    return f"/uploads/{relative}"
    if isinstance(value, list):
        return [normalize_upload_references(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_upload_references(item) for key, item in value.items()}
    return value
