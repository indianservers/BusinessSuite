import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends
from app.core.deps import get_db
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.core.config import settings
from app.core.orm_validation import install as install_input_validation
install_input_validation()
from app.core.log_filters import install_security_log_filters
install_security_log_filters(settings.ENVIRONMENT.lower()=='production' or not settings.DEBUG)
from app.api.v1.router import api_router
from app.core.middleware.audit import AuditLogMiddleware
from app.core.middleware.business_os import BusinessOSModuleAccessMiddleware
from app.core.middleware.request_id import RequestIDMiddleware
from app.module_registry import is_app_enabled


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT == "test" or settings.SERVERLESS:
        yield
        return

    # Startup: create DB tables and seed initial data
    from app.db.session import engine
    from app.db.base import Base
    from app.db.session import SessionLocal
    from app.db.init_common_db import init_common_db

    if settings.DATABASE_AUTO_MIGRATE:
        from app.db.migrations import upgrade_schema
        upgrade_schema()

    # Create upload directories
    for subdir in ["employee_docs", "photos", "resumes", "documents", "certificates", "certificate_imports"]:
        os.makedirs(os.path.join(settings.UPLOAD_DIR, subdir), exist_ok=True)

    db = SessionLocal()
    try:
        if is_app_enabled("hrms"):
            from app.db.init_db import init_db

            init_db(db, seed_demo=settings.SEED_DEMO_DATA)
        else:
            init_common_db(db)
        from app.apps.business_os.services.module_service import ensure_business_os_seed

        ensure_business_os_seed(db, company_id=1)
        if is_app_enabled("crm"):
            from app.apps.crm.schema import ensure_crm_schema

            ensure_crm_schema(db)
            if not is_app_enabled("hrms") and settings.SEED_DEMO_DATA:
                from app.apps.crm.seed import seed_crm_demo_data

                seed_crm_demo_data(db, organization_id=1)
        if is_app_enabled("project_management"):
            from app.apps.project_management.schema import ensure_pms_schema

            ensure_pms_schema(db)
        if is_app_enabled("srm"):
            from app.apps.srm.schema import ensure_srm_schema

            ensure_srm_schema(db)
        if is_app_enabled("fam"):
            from app.apps.fam.schema import ensure_fam_schema

            ensure_fam_schema(db)
        from app.apps.automation.schema import ensure_automation_schema

        ensure_automation_schema(db)
        from app.apps.customization.schema import ensure_customization_schema

        ensure_customization_schema(db)
        from app.apps.communication.schema import ensure_communication_schema

        ensure_communication_schema(db)
        from app.apps.analytics.schema import ensure_analytics_schema

        ensure_analytics_schema(db)
        from app.apps.ai_copilot.schema import ensure_ai_copilot_schema

        ensure_ai_copilot_schema(db)
        from app.ai_agents.services.registry import AiAgentRegistryService
        from app.ai_agents.tools.ai_tool_registry_service import AiToolRegistryService

        AiAgentRegistryService(db).ensure_seed_data()
        AiToolRegistryService(db).ensure_seed_data()
        db.commit()
    finally:
        db.close()

    follow_up_worker = None
    if is_app_enabled("crm") or is_app_enabled("srm"):
        from app.shared.follow_ups import start_worker
        follow_up_worker = start_worker()
    calendar_worker = None
    if settings.CALENDAR_SYNC_WORKER_ENABLED and (is_app_enabled("crm") or is_app_enabled("project_management")):
        from app.apps.crm.calendar_sync import start_worker as start_calendar_worker
        calendar_worker = start_calendar_worker()
    backup_worker = None
    email_worker = None
    if settings.EMAIL_WORKER_ENABLED:
        from app.services.email_dispatch import start_email_worker
        email_worker = start_email_worker()
    accounting_worker = None
    if settings.ACCOUNTING_SYNC_WORKER_ENABLED and is_app_enabled("fam"):
        from app.shared.accounting_sync.jobs import start_worker as start_accounting_worker
        accounting_worker = start_accounting_worker()
    if settings.BUSINESSSUITE_BACKUP_SCHEDULER:
        from app.services.backup_scheduler import start_scheduler
        backup_worker = start_scheduler()
    import asyncio
    from app.platform_owner.worker import run as run_platform_checks
    platform_worker = asyncio.create_task(run_platform_checks())
    try:
        yield
    finally:
        platform_worker.cancel()
        try:
            await platform_worker
        except asyncio.CancelledError:
            pass
        if calendar_worker:
            calendar_worker[0].set()
        if follow_up_worker:
            follow_up_worker[0].set()
        if email_worker:
            email_worker[0].set()
        if backup_worker:
            backup_worker[0].set()
        if accounting_worker:
            accounting_worker[0].set()
    # Shutdown


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Complete AI-powered HRMS API with 16 modules",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from app.core.middleware.storage import PrivateUploadURLMiddleware
app.add_middleware(PrivateUploadURLMiddleware)
from app.core.middleware.rich_text import RichTextMiddleware
app.add_middleware(RichTextMiddleware)

