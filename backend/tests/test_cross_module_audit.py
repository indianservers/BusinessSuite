"""Real persistence and API authorization: no commercial service mocks."""
from uuid import uuid4
import pytest
from app.core.security import create_access_token
from app.models.user import User, Role, Permission
from app.common.models import CommonPerson
from app.apps.project_management.models import PMSProjectMember
from tests.test_connected_commercial import setup_business, link

CASES = [
    ("sales", ["srm_invoice_view"], "Member", True, False, False, True),
    ("project_manager", ["pms_manage_projects", "srm_invoice_create"], "Manager", True, False, False, True),
    ("contributor", ["pms_manage_tasks"], "Member", False, False, False, True),
    ("finance", ["srm_invoice_view", "srm_invoice_approve", "srm_collection_create"], "Member", True, True, True, True),
    ("read_only", ["srm_invoice_view"], "Viewer", True, False, False, True),
    ("outsider", ["srm_invoice_view"], None, False, False, False, True),
    ("removed", ["srm_invoice_view"], None, False, False, False, True),
    ("inactive", ["srm_invoice_view", "srm_invoice_approve"], "Member", False, False, False, False),
    ("other_tenant", ["srm_invoice_view", "srm_invoice_approve", "srm_collection_create"], "Member", False, False, False, True),
]

@pytest.mark.parametrize("name,permissions,membership,view,issue,pay,active", CASES)
def test_commercial_role_matrix(client, db, superuser_headers, name, permissions, membership, view, issue, pay, active):
    buyer, contact, project, team = setup_business(db)
    link(client, superuser_headers, buyer, contact, project, team)
    invoice = client.post(f"/api/v1/project-management/projects/{project.id}/invoices", headers=superuser_headers, json={"request_id":str(uuid4()),"lines":[{"description":"Role audit", "unit_price":100}]}).json()
    role = Role(name=f"audit_{name}", description="Isolated audit fixture")
    db.add(role); db.flush()
    for code in permissions:
        perm = db.query(Permission).filter_by(name=code).first()
        if not perm:
            perm=Permission(name=code,module="srm"); db.add(perm); db.flush()
        role.permissions.append(perm)
    user=User(email=f"{name}@audit.invalid",hashed_password="unused",role_id=role.id,is_active=active,is_superuser=False)
    db.add(user); db.flush()
    if name == "other_tenant":
        person=CommonPerson(organization_id=2,display_name="Other tenant",user_id=user.id);db.add(person);db.flush();db.expire(user, ["person"])
    if membership:
        db.add(PMSProjectMember(project_id=project.id,user_id=user.id,role=membership))
    if name == "removed":
        member=PMSProjectMember(project_id=project.id,user_id=user.id,role="Member");db.add(member);db.flush();db.delete(member)
    db.commit()
    headers={"Authorization":f"Bearer {create_access_token(user.id)}"}
    for suffix in ["", "/pdf"]:
        response=client.get(f"/api/v1/srm/invoices/{invoice['id']}{suffix}",headers=headers)
        assert (response.status_code==200) == view, (name,suffix,response.status_code,response.text[:200])
    issued=client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve",headers=headers)
    assert (issued.status_code==200) == issue, (name,issued.text)
    if not issue:
        assert client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve",headers=superuser_headers).status_code==200
    payment=client.post(f"/api/v1/srm/business/invoices/{invoice['id']}/payments",headers=headers,json={"request_id":str(uuid4()),"amount":25})
    assert (payment.status_code==201) == pay, (name,payment.text)
    if not view:
        history = client.get(f"/api/v1/srm/business/customers/{buyer.id}/history",headers=headers)
        if name in {"outsider", "removed"}:
            # Shared business directory is allowed; protected invoices and projects must be absent.
            assert history.status_code == 200
            assert history.json()["invoices"] == [] and history.json()["projects"] == []
        else:
            assert history.status_code in {403,404}


