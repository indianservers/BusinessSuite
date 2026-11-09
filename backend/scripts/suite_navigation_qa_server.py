"""Loopback UI QA on disposable SQLite or guarded PostgreSQL, never the app DB."""
import asyncio
from contextvars import ContextVar
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import secrets
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temporary = tempfile.TemporaryDirectory(prefix="suite-navigation-qa-")
qa_database = "sqlite:///" + str(Path(temporary.name) / "navigation.db")
if os.environ.get("SUITE_QA_POSTGRES_URL"):
    from sqlalchemy.engine import make_url
    candidate = make_url(os.environ["SUITE_QA_POSTGRES_URL"])
    if candidate.get_backend_name() != "postgresql" or candidate.host != "127.0.0.1" or not (candidate.database or "").startswith("bs_payroll_") or not candidate.database.endswith("_test"):
        raise RuntimeError("QA PostgreSQL must be an isolated loopback bs_payroll_*_test database")
    qa_database = candidate.render_as_string(hide_password=False)
    os.environ.update(PLATFORM_DATABASE_URL=qa_database,TENANT_DATABASES_ENABLED="false")
os.environ.update(
    ENVIRONMENT="test", DEBUG="false",
    DATABASE_URL=qa_database,
    SECRET_KEY=secrets.token_urlsafe(48), REFRESH_SECRET_KEY=secrets.token_urlsafe(48),
    SECRET_KEY_PREVIOUS="", REFRESH_SECRET_KEY_PREVIOUS="",
    INSTALLED_APPS="hrms,crm,project_management,srm,fam,power_apps",
    STORAGE_BACKEND="local", UPLOAD_DIR=str(Path(temporary.name) / "uploads"),
    OPENAI_API_KEY="", ANTHROPIC_API_KEY="", GEMINI_API_KEY="",
    MAIL_USERNAME="", MAIL_PASSWORD="", MAIL_SERVER="",
    FIREBASE_PROJECT_ID="", FIREBASE_WEB_CONFIG="{}",
    CRM_WHATSAPP_PROVIDER="mock", CRM_WHATSAPP_ACCESS_TOKEN="",
    CRM_WHATSAPP_PHONE_NUMBER_ID="", CRM_WHATSAPP_BUSINESS_ACCOUNT_ID="",
    CRM_WHATSAPP_APP_ID="", CRM_WHATSAPP_EMBEDDED_CONFIG_ID="",
    BUSINESSSUITE_BACKUP_SCHEDULER="false", SEED_DEMO_DATA="false",
    SECURITY_RATE_LIMIT_ENABLED="false",
)
from app.main import app
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.company import Company
from app.models.user import User, Role, Permission
from app.models.notification import Notification
from app.common.models import CommonPerson
from app.access.models import AccessMembership, AccessPolicy
from app.apps.business_os.services.module_service import ensure_business_os_seed
from app.core.security import get_password_hash, pwd_context
from app.api.v1.auth import _hash_reset_token

pwd_context.update(bcrypt__rounds=4)
if engine.dialect.name == "postgresql":
    from app.db.migrations import upgrade_schema
    upgrade_schema()
