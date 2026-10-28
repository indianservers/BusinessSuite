"""Explicit module email events captured inside the source database transaction.

Only allowlisted fields trigger mail. Bodies contain no HR, financial or chat
content; recipients sign in to see the current authorized record.
"""
from uuid import uuid4
from hashlib import sha256
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.base_class import Base
from app.services.email_dispatch import queue_email

# table: module, human label, employee FK, user FKs, watched fields, destination
EVENTS = {
    "announcements": ("hrms", "Employee announcement", None, ("created_by",), ("is_published",), "/hrms/engagement"),
    "engagement_surveys": ("hrms", "Employee survey", None, ("created_by",), ("status",), "/hrms/engagement"),
    "notifications": ("notifications", "Business Suite notification", None, ("user_id",), (), "/notifications"),
    "approval_requests": ("approvals", "Approval decision", None, ("requester_user_id",), ("status",), "/hrms/approval-os"),
    "users": ("security", "Account access", None, ("id",), ("role_id", "is_active", "hashed_password"), "/login"),
    "admin_backup_requests": ("admin", "Backup request", None, ("requested_by",), ("status",), "/settings"),
    "recognitions": ("hrms", "Employee recognition", "to_employee_id", (), (), "/hrms/engagement"),
    "intern_hub_certificates": ("interns_hub", "Internship certificate", "employee_id", (), (), "/interns-hub"),
    "intern_hub_tickets": ("interns_hub", "Intern support ticket", "employee_id", (), ("status", "reply"), "/interns-hub"),
    "intern_completion_reviews": ("interns_hub", "Internship completion decision", "employee_id", (), ("decision",), "/interns-hub"),
    "intern_report_reviews": ("interns_hub", "Daily report review", None, (), ("decision",), "/interns-hub"),
    "workforce_messages": ("hrms", "Workforce message", "employee_id", (), (), "/notifications"),
    "certification_renewals": ("hrms", "Certification renewal", "employee_id", (), ("status",), "/hrms/lms"),
    "expense_claims": ("hrms", "Expense claim", "employee_id", ("submitted_by",), ("status", "reimbursed_at"), "/hrms/expenses"),
    "benefit_claims": ("hrms", "Benefit claim", "employee_id", (), ("status",), "/hrms/benefits"),
    "employee_onboardings": ("hrms", "Employee onboarding", "employee_id", (), ("status", "target_completion_date"), "/hrms/onboarding"),
    "employee_onboarding_tasks": ("hrms", "Onboarding task", None, ("assigned_to_user_id",), ("status", "assigned_to_user_id", "due_date"), "/hrms/onboarding"),
    "helpdesk_tickets": ("hrms", "Helpdesk ticket", "employee_id", ("assigned_to", "escalated_to"), ("status", "assigned_to", "escalated_at"), "/hrms/helpdesk"),
    "attendance_regularizations": ("hrms", "Attendance correction", "employee_id", (), ("status",), "/hrms/attendance"),
    "employee_change_requests": ("hrms", "Profile change request", "employee_id", (), ("status",), "/hrms/employees"),
    "asset_assignments": ("hrms", "Asset assignment", "employee_id", (), ("returned_date", "acknowledgement_signed", "is_active"), "/hrms/assets"),
    "exit_records": ("hrms", "Exit process", "employee_id", (), ("status", "last_working_date", "final_settlement_date"), "/hrms/exit"),
    "exit_checklist_items": ("hrms", "Exit clearance task", None, ("assigned_to_user",), ("is_completed", "assigned_to_user"), "/hrms/exit"),
    "performance_reviews": ("hrms", "Performance review", "employee_id", (), ("status",), "/hrms/performance"),
    "performance_goals": ("hrms", "Performance goal", "employee_id", (), ("status",), "/hrms/performance"),
    "learning_assignments": ("hrms", "Learning assignment", "employee_id", (), ("status", "due_date"), "/hrms/lms"),
    "learning_certifications": ("hrms", "Learning certification", "employee_id", (), ("status", "renewal_status"), "/hrms/lms"),
    "generated_documents": ("hrms", "HR document", "employee_id", (), ("is_signed",), "/hrms/documents"),
    "form16_documents": ("hrms", "Form 16", "employee_id", (), ("status", "published_at"), "/hrms/form16"),
    "probation_actions": ("hrms", "Probation decision", "employee_id", (), ("action_type",), "/hrms/probation"),
    "shift_rosters": ("hrms", "Shift roster", "employee_id", (), ("status", "shift_id", "roster_date"), "/hrms/shift-roster"),
    "shift_roster_assignments": ("hrms", "Shift assignment", "employee_id", (), ("status", "shift_id", "work_date"), "/hrms/shift-roster"),
    "background_verification_requests": ("hrms", "Background verification", "employee_id", ("initiated_by",), ("status", "consent_status"), "/hrms/background-verification"),
    "crm_leads": ("crm", "Lead assignment", None, ("owner_user_id",), ("owner_user_id", "next_follow_up_at"), "/crm/leads"),
    "crm_activities": ("crm", "CRM activity", None, ("owner_user_id",), ("status", "owner_user_id", "due_date"), "/crm/activities"),
    "crm_meetings": ("crm", "CRM meeting", None, ("owner_user_id",), ("status", "start_time", "end_time"), "/crm/meetings"),
    "pms_tasks": ("pms", "Task", None, ("assignee_user_id", "reporter_user_id"), ("status", "assignee_user_id", "due_date"), "/pms/my-work"),
    "pms_task_assignees": ("pms", "Assigned task", None, ("user_id",), ("execution_status", "due_date", "reviewer_user_id"), "/dashboard"),
    "pms_work_submissions": ("pms", "Work submission", None, ("user_id",), ("status",), "/dashboard"),
    "pms_work_reviews": ("pms", "Work review", None, (), (), "/dashboard"),
    "pms_milestones": ("pms", "Milestone", None, ("owner_user_id",), ("status", "due_date", "client_approval_status"), "/pms/projects"),
    "report_runs": ("analytics", "Report export", None, ("requested_by",), ("status",), "/analytics"),
    "analytics_report_runs": ("analytics", "Report run", None, ("run_by",), ("status",), "/analytics"),
    "analytics_exports": ("analytics", "Report export", None, ("requested_by",), ("status",), "/analytics"),
    "srm_sales_orders": ("srm", "Sales order", None, ("assigned_user_id", "created_by"), ("status", "assigned_user_id", "expected_end_date"), "/srm/sales-orders"),
    "srm_engagements": ("srm", "Engagement", None, ("assigned_user_id", "project_manager_user_id"), ("status", "planned_end_date"), "/srm/engagements"),
    "srm_contracts": ("srm", "Contract", None, ("created_by",), ("status", "expiry_date"), "/srm/contracts"),
    "srm_purchase_orders": ("inventory", "Purchase order", None, ("created_by",), ("status", "expected_date"), "/inventory"),
    "srm_goods_receipts": ("inventory", "Goods receipt", None, ("created_by",), ("status",), "/inventory"),
    "srm_production_orders": ("inventory", "Production order", None, ("created_by",), ("status", "completed_at"), "/inventory"),
    "srm_invoices": ("srm", "Invoice", None, ("created_by",), ("status", "due_date"), "/srm/invoices"),
    "srm_receipts": ("srm", "Payment receipt", None, ("created_by",), ("status",), "/srm/receipts"),
    "fam_vouchers": ("fam", "Accounting voucher", None, ("posted_by",), ("status",), "/fam"),
    "fam_purchase_bills": ("fam", "Purchase bill", None, (), ("status", "due_date"), "/fam"),
    "fam_vendor_payment_items": ("fam", "Vendor payment", None, (), ("status",), "/fam"),
    "fam_einvoice_jobs": ("fam", "E-invoice processing", None, ("created_by",), ("status",), "/fam"),
    "data_privacy_requests": ("admin", "Privacy request", "employee_id", ("assigned_to",), ("status", "assigned_to"), "/settings"),
    "recruitment_requisitions": ("hrms", "Recruitment requisition", None, ("requested_by",), ("status",), "/hrms/recruitment"),
    "portal_users": ("saas", "Portal account", None, (), ("status",), "/login"),
    "candidates": ("hrms", "Job application", None, (), ("status",), "/login"),
    "interviews": ("hrms", "Interview", None, (), ("status", "scheduled_at", "meet_link", "venue"), "/login"),
    "offer_letters": ("hrms", "Offer", None, (), ("status",), "/login"),
    "intern_hub_applications": ("interns_hub", "Internship application", None, (), ("status",), "/interns-hub"),
    "document_studio_documents": ("hrms", "Issued document", None, (), ("status",), "/hrms/documents"),
    "suite_form_replies": ("forms", "Form submission", None, (), ("status",), "/forms"),
    "helpdesk_replies": ("hrms", "Helpdesk reply", None, (), (), "/hrms/helpdesk"),
}