def test_unknown_delivery_outcome_survives_reload_without_resend(client, db, superuser_headers, monkeypatch):
    from app.apps.srm.models import SRMInvoice
    from app.apps.srm.commercial_models import InvoiceDelivery
    buyer, contact, project, team = setup_business(db)
    link(client, superuser_headers, buyer, contact, project, team)
    invoice=client.post(f"/api/v1/project-management/projects/{project.id}/invoices",headers=superuser_headers,json={"request_id":str(uuid4()),"lines":[{"description":"Ambiguous provider timeout", "unit_price":100}]}).json()
    assert client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve",headers=superuser_headers).status_code==200
    calls=[]
    def ambiguous_provider(*args,**kwargs):
        calls.append(1)
        raise TimeoutError("Simulated accepted-then-lost provider response")
    monkeypatch.setattr("app.apps.communication.services.delivery.deliver_email",ambiguous_provider)
    url=f"/api/v1/srm/invoices/{invoice['id']}/send"
    sent=client.post(url,headers=superuser_headers)
    assert sent.status_code==200 and sent.json()["delivery"]["status"]=="unknown"
    db.expire_all()
    assert db.get(SRMInvoice,invoice['id']).sent_at is None
    assert db.query(InvoiceDelivery).filter_by(invoice_id=invoice['id']).one().status=="unknown"
    retried=client.post(url,headers=superuser_headers)
    assert retried.json()["delivery"]["status"]=="unknown" and len(calls)==1
    assert client.get(f"/api/v1/project-management/projects/{project.id}/billing",headers=superuser_headers).json()["invoices"][0]["document_status"]=="issued"


def test_project_member_removal_revokes_existing_realtime_subscription(client, db, superuser_headers, monkeypatch):
    import asyncio
    from app.apps.project_management.realtime import pms_realtime_manager
    buyer, contact, project, team = setup_business(db)
    user=User(email="socket@audit.invalid",hashed_password="unused",is_active=True)
    db.add(user);db.flush()
    member=PMSProjectMember(project_id=project.id,user_id=user.id,role="Viewer")
    db.add(member);db.commit()
    class Socket:
        def __init__(self): self.messages=[]
        async def accept(self): pass
        async def send_text(self,text): self.messages.append(text)
    from contextlib import contextmanager
    @contextmanager
    def fixture_session():
        yield db
    monkeypatch.setattr(pms_realtime_manager, "_db_factory", fixture_session)
    socket=Socket()
    async def connect():
        await pms_realtime_manager.connect(socket,user_id=user.id,organization_id=1,accessible_project_ids={project.id})
        await pms_realtime_manager.broadcast({"projectId":project.id,"organizationId":1})
    asyncio.run(connect())
    assert len(socket.messages)==1
    try:
        response=client.delete(f"/api/v1/project-management/projects/{project.id}/members/{member.id}",headers=superuser_headers)
        assert response.status_code==200,response.text
        asyncio.run(pms_realtime_manager.broadcast({"projectId":project.id,"organizationId":1,"secret":"after-removal"}))
        assert len(socket.messages)==1
    finally:
        asyncio.run(pms_realtime_manager.disconnect(socket))


