"""Bound input before JSON/multipart parsing and reject abuse before business work."""

import asyncio
import json
import logging
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.core.middleware.audit import client_addresses
from app.core.request_limits import consume, digest, enabled, factory

logger = logging.getLogger("businesssuite.security")


class InvalidEnvelope(Exception):
    def __init__(self, status, detail, retry=None):
        self.status, self.detail, self.retry = status, detail, retry


def validate_json(value, depth=0, budget=None, key=""):
    budget = [0] if budget is None else budget
    budget[0] += 1
    if depth > settings.SECURITY_MAX_JSON_DEPTH or budget[0] > 50000:
        raise InvalidEnvelope(422, "Request structure is too complex")
    if isinstance(value, list):
        is_batch = (
            depth == 0
            or key in {"rows", "items", "operations", "ids", "records", "recipients"}
            or key.endswith("_ids")
        )
        if len(value) > (settings.SECURITY_MAX_BATCH if is_batch else 5000):
            raise InvalidEnvelope(422, "Batch exceeds the configured item limit")
        for item in value:
            validate_json(item, depth + 1, budget)
    elif isinstance(value, dict):
        if len(value) > 1000:
            raise InvalidEnvelope(422, "Too many request fields")
        for name, item in value.items():
            validate_json(item, depth + 1, budget, str(name))
    elif isinstance(value, str) and len(value) > 1048576:
        raise InvalidEnvelope(422, "Request field is too large")
    elif isinstance(value, float):
        import math

        if not math.isfinite(value):
            raise InvalidEnvelope(422, "Numbers must be finite")


def rate_specs(request, body):
    ip = client_addresses(request)[0] or "unknown"
    path = request.url.path
    specifications = [(f"ip:{ip}", settings.RATE_LIMIT_PER_MINUTE * 10, 60)]
    portal_token = request.headers.get("X-Portal-Session")
    if portal_token:
        specifications.append(
            (
                f"portal-session:{digest(portal_token)}",
                settings.RATE_LIMIT_PER_MINUTE,
                60,
            )
        )
    sensitive = any(
        word in path
        for word in (
            "/auth/",
            "/signup",
            "/applications/status",
            "invitations",
            "/invite",
            "/public/",
            "/capture/",
            "/booking/",
        )
    )
    if sensitive and request.method != "GET":
        specifications.append((f"auth-ip:{ip}", 60, 60))
        try:
            value = json.loads(body) if body else {}
            account = value.get("email") if isinstance(value, dict) else None
            if (
                not account
                and isinstance(value, dict)
                and isinstance(value.get("mfa_token"), str)
            ):
                import jwt

                try:
                    claims = jwt.decode(
                        value["mfa_token"],
                        settings.SECRET_KEY,
                        algorithms=[settings.ALGORITHM],
                        options={"require": ["exp", "sub", "scope"]},
                    )
                    if claims.get("scope") == "mfa":
                        account = "mfa:" + str(claims["sub"])
                except jwt.PyJWTError:
                    pass
            if not account and isinstance(value, dict):
                capability = value.get("token") or value.get("code")
                if isinstance(capability, str) and 20 <= len(capability) <= 4096:
                    account = "capability:" + digest(capability)
            if account:
                account = digest(str(account).strip().casefold()[:320])
                specifications.extend(
                    [
                        (f"account:{path}:{account}", 30, 60),
                        (f"pair:{path}:{ip}:{account}", 8, 60),
                    ]
                )
            else:
                specifications.append((f"auth-endpoint:{path}:{ip}", 15, 60))
        except (ValueError, TypeError):
            pass
    return specifications


class RequestBoundaryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            from app.core.middleware.websocket_boundary import (
                WebSocketBoundaryMiddleware,
            )

            return await WebSocketBoundaryMiddleware(self.app)(scope, receive, send)
        if (
            scope["type"] != "http"
            or not scope.get("path", "").startswith(("/api/", "/uploads/"))
            or scope.get("method") == "OPTIONS"
        ):
            return await self.app(scope, receive, send)
        request = Request(scope, receive=receive)
        from uuid import uuid4

        scope.setdefault("state", {})["request_id"] = str(uuid4())
        status = 400
        retry_after = None
        worker = None
        suppress_output = False
        started_response = False
        completed_response = False
        deadline = (
            asyncio.get_running_loop().time()
            + settings.SECURITY_REQUEST_TIMEOUT_SECONDS
        )

        async def tracked_send(message):
            nonlocal started_response, completed_response
            if suppress_output:
                return
            if message["type"] == "http.response.start":
                started_response = True
            if message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                completed_response = True
            await send(message)

        async def budget(specifications):
            if not specifications:
                return

            def reserve():
                with factory(request)() as db:
                    db.info["security_store_timeout"] = True
                    retry = consume(db, specifications)
                    db.commit()
                    return retry

            try:
                retry = await run_in_threadpool(reserve)
            except Exception:
                raise InvalidEnvelope(
                    503, "Security enforcement is temporarily unavailable"
                ) from None
            if retry:
                logger.warning(
                    "security_event=request_throttled ip_key=%s",
                    digest(client_addresses(request)[0] or "unknown"),
                )
                raise InvalidEnvelope(
                    429, "Request limit reached. Try again shortly.", retry
                )

        try:
            if (
                len(scope.get("query_string", b"")) > 8192
                or len(request.query_params.multi_items()) > 100
            ):
                raise InvalidEnvelope(422, "Query is too complex")
            for key, value in request.query_params.multi_items():
                if key in {"limit", "page_size", "per_page", "size", "take"}:
                    if (
                        not value.isascii()
                        or not value.isdecimal()
                        or not 1 <= int(value) <= settings.SECURITY_MAX_PAGE_SIZE
                    ):
                        raise InvalidEnvelope(
                            422, "Page size exceeds the configured limit"
                        )
                if key in {"skip", "offset", "page"}:
                    if (
                        not value.isascii()
                        or not value.isdecimal()
                        or not 0 <= int(value) <= settings.SECURITY_MAX_OFFSET
                    ):
                        raise InvalidEnvelope(
                            422, "Pagination exceeds the configured limit"
                        )
                if (
                    key in {"q", "search", "query", "filter", "sort"}
                    and len(value) > 512
                ):
                    raise InvalidEnvelope(422, "Search expression is too long")
            for segment in scope.get("path", "").split("/"):
                if (
                    segment.isascii()
                    and segment.isdecimal()
                    and (len(segment) > 19 or int(segment) > 9223372036854775807)
                ):
                    raise InvalidEnvelope(422, "Resource identifier is out of range")
            limit = settings.SECURITY_MAX_BODY_BYTES
            length = request.headers.get("content-length")
            if length and (not length.isdecimal() or int(length) > limit):
                raise InvalidEnvelope(413, "Request body exceeds the configured limit")
            header_keys = set()
            if enabled(request):
                headers_only = [
                    spec
                    for spec in rate_specs(request, b"")
                    if not spec[0].startswith("auth-endpoint:")
                ]
                header_keys = {spec[0] for spec in headers_only}
                await budget(headers_only)
            body = bytearray()
            more = True
            while more:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError()
                message = await asyncio.wait_for(receive(), timeout=remaining)
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    raise InvalidEnvelope(
                        413, "Request body exceeds the configured limit"
                    )
                more = message.get("more_body", False)
            raw = bytes(body)
            if raw and "application/json" in request.headers.get("content-type", ""):
                try:
                    value = json.loads(raw)
                    validate_json(value)
                except (ValueError, RecursionError, UnicodeDecodeError):
                    raise InvalidEnvelope(422, "Invalid JSON request") from None
            if "multipart/form-data" in request.headers.get("content-type", ""):
                import re

                if (
                    sum(
                        1
                        for _ in re.finditer(
                            rb"(?im)^content-disposition:\s*form-data", raw
                        )
                    )
                    > settings.SECURITY_MAX_BATCH
                ):
                    raise InvalidEnvelope(
                        422, "Multipart batch exceeds the configured limit"
                    )
            if enabled(request):
                remaining_specs = [
                    spec
                    for spec in rate_specs(request, raw)
                    if spec[0] not in header_keys
                ]
                await budget(remaining_specs)
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": raw, "more_body": False}
                return await receive()

            # Do not cancel an in-flight sync worker and remove its authorization
            # hooks while it is still using the session. Retain the work lease and
            # scope until it actually finishes; the DB/platform enforce hard limits.
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError()
            worker = asyncio.create_task(self.app(scope, replay, tracked_send))
            try:
                return await asyncio.wait_for(asyncio.shield(worker), remaining)
            except asyncio.CancelledError:
                await asyncio.shield(worker)
                raise
        except InvalidEnvelope as exc:
            status = exc.status
            detail = exc.detail
            retry_after = exc.retry
        except TimeoutError:
            suppress_output = True
            status, detail = 504, "Request timed out. Check the result before retrying."
        logger.warning(
            "security_event=request_rejected status=%s request_id=%s",
            status,
            request.state.request_id,
        )
        if started_response:
            if not completed_response:
                await send(
                    {"type": "http.response.body", "body": b"", "more_body": False}
                )
        else:
            headers = {
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "X-Request-ID": request.state.request_id,
            }
            if retry_after is not None or status == 503:
                headers["Retry-After"] = str(retry_after or 5)
            origin = request.headers.get("origin")
            if origin and origin in {
                str(value).rstrip("/") for value in settings.BACKEND_CORS_ORIGINS
            }:
                headers.update(
                    {
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Expose-Headers": "Retry-After, X-Request-ID",
                        "Vary": "Origin",
                    }
                )
            response = JSONResponse(
                {"detail": detail}, status_code=status, headers=headers
            )
            await response(scope, receive, send)
        if worker is not None:
            try:
                await asyncio.shield(worker)
            except Exception as exc:
                logger.warning(
                    "security_event=timed_out_worker_failed error_type=%s",
                    type(exc).__name__,
                )
