"""Remove only this live audit's tagged fixtures from the verified local database.

Financial references have no vouchers or allocations. Operational records are
soft deleted, and approval history remains available as verification evidence.
"""
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from sqlalchemy import or_
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import settings

url = make_url(settings.SQLALCHEMY_DATABASE_URI)
assert url.host in {"localhost", "127.0.0.1"} and url.database == "business_suite"
from app.db.base import Base
from app.db.session import SessionLocal
from app.models.user import User, UserSession
from app.models.recruitment import Candidate
from app.apps.crm.models import CRMDeal
from app.apps.project_management.models import PMSTask, PMSProject, PMSWorkspace
from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
from app.apps.fam.models import FAMBillReference, FAMBillAllocation
from app.apps.srm.models import SRMSalesOrder, SRMEngagement, SRMBillingPlan, SRMInvoice
from app.shared.follow_ups import FollowUp
from app.access.models import AccessMembership, AccessPolicy
from app.apps.power_apps.approvals.models import ApprovalPolicy
from app.apps.power_apps.models import PowerResource

state = json.loads((ROOT / ".tmp/workflow-board-live-records.json").read_text())
run, records = state["run"], state["records"]
assert run == "WFV1794138560767"
now = datetime.now(timezone.utc)
report = {"run": run, "removedBillReferences": [], "softDeleted": [], "revokedUsers": [], "retainedApprovalEvidence": records["approval"]["id"]}
with SessionLocal() as db:
    for entry in records["bills"]:
        bill = db.get(FAMBillReference, entry["id"])
        if bill is None:
            continue
        assert bill.company_id == 1 and bill.bill_number == entry["title"]
        assert bill.source_record_type == "workflow_board_live_verification" and bill.source_record_id == run
        assert bill.original_amount == bill.outstanding_amount == Decimal("0.01")
        assert bill.voucher_id is None and bill.voucher_line_id is None
        assert not db.query(FAMBillAllocation).filter(or_(FAMBillAllocation.from_bill_reference_id == bill.id, FAMBillAllocation.to_bill_reference_id == bill.id)).count()
        report["removedBillReferences"].append(bill.id)
        db.delete(bill)
    candidate = db.get(Candidate, records["candidate"]["id"])
    if candidate:
        assert candidate.first_name == run and candidate.email == run.lower() + "@example.com"
        assert not candidate.interviews and candidate.offer is None
        db.delete(candidate)
        report["removedCandidate"] = candidate.id
    deal = db.get(CRMDeal, records["deal"]["id"])
    assert deal.name == run + " dashboard deal" and deal.organization_id == 1
    deal.deleted_at = now
    report["softDeleted"].append({"deal": deal.id})
    for key in ["task", "oldTask"]:
        entry = records.get(key)
        if entry:
            task = db.get(PMSTask, entry["id"])
            assert task.title == run + " dashboard task"
            task.deleted_at = now
            report["softDeleted"].append({"task": task.id})
    project = db.get(PMSProject, records["qaProject"]["id"])
    workspace = db.get(PMSWorkspace, records["qaWorkspace"]["id"])
    assert project.name.startswith(run) and workspace.name.startswith(run)
    assert project.workspace_id == workspace.id and workspace.organization_id == 1
    assert not db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.deleted_at.is_(None)).count()
    project.deleted_at = now
    archive = db.get(WorkspaceArchive, workspace.id)
    if not archive:
        archive = WorkspaceArchive(workspace_id=workspace.id)
        db.add(archive)
    archive.deleted_at, archive.deleted_by, archive.batch_key = now, state["qaActors"]["verifier"]["id"], run
    report["softDeleted"].extend([{"project": project.id}, {"workspace": workspace.id}])
    order = db.get(SRMSalesOrder, records["order"]["id"])
    assert order.order_number == run and order.organization_id == 1
    assert order.customer_id is None and order.crm_deal_id is None
    assert not db.query(SRMInvoice).filter(SRMInvoice.sales_order_id == order.id).count()
    assert not db.query(FollowUp).filter(FollowUp.order_id == order.id).count()
    order.deleted_at = now
    report["softDeleted"].append({"order": order.id})
    for engagement in db.query(SRMEngagement).filter_by(sales_order_id=order.id):
        assert engagement.name.startswith(run) and engagement.pms_project_id is None
        engagement.deleted_at = now
        for plan in db.query(SRMBillingPlan).filter_by(engagement_id=engagement.id):
            assert plan.status == "draft"
            plan.status = "cancelled"
        report["softDeleted"].append({"engagement": engagement.id})
    for key in ["policy", "qaPolicy"]:
        policy = db.get(ApprovalPolicy, records[key]["id"])
        assert db.get(PowerResource, policy.resource_id).name.startswith(run)
        assert not policy.enabled, "Disable policy through the live API first"
    for actor in state["qaActors"].values():
        user = db.get(User, actor["id"])
        assert user.email == actor["email"] and user.email.startswith(run.lower()) and not user.is_superuser
        user.is_active = False
        db.query(UserSession).filter_by(user_id=user.id).update({"status": "Revoked"}, synchronize_session="fetch")
        for membership in db.query(AccessMembership).filter_by(user_id=user.id):
            membership.active = False
            membership.is_admin = False
        for policy in db.query(AccessPolicy).filter_by(user_id=user.id):
            policy.status = "deactivated"
            policy.version += 1
        report["revokedUsers"].append(user.id)
    db.commit()
    assert not db.query(FAMBillReference).filter_by(source_record_type="workflow_board_live_verification", source_record_id=run).count()
    report["remainingAuditBillReferences"] = 0
(ROOT / "docs/qa/workflow-board-live/cleanup.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report))
