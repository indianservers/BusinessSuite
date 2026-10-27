"""Disposable local HTTP server for real two-browser communication QA.
No production credentials or database are read. Stop the process to discard data.
"""
import os, secrets, sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
qa_dir = tempfile.TemporaryDirectory(prefix="businesssuite-communication-qa-")
os.environ.update(ENVIRONMENT="test",DATABASE_URL="sqlite:///"+str(Path(qa_dir.name)/"qa.db"),SECRET_KEY=secrets.token_urlsafe(48),REFRESH_SECRET_KEY=secrets.token_urlsafe(48),INSTALLED_APPS="hrms,crm,project_management,srm,fam",REALTIME_TRANSPORT="database",STORAGE_BACKEND="local",UPLOAD_DIR=str(Path(qa_dir.name)/"uploads"),OPENAI_API_KEY="",ANTHROPIC_API_KEY="",GEMINI_API_KEY="")
from app.main import app
import asyncio
qa_request_lock=asyncio.Lock()
@app.middleware("http")
async def serialize_sqlite_qa(request,call_next):
    async with qa_request_lock:
        return await call_next(request)
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.company import Company
from app.models.user import User,Role,Permission
from app.common.models import CommonPerson
from app.apps.project_management.models import PMSWorkspace,PMSWorkspaceMember
from app.apps.project_management.chat_models import ChatConversation,ChatMember,ChatMessage
from app.core.security import create_access_token
from uuid import uuid4
from sqlalchemy import event
@event.listens_for(engine, "connect")
def sqlite_configuration(connection, record):
    cursor=connection.cursor();cursor.execute("PRAGMA journal_mode=WAL");cursor.execute("PRAGMA busy_timeout=5000");cursor.close()
@event.listens_for(engine, "handle_error")
def diagnostic(context):
    print("QA database diagnostic: " + str(context.original_exception),flush=True)
Base.metadata.create_all(engine)
with SessionLocal() as db:
    company=Company(name="Communication QA",is_active=True);db.add(company);db.flush()
    perm=Permission(name="pms_view",module="project_management");db.add(perm)
    role=Role(name="pms_team_member",permissions=[perm]);db.add(role);db.flush()
    users=[User(email=f"qa{i}@communication.test",hashed_password="unused",is_superuser=i==0,is_active=True,role=role) for i in range(2)]
    db.add_all(users);db.flush()
    for user in users:db.add(CommonPerson(user_id=user.id,primary_email=user.email,display_name=["Priya Sharma","Aarav Mehta"][users.index(user)],organization_id=company.id))
    workspace=PMSWorkspace(name="Product team",organization_id=company.id);db.add(workspace);db.flush()
    db.add_all([PMSWorkspaceMember(workspace_id=workspace.id,user_id=u.id,role="Owner" if u.is_superuser else "Member") for u in users])
    room=ChatConversation(workspace_id=workspace.id,key=str(uuid4()),kind="channel",name="general",description="Team updates, discussions and workspace collaboration.",visibility="private",owner_id=users[0].id);db.add(room);db.flush()
    db.add_all([ChatMember(conversation_id=room.id,user_id=u.id,active=True,history_after=0,read_id=0) for u in users])
    db.add(ChatMessage(conversation_id=room.id,author_id=users[0].id,client_id=str(uuid4()),body="Good morning team! Please test the deployment and share your feedback here."))
    db.commit()
    from app.apps.business_os.services.module_service import ensure_business_os_seed
    ensure_business_os_seed(db,company.id);db.commit()
    session={"api":"http://127.0.0.1:1541","workspace":workspace.id,"conversation":room.id,"users":[{"id":u.id,"email":u.email,"role":"pms_team_member","is_superuser":u.is_superuser,"token":create_access_token(str(u.id))} for u in users]}
    target=Path(__file__).resolve().parents[2]/".tmp"/"communication-qa-session.json";target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(session),encoding="utf-8")
print("Disposable communication QA server ready on 127.0.0.1:1541",flush=True)
import uvicorn
uvicorn.run(app,host="127.0.0.1",port=1541,log_level="warning")
