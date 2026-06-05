import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.core.config import settings
from app.api.v1.router import api_router
from app.core.middleware.audit import AuditLogMiddleware
from app.core.middleware.request_id import RequestIDMiddleware
from app.module_registry import is_app_enabled


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT == "test":
        yield
        return

    # Startup: create DB tables and seed initial data
    from app.db.session import engine
    from app.db.base import Base
    from app.db.session import SessionLocal
    from app.db.init_common_db import init_common_db

    Base.metadata.create_all(bind=engine)

    # Create upload directories
    for subdir in ["employee_docs", "photos", "resumes", "documents", "certificates", "certificate_imports"]:
        os.makedirs(os.path.join(settings.UPLOAD_DIR, subdir), exist_ok=True)

    db = SessionLocal()
    try:
        if is_app_enabled("hrms"):
            from app.db.init_db import init_db

            init_db(db)
        else:
            init_common_db(db)
        if is_app_enabled("crm"):
            from app.apps.crm.schema import ensure_crm_schema

            ensure_crm_schema(db)
            if not is_app_enabled("hrms"):
                from app.apps.crm.seed import seed_crm_demo_data

                seed_crm_demo_data(db, organization_id=1)
        if is_app_enabled("project_management"):
            from app.apps.project_management.schema import ensure_pms_schema

            ensure_pms_schema(db)
        if is_app_enabled("srm"):
            from app.apps.srm.schema import ensure_srm_schema

            ensure_srm_schema(db)
        from app.ai_agents.services.registry import AiAgentRegistryService
        from app.ai_agents.tools.ai_tool_registry_service import AiToolRegistryService

        AiAgentRegistryService(db).ensure_seed_data()
        AiToolRegistryService(db).ensure_seed_data()
        db.commit()
    finally:
        db.close()

    yield
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Audit logging
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RequestIDMiddleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if settings.DEBUG:
        import traceback
        detail = traceback.format_exc()
    else:
        detail = "An internal server error occurred"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
    )


# Mount static files for uploaded content
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


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