else:
    Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add_all([Company(id=1, name="Indian Servers", email="company1@suiteqa.example.com", is_active=True), Company(id=2, name="Studio Operations", email="company2@suiteqa.example.com", is_active=True)])
    admin_role, employee_role, hr_role = Role(name="admin"), Role(name="employee"), Role(name="hr")
    db.add_all([admin_role, employee_role, hr_role]); db.flush()
    for name in ["payroll_view", "payroll_run", "payroll_approve", "employee_view", "company_view", "report_view"]:
        permission = db.query(Permission).filter_by(name=name).first()
        if not permission:
            permission = Permission(name=name, module="hrms", description="HR payroll UI verification")
            db.add(permission)
        hr_role.permissions.append(permission)
    users = []
    for email, role, superuser in [("admin@suiteqa.example.com", admin_role, True), ("employee@suiteqa.example.com", employee_role, False), ("reset@suiteqa.example.com", employee_role, False), ("hr@suiteqa.example.com", hr_role, False)]:
        user = User(email=email, hashed_password=get_password_hash("SuiteQA@12345"), is_active=True, is_superuser=superuser, role=role,
                    person=CommonPerson(organization_id=1, primary_email=email, display_name=email.split("@")[0].title()))
        db.add(user); users.append(user)
    db.flush()
    db.add(AccessMembership(user_id=users[0].id, company_id=2, active=True, is_admin=True))
    db.add(AccessPolicy(user_id=users[1].id, company_id=1, status="active", grants={"hrms": {"enabled": True, "role": "employee", "scope": "own", "permissions": ["employee_view", "profile_view"], "actions": ["view"]}}))
    db.add(AccessPolicy(user_id=users[3].id, company_id=1, status="active", grants={"hrms": {"enabled": True, "role": "hr", "scope": "organization", "permissions": ["payroll_view", "payroll_run", "payroll_approve", "employee_view", "company_view", "report_view"], "actions": ["view", "create", "edit", "approve", "configure", "export"]}}))
    users[2].password_reset_token = _hash_reset_token("suite-qa-reset-token")
    users[2].password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    for device in ["desktop", "mobile"]:
        reset_user = User(email=f"reset-{device}@suiteqa.example.com", hashed_password=get_password_hash("SuiteQA@12345"), is_active=True, role=employee_role,
                          person=CommonPerson(organization_id=1, primary_email=f"reset-{device}@suiteqa.example.com", display_name="Reset QA"),
                          password_reset_token=_hash_reset_token(f"suite-qa-reset-{device}-token"), password_reset_expires=datetime.now(timezone.utc) + timedelta(hours=1))
        db.add(reset_user)
    for user in users[:2]:
        for module, url, title, company in [("hrms", "/hrms/profile", "Profile update available", 1), ("crm", "/crm/contacts", "Review your contacts", 1), ("fam", "/fam/ledgers", "Finance update", 1), ("hrms", "/hrms/profile", "Other company private update", 2)]:
            db.add(Notification(user_id=user.id, company_id=company, module=module, action_url=url, title=title, message="A QA notification for navigation verification.", priority="normal", channels=["in_app"], is_read=False))
    from app.models.company import Branch
    from app.branches.models import BranchGrant
    for company in [1, 2]:
        branch = Branch(company_id=company, name="Navigation QA branch", code="NAVQA")
        db.add(branch); db.flush()
        for user in [users[0], users[1], users[3]] if company == 1 else users[:1]:
            db.add(BranchGrant(company_id=company, user_id=user.id, branch_id=branch.id, can_write=True))
        ensure_business_os_seed(db, company)
    db.flush()
    from app.branches.migration import backfill
    backfill(db.connection(), 1)
    backfill(db.connection(), 2)
    # These synthetic notifications explicitly belong to their company's QA branch.
    from app.branches.models import BranchOwnership
    for notification in db.query(Notification).all():
        branch = db.query(Branch).filter_by(company_id=notification.company_id, code="NAVQA").one()
        existing = db.get(BranchOwnership, ("notifications", str(notification.id)))
        if existing:
            existing.company_id, existing.branch_id = notification.company_id, branch.id
        else:
            db.add(BranchOwnership(resource_table="notifications", resource_key=str(notification.id), company_id=notification.company_id, branch_id=branch.id, source="explicit QA fixture"))
    db.commit()