def record(db, table_name, identity):
    model = next((mapper.class_ for mapper in Base.registry.mappers if mapper.local_table.name == table_name), None)
    if model is None or not identity:
        return None
    # ORM column selections preserve request tenant criteria and read stored
    # values, even when the source instance has unflushed changes.
    keys = inspect(model).primary_key
    values = identity if isinstance(identity, tuple) else (identity,)
    row = db.query(*(getattr(model, column.name) for column in model.__table__.columns)).filter(
        *(getattr(model, key.name) == value for key, value in zip(keys, values))).first()
    return row._mapping if row else None


def _user(db, identity, org):
    from app.models.user import User
    from app.services.email_dispatch import user_can_receive
    user = db.get(User, identity) if identity else None
    if user and user.is_active and user_can_receive(db, user.id, user.email, org):
        return user.email, user.id, org


def _employee(db, identity, org):
    employee = record(db, "employees", identity)
    if not employee or employee.get("deleted_at"):
        return None
    branch = record(db, "branches", employee.get("branch_id"))
    company = branch.get("company_id") if branch else None
    if org and company and org != company:
        return None
    org = org or company
    if employee.get("user_id"):
        return _user(db, employee["user_id"], org)
    address = employee.get("work_email") or employee.get("personal_email")
    return (address, None, org) if address else None


