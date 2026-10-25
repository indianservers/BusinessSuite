import json
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.core.config import settings
from app.core.storage import sign_upload_references, normalize_upload_references


def raw_private_reference(value):
    if isinstance(value,str) and value.startswith('/uploads/'):
        parts=value[len('/uploads/'):].replace('\\','/').split('/')
        return any(part in {'.','..'} or ':' in part for part in parts) or parts[0].lower() not in {'photos','avatars','logos','branding'}
    if isinstance(value,list):return any(raw_private_reference(item) for item in value)
    if isinstance(value,dict):return any(raw_private_reference(item) for item in value.values())
    return False


class PrivateUploadURLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if any(raw_private_reference(value) for _,value in request.query_params.multi_items()):
            return Response('{"detail":"Use a file link returned by the authorized upload service"}',status_code=422,media_type='application/json')
        if settings.SERVERLESS and request.headers.get("content-length", "0").isdigit():
            if int(request.headers.get("content-length", "0")) > 4 * 1024 * 1024:
                return Response('{"detail":"Upload request exceeds 4 MB. Maximum file size is 3 MB."}',
                                status_code=413, media_type="application/json")
        if settings.STORAGE_BACKEND in {"local", "s3", "vercel_blob"} and "application/json" in request.headers.get("content-type", ""):
            body = await request.body()
            try:
                if raw_private_reference(json.loads(body)):
                    return Response('{"detail":"Use a file link returned by the authorized upload service"}',status_code=422,media_type='application/json')
            except (ValueError,TypeError):pass
            if b"X-Amz-Signature=" in body or b"/api/v1/files/blob?" in body:
                try:
                    request._body = json.dumps(normalize_upload_references(json.loads(body))).encode()
                except HTTPException:
                    return Response('{"detail":"Invalid or expired file reference"}',status_code=403,media_type='application/json')
                except (ValueError, TypeError):
                    pass  # Preserve FastAPI's normal malformed-JSON validation.
        response = await call_next(request)
        if (settings.STORAGE_BACKEND not in {"local", "s3", "vercel_blob"} or response.status_code >= 400
                or "application/json" not in response.headers.get("content-type", "")):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        if b"/uploads/" in body:
            body = json.dumps(sign_upload_references(json.loads(body))).encode()
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["Cache-Control"] = "private, no-store"
        return Response(body, status_code=response.status_code, headers=headers,
                        background=response.background)
