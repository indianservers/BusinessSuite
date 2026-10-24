"""Loopback-only synthetic commercial QA. Never deploy or use real customers."""

import os
import secrets
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = (
    "sqlite:///"
    + (Path(tempfile.gettempdir()) / "businesssuite-commercial-browser.db").as_posix()
)
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["DATABASE_AUTO_MIGRATE"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["COMMUNICATION_EMAIL_PROVIDER"] = "stub"
os.environ["INSTALLED_APPS"] = "hrms,crm,project_management,srm,fam"
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.main import app as imported_app
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import User
from app.models.company import Company
from app.apps.crm.models import CRMCompany, CRMContact, CRMTeam
from app.apps.project_management.models import PMSProject
from app.apps.project_management.api.router import router as pms
from app.apps.srm.api.router import router as sales
from app.apps.crm.api.router import router as crm
from app.core.security import create_access_token

Base.metadata.create_all(engine)
# Keep this reusable disposable fixture current when iterating locally.
from alembic.migration import MigrationContext
from alembic.operations import Operations
import importlib.util

with engine.begin() as connection:
    path = Path(__file__).parents[1] / "alembic/versions/20261024_006_commercial.py"
    spec = importlib.util.spec_from_file_location("qa_commercial_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
with SessionLocal() as db:
    user = db.query(User).filter_by(email="commercial@audit.invalid").first()
    if not user:
        user = User(
            email="commercial@audit.invalid",
            hashed_password="unused",
            is_superuser=True,
            is_active=True,
        )
        db.add_all(
            [
                user,
                Company(
                    id=1,
                    name="Synthetic seller",
                    legal_name="Synthetic seller Ltd",
                    address="Test seller address",
                ),
                CRMCompany(
                    id=1,
                    organization_id=1,
                    name="Synthetic shared customer",
                    email="billing@audit.invalid",
                    address="Original synthetic billing address",
                ),
                CRMTeam(
                    id=1,
                    organization_id=1,
                    name="Synthetic shared team",
                    status="Active",
                ),
            ]
        )
        db.flush()
        db.add(
            CRMContact(
                id=1,
                organization_id=1,
                company_id=1,
                first_name="Synthetic",
                full_name="Synthetic billing contact",
                email="contact@audit.invalid",
            )
        )
        db.add(
            PMSProject(
                id=1,
                organization_id=1,
                name="Synthetic connected project",
                project_key="COMMQA",
                manager_user_id=user.id,
            )
        )
        db.commit()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5176"],
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in [pms, sales, crm]:
    app.include_router(router, prefix="/api/v1")


@app.get("/qa-session")
def qa_session():
    with SessionLocal() as db:
        user = db.query(User).filter_by(email="commercial@audit.invalid").one()
        return {
            "token": create_access_token(user.id),
            "user": {
                "id": user.id,
                "email": user.email,
                "role": "super_admin",
                "is_superuser": True,
            },
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8775, log_level="warning")
