"""Loopback-only notes QA against a disposable SQLite database; never production."""
import os
import secrets
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
qa = TemporaryDirectory(prefix="pms-notes-qa-")
os.environ.update(ENVIRONMENT="test", DATABASE_URL="sqlite:///"+str(Path(qa.name)/"notes.db"), SECRET_KEY=secrets.token_urlsafe(48), REFRESH_SECRET_KEY=secrets.token_urlsafe(48), STORAGE_BACKEND="local", UPLOAD_DIR=str(Path(qa.name)/"uploads"), SEED_DEMO_DATA="false")
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.core.deps import get_db
from app.core.security import get_password_hash, pwd_context
from app.models.user import User, Role
from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember,PMSProject,PMSTask,PMSNote,PMSNoteRevision,PMSNoteFolder
from app.api.v1.auth import router as auth_router
from app.apps.project_management.api.router import router as pms_router
engine=create_engine(os.environ["DATABASE_URL"],connect_args={"check_same_thread":False,"timeout":30})
Base.metadata.create_all(engine)
Session=sessionmaker(bind=engine)
pwd_context.update(bcrypt__rounds=4)
with Session() as db:
    owner=User(email="notes-admin@example.com",hashed_password=get_password_hash("NotesQA@123"),is_active=True,is_superuser=True)
    role=Role(name="pms_team_member",is_system=True);db.add(role);db.flush()
    reader=User(role_id=role.id,email="notes-reader@example.com",hashed_password=get_password_hash("NotesQA@123"),is_active=True)
    db.add_all([owner,reader]);db.flush()
    workspace=PMSWorkspace(name="Notes QA Workspace");db.add(workspace);db.flush()
    db.add_all([PMSWorkspaceMember(workspace_id=workspace.id,user_id=owner.id,role="Owner"),PMSWorkspaceMember(workspace_id=workspace.id,user_id=reader.id,role="Member")])
    project=PMSProject(name="Website Development",project_key="WEB",workspace_id=workspace.id,organization_id=1,manager_user_id=owner.id)
    mobile=PMSProject(name="Mobile Application",project_key="MOB",workspace_id=workspace.id,organization_id=1,manager_user_id=owner.id)
    db.add_all([project,mobile]);db.flush()
    task=PMSTask(title="API Integration",task_key="WEB-1",project_id=project.id);db.add(task);db.flush()
    db.add(PMSTask(title="Review API contract",task_key="WEB-2",project_id=project.id,parent_task_id=task.id))
    folder=PMSNoteFolder(owner_id=owner.id,name="Reference",project_id=project.id,task_id=task.id,color="#8b5cf6",icon="code");db.add(folder);db.flush()
    content="# Overview\nThis document covers the API integration, authentication, endpoints, request formats and error handling.\n\n## Authentication\nUse the assigned API key when calling the project API.\n\n```http\nGET /users HTTP/1.1\nHost: api.example.com\n```\n\n## Endpoints\n| Method | Endpoint | Purpose |\n| --- | --- | --- |\n| GET | /users | List users |\n| POST | /users | Create a user |"
    for title,body,tags,pinned in [("API Documentation",content,["api","documentation","integration"],True),("Testing Notes","Test cases, environments and sample payloads.",["testing","api","qa"],False),("Integration Checklist","- [ ] Review authentication\n- [ ] Test error handling\n- [ ] Confirm API response formats",["checklist"],False),("API Meeting Notes","Discussion on rate limits, versioning and security.",["meeting","api"],False)]:
        note=PMSNote(owner_id=owner.id,title=title,content=body,project_id=project.id,task_id=task.id,tags=tags,pinned=pinned)
        db.add(note);db.flush();db.add(PMSNoteRevision(note_id=note.id,version=1,title=title,content=body))
    db.commit()
app=FastAPI()
app.include_router(auth_router,prefix="/api/v1")
app.include_router(pms_router,prefix="/api/v1")
@app.get("/api/v1/business-os/modules")
def enabled_modules(): return {"enabled_modules":["project_management","hrms"],"modules":[]}
def qa_db():
    with Session() as db: yield db
app.dependency_overrides[get_db]=qa_db
if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="127.0.0.1",port=1559)
