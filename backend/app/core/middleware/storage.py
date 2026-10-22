import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.core.config import settings
from app.core.storage import sign_upload_references, normalize_upload_references


class PrivateUploadURLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if settings.SERVERLESS and request.headers.get("content-length", "0").isdigit():
            if int(request.headers.get("content-length", "0")) > 4 * 1024 * 1024:
                return Response('{"detail":"Upload request exceeds 4 MB. Maximum file size is 3 MB."}',
                                status_code=413, media_type="application/json")
        if settings.STORAGE_BACKEND == "s3" and "application/json" in request.headers.get("content-type", ""):
            body = await request.body()
            if b"X-Amz-Signature=" in body:
                try:
                    request._body = json.dumps(normalize_upload_references(json.loads(body))).encode()
                except (ValueError, TypeError):
                    pass  # Preserve FastAPI's normal malformed-JSON validation.
        response = await call_next(request)
        if (settings.STORAGE_BACKEND != "s3" or response.status_code >= 400
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