def test_multiple_legal_entities_and_similar_names_remain_explicit(client, db, superuser_headers):
    from app.models.company import Company
    from app.apps.crm.models import CRMCompany
    from app.apps.srm.commercial_models import SellerGrant, InvoiceContext
    buyer, contact, project, team = setup_business(db)
    second=Company(name="Second legal seller",legal_name="Second seller Ltd",address="Synthetic second seller")
    lookalike=CRMCompany(organization_id=2,name=buyer.name,email=buyer.email)
    db.add_all([second,lookalike]);db.commit()
    url=f"/api/v1/project-management/projects/{project.id}/commercial"
    payload={"customer_id":buyer.id,"contact_id":contact.id,"seller_id":second.id,"currency":"INR"}
    assert client.put(url,headers=superuser_headers,json=payload).status_code==403
    db.add(SellerGrant(organization_id=1,seller_id=second.id,active=True));db.commit()
    assert client.put(url,headers=superuser_headers,json=payload).status_code==200
    forbidden=client.put(url,headers=superuser_headers,json={**payload,"customer_id":lookalike.id})
    assert forbidden.status_code==404
    invoice=client.post(f"/api/v1/project-management/projects/{project.id}/invoices",headers=superuser_headers,json={"request_id":str(uuid4()),"lines":[{"description":"Explicit second seller", "unit_price":100}]}).json()
    assert client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve",headers=superuser_headers).status_code==200
    db.expire_all();ctx=db.get(InvoiceContext,invoice['id'])
    assert ctx.seller_id==second.id and ctx.seller_snapshot["legal_name"]=="Second seller Ltd"
    assert ctx.customer_snapshot["id"]==buyer.id
    assert db.query(CRMCompany).filter_by(name=buyer.name).count()==2


def test_realtime_checks_inactive_identity_and_current_membership(db, superuser_headers):
    import asyncio
    from contextlib import contextmanager
    from app.apps.project_management.realtime import PMSRealtimeManager
    buyer, contact, project, team = setup_business(db)
    user=User(email="revoked-socket@audit.invalid",hashed_password="unused",is_active=True)
    db.add(user);db.flush();membership=PMSProjectMember(project_id=project.id,user_id=user.id,role="Viewer");db.add(membership);db.commit()
    @contextmanager
    def fixture_session(): yield db
    manager=PMSRealtimeManager(db_factory=fixture_session)
    class Socket:
        def __init__(self): self.messages=[]
        async def accept(self): pass
        async def send_text(self,text): self.messages.append(text)
    socket=Socket()
    async def exercise():
        await manager.connect(socket,user_id=user.id,organization_id=1,accessible_project_ids={project.id})
        await manager.broadcast({"projectId":project.id})
        assert len(socket.messages)==1
        user.is_active=False;db.commit()
        await manager.broadcast({"projectId":project.id})
        assert len(socket.messages)==1
        user.is_active=True;db.delete(membership);db.commit()
        await manager.broadcast({"projectId":project.id})
        assert len(socket.messages)==1
        await manager.disconnect(socket)
    asyncio.run(exercise())


def test_project_member_creation_rejects_foreign_and_inactive_users(client, db, superuser_headers):
    buyer, contact, project, team = setup_business(db)
    foreign=User(email="foreign-member@audit.invalid",hashed_password="unused",is_active=True)
    inactive=User(email="inactive-member@audit.invalid",hashed_password="unused",is_active=False)
    db.add_all([foreign,inactive]);db.flush()
    db.add(CommonPerson(user_id=foreign.id,organization_id=2,display_name="Other tenant"));db.commit()
    for target in [foreign,inactive]:
        response=client.post(f"/api/v1/project-management/projects/{project.id}/members",headers=superuser_headers,json={"user_id":target.id,"role":"Member"})
        assert response.status_code==404,response.text
    assert db.query(PMSProjectMember).filter(PMSProjectMember.project_id==project.id,PMSProjectMember.user_id.in_([foreign.id,inactive.id])).count()==0


def test_realtime_rejects_revoked_session_and_expired_token(db, superuser_headers):
    from contextlib import contextmanager
    from datetime import datetime, timezone, timedelta
    from app.models.user import UserSession
    from app.apps.project_management.realtime import PMSRealtimeManager
    buyer, contact, project, team = setup_business(db)
    user=db.query(User).first()
    session=UserSession(user_id=user.id,session_token_hash="synthetic-test-hash",status="Active",expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
    db.add(session);db.commit()
    @contextmanager
    def fixture_session(): yield db
    manager=PMSRealtimeManager(db_factory=fixture_session)
    assert manager._authorized(user.id,project.id,session.id)
    session.status="Revoked";db.commit()
    assert not manager._authorized(user.id,project.id,session.id)
    assert not manager._authorized(user.id,project.id,token_expires_at=1)
