"""Establish routing before audit, limits, uploads or business middleware run."""
import json
from urllib.parse import parse_qs
import jwt
from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.core.security import verify_access_token, verify_refresh_token
from app.db.tenant import current_tenant, lookup_route


class TenantDatabaseMiddleware:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope["type"] not in {"http","websocket"} or not settings.TENANT_DATABASES_ENABLED:
            return await self.app(scope,receive,send)
        path=scope.get("path","")
        if path.startswith(("/api/v1/platform/","/api/v1/auth/platform/","/api/v1/auth/signup")):
            return await self.app(scope,receive,send)
        headers={k.decode().lower():v.decode() for k,v in scope.get("headers",[])}
        workspace=headers.get("x-suite-tenant","")
        query=parse_qs(scope.get("query_string",b"").decode())
        raw=headers.get("authorization","").partition(" ")[2]
        if scope["type"]=="websocket":raw=raw or query.get("token",query.get("access_token",[""]))[0]
        payload=verify_access_token(raw) if raw else None
        messages=[]
        # Refresh and MFA capabilities must route without an access token/header.
        if scope["type"]=="http" and path in {"/api/v1/auth/refresh","/api/v1/auth/mfa/verify"}:
            body=b""
            while True:
                message=await receive();messages.append(message)
                body+=message.get("body",b"")
                if len(body)>65536 or not message.get("more_body"):break
            async def replay():
                return messages.pop(0) if messages else await receive()
            downstream_receive=replay
            try:
                values=json.loads(body)
                if path.endswith("/refresh"):payload=verify_refresh_token(values.get("refresh_token",""))
                elif values.get("mfa_token"):
                    payload=jwt.decode(values["mfa_token"],settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
                    if payload.get("scope")!="mfa":payload=None
            except (ValueError,TypeError,jwt.PyJWTError):payload=None
        else:downstream_receive=receive
        tenant=payload.get("tenant") if payload else None
        marker=None
        try:
            if raw and workspace and not tenant:
                raise HTTPException(403,"This session is not bound to a company database")
            if tenant or workspace:
                route=await run_in_threadpool(lookup_route,tenant or workspace)
                if workspace and workspace not in {route.tenant_uuid,route.workspace_code}:
                    raise HTTPException(403,"Session and company workspace do not match")
                marker=current_tenant.set(route)
                scope.setdefault("state",{})["database_tenant"]=route.tenant_uuid
            await self.app(scope,downstream_receive,send)
        except HTTPException as exc:
            if scope["type"]=="websocket":await send({"type":"websocket.close","code":4403})
            else:await JSONResponse({"detail":exc.detail},status_code=exc.status_code)(scope,downstream_receive,send)
        finally:
            if marker is not None:current_tenant.reset(marker)