from app.core.middleware.record_sync import RecordSyncMiddleware
app.add_middleware(RecordSyncMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After", "ETag", "X-Suite-Sync-Cursor", "X-Suite-Sync-Scope", "X-Suite-Sync-Mode", "X-Suite-Cache", "X-Suite-Setup-Required"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Audit logging
app.add_middleware(BusinessOSModuleAccessMiddleware)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RequestIDMiddleware)
from app.core.middleware.security_headers import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)
from app.core.middleware.request_boundary import RequestBoundaryMiddleware
app.add_middleware(RequestBoundaryMiddleware)
from app.core.middleware.tenant_database import TenantDatabaseMiddleware
app.add_middleware(TenantDatabaseMiddleware)


# Global exception handler
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, DBAPIError

@app.exception_handler(RequestValidationError)
async def invalid_input_handler(request:Request,exc:RequestValidationError):
    return JSONResponse(status_code=422,content={'detail':[{'loc':list(error['loc']),'msg':error['msg'],'type':error['type']} for error in exc.errors()]})

@app.exception_handler(IntegrityError)
async def conflicting_record_handler(request:Request,exc:IntegrityError):
    return JSONResponse(status_code=409,content={'detail':'This record conflicts with an existing record or referenced value. Refresh the form and check its identifiers.'})

@app.exception_handler(DBAPIError)
async def database_request_handler(request: Request, exc: DBAPIError):
    import logging
    state = getattr(exc.orig, "sqlstate", None)
    code = 422 if state in {"22003", "22P02", "22001"} else 503
    logging.getLogger("businesssuite.security").warning("security_event=database_request_rejected sqlstate=%s status=%s", state, code)
    return JSONResponse(status_code=code, content={"detail": "Invalid or out-of-range value" if code == 422 else "Database operation could not complete. Check its status before retrying."}, headers={"Retry-After": "5"} if code == 503 else {})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger("businesssuite.errors").error("request_failed request_id=%s error_type=%s", getattr(request.state, "request_id", None), type(exc).__name__)
    if settings.DEBUG and settings.ENVIRONMENT.lower() in {"development", "test"}:
        import traceback
        detail = traceback.format_exc()
    else:
        detail = "An internal server error occurred"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail, "request_id": getattr(request.state, "request_id", None)},
        headers={"X-Request-ID": getattr(request.state, "request_id", "")},
    )


# Mount static files for uploaded content
if settings.STORAGE_BACKEND == "local" and os.path.exists(settings.UPLOAD_DIR):
    from app.core.private_uploads import ProtectedUploads
    app.mount("/uploads", ProtectedUploads(directory=settings.UPLOAD_DIR), name="uploads")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/api/v1/files/blob", include_in_schema=False)
def private_blob_file(request: Request, token: str, db=Depends(get_db)):
    from app.core.storage import blob_token_path, materialize_file
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    if settings.STORAGE_BACKEND not in {"local", "vercel_blob", "s3"}:
        raise HTTPException(404, "Not found")
    path = blob_token_path(token, db=db)
    from app.services.file_storage import cloud_content
    cloud = cloud_content(path, db=db)
    if cloud is not None:
        from starlette.responses import Response
        from urllib.parse import quote
        content, stored = cloud
        db.commit()  # Persist provider token rotation without writing downloaded bytes to disk.
        return Response(content, media_type=stored.content_type, headers={
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(stored.filename, safe=""),
        })
    path = materialize_file(path, db=db)
    db.commit()  # Save provider refresh-token rotation.
    if not os.path.isfile(path):
        raise HTTPException(404,'File not found')
    from app.core.photo_cache import private_file_response
    return private_file_response(path, request)


@app.get("/")
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs": f"{settings.API_V1_STR}/docs",
        "status": "running",
    }


@app.get("/health")
def health_check():
    from app.db.session import SessionLocal

    db = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    finally:
        if db:
            db.close()
    status_value = "healthy" if db_status == "ok" else "degraded"
    return {"status": status_value, "db": db_status, "environment": settings.ENVIRONMENT}
