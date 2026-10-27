"""Sanitize explicitly versioned rich content before endpoint validation/storage."""
import json
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from app.core.rich_text import PREFIX, sanitize_tree


class RichTextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Signed Power Apps ingress authenticates the exact raw bytes before schema validation.
        signed_ingress = request.url.path.startswith("/api/v1/power-apps/hooks/")
        if not signed_ingress and "application/json" in request.headers.get("content-type", ""):
            body = await request.body()
            if PREFIX.encode() in body:
                try:
                    request._body = json.dumps(sanitize_tree(json.loads(body))).encode()
                except HTTPException as exc:
                    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
                except (ValueError, TypeError):
                    pass  # Keep the framework's usual malformed-JSON response.
        response = await call_next(request)
        if response.status_code >= 400 or "application/json" not in response.headers.get("content-type", ""):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        if PREFIX.encode() in body:
            body = json.dumps(sanitize_tree(json.loads(body))).encode()
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(body, status_code=response.status_code, headers=headers, background=response.background)
