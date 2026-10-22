"""Add a connected, repeatable PMS showcase to the configured local database.

Run from backend: venv/Scripts/python.exe scripts/seed_pms_showcase.py
Existing records are never reset. The manifest records exactly what was added.
No email, integration webhook, accounting handoff, or background job is invoked.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.base import Base  # register every referenced model
from app.db.session import SessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User, Role
from app.models.notification import Notification
from app.common.models import CommonPerson
from app.apps.project_management import models as m

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "backend/backups/pms_demo_manifest.json"
OUTPUT = ROOT / "Mockup images/PMS Screenshots"
MARK = "PMS-DEMO-20261022"
TODAY = date(2026, 10, 22)
NOW = datetime(2026, 10, 22, 10, 0)
WEEK = TODAY - timedelta(days=TODAY.weekday())


def main():
    engine.echo = False
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        with SessionLocal() as db:
            if all(db.get(m.PMSWorkspace, wid) for wid in manifest["workspace_ids"]):
                print(json.dumps({"status": "already_seeded", "counts": manifest["counts"]}, indent=2))
                return
        raise RuntimeError("Manifest exists but its workspaces are missing; inspect before reseeding.")
    counts = defaultdict(int)
    ids = defaultdict(list)
    def add(db, cls, **values):
        row = cls(**values)
        db.add(row)
        db.flush()
        counts[cls.__tablename__] += 1
        if hasattr(row, "id"):
            ids[cls.__tablename__].append(row.id)
        return row

    with SessionLocal() as db:
        owner = db.query(User).filter_by(email="admin@karyaflow.com").one()
        manager = db.query(User).filter_by(email="manager@karyaflow.com").one()
        client_user = db.query(User).filter_by(email="client@karyaflow.com").one()
        superuser = db.query(User).filter_by(email="admin@aihrms.com").first()
        team_role = db.query(Role).filter_by(name="pms_team_member").one()
        password_hash = get_password_hash("DemoPMS@2026")
        first_names = ["Maya", "Arjun", "Priya", "Rohan", "Isha", "Vikram", "Nora", "Dev", "Ananya", "Kiran", "Neha", "Rahul", "Aditi", "Sanjay", "Meera", "Kabir", "Tara", "Nikhil"]
        last_names = ["Desai", "Mehta", "Shah", "Rao", "Nair", "Patel", "Kapoor", "Iyer", "Gupta", "Joshi", "Sethi", "Malhotra"]
        people = []
        for i in range(216):
            first, last = first_names[i % 18], last_names[i // 18]
            email = f"{first.lower()}.{last.lower()}.pmsdemo@example.com"
            person = db.query(User).filter_by(email=email).first()
            if not person:
                person = add(db, User, email=email, hashed_password=password_hash, role_id=team_role.id, is_active=True, is_superuser=False)
                add(db, CommonPerson, user_id=person.id, primary_email=email, first_name=first, last_name=last, display_name=f"{first} {last}", source_module="project_management", source_record_type=MARK, status="active")
            people.append(person)
        workspace_names = ["Demo · Product Studio", "Demo · Engineering Delivery", "Demo · Customer Experience", "Demo · Growth & Marketing", "Demo · Enterprise Services", "Demo · Operations & PMO"]
        workspaces = []
        for wi, name in enumerate(workspace_names):
            ws = add(db, m.PMSWorkspace, name=name, organization_id=None)
            workspaces.append(ws)
            workspace_users = people[wi * 36:(wi + 1) * 36]
            for user, role in [(owner, "Owner"), (manager, "Admin"), (client_user, "Guest")] + ([(superuser, "Admin")] if superuser else []) + [(u, "Member") for u in workspace_users]:
                add(db, m.PMSWorkspaceMember, workspace_id=ws.id, user_id=user.id, role=role)
            for j in range(36):
                add(db, m.PMSWorkspaceInvitation, workspace_id=ws.id, email=f"prospect.{wi+1}.{j+1}@pmsdemo.example.com", role=["Member", "Member", "Guest"][j % 3], token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(), status=["pending", "accepted", "revoked"][j % 3], expires_at=NOW + timedelta(days=7 if j % 4 else -2))
        brand = ["Aurora", "Meridian", "Nimbus", "Atlas", "Cobalt", "Saffron", "Evergreen", "Nova", "Prism", "Zenith", "Crescent", "Orbit", "Bluebird", "Horizon", "Summit", "Lumen", "Cedar", "Vertex"]
        sectors = ["Retail", "Healthcare", "Logistics", "Fintech", "Education", "Hospitality", "Manufacturing", "SaaS", "Energy", "Travel", "Media", "Professional Services"]
        initiatives = ["Customer Portal", "Mobile Experience", "Operations Platform", "Analytics Hub", "Commerce Launch", "Partner Onboarding", "Cloud Migration", "Brand Refresh", "Service Desk", "Billing Modernization", "Data Foundation", "Growth Campaign"]
        task_titles = ["Align stakeholders on success measures", "Map the customer journey", "Build the application foundation", "Design the core user experience", "Implement access and permissions", "Connect data and service APIs", "Review accessibility and mobile layouts", "Validate end-to-end workflows", "Prepare customer training materials", "Complete release readiness review", "Improve search and discovery", "Automate the approval workflow", "Measure performance against targets", "Publish the launch communication", "Collect pilot customer feedback", "Resolve priority quality findings", "Document support and escalation", "Rehearse the go-live checklist", "Review operational handover", "Confirm stakeholder sign-off"]
        task_statuses = ["Done", "Done", "In Progress", "In Progress", "In Review", "To Do", "Done", "Blocked", "Backlog", "To Do", "In Review", "Done"]
        status_keys = {"Backlog": "BACKLOG", "To Do": "TODO", "In Progress": "IN_PROGRESS", "In Review": "IN_REVIEW", "Blocked": "BLOCKED", "Done": "DONE"}
        files_root = ROOT / "backend/uploads/pms" / MARK.lower()
        all_tasks = []
        project_ids = []
        flagship = None
        sheet_map = {}
        for pi in range(216):
            team = people[(pi // 36) * 36:(pi // 36 + 1) * 36]
            lead = team[pi % 36]
            title = f"{brand[pi % 18]} {initiatives[(pi // 18) % 12]}"
            customer = add(db, m.PMSClient, name=f"{brand[pi % 18]} {sectors[pi // 18]}", company_name=f"{brand[pi % 18]} {sectors[pi // 18]} Pvt Ltd", email=f"delivery.{pi+1}@customers.pmsdemo.example.com", phone=f"+91 80 4000 {pi+1000:04}", website="https://example.com", notes=f"{MARK}: Synthetic client for delivery demonstrations.")
            status = "Active" if pi % 10 < 6 else ["Planned", "Completed", "Completed", "On Hold"][pi % 10 - 6]
            start = TODAY - timedelta(days=42 + pi % 21)
            due = TODAY + timedelta(days=21 + pi % 50) if status != "Completed" else TODAY - timedelta(days=7 + pi % 14)
            project = add(db, m.PMSProject, project_key=f"DMO{pi+1:04}", name=title, workspace_id=workspaces[pi // 36].id, client_id=customer.id, manager_user_id=manager.id, owner_user_id=owner.id, category=sectors[pi // 18], description=f"{MARK}: Deliver a secure, accessible {initiatives[(pi//18)%12].lower()} with clear milestones, measurable outcomes, and a complete operational handover.", status=status, priority=["High", "Medium", "Medium", "Low", "Critical"][pi % 5], health=["Good", "Good", "At Risk", "Good", "Critical"][pi % 5], start_date=start, planned_start_date=start, due_date=due, planned_end_date=due, actual_start_date=start if status != "Planned" else None, actual_end_date=due if status == "Completed" else None, completed_at=datetime.combine(due, datetime.min.time()) if status == "Completed" else None, budget_amount=250000 + pi * 17500, estimated_cost=180000 + pi * 12000, actual_cost=110000 + pi * 8500, estimated_hours=240 + pi % 40 * 8, progress_percent=100 if status == "Completed" else 30 + pi % 61, is_client_visible=True, billing_status=["Unbilled", "Partially Billed", "Billed"][pi % 3], is_template=False)
            project_ids.append(project.id)
            if flagship is None:
                flagship = project
            for user, role in [(owner, "Admin"), (manager, "Manager"), (client_user, "Client Viewer")] + [(u, "Member") for u in team[pi % 30:pi % 30 + 6]]:
                add(db, m.PMSProjectMember, project_id=project.id, user_id=user.id, role=role, allocation_percent=25 if role == "Member" else 10)
            board = add(db, m.PMSBoard, project_id=project.id, name=f"{title} delivery", board_type="Kanban")
            columns = {s: add(db, m.PMSBoardColumn, board_id=board.id, name=s, status_key=k, position=index, color=["#94a3b8", "#64748b", "#8b5cf6", "#f59e0b", "#ef4444", "#10b981"][index], wip_limit=8 if s in {"In Progress", "In Review"} else None) for index, (s, k) in enumerate(status_keys.items())}
            components = [add(db, m.PMSComponent, project_id=project.id, name=label, description=f"{MARK}: {label} ownership and delivery scope.", lead_user_id=lead.id, default_assignee_user_id=lead.id) for label in ["Experience & Frontend", "Platform & Integrations"]]
            epics = [add(db, m.PMSEpic, project_id=project.id, epic_key=f"{project.project_key}-E{ei+1}", name=label, description=f"{MARK}: Outcome-focused delivery initiative.", owner_user_id=lead.id, status="In Progress", color=["#8b5cf6", "#14b8a6"][ei], start_date=start, end_date=due, target_date=due) for ei, label in enumerate(["Customer experience foundation", "Reliable operations & launch"])]
            release = add(db, m.PMSRelease, project_id=project.id, name="v1.0 Launch", description=f"{MARK}: Production launch scope and readiness.", status=["Planning", "In Progress", "Released"][pi % 3], release_date=due, owner_user_id=manager.id, readiness_percent=45 + pi % 55, launch_notes="Security reviewed; deployment rehearsal and support handover tracked.")
            milestones = [add(db, m.PMSMilestone, project_id=project.id, owner_user_id=lead.id, name=label, description=f"{MARK}: Acceptance criteria and stakeholder approval checkpoint.", status=["Completed", "In Progress", "Not Started"][mi], start_date=start + timedelta(days=mi*14), due_date=start + timedelta(days=(mi+1)*21), completed_at=datetime.combine(start+timedelta(days=21), datetime.min.time()) if mi == 0 else None, progress_percent=[100, 65, 15][mi], client_approval_status=["Approved", "Pending", "Not Required"][mi]) for mi, label in enumerate(["Discovery & design sign-off", "Pilot delivery acceptance", "Launch & operational handover"])]
            sprints = []
            for si, (sname, sstatus, offset) in enumerate([("Foundation", "Completed", -28), ("Delivery", "Active", -3), ("Launch", "Planned", 14)]):
                ss = TODAY + timedelta(days=offset)
                sprints.append(add(db, m.PMSSprint, project_id=project.id, name=f"{project.project_key} · {sname}", goal=f"{MARK}: Ship validated {sname.lower()} outcomes with no unresolved critical defects.", status=sstatus, start_date=ss, end_date=ss+timedelta(days=13), capacity_hours=200, velocity_points=34+pi%15, committed_task_count=4, committed_story_points=24, completed_story_points=24 if si == 0 else 8, started_at=datetime.combine(ss,datetime.min.time()) if si < 2 else None, completed_at=datetime.combine(ss+timedelta(days=13),datetime.min.time()) if si == 0 else None, completed_by_user_id=manager.id if si == 0 else None, review_notes="Acceptance checks passed; team agreed on the next delivery priorities.", retrospective_notes="Keep smaller batches and earlier peer review.", what_went_well="Clear ownership and fast feedback.", what_did_not_go_well="External dependency estimates needed earlier confirmation.", outcome="Accepted" if si == 0 else "In progress"))
            project_tasks = []
            count = 60 if pi == 0 else 12
            for ti in range(count):
                task_status = "Done" if status == "Completed" else task_statuses[ti % 12]
                ts = TODAY - timedelta(days=24-ti%18) if task_status == "Done" else TODAY + timedelta(days=ti%12-5)
                td = ts + timedelta(days=3 + ti%5)
                assignee = team[(pi + ti) % 36]
                sprint = sprints[0 if task_status == "Done" else 2 if task_status in {"Backlog", "To Do"} else 1]
                task = add(db, m.PMSTask, project_id=project.id, board_id=board.id, column_id=columns[task_status].id, milestone_id=milestones[ti%3].id, sprint_id=None if task_status == "Backlog" else sprint.id, epic_id=epics[ti%2].id, epic_key=epics[ti%2].epic_key, component_id=components[ti%2].id, component=components[ti%2].name, release_id=release.id, release_name=release.name, task_key=f"{project.project_key}-{ti+1}", title=task_titles[ti%20] + (f" · phase {ti//20+1}" if ti >= 20 else ""), description=f"{MARK}\nDeliver the agreed scope for {title}. Include evidence, peer review, accessibility checks, and stakeholder acceptance.\nAcceptance: documented outcomes, passing checks, and an accountable owner.", work_type=["Story", "Task", "Bug", "Task"][ti%4], status=task_status, priority=["High", "Medium", "Low", "Medium", "Critical"][ti%5], assignee_user_id=assignee.id if ti%11 else None, reporter_user_id=manager.id, start_date=ts, due_date=td, completed_at=datetime.combine(td,datetime.min.time()) if task_status == "Done" else None, estimated_hours=8+ti%5*4, actual_hours=6+ti%6*2, original_estimate_hours=12+ti%5*4, remaining_estimate_hours=0 if task_status=="Done" else 4+ti%4*2, story_points=[2,3,5,8,13][ti%5], position=ti, rank=ti+1, is_client_visible=True, security_level="Client Visible" if ti%4==0 else "Internal", severity=["S1","S2","S3","S4"][ti%4] if ti%4==2 else None, environment="Staging", fix_version="v1.0", development_branch=f"demo/{project.project_key.lower()}/{ti+1}", development_commits=ti%7, development_prs=ti%3, development_build="Passed" if ti%5 else "Pending", is_blocking=task_status=="Blocked", created_at=NOW-timedelta(days=35-ti%12), updated_at=NOW-timedelta(days=ti%7))
                project_tasks.append(task)
                all_tasks.append(task)
                for ci, line in enumerate(["Confirm acceptance criteria with the owner", "Attach implementation and review evidence", "Complete QA and stakeholder sign-off"]):
                    add(db, m.PMSChecklistItem, task_id=task.id, title=line, is_completed=task_status=="Done" or ci==0, position=ci)
                for ci, body in enumerate(["Scope and acceptance criteria confirmed. Please flag dependencies early so we can keep the delivery on track.", "Review update: implementation evidence is attached. The next checkpoint is on the project calendar."]):
                    comment = add(db, m.PMSComment, project_id=project.id, task_id=task.id, author_user_id=assignee.id if ci else manager.id, body=f"{body}\nDemo discussion for {task.task_key}.", body_format="plain", is_internal=ci==0, created_at=NOW-timedelta(days=7-ci, hours=ti%6))
                    if ci == 1 and ti < 2:
                        add(db, m.PMSMention, project_id=project.id, task_id=task.id, comment_id=comment.id, mentioned_user_id=lead.id, mentioned_by_user_id=manager.id, read_at=NOW if pi%2 else None)
                for action, days_ago, old, new in [("task.created", 30, None, "To Do"), ("status.changed", 15, "To Do", task_status)]:
                    add(db, m.PMSActivity, project_id=project.id, task_id=task.id, sprint_id=sprint.id, actor_user_id=assignee.id, action=action, entity_type="task", entity_id=task.id, summary=f"{task.task_key}: {task.title}", metadata_json=json.dumps({"field":"status","old_value":old,"new_value":new}), created_at=NOW-timedelta(days=days_ago, hours=ti%8))
                key = (assignee.id, 0 if ti%2 else 1)
                if key not in sheet_map:
                    week = WEEK-timedelta(weeks=key[1])
                    sheet_map[key] = add(db, m.PMSTimesheet, user_id=assignee.id, week_start_date=week, status=["draft","submitted","approved","rejected"][assignee.id%4], submitted_at=NOW-timedelta(days=2) if assignee.id%4 else None, approved_by_user_id=manager.id if assignee.id%4==2 else None, approved_at=NOW-timedelta(days=1) if assignee.id%4==2 else None, rejection_reason="Add the acceptance evidence before resubmitting." if assignee.id%4==3 else None)
                log_day = sheet_map[key].week_start_date+timedelta(days=ti%5)
                add(db, m.PMSTimeLog, timesheet_id=sheet_map[key].id, user_id=assignee.id, project_id=project.id, task_id=task.id, log_date=log_day, duration_minutes=60+ti%6*30, description=f"{MARK}: {task.title} — implementation, review, and delivery coordination.", is_billable=ti%4!=0, approval_status=["Pending","Approved","Approved"][ti%3], approved_by_user_id=manager.id if ti%3 else None, approved_at=NOW if ti%3 else None)
                if ti < 2:
                    add(db, m.PMSDevLink, task_id=task.id, provider="github", link_type=["pull_request", "commit"][ti], external_id=f"{MARK}-{pi}-{ti}", title=f"{task.task_key}: Delivery review", url=f"https://example.com/demo/{project.project_key}/reviews/{ti+1}", status="merged" if task_status=="Done" else "open", author=assignee.email.split("@")[0], metadata_json=json.dumps({"demo":True,"source":MARK}))
            for di in range(2):
                add(db, m.PMSTaskDependency, task_id=project_tasks[di+3].id, depends_on_task_id=project_tasks[di].id, dependency_type="Finish To Start", lag_days=1)
            for ri in range(2):
                probability, impact = 2+(pi+ri)%4, 2+(pi*2+ri)%4
                add(db, m.PMSRisk, project_id=project.id, linked_task_id=project_tasks[ri+3].id, title=["External API readiness may affect pilot dates", "Stakeholder availability may delay acceptance"][ri], description=f"{MARK}: Track assumptions, exposure, and the accountable owner.", category=["Technical","Delivery"][ri], probability=probability, impact=impact, risk_score=probability*impact, status=["open","mitigating","closed"][pi%3], owner_user_id=lead.id, mitigation_plan="Confirm dependencies weekly, maintain a fallback path, and escalate changes within one business day.", contingency_plan="Re-sequence non-dependent work and use the approved pilot fallback.", due_date=TODAY+timedelta(days=7+ri*7))
            add(db, m.PMSClientApproval, project_id=project.id, milestone_id=milestones[1].id, requested_by_user_id=manager.id, client_user_id=client_user.id, status=["Pending","Approved","Rejected"][pi%3], remarks="Demo acceptance review with documented criteria and delivery evidence.", decided_at=NOW-timedelta(days=1) if pi%3 else None)
            add(db, m.PMSProjectIntake, title=f"{title} · next phase", description=f"{MARK}: Request discovery, estimates, and a phased delivery proposal.", requester_user_id=lead.id, requester_name=f"{first_names[pi%18]} {last_names[pi//18]}", requester_email=lead.email, client_id=customer.id, client_name=customer.name, priority=["High","Medium","Low"][pi%3], desired_start_date=TODAY+timedelta(days=14), desired_due_date=TODAY+timedelta(days=75), budget_amount=300000+pi*5000, status=["submitted","approved","rejected"][pi%3], reviewed_by_user_id=manager.id if pi%3 else None, reviewed_at=NOW if pi%3 else None, review_notes="Capacity and commercial scope reviewed." if pi%3 else None, created_project_id=project.id if pi%3==1 else None)
            add(db, m.PMSSprintRetroActionItem, sprint_id=sprints[0].id, title="Bring dependency confirmation into sprint planning", owner_user_id=lead.id, due_date=TODAY+timedelta(days=5), created_task_id=project_tasks[0].id, status=["Open","In Progress","Completed"][pi%3])
            add(db, m.PMSSavedFilter, project_id=project.id, user_id=owner.id, name=f"{project.project_key} · Team delivery view", view_type="list", entity_type="task", query="status != Done", filters_json=json.dumps({"status":"In Progress"}), sort_json=json.dumps({"field":"due_date","direction":"asc"}), columns_json=json.dumps(["task_key","title","status","assignee","due_date"]), visibility="workspace", is_shared=True)
            add(db, m.PMSDevIntegration, project_id=project.id, provider="github", repo_owner="pms-demo", repo_name=project.project_key.lower(), is_active=False)
            project_files = files_root / project.project_key
            project_files.mkdir(parents=True, exist_ok=True)
            for fi, file_title in enumerate(["delivery-brief", "acceptance-checklist"]):
                content = f"{MARK}\n{title}\n{file_title.replace('-', ' ').title()}\n\nClient: {customer.company_name}\nOwner: {lead.email}\nMilestone: {milestones[fi].name}\n\nDemo deliverable: Confirm requirements, review outcomes, and attach approval evidence.\n"
                path = project_files / f"{file_title}.txt"
                path.write_text(content, encoding="utf-8")
                add(db, m.PMSFileAsset, project_id=project.id, task_id=project_tasks[fi].id, milestone_id=milestones[fi].id, uploaded_by_user_id=lead.id, file_name=path.name, original_name=f"{project.project_key}-{path.name}", mime_type="text/plain", size_bytes=path.stat().st_size, storage_path=str(path.resolve()), version_number=1+pi%3, visibility="Client Visible" if fi else "Project Team")
            if pi % 36 == 0:
                print(f"Prepared projects {pi+1}/216", flush=True)
        for index, person in enumerate(people):
            for offset in range(2):
                add(db, m.PMSUserCapacity, user_id=person.id, week_start_date=WEEK-timedelta(weeks=offset), capacity_hours=[32,36,40,40,40][index%5])
            tag = add(db, m.PMSTag, name=f"Demo · {sectors[index//18]} · {brand[index%18]}", color=["#8b5cf6","#14b8a6","#f59e0b","#3b82f6"][index%4])
            for task in all_tasks[index::216]:
                add(db, m.PMSTaskTag, task_id=task.id, tag_id=tag.id)
        owner_sheet = add(db, m.PMSTimesheet, user_id=owner.id, week_start_date=WEEK, status="draft")
        for day in range(5):
            add(db, m.PMSTimeLog, timesheet_id=owner_sheet.id, user_id=owner.id, project_id=flagship.id, task_id=all_tasks[day].id, log_date=WEEK+timedelta(days=day), duration_minutes=120+day*30, description=f"{MARK}: PMO review, delivery planning, and stakeholder coordination.", is_billable=False, approval_status="Pending")
        db.commit()
        # Count actual rows created by this run rather than reporting a requested target.
        manifest = {"namespace":MARK,"created_at":NOW.isoformat(),"counts":dict(sorted(counts.items())),"total_records":sum(counts.values()),"workspace_ids":[w.id for w in workspaces],"project_ids":project_ids,"flagship_project_id":flagship.id,"flagship_task_id":all_tasks[0].id,"flagship_sprint_id":all_tasks[0].sprint_id,"owner_user_id":owner.id,"created_ids":dict(ids),"record_count_scope":"Records added by this seed; existing data is preserved.","demo_member_login":{"email":people[0].email,"password":"DemoPMS@2026"}}
    MANIFEST.parent.mkdir(parents=True,exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    public = {k:v for k,v in manifest.items() if k not in {"created_ids","demo_member_login"}}
    (OUTPUT / "data-summary.json").write_text(json.dumps(public,indent=2),encoding="utf-8")
    print(json.dumps({"status":"seeded","total_records":manifest["total_records"],"counts":manifest["counts"],"manifest":str(MANIFEST)},indent=2))


if __name__ == "__main__":
    main()