def recipients(db, obj, spec):
    module, label, employee_fk, user_fks, watched, path = spec
    org = getattr(obj, "organization_id", None) if hasattr(obj, "organization_id") else getattr(obj, "company_id", None)
    found = []
    if employee_fk:
        found.append(_employee(db, getattr(obj, employee_fk, None), org))
        if obj.__tablename__ in {"expense_claims", "benefit_claims", "employee_change_requests", "attendance_regularizations"} and str(getattr(obj, "status", "")).casefold() in {"submitted", "pending", "pending manager approval"}:
            employee = record(db, "employees", getattr(obj, employee_fk, None))
            if employee:
                found.append(_employee(db, employee.get("reporting_manager_id"), org))
    for fk in user_fks:
        found.append(_user(db, getattr(obj, fk, None), org))
    table = obj.__tablename__
    if table in {"pms_tasks", "pms_milestones"}:
        project = record(db, "pms_projects", obj.project_id)
        if project:
            org = project.get("organization_id")
            found = []
            from app.apps.project_management.access import can_access_project
            from app.apps.project_management.models import PMSProject
            from app.models.user import User
            project_obj = db.get(PMSProject, obj.project_id)
            for fk in user_fks:
                person = _user(db, getattr(obj, fk, None), org)
                if person and can_access_project(db, project_obj, db.get(User, person[1])):
                    found.append(person)
    if table in {"candidates", "portal_users", "intern_hub_applications"}:
        found.append((obj.email, None, org))
    if table in {"interviews", "offer_letters"}:
        candidate = record(db, "candidates", obj.candidate_id)
        if candidate:
            found.append((candidate["email"], None, org))
            if table == "interviews":
                job = record(db, "jobs", candidate["job_id"])
                branch = record(db, "branches", job.get("branch_id")) if job else None
                interview_org = branch["company_id"] if branch else org
                if interview_org:
                    import json
                    try:
                        employee_ids = json.loads(obj.interviewer_ids or "[]")
                    except (ValueError, TypeError):
                        employee_ids = []
                    if isinstance(employee_ids, list):
                        found.extend(_employee(db, identity, interview_org) for identity in employee_ids if isinstance(identity, int))
    if table == "document_studio_documents":
        if obj.recipient_type == "employee":
            found.append(_employee(db, obj.recipient_id, org))
        elif obj.recipient_type == "application":
            intern = record(db, "intern_hub_applications", obj.recipient_id)
            if intern and intern["organization_id"] == org:
                found.append((intern["email"], None, org))
    if table == "suite_form_replies":
        form = record(db, "suite_forms", obj.form_id)
        if form:
            found.append(_user(db, form["owner_id"], form["organization_id"]))
            for field in (form.get("published") or {}).get("fields", []):
                if field.get("type") == "email":
                    address = (obj.answers or {}).get(field.get("id"))
                    if isinstance(address, str) and "@" in address:
                        found.append((address, None, form["organization_id"]))
                        break
    if table == "intern_report_reviews":
        report = record(db, "intern_hub_reports", obj.report_id)
        if report:
            found.append(_employee(db, report["employee_id"], org))
    if table == "helpdesk_replies" and not obj.is_internal:
        ticket = record(db, "helpdesk_tickets", obj.ticket_id)
        if ticket:
            found.append(_employee(db, ticket["employee_id"], ticket.get("organization_id")))
            found.append(_user(db, ticket["assigned_to"], ticket.get("organization_id")))
    if table in {"pms_task_assignees", "pms_work_submissions", "pms_work_reviews"}:
        task_id = getattr(obj, "task_id", None)
        submitter_id = getattr(obj, "user_id", None)
        if table == "pms_work_reviews":
            submission = record(db, "pms_work_submissions", obj.submission_id)
            task_id = submission["task_id"] if submission else None
            submitter_id = submission["user_id"] if submission else None
        task = record(db, "pms_tasks", task_id)
        project = record(db, "pms_projects", task["project_id"]) if task else None
        org = project["organization_id"] if project else None
        found = [_user(db, submitter_id, org)] if project else []
        if table == "pms_work_submissions" and obj.status == "Pending Review":
            assignment = record(db, "pms_task_assignees", (task_id, submitter_id))
            if assignment:
                found.append(_user(db, assignment["reviewer_user_id"], org))
    if table in {"fam_purchase_bills", "fam_vendor_payment_items"}:
        if table == "fam_vendor_payment_items":
            run = record(db, "fam_vendor_payment_runs", obj.payment_run_id)
            org = run.get("company_id") if run else None
        party = record(db, "fam_parties", obj.vendor_id)
        if org and party and party["company_id"] == org and party.get("active") and party.get("email"):
            found.append((party["email"], None, org))
    return list({item[0].casefold(): item for item in found if item and item[0]}.values())


