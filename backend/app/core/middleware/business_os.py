from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.apps.business_os.services.module_service import is_module_enabled
from app.db.session import SessionLocal


API_MODULE_PREFIXES = (
    ("/api/v1/crm", "crm"),
    ("/api/v1/srm", "srm"),
    ("/api/v1/fam/inventory", "inventory"),
    ("/api/v1/fam", "fam"),
    ("/api/v1/project-management", "project_management"),
    ("/api/v1/ai-operator", "project_management"),
    ("/api/v1/ai", "ai"),
    ("/api/v1/ai-agents", "ai"),
    ("/api/v1/portal", "portals"),
    ("/api/v1/portals", "portals"),
    ("/api/v1/communication", "communication"),
)

ALWAYS_ALLOWED_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/business-os",
    "/api/v1/docs",
    "/api/v1/openapi",
    "/api/v1/redoc",
    "/health",
    "/uploads",
)


class BusinessOSModuleAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/v1/"):
            return await call_next(request)
        if any(path.startswith(prefix) for prefix in ALWAYS_ALLOWED_PREFIXES):
            return await call_next(request)

        module_key = next((module for prefix, module in API_MODULE_PREFIXES if path.startswith(prefix)), None)
        if not module_key:
            return await call_next(request)

        session_factory = getattr(request.app.state, "business_os_session_factory", None)
        close_session = getattr(request.app.state, "business_os_close_session", session_factory is None)
        session_factory = session_factory or SessionLocal
        db = session_factory()
        try:
            company_id = 1
            from app.core.security import verify_access_token
            from app.models.user import User
            from app.access.service import primary_company, companies_for
            payload = verify_access_token(request.headers.get("authorization", "").partition(" ")[2]) or {}
            subject = str(payload.get("sub", ""))
            actor = db.get(User, int(subject)) if subject.isdecimal() else None
            if actor:
                company_id = primary_company(actor)
                requested = request.headers.get("X-Suite-Organization", "")
                if requested.isdecimal() and (actor.is_superuser or int(requested) in companies_for(db, actor)):
                    company_id = int(requested)
            from app.models.company import Company
            if not db.get(Company, company_id):
                if actor:
                    return JSONResponse(status_code=403,content={"detail":"Organization context is unavailable"})
                return await call_next(request)
            if not is_module_enabled(db, module_key, company_id=company_id):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": f"Business OS module disabled: {module_key}",
                        "module": module_key,
                        "historical_data_preserved": True,
                    },
                )
        finally:
            if close_session:
                db.close()
        return await call_next(request)
