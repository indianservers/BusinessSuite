"""Local-only synthetic browser QA server. Run from backend with venv Python.
Exposes test sessions only on loopback port 8774. NEVER deploy this harness.
Uses a separate temporary SQLite database, upload directory, and signing key.
"""

import sys, os
from pathlib import Path
import tempfile, secrets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = (
    "sqlite:///"
    + (Path(tempfile.gettempdir()) / "businesssuite-chat-browser.db").as_posix()
)
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["UPLOAD_DIR"] = str(
    Path(tempfile.gettempdir()) / "businesssuite-chat-browser-files"
)
os.environ["STORAGE_BACKEND"] = "local"
os.environ["DATABASE_AUTO_MIGRATE"] = "false"
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.main import app as full_app
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.apps.project_management.api.router import router
from app.models.user import User, Role
from app.apps.project_management.models import (
    PMSWorkspace,
    PMSWorkspaceMember,
    PMSProject,
    PMSWorkspaceEntry,
    PMSFileAsset,
)
from app.core.security import create_access_token

Base.metadata.create_all(engine)
with SessionLocal() as db:
    if not db.query(User).filter_by(email="owner@audit.invalid").first():
        role = Role(name="pms_team_member")
        db.add(role)
        db.flush()
        users = [
            User(
                email="owner@audit.invalid",
                hashed_password="unused",
                is_active=True,
                is_superuser=True,
            ),
            User(
                email="member@audit.invalid",
                hashed_password="unused",
                is_active=True,
                role_id=role.id,
            ),
            User(
                email="third@audit.invalid",
                hashed_password="unused",
                is_active=True,
                role_id=role.id,
            ),
        ]
        db.add_all(users)
        db.flush()
        w = PMSWorkspace(name="AUDIT Messaging")
        db.add(w)
        db.flush()
        for i, u in enumerate(users):
            db.add(
                PMSWorkspaceMember(
                    workspace_id=w.id,
                    user_id=u.id,
                    role="Owner" if i == 0 else "Member",
                )
            )
        db.add(
            PMSProject(
                workspace_id=w.id,
                name="AUDIT Project",
                project_key="AUDCHAT",
                owner_user_id=users[0].id,
            )
        )
        db.add(
            PMSWorkspaceEntry(
                workspace_id=w.id,
                author_id=users[0].id,
                kind="chat",
                body="AUDIT preserved legacy workspace history",
            )
        )
        db.commit()
with SessionLocal() as db:
    project = db.query(PMSProject).filter_by(project_key="AUDCHAT").one()
    path = Path(os.environ["UPLOAD_DIR"]) / "project-reference.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("AUDIT existing project file content", encoding="utf-8")
    if (
        not db.query(PMSFileAsset)
        .filter_by(project_id=project.id, file_name="AUDIT project reference.txt")
        .first()
    ):
        db.add(
            PMSFileAsset(
                project_id=project.id,
                file_name="AUDIT project reference.txt",
                original_name="AUDIT project reference.txt",
                storage_path=str(path),
                mime_type="text/plain",
                size_bytes=path.stat().st_size,
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
app.include_router(router, prefix="/api/v1")


@app.get("/qa-session/{index}")
def session(index: int):
    with SessionLocal() as db:
        names = ["owner@audit.invalid", "member@audit.invalid", "third@audit.invalid"]
        u = db.query(User).filter_by(email=names[index]).one()
        return {
            "user": {
                "id": u.id,
                "email": u.email,
                "name": u.email,
                "role": "admin" if index == 0 else "pms_team_member",
                "is_superuser": u.is_superuser,
            },
            "token": create_access_token(str(u.id)),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8774, log_level="warning")