@event.listens_for(Session, "before_flush")
def capture_email_events(db, context, instances):
    if not settings.EMAIL_NOTIFICATIONS_ENABLED or db.info.get("suppress_email_events"):
        return
    pending = db.info.setdefault("suite_email_events", [])
    reviewed_submissions = {item.submission_id for item in db.new if getattr(item, "__tablename__", "") == "pms_work_reviews"}
    reviewed_assignments = set()
    for identity in reviewed_submissions:
        submission = record(db, "pms_work_submissions", identity)
        if submission:
            reviewed_assignments.add((submission["task_id"], submission["user_id"]))
    for obj in list(db.new) + list(db.dirty):
        table = getattr(obj, "__tablename__", "")
        spec = EVENTS.get(table)
        if not spec or obj in db.deleted:
            continue
        if table == "notifications" and ("email" in (obj.channels or []) or obj.event_type == "shared.notification" or (obj.event_type or "").startswith("email.")):
            continue
        # Portal invitations have a dedicated token-bearing template.
        if table == "portal_users" and db.info.get("portal_invitation_email"):
            continue
        state = inspect(obj)
        new = obj in db.new
        if table == "pms_work_submissions" and not new and obj.id in reviewed_submissions:
            continue
        if table == "pms_task_assignees" and (obj.task_id, obj.user_id) in reviewed_assignments:
            continue
        if table == "users" and new:
            continue
        if table == "announcements" and not obj.is_published:
            continue
        if table == "engagement_surveys" and obj.status not in {"Active", "Published", "Open"}:
            continue
        if table == "analytics_report_runs" and (obj.parameters_json or {}).get("schedule_id"):
            continue
        if table == "approval_requests" and (new or str(obj.status).lower() in {"pending", "submitted"}):
            continue
        changed = [name for name in spec[4] if name in state.attrs and state.attrs[name].history.has_changes()]
        if not new and changed:
            previous = record(db, table, state.identity)
            if previous:
                changed = [name for name in changed if previous[name] != getattr(obj, name)]
        if not new and not changed:
            continue
        if getattr(obj, "deleted_at", None):
            continue
        # Draft offers/documents and internal support notes must stay internal.
        if str(getattr(obj, "status", "")).lower() in {"draft", "queued", "processing"}:
            continue
        if table == "helpdesk_replies" and obj.is_internal:
            continue
        # Signup receipts/approvals already have their dedicated branded template.
        if table == "intern_hub_applications" and (new or obj.status == "Approved"):
            continue
        if table == "form16_documents" and not obj.published_at:
            continue
        pending.append((obj, spec, uuid4().hex, new))