if os.environ.get("SUITE_QA_COMMERCIAL_CASE") == "1":
    from datetime import date
    from tests.srm_test_utils import seed_invoice_parties
    from app.apps.srm.models import SRMEngagement, SRMSalesOrder, SRMBillingPlan, SRMBillingMilestone, SRMInvoiceDraft, SRMInvoice, SRMAuditLog
    from app.apps.business_os.models import BOSEnabledModule
    with SessionLocal() as db:
        seed_invoice_parties(db)
        actor=db.query(User).filter_by(email="admin@suiteqa.example.com").one()
        db.query(BOSEnabledModule).filter_by(company_id=1,module_key="project_management").update({"enabled":True})
        order=SRMSalesOrder(organization_id=1,order_number="QA-225-SOURCE",title="Reopened delivery",customer_id=101,status="confirmed",currency="INR",total_amount=100,created_by=actor.id)
        db.add(order);db.flush()
        closed=SRMEngagement(organization_id=1,engagement_number="QA-225-CLOSED",name="Reopen mistaken closure",customer_id=101,sales_order_id=order.id,status="closed",created_by=actor.id)
        cancel=SRMEngagement(organization_id=1,engagement_number="QA-224-CANCEL",name="Cancel before delivery",customer_id=101,status="created",created_by=actor.id)
        amend=SRMEngagement(organization_id=1,engagement_number="QA-222-AMEND",name="Amend milestone",customer_id=101,status="created",created_by=actor.id)
        move=SRMEngagement(organization_id=1,engagement_number="QA-223-MOVE",name="Move milestone period",customer_id=101,status="created",created_by=actor.id)
        db.add_all([closed,cancel,amend,move]);db.flush()
        history=SRMBillingPlan(organization_id=1,engagement_id=closed.id,name="QA-225-HISTORY",status="completed",total_amount=100,created_by=actor.id)
        plan=SRMBillingPlan(organization_id=1,engagement_id=amend.id,name="QA-222-PLAN",status="active",total_amount=4000,created_by=actor.id)
        period=SRMBillingPlan(organization_id=1,engagement_id=move.id,name="QA-223-PLAN",status="active",total_amount=4000,created_by=actor.id)
        db.add_all([history,plan,period]);db.flush()
        draft=SRMInvoiceDraft(organization_id=1,engagement_id=closed.id,billing_plan_id=history.id,customer_id=101,source_type="billing_milestone",status="approved",total_amount=100,created_by=actor.id)
        db.add(draft);db.flush()
        db.add(SRMInvoice(organization_id=1,invoice_number="QA-225-PAID-HISTORY",invoice_draft_id=draft.id,engagement_id=closed.id,customer_id=101,status="paid",total_amount=100,paid_amount=100,balance_amount=0,created_by=actor.id))
        db.add_all([SRMBillingMilestone(billing_plan_id=history.id,name="QA-225-OLD-MILESTONE",amount=100,status="invoiced",invoice_draft_id=draft.id),
                    SRMBillingMilestone(billing_plan_id=plan.id,name="QA-222-4000",amount=4000,due_date=date.today()),
                    SRMBillingMilestone(billing_plan_id=period.id,name="QA-223-PERIOD",amount=4000,due_date=date.today().replace(day=15),status="approved")])
        db.flush();backfill(db.connection(),1)
        from app.apps.crm.models import CRMCompany
        qa_branch=db.query(Branch).filter_by(company_id=1,code="NAVQA").one()
        for model in (SRMSalesOrder,SRMEngagement,SRMBillingPlan,SRMBillingMilestone,SRMInvoiceDraft,SRMInvoice,CRMCompany):
            for row in db.query(model).all():
                ownership=db.get(BranchOwnership,(model.__tablename__,str(row.id)))
                if ownership: ownership.company_id,ownership.branch_id=1,qa_branch.id
                else: db.add(BranchOwnership(resource_table=model.__tablename__,resource_key=str(row.id),company_id=1,branch_id=qa_branch.id,source="explicit commercial QA fixture"))
        db.commit()

    @app.middleware("http")
    async def capture_commercial_records(request,call_next):
        response=await call_next(request)
        import json
        with SessionLocal() as db:
            state={"environment":"Disposable Suite QA SQLite, commercial cases222-225", "engagements":[{"id":r.id,"number":r.engagement_number,"status":r.status,"project_id":r.pms_project_id} for r in db.query(SRMEngagement).all()],
                   "plans":[{"id":r.id,"engagement_id":r.engagement_id,"name":r.name,"status":r.status,"total":float(r.total_amount)} for r in db.query(SRMBillingPlan).all()],
                   "milestones":[{"id":r.id,"plan_id":r.billing_plan_id,"amount":float(r.amount),"due_date":str(r.due_date),"status":r.status,"draft_id":r.invoice_draft_id} for r in db.query(SRMBillingMilestone).all()],
                   "invoices":[{"id":r.id,"number":r.invoice_number,"engagement_id":r.engagement_id,"status":r.status,"total":float(r.total_amount),"paid":float(r.paid_amount),"balance":float(r.balance_amount)} for r in db.query(SRMInvoice).all()],
                   "audit":[{"entity":r.entity_type,"id":r.entity_id,"action":r.action,"actor":r.actor_user_id,"before":r.before_json,"after":r.after_json} for r in db.query(SRMAuditLog).all()]}
        (Path(__file__).resolve().parents[2]/"outputs"/"workflows-222-225-browser-records.json").write_text(json.dumps(state,indent=2,default=str),encoding="utf-8")
        return response

# These navigation tests do not need schedulers, external workers, or production
# startup migrations. All tables and test users were created above.
@asynccontextmanager
async def qa_lifespan(application):
    yield
app.router.lifespan_context = qa_lifespan
request_lock = asyncio.Lock()
inside_qa_request = ContextVar("inside_qa_request", default=False)
@app.middleware("http")
async def sqlite_requests(request, call_next):
    # Canonical record adapters make nested ASGI requests from a worker thread.
    # They belong to the already-serialized outer request and must not acquire
    # an asyncio lock owned by the server's different event loop.
    if engine.dialect.name == "postgresql" or inside_qa_request.get():
        return await call_next(request)
    async with request_lock:
        token = inside_qa_request.set(True)
        try:
            return await call_next(request)
        finally:
            inside_qa_request.reset(token)

if __name__ == "__main__":
    import uvicorn
    if sys.platform == 'win32':
        # Local browser probes can close sockets during Windows proactor accept.
        # This QA server does not launch subprocesses from its event loop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try: uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("SUITE_QA_PORT", "1551")), log_level="warning")
    finally:
        engine.dispose()
        temporary.cleanup()