@event.listens_for(Session, "after_flush_postexec")
def enqueue_email_events(db, context):
    for obj, spec, key, new in db.info.pop("suite_email_events", []):
        module, label, employee_fk, user_fks, watched, path = spec
        status = str(getattr(obj, "status", None) or getattr(obj, "execution_status", None) or getattr(obj, "decision", "") or "")
        if status.lower() in {"draft", "queued", "processing"}:
            continue
        subject = f"{label}: {status or ('created' if new else 'updated')}"
        identity = getattr(obj, "id", None) or getattr(obj, "task_id", None)
        body = f"{label} #{identity} has an update."
        if status:
            body += f"\nCurrent status: {status}."
        if obj.__tablename__ == "suite_form_replies" and new:
            body = f"A form submission has been received. Submission reference: {obj.id}."
        if obj.__tablename__ == "interviews" and obj.scheduled_at:
            body += f"\nInterview time: {obj.scheduled_at.isoformat()}. Contact your recruitment coordinator for joining details."
        if obj.__tablename__ == "portal_users":
            body += "\nYour portal uses an invitation token. Contact your administrator for portal access instructions."
        body += f"\nSign in to review details: {settings.FRONTEND_PUBLIC_URL.rstrip('/')}{path}"
        for address, user_id, org in recipients(db, obj, spec):
            broadcast = obj.__tablename__ in {"announcements", "engagement_surveys"}
            row = queue_email(db, recipient=address, user_id=user_id, organization_id=org,
                subject=subject, body=body, module=module,
                event_key=f"broadcast:{obj.__tablename__}:{obj.id}" if broadcast else f"event:{key}:{sha256(address.casefold().encode()).hexdigest()}")
            if broadcast and row:
                row.status = "broadcast"


@event.listens_for(Session, "after_soft_rollback")
def discard_rolled_back_events(db, transaction):
    db.info.pop("suite_email_events", None)
